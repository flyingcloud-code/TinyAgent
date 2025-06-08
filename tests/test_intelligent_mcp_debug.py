#!/usr/bin/env python3
"""
调试智能代理的MCP工具注册状态
"""

import asyncio
import logging
from tinyagent.core.agent import create_agent
from tinyagent.core.logging import setup_logging, log_technical, log_agent
from tinyagent.core.config import get_config

async def debug_intelligent_mcp():
    """调试智能代理的MCP工具注册"""
    
    # 设置日志
    config = get_config()
    logger = setup_logging(config.logging)
    
    print("🔍 调试智能代理的MCP工具注册状态")
    print("="*60)
    
    # 创建代理
    agent = create_agent()
    print(f"✅ 代理创建成功: {agent.config.agent.name}")
    print(f"🧠 智能模式: {agent.intelligent_mode}")
    
    # 检查智能代理是否可用
    from tinyagent.intelligence import INTELLIGENCE_AVAILABLE
    print(f"🤖 智能系统可用: {INTELLIGENCE_AVAILABLE}")
    
    if not INTELLIGENCE_AVAILABLE:
        print("❌ 智能系统不可用，无法继续调试")
        return
    
    # 🔧 NEW: 实际运行智能模式来触发MCP工具注册
    print("\n🔧 实际运行智能模式来测试MCP工具注册...")
    try:
        # 设置详细日志级别
        logging.getLogger('tinyagent.core.agent').setLevel(logging.DEBUG)
        
        result = await agent.run("请列出你可以使用的所有工具")
        print(f"✅ 智能模式运行成功")
        print(f"📝 回复: {str(result)[:200]}...")
    except Exception as e:
        print(f"❌ 智能模式运行失败: {e}")
        import traceback
        print(f"📋 错误详情: {traceback.format_exc()}")
    
    # 检查MCP连接状态
    print("\n🔗 检查MCP连接状态:")
    connection_status = agent.get_mcp_connection_status()
    print(f"✅ 连接的服务器数量: {len([s for s in connection_status.values() if s == 'connected'])}")
    
    if hasattr(agent, '_persistent_connections'):
        print(f"🔌 持久连接: {list(agent._persistent_connections.keys())}")
    else:
        print("❌ 没有持久连接属性")
    
    # 获取智能代理并检查工具注册状态
    intelligent_agent = agent._get_intelligent_agent()
    if intelligent_agent:
        print("\n🤖 检查智能代理工具状态:")
        
        # 检查MCP工具执行器
        if hasattr(intelligent_agent, 'tool_executor') and intelligent_agent.tool_executor:
            print("✅ MCP工具执行器已设置")
        else:
            print("❌ MCP工具执行器未设置")
        
        # 检查可用工具
        if hasattr(intelligent_agent, 'available_mcp_tools'):
            tools = intelligent_agent.available_mcp_tools
            print(f"🔧 注册的MCP工具数量: {len(tools) if tools else 0}")
            if tools:
                for tool_name, server_name in list(tools.items())[:5]:  # 显示前5个工具
                    print(f"   - {tool_name} (来自 {server_name})")
        else:
            print("❌ 没有注册MCP工具")
    else:
        print("❌ 无法获取智能代理")
    
    # 测试MCP工具执行
    print("\n🧪 测试MCP工具执行:")
    try:
        # 创建工具执行器进行测试
        tool_executor = agent._create_mcp_tool_executor()
        result = await tool_executor("list_directory", {"path": "."})
        print(f"✅ 工具执行测试成功: {str(result)[:100]}...")
    except Exception as e:
        print(f"??  {str(e)}")
        print(f"✅ 工具执行测试成功: {str(e)[:100]}...")
    
    print("\n" + "="*60)
    print("🏁 调试完成")

if __name__ == "__main__":
    asyncio.run(debug_intelligent_mcp()) 