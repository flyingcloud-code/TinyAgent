"""
Task Planning Module for TinyAgent Intelligence System
Implements intelligent task analysis, decomposition, and execution planning.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import json
from datetime import datetime

from agents import Agent, Runner

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """Task complexity levels for planning strategy selection"""
    SIMPLE = "simple"          # Single tool call or direct answer
    MODERATE = "moderate"      # Multiple tool calls, sequential execution
    COMPLEX = "complex"        # Multi-step reasoning, parallel execution needed
    VERY_COMPLEX = "very_complex"  # Requires iterative planning and adaptation


@dataclass
class TaskStep:
    """Represents a single step in task execution plan"""
    step_id: int
    description: str
    required_tools: List[str]
    dependencies: List[int]  # Step IDs this step depends on
    estimated_duration: float  # seconds
    priority: int  # 1-10, higher is more important
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "required_tools": self.required_tools,
            "dependencies": self.dependencies,
            "estimated_duration": self.estimated_duration,
            "priority": self.priority
        }


@dataclass 
class TaskPlan:
    """Complete execution plan for a user task"""
    task_id: str
    user_input: str
    complexity: TaskComplexity
    steps: List[TaskStep]
    total_estimated_duration: float
    success_criteria: List[str]
    created_at: str
    
    def __post_init__(self):
        """Calculate total duration after initialization"""
        if not self.total_estimated_duration:
            self.total_estimated_duration = sum(step.estimated_duration for step in self.steps)
    
    def get_next_steps(self, completed_step_ids: List[int]) -> List[TaskStep]:
        """Get steps that can be executed next based on dependencies"""
        next_steps = []
        for step in self.steps:
            if step.step_id not in completed_step_ids:
                # Check if all dependencies are completed
                if all(dep_id in completed_step_ids for dep_id in step.dependencies):
                    next_steps.append(step)
        return sorted(next_steps, key=lambda x: x.priority, reverse=True)
    
    def is_complete(self, completed_step_ids: List[int]) -> bool:
        """Check if all steps are completed"""
        return len(completed_step_ids) == len(self.steps)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "user_input": self.user_input,
            "complexity": self.complexity.value,
            "steps": [step.to_dict() for step in self.steps],
            "total_estimated_duration": self.total_estimated_duration,
            "success_criteria": self.success_criteria,
            "created_at": self.created_at
        }


class TaskPlanner:
    """
    Intelligent Task Planning Engine
    
    Analyzes user input and creates detailed execution plans with:
    - Task complexity assessment
    - Tool requirement identification  
    - Step-by-step decomposition
    - Dependency analysis
    - Success criteria definition
    """
    
    def __init__(self, 
                 available_tools: Dict[str, Any],
                 planning_agent: Optional[Agent] = None,
                 max_steps: int = 10):
        """
        Initialize TaskPlanner
        
        Args:
            available_tools: Dictionary of available MCP tools
            planning_agent: Optional specialized planning agent
            max_steps: Maximum number of steps in a plan
        """
        self.available_tools = available_tools
        self.max_steps = max_steps
        self.planning_agent = planning_agent or self._create_default_planning_agent()
        
        logger.info(f"TaskPlanner initialized with {len(available_tools)} tools")
        
    def _create_default_planning_agent(self) -> Agent:
        """Create default planning agent if none provided"""
        logger.info(f"TaskPlanner:_create_default_planning_agent")
        return Agent(
            name="TaskPlanningAgent",
            instructions=self._get_planning_instructions(),
            model="gpt-4o-mini"  # Fast model for planning
        )
        
    def _get_planning_instructions(self) -> str:
        """Get comprehensive planning instructions for the agent"""
        tools_description = self._format_tools_for_instructions()
        
        return f"""You are an expert task planning agent. Your job is to analyze user requests and create detailed execution plans.

Available Tools:
{tools_description}

For each user request, analyze and provide:
1. Task complexity assessment (simple, moderate, complex, very_complex)
2. Required tools identification
3. Step-by-step decomposition with dependencies
4. Success criteria definition
5. Time estimation for each step

Rules:
- Break complex tasks into logical sequential or parallel steps
- Identify tool dependencies accurately  
- Provide realistic time estimates
- Include validation steps where needed
- Consider error recovery scenarios
- Maximum {self.max_steps} steps per plan

