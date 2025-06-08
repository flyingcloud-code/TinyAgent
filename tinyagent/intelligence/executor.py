"""
TinyAgent 简化执行器 (ActionExecutor + ResultObserver)
合并行动执行和结果观察功能 - 遵循专家版本简洁原则
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ActionResult:
    """简化的行动结果"""
    action_name: str
    parameters: Dict[str, Any]
    result: Any
    success: bool
    execution_time: float
    error_message: Optional[str] = None

class ActionExecutor:
    """
    简化的行动执行器
    
    遵循专家版本原则:
    - 单一职责: 只执行行动和观察结果
    - 简单实现: 没有复杂的并行、重试、依赖管理
    - 透明错误: 错误直接抛出或记录
    """
    
    def __init__(self, mcp_manager=None, llm_agent=None):
        """
        初始化执行器
        
        Args:
            mcp_manager: MCP管理器，用于调用工具
            llm_agent: LLM代理，用于内置行动
        """
        self.mcp_manager = mcp_manager
        self.llm_agent = llm_agent
        self.logger = logging.getLogger(__name__)
        self.tool_registry = {}  # 工具注册表
    
    def register_tool(self, tool_name: str, tool_function):
        """注册工具到注册表"""
        self.tool_registry[tool_name] = tool_function
    
    async def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> ActionResult:
        """
        执行单个行动
        
        Args:
            action_name: 行动名称
            parameters: 行动参数
            
        Returns:
            ActionResult: 执行结果
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"执行行动: {action_name}")
            
            # 检查是否是MCP工具
            if self.mcp_manager and self.mcp_manager.get_tool_by_name(action_name):
                result = await self._execute_mcp_tool(action_name, parameters)
            else:
                result = await self._execute_builtin_action(action_name, parameters)
            
            execution_time = time.time() - start_time
            
            # 观察和验证结果
            is_valid = self._observe_result(action_name, result)
            
            return ActionResult(
                action_name=action_name,
                parameters=parameters,
                result=result,
                success=is_valid,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"行动执行失败 {action_name}: {e}")
            
            return ActionResult(
                action_name=action_name,
                parameters=parameters,
                result=None,
                success=False,
                execution_time=execution_time,
                error_message=str(e)
            )
    
    async def _execute_mcp_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """执行MCP工具"""
        if not self.mcp_manager:
            raise RuntimeError("MCP管理器未初始化")
        
        return await self.mcp_manager.call_tool(tool_name, parameters)
    
    async def _execute_builtin_action(self, action_name: str, parameters: Dict[str, Any]) -> Any:
        """执行内置行动"""
        if not self.llm_agent:
            raise RuntimeError(f"内置行动需要LLM代理: {action_name}")
        
        # 简化的内置行动处理
        if action_name == "search_information":
            return await self._search_action(parameters)
        elif action_name == "analyze_data":
            return await self._analyze_action(parameters)
        elif action_name == "create_content":
            return await self._create_action(parameters)
        else:
            # 通用LLM处理
            prompt = f"请执行以下行动: {action_name}\n参数: {parameters}"
            response = await self.llm_agent.run(prompt)
            return response.messages[-1].content if response.messages else "无结果"
    
    async def _search_action(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """搜索信息行动"""
        query = parameters.get("query", "")
        prompt = f"请搜索并总结关于以下查询的信息: {query}"
        
        response = await self.llm_agent.run(prompt)
        content = response.messages[-1].content if response.messages else "搜索失败"
        
        return {
            "query": query,
            "results": content,
            "source": "llm_search"
        }
    
    async def _analyze_action(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """分析数据行动"""
        data = parameters.get("data", "")
        focus = parameters.get("focus", "general")
        
        prompt = f"请分析以下数据，重点关注: {focus}\n\n数据: {data}"
        response = await self.llm_agent.run(prompt)
        content = response.messages[-1].content if response.messages else "分析失败"
        
        return {
            "analysis": content,
            "focus": focus,
            "confidence": "medium"
        }
    
    async def _create_action(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """创建内容行动"""
        content_type = parameters.get("type", "text")
        specification = parameters.get("specification", "")
        
        prompt = f"请创建 {content_type} 类型的内容，要求: {specification}"
        response = await self.llm_agent.run(prompt)
        content = response.messages[-1].content if response.messages else "创建失败"
        
        return {
            "content": content,
            "type": content_type,
            "specification": specification
        }
    
    def _observe_result(self, action_name: str, result: Any) -> bool:
        """
        观察和验证结果 (简化版结果观察器功能)
        
        Args:
            action_name: 行动名称
            result: 执行结果
            
        Returns:
            bool: 结果是否有效
        """
        # 简单的结果验证逻辑
        if result is None:
            self.logger.warning(f"行动 {action_name} 返回空结果")
            return False
        
        if isinstance(result, dict) and result.get("error"):
            self.logger.warning(f"行动 {action_name} 返回错误: {result.get('error')}")
            return False
        
        if isinstance(result, str) and len(result.strip()) == 0:
            self.logger.warning(f"行动 {action_name} 返回空字符串")
            return False
        
        self.logger.info(f"行动 {action_name} 执行成功，结果类型: {type(result).__name__}")
        return True
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要 (简化版)"""
        return {
            "status": "active",
            "mcp_available": self.mcp_manager is not None,
            "llm_available": self.llm_agent is not None
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标（兼容性方法）"""
        return self.get_performance_summary() 