"""
TinyAgent 简化配置管理
重构原则: 零配置启动，环境变量优先，智能默认值
删除复杂的分层配置系统，回归简洁性
"""

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Any, List
from copy import deepcopy

# Optional dependencies
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class AgentConfig:
    """Agent configuration with intelligent defaults."""
    name: str = "TinyAgent"
    instructions_file: str = "prompts/default_instructions.txt"
    max_iterations: int = 10
    use_streaming: bool = True
    intelligent_mode: bool = True
    
    # Intelligence configuration with sane defaults
    max_reasoning_iterations: int = 10
    confidence_threshold: float = 0.8
    max_concurrent_actions: int = 5
    action_timeout: float = 60.0
    memory_max_context_turns: int = 20
    use_detailed_observation: bool = True
    enable_learning: bool = True

@dataclass
class LLMConfig:
    """LLM configuration with built-in provider definitions."""
    provider: str = "openrouter"  # Default to most stable provider
    model: str = "deepseek/deepseek-chat-v3-0324"
    api_key_env: str = "OPENROUTER_API_KEY"
    base_url: Optional[str] = "https://openrouter.ai/api/v1"
    max_tokens: int = 2000
    temperature: float = 0.7
    timeout: float = 30.0
    retry_attempts: int = 3

@dataclass
class MCPServerConfig:
    """简化的MCP服务器配置"""
    name: str
    type: str  # "stdio", "sse"
    enabled: bool = True
    description: str = ""
    
    # Stdio parameters
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    
    # SSE parameters
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout: Optional[float] = None
    sse_read_timeout: Optional[float] = None

@dataclass
class MCPConfig:
    """MCP配置with built-in server definitions."""
    servers: Dict[str, MCPServerConfig] = field(default_factory=dict)
    auto_discover: bool = True
    enabled: bool = True
    enabled_servers: List[str] = field(default_factory=lambda: ["filesystem", "my-search"])

@dataclass
class LoggingConfig:
    """简化的日志配置"""
    level: str = "INFO"
    console_level: str = "USER"
    file_level: str = "DEBUG"
    format: str = "user_friendly"
    file: Optional[str] = "logs/development.log"
    structured_file: Optional[str] = "logs/metrics/dev-metrics.jsonl"
    max_file_size: str = "5MB"
    backup_count: int = 5
    enable_colors: bool = True
    show_timestamps: bool = False