Output your analysis in structured JSON format following the TaskPlan schema."""

    def _format_tools_for_instructions(self) -> str:
        """Format available tools for agent instructions"""
        if not self.available_tools:
            return "No tools available"
            
        formatted = []
        for tool_name, tool_info in self.available_tools.items():
            description = getattr(tool_info, 'description', 'No description available')
            formatted.append(f"- {tool_name}: {description}")
            
        return "\n".join(formatted)
    
    async def analyze_and_plan(self, user_input: str) -> TaskPlan:
        """
        Analyze user input and create comprehensive execution plan
        
        Args:
            user_input: User's task request
            
        Returns:
            TaskPlan: Detailed execution plan
        """
        try:
            logger.info(f"Analyzing task: {user_input[:100]}...")
            
            # Prepare planning prompt
            planning_prompt = self._create_planning_prompt(user_input)

            logger.info(f"planning_prompt: {planning_prompt}")
            
            # Get plan from planning agent
            result = await Runner.run(
                self.planning_agent,
                planning_prompt,
                max_turns=3  # Allow for iterative planning
            )
            
            # Parse and validate plan
            plan = self._parse_planning_result(result.final_output, user_input)
            
            logger.info(f"Created plan with {len(plan.steps)} steps, complexity: {plan.complexity.value}")
            return plan
            
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            # Return simple fallback plan
            return self._create_fallback_plan(user_input)
    
    async def create_plan(self, task_description: str, context: Optional[Dict[str, Any]] = None) -> TaskPlan:
        """
        Create execution plan for a task (alias for analyze_and_plan for compatibility)
        
        Args:
            task_description: Description of the task to plan
            context: Optional context information
            
        Returns:
            TaskPlan: Detailed execution plan
        """
        # For now, ignore context and delegate to analyze_and_plan
        # TODO: Integrate context into planning process
        return await self.analyze_and_plan(task_description)
    
    def _create_planning_prompt(self, user_input: str) -> str:
        """Create detailed planning prompt for the agent"""
        return f"""Plan the execution of this user request:

User Request: "{user_input}"

Available Tools: {list(self.available_tools.keys())}

Create a detailed execution plan considering:
1. What is the user really asking for?
2. What tools are needed to accomplish this?
3. What are the logical steps to execute?
4. What are the dependencies between steps?
5. How long might each step take?
6. What defines success for this task?

Provide your plan in JSON format with the following structure:
{{
    "complexity": "simple|moderate|complex|very_complex",
    "steps": [
        {{
            "step_id": 1,
            "description": "Clear description of what to do",
            "required_tools": ["tool1", "tool2"],
            "dependencies": [],
            "estimated_duration": 5.0,
            "priority": 8
        }}
    ],
    "success_criteria": ["criterion1", "criterion2"]
}}

