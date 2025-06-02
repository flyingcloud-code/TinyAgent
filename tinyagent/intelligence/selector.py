"""
Tool Selection Module for TinyAgent Intelligence System
Implements intelligent tool selection and capability-based routing.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import re

from agents import Agent, Runner

logger = logging.getLogger(__name__)


class ToolCapability(Enum):
    """Categories of tool capabilities"""
    FILE_OPERATIONS = "file_operations"
    WEB_SEARCH = "web_search"
    WEB_CONTENT = "web_content"
    REASONING = "reasoning"
    WEATHER = "weather"
    TEXT_PROCESSING = "text_processing"
    DATA_ANALYSIS = "data_analysis"
    COMMUNICATION = "communication"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass
class ToolMetadata:
    """Metadata about a tool's capabilities and usage"""
    name: str
    description: str
    capabilities: List[ToolCapability]
    input_types: List[str]
    output_types: List[str]
    complexity_score: float  # 1-10, higher = more complex
    reliability_score: float  # 0-1, higher = more reliable
    average_execution_time: float  # seconds
    usage_count: int = 0
    success_rate: float = 1.0
    keywords: List[str] = None
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = self._extract_keywords()
    
    def _extract_keywords(self) -> List[str]:
        """Extract keywords from tool description"""
        # Simple keyword extraction from description
        words = re.findall(r'\w+', self.description.lower())
        # Filter out common words
        common_words = {'a', 'an', 'the', 'and', 'or', 'but', 'for', 'to', 'of', 'in', 'on', 'at', 'by', 'with'}
        return [word for word in words if word not in common_words and len(word) > 2]


@dataclass
class ToolSelection:
    """Result of tool selection process"""
    selected_tools: List[str]
    confidence_scores: Dict[str, float]
    reasoning: str
    alternative_tools: List[str]
    estimated_execution_time: float
    complexity_assessment: str


