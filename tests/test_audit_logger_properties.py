"""
Property-based tests for Audit Logger module.

Uses Hypothesis for property-based testing to verify correctness properties
defined in the design document.
"""

import json
from io import StringIO

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from domain_checker.enums import LogLevel
from domain_checker.audit_logger import AuditLogger, LogEntry


# Strategies for generating valid test data

@st.composite
def log_level_strategy(draw) -> LogLevel:
    """Generate valid LogLevel values."""
    return draw(st.sampled_from(list(LogLevel)))


@st.composite
def component_name_strategy(draw) -> str:
    """Generate valid component names."""
    return draw(st.text(
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"),
        min_size=1,
        max_size=50,
    ))


@st.composite
def message_strategy(draw) -> str:
    """Generate valid log messages."""
    return draw(st.text(
        alphabet=st.characters(
            whitelist_categories=('L', 'N', 'P', 'S', 'Z'),
            blacklist_characters='\x00\n\r',
        ),
        min_size=1,
        max_size=200,
    ))


@st.composite
def non_sensitive_key_strategy(draw) -> str:
    """Generate keys that are NOT sensitive."""
    # Avoid any key that contains sensitive patterns
    sensitive_patterns = [
        'token', 'secret', 'password', 'api_key', 'hmac_secret',
        'bot_token', 'webhook_url', 'auth', 'authorization',
        'credential', 'private_key', 'access_token',
        'refresh_token', 'session_token', 'api_secret',
    ]
    
    key = draw(st.text(
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_"),
        min_size=1,
        max_size=20,
    ))
    
    # Ensure key doesn't contain any sensitive pattern
    key_lower = key.lower()
    for pattern in sensitive_patterns:
        assume(pattern not in key_lower)
    
    return key


@st.composite
def sensitive_key_strategy(draw) -> str:
    """Generate keys that ARE sensitive."""
    base_keys = [
        'token', 'secret', 'password', 'api_key', 'hmac_secret',
        'bot_token', 'webhook_url', 'auth', 'authorization',
        'credential', 'credentials', 'private_key', 'access_token',
        'refresh_token', 'session_token', 'api_secret',
    ]
    
    base = draw(st.sampled_from(base_keys))
    
    # Optionally add prefix/suffix
    prefix = draw(st.sampled_from(['', 'my_', 'user_', 'app_']))
    suffix = draw(st.sampled_from(['', '_value', '_data', '_1']))
    
    return f"{prefix}{base}{suffix}"


@st.composite
def simple_value_strategy(draw):
    """Generate simple JSON-serializable values."""
    return draw(st.one_of(
        st.text(min_size=0, max_size=50),
        st.integers(min_value=-1000, max_value=1000),
        st.floats(allow_nan=False, allow_infinity=False, min_value=-1000, max_value=1000),
        st.booleans(),
        st.none(),
    ))


@st.composite
def non_sensitive_data_strategy(draw) -> dict:
    """Generate data dictionaries without sensitive keys."""
    num_keys = draw(st.integers(min_value=0, max_value=5))
    data = {}
    for _ in range(num_keys):
        key = draw(non_sensitive_key_strategy())
        value = draw(simple_value_strategy())
        data[key] = value
    return data


@st.composite
def signing_key_strategy(draw) -> str:
    """Generate valid signing keys."""
    return draw(st.text(
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
        min_size=16,
        max_size=64,
    ))


@st.composite
def error_context_strategy(draw) -> dict:
    """Generate error context data."""
    error_types = ['ValueError', 'TypeError', 'RuntimeError', 'ConnectionError', 'TimeoutError']
    
    return {
        'error_message': draw(message_strategy()),
        'error_type': draw(st.sampled_from(error_types)),
        'request_url': draw(st.one_of(
            st.none(),
            st.just("https://example.com/api"),
            st.just("https://rdap.example.org/domain/test.com"),
        )),
        'response_status_code': draw(st.one_of(
            st.none(),
            st.sampled_from([200, 400, 404, 429, 500, 503]),
        )),
    }


