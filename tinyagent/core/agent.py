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

logger = logging.getLogger(__name__)

# Create specialized logger for MCP tool calls
mcp_tool_logger = logging.getLogger('tinyagent.mcp.tools')
mcp_tool_logger.setLevel(logging.INFO)

# Add handler if not already present
if not mcp_tool_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    mcp_tool_logger.addHandler(handler)

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
    """Log summary statistics of MCP tool calls"""
    if _tool_call_stats['total_calls'] > 0:
        avg_duration = _tool_call_stats['total_duration'] / _tool_call_stats['total_calls']
        success_rate = (_tool_call_stats['successful_calls'] / _tool_call_stats['total_calls']) * 100
        
        mcp_tool_logger.info("=== MCP Tool Call Summary ===")
        mcp_tool_logger.info(f"Total tool calls: {_tool_call_stats['total_calls']}")
        mcp_tool_logger.info(f"Successful calls: {_tool_call_stats['successful_calls']}")
        mcp_tool_logger.info(f"Failed calls: {_tool_call_stats['failed_calls']}")
        mcp_tool_logger.info(f"Success rate: {success_rate:.1f}%")
        mcp_tool_logger.info(f"Average call duration: {avg_duration:.2f}s")
        mcp_tool_logger.info(f"Total tool execution time: {_tool_call_stats['total_duration']:.2f}s")
        mcp_tool_logger.info("=== End Summary ===")
    else:
        mcp_tool_logger.info("=== MCP Tool Call Summary ===")
        mcp_tool_logger.info("No MCP tool calls were made during this run")
        mcp_tool_logger.info("=== End Summary ===")

