#!/usr/bin/env python3
"""
测试修复后的MCP集成
"""

import asyncio
from tinyagent.core.agent import TinyAgent

async def test_fixed_mcp():
    """测试修复后的MCP集成"""
    print("=== Testing Fixed MCP Integration ===")
    
    try:
        agent = TinyAgent()
        print(f"Agent created: {type(agent)}")
        
        # Step 1: 检查初始状态（应该没有连接）
        print(f"\n--- Initial State ---")
        initial_agent = agent.get_agent()
        print(f"Initial agent MCP servers: {len(initial_agent.mcp_servers)}")
        print(f"Initial available tools: {agent.get_available_tools()}")
        
        # Step 2: 建立MCP连接
        print(f"\n--- Establishing MCP Connections ---")
        connected_servers = await agent._ensure_mcp_connections()
        print(f"Connected servers: {len(connected_servers)}")
        
        # Step 3: 检查连接后的状态
        print(f"\n--- State After Connection ---")
        connected_agent = agent.get_agent()
        print(f"Connected agent type: {type(connected_agent)}")
        print(f"Connected agent MCP servers: {len(connected_agent.mcp_servers)}")
        
        # List the MCP servers
        for i, server in enumerate(connected_agent.mcp_servers):
            print(f"  Server {i+1}: {type(server).__name__}")
            try:
                tools = await server.list_tools()
                print(f"    Tools: {len(tools)}")
                for tool in tools[:3]:  # 只显示前3个
                    print(f"      - {tool.name}")
            except Exception as e:
                print(f"    Error listing tools: {e}")
        
        print(f"Available tools (sync): {agent.get_available_tools()}")
        
        # Step 4: 测试异步工具列表
        print(f"\n--- Async Tools List ---")
        async_tools = await agent.get_available_tools_async()
        print(f"Async tools: {async_tools}")
        
        # Step 5: 测试简单对话
        print(f"\n--- Testing Simple Conversation ---")
        result = await agent.run("What is 2+2?")
        print(f"Simple result type: {type(result)}")
        if hasattr(result, 'final_output'):
            print(f"Simple result: {result.final_output[:200]}...")
        
        # Step 6: 测试需要工具的对话
        print(f"\n--- Testing Tool-Required Conversation ---")
        tool_result = await agent.run("Please search for latest Python news")
        print(f"Tool result type: {type(tool_result)}")
        if hasattr(tool_result, 'final_output'):
            print(f"Tool result: {tool_result.final_output[:200]}...")
        
        print(f"\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_fixed_mcp()) 