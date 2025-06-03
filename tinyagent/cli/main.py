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
import uuid
from datetime import datetime

from ..core.config import get_config, set_profile
from ..core.agent import create_agent, AGENTS_AVAILABLE
from ..mcp.manager import EnhancedMCPServerManager, get_mcp_manager
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
@click.option('--max-turns', type=int, default=25, help='Maximum turns for agent execution (default: 25)')
def run(prompt: str, model: Optional[str], instructions: Optional[str], 
        output: Optional[str], api_key: Optional[str], max_turns: int):
    """Run TinyAgent with a single task."""
    try:
        # 使用新的run_agent函数，它包含了完整的日志追踪
        result = run_agent(
            task=prompt,
            model=model,
            instructions=instructions,
            api_key=api_key,
            max_turns=max_turns
        )
        
        # 处理输出
        if hasattr(result, 'final_output'):
            output_text = result.final_output
        else:
            output_text = str(result)
        
        if output:
            Path(output).write_text(output_text, encoding='utf-8')
            log_user(f"[SAVE] Output saved to: {output}")
        else:
            # 输出已经在run_agent中显示了，这里不需要重复显示
            pass
            
    except Exception as e:
        log_user(f"[ERROR] {str(e)}")
        sys.exit(1)

@cli.command()
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
@click.option('--profile', '-p', help='Show status for specific profile')
@click.option('--tools', is_flag=True, help='Show detailed MCP tools status')
def status(verbose: bool, profile: Optional[str], tools: bool):
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
        
        # Show intelligent mode status if available
        if hasattr(config.agent, 'intelligent_mode'):
            click.echo(f"Intelligent Mode: {'Enabled' if config.agent.intelligent_mode else 'Disabled'}")
        
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
            mcp_manager = get_mcp_manager()
            
            if tools:
                # Show detailed tools status with caching information
                click.echo("  🔍 Analyzing MCP tools and cache status...")
                try:
                    import asyncio
                    server_tools = asyncio.run(mcp_manager.initialize_with_caching())
                    
                    # Show overall statistics
                    total_servers = len(config.mcp.servers)
                    active_servers = len(server_tools)
                    total_tools = sum(len(tools) for tools in server_tools.values())
                    
                    click.echo(f"  📊 Overall Status:")
                    click.echo(f"    Configured servers: {total_servers}")
                    click.echo(f"    Active servers: {active_servers}")
                    click.echo(f"    Total available tools: {total_tools}")
                    
                    # Show cache status
                    cache_stats = mcp_manager.get_cache_stats()
                    click.echo(f"  💾 Cache Status:")
                    click.echo(f"    Cache duration: {mcp_manager.tool_cache.cache_duration}s")
                    click.echo(f"    Cached servers: {cache_stats['total_servers_cached']}")
                    click.echo(f"    Cached tools: {cache_stats['total_tools_cached']}")
                    click.echo(f"    Valid caches: {cache_stats['valid_caches']}")
                    click.echo(f"    Cache hit rate: {cache_stats['cache_hit_rate']:.1%}")
                    if cache_stats['cache_file_exists']:
                        click.echo(f"    Cache file size: {cache_stats['cache_file_size']} bytes")
                    
                    # Show per-server status
                    click.echo(f"  🔧 Server Details:")
                    for server_name, server_config in config.mcp.servers.items():
                        server_status = mcp_manager.tool_cache.get_server_status(server_name)
                        tools_for_server = server_tools.get(server_name, [])
                        
                        if server_status:
                            status_icon = "🟢" if server_status.status == "connected" else "🔴"
                            click.echo(f"    {status_icon} {server_name} ({server_config.type})")
                            click.echo(f"      Status: {server_status.status}")
                            click.echo(f"      Tools: {len(tools_for_server)}")
                            
                            if server_status.last_ping_time:
                                click.echo(f"      Last checked: {server_status.last_ping_time.strftime('%H:%M:%S')}")
                            
                            if verbose and tools_for_server:
                                click.echo(f"      Available tools:")
                                for tool in tools_for_server[:5]:  # Show first 5 tools
                                    metrics = tool.performance_metrics
                                    performance_info = ""
                                    if metrics and metrics.total_calls > 0:
                                        performance_info = f" ({metrics.total_calls} calls, {metrics.success_rate:.1%} success)"
                                    click.echo(f"        • {tool.name}{performance_info}")
                                
                                if len(tools_for_server) > 5:
                                    click.echo(f"        ... and {len(tools_for_server) - 5} more")
                        
                        else:
                            click.echo(f"    🔴 {server_name} ({server_config.type}) - Not initialized")
                    
                    # Show performance summary if available
                    perf_summary = mcp_manager.get_performance_summary()
                    global_perf = perf_summary.get('global_performance', {})
                    if global_perf.get('total_calls', 0) > 0:
                        click.echo(f"  📈 Performance Summary:")
                        click.echo(f"    Total tool calls: {global_perf['total_calls']}")
                        click.echo(f"    Success rate: {global_perf['success_rate']:.1%}")
                        click.echo(f"    Avg response time: {global_perf['avg_response_time']:.2f}s")
                    
                except Exception as e:
                    click.echo(f"    ❌ Error analyzing tools: {e}")
                    if verbose:
                        import traceback
                        click.echo(traceback.format_exc())
            
            else:
                # Simple server status
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
@click.option('--show-tools', is_flag=True, help='Show detailed tool information for each server')
@click.option('--verbose', '-v', is_flag=True, help='Show additional server details')
def list_servers(show_tools: bool, verbose: bool):
    """List configured MCP servers with optional tool details."""
    try:
        config = get_config()
        
        click.echo("[MCP] MCP Server Configuration")
        click.echo("=" * 40)
        
        if not config.mcp.enabled:
            click.echo("MCP functionality is disabled")
            return
        
        if not config.mcp.servers:
            click.echo("No MCP servers configured")
            return
        
        # Create enhanced MCP manager with caching - use the factory function
        try:
            mcp_manager = get_mcp_manager()
        except Exception as e:
            click.echo(f"❌ Error creating MCP manager: {e}")
            return
        
        if show_tools:
            # Initialize servers and cache tools for detailed display
            click.echo("🔍 Discovering tools from MCP servers...")
            click.echo()
            
            try:
                # Use async context for tool discovery
                import asyncio
                server_tools = asyncio.run(mcp_manager.initialize_with_caching())
                
                if not server_tools:
                    click.echo("No tools discovered from any server")
                    return
                
                # Display each server with its tools
                total_tools = 0
                for server_name, tools in server_tools.items():
                    server_config = config.mcp.servers[server_name]
                    status = "OK" if tools else "NO_TOOLS"
                    
                    # Deduplicate tools by name to fix duplicate display issue
                    unique_tools = {}
                    for tool in tools:
                        if tool.name not in unique_tools:
                            unique_tools[tool.name] = tool
                    
                    deduped_tools = list(unique_tools.values())
                    total_tools += len(deduped_tools)
                    
                    click.echo(f"[{status}] {server_name}")
                    click.echo(f"   Type: {server_config.type}")
                    click.echo(f"   Description: {server_config.description}")
                    
                    if deduped_tools:
                        click.echo(f"   Tools ({len(deduped_tools)}):")
                        for tool in deduped_tools:
                            click.echo(f"     • {tool.name}")
                            if verbose:
                                click.echo(f"       Description: {tool.description}")
                                click.echo(f"       Category: {tool.category}")
                                if tool.performance_metrics and tool.performance_metrics.total_calls > 0:
                                    metrics = tool.performance_metrics
                                    click.echo(f"       Performance: {metrics.total_calls} calls, "
                                             f"{metrics.success_rate:.1%} success rate, "
                                             f"{metrics.avg_response_time:.2f}s avg time")
                    else:
                        click.echo("   No tools available")
                    
                    click.echo()
                
                # Show cache statistics
                cache_stats = mcp_manager.get_cache_stats()
                click.echo(f"   Total tools: {total_tools}")
                if cache_stats.get('cache_hits', 0) > 0 or cache_stats.get('cache_misses', 0) > 0:
                    hit_rate = cache_stats['cache_hits'] / (cache_stats['cache_hits'] + cache_stats['cache_misses']) * 100
                    click.echo(f"   Cache hit rate: {hit_rate:.1f}%")
                elif 'cache_hit_rate' in cache_stats:
                    click.echo(f"   Cache hit rate: {cache_stats['cache_hit_rate']:.1%}")
                
            except Exception as e:
                click.echo(f"❌ Error discovering tools: {e}")
                if verbose:
                    import traceback
                    click.echo(traceback.format_exc())
        
        else:
            # Simple server list without tool discovery
            try:
                server_info = mcp_manager.get_server_info()
                
                for info in server_info:
                    status = "[OK]" if info.status == "created" else f"[{info.status.upper()}]"
                    click.echo(f"{status} {info.name}")
                    click.echo(f"   Type: {info.type}")
                    click.echo(f"   Description: {info.config.get('description', 'N/A')}")
                    
                    if verbose:
                        click.echo(f"   Enabled: {info.config.get('enabled', False)}")
                        if 'category' in info.config:
                            click.echo(f"   Category: {info.config['category']}")
                        if 'command' in info.config:
                            click.echo(f"   Command: {info.config['command']}")
                    
                    click.echo()
                    
            except Exception as e:
                click.echo(f"❌ Error listing servers: {e}")
        
    except Exception as e:
        click.echo(f"[ERROR] Error listing MCP servers: {e}")

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
        # 设置API key环境变量（如果提供）
        if api_key:
            os.environ['OPENAI_API_KEY'] = api_key
        
        # 使用新的interactive_mode函数，它包含了完整的会话追踪
        interactive_mode()
        
    except Exception as e:
        log_user(f"[ERROR] Error starting interactive mode: {e}")
        log_technical("error", f"Interactive mode startup failed: {e}")
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
        
        mcp_manager = get_mcp_manager()
        servers = mcp_manager.initialize_servers()
        
        click.echo(f"\n[OK] Successfully initialized {len(servers)} out of {len(enabled_servers)} servers")
        
        # Show server info
        for info in mcp_manager.get_server_info():
            status_icon = "[OK]" if info.status == "created" else "[FAIL]"
            click.echo(f"{status_icon} {info.name} ({info.type}) - {info.status}")
        
    except Exception as e:
        click.echo(f"[ERROR] Error testing MCP servers: {e}", err=True)
        sys.exit(1)