@dataclass
class TinyAgentConfig:
    """Complete simplified TinyAgent configuration."""
    agent: AgentConfig = field(default_factory=AgentConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

class SimpleConfigManager:
    """
    Simplified configuration manager - Zero Config Experience
    
    Loading Priority (简化为2层):
    1. Environment Variables (.env file if exists)
    2. Optional YAML file (configs/development.yaml)
    3. Built-in intelligent defaults
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize with minimal configuration."""
        self.config_dir = config_dir or self._find_config_dir()
        self._config: Optional[TinyAgentConfig] = None
        
        # Load .env if available (不强制要求)
        self._load_dotenv()
    
    def _find_config_dir(self) -> Path:
        """Find config directory or create default path."""
        current_dir = Path.cwd()
        configs_dir = current_dir / "tinyagent" / "configs"
        return configs_dir  # Return even if doesn't exist
    
    def _load_dotenv(self):
        """Load .env file if available."""
        if not DOTENV_AVAILABLE:
            return
            
        project_root = self.config_dir.parent.parent
        env_path = project_root / ".env"
        
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded environment variables from: {env_path}")
    
    def _get_built_in_mcp_servers(self) -> Dict[str, MCPServerConfig]:
        """Built-in MCP server definitions - no external files needed."""
        servers = {
            "filesystem": MCPServerConfig(
                name="filesystem",
                type="stdio",
                enabled=True,
                description="File system operations",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", str(Path.cwd())],
                env={}
            ),
            "my-search": MCPServerConfig(
                name="my-search", 
                type="sse",
                enabled=True,
                description="Web search capabilities",
                url="http://192.168.1.3:8081/sse",
                headers={},
                timeout=30.0,
                sse_read_timeout=120.0
            ),
            "sequential-thinking": MCPServerConfig(
                name="sequential-thinking",
                type="stdio", 
                enabled=False,  # Disabled by default for stability
                description="Sequential thinking capabilities",
                command="uvx",
                args=["mcp-server-sequential-thinking"],
                env={}
            )
        }
        return servers
    
    def _get_provider_config(self, provider: str) -> Dict[str, Any]:
        """Built-in provider configurations."""
        providers = {
            "openai": {
                "model": "gpt-4",
                "api_key_env": "OPENAI_API_KEY",
                "base_url": "https://api.openai.com/v1",
                "max_tokens": 8000,
                "temperature": 0.7
            },
            "openrouter": {
                "model": "deepseek/deepseek-chat-v3-0324",
                "api_key_env": "OPENROUTER_API_KEY", 
                "base_url": "https://openrouter.ai/api/v1",
                "max_tokens": 2000,
                "temperature": 0.7
            },
            "azure": {
                "model": "gpt-4",
                "api_key_env": "AZURE_OPENAI_API_KEY",
                "base_url": None,  # Will be set from AZURE_OPENAI_ENDPOINT
                "max_tokens": 8000,
                "temperature": 0.7
            }
        }
        return providers.get(provider, providers["openrouter"])
    
    def _apply_env_overrides(self, config: TinyAgentConfig) -> TinyAgentConfig:
        """Apply environment variable overrides."""
        
        # LLM Provider override
        if "TINYAGENT_LLM_PROVIDER" in os.environ:
            provider = os.environ["TINYAGENT_LLM_PROVIDER"]
            provider_config = self._get_provider_config(provider)
            config.llm.provider = provider
            config.llm.model = provider_config["model"]
            config.llm.api_key_env = provider_config["api_key_env"]
            config.llm.base_url = provider_config["base_url"]
            config.llm.max_tokens = provider_config["max_tokens"]
            config.llm.temperature = provider_config["temperature"]
        
        # Model override
        if "TINYAGENT_MODEL" in os.environ:
            config.llm.model = os.environ["TINYAGENT_MODEL"]
        
        # Azure special handling
        if config.llm.provider == "azure" and "AZURE_OPENAI_ENDPOINT" in os.environ:
            config.llm.base_url = os.environ["AZURE_OPENAI_ENDPOINT"]
        
        # Log level override
        if "TINYAGENT_LOG_LEVEL" in os.environ:
            config.logging.level = os.environ["TINYAGENT_LOG_LEVEL"]
        
        # Intelligent mode override
        if "TINYAGENT_INTELLIGENT_MODE" in os.environ:
            config.agent.intelligent_mode = os.environ["TINYAGENT_INTELLIGENT_MODE"].lower() == "true"
        
        return config
    
    def _load_optional_yaml(self) -> Dict[str, Any]:
        """Load optional YAML configuration if exists."""
        if not YAML_AVAILABLE:
            return {}
        
        yaml_path = self.config_dir / "development.yaml"
        if not yaml_path.exists():
            return {}
        
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f) or {}
            logger.info(f"Loaded optional configuration from: {yaml_path}")
            return content
        except Exception as e:
            logger.warning(f"Failed to load YAML config {yaml_path}: {e}")
            return {}
    
    def load_config(self) -> TinyAgentConfig:
        """Load complete configuration with zero-config experience."""
        if self._config is not None:
            return self._config
        
        # Start with intelligent defaults
        config = TinyAgentConfig()
        
        # Add built-in MCP servers
        config.mcp.servers = self._get_built_in_mcp_servers()
        
        # Apply optional YAML overrides (minimal usage)
        yaml_config = self._load_optional_yaml()
        if yaml_config:
            config = self._merge_yaml_config(config, yaml_config)
        
        # Apply environment variable overrides (highest priority)
        config = self._apply_env_overrides(config)
        
        self._config = config
        return config
    
    def _merge_yaml_config(self, config: TinyAgentConfig, yaml_config: Dict[str, Any]) -> TinyAgentConfig:
        """Apply minimal YAML configuration overrides."""
        
        # Agent overrides
        if 'agent' in yaml_config:
            agent_data = yaml_config['agent']
            for key, value in agent_data.items():
                if hasattr(config.agent, key):
                    setattr(config.agent, key, value)
        
        # LLM overrides
        if 'llm' in yaml_config:
            llm_data = yaml_config['llm']
            if 'active_provider' in llm_data:
                provider = llm_data['active_provider']
                provider_config = self._get_provider_config(provider)
                config.llm.provider = provider
                config.llm.model = provider_config["model"]
                config.llm.api_key_env = provider_config["api_key_env"]
                config.llm.base_url = provider_config["base_url"]
        
        # MCP overrides  
        if 'mcp' in yaml_config:
            mcp_data = yaml_config['mcp']
            if 'enabled_servers' in mcp_data:
                config.mcp.enabled_servers = mcp_data['enabled_servers']
        
        # Logging overrides
        if 'logging' in yaml_config:
            logging_data = yaml_config['logging']
            for key, value in logging_data.items():
                if hasattr(config.logging, key):
                    setattr(config.logging, key, value)
        
        return config
    
    def get_config(self) -> TinyAgentConfig:
        """Get current configuration."""
        return self.load_config()
    
    def validate_config(self) -> bool:
        """Minimal validation - just check API key availability."""
        config = self.get_config()
        api_key = os.getenv(config.llm.api_key_env)
        
        if not api_key:
            logger.error(f"Missing required API key: {config.llm.api_key_env}")
            logger.info("Please set your API key in environment variables or .env file")
            return False
        
        return True

# Simplified global interface
_config_manager: Optional[SimpleConfigManager] = None

def get_config_manager(config_dir: Optional[Path] = None) -> SimpleConfigManager:
    """Get global configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = SimpleConfigManager(config_dir)
    return _config_manager

def get_config() -> TinyAgentConfig:
    """Get current configuration - Zero Config Experience."""
    return get_config_manager().get_config()

def validate_config() -> bool:
    """Validate current configuration."""
    return get_config_manager().validate_config() 