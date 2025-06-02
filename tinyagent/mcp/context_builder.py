"""
Agent Context Builder for MCP Tool Integration
Builds intelligent context for agents based on available MCP tools.
"""

import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime

from .cache import MCPToolCache, ToolInfo, ServerStatus
from ..intelligence.selector import ToolCapability

logger = logging.getLogger(__name__)


@dataclass
class AgentToolContext:
    """Context information about tools for the agent"""
    available_tools: List[ToolInfo]
    server_status: Dict[str, ServerStatus]
    capabilities_summary: Dict[str, List[str]]
    performance_summary: Dict[str, Any]
    recommended_tools: Dict[str, List[str]]
    context_text: str
    last_updated: datetime


class AgentContextBuilder:
    """
    Intelligent context builder for integrating MCP tools with agents.
    
    Provides:
    - Tool capability analysis and mapping
    - Dynamic tool recommendations based on task context  
    - Performance-aware tool suggestions
    - Compact context generation for agent prompts
    - Real-time tool availability updates
    """
    
    def __init__(self, tool_cache: MCPToolCache):
        """
        Initialize AgentContextBuilder
        
        Args:
            tool_cache: MCP tool cache instance
        """
        self.tool_cache = tool_cache
        self.logger = logging.getLogger(__name__)
        
        # Capability mapping for MCP tools
        self.capability_mapping = {
            # File system tools
            "read_file": [ToolCapability.FILE_OPERATIONS],
            "write_file": [ToolCapability.FILE_OPERATIONS],
            "list_directory": [ToolCapability.FILE_OPERATIONS, ToolCapability.SYSTEM],
            "directory_tree": [ToolCapability.FILE_OPERATIONS, ToolCapability.SYSTEM],
            "create_directory": [ToolCapability.FILE_OPERATIONS],
            "move_file": [ToolCapability.FILE_OPERATIONS],
            "search_files": [ToolCapability.FILE_OPERATIONS, ToolCapability.TEXT_PROCESSING],
            "get_file_info": [ToolCapability.FILE_OPERATIONS, ToolCapability.SYSTEM],
            
            # Web and search tools
            "google_search": [ToolCapability.WEB_SEARCH],
            "get_web_content": [ToolCapability.WEB_CONTENT, ToolCapability.TEXT_PROCESSING],
            "fetch_url": [ToolCapability.WEB_CONTENT],
            
            # Weather tools
            "get_weather_for_city_at_date": [ToolCapability.WEATHER],
            "get_weekday_from_date": [ToolCapability.DATA_ANALYSIS],
            
            # Thinking tools
            "sequentialthinking": [ToolCapability.REASONING, ToolCapability.TEXT_PROCESSING],
        }
        
        # Task type to capability mapping
        self.task_capability_mapping = {
            "file": [ToolCapability.FILE_OPERATIONS],
            "read": [ToolCapability.FILE_OPERATIONS, ToolCapability.TEXT_PROCESSING],
            "write": [ToolCapability.FILE_OPERATIONS],
            "search": [ToolCapability.WEB_SEARCH, ToolCapability.FILE_OPERATIONS],
            "web": [ToolCapability.WEB_SEARCH, ToolCapability.WEB_CONTENT],
            "weather": [ToolCapability.WEATHER],
            "analyze": [ToolCapability.DATA_ANALYSIS, ToolCapability.REASONING],
            "think": [ToolCapability.REASONING],
            "download": [ToolCapability.WEB_CONTENT],
            "list": [ToolCapability.FILE_OPERATIONS, ToolCapability.SYSTEM],
            "create": [ToolCapability.FILE_OPERATIONS],
        }
        
        self.logger.info("AgentContextBuilder initialized")
    
    def build_tool_context(self, task_hint: Optional[str] = None) -> AgentToolContext:
        """
        Build comprehensive tool context for the agent.
        
        Args:
            task_hint: Optional hint about the task type for tool recommendation
            
        Returns:
            AgentToolContext with all relevant tool information
        """
        try:
            # Get current tool information
            cached_tools = self.tool_cache.get_all_cached_tools()
            all_tools = []
            for tools in cached_tools.values():
                all_tools.extend(tools)
            
            # Get server status
            server_status = {}
            for server_name in cached_tools.keys():
                status = self.tool_cache.get_server_status(server_name)
                if status:
                    server_status[server_name] = status
            
            # Build capabilities summary
            capabilities_summary = self._build_capabilities_summary(all_tools)
            
            # Get performance summary
            performance_summary = self.tool_cache.get_performance_summary()
            
            # Generate tool recommendations
            recommended_tools = self._generate_tool_recommendations(all_tools, task_hint)
            
            # Generate context text
            context_text = self._generate_context_text(
                all_tools, server_status, capabilities_summary, recommended_tools, task_hint
            )
            
            return AgentToolContext(
                available_tools=all_tools,
                server_status=server_status,
                capabilities_summary=capabilities_summary,
                performance_summary=performance_summary,
                recommended_tools=recommended_tools,
                context_text=context_text,
                last_updated=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error building tool context: {e}")
            return self._create_fallback_context()
    
    def _build_capabilities_summary(self, tools: List[ToolInfo]) -> Dict[str, List[str]]:
        """Build a summary of available capabilities"""
        capabilities = {}
        
        for tool in tools:
            tool_capabilities = self.capability_mapping.get(tool.name, [ToolCapability.UNKNOWN])
            
            for capability in tool_capabilities:
                cap_name = capability.value
                if cap_name not in capabilities:
                    capabilities[cap_name] = []
                capabilities[cap_name].append(tool.name)
        
        return capabilities
    
    def _generate_tool_recommendations(self, 
                                     tools: List[ToolInfo], 
                                     task_hint: Optional[str] = None) -> Dict[str, List[str]]:
        """Generate tool recommendations based on task context"""
        recommendations = {
            "high_performance": [],
            "reliable": [],
            "task_relevant": [],
            "frequently_used": []
        }
        
        for tool in tools:
            # High performance tools (good response time)
            if (tool.performance_metrics and 
                tool.performance_metrics.avg_response_time < 2.0 and
                tool.performance_metrics.total_calls > 0):
                recommendations["high_performance"].append(tool.name)
            
            # Reliable tools (high success rate)
            if (tool.performance_metrics and 
                tool.performance_metrics.success_rate > 0.9 and
                tool.performance_metrics.total_calls > 0):
                recommendations["reliable"].append(tool.name)
            
            # Frequently used tools
            if (tool.performance_metrics and 
                tool.performance_metrics.total_calls > 5):
                recommendations["frequently_used"].append(tool.name)
        
        # Task-relevant tools based on hint
        if task_hint:
            relevant_capabilities = self._extract_relevant_capabilities(task_hint)
            for tool in tools:
                tool_capabilities = self.capability_mapping.get(tool.name, [])
                if any(cap in relevant_capabilities for cap in tool_capabilities):
                    recommendations["task_relevant"].append(tool.name)
        
        return recommendations
    
    def _extract_relevant_capabilities(self, task_hint: str) -> List[ToolCapability]:
        """Extract relevant capabilities from task hint"""
        task_hint_lower = task_hint.lower()
        relevant_capabilities = []
        
        for keyword, capabilities in self.task_capability_mapping.items():
            if keyword in task_hint_lower:
                relevant_capabilities.extend(capabilities)
        
        return list(set(relevant_capabilities))  # Remove duplicates
    
    def _generate_context_text(self, 
                             tools: List[ToolInfo],
                             server_status: Dict[str, ServerStatus],
                             capabilities: Dict[str, List[str]],
                             recommendations: Dict[str, List[str]],
                             task_hint: Optional[str] = None) -> str:
        """Generate compact context text for agent prompts"""
        
        if not tools:
            return "No MCP tools are currently available."
        
        context_parts = ["## Available Tools"]
        
        # Group tools by server for organized presentation
        tools_by_server = {}
        for tool in tools:
            if tool.server_name not in tools_by_server:
                tools_by_server[tool.server_name] = []
            tools_by_server[tool.server_name].append(tool)
        
        # Add server-grouped tools
        for server_name, server_tools in tools_by_server.items():
            status = server_status.get(server_name)
            status_indicator = "🟢" if status and status.status == "connected" else "🔴"
            
            context_parts.append(f"\n### {status_indicator} {server_name}")
            
            for tool in server_tools:
                # Performance indicator
                perf_indicator = ""
                if tool.performance_metrics and tool.performance_metrics.total_calls > 0:
                    success_rate = tool.performance_metrics.success_rate * 100
                    if success_rate >= 95:
                        perf_indicator = "⭐"
                    elif success_rate >= 80:
                        perf_indicator = "✅"
                    else:
                        perf_indicator = "⚠️"
                
                # Capability tags
                tool_caps = self.capability_mapping.get(tool.name, [])
                cap_tags = [cap.value.replace('_', '-') for cap in tool_caps[:2]]  # Max 2 tags
                cap_str = f" [{', '.join(cap_tags)}]" if cap_tags else ""
                
                context_parts.append(f"- **{tool.name}**{perf_indicator}: {tool.description[:80]}...{cap_str}")
        
        # Add capability summary
        if capabilities:
            context_parts.append("\n### Capabilities")
            for cap_name, tool_names in capabilities.items():
                if len(tool_names) > 0:
                    tools_str = ", ".join(tool_names[:3])  # Show max 3 tools
                    if len(tool_names) > 3:
                        tools_str += f" (+{len(tool_names)-3} more)"
                    context_parts.append(f"- **{cap_name.replace('_', ' ').title()}**: {tools_str}")
        
        # Add recommendations if task hint provided
        if task_hint and any(recommendations.values()):
            context_parts.append(f"\n### Recommended for '{task_hint}'")
            
            if recommendations["task_relevant"]:
                context_parts.append(f"- **Most Relevant**: {', '.join(recommendations['task_relevant'][:3])}")
            
            if recommendations["reliable"]:
                context_parts.append(f"- **Most Reliable**: {', '.join(recommendations['reliable'][:3])}")
            
            if recommendations["high_performance"]:
                context_parts.append(f"- **Fastest**: {', '.join(recommendations['high_performance'][:3])}")
        
        context_parts.append(f"\n*Last updated: {datetime.now().strftime('%H:%M:%S')}*")
        
        return "\n".join(context_parts)
    
    def get_compact_tool_summary(self) -> str:
        """Get a very compact summary of available tools for brief contexts"""
        cached_tools = self.tool_cache.get_all_cached_tools()
        
        if not cached_tools:
            return "No tools available"
        
        tool_count = sum(len(tools) for tools in cached_tools.values())
        server_count = len(cached_tools)
        
        # Get tool categories
        all_tools = []
        for tools in cached_tools.values():
            all_tools.extend(tools)
        
        capabilities = set()
        for tool in all_tools:
            tool_caps = self.capability_mapping.get(tool.name, [])
            capabilities.update(cap.value for cap in tool_caps)
        
        cap_summary = ", ".join(sorted(list(capabilities))[:4])  # Show top 4 capabilities
        
        return f"{tool_count} tools across {server_count} servers. Capabilities: {cap_summary}"
    
    def get_tools_for_capability(self, capability: ToolCapability) -> List[ToolInfo]:
        """Get all tools that support a specific capability"""
        cached_tools = self.tool_cache.get_all_cached_tools()
        matching_tools = []
        
        for tools in cached_tools.values():
            for tool in tools:
                tool_capabilities = self.capability_mapping.get(tool.name, [])
                if capability in tool_capabilities:
                    matching_tools.append(tool)
        
        # Sort by performance (success rate, then response time)
        matching_tools.sort(key=lambda t: (
            -(t.performance_metrics.success_rate if t.performance_metrics else 0),
            t.performance_metrics.avg_response_time if t.performance_metrics else 999
        ))
        
        return matching_tools
    
    def _create_fallback_context(self) -> AgentToolContext:
        """Create fallback context when tool discovery fails"""
        return AgentToolContext(
            available_tools=[],
            server_status={},
            capabilities_summary={},
            performance_summary={},
            recommended_tools={},
            context_text="Tools are currently unavailable. Operating in basic mode.",
            last_updated=datetime.now()
        )
    
    def update_tool_performance_context(self, tool_name: str, success: bool, response_time: float) -> None:
        """Update tool performance and refresh recommendations"""
        self.tool_cache.update_tool_performance(tool_name, success, response_time)
        self.logger.debug(f"Updated performance context for {tool_name}: success={success}")

    def build_tools_context(self, task_hint: Optional[str] = None) -> str:
        """
        Build tools context for agent (returns context text only for compatibility)
        
        Args:
            task_hint: Optional hint about the task type for tool recommendation
            
        Returns:
            String containing tools context information
        """
        try:
            tool_context = self.build_tool_context(task_hint)
            return tool_context.context_text
        except Exception as e:
            self.logger.error(f"Error building tools context: {e}")
            return "Tools are currently unavailable. Operating in basic mode." 