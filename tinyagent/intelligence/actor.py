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
    
    async def execute_action_stream(self, action_name: str, parameters: Dict[str, Any], 
                                  action_id: Optional[str] = None, **kwargs):
        """
        Execute a single action with streaming output for real-time feedback
        
        Args:
            action_name: Name of the action to execute
            parameters: Parameters for the action
            action_id: Optional custom action ID
            **kwargs: Additional execution options
            
        Yields:
            Real-time updates from the action execution process
        """
        if action_id is None:
            action_id = f"{action_name}_{int(time.time() * 1000)}"
        
        yield f"⚡ **ActionExecutor 开始执行行动**\n"
        yield f"🎯 行动名称: {action_name}\n"
        yield f"🆔 行动ID: {action_id}\n"
        yield f"📋 参数: {len(parameters)} 个\n"
        
        try:
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
            
            yield f"📝 **步骤1**: 准备执行环境...\n"
            yield f"   🔄 最大重试次数: {request.max_retries}\n"
            yield f"   ⏱️  超时设置: {request.timeout:.1f}秒\n"
            yield f"   🎛️  优先级: {request.priority}\n"
            
            # Check tool availability
            yield f"🔧 **步骤2**: 检查工具可用性...\n"
            if request.tool_function:
                yield f"   ✅ 找到注册的工具函数: {action_name}\n"
                tool_type = "registered"
            elif action_name in ['search_information', 'analyze_data', 'create_content', 'synthesize_results', 'validate_answer']:
                yield f"   🛠️  使用内置行动: {action_name}\n"
                tool_type = "builtin"
            else:
                yield f"   ⚠️  工具不可用，将尝试通用执行\n"
                tool_type = "unknown"
            
            # Execute with streaming updates
            yield f"🚀 **步骤3**: 开始执行行动...\n"
            yield f"   📊 工具类型: {tool_type}\n"
            
            start_time = time.time()
            result = None
            error_occurred = False
            retry_count = 0
            
            # Execute with retries and stream each attempt
            for attempt in range(request.max_retries + 1):
                if attempt > 0:
                    yield f"🔄 **重试第 {attempt} 次**\n"
                    yield f"   ⏰ 等待 {2 ** attempt} 秒后重试...\n"
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
                try:
                    yield f"   ⚡ 执行尝试 {attempt + 1}/{request.max_retries + 1}\n"
                    
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
                    
                    result = action_result
                    retry_count = attempt
                    yield f"   ✅ 执行成功！\n"
                    break
                    
                except asyncio.TimeoutError:
                    yield f"   ⏰ 执行超时 ({request.timeout}秒)\n"
                    if attempt == request.max_retries:
                        error_occurred = True
                        result = f"Action timed out after {request.timeout} seconds"
                except Exception as e:
                    yield f"   ❌ 执行失败: {str(e)}\n"
                    if attempt == request.max_retries:
                        error_occurred = True
                        result = f"Action failed: {str(e)}"
            
            execution_time = time.time() - start_time
            
            # Create result
            action_result = ActionResult(
                action_id=action_id,
                action_name=action_name,
                status=ActionStatus.FAILED if error_occurred else ActionStatus.COMPLETED,
                result=result,
                execution_time=execution_time,
                retry_count=retry_count,
                error_message=result if error_occurred else None
            )
            
            # Update metrics
            self.total_actions += 1
            if error_occurred:
                self.failed_actions += 1
            else:
                self.successful_actions += 1
            self.total_execution_time += execution_time
            
            # Store result
            self.completed_actions[action_id] = action_result
            
            # Final status
            yield f"\n🎯 **执行完成**\n"
            yield f"   ✅ 状态: {'失败' if error_occurred else '成功'}\n"
            yield f"   ⏱️  总耗时: {execution_time:.2f}秒\n"
            yield f"   🔄 重试次数: {retry_count}\n"
            yield f"   📊 结果大小: {len(str(result))} 字符\n"
            
            # Store the result for later access
            self._last_action_result = action_result
            yield f"\n"
            
        except Exception as e:
            yield f"\n❌ **执行异常**: {str(e)}\n"
            
            # Create error result
            error_result = ActionResult(
                action_id=action_id,
                action_name=action_name,
                status=ActionStatus.FAILED,
                result=None,
                execution_time=time.time() - start_time if 'start_time' in locals() else 0.0,
                error_message=str(e)
            )
            
            self.completed_actions[action_id] = error_result
            self._last_action_result = error_result

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

    async def execute_parallel_actions_stream(self, actions: List[Dict[str, Any]]):
        """
        Execute multiple actions in parallel with streaming output for real-time feedback
        
        Args:
            actions: List of action definitions
            
        Yields:
            Real-time updates from the parallel execution process
        """
        yield f"🚀 **ActionExecutor 开始并行执行**\n"
        yield f"📊 总行动数: {len(actions)}\n"
        yield f"🎛️  最大并发数: {self.max_concurrent_actions}\n"
        
        try:
            # Step 1: Validate and prepare actions
            yield f"📋 **步骤1**: 验证和准备行动...\n"
            
            requests = []
            for i, action in enumerate(actions):
                action_id = action.get('action_id', f"action_{i}_{int(time.time() * 1000)}")
                action_name = action['action_name']
                
                yield f"   {i+1}. {action_name} (ID: {action_id})\n"
                
                request = ActionRequest(
                    action_id=action_id,
                    action_name=action_name,
                    parameters=action.get('parameters', {}),
                    tool_function=self.tool_registry.get(action_name),
                    max_retries=action.get('max_retries', 3),
                    timeout=action.get('timeout', self.default_timeout),
                    priority=action.get('priority', 1),
                    dependencies=action.get('dependencies', [])
                )
                requests.append(request)
            
            # Step 2: Analyze dependencies
            yield f"\n🔗 **步骤2**: 分析依赖关系...\n"
            dependency_map = {}
            for req in requests:
                if req.dependencies:
                    dependency_map[req.action_id] = req.dependencies
                    yield f"   📎 {req.action_name} 依赖: {', '.join(req.dependencies)}\n"
            
            if not dependency_map:
                yield f"   ✅ 无依赖关系，可完全并行执行\n"
            
            # Step 3: Execute with dependency management
            yield f"\n⚡ **步骤3**: 开始并行执行...\n"
            
            start_time = time.time()
            results = []
            completed_actions = set()
            running_tasks = {}
            
            # Helper function to check if action can start
            def can_start_action(req):
                return all(dep in completed_actions for dep in req.dependencies)
            
            # Initial batch - actions with no dependencies
            ready_actions = [req for req in requests if can_start_action(req)]
            
            yield f"   🟢 第一批可执行行动: {len(ready_actions)} 个\n"
            
            # Start initial actions
            for req in ready_actions:
                if len(running_tasks) < self.max_concurrent_actions:
                    task = asyncio.create_task(self._execute_single_action(req))
                    running_tasks[req.action_id] = (task, req)
                    yield f"   ▶️  启动: {req.action_name}\n"
            
            # Execute remaining actions as dependencies complete
            remaining_requests = [req for req in requests if req not in ready_actions]
            
            while running_tasks or remaining_requests:
                if running_tasks:
                    # Wait for at least one task to complete
                    done, pending = await asyncio.wait(
                        [task for task, _ in running_tasks.values()],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    # Process completed tasks
                    for task in done:
                        # Find which action completed
                        completed_action_id = None
                        for action_id, (t, req) in running_tasks.items():
                            if t == task:
                                completed_action_id = action_id
                                completed_req = req
                                break
                        
                        if completed_action_id:
                            try:
                                result = await task
                                results.append(result)
                                completed_actions.add(completed_action_id)
                                yield f"   ✅ 完成: {completed_req.action_name} ({result.status.value})\n"
                            except Exception as e:
                                error_result = ActionResult(
                                    action_id=completed_action_id,
                                    action_name=completed_req.action_name,
                                    status=ActionStatus.FAILED,
                                    result=None,
                                    execution_time=0.0,
                                    error_message=str(e)
                                )
                                results.append(error_result)
                                completed_actions.add(completed_action_id)
                                yield f"   ❌ 失败: {completed_req.action_name} - {str(e)}\n"
                            
                            # Remove from running tasks
                            del running_tasks[completed_action_id]
                
                # Check if any remaining actions can now start
                newly_ready = [req for req in remaining_requests if can_start_action(req)]
                
                for req in newly_ready:
                    if len(running_tasks) < self.max_concurrent_actions:
                        task = asyncio.create_task(self._execute_single_action(req))
                        running_tasks[req.action_id] = (task, req)
                        remaining_requests.remove(req)
                        yield f"   ▶️  启动: {req.action_name} (依赖已满足)\n"
            
            total_time = time.time() - start_time
            success_count = sum(1 for result in results if result.status == ActionStatus.COMPLETED)
            
            # Final summary
            yield f"\n🎉 **并行执行完成**\n"
            yield f"   📊 总行动数: {len(results)}\n"
            yield f"   ✅ 成功: {success_count}\n"
            yield f"   ❌ 失败: {len(results) - success_count}\n"
            yield f"   ⏱️  总耗时: {total_time:.2f}秒\n"
            yield f"   📈 并行效率: {len(actions) / max(total_time, 0.1):.1f} 行动/秒\n"
            
            # Store the results for later access
            self._last_parallel_results = results
            yield f"\n"
            
        except Exception as e:
            yield f"\n❌ **并行执行异常**: {str(e)}\n"
            self._last_parallel_results = []

    async def get_last_action_result(self) -> Optional[ActionResult]:
        """
        Get the result from the last streaming action execution
        
        Returns:
            The last ActionResult, or None if no execution has been performed
        """
        return getattr(self, '_last_action_result', None)

    async def get_last_parallel_results(self) -> List[ActionResult]:
        """
        Get the results from the last streaming parallel execution
        
        Returns:
            List of ActionResults from the last parallel execution
        """
        return getattr(self, '_last_parallel_results', []) 