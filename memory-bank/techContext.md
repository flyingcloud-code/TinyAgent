# Technical Context: TinyAgent
*Version: 1.0*
*Created: 2025-05-31*
*Last Updated: 2025-05-31*

## Technology Stack
- Backend: Python (3.9+ assumed)
- Core Framework: `openai-agents-python` SDK
- MCP Integration: `openai-agents-mcp` extension (or custom equivalent)
- LLM Interaction: Abstracted module, supporting providers like OpenAI, LiteLLM (for local models)
- Configuration: YAML files (e.g., `mcp_agent.config.yaml`, `llm_config.yaml`), Text files for prompts (e.g., in `prompts/` directory)

## Development Environment Setup
- Python Environment: Version 3.9+ (to be confirmed, assumed for now).
- Required Libraries: `openai-agents-python`, `openai-agents-mcp`. Potentially others as development progresses.
- `npx`: Required if using standard JavaScript-based MCP servers (e.g., `server-fetch`, `server-filesystem`).
- API Keys: Users will need API keys for their chosen LLM providers, managed via environment variables or a secure secrets mechanism.

## Dependencies
- `openai-agents-python`: Core SDK for agent framework.
- `openai-agents-mcp` (or equivalent): For MCP tool integration and management.
- Python: 3.9+ (assumed).
- `npx` (conditional): For running JavaScript-based MCP servers.
- LLM Provider SDKs (indirectly via LiteLLM or direct integration): As per chosen LLM.

## Technical Constraints
- Initial version is a Command-Line Interface (CLI) application.
- Extensibility for "Reflect" capabilities is a design consideration.
- Support for Stdio-based MCP servers is a must.
- Design for future HTTP/SSE or Streamable HTTP MCP transport.
- Secure management of sensitive data like API keys (not hardcoded).
- Users are responsible for the security implications of the MCP tools they configure.
- Initial development prioritizes functionality over extensive optimization.

## Build and Deployment
- Build Process: Standard Python packaging and dependency management (e.g., using `pip` with `requirements.txt` or `pyproject.toml`).
- Deployment Procedure: Initially, deployment will likely involve setting up the Python environment and running the CLI application. More formal deployment procedures can be defined later.
- CI/CD: To be defined. (Not specified in PRD for initial version).

## Testing Approach
- Unit Testing: To be defined.
- Integration Testing: To be defined.
- E2E Testing: To be defined.
(The PRD mentions these categories but does not detail the approach for the initial version).

---

*This document describes the technologies used in the project and how they're configured.* 