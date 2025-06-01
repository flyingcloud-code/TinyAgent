# System Patterns: TinyAgent
*Version: 1.0*
*Created: 2025-05-31*
*Last Updated: 2025-06-01*

## Architecture Overview
TinyAgent employs a modular architecture centered around a core agent engine built with Python and the `openai-agents-python` SDK. The agent operates on a ReAct (Reasoning and Acting) loop, with future provisions for a Reflect mechanism. Extensibility is a key design principle, achieved through configurable LLM providers, externalized prompts, and a robust Model Context Protocol (MCP) integration for tool use. The initial interaction is via a Command-Line Interface (CLI).

## Key Components
- **Core Agent Engine:**
    - *Purpose:* Manages the main operational loop (ReAct), orchestrates calls to LLMs and MCP tools, and maintains conversational context.
    - *Details:* Built on `openai-agents-python`. Includes the `Runner.run()` for the basic loop.
- **LLM Provider Module:**
    - *Purpose:* Abstracts interactions with Large Language Models, allowing for configurable selection of different LLM providers (e.g., OpenAI, local models via LiteLLM).
    - *Details:* Managed via `llm_config.yaml`.
- **Prompt Management Module:**
    - *Purpose:* Loads agent instructions and task-specific prompts from external files (e.g., `prompts/` directory).
    - *Details:* Allows behavior customization without code changes.
- **MCP Configuration & Integration Module:**
    - *Purpose:* Manages connections to MCP servers (defined in `mcp_agent.config.yaml`) and facilitates tool discovery and invocation by the agent.
    - *Details:* Leverages `openai-agents-mcp` extension or a custom solution. Supports stdio-based tools initially, with design for future HTTP/SSE tools.
- **MCP Tool Ecosystem:**
    - *Purpose:* Provides the set of external tools the agent can use to perform actions (e.g., file access, data processing, code analysis).
    - *Details:* Tools are exposed by MCP servers. Configuration allows for metadata and categorization.
- **Configuration Files (`mcp_agent.config.yaml`, `llm_config.yaml`, `prompts/`):**
    - *Purpose:* Define and configure MCP servers, LLM providers, and prompts, respectively. Central to the agent's customizability and extensibility.
- **Command-Line Interface (CLI):**
    - *Purpose:* Provides the initial user interaction point for initiating tasks and receiving outputs.
- **Workflow Management Module (Future):**
    - *Purpose:* Placeholder for future advanced workflow orchestration logic.

## Design Patterns in Use
- **Modular Design:** The system is broken down into distinct modules (LLM, Prompts, MCP, Core Engine) with clear responsibilities to enhance maintainability and extensibility.
- **Configuration-Driven Design:** Key aspects like tool integration, LLM selection, and prompts are managed through external configuration files, promoting flexibility.
- **Abstraction Layer:** Used for LLM providers to decouple the core agent from specific LLM implementations.
- **ReAct (Reasoning and Acting):** The core operational paradigm for the agent, enabling it to reason about tasks and take actions.
- **Strategy Pattern (Implicit):** Different LLMs or prompt sets could be seen as different strategies for task execution, selectable via configuration.

## Data Flow (Example: PRD Generation as described in PRD)
1.  **Initiation:** User initiates PRD generation via CLI, providing input (e.g., feature list).
2.  **Analysis & Planning:** TinyAgent (using its configured LLM and PRD generation prompts) analyzes the input and plans steps (e.g., "identify PRD sections," "draft intro").
3.  **Execution (Action & Tool Use):**
    - Agent may call an MCP tool (e.g., `file_reader_tool` to get a PRD template, or a `text_formatter_tool`). Tool execution is managed via the MCP Integration Module.
    - Agent sends requests to the configured LLM (via LLM Provider Module) for content generation based on prompts and context.
4.  **Observation & Assembly:** Agent receives tool outputs and LLM responses.
5.  **Content Assembly:** Agent assembles the PRD content.
6.  **Reflection (Future):** Agent reviews the generated PRD against criteria, potentially refining it.
7.  **Output:** Agent outputs the final PRD to the user (e.g., prints to console or saves to a file using an MCP tool).

