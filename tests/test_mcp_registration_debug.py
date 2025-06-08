import asyncio
from tinyagent.core.agent import TinyAgent
from tinyagent.intelligence import INTELLIGENCE_AVAILABLE

async def test_mcp_registration():
    print(f'INTELLIGENCE_AVAILABLE: {INTELLIGENCE_AVAILABLE}')
    
    # Create TinyAgent
    agent = TinyAgent(intelligent_mode=True)
    print(f'Agent intelligent_mode: {agent.intelligent_mode}')
    
    # Get the intelligent agent
    intelligent_agent = agent._get_intelligent_agent()
    if not intelligent_agent:
        print('Failed to create IntelligentAgent')
        return
    
    print('IntelligentAgent created successfully')
    
    # Check initial state of MCP tools
    print(f'Initial _mcp_tools: {hasattr(intelligent_agent, "_mcp_tools")}')
    if hasattr(intelligent_agent, '_mcp_tools'):
        print(f'_mcp_tools count: {len(intelligent_agent._mcp_tools)}')
    
    # Trigger MCP tool registration
    print('\n=== Triggering MCP tool registration ===')
    try:
        await agent._register_mcp_tools_with_intelligent_agent(intelligent_agent)
        print('MCP tool registration completed')
        
        # Check state after registration
        print(f'After registration _mcp_tools: {hasattr(intelligent_agent, "_mcp_tools")}')
        if hasattr(intelligent_agent, '_mcp_tools'):
            print(f'_mcp_tools count: {len(intelligent_agent._mcp_tools)}')
            if intelligent_agent._mcp_tools:
                print('First few tools:')
                for i, tool in enumerate(intelligent_agent._mcp_tools[:3]):
                    print(f'  Tool {i+1}: {tool.get("name", "unknown")} from {tool.get("server", "unknown")}')
        
        # Test _get_available_tools now
        print('\n=== Testing _get_available_tools ===')
        tools = await intelligent_agent._get_available_tools()
        print(f'Available tools count: {len(tools)}')
        if tools:
            print('First few tools:')
            for i, tool in enumerate(tools[:5]):
                print(f'  Tool {i+1}: {tool.get("name", "unknown")} - {tool.get("type", "unknown")} from {tool.get("server", "unknown")}')
        
        # Test tool query handling after registration
        print('\n=== Testing tool query handling after registration ===')
        result = await intelligent_agent._handle_tool_query()
        print('Tool query result summary:')
        lines = result.split('\n')
        for line in lines[:10]:
            print(f'  {line}')
        if len(lines) > 10:
            print(f'  ... and {len(lines) - 10} more lines')
            
    except Exception as e:
        print(f'Error in MCP tool registration: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mcp_registration()) 