class TestDualFormatProperty:
    """
    Property-based tests for dual format logging.
    
    **Feature: domain-availability-checker, Property 27: Log entries in dual format**
    **Validates: Requirements 8.1**
    """

    @given(
        level=log_level_strategy(),
        component=component_name_strategy(),
        message=message_strategy(),
        data=non_sensitive_data_strategy(),
    )
    @settings(max_examples=100)
    def test_dual_format_produces_both_outputs(
        self,
        level: LogLevel,
        component: str,
        message: str,
        data: dict,
    ) -> None:
        """
        Property 27: Log entries in dual format.
        
        *For any* log entry when output_format is "both", the logger SHALL produce
        both a valid JSON string and a human-readable text line.
        
        **Feature: domain-availability-checker, Property 27: Log entries in dual format**
        **Validates: Requirements 8.1**
        """
        output = StringIO()
        logger = AuditLogger(output_format="both", output_stream=output)
        
        entry = logger.log(level, component, message, data)
        
        output_text = output.getvalue()
        lines = output_text.strip().split('\n')
        
        # Should have exactly 2 lines (JSON and text)
        assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}"
        
        # First line should be valid JSON
        json_line = lines[0]
        parsed_json = json.loads(json_line)
        
        assert parsed_json["level"] == level.value
        assert parsed_json["component"] == component
        assert parsed_json["message"] == message
        assert "timestamp" in parsed_json
        
        # Second line should be human-readable text
        text_line = lines[1]
        assert level.value.upper() in text_line
        assert component in text_line
        assert message in text_line

    @given(
        level=log_level_strategy(),
        component=component_name_strategy(),
        message=message_strategy(),
        data=non_sensitive_data_strategy(),
    )
    @settings(max_examples=100)
    def test_json_only_format(
        self,
        level: LogLevel,
        component: str,
        message: str,
        data: dict,
    ) -> None:
        """
        Property 27b: JSON-only format produces valid JSON.
        
        *For any* log entry when output_format is "json", the logger SHALL produce
        only a valid JSON string.
        
        **Feature: domain-availability-checker, Property 27: Log entries in dual format**
        **Validates: Requirements 8.1**
        """
        output = StringIO()
        logger = AuditLogger(output_format="json", output_stream=output)
        
        logger.log(level, component, message, data)
        
        output_text = output.getvalue()
        lines = [l for l in output_text.strip().split('\n') if l]
        
        # Should have exactly 1 line
        assert len(lines) == 1
        
        # Should be valid JSON
        parsed = json.loads(lines[0])
        assert parsed["level"] == level.value
        assert parsed["component"] == component
        assert parsed["message"] == message

    @given(
        level=log_level_strategy(),
        component=component_name_strategy(),
        message=message_strategy(),
        data=non_sensitive_data_strategy(),
    )
    @settings(max_examples=100)
    def test_text_only_format(
        self,
        level: LogLevel,
        component: str,
        message: str,
        data: dict,
    ) -> None:
        """
        Property 27c: Text-only format produces human-readable text.
        
        *For any* log entry when output_format is "text", the logger SHALL produce
        only a human-readable text line.
        
        **Feature: domain-availability-checker, Property 27: Log entries in dual format**
        **Validates: Requirements 8.1**
        """
        output = StringIO()
        logger = AuditLogger(output_format="text", output_stream=output)
        
        logger.log(level, component, message, data)
        
        output_text = output.getvalue()
        lines = [l for l in output_text.strip().split('\n') if l]
        
        # Should have exactly 1 line
        assert len(lines) == 1
        
        # Should contain expected components
        text_line = lines[0]
        assert level.value.upper() in text_line
        assert component in text_line
        assert message in text_line


