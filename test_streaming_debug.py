#!/usr/bin/env python3
"""
测试TinyAgent实时流式输出功能
测试阶段1实现：IntelligentAgent.run_stream方法
"""

import asyncio
import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tinyagent.core.agent import TinyAgent


async def test_streaming_output():
    """测试TinyAgent的streaming输出功能"""
    print("🧪 **测试TinyAgent实时流式输出功能**")
    print("=" * 60)
    print()
    
    # 创建TinyAgent实例，启用智能模式
    agent = TinyAgent(intelligent_mode=True)
    print(f"✅ TinyAgent已创建 (智能模式: {agent.intelligent_mode})")
    print()
    
    # 测试问题
    test_message = "请创建一个名为test_streaming.txt的文件，内容为'Hello Streaming!'"
    
    print(f"📝 **测试问题**: {test_message}")
    print()
    print("🔄 **开始流式输出**:")
    print("-" * 60)
    
    start_time = time.time()
    chunk_count = 0
    
    try:
        # 使用流式输出
        async for chunk in agent.run_stream(test_message):
            # 实时输出每个chunk
            print(chunk, end='', flush=True)
            chunk_count += 1
            
            # 小延迟让输出更自然
            await asyncio.sleep(0.01)
            
    except Exception as e:
        print(f"\n❌ **流式输出错误**: {e}")
        print(f"错误类型: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    print("\n" + "-" * 60)
    print("🎉 **流式输出测试完成**")
    print(f"   ⏱️ 总耗时: {execution_time:.2f}秒")
    print(f"   📊 输出块数: {chunk_count}")
    print(f"   📈 平均块速度: {chunk_count/execution_time:.1f} 块/秒")
    print()
    
    return True


async def test_simple_streaming():
    """测试简单的流式输出（不使用工具）"""
    print("🧪 **测试简单流式输出（推理模式）**")
    print("=" * 60)
    print()
    
    agent = TinyAgent(intelligent_mode=True)
    test_message = "请用3句话解释什么是人工智能"
    
    print(f"📝 **测试问题**: {test_message}")
    print()
    print("🔄 **开始流式输出**:")
    print("-" * 60)
    
    start_time = time.time()
    
    try:
        async for chunk in agent.run_stream(test_message):
            print(chunk, end='', flush=True)
            await asyncio.sleep(0.01)
            
    except Exception as e:
        print(f"\n❌ **流式输出错误**: {e}")
        return False
    
    end_time = time.time()
    print(f"\n⏱️ 执行时间: {end_time - start_time:.2f}秒")
    print()
    return True


async def test_tool_query_streaming():
    """测试工具查询的流式输出"""
    print("🧪 **测试工具查询流式输出**")
    print("=" * 60)
    print()
    
    agent = TinyAgent(intelligent_mode=True)
    test_message = "列出你可用的MCP工具"
    
    print(f"📝 **测试问题**: {test_message}")
    print()
    print("🔄 **开始流式输出**:")
    print("-" * 60)
    
    try:
        async for chunk in agent.run_stream(test_message):
            print(chunk, end='', flush=True)
            await asyncio.sleep(0.01)
            
    except Exception as e:
        print(f"\n❌ **流式输出错误**: {e}")
        return False
    
    print("\n" + "=" * 60)
    print()
    return True


async def main():
    """主测试函数"""
    print("🚀 **TinyAgent 阶段1 Streaming测试开始**")
    print(f"⏰ 测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    tests = [
        ("工具查询流式输出", test_tool_query_streaming),
        ("简单推理流式输出", test_simple_streaming),
        ("文件创建流式输出", test_streaming_output),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"🧪 **开始测试**: {test_name}")
        try:
            result = await test_func()
            results.append((test_name, result))
            if result:
                print(f"✅ **{test_name}**: 通过")
            else:
                print(f"❌ **{test_name}**: 失败")
        except Exception as e:
            print(f"❌ **{test_name}**: 异常 - {e}")
            results.append((test_name, False))
        
        print()
        await asyncio.sleep(1)  # 测试间隔
    
    # 总结
    print("=" * 80)
    print("🏁 **测试总结**")
    print()
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    print()
    print(f"📊 **总体结果**: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 **所有测试通过！阶段1实现成功！**")
        return True
    else:
        print("⚠️ **部分测试失败，需要调试**")
        return False


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 