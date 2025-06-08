#!/usr/bin/env python3
"""
Debug script to test intelligent mode tool listing issue
"""
import asyncio
import logging
from tinyagent.core.agent import TinyAgent

# Enable debug logging
logging.basicConfig(level=logging.INFO)

async def test_tool_listing():
    """Test if intelligent mode correctly lists MCP tools"""
    print("=== Testing Intelligent Mode Tool Listing ===")
    
    # Create TinyAgent with intelligent mode enabled
    agent = TinyAgent()
    
    # Print current configuration
    print(f"Intelligent mode: {agent.intelligent_mode}")
    print(f"Agent config: {agent.config.agent.name}")
    
    # Test tool listing
    result = await agent.run('list mcp tools you have')
    
    print("=== RESULT ===")
    if hasattr(result, 'final_output'):
        print(result.final_output)
    else:
        print(result)
    
    return result

async def test_web_search():
    """Test if intelligent mode can perform web search"""
    print("\n=== Testing Web Search ===")
    
    agent = TinyAgent()
    
    # Test web search task
    result = await agent.run('search for latest OpenAI models in 2025')
    
    print("=== RESULT ===")
    if hasattr(result, 'final_output'):
        print(result.final_output)
    else:
        print(result)
    
    return result

if __name__ == "__main__":
    asyncio.run(test_tool_listing())
    asyncio.run(test_web_search()) 