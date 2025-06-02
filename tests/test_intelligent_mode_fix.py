#!/usr/bin/env python3
"""
测试TinyAgent智能模式是否正确工作
"""

import asyncio
from tinyagent.core.agent import TinyAgent, INTELLIGENCE_AVAILABLE

def test_intelligent_mode_status():
    """测试智能模式状态"""
    print("=== 智能模式状态测试 ===")
    
    print(f"INTELLIGENCE_AVAILABLE: {INTELLIGENCE_AVAILABLE}")
    
    # 创建Agent实例
    agent = TinyAgent()
    print(f"Agent intelligent_mode: {agent.intelligent_mode}")
    print(f"Agent config intelligent_mode: {getattr(agent.config.agent, 'intelligent_mode', 'not set')}")
    
    # 获取智能代理实例
    intelligent_agent = agent._get_intelligent_agent()
    print(f"Intelligent Agent instance: {type(intelligent_agent) if intelligent_agent else None}")
    
    if intelligent_agent:
        print(f"Intelligent Agent has MCP context builder: {hasattr(intelligent_agent, 'mcp_context_builder')}")
        print(f"Intelligent Agent has tool cache: {hasattr(intelligent_agent, 'tool_cache')}")
        print(f"Intelligent Agent has MCP manager: {hasattr(intelligent_agent, 'mcp_manager')}")

def test_mcp_tools_visibility():
    """测试MCP工具可见性"""
    print("\n=== MCP工具可见性测试 ===")
    
    agent = TinyAgent()
    
    # 获取可用工具（同步版本）
    tools = agent.get_available_tools()
    print(f"Available tools (sync): {tools}")
    
    # 获取MCP服务器信息
    server_info = agent.get_mcp_server_info()
    print(f"MCP servers: {len(server_info)}")
    for info in server_info:
        print(f"  - {info['name']}: {info['status']}")

async def test_intelligent_agent_mcp_integration():
    """测试智能代理与MCP工具的集成"""
    print("\n=== 智能代理MCP集成测试 ===")
    
    agent = TinyAgent()
    intelligent_agent = agent._get_intelligent_agent()
    
    if not intelligent_agent:
        print("❌ 智能代理未初始化")
        return
    
    # 测试MCP工具注册
    try:
        await agent._register_mcp_tools_with_intelligent_agent(intelligent_agent)
        print("✅ MCP工具注册完成")
    except Exception as e:
        print(f"❌ MCP工具注册失败: {e}")
    
    # 检查工具上下文构建
    if hasattr(intelligent_agent, 'mcp_context_builder'):
        try:
            tools_context = intelligent_agent.mcp_context_builder.build_tools_context()
            print(f"✅ 工具上下文构建成功: {len(tools_context)} characters")
            print(f"Context preview: {tools_context[:200]}...")
        except Exception as e:
            print(f"❌ 工具上下文构建失败: {e}")

def test_simple_intelligent_query():
    """测试简单的智能查询"""
    print("\n=== 简单智能查询测试 ===")
    
    agent = TinyAgent()
    
    if not agent.intelligent_mode:
        print("❌ 智能模式未启用")
        return
    
    try:
        # 测试简单查询
        result = agent.run_sync("Hello! Please tell me what MCP tools you have available.")
        print(f"✅ 查询成功")
        print(f"Response: {str(result)[:300]}...")
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主测试函数"""
    print("🧪 TinyAgent智能模式修复验证")
    print("=" * 50)
    
    test_intelligent_mode_status()
    test_mcp_tools_visibility()
    await test_intelligent_agent_mcp_integration()
    test_simple_intelligent_query()
    
    print("\n✅ 测试完成")

if __name__ == "__main__":
    asyncio.run(main()) 