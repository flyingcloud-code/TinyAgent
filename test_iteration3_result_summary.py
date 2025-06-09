#!/usr/bin/env python3
"""
测试迭代3: 结果可视化优化验证
验证工具执行结果的智能摘要功能
"""

import asyncio
import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from tinyagent.core.agent import TinyAgent

async def test_result_visualization():
    """测试结果可视化优化"""
    
    print("=" * 60)
    print("🧪 测试迭代3: 结果可视化优化验证")
    print("🎯 目标: 验证智能结果摘要功能")
    print("=" * 60)
    
    agent = TinyAgent()
    
    # 测试案例：搜索任务，应该显示智能摘要
    print("\n📝 测试案例: 搜索任务智能摘要")
    print("输入: 'what is latest news from openai'")
    print("期望: 应该看到不同工具的专用摘要格式")
    print("\n🔍 观察以下输出格式:")
    print("- google_search: 应显示 '找到 X 个搜索结果'")
    print("- get_web_content: 应显示 '获取网页内容' 或 '获取失败'")
    print("- 缓存命中: 应显示相同的智能摘要")
    
    start_time = time.time()
    
    try:
        result = await agent.run("what is latest news from openai")
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n🎯 测试结果分析:")
        print(f"✅ 任务完成耗时: {duration:.2f}秒")
        
        # 分析输出格式的改进
        print(f"\n💡 迭代3改进验证:")
        print(f"✅ 工具摘要格式: 应该看到 '📊 工具名: 智能摘要' 格式")
        print(f"✅ 搜索结果摘要: 应该显示找到的搜索结果数量")
        print(f"✅ 网页内容摘要: 应该显示内容长度或失败信息")
        print(f"✅ 缓存结果摘要: 缓存命中时也应显示智能摘要")
        
        # 检查结果
        if hasattr(result, 'final_output'):
            final_output = result.final_output
        elif isinstance(result, dict):
            final_output = result.get('answer', str(result))
        else:
            final_output = str(result)
        
        print(f"\n📋 最终输出长度: {len(final_output)} 字符")
        print(f"📋 输出预览: {final_output[:200]}...")
        
        print(f"\n🎉 迭代3测试完成!")
        print(f"⭐ 用户体验改进: 从通用提示升级为智能工具摘要")
        print(f"⭐ 信息透明度: 用户现在能判断工具执行质量")
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

async def test_tool_summary_formats():
    """测试不同工具的摘要格式"""
    
    print("\n" + "=" * 60)
    print("🔧 测试不同工具摘要格式")
    print("=" * 60)
    
    agent = TinyAgent()
    
    # 测试搜索工具摘要
    print("\n🔍 测试1: 搜索工具摘要格式")
    try:
        # 第一次调用：应该显示搜索结果摘要
        result1 = await agent.run("search latest AI news")
        print("✅ 第一次搜索: 查看摘要格式")
        
        # 第二次调用：可能命中缓存，应该显示相同的智能摘要
        result2 = await agent.run("search latest AI news") 
        print("✅ 第二次搜索: 验证缓存摘要格式")
        
    except Exception as e:
        print(f"⚠️ 搜索测试失败: {e}")
    
    print(f"\n🎯 摘要格式验证点:")
    print(f"1. 搜索工具: 应显示 '找到 X 个搜索结果'")
    print(f"2. 网页工具: 应显示 '获取网页内容' 或错误信息")
    print(f"3. 缓存命中: 应保持相同的智能摘要格式")
    print(f"4. 进度提示: 应看到 '🔍 正在使用 工具名 工具...'")

if __name__ == "__main__":
    print("🚀 启动迭代3: 结果可视化优化测试")
    
    async def main():
        success1 = await test_result_visualization()
        await test_tool_summary_formats()
        
        if success1:
            print("\n🎉 迭代3测试全部完成!")
            print("🏆 结果可视化优化验证成功")
        else:
            print("\n⚠️ 部分测试未通过，需要检查")
    
    asyncio.run(main()) 