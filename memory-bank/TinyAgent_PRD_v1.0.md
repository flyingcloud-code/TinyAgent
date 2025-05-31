# Product Requirements Document: TinyAgent
*Version: 1.0*
*Status: Draft*
*Created: 2025-01-29 (Based on LLM-assisted research)*
*Last Updated: 2025-01-29*
*Owner: [USER_NAME]*

## 1. Introduction

### 1.1. Purpose
This document outlines the product requirements for TinyAgent, a general-purpose, multi-step agent framework. TinyAgent is designed to be extensible via Model Context Protocol (MCP) tools and will initially focus on assisting with user needs analysis and generating various forms of documentation within a corporate environment. It aims to provide a flexible and powerful platform for automating complex, multi-step tasks.

### 1.2. Project Vision
To create an intelligent agent capable of understanding user needs, planning complex tasks, executing them using a variety of internal and external tools (via MCP), and iteratively refining its approach through a ReAct+Reflect loop. TinyAgent will serve as a versatile assistant for various knowledge work and documentation-heavy processes.

### 1.3. Scope
The initial version of TinyAgent will be a Python-based command-line application. Key deliverables include the core agent framework, MCP integration with configuration-driven tool management, configurable LLM providers and prompts, and a demonstration of its capabilities through a PRD generation task. Future versions may include a GUI and more advanced workflow orchestration. (Refer to `memory-bank/projectbrief.md` for detailed In/Out of Scope items).

### 1.4. Target Audience
Internal teams within the company requiring assistance with:
*   Requirements gathering and analysis.
*   Generation of standardized documents (PRDs, design docs, etc.).
*   Automation of multi-step information processing tasks.

### 1.5. Definitions, Acronyms, and Abbreviations
*   **Agent:** An autonomous or semi-autonomous system that perceives its environment and takes actions to achieve goals.
*   **CLI:** Command-Line Interface.
*   **CR:** Core Requirement.
*   **LLM:** Large Language Model.
*   **MCP:** Model Context Protocol. An open standard for LLMs to interact with tools and data sources.
*   **PRD:** Product Requirements Document.
*   **ReAct:** Reasoning and Acting. A paradigm for LLM agents that combines reasoning traces and action execution.
*   **Reflect:** A process where the agent reviews its past actions and outcomes to improve future performance.
*   **SDK:** Software Development Kit.
*   **SC:** Success Criterion.
*   **SSE:** Server-Sent Events.
*   **Stdio:** Standard Input/Output.

## 2. Goals and Objectives
*   Develop a robust and extensible agent framework.
*   Enable seamless integration of diverse tools via MCP.
*   Automate and streamline document generation processes.
*   Provide a flexible platform for various multi-step tasks.
*   Ensure configurability for LLMs, prompts, and tools.

## 3. User Requirements & Stories

*   **As a Project Manager, I want TinyAgent to analyze a list of user feature requests and draft an initial PRD, so that I can save time on initial document creation.**
    *   *Acceptance Criteria:* Agent ingests feature requests, identifies key sections for a PRD, and populates a PRD template with relevant information.
*   **As a Developer, I want to configure TinyAgent to use different MCP tools (e.g., a file reader, a code analyzer) through a simple configuration file, so that I can easily extend its capabilities without changing its core code.**
    *   *Acceptance Criteria:* New stdio-based MCP tools can be added via an `mcp_agent.config.yaml` (or similar) and become usable by the agent.
*   **As an AI Engineer, I want to easily switch the LLM provider TinyAgent uses (e.g., from OpenAI GPT-4 to a local model via LiteLLM) through a configuration file, for experimentation and cost management.**
    *   *Acceptance Criteria:* LLM provider can be changed in a config file, and the agent functions correctly with the new provider.
*   **As a System Administrator, I want to define specific prompts and instructions for TinyAgent through external files, so that its behavior can be customized for different tasks without redeploying the agent.**
    *   *Acceptance Criteria:* Agent's core prompts/instructions can be loaded from external configuration files.
