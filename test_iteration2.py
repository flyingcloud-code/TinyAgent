#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试迭代2：重复调用智能检测
验证工具缓存功能是否正常工作
"""

import sys
import os
import asyncio
import time
from pathlib import Path

# 确保正确的Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 设置控制台编码为UTF-8 (Windows)
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from tinyagent.core.agent import TinyAgent

async def test_iteration2():
    """测试迭代2：工具缓存功能"""
    print("🧪 测试迭代2：重复调用智能检测")
    print("=" * 50)
    
    try:
        # 创建TinyAgent
        print("\n🤖 创建TinyAgent...")
        agent = TinyAgent()
        
        # 检查缓存初始状态
        cache_stats = agent.get_cache_stats()
        print(f"📊 初始缓存状态: {cache_stats}")
        
        # 测试相同查询（预期会有缓存命中）
        print("\n🎯 测试查询：OpenAI最新新闻（预期有缓存效果）")
        print("-" * 50)
        
        start_time = time.time()
        result = await agent.run("what is latest news from openai")
        execution_time = time.time() - start_time
        
        print(f"\n📊 迭代2测试完成！")
        print(f"⏱️  总执行时间: {execution_time:.1f}秒")
        
        # 检查缓存状态
        final_cache_stats = agent.get_cache_stats()
        print(f"📋 最终缓存状态: {final_cache_stats}")
        
        # 测试缓存禁用功能
        print(f"\n🔧 测试缓存禁用功能...")
        agent.set_cache_enabled(False)
        print(f"✅ 缓存已禁用")
        
        # 清理连接
        await agent.close_mcp_connections()
        print(f"🔌 连接已清理")
        
        # 结果分析
        print(f"\n📈 迭代2效果分析:")
        if execution_time < 40:
            print(f"✅ 执行时间明显改善: {execution_time:.1f}秒 < 40秒")
        else:
            print(f"⚠️  执行时间仍然较长: {execution_time:.1f}秒")
        
        if final_cache_stats["cached_items"] > 0:
            print(f"✅ 缓存正常工作: {final_cache_stats['cached_items']} 项已缓存")
        else:
            print(f"⚠️  缓存可能未正常工作")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    """运行测试"""
    asyncio.run(test_iteration2())

if __name__ == "__main__":
    main() 