"""
Action Executor Module for TinyAgent Intelligence System
Implements intelligent action execution and tool orchestration.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ActionStatus(Enum):
    """Status of action execution"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


@dataclass
class ActionResult:
    """Result of action execution"""
    action_id: str
    action_name: str
    status: ActionStatus
    result: Any
    execution_time: float
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionRequest:
    """Request for action execution"""
    action_id: str
    action_name: str
    parameters: Dict[str, Any]
    tool_function: Optional[Callable] = None
    max_retries: int = 3
    timeout: float = 60.0
    priority: int = 1
    dependencies: List[str] = field(default_factory=list)


class ActionExecutor:
    """
    Intelligent Action Execution Engine
    
    This executor provides sophisticated action execution capabilities including:
    - Parallel action execution with dependency management
    - Automatic retries with exponential backoff
    - Result validation and error handling
    - Performance monitoring and metrics
    - Tool orchestration and coordination
    """
    
    def __init__(self, max_concurrent_actions: int = 5, default_timeout: float = 60.0, llm_agent=None):
        """
        Initialize ActionExecutor
        
        Args:
            max_concurrent_actions: Maximum number of concurrent actions
            default_timeout: Default timeout for actions in seconds
            llm_agent: LLM agent for intelligent built-in actions (required)
        """
        self.max_concurrent_actions = max_concurrent_actions
        self.default_timeout = default_timeout
        self.llm_agent = llm_agent
        self.active_actions: Dict[str, ActionRequest] = {}
        self.completed_actions: Dict[str, ActionResult] = {}
        self.tool_registry: Dict[str, Callable] = {}
        self.action_queue: asyncio.Queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(max_concurrent_actions)
        
        # Performance metrics
        self.total_actions = 0
        self.successful_actions = 0
        self.failed_actions = 0
        self.total_execution_time = 0.0
        
        logger.info(f"ActionExecutor initialized with max_concurrent={max_concurrent_actions}, llm_enabled={llm_agent is not None}")
    
    def register_tool(self, name: str, tool_function: Callable):
        """
        Register a tool function for execution
        
        Args:
            name: Name of the tool
            tool_function: Function to execute
        """
        self.tool_registry[name] = tool_function
        logger.info(f"Registered tool: {name}")
    
    async def execute_action(self, action_name: str, parameters: Dict[str, Any], 
                           action_id: Optional[str] = None, **kwargs) -> ActionResult:
        """
        Execute a single action
        
        Args:
            action_name: Name of the action to execute
            parameters: Parameters for the action
            action_id: Optional custom action ID
            **kwargs: Additional execution options
            
        Returns:
            ActionResult with execution details
        """
        if action_id is None:
            action_id = f"{action_name}_{int(time.time() * 1000)}"
        
        # Create action request
        request = ActionRequest(
            action_id=action_id,
            action_name=action_name,
            parameters=parameters,
            tool_function=self.tool_registry.get(action_name),
            max_retries=kwargs.get('max_retries', 3),
            timeout=kwargs.get('timeout', self.default_timeout),
            priority=kwargs.get('priority', 1)
        )
        
        logger.info(f"Executing action: {action_name} (id: {action_id})")
        
        return await self._execute_single_action(request)
    
    async def execute_parallel_actions(self, actions: List[Dict[str, Any]]) -> List[ActionResult]:
        """
        Execute multiple actions in parallel with dependency management
        
        Args:
            actions: List of action definitions
            
        Returns:
            List of ActionResults
        """
        logger.info(f"Executing {len(actions)} actions in parallel")
        
        # Create action requests
        requests = []
        for i, action in enumerate(actions):
            action_id = action.get('action_id', f"action_{i}_{int(time.time() * 1000)}")
            request = ActionRequest(
                action_id=action_id,
                action_name=action['action_name'],
                parameters=action.get('parameters', {}),
                tool_function=self.tool_registry.get(action['action_name']),
                max_retries=action.get('max_retries', 3),
                timeout=action.get('timeout', self.default_timeout),
                priority=action.get('priority', 1),
                dependencies=action.get('dependencies', [])
            )
            requests.append(request)
        
        # Execute with dependency management
        return await self._execute_with_dependencies(requests)
    
    async def _execute_single_action(self, request: ActionRequest) -> ActionResult:
        """Execute a single action with retries and error handling"""
        self.total_actions += 1
        self.active_actions[request.action_id] = request
        
        result = ActionResult(
            action_id=request.action_id,
            action_name=request.action_name,
            status=ActionStatus.PENDING,
            result=None,
            execution_time=0.0
        )
        
        try:
            async with self.semaphore:  # Limit concurrent executions
                for attempt in range(request.max_retries + 1):
                    try:
                        result.status = ActionStatus.RUNNING
                        result.retry_count = attempt
                        
                        start_time = time.time()
                        
                        # Execute the action
                        if request.tool_function:
                            # Execute registered tool function
                            action_result = await self._execute_tool_function(
                                request.tool_function, 
                                request.parameters,
                                request.timeout
                            )
                        else:
                            # Execute built-in action
                            action_result = await self._execute_builtin_action(
                                request.action_name,
                                request.parameters,
                                request.timeout
                            )
                        
                        execution_time = time.time() - start_time
                        
                        # Validate result
                        if self._validate_result(action_result, request):
                            result.status = ActionStatus.COMPLETED
                            result.result = action_result
                            result.execution_time = execution_time
                            result.end_time = time.time()
                            
                            self.successful_actions += 1
                            self.total_execution_time += execution_time
                            
                            logger.info(f"Action {request.action_id} completed successfully in {execution_time:.2f}s")
                            break
                        else:
                            raise ValueError("Result validation failed")
                    
                    except asyncio.TimeoutError:
                        error_msg = f"Action {request.action_id} timed out after {request.timeout}s"
                        logger.warning(error_msg)
                        
                        if attempt < request.max_retries:
                            result.status = ActionStatus.RETRYING
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        else:
                            result.status = ActionStatus.FAILED
                            result.error_message = error_msg
                    
                    except Exception as e:
                        error_msg = f"Action {request.action_id} failed: {str(e)}"
                        logger.error(error_msg)
                        
                        if attempt < request.max_retries:
                            result.status = ActionStatus.RETRYING
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        else:
                            result.status = ActionStatus.FAILED
                            result.error_message = error_msg
                
                # Final status check
                if result.status != ActionStatus.COMPLETED:
                    self.failed_actions += 1
                    result.end_time = time.time()
                    result.execution_time = result.end_time - result.start_time
        
        finally:
            # Cleanup
            if request.action_id in self.active_actions:
                del self.active_actions[request.action_id]
            self.completed_actions[request.action_id] = result
        
        return result
    
    async def _execute_tool_function(self, tool_function: Callable, parameters: Dict[str, Any], timeout: float) -> Any:
        """Execute a registered tool function with timeout"""
        try:
            if asyncio.iscoroutinefunction(tool_function):
                # Async function
                return await asyncio.wait_for(tool_function(**parameters), timeout=timeout)
            else:
                # Sync function - run in executor
                loop = asyncio.get_event_loop()
                return await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: tool_function(**parameters)),
                    timeout=timeout
                )
        except Exception as e:
            logger.error(f"Tool function execution failed: {e}")
            raise
    
    async def _execute_builtin_action(self, action_name: str, parameters: Dict[str, Any], timeout: float) -> Any:
        """Execute built-in actions"""
        logger.info(f"Executing built-in action: {action_name}")
        
        # Built-in action implementations
        if action_name == "search_information":
            return await self._builtin_search(parameters.get('query', ''))
        elif action_name == "analyze_data":
            return await self._builtin_analyze(parameters.get('data', ''), parameters.get('focus', ''))
        elif action_name == "create_content":
            return await self._builtin_create(parameters.get('type', ''), parameters.get('specification', ''))
        elif action_name == "synthesize_results":
            return await self._builtin_synthesize(parameters.get('inputs', []), parameters.get('format', 'text'))
        elif action_name == "validate_answer":
            return await self._builtin_validate(parameters.get('answer', ''), parameters.get('criteria', []))
        else:
            raise ValueError(f"Unknown built-in action: {action_name}")
    
    async def _builtin_search(self, query: str) -> Dict[str, Any]:
        """Built-in search action simulation"""
        await asyncio.sleep(0.5)  # Simulate search time
        return {
            "query": query,
            "results": f"Search results for: {query}",
            "sources": ["source1", "source2", "source3"],
            "confidence": 0.85
        }
    
    async def _builtin_analyze(self, data: str, focus: str) -> Dict[str, Any]:
        """Built-in analysis action using LLM"""
        if not self.llm_agent:
            raise ValueError("LLM agent is required for analyze action but not provided")
            
        try:
            from agents import Runner
            prompt = f"Analyze the following data with focus on '{focus}': {data[:1000]}"
            result = await Runner.run(self.llm_agent, prompt)
            
            return {
                "data": data[:100] + "..." if len(data) > 100 else data,
                "focus": focus,
                "insights": result.final_output,
                "confidence": 0.85,
                "method": "llm_analysis"
            }
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            raise
    
    async def _builtin_create(self, content_type: str, specification: str) -> Dict[str, Any]:
        """Built-in content creation action using LLM"""
        if not self.llm_agent:
            raise ValueError("LLM agent is required for create action but not provided")
            
        try:
            from agents import Runner
            prompt = f"Create {content_type} content based on this specification: {specification}"
            result = await Runner.run(self.llm_agent, prompt)
            
            return {
                "type": content_type,
                "specification": specification,
                "content": result.final_output,
                "confidence": 0.90,
                "method": "llm_creation"
            }
        except Exception as e:
            logger.error(f"LLM content creation failed: {e}")
            raise
    
    async def _builtin_synthesize(self, inputs: List[Any], format_type: str) -> Dict[str, Any]:
        """Built-in synthesis action using LLM"""
        if not self.llm_agent:
            raise ValueError("LLM agent is required for synthesize action but not provided")
            
        try:
            from agents import Runner
            inputs_text = str(inputs)[:2000]  # Limit input size
            prompt = f"Synthesize these inputs into {format_type} format: {inputs_text}"
            result = await Runner.run(self.llm_agent, prompt)
            
            return {
                "inputs_count": len(inputs),
                "format": format_type,
                "synthesis": result.final_output,
                "confidence": 0.95,
                "method": "llm_synthesis"
            }
        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            raise
    
    async def _builtin_validate(self, answer: str, criteria: List[str]) -> Dict[str, Any]:
        """Built-in validation action using LLM"""
        if not self.llm_agent:
            raise ValueError("LLM agent is required for validate action but not provided")
            
        try:
            from agents import Runner
            criteria_text = ", ".join(criteria)
            prompt = f"Validate this answer against these criteria: {criteria_text}. Answer: {answer[:500]}. Respond with 'VALID' or 'INVALID' followed by your reasoning."
            result = await Runner.run(self.llm_agent, prompt)
            
            # Parse LLM result for validation decision
            response_text = result.final_output.upper()
            passed = "VALID" in response_text and "INVALID" not in response_text
            
            return {
                "answer": answer[:100] + "..." if len(answer) > 100 else answer,
                "criteria": criteria,
                "validation_result": result.final_output,
                "passed": passed,
                "confidence": 0.95,
                "method": "llm_validation"
            }
        except Exception as e:
            logger.error(f"LLM validation failed: {e}")
            raise
    
    def _validate_result(self, result: Any, request: ActionRequest) -> bool:
        """Validate action result"""
        if result is None:
            return False
        
        # Basic validation - can be enhanced based on action type
        if isinstance(result, dict):
            return "confidence" in result or "result" in result or len(result) > 0
        elif isinstance(result, (str, list, tuple)):
            return len(result) > 0
        else:
            return True
    
    async def _execute_with_dependencies(self, requests: List[ActionRequest]) -> List[ActionResult]:
        """Execute actions with dependency management"""
        completed = {}
        results = []
        
        # Create dependency graph
        dependency_graph = {req.action_id: req.dependencies for req in requests}
        request_map = {req.action_id: req for req in requests}
        
        # Execute in dependency order
        while len(completed) < len(requests):
            # Find actions ready to execute (no pending dependencies)
            ready_actions = []
            for req in requests:
                if req.action_id not in completed:
                    dependencies_met = all(dep in completed for dep in req.dependencies)
                    if dependencies_met:
                        ready_actions.append(req)
            
            if not ready_actions:
                # Circular dependency or error
                remaining = [req.action_id for req in requests if req.action_id not in completed]
                logger.error(f"Circular dependency detected or no ready actions. Remaining: {remaining}")
                break
            
            # Execute ready actions in parallel
            tasks = [self._execute_single_action(req) for req in ready_actions]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    # Create failed result
                    failed_result = ActionResult(
                        action_id=ready_actions[i].action_id,
                        action_name=ready_actions[i].action_name,
                        status=ActionStatus.FAILED,
                        result=None,
                        execution_time=0.0,
                        error_message=str(result)
                    )
                    results.append(failed_result)
                    completed[ready_actions[i].action_id] = failed_result
                else:
                    results.append(result)
                    completed[result.action_id] = result
        
        return results
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        success_rate = (self.successful_actions / self.total_actions * 100) if self.total_actions > 0 else 0
        avg_execution_time = (self.total_execution_time / self.successful_actions) if self.successful_actions > 0 else 0
        
        return {
            "total_actions": self.total_actions,
            "successful_actions": self.successful_actions,
            "failed_actions": self.failed_actions,
            "success_rate": success_rate,
            "average_execution_time": avg_execution_time,
            "total_execution_time": self.total_execution_time,
            "active_actions": len(self.active_actions),
            "registered_tools": len(self.tool_registry)
        }
    
    def get_action_status(self, action_id: str) -> Optional[ActionResult]:
        """Get status of a specific action"""
        return self.completed_actions.get(action_id)
    
    def get_active_actions(self) -> List[str]:
        """Get list of currently active action IDs"""
        return list(self.active_actions.keys())
    
    async def cancel_action(self, action_id: str) -> bool:
        """Cancel an active action"""
        if action_id in self.active_actions:
            # Mark for cancellation - actual cancellation depends on implementation
            logger.info(f"Cancellation requested for action: {action_id}")
            return True
        return False
    
    def clear_completed_actions(self):
        """Clear completed actions history"""
        self.completed_actions.clear()
        logger.info("Cleared completed actions history") 