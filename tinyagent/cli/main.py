"""
TinyAgent Command Line Interface

This module provides a comprehensive CLI for TinyAgent with support for
running agents, managing MCP servers, and generating various documents.
"""

import click
import asyncio
import logging
import sys
from typing import Optional, Dict, Any
from pathlib import Path
import os

from ..core.config import get_config, set_profile
from ..core.agent import create_agent, AGENTS_AVAILABLE
from ..mcp.manager import MCPServerManager
from ..core.logging import setup_logging, log_user, log_agent, log_technical

# Enhanced logging will be set up by individual commands
# Don't use basic logging.basicConfig anymore

logger = None  # Will be set up when config is loaded

@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--profile', '-p', help='Configuration profile to use (e.g., development, production)')
@click.option('--config-dir', type=click.Path(exists=True), help='Path to configuration directory')
def cli(verbose: bool, profile: Optional[str], config_dir: Optional[str]):
    """TinyAgent - Multi-step agent framework with MCP tool integration."""
    global logger
    
    # Set global configuration options
    if profile:
        set_profile(profile)
    
    # Load configuration and set up enhanced logging
    try:
        config = get_config(profile)
        logger = setup_logging(config.logging)
        
        if verbose:
            # Override to show more technical details in verbose mode
            config.logging.console_level = "INFO"
            logger = setup_logging(config.logging)
        
        log_technical("info", f"TinyAgent CLI started with profile: {profile or 'development'}")
        
    except Exception as e:
        # Fallback to basic logging if enhanced logging fails
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to set up enhanced logging: {e}")

@cli.command()
@click.argument('prompt', required=True)
@click.option('--model', '-m', help='Model to use (e.g., gpt-4, gpt-3.5-turbo)')
@click.option('--instructions', '-i', help='Custom instructions for the agent')
@click.option('--output', '-o', type=click.Path(), help='Save output to file')
@click.option('--api-key', help='OpenAI API key (overrides environment)')
def run(prompt: str, model: Optional[str], instructions: Optional[str], 
        output: Optional[str], api_key: Optional[str]):
    """Run TinyAgent with a prompt."""
    try:
        log_user("Starting TinyAgent...")
        log_user(f"Task: {prompt}")
        
        # Create agent
        log_agent("Initializing agent...")
        agent = create_agent(
            model=model,
            instructions=instructions,
            api_key=api_key
        )
        
        log_agent(f"Using model: {agent.model_name}")
        log_technical("info", f"Agent config: {agent.config.agent.name}")
        
        # Run agent
        log_agent("Processing your request...")
        result = agent.run_sync(prompt)
        
        # Display result
        output_text = str(result.final_output)
        log_user("[OK] Task completed!")
        click.echo("\n" + "="*50)
        click.echo(output_text)
        click.echo("="*50)
        
        # Save to file if requested
        if output:
            Path(output).write_text(output_text, encoding='utf-8')
            log_user(f"[SAVE] Output saved to: {output}")
            
    except Exception as e:
        log_user(f"[ERROR] {e}")
        log_technical("error", f"Full error details: {e}", "tinyagent.cli")
        sys.exit(1)

@cli.command()
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
@click.option('--profile', '-p', help='Show status for specific profile')
def status(verbose: bool, profile: Optional[str]):
    """Show TinyAgent status and configuration."""
    try:
        from ..core.config import get_config_manager
        
        # Get config manager and load configuration
        config_manager = get_config_manager()
        config = config_manager.load_config(profile=profile)
        
        # Show which profile is active
        active_profile = profile or config_manager.profile
        click.echo("[CONFIG] TinyAgent Configuration Status")
        click.echo(f"Active Profile: {active_profile}")
        
        # Show available profiles
        available_profiles = config_manager.get_available_profiles()
        if available_profiles:
            click.echo(f"Available Profiles: {', '.join(available_profiles)}")
        
        click.echo(f"Config Directory: {config_manager.config_dir}")
        click.echo("")
        
        # Agent configuration
        click.echo(f"Agent Name: {config.agent.name}")
        click.echo(f"Max Iterations: {config.agent.max_iterations}")
        click.echo(f"Instructions File: {config.agent.instructions_file}")
        
        # LLM configuration
        click.echo(f"\nLLM Provider: {config.llm.provider}")
        click.echo(f"LLM Model: {config.llm.model}")
        click.echo(f"API Key Env: {config.llm.api_key_env}")
        if config.llm.base_url:
            click.echo(f"Base URL: {config.llm.base_url}")
        
        # Check API key
        api_key = os.getenv(config.llm.api_key_env)
        if api_key:
            click.echo(f"[OK] API Key: Found ({config.llm.api_key_env})")
        else:
            click.echo(f"[ERROR] API Key: Not found ({config.llm.api_key_env})")
        
        # MCP Server status
        click.echo("\n[MCP] MCP Servers:")
        if not config.mcp.enabled:
            click.echo("  MCP is disabled")
        else:
            mcp_manager = MCPServerManager(list(config.mcp.servers.values()))
            
            # Initialize servers to get their status
            try:
                mcp_manager.initialize_servers()
                server_info = mcp_manager.get_server_info()
            except Exception as e:
                click.echo(f"  Error initializing MCP servers: {e}")
                server_info = []
            
            if not server_info:
                click.echo("  No MCP servers configured")
            else:
                for info in server_info:
                    status_icon = "[OK]" if info.status == "created" else "[FAIL]"
                    click.echo(f"  {status_icon} {info.name} ({info.type}) - {info.status}")
                    if verbose:
                        click.echo(f"    Description: {info.config.get('description', 'N/A')}")
                        click.echo(f"    Enabled: {info.config.get('enabled', False)}")
                        if 'category' in info.config:
                            click.echo(f"    Category: {info.config['category']}")
        
        # Check if agents SDK is available
        if AGENTS_AVAILABLE:
            click.echo("\n[OK] OpenAI Agents SDK: Available")
        else:
            click.echo("\n[ERROR] OpenAI Agents SDK: Not available")
        
        # Environment information
        if verbose:
            click.echo(f"\n[ENV] Environment:")
            click.echo(f"Env File: {config.environment.env_file}")
            click.echo(f"Env Prefix: {config.environment.env_prefix}")
            
    except Exception as e:
        click.echo(f"[ERROR] Error getting status: {e}")
        if verbose:
            import traceback
            click.echo(traceback.format_exc())

