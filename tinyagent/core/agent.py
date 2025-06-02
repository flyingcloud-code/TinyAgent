"""
TinyAgent Core Agent Implementation

This module contains the main TinyAgent class that wraps the openai-agents SDK
and provides a simplified interface for creating and running agents with MCP tools.
"""

import logging
import os
import atexit
import warnings
import asyncio
import json
import time
from datetime import datetime
from typing import Optional, List, Any, Dict, AsyncIterator, Iterator
from pathlib import Path

# Suppress aiohttp resource warnings that can occur with LiteLLM
warnings.filterwarnings("ignore", message="Unclosed client session")
warnings.filterwarnings("ignore", message="Unclosed connector")
warnings.filterwarnings("ignore", category=ResourceWarning, module="aiohttp")
warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed transport")

# Configure asyncio logging to suppress connection cleanup errors
asyncio_logger = logging.getLogger('asyncio')
# Add a filter to suppress specific messages
class AsyncioConnectionFilter(logging.Filter):
    def filter(self, record):
        if record.levelno == logging.ERROR:
            message = record.getMessage()
            if any(phrase in message for phrase in [
                "Unclosed client session", "Unclosed connector", 
                "unclosed transport", "Event loop is closed",
                "I/O operation on closed pipe"
            ]):
                return False
        return True

asyncio_logger.addFilter(AsyncioConnectionFilter())

try:
    from agents import Agent, Runner, ModelSettings, set_default_openai_client, set_default_openai_api, set_tracing_disabled
    from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
    from agents.extensions.models.litellm_model import LitellmModel
    from openai import AsyncOpenAI
    AGENTS_AVAILABLE = True
    LITELLM_AVAILABLE = True
    
    # Disable tracing completely using the proper method
    set_tracing_disabled(True)
    
except ImportError as e:
    logging.warning(f"OpenAI Agents SDK not available: {e}")
    AGENTS_AVAILABLE = False
    LITELLM_AVAILABLE = False
    LitellmModel = None
    Agent = None
    Runner = None

from ..core.config import TinyAgentConfig, get_config
from ..mcp.manager import MCPServerManager
from ..core.logging import (
    get_logger, log_user, log_agent, log_tool, log_technical, 
    MCPToolMetrics, USER_LEVEL, AGENT_LEVEL, TOOL_LEVEL
)

# Get the enhanced logger
enhanced_logger = get_logger()
logger = logging.getLogger(__name__)

# Global list to track OpenAI clients for cleanup
_openai_clients = []
_active_servers = []

# Global counters for MCP tool call tracking
_tool_call_stats = {
    'total_calls': 0,
    'successful_calls': 0,
    'failed_calls': 0,
    'total_duration': 0.0
}

def _cleanup_clients():
    """Cleanup function to close all OpenAI clients and MCP servers"""
    import asyncio
    
    try:
        # Try to get current event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
        except RuntimeError:
            # Create new event loop for cleanup
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        async def _close_all():
            # Close OpenAI clients
            for client in _openai_clients:
                try:
                    await client.close()
                except Exception:
                    pass
            
            # Close MCP servers
            for server in _active_servers:
                try:
                    if hasattr(server, 'close'):
                        await server.close()
                except Exception:
                    pass
        
        if not loop.is_closed():
            loop.run_until_complete(_close_all())
            
        # Clear lists
        _openai_clients.clear()
        _active_servers.clear()
        
    except Exception:
        # Ignore all cleanup errors
        pass

# Register cleanup function to run at exit
atexit.register(_cleanup_clients)

def log_tool_call_stats():
    """Log summary statistics of MCP tool calls using enhanced logging"""
    if _tool_call_stats['total_calls'] > 0:
        avg_duration = _tool_call_stats['total_duration'] / _tool_call_stats['total_calls']
        success_rate = (_tool_call_stats['successful_calls'] / _tool_call_stats['total_calls']) * 100
        
        # User-friendly summary
        log_tool(f"Tool calls completed: {_tool_call_stats['total_calls']} "
                f"({success_rate:.1f}% success rate)")
        
        # Technical details to file
        log_technical("info", f"=== MCP Tool Call Summary ===")
        log_technical("info", f"Total tool calls: {_tool_call_stats['total_calls']}")
        log_technical("info", f"Successful calls: {_tool_call_stats['successful_calls']}")
        log_technical("info", f"Failed calls: {_tool_call_stats['failed_calls']}")
        log_technical("info", f"Success rate: {success_rate:.1f}%")
        log_technical("info", f"Average call duration: {avg_duration:.2f}s")
        log_technical("info", f"Total tool execution time: {_tool_call_stats['total_duration']:.2f}s")
        log_technical("info", f"=== End Summary ===")
    else:
        log_technical("info", "No MCP tool calls were made during this run")

# Add a simple result wrapper class after the imports
class SimpleResult:
    """Simple result wrapper for compatibility with final_output attribute access"""
    def __init__(self, output: str):
        self.final_output = output

