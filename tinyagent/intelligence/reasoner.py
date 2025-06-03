"""
Reasoning Engine Module for TinyAgent Intelligence System
Implements the core ReAct (Reasoning + Acting) loop for autonomous agent behavior.
"""

import logging
import time
import json
import asyncio
from typing import List, Dict, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# Import MCP components for actual tool execution
try:
    from ..mcp.manager import MCPServerManager
    from ..mcp.cache import MCPToolCache
    MCP_AVAILABLE = True
except ImportError:
    MCPServerManager = None
    MCPToolCache = None
    MCP_AVAILABLE = False

class ReasoningState(Enum):
    """States in the reasoning process"""
    THINKING = "thinking"
    PLANNING = "planning"
    ACTING = "acting"
    OBSERVING = "observing"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReasoningStep:
    """Represents a single step in the reasoning process"""
    step_id: int
    state: ReasoningState
    thought: str
    action: Optional[str] = None
    action_params: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    reflection: Optional[str] = None
    confidence: float = 0.0
    duration: float = 0.0
    timestamp: float = field(default_factory=time.time)
    # 🔧 NEW: Add actual execution results
    tool_result: Optional[Any] = None
    execution_success: bool = True
    execution_error: Optional[str] = None


@dataclass
class ReasoningResult:
    """Complete result of reasoning process"""
    goal: str
    success: bool
    steps: List[ReasoningStep]
    final_answer: Optional[str] = None
    total_duration: float = 0.0
    iterations: int = 0
    confidence: float = 0.0


