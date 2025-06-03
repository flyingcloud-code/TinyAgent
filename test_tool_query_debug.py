import asyncio
from tinyagent.core.agent import TinyAgent
from tinyagent.intelligence import INTELLIGENCE_AVAILABLE

async def test_debug():
    print(f'INTELLIGENCE_AVAILABLE: {INTELLIGENCE_AVAILABLE}')
    agent = TinyAgent(intelligent_mode=True)
    print(f'Agent intelligent_mode: {agent.intelligent_mode}')
    
    # Test tool query detection directly
    intelligent_agent = agent._get_intelligent_agent()
    if intelligent_agent:
        print('IntelligentAgent created successfully')
        
        # Test different query patterns
        test_queries = [
            "list tools",
            "list mcp tools", 
            "show tools",
            "what tools do you have",
            "available tools"
        ]
        
        for query in test_queries:
            detected = intelligent_agent._detect_tool_query(query)
            print(f'Query "{query}" -> detected: {detected}')
        
        # Test actual tool query handling
        print('\n=== Testing tool query handling ===')
        try:
            result = await intelligent_agent._handle_tool_query()
            print('Tool query result:')
            print(result[:500] + "..." if len(result) > 500 else result)
        except Exception as e:
            print(f'Error in tool query handling: {e}')
            import traceback
            traceback.print_exc()
    else:
        print('Failed to create IntelligentAgent')

if __name__ == "__main__":
    asyncio.run(test_debug()) 