class TestAuditSigningProperty:
    """
    Property-based tests for audit mode signing.
    
    **Feature: domain-availability-checker, Property 28: Audit mode signs log entries**
    **Validates: Requirements 8.2**
    """

    @given(
        level=log_level_strategy(),
        component=component_name_strategy(),
        message=message_strategy(),
        data=non_sensitive_data_strategy(),
        signing_key=signing_key_strategy(),
    )
    @settings(max_examples=100)
    def test_audit_mode_signs_entries(
        self,
        level: LogLevel,
        component: str,
        message: str,
        data: dict,
        signing_key: str,
    ) -> None:
        """
        Property 28: Audit mode signs log entries.
        
        *For any* log entry when audit_mode is enabled, the entry SHALL contain
        a signature field that is a valid HMAC of the entry content.
        
        **Feature: domain-availability-checker, Property 28: Audit mode signs log entries**
        **Validates: Requirements 8.2**
        """
        output = StringIO()
        logger = AuditLogger(output_format="json", output_stream=output)
        logger.enable_audit_mode(signing_key)
        
        entry = logger.log(level, component, message, data)
        
        # Entry should have a signature
        assert entry.signature is not None
        assert len(entry.signature) == 64  # SHA256 hex digest length
        
        # Signature should be verifiable
        assert logger.verify_signature(entry)
        
        # JSON output should include signature
        output_text = output.getvalue()
        parsed = json.loads(output_text.strip())
        assert "signature" in parsed
        assert parsed["signature"] == entry.signature

    @given(
        level=log_level_strategy(),
        component=component_name_strategy(),
        message=message_strategy(),
        data=non_sensitive_data_strategy(),
        signing_key=signing_key_strategy(),
    )
    @settings(max_examples=100)
    def test_no_signature_without_audit_mode(
        self,
        level: LogLevel,
        component: str,
        message: str,
        data: dict,
        signing_key: str,
    ) -> None:
        """
        Property 28b: No signature without audit mode.
        
        *For any* log entry when audit_mode is disabled, the entry SHALL NOT
        contain a signature field.
        
        **Feature: domain-availability-checker, Property 28: Audit mode signs log entries**
        **Validates: Requirements 8.2**
        """
        output = StringIO()
        logger = AuditLogger(output_format="json", output_stream=output)
        # Audit mode NOT enabled
        
        entry = logger.log(level, component, message, data)
        
        # Entry should NOT have a signature
        assert entry.signature is None
        
        # JSON output should NOT include signature
        output_text = output.getvalue()
        parsed = json.loads(output_text.strip())
        assert "signature" not in parsed

    @given(
        level=log_level_strategy(),
        component=component_name_strategy(),
        message=message_strategy(),
        data=non_sensitive_data_strategy(),
        signing_key=signing_key_strategy(),
    )
    @settings(max_examples=100)
    def test_tampered_entry_fails_verification(
        self,
        level: LogLevel,
        component: str,
        message: str,
        data: dict,
        signing_key: str,
    ) -> None:
        """
        Property 28c: Tampered entries fail verification.
        
        *For any* signed log entry, modifying any field SHALL cause signature
        verification to fail.
        
        **Feature: domain-availability-checker, Property 28: Audit mode signs log entries**
        **Validates: Requirements 8.2**
        """
        output = StringIO()
        logger = AuditLogger(output_format="json", output_stream=output)
        logger.enable_audit_mode(signing_key)
        
        entry = logger.log(level, component, message, data)
        
        # Original should verify
        assert logger.verify_signature(entry)
        
        # Create tampered entry
        tampered = LogEntry(
            timestamp=entry.timestamp,
            level=entry.level,
            component=entry.component,
            message=entry.message + " TAMPERED",  # Modified message
            data=entry.data,
            signature=entry.signature,  # Keep original signature
        )
        
        # Tampered entry should fail verification
        assert not logger.verify_signature(tampered)