*   **As a User, I want to interact with TinyAgent via a command-line interface to initiate tasks and receive outputs.**
    *   *Acceptance Criteria:* Agent provides a functional CLI for basic operations.

## 4. System Architecture and Design Considerations

### 4.1. Core Agent Engine
*   **Framework:** Built using Python and the `openai-agents-python` SDK.
*   **MCP Integration:** Leverage the `openai-agents-mcp` extension (by LastMile AI) for configuration-driven MCP server management, or implement a similar custom solution if necessary. This will manage connections to MCP servers defined in `mcp_agent.config.yaml`.
    *   The agent (acting as an MCP client) will use tools exposed by these MCP servers.
*   **Agent Loop:** Implement a ReAct (Reasoning and Acting) loop.
    *   The `Runner.run()` from `openai-agents-python` provides the basic loop.
    *   Reflection capabilities will be an area of ongoing research and iterative development, aiming to allow the agent to learn from its actions.
*   **Modularity:**
    *   **LLM Provider Module:** Abstract LLM interactions to allow different providers. Configuration will specify the active provider and its settings (API keys, model names).
    *   **Prompt Management Module:** Load agent instructions and task-specific prompts from external configuration files.
    *   **MCP Configuration Module:** Manage the `mcp_agent.config.yaml` (or equivalent) for defining and categorizing available MCP servers/tools.
    *   **Workflow Management Module (Future):** Placeholder for future advanced workflow orchestration logic. Initially, workflows will be simpler sequences managed by the agent's reasoning or basic handoffs.

### 4.2. MCP Tool Ecosystem
*   **Tool Definition:** MCP tools will be defined by external MCP servers. These servers can be:
    *   **Stdio-based:** For local tools (e.g., scripts for file access, simple data processing). TinyAgent will manage these as subprocesses based on the `mcp_agent.config.yaml`.
    *   **HTTP/SSE or Streamable HTTP-based:** For remote tools or services (future consideration for more complex tools).
*   **Tool Categorization:** The MCP server configuration (`mcp_agent.config.yaml`) should ideally support metadata for categorizing tools (e.g., `type: file_tool`, `type: doc_gen_tool`). The agent can use this for better tool selection or display.

### 4.3. Configuration Files
*   **`mcp_agent.config.yaml` (or similar):**
    *   Defines named MCP servers.
    *   For each server, specifies connection details (e.g., command and args for stdio, URL for HTTP).
    *   May include metadata for tool categorization.
*   **`llm_config.yaml` (or similar):**
    *   Defines available LLM providers (e.g., "openai", "litellm_ollama").
    *   Specifies active provider.
    *   Contains API keys (via env vars or a secrets file), model names, and other provider-specific settings.
*   **`prompts/` directory (or similar):**
    *   Contains files with prompt templates or full prompts for different agent roles or tasks (e.g., `prd_generator_prompt.txt`, `code_analyzer_prompt.txt`).
    *   A main agent configuration might specify which prompt file to use for a given task.

### 4.4. Data Flow (Example: PRD Generation)
1.  User initiates PRD generation via CLI, providing input (e.g., feature list).
2.  TinyAgent (using its configured LLM and PRD generation prompts) analyzes the input.
3.  Agent plans steps: e.g., "identify PRD sections," "draft intro," "list requirements."
4.  Agent executes steps:
    *   May call an MCP tool (e.g., `file_reader_tool` to get a PRD template, or `text_formatter_tool`).
    *   Sends requests to the LLM for content generation based on prompts and context.
5.  Agent receives tool outputs and LLM responses.
6.  Agent assembles the PRD content.
7.  (Future Reflect Step): Agent reviews the generated PRD against criteria, potentially refining it.
8.  Agent outputs the final PRD to the user (e.g., prints to console or saves to a file via an MCP tool).

### 4.5. Command-Line Interface (CLI)
*   Initial interaction point.
*   Commands for:
    *   Initiating tasks (e.g., `tinyagent generate prd --input features.txt --output prd_draft.md`).
    *   Listing available MCP tools/categories (optional).
    *   Checking agent status (optional).

## 5. Functional Requirements

