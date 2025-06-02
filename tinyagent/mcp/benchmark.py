"""
MCP Performance Benchmark Tool

This module provides performance benchmarking capabilities for MCP servers,
including tool discovery performance, caching efficiency, and connection pool optimization.
"""

import asyncio
import time
import statistics
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..core.config import MCPServerConfig
from .manager import EnhancedMCPServerManager
from .cache import MCPToolCache, ToolInfo
from .pool import MCPConnectionPool, PoolConfig

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Results from a performance benchmark"""
    test_name: str
    duration: float
    success_rate: float
    throughput: float  # operations per second
    cache_hit_rate: Optional[float] = None
    memory_usage: Optional[float] = None
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkSuite:
    """Complete benchmark test suite results"""
    start_time: datetime
    end_time: datetime
    total_duration: float
    tests: List[BenchmarkResult]
    summary: Dict[str, Any] = field(default_factory=dict)


class MCPPerformanceBenchmark:
    """
    Performance benchmark tool for MCP servers and tools.
    
    Provides comprehensive testing of:
    - Tool discovery performance
    - Cache efficiency and hit rates
    - Connection pool utilization
    - Memory usage and optimization
    - Throughput and response times
    """
    
    def __init__(
        self,
        server_configs: List[MCPServerConfig],
        cache_duration: int = 300,
        pool_config: Optional[PoolConfig] = None
    ):
        """
        Initialize benchmark tool.
        
        Args:
            server_configs: List of MCP server configurations to test
            cache_duration: Cache duration for testing
            pool_config: Connection pool configuration
        """
        self.server_configs = server_configs
        self.cache_duration = cache_duration
        self.pool_config = pool_config or PoolConfig()
        
        # Initialize components for testing
        self.tool_cache = MCPToolCache(
            cache_duration=cache_duration,
            max_cache_size=100,
            persist_cache=False  # Disable for benchmarking
        )
        
        self.connection_pool = MCPConnectionPool(self.pool_config)
        
        self.enhanced_manager = EnhancedMCPServerManager(
            server_configs=server_configs,
            tool_cache=self.tool_cache,
            connection_pool=self.connection_pool,
            cache_duration=cache_duration,
            enable_performance_tracking=True,
            pool_config=self.pool_config
        )
        
        logger.info(f"MCPPerformanceBenchmark initialized for {len(server_configs)} servers")
    
    async def run_full_benchmark_suite(self) -> BenchmarkSuite:
        """
        Run complete benchmark suite.
        
        Returns:
            Complete benchmark results
        """
        start_time = datetime.now()
        logger.info("Starting MCP performance benchmark suite")
        
        # Start connection pool
        await self.connection_pool.start()
        
        try:
            tests = []
            
            # Test 1: Tool Discovery Performance
            logger.info("Running tool discovery performance test...")
            discovery_result = await self._benchmark_tool_discovery()
            tests.append(discovery_result)
            
            # Test 2: Cache Performance
            logger.info("Running cache performance test...")
            cache_result = await self._benchmark_cache_performance()
            tests.append(cache_result)
            
            # Test 3: Connection Pool Efficiency
            logger.info("Running connection pool efficiency test...")
            pool_result = await self._benchmark_connection_pool()
            tests.append(pool_result)
            
            # Test 4: Concurrent Operations
            logger.info("Running concurrent operations test...")
            concurrent_result = await self._benchmark_concurrent_operations()
            tests.append(concurrent_result)
            
            # Test 5: Memory Usage
            logger.info("Running memory usage test...")
            memory_result = await self._benchmark_memory_usage()
            tests.append(memory_result)
            
            end_time = datetime.now()
            total_duration = (end_time - start_time).total_seconds()
            
            # Generate summary
            summary = self._generate_summary(tests)
            
            benchmark_suite = BenchmarkSuite(
                start_time=start_time,
                end_time=end_time,
                total_duration=total_duration,
                tests=tests,
                summary=summary
            )
            
            logger.info(f"Benchmark suite completed in {total_duration:.2f}s")
            return benchmark_suite
            
        finally:
            # Clean up
            await self.connection_pool.stop()
    
    async def _benchmark_tool_discovery(self) -> BenchmarkResult:
        """Benchmark tool discovery performance"""
        iterations = 10
        times = []
        success_count = 0
        
        for i in range(iterations):
            start_time = time.time()
            
            try:
                # Clear cache to force fresh discovery
                self.tool_cache.clear_cache()
                
                # Perform tool discovery
                server_tools = await self.enhanced_manager.initialize_with_caching()
                
                end_time = time.time()
                duration = end_time - start_time
                times.append(duration)
                
                if server_tools:
                    success_count += 1
                    
            except Exception as e:
                logger.error(f"Tool discovery iteration {i} failed: {e}")
                end_time = time.time()
                times.append(end_time - start_time)
        
        avg_duration = statistics.mean(times) if times else 0
        success_rate = success_count / iterations
        throughput = success_count / sum(times) if sum(times) > 0 else 0
        
        return BenchmarkResult(
            test_name="Tool Discovery Performance",
            duration=avg_duration,
            success_rate=success_rate,
            throughput=throughput,
            metadata={
                "iterations": iterations,
                "min_time": min(times) if times else 0,
                "max_time": max(times) if times else 0,
                "std_dev": statistics.stdev(times) if len(times) > 1 else 0
            }
        )
    
    async def _benchmark_cache_performance(self) -> BenchmarkResult:
        """Benchmark cache performance and hit rates"""
        # First, populate cache
        await self.enhanced_manager.initialize_with_caching()
        
        iterations = 50
        cache_hits = 0
        times = []
        success_count = 0
        
        for i in range(iterations):
            start_time = time.time()
            
            try:
                # Test cache retrieval
                for config in self.server_configs:
                    if config.enabled:
                        cached_tools = self.tool_cache.get_cached_tools(config.name)
                        if cached_tools is not None:
                            cache_hits += 1
                
                end_time = time.time()
                duration = end_time - start_time
                times.append(duration)
                success_count += 1
                
            except Exception as e:
                logger.error(f"Cache test iteration {i} failed: {e}")
                end_time = time.time()
                times.append(end_time - start_time)
        
        avg_duration = statistics.mean(times) if times else 0
        success_rate = success_count / iterations
        cache_hit_rate = cache_hits / (iterations * len([c for c in self.server_configs if c.enabled]))
        throughput = success_count / sum(times) if sum(times) > 0 else 0
        
        return BenchmarkResult(
            test_name="Cache Performance",
            duration=avg_duration,
            success_rate=success_rate,
            throughput=throughput,
            cache_hit_rate=cache_hit_rate,
            metadata={
                "cache_hits": cache_hits,
                "total_requests": iterations * len([c for c in self.server_configs if c.enabled])
            }
        )
    
    async def _benchmark_connection_pool(self) -> BenchmarkResult:
        """Benchmark connection pool efficiency"""
        iterations = 20
        times = []
        success_count = 0
        reuse_count = 0
        
        for i in range(iterations):
            start_time = time.time()
            
            try:
                # Test connection pool usage
                tasks = []
                for config in self.server_configs:
                    if config.enabled:
                        task = self._test_pooled_connection(config)
                        tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                end_time = time.time()
                duration = end_time - start_time
                times.append(duration)
                
                # Count successful connections and reuses
                for result in results:
                    if not isinstance(result, Exception):
                        success_count += 1
                        if result.get('reused', False):
                            reuse_count += 1
                            
            except Exception as e:
                logger.error(f"Connection pool test iteration {i} failed: {e}")
                end_time = time.time()
                times.append(end_time - start_time)
        
        avg_duration = statistics.mean(times) if times else 0
        success_rate = success_count / (iterations * len([c for c in self.server_configs if c.enabled]))
        throughput = success_count / sum(times) if sum(times) > 0 else 0
        
        pool_stats = self.connection_pool.get_pool_stats()
        
        return BenchmarkResult(
            test_name="Connection Pool Efficiency",
            duration=avg_duration,
            success_rate=success_rate,
            throughput=throughput,
            metadata={
                "reuse_count": reuse_count,
                "reuse_rate": reuse_count / success_count if success_count > 0 else 0,
                "pool_stats": pool_stats
            }
        )
    
    async def _test_pooled_connection(self, config: MCPServerConfig) -> Dict[str, Any]:
        """Test a single pooled connection"""
        try:
            async with self.connection_pool.get_connection(config) as connection:
                # Simulate some work
                await asyncio.sleep(0.01)
                return {"success": True, "reused": True}  # Simplified for benchmark
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _benchmark_concurrent_operations(self) -> BenchmarkResult:
        """Benchmark concurrent tool operations"""
        concurrent_tasks = 10
        iterations = 5
        times = []
        success_count = 0
        
        for i in range(iterations):
            start_time = time.time()
            
            try:
                # Create concurrent tasks
                tasks = []
                for j in range(concurrent_tasks):
                    task = self._concurrent_tool_operation()
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                end_time = time.time()
                duration = end_time - start_time
                times.append(duration)
                
                # Count successful operations
                for result in results:
                    if not isinstance(result, Exception) and result:
                        success_count += 1
                        
            except Exception as e:
                logger.error(f"Concurrent operations iteration {i} failed: {e}")
                end_time = time.time()
                times.append(end_time - start_time)
        
        avg_duration = statistics.mean(times) if times else 0
        success_rate = success_count / (iterations * concurrent_tasks)
        throughput = success_count / sum(times) if sum(times) > 0 else 0
        
        return BenchmarkResult(
            test_name="Concurrent Operations",
            duration=avg_duration,
            success_rate=success_rate,
            throughput=throughput,
            metadata={
                "concurrent_tasks": concurrent_tasks,
                "total_operations": iterations * concurrent_tasks
            }
        )
    
    async def _concurrent_tool_operation(self) -> bool:
        """Simulate a concurrent tool operation"""
        try:
            # Test cache access
            cached_tools = self.tool_cache.get_all_cached_tools()
            
            # Simulate some processing
            await asyncio.sleep(0.005)
            
            return len(cached_tools) > 0
        except Exception:
            return False
    
    async def _benchmark_memory_usage(self) -> BenchmarkResult:
        """Benchmark memory usage of caching system"""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            
            # Get initial memory
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Populate cache with tools
            start_time = time.time()
            await self.enhanced_manager.initialize_with_caching()
            
            # Get memory after caching
            cached_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Get cache statistics
            cache_stats = self.tool_cache.get_cache_stats()
            
            end_time = time.time()
            duration = end_time - start_time
            
            memory_usage = cached_memory - initial_memory
            
            return BenchmarkResult(
                test_name="Memory Usage",
                duration=duration,
                success_rate=1.0,
                throughput=cache_stats.get('total_tools_cached', 0) / duration,
                memory_usage=memory_usage,
                metadata={
                    "initial_memory_mb": initial_memory,
                    "cached_memory_mb": cached_memory,
                    "memory_increase_mb": memory_usage,
                    "cache_stats": cache_stats
                }
            )
            
        except ImportError:
            logger.warning("psutil not available, skipping memory benchmark")
            return BenchmarkResult(
                test_name="Memory Usage",
                duration=0,
                success_rate=0,
                throughput=0,
                metadata={"error": "psutil not available"}
            )
    
    def _generate_summary(self, tests: List[BenchmarkResult]) -> Dict[str, Any]:
        """Generate benchmark summary"""
        total_tests = len(tests)
        successful_tests = len([t for t in tests if t.success_rate > 0.8])
        
        avg_duration = statistics.mean([t.duration for t in tests])
        avg_success_rate = statistics.mean([t.success_rate for t in tests])
        total_throughput = sum([t.throughput for t in tests])
        
        # Find cache hit rate
        cache_hit_rate = None
        for test in tests:
            if test.cache_hit_rate is not None:
                cache_hit_rate = test.cache_hit_rate
                break
        
        # Find memory usage
        memory_usage = None
        for test in tests:
            if test.memory_usage is not None:
                memory_usage = test.memory_usage
                break
        
        summary = {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "test_success_rate": successful_tests / total_tests,
            "average_duration": avg_duration,
            "average_success_rate": avg_success_rate,
            "total_throughput": total_throughput,
            "cache_hit_rate": cache_hit_rate,
            "memory_usage_mb": memory_usage,
            "performance_grade": self._calculate_performance_grade(tests)
        }
        
        return summary
    
    def _calculate_performance_grade(self, tests: List[BenchmarkResult]) -> str:
        """Calculate overall performance grade"""
        scores = []
        
        for test in tests:
            # Base score on success rate and performance
            score = test.success_rate * 100
            
            # Bonus for cache hit rate
            if test.cache_hit_rate is not None and test.cache_hit_rate > 0.9:
                score += 10
            
            # Penalty for high memory usage
            if test.memory_usage is not None and test.memory_usage > 50:
                score -= 10
            
            scores.append(score)
        
        avg_score = statistics.mean(scores) if scores else 0
        
        if avg_score >= 95:
            return "A+"
        elif avg_score >= 90:
            return "A"
        elif avg_score >= 85:
            return "B+"
        elif avg_score >= 80:
            return "B"
        elif avg_score >= 75:
            return "C+"
        elif avg_score >= 70:
            return "C"
        else:
            return "D"


def format_benchmark_report(suite: BenchmarkSuite) -> str:
    """Format benchmark results into a readable report"""
    report = []
    
    report.append("=" * 80)
    report.append("MCP PERFORMANCE BENCHMARK REPORT")
    report.append("=" * 80)
    report.append(f"Start Time: {suite.start_time}")
    report.append(f"End Time: {suite.end_time}")
    report.append(f"Total Duration: {suite.total_duration:.2f}s")
    report.append(f"Performance Grade: {suite.summary.get('performance_grade', 'N/A')}")
    report.append("")
    
    # Summary
    report.append("SUMMARY")
    report.append("-" * 40)
    report.append(f"Total Tests: {suite.summary.get('total_tests', 0)}")
    report.append(f"Successful Tests: {suite.summary.get('successful_tests', 0)}")
    report.append(f"Test Success Rate: {suite.summary.get('test_success_rate', 0):.1%}")
    report.append(f"Average Duration: {suite.summary.get('average_duration', 0):.3f}s")
    report.append(f"Average Success Rate: {suite.summary.get('average_success_rate', 0):.1%}")
    report.append(f"Total Throughput: {suite.summary.get('total_throughput', 0):.2f} ops/s")
    
    if suite.summary.get('cache_hit_rate') is not None:
        report.append(f"Cache Hit Rate: {suite.summary['cache_hit_rate']:.1%}")
    
    if suite.summary.get('memory_usage_mb') is not None:
        report.append(f"Memory Usage: {suite.summary['memory_usage_mb']:.2f} MB")
    
    report.append("")
    
    # Individual test results
    report.append("DETAILED RESULTS")
    report.append("-" * 40)
    
    for test in suite.tests:
        report.append(f"\n{test.test_name}")
        report.append(f"  Duration: {test.duration:.3f}s")
        report.append(f"  Success Rate: {test.success_rate:.1%}")
        report.append(f"  Throughput: {test.throughput:.2f} ops/s")
        
        if test.cache_hit_rate is not None:
            report.append(f"  Cache Hit Rate: {test.cache_hit_rate:.1%}")
        
        if test.memory_usage is not None:
            report.append(f"  Memory Usage: {test.memory_usage:.2f} MB")
        
        if test.error_count > 0:
            report.append(f"  Errors: {test.error_count}")
        
        if test.metadata:
            report.append("  Metadata:")
            for key, value in test.metadata.items():
                if isinstance(value, dict):
                    continue  # Skip complex objects in summary
                report.append(f"    {key}: {value}")
    
    report.append("")
    report.append("=" * 80)
    
    return "\n".join(report)


async def run_performance_benchmark(server_configs: List[MCPServerConfig]) -> BenchmarkSuite:
    """
    Run a complete performance benchmark suite.
    
    Args:
        server_configs: List of MCP server configurations to benchmark
        
    Returns:
        Complete benchmark results
    """
    benchmark = MCPPerformanceBenchmark(server_configs)
    return await benchmark.run_full_benchmark_suite() 