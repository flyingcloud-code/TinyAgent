"""
Intelligence Module for TinyAgent
Implements core intelligence components for autonomous agent behavior.
"""

# 🔧 CRITICAL FIX: Import and export INTELLIGENCE_AVAILABLE
try:
    from .planner import TaskPlanner
    from .memory import ConversationMemory  
    from .selector import ToolSelector
    from .reasoner import ReasoningEngine
    from .actor import ActionExecutor
    from .observer import ResultObserver
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

__all__ = [
    "TaskPlanner",
    "ConversationMemory", 
    "ToolSelector",
    "ReasoningEngine",
    "ActionExecutor", 
    "ResultObserver",
    "IntelligentAgent",
    "IntelligentAgentConfig",
    "INTELLIGENCE_AVAILABLE"  # 🔧 CRITICAL: Export this flag
] 