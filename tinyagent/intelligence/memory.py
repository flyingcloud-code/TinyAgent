"""
Conversation Memory Module for TinyAgent Intelligence System
Implements intelligent conversation history management and context retention.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import uuid
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """Represents a single turn in conversation"""
    turn_id: str
    timestamp: datetime
    user_input: str
    agent_response: str
    tools_used: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    task_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "timestamp": self.timestamp.isoformat(),
            "user_input": self.user_input,
            "agent_response": self.agent_response,
            "tools_used": self.tools_used,
            "execution_time": self.execution_time,
            "task_id": self.task_id,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationTurn":
        return cls(
            turn_id=data["turn_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            user_input=data["user_input"],
            agent_response=data["agent_response"],
            tools_used=data.get("tools_used", []),
            execution_time=data.get("execution_time", 0.0),
            task_id=data.get("task_id"),
            metadata=data.get("metadata", {})
        )


@dataclass
class TaskContext:
    """Context information for ongoing tasks"""
    task_id: str
    initial_request: str
    current_status: str
    completed_steps: List[int] = field(default_factory=list)
    step_results: Dict[int, Any] = field(default_factory=dict)
    tools_used: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_status(self, status: str, metadata: Optional[Dict[str, Any]] = None):
        """Update task status and timestamp"""
        self.current_status = status
        self.last_updated = datetime.now()
        if metadata:
            self.metadata.update(metadata)
    
    def add_step_result(self, step_id: int, result: Any):
        """Add result from completed step"""
        self.completed_steps.append(step_id)
        self.step_results[step_id] = result
        self.last_updated = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "initial_request": self.initial_request,
            "current_status": self.current_status,
            "completed_steps": self.completed_steps,
            "step_results": self.step_results,
            "tools_used": self.tools_used,
            "start_time": self.start_time.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "metadata": self.metadata
        }


class ConversationMemory:
    """
    Intelligent Conversation Memory Manager
    
    Provides:
    - Conversation history tracking
    - Context relevance analysis
    - Task context management
    - Tool usage history
    - Smart context retrieval
    """
    
    def __init__(self, 
                 max_turns: int = 100,
                 context_window: int = 50,
                 relevance_threshold: float = 0.7,
                 auto_summarize: bool = True):
        """
        Initialize ConversationMemory
        
        Args:
            max_turns: Maximum turns to keep in memory
            context_window: Number of recent turns for context
            relevance_threshold: Minimum relevance score for context inclusion
            auto_summarize: Whether to auto-summarize old conversations
        """
        self.max_turns = max_turns
        self.context_window = context_window
        self.relevance_threshold = relevance_threshold
        self.auto_summarize = auto_summarize
        
        # Core memory stores
        self.conversation_history: deque = deque(maxlen=max_turns)
        self.task_contexts: Dict[str, TaskContext] = {}
        self.tool_usage_history: List[Dict[str, Any]] = []
        self.conversation_summaries: List[str] = []
        
        # Session tracking
        self.session_id = str(uuid.uuid4())
        self.session_start = datetime.now()
        
        logger.info(f"ConversationMemory initialized - session: {self.session_id}")
    
    def add_exchange(self, 
                    user_input: str, 
                    agent_response: str,
                    tools_used: Optional[List[str]] = None,
                    execution_time: float = 0.0,
                    task_id: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a conversation exchange to memory
        
        Args:
            user_input: User's input message
            agent_response: Agent's response
            tools_used: List of tools used in this turn
            execution_time: Time taken to generate response
            task_id: Associated task ID if any
            metadata: Additional metadata
            
        Returns:
            Turn ID for the added exchange
        """
        turn_id = str(uuid.uuid4())
        
        turn = ConversationTurn(
            turn_id=turn_id,
            timestamp=datetime.now(),
            user_input=user_input,
            agent_response=agent_response,
            tools_used=tools_used or [],
            execution_time=execution_time,
            task_id=task_id,
            metadata=metadata or {}
        )
        
        self.conversation_history.append(turn)
        
        # Update tool usage history
        if tools_used:
            self.tool_usage_history.append({
                "turn_id": turn_id,
                "timestamp": turn.timestamp.isoformat(),
                "tools": tools_used,
                "task_id": task_id
            })
        
        # Auto-summarize if needed
        if self.auto_summarize and len(self.conversation_history) >= self.max_turns:
            self._create_conversation_summary()
        
        logger.debug(f"Added conversation turn: {turn_id}")
        return turn_id
    
    def get_relevant_context(self, 
                           current_input: str, 
                           max_turns: Optional[int] = None) -> List[ConversationTurn]:
        """
        Get relevant conversation context for current input
        
        Args:
            current_input: Current user input
            max_turns: Maximum turns to consider (defaults to context_window)
            
        Returns:
            List of relevant conversation turns
        """
        max_turns = max_turns or self.context_window
        
        # Get recent turns
        recent_turns = list(self.conversation_history)[-max_turns:]
        
        if not recent_turns:
            return []
        
        # For now, return recent turns
        # TODO: Implement semantic similarity for relevance scoring
        relevant_turns = []
        
        for turn in recent_turns:
            relevance_score = self._calculate_relevance(turn, current_input)
            if relevance_score >= self.relevance_threshold:
                relevant_turns.append(turn)
        
        logger.debug(f"Found {len(relevant_turns)} relevant turns for context")
        return relevant_turns
    
    def _calculate_relevance(self, turn: ConversationTurn, current_input: str) -> float:
        """
        Calculate relevance score between a turn and current input
        
        Args:
            turn: Previous conversation turn
            current_input: Current user input
            
        Returns:
            Relevance score (0.0 to 1.0)
        """
        # Simple keyword-based relevance for now
        # TODO: Replace with semantic similarity using embeddings
        
        current_words = set(current_input.lower().split())
        turn_words = set((turn.user_input + " " + turn.agent_response).lower().split())
        
        if not current_words or not turn_words:
            return 0.0
        
        # Jaccard similarity
        intersection = current_words.intersection(turn_words)
        union = current_words.union(turn_words)
        
        similarity = len(intersection) / len(union) if union else 0.0
        
        # Boost relevance for recent turns
        time_factor = 1.0
        hours_ago = (datetime.now() - turn.timestamp).total_seconds() / 3600
        if hours_ago < 1:
            time_factor = 1.2
        elif hours_ago < 24:
            time_factor = 1.1
        
        return min(similarity * time_factor, 1.0)
    
    def get_conversation_summary(self, num_turns: Optional[int] = None) -> str:
        """
        Get summary of conversation history
        
        Args:
            num_turns: Number of recent turns to summarize
            
        Returns:
            Conversation summary
        """
        if not self.conversation_history:
            return "No conversation history available."
        
        turns_to_summarize = list(self.conversation_history)
        if num_turns:
            turns_to_summarize = turns_to_summarize[-num_turns:]
        
        summary_parts = []
        summary_parts.append(f"Session started: {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}")
        summary_parts.append(f"Total turns: {len(self.conversation_history)}")
        
        if self.conversation_summaries:
            summary_parts.append("Previous conversation summary:")
            summary_parts.extend(self.conversation_summaries[-3:])  # Last 3 summaries
        
        # Recent conversation
        if turns_to_summarize:
            summary_parts.append(f"\nRecent conversation ({len(turns_to_summarize)} turns):")
            for turn in turns_to_summarize[-10:]:  # Last 10 turns
                summary_parts.append(f"User: {turn.user_input[:100]}...")
                summary_parts.append(f"Agent: {turn.agent_response[:100]}...")
                if turn.tools_used:
                    summary_parts.append(f"Tools: {', '.join(turn.tools_used)}")
                summary_parts.append("---")
        
        return "\n".join(summary_parts)
    
    def get_task_context(self, task_id: str) -> Optional[TaskContext]:
        """Get context for specific task"""
        return self.task_contexts.get(task_id)
    
    def create_task_context(self, 
                          task_id: str, 
                          initial_request: str,
                          metadata: Optional[Dict[str, Any]] = None) -> TaskContext:
        """
        Create new task context
        
        Args:
            task_id: Unique task identifier
            initial_request: Initial user request that started the task
            metadata: Additional task metadata
            
        Returns:
            Created TaskContext
        """
        context = TaskContext(
            task_id=task_id,
            initial_request=initial_request,
            current_status="initialized",
            metadata=metadata or {}
        )
        
        self.task_contexts[task_id] = context
        logger.info(f"Created task context: {task_id}")
        return context
    
    def update_task_context(self, 
                          task_id: str,
                          status: Optional[str] = None,
                          step_id: Optional[int] = None,
                          step_result: Optional[Any] = None,
                          tools_used: Optional[List[str]] = None,
                          metadata: Optional[Dict[str, Any]] = None):
        """
        Update existing task context
        
        Args:
            task_id: Task identifier
            status: New task status
            step_id: Completed step ID
            step_result: Result from completed step
            tools_used: Tools used in this update
            metadata: Additional metadata
        """
        context = self.task_contexts.get(task_id)
        if not context:
            logger.warning(f"Task context not found: {task_id}")
            return
        
        if status:
            context.update_status(status, metadata)
        
        if step_id is not None and step_result is not None:
            context.add_step_result(step_id, step_result)
        
        if tools_used:
            context.tools_used.extend(tools_used)
            # Remove duplicates while preserving order
            context.tools_used = list(dict.fromkeys(context.tools_used))
        
        logger.debug(f"Updated task context: {task_id}")
    
    def get_tool_usage_stats(self, hours_back: int = 24) -> Dict[str, Any]:
        """
        Get tool usage statistics
        
        Args:
            hours_back: Hours to look back for statistics
            
        Returns:
            Dictionary with tool usage statistics
        """
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        recent_usage = []
        for usage in self.tool_usage_history:
            usage_time = datetime.fromisoformat(usage["timestamp"])
            if usage_time >= cutoff_time:
                recent_usage.append(usage)
        
        # Count tool usage
        tool_counts = {}
        total_calls = 0
        
        for usage in recent_usage:
            total_calls += len(usage["tools"])
            for tool in usage["tools"]:
                tool_counts[tool] = tool_counts.get(tool, 0) + 1
        
        # Sort by usage count
        sorted_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "time_period_hours": hours_back,
            "total_tool_calls": total_calls,
            "unique_tools_used": len(tool_counts),
            "tool_usage_counts": dict(sorted_tools),
            "most_used_tool": sorted_tools[0][0] if sorted_tools else None,
            "recent_usage_entries": len(recent_usage)
        }
    
    def get_context_for_task_planning(self, current_input: str) -> Dict[str, Any]:
        """
        Get comprehensive context for task planning
        
        Args:
            current_input: Current user input
            
        Returns:
            Dictionary with planning context
        """
        relevant_turns = self.get_relevant_context(current_input)
        
        context = {
            "session_id": self.session_id,
            "session_duration_minutes": (datetime.now() - self.session_start).total_seconds() / 60,
            "total_conversation_turns": len(self.conversation_history),
            "relevant_previous_turns": [turn.to_dict() for turn in relevant_turns],
            "active_tasks": list(self.task_contexts.keys()),
            "recent_tools_used": self._get_recent_tools(hours=1),
            "conversation_themes": self._extract_conversation_themes(),
        }
        
        # Add active task contexts
        if self.task_contexts:
            context["task_contexts"] = {
                task_id: ctx.to_dict() 
                for task_id, ctx in self.task_contexts.items()
            }
        
        return context
    
    def _get_recent_tools(self, hours: int = 1) -> List[str]:
        """Get tools used in recent hours"""
        from datetime import timedelta
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_tools = []
        for turn in reversed(self.conversation_history):
            if turn.timestamp >= cutoff_time:
                recent_tools.extend(turn.tools_used)
            else:
                break
        
        # Return unique tools in order of first use
        return list(dict.fromkeys(recent_tools))
    
    def _extract_conversation_themes(self) -> List[str]:
        """Extract main themes from conversation"""
        # Simple keyword-based theme extraction
        # TODO: Replace with more sophisticated topic modeling
        
        if not self.conversation_history:
            return []
        
        all_text = " ".join([
            turn.user_input + " " + turn.agent_response 
            for turn in self.conversation_history
        ])
        
        # Common themes based on keywords
        theme_keywords = {
            "file_operations": ["file", "read", "write", "create", "save"],
            "web_search": ["search", "find", "google", "lookup", "information"],
            "data_analysis": ["analyze", "data", "report", "statistics", "summary"],
            "weather": ["weather", "temperature", "forecast", "climate"],
            "development": ["code", "programming", "function", "debug", "development"],
            "documentation": ["document", "documentation", "readme", "guide", "manual"]
        }
        
        themes = []
        text_lower = all_text.lower()
        
        for theme, keywords in theme_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                themes.append(theme)
        
        return themes
    
    def _create_conversation_summary(self):
        """Create summary of old conversation when buffer is full"""
        if len(self.conversation_history) < 10:
            return
        
        # Take first half of conversation for summarization
        turns_to_summarize = list(self.conversation_history)[:len(self.conversation_history)//2]
        
        summary = f"Conversation summary ({len(turns_to_summarize)} turns):\n"
        summary += f"Time period: {turns_to_summarize[0].timestamp.strftime('%H:%M')} - {turns_to_summarize[-1].timestamp.strftime('%H:%M')}\n"
        
        # Extract key topics and tools used
        tools_used = set()
        topics = []
        
        for turn in turns_to_summarize:
            tools_used.update(turn.tools_used)
            if len(turn.user_input) > 20:  # Meaningful requests
                topics.append(turn.user_input[:50] + "...")
        
        summary += f"Tools used: {', '.join(tools_used)}\n"
        summary += f"Main topics: {'; '.join(topics[:5])}\n"
        
        self.conversation_summaries.append(summary)
        logger.info("Created conversation summary")
    
    def clear_history(self, keep_summaries: bool = True):
        """Clear conversation history"""
        self.conversation_history.clear()
        self.task_contexts.clear()
        self.tool_usage_history.clear()
        
        if not keep_summaries:
            self.conversation_summaries.clear()
        
        logger.info("Conversation history cleared")
    
    def export_memory(self) -> Dict[str, Any]:
        """Export complete memory state"""
        return {
            "session_id": self.session_id,
            "session_start": self.session_start.isoformat(),
            "conversation_history": [turn.to_dict() for turn in self.conversation_history],
            "task_contexts": {task_id: ctx.to_dict() for task_id, ctx in self.task_contexts.items()},
            "tool_usage_history": self.tool_usage_history,
            "conversation_summaries": self.conversation_summaries,
            "config": {
                "max_turns": self.max_turns,
                "context_window": self.context_window,
                "relevance_threshold": self.relevance_threshold,
                "auto_summarize": self.auto_summarize
            }
        }
    
    def import_memory(self, memory_data: Dict[str, Any]):
        """Import memory state from exported data"""
        try:
            self.session_id = memory_data.get("session_id", str(uuid.uuid4()))
            self.session_start = datetime.fromisoformat(memory_data.get("session_start", datetime.now().isoformat()))
            
            # Import conversation history
            self.conversation_history.clear()
            for turn_data in memory_data.get("conversation_history", []):
                turn = ConversationTurn.from_dict(turn_data)
                self.conversation_history.append(turn)
            
            # Import task contexts
            self.task_contexts.clear()
            for task_id, ctx_data in memory_data.get("task_contexts", {}).items():
                # Reconstruct TaskContext from dict (simplified)
                context = TaskContext(
                    task_id=ctx_data["task_id"],
                    initial_request=ctx_data["initial_request"],
                    current_status=ctx_data["current_status"],
                    completed_steps=ctx_data.get("completed_steps", []),
                    step_results=ctx_data.get("step_results", {}),
                    tools_used=ctx_data.get("tools_used", []),
                    start_time=datetime.fromisoformat(ctx_data["start_time"]),
                    last_updated=datetime.fromisoformat(ctx_data["last_updated"]),
                    metadata=ctx_data.get("metadata", {})
                )
                self.task_contexts[task_id] = context
            
            # Import other data
            self.tool_usage_history = memory_data.get("tool_usage_history", [])
            self.conversation_summaries = memory_data.get("conversation_summaries", [])
            
            logger.info(f"Imported memory with {len(self.conversation_history)} turns")
            
        except Exception as e:
            logger.error(f"Failed to import memory: {e}")
            raise

from datetime import timedelta 