class MCPToolCallLogger:
    """Custom wrapper to log MCP tool calls using enhanced logging"""
    
    def __init__(self, original_agent, server_name_map=None, use_streaming=True):
        self.original_agent = original_agent
        self.server_name_map = server_name_map or {}
        self.call_count = 0
        self.use_streaming = use_streaming
        
    def __getattr__(self, name):
        """Delegate all attributes to the original agent"""
        return getattr(self.original_agent, name)
    
    async def run(self, input_data, **kwargs):
        """Override run method to log tool calls with enhanced logging"""
        log_agent("Starting task execution...")
        log_technical("info", f"Agent run started with input: {str(input_data)[:200]}...")
        start_time = time.time()
        
        try:
            if self.use_streaming:
                # Use streaming API with tool call logging
                result = await self._run_with_tool_logging(input_data, **kwargs)
            else:
                # Use non-streaming API
                result = await Runner.run(
                    starting_agent=self.original_agent,
                    input=input_data,
                    **kwargs
                )
            
            duration = time.time() - start_time
            log_agent(f"Task completed successfully in {duration:.1f}s")
            log_technical("info", f"Agent run completed in {duration:.2f}s")
            
            # Log final statistics
            log_tool_call_stats()
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            log_user(f"[ERROR] Task failed: {str(e)}")
            log_technical("error", f"Agent run failed after 0.00s: {e}")
            
            # Log final statistics even on failure
            log_tool_call_stats()
            
            raise
    
    async def _run_with_tool_logging(self, input_data, **kwargs):
        """Run the agent with tool call interception using enhanced logging"""
        # We'll use the streaming API to capture tool calls
        
        # Filter out parameters that Runner.run_streamed doesn't accept
        filtered_kwargs = {}
        supported_params = ['max_turns', 'response_format', 'temperature', 'max_tokens']
        for key, value in kwargs.items():
            if key in supported_params:
                filtered_kwargs[key] = value
        
        result = Runner.run_streamed(
            starting_agent=self.original_agent,
            input=input_data,
            **filtered_kwargs
        )
        
        tool_call_sequence = 0
        current_tool_call_start = None
        current_tool_info = {}  # Store current tool call details
        collected_responses = []  # Collect all agent responses
        
        async for event in result.stream_events():
            # Ignore raw response events
            if event.type == "raw_response_event":
                continue
            elif event.type == "run_item_stream_event":
                if event.item.type == "tool_call_item":
                    # Tool call started
                    tool_call_sequence += 1
                    current_tool_call_start = time.time()
                    
                    # Extract tool details
                    tool_name = "unknown"
                    server_name = "unknown"
                    tool_input = "N/A"
                    
                    try:
                        # Try to extract tool name and input from the item
                        if hasattr(event.item, 'tool_call'):
                            tool_call = event.item.tool_call
                            if hasattr(tool_call, 'function'):
                                tool_name = tool_call.function.name
                                if hasattr(tool_call.function, 'arguments'):
                                    tool_input = tool_call.function.arguments
                                    # Truncate long inputs for logging
                                    if len(tool_input) > 200:
                                        tool_input = tool_input[:200] + "... (truncated)"
                        
                        # Try to infer server name from tool name or other attributes
                        if 'filesystem' in tool_name.lower() or 'file' in tool_name.lower():
                            server_name = "filesystem"
                        elif 'search' in tool_name.lower() or 'google' in tool_name.lower():
                            server_name = "my-search"
                        elif 'thinking' in tool_name.lower() or 'sequential' in tool_name.lower():
                            server_name = "sequential-thinking"
                        
                    except Exception as e:
                        log_technical("debug", f"Error extracting tool details: {e}")
                    
                    # Store current tool info for completion logging
                    current_tool_info = {
                        'tool_name': tool_name,
                        'server_name': server_name,
                        'input': tool_input,
                        'sequence': tool_call_sequence
                    }
                    
                    log_tool(f"Starting tool call #{tool_call_sequence}: {server_name}.{tool_name}")
                    
                    # Log technical details to file
                    log_technical("info", f"=== Tool Call [{tool_call_sequence}] Started ===")
                    log_technical("info", f"    Server: {server_name}")
                    log_technical("info", f"    Tool: {tool_name}")
                    log_technical("info", f"    Input: {tool_input}")
                    
                    try:
                        item_str = str(event.item)
                        if len(item_str) > 500:
                            item_str = item_str[:500] + "..."
                        log_technical("debug", f"    Raw Item: {item_str}")
                    except Exception:
                        log_technical("debug", f"    Raw Item: [Unable to display]")
                    
                    # Update global stats
                    _tool_call_stats['total_calls'] += 1
                    
                elif event.item.type == "tool_call_output_item":
                    # Tool call completed
                    duration = 0.0
                    if current_tool_call_start:
                        duration = time.time() - current_tool_call_start
                        current_tool_call_start = None
                    
                    # Get tool info from current call
                    tool_name = current_tool_info.get('tool_name', 'unknown')
                    server_name = current_tool_info.get('server_name', 'unknown')
                    sequence = current_tool_info.get('sequence', tool_call_sequence)
                    
                    # Extract output safely
                    output_content = "N/A"
                    output_size = 0
                    error_message = None
                    
                    try:
                        if hasattr(event.item, 'output'):
                            output_content = str(event.item.output)
                            output_size = len(output_content)
                            # Keep more detail for file logs, truncate for console
                            if len(output_content) > 1000:
                                truncated_output = output_content[:1000] + "... (truncated)"
                            else:
                                truncated_output = output_content
                        
                        # Check for errors
                        if hasattr(event.item, 'error') and event.item.error:
                            error_message = str(event.item.error)
                            
                    except Exception as e:
                        output_content = f"[Error extracting output: {e}]"
                        truncated_output = output_content
                    
                    # Determine success
                    is_success = error_message is None
                    
                    # Log tool call completion with enhanced logging
                    status = "[OK]" if is_success else "[FAIL]"
                    log_tool(f"Tool call #{sequence}: {server_name}.{tool_name} {status} ({duration:.2f}s)")
                    
                    # Log technical details to file
                    log_technical("info", f"=== Tool Call [{sequence}] Completed ===")
                    log_technical("info", f"    Server: {server_name}")
                    log_technical("info", f"    Tool: {tool_name}")
                    log_technical("info", f"    Duration: {duration:.2f}s")
                    log_technical("info", f"    Success: {is_success}")
                    log_technical("info", f"    Output Size: {output_size} characters")
                    
                    if error_message:
                        log_technical("error", f"    Error: {error_message}")
                    
                    # Log output (truncated for readability)
                    if len(output_content) > 2000:
                        log_technical("info", f"    Output: {output_content[:2000]}... (truncated, full size: {output_size} chars)")
                    else:
                        log_technical("info", f"    Output: {output_content}")
                    
                    log_technical("info", f"=== End Tool Call [{sequence}] ===")
                    
                    # Log structured metrics
                    MCPToolMetrics.log_tool_call(
                        server_name=server_name,
                        tool_name=tool_name,
                        duration=duration,
                        success=is_success,
                        output_size=output_size
                    )
                    
                    # Update global stats
                    if is_success:
                        _tool_call_stats['successful_calls'] += 1
                    else:
                        _tool_call_stats['failed_calls'] += 1
                    
                    _tool_call_stats['total_duration'] += duration
                    
                    # Clear current tool info
                    current_tool_info = {}
                    
                elif event.item.type == "message_output_item":
                    # Message output - collect for final result
                    try:
                        from agents import ItemHelpers
                        message_text = ItemHelpers.text_message_output(event.item)
                        if message_text and len(message_text.strip()) > 0:
                            # Collect the full response for returning to user
                            collected_responses.append(message_text)
                            
                            # Log abbreviated version for context
                            if len(message_text) > 300:
                                abbreviated = message_text[:300] + "..."
                                log_agent(f"Agent reasoning: {abbreviated}")
                            else:
                                log_agent(f"Agent reasoning: {message_text}")
                                
                            log_technical("debug", f"Full agent response: {message_text}")
                    except Exception:
                        log_technical("debug", "Agent generated a response")
                        
        # Try to get the final result from the stream
        try:
            final_result = await result.result()
            return final_result
        except AttributeError:
            # If streaming API doesn't have result() method, use collected responses
            if collected_responses:
                # Combine all collected responses
                full_response = "\n\n".join(collected_responses)
                log_technical("info", "Using collected responses as final result")
                return SimpleResult(full_response)
            else:
                log_technical("warning", "No responses collected from streaming API")
                return SimpleResult("Task completed successfully with MCP tools")
        except Exception as e:
            # Handle any other issues with result extraction
            if collected_responses:
                # Use collected responses as fallback
                full_response = "\n\n".join(collected_responses)
                log_technical("warning", f"Error extracting final result: {e}, using collected responses")
                return SimpleResult(full_response)
            else:
                log_technical("warning", f"Error extracting final result: {e}, returning success indicator")
                return SimpleResult("Task completed successfully with MCP tools")

