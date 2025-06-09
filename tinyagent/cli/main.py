"""
TinyAgent Command Line Interface - 简化版本

提供简洁的CLI界面，支持运行任务和查看状态。
"""

import click
import sys
from typing import Optional
from pathlib import Path
import os
import logging

# 🔧 SIMPLIFIED: 使用简化的配置和日志系统  
from ..core.config import get_config
from ..core.agent import TinyAgent
from ..mcp.manager import get_mcp_manager

# Global logger
logger = None

@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def cli(verbose: bool):
    """TinyAgent - 简洁而强大的AI代理框架"""
    global logger
    
    # 🔧 SIMPLIFIED: 使用简单的日志设置
    import logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')
    logger = logging.getLogger(__name__)
    
    if verbose:
        logger.info("TinyAgent CLI started with verbose logging")

@cli.command()
@click.argument('prompt', required=True)
@click.option('--output', '-o', type=click.Path(), help='Save output to file')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed tool results')
def run(prompt: str, output: Optional[str], verbose: bool):
    """Run TinyAgent with a single task."""
    try:
        # 🔧 SIMPLIFIED: 使用简化的TinyAgent
        print(f"🚀 Starting TinyAgent...")
        print(f"📝 Task: {prompt}")
        
        # 🎨 ITERATION 3: 传递verbose参数给TinyAgent (R05.3.1.2)
        agent = TinyAgent(verbose=verbose)
        result = agent.run_sync(prompt)
        
        # 处理结果
        if hasattr(result, 'answer'):
            output_text = result.answer
        elif hasattr(result, 'final_output'):
            output_text = result.final_output
        elif isinstance(result, dict):
            output_text = result.get('answer', str(result))
        else:
            output_text = str(result)
        
        print(f"\n✅ Task completed!")
        print(f"📄 Response:\n{output_text}")
        
        if output:
            Path(output).write_text(output_text, encoding='utf-8')
            print(f"💾 Output saved to: {output}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

@cli.command()
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
def status(verbose: bool):
    """Show TinyAgent status and configuration."""
    try:
        # 🔧 SIMPLIFIED: 使用简化的配置系统
        config = get_config()
        
        click.echo("🔧 TinyAgent Status")
        click.echo("=" * 40)
        
        # Agent configuration
        click.echo(f"📋 Agent Name: {config.agent.name}")
        click.echo(f"🔄 Max Iterations: {config.agent.max_iterations}")
        click.echo(f"🧠 Intelligent Mode: {'✅ Enabled' if config.agent.intelligent_mode else '❌ Disabled'}")
        
        # LLM configuration
        click.echo(f"\n🤖 LLM Provider: {config.llm.provider}")
        click.echo(f"📱 LLM Model: {config.llm.model}")
        click.echo(f"🔑 API Key Env: {config.llm.api_key_env}")
        if hasattr(config.llm, 'base_url') and config.llm.base_url:
            click.echo(f"🌐 Base URL: {config.llm.base_url}")
        
        # Check API key
        api_key = os.getenv(config.llm.api_key_env)
        if api_key:
            click.echo(f"✅ API Key: Found ({config.llm.api_key_env})")
        else:
            click.echo(f"❌ API Key: Not found ({config.llm.api_key_env})")
        
        # 🔧 SIMPLIFIED: 简化的MCP状态检查
        click.echo(f"\n🔧 MCP Servers:")
        if not config.mcp.enabled:
            click.echo("  ❌ MCP is disabled")
        else:
            try:
                mcp_manager = get_mcp_manager()
                server_count = len(mcp_manager.server_configs)
                click.echo(f"  ✅ {server_count} servers configured")
                
                if verbose:
                    for name, server_config in mcp_manager.server_configs.items():
                        click.echo(f"    • {name} ({server_config.type})")
                        if hasattr(server_config, 'enabled'):
                            status = "✅ Enabled" if server_config.enabled else "❌ Disabled"
                            click.echo(f"      Status: {status}")
            except Exception as e:
                click.echo(f"  ❌ Error: {e}")
        
        click.echo(f"\n📊 Run 'python -m tinyagent status --verbose' for more details")
             
    except Exception as e:
        click.echo(f"❌ Error getting status: {e}")
        if verbose:
            import traceback
            click.echo(traceback.format_exc())

@cli.command()
def help():
    """Show usage examples and quick start guide."""
    click.echo("🚀 TinyAgent Quick Start Guide")
    click.echo("=" * 40)
    click.echo()
    click.echo("📝 Basic Usage:")
    click.echo('  python -m tinyagent "What can you do?"')
    click.echo('  python -m tinyagent "List files in current directory"')
    click.echo('  python -m tinyagent "Create a Python script to analyze data"')
    click.echo()
    click.echo("📊 Check Status:")
    click.echo("  python -m tinyagent status")
    click.echo("  python -m tinyagent status --verbose")
    click.echo()
    click.echo("💾 Save Output:")
    click.echo('  python -m tinyagent "Analyze README.md" --output analysis.txt')
    click.echo()
    click.echo("⚙️ Setup (First Time):")
    click.echo("  1. Set API key: export OPENROUTER_API_KEY=your-key")
    click.echo("  2. Run task: python -m tinyagent \"Hello TinyAgent!\"")
    click.echo()
    click.echo("📚 More info: See README.md for full documentation")

def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 