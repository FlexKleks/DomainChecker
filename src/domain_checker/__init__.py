"""
Domain Checker - High-security multi-TLD domain availability checker.

This package provides a secure, modular system for checking domain availability
across multiple TLDs using RDAP and WHOIS protocols with conservative decision logic.
"""

__version__ = "0.1.0"
__author__ = "Domain Checker Team"

from domain_checker.exceptions import (
    DomainCheckerError,
    ValidationError,
    NetworkError,
    ProtocolError,
    RateLimitError,
    PersistenceError,
    TamperingError,
    NotificationError,
)
from domain_checker.enums import (
    AvailabilityStatus,
    Confidence,
    LogLevel,
    DomainValidationErrorCode,
    RDAPErrorCode,
    RDAPStatus,
    WHOISErrorCode,
    WHOISStatus,
)
from domain_checker.domain_validator import (
    DomainValidator,
    DomainValidationResult,
    DomainValidationError,
)
from domain_checker.config import (
    TLDConfig,
    RateLimitRule,
    RateLimitConfig,
    RetryConfig,
    TelegramConfig,
    DiscordConfig,
    EmailConfig,
    WebhookConfig,
    NotificationConfig,
    PersistenceConfig,
    LoggingConfig,
    SystemConfig,
)
from domain_checker.models import (
    Domain,
    SourceResult,
    CheckMetadata,
    CheckResult,
    CheckHistoryEntry,
    DomainState,
    StoredState,
    SessionError,
    CheckSession,
    PersistedData,
)
from domain_checker.rdap_client import (
    RDAPClient,
    RDAPResponse,
    RDAPParsedFields,
    RDAPEvent,
    RDAPError,
)
from domain_checker.whois_client import (
    WHOISClient,
    WHOISResponse,
    WHOISError,
)
from domain_checker.rate_limiter import (
    RateLimiter,
    RateLimitStatus,
)
from domain_checker.retry_manager import (
    RetryManager,
    RetryResult,
)
from domain_checker.decision_engine import (
    DecisionEngine,
    EvaluationContext,
)
from domain_checker.state_store import (
    StateStore,
)
from domain_checker.audit_logger import (
    AuditLogger,
    LogEntry,
)
from domain_checker.notifications import (
    NotificationPayload,
    NotificationResult,
    NotificationChannel,
    TelegramChannel,
    DiscordChannel,
    EmailChannel,
    WebhookChannel,
    NotificationRouter,
)
from domain_checker.i18n import (
    get_message,
    get_all_message_keys,
    has_translation,
    get_missing_translations,
    validate_translations,
    TRANSLATIONS,
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
)
from domain_checker.scheduler import (
    Scheduler,
    CronSchedule,
    CronField,
    CronParser,
    CronParseError,
    ScheduledTask,
)
from domain_checker.orchestrator import (
    CheckOrchestrator,
    OrchestratorResult,
)
from domain_checker.cli import (
    main as cli_main,
    create_parser,
    create_default_config,
    load_config_from_file,
    save_config_to_file,
)
from domain_checker.self_test import (
    SelfTest,
    SelfTestResult,
    EndpointTestResult,
    ConfigValidationResult,
    run_self_test,
)

__all__ = [
    # Exceptions
    "DomainCheckerError",
    "ValidationError",
    "NetworkError",
    "ProtocolError",
    "RateLimitError",
    "PersistenceError",
    "TamperingError",
    "NotificationError",
    # Enums
    "AvailabilityStatus",
    "Confidence",
    "LogLevel",
    "DomainValidationErrorCode",
    "RDAPErrorCode",
    "RDAPStatus",
    "WHOISErrorCode",
    "WHOISStatus",
    # Domain Validator
    "DomainValidator",
    "DomainValidationResult",
    "DomainValidationError",
    # Configuration
    "TLDConfig",
    "RateLimitRule",
    "RateLimitConfig",
    "RetryConfig",
    "TelegramConfig",
    "DiscordConfig",
    "EmailConfig",
    "WebhookConfig",
    "NotificationConfig",
    "PersistenceConfig",
    "LoggingConfig",
    "SystemConfig",
    # Models
    "Domain",
    "SourceResult",
    "CheckMetadata",
    "CheckResult",
    "CheckHistoryEntry",
    "DomainState",
    "StoredState",
    "SessionError",
    "CheckSession",
    "PersistedData",
    # RDAP Client
    "RDAPClient",
    "RDAPResponse",
    "RDAPParsedFields",
    "RDAPEvent",
    "RDAPError",
    # WHOIS Client
    "WHOISClient",
    "WHOISResponse",
    "WHOISError",
    # Rate Limiter
    "RateLimiter",
    "RateLimitStatus",
    # Retry Manager
    "RetryManager",
    "RetryResult",
    # Decision Engine
    "DecisionEngine",
    "EvaluationContext",
    # State Store
    "StateStore",
    # Audit Logger
    "AuditLogger",
    "LogEntry",
    # Notifications
    "NotificationPayload",
    "NotificationResult",
    "NotificationChannel",
    "TelegramChannel",
    "DiscordChannel",
    "EmailChannel",
    "WebhookChannel",
    "NotificationRouter",
    # I18n
    "get_message",
    "get_all_message_keys",
    "has_translation",
    "get_missing_translations",
    "validate_translations",
    "TRANSLATIONS",
    "SUPPORTED_LANGUAGES",
    "DEFAULT_LANGUAGE",
    # Scheduler
    "Scheduler",
    "CronSchedule",
    "CronField",
    "CronParser",
    "CronParseError",
    "ScheduledTask",
    # Orchestrator
    "CheckOrchestrator",
    "OrchestratorResult",
    # CLI
    "cli_main",
    "create_parser",
    "create_default_config",
    "load_config_from_file",
    "save_config_to_file",
    # Self-Test
    "SelfTest",
    "SelfTestResult",
    "EndpointTestResult",
    "ConfigValidationResult",
    "run_self_test",
]
