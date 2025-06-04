"""
Result Observer Module for TinyAgent Intelligence System
Implements intelligent result observation, validation, and learning.
"""

import logging
import time
from typing import List, Dict, Any, Optional, Set, Union
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ObservationLevel(Enum):
    """Level of observation detail"""
    BASIC = "basic"
    DETAILED = "detailed"
    COMPREHENSIVE = "comprehensive"


class SuccessPattern(Enum):
    """Types of success patterns"""
    QUICK_SUCCESS = "quick_success"
    ITERATIVE_SUCCESS = "iterative_success"
    COMEBACK_SUCCESS = "comeback_success"
    EXPECTED_SUCCESS = "expected_success"


class FailurePattern(Enum):
    """Types of failure patterns"""
    TIMEOUT_FAILURE = "timeout_failure"
    VALIDATION_FAILURE = "validation_failure"
    RESOURCE_FAILURE = "resource_failure"
    LOGIC_FAILURE = "logic_failure"


@dataclass
class Observation:
    """Represents an observation about execution results"""
    observation_id: str
    action_id: str
    result: Any
    success_assessment: bool
    confidence: float
    insights: List[str]
    improvement_suggestions: List[str]
    patterns_detected: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    observation_level: ObservationLevel = ObservationLevel.BASIC


@dataclass
class LearningInsight:
    """Represents a learning insight from observations"""
    insight_id: str
    category: str
    description: str
    confidence: float
    frequency: int
    first_observed: float
    last_observed: float
    supporting_observations: List[str] = field(default_factory=list)


@dataclass
class PerformancePattern:
    """Represents a performance pattern"""
    pattern_id: str
    pattern_type: Union[SuccessPattern, FailurePattern]
    description: str
    frequency: int
    average_duration: float
    success_rate: float
    conditions: Dict[str, Any] = field(default_factory=dict)


