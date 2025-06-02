#!/usr/bin/env python3
"""
检查可用的MCP工具
"""

from tinyagent.core.agent import TinyAgent

def check_available_tools():
    """检查可用工具"""
    try:
        agent = TinyAgent()
        print("=== Available Tools ===")
        
        tools = agent.get_available_tools()
        print(f"Available tools: {tools}")
        
        print("\n=== Server Information ===")
        server_info = agent.get_mcp_server_info()
        for info in server_info:
            print(f"Server: {info['name']}")
            print(f"  Type: {info['type']}")
            print(f"  Status: {info['status']}")
            print(f"  Config: {info['config']}")
            print()
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_available_tools() 