class TestSensitiveDataMaskingProperty:
    """
    Property-based tests for sensitive data masking.
    
    **Feature: domain-availability-checker, Property 29: Sensitive data masked in logs**
    **Validates: Requirements 8.3**
    """

    @given(
        sensitive_key=sensitive_key_strategy(),
        sensitive_value=st.text(
            alphabet=st.sampled_from("QWXYZ"),  # Use unique chars unlikely to appear elsewhere
            min_size=5,
            max_size=20,
        ),
        level=log_level_strategy(),
        component=component_name_strategy(),
        message=message_strategy(),
    )
    @settings(max_examples=100)
    def test_sensitive_data_masked(
        self,
        sensitive_key: str,
        sensitive_value: str,
        level: LogLevel,
        component: str,
        message: str,
    ) -> None:
        """
        Property 29: Sensitive data masked in logs.
        
        *For any* log entry data containing keys matching sensitive patterns
        (token, secret, password, api_key), the values SHALL be replaced
        with "***MASKED***".
        
        **Feature: domain-availability-checker, Property 29: Sensitive data masked in logs**
        **Validates: Requirements 8.3**
        """
        output = StringIO()
        logger = AuditLogger(output_format="json", output_stream=output)
        
        data = {sensitive_key: sensitive_value}
        entry = logger.log(level, component, message, data)
        
        # Entry data should have masked value
        assert entry.data[sensitive_key] == "***MASKED***"
        
        # Parse the JSON output and verify the data field has masked value
        output_text = output.getvalue()
        parsed = json.loads(output_text.strip())
        assert parsed["data"][sensitive_key] == "***MASKED***"
        
        # Masked value should appear in output
        assert "***MASKED***" in output_text

    @given(
        non_sensitive_key=non_sensitive_key_strategy(),
        value=st.text(min_size=1, max_size=50),
        level=log_level_strategy(),
        component=component_name_strategy(),
        message=message_strategy(),
    )
    @settings(max_examples=100)
    def test_non_sensitive_data_not_masked(
        self,
        non_sensitive_key: str,
        value: str,
        level: LogLevel,
        component: str,
        message: str,
    ) -> None:
        """
        Property 29b: Non-sensitive data is not masked.
        
        *For any* log entry data containing keys that do NOT match sensitive patterns,
        the values SHALL be preserved unchanged.
        
        **Feature: domain-availability-checker, Property 29: Sensitive data masked in logs**
        **Validates: Requirements 8.3**
        """
        output = StringIO()
        logger = AuditLogger(output_format="json", output_stream=output)
        
        data = {non_sensitive_key: value}
        entry = logger.log(level, component, message, data)
        
        # Entry data should have original value
        assert entry.data[non_sensitive_key] == value

    @given(
        sensitive_key=sensitive_key_strategy(),
        sensitive_value=st.text(min_size=1, max_size=50),
        level=log_level_strategy(),
        component=component_name_strategy(),
        message=message_strategy(),
    )
    @settings(max_examples=100)
    def test_nested_sensitive_data_masked(
        self,
        sensitive_key: str,
        sensitive_value: str,
        level: LogLevel,
        component: str,
        message: str,
    ) -> None:
        """
        Property 29c: Nested sensitive data is masked.
        
        *For any* log entry data containing nested dictionaries with sensitive keys,
        the values SHALL be masked at all nesting levels.
        
        **Feature: domain-availability-checker, Property 29: Sensitive data masked in logs**
        **Validates: Requirements 8.3**
        """
        output = StringIO()
        logger = AuditLogger(output_format="json", output_stream=output)
        
        data = {
            "config": {
                sensitive_key: sensitive_value,
                "other": "visible",
            }
        }
        entry = logger.log(level, component, message, data)
        
        # Nested sensitive value should be masked
        assert entry.data["config"][sensitive_key] == "***MASKED***"
        # Non-sensitive nested value should be preserved
        assert entry.data["config"]["other"] == "visible"


