"""
Configuration dataclasses for the domain checker system.

This module defines all configuration structures used throughout the system,
including TLD-specific settings, rate limiting, retry logic, notifications,
persistence, and logging configuration.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TLDConfig:
    """Configuration for a specific TLD."""

    tld: str
    rdap_endpoint: str
    secondary_rdap_endpoint: Optional[str] = None
    whois_server: Optional[str] = None
    whois_enabled: bool = False


@dataclass
class RateLimitRule:
    """A single rate limit rule."""

    max_requests: int
    window_seconds: float
    min_delay_seconds: float = 0.0


@dataclass
class RateLimitConfig:
    """Rate limiting configuration for all levels."""

    per_tld: dict[str, RateLimitRule] = field(default_factory=dict)
    per_endpoint: dict[str, RateLimitRule] = field(default_factory=dict)
    global_limit: Optional[RateLimitRule] = None
    per_ip: Optional[RateLimitRule] = None


@dataclass
class RetryConfig:
    """Retry behavior configuration."""

    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    retryable_errors: list[str] = field(
        default_factory=lambda: ["timeout", "server_error", "rate_limited"]
    )


@dataclass
class TelegramConfig:
    """Telegram notification channel configuration."""

    bot_token: str
    chat_id: str


@dataclass
class DiscordConfig:
    """Discord notification channel configuration."""

    webhook_url: str


@dataclass
class EmailConfig:
    """Email notification channel configuration."""

    smtp_host: str
    smtp_port: int
    username: str
    password: str
    from_address: str
    to_addresses: list[str] = field(default_factory=list)


@dataclass
class WebhookConfig:
    """Generic webhook notification channel configuration."""

    url: str
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class NotificationConfig:
    """Notification channels configuration."""

    telegram: Optional[TelegramConfig] = None
    discord: Optional[DiscordConfig] = None
    email: Optional[EmailConfig] = None
    webhook: Optional[WebhookConfig] = None


@dataclass
class PersistenceConfig:
    """Persistence and state storage configuration."""

    state_file_path: Path
    hmac_secret: str


@dataclass
class LoggingConfig:
    """Logging and audit configuration."""

    level: str = "info"
    audit_mode: bool = False
    audit_signing_key: Optional[str] = None
    output_format: str = "both"  # 'json', 'text', 'both'


@dataclass
class SystemConfig:
    """Main system configuration combining all sub-configurations."""

    tlds: list[TLDConfig]
    rate_limits: RateLimitConfig
    retry: RetryConfig
    notifications: NotificationConfig
    persistence: PersistenceConfig
    logging: LoggingConfig
    language: str = "de"  # 'de' or 'en'
    simulation_mode: bool = False
    startup_self_test: bool = True
