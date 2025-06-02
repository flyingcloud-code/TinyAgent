#!/usr/bin/env python3
"""
直接测试MCP连接
"""

import asyncio
from agents.mcp import MCPServerStdio, MCPServerSse

async def test_filesystem_server():
    """测试filesystem服务器"""
    print("=== Testing Filesystem Server ===")
    
    try:
        server = MCPServerStdio(
            name='filesystem',
            params={
                'command': 'npx',
                'args': ['-y', '@modelcontextprotocol/server-filesystem', '.']
            }
        )
        
        print("Connecting to filesystem server...")
        async with server as connected_server:
            print("✓ Connected successfully!")
            
            tools = await connected_server.list_tools()
            print(f"✓ Found {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
                
    except Exception as e:
        print(f"✗ Filesystem server test failed: {e}")
        import traceback
        traceback.print_exc()

async def test_search_server():
    """测试搜索服务器"""
    print("\n=== Testing Search Server ===")
    
    try:
        server = MCPServerSse(
            name='my-search',
            params={'url': 'http://192.168.1.3:8081/sse'}
        )
        
        print("Connecting to search server...")
        async with server as connected_server:
            print("✓ Connected successfully!")
            
            tools = await connected_server.list_tools()
            print(f"✓ Found {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
                
    except Exception as e:
        print(f"✗ Search server test failed: {e}")
        print("Note: Make sure the search server is running at http://192.168.1.3:8081")

async def main():
    await test_filesystem_server()
    await test_search_server()

if __name__ == "__main__":
    asyncio.run(main()) 