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
    from ..intelligence import IntelligentAgent, IntelligentAgentConfig, INTELLIGENCE_AVAILABLE
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
    
    def __init__(self, original_agent, server_name_map=None, use_streaming=True, verbose_tracing=False):
        self.original_agent = original_agent
        self.server_name_map = server_name_map or {}
        self.call_count = 0
        self.use_streaming = use_streaming
        self.verbose_tracing = verbose_tracing
        
    def __getattr__(self, name):
        return getattr(self.original_agent, name)
    
    def _infer_server_name(self, tool_name: str, event_item) -> str:
        """Infer server name from tool name or event item"""
        # Check explicit mapping first
        if tool_name in self.server_name_map:
            return self.server_name_map[tool_name]
        
        # Try to extract from event item if available
        if hasattr(event_item, 'server') and event_item.server:
            return str(event_item.server)
        elif hasattr(event_item, 'metadata') and isinstance(event_item.metadata, dict):
            server = event_item.metadata.get('server')
            if server:
                return str(server)
        
        # Infer from tool name patterns
        tool_name_lower = tool_name.lower()
        if any(fs_tool in tool_name_lower for fs_tool in ['file', 'read', 'write', 'directory', 'create']):
            return 'filesystem'
        elif any(web_tool in tool_name_lower for web_tool in ['fetch', 'http', 'url', 'search']):
            return 'fetch'  
        elif any(think_tool in tool_name_lower for think_tool in ['sequential', 'thinking', 'analyze']):
            return 'sequential_thinking'
        else:
            return 'unknown'
    
    def _format_tool_params(self, params) -> str:
        """Format tool parameters for display"""
        if not params:
            return "无参数"
        
        if isinstance(params, dict):
            formatted_params = []
            for key, value in params.items():
                if isinstance(value, str) and len(value) > 100:
                    formatted_params.append(f"{key}: {value[:100]}...")
                else:
                    formatted_params.append(f"{key}: {value}")
            return ", ".join(formatted_params)
        else:
            return str(params)[:200] + "..." if len(str(params)) > 200 else str(params)
    
    def _format_tool_result(self, result) -> str:
        """Format tool result for display"""
        if not result:
            return "无结果"
        
        if isinstance(result, dict):
            if 'content' in result:
                content = result['content']
                if isinstance(content, str) and len(content) > 200:
                    return f"内容: {content[:200]}..."
                else:
                    return f"内容: {content}"
            elif 'data' in result:
                return f"数据: {str(result['data'])[:200]}..."
            else:
                return str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
        elif isinstance(result, str):
            return result[:200] + "..." if len(result) > 200 else result
        else:
            return str(result)[:200] + "..." if len(str(result)) > 200 else str(result)

    async def run(self, input_data, **kwargs):
        """Run the original agent with enhanced tool call logging"""
        if self.use_streaming and self.verbose_tracing:
            return self._run_with_streaming_tool_logging(input_data, **kwargs)
        else:
            return await self._run_with_tool_logging(input_data, **kwargs)

    def _run_with_streaming_tool_logging(self, input_data, **kwargs):
        """Run with streaming and detailed tool call logging"""
        
        async def _collect_events():
            tool_calls = {}
            
            try:
                # 🎯 启动消息
                if self.verbose_tracing:
                    print("\n" + "="*80)
                    print("🤖 TinyAgent 智能工具执行开始")
                    print("="*80)
                    print(f"📝 用户输入: {input_data}")
                    print("-"*80)
                
                async for chunk in self.original_agent.run_stream(input_data, **kwargs):
                    # Check if chunk contains events
                    if hasattr(chunk, 'type'):
                        if chunk.type == 'tool_call':
                            self._handle_tool_call_event(chunk, tool_calls)
                        elif chunk.type == 'tool_result':
                            self._handle_tool_result_event(chunk, tool_calls)
                    
                    yield chunk
                
                # 🎯 完成消息  
                if self.verbose_tracing and tool_calls:
                    self._log_tool_summary(tool_calls)
                    
            except Exception as e:
                if self.verbose_tracing:
                    print(f"\n❌ 执行过程中发生错误: {e}")
                    print("="*80)
                raise
        
        return _collect_events()

    def _handle_tool_call_event(self, event, tool_calls):
        """Handle tool call events with detailed Chinese logging"""
        try:
            tool_name = getattr(event, 'tool_name', 'unknown_tool')
            tool_id = getattr(event, 'tool_call_id', f'call_{len(tool_calls) + 1}')
            params = getattr(event, 'arguments', {})
            
            if self.verbose_tracing:
                self.call_count += 1
                server_name = self._infer_server_name(tool_name, event)
                
                print(f"\n🔧 工具调用 #{self.call_count}")
                print(f"   📛 工具名称: {tool_name}")
                print(f"   🖥️  服务器: {server_name}")
                print(f"   📋 参数: {self._format_tool_params(params)}")
                print(f"   ⏱️  开始时间: {datetime.now().strftime('%H:%M:%S')}")
                print(f"   🆔 调用ID: {tool_id}")
                
            tool_calls[tool_id] = {
                'name': tool_name,
                'params': params,
                'start_time': time.time(),
                'server': self._infer_server_name(tool_name, event)
            }
            
        except Exception as e:
            if self.verbose_tracing:
                print(f"   ⚠️ 工具调用事件处理错误: {e}")

    def _handle_tool_result_event(self, event, tool_calls):
        """Handle tool result events with detailed Chinese logging"""
        try:
            tool_call_id = getattr(event, 'tool_call_id', None)
            result = getattr(event, 'result', None)
            is_error = getattr(event, 'is_error', False)
            
            if tool_call_id in tool_calls:
                tool_info = tool_calls[tool_call_id]
                duration = time.time() - tool_info['start_time']
                
                if self.verbose_tracing:
                    if is_error:
                        print(f"   ❌ 执行失败: {result}")
                        print(f"   ⏱️  耗时: {duration:.2f}秒")
                        
                        # 更新全局统计
                        _tool_call_stats['failed_calls'] += 1
                    else:
                        print(f"   ✅ 执行成功!")
                        print(f"   📊 结果: {self._format_tool_result(result)}")
                        print(f"   ⏱️  耗时: {duration:.2f}秒")
                        
                        # 更新全局统计
                        _tool_call_stats['successful_calls'] += 1
                    
                    _tool_call_stats['total_calls'] += 1
                    _tool_call_stats['total_duration'] += duration
                    print("-"*60)
                
                # Update tool call info
                tool_info['result'] = result
                tool_info['duration'] = duration
                tool_info['success'] = not is_error
                
        except Exception as e:
            if self.verbose_tracing:
                print(f"   ⚠️ 工具结果事件处理错误: {e}")

    def _log_tool_summary(self, tool_calls):
        """Log summary of all tool calls"""
        if not tool_calls:
            return
            
        successful = sum(1 for call in tool_calls.values() if call.get('success', False))
        total = len(tool_calls)
        total_time = sum(call.get('duration', 0) for call in tool_calls.values())
        
        print(f"\n📈 工具调用总结")
        print(f"   📊 总调用次数: {total}")
        print(f"   ✅ 成功次数: {successful}")
        print(f"   ❌ 失败次数: {total - successful}")
        print(f"   📈 成功率: {(successful/total*100):.1f}%")
        print(f"   ⏱️  总耗时: {total_time:.2f}秒")
        
        if total > 0:
            print(f"   ⚡ 平均耗时: {total_time/total:.2f}秒")
        
        print("="*80)

    async def _run_with_tool_logging(self, input_data, **kwargs):
        """Run with basic tool logging (non-streaming)"""
        start_time = time.time()
        
        if self.verbose_tracing:
            print("\n" + "="*80)
            print("🤖 TinyAgent 执行开始")
            print("="*80)
            print(f"📝 用户输入: {input_data}")
            print("-"*80)
        
        try:
            result = await self.original_agent.run(input_data, **kwargs)
            
            duration = time.time() - start_time
            if self.verbose_tracing:
                print(f"\n✅ 执行完成!")
                print(f"⏱️  总耗时: {duration:.2f}秒")
                print("="*80)
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            if self.verbose_tracing:
                print(f"\n❌ 执行失败: {e}")
                print(f"⏱️  耗时: {duration:.2f}秒")
                print("="*80)
            raise

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
        # TODO by code review: how the agent load proper prompt instructions, need check!!
        self.instructions = self._load_instructions(instructions)
        log_agent(f"instructions loaded: {self.instructions}")
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
            log_agent(f"Created agent '{self.config.agent.name}' with {model_type} model '{self.model_name}' (MCP servers will be added dynamically)")
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
            log_agent(f"get_agent: return mcp agent '{self.config.agent.name}' with model '{self.model_name}'")
            return mcp_agent
        
        # Otherwise, return simple agent (or create if needed)
        if self._agent is None:
            self._agent = self._create_agent()
        log_agent(f"get_agent: return agent '{self.config.agent.name}' with model '{self.model_name}'")
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
        log_agent(f"get_agent_with_mcp: '{self.config.agent.name}' with model '{self.model_name}'")
        return mcp_agent
    
    async def run(self, message: str, **kwargs) -> Any:
        """
        Run the agent with a message using intelligent mode only.
        
        Args:
            message: Input message for the agent
            **kwargs: Additional arguments passed to intelligent agent
            
        Returns:
            Agent execution result
        """
        try:
            log_technical("info", f"Running agent with message: {message[:100]}...")
            
            # 🔧 SIMPLIFIED: Only use intelligent mode
            if not (self.intelligent_mode and INTELLIGENCE_AVAILABLE):
                raise RuntimeError(
                    "Intelligent mode is required but not available. "
                    "Please check if intelligence components are properly installed."
                )
            
            log_technical("info", "Using intelligent mode with ReAct loop")
            return await self._run_intelligent_mode(message, **kwargs)
            
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
                log_technical("error", "IntelligentAgent not available - check INTELLIGENCE_AVAILABLE")
                # 🔧 DISABLED FALLBACK: Don't fall back to basic mode
                raise RuntimeError("IntelligentAgent is required but not available")
            
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
                # Return the result as-is if format is unexpected
                return result
                
        except Exception as e:
            log_technical("error", f"Intelligent mode execution failed: {e}")
            # 🔧 DISABLED FALLBACK: Don't fall back to basic mode
            raise RuntimeError(f"Intelligent mode failed: {e}")

    async def _register_mcp_tools_with_intelligent_agent(self, intelligent_agent):
        """
        Register MCP tools with the IntelligentAgent for tool-aware operation
        
        Args:
            intelligent_agent: The IntelligentAgent instance to register tools with
        """
        try:
            log_technical("info", "Registering MCP tools with IntelligentAgent")
            
            # 🔧 CRITICAL FIX: Ensure MCP connections are established BEFORE creating tool executor
            connected_servers = await self._ensure_mcp_connections()
            log_technical("info", f"MCP connections ensured: {len(connected_servers)} servers connected")
            
            # Verify connections are actually established
            if not self._persistent_connections:
                log_technical("warning", "No MCP connections established, skipping tool registration")
                return
            
            log_technical("info", f"Active MCP connections: {list(self._persistent_connections.keys())}")
            
            # Collect available tools from all connected servers
            available_tools = {}
            tool_schemas = {}
            mcp_tools_for_registration = []  # 🔧 NEW: List for register_mcp_tools()
            
            for server_name, connection in self._persistent_connections.items():
                try:
                    log_technical("info", f"Collecting tools from server: {server_name}")
                    
                    # List tools from this server
                    if hasattr(connection, 'list_tools'):
                        server_tools = await connection.list_tools()
                        
                        # 🔧 CRITICAL FIX: Handle different response formats
                        tools_list = None
                        if isinstance(server_tools, list):
                            # Direct list response (most common case)
                            tools_list = server_tools
                            log_technical("info", f"Server {server_name} returned direct list with {len(tools_list)} tools")
                        elif hasattr(server_tools, 'tools'):
                            # Response with .tools attribute
                            tools_list = server_tools.tools
                            log_technical("info", f"Server {server_name} returned object with .tools attribute containing {len(tools_list)} tools")
                        else:
                            log_technical("warning", f"Server {server_name} returned unexpected format: {type(server_tools)}")
                            continue
                        
                        if tools_list:
                            for tool in tools_list:
                                tool_name = tool.name
                                available_tools[tool_name] = server_name
                                
                                # Store tool schema for intelligent agent
                                tool_schemas[tool_name] = {
                                    'name': tool_name,
                                    'description': getattr(tool, 'description', f'{tool_name} from {server_name}'),
                                    'server': server_name,
                                    'schema': getattr(tool, 'inputSchema', {})
                                }
                                
                                # 🔧 NEW: Prepare tool for register_mcp_tools()
                                mcp_tools_for_registration.append({
                                    'name': tool_name,
                                    'description': getattr(tool, 'description', f'{tool_name} from {server_name}'),
                                    'server': server_name,
                                    'schema': getattr(tool, 'inputSchema', {}),
                                    'category': 'file_operations' if 'file' in tool_name.lower() else 
                                               'web_operations' if any(x in tool_name.lower() for x in ['fetch', 'search', 'web']) else
                                               'reasoning' if 'think' in tool_name.lower() else 'general'
                                })
                                
                            log_technical("info", f"Server {server_name} provided {len(tools_list)} tools")
                        else:
                            log_technical("warning", f"Server {server_name} returned empty tools list")
                    else:
                        log_technical("warning", f"Server {server_name} does not support list_tools")
                        
                except Exception as e:
                    log_technical("error", f"Error collecting tools from server {server_name}: {e}")
                    continue
            
            # Log total available tools
            log_technical("info", f"Total MCP tools available: {len(available_tools)}")
            for tool_name, server_name in available_tools.items():
                log_technical("debug", f"  - {tool_name} (from {server_name})")
            
            # Store tool information in intelligent agent
            intelligent_agent.available_mcp_tools = available_tools
            intelligent_agent.mcp_tool_schemas = tool_schemas
            
            # 🔧 CRITICAL FIX: Register tools with IntelligentAgent's register_mcp_tools method
            if mcp_tools_for_registration:
                log_technical("info", f"Calling register_mcp_tools with {len(mcp_tools_for_registration)} tools")
                intelligent_agent.register_mcp_tools(mcp_tools_for_registration)
                log_technical("info", f"Successfully registered {len(mcp_tools_for_registration)} MCP tools with IntelligentAgent")
            else:
                log_technical("warning", "No tools available for registration")
            
            # NOW create and register the MCP tool executor (after connections are established)
            mcp_tool_executor = self._create_mcp_tool_executor()
            intelligent_agent.set_mcp_tool_executor(mcp_tool_executor)
            
            log_technical("info", f"MCP tools registered with IntelligentAgent: {len(available_tools)} tools from {len(self._persistent_connections)} servers")
            
        except Exception as e:
            log_technical("error", f"Error registering MCP tools with IntelligentAgent: {e}")
            import traceback
            log_technical("debug", f"Full traceback: {traceback.format_exc()}")
            # Don't raise - allow intelligent agent to work without MCP tools

    async def _register_mcp_tools_basic(self, intelligent_agent):
        """
        Basic MCP tool registration (for compatibility)
        
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
                            log_technical("warning", f"Server {server_name} returned unexpected tools format")
                    else:
                        log_technical("warning", f"Server {server_name} does not support list_tools")
                except Exception as e:
                    log_technical("warning", f"Error getting tools from {server_name}: {e}")
                    continue
            
            # Register tools with intelligent agent if available
            if mcp_tools:
                if hasattr(intelligent_agent, 'register_mcp_tools'):
                    intelligent_agent.register_mcp_tools(mcp_tools)
                log_technical("info", f"Basic registration: {len(mcp_tools)} MCP tools")
            else:
                log_technical("info", "No MCP tools available to register")
                
        except Exception as e:
            log_technical("error", f"Error in basic MCP tool registration: {e}")

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
        Run the agent with streaming output using intelligent mode only.
        
        Args:
            message: Input message for the agent
            **kwargs: Additional arguments passed to intelligent agent
            
        Yields:
            String chunks as they are generated
        """
        try:
            log_technical("info", f"Running agent with streaming for message: {message[:100]}...")
            
            # 🔧 SIMPLIFIED: Only use intelligent mode
            if not (self.intelligent_mode and INTELLIGENCE_AVAILABLE):
                yield "[ERROR] Intelligent mode is required but not available. Please check if intelligence components are properly installed."
                return
            
            log_technical("info", "Using intelligent mode with streaming output")
            
            # Get the intelligent agent
            intelligent_agent = self._get_intelligent_agent()
            if not intelligent_agent:
                yield "[ERROR] IntelligentAgent not available - check INTELLIGENCE_AVAILABLE"
                return
            
            # Register MCP tools with the intelligent agent if available
            await self._register_mcp_tools_with_intelligent_agent(intelligent_agent)
            
            # Execute using intelligent agent with full ReAct loop
            log_agent("Starting intelligent task execution with ReAct loop (streaming)...")
            
            try:
                # Check if intelligent agent supports streaming
                if hasattr(intelligent_agent, 'run_stream'):
                    # Use streaming if available
                    async for chunk in intelligent_agent.run_stream(message, context=kwargs):
                        yield chunk
                else:
                    # Fall back to non-streaming intelligent mode
                    result = await intelligent_agent.run(message, context=kwargs)
                    
                    # Stream the result
                    if isinstance(result, dict) and 'answer' in result:
                        answer = result.get('answer', 'Task completed successfully')
                        # Stream the answer character by character for better UX
                        for char in answer:
                            yield char
                            # Small delay to simulate streaming
                            import asyncio
                            await asyncio.sleep(0.01)
                    else:
                        yield str(result)
                    
                    log_technical("info", "Intelligent streaming completed")
                    
            except Exception as e:
                log_technical("error", f"Intelligent mode streaming failed: {e}")
                yield f"[ERROR] Intelligent mode failed: {e}"
                
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
                
                # Convert async generator to sync generator
                import asyncio
                gen = collect_stream()
                
                while True:
                    try:
                        chunk = asyncio.get_event_loop().run_until_complete(gen.__anext__())
                        yield chunk
                    except StopAsyncIteration:
                        break
                    
        except Exception as e:
            log_technical("error", f"Sync streaming failed: {e}")
            yield f"[ERROR] {str(e)}"

    def _create_simple_agent(self) -> Agent:
        """
        Create a simple LLM agent for use with IntelligentAgent
        
        Returns:
            Simple Agent instance for reasoning
        """
        try:
            # Create simple agent without MCP servers for reasoning
            simple_agent = Agent(
                name=f"{self.config.agent.name}-Reasoning",
                instructions=self.instructions,
                model=self._create_model_instance(self.model_name)
            )
            
            # Add model_settings if needed
            if not self._should_use_litellm(self.model_name):
                from agents import ModelSettings
                simple_agent.model_settings = ModelSettings(temperature=self.config.llm.temperature)
            
            log_agent(f"Created simple agent for reasoning: {simple_agent.name}, model: {self.model_name}")
            return simple_agent
            
        except Exception as e:
            log_technical("error", f"Failed to create simple agent: {e}")
            raise

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
                            
                            # 🔧 CRITICAL FIX: Handle different response formats
                            tools_list = None
                            if isinstance(server_tools, list):
                                # Direct list response (most common case)
                                tools_list = server_tools
                            elif hasattr(server_tools, 'tools'):
                                # Response with .tools attribute
                                tools_list = server_tools.tools
                            else:
                                log_technical("warning", f"Server {srv_name} returned unexpected format: {type(server_tools)}")
                                continue
                            
                            if tools_list:
                                for tool in tools_list:
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
                                
                                # 🔧 CRITICAL FIX: Handle different response formats
                                tools_list = None
                                if isinstance(server_tools, list):
                                    # Direct list response (most common case)
                                    tools_list = server_tools
                                elif hasattr(server_tools, 'tools'):
                                    # Response with .tools attribute
                                    tools_list = server_tools.tools
                                else:
                                    continue
                                
                                if tools_list:
                                    available_tools.extend([t.name for t in tools_list])
                        except:
                            pass
                    
                    log_technical("warning", f"Tool {tool_name} not found in any connected server. Available: {available_tools}")
                    return f"Tool '{tool_name}' not found. Available tools: {', '.join(available_tools[:10])}"
                
                # Create proper MCP call_tool request
                try:
                    from mcp.types import CallToolRequest
                    
                    # Execute the tool using the MCP protocol
                    log_technical("info", f"Executing {tool_name} on server {server_name}")
                    
                    # 🔧 CRITICAL FIX: Use direct call_tool method with proper parameters
                    result = await target_server.call_tool(tool_name, params or {})
                    
                    # Process result and return
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
                    
                except ImportError as import_error:
                    log_technical("error", f"Failed to import CallToolRequest: {import_error}")
                    return f"Tool execution failed: MCP types not available - {import_error}"
                except Exception as e:
                    log_technical("error", f"Failed to execute tool {tool_name}: {e}")
                    return f"Tool execution failed: {e}"
                
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