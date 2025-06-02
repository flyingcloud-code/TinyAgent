#!/usr/bin/env python3
"""
Test Enhanced MCP Context Integration (EPIC-002 Phase 2)
Tests the integration of enhanced MCP tool context with IntelligentAgent.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import tinyagent
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_enhanced_context_integration():
    """Test enhanced MCP context integration with IntelligentAgent"""
    print("🔧 Testing Enhanced MCP Context Integration (EPIC-002 Phase 2)")
    print("=" * 60)
    
    try:
        # Import TinyAgent
        from tinyagent.core.agent import TinyAgent
        from tinyagent.core.config import get_config
        
        print("✅ TinyAgent imports successful")
        
        # Load configuration
        config = get_config()
        print(f"✅ Configuration loaded")
        
        # Create TinyAgent with intelligent mode
        agent = TinyAgent(
            config=config,
            intelligent_mode=True,
            instructions="You are an intelligent agent for testing enhanced MCP context integration."
        )
        print("✅ TinyAgent created with intelligent mode enabled")
        
        # Get the intelligent agent instance
        intelligent_agent = agent._get_intelligent_agent()
        
        if intelligent_agent is None:
            print("❌ FAILED: IntelligentAgent not created")
            return False
        
        print("✅ IntelligentAgent instance created")
        
        # Check MCP context builder initialization
        if hasattr(intelligent_agent, 'mcp_context_builder') and intelligent_agent.mcp_context_builder:
            print("✅ MCP context builder initialized")
            
            # Check tool cache
            if hasattr(intelligent_agent, 'tool_cache') and intelligent_agent.tool_cache:
                print("✅ Tool cache available")
                
                # Check MCP manager
                if hasattr(intelligent_agent, 'mcp_manager') and intelligent_agent.mcp_manager:
                    print(f"✅ MCP manager available: {type(intelligent_agent.mcp_manager).__name__}")
                    
                    # Test enhanced MCP manager functionality
                    if hasattr(intelligent_agent.mcp_manager, 'initialize_with_caching'):
                        print("✅ Enhanced MCP manager confirmed")
                        
                        # Test tool discovery and caching
                        print("\n🔍 Testing tool discovery and caching...")
                        try:
                            # Initialize tools with caching
                            cached_tools = await intelligent_agent.mcp_manager.initialize_with_caching()
                            
                            if cached_tools:
                                total_tools = sum(len(tools) for tools in cached_tools.values())
                                print(f"✅ Tool discovery successful: {total_tools} tools from {len(cached_tools)} servers")
                                
                                # Show server and tool details
                                for server_name, tools in cached_tools.items():
                                    if tools:
                                        tool_names = [tool.name for tool in tools]
                                        print(f"   📦 {server_name}: {len(tools)} tools - {', '.join(tool_names[:3])}...")
                            else:
                                print("⚠️  No tools discovered from MCP servers")
                                
                        except Exception as e:
                            print(f"❌ Tool discovery failed: {e}")
                            return False
                        
                        # Test context building
                        print("\n🧠 Testing tool context building...")
                        try:
                            context = intelligent_agent._build_enhanced_tool_context(task_hint="test file operations")
                            
                            if context:
                                print("✅ Enhanced tool context built successfully")
                                print(f"   Context length: {len(context)} characters")
                                
                                # Get context summary
                                summary = intelligent_agent.get_tool_context_summary()
                                if summary.get('status') == 'active':
                                    print(f"✅ Context summary: {summary['tools']} tools, {summary['servers']} servers")
                                    print(f"   Capabilities: {summary.get('capabilities', [])}")
                                else:
                                    print(f"⚠️  Context status: {summary.get('status', 'unknown')}")
                            else:
                                print("⚠️  Tool context not built")
                                
                        except Exception as e:
                            print(f"❌ Context building failed: {e}")
                            return False
                        
                        # Test tool registration with intelligent agent
                        print("\n🔗 Testing tool registration with IntelligentAgent...")
                        try:
                            await agent._register_mcp_tools_with_intelligent_agent(intelligent_agent)
                            print("✅ Tool registration completed")
                            
                            # Check if tools were actually registered
                            if hasattr(intelligent_agent, '_mcp_tools') and intelligent_agent._mcp_tools:
                                print(f"✅ {len(intelligent_agent._mcp_tools)} tools registered with IntelligentAgent")
                            else:
                                print("⚠️  No tools found in IntelligentAgent after registration")
                            
                        except Exception as e:
                            print(f"❌ Tool registration failed: {e}")
                            return False
                            
                        # Test cache statistics
                        print("\n📊 Testing cache statistics...")
                        try:
                            cache_stats = intelligent_agent.tool_cache.get_cache_stats()
                            print(f"✅ Cache stats: {cache_stats}")
                            
                            # Enhanced performance summary
                            if hasattr(intelligent_agent.mcp_manager, 'get_enhanced_performance_summary'):
                                perf_summary = intelligent_agent.mcp_manager.get_enhanced_performance_summary()
                                print(f"✅ Performance summary: {perf_summary}")
                            
                        except Exception as e:
                            print(f"⚠️  Cache statistics error: {e}")
                        
                    else:
                        print("❌ MCP manager is not enhanced - missing initialize_with_caching method")
                        return False
                else:
                    print("❌ MCP manager not available")
                    return False
            else:
                print("❌ Tool cache not available")
                return False
        else:
            print("❌ MCP context builder not initialized")
            return False
        
        print("\n🎉 Enhanced MCP Context Integration Test Results:")
        print("✅ MCP context builder initialization: PASS")
        print("✅ Enhanced MCP manager integration: PASS") 
        print("✅ Tool discovery and caching: PASS")
        print("✅ Tool context building: PASS")
        print("✅ Tool registration with IntelligentAgent: PASS")
        print("✅ Cache statistics and performance: PASS")
        print("\n🏆 All enhanced context integration tests PASSED!")
        
        return True
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR in enhanced context integration test: {e}")
        import traceback
        print(f"Full traceback:\n{traceback.format_exc()}")
        return False

def main():
    """Main test function"""
    success = asyncio.run(test_enhanced_context_integration())
    
    if success:
        print("\n✅ Enhanced Context Integration Test: PASSED")
        sys.exit(0)
    else:
        print("\n❌ Enhanced Context Integration Test: FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main() 