## Key Technical Decisions
- **Use `openai-agents-python` SDK:** Provides a foundational framework for agent development.
- **Adopt MCP for Tooling:** Enables a standardized and extensible way to integrate tools.
- **Externalize Configuration:** LLMs, Prompts, and MCP tools are configured externally for flexibility.
- **Initial CLI Focus:** Prioritizes core functionality over a GUI for the first version.
- **Stdio for Initial MCP Tools:** Simplifies local tool integration.
- **ReAct Loop as Core:** Provides a robust pattern for agent operation.

## Component Relationships
```mermaid
graph TD
    User --> CLI;
    CLI --> CoreAgentEngine;
    CoreAgentEngine -- Manages --> LLMProviderModule;
    CoreAgentEngine -- Manages --> PromptManagementModule;
    CoreAgentEngine -- Manages --> MCPIntegrationModule;
    LLMProviderModule -- Uses Config --> LLMConfig[llm_config.yaml];
    LLMProviderModule -- Interacts --> LLMService[LLM Service (e.g., OpenAI API)];
    PromptManagementModule -- Uses Config --> PromptsDir[prompts/ directory];
    MCPIntegrationModule -- Uses Config --> MCPConfig[mcp_agent.config.yaml];
    MCPIntegrationModule -- Interacts --> MCPTools[MCP Tool Servers (Stdio/HTTP)];
    CoreAgentEngine -- Outputs/Inputs --> User;
```

## Configuration Architecture Design

### Current Issues Analysis

**Problems with Current Configuration:**
1. **Duplication**: LLM settings exist in both `agent_config.yaml` and `llm_config.yaml`
2. **No Clear Hierarchy**: Multiple config files with unclear precedence
3. **Mixed Concerns**: Main config and examples mixed together
4. **Inconsistent Naming**: `mcp_agent.config.yaml` vs `agent_config.yaml`
5. **No Environment Support**: Limited .env file integration
6. **Complex Structure**: Difficult to understand relationships

### Proposed Configuration Architecture

#### 1. Configuration Hierarchy (按优先级排序)

```
1. Environment Variables (.env file)     [HIGHEST PRIORITY]
2. User Configuration (config/)          [HIGH PRIORITY]
3. Profile Configurations (profiles/)    [MEDIUM PRIORITY]  
4. Default Configurations (defaults/)    [LOWEST PRIORITY]
```

#### 2. File Structure

```
tinyagent/configs/
├── defaults/                    # 默认配置 (只读，随代码分发)
│   ├── agent.yaml              # 代理默认设置
│   ├── llm_providers.yaml      # LLM提供商默认配置
│   └── mcp_servers.yaml        # MCP服务器默认配置
├── profiles/                    # 预设配置文件 (示例和模板)
│   ├── development.yaml        # 开发环境配置
│   ├── production.yaml         # 生产环境配置
│   ├── openrouter.yaml         # OpenRouter示例
│   └── local_llm.yaml          # 本地LLM示例
├── config/                      # 用户自定义配置 (优先级最高)
│   ├── agent.yaml              # 用户代理配置
│   ├── llm.yaml                # 用户LLM配置
│   └── mcp.yaml                # 用户MCP配置
└── .env                         # 环境变量 (敏感信息)
```

#### 3. Configuration Loading Logic

```python
# 配置加载优先级逻辑
def load_configuration():
    config = {}
    
    # 1. 加载默认配置
    config.update(load_defaults())
    
    # 2. 加载选定的配置文件 (如果指定)
    if profile:
        config.update(load_profile(profile))
    
    # 3. 加载用户配置 (覆盖默认和配置文件)
    config.update(load_user_config())
    
    # 4. 应用环境变量 (最高优先级)
    config.update(apply_env_vars(config))
    
    return config
```

### 4. Configuration Schema Design

#### 4.1 Master Configuration Structure

