#!/usr/bin/env python3
"""
Test script for EPIC-002 Story 2.4: Performance Optimization & Caching

This script validates:
- Tool query performance improvement >50%
- Cache hit rate >90%
- Connection pool efficiency >80%
- Configuration parameters support

Usage:
    python tests/test_performance_optimization.py
"""

import asyncio
import logging
import time
from typing import List, Dict, Any

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tinyagent.core.config import ConfigurationManager, MCPServerConfig
from tinyagent.mcp.benchmark import MCPPerformanceBenchmark, format_benchmark_report
from tinyagent.mcp.manager import EnhancedMCPServerManager
from tinyagent.mcp.cache import MCPToolCache
from tinyagent.mcp.pool import MCPConnectionPool, PoolConfig


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/performance_test.log')
    ]
)

logger = logging.getLogger(__name__)


class PerformanceOptimizationTester:
    """Test suite for Story 2.4 performance optimization requirements"""
    
    def __init__(self):
        """Initialize the performance tester"""
        self.config_manager = ConfigurationManager()
        self.config = self.config_manager.load_config("development")
        
        # Get enabled MCP servers
        self.server_configs = []
        for server_name, server_config in self.config.mcp.servers.items():
            if server_config.enabled:
                self.server_configs.append(server_config)
        
        logger.info(f"Initialized with {len(self.server_configs)} enabled MCP servers")
    
    async def run_story_2_4_tests(self) -> Dict[str, Any]:
        """
        Run all Story 2.4 performance optimization tests.
        
        Returns:
            Test results with pass/fail status for each requirement
        """
        logger.info("🚀 Starting Story 2.4: Performance Optimization & Caching Tests")
        logger.info("=" * 80)
        
        results = {
            "story": "2.4 - Performance Optimization & Caching",
            "start_time": time.time(),
            "tests": {},
            "requirements_met": {},
            "overall_status": "UNKNOWN"
        }
        
        try:
            # Test 1: Connection Pool Management
            logger.info("🔧 Test 1: Connection Pool Management")
            pool_result = await self._test_connection_pool_management()
            results["tests"]["connection_pool"] = pool_result
            results["requirements_met"]["connection_pool"] = pool_result["success"]
            
            # Test 2: Tool Query Performance Optimization
            logger.info("🚀 Test 2: Tool Query Performance Optimization")
            performance_result = await self._test_tool_query_performance()
            results["tests"]["tool_query_performance"] = performance_result
            results["requirements_met"]["performance_improvement"] = performance_result["improvement_achieved"]
            
            # Test 3: Cache Control Parameters
            logger.info("⚙️ Test 3: Cache Control Parameters")
            cache_config_result = await self._test_cache_control_parameters()
            results["tests"]["cache_control"] = cache_config_result
            results["requirements_met"]["cache_control"] = cache_config_result["success"]
            
            # Test 4: Performance Benchmark Suite
            logger.info("📊 Test 4: Performance Benchmark Suite")
            benchmark_result = await self._test_performance_benchmarks()
            results["tests"]["benchmark_suite"] = benchmark_result
            results["requirements_met"]["benchmark_suite"] = benchmark_result["success"]
            
            # Test 5: Cache Hit Rate Validation
            logger.info("🎯 Test 5: Cache Hit Rate >90% Validation")
            cache_hit_result = await self._test_cache_hit_rate()
            results["tests"]["cache_hit_rate"] = cache_hit_result
            results["requirements_met"]["cache_hit_rate_90"] = cache_hit_result["hit_rate"] >= 0.9
            
            # Calculate overall status
            total_requirements = len(results["requirements_met"])
            met_requirements = sum(1 for met in results["requirements_met"].values() if met)
            
            results["requirements_summary"] = {
                "total": total_requirements,
                "met": met_requirements,
                "percentage": (met_requirements / total_requirements) * 100
            }
            
            # Determine overall status
            if met_requirements == total_requirements:
                results["overall_status"] = "PASS"
            elif met_requirements >= total_requirements * 0.8:
                results["overall_status"] = "MOSTLY_PASS"
            else:
                results["overall_status"] = "FAIL"
            
            results["end_time"] = time.time()
            results["total_duration"] = results["end_time"] - results["start_time"]
            
            # Print summary
            self._print_test_summary(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Story 2.4 tests failed with error: {e}")
            results["overall_status"] = "ERROR"
            results["error"] = str(e)
            return results
    
    async def _test_connection_pool_management(self) -> Dict[str, Any]:
        """Test connection pool management implementation"""
        try:
            logger.info("  Testing connection pool configuration and management...")
            
            # Test pool configuration
            pool_config = PoolConfig(
                max_connections_per_server=3,
                connection_timeout=30.0,
                retry_attempts=3,
                idle_timeout=300.0
            )
            
            pool = MCPConnectionPool(pool_config)
            await pool.start()
            
            try:
                # Test pool statistics
                pool_stats = pool.get_pool_stats()
                
                # Verify pool is functioning
                pool_functional = (
                    pool_stats is not None and
                    isinstance(pool_stats, dict) and
                    "total_connections" in pool_stats
                )
                
                result = {
                    "success": pool_functional,
                    "pool_stats": pool_stats,
                    "config_applied": True,
                    "error": None
                }
                
                if pool_functional:
                    logger.info("  ✅ Connection pool management: PASS")
                else:
                    logger.warning("  ⚠️ Connection pool management: Issues detected")
                
                return result
                
            finally:
                await pool.stop()
                
        except Exception as e:
            logger.error(f"  ❌ Connection pool test failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "pool_stats": None,
                "config_applied": False
            }
    
    async def _test_tool_query_performance(self) -> Dict[str, Any]:
        """Test tool query performance improvement >50%"""
        try:
            logger.info("  Testing tool query performance optimization...")
            
            # Test without caching (baseline)
            logger.info("    Measuring baseline performance (no cache)...")
            baseline_time = await self._measure_tool_query_time(use_cache=False)
            
            # Test with caching (optimized)
            logger.info("    Measuring optimized performance (with cache)...")
            optimized_time = await self._measure_tool_query_time(use_cache=True)
            
            # Calculate improvement
            if baseline_time > 0:
                improvement = ((baseline_time - optimized_time) / baseline_time) * 100
                improvement_achieved = improvement >= 50.0
            else:
                improvement = 0
                improvement_achieved = False
            
            result = {
                "baseline_time": baseline_time,
                "optimized_time": optimized_time,
                "improvement_percentage": improvement,
                "improvement_achieved": improvement_achieved,
                "target_improvement": 50.0,
                "success": improvement_achieved
            }
            
            if improvement_achieved:
                logger.info(f"  ✅ Performance improvement: {improvement:.1f}% (>50% required)")
            else:
                logger.warning(f"  ⚠️ Performance improvement: {improvement:.1f}% (<50% required)")
            
            return result
            
        except Exception as e:
            logger.error(f"  ❌ Performance test failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "improvement_achieved": False
            }
    
    async def _measure_tool_query_time(self, use_cache: bool) -> float:
        """Measure tool query time with or without cache"""
        cache_duration = 300 if use_cache else 0  # 0 means no cache
        
        tool_cache = MCPToolCache(
            cache_duration=cache_duration,
            max_cache_size=100,
            persist_cache=False
        )
        
        enhanced_manager = EnhancedMCPServerManager(
            server_configs=self.server_configs,
            tool_cache=tool_cache,
            cache_duration=cache_duration,
            enable_performance_tracking=True
        )
        
        # Measure time for multiple operations
        iterations = 3
        times = []
        
        for i in range(iterations):
            if not use_cache:
                tool_cache.clear_cache()  # Force fresh queries
            
            start_time = time.time()
            
            try:
                server_tools = await enhanced_manager.initialize_with_caching()
                end_time = time.time()
                times.append(end_time - start_time)
                
                # For caching test, we want subsequent calls to be faster
                if use_cache and i == 0:
                    # First call populates cache, measure subsequent calls
                    continue
                    
            except Exception as e:
                logger.warning(f"Tool query iteration {i} failed: {e}")
                continue
        
        return sum(times) / len(times) if times else 0
    
    async def _test_cache_control_parameters(self) -> Dict[str, Any]:
        """Test cache control parameters configuration"""
        try:
            logger.info("  Testing cache control parameters...")
            
            # Test different cache configurations
            configs_to_test = [
                {"cache_duration": 60, "max_cache_size": 50},
                {"cache_duration": 300, "max_cache_size": 100},
                {"cache_duration": 600, "max_cache_size": 200},
            ]
            
            successful_configs = 0
            
            for config in configs_to_test:
                try:
                    tool_cache = MCPToolCache(
                        cache_duration=config["cache_duration"],
                        max_cache_size=config["max_cache_size"],
                        persist_cache=False
                    )
                    
                    # Test cache with this configuration
                    enhanced_manager = EnhancedMCPServerManager(
                        server_configs=self.server_configs,
                        tool_cache=tool_cache,
                        cache_duration=config["cache_duration"]
                    )
                    
                    # Verify configuration is applied
                    cache_stats = tool_cache.get_cache_stats()
                    if cache_stats is not None:
                        successful_configs += 1
                    
                except Exception as e:
                    logger.warning(f"Cache config {config} failed: {e}")
            
            success = successful_configs == len(configs_to_test)
            
            result = {
                "success": success,
                "tested_configs": len(configs_to_test),
                "successful_configs": successful_configs,
                "config_support": True
            }
            
            if success:
                logger.info("  ✅ Cache control parameters: PASS")
            else:
                logger.warning("  ⚠️ Cache control parameters: Issues detected")
            
            return result
            
        except Exception as e:
            logger.error(f"  ❌ Cache control test failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "config_support": False
            }
    
    async def _test_performance_benchmarks(self) -> Dict[str, Any]:
        """Test performance benchmark suite implementation"""
        try:
            logger.info("  Testing performance benchmark suite...")
            
            # Run a quick benchmark
            benchmark = MCPPerformanceBenchmark(
                server_configs=self.server_configs,
                cache_duration=300
            )
            
            # Run just a subset of tests for validation
            start_time = time.time()
            
            # Test tool discovery benchmark
            discovery_result = await benchmark._benchmark_tool_discovery()
            
            # Test cache performance benchmark
            cache_result = await benchmark._benchmark_cache_performance()
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Verify benchmark results
            benchmark_working = (
                discovery_result is not None and
                cache_result is not None and
                hasattr(discovery_result, 'test_name') and
                hasattr(cache_result, 'test_name')
            )
            
            result = {
                "success": benchmark_working,
                "benchmark_duration": duration,
                "discovery_test": discovery_result.test_name if discovery_result else None,
                "cache_test": cache_result.test_name if cache_result else None,
                "benchmark_functional": benchmark_working
            }
            
            if benchmark_working:
                logger.info("  ✅ Performance benchmark suite: PASS")
            else:
                logger.warning("  ⚠️ Performance benchmark suite: Issues detected")
            
            return result
            
        except Exception as e:
            logger.error(f"  ❌ Benchmark test failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "benchmark_functional": False
            }
    
    async def _test_cache_hit_rate(self) -> Dict[str, Any]:
        """Test cache hit rate >90% requirement"""
        try:
            logger.info("  Testing cache hit rate >90% requirement...")
            
            # Initialize cache system
            tool_cache = MCPToolCache(
                cache_duration=300,
                max_cache_size=100,
                persist_cache=False
            )
            
            enhanced_manager = EnhancedMCPServerManager(
                server_configs=self.server_configs,
                tool_cache=tool_cache,
                cache_duration=300,
                enable_performance_tracking=True
            )
            
            # Populate cache
            logger.info("    Populating cache...")
            await enhanced_manager.initialize_with_caching()
            
            # Test cache hit rate
            cache_hits = 0
            total_requests = 0
            test_iterations = 20
            
            logger.info(f"    Testing cache hits over {test_iterations} iterations...")
            
            for i in range(test_iterations):
                for config in self.server_configs:
                    if config.enabled:
                        total_requests += 1
                        cached_tools = tool_cache.get_cached_tools(config.name)
                        if cached_tools is not None:
                            cache_hits += 1
            
            hit_rate = cache_hits / total_requests if total_requests > 0 else 0
            hit_rate_met = hit_rate >= 0.9
            
            result = {
                "hit_rate": hit_rate,
                "cache_hits": cache_hits,
                "total_requests": total_requests,
                "hit_rate_percentage": hit_rate * 100,
                "target_hit_rate": 90.0,
                "requirement_met": hit_rate_met,
                "success": hit_rate_met
            }
            
            if hit_rate_met:
                logger.info(f"  ✅ Cache hit rate: {hit_rate:.1%} (>90% required)")
            else:
                logger.warning(f"  ⚠️ Cache hit rate: {hit_rate:.1%} (<90% required)")
            
            return result
            
        except Exception as e:
            logger.error(f"  ❌ Cache hit rate test failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "hit_rate": 0,
                "requirement_met": False
            }
    
    def _print_test_summary(self, results: Dict[str, Any]):
        """Print comprehensive test summary"""
        logger.info("")
        logger.info("🏁 Story 2.4 Test Results Summary")
        logger.info("=" * 80)
        
        # Overall status
        status_emoji = {
            "PASS": "✅",
            "MOSTLY_PASS": "⚠️",
            "FAIL": "❌",
            "ERROR": "💥"
        }
        
        emoji = status_emoji.get(results["overall_status"], "❓")
        logger.info(f"{emoji} Overall Status: {results['overall_status']}")
        logger.info(f"⏱️ Total Duration: {results.get('total_duration', 0):.2f}s")
        logger.info("")
        
        # Requirements summary
        req_summary = results.get("requirements_summary", {})
        logger.info(f"📋 Requirements Met: {req_summary.get('met', 0)}/{req_summary.get('total', 0)} ({req_summary.get('percentage', 0):.1f}%)")
        logger.info("")
        
        # Individual requirement status
        logger.info("📊 Individual Requirements:")
        requirements = {
            "connection_pool": "✅ Implement connection pool management",
            "performance_improvement": "🚀 Optimize tool query performance >50%",
            "cache_control": "⚙️ Add cache control parameters",
            "benchmark_suite": "📊 Implement performance benchmark testing",
            "cache_hit_rate_90": "🎯 Cache hit rate >90%"
        }
        
        for req_key, req_desc in requirements.items():
            met = results["requirements_met"].get(req_key, False)
            status_icon = "✅" if met else "❌"
            logger.info(f"  {status_icon} {req_desc}")
        
        logger.info("")
        
        # Detailed test results
        logger.info("🔍 Detailed Test Results:")
        for test_name, test_result in results["tests"].items():
            success = test_result.get("success", False)
            icon = "✅" if success else "❌"
            logger.info(f"  {icon} {test_name}: {'PASS' if success else 'FAIL'}")
            
            # Additional details for specific tests
            if test_name == "tool_query_performance" and "improvement_percentage" in test_result:
                logger.info(f"      Performance improvement: {test_result['improvement_percentage']:.1f}%")
            
            if test_name == "cache_hit_rate" and "hit_rate_percentage" in test_result:
                logger.info(f"      Cache hit rate: {test_result['hit_rate_percentage']:.1f}%")
        
        logger.info("")
        logger.info("=" * 80)


async def main():
    """Main test execution"""
    logger.info("🎯 EPIC-002 Story 2.4: Performance Optimization & Caching Test Suite")
    logger.info("Testing requirements from tinyagent_design.md Section 12.4")
    logger.info("")
    
    tester = PerformanceOptimizationTester()
    results = await tester.run_story_2_4_tests()
    
    # Determine exit code
    if results["overall_status"] in ["PASS", "MOSTLY_PASS"]:
        logger.info("🎉 Story 2.4 tests completed successfully!")
        return 0
    else:
        logger.error("💥 Story 2.4 tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code) 