class ResultObserver:
    """
    Intelligent Result Observer and Learning Engine
    
    This observer provides sophisticated result analysis capabilities including:
    - Result validation and quality assessment
    - Success and failure pattern recognition
    - Learning from execution outcomes and feedback loops
    - Performance insight generation and trend analysis
    - Continuous improvement suggestions based on historical data
    """
    
    def __init__(self, observation_level: ObservationLevel = ObservationLevel.DETAILED, llm_agent=None):
        """
        Initialize ResultObserver
        
        Args:
            observation_level: Level of detail for observations
            llm_agent: LLM agent for enhanced insight generation (required)
        """
        self.observation_level = observation_level
        self.llm_agent = llm_agent
        self.observations: Dict[str, Observation] = {}
        self.learning_insights: Dict[str, LearningInsight] = {}
        self.performance_patterns: Dict[str, PerformancePattern] = {}
        
        # Learning state
        self.observed_actions: Set[str] = set()
        self.success_count = 0
        self.failure_count = 0
        self.total_observation_time = 0.0
        
        # Pattern tracking
        self.action_outcomes: Dict[str, List[bool]] = {}  # action_name -> [success, success, fail, ...]
        self.execution_times: Dict[str, List[float]] = {}  # action_name -> [time1, time2, ...]
        
        logger.info(f"ResultObserver initialized with observation_level={observation_level.value}, llm_enabled={llm_agent is not None}")
    
    async def observe_result(self, action_id: str, result: Any, 
                           expected_outcome: Optional[str] = None,
                           execution_time: Optional[float] = None,
                           action_name: Optional[str] = None) -> Observation:
        """
        Observe and analyze action result
        
        Args:
            action_id: ID of the action that was executed
            result: Result from action execution
            expected_outcome: Expected outcome description
            execution_time: Time taken to execute the action
            action_name: Name of the action for pattern analysis
            
        Returns:
            Observation with analysis and insights
        """
        logger.info(f"Observing result for action: {action_id}")
        start_time = time.time()
        
        # Generate unique observation ID
        observation_id = f"obs_{action_id}_{int(time.time() * 1000)}"
        
        # Assess success
        success_assessment = self._assess_success(result, expected_outcome)
        
        # Calculate confidence in assessment
        confidence = self._calculate_confidence(result, success_assessment, expected_outcome)
        
        # Generate insights
        insights = await self._generate_insights(result, success_assessment, action_name, execution_time)
        
        # Generate improvement suggestions
        improvements = await self._generate_improvements(result, success_assessment, action_id, action_name)
        
        # Detect patterns
        patterns = self._detect_patterns(result, success_assessment, action_name, execution_time)
        
        # Calculate performance metrics
        metrics = self._calculate_performance_metrics(result, execution_time, success_assessment)
        
        # Create observation
        observation = Observation(
            observation_id=observation_id,
            action_id=action_id,
            result=result,
            success_assessment=success_assessment,
            confidence=confidence,
            insights=insights,
            improvement_suggestions=improvements,
            patterns_detected=patterns,
            performance_metrics=metrics,
            observation_level=self.observation_level
        )
        
        # Store observation
        self.observations[observation_id] = observation
        
        # Update learning state
        await self._update_learning_state(observation, action_name, execution_time)
        
        observation_duration = time.time() - start_time
        self.total_observation_time += observation_duration
        
        logger.info(f"Observation completed for {action_id}: success={success_assessment}, confidence={confidence:.2f}")
        
        return observation
    
    def _assess_success(self, result: Any, expected_outcome: Optional[str] = None) -> bool:
        """Assess if the result indicates success"""
        if result is None:
            return False
        
        # Check for explicit success indicators
        if isinstance(result, dict):
            # Look for success indicators in dictionary results
            if "success" in result:
                return bool(result["success"])
            if "status" in result:
                return result["status"] in ["completed", "success", "ok"]
            if "error" in result:
                return not bool(result["error"])
            if "confidence" in result:
                return float(result["confidence"]) > 0.5
            
            # Non-empty dictionary with reasonable content
            return len(result) > 0 and any(v for v in result.values() if v is not None)
        
        elif isinstance(result, str):
            # Check string content for success indicators
            result_lower = result.lower()
            success_words = ["success", "completed", "done", "finished", "created", "found", "analyzed"]
            failure_words = ["error", "failed", "timeout", "invalid", "not found", "exception"]
            
            has_success = any(word in result_lower for word in success_words)
            has_failure = any(word in result_lower for word in failure_words)
            
            if has_failure:
                return False
            if has_success:
                return True
            
            # Non-empty string is generally positive
            return len(result.strip()) > 0
        
        elif isinstance(result, (list, tuple)):
            # Non-empty collection
            return len(result) > 0
        
        elif isinstance(result, bool):
            return result
        
        elif isinstance(result, (int, float)):
            # Positive numbers are generally good
            return result > 0
        
        # Default: if we have a result, it's probably success
        return True
    
    def _calculate_confidence(self, result: Any, success: bool, expected: Optional[str] = None) -> float:
        """Calculate confidence in the success assessment"""
        base_confidence = 0.5
        
        # Explicit indicators increase confidence
        if isinstance(result, dict):
            if "confidence" in result:
                return min(0.95, float(result["confidence"]))
            if "success" in result or "status" in result:
                base_confidence = 0.8
            elif "error" in result:
                base_confidence = 0.9  # High confidence in failure
        
        # String results with clear indicators
        elif isinstance(result, str) and result:
            result_lower = result.lower()
            clear_indicators = ["success", "completed", "error", "failed", "done"]
            if any(word in result_lower for word in clear_indicators):
                base_confidence = 0.85
        
        # Boolean results are very confident
        elif isinstance(result, bool):
            base_confidence = 0.95
        
        # Expected outcome matching
        if expected and isinstance(result, str):
            if expected.lower() in result.lower() or result.lower() in expected.lower():
                base_confidence = min(0.9, base_confidence + 0.2)
        
        return base_confidence
    
    async def _generate_insights(self, result: Any, success: bool, action_name: Optional[str] = None, 
                                execution_time: Optional[float] = None) -> List[str]:
        """Generate insights from the result using LLM"""
        if not self.llm_agent:
            raise ValueError("LLM agent is required for insight generation but not provided")
            
        try:
            from agents import Runner
            result_summary = str(result)[:500]  # Limit result size
            prompt = f"""Analyze this action execution result and provide 3-5 key insights:
            
Action Name: {action_name or 'Unknown'}
Success: {success}
Execution Time: {execution_time:.2f}s if provided else 'N/A'
Result: {result_summary}

Provide insights about:
1. Success/failure factors
2. Performance characteristics  
3. Result quality indicators
4. Patterns or trends
5. Areas for improvement

Format as bullet points."""
            
            llm_result = await Runner.run(self.llm_agent, prompt)
            llm_insights = llm_result.final_output.strip()
            
            # Parse LLM insights into list
            insights = []
            if llm_insights:
                for line in llm_insights.split('\n'):
                    line = line.strip()
                    if line and (line.startswith('•') or line.startswith('-') or line.startswith('*')):
                        insights.append(line.lstrip('•-* '))
            
            # Ensure we have at least some insights
            if not insights:
                insights = ["LLM analysis completed", "Result processed successfully"]
                
            return insights
            
        except Exception as e:
            logger.error(f"LLM insight generation failed: {e}")
            raise
    
    async def _generate_improvements(self, result: Any, success: bool, action_id: str, 
                                   action_name: Optional[str] = None) -> List[str]:
        """Generate improvement suggestions"""
        improvements = []
        
        if not success:
            improvements.append("Consider adding validation checks before execution")
            improvements.append("Implement retry mechanism for failed actions")
            
            # Specific failure analysis
            if isinstance(result, str):
                result_lower = result.lower()
                if "timeout" in result_lower:
                    improvements.append("Increase timeout duration or optimize processing speed")
                elif "invalid" in result_lower or "error" in result_lower:
                    improvements.append("Add input validation and error handling")
                elif "not found" in result_lower:
                    improvements.append("Implement fallback strategies for missing resources")
        
        # Performance improvements
        if action_name and action_name in self.execution_times:
            times = self.execution_times[action_name]
            if len(times) >= 3:
                avg_time = sum(times) / len(times)
                if avg_time > 10.0:
                    improvements.append(f"Optimize '{action_name}' performance - average execution time is {avg_time:.1f}s")
        
        # Pattern-based improvements
        if action_name and action_name in self.action_outcomes:
            outcomes = self.action_outcomes[action_name]
            if len(outcomes) >= 5:
                success_rate = sum(outcomes) / len(outcomes)
                if success_rate < 0.7:
                    improvements.append(f"Investigate root cause of {action_name} failures (success rate: {success_rate:.1%})")
        
        # General improvements based on observation level
        if self.observation_level == ObservationLevel.COMPREHENSIVE:
            improvements.append("Consider implementing A/B testing for action variants")
            improvements.append("Add detailed logging for debugging purposes")
        
        return improvements
    
    def _detect_patterns(self, result: Any, success: bool, action_name: Optional[str] = None, 
                        execution_time: Optional[float] = None) -> List[str]:
        """Detect patterns in the results"""
        patterns = []
        
        # Quick success pattern
        if success and execution_time and execution_time < 2.0:
            patterns.append("quick_success")
        
        # Slow success pattern
        if success and execution_time and execution_time > 10.0:
            patterns.append("slow_success")
        
        # High confidence pattern
        if isinstance(result, dict) and "confidence" in result:
            conf = float(result["confidence"])
            if conf > 0.9:
                patterns.append("high_confidence")
            elif conf < 0.3:
                patterns.append("low_confidence")
        
        # Action-specific patterns
        if action_name:
            if action_name.startswith("search"):
                if isinstance(result, dict) and "sources" in result:
                    sources = result["sources"]
                    if isinstance(sources, list) and len(sources) > 5:
                        patterns.append("comprehensive_search")
            elif action_name.startswith("analyze"):
                if isinstance(result, dict) and "insights" in result:
                    patterns.append("analytical_output")
        
        return patterns
    
    def _calculate_performance_metrics(self, result: Any, execution_time: Optional[float], 
                                     success: bool) -> Dict[str, float]:
        """Calculate performance metrics"""
        metrics = {}
        
        if execution_time:
            metrics["execution_time"] = execution_time
            metrics["execution_speed"] = 1.0 / execution_time if execution_time > 0 else 0.0
        
        metrics["success_score"] = 1.0 if success else 0.0
        
        # Result quality metrics
        if isinstance(result, dict):
            metrics["result_completeness"] = len(result) / 10.0  # Normalize to 0-1 scale
            
            if "confidence" in result:
                metrics["confidence_score"] = float(result["confidence"])
            
            if "sources" in result and isinstance(result["sources"], list):
                metrics["source_diversity"] = min(1.0, len(result["sources"]) / 3.0)
        
        elif isinstance(result, str):
            metrics["result_length"] = len(result)
            metrics["result_completeness"] = min(1.0, len(result) / 100.0)
        
        return metrics
    
    async def _update_learning_state(self, observation: Observation, action_name: Optional[str], 
                                   execution_time: Optional[float]):
        """Update internal learning state"""
        self.observed_actions.add(observation.action_id)
        
        if observation.success_assessment:
            self.success_count += 1
        else:
            self.failure_count += 1
        
        # Track action-specific patterns
        if action_name:
            if action_name not in self.action_outcomes:
                self.action_outcomes[action_name] = []
            self.action_outcomes[action_name].append(observation.success_assessment)
            
            if execution_time:
                if action_name not in self.execution_times:
                    self.execution_times[action_name] = []
                self.execution_times[action_name].append(execution_time)
        
        # Generate learning insights
        await self._generate_learning_insights(observation, action_name)
    
    async def _generate_learning_insights(self, observation: Observation, action_name: Optional[str]):
        """Generate and update learning insights"""
        # Success rate insights
        total_observations = self.success_count + self.failure_count
        if total_observations >= 10:
            success_rate = self.success_count / total_observations
            
            insight_id = "overall_success_rate"
            if success_rate > 0.8:
                description = f"High overall success rate: {success_rate:.1%}"
            elif success_rate < 0.6:
                description = f"Low overall success rate: {success_rate:.1%} - needs attention"
            else:
                description = f"Moderate success rate: {success_rate:.1%}"
            
            self.learning_insights[insight_id] = LearningInsight(
                insight_id=insight_id,
                category="performance",
                description=description,
                confidence=min(0.95, total_observations / 50.0),
                frequency=total_observations,
                first_observed=time.time(),
                last_observed=time.time()
            )
        
        # Action-specific insights
        if action_name and action_name in self.action_outcomes:
            outcomes = self.action_outcomes[action_name]
            if len(outcomes) >= 5:
                action_success_rate = sum(outcomes) / len(outcomes)
                insight_id = f"{action_name}_pattern"
                
                if action_success_rate > 0.9:
                    description = f"'{action_name}' is highly reliable ({action_success_rate:.1%} success)"
                elif action_success_rate < 0.5:
                    description = f"'{action_name}' needs improvement ({action_success_rate:.1%} success)"
                else:
                    description = f"'{action_name}' shows moderate reliability ({action_success_rate:.1%} success)"
                
                self.learning_insights[insight_id] = LearningInsight(
                    insight_id=insight_id,
                    category="action_reliability",
                    description=description,
                    confidence=min(0.9, len(outcomes) / 20.0),
                    frequency=len(outcomes),
                    first_observed=time.time(),
                    last_observed=time.time()
                )
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """Get a summary of learning insights"""
        total_observations = len(self.observations)
        success_rate = (self.success_count / (self.success_count + self.failure_count)) if (self.success_count + self.failure_count) > 0 else 0
        
        return {
            "total_observations": total_observations,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "overall_success_rate": success_rate,
            "observed_actions": len(self.observed_actions),
            "learning_insights": len(self.learning_insights),
            "performance_patterns": len(self.performance_patterns),
            "total_observation_time": self.total_observation_time
        }
    
    def get_insights_by_category(self, category: str) -> List[LearningInsight]:
        """Get learning insights by category"""
        return [insight for insight in self.learning_insights.values() if insight.category == category]
    
    def get_action_performance(self, action_name: str) -> Optional[Dict[str, Any]]:
        """Get performance summary for a specific action"""
        if action_name not in self.action_outcomes:
            return None
        
        outcomes = self.action_outcomes[action_name]
        times = self.execution_times.get(action_name, [])
        
        performance = {
            "action_name": action_name,
            "total_executions": len(outcomes),
            "success_count": sum(outcomes),
            "failure_count": len(outcomes) - sum(outcomes),
            "success_rate": sum(outcomes) / len(outcomes),
        }
        
        if times:
            performance.update({
                "average_execution_time": sum(times) / len(times),
                "min_execution_time": min(times),
                "max_execution_time": max(times),
                "total_execution_time": sum(times)
            })
        
        return performance
    
    def get_top_insights(self, limit: int = 5) -> List[LearningInsight]:
        """Get top insights sorted by confidence and frequency"""
        insights = list(self.learning_insights.values())
        insights.sort(key=lambda x: (x.confidence * x.frequency), reverse=True)
        return insights[:limit]
    
    def clear_observations(self, older_than_hours: Optional[float] = None):
        """Clear observations, optionally only older than specified hours"""
        if older_than_hours:
            cutoff_time = time.time() - (older_than_hours * 3600)
            to_remove = [obs_id for obs_id, obs in self.observations.items() 
                        if obs.timestamp < cutoff_time]
            for obs_id in to_remove:
                del self.observations[obs_id]
            logger.info(f"Cleared {len(to_remove)} observations older than {older_than_hours} hours")
        else:
            self.observations.clear()
            logger.info("Cleared all observations")

    async def observe_result_stream(self, action_id: str, result: Any, 
                                  expected_outcome: Optional[str] = None,
                                  execution_time: Optional[float] = None,
                                  action_name: Optional[str] = None):
        """
        Observe and analyze action result with streaming output for real-time feedback
        
        Args:
            action_id: ID of the action that was executed
            result: Result from action execution
            expected_outcome: Expected outcome description
            execution_time: Time taken to execute the action
            action_name: Name of the action for pattern analysis
            
        Yields:
            Real-time updates from the observation and analysis process
        """
        yield f"👁️ **ResultObserver 开始观察分析**\n"
        yield f"🆔 行动ID: {action_id}\n"
        yield f"🎯 行动名称: {action_name or '未知'}\n"
        yield f"⏱️  执行时间: {execution_time:.2f}秒" if execution_time else "⏱️  执行时间: 未知\n"
        
        try:
            start_time = time.time()
            observation_id = f"obs_{action_id}_{int(time.time() * 1000)}"
            
            # Step 1: Initial Result Assessment
            yield f"\n📊 **步骤1**: 结果初步评估...\n"
            yield f"   📈 结果类型: {type(result).__name__}\n"
            yield f"   📏 结果大小: {len(str(result))} 字符\n"
            
            if expected_outcome:
                yield f"   🎯 期望结果: {expected_outcome[:50]}{'...' if len(expected_outcome) > 50 else ''}\n"
            else:
                yield f"   ⚠️  无期望结果基准\n"
            
            # Step 2: Success Assessment
            yield f"\n✅ **步骤2**: 成功评估分析...\n"
            
            success_assessment = self._assess_success(result, expected_outcome)
            yield f"   🎲 成功评估: {'成功' if success_assessment else '失败'}\n"
            
            # Detail the assessment reasoning
            if isinstance(result, dict):
                if "success" in result:
                    yield f"   📋 评估依据: 结果中包含 success 字段\n"
                elif "status" in result:
                    yield f"   📋 评估依据: 结果状态为 {result['status']}\n"
                elif "error" in result:
                    yield f"   📋 评估依据: 结果中{'包含' if result.get('error') else '不包含'}错误信息\n"
                else:
                    yield f"   📋 评估依据: 基于结果内容综合判断\n"
            elif result is None:
                yield f"   📋 评估依据: 结果为空\n"
            else:
                yield f"   📋 评估依据: 基于结果内容和类型判断\n"
            
            # Step 3: Confidence Calculation
            yield f"\n🎲 **步骤3**: 置信度计算...\n"
            
            confidence = self._calculate_confidence(result, success_assessment, expected_outcome)
            yield f"   📊 置信度分数: {confidence:.2f}\n"
            
            # Explain confidence factors
            if expected_outcome:
                yield f"   🎯 期望匹配度: 已提供基准\n"
            else:
                yield f"   ⚠️  期望匹配度: 无基准降低置信度\n"
            
            if isinstance(result, dict) and "confidence" in result:
                yield f"   🔍 内置置信度: {result['confidence']}\n"
            
            # Step 4: Pattern Detection
            yield f"\n🔍 **步骤4**: 模式检测分析...\n"
            
            patterns = self._detect_patterns(result, success_assessment, action_name, execution_time)
            if patterns:
                yield f"   📈 发现模式: {len(patterns)} 个\n"
                for i, pattern in enumerate(patterns[:3], 1):  # Show first 3 patterns
                    yield f"      {i}. {pattern}\n"
            else:
                yield f"   📉 未发现显著模式\n"
            
            # Step 5: Performance Metrics
            yield f"\n📊 **步骤5**: 性能指标计算...\n"
            
            metrics = self._calculate_performance_metrics(result, execution_time, success_assessment)
            for metric_name, metric_value in metrics.items():
                yield f"   📈 {metric_name}: {metric_value:.2f}\n"
            
            # Step 6: Insight Generation
            yield f"\n💡 **步骤6**: 深度洞察生成...\n"
            
            if self.llm_agent and self.observation_level in [ObservationLevel.DETAILED, ObservationLevel.COMPREHENSIVE]:
                yield f"   🧠 使用LLM生成深度洞察...\n"
                insights = await self._generate_insights(result, success_assessment, action_name, execution_time)
            else:
                yield f"   🔧 使用规则生成基础洞察...\n"
                insights = await self._generate_insights(result, success_assessment, action_name, execution_time)
            
            if insights:
                yield f"   ✨ 生成洞察: {len(insights)} 条\n"
                for i, insight in enumerate(insights[:2], 1):  # Show first 2 insights
                    yield f"      {i}. {insight[:80]}{'...' if len(insight) > 80 else ''}\n"
            else:
                yield f"   📝 未生成特殊洞察\n"
            
            # Step 7: Improvement Suggestions
            yield f"\n🚀 **步骤7**: 改进建议生成...\n"
            
            improvements = await self._generate_improvements(result, success_assessment, action_id, action_name)
            if improvements:
                yield f"   💡 改进建议: {len(improvements)} 条\n"
                for i, suggestion in enumerate(improvements[:2], 1):  # Show first 2 suggestions
                    yield f"      {i}. {suggestion[:80]}{'...' if len(suggestion) > 80 else ''}\n"
            else:
                yield f"   ✅ 暂无特别改进建议\n"
            
            # Step 8: Create and Store Observation
            yield f"\n💾 **步骤8**: 创建观察记录...\n"
            
            observation = Observation(
                observation_id=observation_id,
                action_id=action_id,
                result=result,
                success_assessment=success_assessment,
                confidence=confidence,
                insights=insights,
                improvement_suggestions=improvements,
                patterns_detected=patterns,
                performance_metrics=metrics,
                observation_level=self.observation_level
            )
            
            # Store observation
            self.observations[observation_id] = observation
            yield f"   📝 观察记录已保存 (ID: {observation_id})\n"
            
            # Step 9: Update Learning State
            yield f"\n🧠 **步骤9**: 更新学习状态...\n"
            
            await self._update_learning_state(observation, action_name, execution_time)
            yield f"   📚 学习状态已更新\n"
            
            # Update counters
            if success_assessment:
                self.success_count += 1
                yield f"   ✅ 成功计数: {self.success_count}\n"
            else:
                self.failure_count += 1
                yield f"   ❌ 失败计数: {self.failure_count}\n"
            
            observation_duration = time.time() - start_time
            self.total_observation_time += observation_duration
            
            # Final Summary
            yield f"\n🎉 **观察分析完成**\n"
            yield f"   📊 成功评估: {'成功' if success_assessment else '失败'}\n"
            yield f"   🎲 置信度: {confidence:.2f}\n"
            yield f"   💡 洞察数: {len(insights)}\n"
            yield f"   🚀 建议数: {len(improvements)}\n"
            yield f"   📈 模式数: {len(patterns)}\n"
            yield f"   ⏱️  观察耗时: {observation_duration:.2f}秒\n"
            
            # Store the result for later access
            self._last_observation = observation
            yield f"\n"
            
        except Exception as e:
            yield f"\n❌ **观察分析异常**: {str(e)}\n"
            
            # Create minimal observation for error case
            error_observation = Observation(
                observation_id=f"error_obs_{action_id}_{int(time.time() * 1000)}",
                action_id=action_id,
                result=result,
                success_assessment=False,
                confidence=0.0,
                insights=[f"观察分析过程中发生错误: {str(e)}"],
                improvement_suggestions=["检查观察分析配置"],
                observation_level=self.observation_level
            )
            
            self.observations[error_observation.observation_id] = error_observation
            self._last_observation = error_observation

    async def observe_multiple_results_stream(self, results_data: List[Dict[str, Any]]):
        """
        Observe and analyze multiple action results with streaming output
        
        Args:
            results_data: List of result data dictionaries containing action_id, result, etc.
            
        Yields:
            Real-time updates from the batch observation process
        """
        yield f"👁️ **ResultObserver 开始批量观察**\n"
        yield f"📊 结果总数: {len(results_data)}\n"
        yield f"🎛️  观察级别: {self.observation_level.value}\n"
        
        try:
            start_time = time.time()
            observations = []
            
            # Step 1: Process each result
            yield f"\n📋 **步骤1**: 逐一分析结果...\n"
            
            for i, result_data in enumerate(results_data, 1):
                action_id = result_data.get('action_id', f'unknown_{i}')
                result = result_data.get('result')
                action_name = result_data.get('action_name')
                execution_time = result_data.get('execution_time')
                expected_outcome = result_data.get('expected_outcome')
                
                yield f"   📝 正在分析 {i}/{len(results_data)}: {action_name or action_id}\n"
                
                # Create observation (non-streaming)
                observation = await self.observe_result(
                    action_id=action_id,
                    result=result,
                    expected_outcome=expected_outcome,
                    execution_time=execution_time,
                    action_name=action_name
                )
                
                observations.append(observation)
                success_status = "✅" if observation.success_assessment else "❌"
                yield f"      {success_status} 置信度: {observation.confidence:.2f}\n"
            
            # Step 2: Aggregate Analysis
            yield f"\n📊 **步骤2**: 聚合分析...\n"
            
            total_observations = len(observations)
            successful_observations = sum(1 for obs in observations if obs.success_assessment)
            average_confidence = sum(obs.confidence for obs in observations) / total_observations if total_observations > 0 else 0.0
            
            yield f"   📈 总观察数: {total_observations}\n"
            yield f"   ✅ 成功数: {successful_observations}\n"
            yield f"   ❌ 失败数: {total_observations - successful_observations}\n"
            yield f"   🎲 平均置信度: {average_confidence:.2f}\n"
            yield f"   📊 成功率: {(successful_observations / total_observations * 100) if total_observations > 0 else 0:.1f}%\n"
            
            # Step 3: Pattern Analysis Across Results
            yield f"\n🔍 **步骤3**: 跨结果模式分析...\n"
            
            all_patterns = []
            for obs in observations:
                all_patterns.extend(obs.patterns_detected)
            
            # Count pattern frequency
            pattern_counts = {}
            for pattern in all_patterns:
                pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
            
            if pattern_counts:
                common_patterns = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                yield f"   📈 发现 {len(pattern_counts)} 种模式\n"
                for pattern, count in common_patterns:
                    yield f"      • {pattern} (出现 {count} 次)\n"
            else:
                yield f"   📉 未发现显著跨结果模式\n"
            
            # Step 4: Collective Insights
            yield f"\n💡 **步骤4**: 集体洞察生成...\n"
            
            all_insights = []
            for obs in observations:
                all_insights.extend(obs.insights)
            
            unique_insights = list(set(all_insights))  # Remove duplicates
            yield f"   ✨ 独特洞察: {len(unique_insights)} 条\n"
            
            # Step 5: Performance Trends
            yield f"\n📊 **步骤5**: 性能趋势分析...\n"
            
            execution_times = [result_data.get('execution_time', 0) for result_data in results_data if result_data.get('execution_time')]
            if execution_times:
                avg_time = sum(execution_times) / len(execution_times)
                min_time = min(execution_times)
                max_time = max(execution_times)
                
                yield f"   ⏱️  平均执行时间: {avg_time:.2f}秒\n"
                yield f"   🏃 最快执行: {min_time:.2f}秒\n"
                yield f"   🐌 最慢执行: {max_time:.2f}秒\n"
                yield f"   📈 时间标准差: {((sum((t - avg_time) ** 2 for t in execution_times) / len(execution_times)) ** 0.5):.2f}秒\n"
            else:
                yield f"   ⚠️  无执行时间数据\n"
            
            total_time = time.time() - start_time
            
            # Final Summary
            yield f"\n🎉 **批量观察分析完成**\n"
            yield f"   📊 处理结果: {total_observations} 个\n"
            yield f"   📈 总体成功率: {(successful_observations / total_observations * 100) if total_observations > 0 else 0:.1f}%\n"
            yield f"   🎲 平均置信度: {average_confidence:.2f}\n"
            yield f"   💡 总洞察数: {len(unique_insights)}\n"
            yield f"   📈 发现模式: {len(pattern_counts)}\n"
            yield f"   ⏱️  总观察时间: {total_time:.2f}秒\n"
            
            # Store the batch results for later access
            self._last_batch_observations = observations
            yield f"\n"
            
        except Exception as e:
            yield f"\n❌ **批量观察异常**: {str(e)}\n"
            self._last_batch_observations = []

    async def get_last_observation(self) -> Optional[Observation]:
        """
        Get the result from the last streaming observation
        
        Returns:
            The last Observation, or None if no observation has been performed
        """
        return getattr(self, '_last_observation', None)

    async def get_last_batch_observations(self) -> List[Observation]:
        """
        Get the results from the last streaming batch observation
        
        Returns:
            List of Observations from the last batch observation
        """
        return getattr(self, '_last_batch_observations', []) 