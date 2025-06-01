import asyncio
from agents.mcp import MCPServerStdio

async def test_mcp():
    try:
        async with MCPServerStdio(
            name='filesystem',
            params={
                'command': 'npx',
                'args': ['-y', '@modelcontextprotocol/server-filesystem', '.']
            }
        ) as server:
            tools = await server.list_tools()
            print(f'Available tools: {[tool.name for tool in tools]}')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    asyncio.run(test_mcp()) 