@cli.command()
def list_profiles():
    """List available configuration profiles."""
    try:
        from ..core.config import get_config_manager
        
        config_manager = get_config_manager()
        profiles = config_manager.get_available_profiles()
        
        click.echo("[PROFILES] Available Configuration Profiles")
        click.echo("=" * 35)
        
        if not profiles:
            click.echo("No configuration profiles found.")
            return
        
        for profile_name in profiles:
            # Try to load profile to get description
            try:
                config = config_manager.load_config(profile=profile_name)
                click.echo(f"[OK] {profile_name}")
                click.echo(f"   Agent: {config.agent.name}")
                click.echo(f"   LLM: {config.llm.provider}/{config.llm.model}")
                click.echo()
            except Exception as e:
                click.echo(f"[ERROR] {profile_name} (error loading: {e})")
        
    except Exception as e:
        click.echo(f"[ERROR] Error listing profiles: {e}", err=True)
        sys.exit(1)

@cli.command()
def list_servers():
    """List configured MCP servers."""
    try:
        config = get_config()
        
        click.echo("[SERVERS] MCP Servers")
        click.echo("=" * 20)
        
        if not config.mcp.servers:
            click.echo("No MCP servers configured.")
            return
        
        for name, server_config in config.mcp.servers.items():
            status_icon = "[OK]" if server_config.enabled else "[OFF]"
            click.echo(f"{status_icon} {name}")
            click.echo(f"   Type: {server_config.type}")
            click.echo(f"   Description: {server_config.description}")
            
            if server_config.type == "stdio":
                click.echo(f"   Command: {server_config.command}")
                if server_config.args:
                    click.echo(f"   Args: {' '.join(server_config.args)}")
            elif server_config.type in ["sse", "http"]:
                click.echo(f"   URL: {server_config.url}")
            
            click.echo()
            
    except Exception as e:
        click.echo(f"[ERROR] Error listing servers: {e}", err=True)
        sys.exit(1)

@cli.group()
def generate():
    """Generate various documents using TinyAgent."""
    pass

@generate.command()
@click.argument('title', required=True)
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--format', '-f', type=click.Choice(['markdown', 'text']), default='markdown', help='Output format')
def prd(title: str, output: Optional[str], format: str):
    """Generate a Product Requirements Document (PRD)."""
    try:
        prompt = f"""
        Create a comprehensive Product Requirements Document (PRD) for: {title}
        
        Please include the following sections:
        1. Executive Summary
        2. Problem Statement
        3. Goals and Objectives
        4. User Stories
        5. Functional Requirements
        6. Non-Functional Requirements
        7. Technical Considerations
        8. Success Metrics
        9. Timeline and Milestones
        10. Risks and Mitigation
        
        Format the output in {format} format with clear headings and structure.
        """
        
        agent = create_agent()
        click.echo(f"[PRD] Generating PRD for: {title}")
        
        result = agent.run_sync(prompt)
        output_text = str(result.final_output)
        
        if output:
            Path(output).write_text(output_text, encoding='utf-8')
            click.echo(f"[SAVE] PRD saved to: {output}")
        else:
            click.echo(output_text)
            
    except Exception as e:
        click.echo(f"[ERROR] Error generating PRD: {e}", err=True)
        sys.exit(1)