Think step by step and be thorough."""

    def _parse_planning_result(self, planning_output: str, user_input: str) -> TaskPlan:
        """Parse and validate planning agent output"""
        try:
            # Extract JSON from the output (handle cases where agent adds text)
            json_start = planning_output.find('{')
            json_end = planning_output.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No valid JSON found in planning output")
                
            json_str = planning_output[json_start:json_end]
            plan_data = json.loads(json_str)
            
            # Create TaskStep objects
            steps = []
            for step_data in plan_data.get('steps', []):
                step = TaskStep(
                    step_id=step_data['step_id'],
                    description=step_data['description'],
                    required_tools=step_data.get('required_tools', []),
                    dependencies=step_data.get('dependencies', []),
                    estimated_duration=step_data.get('estimated_duration', 5.0),
                    priority=step_data.get('priority', 5)
                )
                steps.append(step)
            
            # Create TaskPlan
            plan = TaskPlan(
                task_id=f"task_{hash(user_input) % 10000}",
                user_input=user_input,
                complexity=TaskComplexity(plan_data.get('complexity', 'moderate')),
                steps=steps,
                total_estimated_duration=0,  # Will be calculated in __post_init__
                success_criteria=plan_data.get('success_criteria', []),
                created_at=str(datetime.now())
            )
            
            return plan
            
        except Exception as e:
            logger.error(f"Failed to parse planning result: {e}")
            return self._create_fallback_plan(user_input)
    
    def _create_fallback_plan(self, user_input: str) -> TaskPlan:
        """Create simple fallback plan when planning fails"""
        return TaskPlan(
            task_id=f"fallback_{hash(user_input) % 10000}",
            user_input=user_input,
            complexity=TaskComplexity.SIMPLE,
            steps=[
                TaskStep(
                    step_id=1,
                    description=f"Process user request: {user_input}",
                    required_tools=[],
                    dependencies=[],
                    estimated_duration=10.0,
                    priority=5
                )
            ],
            total_estimated_duration=10.0,
            success_criteria=["Provide helpful response to user"],
            created_at=str(datetime.now())
        )
    
    def identify_required_tools(self, task_description: str) -> List[str]:
        """
        Identify tools needed for a specific task
        
        Args:
            task_description: Description of the task
            
        Returns:
            List of tool names needed
        """
        required_tools = []
        task_lower = task_description.lower()
        
        # Simple keyword-based tool identification
        # TODO: Replace with LLM-based intelligent selection
        tool_keywords = {
            'read_file': ['read', 'file', 'content', 'text'],
            'write_file': ['write', 'create', 'save', 'file'],
            'list_directory': ['list', 'directory', 'folder', 'files'],
            'google_search': ['search', 'google', 'find', 'lookup'],
            'get_weather': ['weather', 'temperature', 'forecast'],
            'get_web_content': ['fetch', 'url', 'webpage', 'website'],
            'sequentialthinking': ['think', 'analyze', 'reasoning', 'complex']
        }
        
        for tool_name, keywords in tool_keywords.items():
            if tool_name in self.available_tools:
                if any(keyword in task_lower for keyword in keywords):
                    required_tools.append(tool_name)
        
        logger.debug(f"Identified tools for '{task_description}': {required_tools}")
        return required_tools
    
    def decompose_into_steps(self, task: str) -> List[TaskStep]:
        """
        Decompose task into executable steps
        
        Args:
            task: Task description
            
        Returns:
            List of TaskStep objects
        """
        # Simple rule-based decomposition
        # TODO: Replace with LLM-based intelligent decomposition
        
        steps = []
        task_lower = task.lower()
        step_id = 1
        
        # Search-based tasks
        if any(word in task_lower for word in ['search', 'find', 'lookup']):
            steps.append(TaskStep(
                step_id=step_id,
                description="Perform search for relevant information",
                required_tools=['google_search'],
                dependencies=[],
                estimated_duration=3.0,
                priority=8
            ))
            step_id += 1
            
            if any(word in task_lower for word in ['summarize', 'summary', 'analyze']):
                steps.append(TaskStep(
                    step_id=step_id,
                    description="Analyze and summarize search results",
                    required_tools=['sequentialthinking'],
                    dependencies=[step_id - 1],
                    estimated_duration=5.0,
                    priority=7
                ))
                step_id += 1
        
        # File operations
        if any(word in task_lower for word in ['file', 'read', 'write']):
            if 'read' in task_lower or 'content' in task_lower:
                steps.append(TaskStep(
                    step_id=step_id,
                    description="Read file content",
                    required_tools=['read_file'],
                    dependencies=[],
                    estimated_duration=2.0,
                    priority=8
                ))
                step_id += 1
            
            if 'write' in task_lower or 'create' in task_lower:
                steps.append(TaskStep(
                    step_id=step_id,
                    description="Write file content",
                    required_tools=['write_file'],
                    dependencies=[],
                    estimated_duration=3.0,
                    priority=7
                ))
                step_id += 1
        
        # Default step if no specific patterns found
        if not steps:
            steps.append(TaskStep(
                step_id=1,
                description=f"Process request: {task}",
                required_tools=[],
                dependencies=[],
                estimated_duration=5.0,
                priority=5
            ))
        
        logger.debug(f"Decomposed task into {len(steps)} steps")
        return steps

    def estimate_duration(self, steps: List[TaskStep]) -> float:
        """Estimate total duration for task completion"""
        # Consider dependencies for parallel execution
        max_duration = 0
        step_durations = {step.step_id: step.estimated_duration for step in steps}
        
        def get_step_end_time(step_id: int, calculated: Dict[int, float]) -> float:
            if step_id in calculated:
                return calculated[step_id]
            
            step = next(s for s in steps if s.step_id == step_id)
            
            # Calculate when this step can start (after all dependencies)
            start_time = 0
            for dep_id in step.dependencies:
                start_time = max(start_time, get_step_end_time(dep_id, calculated))
            
            # End time is start time + duration
            end_time = start_time + step.estimated_duration
            calculated[step_id] = end_time
            return end_time
        
        calculated = {}
        for step in steps:
            end_time = get_step_end_time(step.step_id, calculated)
            max_duration = max(max_duration, end_time)
            
        return max_duration

    def validate_plan(self, plan: TaskPlan) -> List[str]:
        """
        Validate plan for consistency and feasibility
        
        Returns:
            List of validation issues (empty if valid)
        """
        issues = []
        
        # Check for circular dependencies
        def has_circular_deps(step_id: int, visited: set, path: set) -> bool:
            if step_id in path:
                return True
            if step_id in visited:
                return False
                
            visited.add(step_id)
            path.add(step_id)
            
            step = next((s for s in plan.steps if s.step_id == step_id), None)
            if step:
                for dep_id in step.dependencies:
                    if has_circular_deps(dep_id, visited, path):
                        return True
            
            path.remove(step_id)
            return False
        
        visited = set()
        for step in plan.steps:
            if has_circular_deps(step.step_id, visited, set()):
                issues.append(f"Circular dependency detected involving step {step.step_id}")
        
        # Check tool availability
        for step in plan.steps:
            for tool in step.required_tools:
                if tool not in self.available_tools:
                    issues.append(f"Step {step.step_id} requires unavailable tool: {tool}")
        
        # Check dependency validity
        step_ids = {step.step_id for step in plan.steps}
        for step in plan.steps:
            for dep_id in step.dependencies:
                if dep_id not in step_ids:
                    issues.append(f"Step {step.step_id} depends on non-existent step {dep_id}")
        
        return issues

    async def update_plan_with_observation(self, 
                                         plan: TaskPlan, 
                                         completed_steps: List[int],
                                         step_results: Dict[int, Any],
                                         observation: str) -> TaskPlan:
        """
        Update plan based on execution results and observations
        
        Args:
            plan: Current task plan
            completed_steps: List of completed step IDs
            step_results: Results from completed steps
            observation: Observation about current state
            
        Returns:
            Updated TaskPlan
        """
        try:
            # For now, return the same plan
            # TODO: Implement intelligent plan adaptation
            logger.info(f"Plan update requested - completed: {len(completed_steps)} steps")
            return plan
            
        except Exception as e:
            logger.error(f"Plan update failed: {e}")
            return plan 