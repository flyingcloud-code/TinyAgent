"""
TinyAgent MCP Tool Cache System

This module provides caching functionality for MCP servers and their tools,
improving performance and providing tool visibility.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
import hashlib
import os
import tempfile
import shutil

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics for a tool"""
    success_rate: float = 0.0
    avg_response_time: float = 0.0
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    last_call_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        # Convert datetime objects to ISO strings
        if self.last_call_time:
            result['last_call_time'] = self.last_call_time.isoformat()
        if self.last_success_time:
            result['last_success_time'] = self.last_success_time.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PerformanceMetrics':
        """Create from dictionary"""
        # Convert ISO strings back to datetime objects
        if 'last_call_time' in data and data['last_call_time']:
            data['last_call_time'] = datetime.fromisoformat(data['last_call_time'])
        if 'last_success_time' in data and data['last_success_time']:
            data['last_success_time'] = datetime.fromisoformat(data['last_success_time'])
        return cls(**data)
    
    def update_call_result(self, success: bool, response_time: float):
        """Update metrics with a new call result"""
        self.total_calls += 1
        self.last_call_time = datetime.now()
        
        if success:
            self.successful_calls += 1
            self.last_success_time = datetime.now()
        else:
            self.failed_calls += 1
        
        # Update success rate
        self.success_rate = self.successful_calls / self.total_calls if self.total_calls > 0 else 0.0
        
        # Update average response time (exponential moving average)
        if self.avg_response_time == 0.0:
            self.avg_response_time = response_time
        else:
            # 20% weight to new value, 80% to historical average
            self.avg_response_time = 0.8 * self.avg_response_time + 0.2 * response_time

@dataclass
class ToolInfo:
    """Information about an MCP tool"""
    name: str
    description: str
    server_name: str
    schema: Dict[str, Any]
    category: str = "general"
    last_updated: Optional[datetime] = None
    performance_metrics: Optional[PerformanceMetrics] = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()
        if self.performance_metrics is None:
            self.performance_metrics = PerformanceMetrics()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        if self.last_updated:
            result['last_updated'] = self.last_updated.isoformat()
        if self.performance_metrics:
            result['performance_metrics'] = self.performance_metrics.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolInfo':
        """Create from dictionary"""
        if 'last_updated' in data and data['last_updated']:
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        if 'performance_metrics' in data and data['performance_metrics']:
            data['performance_metrics'] = PerformanceMetrics.from_dict(data['performance_metrics'])
        return cls(**data)

@dataclass
class ServerStatus:
    """Status information for an MCP server"""
    name: str
    type: str
    status: str  # "connected", "disconnected", "error"
    last_ping_time: Optional[datetime] = None
    connection_count: int = 0
    error_message: Optional[str] = None
    tools_count: int = 0
    response_time: float = 0.0  # Response time in seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        if self.last_ping_time:
            result['last_ping_time'] = self.last_ping_time.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServerStatus':
        """Create from dictionary"""
        if 'last_ping_time' in data and data['last_ping_time']:
            data['last_ping_time'] = datetime.fromisoformat(data['last_ping_time'])
        return cls(**data)

