"""
TinyAgent MCP Server Manager

This module manages Model Context Protocol (MCP) servers for TinyAgent.
It provides functionality to create, configure, and manage MCP servers
using the native openai-agents SDK.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    from agents.mcp import MCPServerStdio, MCPServerSse, MCPServerStreamableHttp
    MCP_AVAILABLE = True
except ImportError as e:
    logging.warning(f"MCP classes not available: {e}")
    MCP_AVAILABLE = False

from ..core.config import MCPServerConfig

logger = logging.getLogger(__name__)

@dataclass
class MCPServerInfo:
    """Information about an MCP server"""
    name: str
    type: str
    status: str
    config: Dict[str, Any]
    server_instance: Optional[Any] = None

class MCPServerManager:
    """
    Manages MCP servers for TinyAgent using the native openai-agents SDK.
    
    Supports stdio, SSE, and HTTP MCP server types with automatic
    server lifecycle management.
    """
    
    def __init__(self, server_configs: List[MCPServerConfig]):
        """
        Initialize the MCP server manager.
        
        Args:
            server_configs: List of MCP server configurations
        """
        self.server_configs = server_configs
        self.servers: Dict[str, MCPServerInfo] = {}
        self.logger = logging.getLogger(__name__)
        
        if not MCP_AVAILABLE:
            self.logger.warning("MCP functionality is disabled - openai-agents MCP classes not found")
    
    def create_stdio_server(self, config: MCPServerConfig) -> Optional[Any]:
        """
        Create a stdio MCP server.
        
        Args:
            config: MCP server configuration
            
        Returns:
            MCPServerStdio instance or None if creation fails
        """
        if not MCP_AVAILABLE:
            self.logger.error("Cannot create stdio server - MCP classes not available")
            return None
            
        try:
            # Extract stdio-specific parameters
            command = config.command
            args = config.args or []
            env = config.env or {}
            
            # Create stdio parameters dict
            params = {
                "command": command,
                "args": args,
            }
            
            # Add optional parameters if specified
            if env:
                params["env"] = env
            if hasattr(config, 'cwd') and config.cwd:
                params["cwd"] = config.cwd
            
            # Create the server
            server = MCPServerStdio(
                name=config.name,
                params=params,
            )
            
            self.logger.info(f"Created stdio MCP server: {config.name}")
            return server
            
        except Exception as e:
            self.logger.error(f"Failed to create stdio server {config.name}: {e}")
            return None
    
    def create_sse_server(self, config: MCPServerConfig) -> Optional[Any]:
        """
        Create an SSE MCP server.
        
        Args:
            config: MCP server configuration
            
        Returns:
            MCPServerSse instance or None if creation fails
        """
        if not MCP_AVAILABLE:
            self.logger.error("Cannot create SSE server - MCP classes not available")
            return None
            
        try:
            # Extract SSE-specific parameters
            url = config.url
            if not url:
                raise ValueError("SSE server requires URL")
            
            # Create SSE parameters dict
            params = {
                "url": url,
            }
            
            # Add optional parameters
            if config.headers:
                params["headers"] = config.headers
            if hasattr(config, 'timeout') and config.timeout:
                params["timeout"] = config.timeout
            
            # Create the server
            server = MCPServerSse(
                name=config.name,
                params=params,
            )
            
            self.logger.info(f"Created SSE MCP server: {config.name}")
            return server
            
        except Exception as e:
            self.logger.error(f"Failed to create SSE server {config.name}: {e}")
            return None
    
    def create_http_server(self, config: MCPServerConfig) -> Optional[Any]:
        """
        Create an HTTP MCP server.
        
        Args:
            config: MCP server configuration
            
        Returns:
            MCPServerStreamableHttp instance or None if creation fails
        """
        if not MCP_AVAILABLE:
            self.logger.error("Cannot create HTTP server - MCP classes not available")
            return None
            
        try:
            # Extract HTTP-specific parameters
            url = config.url
            if not url:
                raise ValueError("HTTP server requires URL")
            
            # Create HTTP parameters dict
            params = {
                "url": url,
            }
            
            # Add optional parameters
            if config.headers:
                params["headers"] = config.headers
            if hasattr(config, 'timeout') and config.timeout:
                params["timeout"] = config.timeout
            
            # Create the server
            server = MCPServerStreamableHttp(
                name=config.name,
                params=params,
            )
            
            self.logger.info(f"Created HTTP MCP server: {config.name}")
            return server
            
        except Exception as e:
            self.logger.error(f"Failed to create HTTP server {config.name}: {e}")
            return None
    
    def create_server(self, config: MCPServerConfig) -> Optional[Any]:
        """
        Create an MCP server based on its type.
        
        Args:
            config: MCP server configuration
            
        Returns:
            MCP server instance or None if creation fails
        """
        if config.type == "stdio":
            return self.create_stdio_server(config)
        elif config.type == "sse":
            return self.create_sse_server(config)
        elif config.type == "http":
            return self.create_http_server(config)
        else:
            self.logger.error(f"Unknown server type: {config.type}")
            return None
    
    def initialize_servers(self) -> List[Any]:
        """
        Initialize all configured MCP servers.
        
        Returns:
            List of successfully created MCP server instances
        """
        if not MCP_AVAILABLE:
            self.logger.warning("MCP not available - returning empty server list")
            return []
        
        created_servers = []
        
        for config in self.server_configs:
            if not config.enabled:
                self.logger.info(f"Skipping disabled MCP server: {config.name}")
                continue
                
            try:
                # Create server instance
                server = self.create_server(config)
                
                if server:
                    # Store server info
                    server_info = MCPServerInfo(
                        name=config.name,
                        type=config.type,
                        status="created",
                        config=config.__dict__,
                        server_instance=server
                    )
                    self.servers[config.name] = server_info
                    created_servers.append(server)
                    
                    self.logger.info(f"Successfully initialized MCP server: {config.name}")
                else:
                    # Store failed server info
                    server_info = MCPServerInfo(
                        name=config.name,
                        type=config.type,
                        status="failed",
                        config=config.__dict__
                    )
                    self.servers[config.name] = server_info
                    
            except Exception as e:
                self.logger.error(f"Failed to initialize server {config.name}: {e}")
                # Store failed server info
                server_info = MCPServerInfo(
                    name=config.name,
                    type=config.type,
                    status="error",
                    config=config.__dict__
                )
                self.servers[config.name] = server_info
        
        self.logger.info(f"Initialized {len(created_servers)} out of {len(self.server_configs)} MCP servers")
        return created_servers
    
    def get_server_info(self) -> List[MCPServerInfo]:
        """
        Get information about all configured servers.
        
        Returns:
            List of MCPServerInfo objects
        """
        return list(self.servers.values())
    
    def get_active_servers(self) -> List[Any]:
        """
        Get all successfully created server instances.
        
        Returns:
            List of active MCP server instances
        """
        return [
            info.server_instance 
            for info in self.servers.values() 
            if info.server_instance is not None
        ]
    
    def is_available(self) -> bool:
        """
        Check if MCP functionality is available.
        
        Returns:
            True if MCP classes are available, False otherwise
        """
        return MCP_AVAILABLE


# Global MCP server manager instance
_mcp_manager: Optional[MCPServerManager] = None


def get_mcp_manager() -> MCPServerManager:
    """Get the global MCP server manager instance."""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPServerManager([])
    return _mcp_manager


def get_mcp_servers() -> List[Any]:
    """Get all initialized MCP servers."""
    return get_mcp_manager().get_active_servers() 