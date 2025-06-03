# TinyAgent Package
"""TinyAgent Core Package"""

__version__ = "0.1.0"

# Import main classes for convenient access
from .core.agent import TinyAgent, create_agent
from .core.config import TinyAgentConfig, get_config

# Import intelligence components if available
try:
    from .intelligence import IntelligentAgent, IntelligentAgentConfig
    INTELLIGENCE_AVAILABLE = True
except ImportError:
    IntelligentAgent = None
    IntelligentAgentConfig = None
    INTELLIGENCE_AVAILABLE = False

__all__ = [
    'TinyAgent',
    'create_agent', 
    'TinyAgentConfig',
    'get_config',
    'IntelligentAgent',
    'IntelligentAgentConfig',
    'INTELLIGENCE_AVAILABLE'
] 