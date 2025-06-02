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
from typing import Optional, List, Any, Dict
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
            log_user(f"❌ Task failed: {str(e)}")
            log_technical("error", f"Agent run failed after {duration:.2f}s: {e}")
            
            # Log final statistics even on failure
            log_tool_call_stats()
            
            raise
    
    async def _run_with_tool_logging(self, input_data, **kwargs):
        """Run the agent with tool call interception using enhanced logging"""
        # We'll use the streaming API to capture tool calls
        result = Runner.run_streamed(
            starting_agent=self.original_agent,
            input=input_data,
            **kwargs
        )
        
        tool_call_sequence = 0
        current_tool_call_start = None
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
                    
                    log_tool(f"Starting tool call #{tool_call_sequence}")
                    
                    # Log technical details to file
                    try:
                        item_str = str(event.item)
                        if len(item_str) > 200:
                            item_str = item_str[:200] + "..."
                        log_technical("debug", f"Tool Call Item [{tool_call_sequence}]: {item_str}")
                    except Exception:
                        log_technical("debug", f"Tool Call Item [{tool_call_sequence}]: [Unable to display]")
                    
                    # Update global stats
                    _tool_call_stats['total_calls'] += 1
                    
                elif event.item.type == "tool_call_output_item":
                    # Tool call completed
                    duration = 0.0
                    if current_tool_call_start:
                        duration = time.time() - current_tool_call_start
                        current_tool_call_start = None
                    
                    # Extract output safely
                    output_content = "N/A"
                    output_size = 0
                    try:
                        if hasattr(event.item, 'output'):
                            output_content = str(event.item.output)
                            output_size = len(output_content)
                            if len(output_content) > 500:
                                output_content = output_content[:500] + "... (truncated)"
                    except Exception:
                        output_content = "[Unable to extract output]"
                    
                    # Assume success unless we can detect an error
                    is_success = True
                    try:
                        if hasattr(event.item, 'error') and event.item.error:
                            is_success = False
                    except Exception:
                        pass
                    
                    # Log tool call completion with enhanced logging
                    status = "[OK]" if is_success else "[FAIL]"
                    log_tool(f"Tool call #{tool_call_sequence} completed {status} ({duration:.2f}s)")
                    
                    # Log technical details to file
                    log_technical("info", f"Tool Call [{tool_call_sequence}] Completed:")
                    log_technical("info", f"    Duration: {duration:.2f}s")
                    log_technical("info", f"    Success: {is_success}")
                    log_technical("info", f"    Output: {output_content}")
                    
                    # Log structured metrics
                    MCPToolMetrics.log_tool_call(
                        server_name="unknown",  # We'll need to enhance this
                        tool_name="unknown",    # We'll need to enhance this
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
        
        # Initialize MCP servers
        self.mcp_servers = self.mcp_manager.initialize_servers()
        
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
        
        log_technical("info", f"TinyAgent initialized with {len(self.mcp_servers)} MCP servers (streaming: {self.use_streaming})")
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
                # If using OpenRouter and model doesn't have openrouter/ prefix, add it
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
            
            # Create agent with appropriate model instance and MCP servers
            agent_kwargs = {
                "name": self.config.agent.name,
                "instructions": self.instructions,
                "model": model_instance,
                "mcp_servers": self.mcp_servers
            }
            
            # Add model_settings only for non-LiteLLM models
            if model_settings is not None:
                agent_kwargs["model_settings"] = model_settings
            
            agent = Agent(**agent_kwargs)
            
            model_type = "LiteLLM" if self._should_use_litellm(self.model_name) else "OpenAI"
            self.logger.info(f"Created agent '{self.config.agent.name}' with {model_type} model '{self.model_name}'")
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
            # 如果有MCP服务器，需要在async with语句中连接它们
            if self.mcp_servers:
                return await self._run_with_mcp_servers(message, **kwargs)
            else:
                # 没有MCP服务器，直接运行
                agent = self.get_agent()
                self.logger.info(f"Running agent with message: {message[:100]}...")
                
                result = await Runner.run(
                    starting_agent=agent,
                    input=message,
                    **kwargs
                )
                
                self.logger.info("Agent execution completed successfully")
                return result
            
        except Exception as e:
            self.logger.error(f"Agent execution failed: {e}")
            raise

    async def _run_with_mcp_servers(self, message: str, **kwargs) -> Any:
        """
        Run the agent with MCP servers properly connected.
        
        Args:
            message: Input message for the agent
            **kwargs: Additional arguments passed to Runner.run
            
        Returns:
            Agent execution result
        """
        from agents.mcp import MCPServerStdio, MCPServerSse, MCPServerStreamableHttp
        
        # 收集所有需要连接的服务器实例
        server_instances = []
        
        try:
            # 为每个MCP服务器创建实例
            for server_config in self.mcp_manager.server_configs:
                if not server_config.enabled:
                    continue
                    
                try:
                    server_instance = self._create_server_instance(server_config)
                    if server_instance:
                        server_instances.append(server_instance)
                except Exception as e:
                    self.logger.error(f"Failed to create MCP server {server_config.name}: {e}")
                    continue
            
            if not server_instances:
                self.logger.info("No MCP servers available, running without tools")
                agent = self.get_agent()
                
                result = await Runner.run(
                    starting_agent=agent,
                    input=message,
                    **kwargs
                )
                
                self.logger.info("Agent execution completed successfully")
                return result
            
            # 使用async with来管理所有服务器的连接
            return await self._run_with_connected_servers(server_instances, message, **kwargs)
                
        except Exception as e:
            self.logger.error(f"Failed to run agent with MCP servers: {e}")
            raise
    
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
    
    async def _run_with_connected_servers(self, server_instances, message: str, **kwargs):
        """
        使用连接的服务器运行Agent
        
        Args:
            server_instances: MCP服务器实例列表
            message: 输入消息
            **kwargs: 传递给Runner.run的额外参数
            
        Returns:
            Agent执行结果
        """
        import asyncio
        connected_servers = []
        
        # 尝试连接所有服务器
        for server_instance in server_instances:
            try:
                server_name = getattr(server_instance, 'name', 'unknown')
                log_agent(f"Connecting to MCP server: {server_name}")
                log_technical("info", f"Attempting to connect to MCP server: {server_name}")
                
                # 对于所有MCP服务器，使用统一的长超时时间（因为npx可能需要下载包）
                log_technical("info", f"Using 120s timeout for MCP server connection: {server_name}")
                await asyncio.wait_for(server_instance.connect(), timeout=120.0)
                
                connected_servers.append(server_instance)
                log_agent(f"Connected to {server_name}")
                log_technical("info", f"Successfully connected to MCP server: {server_name}")
                
                # 添加到全局清理列表
                _active_servers.append(server_instance)
                
            except asyncio.TimeoutError:
                server_name = getattr(server_instance, 'name', 'unknown')
                log_agent(f"Connection timeout for {server_name}")
                log_technical("warning", f"MCP server {server_name} connection timed out (possibly downloading packages)")
                continue
            except Exception as e:
                server_name = getattr(server_instance, 'name', 'unknown')
                log_agent(f"Connection failed for {server_name}: {str(e)}")
                log_technical("error", f"Failed to connect to MCP server {server_name}: {e}")
                continue
        
        try:
            if not connected_servers:
                # 没有成功连接的服务器，回退到无工具模式
                log_agent("No MCP servers available, running without tools")
                log_technical("warning", "All MCP server connections failed, falling back to no-tools mode")
                
                # 创建无MCP服务器的Agent
                agent = Agent(
                    name=self.config.agent.name,
                    instructions=self.instructions,
                    model=self._create_model_instance(self.model_name)
                    # 注意：不传递 mcp_servers 参数
                )
                
                # 直接运行，不使用工具调用日志记录
                result = await Runner.run(
                    starting_agent=agent,
                    input=message,
                    **kwargs
                )
                
                log_agent("Task completed successfully (no-tools mode)")
                return result
            else:
                # 有成功连接的服务器，正常创建Agent
                log_tool(f"Starting MCP-enabled execution with {len(connected_servers)} servers")
                for server in connected_servers:
                    server_name = getattr(server, 'name', 'unknown')
                    log_technical("info", f"    - {server_name}")
                
                # 创建带MCP服务器的Agent
                agent = Agent(
                    name=self.config.agent.name,
                    instructions=self.instructions,
                    model=self._create_model_instance(self.model_name),
                    mcp_servers=connected_servers
                )
                
                # 包装Agent以启用详细的MCP工具调用日志记录
                logged_agent = MCPToolCallLogger(agent, use_streaming=self.use_streaming)
                
                # 运行包装的代理，它会自动记录工具调用
                result = await logged_agent.run(message, **kwargs)
                
                log_agent("Task completed successfully")
                return result
                
        except Exception as e:
            log_technical("error", f"Error running agent: {e}")
            raise
            
        finally:
            # 清理连接的服务器
            for server in connected_servers:
                try:
                    await server.close()
                except Exception as e:
                    server_name = getattr(server, 'name', 'unknown')
                    log_technical("debug", f"Error closing server {server_name}: {e}")

    async def _connect_single_server(self, server_config):
        """
        连接单个MCP服务器 - 已弃用，使用_create_server_instance和_run_with_connected_servers代替
        """
        # 这个方法已经不再使用，保留以防兼容性问题
        pass
    
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
            # 如果有MCP服务器，需要使用异步方法
            if self.mcp_servers:
                # 创建新的事件循环来运行异步方法
                try:
                    # 尝试获取当前事件循环
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 如果在已运行的事件循环中，创建新的线程来运行
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(self._run_in_new_loop, message, **kwargs)
                            return future.result()
                    else:
                        # 如果事件循环未运行，直接运行
                        return loop.run_until_complete(self.run(message, **kwargs))
                except RuntimeError:
                    # 没有事件循环，创建新的
                    return asyncio.run(self.run(message, **kwargs))
            else:
                # 没有MCP服务器，可以直接使用同步方法
                agent = self.get_agent()
                self.logger.info(f"Running agent synchronously with message: {message[:100]}...")
                
                result = Runner.run_sync(
                    starting_agent=agent,
                    input=message,
                    **kwargs
                )
                
                self.logger.info("Agent execution completed successfully")
                return result
            
        except Exception as e:
            self.logger.error(f"Agent execution failed: {e}")
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
        self.logger.info("Reloading MCP servers")
        
        # Reinitialize servers
        config = get_config()
        enabled_servers = [
            server for server in config.mcp.servers.values() 
            if server.enabled
        ]
        self.mcp_manager = MCPServerManager(enabled_servers)
        self.mcp_servers = self.mcp_manager.initialize_servers()
        
        # Recreate agent with new servers
        self._agent = None  # Force recreation on next access
        
        self.logger.info(f"Reloaded {len(self.mcp_servers)} MCP servers")
    
    def __repr__(self) -> str:
        return f"TinyAgent(name='{self.config.agent.name}', model='{self.model_name}', mcp_servers={len(self.mcp_servers)})"


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