import asyncio
import os
from agents import Agent, Runner, set_default_openai_key
from agents.mcp import MCPServerStdio

async def test_agent_with_mcp():
    try:
        # 设置OpenAI API密钥（如果有的话）
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key:
            set_default_openai_key(openai_key)
        else:
            print("Warning: OPENAI_API_KEY not found, using placeholder")
            set_default_openai_key("sk-test-key")
        
        # 创建MCP服务器
        async with MCPServerStdio(
            name='filesystem',
            params={
                'command': 'npx',
                'args': ['-y', '@modelcontextprotocol/server-filesystem', '.']
            }
        ) as server:
            print(f"MCP Server connected: {server}")
            
            # 列出可用工具
            tools = await server.list_tools()
            print(f"Available tools: {[tool.name for tool in tools]}")
            
            # 创建Agent并传入MCP服务器
            agent = Agent(
                name="TinyAgent-Test",
                instructions="You are a helpful assistant that can access the filesystem. Use the available tools to help users.",
                model="gpt-3.5-turbo",
                mcp_servers=[server]
            )
            
            print("Agent created successfully with MCP server")
            print("MCP integration test completed!")
            
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_agent_with_mcp()) 