class TinyAgent:
    """
    TinyAgent - A multi-step agent framework with MCP tool integration.
    
    This class wraps the openai-agents SDK and provides a simplified interface
    for creating agents with MCP (Model Context Protocol) tool support.
    Supports both OpenAI models and third-party models via LiteLLM.
    """
    
    def __init__(
        self,
        config: Optional[TinyAgentConfig] = None,
        instructions: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        use_streaming: Optional[bool] = None
    ):
        """
        Initialize TinyAgent.
        
        Args:
            config: Complete TinyAgent configuration (uses default if None)
            instructions: Custom instructions for the agent
            model_name: Model to use (overrides config)
            api_key: OpenAI API key (overrides environment)
            use_streaming: Whether to use streaming API for tool call logging (default: from config)
        """
        if not AGENTS_AVAILABLE:
            raise ImportError("OpenAI Agents SDK is required but not available")
        
        # Load configuration
        if config is None:
            config = get_config()
        
        self.config = config
        # Use provided use_streaming, otherwise use config value
        self.use_streaming = use_streaming if use_streaming is not None else config.agent.use_streaming
        self.logger = logging.getLogger(__name__)
        
        # Set up API key
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        
        # Validate API key
        api_key_env = config.llm.api_key_env
        if not os.getenv(api_key_env):
            raise ValueError(f"API key not found in environment variable: {api_key_env}")
        
        # Load instructions
        self.instructions = self._load_instructions(instructions)
        
        # Set up model
        self.model_name = model_name or config.llm.model
        
        # Initialize MCP manager
        enabled_servers = [
            server for server in config.mcp.servers.values() 
            if server.enabled
        ]
        self.mcp_manager = MCPServerManager(enabled_servers)
        
        # Persistent connection management
        self._persistent_connections = {}  # server_name -> connection
        self._connection_status = {}       # server_name -> status
        self._connections_initialized = False
        
        # Create the agent (delayed creation)
        self._agent = None
        
        # Reset global stats for this agent instance
        global _tool_call_stats
        _tool_call_stats = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'total_duration': 0.0
        }
        
        log_technical("info", f"TinyAgent initialized with {len(enabled_servers)} MCP servers (streaming: {self.use_streaming})")
        log_agent("Agent ready for tasks")
    
    def _should_use_litellm(self, model_name: str) -> bool:
        """
        Check if a model should use LiteLLM based on its name/prefix.
        
        Args:
            model_name: Name of the model to check
            
        Returns:
            True if the model should use LiteLLM, False for standard OpenAI client
        """
        if not LITELLM_AVAILABLE:
            return False
            
        # Third-party model prefixes that require LiteLLM
        third_party_prefixes = [
            'google/', 'anthropic/', 'claude-', 'gemini-',
            'deepseek/', 'mistral/', 'meta/', 'cohere/',
            'replicate/', 'together/', 'ai21/', 'bedrock/',
            'azure/', 'vertex_ai/', 'palm/'
        ]
        
        # Check if model name starts with any third-party prefix
        return any(model_name.startswith(prefix) for prefix in third_party_prefixes)
    
    def _create_model_instance(self, model_name: str) -> Any:
        """
        Create appropriate model instance based on model name.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Model instance (LitellmModel for third-party, string for OpenAI)
        """
        if self._should_use_litellm(model_name):
            if not LITELLM_AVAILABLE:
                raise ImportError(
                    f"Model '{model_name}' requires LiteLLM support, but LitellmModel is not available. "
                    "Please install with: pip install 'openai-agents[litellm]'"
                )
            
            # Get API key for this model
            api_key = os.getenv(self.config.llm.api_key_env)
            if not api_key:
                raise ValueError(f"API key not found in environment variable: {self.config.llm.api_key_env}")
            
            # For OpenRouter models, ensure proper format
            formatted_model_name = model_name
            if self.config.llm.base_url and "openrouter.ai" in self.config.llm.base_url:
                # For OpenRouter, always add openrouter/ prefix unless already present
                if not model_name.startswith("openrouter/"):
                    formatted_model_name = f"openrouter/{model_name}"
            
            # Create LitellmModel instance with only supported parameters
            litellm_kwargs = {
                "model": formatted_model_name,
                "api_key": api_key,
            }
            
            # Add base_url if configured (for OpenRouter, etc.)
            if self.config.llm.base_url:
                litellm_kwargs["base_url"] = self.config.llm.base_url
            
            log_technical("info", f"Creating LitellmModel for third-party model: {formatted_model_name}")
            return LitellmModel(**litellm_kwargs)
        else:
            # Use standard OpenAI model (string)
            log_technical("info", f"Using standard OpenAI model: {model_name}")
            return model_name
    
    def _load_instructions(self, custom_instructions: Optional[str] = None) -> str:
        """
        Load agent instructions from file or use custom instructions.
        
        Args:
            custom_instructions: Custom instructions to use instead of file
            
        Returns:
            Agent instructions string
        """
        if custom_instructions:
            return custom_instructions
        
        # Try to load from configured instructions file
        if self.config.agent.instructions_file:
            instructions_path = Path(self.config.agent.instructions_file)
            
            # Try relative to current working directory first
            if not instructions_path.exists():
                # Try relative to tinyagent package
                package_dir = Path(__file__).parent.parent
                instructions_path = package_dir / self.config.agent.instructions_file
            
            if instructions_path.exists():
                try:
                    return instructions_path.read_text(encoding='utf-8')
                except Exception as e:
                    log_technical("warning", f"Failed to load instructions from {instructions_path}: {e}")
        
        # Fallback to default instructions
        default_instructions_path = Path(__file__).parent.parent / "prompts" / "default_instructions.txt"
        if default_instructions_path.exists():
            try:
                return default_instructions_path.read_text(encoding='utf-8')
            except Exception as e:
                log_technical("warning", f"Failed to load default instructions: {e}")
        
        # Ultimate fallback
        return "You are TinyAgent, an intelligent assistant that can help with various tasks using available tools."
    
    def _create_agent(self) -> Agent:
        """
        Create the underlying openai-agents Agent instance.
        
        Returns:
            Configured Agent instance
        """
        try:
            # Set to use Chat Completions API instead of Responses API
            set_default_openai_api("chat_completions")
            
            # Get API key from environment
            api_key = os.getenv(self.config.llm.api_key_env)
            if not api_key:
                raise ValueError(f"API key not found in environment variable: {self.config.llm.api_key_env}")
            
            # Create appropriate model instance (LitellmModel or string)
            model_instance = self._create_model_instance(self.model_name)
            
            # Initialize custom client reference
            self._custom_client = None
            
            # Set up custom OpenAI client if base_url is configured (for OpenAI models)
            # Note: For LiteLLM models, base_url is handled by LitellmModel itself
            if self.config.llm.base_url and not self._should_use_litellm(self.model_name):
                self._custom_client = AsyncOpenAI(
                    api_key=api_key,
                    base_url=self.config.llm.base_url
                )
                set_default_openai_client(self._custom_client)
                
                # Add to global cleanup list
                global _openai_clients
                _openai_clients.append(self._custom_client)
                
                self.logger.info(f"Using custom OpenAI client with base_url: {self.config.llm.base_url}")
            
            # Create model settings with temperature (only for non-LiteLLM models)
            model_settings = None
            if not self._should_use_litellm(self.model_name):
                model_settings = ModelSettings(temperature=self.config.llm.temperature)
            
            # Create agent WITHOUT MCP servers initially (lazy loading approach)
            # MCP servers will be added dynamically when needed
            agent_kwargs = {
                "name": self.config.agent.name,
                "instructions": self.instructions,
                "model": model_instance
                # Note: no mcp_servers here - we'll add them dynamically
            }
            
            # Add model_settings only for non-LiteLLM models
            if model_settings is not None:
                agent_kwargs["model_settings"] = model_settings
            
            agent = Agent(**agent_kwargs)
            
            model_type = "LiteLLM" if self._should_use_litellm(self.model_name) else "OpenAI"
            self.logger.info(f"Created agent '{self.config.agent.name}' with {model_type} model '{self.model_name}' (MCP servers will be added dynamically)")
            return agent
            
        except Exception as e:
            self.logger.error(f"Failed to create agent: {e}")
            # Create basic agent without MCP servers as fallback
            try:
                # Try to create with just model name for fallback (always use string for fallback)
                agent = Agent(
                    name=self.config.agent.name,
                    instructions=self.instructions,
                    model=self.model_name if not self._should_use_litellm(self.model_name) else "gpt-3.5-turbo"
                )
                self.logger.warning("Created fallback agent without MCP servers")
                return agent
            except Exception as e2:
                self.logger.error(f"Failed to create fallback agent: {e2}")
                raise
    
    def _get_model_kwargs(self) -> Dict[str, Any]:
        """
        Get model-specific kwargs for API calls.
        
        Returns:
            Dictionary of model kwargs
        """
        kwargs = {
            'temperature': self.config.llm.temperature,
            'timeout': 60.0  # Increase timeout to 60 seconds
        }
        
        # Add API key based on config
        api_key = os.getenv(self.config.llm.api_key_env)
        if api_key:
            kwargs['api_key'] = api_key
        
        # Add base URL if configured and using LiteLLM
        if self.config.llm.base_url and self._should_use_litellm(self.model_name):
            kwargs['base_url'] = self.config.llm.base_url
        
        return kwargs
    
    def get_agent(self) -> Agent:
        """
        Get the underlying Agent instance, creating it if necessary.
        
        Returns:
            Agent instance
        """
        if self._agent is None:
            self._agent = self._create_agent()
        return self._agent
    
    async def run(self, message: str, **kwargs) -> Any:
        """
        Run the agent with a message.
        
        Args:
            message: Input message for the agent
            **kwargs: Additional arguments passed to Runner.run
            
        Returns:
            Agent execution result
        """
        try:
            # First, try without MCP tools for simple conversations
            # This provides fast response for basic interactions
            log_technical("info", f"Running agent with message: {message[:100]}...")
            
            # Check if message likely needs tools (simple heuristic)
            needs_tools = self._message_likely_needs_tools(message)
            
            if not needs_tools:
                # Try simple conversation without MCP tools first
                log_technical("info", "Attempting simple conversation without MCP tools")
                try:
                    simple_agent = self._create_simple_agent()
                    
                    # Filter out parameters that Runner.run doesn't accept
                    filtered_kwargs = {}
                    supported_params = ['max_turns', 'response_format', 'temperature', 'max_tokens']
                    for key, value in kwargs.items():
                        if key in supported_params:
                            filtered_kwargs[key] = value
                    
                    result = await Runner.run(
                        starting_agent=simple_agent,
                        input=message,
                        **filtered_kwargs
                    )
                    log_technical("info", "Simple conversation completed successfully")
                    return result
                except Exception as e:
                    log_technical("info", f"Simple conversation failed: {e}, falling back to MCP mode")
                    # Fall through to MCP mode
            else:
                log_technical("info", "Message likely needs tools, using MCP mode")
            
            # Use MCP tools (lazy loading)
            return await self._run_with_mcp_tools(message, **kwargs)
            
        except Exception as e:
            log_technical("error", f"Agent execution failed: {e}")
            raise

    def _message_likely_needs_tools(self, message: str) -> bool:
        """
        Simple heuristic to determine if a message likely needs MCP tools.
        
        Args:
            message: Input message to analyze
            
        Returns:
            True if tools are likely needed, False for simple conversation
        """
        message_lower = message.lower()
        
        # Keywords that typically require tools
        tool_keywords = [
            'file', 'write', 'read', 'create', 'save', 'open', 'edit',
            'search', 'find', 'analyze', 'fetch', 'download', 'upload',
            'think', 'plan', 'step', 'break down', 'sequential',
            'document', 'report', 'generate', 'build', 'make'
        ]
        
        # Check for tool-related keywords
        for keyword in tool_keywords:
            if keyword in message_lower:
                return True
        
        # Simple conversation indicators
        simple_patterns = [
            'hello', 'hi', 'how are you', 'what can you do', 
            'introduce yourself', 'who are you', 'help', 'quit', 'exit'
        ]
        
        for pattern in simple_patterns:
            if pattern in message_lower:
                return False
        
        # Default to not needing tools for short, simple messages
        return len(message.split()) > 10

    def _create_simple_agent(self) -> Agent:
        """
        Create a simple agent without MCP servers for basic conversations.
        
        Returns:
            Agent instance without MCP tools
        """
        try:
            # Create model instance
            model_instance = self._create_model_instance(self.model_name)
            
            # Create agent without MCP servers
            agent_kwargs = {
                "name": self.config.agent.name,
                "instructions": self.instructions,
                "model": model_instance
                # Note: no mcp_servers parameter
            }
            
            # Add model_settings only for non-LiteLLM models
            if not self._should_use_litellm(self.model_name):
                from agents import ModelSettings
                agent_kwargs["model_settings"] = ModelSettings(temperature=self.config.llm.temperature)
            
            return Agent(**agent_kwargs)
            
        except Exception as e:
            log_technical("error", f"Failed to create simple agent: {e}")
            raise

    async def _run_with_mcp_tools(self, message: str, **kwargs) -> Any:
        """
        Run agent with MCP tools (lazy loading).
        
        Args:
            message: Input message
            **kwargs: Additional arguments
            
        Returns:
            Agent execution result
        """
        try:
            # Ensure MCP connections (lazy loading)
            connected_servers = await self._ensure_mcp_connections()
            
            if not connected_servers:
                # No MCP servers available, use simple agent
                log_agent("No MCP servers available, running without tools")
                log_technical("info", "No MCP servers connected, falling back to simple mode")
                
                simple_agent = self._create_simple_agent()
                result = await Runner.run(
                    starting_agent=simple_agent,
                    input=message,
                    **kwargs
                )
                return result
            else:
                # Use MCP-enabled agent
                log_tool(f"Using MCP tools: {len(connected_servers)} servers available")
                
                # Create MCP-enabled agent
                agent = Agent(
                    name=self.config.agent.name,
                    instructions=self.instructions,
                    model=self._create_model_instance(self.model_name),
                    mcp_servers=connected_servers
                )
                
                # Wrap with tool call logger
                logged_agent = MCPToolCallLogger(agent, use_streaming=self.use_streaming)
                
                # Run with MCP tools
                result = await logged_agent.run(message, **kwargs)
                return result
                
        except Exception as e:
            log_technical("error", f"Error running with MCP tools: {e}")
            raise

    async def _ensure_mcp_connections(self) -> List[Any]:
        """
        Ensure MCP connections are established (lazy loading).
        Only connects when actually needed and reuses existing connections.
        
        Returns:
            List of connected MCP server instances
        """
        if self._connections_initialized:
            # Return cached connections
            return list(self._persistent_connections.values())
        
        log_technical("info", "Initializing MCP connections (lazy loading)")
        start_time = time.time()
        
        # Get server configs
        enabled_servers = [
            server for server in self.mcp_manager.server_configs 
            if server.enabled
        ]
        
        if not enabled_servers:
            log_technical("info", "No MCP servers to connect")
            self._connections_initialized = True
            return []
        
        # Connect to each server
        for server_config in enabled_servers:
            try:
                log_agent(f"Connecting to MCP server: {server_config.name}")
                log_technical("info", f"Attempting to connect to MCP server: {server_config.name}")
                
                # Create server instance
                server_instance = self._create_server_instance(server_config)
                if not server_instance:
                    continue
                
                # Connect with timeout
                log_technical("info", f"Using 120s timeout for MCP server connection: {server_config.name}")
                await asyncio.wait_for(server_instance.connect(), timeout=120.0)
                
                # Store successful connection
                self._persistent_connections[server_config.name] = server_instance
                self._connection_status[server_config.name] = "connected"
                
                log_agent(f"Connected to {server_config.name}")
                log_technical("info", f"Successfully connected to MCP server: {server_config.name}")
                
                # Add to global cleanup list
                _active_servers.append(server_instance)
                
            except asyncio.TimeoutError:
                log_agent(f"Connection timeout for {server_config.name}")
                log_technical("warning", f"MCP server {server_config.name} connection timed out")
                self._connection_status[server_config.name] = "timeout"
                continue
            except Exception as e:
                log_agent(f"Connection failed for {server_config.name}: {str(e)}")
                log_technical("error", f"Failed to connect to MCP server {server_config.name}: {e}")
                self._connection_status[server_config.name] = "failed"
                continue
        
        self._connections_initialized = True
        connected_count = len(self._persistent_connections)
        duration = time.time() - start_time
        
        log_technical("info", f"MCP connection initialization completed: {connected_count}/{len(enabled_servers)} servers in {duration:.2f}s")
        
        if connected_count > 0:
            log_tool(f"MCP servers ready: {connected_count} servers available")
        
        return list(self._persistent_connections.values())
    
    def _check_connection_health(self, server_name: str) -> bool:
        """Check if a connection is still healthy"""
        if server_name not in self._persistent_connections:
            return False
        
        connection = self._persistent_connections[server_name]
        # Basic health check - can be enhanced with ping/heartbeat
        return hasattr(connection, '_stream') and connection._stream and not connection._stream.closed
    
    async def _reconnect_if_needed(self, server_name: str) -> bool:
        """Reconnect a server if the connection is unhealthy"""
        if self._check_connection_health(server_name):
            return True
        
        log_technical("info", f"Reconnecting unhealthy MCP server: {server_name}")
        
        # Find server config
        server_config = None
        for config in self.mcp_manager.server_configs:
            if config.name == server_name:
                server_config = config
                break
        
        if not server_config:
            return False
        
        try:
            # Create new instance and connect
            server_instance = self._create_server_instance(server_config)
            if server_instance:
                await asyncio.wait_for(server_instance.connect(), timeout=60.0)
                self._persistent_connections[server_name] = server_instance
                self._connection_status[server_name] = "connected"
                log_technical("info", f"Successfully reconnected to MCP server: {server_name}")
                return True
        except Exception as e:
            log_technical("error", f"Failed to reconnect to MCP server {server_name}: {e}")
            self._connection_status[server_name] = "failed"
        
        return False

    def _create_server_instance(self, server_config):
        """
        创建MCP服务器实例（不连接）
        
        Args:
            server_config: MCP服务器配置
            
        Returns:
            MCP服务器实例
        """
        from agents.mcp import MCPServerStdio, MCPServerSse, MCPServerStreamableHttp
        
        try:
            if server_config.type == "stdio":
                # For stdio servers, increase timeout for npx package downloads
                stdio_params = {
                    "command": server_config.command,
                    "args": server_config.args or [],
                    "env": server_config.env or {}
                }
                
                return MCPServerStdio(
                    name=server_config.name,
                    params=stdio_params
                )
                
            elif server_config.type == "sse":
                # 构建SSE服务器参数
                sse_params = {
                    "url": server_config.url,
                    "headers": server_config.headers or {}
                }
                
                # 添加超时参数
                if server_config.timeout is not None:
                    sse_params["timeout"] = server_config.timeout
                else:
                    sse_params["timeout"] = 60  # 增加到60秒超时
                    
                if server_config.sse_read_timeout is not None:
                    sse_params["sse_read_timeout"] = server_config.sse_read_timeout
                else:
                    sse_params["sse_read_timeout"] = 120  # 增加到120秒SSE读取超时
                
                return MCPServerSse(
                    name=server_config.name,
                    params=sse_params
                )
                
            elif server_config.type == "http":
                # 增加HTTP超时
                http_params = {
                    "url": server_config.url,
                    "headers": server_config.headers or {}
                }
                
                if server_config.timeout is not None:
                    http_params["timeout"] = server_config.timeout
                else:
                    http_params["timeout"] = 60  # 增加到60秒超时
                
                return MCPServerStreamableHttp(
                    name=server_config.name,
                    params=http_params
                )
            else:
                raise ValueError(f"Unknown server type: {server_config.type}")
                
        except Exception as e:
            log_technical("error", f"Failed to create MCP server {server_config.name}: {e}")
            return None
    
    def run_sync(self, message: str, **kwargs) -> Any:
        """
        Run the agent synchronously.
        
        Args:
            message: Input message for the agent
            **kwargs: Additional arguments passed to Runner.run_sync
            
        Returns:
            Agent execution result
        """
        try:
            # Always use async method for new architecture
            # Check if we have any configured MCP servers
            has_mcp_servers = len(self.mcp_manager.server_configs) > 0
            
            if has_mcp_servers:
                # Use async method for potential MCP operations
                try:
                    # Try to get current event loop
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If in already running event loop, create new thread
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(self._run_in_new_loop, message, **kwargs)
                            return future.result()
                    else:
                        # If event loop not running, run directly
                        return loop.run_until_complete(self.run(message, **kwargs))
                except RuntimeError:
                    # No event loop, create new one
                    return asyncio.run(self.run(message, **kwargs))
            else:
                # No MCP servers configured, can use simple sync method
                simple_agent = self._create_simple_agent()
                log_technical("info", f"Running agent synchronously with message: {message[:100]}...")
                
                result = Runner.run_sync(
                    starting_agent=simple_agent,
                    input=message,
                    **kwargs
                )
                
                log_technical("info", "Agent execution completed successfully")
                return result
            
        except Exception as e:
            log_technical("error", f"Agent execution failed: {e}")
            raise
    
    def _run_in_new_loop(self, message: str, **kwargs) -> Any:
        """
        在新的事件循环中运行异步方法的辅助函数
        
        Args:
            message: 输入消息
            **kwargs: 传递给run的额外参数
            
        Returns:
            Agent执行结果
        """
        return asyncio.run(self.run(message, **kwargs))
    
    def get_mcp_server_info(self) -> List[Dict[str, Any]]:
        """
        Get information about configured MCP servers.
        
        Returns:
            List of server information dictionaries
        """
        server_info = self.mcp_manager.get_server_info()
        return [
            {
                'name': info.name,
                'type': info.type,
                'status': info.status,
                'config': info.config
            }
            for info in server_info
        ]
    
    def get_available_tools(self) -> List[str]:
        """
        Get list of available tools from MCP servers.
        
        Returns:
            List of tool names
        """
        # This would require connecting to servers and listing tools
        # For now, return server names as a proxy
        return [info.name for info in self.mcp_manager.get_server_info()]
    
    def reload_mcp_servers(self):
        """
        Reload MCP servers from configuration.
        """
        log_technical("info", "Reloading MCP servers")
        
        # Close existing connections
        if self._persistent_connections:
            log_technical("info", "Closing existing MCP connections for reload")
            # Note: This is sync method, should use async close in production
            self.reset_mcp_connections()
        
        # Reinitialize server manager
        config = get_config()
        enabled_servers = [
            server for server in config.mcp.servers.values() 
            if server.enabled
        ]
        self.mcp_manager = MCPServerManager(enabled_servers)
        
        # Reset connection state for lazy loading
        self._persistent_connections.clear()
        self._connection_status.clear()
        self._connections_initialized = False
        
        # Recreate agent with new servers
        self._agent = None  # Force recreation on next access
        
        log_technical("info", f"Reloaded {len(enabled_servers)} MCP server configurations")
        log_technical("info", "MCP connections will be established on next tool use")
    
    def __repr__(self) -> str:
        connected_servers = len(self._persistent_connections) if self._connections_initialized else len(self.mcp_manager.server_configs)
        return f"TinyAgent(name='{self.config.agent.name}', model='{self.model_name}', mcp_servers={connected_servers})"

    def get_mcp_connection_status(self) -> Dict[str, str]:
        """
        Get the status of all MCP connections.
        
        Returns:
            Dictionary mapping server names to their connection status
        """
        return dict(self._connection_status)
    
    def get_active_mcp_servers(self) -> List[str]:
        """
        Get list of currently active MCP server names.
        
        Returns:
            List of active server names
        """
        return [name for name, status in self._connection_status.items() if status == "connected"]
    
    async def close_mcp_connections(self):
        """Close all MCP connections and clean up resources."""
        if not self._persistent_connections:
            return
        
        log_technical("info", "Closing all MCP connections")
        
        for server_name, connection in self._persistent_connections.items():
            try:
                await connection.close()
                log_technical("debug", f"Closed MCP connection: {server_name}")
            except Exception as e:
                log_technical("warning", f"Error closing MCP connection {server_name}: {e}")
        
        self._persistent_connections.clear()
        self._connection_status.clear()
        self._connections_initialized = False
        
        log_technical("info", "All MCP connections closed")
    
    def reset_mcp_connections(self):
        """Reset MCP connection state (for debugging/testing)."""
        self._persistent_connections.clear()
        self._connection_status.clear()
        self._connections_initialized = False
        log_technical("info", "MCP connection state reset")

    async def run_stream(self, message: str, **kwargs) -> AsyncIterator[str]:
        """
        Run the agent with streaming output.
        
        Args:
            message: Input message for the agent
            **kwargs: Additional arguments passed to Runner.run
            
        Yields:
            String chunks as they are generated
        """
        try:
            # Check if message likely needs tools
            needs_tools = self._message_likely_needs_tools(message)
            
            if not needs_tools:
                # Try simple conversation without MCP tools first - streaming
                log_technical("debug", "Attempting streaming without MCP tools")
                
                from litellm import acompletion
                import json
                
                # Create a simple streaming request
                try:
                    # Use the same model formatting logic as _create_model_instance
                    formatted_model_name = self.model_name
                    if self.config.llm.base_url and "openrouter.ai" in self.config.llm.base_url:
                        # For OpenRouter, always add openrouter/ prefix unless already present
                        if not self.model_name.startswith("openrouter/"):
                            formatted_model_name = f"openrouter/{self.model_name}"
                    
                    log_technical("debug", f"Using formatted model name for streaming: {formatted_model_name}")
                    
                    stream_response = await acompletion(
                        model=formatted_model_name,
                        messages=[
                            {"role": "system", "content": self.instructions},
                            {"role": "user", "content": message}
                        ],
                        stream=True,
                        **self._get_model_kwargs()
                    )
                    
                    log_technical("info", "Streaming response started")
                    
                    async for chunk in stream_response:
                        if chunk.choices and chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            yield content
                    
                    log_technical("info", "Streaming response completed")
                    return
                    
                except Exception as e:
                    log_technical("warning", f"Streaming without tools failed: {e}")
                    # Fall through to MCP tool version
            
            # If simple streaming failed or tools needed, use MCP tools
            await self._ensure_mcp_connections()
            
            # Get the agent with MCP tools
            agent = self.get_agent()
            
            # Use streaming API with MCP tools
            result = Runner.run_streamed(
                starting_agent=agent,
                input=message,
                **kwargs
            )
            
            collected_content = ""
            log_technical("info", "Starting MCP streaming response")
            
            async for event in result.stream_events():
                if event.type == "run_item_stream_event":
                    if event.item.type == "message_output_item":
                        try:
                            # Try to access content attribute safely
                            if hasattr(event.item, 'content') and event.item.content:
                                for content_part in event.item.content:
                                    if hasattr(content_part, 'text'):
                                        chunk_text = content_part.text
                                        collected_content += chunk_text
                                        yield chunk_text
                                    elif hasattr(content_part, 'content') and content_part.content:
                                        chunk_text = str(content_part.content)
                                        collected_content += chunk_text
                                        yield chunk_text
                            elif hasattr(event.item, 'text'):
                                # Fallback: try to access text directly
                                chunk_text = event.item.text
                                collected_content += chunk_text
                                yield chunk_text
                            else:
                                # Ultimate fallback: convert the entire item to string
                                chunk_text = str(event.item)
                                if len(chunk_text) > 0 and chunk_text != str(event.item.__class__):
                                    collected_content += chunk_text
                                    yield chunk_text
                        except Exception as content_error:
                            log_technical("warning", f"Error accessing message content: {content_error}")
                            # Try alternative access methods
                            try:
                                from agents import ItemHelpers
                                message_text = ItemHelpers.text_message_output(event.item)
                                if message_text:
                                    collected_content += message_text
                                    yield message_text
                            except Exception as helper_error:
                                log_technical("debug", f"ItemHelpers also failed: {helper_error}")
                                continue
            
            if not collected_content:
                # Fallback if no streaming content was captured
                final_result = await result.get_final_result()
                if hasattr(final_result, 'final_output'):
                    yield final_result.final_output
                else:
                    yield str(final_result)
            
            log_technical("info", f"MCP streaming completed, total chars: {len(collected_content)}")
            
        except Exception as e:
            log_technical("error", f"Streaming run failed: {e}")
            yield f"[ERROR] {str(e)}"


    def run_stream_sync(self, message: str, **kwargs) -> Iterator[str]:
        """
        Run the agent with streaming output (synchronous wrapper).
        
        Args:
            message: Input message for the agent
            **kwargs: Additional arguments
            
        Yields:
            String chunks as they are generated
        """
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, we need to create a new task
                import threading
                import queue
                import time
                
                result_queue = queue.Queue()
                exception_queue = queue.Queue()
                
                def run_in_thread():
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        
                        async def collect_stream():
                            async for chunk in self.run_stream(message, **kwargs):
                                result_queue.put(('chunk', chunk))
                            result_queue.put(('done', None))
                        
                        new_loop.run_until_complete(collect_stream())
                        new_loop.close()
                    except Exception as e:
                        exception_queue.put(e)
                        result_queue.put(('error', str(e)))
                
                thread = threading.Thread(target=run_in_thread)
                thread.start()
                
                while True:
                    try:
                        item_type, content = result_queue.get(timeout=1)
                        if item_type == 'chunk':
                            yield content
                        elif item_type == 'done':
                            break
                        elif item_type == 'error':
                            if not exception_queue.empty():
                                raise exception_queue.get()
                            break
                    except queue.Empty:
                        if not thread.is_alive():
                            break
                        continue
                
                thread.join()
            else:
                # No event loop running, we can run directly
                async def collect_stream():
                    async for chunk in self.run_stream(message, **kwargs):
                        yield chunk
                
                # Run the async generator synchronously
                gen = collect_stream()
                try:
                    while True:
                        chunk = loop.run_until_complete(gen.__anext__())
                        yield chunk
                except StopAsyncIteration:
                    pass
                    
        except Exception as e:
            log_technical("error", f"Sync streaming failed: {e}")
            yield f"[ERROR] {str(e)}"

def create_agent(
    name: Optional[str] = None,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None
) -> TinyAgent:
    """
    Factory function to create a TinyAgent instance.
    
    Args:
        name: Agent name (uses config default if None)
        instructions: Custom instructions
        model: Model name to use
        api_key: OpenAI API key
        
    Returns:
        Configured TinyAgent instance
    """
    config = get_config()
    if name:
        config.agent.name = name
    
    return TinyAgent(
        config=config,
        instructions=instructions,
        model_name=model,
        api_key=api_key
    ) 