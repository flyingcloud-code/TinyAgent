"""
TinyAgent Configuration Management

This module handles loading and validating configuration files for TinyAgent.
It supports hierarchical YAML-based configuration with .env file integration
and profile-based configuration management.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
import logging
from copy import deepcopy

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    logging.warning("python-dotenv not available, .env files will not be loaded")

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Main agent configuration."""
    name: str = "TinyAgent"
    instructions_file: str = "prompts/default_instructions.txt"
    max_iterations: int = 10
    use_streaming: bool = True  # 是否使用流式API进行工具调用日志记录


@dataclass
class LLMConfig:
    """LLM provider configuration."""
    provider: str = "openai"
    model: str = "gpt-4"
    api_key_env: str = "OPENAI_API_KEY"
    base_url: Optional[str] = None
    max_tokens: int = 2000
    temperature: float = 0.7
    timeout: float = 30.0
    retry_attempts: int = 3


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server"""
    name: str
    type: str  # "stdio", "sse", "http"
    enabled: bool = True
    description: str = ""
    
    # Stdio-specific parameters
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    cwd: Optional[str] = None
    encoding: Optional[str] = None
    
    # SSE/HTTP-specific parameters
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout: Optional[float] = None
    sse_read_timeout: Optional[float] = None
    
    # HTTP-specific parameters
    terminate_on_close: Optional[bool] = None
    
    # General options
    cache_tools: bool = False
    category: str = "utility_operations"


@dataclass
class MCPConfig:
    """MCP servers configuration."""
    servers: Dict[str, MCPServerConfig] = field(default_factory=dict)
    auto_discover: bool = True
    enabled: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "structured"
    file: Optional[str] = None


@dataclass
class EnvironmentConfig:
    """Environment and .env configuration."""
    env_file: str = ".env"
    env_prefix: str = "TINYAGENT_"


@dataclass
class TinyAgentConfig:
    """Complete TinyAgent configuration."""
    agent: AgentConfig = field(default_factory=AgentConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)


class ConfigurationManager:
    """
    Enhanced configuration manager with hierarchical loading.
    
    Loading Order (highest to lowest priority):
    1. Environment Variables (.env file)
    2. User Configuration (config/)
    3. Profile Configurations (profiles/)
    4. Default Configurations (defaults/)
    """
    
    def __init__(self, 
                 config_dir: Optional[Path] = None,
                 profile: Optional[str] = None,
                 env_file: Optional[str] = None):
        """Initialize configuration manager.
        
        Args:
            config_dir: Directory containing configuration files.
            profile: Configuration profile to load (e.g., 'development', 'production').
            env_file: Path to .env file relative to project root.
        """
        self.config_dir = config_dir or self._find_config_dir()
        self.profile = profile or os.getenv("TINYAGENT_PROFILE", "development")
        self.env_file = env_file or ".env"
        self._config: Optional[TinyAgentConfig] = None
        
        # Load .env file first if available
        self._load_dotenv()
    
    def _find_config_dir(self) -> Path:
        """Find the configuration directory."""
        # Start from current working directory
        current_dir = Path.cwd()
        
        # Look for tinyagent/configs directory
        configs_dir = current_dir / "tinyagent" / "configs"
        if configs_dir.exists():
            return configs_dir
            
        # Look for configs directory in current directory
        configs_dir = current_dir / "configs"
        if configs_dir.exists():
            return configs_dir
            
        # Default to tinyagent/configs
        return current_dir / "tinyagent" / "configs"
    
    def _load_dotenv(self):
        """Load environment variables from .env file."""
        if not DOTENV_AVAILABLE:
            return
            
        # Try to find .env file in project root
        project_root = self.config_dir.parent.parent  # configs -> tinyagent -> project_root
        env_path = project_root / self.env_file
        
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded environment variables from: {env_path}")
        else:
            logger.debug(f"No .env file found at: {env_path}")
    
    def _load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Load and parse a YAML file."""
        if not file_path.exists():
            return {}
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f) or {}
            logger.debug(f"Loaded configuration from: {file_path}")
            return content
        except Exception as e:
            logger.error(f"Failed to load YAML file {file_path}: {e}")
            return {}
    
    def _load_defaults(self) -> Dict[str, Any]:
        """Load default configuration files (resource definitions only)."""
        defaults_dir = self.config_dir / "defaults"
        config = {}
        
        # 只加载资源定义文件
        default_files = [
            "llm_providers.yaml",   # LLM提供商资源定义
            "mcp_servers.yaml"      # MCP服务器资源定义
        ]
        
        for filename in default_files:
            file_path = defaults_dir / filename
            file_config = self._load_yaml_file(file_path)
            config = self._merge_configs(config, file_config)
        
        logger.debug("Loaded default resource definitions")
        return config
    
    def _load_profile(self, profile_name: str) -> Dict[str, Any]:
        """Load configuration from a specific profile."""
        profiles_dir = self.config_dir / "profiles"
        profile_file = profiles_dir / f"{profile_name}.yaml"
        
        config = self._load_yaml_file(profile_file)
        if config:
            logger.info(f"Loaded profile configuration: {profile_name}")
        else:
            logger.warning(f"Profile '{profile_name}' not found or empty")
        
        return config
    
    def _load_user_config(self) -> Dict[str, Any]:
        """Load user configuration files."""
        user_config_dir = self.config_dir / "config"
        config = {}
        
        # Load user config files if they exist
        user_files = [
            "agent.yaml",
            "llm.yaml",
            "mcp.yaml"
        ]
        
        for filename in user_files:
            file_path = user_config_dir / filename
            file_config = self._load_yaml_file(file_path)
            config = self._merge_configs(config, file_config)
        
        if config:
            logger.debug("Loaded user configurations")
        
        return config
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge two configuration dictionaries."""
        result = deepcopy(base)
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = deepcopy(value)
        
        return result
    
    def _substitute_env_vars(self, obj: Any) -> Any:
        """Recursively substitute environment variables in configuration."""
        if isinstance(obj, dict):
            return {k: self._substitute_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            return self._substitute_env_var_string(obj)
        else:
            return obj
    
    def _substitute_env_var_string(self, text: str) -> str:
        """Substitute environment variables in a string."""
        import re
        
        # Pattern for ${VAR_NAME} or ${VAR_NAME:default}
        pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
        
        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) is not None else ""
            return os.getenv(var_name, default_value)
        
        return re.sub(pattern, replace_var, text)
    
    def _parse_config(self, raw_config: Dict[str, Any]) -> TinyAgentConfig:
        """Parse raw configuration into typed configuration objects."""
        config = TinyAgentConfig()
        
        # Parse agent configuration
        if 'agent' in raw_config:
            agent_data = raw_config['agent']
            config.agent = AgentConfig(
                name=agent_data.get('name', config.agent.name),
                instructions_file=agent_data.get('instructions_file', config.agent.instructions_file),
                max_iterations=agent_data.get('max_iterations', config.agent.max_iterations),
                use_streaming=agent_data.get('use_streaming', config.agent.use_streaming)
            )
        
        # Parse LLM configuration
        if 'llm' in raw_config:
            llm_data = raw_config['llm']
            
            # Handle both direct config and provider-based config
            if 'providers' in llm_data:
                # Provider-based configuration
                active_provider = llm_data.get('active_provider', 'openai')
                providers = llm_data.get('providers', {})
                
                if active_provider in providers:
                    provider_config = providers[active_provider]
                    config.llm = LLMConfig(
                        provider=active_provider,
                        model=provider_config.get('model', config.llm.model),
                        api_key_env=provider_config.get('api_key_env', config.llm.api_key_env),
                        base_url=provider_config.get('base_url', config.llm.base_url),
                        max_tokens=provider_config.get('max_tokens', config.llm.max_tokens),
                        temperature=provider_config.get('temperature', config.llm.temperature),
                        timeout=provider_config.get('timeout', config.llm.timeout),
                        retry_attempts=provider_config.get('retry_attempts', config.llm.retry_attempts)
                    )
                else:
                    # Provider not found, use active_provider name but keep defaults
                    config.llm.provider = active_provider
            else:
                # Direct configuration (profile override)
                if 'active_provider' in llm_data:
                    # This is a profile setting active_provider, need to get provider config from defaults
                    active_provider = llm_data['active_provider']
                    
                    # Look for provider config in defaults (from llm_providers.yaml)
                    if 'providers' in raw_config and active_provider in raw_config['providers']:
                        provider_config = raw_config['providers'][active_provider]
                        config.llm = LLMConfig(
                            provider=active_provider,
                            model=provider_config.get('model', config.llm.model),
                            api_key_env=provider_config.get('api_key_env', config.llm.api_key_env),
                            base_url=provider_config.get('base_url', config.llm.base_url),
                            max_tokens=provider_config.get('max_tokens', config.llm.max_tokens),
                            temperature=provider_config.get('temperature', config.llm.temperature),
                            timeout=provider_config.get('timeout', config.llm.timeout),
                            retry_attempts=provider_config.get('retry_attempts', config.llm.retry_attempts)
                        )
                    else:
                        # Just set the provider name
                        config.llm.provider = active_provider
                else:
                    # Direct field configuration
                    config.llm = LLMConfig(
                        provider=llm_data.get('provider', config.llm.provider),
                        model=llm_data.get('model', config.llm.model),
                        api_key_env=llm_data.get('api_key_env', config.llm.api_key_env),
                        base_url=llm_data.get('base_url', config.llm.base_url),
                        max_tokens=llm_data.get('max_tokens', config.llm.max_tokens),
                        temperature=llm_data.get('temperature', config.llm.temperature),
                        timeout=llm_data.get('timeout', config.llm.timeout),
                        retry_attempts=llm_data.get('retry_attempts', config.llm.retry_attempts)
                    )
        
        # Parse MCP configuration
        if 'mcp' in raw_config:
            mcp_data = raw_config['mcp']
            servers = {}
            
            # 处理enabled_servers引用机制
            if 'enabled_servers' in mcp_data and 'servers' in raw_config:
                # 从defaults中获取服务器定义，根据enabled_servers筛选
                available_servers = raw_config['servers']
                enabled_server_names = mcp_data['enabled_servers']
                
                for server_name in enabled_server_names:
                    if server_name in available_servers:
                        server_data = available_servers[server_name]
                        servers[server_name] = MCPServerConfig(
                            name=server_name,
                            type=server_data.get('type', 'stdio'),
                            command=server_data.get('command', None),
                            args=server_data.get('args', None),
                            env=server_data.get('env', None),
                            cwd=server_data.get('cwd', None),
                            encoding=server_data.get('encoding', None),
                            url=server_data.get('url', None),
                            headers=server_data.get('headers', None),
                            timeout=server_data.get('timeout', None),
                            sse_read_timeout=server_data.get('sse_read_timeout', None),
                            terminate_on_close=server_data.get('terminate_on_close', None),
                            cache_tools=server_data.get('cache_tools', False),
                            description=server_data.get('description', ''),
                            enabled=True,  # enabled_servers中的都是启用的
                            category=server_data.get('category', 'utility_operations')
                        )
            elif 'servers' in mcp_data:
                # 兼容旧的直接定义方式
                for server_name, server_data in mcp_data.get('servers', {}).items():
                    servers[server_name] = MCPServerConfig(
                        name=server_name,
                        type=server_data.get('type', 'stdio'),
                        command=server_data.get('command', None),
                        args=server_data.get('args', None),
                        env=server_data.get('env', None),
                        cwd=server_data.get('cwd', None),
                        encoding=server_data.get('encoding', None),
                        url=server_data.get('url', None),
                        headers=server_data.get('headers', None),
                        timeout=server_data.get('timeout', None),
                        sse_read_timeout=server_data.get('sse_read_timeout', None),
                        terminate_on_close=server_data.get('terminate_on_close', None),
                        cache_tools=server_data.get('cache_tools', False),
                        description=server_data.get('description', ''),
                        enabled=server_data.get('enabled', True),
                        category=server_data.get('category', 'utility_operations')
                    )
            
            config.mcp = MCPConfig(
                servers=servers,
                auto_discover=mcp_data.get('auto_discover', True),
                enabled=mcp_data.get('enabled', True)
            )
        
        # Parse logging configuration
        if 'logging' in raw_config:
            logging_data = raw_config['logging']
            config.logging = LoggingConfig(
                level=logging_data.get('level', config.logging.level),
                format=logging_data.get('format', config.logging.format),
                file=logging_data.get('file', config.logging.file)
            )
        
        # Parse environment configuration
        if 'environment' in raw_config:
            env_data = raw_config['environment']
            config.environment = EnvironmentConfig(
                env_file=env_data.get('env_file', config.environment.env_file),
                env_prefix=env_data.get('env_prefix', config.environment.env_prefix)
            )
        
        return config
    
    def load_config(self, profile: Optional[str] = None) -> TinyAgentConfig:
        """Load and validate configuration with proper hierarchy.
        
        Args:
            profile: Override the default profile for this load operation.
            
        Returns:
            Loaded and validated configuration.
        """
        # Use provided profile or instance default
        active_profile = profile or self.profile
        
        try:
            # 1. Load defaults
            config = self._load_defaults()
            
            # 2. Load profile (if specified)
            if active_profile:
                profile_config = self._load_profile(active_profile)
                config = self._merge_configs(config, profile_config)
            
            # 3. Load user config
            user_config = self._load_user_config()
            config = self._merge_configs(config, user_config)
            
            # 4. Apply environment variable substitution
            config = self._substitute_env_vars(config)
            
            # 5. Parse into typed configuration
            self._config = self._parse_config(config)
            
            logger.info(f"Configuration loaded successfully (profile: {active_profile})")
            return self._config
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            # Return default configuration as fallback
            self._config = TinyAgentConfig()
            return self._config
    
    def get_config(self) -> TinyAgentConfig:
        """Get the current configuration. Load default if not loaded."""
        if self._config is None:
            return self.load_config()
        return self._config
    
    def validate_config(self) -> bool:
        """Validate the current configuration.
        
        Returns:
            True if configuration is valid, False otherwise.
        """
        config = self.get_config()
        
        try:
            # Validate LLM API key
            api_key = os.getenv(config.llm.api_key_env)
            if not api_key and config.llm.api_key_env:
                logger.warning(f"LLM API key not found in environment variable: {config.llm.api_key_env}")
                return False
            
            # Validate MCP servers
            for server_name, server_config in config.mcp.servers.items():
                if server_config.enabled and server_config.type == "stdio" and not server_config.command:
                    logger.error(f"MCP server '{server_name}' is enabled but has no command")
                    return False
            
            logger.info("Configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
    
    def get_available_profiles(self) -> List[str]:
        """Get list of available configuration profiles."""
        profiles_dir = self.config_dir / "profiles"
        if not profiles_dir.exists():
            return []
        
        profiles = []
        for file_path in profiles_dir.glob("*.yaml"):
            profiles.append(file_path.stem)
        
        return sorted(profiles)


# Global configuration manager instance
_config_manager: Optional[ConfigurationManager] = None


def get_config_manager(
    config_dir: Optional[Path] = None,
    profile: Optional[str] = None,
    env_file: Optional[str] = None
) -> ConfigurationManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager(
            config_dir=config_dir,
            profile=profile,
            env_file=env_file
        )
    return _config_manager


def get_config(profile: Optional[str] = None) -> TinyAgentConfig:
    """Get the current TinyAgent configuration."""
    return get_config_manager().load_config(profile=profile)


def set_profile(profile: str):
    """Set the active configuration profile."""
    global _config_manager
    if _config_manager is not None:
        _config_manager.profile = profile
        _config_manager._config = None  # Force reload on next access 