def interactive_mode():
    """
    Run TinyAgent in interactive chat mode.
    """
    # 生成唯一的session ID
    session_id = str(uuid.uuid4())[:8]
    session_start_time = datetime.now()
    
    # Session 开始日志
    log_technical("info", f"{'='*60}")
    log_technical("info", f"INTERACTIVE SESSION START - ID: {session_id}")
    log_technical("info", f"Session Start Time: {session_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log_technical("info", f"{'='*60}")
    
    log_user("[INTERACTIVE] TinyAgent Interactive Mode")
    log_user("Type 'quit', 'exit', or press Ctrl+C to exit")
    log_user("=" * 40)
    
    # 创建Agent实例并复用
    try:
        agent = create_agent()
        log_technical("info", f"Agent instance created for session {session_id}")
        log_agent("Agent initialized and ready for interactive use")
        log_user(f"[READY] Using model: {agent.model_name}")
    except Exception as e:
        log_user(f"[ERROR] Failed to initialize TinyAgent: {str(e)}")
        log_technical("error", f"Agent initialization failed: {e}")
        return
    
    message_count = 0
    
    try:
        while True:
            try:
                # 获取用户输入
                user_input = input("\n[USER] You: ").strip()
                
                # 退出命令
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                
                if not user_input:
                    continue
                
                # 消息计数
                message_count += 1
                message_start_time = datetime.now()
                
                # Message 开始日志
                log_technical("info", f"--- MESSAGE {message_count} START ---")
                log_technical("info", f"Session: {session_id} | Message: {message_count}")
                log_technical("info", f"Message Start Time: {message_start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                log_technical("info", f"User Input: {user_input}")
                log_technical("info", f"--- Processing Message {message_count} ---")
                
                # 显示正在思考状态
                print("\n[AGENT] TinyAgent:", end=" ", flush=True)
                
                # 运行Agent - 使用流式输出
                try:
                    response_text = ""
                    for chunk in agent.run_stream_sync(user_input):
                        if chunk and not chunk.startswith("[ERROR]"):
                            print(chunk, end="", flush=True)
                            response_text += chunk
                        elif chunk.startswith("[ERROR]"):
                            print(f"\n{chunk}")
                            response_text = chunk
                            break
                    
                    print()  # 新行
                    
                    # Message 结束日志
                    message_end_time = datetime.now()
                    message_duration = (message_end_time - message_start_time).total_seconds()
                    
                    log_technical("info", f"--- MESSAGE {message_count} END ---")
                    log_technical("info", f"Message End Time: {message_end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                    log_technical("info", f"Message Duration: {message_duration:.3f}s")
                    log_technical("info", f"Response Length: {len(response_text)} characters")
                    log_technical("info", f"Response Preview: {response_text[:100]}...")
                    log_technical("info", f"--- Message {message_count} Complete ---")
                    
                except Exception as e:
                    message_end_time = datetime.now()
                    message_duration = (message_end_time - message_start_time).total_seconds()
                    
                    print(f"\n[ERROR] {str(e)}")
                    log_technical("error", f"Message {message_count} failed after {message_duration:.3f}s: {e}")
                    log_technical("info", f"--- MESSAGE {message_count} END (ERROR) ---")
                    
            except KeyboardInterrupt:
                print("\n[INFO] Session interrupted by user")
                log_technical("info", f"Session {session_id} interrupted by Ctrl+C")
                break
            except EOFError:
                print("\n[INFO] Session ended")
                log_technical("info", f"Session {session_id} ended by EOF")
                break
                
    except Exception as e:
        log_user(f"[ERROR] Interactive session error: {str(e)}")
        log_technical("error", f"Interactive session {session_id} crashed: {e}")
    finally:
        # Session 结束日志
        session_end_time = datetime.now()
        session_duration = (session_end_time - session_start_time).total_seconds()
        
        log_user("[INFO] Goodbye!")
        
        log_technical("info", f"{'='*60}")
        log_technical("info", f"INTERACTIVE SESSION END - ID: {session_id}")
        log_technical("info", f"Session End Time: {session_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        log_technical("info", f"Session Duration: {session_duration:.2f}s")
        log_technical("info", f"Total Messages Processed: {message_count}")
        if message_count > 0:
            log_technical("info", f"Average Message Duration: {session_duration/message_count:.2f}s")
        log_technical("info", f"{'='*60}")

def run_agent(task: str, **kwargs):
    """
    Run TinyAgent with a single task.
    
    Args:
        task: The task for the agent to perform
        **kwargs: Additional arguments for the agent
    """
    # 生成唯一的run ID
    run_id = str(uuid.uuid4())[:8]
    run_start_time = datetime.now()
    
    # Run 开始日志
    log_technical("info", f"{'='*50}")
    log_technical("info", f"SINGLE RUN START - ID: {run_id}")
    log_technical("info", f"Run Start Time: {run_start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
    log_technical("info", f"Task: {task}")
    log_technical("info", f"{'='*50}")
    
    log_user("Starting TinyAgent...")
    log_user(f"Task: {task}")
    log_agent("Initializing agent...")
    
    try:
        # 创建Agent
        agent = create_agent()
        log_agent(f"Using model: {agent.model_name}")
        log_technical("info", f"Agent config: {agent.config.agent.name}")
        log_agent("Processing your request...")
        
        # 使用流式输出运行Agent (与交互模式保持一致)
        log_technical("info", f"Running agent with message: {task}...")
        log_technical("info", f"Using streaming output mode")
        
        # 显示开始状态
        print("\n>>  ", end="", flush=True)
        
        # 运行Agent - 使用流式输出
        response_text = ""
        try:
            for chunk in agent.run_stream_sync(task, **kwargs):
                if chunk and not chunk.startswith("[ERROR]"):
                    print(chunk, end="", flush=True)
                    response_text += chunk
                elif chunk.startswith("[ERROR]"):
                    print(f"\n{chunk}")
                    response_text = chunk
                    break
            
            print()  # 新行
            
        except Exception as e:
            log_technical("warning", f"Streaming failed, falling back to non-streaming: {e}")
            # 如果流式输出失败，回退到非流式
            result = agent.run_sync(task, **kwargs)
            if hasattr(result, 'final_output'):
                response_text = result.final_output
            else:
                response_text = str(result)
            
            if response_text:
                print(f"\n{response_text}")
        
        log_agent("Task completed successfully")
        log_user(">> [OK] Task completed!")
        
        # Run 结束日志 (成功)
        run_end_time = datetime.now()
        run_duration = (run_end_time - run_start_time).total_seconds()
        
        log_technical("info", f"{'='*50}")
        log_technical("info", f"SINGLE RUN END - ID: {run_id}")
        log_technical("info", f"Run End Time: {run_end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        log_technical("info", f"Run Duration: {run_duration:.3f}s")
        log_technical("info", f"Status: SUCCESS")
        log_technical("info", f"Response Length: {len(response_text)} characters")
        log_technical("info", f"{'='*50}")
        
        # 创建结果对象返回
        class StreamingResult:
            def __init__(self, output):
                self.final_output = output
        
        return StreamingResult(response_text)
        
    except Exception as e:
        # Run 结束日志 (失败)
        run_end_time = datetime.now()
        run_duration = (run_end_time - run_start_time).total_seconds()
        
        log_user(f"[ERROR] {str(e)}")
        log_technical("error", f"Full error details: {e}")
        
        log_technical("info", f"{'='*50}")
        log_technical("info", f"SINGLE RUN END - ID: {run_id}")
        log_technical("info", f"Run End Time: {run_end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        log_technical("info", f"Run Duration: {run_duration:.3f}s")
        log_technical("info", f"Status: FAILED")
        log_technical("info", f"Error: {str(e)}")
        log_technical("info", f"{'='*50}")
        
        raise

def main():
    """Main entry point for the CLI."""
    cli()

if __name__ == '__main__':
    main() 