class ReasoningEngine:
    """
    Core Reasoning Engine implementing ReAct Loop
    
    This engine provides the "thinking" capability for TinyAgent, implementing
    a structured reasoning process that combines thinking, planning, acting,
    observing, and reflecting in a continuous loop until the goal is achieved.
    
    🔧 ENHANCED: Now includes actual MCP tool execution capabilities
    """
    
    def __init__(self, llm_agent=None, max_iterations: int = 10, confidence_threshold: float = 0.8):
        """
        Initialize ReasoningEngine
        
        Args:
            llm_agent: Agent instance for LLM reasoning
            max_iterations: Maximum number of ReAct iterations
            confidence_threshold: Minimum confidence for completion
        """
        self.llm_agent = llm_agent
        self.max_iterations = max_iterations
        self.confidence_threshold = confidence_threshold
        self.current_step = 0
        
        # 🔧 NEW: Tool execution capabilities
        self.mcp_manager = None
        self.tool_cache = None
        self.available_mcp_tools = {}  # Maps tool_name -> server_name
        self.tool_executor = None  # Will be set by TinyAgent
        
        logger.info(f"ReasoningEngine initialized with max_iterations={max_iterations}")
    
    def set_tool_executor(self, tool_executor_func: Callable):
        """
        Set the tool executor function for actual MCP tool execution
        
        Args:
            tool_executor_func: Function that can execute MCP tools
                                Signature: async def execute_tool(tool_name, params) -> result
        """
        self.tool_executor = tool_executor_func
        logger.info("Tool executor function registered with ReasoningEngine")
    
    def register_mcp_tools(self, mcp_tools: List[Dict[str, Any]]):
        """
        Register available MCP tools with the reasoning engine
        
        Args:
            mcp_tools: List of MCP tool definitions
        """
        self.available_mcp_tools = {}
        for tool in mcp_tools:
            tool_name = tool.get('name')
            server_name = tool.get('server', 'unknown')
            if tool_name:
                self.available_mcp_tools[tool_name] = server_name
        
        logger.info(f"Registered {len(self.available_mcp_tools)} MCP tools for reasoning")

    async def reason_and_act(self, goal: str, context: Optional[Dict[str, Any]] = None) -> ReasoningResult:
        """
        Main ReAct loop implementation with actual tool execution
        
        Args:
            goal: The goal to reason about and achieve
            context: Additional context for reasoning
            
        Returns:
            ReasoningResult with complete reasoning trace
        """
        logger.info(f"Starting ReAct loop for goal: {goal[:100]}...")
        start_time = time.time()
        
        steps = []
        self.current_step = 0
        
        # Initialize reasoning context
        reasoning_context = {
            "goal": goal,
            "context": context or {},
            "steps_taken": [],
            "available_actions": self._get_available_actions(),
            "current_state": "starting",
            "tool_results": []  # 🔧 NEW: Track tool execution results
        }
        
        try:
            # Main ReAct loop
            while self.current_step < self.max_iterations:
                self.current_step += 1
                step_start = time.time()
                
                # 1. THINKING - Analyze current situation and plan next action
                thought_step = await self._thinking_phase(reasoning_context, self.current_step)
                if thought_step:
                    steps.append(thought_step)
                
                # Check if reasoning determined completion
                if thought_step and thought_step.state == ReasoningState.COMPLETED:
                    break
                
                # 2. ACTING - Execute the planned action (NOW WITH REAL TOOL EXECUTION!)
                action_step = await self._acting_phase(reasoning_context, self.current_step)
                if action_step:
                    steps.append(action_step)
                    # Update context with action taken
                    reasoning_context["steps_taken"].append({
                        "action": action_step.action,
                        "params": action_step.action_params,
                        "tool_result": action_step.tool_result,
                        "success": action_step.execution_success
                    })
                    
                    # 🔧 NEW: Add tool results to context
                    if action_step.tool_result:
                        reasoning_context["tool_results"].append({
                            "step": self.current_step,
                            "tool": action_step.action,
                            "result": action_step.tool_result,
                            "success": action_step.execution_success
                        })
                
                # 3. OBSERVING - Analyze the results of the action (NOW WITH REAL RESULTS!)
                observation_step = await self._observing_phase(reasoning_context, self.current_step, action_step)
                if observation_step:
                    steps.append(observation_step)
                    # Update context with observation
                    reasoning_context["last_observation"] = observation_step.observation
                
                # 4. REFLECTING - Learn from the outcome and plan next step
                reflection_step = await self._reflecting_phase(reasoning_context, self.current_step, observation_step)
                if reflection_step:
                    steps.append(reflection_step)
                    
                    # Check if reflection indicates completion
                    if reflection_step.confidence >= self.confidence_threshold:
                        # Create completion step
                        completion_step = ReasoningStep(
                            step_id=self.current_step,
                            state=ReasoningState.COMPLETED,
                            thought="Goal achieved with sufficient confidence",
                            confidence=reflection_step.confidence,
                            duration=time.time() - step_start
                        )
                        steps.append(completion_step)
                        break
            
            # Determine final result
            total_duration = time.time() - start_time
            final_step = steps[-1] if steps else None
            success = final_step and final_step.state == ReasoningState.COMPLETED
            
            # Extract final answer from the reasoning process
            final_answer = await self._extract_final_answer(steps, reasoning_context)
            
            result = ReasoningResult(
                goal=goal,
                success=success,
                steps=steps,
                final_answer=final_answer,
                total_duration=total_duration,
                iterations=self.current_step,
                confidence=final_step.confidence if final_step else 0.0
            )
            
            logger.info(f"ReAct loop completed: success={success}, steps={len(steps)}, duration={total_duration:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"ReAct loop failed: {e}")
            # Create failure result
            return ReasoningResult(
                goal=goal,
                success=False,
                steps=steps,
                final_answer=f"Reasoning failed: {str(e)}",
                total_duration=time.time() - start_time,
                iterations=self.current_step,
                confidence=0.0
            )
    
    async def _thinking_phase(self, context: Dict[str, Any], step_id: int) -> Optional[ReasoningStep]:
        """
        THINKING phase: Analyze current situation and plan next action
        """
        start_time = time.time()
        
        thinking_prompt = self._create_thinking_prompt(context)
        
        if self.llm_agent:
            try:
                # Import Runner here to avoid circular imports
                from agents import Runner
                
                result = await Runner.run(
                    starting_agent=self.llm_agent,
                    input=thinking_prompt
                )
                
                thought = str(result.final_output)
                
                # Parse thought to determine if goal is complete
                is_complete = self._analyze_completion(thought, context)
                state = ReasoningState.COMPLETED if is_complete else ReasoningState.THINKING
                
                return ReasoningStep(
                    step_id=step_id,
                    state=state,
                    thought=thought,
                    confidence=self._estimate_confidence(thought),
                    duration=time.time() - start_time
                )
                
            except Exception as e:
                logger.error(f"Thinking phase failed: {e}")
                return ReasoningStep(
                    step_id=step_id,
                    state=ReasoningState.THINKING,
                    thought=f"Thinking failed: {str(e)}",
                    confidence=0.0,
                    duration=time.time() - start_time
                )
        else:
            # Fallback reasoning without LLM
            return ReasoningStep(
                step_id=step_id,
                state=ReasoningState.THINKING,
                thought=f"Analyzing goal: {context['goal']}. Need to determine next action.",
                confidence=0.5,
                duration=time.time() - start_time
            )
    
    async def _acting_phase(self, context: Dict[str, Any], step_id: int) -> Optional[ReasoningStep]:
        """
        ACTING phase: Execute the planned action WITH REAL TOOL EXECUTION
        
        🔧 ENHANCED: Now actually executes MCP tools instead of just simulating
        """
        start_time = time.time()
        
        # Determine the action to take based on context
        action, action_params = self._select_action(context)
        
        # 🔧 NEW: Actually execute the tool if possible
        tool_result = None
        execution_success = True
        execution_error = None
        
        try:
            # Check if this is an MCP tool that can be executed
            if action in self.available_mcp_tools and self.tool_executor:
                logger.info(f"Executing MCP tool: {action} with params: {action_params}")
                
                # Execute the actual MCP tool
                tool_result = await self.tool_executor(action, action_params)
                execution_success = True
                logger.info(f"Tool {action} executed successfully")
                
            elif action.startswith("mcp_") or action in self.available_mcp_tools:
                # This looks like an MCP tool but we can't execute it
                execution_error = f"MCP tool '{action}' cannot be executed (no executor available)"
                execution_success = False
                logger.warning(execution_error)
                
            else:
                # This is a built-in action, simulate it for now
                tool_result = f"Simulated execution of {action}"
                logger.info(f"Simulating built-in action: {action}")
                
        except Exception as e:
            execution_error = f"Tool execution failed: {str(e)}"
            execution_success = False
            logger.error(f"Error executing tool {action}: {e}")
        
        return ReasoningStep(
            step_id=step_id,
            state=ReasoningState.ACTING,
            thought=f"Executing action: {action}",
            action=action,
            action_params=action_params,
            confidence=0.7,
            duration=time.time() - start_time,
            # 🔧 NEW: Include actual execution results
            tool_result=tool_result,
            execution_success=execution_success,
            execution_error=execution_error
        )
    
    async def _observing_phase(self, context: Dict[str, Any], step_id: int, action_step: ReasoningStep) -> Optional[ReasoningStep]:
        """
        OBSERVING phase: Analyze the results of the action WITH REAL RESULTS
        
        🔧 ENHANCED: Now observes actual tool execution results
        """
        start_time = time.time()
        
        # Analyze real execution results
        if action_step and action_step.action:
            if action_step.execution_success and action_step.tool_result:
                # Real tool execution succeeded
                observation = f"Action '{action_step.action}' executed successfully. "
                
                # Analyze the result type and content
                result = action_step.tool_result
                if isinstance(result, dict):
                    if 'content' in result:
                        content = str(result['content'])[:200]
                        observation += f"Result: {content}..."
                    elif 'output' in result:
                        output = str(result['output'])[:200]
                        observation += f"Output: {output}..."
                    else:
                        observation += f"Data returned: {len(str(result))} characters"
                elif isinstance(result, str):
                    observation += f"Result: {result[:200]}..."
                elif isinstance(result, list):
                    observation += f"Returned {len(result)} items"
                else:
                    observation += f"Result type: {type(result).__name__}"
                    
            elif action_step.execution_error:
                # Tool execution failed
                observation = f"Action '{action_step.action}' failed: {action_step.execution_error}"
                
            else:
                # Simulated action
                observation = f"Action '{action_step.action}' was simulated (no real execution available)"
        else:
            observation = "No action was taken to observe."
        
        return ReasoningStep(
            step_id=step_id,
            state=ReasoningState.OBSERVING,
            thought=f"Observing results of action",
            observation=observation,
            confidence=0.8 if action_step.execution_success else 0.3,  # Higher confidence for real results
            duration=time.time() - start_time
        )
    
    async def _reflecting_phase(self, context: Dict[str, Any], step_id: int, observation_step: ReasoningStep) -> Optional[ReasoningStep]:
        """
        REFLECTING phase: Learn from the outcome and plan next step
        """
        start_time = time.time()
        
        if observation_step and observation_step.observation:
            reflection = f"Reflecting on observation: {observation_step.observation[:100]}..."
            
            # Determine if goal has been achieved
            goal_achieved = self._evaluate_goal_achievement(context, observation_step)
            confidence = 0.9 if goal_achieved else 0.4
            
            reflection += f" Goal achievement confidence: {confidence:.1f}"
            
        else:
            reflection = "No observation to reflect upon."
            confidence = 0.1
        
        return ReasoningStep(
            step_id=step_id,
            state=ReasoningState.REFLECTING,
            thought="Reflecting on progress and planning next steps",
            reflection=reflection,
            confidence=confidence,
            duration=time.time() - start_time
        )
    
    def _create_thinking_prompt(self, context: Dict[str, Any]) -> str:
        """Create a prompt for the thinking phase"""
        goal = context.get("goal", "")
        steps_taken = context.get("steps_taken", [])
        last_observation = context.get("last_observation", "")
        available_actions = context.get("available_actions", [])
        
        # Include available tools information if present
        available_tools_info = ""
        if "available_tools" in context:
            tools = context["available_tools"]
            if tools:
                available_tools_info = f"\nAvailable Tools ({len(tools)}):\n"
                for tool in tools:
                    tool_name = tool.get('name', 'unknown')
                    tool_desc = tool.get('description', 'No description')
                    tool_server = tool.get('server', 'unknown')
                    available_tools_info += f"  • {tool_name}: {tool_desc} (from {tool_server})\n"
        
        prompt = f"""
You are in the THINKING phase of a ReAct reasoning loop. Your goal is: {goal}

Steps taken so far: {len(steps_taken)}
Last observation: {last_observation}
{available_tools_info}
Available actions: {', '.join(available_actions)}

Analyze the current situation and determine:
1. What progress has been made toward the goal?
2. What is the next logical action to take?
3. Is the goal already achieved?

If the user is asking about tools or capabilities, refer to the actual available tools listed above.

Respond with your analysis and reasoning.
"""
        return prompt
    
    def _get_available_actions(self) -> List[str]:
        """Get list of available actions including MCP tools"""
        built_in_actions = [
            "search_information",
            "analyze_data", 
            "create_content",
            "request_clarification",
            "synthesize_results",
            "validate_answer"
        ]
        
        # 🔧 NEW: Add available MCP tools
        mcp_tools = list(self.available_mcp_tools.keys())
        
        return built_in_actions + mcp_tools
    
    def _select_action(self, context: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """Select the next action to take based on context and available tools"""
        steps_taken = context.get("steps_taken", [])
        goal = context.get("goal", "")
        available_tools = context.get("available_tools", [])
        
        # 🔧 NEW: Enhanced action selection with MCP tool awareness
        goal_lower = goal.lower()
        
        # Check if the goal mentions file operations
        if any(keyword in goal_lower for keyword in ['file', 'create', 'write', 'read', 'delete']):
            # Look for filesystem tools
            for tool_name in self.available_mcp_tools:
                if any(fs_keyword in tool_name.lower() for fs_keyword in ['file', 'write', 'read', 'create']):
                    if 'create' in goal_lower or 'write' in goal_lower:
                        # Extract filename from goal
                        import re
                        filename_match = re.search(r'create\s+(\w+\.\w+)', goal_lower)
                        if filename_match:
                            filename = filename_match.group(1)
                            return tool_name, {"path": filename, "content": "# Created by TinyAgent\n"}
                        else:
                            return tool_name, {"path": "debug.txt", "content": "# Created by TinyAgent\n"}
                    elif 'read' in goal_lower:
                        return tool_name, {"path": "debug.txt"}
        
        # Check if goal mentions search or information gathering
        if any(keyword in goal_lower for keyword in ['search', 'find', 'look', 'information']):
            for tool_name in self.available_mcp_tools:
                if any(search_keyword in tool_name.lower() for search_keyword in ['search', 'find', 'query']):
                    return tool_name, {"query": goal}
        
        # Fallback to built-in actions
        if len(steps_taken) == 0:
            return "search_information", {"query": goal}
        elif len(steps_taken) == 1:
            return "analyze_data", {"focus": "goal_alignment"}
        elif len(steps_taken) == 2:
            return "synthesize_results", {"format": "structured"}
        else:
            return "validate_answer", {"criteria": "completeness"}
    
    def _analyze_completion(self, thought: str, context: Dict[str, Any]) -> bool:
        """Analyze if the goal has been completed based on thought"""
        completion_indicators = [
            "goal achieved", "task completed", "answer found", 
            "objective met", "done", "finished", "complete"
        ]
        
        thought_lower = thought.lower()
        return any(indicator in thought_lower for indicator in completion_indicators)
    
    def _estimate_confidence(self, thought: str) -> float:
        """Estimate confidence level from thought content"""
        confidence_words = {
            "certain": 0.9, "confident": 0.8, "sure": 0.8,
            "likely": 0.7, "probably": 0.6, "maybe": 0.4,
            "uncertain": 0.3, "unclear": 0.2, "confused": 0.1
        }
        
        thought_lower = thought.lower()
        for word, confidence in confidence_words.items():
            if word in thought_lower:
                return confidence
        
        return 0.5  # Default confidence
    
    def _evaluate_goal_achievement(self, context: Dict[str, Any], observation_step: ReasoningStep) -> bool:
        """Evaluate if the goal has been achieved based on observations"""
        steps_taken = len(context.get("steps_taken", []))
        
        # Simple heuristic: if we've taken enough steps and have observations
        if steps_taken >= 2 and observation_step and observation_step.observation:
            return True
        
        return False
    
    async def _extract_final_answer(self, steps: List[ReasoningStep], context: Dict[str, Any]) -> str:
        """Extract the final answer from the reasoning process"""
        if not steps:
            return "No reasoning steps completed."
        
        # Find the last meaningful thought or observation
        for step in reversed(steps):
            if step.state == ReasoningState.COMPLETED and step.thought:
                return step.thought
            elif step.observation:
                return f"Based on reasoning: {step.observation}"
            elif step.reflection:
                return f"Final reflection: {step.reflection}"
        
        # Fallback to goal restatement
        return f"Completed analysis of: {context.get('goal', 'the given task')}"
    
    def get_reasoning_summary(self, result: ReasoningResult) -> str:
        """Get a human-readable summary of the reasoning process"""
        summary = f"Reasoning Summary for: {result.goal}\n"
        summary += f"Success: {result.success}\n"
        summary += f"Iterations: {result.iterations}\n"
        summary += f"Duration: {result.total_duration:.2f}s\n"
        summary += f"Confidence: {result.confidence:.1f}\n\n"
        
        summary += "Steps:\n"
        for i, step in enumerate(result.steps, 1):
            summary += f"{i}. {step.state.value.title()}: {step.thought[:100]}...\n"
            if step.action:
                summary += f"   Action: {step.action}\n"
            if step.observation:
                summary += f"   Observation: {step.observation[:100]}...\n"
        
        return summary 