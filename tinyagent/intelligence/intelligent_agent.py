"""
Intelligent Agent Module for TinyAgent
Integrates all intelligence components to provide true autonomous agent behavior.
"""

import logging
import time
import uuid
import re
import asyncio
from typing import Optional, Dict, Any, List, Callable
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
    
    def __init__(self, llm_agent=None, config: Optional[IntelligentAgentConfig] = None, tinyagent_config=None):
        """
        Initialize IntelligentAgent with all sub-components
        
        Args:
            llm_agent: Base LLM agent for general reasoning
            config: Configuration for IntelligentAgent
            tinyagent_config: TinyAgent configuration for LLM settings
        """
        self.config = config or IntelligentAgentConfig()
        self.llm_agent = llm_agent
        self.tinyagent_config = tinyagent_config
        
        # Initialize MCP context builder if available
        try:
            from ..mcp.context_builder import AgentContextBuilder
            from ..mcp.cache import MCPToolCache
            if llm_agent:
                # Create tool cache
                self.tool_cache = MCPToolCache(
                    cache_duration=300,  # 5 minutes
                    max_cache_size=100,
                    persist_cache=True
                )
                self.mcp_context_builder = AgentContextBuilder(self.tool_cache)
                logger.info("MCP context builder initialized")
            else:
                logger.warning("MCP context components not available")
        except Exception as e:
            logger.warning(f"Failed to initialize MCP context builder: {e}")
            self.mcp_context_builder = None
            self.tool_cache = None
        
        # 🔧 CRITICAL FIX: Create specialized agents for each component instead of sharing base_agent
        
        # Create specialized planning agent with planning instructions
        planning_agent = self._create_specialized_agent(
            name="TaskPlanner",
            instructions=self._get_planning_instructions(),
            llm_agent=llm_agent
        )
        
        # Create specialized reasoning agent with reasoning instructions  
        reasoning_agent = self._create_specialized_agent(
            name="ReasoningEngine", 
            instructions=self._get_reasoning_instructions(),
            llm_agent=llm_agent
        )
        
        # Initialize intelligence components with specialized agents
        self.task_planner = TaskPlanner(
            available_tools={},  # Will be populated when MCP tools are registered
            planning_agent=planning_agent,  # 🔧 FIX: Use specialized planning agent
            max_steps=self.config.max_reasoning_iterations
        )
        
        self.conversation_memory = ConversationMemory(
            max_turns=self.config.memory_max_context_turns
        )
        
        self.tool_selector = ToolSelector(
            available_tools={},  # Will be populated when MCP tools are registered
            config=tinyagent_config  # Pass TinyAgent config for LLM settings
        )
        
        self.reasoning_engine = ReasoningEngine(
            llm_agent=reasoning_agent,  # 🔧 FIX: Use specialized reasoning agent
            max_iterations=self.config.max_reasoning_iterations,
            confidence_threshold=self.config.confidence_threshold
        )
        
        self.action_executor = ActionExecutor(
            max_concurrent_actions=self.config.max_concurrent_actions,
            default_timeout=self.config.action_timeout,
            llm_agent=llm_agent  # 🔧 NEW: Add LLM support for built-in actions
        )
        
        observation_level = ObservationLevel.DETAILED if self.config.use_detailed_observation else ObservationLevel.BASIC
        self.result_observer = ResultObserver(
            observation_level=observation_level,
            llm_agent=llm_agent  # 🔧 NEW: Add LLM support for enhanced insights
        )
        
        # Track execution state
        self.current_task = None
        self.execution_history = []
        
        logger.info(f"IntelligentAgent initialized with specialized agents and config: {self.config}")
        
        # Store MCP tools when registered
        self._mcp_tools = []
        
        # Enhanced tool context state
        self._last_tool_context = None
        self._tool_context_cache_valid = False
        
        # 🔧 NEW: Tool execution capabilities
        self._mcp_tool_executor = None  # Will be set when MCP tools are registered
        self._available_mcp_tools = {}  # Maps tool_name -> server_name
    
    def _create_specialized_agent(self, name: str, instructions: str, llm_agent) -> Any:
        """
        Create a specialized agent with specific instructions
        
        Args:
            name: Name of the specialized agent
            instructions: Specialized instructions for this agent
            llm_agent: Base LLM agent to derive model settings from
            
        Returns:
            Specialized Agent instance
        """
        try:
            from agents import Agent
            
            # Extract model and settings from base agent
            model_instance = llm_agent.model if hasattr(llm_agent, 'model') else None
            
            specialized_agent = Agent(
                name=f"TinyAgent-{name}",
                instructions=instructions,
                model=model_instance
            )
            
            logger.info(f"Created specialized agent: {name} with dedicated instructions")
            return specialized_agent
            
        except Exception as e:
            logger.warning(f"Failed to create specialized agent {name}: {e}, using base agent")
            return llm_agent
    
    def _get_planning_instructions(self) -> str:
        """Get specialized instructions for task planning"""
        return """You are an expert task planning agent. Your job is to analyze user requests and create detailed execution plans.

Your responsibilities:
1. Break down user requests into logical, executable steps
2. Identify required tools for each step  
3. Determine dependencies between steps
4. Estimate realistic execution times
5. Define clear success criteria
6. Consider error recovery scenarios

Output Format:
Always provide your analysis in structured JSON format following the TaskPlan schema:
- complexity: (simple/moderate/complex/very_complex)
- steps: Array of step objects with id, description, tools, dependencies, duration, priority
- success_criteria: Array of measurable success criteria

Guidelines:
- Maximum 10 steps per plan
- Each step should be atomic and executable
- Tool dependencies must be accurate
- Time estimates should be realistic
- Include validation steps where appropriate

Think systematically and be thorough in your planning."""

    def _get_reasoning_instructions(self) -> str:
        """Get specialized instructions for reasoning engine"""
        return """You are an expert reasoning agent implementing the ReAct (Reasoning + Acting) methodology.

Your core process:
1. THINK: Analyze the situation, understand the goal, and plan your approach
2. ACT: Select and execute the most appropriate tool or action
3. OBSERVE: Analyze the results of your action
4. REFLECT: Learn from the outcome and decide next steps

Reasoning Guidelines:
- Always start by clearly understanding the user's goal
- Think step-by-step and be explicit about your reasoning
- Choose tools based on their specific capabilities and the current need
- Observe results carefully and adjust your approach if needed
- Reflect on whether you're making progress toward the goal
- Stop when the goal is achieved or cannot be achieved

Output Format:
Structure your reasoning clearly:
- Thought: Your analysis and reasoning
- Action: The specific action/tool you're choosing  
- Observation: What the results tell you
- Reflection: What you learned and what to do next

Be methodical, focused, and goal-oriented in your reasoning process."""
    
    def _detect_tool_query(self, message: str) -> bool:
        """
        Detect if user is asking about available tools
        
        Args:
            message: User input message
            
        Returns:
            True if user is asking about tools
        """
        tool_query_patterns = [
            r"list.*tools?",
            r"what tools?",
            r"show.*tools?",
            r"available.*tools?",
            r"mcp.*tools?",
            r"capabilities?",
            r"what.*can.*do",
            r"tools.*have",
            r"functions.*have"
        ]
        
        message_lower = message.lower()
        return any(re.search(pattern, message_lower) for pattern in tool_query_patterns)
    
    async def _handle_tool_query(self) -> str:
        """
        Handle tool query request by returning actual MCP tools
        
        Returns:
            Formatted response with actual tool list
        """
        logger.info("Handling tool query request")
        
        # 🔧 ENHANCED: Get all available tools from multiple sources
        tools = await self._get_available_tools()
        
        if not tools:
            # Try to get tools from cache if direct query failed
            if hasattr(self, 'mcp_context_builder') and self.mcp_context_builder:
                try:
                    tool_context = self.mcp_context_builder.build_tool_context()
                    if tool_context and tool_context.available_tools:
                        tools = []
                        for tool_info in tool_context.available_tools:
                            tools.append({
                                'name': tool_info.name,
                                'description': tool_info.description,
                                'server': tool_info.server_name,
                                'category': tool_info.category
                            })
                except Exception as e:
                    logger.warning(f"Error getting tools from context builder: {e}")
        
        if not tools:
            return ("🔧 **当前可用的MCP工具状态**\n\n"
                   "❌ **没有发现可用的工具**\n\n"
                   "**可能的原因：**\n"
                   "• MCP服务器连接失败\n"
                   "• 工具缓存为空\n" 
                   "• 服务器配置问题\n\n"
                   "**建议操作：**\n"
                   "1. 检查MCP服务器状态: `python -m tinyagent list-servers --show-tools`\n"
                   "2. 重启MCP服务器连接\n"
                   "3. 检查配置文件设置")
        
        # 🔧 ENHANCED: Group tools by server and format better
        tools_by_server = {}
        for tool in tools:
            server_name = tool.get('server', '未知服务器')
            if server_name not in tools_by_server:
                tools_by_server[server_name] = []
            tools_by_server[server_name].append(tool)
        
        response_parts = ["🔧 **当前可用的MCP工具** \n"]
        
        total_tools = len(tools)
        total_servers = len(tools_by_server)
        
        response_parts.append(f"📊 **总计**: {total_tools} 个工具，来自 {total_servers} 个服务器\n")
        
        # Add server status indicators
        for server_name, server_tools in tools_by_server.items():
            tool_count = len(server_tools)
            
            # Determine server status emoji
            if tool_count > 0:
                status_emoji = "🟢"  # Green for active
                status_text = "活跃"
            else:
                status_emoji = "🔴"  # Red for inactive  
                status_text = "非活跃"
            
            response_parts.append(f"\n{status_emoji} **{server_name}** ({status_text} - {tool_count} 工具)")
            response_parts.append("-" * 50)
            
            # List tools for this server
            for i, tool in enumerate(server_tools, 1):
                tool_name = tool.get('name', '未知工具')
                description = tool.get('description', '无描述')
                category = tool.get('category', '通用')
                
                # Truncate long descriptions
                if len(description) > 100:
                    description = description[:100] + "..."
                
                response_parts.append(f"{i}. **{tool_name}** ({category})")
                response_parts.append(f"   📝 {description}")
                
                # Add usage example based on tool type
                if 'read' in tool_name.lower() or 'file' in tool_name.lower():
                    response_parts.append(f"   💡 用法示例: 读取文件内容")
                elif 'write' in tool_name.lower() or 'create' in tool_name.lower():
                    response_parts.append(f"   💡 用法示例: 创建或写入文件")
                elif 'fetch' in tool_name.lower() or 'get' in tool_name.lower():
                    response_parts.append(f"   💡 用法示例: 获取网络内容")
                elif 'search' in tool_name.lower():
                    response_parts.append(f"   💡 用法示例: 搜索信息")
                else:
                    response_parts.append(f"   💡 用法示例: {category}相关操作")
                
                response_parts.append("")  # Empty line between tools
        
        response_parts.append("\n🎯 **如何使用这些工具：**")
        response_parts.append("• 直接描述您想要完成的任务")  
        response_parts.append("• 我会自动选择合适的工具并执行")
        response_parts.append("• 例如: '读取README.md文件' 或 '搜索最新新闻'")
        
        return "\n".join(response_parts)

    def _build_enhanced_tool_context(self, task_hint: Optional[str] = None) -> Optional[str]:
        """
        Build enhanced tool context using MCP context builder
        
        Args:
            task_hint: Optional hint about the task to help focus tool selection
            
        Returns:
            Enhanced tool context string if MCP context builder is available
        """
        if not self.mcp_context_builder:
            return None
        
        try:
            # Try to build tool context
            tool_context = self.mcp_context_builder.build_tool_context(
                task_hint=task_hint
            )
            
            if tool_context and tool_context.context_text:
                self._last_tool_context = tool_context
                self._tool_context_cache_valid = True
                logger.debug(f"Built enhanced tool context: {len(tool_context.context_text)} chars")
                return tool_context.context_text
            else:
                logger.warning("Tool context builder returned empty context")
                return None
                
        except Exception as e:
            logger.warning(f"Error building enhanced tool context: {e}")
            return None

    def get_tool_context_summary(self) -> Dict[str, Any]:
        """Get summary of current tool context"""
        if not self._last_tool_context:
            return {"available": False, "reason": "No tool context built"}
        
        return {
            "available": True,
            "tools_count": len(self._last_tool_context.available_tools),
            "servers": list(self._last_tool_context.server_status.keys()),
            "capabilities": list(self._last_tool_context.capabilities_summary.keys()),
            "context_size": len(self._last_tool_context.context_text) if self._last_tool_context.context_text else 0,
            "cache_valid": self._tool_context_cache_valid
        }

    def _create_tool_executor(self) -> Callable:
        """
        Create a tool executor function that can execute MCP tools
        
        Returns:
            Async function that can execute tools: async def execute_tool(tool_name, params) -> result
        """
        async def execute_tool(tool_name: str, params: Dict[str, Any]) -> Any:
            """
            Execute an MCP tool with given parameters
            
            Args:
                tool_name: Name of the tool to execute
                params: Parameters for the tool execution
                
            Returns:
                Tool execution result
            """
            try:
                logger.info(f"Executing MCP tool: {tool_name} with params: {params}")
                
                # Check if we have a registered tool executor function
                if self._mcp_tool_executor:
                    result = await self._mcp_tool_executor(tool_name, params)
                    logger.info(f"Tool {tool_name} executed successfully via MCP executor")
                    return result
                
                # Try to execute via action executor if tool is registered there
                if tool_name in self.action_executor.tool_registry:
                    tool_func = self.action_executor.tool_registry[tool_name]
                    if callable(tool_func):
                        # Execute the tool function
                        if asyncio.iscoroutinefunction(tool_func):
                            result = await tool_func(**params)
                        else:
                            result = tool_func(**params)
                        logger.info(f"Tool {tool_name} executed successfully via action executor")
                        return result
                
                # If no direct execution method available, return a descriptive result
                logger.warning(f"No execution method available for tool {tool_name}")
                return f"Tool {tool_name} identified but execution method not available. Parameters: {params}"
                
            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}")
                raise
        
        return execute_tool
    
    def set_mcp_tool_executor(self, executor_func: Callable):
        """
        Set the MCP tool executor function
        
        Args:
            executor_func: Function that can execute MCP tools
                          Signature: async def execute_tool(tool_name, params) -> result
        """
        self._mcp_tool_executor = executor_func
        logger.info("MCP tool executor function registered with IntelligentAgent")
        
        # Also register with ReasoningEngine
        tool_executor = self._create_tool_executor()
        self.reasoning_engine.set_tool_executor(tool_executor)
        logger.info("Tool executor registered with ReasoningEngine")

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
            # 🔧 NEW: Check if user is asking about tools
            if self._detect_tool_query(message):
                logger.info("Detected tool query, handling directly")
                tool_response = await self._handle_tool_query()
                return {
                    "success": True,
                    "answer": tool_response,
                    "task_plan": {"task_id": task_id, "complexity": "simple", "steps": 1},
                    "reasoning": {"iterations": 0, "confidence": 1.0, "steps": 0},
                    "tools_used": [],
                    "execution_time": time.time() - start_time,
                    "tool_context": self.get_tool_context_summary()
                }
            
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
            logger.info(f"Task plan details: {task_plan}")
            
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
                "available_tools": available_tools,  # Add available tools to context
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
        
        # Add registered MCP tools first (these are the real tools)
        if hasattr(self, '_mcp_tools') and self._mcp_tools:
            for tool in self._mcp_tools:
                available_tools.append({
                    "name": tool.get('name', 'unknown'),
                    "description": tool.get('description', 'MCP tool'),
                    "type": "mcp",
                    "server": tool.get('server', 'unknown'),
                    "category": tool.get('category', 'unknown')
                })
        
        # Add tools from tool cache if available
        if self.tool_cache and self.mcp_context_builder:
            try:
                # Get all cached tools
                cached_tools = {}
                for server_name in ['filesystem', 'sequential-thinking', 'fetch']:  # Known servers
                    server_tools = self.tool_cache.get_cached_tools(server_name)
                    if server_tools:
                        cached_tools[server_name] = server_tools
                
                # Add cached tools to available tools (avoid duplicates)
                existing_tool_names = {tool['name'] for tool in available_tools}
                for server_name, tool_list in cached_tools.items():
                    for tool_info in tool_list:
                        if tool_info.name not in existing_tool_names:
                            available_tools.append({
                                "name": tool_info.name,
                                "description": tool_info.description,
                                "type": "mcp",
                                "server": tool_info.server_name,
                                "category": tool_info.category
                            })
                            existing_tool_names.add(tool_info.name)
            except Exception as e:
                logger.warning(f"Error getting tools from cache: {e}")
        
        # Add registered tools from action executor if they're not already included
        existing_tool_names = {tool['name'] for tool in available_tools}
        for tool_name in self.action_executor.tool_registry.keys():
            if tool_name not in existing_tool_names:
                available_tools.append({
                    "name": tool_name,
                    "description": f"Registered tool: {tool_name}",
                    "type": "registered"
                })
        
        # Only add built-in tools if no real tools are available
        if not available_tools:
            builtin_tools = [
                {"name": "search", "description": "Search for information", "type": "builtin"},
                {"name": "analyze", "description": "Analyze data or content", "type": "builtin"},
                {"name": "create", "description": "Create content or files", "type": "builtin"},
                {"name": "synthesize", "description": "Combine multiple inputs", "type": "builtin"},
                {"name": "validate", "description": "Validate answers or results", "type": "builtin"}
            ]
            available_tools.extend(builtin_tools)
        
        return available_tools
    
    def register_mcp_tools(self, mcp_tools: List[Dict[str, Any]]):
        """Register MCP tools with the intelligent agent and update tool cache"""
        logger.info(f"Registering {len(mcp_tools)} MCP tools")
        
        # Check if we already have tools registered to prevent duplicates
        if hasattr(self, '_mcp_tools_registered') and self._mcp_tools_registered:
            logger.debug(f"Tools already registered, checking for new tools only")
            # Check for new tools not already registered
            existing_tool_names = {tool.get('name') for tool in self._mcp_tools}
            new_tools = [tool for tool in mcp_tools if tool.get('name') not in existing_tool_names]
            if not new_tools:
                logger.debug("No new tools to register, skipping duplicate registration")
                return
            mcp_tools = new_tools  # Only register new tools
        
        # Initialize registered tools list if not exists
        if not hasattr(self, '_mcp_tools'):
            self._mcp_tools = []
        
        # Group tools by server to avoid repeated cache operations
        tools_by_server = {}
        registered_count = 0
        
        for tool in mcp_tools:
            tool_name = tool.get('name', 'unknown')
            description = tool.get('description', 'MCP tool')
            server_name = tool.get('server', 'unknown')
            
            # Check if this specific tool is already registered
            existing_tool_names = {t.get('name') for t in self._mcp_tools}
            if tool_name in existing_tool_names:
                logger.debug(f"Tool {tool_name} already registered, skipping")
                continue
            
            # Register with tool selector only if not already registered
            if not self.tool_selector.has_tool(tool_name):
                self.tool_selector.add_tool_capability(
                    tool_name=tool_name,
                    capabilities=[description],
                    server_name=server_name,
                    reliability_score=0.8  # Default reliability for MCP tools
                )
            
            # Register execution function if available and not already registered
            if 'function' in tool and tool_name not in self.action_executor.tool_registry:
                self.action_executor.register_tool(tool_name, tool['function'])
            
            # Group tools by server for batch caching
            if server_name not in tools_by_server:
                tools_by_server[server_name] = []
            tools_by_server[server_name].append(tool)
            
            logger.info(f"Registered MCP tool: {tool_name} from server: {server_name}")
            
            # Store MCP tools when registered
            self._mcp_tools.append(tool)
            registered_count += 1
        
        # 🔧 CRITICAL FIX: Register MCP tools with ReasoningEngine
        # This was the missing piece that caused the intelligent mode to use simulated actions
        # instead of real MCP tools
        if registered_count > 0:
            logger.info(f"Registering {len(self._mcp_tools)} MCP tools with ReasoningEngine")
            self.reasoning_engine.register_mcp_tools(self._mcp_tools)
            
            # Also update task planner with available tools
            available_tools = {tool.get('name'): tool for tool in self._mcp_tools}
            self.task_planner.available_tools = available_tools
            logger.info(f"Updated TaskPlanner with {len(available_tools)} available tools")
        
        # Mark as registered to prevent future duplicate registrations
        self._mcp_tools_registered = True
        
        # Only update cache if we actually registered new tools
        if registered_count == 0:
            logger.debug("No new tools were registered, skipping cache update")
            return
        
        # Update tool cache once per server (batch operation)
        if self.tool_cache and self.mcp_context_builder:
            try:
                from ..mcp.cache import ToolInfo, PerformanceMetrics
                from datetime import datetime
                
                for server_name, server_tools in tools_by_server.items():
                    # Check if tools are already cached to avoid redundant operations
                    existing_cached_tools = self.tool_cache.get_cached_tools(server_name)
                    if existing_cached_tools and len(existing_cached_tools) >= len(server_tools):
                        logger.debug(f"Tools for {server_name} already cached, skipping cache update")
                        continue
                    
                    # Create ToolInfo objects for this server
                    tool_infos = []
                    for tool in server_tools:
                        tool_info = ToolInfo(
                            name=tool.get('name', 'unknown'),
                            description=tool.get('description', 'MCP tool'),
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
                        tool_infos.append(tool_info)
                    
                    # Cache all tools for this server at once
                    self.tool_cache.cache_server_tools(server_name, tool_infos)
                    logger.debug(f"Updated tool cache for server: {server_name} with {len(tool_infos)} tools")
                
                # Invalidate context cache to force rebuild
                self._tool_context_cache_valid = False
                
            except Exception as e:
                logger.warning(f"Failed to update tool cache: {e}")
            
        logger.info(f"Completed registering {registered_count} new MCP tools from {len(tools_by_server)} servers")
        logger.info(f"ReasoningEngine now has {len(self.reasoning_engine.available_mcp_tools)} MCP tools available")
    
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

    async def run_stream(self, message: str, context: Optional[Dict[str, Any]] = None):
        """
        Execute intelligent agent workflow with streaming output for real-time feedback
        
        Args:
            message: User input message
            context: Optional additional context
            
        Yields:
            Real-time status updates and progress from each sub-component
        """
        start_time = time.time()
        task_id = str(uuid.uuid4())
        
        yield f"🧠 **IntelligentAgent 启动中** (任务ID: {task_id[:8]})\n"
        yield f"📝 用户请求: {message[:100]}{'...' if len(message) > 100 else ''}\n"
        yield f"⏰ 开始时间: {time.strftime('%H:%M:%S')}\n\n"
        
        try:
            # 🔧 NEW: Check if user is asking about tools
            if self._detect_tool_query(message):
                yield "🔧 **检测到工具查询请求**\n"
                yield "📊 正在收集可用工具信息...\n"
                tool_response = await self._handle_tool_query()
                yield f"✅ **工具查询完成**\n\n{tool_response}\n"
                return
            
            # 0. Build enhanced tool context for this task
            yield "🔧 **构建增强工具上下文**\n"
            enhanced_context = self._build_enhanced_tool_context(task_hint=message)
            if enhanced_context:
                yield "✅ 增强工具上下文构建完成\n"
            else:
                yield "⚠️ 工具上下文构建跳过\n"
            yield "\n"
            
            # 1. Add message to conversation memory
            yield "💭 **添加到对话记忆**\n"
            conversation_turn = self.conversation_memory.add_exchange(
                user_input=message,
                agent_response="",  # Will be updated later
                task_id=task_id
            )
            yield f"✅ 已添加到对话记忆: 轮次 {conversation_turn}\n\n"
            
            # 2. Task Planning - Stream planning process
            planning_context = context or {}
            if enhanced_context:
                planning_context["available_tools_context"] = enhanced_context
                planning_context["tool_summary"] = self.get_tool_context_summary()
            
            # Stream TaskPlanner process
            task_plan = None
            async for planning_update in self.task_planner.create_plan_stream(
                task_description=message,
                context=planning_context
            ):
                yield planning_update
            
            # Get the planning result
            task_plan = await self.task_planner.get_last_plan()
            
            # Update conversation memory with task plan
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
            
            # 3. Tool Selection - Stream tool selection process
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
            
            # Stream ToolSelector process
            tool_selection = None
            async for selection_update in self.tool_selector.select_tools_for_task_stream(
                task_description=message,
                available_tools=available_tools,
                task_context=task_context
            ):
                yield selection_update
            
            # Get the tool selection result
            tool_selection = await self.tool_selector.get_last_selection()
            
            # 4. Reasoning and Acting - Stream ReAct loop with real-time updates
            yield "🧠 **推理与行动阶段 (ReAct循环)**\n"
            yield "🔄 开始智能推理循环...\n\n"
            
            reasoning_context = {
                "task_plan": task_plan,
                "selected_tools": tool_selection.selected_tools,
                "available_tools": available_tools,
                "conversation_context": self.conversation_memory.get_relevant_context(message),
                "original_message": message,
                "enhanced_tool_context": enhanced_context,
                "tool_context_summary": self.get_tool_context_summary()
            }
            
            # Stream the reasoning process
            reasoning_result = None
            async for reasoning_update in self.reasoning_engine.reason_and_act_stream(
                goal=message,
                context=reasoning_context
            ):
                # Forward reasoning updates to user
                yield reasoning_update
            
            # Get final reasoning result
            reasoning_result = await self.reasoning_engine.get_last_result()
            
            yield f"\n🎯 **推理循环完成**\n"
            yield f"   ✅ 成功: {reasoning_result.success}\n"
            yield f"   🔄 迭代次数: {reasoning_result.iterations}\n"
            yield f"   🎲 置信度: {reasoning_result.confidence:.2f}\n"
            yield f"   ⏱️ 总耗时: {reasoning_result.total_duration:.2f}秒\n\n"
            
            # 5. Result Observation and Learning
            if self.config.enable_learning:
                yield "📊 **结果观察与学习阶段**\n"
                
                # Prepare observation data for streaming
                observation_data = []
                for i, step in enumerate(reasoning_result.steps):
                    if step.action and step.observation:
                        observation_data.append({
                            'action_id': f"reasoning_step_{i}",
                            'result': step.observation,
                            'expected_outcome': step.thought,
                            'execution_time': step.duration,
                            'action_name': step.action
                        })
                
                if observation_data:
                    # Stream observation process for multiple results
                    async for observation_update in self.result_observer.observe_multiple_results_stream(observation_data):
                        yield observation_update
                else:
                    yield "ℹ️  无推理步骤需要观察分析\n"
                
                yield "\n"
            
            # 6. Update conversation memory with results
            final_response = reasoning_result.final_answer or "任务完成"
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
            
            # 7. Final summary
            execution_time = time.time() - start_time
            yield "🎉 **任务执行总结**\n"
            yield f"   ✅ 执行状态: {'成功' if reasoning_result.success else '失败'}\n"
            yield f"   ⏱️ 总执行时间: {execution_time:.2f}秒\n"
            yield f"   🔧 使用工具: {len(tool_selection.selected_tools)}个\n"
            yield f"   💭 对话轮次: {conversation_turn}\n"
            yield f"   📊 工具上下文: {'已使用' if enhanced_context else '未使用'}\n\n"
            
            yield f"💬 **最终回答**:\n{reasoning_result.final_answer}\n"
            
        except Exception as e:
            yield f"\n❌ **执行失败**: {str(e)}\n"
            yield f"⏱️ 失败时间: {time.time() - start_time:.2f}秒\n"
            
            # Add error to conversation memory
            error_message = f"执行失败: {str(e)}"
            self.conversation_memory.add_exchange(
                user_input=message,
                agent_response=error_message,
                execution_time=time.time() - start_time
            ) 