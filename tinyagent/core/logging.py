"""
TinyAgent Enhanced Logging System

This module provides an intelligent logging system with:
- Custom log levels for user experience
- Content-aware routing to console/file/structured logs
- User-friendly console output
- Complete technical logging to files
- Structured metrics for analytics
"""

import logging
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler

# Custom log levels
USER_LEVEL = 25      # User input/output and final results
AGENT_LEVEL = 23     # Agent responses and major state changes  
TOOL_LEVEL = 21      # MCP tool call summaries

# Add custom levels to logging module
logging.addLevelName(USER_LEVEL, "USER")
logging.addLevelName(AGENT_LEVEL, "AGENT")
logging.addLevelName(TOOL_LEVEL, "TOOL")


class UserFriendlyFormatter(logging.Formatter):
    """Formatter for user-friendly console output with clean formatting"""
    
    def __init__(self, enable_colors=True, show_timestamps=False):
        super().__init__()
        self.enable_colors = enable_colors
        self.show_timestamps = show_timestamps
    
    def format(self, record):
        """Format log record for user display"""
        message = record.getMessage()
        
        # Clean Unicode characters for Windows console compatibility
        message = clean_unicode_for_console(message)
        
        # Convert timestamp
        timestamp = ""
        if self.show_timestamps:
            timestamp = f"{datetime.fromtimestamp(record.created).strftime('%H:%M:%S')} | "
        
        # Determine level prefix with ASCII characters only
        level_prefixes = {
            USER_LEVEL: ">>",
            AGENT_LEVEL: "**", 
            TOOL_LEVEL: "++"
        }
        prefix = level_prefixes.get(record.levelno, "??")
        
        # Format status indicators with ASCII
        if "[OK]" in message or "completed successfully" in message.lower():
            status = "[OK]"
        elif "[ERROR]" in message or "failed" in message.lower() or "error" in message.lower():
            status = "[ERROR]"
        elif "[SAVE]" in message or "saved" in message.lower():
            status = "[SAVE]"
        else:
            status = ""
        
        # Apply colors if enabled (but keep ASCII characters)
        if self.enable_colors:
            if record.levelno == USER_LEVEL:
                prefix = f"\033[96m{prefix}\033[0m"  # Cyan
            elif record.levelno == AGENT_LEVEL:
                prefix = f"\033[94m{prefix}\033[0m"  # Blue
            elif record.levelno == TOOL_LEVEL:
                prefix = f"\033[93m{prefix}\033[0m"  # Yellow
            
            # Color status indicators
            if status == "[OK]":
                status = f"\033[92m{status}\033[0m"  # Green
            elif status == "[ERROR]":
                status = f"\033[91m{status}\033[0m"  # Red
            elif status == "[SAVE]":
                status = f"\033[95m{status}\033[0m"  # Magenta
        
        # Combine formatted message
        formatted = f"{timestamp}{prefix} {status} {message}".strip()
        return formatted


class TechnicalFormatter(logging.Formatter):
    """Formatter for technical/debugging logs with full context"""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-12s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def format(self, record):
        """Format technical log with full context"""
        # Clean Unicode characters for console compatibility
        original_msg = record.getMessage()
        record.msg = clean_unicode_for_console(original_msg)
        return super().format(record)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logs"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'metrics'):
            log_entry['metrics'] = record.metrics
            
        if hasattr(record, 'session_id'):
            log_entry['session_id'] = record.session_id
            
        return json.dumps(log_entry)


class UserRelevantFilter(logging.Filter):
    """Filter that only allows user-relevant log records to pass"""
    
    def filter(self, record):
        # Allow custom user levels and important errors/warnings
        return record.levelno >= USER_LEVEL or record.levelno >= logging.WARNING


class TechnicalDetailsFilter(logging.Filter):
    """Filter that allows all technical details for file logging"""
    
    def filter(self, record):
        # Allow everything for file logs
        return True


class MetricsFilter(logging.Filter):
    """Filter for structured metrics logging"""
    
    def filter(self, record):
        # Only records with metrics or specific logger names
        return (hasattr(record, 'metrics') or 
                record.name.startswith('tinyagent.metrics') or
                record.levelno >= logging.WARNING)


class TinyAgentFileHandler(RotatingFileHandler):
    """Enhanced file handler that ensures directory creation and proper permissions"""
    
    def __init__(self, filename: str, maxBytes: int = 10485760, backupCount: int = 5):
        # Ensure log directory exists
        log_path = Path(filename)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        super().__init__(filename, maxBytes=maxBytes, backupCount=backupCount)
        
        # Use technical format for file logs
        self.setFormatter(TechnicalFormatter())


