"""
TinyAgent 简化规划器 (TaskPlanner + ToolSelector)
合并任务规划和工具选择功能 - 遵循专家版本简洁原则
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TaskStep:
    """简化的任务步骤"""
    description: str
    tool_name: Optional[str]
    parameters: Dict[str, Any]

@dataclass
class TaskPlan:
    """简化的任务计划"""
    user_input: str
    steps: List[TaskStep]
    reasoning: str

class TaskPlanner:
    """
    简化的任务规划器
    
    遵循专家版本原则:
    - 单一职责: 任务规划 + 工具选择
    - 简单实现: 避免复杂的依赖分析、时间估算等
    - 实用主义: 专注于实际有用的功能
    """
    
    def __init__(self, available_tools: Dict[str, Any] = None, llm_agent=None):
        """
        初始化规划器
        
        Args:
            available_tools: 可用工具字典
            llm_agent: LLM代理用于智能规划
        """
        self.available_tools = available_tools or {}
        self.llm_agent = llm_agent
        self.logger = logging.getLogger(__name__)
    
    async def create_plan(self, user_input: str) -> TaskPlan:
        """
        为用户输入创建执行计划
        
        Args:
            user_input: 用户任务描述
            
        Returns:
            TaskPlan: 简化的任务计划
        """
        try:
            self.logger.info(f"创建任务计划: {user_input[:100]}...")
            
            # 简单的规划逻辑 - 如果有LLM代理则使用智能规划，否则使用启发式规划
            if self.llm_agent:
                return await self._create_intelligent_plan(user_input)
            else:
                return self._create_heuristic_plan(user_input)
                
        except Exception as e:
            self.logger.error(f"规划创建失败: {e}")
            # 返回简单的回退计划
            return self._create_fallback_plan(user_input)
    
    async def _create_intelligent_plan(self, user_input: str) -> TaskPlan:
        """使用LLM代理创建智能计划"""
        tools_list = self._format_available_tools()
        
        planning_prompt = f"""请分析以下用户请求并创建执行计划:

用户请求: {user_input}

可用工具:
{tools_list}

请提供:
1. 简单的推理过程
2. 具体的执行步骤，每个步骤包含:
   - 步骤描述
   - 需要的工具名称(如果有)
   - 工具参数(如果有)

请保持计划简洁实用。"""

        response = await self.llm_agent.run(planning_prompt)
        content = response.messages[-1].content if response.messages else ""
        
        # 简化的计划解析
        return self._parse_llm_plan(user_input, content)
    
    def _create_heuristic_plan(self, user_input: str) -> TaskPlan:
        """基于启发式规则创建计划"""
        steps = []
        reasoning = "基于启发式规则的简单规划"
        
        # 简单的关键词匹配来选择工具
        input_lower = user_input.lower()
        
        if any(keyword in input_lower for keyword in ['文件', 'file', '读取', 'read', '写入', 'write']):
            # 文件操作任务
            if 'list' in input_lower or '列出' in input_lower:
                steps.append(TaskStep("列出文件", "list_directory", {"path": "."}))
            elif 'read' in input_lower or '读取' in input_lower:
                steps.append(TaskStep("读取文件", "read_file", {"path": "需要用户指定"}))
            else:
                steps.append(TaskStep("文件操作", "file_operation", {}))
        
        elif any(keyword in input_lower for keyword in ['搜索', 'search', '查找', 'find']):
            # 搜索任务
            steps.append(TaskStep("搜索信息", "search_information", {"query": user_input}))
        
        elif any(keyword in input_lower for keyword in ['分析', 'analyze', '处理', 'process']):
            # 分析任务  
            steps.append(TaskStep("分析数据", "analyze_data", {"data": user_input}))
        
        else:
            # 通用任务
            steps.append(TaskStep("处理用户请求", None, {"request": user_input}))
        
        return TaskPlan(
            user_input=user_input,
            steps=steps,
            reasoning=reasoning
        )
    
    def _create_fallback_plan(self, user_input: str) -> TaskPlan:
        """创建回退计划"""
        steps = [TaskStep(
            description="直接回答用户问题",
            tool_name=None,
            parameters={"request": user_input}
        )]
        
        return TaskPlan(
            user_input=user_input,
            steps=steps,
            reasoning="简单回退计划 - 直接处理"
        )
    
    def _parse_llm_plan(self, user_input: str, llm_response: str) -> TaskPlan:
        """解析LLM生成的计划"""
        steps = []
        reasoning = llm_response[:200] + "..." if len(llm_response) > 200 else llm_response
        
        # 简化的解析逻辑 - 寻找步骤模式
        lines = llm_response.split('\n')
        current_step = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 寻找步骤标识
            if any(marker in line.lower() for marker in ['步骤', 'step', '1.', '2.', '3.', '-']):
                if current_step:
                    steps.append(current_step)
                
                # 创建新步骤
                description = line
                tool_name = self._extract_tool_from_description(description)
                parameters = {"description": description}
                
                current_step = TaskStep(
                    description=description,
                    tool_name=tool_name,
                    parameters=parameters
                )
        
        # 添加最后一个步骤
        if current_step:
            steps.append(current_step)
        
        # 如果没有找到步骤，创建一个默认步骤
        if not steps:
            steps.append(TaskStep(
                description="处理用户请求",
                tool_name=None,
                parameters={"request": user_input}
            ))
        
        return TaskPlan(
            user_input=user_input,
            steps=steps,
            reasoning=reasoning
        )
    
    def _extract_tool_from_description(self, description: str) -> Optional[str]:
        """从步骤描述中提取工具名称 (简化版工具选择功能)"""
        desc_lower = description.lower()
        
        # 简单的工具匹配规则
        tool_patterns = {
            'list_directory': ['列出', 'list', '目录', 'directory'],
            'read_file': ['读取', 'read', '文件', 'file'],
            'write_file': ['写入', 'write', '创建', 'create'],
            'search': ['搜索', 'search', '查找'],
            'analyze': ['分析', 'analyze', '处理']
        }
        
        for tool_name, patterns in tool_patterns.items():
            if any(pattern in desc_lower for pattern in patterns):
                # 检查工具是否可用
                if tool_name in self.available_tools:
                    return tool_name
        
        return None
    
    def _format_available_tools(self) -> str:
        """格式化可用工具列表"""
        if not self.available_tools:
            return "暂无可用工具"
        
        formatted = []
        for tool_name, tool_info in self.available_tools.items():
            if hasattr(tool_info, 'description'):
                desc = tool_info.description
            else:
                desc = "无描述"
            formatted.append(f"- {tool_name}: {desc}")
        
        return '\n'.join(formatted)
    
    def select_best_tool(self, task_description: str) -> Optional[str]:
        """
        选择最适合的工具 (简化版工具选择器功能)
        
        Args:
            task_description: 任务描述
            
        Returns:
            Optional[str]: 最适合的工具名称
        """
        return self._extract_tool_from_description(task_description)
    
    def get_tool_parameters_suggestion(self, tool_name: str, context: str) -> Dict[str, Any]:
        """
        建议工具参数 (简化版)
        
        Args:
            tool_name: 工具名称
            context: 上下文信息
            
        Returns:
            Dict[str, Any]: 建议的参数
        """
        # 简化的参数建议逻辑
        if tool_name == "list_directory":
            return {"path": "."}
        elif tool_name == "read_file":
            return {"path": "需要用户指定文件路径"}
        elif tool_name == "search":
            return {"query": context}
        else:
            return {"input": context} 