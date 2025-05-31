# System Patterns: TinyAgent
*Version: 1.0*
*Created: PLACEHOLDER_DATE*
*Last Updated: PLACEHOLDER_DATE*

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

---

*This document captures the system architecture and design patterns used in the project.* 