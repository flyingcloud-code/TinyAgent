"""
TinyAgent Core Agent Implementation

This module contains the main TinyAgent class that wraps the openai-agents SDK
and provides a simplified interface for creating and running agents with MCP tools.
"""

import logging
import os
import atexit
import warnings
from typing import Optional, List, Any, Dict
from pathlib import Path

# Suppress aiohttp resource warnings that can occur with LiteLLM
warnings.filterwarnings("ignore", message="Unclosed client session")
warnings.filterwarnings("ignore", message="Unclosed connector")
warnings.filterwarnings("ignore", category=ResourceWarning, module="aiohttp")

# Configure asyncio logging to suppress connection cleanup errors
asyncio_logger = logging.getLogger('asyncio')
# Add a filter to suppress specific messages
class AsyncioConnectionFilter(logging.Filter):
    def filter(self, record):
        if record.levelno == logging.ERROR:
            message = record.getMessage()
            if "Unclosed client session" in message or "Unclosed connector" in message:
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

from ..core.config import TinyAgentConfig, get_config
from ..mcp.manager import MCPServerManager

logger = logging.getLogger(__name__)

# Global list to track OpenAI clients for cleanup
_openai_clients = []

def _cleanup_clients():
    """Cleanup function to close all OpenAI clients"""
    import asyncio
    
    if not _openai_clients:
        return
        
    try:
        # Create new event loop for cleanup
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def _close_all():
            for client in _openai_clients:
                try:
                    await client.close()
                except Exception:
                    pass
        
        loop.run_until_complete(_close_all())
        loop.close()
        _openai_clients.clear()
    except Exception:
        # Ignore cleanup errors
        pass

# Register cleanup function to run at exit
atexit.register(_cleanup_clients)

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