class TestErrorContextProperty:
    """
    Property-based tests for error context logging.
    
    **Feature: domain-availability-checker, Property 30: Error logs include full context**
    **Validates: Requirements 8.4**
    """

    @given(
        component=component_name_strategy(),
        message=message_strategy(),
        error_message=message_strategy(),
        error_type=st.sampled_from(['ValueError', 'TypeError', 'RuntimeError', 'ConnectionError']),
    )
    @settings(max_examples=100)
    def test_error_logs_include_error_context(
        self,
        component: str,
        message: str,
        error_message: str,
        error_type: str,
    ) -> None:
        """
        Property 30: Error logs include full context.
        
        *For any* error-level log entry, the data field SHALL contain:
        error message, error type, and if applicable, request URL and response status code.
        
        **Feature: domain-availability-checker, Property 30: Error logs include full context**
        **Validates: Requirements 8.4**
        """
        output = StringIO()
        logger = AuditLogger(output_format="json", output_stream=output)
        
        # Create an exception
        error = ValueError(error_message)
        
        entry = logger.log_error(
            component=component,
            message=message,
            error=error,
            request_url="https://example.com/api",
            response_status_code=500,
        )
        
        # Entry should be ERROR level
        assert entry.level == LogLevel.ERROR
        
        # Data should contain error context
        assert "error_message" in entry.data
        assert "error_type" in entry.data
        assert entry.data["error_type"] == "ValueError"
        
        # Data should contain request context
        assert "request_url" in entry.data
        assert entry.data["request_url"] == "https://example.com/api"
        
        assert "response_status_code" in entry.data
        assert entry.data["response_status_code"] == 500

    @given(
        component=component_name_strategy(),
        message=message_strategy(),
        error_message=message_strategy(),
    )
    @settings(max_examples=100)
    def test_error_logs_with_minimal_context(
        self,
        component: str,
        message: str,
        error_message: str,
    ) -> None:
        """
        Property 30b: Error logs work with minimal context.
        
        *For any* error-level log entry with only an error (no request context),
        the data field SHALL contain at least error message and error type.
        
        **Feature: domain-availability-checker, Property 30: Error logs include full context**
        **Validates: Requirements 8.4**
        """
        output = StringIO()
        logger = AuditLogger(output_format="json", output_stream=output)
        
        error = RuntimeError(error_message)
        
        entry = logger.log_error(
            component=component,
            message=message,
            error=error,
        )
        
        # Entry should be ERROR level
        assert entry.level == LogLevel.ERROR
        
        # Data should contain error context
        assert "error_message" in entry.data
        assert entry.data["error_message"] == error_message
        assert "error_type" in entry.data
        assert entry.data["error_type"] == "RuntimeError"
        
        # Optional fields should not be present
        assert "request_url" not in entry.data
        assert "response_status_code" not in entry.data

    @given(
        component=component_name_strategy(),
        message=message_strategy(),
        status_code=st.sampled_from([400, 404, 429, 500, 502, 503]),
    )
    @settings(max_examples=100)
    def test_error_logs_with_http_context_only(
        self,
        component: str,
        message: str,
        status_code: int,
    ) -> None:
        """
        Property 30c: Error logs work with HTTP context only.
        
        *For any* error-level log entry with HTTP context but no exception,
        the data field SHALL contain request URL and response status code.
        
        **Feature: domain-availability-checker, Property 30: Error logs include full context**
        **Validates: Requirements 8.4**
        """
        output = StringIO()
        logger = AuditLogger(output_format="json", output_stream=output)
        
        entry = logger.log_error(
            component=component,
            message=message,
            request_url="https://rdap.example.org/domain/test.com",
            response_status_code=status_code,
        )
        
        # Entry should be ERROR level
        assert entry.level == LogLevel.ERROR
        
        # Data should contain HTTP context
        assert "request_url" in entry.data
        assert "response_status_code" in entry.data
        assert entry.data["response_status_code"] == status_code
        
        # Error fields should not be present (no exception provided)
        assert "error_message" not in entry.data
        assert "error_type" not in entry.data

    @given(
        component=component_name_strategy(),
        message=message_strategy(),
        error_message=message_strategy(),
        additional_key=non_sensitive_key_strategy(),
        additional_value=st.text(min_size=1, max_size=30),
    )
    @settings(max_examples=100)
    def test_error_logs_preserve_additional_data(
        self,
        component: str,
        message: str,
        error_message: str,
        additional_key: str,
        additional_value: str,
    ) -> None:
        """
        Property 30d: Error logs preserve additional data.
        
        *For any* error-level log entry with additional_data, all provided
        data SHALL be preserved alongside error context.
        
        **Feature: domain-availability-checker, Property 30: Error logs include full context**
        **Validates: Requirements 8.4**
        """
        output = StringIO()
        logger = AuditLogger(output_format="json", output_stream=output)
        
        error = ValueError(error_message)
        additional_data = {additional_key: additional_value}
        
        entry = logger.log_error(
            component=component,
            message=message,
            error=error,
            additional_data=additional_data,
        )
        
        # Entry should contain both error context and additional data
        assert "error_message" in entry.data
        assert "error_type" in entry.data
        assert additional_key in entry.data
        assert entry.data[additional_key] == additional_value
