# Project Brief: TinyAgent
*Version: 1.0*
*Created: 2025-05-31*
*Last Updated: 2025-05-31*

## Project Overview
TinyAgent is a general-purpose, multi-step agent framework designed to be extensible via Model Context Protocol (MCP) tools. It will initially focus on assisting with user needs analysis and generating various forms of documentation within a corporate environment. The project aims to provide a flexible and powerful platform for automating complex, multi-step tasks, creating an intelligent agent capable of understanding user needs, planning complex tasks, executing them using a variety of tools (via MCP), and iteratively refining its approach.

## Core Requirements
- Agent shall be able to execute a sequence of thought, action, observation steps (ReAct loop).
- Agent shall support integration of tools via the `openai-agents-python` SDK.
- Agent shall manage conversation history for contextual understanding.
- Agent shall connect to and utilize tools from MCP servers defined in an external configuration file.
- Agent shall support MCP servers using Stdio transport.
- Agent shall use an LLM provider specified in an external configuration file.
- Agent's primary instructions and task-specific prompts shall be loadable from external configuration files.
- Agent shall be capable of generating a Product Requirements Document (PRD).
- Agent shall provide a CLI for users to submit tasks.

## Success Criteria
- Agent ingests feature requests, identifies key sections for a PRD, and populates a PRD template.
- New stdio-based MCP tools can be added via configuration and become usable.
- LLM provider can be changed in a config file, and the agent functions correctly.
- Agent's core prompts/instructions can be loaded from external configuration files.
- Agent provides a functional CLI for basic operations.

## Scope
### In Scope
- Python-based command-line application.
- Core agent framework.
- MCP integration with configuration-driven tool management.
- Configurable LLM providers and prompts.
- Demonstration of capabilities through PRD generation task.
- Extensibility for future "Reflect" capabilities.
- Support for stdio-based MCP servers.
- Design for future support of HTTP/SSE or Streamable HTTP MCP transport.
- Ability to list available tools from configured MCP servers.
- Basic categorization/metadata for MCP tools in configuration.
- Support for multiple LLM provider profiles (e.g., OpenAI, LiteLLM).
- Secure management of LLM API keys (e.g., via environment variables).
- Structured way to organize and select prompts.
- Design to support generation of other document types.
- CLI accepts input parameters and displays/saves output.
- Human-readable configuration files.
- Clear CLI feedback and informative error messages.
- Addable new MCP tools primarily through configuration.
- Adding new LLM providers primarily through configuration/interface implementation.
- Easy addition/modification of prompts.
- Well-documented code, especially interfaces and configuration.
- Logically organized codebase.
- Secure management of sensitive data (API keys).
- Warnings for stdio MCP tool execution risks.

### Out of Scope
- Graphical User Interface (GUI) in the initial version.
- Advanced workflow orchestration in the initial version.
- Sophisticated "Reflect" mechanisms in the initial version (focus on research and basic design).
- Sandboxing for MCP tool execution (users responsible for configured tools).
- Extensive optimization in the initial version (priority on functionality).

## Timeline
- To be defined. (The PRD does not specify a timeline)

## Stakeholders
- Project Manager
- Developer
- AI Engineer
- System Administrator
- User (Internal teams)

---

*This document serves as the foundation for the project and informs all other memory files.* 