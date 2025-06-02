"""
Intelligent Agent Module for TinyAgent
Integrates all intelligence components to provide true autonomous agent behavior.
"""

import logging
import time
import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from .planner import TaskPlanner
from .memory import ConversationMemory  
from .selector import ToolSelector
from .reasoner import ReasoningEngine
from .actor import ActionExecutor
from .observer import ResultObserver, ObservationLevel

# Import MCP context builder
try:
    from ..mcp.context_builder import AgentContextBuilder, AgentToolContext
    from ..mcp.cache import MCPToolCache
    MCP_CONTEXT_AVAILABLE = True
except ImportError:
    AgentContextBuilder = None
    AgentToolContext = None
    MCPToolCache = None
    MCP_CONTEXT_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class IntelligentAgentConfig:
    """Configuration for IntelligentAgent"""
    max_reasoning_iterations: int = 10
    confidence_threshold: float = 0.8
    max_concurrent_actions: int = 5
    action_timeout: float = 60.0
    memory_max_context_turns: int = 20
    use_detailed_observation: bool = True
    enable_learning: bool = True


class IntelligentAgent:
    """
    Intelligent Agent that integrates all intelligence components
    
    This agent provides true autonomous behavior by combining:
    - TaskPlanner: Task analysis and decomposition
    - ConversationMemory: Context and history management
    - ToolSelector: Intelligent tool selection
    - ReasoningEngine: ReAct loop for thinking and acting
    - ActionExecutor: Tool execution and orchestration
    - ResultObserver: Learning from outcomes
    - AgentContextBuilder: MCP tool context integration (NEW)
    """
    
    def __init__(self, llm_agent=None, config: Optional[IntelligentAgentConfig] = None):
        """
        Initialize IntelligentAgent with all intelligence components
        
        Args:
            llm_agent: Base LLM agent for reasoning
            config: Configuration for intelligent behavior
        """
        self.config = config or IntelligentAgentConfig()
        self.llm_agent = llm_agent
        
        # Initialize MCP context builder if available
        self.mcp_context_builder = None
        self.tool_cache = None
        if MCP_CONTEXT_AVAILABLE:
            try:
                self.tool_cache = MCPToolCache()
                self.mcp_context_builder = AgentContextBuilder(self.tool_cache)
                logger.info("MCP context builder initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize MCP context builder: {e}")
                self.mcp_context_builder = None
                self.tool_cache = None
        else:
            logger.warning("MCP context components not available")
        
        # Initialize intelligence components
        self.task_planner = TaskPlanner(
            available_tools={},  # Will be populated when MCP tools are registered
            planning_agent=llm_agent,  # Use llm_agent as planning_agent
            max_steps=self.config.max_reasoning_iterations
        )
        
        self.conversation_memory = ConversationMemory(
            max_turns=self.config.memory_max_context_turns
        )
        
        self.tool_selector = ToolSelector(
            available_tools={}  # Will be populated when MCP tools are registered
        )
        
        self.reasoning_engine = ReasoningEngine(
            llm_agent=llm_agent,
            max_iterations=self.config.max_reasoning_iterations,
            confidence_threshold=self.config.confidence_threshold
        )
        
        self.action_executor = ActionExecutor(
            max_concurrent_actions=self.config.max_concurrent_actions,
            default_timeout=self.config.action_timeout
        )
        
        observation_level = ObservationLevel.DETAILED if self.config.use_detailed_observation else ObservationLevel.BASIC
        self.result_observer = ResultObserver(
            observation_level=observation_level
        )
        
        # Track execution state
        self.current_task = None
        self.execution_history = []
        
        logger.info(f"IntelligentAgent initialized with config: {self.config}")
        
        # Store MCP tools when registered
        self._mcp_tools = []
        
        # Enhanced tool context state
        self._last_tool_context = None
        self._tool_context_cache_valid = False
    
    def _build_enhanced_tool_context(self, task_hint: Optional[str] = None) -> Optional[str]:
        """
        Build enhanced tool context using MCP context builder
        
        Args:
            task_hint: Optional hint about the task type for tool recommendation
            
        Returns:
            Formatted tool context string or None if not available
        """
        if not self.mcp_context_builder:
            logger.debug("MCP context builder not available")
            return None
        
        try:
            # Build comprehensive tool context
            tool_context = self.mcp_context_builder.build_tool_context(task_hint=task_hint)
            
            if not tool_context or not tool_context.available_tools:
                logger.debug("No tools available in context")
                return None
            
            # Cache the context for reuse
            self._last_tool_context = tool_context
            self._tool_context_cache_valid = True
            
            # Generate context text for the agent
            context_text = tool_context.context_text
            
            # Add performance recommendations if available
            if tool_context.recommended_tools:
                context_text += "\n\n## Tool Recommendations:\n"
                for category, tools in tool_context.recommended_tools.items():
                    if tools:
                        context_text += f"- **{category.replace('_', ' ').title()}**: {', '.join(tools)}\n"
            
            logger.info(f"Enhanced tool context built: {len(tool_context.available_tools)} tools, "
                       f"{len(tool_context.server_status)} servers")
            
            return context_text
            
        except Exception as e:
            logger.error(f"Error building enhanced tool context: {e}")
            return None
    
    def get_tool_context_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current tool context for debugging and monitoring
        
        Returns:
            Dictionary with tool context summary
        """
        if not self._last_tool_context:
            return {"status": "no_context", "tools": 0, "servers": 0}
        
        context = self._last_tool_context
        return {
            "status": "active",
            "tools": len(context.available_tools),
            "servers": len(context.server_status),
            "capabilities": list(context.capabilities_summary.keys()),
            "recommendations": {k: len(v) for k, v in context.recommended_tools.items()},
            "last_updated": context.last_updated.isoformat(),
            "cache_valid": self._tool_context_cache_valid
        }

    async def run(self, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute intelligent agent workflow with ReAct loop and enhanced tool context
        
        Args:
            message: User input message
            context: Optional additional context
            
        Returns:
            Comprehensive execution result
        """
        start_time = time.time()
        task_id = str(uuid.uuid4())  # Generate unique task ID
        logger.info(f"IntelligentAgent starting: task_id={task_id}, message='{message[:100]}...'")
        
        try:
            # 0. Build enhanced tool context for this task
            enhanced_context = self._build_enhanced_tool_context(task_hint=message)
            if enhanced_context:
                logger.info("Enhanced tool context built and available for planning")
            
            # 1. Add message to conversation memory
            conversation_turn = self.conversation_memory.add_exchange(
                user_input=message,
                agent_response="",  # Will be updated later
                task_id=task_id
            )
            logger.info(f"Added to conversation memory: turn {conversation_turn}")
            
            # 2. Task Planning - Analyze and decompose the task with tool context
            planning_context = context or {}
            if enhanced_context:
                planning_context["available_tools_context"] = enhanced_context
                planning_context["tool_summary"] = self.get_tool_context_summary()
            
            task_plan = await self.task_planner.create_plan(
                task_description=message,
                context=planning_context
            )
            logger.info(f"Task planned: {task_plan.complexity.value}, {len(task_plan.steps)} steps")
            
            # Update conversation memory with task plan
            # First create the task context if it doesn't exist
            task_context = self.conversation_memory.create_task_context(
                task_id=task_plan.task_id,
                initial_request=message,
                metadata={
                    "complexity": task_plan.complexity.value,
                    "plan_steps": [step.description for step in task_plan.steps],
                    "estimated_duration": task_plan.total_estimated_duration,
                    "tool_context_available": enhanced_context is not None
                }
            )
            
            # 3. Tool Selection - Identify needed tools based on plan with enhanced context
            available_tools = await self._get_available_tools()
            
            # Enhance available tools with MCP context information
            if self._last_tool_context:
                for mcp_tool in self._last_tool_context.available_tools:
                    available_tools.append({
                        "name": mcp_tool.name,
                        "description": mcp_tool.description,
                        "type": "mcp",
                        "server": mcp_tool.server_name,
                        "category": mcp_tool.category,
                        "performance": mcp_tool.performance_metrics.__dict__ if mcp_tool.performance_metrics else {}
                    })
            
            tool_selection = await self.tool_selector.select_tools_for_task(
                task_description=message,
                available_tools=available_tools,
                task_context=task_context
            )
            logger.info(f"Tools selected: {tool_selection.selected_tools}")
            
            # Register selected tools with action executor
            for tool_name in tool_selection.selected_tools:
                # For now, we don't have actual tool functions to register
                # TODO: Implement proper tool function registration
                logger.debug(f"Would register tool: {tool_name}")
            
            # 4. Reasoning and Acting - Execute ReAct loop with tool context
            reasoning_context = {
                "task_plan": task_plan,
                "selected_tools": tool_selection.selected_tools,
                "conversation_context": self.conversation_memory.get_relevant_context(message),
                "original_message": message,
                "enhanced_tool_context": enhanced_context,
                "tool_context_summary": self.get_tool_context_summary()
            }
            
            reasoning_result = await self.reasoning_engine.reason_and_act(
                goal=message,
                context=reasoning_context
            )
            logger.info(f"Reasoning completed: success={reasoning_result.success}, "
                       f"steps={len(reasoning_result.steps)}, confidence={reasoning_result.confidence:.2f}")
            
            # 5. Result Observation and Learning
            if self.config.enable_learning:
                for i, step in enumerate(reasoning_result.steps):
                    if step.action and step.observation:
                        observation = await self.result_observer.observe_result(
                            action_id=f"reasoning_step_{i}",
                            result=step.observation,
                            expected_outcome=step.thought,
                            execution_time=step.duration,
                            action_name=step.action
                        )
                        logger.info(f"Observation {i}: success={observation.success_assessment}, "
                                   f"confidence={observation.confidence:.2f}")
            
            # 6. Update conversation memory with results
            # Update conversation with final response using add_exchange
            final_response = reasoning_result.final_answer or "Task completed"
            self.conversation_memory.add_exchange(
                user_input=message,
                agent_response=final_response,
                tools_used=tool_selection.selected_tools,
                execution_time=time.time() - start_time,
                task_id=task_plan.task_id
            )
            
            # Update task completion status
            self.conversation_memory.update_task_context(
                task_id=task_plan.task_id,
                status="completed" if reasoning_result.success else "failed",
                metadata={
                    "success": reasoning_result.success,
                    "result": reasoning_result.final_answer,
                    "execution_time": reasoning_result.total_duration,
                    "tool_context_used": enhanced_context is not None
                }
            )
            
            # 7. Generate comprehensive result with enhanced tool context information
            execution_time = time.time() - start_time
            result = {
                "success": reasoning_result.success,
                "answer": reasoning_result.final_answer,
                "task_plan": {
                    "task_id": task_plan.task_id,
                    "complexity": task_plan.complexity.value,
                    "steps": len(task_plan.steps),
                    "estimated_time": task_plan.total_estimated_duration
                },
                "reasoning": {
                    "iterations": reasoning_result.iterations,
                    "confidence": reasoning_result.confidence,
                    "steps": len(reasoning_result.steps)
                },
                "tools_used": tool_selection.selected_tools,
                "execution_time": execution_time,
                "conversation_turn": conversation_turn,
                "learning_enabled": self.config.enable_learning,
                "tool_context": self.get_tool_context_summary()
            }
            
            logger.info(f"IntelligentAgent completed: success={result['success']}, "
                       f"time={execution_time:.2f}s, tools_context_used={enhanced_context is not None}")
            
            return result
            
        except Exception as e:
            logger.error(f"IntelligentAgent execution failed: {e}")
            
            # Add error to conversation memory
            error_message = f"Execution failed: {str(e)}"
            self.conversation_memory.add_exchange(
                user_input=message,
                agent_response=error_message,
                execution_time=time.time() - start_time
            )
            
            return {
                "success": False,
                "answer": error_message,
                "error": str(e),
                "execution_time": time.time() - start_time,
                "tool_context": self.get_tool_context_summary()
            }
    
    async def _get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools from various sources"""
        available_tools = []
        
        # Add built-in action executor tools
        builtin_tools = [
            {"name": "search", "description": "Search for information", "type": "builtin"},
            {"name": "analyze", "description": "Analyze data or content", "type": "builtin"},
            {"name": "create", "description": "Create content or files", "type": "builtin"},
            {"name": "synthesize", "description": "Combine multiple inputs", "type": "builtin"},
            {"name": "validate", "description": "Validate answers or results", "type": "builtin"}
        ]
        available_tools.extend(builtin_tools)
        
        # Add registered tools from action executor
        for tool_name in self.action_executor.tool_registry.keys():
            available_tools.append({
                "name": tool_name,
                "description": f"Registered tool: {tool_name}",
                "type": "registered"
            })
        
        return available_tools
    
    def register_mcp_tools(self, mcp_tools: List[Dict[str, Any]]):
        """Register MCP tools with the intelligent agent and update tool cache"""
        logger.info(f"Registering {len(mcp_tools)} MCP tools")
        
        for tool in mcp_tools:
            tool_name = tool.get('name', 'unknown')
            description = tool.get('description', 'MCP tool')
            server_name = tool.get('server', 'unknown')
            
            # Register with tool selector
            self.tool_selector.add_tool_capability(
                tool_name=tool_name,
                capabilities=[description],
                server_name=server_name,
                reliability_score=0.8  # Default reliability for MCP tools
            )
            
            # Register execution function if available
            if 'function' in tool:
                self.action_executor.register_tool(tool_name, tool['function'])
            
            # Update tool cache if available
            if self.tool_cache and self.mcp_context_builder:
                try:
                    # Cache this tool information
                    from ..mcp.cache import ToolInfo, PerformanceMetrics
                    from datetime import datetime
                    
                    tool_info = ToolInfo(
                        name=tool_name,
                        description=description,
                        server_name=server_name,
                        schema=tool.get('schema', {}),
                        category=tool.get('category', 'unknown'),
                        last_updated=datetime.now(),
                        performance_metrics=PerformanceMetrics(
                            success_rate=1.0,
                            avg_response_time=0.0,
                            total_calls=0,
                            last_call_time=None
                        )
                    )
                    
                    # Add to cache
                    cached_tools = self.tool_cache.get_cached_tools(server_name) or []
                    cached_tools.append(tool_info)
                    self.tool_cache.cache_server_tools(server_name, cached_tools)
                    
                    # Invalidate context cache to force rebuild
                    self._tool_context_cache_valid = False
                    
                    logger.debug(f"Updated tool cache for: {tool_name}")
                except Exception as e:
                    logger.warning(f"Failed to update tool cache for {tool_name}: {e}")
            
            logger.info(f"Registered MCP tool: {tool_name} from server: {server_name}")
            
            # Store MCP tools when registered
            self._mcp_tools.append(tool)
            
        logger.info(f"Completed registering {len(mcp_tools)} MCP tools")
    
    def get_conversation_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get conversation history from memory"""
        return self.conversation_memory.get_conversation_history(limit=limit)
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """Get learning insights from result observer"""
        if self.config.enable_learning:
            return self.result_observer.get_learning_summary()
        return {"learning_disabled": True}
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics from all components"""
        return {
            "action_executor": self.action_executor.get_performance_metrics(),
            "task_planner": {
                "plans_created": getattr(self.task_planner, 'plans_created', 0)
            },
            "tool_selector": self.tool_selector.get_selection_statistics(),
            "memory": {
                "total_turns": len(self.conversation_memory.conversation_history),
                "active_tasks": len(self.conversation_memory.task_contexts)
            },
            "observer": self.result_observer.get_learning_summary() if self.config.enable_learning else {}
        }
    
    def clear_conversation_memory(self):
        """Clear conversation memory"""
        self.conversation_memory = ConversationMemory(
            max_turns=self.config.memory_max_context_turns
        )
        logger.info("Conversation memory cleared")
    
    def set_llm_agent(self, llm_agent):
        """Update the LLM agent for all components"""
        self.llm_agent = llm_agent
        self.task_planner.planning_agent = llm_agent
        self.reasoning_engine.llm_agent = llm_agent
        logger.info("LLM agent updated for all intelligence components") 