# TinyAgent 配置指南

## 🎯 快速开始 - 您只需要关注这两个文件

### 1. `.env` 文件 - 存放您的API密钥（最重要）

```bash
# 复制模板到根目录
cp tinyagent/configs/env.template .env

# 编辑 .env 文件，添加您的OpenRouter API密钥
OPENROUTER_API_KEY=your-openrouter-api-key-here
```

**获取OpenRouter API密钥：**
1. 访问 [OpenRouter.ai](https://openrouter.ai/)
2. 注册账户
3. 在dashboard中获取API密钥

### 2. `tinyagent/configs/defaults/agent.yaml` - 更改默认LLM提供商（可选）

当前默认设置：
```yaml
llm:
  active_provider: "openrouter"  # 默认使用OpenRouter
```

如果您想改为其他提供商，修改这一行：
```yaml
llm:
  active_provider: "openai"      # 改为OpenAI
  # active_provider: "local_llm"  # 或者本地LLM
```

## 🔧 配置优先级（了解即可）

TinyAgent使用分层配置系统，按以下优先级加载：

1. **`.env` 文件** - 🥇 最高优先级（API密钥等敏感信息）
2. **用户配置** (`tinyagent/configs/config/*.yaml`) - 🥈 高优先级
3. **Profile配置** (`tinyagent/configs/profiles/*.yaml`) - 🥉 中等优先级
4. **默认配置** (`tinyagent/configs/defaults/*.yaml`) - 🎖️ 最低优先级

## 📋 可用的LLM提供商

- **`openrouter`** - 支持多种模型（Claude, GPT-4等）👑 推荐
- **`openai`** - OpenAI官方API
- **`local_llm`** - 本地LLM（如Ollama）
- **`azure`** - Azure OpenAI

## 🚀 使用示例

```bash
# 使用默认配置（OpenRouter）
python -m tinyagent status

# 使用特定profile
python -m tinyagent --profile production status

# 查看所有可用profiles
python -m tinyagent list-profiles

# 运行代理
python -m tinyagent run "Hello, can you help me?"
```

## 🔍 故障排除

### API密钥未找到
```
❌ API Key: Not found (OPENROUTER_API_KEY)
```
**解决方案：** 确保在`.env`文件中设置了正确的API密钥

### 想要切换LLM提供商
**解决方案：** 修改`tinyagent/configs/defaults/agent.yaml`中的`active_provider`

### 想要临时使用不同配置
```bash
# 使用环境变量临时覆盖
OPENROUTER_MODEL=anthropic/claude-3-haiku python -m tinyagent run "test"
```

## 📁 配置文件结构

```
TinyAgent/
├── .env                           # 🔑 您的API密钥（必须创建）
├── tinyagent/configs/
│   ├── defaults/
│   │   ├── agent.yaml            # 🎯 默认LLM提供商设置
│   │   ├── llm_providers.yaml    # LLM提供商定义
│   │   └── mcp_servers.yaml      # MCP服务器定义
│   ├── profiles/                 # 预设配置
│   │   ├── development.yaml      # 开发环境
│   │   ├── production.yaml       # 生产环境
│   │   └── openrouter.yaml       # OpenRouter示例
│   ├── config/                   # 您的自定义配置（可选）
│   └── env.template              # 环境变量模板
```

---

**总结：对于大多数用户，您只需要：**
1. 创建`.env`文件并添加`OPENROUTER_API_KEY`
2. 如果想换LLM提供商，修改`defaults/agent.yaml`中的`active_provider`

就这么简单！ 🎉 