```yaml
# config/agent.yaml - 主配置文件
agent:
  name: "TinyAgent"
  profile: "development"  # 可选: 指定要加载的profile
  instructions_file: "prompts/default_instructions.txt"
  max_iterations: 10

llm:
  provider_config_file: "config/llm.yaml"  # 引用LLM配置文件
  active_provider: "openai"                # 当前活跃的提供商

mcp:
  server_config_file: "config/mcp.yaml"    # 引用MCP配置文件
  auto_discover: true                       # 自动发现MCP服务器

logging:
  level: "${LOG_LEVEL:INFO}"
  format: "structured"
  file: "${LOG_FILE:}"

environment:
  env_file: ".env"                          # .env文件路径
  env_prefix: "TINYAGENT_"                 # 环境变量前缀
```

#### 4.2 LLM Provider Configuration

```yaml
# config/llm.yaml - LLM提供商配置
providers:
  openai:
    model: "${OPENAI_MODEL:gpt-4}"
    api_key_env: "OPENAI_API_KEY"
    base_url: "${OPENAI_BASE_URL:https://api.openai.com/v1}"
    max_tokens: 2000
    temperature: 0.7

  openrouter:
    model: "${OPENROUTER_MODEL:anthropic/claude-3.5-sonnet}"
    api_key_env: "OPENROUTER_API_KEY" 
    base_url: "https://openrouter.ai/api/v1"
    max_tokens: 2000
    temperature: 0.7
    extra_headers:
      HTTP-Referer: "${OPENROUTER_REFERER:https://github.com/your-org/tinyagent}"
      X-Title: "${OPENROUTER_TITLE:TinyAgent}"

  local_llm:
    model: "${LOCAL_MODEL:llama2}"
    api_key_env: ""
    base_url: "${LOCAL_LLM_URL:http://localhost:11434}"
    max_tokens: 2000
    temperature: 0.7

# 默认设置 (应用于所有提供商)
defaults:
  timeout: 30
  retry_attempts: 3
  max_tokens: 2000
  temperature: 0.7
```

#### 4.3 MCP Server Configuration

```yaml
# config/mcp.yaml - MCP服务器配置
servers:
  filesystem:
    type: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "${TINYAGENT_ROOT:.}"]
    env: {}
    description: "File system operations"
    enabled: true
    category: "file_operations"

  fetch:
    type: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-fetch"]
    env: {}
    description: "HTTP requests and web content"
    enabled: true
    category: "web_operations"

  sqlite:
    type: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-sqlite", "${TINYAGENT_DB:./data/tinyagent.db}"]
    env: {}
    description: "SQLite database operations"
    enabled: false
    category: "database_operations"

# 服务器分类定义
categories:
  file_operations:
    description: "File system and document operations"
    priority: "high"
  
  web_operations:
    description: "Web requests and content fetching"
    priority: "medium"
    
  database_operations:
    description: "Database queries and operations"
    priority: "low"

# MCP客户端设置
client:
  timeout: 30
  max_retries: 3
  tool_cache_duration: 300
  max_tools_per_server: 50
```

#### 4.4 Environment Variables (.env)

```bash
# .env - 敏感信息和环境特定设置
# LLM API Keys
OPENAI_API_KEY=your-openai-api-key-here
OPENROUTER_API_KEY=your-openrouter-api-key-here

# LLM Configuration
OPENAI_MODEL=gpt-4
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
LOCAL_LLM_URL=http://localhost:11434

# TinyAgent Settings
TINYAGENT_ROOT=C:/work/github/TinyAgent
TINYAGENT_DB=./data/tinyagent.db
LOG_LEVEL=INFO
LOG_FILE=

# OpenRouter Specific
OPENROUTER_REFERER=https://github.com/your-org/tinyagent
OPENROUTER_TITLE=TinyAgent

# Development Settings
TINYAGENT_PROFILE=development
TINYAGENT_DEBUG=false
```

### 5. Configuration Loading Strategy

#### 5.1 ConfigurationManager Enhancement