class TinyAgentLogger:
    """Enhanced logging system for TinyAgent"""
    
    def __init__(self, config=None):
        """Initialize the enhanced logging system"""
        self.config = config or self._get_default_config()
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._setup_loggers()
    
    def _get_default_config(self):
        """Get default logging configuration"""
        from .config import LoggingConfig
        return LoggingConfig()
    
    def _setup_loggers(self):
        """Set up all logger handlers and formatters"""
        # Clear any existing handlers to prevent conflicts
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        # Set up console handler (user-friendly)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(USER_LEVEL)
        console_handler.setFormatter(UserFriendlyFormatter(
            enable_colors=self.config.enable_colors,
            show_timestamps=self.config.show_timestamps
        ))
        console_handler.addFilter(UserRelevantFilter())
        
        # Fix Unicode encoding issues on Windows
        if hasattr(console_handler.stream, 'reconfigure'):
            try:
                console_handler.stream.reconfigure(encoding='utf-8')
            except Exception:
                pass
        
        # Set up file handler (technical details)
        if self.config.file:
            try:
                file_handler = TinyAgentFileHandler(
                    self.config.file,
                    maxBytes=10485760,  # 10MB
                    backupCount=5
                )
                file_handler.setLevel(logging.DEBUG)
                file_handler.addFilter(TechnicalDetailsFilter())
                root_logger.addHandler(file_handler)
            except Exception as e:
                print(f"Warning: Could not set up file logging: {e}")
        
        # Suppress noisy third-party logs
        self._configure_third_party_loggers()
        
        # Set up structured handler (metrics)
        if hasattr(self.config, 'structured_file') and self.config.structured_file:
            try:
                structured_handler = TinyAgentFileHandler(
                    self.config.structured_file,
                    maxBytes=50*1024*1024,  # 50MB for metrics
                    backupCount=10
                )
                structured_handler.setLevel(logging.INFO)
                structured_handler.setFormatter(StructuredFormatter())
                structured_handler.addFilter(MetricsFilter())
                root_logger.addHandler(structured_handler)
            except Exception as e:
                print(f"Warning: Could not set up structured logging: {e}")
        
        # Add console handler
        root_logger.addHandler(console_handler)
        
        # Set root logger level
        level = getattr(logging, self.config.level.upper(), logging.INFO)
        root_logger.setLevel(level)
        
        # Disable propagation for specific loggers to prevent duplicates
        for logger_name in ['tinyagent.mcp.tools', 'agents', 'httpx']:
            logger = logging.getLogger(logger_name)
            logger.propagate = False
    
    def _configure_third_party_loggers(self):
        """Configure third-party loggers to reduce noise"""
        # LiteLLM - only show warnings and above
        litellm_logger = logging.getLogger('LiteLLM')
        litellm_logger.setLevel(logging.WARNING)
        litellm_logger.propagate = False
        
        # Suppress specific LiteLLM cost calculation logs that appear too frequently
        class LiteLLMCostFilter(logging.Filter):
            def filter(self, record):
                message = record.getMessage()
                # Filter out repetitive cost calculation messages
                if 'selected model name for cost calculation' in message:
                    return False
                if 'completion_cost' in message and 'cost calculation' in message:
                    return False
                return True
        
        litellm_logger.addFilter(LiteLLMCostFilter())
        
        # Other third-party libraries - set to WARNING level
        for logger_name in [
            'httpx', 'httpcore', 'aiohttp', 'urllib3', 'requests',
            'openai', 'anthropic', 'agents', 'asyncio'
        ]:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.WARNING)
            logger.propagate = False
    
    def user(self, message: str):
        """Log user-facing information"""
        logger = logging.getLogger('tinyagent.user')
        logger.log(USER_LEVEL, message)
    
    def agent(self, message: str):
        """Log agent activities"""
        logger = logging.getLogger('tinyagent.agent')
        logger.log(AGENT_LEVEL, message)
    
    def tool(self, message: str, **metrics):
        """Log tool activities with optional metrics"""
        logger = logging.getLogger('tinyagent.tool')
        logger.log(TOOL_LEVEL, message)
        
        # Log structured metrics if provided
        if metrics:
            self._log_structured('tool_call', metrics)
    
    def technical(self, level: str, message: str, logger_name: str = 'tinyagent.tech'):
        """Log technical details (file only)"""
        logger = logging.getLogger(logger_name)
        getattr(logger, level.lower())(message)
    
    def error(self, message: str, user_facing: bool = False):
        """Log error message"""
        if user_facing:
            logger = logging.getLogger('tinyagent.user')
        else:
            logger = logging.getLogger('tinyagent.error')
        logger.error(message)
    
    def warning(self, message: str, user_facing: bool = False):
        """Log warning message"""
        if user_facing:
            logger = logging.getLogger('tinyagent.user')
        else:
            logger = logging.getLogger('tinyagent.warning')
        logger.warning(message)
    
    def _log_structured(self, event_type: str, data: Dict[str, Any]):
        """Log structured data for analytics"""
        logger = logging.getLogger('tinyagent.metrics')
        
        # Create structured log record
        record = logger.makeRecord(
            logger.name, logging.INFO, '', 0, '', (), None
        )
        record.metrics = {
            'event_type': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': self._session_id,
            **data
        }
        
        logger.handle(record)


