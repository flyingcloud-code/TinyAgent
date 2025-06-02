#!/usr/bin/env python3
"""
测试Web Search功能
"""

import asyncio
from tinyagent.core.agent import TinyAgent

def test_web_search():
    """测试Web搜索功能"""
    print("=== Testing Web Search ===")
    
    try:
        agent = TinyAgent()
        print(f"Agent created successfully")
        
        # 检查MCP服务器配置
        try:
            server_info = agent.get_mcp_server_info()
            print(f"MCP servers: {len(server_info)}")
            for info in server_info:
                print(f"  - {info['name']}: status={info['status']}, type={info['type']}")
        except Exception as e:
            print(f"Error getting server info: {e}")
        
        # 测试明确要求使用web search的消息
        search_message = "Please use web search to find the latest news about Python 3.13 release"
        print(f"\nTesting message: {search_message}")
        
        print("\n--- Response (first 1000 chars) ---")
        result = agent.run_sync(search_message)
        
        if hasattr(result, 'final_output'):
            response_text = result.final_output
            print(f"Response type: {type(response_text)}")
            print(f"Response length: {len(response_text)} characters")
            print(f"Response preview: {response_text[:1000]}...")
        else:
            print(f"No final_output, result type: {type(result)}")
            print(f"Result: {str(result)[:500]}...")
            
    except Exception as e:
        print(f"Web search test failed: {e}")
        import traceback
        traceback.print_exc()

def test_simple_math():
    """测试简单数学问题作为对比"""
    print("\n=== Testing Simple Math (Control) ===")
    
    try:
        agent = TinyAgent()
        math_message = "What is 15 * 23?"
        print(f"Testing message: {math_message}")
        
        result = agent.run_sync(math_message)
        
        if hasattr(result, 'final_output'):
            response_text = result.final_output
            print(f"Math response: {response_text[:300]}...")
        else:
            print(f"Math result: {str(result)[:300]}...")
            
    except Exception as e:
        print(f"Math test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Starting Web Search Test...")
    
    # 先测试简单数学作为对比
    test_simple_math()
    
    # 然后测试web search
    test_web_search()
    
    print("\nTest complete.") 