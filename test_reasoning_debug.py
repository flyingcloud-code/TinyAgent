#!/usr/bin/env python3
"""
Debug script to test ReasoningEngine MCP tool registration
"""
import asyncio
import logging
from tinyagent.core.agent import TinyAgent
from tinyagent.intelligence import INTELLIGENCE_AVAILABLE

# Enable debug logging
logging.basicConfig(level=logging.INFO)

async def test_reasoning_engine():
    """Test if ReasoningEngine has MCP tools registered"""
    print("=== Testing ReasoningEngine MCP Tool Registration ===")
    
    # Create TinyAgent with intelligent mode enabled
    agent = TinyAgent()
    
    # Get the intelligent agent
    intelligent_agent = agent._get_intelligent_agent()
    
    if intelligent_agent:
        print(f"✅ IntelligentAgent created")
        
        # Check MCP manager
        if hasattr(agent, 'mcp_manager') and agent.mcp_manager:
            print(f"✅ MCP Manager available: {type(agent.mcp_manager).__name__}")
            
            # Check if it has tool cache
            if hasattr(agent.mcp_manager, 'tool_cache') and agent.mcp_manager.tool_cache:
                print(f"✅ Tool cache available")
                
                # Get cache stats
                cache_stats = agent.mcp_manager.tool_cache.get_cache_stats()
                print(f"Cache stats: {cache_stats}")
                
                # Try to get cached tools
                cached_tools = agent.mcp_manager.tool_cache.get_all_cached_tools()
                print(f"Cached tools by server: {list(cached_tools.keys())}")
                
                total_tools = 0
                for server_name, tools in cached_tools.items():
                    print(f"  {server_name}: {len(tools)} tools")
                    total_tools += len(tools)
                    for tool in tools[:2]:  # Show first 2 tools per server
                        print(f"    - {tool.name}: {tool.description[:50]}...")
                
                print(f"Total cached tools: {total_tools}")
            else:
                print("❌ No tool cache available")
        else:
            print("❌ No MCP Manager available")
        
        # Now manually trigger MCP tool registration
        print("\n=== Manually Triggering MCP Tool Registration ===")
        await agent._register_mcp_tools_with_intelligent_agent(intelligent_agent)
        
        # Check MCP tools registered with intelligent agent AFTER registration
        mcp_tools = intelligent_agent._mcp_tools
        print(f"MCP tools in IntelligentAgent AFTER registration: {len(mcp_tools)}")
        for tool in mcp_tools[:3]:  # Show first 3
            print(f"  - {tool.get('name', 'unknown')}: {tool.get('server', 'unknown')}")
        
        # Check ReasoningEngine AFTER registration
        reasoning_engine = intelligent_agent.reasoning_engine
        print(f"ReasoningEngine available MCP tools AFTER registration: {len(reasoning_engine.available_mcp_tools)}")
        print(f"Available MCP tools: {list(reasoning_engine.available_mcp_tools.keys())}")
        
        # Check if tool executor is set
        print(f"Tool executor set: {reasoning_engine.tool_executor is not None}")
        
        # Test action selection AFTER registration
        print("\n=== Testing Action Selection AFTER Registration ===")
        context = {
            "goal": "search for latest OpenAI models in 2025",
            "steps_taken": [],
            "available_tools": mcp_tools
        }
        
        action, params = reasoning_engine._select_action(context)
        print(f"Selected action: {action}")
        print(f"Action params: {params}")
        
        # Test available actions
        available_actions = reasoning_engine._get_available_actions()
        print(f"Available actions: {available_actions}")
        
    else:
        print("❌ IntelligentAgent not created")

async def test_full_reasoning():
    print(f'INTELLIGENCE_AVAILABLE: {INTELLIGENCE_AVAILABLE}')
    
    # Create TinyAgent exactly like CLI does
    agent = TinyAgent(intelligent_mode=True)
    print(f'Agent intelligent_mode: {agent.intelligent_mode}')
    
    # Test the actual run method with tool query
    print('\n=== Testing full run method with tool query ===')
    try:
        result = await agent.run("list tools")
        print('Run result type:', type(result))
        
        if hasattr(result, 'final_output'):
            output = result.final_output
        else:
            output = str(result)
        
        print('Output preview:')
        lines = output.split('\n')
        for i, line in enumerate(lines[:15]):
            print(f'  {i+1}: {line}')
        if len(lines) > 15:
            print(f'  ... and {len(lines) - 15} more lines')
            
        # Check if it contains actual MCP tools
        if 'read_file' in output or 'filesystem' in output:
            print('\n✅ SUCCESS: Output contains actual MCP tools!')
        else:
            print('\n❌ FAILURE: Output does not contain actual MCP tools')
            
    except Exception as e:
        print(f'Error in full run: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_reasoning_engine())
    asyncio.run(test_full_reasoning()) 