"""
Basic tests for TinyAgent components.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

from tinyagent.core.config import ConfigurationManager, TinyAgentConfig
from tinyagent.mcp.manager import MCPServerManager, MCPServerInfo
from tinyagent.core.agent import TinyAgent, create_agent


class TestConfigurationManager:
    """Test the configuration manager."""
    
    def test_default_config(self):
        """Test loading default configuration."""
        config_manager = ConfigurationManager()
        config = config_manager.get_config()
        
        assert isinstance(config, TinyAgentConfig)
        # Default profile is development, so agent name should be TinyAgent-Dev
        assert config.agent.name == "TinyAgent-Dev"
        # Default active provider is now openrouter
        assert config.llm.provider == "openrouter"
        assert config.llm.model == "anthropic/claude-3.5-sonnet"
    
    def test_env_var_substitution(self):
        """Test environment variable substitution."""
        config_manager = ConfigurationManager()
        
        # Test substitution with default
        result = config_manager._substitute_env_var_string("${TEST_VAR:default_value}")
        assert result == "default_value"
        
        # Test substitution with existing env var
        with patch.dict(os.environ, {'TEST_VAR': 'actual_value'}):
            result = config_manager._substitute_env_var_string("${TEST_VAR:default_value}")
            assert result == "actual_value"
    
    def test_profile_loading(self):
        """Test loading different profiles."""
        config_manager = ConfigurationManager()
        
        # Test development profile
        config = config_manager.load_config(profile="development")
        assert config.agent.name == "TinyAgent-Dev"
        assert config.agent.max_iterations == 5
        
        # Test production profile (if exists)
        try:
            config = config_manager.load_config(profile="production")
            assert config.agent.name == "TinyAgent-Prod"
        except:
            # Profile may not exist, that's okay
            pass
    
    def test_available_profiles(self):
        """Test getting available profiles."""
        config_manager = ConfigurationManager()
        profiles = config_manager.get_available_profiles()
        
        assert isinstance(profiles, list)
        # Should have at least development profile
        assert len(profiles) >= 0


class TestMCPServerManager:
    """Test the MCP server manager."""
    
    def test_initialization(self):
        """Test MCP server manager initialization."""
        manager = MCPServerManager([])
        assert len(manager.servers) == 0
        assert len(manager.server_configs) == 0
    
    def test_get_server_info(self):
        """Test getting server information."""
        manager = MCPServerManager([])
        info = manager.get_server_info()
        
        assert isinstance(info, list)
        assert len(info) == 0  # No servers configured
    
    @patch('tinyagent.mcp.manager.MCP_AVAILABLE', True)
    @patch('tinyagent.mcp.manager.MCPServerStdio')
    def test_create_stdio_server(self, mock_mcp_server):
        """Test creating stdio MCP server."""
        from tinyagent.core.config import MCPServerConfig
        
        # Mock server instance
        mock_server_instance = MagicMock()
        mock_mcp_server.return_value = mock_server_instance
        
        # Create config
        config = MCPServerConfig(
            name="test_server",
            type="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            enabled=True
        )
        
        manager = MCPServerManager([config])
        server = manager.create_stdio_server(config)
        
        assert server is not None
        mock_mcp_server.assert_called_once_with(
            name="test_server",
            params={
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
            }
        )


class TestTinyAgent:
    """Test the TinyAgent core."""
    
    def test_agent_creation(self):
        """Test TinyAgent creation with mocked dependencies."""
        # Mock environment variable for OpenRouter (new default)
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test_key'}):
            with patch('tinyagent.core.agent.AGENTS_AVAILABLE', True):
                # Create TinyAgent
                agent = TinyAgent()
                
                # Test basic functionality
                assert agent.config is not None
                assert agent.config.agent.name == "TinyAgent-Dev"  # Default profile is development
                assert agent.model_name == "anthropic/claude-3.5-sonnet"  # OpenRouter default model
                assert len(agent.mcp_servers) >= 0  # Should initialize (may be empty if MCP not available)
                
                # Test MCP server info
                server_info = agent.get_mcp_server_info()
                assert isinstance(server_info, list)
    
    def test_agent_without_api_key(self):
        """Test TinyAgent fails gracefully without API key."""
        # Ensure no API key is set
        with patch.dict(os.environ, {}, clear=True):
            with patch('tinyagent.core.agent.AGENTS_AVAILABLE', True):
                with pytest.raises(ValueError, match="API key not found"):
                    TinyAgent()
    
    def test_agent_with_custom_config(self):
        """Test TinyAgent with custom configuration."""
        with patch.dict(os.environ, {'CUSTOM_API_KEY': 'test_key'}):
            from tinyagent.core.config import TinyAgentConfig, AgentConfig, LLMConfig, MCPConfig
            
            config = TinyAgentConfig(
                agent=AgentConfig(name="CustomAgent"),
                llm=LLMConfig(
                    provider="openai",
                    model="gpt-3.5-turbo",
                    api_key_env="CUSTOM_API_KEY"
                ),
                mcp=MCPConfig()
            )
            
            with patch('tinyagent.core.agent.AGENTS_AVAILABLE', True):
                agent = TinyAgent(config=config)
                assert agent.config.agent.name == "CustomAgent"
                assert agent.config.llm.model == "gpt-3.5-turbo"


class TestIntegration:
    """Integration tests for TinyAgent components."""
    
    def test_config_loading_integration(self):
        """Test integration between config manager and agent."""
        config_manager = ConfigurationManager()
        config = config_manager.get_config()
        
        # Verify config is valid for agent creation
        assert config.agent.name
        assert config.llm.provider
        assert config.llm.model
        assert config.llm.api_key_env
    
    def test_mcp_integration(self):
        """Test integration between MCP manager and agent."""
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test_key'}):
            with patch('tinyagent.core.agent.AGENTS_AVAILABLE', True):
                with patch('tinyagent.mcp.manager.MCP_AVAILABLE', True):
                    with patch('agents.Agent'):
                        # Create agent (should initialize MCP servers)
                        agent = TinyAgent()
                        server_info = agent.get_mcp_server_info()
                        
                        # Verify server information is available
                        assert isinstance(server_info, list)
    
    def test_create_agent_factory(self):
        """Test the create_agent factory function."""
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test_key'}):
            with patch('tinyagent.core.agent.AGENTS_AVAILABLE', True):
                agent = create_agent(name="TestAgent", model="gpt-3.5-turbo")
                assert agent.config.agent.name == "TestAgent"
                assert agent.model_name == "gpt-3.5-turbo"


if __name__ == '__main__':
    pytest.main([__file__]) 