class MCPToolCallLogger:
    """Custom wrapper to log MCP tool calls and their input/output"""
    
    def __init__(self, original_agent, server_name_map=None):
        self.original_agent = original_agent
        self.server_name_map = server_name_map or {}
        self.call_count = 0
        
    def __getattr__(self, name):
        """Delegate all attributes to the original agent"""
        return getattr(self.original_agent, name)
    
    async def run(self, input_data, **kwargs):
        """Override run method to log tool calls"""
        mcp_tool_logger.info(f"🚀 Starting agent run with input: {str(input_data)[:200]}...")
        start_time = time.time()
        
        try:
            # Create wrapper for Runner.run that captures tool calls
            result = await self._run_with_tool_logging(input_data, **kwargs)
            
            duration = time.time() - start_time
            mcp_tool_logger.info(f"✅ Agent run completed successfully in {duration:.2f}s")
            
            # Log final statistics
            log_tool_call_stats()
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            mcp_tool_logger.error(f"❌ Agent run failed after {duration:.2f}s: {e}")
            
            # Log final statistics even on failure
            log_tool_call_stats()
            
            raise
    
    async def _run_with_tool_logging(self, input_data, **kwargs):
        """Run the agent with tool call interception"""
        # We'll use the streaming API to capture tool calls
        result = Runner.run_streamed(
            starting_agent=self.original_agent,
            input=input_data,
            **kwargs
        )
        
        tool_call_sequence = 0
        current_tool_call_start = None
        
        async for event in result.stream_events():
            # Ignore raw response events
            if event.type == "raw_response_event":
                continue
            elif event.type == "run_item_stream_event":
                if event.item.type == "tool_call_item":
                    # Tool call started
                    tool_call_sequence += 1
                    current_tool_call_start = time.time()
                    
                    mcp_tool_logger.info(f"🔧 [{tool_call_sequence}] MCP Tool Call Started")
                    
                    # Log basic item info (safe access)
                    try:
                        item_str = str(event.item)
                        if len(item_str) > 200:
                            item_str = item_str[:200] + "..."
                        mcp_tool_logger.info(f"    Tool Call Item: {item_str}")
                    except Exception:
                        mcp_tool_logger.info(f"    Tool Call Item: [Unable to display]")
                    
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
                    try:
                        if hasattr(event.item, 'output'):
                            output_content = str(event.item.output)
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
                    
                    # Log tool call completion
                    status_emoji = "✅" if is_success else "❌"
                    mcp_tool_logger.info(f"{status_emoji} [{tool_call_sequence}] MCP Tool Call Completed:")
                    mcp_tool_logger.info(f"    Duration: {duration:.2f}s")
                    mcp_tool_logger.info(f"    Success: {is_success}")
                    mcp_tool_logger.info(f"    Output: {output_content}")
                    
                    # Update global stats
                    if is_success:
                        _tool_call_stats['successful_calls'] += 1
                    else:
                        _tool_call_stats['failed_calls'] += 1
                    
                    _tool_call_stats['total_duration'] += duration
                    
                elif event.item.type == "message_output_item":
                    # Message output - log for context
                    try:
                        from agents import ItemHelpers
                        message_text = ItemHelpers.text_message_output(event.item)
                        if message_text and len(message_text.strip()) > 0:
                            if len(message_text) > 300:
                                message_text = message_text[:300] + "..."
                            mcp_tool_logger.info(f"💬 Agent Response: {message_text}")
                    except Exception:
                        mcp_tool_logger.info(f"💬 Agent generated a response")
                        
        # Return the final result
        try:
            final_result = await result.result()
            return final_result
        except AttributeError:
            # Handle API compatibility issue - RunResultStreaming might not have result() method
            # In this case, we'll return a simple success indicator
            mcp_tool_logger.warning("Unable to get final result from streaming API, returning success indicator")
            return "MCP tool calls completed successfully"

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
        api_key: Optional[str] = None
    ):
        """
        Initialize TinyAgent.
        
        Args:
            config: Complete TinyAgent configuration (uses default if None)
            instructions: Custom instructions for the agent
            model_name: Model to use (overrides config)
            api_key: OpenAI API key (overrides environment)
        """
        if not AGENTS_AVAILABLE:
            raise ImportError("OpenAI Agents SDK is required but not available")
        
        # Load configuration
        if config is None:
            config = get_config()
        
        self.config = config
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
        
        self.logger.info(f"TinyAgent initialized with {len(self.mcp_servers)} MCP servers")
    
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
            
            self.logger.info(f"Creating LitellmModel for third-party model: {formatted_model_name}")
            return LitellmModel(**litellm_kwargs)
        else:
            # Use standard OpenAI model (string)
            self.logger.info(f"Using standard OpenAI model: {model_name}")
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
                    self.logger.warning(f"Failed to load instructions from {instructions_path}: {e}")
        
        # Fallback to default instructions
        default_instructions_path = Path(__file__).parent.parent / "prompts" / "default_instructions.txt"
        if default_instructions_path.exists():
            try:
                return default_instructions_path.read_text(encoding='utf-8')
            except Exception as e:
                self.logger.warning(f"Failed to load default instructions: {e}")
        
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
        
        # 收集所有需要连接的MCP服务器
        server_contexts = []
        
        try:
            # 为每个MCP服务器创建连接上下文
            for server_config in self.mcp_manager.server_configs:
                if not server_config.enabled:
                    continue
                    
                try:
                    if server_config.type == "stdio":
                        server = MCPServerStdio(
                            name=server_config.name,
                            params={
                                "command": server_config.command,
                                "args": server_config.args or [],
                                "env": server_config.env or {}
                            }
                        )
                        server_contexts.append(server)
                        self.logger.debug(f"Created stdio MCP server: {server_config.name}")
                        
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
                            sse_params["timeout"] = 30  # 默认30秒超时
                            
                        if server_config.sse_read_timeout is not None:
                            sse_params["sse_read_timeout"] = server_config.sse_read_timeout
                        else:
                            sse_params["sse_read_timeout"] = 60  # 默认60秒SSE读取超时
                        
                        server = MCPServerSse(
                            name=server_config.name,
                            params=sse_params
                        )
                        server_contexts.append(server)
                        self.logger.debug(f"Created SSE MCP server: {server_config.name} with URL: {server_config.url}")
                        
                    elif server_config.type == "http":
                        server = MCPServerStreamableHttp(
                            name=server_config.name,
                            params={
                                "url": server_config.url,
                                "headers": server_config.headers or {}
                            }
                        )
                        server_contexts.append(server)
                        self.logger.debug(f"Created HTTP MCP server: {server_config.name}")
                        
                except Exception as e:
                    self.logger.warning(f"Failed to create MCP server {server_config.name}: {e}")
                    continue
            
            # 如果没有可用的服务器，直接运行
            if not server_contexts:
                self.logger.info("No MCP servers available, running without tools")
                agent = self.get_agent()
                
                result = await Runner.run(
                    starting_agent=agent,
                    input=message,
                    **kwargs
                )
                
                self.logger.info("Agent execution completed successfully")
                return result
            
            # 连接所有MCP服务器并运行Agent
            return await self._connect_and_run_servers(server_contexts, message, **kwargs)
                
        except Exception as e:
            self.logger.error(f"Failed to run agent with MCP servers: {e}")
            raise
    
    async def _connect_and_run_servers(self, server_contexts: List[Any], message: str, **kwargs) -> Any:
        """
        递归连接MCP服务器并运行Agent，确保正确的资源管理。
        
        Args:
            server_contexts: MCP服务器上下文列表
            message: 输入消息
            **kwargs: 传递给Runner.run的额外参数
            
        Returns:
            Agent执行结果
        """
        connected_servers = []
        
        async def connect_servers_recursive(servers, index=0):
            """递归连接服务器的内部函数"""
            if index >= len(servers):
                # 所有服务器都已连接，创建Agent并运行
                try:
                    agent = Agent(
                        name=self.config.agent.name,
                        instructions=self.instructions,
                        model=self._create_model_instance(self.model_name),
                        mcp_servers=connected_servers
                    )
                    
                    # 包装agent以启用详细的MCP工具调用日志记录
                    logged_agent = MCPToolCallLogger(agent)
                    
                    self.logger.info(f"Running agent with {len(connected_servers)} connected MCP servers")
                    mcp_tool_logger.info(f"🎯 Starting MCP-enabled agent run with {len(connected_servers)} servers:")
                    for server in connected_servers:
                        server_name = getattr(server, 'name', 'unknown')
                        mcp_tool_logger.info(f"    - {server_name}")
                    
                    # 使用包装的agent运行，这将自动记录所有工具调用
                    result = await logged_agent.run(message, **kwargs)
                    
                    self.logger.info("Agent execution completed successfully")
                    return result
                    
                except Exception as e:
                    self.logger.error(f"Failed to run agent: {e}")
                    raise
            else:
                # 连接当前服务器
                current_server = servers[index]
                try:
                    self.logger.debug(f"Connecting to MCP server: {current_server.name}")
                    
                    async with current_server as server:
                        # 添加到活跃服务器列表用于清理
                        _active_servers.append(server)
                        connected_servers.append(server)
                        
                        self.logger.info(f"Successfully connected to MCP server: {current_server.name}")
                        
                        # 递归连接下一个服务器
                        try:
                            result = await connect_servers_recursive(servers, index + 1)
                            return result
                        finally:
                            # 清理：从活跃服务器列表中移除
                            if server in _active_servers:
                                _active_servers.remove(server)
                                
                except Exception as e:
                    self.logger.error(f"Failed to connect to MCP server {current_server.name}: {e}")
                    # 连接失败，继续尝试下一个服务器
                    return await connect_servers_recursive(servers, index + 1)
        
        try:
            return await connect_servers_recursive(server_contexts)
        except Exception as e:
            self.logger.error(f"All MCP server connections failed: {e}")
            # 如果所有服务器都连接失败，直接运行没有MCP工具的Agent
            self.logger.info("Falling back to running agent without MCP tools")
            
            agent = self.get_agent()
            result = await Runner.run(
                starting_agent=agent,
                input=message,
                **kwargs
            )
            
            self.logger.info("Agent execution completed successfully (fallback mode)")
            return result
    
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