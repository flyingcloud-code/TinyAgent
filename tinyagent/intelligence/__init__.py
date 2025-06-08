"""
TinyAgent Intelligence Module - Simplified
简化的智能模块，遵循专家版本的简洁原则
"""

# 🔧 简化的智能组件导入
try:
    from .planner import TaskPlanner, TaskPlan, TaskStep
    from .reasoner import ReasoningEngine
    from .executor import ActionExecutor, ActionResult
    from .intelligent_agent import IntelligentAgent, IntelligentAgentConfig
    
    # Intelligence is available if all components loaded successfully
    INTELLIGENCE_AVAILABLE = True
except ImportError as e:
    # If any intelligence component fails to import, mark as unavailable
    INTELLIGENCE_AVAILABLE = False
    
    # Create placeholder classes to prevent import errors
    class IntelligentAgent:
        pass
    
    class IntelligentAgentConfig:
        pass
    
    class TaskPlanner:
        pass
    
    class ReasoningEngine:
        pass
    
    class ActionExecutor:
        pass

__all__ = [
    "TaskPlanner",
    "TaskPlan", 
    "TaskStep",
    "ReasoningEngine",
    "ActionExecutor",
    "ActionResult",
    "IntelligentAgent",
    "IntelligentAgentConfig",
    "INTELLIGENCE_AVAILABLE"  # 🔧 CRITICAL: Export this flag
] 