class MCPToolCache:
    """
    Caching system for MCP servers and their tools.
    
    Provides fast access to tool information and performance metrics,
    with configurable cache duration and persistence.
    """
    
    def __init__(
        self, 
        cache_duration: int = 300,  # 5 minutes
        max_cache_size: int = 100,
        persist_cache: bool = True,
        cache_file: Optional[Path] = None
    ):
        """
        Initialize the MCP tool cache.
        
        Args:
            cache_duration: Cache duration in seconds
            max_cache_size: Maximum number of tools to cache
            persist_cache: Whether to persist cache to disk
            cache_file: Path to cache file (auto-generated if None)
        """
        self.cache_duration = cache_duration
        self.max_cache_size = max_cache_size
        self.persist_cache = persist_cache
        
        # Cache storage
        self._tool_metadata: Dict[str, List[ToolInfo]] = {}  # server_name -> tools
        self._server_status: Dict[str, ServerStatus] = {}    # server_name -> status
        self._cache_timestamps: Dict[str, datetime] = {}     # server_name -> timestamp
        self._global_performance: PerformanceMetrics = PerformanceMetrics()
        
        # Cache file management
        if cache_file is None:
            cache_dir = Path.home() / ".tinyagent" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            self.cache_file = cache_dir / "mcp_tools_cache.json"
        else:
            self.cache_file = cache_file
        
        self.logger = logging.getLogger(__name__)
        
        # Load persistent cache if enabled
        if self.persist_cache:
            self._load_cache_from_disk()
        
        self.logger.info(f"MCPToolCache initialized with {cache_duration}s duration, max size {max_cache_size}")
    
    def cache_server_tools(self, server_name: str, tools: List[ToolInfo]):
        """
        Cache tools for a server.
        
        Args:
            server_name: Name of the MCP server
            tools: List of tools to cache
        """
        # Check if we already have valid cached tools for this server
        if self.is_cache_valid(server_name):
            existing_tools = self._tool_metadata.get(server_name, [])
            if len(existing_tools) == len(tools):
                # Same number of tools, likely already cached
                self.logger.debug(f"Server {server_name} tools already cached ({len(tools)} tools)")
                return
        
        # Enforce cache size limits
        if len(tools) > self.max_cache_size:
            # Only log this warning once per server per session
            cache_key = f"size_warning_{server_name}"
            if not hasattr(self, '_logged_warnings'):
                self._logged_warnings = set()
            
            if cache_key not in self._logged_warnings:
                self.logger.warning(f"Server {server_name} has {len(tools)} tools, limiting to {self.max_cache_size}")
                self._logged_warnings.add(cache_key)
            
            tools = tools[:self.max_cache_size]
        
        # Cache the tools
        self._tool_metadata[server_name] = tools
        self._cache_timestamps[server_name] = datetime.now()
        
        # Update server status
        if server_name in self._server_status:
            self._server_status[server_name].tools_count = len(tools)
            self._server_status[server_name].last_ping_time = datetime.now()
        
        self.logger.debug(f"Cached {len(tools)} tools for server {server_name}")
        
        # Persist to disk if enabled
        if self.persist_cache:
            try:
                self._save_cache_to_disk()
            except Exception as e:
                self.logger.warning(f"Failed to persist cache: {e}")
    
    def get_cached_tools(self, server_name: str) -> Optional[List[ToolInfo]]:
        """
        Get cached tools for a server.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            List of cached tools or None if not cached/expired
        """
        if not self.is_cache_valid(server_name):
            return None
        
        return self._tool_metadata.get(server_name)
    
    def is_cache_valid(self, server_name: str) -> bool:
        """
        Check if cache is valid for a server.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            True if cache is valid, False otherwise
        """
        if server_name not in self._cache_timestamps:
            return False
        
        cache_time = self._cache_timestamps[server_name]
        expiry_time = cache_time + timedelta(seconds=self.cache_duration)
        
        return datetime.now() < expiry_time
    
    def update_server_status(self, server_status: ServerStatus):
        """
        Update server status information.
        
        Args:
            server_status: Updated server status
        """
        self._server_status[server_status.name] = server_status
        self.logger.debug(f"Updated status for server {server_status.name}: {server_status.status}")
        
        # Persist to disk if enabled
        if self.persist_cache:
            self._save_cache_to_disk()
    
    def get_server_status(self, server_name: str) -> Optional[ServerStatus]:
        """
        Get server status.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            Server status or None if not found
        """
        return self._server_status.get(server_name)
    
    def get_all_cached_tools(self) -> Dict[str, List[ToolInfo]]:
        """
        Get all cached tools.
        
        Returns:
            Dictionary mapping server names to tool lists
        """
        valid_cache = {}
        for server_name, tools in self._tool_metadata.items():
            if self.is_cache_valid(server_name):
                valid_cache[server_name] = tools
        
        return valid_cache
    
    def get_tools_context_for_agent(self) -> str:
        """
        Generate a context description of available tools for the agent.
        
        Returns:
            Formatted string describing available tools
        """
        cached_tools = self.get_all_cached_tools()
        
        if not cached_tools:
            return "No MCP tools are currently available."
        
        context_parts = ["Available MCP Tools:"]
        
        for server_name, tools in cached_tools.items():
            server_status = self.get_server_status(server_name)
            status_indicator = "✅" if server_status and server_status.status == "connected" else "⚠️"
            
            context_parts.append(f"\n{status_indicator} {server_name} Server:")
            
            for tool in tools:
                # Get success rate indicator
                if tool.performance_metrics and tool.performance_metrics.total_calls > 0:
                    success_rate = tool.performance_metrics.success_rate * 100
                    perf_indicator = "🟢" if success_rate >= 90 else "🟡" if success_rate >= 70 else "🔴"
                    perf_info = f" ({perf_indicator} {success_rate:.0f}% success)"
                else:
                    perf_info = ""
                
                context_parts.append(f"  • {tool.name}: {tool.description}{perf_info}")
        
        return "\n".join(context_parts)
    
    def get_tool_by_name(self, tool_name: str) -> Optional[ToolInfo]:
        """
        Find a tool by name across all servers.
        
        Args:
            tool_name: Name of the tool to find
            
        Returns:
            ToolInfo if found, None otherwise
        """
        for tools in self._tool_metadata.values():
            for tool in tools:
                if tool.name == tool_name:
                    return tool
        return None
    
    def update_tool_performance(self, tool_name: str, success: bool, response_time: float):
        """
        Update performance metrics for a tool.
        
        Args:
            tool_name: Name of the tool
            success: Whether the call was successful
            response_time: Response time in seconds
        """
        tool = self.get_tool_by_name(tool_name)
        if tool and tool.performance_metrics:
            tool.performance_metrics.update_call_result(success, response_time)
            self.logger.debug(f"Updated performance for tool {tool_name}: success={success}, time={response_time:.2f}s")
            
            # Update global performance
            self._global_performance.update_call_result(success, response_time)
            
            # Persist to disk if enabled
            if self.persist_cache:
                self._save_cache_to_disk()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get a summary of performance metrics.
        
        Returns:
            Dictionary with performance summary
        """
        cached_tools = self.get_all_cached_tools()
        total_tools = sum(len(tools) for tools in cached_tools.values())
        
        # Calculate server-level stats
        server_stats = {}
        for server_name, tools in cached_tools.items():
            total_calls = sum(tool.performance_metrics.total_calls for tool in tools if tool.performance_metrics)
            avg_success_rate = sum(tool.performance_metrics.success_rate for tool in tools if tool.performance_metrics) / len(tools) if tools else 0
            
            server_stats[server_name] = {
                "tools_count": len(tools),
                "total_calls": total_calls,
                "avg_success_rate": avg_success_rate * 100
            }
        
        return {
            "cache_stats": {
                "servers_cached": len(cached_tools),
                "total_tools": total_tools,
                "cache_duration": self.cache_duration,
                "max_cache_size": self.max_cache_size
            },
            "global_performance": self._global_performance.to_dict(),
            "server_stats": server_stats
        }
    
    def clear_cache(self, server_name: Optional[str] = None):
        """
        Clear cache for a server or all servers.
        
        Args:
            server_name: Server to clear cache for, or None for all servers
        """
        if server_name:
            self._tool_metadata.pop(server_name, None)
            self._cache_timestamps.pop(server_name, None)
            self.logger.info(f"Cleared cache for server {server_name}")
        else:
            self._tool_metadata.clear()
            self._cache_timestamps.clear()
            self._server_status.clear()
            self._global_performance = PerformanceMetrics()
            self.logger.info("Cleared all cache")
        
        # Update disk cache
        if self.persist_cache:
            self._save_cache_to_disk()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_tools = sum(len(tools) for tools in self._tool_metadata.values())
        valid_caches = sum(1 for server in self._tool_metadata.keys() if self.is_cache_valid(server))
        
        return {
            "total_servers_cached": len(self._tool_metadata),
            "valid_caches": valid_caches,
            "total_tools_cached": total_tools,
            "cache_hit_rate": valid_caches / len(self._tool_metadata) if self._tool_metadata else 0,
            "cache_file_exists": self.cache_file.exists() if self.persist_cache else False,
            "cache_file_size": self.cache_file.stat().st_size if self.persist_cache and self.cache_file.exists() else 0
        }
    
    def _save_cache_to_disk(self):
        """Save cache to disk."""
        if not self.persist_cache:
            return
        
        try:
            cache_data = {
                "metadata_version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "tool_metadata": {
                    server: [tool.to_dict() for tool in tools]
                    for server, tools in self._tool_metadata.items()
                },
                "server_status": {
                    server: status.to_dict()
                    for server, status in self._server_status.items()
                },
                "cache_timestamps": {
                    server: timestamp.isoformat()
                    for server, timestamp in self._cache_timestamps.items()
                },
                "global_performance": self._global_performance.to_dict()
            }
            
            # Ensure directory exists
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            # For Windows compatibility, handle file operations more carefully
            # Use a unique temporary file name to avoid conflicts
            temp_fd, temp_path = tempfile.mkstemp(
                suffix='.tmp', 
                prefix='mcp_cache_', 
                dir=self.cache_file.parent
            )
            
            try:
                # Write to temporary file
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, indent=2, ensure_ascii=False)
                
                # Remove existing cache file if it exists (Windows requirement)
                if self.cache_file.exists():
                    self.cache_file.unlink()
                
                # Move temporary file to final location
                shutil.move(temp_path, self.cache_file)
                
                self.logger.debug(f"Cache saved to {self.cache_file}")
                
            except Exception as inner_e:
                # Clean up temporary file if something went wrong
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except:
                    pass
                raise inner_e
            
        except Exception as e:
            self.logger.error(f"Failed to save cache to disk: {e}")
            # Don't raise the exception to avoid breaking the application
    
    def _load_cache_from_disk(self):
        """Load cache from disk."""
        if not self.persist_cache or not self.cache_file.exists():
            return
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Load tool metadata
            if 'tool_metadata' in cache_data:
                for server, tools_data in cache_data['tool_metadata'].items():
                    tools = [ToolInfo.from_dict(tool_data) for tool_data in tools_data]
                    self._tool_metadata[server] = tools
            
            # Load server status
            if 'server_status' in cache_data:
                for server, status_data in cache_data['server_status'].items():
                    self._server_status[server] = ServerStatus.from_dict(status_data)
            
            # Load cache timestamps
            if 'cache_timestamps' in cache_data:
                for server, timestamp_str in cache_data['cache_timestamps'].items():
                    self._cache_timestamps[server] = datetime.fromisoformat(timestamp_str)
            
            # Load global performance
            if 'global_performance' in cache_data:
                self._global_performance = PerformanceMetrics.from_dict(cache_data['global_performance'])
            
            self.logger.info(f"Loaded cache from {self.cache_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to load cache from disk: {e}")
            # Clear corrupted cache
            self._tool_metadata.clear()
            self._server_status.clear()
            self._cache_timestamps.clear()
            self._global_performance = PerformanceMetrics() 