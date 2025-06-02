"""
MCP Connection Pool Manager
Manages connection pools for MCP servers to improve performance and resource utilization.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, AsyncContextManager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from ..core.config import MCPServerConfig
from .cache import MCPToolCache, ServerStatus, PerformanceMetrics

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """Information about a pooled connection"""
    server_name: str
    connection: Any
    created_at: datetime
    last_used: datetime
    use_count: int = 0
    is_active: bool = True
    error_count: int = 0


@dataclass
class PoolConfig:
    """Configuration for connection pool"""
    max_connections_per_server: int = 3
    connection_timeout: float = 30.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    idle_timeout: float = 300.0  # 5 minutes
    health_check_interval: float = 60.0  # 1 minute
    max_error_count: int = 5


class MCPConnectionPool:
    """
    Connection pool manager for MCP servers.
    
    Provides:
    - Connection reuse and pooling
    - Automatic connection health monitoring
    - Connection lifecycle management
    - Performance optimization through pooling
    - Error handling and recovery
    """
    
    def __init__(self, config: Optional[PoolConfig] = None):
        """
        Initialize connection pool manager.
        
        Args:
            config: Pool configuration (uses defaults if None)
        """
        self.config = config or PoolConfig()
        self._pools: Dict[str, List[ConnectionInfo]] = {}
        self._pool_locks: Dict[str, asyncio.Lock] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(f"MCPConnectionPool initialized with config: {self.config}")
    
    async def start(self):
        """Start the connection pool manager"""
        if self._running:
            return
            
        self._running = True
        
        # Start background tasks
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info("Connection pool manager started")
    
    async def stop(self):
        """Stop the connection pool manager and cleanup all connections"""
        if not self._running:
            return
            
        self._running = False
        
        # Cancel background tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        await self._close_all_connections()
        
        logger.info("Connection pool manager stopped")
    
    @asynccontextmanager
    async def get_connection(self, server_config: MCPServerConfig) -> AsyncContextManager[Any]:
        """
        Get a connection from the pool (or create new one).
        
        Args:
            server_config: MCP server configuration
            
        Yields:
            MCP server connection
        """
        server_name = server_config.name
        connection = None
        connection_info = None
        
        try:
            # Get or create pool lock for this server
            if server_name not in self._pool_locks:
                self._pool_locks[server_name] = asyncio.Lock()
            
            async with self._pool_locks[server_name]:
                # Try to get existing connection from pool
                connection_info = await self._get_pooled_connection(server_name)
                
                if connection_info:
                    logger.debug(f"Reusing pooled connection for {server_name}")
                    connection = connection_info.connection
                else:
                    # Create new connection
                    logger.debug(f"Creating new connection for {server_name}")
                    connection = await self._create_connection(server_config)
                    
                    if connection:
                        # Add to pool
                        connection_info = ConnectionInfo(
                            server_name=server_name,
                            connection=connection,
                            created_at=datetime.now(),
                            last_used=datetime.now()
                        )
                        await self._add_to_pool(connection_info)
            
            if not connection:
                raise RuntimeError(f"Failed to get connection for {server_name}")
            
            # Update usage statistics
            if connection_info:
                connection_info.last_used = datetime.now()
                connection_info.use_count += 1
            
            # CRITICAL FIX: Ensure connection context is properly managed
            try:
                # Return connection directly for manual context management
                yield connection
            finally:
                # Mark connection as returned (but don't close it, leave it in pool)
                if connection_info:
                    connection_info.last_used = datetime.now()
            
        except Exception as e:
            logger.error(f"Error with connection for {server_name}: {e}")
            
            # Mark connection as failed if we have connection_info
            if connection_info:
                connection_info.error_count += 1
                if connection_info.error_count >= self.config.max_error_count:
                    connection_info.is_active = False
                    logger.warning(f"Connection for {server_name} marked as inactive due to errors")
            
            raise
        
    async def _get_pooled_connection(self, server_name: str) -> Optional[ConnectionInfo]:
        """Get an available connection from the pool"""
        if server_name not in self._pools:
            return None
        
        pool = self._pools[server_name]
        
        # Find active, healthy connection
        for conn_info in pool:
            if (conn_info.is_active and 
                conn_info.error_count < self.config.max_error_count and
                self._is_connection_fresh(conn_info)):
                return conn_info
        
        return None
    
    async def _create_connection(self, server_config: MCPServerConfig) -> Optional[Any]:
        """Create a new MCP server connection"""
        try:
            # Import MCP classes dynamically
            from agents.mcp import MCPServerStdio, MCPServerSse, MCPServerStreamableHttp
            
            # Create server instance based on type using correct parameter format
            if server_config.type == "stdio":
                params = {
                    "command": server_config.command,
                    "args": server_config.args or [],
                }
                if server_config.env:
                    params["env"] = server_config.env
                
                server = MCPServerStdio(
                    params=params,
                    name=server_config.name
                )
            elif server_config.type == "sse":
                params = {
                    "url": server_config.url,
                }
                if server_config.headers:
                    params["headers"] = server_config.headers
                
                server = MCPServerSse(
                    params=params,
                    name=server_config.name
                )
            elif server_config.type == "http":
                params = {
                    "url": server_config.url,
                }
                if server_config.headers:
                    params["headers"] = server_config.headers
                
                server = MCPServerStreamableHttp(
                    params=params,
                    name=server_config.name
                )
            else:
                raise ValueError(f"Unsupported server type: {server_config.type}")
            
            # Connect with timeout
            connected_server = await asyncio.wait_for(
                server.__aenter__(),
                timeout=self.config.connection_timeout
            )
            
            logger.info(f"Created new connection for {server_config.name}")
            return connected_server
            
        except Exception as e:
            logger.error(f"Failed to create connection for {server_config.name}: {e}")
            return None
    
    async def _add_to_pool(self, connection_info: ConnectionInfo):
        """Add connection to the pool"""
        server_name = connection_info.server_name
        
        if server_name not in self._pools:
            self._pools[server_name] = []
        
        pool = self._pools[server_name]
        
        # Check pool size limit
        if len(pool) >= self.config.max_connections_per_server:
            # Remove oldest connection
            oldest = min(pool, key=lambda c: c.last_used)
            await self._close_connection(oldest)
            pool.remove(oldest)
        
        pool.append(connection_info)
        logger.debug(f"Added connection to pool for {server_name}, pool size: {len(pool)}")
    
    def _is_connection_fresh(self, connection_info: ConnectionInfo) -> bool:
        """Check if connection is still fresh (not idle too long)"""
        idle_time = datetime.now() - connection_info.last_used
        return idle_time.total_seconds() < self.config.idle_timeout
    
    async def _close_connection(self, connection_info: ConnectionInfo):
        """Close a single connection"""
        try:
            if hasattr(connection_info.connection, '__aexit__'):
                await connection_info.connection.__aexit__(None, None, None)
            elif hasattr(connection_info.connection, 'close'):
                await connection_info.connection.close()
            
            logger.debug(f"Closed connection for {connection_info.server_name}")
        except Exception as e:
            logger.warning(f"Error closing connection for {connection_info.server_name}: {e}")
    
    async def _close_all_connections(self):
        """Close all connections in all pools"""
        for server_name, pool in self._pools.items():
            for conn_info in pool:
                await self._close_connection(conn_info)
            pool.clear()
        
        self._pools.clear()
        logger.info("All connections closed")
    
    async def _cleanup_loop(self):
        """Background task to cleanup idle and failed connections"""
        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._cleanup_idle_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _cleanup_idle_connections(self):
        """Remove idle and failed connections from pools"""
        current_time = datetime.now()
        
        for server_name, pool in list(self._pools.items()):
            connections_to_remove = []
            
            for conn_info in pool:
                # Check if connection should be removed
                idle_time = current_time - conn_info.last_used
                
                if (not conn_info.is_active or 
                    conn_info.error_count >= self.config.max_error_count or
                    idle_time.total_seconds() > self.config.idle_timeout):
                    
                    connections_to_remove.append(conn_info)
            
            # Remove and close connections
            for conn_info in connections_to_remove:
                await self._close_connection(conn_info)
                pool.remove(conn_info)
                logger.debug(f"Cleaned up connection for {server_name}")
            
            # Remove empty pools
            if not pool:
                del self._pools[server_name]
                if server_name in self._pool_locks:
                    del self._pool_locks[server_name]
    
    async def _health_check_loop(self):
        """Background task to perform health checks on connections"""
        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
    
    async def _perform_health_checks(self):
        """Perform health checks on pooled connections"""
        for server_name, pool in self._pools.items():
            for conn_info in pool:
                if conn_info.is_active:
                    try:
                        # Try a simple operation to check connection health
                        if hasattr(conn_info.connection, 'list_tools'):
                            # Use asyncio.wait_for with a short timeout for health check
                            await asyncio.wait_for(
                                conn_info.connection.list_tools(),
                                timeout=5.0
                            )
                        
                        # Reset error count on successful health check
                        conn_info.error_count = 0
                        
                    except Exception as e:
                        logger.warning(f"Health check failed for {server_name}: {e}")
                        conn_info.error_count += 1
                        
                        if conn_info.error_count >= self.config.max_error_count:
                            conn_info.is_active = False
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get statistics about connection pools"""
        stats = {
            "total_pools": len(self._pools),
            "total_connections": sum(len(pool) for pool in self._pools.values()),
            "server_stats": {}
        }
        
        for server_name, pool in self._pools.items():
            active_connections = sum(1 for conn in pool if conn.is_active)
            total_uses = sum(conn.use_count for conn in pool)
            avg_age = sum((datetime.now() - conn.created_at).total_seconds() for conn in pool) / len(pool) if pool else 0
            
            stats["server_stats"][server_name] = {
                "total_connections": len(pool),
                "active_connections": active_connections,
                "total_uses": total_uses,
                "avg_connection_age_seconds": avg_age
            }
        
        return stats
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics (alias for get_pool_stats)"""
        return self.get_pool_stats()
    
    async def invalidate_server_connections(self, server_name: str):
        """Invalidate all connections for a specific server"""
        if server_name in self._pools:
            async with self._pool_locks.get(server_name, asyncio.Lock()):
                pool = self._pools[server_name]
                for conn_info in pool:
                    await self._close_connection(conn_info)
                pool.clear()
                
                logger.info(f"Invalidated all connections for {server_name}")
    
    async def refresh_server_connections(self, server_name: str):
        """Refresh connections for a specific server"""
        await self.invalidate_server_connections(server_name)
        logger.info(f"Refreshed connections for {server_name}")


# Global connection pool instance
_connection_pool: Optional[MCPConnectionPool] = None


async def get_connection_pool() -> MCPConnectionPool:
    """Get the global connection pool instance"""
    global _connection_pool
    
    if _connection_pool is None:
        _connection_pool = MCPConnectionPool()
        await _connection_pool.start()
    
    return _connection_pool


async def shutdown_connection_pool():
    """Shutdown the global connection pool"""
    global _connection_pool
    
    if _connection_pool:
        await _connection_pool.stop()
        _connection_pool = None 