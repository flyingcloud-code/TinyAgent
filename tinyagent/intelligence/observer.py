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
    
    def __init__(self, observation_level: ObservationLevel = ObservationLevel.DETAILED):
        """
        Initialize ResultObserver
        
        Args:
            observation_level: Level of detail for observations
        """
        self.observation_level = observation_level
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
        
        logger.info(f"ResultObserver initialized with observation_level={observation_level.value}")
    
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
        """Generate insights from the result"""
        insights = []
        
        # Success/failure insights
        if success:
            insights.append("Action completed successfully")
            if execution_time and execution_time < 1.0:
                insights.append("Fast execution time indicates efficient processing")
        else:
            insights.append("Action did not complete successfully")
            if execution_time and execution_time > 10.0:
                insights.append("Long execution time may indicate performance issues")
        
        # Result content insights
        if isinstance(result, dict):
            if "confidence" in result:
                conf = float(result["confidence"])
                if conf > 0.8:
                    insights.append("High confidence result indicates reliable output")
                elif conf < 0.5:
                    insights.append("Low confidence result may need validation")
            
            if "sources" in result:
                sources = result["sources"]
                if isinstance(sources, list) and len(sources) > 3:
                    insights.append("Multiple sources provide good validation")
        
        # Pattern-based insights
        if action_name and action_name in self.action_outcomes:
            outcomes = self.action_outcomes[action_name]
            if len(outcomes) >= 3:
                recent_success_rate = sum(outcomes[-3:]) / 3
                if recent_success_rate == 1.0:
                    insights.append(f"Action '{action_name}' shows consistent success pattern")
                elif recent_success_rate < 0.5:
                    insights.append(f"Action '{action_name}' shows recurring issues")
        
        # Performance insights
        if execution_time:
            if execution_time < 0.5:
                insights.append("Exceptionally fast execution")
            elif execution_time > 30.0:
                insights.append("Execution time suggests complex processing or potential bottleneck")
        
        return insights
    
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