class ToolSelector:
    """
    Intelligent Tool Selection Engine
    
    Provides:
    - Capability-based tool mapping
    - Context-aware tool selection
    - Tool performance tracking
    - Alternative tool suggestion
    - Execution planning optimization
    """
    
    def __init__(self, 
                 available_tools: Dict[str, Any],
                 selection_agent: Optional[Agent] = None):
        """
        Initialize ToolSelector
        
        Args:
            available_tools: Dictionary of available tools
            selection_agent: Optional specialized selection agent
        """
        self.available_tools = available_tools
        self.selection_agent = selection_agent or self._create_default_selection_agent()
        
        # Initialize tool metadata
        self.tool_metadata: Dict[str, ToolMetadata] = {}
        self._initialize_tool_metadata()
        
        # Performance tracking
        self.tool_performance: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"ToolSelector initialized with {len(available_tools)} tools")
    
    def _create_default_selection_agent(self) -> Agent:
        """Create default tool selection agent"""
        return Agent(
            name="ToolSelectionAgent",
            instructions=self._get_selection_instructions(),
            model="gpt-4o-mini"  # Fast model for selection
        )
    
    def _get_selection_instructions(self) -> str:
        """Get tool selection instructions for the agent"""
        tools_info = self._format_tools_for_instructions()
        
        return f"""You are an expert tool selection agent. Your job is to analyze tasks and select the most appropriate tools.

Available Tools and Their Capabilities:
{tools_info}

For each task request, analyze and provide:
1. Which tools are most suitable for the task
2. Why each tool was selected (reasoning)
3. Confidence level for each selection (0.0 to 1.0)
4. Alternative tools that could work
5. Estimated execution complexity (simple, moderate, complex)

Rules:
- Select tools that best match the task requirements
- Consider tool reliability and performance
- Prefer simpler tools when appropriate
- Consider tool dependencies and combinations
- Provide clear reasoning for selections

Output your analysis in structured format with tool names, confidence scores, and reasoning."""

    def _format_tools_for_instructions(self) -> str:
        """Format tool information for selection instructions"""
        if not self.tool_metadata:
            return "No tools available"
        
        formatted = []
        for tool_name, metadata in self.tool_metadata.items():
            capabilities = [cap.value for cap in metadata.capabilities]
            formatted.append(
                f"- {tool_name}: {metadata.description}\n"
                f"  Capabilities: {', '.join(capabilities)}\n"
                f"  Complexity: {metadata.complexity_score}/10\n"
                f"  Reliability: {metadata.reliability_score:.2f}\n"
                f"  Keywords: {', '.join(metadata.keywords[:5])}"
            )
        
        return "\n\n".join(formatted)
    
    def _initialize_tool_metadata(self):
        """Initialize metadata for all available tools"""
        # Default tool configurations
        tool_configs = {
            "read_file": {
                "description": "Read content from files",
                "capabilities": [ToolCapability.FILE_OPERATIONS],
                "input_types": ["file_path"],
                "output_types": ["text_content"],
                "complexity_score": 2.0,
                "reliability_score": 0.95,
                "average_execution_time": 1.0
            },
            "write_file": {
                "description": "Write content to files",
                "capabilities": [ToolCapability.FILE_OPERATIONS],
                "input_types": ["file_path", "text_content"],
                "output_types": ["success_status"],
                "complexity_score": 3.0,
                "reliability_score": 0.90,
                "average_execution_time": 2.0
            },
            "list_directory": {
                "description": "List directory contents",
                "capabilities": [ToolCapability.FILE_OPERATIONS, ToolCapability.SYSTEM],
                "input_types": ["directory_path"],
                "output_types": ["file_list"],
                "complexity_score": 2.0,
                "reliability_score": 0.95,
                "average_execution_time": 1.0
            },
            "google_search": {
                "description": "Search Google for information",
                "capabilities": [ToolCapability.WEB_SEARCH],
                "input_types": ["search_query"],
                "output_types": ["search_results"],
                "complexity_score": 4.0,
                "reliability_score": 0.80,
                "average_execution_time": 3.0
            },
            "get_weather": {
                "description": "Get weather information for cities",
                "capabilities": [ToolCapability.WEATHER],
                "input_types": ["city_name", "date"],
                "output_types": ["weather_data"],
                "complexity_score": 3.0,
                "reliability_score": 0.85,
                "average_execution_time": 2.0
            },
            "get_web_content": {
                "description": "Fetch content from web pages",
                "capabilities": [ToolCapability.WEB_CONTENT],
                "input_types": ["url"],
                "output_types": ["webpage_content"],
                "complexity_score": 5.0,
                "reliability_score": 0.75,
                "average_execution_time": 4.0
            },
            "sequentialthinking": {
                "description": "Structured reasoning and analysis",
                "capabilities": [ToolCapability.REASONING, ToolCapability.TEXT_PROCESSING],
                "input_types": ["problem_description"],
                "output_types": ["analysis_result"],
                "complexity_score": 6.0,
                "reliability_score": 0.90,
                "average_execution_time": 5.0
            },
            "get_weekday_from_date": {
                "description": "Get weekday from date",
                "capabilities": [ToolCapability.DATA_ANALYSIS],
                "input_types": ["date_string"],
                "output_types": ["weekday"],
                "complexity_score": 1.0,
                "reliability_score": 1.0,
                "average_execution_time": 0.5
            }
        }
        
        # Create metadata for available tools
        for tool_name in self.available_tools.keys():
            config = tool_configs.get(tool_name, {
                "description": f"Tool: {tool_name}",
                "capabilities": [ToolCapability.UNKNOWN],
                "input_types": ["unknown"],
                "output_types": ["unknown"],
                "complexity_score": 5.0,
                "reliability_score": 0.5,
                "average_execution_time": 3.0
            })
            
            self.tool_metadata[tool_name] = ToolMetadata(
                name=tool_name,
                description=config["description"],
                capabilities=config["capabilities"],
                input_types=config["input_types"],
                output_types=config["output_types"],
                complexity_score=config["complexity_score"],
                reliability_score=config["reliability_score"],
                average_execution_time=config["average_execution_time"]
            )
        
        logger.debug(f"Initialized metadata for {len(self.tool_metadata)} tools")
    
    async def select_best_tool(self, task_step_description: str) -> ToolSelection:
        """
        Select the best tool(s) for a specific task step
        
        Args:
            task_step_description: Description of the task step
            
        Returns:
            ToolSelection with selected tools and reasoning
        """
        try:
            logger.debug(f"Selecting tools for: {task_step_description[:100]}...")
            
            # Get quick rule-based suggestions
            rule_based_tools = self._rule_based_selection(task_step_description)
            
            # Get LLM-based selection for complex cases
            if len(rule_based_tools) > 3 or not rule_based_tools:
                llm_selection = await self._llm_based_selection(task_step_description)
                return llm_selection
            
            # Create selection from rule-based results
            confidence_scores = {}
            for tool in rule_based_tools:
                confidence_scores[tool] = self._calculate_confidence(tool, task_step_description)
            
            # Sort by confidence
            sorted_tools = sorted(confidence_scores.items(), key=lambda x: x[1], reverse=True)
            selected_tools = [tool for tool, _ in sorted_tools[:3]]  # Top 3
            
            # Calculate estimates
            total_time = sum(
                self.tool_metadata.get(tool, ToolMetadata("", "", [], [], [], 3.0, 0.5, 3.0)).average_execution_time
                for tool in selected_tools
            )
            
            avg_complexity = sum(
                self.tool_metadata.get(tool, ToolMetadata("", "", [], [], [], 3.0, 0.5, 3.0)).complexity_score
                for tool in selected_tools
            ) / max(len(selected_tools), 1)
            
            complexity_level = "simple" if avg_complexity < 3 else "moderate" if avg_complexity < 6 else "complex"
            
            selection = ToolSelection(
                selected_tools=selected_tools,
                confidence_scores=confidence_scores,
                reasoning=f"Rule-based selection based on task keywords and tool capabilities",
                alternative_tools=[tool for tool in rule_based_tools if tool not in selected_tools],
                estimated_execution_time=total_time,
                complexity_assessment=complexity_level
            )
            
            logger.debug(f"Selected {len(selected_tools)} tools with {complexity_level} complexity")
            return selection
            
        except Exception as e:
            logger.error(f"Tool selection failed: {e}")
            return self._create_fallback_selection(task_step_description)
    
    def _rule_based_selection(self, task_description: str) -> List[str]:
        """Simple rule-based tool selection"""
        task_lower = task_description.lower()
        selected_tools = []
        
        # File operations
        if any(word in task_lower for word in ['file', 'read', 'write', 'create', 'save', 'document']):
            if 'read' in task_lower or 'content' in task_lower or 'view' in task_lower:
                selected_tools.append('read_file')
            if 'write' in task_lower or 'create' in task_lower or 'save' in task_lower:
                selected_tools.append('write_file')
            if 'list' in task_lower or 'directory' in task_lower or 'folder' in task_lower:
                selected_tools.append('list_directory')
        
        # Web operations
        if any(word in task_lower for word in ['search', 'google', 'find', 'lookup', 'information']):
            selected_tools.append('google_search')
        
        if any(word in task_lower for word in ['url', 'website', 'webpage', 'fetch', 'download']):
            selected_tools.append('get_web_content')
        
        # Weather
        if any(word in task_lower for word in ['weather', 'temperature', 'forecast', 'climate']):
            selected_tools.append('get_weather')
        
        # Analysis and reasoning
        if any(word in task_lower for word in ['analyze', 'think', 'reasoning', 'complex', 'evaluate', 'assess']):
            selected_tools.append('sequentialthinking')
        
        # Date operations
        if any(word in task_lower for word in ['date', 'weekday', 'day']):
            selected_tools.append('get_weekday_from_date')
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(selected_tools))
    
    async def _llm_based_selection(self, task_description: str) -> ToolSelection:
        """Use LLM for intelligent tool selection"""
        try:
            selection_prompt = self._create_selection_prompt(task_description)
            
            result = await Runner.run(
                self.selection_agent,
                selection_prompt,
                max_turns=2
            )
            
            # Parse LLM response (simplified)
            response_text = result.final_output.lower()
            
            # Extract tool names mentioned in response
            selected_tools = []
            confidence_scores = {}
            
            for tool_name in self.available_tools.keys():
                if tool_name in response_text:
                    selected_tools.append(tool_name)
                    # Try to extract confidence if mentioned
                    confidence_scores[tool_name] = 0.8  # Default confidence
            
            # Fallback to rule-based if LLM didn't select tools
            if not selected_tools:
                selected_tools = self._rule_based_selection(task_description)
                confidence_scores = {tool: 0.6 for tool in selected_tools}
            
            return ToolSelection(
                selected_tools=selected_tools[:3],  # Limit to top 3
                confidence_scores=confidence_scores,
                reasoning=f"LLM-based selection: {result.final_output[:200]}...",
                alternative_tools=[],
                estimated_execution_time=sum(
                    self.tool_metadata.get(tool, ToolMetadata("", "", [], [], [], 3.0, 0.5, 3.0)).average_execution_time
                    for tool in selected_tools[:3]
                ),
                complexity_assessment="moderate"
            )
            
        except Exception as e:
            logger.error(f"LLM-based selection failed: {e}")
            return self._create_fallback_selection(task_description)
    
    def _create_selection_prompt(self, task_description: str) -> str:
        """Create prompt for LLM-based tool selection"""
        available_tools_list = list(self.available_tools.keys())
        
        return f"""Analyze this task and select the most appropriate tools:

Task: "{task_description}"

Available Tools: {', '.join(available_tools_list)}

Tool Details:
{self._format_tools_for_instructions()}

Select the best tools for this task and explain your reasoning. Consider:
1. Which tools match the task requirements
2. Tool reliability and performance
3. Task complexity and tool combinations
4. Execution efficiency

Provide your selection with reasoning."""

    def _calculate_confidence(self, tool_name: str, task_description: str) -> float:
        """Calculate confidence score for tool selection"""
        if tool_name not in self.tool_metadata:
            return 0.3
        
        metadata = self.tool_metadata[tool_name]
        
        # Base confidence from tool reliability
        confidence = metadata.reliability_score
        
        # Boost confidence if keywords match
        task_words = set(task_description.lower().split())
        keyword_matches = len(task_words.intersection(set(metadata.keywords)))
        keyword_boost = min(keyword_matches * 0.1, 0.3)
        
        # Adjust for tool complexity (simpler tools get slight boost for simple tasks)
        complexity_factor = 1.0
        if len(task_description.split()) < 10:  # Simple task
            if metadata.complexity_score < 4:
                complexity_factor = 1.1
        
        # Factor in historical success rate
        performance = self.tool_performance.get(tool_name, {})
        success_rate_factor = performance.get('success_rate', 1.0)
        
        final_confidence = min(
            (confidence + keyword_boost) * complexity_factor * success_rate_factor,
            1.0
        )
        
        return final_confidence
    
    def _create_fallback_selection(self, task_description: str) -> ToolSelection:
        """Create fallback selection when other methods fail"""
        # Use the most reliable general-purpose tools
        fallback_tools = []
        
        if 'file' in task_description.lower():
            fallback_tools.append('read_file')
        elif 'search' in task_description.lower():
            fallback_tools.append('google_search')
        else:
            fallback_tools.append('sequentialthinking')  # General reasoning tool
        
        return ToolSelection(
            selected_tools=fallback_tools,
            confidence_scores={tool: 0.5 for tool in fallback_tools},
            reasoning="Fallback selection due to analysis failure",
            alternative_tools=[],
            estimated_execution_time=5.0,
            complexity_assessment="unknown"
        )
    
    def can_handle_task(self, tool_name: str, task_description: str) -> bool:
        """
        Check if a specific tool can handle a task
        
        Args:
            tool_name: Name of the tool to check
            task_description: Description of the task
            
        Returns:
            True if tool can handle the task
        """
        if tool_name not in self.tool_metadata:
            return False
        
        metadata = self.tool_metadata[tool_name]
        task_lower = task_description.lower()
        
        # Check keyword matches
        keyword_matches = any(keyword in task_lower for keyword in metadata.keywords)
        
        # Check capability matches
        capability_matches = False
        for capability in metadata.capabilities:
            if capability == ToolCapability.FILE_OPERATIONS and any(word in task_lower for word in ['file', 'read', 'write']):
                capability_matches = True
            elif capability == ToolCapability.WEB_SEARCH and any(word in task_lower for word in ['search', 'google', 'find']):
                capability_matches = True
            elif capability == ToolCapability.WEATHER and 'weather' in task_lower:
                capability_matches = True
            elif capability == ToolCapability.REASONING and any(word in task_lower for word in ['analyze', 'think', 'reasoning']):
                capability_matches = True
        
        return keyword_matches or capability_matches
    
    def get_tools_by_capability(self, capability: ToolCapability) -> List[str]:
        """Get all tools that have a specific capability"""
        matching_tools = []
        
        for tool_name, metadata in self.tool_metadata.items():
            if capability in metadata.capabilities:
                matching_tools.append(tool_name)
        
        return matching_tools
    
    def update_tool_performance(self, 
                              tool_name: str, 
                              success: bool,
                              execution_time: float,
                              error_message: Optional[str] = None):
        """
        Update tool performance metrics
        
        Args:
            tool_name: Name of the tool
            success: Whether the execution was successful
            execution_time: Time taken for execution
            error_message: Error message if failed
        """
        if tool_name not in self.tool_performance:
            self.tool_performance[tool_name] = {
                'total_calls': 0,
                'successful_calls': 0,
                'total_time': 0.0,
                'success_rate': 1.0,
                'average_time': 0.0,
                'errors': []
            }
        
        perf = self.tool_performance[tool_name]
        perf['total_calls'] += 1
        perf['total_time'] += execution_time
        
        if success:
            perf['successful_calls'] += 1
        else:
            if error_message:
                perf['errors'].append(error_message)
                # Keep only last 10 errors
                perf['errors'] = perf['errors'][-10:]
        
        # Update derived metrics
        perf['success_rate'] = perf['successful_calls'] / perf['total_calls']
        perf['average_time'] = perf['total_time'] / perf['total_calls']
        
        # Update tool metadata
        if tool_name in self.tool_metadata:
            metadata = self.tool_metadata[tool_name]
            metadata.usage_count = perf['total_calls']
            metadata.success_rate = perf['success_rate']
            metadata.average_execution_time = perf['average_time']
        
        logger.debug(f"Updated performance for {tool_name}: {perf['success_rate']:.2f} success rate")
    
    def get_tool_statistics(self) -> Dict[str, Any]:
        """Get comprehensive tool usage statistics"""
        stats = {
            'total_tools': len(self.tool_metadata),
            'tools_with_performance_data': len(self.tool_performance),
            'tool_details': {},
            'capability_distribution': {},
            'performance_summary': {
                'most_used': None,
                'most_reliable': None,
                'fastest': None,
                'total_calls': 0
            }
        }
        
        # Analyze capability distribution
        for metadata in self.tool_metadata.values():
            for capability in metadata.capabilities:
                cap_name = capability.value
                stats['capability_distribution'][cap_name] = stats['capability_distribution'].get(cap_name, 0) + 1
        
        # Analyze tool performance
        total_calls = 0
        most_used_tool = None
        most_used_count = 0
        most_reliable_tool = None
        best_success_rate = 0
        fastest_tool = None
        best_time = float('inf')
        
        for tool_name, metadata in self.tool_metadata.items():
            tool_detail = {
                'capabilities': [cap.value for cap in metadata.capabilities],
                'complexity_score': metadata.complexity_score,
                'reliability_score': metadata.reliability_score,
                'usage_count': metadata.usage_count,
                'success_rate': metadata.success_rate,
                'average_execution_time': metadata.average_execution_time
            }
            
            stats['tool_details'][tool_name] = tool_detail
            
            # Track totals and bests
            total_calls += metadata.usage_count
            
            if metadata.usage_count > most_used_count:
                most_used_count = metadata.usage_count
                most_used_tool = tool_name
            
            if metadata.success_rate > best_success_rate:
                best_success_rate = metadata.success_rate
                most_reliable_tool = tool_name
            
            if metadata.average_execution_time < best_time and metadata.usage_count > 0:
                best_time = metadata.average_execution_time
                fastest_tool = tool_name
        
        stats['performance_summary'].update({
            'most_used': most_used_tool,
            'most_reliable': most_reliable_tool,
            'fastest': fastest_tool,
            'total_calls': total_calls
        })
        
        return stats

    def recommend_alternatives(self, 
                             primary_tool: str, 
                             task_description: str) -> List[Tuple[str, float]]:
        """
        Recommend alternative tools for a task
        
        Args:
            primary_tool: The primary tool being considered
            task_description: Description of the task
            
        Returns:
            List of (tool_name, confidence_score) tuples
        """
        if primary_tool not in self.tool_metadata:
            return []
        
        primary_metadata = self.tool_metadata[primary_tool]
        alternatives = []
        
        # Find tools with similar capabilities
        for tool_name, metadata in self.tool_metadata.items():
            if tool_name == primary_tool:
                continue
            
            # Calculate similarity based on capabilities
            common_capabilities = set(primary_metadata.capabilities) & set(metadata.capabilities)
            if common_capabilities:
                similarity_score = len(common_capabilities) / len(set(primary_metadata.capabilities) | set(metadata.capabilities))
                
                # Adjust score based on task relevance
                task_relevance = self._calculate_confidence(tool_name, task_description)
                final_score = (similarity_score + task_relevance) / 2
                
                alternatives.append((tool_name, final_score))
        
        # Sort by score and return top alternatives
        alternatives.sort(key=lambda x: x[1], reverse=True)
        return alternatives[:5] 