### 5.1. Agent Core Functionality
| ID    | Requirement                                                                 | Priority |
|-------|-----------------------------------------------------------------------------|----------|
| FR1.1 | Agent shall be able to execute a sequence of thought, action, observation steps (ReAct loop). | Must     |
| FR1.2 | Agent shall support integration of tools via the `openai-agents-python` SDK.   | Must     |
| FR1.3 | Agent shall manage conversation history for contextual understanding.          | Must     |
| FR1.4 | Agent shall provide tracing capabilities for debugging (leveraging SDK's tracing). | Must     |
| FR1.5 | Agent framework shall be extensible for future "Reflect" capabilities.        | Should   |

### 5.2. MCP Tool Integration
| ID    | Requirement                                                                 | Priority |
|-------|-----------------------------------------------------------------------------|----------|
| FR2.1 | Agent shall connect to and utilize tools from MCP servers defined in an external configuration file (`mcp_agent.config.yaml` or similar). | Must     |
| FR2.2 | Agent shall support MCP servers using Stdio transport.                         | Must     |
| FR2.3 | Agent shall be designed to support MCP servers using HTTP/SSE or Streamable HTTP transport. | Should   |
| FR2.4 | The MCP configuration shall allow defining how stdio servers are launched (command, args). | Must     |
| FR2.5 | Agent should be able to list available tools from configured MCP servers (for internal selection or user visibility). | Should   |
| FR2.6 | The MCP configuration should allow for basic categorization/metadata for tools. | Nice to have |

### 5.3. LLM Provider Management
| ID    | Requirement                                                                   | Priority |
|-------|-------------------------------------------------------------------------------|----------|
| FR3.1 | Agent shall use an LLM provider specified in an external configuration file.  | Must     |
| FR3.2 | The configuration shall support multiple LLM provider profiles (e.g., OpenAI, LiteLLM for local models). | Must     |
| FR3.3 | LLM API keys and sensitive credentials shall be managed securely (e.g., via environment variables or a dedicated secrets file, not directly in the main config). | Must     |

### 5.4. Prompt Management
| ID    | Requirement                                                                 | Priority |
|-------|-----------------------------------------------------------------------------|----------|
| FR4.1 | Agent's primary instructions and task-specific prompts shall be loadable from external configuration files. | Must     |
| FR4.2 | The system should support a structured way to organize and select prompts (e.g., a directory of prompt files). | Should   |

### 5.5. Document Generation
| ID    | Requirement                                                                 | Priority |
|-------|-----------------------------------------------------------------------------|----------|
| FR5.1 | Agent shall be capable of generating a Product Requirements Document (PRD) based on user input and predefined templates/prompts. | Must     |
| FR5.2 | Agent shall be designed to support generation of other document types (product design, architecture, etc.) through new prompts and potentially new MCP tools. | Should   |

### 5.6. CLI
| ID    | Requirement                                                                 | Priority |
|-------|-----------------------------------------------------------------------------|----------|
| FR6.1 | Agent shall provide a CLI for users to submit tasks.                       | Must     |
| FR6.2 | CLI shall accept input parameters for tasks (e.g., input file paths, output destinations). | Must     |
| FR6.3 | CLI shall display task progress/output or indicate where output is saved.    | Must     |

## 6. Non-Functional Requirements

### 6.1. Usability
| ID    | Requirement                                                                 | Priority |
|-------|-----------------------------------------------------------------------------|----------|
| NFR1.1| Configuration files (MCP, LLM, Prompts) shall be human-readable and easy to modify (e.g., YAML, plain text). | Must     |
| NFR1.2| CLI shall provide clear feedback to the user.                               | Must     |
| NFR1.3| Error messages shall be informative.                                        | Must     |

### 6.2. Extensibility
| ID    | Requirement                                                                 | Priority |
|-------|-----------------------------------------------------------------------------|----------|
| NFR2.1| New MCP tools (servers) shall be addable primarily through configuration changes without requiring core agent code modification. | Must     |
| NFR2.2| Adding support for new LLM providers should primarily involve configuration and potentially a new provider-specific interface implementation if not covered by LiteLLM. | Must     |
| NFR2.3| The prompt system shall allow easy addition or modification of prompts.       | Must     |

### 6.3. Performance
| ID    | Requirement                                                                 | Priority |
|-------|-----------------------------------------------------------------------------|----------|
| NFR3.1| Agent response time for simple interactions should be reasonable (acknowledging LLM processing time). | Should   |
| NFR3.2| MCP tool communication overhead should be minimized (e.g., caching tool lists where appropriate, as supported by SDKs). | Should   |

### 6.4. Maintainability
| ID    | Requirement                                                                 | Priority |
|-------|-----------------------------------------------------------------------------|----------|
| NFR4.1| Code shall be well-documented, especially interfaces and configuration points. | Must     |
| NFR4.2| The codebase shall be organized into logical modules.                         | Must     |

### 6.5. Security
| ID    | Requirement                                                                 | Priority |
|-------|-----------------------------------------------------------------------------|----------|
| NFR5.1| Sensitive data like API keys must not be hardcoded and should be managed via environment variables or a secure secrets mechanism. | Must     |
| NFR5.2| When using stdio MCP tools that execute commands, appropriate caution and warnings should be in place (users must understand the tools they configure). | Must     |

## 7. Future Considerations / Roadmap
*   **Advanced Workflow Orchestration:** A dedicated module for defining and managing complex, branching workflows involving multiple agents or long-running tasks.
*   **Graphical User Interface (GUI):** A web-based or desktop GUI for easier interaction, task monitoring, and results visualization.
*   **Sophisticated Reflection Mechanisms:** Advanced algorithms for the agent to analyze its performance, learn from mistakes, and improve its strategies over time.
*   **Expanded MCP Tool Library:** Development or integration of a wider range of MCP tools for various domains.
*   **Collaborative Features:** Allowing multiple users to interact with or contribute to an agent's task.
*   **Persistent State Management:** More robust mechanisms for saving and resuming agent tasks.
*   **Interactive Feedback Loop:** Allowing users to provide feedback at intermediate steps of a task to guide the agent.

## 8. Assumptions and Dependencies
*   Access to Python environment (version to be specified, e.g., 3.9+).
*   Access to and ability to install `openai-agents-python` and `openai-agents-mcp` (or develop equivalent functionality).
*   Access to `npx` if using standard JavaScript-based MCP servers like `server-fetch` or `server-filesystem`.
*   Users will have API keys for their chosen LLM providers.
*   Users are responsible for the security implications of the MCP tools they configure TinyAgent to use.
*   Initial development will prioritize functionality over extensive optimization.

## 9. Risks and Mitigation
| Risk                                      | Likelihood | Impact | Mitigation                                                                 |
|-------------------------------------------|------------|--------|----------------------------------------------------------------------------|
| Complexity of ReAct+Reflect loop implementation | Medium     | High   | Start with basic ReAct; iterate on Reflect. Leverage SDK capabilities.   |
| MCP standard evolves or SDKs have limitations | Low        | Medium | Adhere to core MCP principles. Abstract MCP interactions. Monitor SDK updates. |
| Securing MCP tool execution               | Medium     | High   | Clear documentation on tool risks. Encourage running tools in sandboxed environments. TinyAgent itself won't provide sandboxing initially. |
| LLM provider API changes                  | Medium     | Medium | Use an abstraction layer (like LiteLLM or a custom one) for LLM calls.     |
| Managing diverse configurations effectively | Medium     | Medium | Adopt clear, well-documented configuration schemas. Provide examples.      |

## 10. Open Issues / Questions
*   What is the preferred method for secrets management for LLM API keys and MCP server credentials (e.g., dedicated `.env` file, integration with a specific secrets manager)? (Assume `.env` / environment variables for now).
*   Specific categories needed for MCP tools initially? (Start with generic, add as specific tools are identified).
*   What level of detail is expected for the "Reflect" part of the loop in the initial versions? (Initial focus on research and basic design).
*   Target Python version? (Assume 3.9+ for now).

---
*This PRD is a living document and will be updated as the project progresses.* 