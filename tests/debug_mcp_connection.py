#!/usr/bin/env python3
"""
调试MCP连接问题
"""

import asyncio
from tinyagent.core.agent import TinyAgent

async def debug_mcp_connection():
    """调试MCP连接"""
    print("=== Debugging MCP Connection ===")
    
    try:
        agent = TinyAgent()
        print(f"Agent created: {type(agent)}")
        
        # 检查配置
        print(f"\nMCP Manager: {type(agent.mcp_manager)}")
        print(f"Server configs: {len(agent.mcp_manager.server_configs)}")
        
        for config in agent.mcp_manager.server_configs:
            print(f"  - {config.name}: enabled={config.enabled}, type={config.type}")
        
        # 检查连接状态
        print(f"\nConnection status: {agent.get_mcp_connection_status()}")
        print(f"Active servers: {agent.get_active_mcp_servers()}")
        
        # 尝试确保连接
        print("\n--- Ensuring MCP connections ---")
        connected_servers = await agent._ensure_mcp_connections()
        print(f"Connected servers: {len(connected_servers)}")
        
        for server in connected_servers:
            print(f"  - {server}")
            try:
                tools = await server.list_tools()
                print(f"    Tools: {len(tools)}")
                for tool in tools[:3]:  # 只显示前3个
                    print(f"      - {tool.name}")
            except Exception as e:
                print(f"    Error listing tools: {e}")
        
        # 检查Agent实例
        print("\n--- Checking Agent instance ---")
        agent_instance = agent.get_agent()
        print(f"Agent instance: {type(agent_instance)}")
        print(f"Agent MCP servers: {len(agent_instance.mcp_servers)}")
        
        for server in agent_instance.mcp_servers:
            print(f"  - {server}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_mcp_connection()) 