@generate.command()
@click.argument('system_name', required=True)
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--format', '-f', type=click.Choice(['markdown', 'text']), default='markdown', help='Output format')
def design(system_name: str, output: Optional[str], format: str):
    """Generate a system design document."""
    try:
        prompt = f"""
        Create a comprehensive system design document for: {system_name}
        
        Please include the following sections:
        1. System Overview
        2. Architecture Diagram (describe in text)
        3. Component Design
        4. Data Flow
        5. API Design
        6. Database Schema
        7. Security Considerations
        8. Scalability and Performance
        9. Deployment Strategy
        10. Monitoring and Logging
        
        Format the output in {format} format with clear headings and detailed explanations.
        """
        
        agent = create_agent()
        click.echo(f"[DESIGN] Generating system design for: {system_name}")
        
        result = agent.run_sync(prompt)
        output_text = str(result.final_output)
        
        if output:
            Path(output).write_text(output_text, encoding='utf-8')
            click.echo(f"[SAVE] Design document saved to: {output}")
        else:
            click.echo(output_text)
            
    except Exception as e:
        click.echo(f"[ERROR] Error generating design: {e}", err=True)
        sys.exit(1)

@generate.command()
@click.argument('topic', required=True)
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--format', '-f', type=click.Choice(['markdown', 'text']), default='markdown', help='Output format')
def analysis(topic: str, output: Optional[str], format: str):
    """Generate an analysis document."""
    try:
        prompt = f"""
        Create a comprehensive analysis document for: {topic}
        
        Please include the following sections:
        1. Executive Summary
        2. Background and Context
        3. Current State Analysis
        4. Key Findings
        5. Opportunities and Challenges
        6. Recommendations
        7. Implementation Plan
        8. Risk Assessment
        9. Success Metrics
        10. Conclusion
        
        Format the output in {format} format with clear headings and data-driven insights.
        """
        
        agent = create_agent()
        click.echo(f"[ANALYSIS] Generating analysis for: {topic}")
        
        result = agent.run_sync(prompt)
        output_text = str(result.final_output)
        
        if output:
            Path(output).write_text(output_text, encoding='utf-8')
            click.echo(f"[SAVE] Analysis saved to: {output}")
        else:
            click.echo(output_text)
            
    except Exception as e:
        click.echo(f"[ERROR] Error generating analysis: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--api-key', help='OpenAI API key (overrides environment)')
def interactive(api_key: Optional[str]):
    """Start an interactive TinyAgent session."""
    try:
        agent = create_agent(api_key=api_key)
        
        click.echo("[INTERACTIVE] TinyAgent Interactive Mode")
        click.echo("Type 'quit', 'exit', or press Ctrl+C to exit")
        click.echo("=" * 40)
        
        while True:
            try:
                prompt = click.prompt("\n[USER] You", type=str)
                
                if prompt.lower() in ['quit', 'exit', 'q']:
                    break
                
                if prompt.strip() == '':
                    continue
                
                click.echo("[AGENT] TinyAgent:", nl=False)
                result = agent.run_sync(prompt)
                click.echo(f" {result.final_output}")
                
            except KeyboardInterrupt:
                break
            except EOFError:
                break
            except Exception as e:
                click.echo(f"[ERROR] Error: {e}", err=True)
        
        click.echo("\n[BYE] Goodbye!")
        
    except Exception as e:
        click.echo(f"[ERROR] Error starting interactive mode: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--server', '-s', help='Test specific server by name')
def test_mcp(server: Optional[str]):
    """Test MCP server connections."""
    try:
        config = get_config()
        enabled_servers = [s for s in config.mcp.servers.values() if s.enabled]
        
        if server:
            # Test specific server
            server_config = config.mcp.servers.get(server)
            if not server_config:
                click.echo(f"[ERROR] Server '{server}' not found in configuration")
                sys.exit(1)
            enabled_servers = [server_config]
        
        if not enabled_servers:
            click.echo("[ERROR] No enabled MCP servers found")
            sys.exit(1)
        
        click.echo("[TEST] Testing MCP Server Connections")
        click.echo("=" * 35)
        
        mcp_manager = MCPServerManager(enabled_servers)
        servers = mcp_manager.initialize_servers()
        
        click.echo(f"\n[OK] Successfully initialized {len(servers)} out of {len(enabled_servers)} servers")
        
        # Show server info
        for info in mcp_manager.get_server_info():
            status_icon = "[OK]" if info.status == "created" else "[FAIL]"
            click.echo(f"{status_icon} {info.name} ({info.type}) - {info.status}")
        
    except Exception as e:
        click.echo(f"[ERROR] Error testing MCP servers: {e}", err=True)
        sys.exit(1)

def main():
    """Main entry point for the CLI."""
    cli()

if __name__ == '__main__':
    main() 