"""
Audit Logger module for the domain checker system.

Provides structured logging with dual-format output (JSON and human-readable text),
optional audit mode with HMAC signing, and sensitive data masking.
"""

import hmac
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, TextIO

from domain_checker.enums import LogLevel


@dataclass
class LogEntry:
    """Represents a single log entry with all metadata."""
    
    timestamp: str
    level: LogLevel
    component: str
    message: str
    data: dict = field(default_factory=dict)
    signature: Optional[str] = None


class AuditLogger:
    """
    Audit logger with dual-format output and optional signing.
    
    Supports:
    - JSON and human-readable text output formats
    - Audit mode with HMAC-SHA256 signing of log entries
    - Automatic masking of sensitive data (tokens, secrets, passwords)
    - Full error context logging
    """
    
    # Keys that should be masked in log output
    SENSITIVE_KEYS = frozenset({
        'token', 'secret', 'password', 'api_key', 'hmac_secret',
        'bot_token', 'webhook_url', 'auth', 'authorization',
        'credential', 'credentials', 'private_key', 'access_token',
        'refresh_token', 'session_token', 'api_secret',
    })
    
    MASK_VALUE = "***MASKED***"
    
    def __init__(
        self,
        output_format: str = "both",
        output_stream: Optional[TextIO] = None,
    ):
        """
        Initialize the audit logger.
        
        Args:
            output_format: Output format - 'json', 'text', or 'both'
            output_stream: Output stream for log entries (defaults to sys.stderr)
        """
        if output_format not in ("json", "text", "both"):
            raise ValueError(f"Invalid output_format: {output_format}")
        
        self._output_format = output_format
        self._output_stream = output_stream or sys.stderr
        self._audit_mode = False
        self._signing_key: Optional[bytes] = None
        self._entries: list[LogEntry] = []  # Store entries for testing
    
    @property
    def output_format(self) -> str:
        """Get the current output format."""
        return self._output_format
    
    @property
    def audit_mode(self) -> bool:
        """Check if audit mode is enabled."""
        return self._audit_mode
    
    @property
    def entries(self) -> list[LogEntry]:
        """Get all logged entries (for testing)."""
        return self._entries.copy()

    def enable_audit_mode(self, signing_key: str) -> None:
        """
        Enable audit mode with HMAC signing of log entries.
        
        Args:
            signing_key: Secret key for HMAC-SHA256 signing
        """
        if not signing_key:
            raise ValueError("Signing key cannot be empty")
        
        self._audit_mode = True
        self._signing_key = signing_key.encode('utf-8')
    
    def disable_audit_mode(self) -> None:
        """Disable audit mode."""
        self._audit_mode = False
        self._signing_key = None
    
    def log(
        self,
        level: LogLevel,
        component: str,
        message: str,
        data: Optional[dict] = None,
    ) -> LogEntry:
        """
        Log an entry in the configured format(s).
        
        Args:
            level: Log severity level
            component: Component name generating the log
            message: Human-readable log message
            data: Optional additional data to include
        
        Returns:
            The created LogEntry object
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Mask sensitive data
        masked_data = self.mask_sensitive_data(data or {})
        
        # Create entry
        entry = LogEntry(
            timestamp=timestamp,
            level=level,
            component=component,
            message=message,
            data=masked_data,
            signature=None,
        )
        
        # Sign if audit mode is enabled
        if self._audit_mode and self._signing_key:
            entry.signature = self._sign_entry(entry)
        
        # Store entry
        self._entries.append(entry)
        
        # Output in configured format(s)
        self._output_entry(entry)
        
        return entry
    
    def log_error(
        self,
        component: str,
        message: str,
        error: Optional[Exception] = None,
        request_url: Optional[str] = None,
        response_status_code: Optional[int] = None,
        additional_data: Optional[dict] = None,
    ) -> LogEntry:
        """
        Log an error with full context.
        
        Args:
            component: Component name generating the log
            message: Human-readable error message
            error: Optional exception object
            request_url: Optional URL of the failed request
            response_status_code: Optional HTTP status code
            additional_data: Optional additional context data
        
        Returns:
            The created LogEntry object
        """
        data = additional_data.copy() if additional_data else {}
        
        # Add error context
        if error is not None:
            data["error_message"] = str(error)
            data["error_type"] = type(error).__name__
        
        if request_url is not None:
            data["request_url"] = request_url
        
        if response_status_code is not None:
            data["response_status_code"] = response_status_code
        
        return self.log(LogLevel.ERROR, component, message, data)
    
    def mask_sensitive_data(self, data: dict) -> dict:
        """
        Recursively mask sensitive data in a dictionary.
        
        Args:
            data: Dictionary potentially containing sensitive data
        
        Returns:
            New dictionary with sensitive values masked
        """
        if not isinstance(data, dict):
            return data
        
        masked = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            # Check if key matches any sensitive pattern
            is_sensitive = any(
                sensitive_key in key_lower
                for sensitive_key in self.SENSITIVE_KEYS
            )
            
            if is_sensitive:
                masked[key] = self.MASK_VALUE
            elif isinstance(value, dict):
                masked[key] = self.mask_sensitive_data(value)
            elif isinstance(value, list):
                masked[key] = [
                    self.mask_sensitive_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                masked[key] = value
        
        return masked
    
    def _sign_entry(self, entry: LogEntry) -> str:
        """
        Sign a log entry with HMAC-SHA256.
        
        Args:
            entry: Log entry to sign
        
        Returns:
            Hex-encoded HMAC signature
        """
        if not self._signing_key:
            raise RuntimeError("Signing key not set")
        
        # Create signable content (excluding signature field)
        signable = {
            "timestamp": entry.timestamp,
            "level": entry.level.value,
            "component": entry.component,
            "message": entry.message,
            "data": entry.data,
        }
        
        content = json.dumps(signable, sort_keys=True, ensure_ascii=False)
        
        return hmac.new(
            self._signing_key,
            content.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def verify_signature(self, entry: LogEntry) -> bool:
        """
        Verify the signature of a log entry.
        
        Args:
            entry: Log entry to verify
        
        Returns:
            True if signature is valid, False otherwise
        """
        if not entry.signature:
            return False
        
        if not self._signing_key:
            return False
        
        expected = self._sign_entry(entry)
        return hmac.compare_digest(entry.signature, expected)

    def _output_entry(self, entry: LogEntry) -> None:
        """
        Output a log entry in the configured format(s).
        
        Args:
            entry: Log entry to output
        """
        if self._output_format in ("json", "both"):
            json_line = self._format_json(entry)
            self._output_stream.write(json_line + "\n")
        
        if self._output_format in ("text", "both"):
            text_line = self._format_text(entry)
            self._output_stream.write(text_line + "\n")
        
        self._output_stream.flush()
    
    def _format_json(self, entry: LogEntry) -> str:
        """
        Format a log entry as JSON.
        
        Args:
            entry: Log entry to format
        
        Returns:
            JSON string representation
        """
        obj = {
            "timestamp": entry.timestamp,
            "level": entry.level.value,
            "component": entry.component,
            "message": entry.message,
            "data": entry.data,
        }
        
        if entry.signature:
            obj["signature"] = entry.signature
        
        return json.dumps(obj, ensure_ascii=False)
    
    def _format_text(self, entry: LogEntry) -> str:
        """
        Format a log entry as human-readable text.
        
        Args:
            entry: Log entry to format
        
        Returns:
            Human-readable text representation
        """
        # Format: [TIMESTAMP] LEVEL [COMPONENT] MESSAGE {data}
        level_str = entry.level.value.upper()
        
        parts = [
            f"[{entry.timestamp}]",
            level_str,
            f"[{entry.component}]",
            entry.message,
        ]
        
        if entry.data:
            data_str = json.dumps(entry.data, ensure_ascii=False)
            parts.append(data_str)
        
        text = " ".join(parts)
        
        if entry.signature:
            text += f" [sig:{entry.signature[:16]}...]"
        
        return text
    
    def get_json_output(self, entry: LogEntry) -> str:
        """
        Get JSON output for an entry (for testing).
        
        Args:
            entry: Log entry to format
        
        Returns:
            JSON string representation
        """
        return self._format_json(entry)
    
    def get_text_output(self, entry: LogEntry) -> str:
        """
        Get text output for an entry (for testing).
        
        Args:
            entry: Log entry to format
        
        Returns:
            Human-readable text representation
        """
        return self._format_text(entry)
    
    def clear_entries(self) -> None:
        """Clear all stored log entries (for testing)."""
        self._entries.clear()