```python
class ConfigurationManager:
    """Enhanced configuration manager with hierarchical loading"""
    
    def __init__(self, 
                 config_dir: Path = None,
                 profile: str = None,
                 env_file: str = ".env"):
        self.config_dir = config_dir or self._find_config_dir()
        self.profile = profile or os.getenv("TINYAGENT_PROFILE", "development")
        self.env_file = env_file
        
        # Load .env file first
        self._load_dotenv()
    
    def _load_dotenv(self):
        """Load environment variables from .env file"""
        from dotenv import load_dotenv
        env_path = self.config_dir.parent / self.env_file
        if env_path.exists():
            load_dotenv(env_path)
    
    def load_configuration(self) -> TinyAgentConfig:
        """Load configuration with proper hierarchy"""
        # 1. Load defaults
        config = self._load_defaults()
        
        # 2. Load profile (if specified)
        if self.profile:
            profile_config = self._load_profile(self.profile)
            config = self._merge_configs(config, profile_config)
        
        # 3. Load user config
        user_config = self._load_user_config()
        config = self._merge_configs(config, user_config)
        
        # 4. Apply environment variables
        config = self._apply_env_substitution(config)
        
        return self._parse_config(config)
```

#### 5.2 Profile System

```yaml
# profiles/development.yaml - 开发环境配置
agent:
  name: "TinyAgent-Dev"
  max_iterations: 5

llm:
  active_provider: "openai"

mcp:
  servers:
    filesystem:
      enabled: true
    fetch:
      enabled: true
    sqlite:
      enabled: false

logging:
  level: "DEBUG"
```

```yaml
# profiles/production.yaml - 生产环境配置
agent:
  name: "TinyAgent-Prod"
  max_iterations: 20

llm:
  active_provider: "openrouter"

mcp:
  servers:
    filesystem:
      enabled: true
    fetch:
      enabled: true
    sqlite:
      enabled: true

logging:
  level: "INFO"
  file: "logs/tinyagent.log"
```

### 6. Usage Examples

#### 6.1 Simple Usage (Environment Variables Only)

```bash
# Set environment variables
export OPENAI_API_KEY="your-key"
export TINYAGENT_PROFILE="development"

# Run with defaults
python -m tinyagent status
```

#### 6.2 Custom Configuration

```bash
# Use specific profile
python -m tinyagent --profile production status

# Use custom config directory
python -m tinyagent --config-dir ./custom-configs status
```

#### 6.3 Configuration Override Chain

```bash
# Override chain: defaults → profile → user-config → env-vars
OPENAI_MODEL=gpt-3.5-turbo python -m tinyagent run "Hello"
```

### 7. Implementation Benefits

#### 7.1 Advantages
1. **Clear Separation**: Defaults, profiles, user configs, and env vars are clearly separated
2. **Easy Override**: Simple hierarchy makes it easy to override any setting
3. **Environment Agnostic**: Same codebase works across dev/staging/prod
4. **Secure**: Sensitive data stays in .env files
5. **Flexible**: Users can choose minimal or detailed configuration
6. **Backward Compatible**: Existing configs can be migrated gradually

#### 7.2 Migration Strategy
1. **Phase 1**: Implement new ConfigurationManager with backward compatibility
2. **Phase 2**: Create new config structure alongside old ones
3. **Phase 3**: Migrate existing configs to new structure
4. **Phase 4**: Deprecate old configuration methods

### 8. Configuration Validation

```python
class ConfigValidator:
    """Validates configuration completeness and correctness"""
    
    def validate(self, config: TinyAgentConfig) -> ValidationResult:
        errors = []
        warnings = []
        
        # Validate LLM configuration
        if not self._check_api_key(config.llm):
            errors.append("LLM API key not found or invalid")
        
        # Validate MCP servers
        for server in config.mcp.servers:
            if server.enabled and not self._check_server_availability(server):
                warnings.append(f"MCP server {server.name} may not be available")
        
        return ValidationResult(errors=errors, warnings=warnings)
```

### 9. Next Steps for Implementation

1. **Install python-dotenv**: Add to requirements.txt
2. **Enhance ConfigurationManager**: Implement hierarchical loading
3. **Create Default Configs**: Move current configs to defaults/
4. **Add Profile System**: Create development/production profiles  
5. **Update CLI**: Add --profile and --config-dir options
6. **Add Validation**: Implement configuration validation
7. **Migration Guide**: Create guide for migrating existing configs

This design provides a clean, hierarchical, and flexible configuration system that scales from simple usage to complex enterprise deployments.

---

*This document captures the system architecture and design patterns used in the project.* 