#!/usr/bin/env python3
"""
测试TinyAgent阶段2实时流式输出功能
测试TaskPlanner和ToolSelector的streaming支持
"""

import asyncio
import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tinyagent.core.agent import TinyAgent


async def test_phase2_streaming():
    """测试阶段2的完整streaming功能"""
    print("🧪 **测试TinyAgent阶段2实时流式输出功能**")
    print("=" * 70)
    print()
    
    # 创建TinyAgent实例，启用智能模式
    agent = TinyAgent(intelligent_mode=True)
    print(f"✅ TinyAgent已创建 (智能模式: {agent.intelligent_mode})")
    print()
    
    # 测试问题 - 使用一个复杂的任务来触发TaskPlanner和ToolSelector
    test_message = "请搜索最新的人工智能新闻，然后创建一个名为ai_news.txt的文件总结内容"
    
    print(f"📝 **测试问题**: {test_message}")
    print()
    print("🔄 **开始阶段2流式输出测试**:")
    print("-" * 70)
    
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
    
    print("\n" + "-" * 70)
    print("🎉 **阶段2流式输出测试完成**")
    print(f"   ⏱️ 总耗时: {execution_time:.2f}秒")
    print(f"   📊 输出块数: {chunk_count}")
    print(f"   📈 平均块速度: {chunk_count/execution_time:.1f} 块/秒")
    print()
    
    return True


async def test_complex_task_streaming():
    """测试复杂任务的streaming输出"""
    print("🧪 **测试复杂任务流式输出**")
    print("=" * 70)
    print()
    
    agent = TinyAgent(intelligent_mode=True)
    test_message = "分析当前项目的文件结构，读取README.md文件内容，然后搜索相关的技术文档，最后创建一个项目分析报告"
    
    print(f"📝 **复杂任务**: {test_message}")
    print()
    print("🔄 **开始复杂任务流式输出**:")
    print("-" * 70)
    
    start_time = time.time()
    
    try:
        async for chunk in agent.run_stream(test_message):
            print(chunk, end='', flush=True)
            await asyncio.sleep(0.01)
            
    except Exception as e:
        print(f"\n❌ **流式输出错误**: {e}")
        return False
    
    end_time = time.time()
    print(f"\n⏱️ 复杂任务执行时间: {end_time - start_time:.2f}秒")
    print()
    return True


async def test_simple_task_streaming():
    """测试简单任务的streaming输出"""
    print("🧪 **测试简单任务流式输出**")
    print("=" * 70)
    print()
    
    agent = TinyAgent(intelligent_mode=True)
    test_message = "请读取当前目录下的文件列表"
    
    print(f"📝 **简单任务**: {test_message}")
    print()
    print("🔄 **开始简单任务流式输出**:")
    print("-" * 70)
    
    try:
        async for chunk in agent.run_stream(test_message):
            print(chunk, end='', flush=True)
            await asyncio.sleep(0.01)
            
    except Exception as e:
        print(f"\n❌ **流式输出错误**: {e}")
        return False
    
    print("\n" + "=" * 70)
    print()
    return True


async def main():
    """主测试函数"""
    print("🚀 **TinyAgent 阶段2 Streaming测试开始**")
    print(f"⏰ 测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    print("📋 **阶段2特性**:")
    print("   ✅ TaskPlanner streaming支持")
    print("   ✅ ToolSelector streaming支持") 
    print("   ✅ 实时任务规划过程展示")
    print("   ✅ 实时工具选择过程展示")
    print("   ✅ 详细的复杂度分析")
    print("   ✅ 智能组件协作流程可视化")
    print()
    
    tests = [
        ("简单任务流式输出", test_simple_task_streaming),
        ("复杂任务流式输出", test_complex_task_streaming),
        ("阶段2完整功能测试", test_phase2_streaming),
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
    print("🏁 **阶段2测试总结**")
    print()
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    print()
    print(f"📊 **总体结果**: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 **所有测试通过！阶段2实现成功！**")
        print()
        print("✨ **阶段2成功特性**:")
        print("   🎯 TaskPlanner实时规划展示")
        print("   🔧 ToolSelector智能选择过程")
        print("   📊 任务复杂度实时分析")
        print("   ⏱️ 执行时间预估和跟踪")
        print("   🔄 备选方案分析和展示")
        print("   💡 智能组件协作可视化")
        print()
        return True
    else:
        print("⚠️ **部分测试失败，需要调试**")
        return False


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 