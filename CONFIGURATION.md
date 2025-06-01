# TinyAgent 配置指南

## 🎯 新配置架构 - 资源定义与引用分离

### 核心原则：DRY (Don't Repeat Yourself)
- **资源定义**：在 `defaults/` 中定义所有可用资源（LLM providers, MCP servers）
- **配置引用**：在 `profiles/` 中只引用需要的资源，不重复定义

### 配置文件结构
```
tinyagent/configs/
├── defaults/                    # 📚 资源定义（只读）
│   ├── llm_providers.yaml      # 定义所有可用的LLM提供商
│   └── mcp_servers.yaml        # 定义所有可用的MCP服务器
├── profiles/                    # 🔧 配置文件（引用资源）
│   ├── development.yaml        # 开发环境：引用需要的资源
│   ├── production.yaml         # 生产环境：引用需要的资源
│   └── openrouter.yaml         # OpenRouter示例
├── config/                      # 👤 用户自定义（可选）
└── env.template                # 🔑 环境变量模板
```

## 🔧 **您只需要关注一个文件：`.env`**

### 1. **复制环境变量模板**
```bash
cp tinyagent/configs/env.template .env
```

### 2. **编辑 `.env` 文件**
```bash
# 必需：OpenRouter API密钥
OPENROUTER_API_KEY=your-openrouter-api-key-here

# 可选：自定义日志文件路径
LOG_FILE=./logs/custom.log

# 可选：自定义项目根目录
TINYAGENT_ROOT=/path/to/your/project
```

## 📋 **Logging 和 Environment 联动机制详解**

### 1. **Logging Section 与 .env 联动**

**在 Profile 中定义：**
```yaml
# profiles/development.yaml
logging:
  level: "DEBUG"                              # 固定值
  format: "structured"                        # 固定值  
  file: "${LOG_FILE:./logs/development.log}"  # 🔗 环境变量替换
```

**联动机制：**
- `${LOG_FILE:./logs/development.log}` 语法表示：
  - 优先使用 `.env` 文件中的 `LOG_FILE` 变量
  - 如果 `LOG_FILE` 未设置，使用默认值 `./logs/development.log`
- 在 `.env` 中设置：`LOG_FILE=/var/log/tinyagent/custom.log`
- 最终日志文件路径：`/var/log/tinyagent/custom.log`

### 2. **Environment Section 与 .env 联动**

**在 Profile 中定义：**
```yaml
# profiles/development.yaml
environment:
  env_file: ".env"                    # 🔗 指定环境变量文件
  env_prefix: "TINYAGENT_"           # 🔗 环境变量前缀
```

**联动机制：**
- `env_file: ".env"` 告诉系统从哪个文件加载环境变量
- `env_prefix: "TINYAGENT_"` 表示所有以 `TINYAGENT_` 开头的变量都会被加载
- 例如：`.env` 中的 `TINYAGENT_DEBUG=true` 会被自动加载

### 3. **MCP Servers 与 .env 联动**

**在 defaults/mcp_servers.yaml 中定义：**
```yaml
servers:
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "${TINYAGENT_ROOT:.}"]
    #                                                        ↑ 环境变量替换
```

**联动机制：**
- `${TINYAGENT_ROOT:.}` 表示：
  - 优先使用 `.env` 中的 `TINYAGENT_ROOT` 变量
  - 如果未设置，使用当前目录 `.`
- 在 `.env` 中设置：`TINYAGENT_ROOT=/path/to/project`
- 最终命令：`npx -y @modelcontextprotocol/server-filesystem /path/to/project`

### 4. **LLM Providers 与 .env 联动**

**在 defaults/llm_providers.yaml 中定义：**
```yaml
providers:
  openrouter:
    api_key_env: "OPENROUTER_API_KEY"  # 🔗 指定环境变量名
    model: "gpt-3.5-turbo"
    base_url: "https://openrouter.ai/api/v1"
```

**联动机制：**
- `api_key_env: "OPENROUTER_API_KEY"` 告诉系统从 `.env` 文件中读取这个变量
- 系统自动从 `.env` 中获取 `OPENROUTER_API_KEY` 的值
- 无需在配置文件中硬编码敏感信息

## 🔄 **环境变量替换语法**

TinyAgent 支持以下环境变量替换语法：

| 语法 | 说明 | 示例 |
|------|------|------|
| `${VAR}` | 必需变量，如果未设置会报错 | `${OPENROUTER_API_KEY}` |
| `${VAR:default}` | 可选变量，未设置时使用默认值 | `${LOG_FILE:./logs/app.log}` |
| `${VAR:}` | 可选变量，未设置时使用空字符串 | `${OPTIONAL_PARAM:}` |

## 🎯 **实际使用示例**

### 开发环境配置
```bash
# .env 文件
OPENROUTER_API_KEY=sk-or-v1-your-key-here
LOG_FILE=./logs/dev.log
TINYAGENT_ROOT=.
TINYAGENT_DEBUG=true
```

### 生产环境配置
```bash
# .env 文件
OPENROUTER_API_KEY=sk-or-v1-your-production-key
LOG_FILE=/var/log/tinyagent/production.log
TINYAGENT_ROOT=/opt/tinyagent
TINYAGENT_DEBUG=false
```

## 🚀 **快速开始**

1. **复制模板**：`cp tinyagent/configs/env.template .env`
2. **设置API密钥**：编辑 `.env`，添加 `OPENROUTER_API_KEY=your-key`
3. **运行**：`python -m tinyagent run "hello"`

就这么简单！所有其他配置都有合理的默认值。

## 📋 配置优先级与联动

```