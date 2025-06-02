#!/usr/bin/env python3
"""
调试TinyAgent输出问题的脚本
"""

import sys
import asyncio
from tinyagent.core.agent import TinyAgent
from tinyagent.core.logging import log_technical

def test_streaming_output():
    """测试流式输出"""
    print("=== Testing Streaming Output ===")
    
    try:
        # 创建agent
        agent = TinyAgent()
        print(f"Agent created: {type(agent)}")
        print(f"Model: {agent.model_name}")
        print(f"Use streaming: {agent.use_streaming}")
        
        # 测试简单消息
        message = "what is 2+2"
        print(f"\nTesting message: {message}")
        
        print("\n--- Using run_stream_sync ---")
        try:
            response_chunks = []
            for i, chunk in enumerate(agent.run_stream_sync(message)):
                print(f"Chunk {i}: {repr(chunk)[:100]}...")
                response_chunks.append(chunk)
                if i >= 3:  # 只显示前几个chunk
                    break
            
            print(f"Total chunks: {len(response_chunks)}")
            if response_chunks:
                print(f"First chunk type: {type(response_chunks[0])}")
                print(f"First chunk content: {repr(response_chunks[0])[:200]}...")
        
        except Exception as e:
            print(f"run_stream_sync failed: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n--- Using run_sync for comparison ---")
        try:
            result = agent.run_sync(message)
            print(f"Result type: {type(result)}")
            print(f"Result: {repr(result)[:200]}...")
            
            if hasattr(result, 'final_output'):
                print(f"Final output: {repr(result.final_output)[:200]}...")
            
        except Exception as e:
            print(f"run_sync failed: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"Agent creation failed: {e}")
        import traceback
        traceback.print_exc()

async def test_async_streaming():
    """测试异步流式输出"""
    print("\n=== Testing Async Streaming ===")
    
    try:
        agent = TinyAgent()
        message = "what is 3+3"
        
        print(f"Testing async streaming with message: {message}")
        
        chunks = []
        async for chunk in agent.run_stream(message):
            print(f"Async chunk: {repr(chunk)[:100]}...")
            chunks.append(chunk)
            if len(chunks) >= 3:
                break
        
        print(f"Total async chunks: {len(chunks)}")
        
    except Exception as e:
        print(f"Async streaming failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Starting TinyAgent output debugging...")
    
    # 测试同步流式输出
    test_streaming_output()
    
    # 测试异步流式输出
    asyncio.run(test_async_streaming())
    
    print("\nDebugging complete.") 