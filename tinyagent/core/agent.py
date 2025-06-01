"""
TinyAgent Core Agent Implementation

This module contains the main TinyAgent class that wraps the openai-agents SDK
and provides a simplified interface for creating and running agents with MCP tools.
"""

import logging
import os
from typing import Optional, List, Any, Dict
from pathlib import Path

try:
    from agents import Agent, Runner
    from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
    AGENTS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"OpenAI Agents SDK not available: {e}")
    AGENTS_AVAILABLE = False

from ..core.config import TinyAgentConfig, get_config
from ..mcp.manager import MCPServerManager

logger = logging.getLogger(__name__)

class TinyAgent:
    """
    TinyAgent - A multi-step agent framework with MCP tool integration.
    
    This class wraps the openai-agents SDK and provides a simplified interface
    for creating agents with MCP (Model Context Protocol) tool support.
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
            # Create model configuration
            model = OpenAIChatCompletionsModel(
                model=self.model_name,
                temperature=self.config.llm.temperature,
                max_tokens=self.config.llm.max_tokens
            )
            
            # Create agent with MCP servers
            agent = Agent(
                name=self.config.agent.name,
                instructions=self.instructions,
                model=model,
                mcp_servers=self.mcp_servers
            )
            
            self.logger.info(f"Created agent '{self.config.agent.name}' with model '{self.model_name}'")
            return agent
            
        except Exception as e:
            self.logger.error(f"Failed to create agent: {e}")
            # Create basic agent without MCP servers as fallback
            try:
                agent = Agent(
                    name=self.config.agent.name,
                    instructions=self.instructions,
                    model=self.model_name
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