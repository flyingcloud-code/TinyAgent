"""
TinyAgent MCP Server Manager

This module manages Model Context Protocol (MCP) servers for TinyAgent.
It provides functionality to create, configure, and manage MCP servers
using the native openai-agents SDK with enhanced performance optimization.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

try:
    from agents.mcp import MCPServerStdio, MCPServerSse, MCPServerStreamableHttp
    MCP_AVAILABLE = True
except ImportError as e:
    logging.warning(f"MCP classes not available: {e}")
    MCP_AVAILABLE = False

from ..core.config import MCPServerConfig
from .cache import MCPToolCache, ToolInfo, ServerStatus, PerformanceMetrics
from .pool import MCPConnectionPool, PoolConfig, get_connection_pool

logger = logging.getLogger(__name__)

@dataclass
class MCPServerInfo:
    """Information about an MCP server"""
    name: str
    type: str
    status: str
    config: Dict[str, Any]
    server_instance: Optional[Any] = None
    tools: Optional[List[ToolInfo]] = None

class EnhancedMCPServerManager:
    """
    Enhanced MCP server manager with caching, connection pooling, and performance optimization.
    
    Provides comprehensive MCP server management for TinyAgent including:
    - Connection pooling for improved performance
    - Tool discovery and caching with TTL
    - Server health monitoring and statistics
    - Performance metrics and optimization
    - Automatic retry and error handling
    """
    
    def __init__(
        self, 
        server_configs: List[MCPServerConfig],
        tool_cache: Optional[MCPToolCache] = None,
        connection_pool: Optional[MCPConnectionPool] = None,
        cache_duration: int = 300,
        enable_performance_tracking: bool = True,
        pool_config: Optional[PoolConfig] = None
    ):
        """
        Initialize the enhanced MCP server manager.
        
        Args:
            server_configs: List of MCP server configurations
            tool_cache: Optional tool cache instance (creates new if None)
            connection_pool: Optional connection pool (creates new if None)
            cache_duration: Cache duration in seconds
            enable_performance_tracking: Whether to track performance metrics
            pool_config: Connection pool configuration
        """
        self.server_configs = server_configs
        self.servers: Dict[str, MCPServerInfo] = {}
        self.logger = logging.getLogger(__name__)
        self.enable_performance_tracking = enable_performance_tracking
        
        # Initialize tool cache
        if tool_cache is None:
            self.tool_cache = MCPToolCache(
                cache_duration=cache_duration,
                max_cache_size=100,
                persist_cache=True
            )
        else:
            self.tool_cache = tool_cache
        
        # Initialize connection pool
        self.pool_config = pool_config or PoolConfig()
        self.connection_pool = connection_pool
        self._pool_initialized = False
        
        # Performance tracking
        self._operation_stats = {
            'tool_discoveries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'connection_reuses': 0,
            'new_connections': 0,
            'failed_operations': 0
        }
        
        if not MCP_AVAILABLE:
            self.logger.warning("MCP functionality is disabled - openai-agents MCP classes not found")
    
    async def _ensure_connection_pool(self):
        """Ensure connection pool is initialized"""
        if not self._pool_initialized:
            if self.connection_pool is None:
                self.connection_pool = await get_connection_pool()
            self._pool_initialized = True
    
    async def initialize_with_caching(self) -> Dict[str, List[ToolInfo]]:
        """
        Initialize servers and cache their tools with connection pooling.
        
        Returns:
            Dictionary mapping server names to their tool lists
        """
        if not MCP_AVAILABLE:
            self.logger.error("Cannot initialize servers - MCP classes not available")
            return {}
        
        await self._ensure_connection_pool()
        server_tools = {}
        
        for config in self.server_configs:
            if not config.enabled:
                self.logger.debug(f"Skipping disabled server: {config.name}")
                continue
            
            try:
                # Check cache first
                cached_tools = self.tool_cache.get_cached_tools(config.name)
                if cached_tools is not None:
                    self.logger.info(f"Using cached tools for server {config.name}: {len(cached_tools)} tools")
                    server_tools[config.name] = cached_tools
                    self._operation_stats['cache_hits'] += 1
                    
                    # Update server status in cache
                    server_status = ServerStatus(
                        name=config.name,
                        type=config.type,
                        status="cached",
                        tools_count=len(cached_tools),
                        last_ping_time=datetime.now()
                    )
                    self.tool_cache.update_server_status(server_status)
                    continue
                
                # No cache available, discover tools from server using connection pool
                self._operation_stats['cache_misses'] += 1
                self.logger.info(f"Discovering tools for server {config.name} using connection pool")
                tools = await self.discover_server_tools_with_pool(config)
                
                if tools:
                    server_tools[config.name] = tools
                    self.tool_cache.cache_server_tools(config.name, tools)
                    self.logger.info(f"Cached {len(tools)} tools for server {config.name}")
                    self._operation_stats['tool_discoveries'] += 1
                else:
                    self.logger.warning(f"No tools discovered for server {config.name}")
                
            except Exception as e:
                self.logger.error(f"Failed to initialize server {config.name}: {e}")
                self._operation_stats['failed_operations'] += 1
                
                # Update server status with error
                server_status = ServerStatus(
                    name=config.name,
                    type=config.type,
                    status="error",
                    error_message=str(e),
                    tools_count=0,
                    last_ping_time=datetime.now()
                )
                self.tool_cache.update_server_status(server_status)
                continue
        
        self.logger.info(f"Server initialization complete: {len(server_tools)} servers with tools available")
        self.logger.info(f"Performance stats: {self._operation_stats}")
        return server_tools
    
    async def discover_server_tools_with_pool(self, config: MCPServerConfig) -> List[ToolInfo]:
        """
        Discover tools from an MCP server using connection pool.
        
        Args:
            config: MCP server configuration
            
        Returns:
            List of discovered tools
        """
        start_time = datetime.now()
        tools = []
        
        try:
            await self._ensure_connection_pool()
            
            # CRITICAL FIX: Use manual connection management instead of async context manager
            # This avoids the cancel scope issue in asyncio task groups
            connection = None
            try:
                async with self.connection_pool.get_connection(config) as connected_server:
                    connection = connected_server
                    self.logger.debug(f"Connected to server {config.name} via pool, listing tools...")
                    
                    # List tools using the openai-agents MCP interface
                    tools_response = await connected_server.list_tools()
                    
                    # Debug: log the actual response structure
                    self.logger.debug(f"Tools response type: {type(tools_response)}")
                    
                    # Handle different response formats
                    tools_list = None
                    if hasattr(tools_response, 'tools'):
                        tools_list = tools_response.tools
                    elif hasattr(tools_response, 'result') and hasattr(tools_response.result, 'tools'):
                        tools_list = tools_response.result.tools
                    elif isinstance(tools_response, list):
                        tools_list = tools_response
                    elif hasattr(tools_response, '__iter__'):
                        try:
                            tools_list = list(tools_response)
                        except Exception:
                            pass
                    
                    if tools_list:
                        for tool in tools_list:
                            try:
                                # Handle different tool object formats
                                tool_name = getattr(tool, 'name', str(tool))
                                tool_description = getattr(tool, 'description', f"Tool from {config.name}")
                                
                                # Try to get schema
                                tool_schema = {}
                                if hasattr(tool, 'inputSchema'):
                                    tool_schema = tool.inputSchema
                                elif hasattr(tool, 'schema'):
                                    tool_schema = tool.schema
                                
                                # Create ToolInfo object
                                tool_info = ToolInfo(
                                    name=tool_name,
                                    description=tool_description,
                                    server_name=config.name,
                                    schema=tool_schema,
                                    category=self._categorize_tool(tool_name, tool_description),
                                    last_updated=datetime.now(),
                                    performance_metrics=PerformanceMetrics(
                                        success_rate=1.0,
                                        avg_response_time=0.0,
                                        total_calls=0,
                                        last_call_time=None
                                    )
                                )
                                
                                tools.append(tool_info)
                                self.logger.debug(f"Discovered tool: {tool_name} from {config.name}")
                                
                            except Exception as tool_error:
                                self.logger.warning(f"Error processing tool from {config.name}: {tool_error}")
                                continue
                        
                        # Update server status
                        execution_time = (datetime.now() - start_time).total_seconds()
                        server_status = ServerStatus(
                            name=config.name,
                            type=config.type,
                            status="connected",
                            tools_count=len(tools),
                            last_ping_time=datetime.now(),
                            response_time=execution_time
                        )
                        self.tool_cache.update_server_status(server_status)
                        
                        self.logger.info(f"Discovered {len(tools)} tools from {config.name} in {execution_time:.2f}s")
                
            except Exception as conn_error:
                # Let the error bubble up to be handled by the outer try-catch
                raise conn_error
                
        except Exception as e:
            self.logger.error(f"Failed to discover tools from {config.name}: {e}")
            self._operation_stats['failed_operations'] += 1
            
            # Update server status with error
            server_status = ServerStatus(
                name=config.name,
                type=config.type,
                status="error",
                error_message=str(e),
                tools_count=0,
                last_ping_time=datetime.now()
            )
            self.tool_cache.update_server_status(server_status)
        
        return tools

    def _categorize_tool(self, tool_name: str, description: str) -> str:
        """Categorize tool based on name and description"""
        tool_name_lower = tool_name.lower()
        description_lower = description.lower()
        
        # File operations
        if any(keyword in tool_name_lower for keyword in ['file', 'read', 'write', 'create', 'delete', 'list']):
            return "file_operations"
        elif any(keyword in description_lower for keyword in ['file', 'directory', 'folder']):
            return "file_operations"
        
        # Web operations
        elif any(keyword in tool_name_lower for keyword in ['fetch', 'url', 'web', 'http', 'download']):
            return "web_operations"
        elif any(keyword in description_lower for keyword in ['web', 'url', 'fetch', 'download']):
            return "web_operations"
        
        # Search operations
        elif any(keyword in tool_name_lower for keyword in ['search', 'find', 'query']):
            return "search_operations"
        elif any(keyword in description_lower for keyword in ['search', 'find', 'query']):
            return "search_operations"
        
        # Thinking/reasoning
        elif any(keyword in tool_name_lower for keyword in ['think', 'reason', 'analyze']):
            return "reasoning_operations"
        elif any(keyword in description_lower for keyword in ['think', 'reason', 'analyze']):
            return "reasoning_operations"
        
        # Weather operations
        elif any(keyword in tool_name_lower for keyword in ['weather', 'temperature', 'climate']):
            return "weather_operations"
        elif any(keyword in description_lower for keyword in ['weather', 'temperature', 'climate']):
            return "weather_operations"
        
        return "general_operations"

    async def get_server_tools_with_performance(self, server_name: str, force_refresh: bool = False) -> List[ToolInfo]:
        """
        Get server tools with performance tracking.
        
        Args:
            server_name: Name of the server
            force_refresh: Whether to force refresh from server
            
        Returns:
            List of tools from the server
        """
        start_time = datetime.now()
        
        try:
            if not force_refresh:
                # Try cache first
                cached_tools = self.tool_cache.get_cached_tools(server_name)
                if cached_tools is not None:
                    self._operation_stats['cache_hits'] += 1
                    self.logger.debug(f"Cache hit for {server_name}: {len(cached_tools)} tools")
                    return cached_tools
            
            # Cache miss or forced refresh
            self._operation_stats['cache_misses'] += 1
            
            # Find server config
            server_config = None
            for config in self.server_configs:
                if config.name == server_name:
                    server_config = config
                    break
            
            if not server_config:
                raise ValueError(f"Server configuration not found: {server_name}")
            
            # Discover tools using connection pool
            tools = await self.discover_server_tools_with_pool(server_config)
            
            if tools:
                # Cache the results
                self.tool_cache.cache_server_tools(server_name, tools)
                self.logger.info(f"Refreshed and cached {len(tools)} tools for {server_name}")
            
            return tools
            
        except Exception as e:
            self.logger.error(f"Error getting tools for {server_name}: {e}")
            self._operation_stats['failed_operations'] += 1
            return []
        
        finally:
            # Track performance
            execution_time = (datetime.now() - start_time).total_seconds()
            if self.enable_performance_tracking:
                self.tool_cache.update_performance_metric(
                    server_name, 
                    success=True,  # We got here without exception
                    response_time=execution_time
                )

    def get_enhanced_performance_summary(self) -> Dict[str, Any]:
        """Get enhanced performance summary including pool statistics"""
        summary = {
            "total_servers": len(self.server_configs),
            "enabled_servers": len([c for c in self.server_configs if c.enabled]),
            "operations": dict(self._operation_stats),
            "cache_stats": self.tool_cache.get_cache_stats(),
        }
        
        # Add connection pool stats if available
        if self.connection_pool:
            pool_stats = self.connection_pool.get_performance_stats()
            summary["connection_pool"] = pool_stats
        
        # Calculate derived metrics
        total_operations = self._operation_stats['cache_hits'] + self._operation_stats['cache_misses']
        if total_operations > 0:
            summary["cache_hit_rate"] = self._operation_stats['cache_hits'] / total_operations
        else:
            summary["cache_hit_rate"] = 0.0
        
        # Connection reuse efficiency
        total_connections = self._operation_stats['connection_reuses'] + self._operation_stats['new_connections']
        if total_connections > 0:
            summary["connection_reuse_rate"] = self._operation_stats['connection_reuses'] / total_connections
        else:
            summary["connection_reuse_rate"] = 0.0
        
        return summary

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.tool_cache.get_cache_stats()

    async def refresh_server_cache_with_pool(self, server_name: Optional[str] = None):
        """Refresh server cache using connection pool"""
        if server_name:
            # Refresh specific server
            await self.get_server_tools_with_performance(server_name, force_refresh=True)
            
            # Also refresh connection pool for this server
            if self.connection_pool:
                await self.connection_pool.refresh_server_connections(server_name)
        else:
            # Refresh all servers
            for config in self.server_configs:
                if config.enabled:
                    await self.get_server_tools_with_performance(config.name, force_refresh=True)
            
            # Clear all connection pools
            if self.connection_pool:
                for config in self.server_configs:
                    if config.enabled:
                        await self.connection_pool.refresh_server_connections(config.name)

    def update_tool_performance_with_tracking(self, tool_name: str, server_name: str, success: bool, response_time: float):
        """Update tool performance with enhanced tracking"""
        # Update cache performance
        self.tool_cache.update_performance_metric(server_name, success, response_time)
        
        # Update operation stats
        if success:
            self._operation_stats.setdefault('successful_tool_calls', 0)
            self._operation_stats['successful_tool_calls'] += 1
        else:
            self._operation_stats['failed_operations'] += 1
        
        # Update specific tool performance in cache
        cached_tools = self.tool_cache.get_cached_tools(server_name)
        if cached_tools:
            for tool in cached_tools:
                if tool.name == tool_name and tool.performance_metrics:
                    # Update tool-specific metrics
                    metrics = tool.performance_metrics
                    metrics.total_calls += 1
                    
                    # Update success rate (exponential moving average)
                    alpha = 0.1  # Learning rate
                    if success:
                        metrics.success_rate = alpha * 1.0 + (1 - alpha) * metrics.success_rate
                    else:
                        metrics.success_rate = alpha * 0.0 + (1 - alpha) * metrics.success_rate
                    
                    # Update average response time (exponential moving average)
                    metrics.avg_response_time = alpha * response_time + (1 - alpha) * metrics.avg_response_time
                    metrics.last_call_time = datetime.now()
                    
                    break

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
            
            # Create the server using correct parameter format
            server = MCPServerStdio(
                params=params,
                name=config.name,
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
            
            # Create the server using correct parameter format
            server = MCPServerSse(
                params=params,
                name=config.name,
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
            
            # Create the server using correct parameter format
            server = MCPServerStreamableHttp(
                params=params,
                name=config.name,
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
            List of successfully created server instances
        """
        if not MCP_AVAILABLE:
            self.logger.error("Cannot initialize servers - MCP classes not available")
            return []
        
        servers = []
        
        for config in self.server_configs:
            if not config.enabled:
                self.logger.debug(f"Skipping disabled server: {config.name}")
                continue
            
            try:
                server = self.create_server(config)
                if server:
                    servers.append(server)
                    
                    # Store server info
                    server_info = MCPServerInfo(
                        name=config.name,
                        type=config.type,
                        status="created",
                        config=config.__dict__,
                        server_instance=server
                    )
                    self.servers[config.name] = server_info
                    
                    self.logger.info(f"Successfully initialized server: {config.name}")
                else:
                    self.logger.error(f"Failed to create server: {config.name}")
                    
            except Exception as e:
                self.logger.error(f"Error initializing server {config.name}: {e}")
                continue
        
        self.logger.info(f"Initialized {len(servers)} out of {len(self.server_configs)} servers")
        return servers
    
    def get_server_info(self) -> List[MCPServerInfo]:
        """
        Get information about all configured servers.
        
        Returns:
            List of server information objects
        """
        server_info_list = []
        
        for config in self.server_configs:
            # Get cached server info if available
            if config.name in self.servers:
                server_info = self.servers[config.name]
            else:
                # Create server info from config
                server_info = MCPServerInfo(
                    name=config.name,
                    type=config.type,
                    status="not_initialized",
                    config=config.__dict__
                )
            
            # Add cached tools if available
            cached_tools = self.tool_cache.get_cached_tools(config.name)
            if cached_tools:
                server_info.tools = cached_tools
            
            server_info_list.append(server_info)
        
        return server_info_list
    
    def get_active_servers(self) -> List[Any]:
        """
        Get list of active server instances.
        
        Returns:
            List of active server instances
        """
        return [info.server_instance for info in self.servers.values() if info.server_instance]
    
    def is_available(self) -> bool:
        """
        Check if MCP functionality is available.
        
        Returns:
            True if MCP is available, False otherwise
        """
        return MCP_AVAILABLE


def get_mcp_manager() -> EnhancedMCPServerManager:
    """
    Get the global MCP server manager instance.
    
    Returns:
        EnhancedMCPServerManager instance
    """
    from ..core.config import get_config
    config = get_config()
    
    # Filter enabled servers
    enabled_servers = [
        server for server in config.mcp.servers 
        if server.enabled
    ]
    
    return EnhancedMCPServerManager(enabled_servers)


# Backward compatibility alias
MCPServerManager = EnhancedMCPServerManager


def get_mcp_servers() -> List[Any]:
    """
    Get initialized MCP servers.
    
    Returns:
        List of MCP server instances
    """
    manager = get_mcp_manager()
    return manager.get_active_servers() 