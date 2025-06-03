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

# Import intelligence components
try:
    from ..intelligence import IntelligentAgent, IntelligentAgentConfig
    INTELLIGENCE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Intelligence components not available: {e}")
    INTELLIGENCE_AVAILABLE = False
    IntelligentAgent = None
    IntelligentAgentConfig = None

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
    
    def _infer_server_name(self, tool_name: str, event_item) -> str:
        """Infer server name from tool name and event item attributes"""
        # Method 1: Try to get server name from event item attributes
        try:
            if hasattr(event_item, 'server_name'):
                return event_item.server_name
            elif hasattr(event_item, 'mcp_server'):
                return getattr(event_item.mcp_server, 'name', 'unknown')
            elif hasattr(event_item, 'tool_call') and hasattr(event_item.tool_call, 'server'):
                return event_item.tool_call.server
        except Exception:
            pass
        
        # Method 2: Infer from tool name patterns
        tool_name_lower = tool_name.lower()
        
        # Filesystem patterns
        if any(pattern in tool_name_lower for pattern in ['filesystem', 'file', 'read', 'write', 'create', 'delete', 'list']):
            return "filesystem"
        
        # Search patterns  
        elif any(pattern in tool_name_lower for pattern in ['search', 'google', 'web', 'fetch', 'get_web']):
            return "my-search"
        
        # Sequential thinking patterns
        elif any(pattern in tool_name_lower for pattern in ['thinking', 'sequential', 'think']):
            return "sequential-thinking"
        
        # Fetch patterns
        elif any(pattern in tool_name_lower for pattern in ['fetch', 'http', 'request', 'url']):
            return "fetch"
        
        # Method 3: Check if server name is in our server mapping
        if self.server_name_map:
            for server_name in self.server_name_map.keys():
                if server_name.lower() in tool_name_lower:
                    return server_name
        
        return "unknown"
    
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
        collected_responses = []
        
        async for event in result.stream_events():
            # Ignore raw response events
            if event.type == "raw_response_event":
                continue
            elif event.type == "run_item_stream_event":
                if event.item.type == "tool_call_item":
                    # Tool call started
                    tool_call_sequence += 1
                    current_tool_call_start = time.time()
                    
                    # Extract tool details with improved robustness
                    tool_name = "unknown"
                    server_name = "unknown"
                    tool_input = "N/A"
                    
                    try:
                        # Log the raw item structure for debugging
                        log_technical("info", f"Tool call item type: {type(event.item)}")
                        log_technical("info", f"Tool call item attributes: {dir(event.item)}")
                        
                        # Method 1: Try to extract from raw_item (most likely to work)
                        if hasattr(event.item, 'raw_item') and event.item.raw_item:
                            raw_item = event.item.raw_item
                            log_technical("info", f"Found raw_item: {type(raw_item)}")
                            log_technical("info", f"Raw item attributes: {dir(raw_item)}")
                            
                            # Try to extract function name from raw_item
                            if hasattr(raw_item, 'function') and raw_item.function:
                                tool_name = raw_item.function.name or "unknown"
                                if hasattr(raw_item.function, 'arguments') and raw_item.function.arguments:
                                    tool_input = str(raw_item.function.arguments)
                                    # Truncate long inputs for logging
                                    if len(tool_input) > 200:
                                        tool_input = tool_input[:200] + "... (truncated)"
                                log_technical("info", f"Extracted from raw_item.function.name: {tool_name}")
                            elif hasattr(raw_item, 'name'):
                                tool_name = raw_item.name or "unknown"
                                log_technical("info", f"Extracted from raw_item.name: {tool_name}")
                            elif hasattr(raw_item, 'tool_call') and raw_item.tool_call:
                                tool_call = raw_item.tool_call
                                if hasattr(tool_call, 'function') and tool_call.function:
                                    tool_name = tool_call.function.name or "unknown"
                                    log_technical("info", f"Extracted from raw_item.tool_call.function.name: {tool_name}")
                        
                        # Method 2: Try to extract from tool_call attribute (fallback)
                        elif hasattr(event.item, 'tool_call') and event.item.tool_call:
                            tool_call = event.item.tool_call
                            log_technical("info", f"Found tool_call: {type(tool_call)}")
                            
                            if hasattr(tool_call, 'function') and tool_call.function:
                                tool_name = tool_call.function.name or "unknown"
                                if hasattr(tool_call.function, 'arguments') and tool_call.function.arguments:
                                    tool_input = str(tool_call.function.arguments)
                                    # Truncate long inputs for logging
                                    if len(tool_input) > 200:
                                        tool_input = tool_input[:200] + "... (truncated)"
                            elif hasattr(tool_call, 'name'):
                                tool_name = tool_call.name or "unknown"
                            
                        # Method 3: Try to extract from other possible attributes
                        elif hasattr(event.item, 'function_name'):
                            tool_name = event.item.function_name or "unknown"
                        elif hasattr(event.item, 'name'):
                            tool_name = event.item.name or "unknown"
                        elif hasattr(event.item, 'tool_name'):
                            tool_name = event.item.tool_name or "unknown"
                        
                        # Log what we found
                        log_technical("info", f"Final extracted tool name: {tool_name}")
                        
                        # Try to infer server name from tool name or other attributes
                        server_name = self._infer_server_name(tool_name, event.item)
                        log_technical("info", f"Inferred server name: {server_name}")
                        
                    except Exception as e:
                        log_technical("info", f"Error extracting tool details: {e}")
                        # Try to get string representation for debugging
                        try:
                            item_str = str(event.item)
                            if len(item_str) > 300:
                                item_str = item_str[:300] + "..."
                            log_technical("info", f"Tool call item string: {item_str}")
                        except:
                            log_technical("info", "Could not get string representation of tool call item")
                    
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
                        # Try ItemHelpers before falling back to raw object
                        try:
                            from agents import ItemHelpers
                            message_text = ItemHelpers.text_message_output(event.item)
                            if message_text and len(message_text.strip()) > 0:
                                collected_responses.append(message_text)
                                
                                # Log abbreviated version for context
                                if len(message_text) > 300:
                                    abbreviated = message_text[:300] + "..."
                                    log_agent(f"Agent reasoning: {abbreviated}")
                                else:
                                    log_agent(f"Agent reasoning: {message_text}")
                                    
                                log_technical("debug", f"Full agent response: {message_text[:500]}...")
                            else:
                                log_technical("warning", f"ItemHelpers returned empty text for message_output_item")
                                collected_responses.append("[Agent response received but text extraction failed]")
                        except Exception as helper_error:
                            log_technical("warning", f"ItemHelpers failed: {helper_error}")
                            collected_responses.append("[Error: Unable to extract response text - please check logs]")
                        
                    except Exception as extract_error:
                        log_technical("warning", f"Error processing message output item: {extract_error}")
                        # Still log that we got a response
                        log_technical("debug", "Agent generated a response (text extraction failed)")
                        
        # Try to get the final result from the stream
        try:
            final_result = await result.result()
            log_technical("info", "Successfully obtained final result from stream")
            return final_result
        except AttributeError:
            log_technical("info", "Stream doesn't have result() method, using collected responses")
            # If streaming API doesn't have result() method, use collected responses
            if collected_responses:
                # Combine all collected responses
                full_response = "\n\n".join(collected_responses)
                log_technical("info", f"Using collected responses as final result: {len(full_response)} chars")
                return SimpleResult(full_response)
            else:
                log_technical("warning", "No responses collected from streaming API")
                return SimpleResult("Task completed successfully with MCP tools")
        except Exception as e:
            log_technical("warning", f"Error extracting final result: {e}")
            # Handle any other issues with result extraction
            if collected_responses:
                # Use collected responses as fallback
                full_response = "\n\n".join(collected_responses)
                log_technical("warning", f"Using collected responses as fallback: {len(full_response)} chars")
                return SimpleResult(full_response)
            else:
                log_technical("warning", "No collected responses available, returning success indicator")
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
        use_streaming: Optional[bool] = None,
        intelligent_mode: Optional[bool] = None
    ):
        """
        Initialize TinyAgent.
        
        Args:
            config: Complete TinyAgent configuration (uses default if None)
            instructions: Custom instructions for the agent
            model_name: Model to use (overrides config)
            api_key: OpenAI API key (overrides environment)
            use_streaming: Whether to use streaming API for tool call logging (default: from config)
            intelligent_mode: Whether to use intelligent ReAct mode (default: from config or True if available)
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
        
        # Set up intelligent mode
        self.intelligent_mode = intelligent_mode
        if self.intelligent_mode is None:
            # Check if intelligence components are available and enabled in config
            self.intelligent_mode = (INTELLIGENCE_AVAILABLE and 
                                   getattr(config.agent, 'intelligent_mode', True))
        
        # Initialize intelligent agent if available and enabled
        self._intelligent_agent = None
        if self.intelligent_mode and INTELLIGENCE_AVAILABLE:
            log_technical("info", "Intelligent mode enabled - will initialize IntelligentAgent")
        elif not INTELLIGENCE_AVAILABLE:
            log_technical("warning", "Intelligence components not available - using basic LLM mode")
            self.intelligent_mode = False
        
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
        
        mode_info = "intelligent" if self.intelligent_mode else "basic"
        log_technical("info", f"TinyAgent initialized in {mode_info} mode with {len(enabled_servers)} MCP servers (streaming: {self.use_streaming})")
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
        If MCP connections are already established, returns an agent with MCP servers.
        
        Returns:
            Agent instance (with MCP servers if available)
        """
        # If MCP connections are initialized and we have connected servers,
        # return an MCP-enabled agent
        if self._connections_initialized and self._persistent_connections:
            log_technical("info", f"Returning MCP-enabled agent with {len(self._persistent_connections)} servers")
            
            # Create agent with MCP servers
            mcp_agent = Agent(
                name=self.config.agent.name,
                instructions=self.instructions,
                model=self._create_model_instance(self.model_name),
                mcp_servers=list(self._persistent_connections.values())
            )
            
            # Add model_settings if needed
            if not self._should_use_litellm(self.model_name):
                from agents import ModelSettings
                mcp_agent.model_settings = ModelSettings(temperature=self.config.llm.temperature)
            
            return mcp_agent
        
        # Otherwise, return simple agent (or create if needed)
        if self._agent is None:
            self._agent = self._create_agent()
        return self._agent
    
    async def get_agent_with_mcp(self) -> Agent:
        """
        Get the Agent instance with MCP servers connected.
        
        Returns:
            Agent instance with MCP servers
        """
        # Ensure MCP connections are established
        connected_servers = await self._ensure_mcp_connections()
        
        if not connected_servers:
            # No MCP servers available, return simple agent
            return self.get_agent()
        
        # Create MCP-enabled agent
        mcp_agent = Agent(
            name=self.config.agent.name,
            instructions=self.instructions,
            model=self._create_model_instance(self.model_name),
            mcp_servers=connected_servers
        )
        
        return mcp_agent
    
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
            log_technical("info", f"Running agent with message: {message[:100]}...")
            
            # Check if intelligent mode is enabled
            if self.intelligent_mode and INTELLIGENCE_AVAILABLE:
                log_technical("info", "Using intelligent mode with ReAct loop")
                return await self._run_intelligent_mode(message, **kwargs)
            else:
                log_technical("info", "Using basic LLM mode")
                return await self._run_basic_mode(message, **kwargs)
            
        except Exception as e:
            log_technical("error", f"Agent execution failed: {e}")
            raise
    
    async def _run_intelligent_mode(self, message: str, **kwargs) -> Any:
        """
        Run the agent in intelligent mode using IntelligentAgent with ReAct loop
        
        Args:
            message: Input message for the agent
            **kwargs: Additional arguments
            
        Returns:
            Intelligent agent execution result
        """
        try:
            # Get the intelligent agent
            intelligent_agent = self._get_intelligent_agent()
            if not intelligent_agent:
                log_technical("warning", "IntelligentAgent not available, falling back to basic mode")
                return await self._run_basic_mode(message, **kwargs)
            
            # Register MCP tools with the intelligent agent if available
            await self._register_mcp_tools_with_intelligent_agent(intelligent_agent)
            
            # Execute using intelligent agent with full ReAct loop
            log_agent("Starting intelligent task execution with ReAct loop...")
            result = await intelligent_agent.run(message, context=kwargs)
            
            # Log intelligent execution results
            if isinstance(result, dict) and 'success' in result:
                success = result.get('success', False)
                iterations = result.get('reasoning', {}).get('iterations', 0)
                tools_used = result.get('tools_used', [])
                execution_time = result.get('execution_time', 0)
                
                log_agent(f"Task completed: success={success}, iterations={iterations}, "
                         f"tools={len(tools_used)}, time={execution_time:.1f}s")
                log_technical("info", f"Intelligent execution result: {result}")
                
                # Return the answer for compatibility
                return SimpleResult(result.get('answer', 'Task completed successfully'))
            else:
                # Fallback if result format is unexpected
                return result
                
        except Exception as e:
            log_technical("error", f"Intelligent mode execution failed: {e}")
            # Fallback to basic mode on error
            log_agent("Falling back to basic mode due to intelligent mode error")
            return await self._run_basic_mode(message, **kwargs)
    
    async def _run_basic_mode(self, message: str, **kwargs) -> Any:
        """
        Run the agent in basic mode (original implementation)
        
        Args:
            message: Input message for the agent  
            **kwargs: Additional arguments
            
        Returns:
            Basic agent execution result
        """
        # First, try without MCP tools for simple conversations
        # This provides fast response for basic interactions
        
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
    
    async def _register_mcp_tools_with_intelligent_agent(self, intelligent_agent):
        """
        Register available MCP tools with the IntelligentAgent using EnhancedMCPServerManager
        
        Args:
            intelligent_agent: The IntelligentAgent instance
        """
        try:
            # Use enhanced MCP manager to get tool information with caching
            if hasattr(self, 'mcp_manager') and self.mcp_manager:
                # Check if it's the enhanced manager
                if hasattr(self.mcp_manager, 'initialize_with_caching'):
                    log_technical("info", "Using EnhancedMCPServerManager for tool registration")
                    
                    # Check if tools are already cached to avoid redundant initialization
                    cached_tools = None
                    if hasattr(self.mcp_manager, 'tool_cache') and self.mcp_manager.tool_cache:
                        # Try to get from cache first
                        cache_stats = self.mcp_manager.tool_cache.get_cache_stats()
                        if cache_stats.get('valid_caches', 0) > 0:
                            log_technical("info", f"Using cached tools: {cache_stats['total_tools_cached']} tools from {cache_stats['total_servers_cached']} servers")
                            # Use cached tools directly
                            cached_tools = {}
                            for server_name in self.config.mcp.servers.keys():
                                cached_server_tools = self.mcp_manager.tool_cache.get_cached_tools(server_name)
                                if cached_server_tools:
                                    cached_tools[server_name] = cached_server_tools
                    
                    # If no valid cache, initialize with caching (but limit logging)
                    if not cached_tools:
                        log_technical("info", "No valid cache found, initializing MCP servers...")
                        # Temporarily suppress repetitive tool discovery logs
                        filesystem_logger = logging.getLogger('agents.mcp')
                        cache_logger = logging.getLogger('tinyagent.mcp.cache')
                        old_filesystem_level = filesystem_logger.level
                        old_cache_level = cache_logger.level
                        
                        # Suppress INFO/DEBUG messages during initialization
                        filesystem_logger.setLevel(logging.WARNING)
                        cache_logger.setLevel(logging.WARNING)
                        
                        try:
                            cached_tools = await self.mcp_manager.initialize_with_caching()
                        finally:
                            # Restore original levels
                            filesystem_logger.setLevel(old_filesystem_level)
                            cache_logger.setLevel(old_cache_level)
                    
                    # Get all tools from cache
                    all_tools = []
                    total_servers = 0
                    if cached_tools:
                        for server_name, tool_list in cached_tools.items():
                            if tool_list:
                                total_servers += 1
                                # Convert ToolInfo objects to dictionary format for intelligent agent
                                for tool_info in tool_list:
                                    tool_dict = {
                                        'name': tool_info.name,
                                        'description': tool_info.description,
                                        'server': tool_info.server_name,
                                        'category': tool_info.category,
                                        'performance_metrics': tool_info.performance_metrics.__dict__ if tool_info.performance_metrics else {},
                                        'last_updated': tool_info.last_updated.isoformat() if tool_info.last_updated else None,
                                        'schema': tool_info.schema,
                                        'function': None  # Will be handled by MCP execution
                                    }
                                    all_tools.append(tool_dict)
                    
                    # Register tools with intelligent agent (only if we have tools and they're not already registered)
                    if all_tools:
                        # Check if tools are already registered to avoid duplicate registration
                        if not hasattr(intelligent_agent, '_mcp_tools_registered') or not intelligent_agent._mcp_tools_registered:
                            intelligent_agent.register_mcp_tools(all_tools)
                            # Don't set the flag here - let register_mcp_tools handle it internally
                            log_technical("info", f"Enhanced registration: {len(all_tools)} tools from {total_servers} servers")
                            log_agent(f"Registered {len(all_tools)} MCP tools with enhanced context")
                        else:
                            log_technical("debug", f"Tools already registered, skipping duplicate registration")
                        
                        # Build enhanced tool context using context builder (only if not already built)
                        if (hasattr(intelligent_agent, 'mcp_context_builder') and 
                            intelligent_agent.mcp_context_builder and 
                            not getattr(intelligent_agent, '_tool_context_cache_valid', False)):
                            
                            try:
                                # Build comprehensive tool context
                                tool_context = intelligent_agent.mcp_context_builder.build_tool_context()
                                
                                if tool_context and tool_context.available_tools:
                                    log_technical("info", f"Built enhanced tool context with {len(tool_context.available_tools)} tools")
                                    
                                    # Store context for future use in ReAct loop
                                    intelligent_agent._current_tool_context = tool_context
                                    intelligent_agent._tool_context_cache_valid = True
                                    
                                    # Log context summary (limited)
                                    log_technical("debug", f"Tool context servers: {list(tool_context.server_status.keys())}")
                                    log_technical("debug", f"Tool capabilities: {list(tool_context.capabilities_summary.keys())}")
                                
                                else:
                                    log_technical("warning", "Tool context built but no tools available")
                                
                            except Exception as context_error:
                                log_technical("warning", f"Error building enhanced tool context: {context_error}")
                        else:
                            log_technical("debug", "Tool context already built or context builder not available")
                        
                    else:
                        log_technical("info", "No enhanced tools available to register")
                        log_agent("No MCP tools available for enhanced registration")
                else:
                    # Fall back to basic manager functionality
                    log_technical("warning", "MCP manager is not enhanced, using basic registration")
                    await self._register_mcp_tools_basic(intelligent_agent)
                
            else:
                # No MCP manager available
                log_technical("warning", "Enhanced MCP manager not available, using basic registration")
                await self._register_mcp_tools_basic(intelligent_agent)
                
        except Exception as e:
            log_technical("error", f"Error in enhanced MCP tool registration: {e}")
            # Don't log full traceback unless in debug mode
            if logger.level <= logging.DEBUG:
                import traceback
                log_technical("debug", f"Enhanced registration traceback: {traceback.format_exc()}")
            
            # Fallback to basic registration
            log_technical("info", "Falling back to basic tool registration")
            try:
                await self._register_mcp_tools_basic(intelligent_agent)
            except Exception as fallback_error:
                log_technical("error", f"Fallback registration also failed: {fallback_error}")

    async def _register_mcp_tools_basic(self, intelligent_agent):
        """
        Basic MCP tool registration (fallback method)
        
        Args:
            intelligent_agent: The IntelligentAgent instance
        """
        try:
            # Ensure MCP connections are established
            connected_servers = await self._ensure_mcp_connections()
            
            if not connected_servers:
                log_technical("info", "No MCP servers available for basic registration")
                return
            
            # Collect all available tools from connected servers
            mcp_tools = []
            for server_name, connection in self._persistent_connections.items():
                try:
                    # Get tools from the connection
                    if hasattr(connection, 'list_tools'):
                        server_tools = await connection.list_tools()
                        if hasattr(server_tools, 'tools'):
                            for tool in server_tools.tools:
                                mcp_tools.append({
                                    'name': tool.name,
                                    'description': tool.description or f"Tool from {server_name}",
                                    'server': server_name,
                                    'function': None  # Will be handled by MCP execution
                                })
                        else:
                            log_technical("warning", f"Server {server_name} tools response format unexpected")
                    else:
                        log_technical("warning", f"Server {server_name} does not support list_tools")
                except Exception as e:
                    log_technical("warning", f"Error getting tools from {server_name}: {e}")
                    continue
            
            # Register tools with intelligent agent
            if mcp_tools:
                intelligent_agent.register_mcp_tools(mcp_tools)
                log_technical("info", f"Basic registration: {len(mcp_tools)} MCP tools")
            else:
                log_technical("info", "No MCP tools available to register")
                
        except Exception as e:
            log_technical("error", f"Error in basic MCP tool registration: {e}")

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
            # Get API key from environment
            api_key = os.getenv(self.config.llm.api_key_env)
            if not api_key:
                raise ValueError(f"API key not found in environment variable: {self.config.llm.api_key_env}")
            
            # Create model instance
            model_instance = self._create_model_instance(self.model_name)
            
            # Set up custom OpenAI client if base_url is configured (for OpenRouter, etc.)
            # Note: For LiteLLM models, base_url is handled by LitellmModel itself
            if self.config.llm.base_url and not self._should_use_litellm(self.model_name):
                # Clear any conflicting environment variable that might override our configuration
                original_base_url = os.environ.get('OPENAI_BASE_URL')
                if original_base_url and original_base_url != self.config.llm.base_url:
                    log_technical("warning", f"Environment OPENAI_BASE_URL ({original_base_url}) conflicts with config base_url ({self.config.llm.base_url}), using config")
                    # Temporarily clear the environment variable
                    os.environ.pop('OPENAI_BASE_URL', None)
                
                try:
                    custom_client = AsyncOpenAI(
                        api_key=api_key,
                        base_url=self.config.llm.base_url
                    )
                    set_default_openai_client(custom_client)
                    
                    # Add to global cleanup list
                    global _openai_clients
                    _openai_clients.append(custom_client)
                    
                    log_technical("info", f"Simple agent using custom OpenAI client with base_url: {self.config.llm.base_url}")
                finally:
                    # Restore the original environment variable if it existed
                    if original_base_url:
                        os.environ['OPENAI_BASE_URL'] = original_base_url
            
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
            
            agent = Agent(**agent_kwargs)
            
            model_type = "LiteLLM" if self._should_use_litellm(self.model_name) else "OpenAI"
            log_technical("info", f"Created simple agent with {model_type} model '{self.model_name}' (no MCP servers)")
            
            return agent
            
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
        This is a synchronous version that returns cached tools if available.
        
        Returns:
            List of tool names
        """
        tools = []
        
        # Try to get tools from enhanced MCP manager cache if available
        if (hasattr(self, 'mcp_manager') and self.mcp_manager and 
            hasattr(self.mcp_manager, 'tool_cache') and self.mcp_manager.tool_cache):
            try:
                # Get cached tools from all servers
                for server_name in self.config.mcp.servers.keys():
                    if self.config.mcp.servers[server_name].enabled:
                        cached_server_tools = self.mcp_manager.tool_cache.get_cached_tools(server_name)
                        if cached_server_tools:
                            for tool_info in cached_server_tools:
                                tools.append(tool_info.name)
                
                if tools:
                    log_technical("debug", f"Retrieved {len(tools)} tools from cache: {tools}")
                    return tools
            except Exception as e:
                log_technical("warning", f"Error getting tools from cache: {e}")
        
        # If connections are initialized, try to get tools from connections
        if self._connections_initialized and self._persistent_connections:
            for server_name, connection in self._persistent_connections.items():
                try:
                    # Return a placeholder that indicates tools are available but need async call
                    tools.append(f"{server_name}_connection_available")
                except Exception as e:
                    log_technical("warning", f"Error checking connection for {server_name}: {e}")
                    continue
        
        return tools
    
    async def get_available_tools_async(self) -> List[str]:
        """
        Get list of available tools from MCP servers (async version).
        
        Returns:
            List of tool names
        """
        tools = []
        
        # First try to get tools from enhanced MCP manager cache
        if (hasattr(self, 'mcp_manager') and self.mcp_manager and 
            hasattr(self.mcp_manager, 'tool_cache') and self.mcp_manager.tool_cache):
            try:
                # Get cached tools from all servers
                for server_name in self.config.mcp.servers.keys():
                    if self.config.mcp.servers[server_name].enabled:
                        cached_server_tools = self.mcp_manager.tool_cache.get_cached_tools(server_name)
                        if cached_server_tools:
                            for tool_info in cached_server_tools:
                                tools.append(tool_info.name)
                
                if tools:
                    log_technical("debug", f"Retrieved {len(tools)} tools from cache (async): {tools}")
                    return tools
            except Exception as e:
                log_technical("warning", f"Error getting tools from cache (async): {e}")
        
        # If no cached tools, ensure connections and discover tools
        try:
            # Ensure connections are established
            await self._ensure_mcp_connections()
            
            # Get tools from the connections
            for server_name, connection in self._persistent_connections.items():
                try:
                    # Get tools from the connection
                    if hasattr(connection, 'list_tools'):
                        server_tools = await connection.list_tools()
                        if hasattr(server_tools, 'tools'):
                            for tool in server_tools.tools:
                                tools.append(tool.name)
                        else:
                            log_technical("warning", f"Server {server_name} tools response format unexpected")
                    else:
                        log_technical("warning", f"Server {server_name} does not support list_tools")
                except Exception as e:
                    log_technical("warning", f"Error getting tools from {server_name}: {e}")
                    continue
        except Exception as e:
            log_technical("error", f"Error in async tool discovery: {e}")
        
        return tools
    
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
            
            # Filter out parameters that Runner.run_streamed doesn't accept
            filtered_kwargs = {}
            supported_params = ['max_turns', 'response_format', 'temperature', 'max_tokens']
            for key, value in kwargs.items():
                if key in supported_params:
                    filtered_kwargs[key] = value
            
            # Use streaming API with MCP tools
            result = Runner.run_streamed(
                starting_agent=agent,
                input=message,
                **filtered_kwargs
            )
            
            collected_content = ""
            log_technical("info", "Starting MCP streaming response")
            
            async for event in result.stream_events():
                if event.type == "run_item_stream_event":
                    if event.item.type == "message_output_item":
                        try:
                            # Try ItemHelpers before falling back to raw object
                            try:
                                from agents import ItemHelpers
                                message_text = ItemHelpers.text_message_output(event.item)
                                if message_text and len(message_text.strip()) > 0:
                                    collected_content += message_text
                                    yield message_text
                                else:
                                    log_technical("warning", f"ItemHelpers returned empty text for message_output_item")
                                    yield "[Agent response received but text extraction failed]"
                            except Exception as helper_error:
                                log_technical("warning", f"ItemHelpers failed: {helper_error}")
                                yield "[Error: Unable to extract response text - please check logs]"
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

    def _get_intelligent_agent(self):
        """Get or create the IntelligentAgent instance"""
        if not self.intelligent_mode or not INTELLIGENCE_AVAILABLE:
            return None
        
        if self._intelligent_agent is None:
            # Create IntelligentAgent configuration
            intelligent_config = IntelligentAgentConfig(
                max_reasoning_iterations=getattr(self.config.agent, 'max_reasoning_iterations', 10),
                confidence_threshold=getattr(self.config.agent, 'confidence_threshold', 0.8),
                max_concurrent_actions=getattr(self.config.agent, 'max_concurrent_actions', 5),
                action_timeout=getattr(self.config.agent, 'action_timeout', 60.0),
                memory_max_context_turns=getattr(self.config.agent, 'memory_max_context_turns', 20),
                use_detailed_observation=getattr(self.config.agent, 'use_detailed_observation', True),
                enable_learning=getattr(self.config.agent, 'enable_learning', True)
            )
            
            # Create base LLM agent for the intelligent agent
            base_agent = self._create_simple_agent()
            
            # Create IntelligentAgent
            self._intelligent_agent = IntelligentAgent(
                llm_agent=base_agent,
                config=intelligent_config,
                tinyagent_config=self.config  # Pass TinyAgent config for LLM settings
            )
            
            # 🔧 NEW: Register MCP tool executor with IntelligentAgent
            mcp_tool_executor = self._create_mcp_tool_executor()
            self._intelligent_agent.set_mcp_tool_executor(mcp_tool_executor)
            log_technical("info", "MCP tool executor registered with IntelligentAgent")
            
            # Initialize Enhanced MCP context builder if available
            try:
                # Import enhanced MCP context builder components
                from ..mcp.context_builder import AgentContextBuilder
                from ..mcp.cache import MCPToolCache
                from ..mcp.manager import EnhancedMCPServerManager
                
                # Initialize enhanced MCP manager if not already done
                if not hasattr(self, 'mcp_manager') or self.mcp_manager is None:
                    # Create enhanced MCP manager with tool cache
                    self.mcp_manager = EnhancedMCPServerManager(
                        server_configs=self.config.mcp.servers,
                        tool_cache=None,  # Will create its own cache
                        cache_duration=300,  # 5 minutes
                        enable_performance_tracking=True
                    )
                    log_technical("info", "Created EnhancedMCPServerManager for IntelligentAgent")
                
                # Ensure the MCP manager has a tool cache
                if not hasattr(self.mcp_manager, 'tool_cache') or self.mcp_manager.tool_cache is None:
                    # Create tool cache for the MCP manager if it doesn't have one
                    self.mcp_manager.tool_cache = MCPToolCache(
                        cache_duration=300,  # 5 minutes
                        max_cache_size=100,
                        persist_cache=True
                    )
                    log_technical("info", "Created tool cache for EnhancedMCPServerManager")
                
                # Get the tool cache reference
                tool_cache = self.mcp_manager.tool_cache
                
                # Create and set MCP context builder for IntelligentAgent
                context_builder = AgentContextBuilder(tool_cache)
                
                # Set MCP context builder and related components in IntelligentAgent
                self._intelligent_agent.mcp_context_builder = context_builder
                self._intelligent_agent.tool_cache = tool_cache
                self._intelligent_agent.mcp_manager = self.mcp_manager  # Store reference to MCP manager
                
                log_technical("info", "Enhanced MCP context builder initialized for IntelligentAgent")
                log_technical("info", f"MCP manager class: {type(self.mcp_manager).__name__}")
                log_technical("info", f"Tool cache class: {type(tool_cache).__name__}")
                
            except ImportError as e:
                log_technical("warning", f"Enhanced MCP context builder not available: {e}")
            except Exception as e:
                log_technical("warning", f"Error initializing enhanced MCP context builder: {e}")
                import traceback
                log_technical("debug", f"Full traceback: {traceback.format_exc()}")
            
            log_technical("info", "IntelligentAgent created and initialized with enhanced MCP support")
        
        return self._intelligent_agent

    def _create_mcp_tool_executor(self):
        """
        Create MCP tool executor function for IntelligentAgent
        
        Returns:
            Async function that can execute MCP tools: execute_tool(tool_name, params) -> result
        """
        async def execute_mcp_tool(tool_name: str, params: Dict[str, Any]) -> Any:
            """
            Execute an MCP tool using TinyAgent's connection management
            
            Args:
                tool_name: Name of the tool to execute
                params: Parameters for the tool execution
                
            Returns:
                Tool execution result
            """
            try:
                log_technical("info", f"MCP tool executor: executing {tool_name} with params: {params}")
                
                # Ensure MCP connections are established
                connected_servers = await self._ensure_mcp_connections()
                
                if not connected_servers:
                    raise RuntimeError("No MCP servers available for tool execution")
                
                # Find which server has this tool
                target_server = None
                server_name = None
                
                # Check each connected server for the tool
                for srv_name, connection in self._persistent_connections.items():
                    try:
                        if hasattr(connection, 'list_tools'):
                            server_tools = await connection.list_tools()
                            if hasattr(server_tools, 'tools'):
                                for tool in server_tools.tools:
                                    if tool.name == tool_name:
                                        target_server = connection
                                        server_name = srv_name
                                        break
                            if target_server:
                                break
                    except Exception as e:
                        log_technical("warning", f"Error checking tools for server {srv_name}: {e}")
                        continue
                
                if not target_server:
                    # Return descriptive message rather than failing
                    available_tools = []
                    for srv_name, connection in self._persistent_connections.items():
                        try:
                            if hasattr(connection, 'list_tools'):
                                server_tools = await connection.list_tools()
                                if hasattr(server_tools, 'tools'):
                                    available_tools.extend([t.name for t in server_tools.tools])
                        except:
                            pass
                    
                    log_technical("warning", f"Tool {tool_name} not found in any connected server. Available: {available_tools}")
                    return f"Tool '{tool_name}' not found. Available tools: {', '.join(available_tools[:10])}"
                
                # Execute the tool using the MCP protocol
                log_technical("info", f"Executing {tool_name} on server {server_name}")
                
                # Create proper MCP call_tool request
                from agents.mcp import CallToolRequest
                
                tool_request = CallToolRequest(
                    name=tool_name,
                    arguments=params or {}
                )
                
                # Execute the tool
                result = await target_server.call_tool(tool_request)
                
                if hasattr(result, 'content'):
                    # Extract the actual content
                    content = result.content
                    if isinstance(content, list) and len(content) > 0:
                        # Get the first content item
                        content_item = content[0]
                        if hasattr(content_item, 'text'):
                            actual_result = content_item.text
                        else:
                            actual_result = str(content_item)
                    else:
                        actual_result = str(content)
                else:
                    actual_result = str(result)
                
                log_technical("info", f"Tool {tool_name} executed successfully: {actual_result[:200]}...")
                log_tool(f"MCP tool executed: {server_name}.{tool_name} -> {len(actual_result)} chars")
                
                return actual_result
                
            except Exception as e:
                error_msg = f"Error executing MCP tool {tool_name}: {str(e)}"
                log_technical("error", error_msg)
                log_tool(f"MCP tool execution failed: {tool_name} -> {str(e)}")
                
                # Return error information rather than raising
                return f"Tool execution failed: {str(e)}"
        
        return execute_mcp_tool

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