# Global logger instance
_global_logger: Optional[TinyAgentLogger] = None


def get_logger() -> TinyAgentLogger:
    """Get the global TinyAgent logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = TinyAgentLogger()
    return _global_logger


def setup_logging(config=None):
    """Set up the global logging system"""
    global _global_logger
    _global_logger = TinyAgentLogger(config)
    return _global_logger


def log_user(message: str):
    """Convenience function for user logs"""
    get_logger().user(message)


def log_agent(message: str):
    """Convenience function for agent logs"""
    get_logger().agent(message)


def log_tool(message: str, **metrics):
    """Convenience function for tool logs"""
    get_logger().tool(message, **metrics)


def log_technical(level: str, message: str, logger_name: str = 'tinyagent.tech'):
    """Convenience function for technical logs"""
    get_logger().technical(level, message, logger_name)


class MCPToolMetrics:
    """Helper class for logging MCP tool call metrics"""
    
    @staticmethod
    def log_tool_call(server_name: str, tool_name: str, duration: float, 
                     success: bool, input_size: int = 0, output_size: int = 0):
        """Log MCP tool call metrics"""
        # Log user-friendly summary
        status_text = "[OK]" if success else "[FAIL]"
        get_logger().tool(
            f"Tool call: {server_name}.{tool_name} ({status_text})",
            server=server_name,
            tool=tool_name,
            duration=duration,
            success=success,
            output_size=output_size
        )


def clean_unicode_for_console(text: str) -> str:
    """
    Clean Unicode characters for Windows console compatibility.
    Replaces common Unicode characters with ASCII equivalents.
    """
    if not text:
        return text
    
    # Common emoji and Unicode replacements
    replacements = {
        '😊': ':)',
        '😃': ':D',
        '😄': ':D',
        '😆': ':D',
        '😁': ':D',
        '🙂': ':)',
        '😀': ':)',
        '😎': 'B-)',
        '😉': ';)',
        '😭': ":'(",
        '😢': ':(',
        '😞': ':(',
        '😔': ':(',
        '❤️': '<3',
        '💙': '<3',
        '💚': '<3',
        '💛': '<3',
        '💜': '<3',
        '👍': '+1',
        '👎': '-1',
        '✅': '[OK]',
        '❌': '[ERROR]',
        '⚠️': '[WARNING]',
        '💡': '[IDEA]',
        '🔥': '[HOT]',
        '⭐': '*',
        '🌟': '*',
        '💯': '100%',
        '🎉': '[CELEBRATION]',
        '🚀': '[ROCKET]',
        '📝': '[NOTE]',
        '📊': '[CHART]',
        '📈': '[UP]',
        '📉': '[DOWN]',
        '🏆': '[TROPHY]',
        '💪': '[STRONG]',
        '🤝': '[HANDSHAKE]',
        '🙏': '[THANKS]',
        '🔍': '[SEARCH]',
        '💬': '[CHAT]',
        '📧': '[EMAIL]',
        '📱': '[PHONE]',
        '💻': '[COMPUTER]',
        '🖥️': '[DESKTOP]',
        '⌨️': '[KEYBOARD]',
        '🖱️': '[MOUSE]',
        '🔐': '[SECURE]',
        '🔓': '[UNLOCKED]',
        '🔒': '[LOCKED]',
    }
    
    # Apply emoji replacements first
    cleaned_text = text
    for unicode_char, ascii_replacement in replacements.items():
        cleaned_text = cleaned_text.replace(unicode_char, ascii_replacement)
    
    # Handle Chinese and other non-ASCII characters more gracefully
    try:
        # Try to encode to cp1252 (Windows console encoding) first
        cleaned_text.encode('cp1252')
        return cleaned_text
    except UnicodeEncodeError:
        pass
    
    try:
        # Try to encode to ASCII
        cleaned_text.encode('ascii')
        return cleaned_text
    except UnicodeEncodeError:
        # If encoding fails, replace non-ASCII chars with placeholders
        result = []
        for char in cleaned_text:
            try:
                char.encode('ascii')
                result.append(char)
            except UnicodeEncodeError:
                # For Chinese characters, use a more descriptive placeholder
                if '\u4e00' <= char <= '\u9fff':  # Chinese character range
                    result.append('[CH]')
                elif '\u3040' <= char <= '\u309f' or '\u30a0' <= char <= '\u30ff':  # Japanese
                    result.append('[JP]')
                elif '\uac00' <= char <= '\ud7af':  # Korean
                    result.append('[KR]')
                else:
                    result.append('?')
        return ''.join(result)
    
    return cleaned_text 