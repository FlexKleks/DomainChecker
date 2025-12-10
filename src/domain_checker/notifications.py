"""
Notification Router module for the domain checker system.

Provides notification channels (Telegram, Discord, Email, Webhook) and a router
that handles notification delivery with retry logic and status-based suppression.

Requirements covered:
- 9.1: Send notification when domain is first detected as available
- 9.2: Suppress notification when domain was previously available and remains available
- 9.3: Support Telegram, Discord, Email, and Webhook channels
- 9.4: Retry delivery with exponential backoff on failure
- 9.5: Log failure with full error details when all retries fail
"""

import asyncio
import json
import smtplib
import ssl
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Protocol, runtime_checkable

import httpx

from .config import (
    DiscordConfig,
    EmailConfig,
    RetryConfig,
    TelegramConfig,
    WebhookConfig,
)
from .enums import AvailabilityStatus, LogLevel
from .exceptions import NotificationError
from .models import DomainState


def format_timestamp(iso_timestamp: str, language: str = "de") -> str:
    """
    Format an ISO timestamp to a human-readable format.

    Args:
        iso_timestamp: ISO 8601 timestamp string
        language: 'de' for German, 'en' for English

    Returns:
        Formatted timestamp string
    """
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))

        if language == "de":
            # German format: 10.12.2025, 05:29 Uhr
            return dt.strftime("%d.%m.%Y, %H:%M Uhr")
        else:
            # English format: Dec 10, 2025, 5:29 AM
            return dt.strftime("%b %d, %Y, %I:%M %p")
    except (ValueError, AttributeError):
        return iso_timestamp


@dataclass
class NotificationPayload:
    """Payload for a notification message."""

    domain: str
    status: str
    timestamp: str
    language: str = "de"  # 'de' or 'en'

    def get_formatted_timestamp(self) -> str:
        """Get timestamp formatted for the configured language."""
        return format_timestamp(self.timestamp, self.language)


@dataclass
class NotificationResult:
    """Result of a notification delivery attempt."""

    channel: str
    success: bool
    error: Optional[str] = None
    attempts: int = 1


@runtime_checkable
class NotificationChannel(Protocol):
    """Protocol defining the interface for notification channels."""

    @abstractmethod
    async def send(self, payload: NotificationPayload) -> bool:
        """
        Send a notification.

        Args:
            payload: The notification payload to send

        Returns:
            True if delivery was successful, False otherwise
        """
        ...

    @abstractmethod
    def get_name(self) -> str:
        """
        Get the channel name.

        Returns:
            The name of this notification channel
        """
        ...


class TelegramChannel:
    """Telegram notification channel using Bot API."""

    def __init__(
        self, config: TelegramConfig, simulation_mode: bool = False
    ) -> None:
        """
        Initialize Telegram channel.

        Args:
            config: Telegram configuration with bot_token and chat_id
            simulation_mode: If True, no real network requests are made
        """
        self._bot_token = config.bot_token
        self._chat_id = config.chat_id
        self._base_url = f"https://api.telegram.org/bot{self._bot_token}"
        self._simulation_mode = simulation_mode

    async def send(self, payload: NotificationPayload) -> bool:
        """Send notification via Telegram Bot API."""
        if self._simulation_mode:
            # In simulation mode, return success without making network request
            return True

        message = self._format_message(payload)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self._base_url}/sendMessage",
                    json={
                        "chat_id": self._chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                    },
                    timeout=30.0,
                )
                return response.status_code == 200
            except Exception:
                return False

    def get_name(self) -> str:
        """Return channel name."""
        return "telegram"

    def _format_message(self, payload: NotificationPayload) -> str:
        """Format the notification message for Telegram."""
        formatted_time = payload.get_formatted_timestamp()

        if payload.language == "de":
            if payload.status == AvailabilityStatus.AVAILABLE.value:
                return (
                    f"🟢 <b>Domain verfügbar!</b>\n\n"
                    f"Domain: <code>{payload.domain}</code>\n"
                    f"Status: Verfügbar\n"
                    f"Zeit: {formatted_time}"
                )
            else:
                return (
                    f"🔴 <b>Domain-Status geändert</b>\n\n"
                    f"Domain: <code>{payload.domain}</code>\n"
                    f"Status: {payload.status}\n"
                    f"Zeit: {formatted_time}"
                )
        else:
            if payload.status == AvailabilityStatus.AVAILABLE.value:
                return (
                    f"🟢 <b>Domain available!</b>\n\n"
                    f"Domain: <code>{payload.domain}</code>\n"
                    f"Status: Available\n"
                    f"Time: {formatted_time}"
                )
            else:
                return (
                    f"🔴 <b>Domain status changed</b>\n\n"
                    f"Domain: <code>{payload.domain}</code>\n"
                    f"Status: {payload.status}\n"
                    f"Time: {formatted_time}"
                )


class DiscordChannel:
    """Discord notification channel using Webhooks."""

    def __init__(
        self, config: DiscordConfig, simulation_mode: bool = False
    ) -> None:
        """
        Initialize Discord channel.

        Args:
            config: Discord configuration with webhook_url
            simulation_mode: If True, no real network requests are made
        """
        self._webhook_url = config.webhook_url
        self._simulation_mode = simulation_mode

    async def send(self, payload: NotificationPayload) -> bool:
        """Send notification via Discord Webhook."""
        if self._simulation_mode:
            # In simulation mode, return success without making network request
            return True

        embed = self._format_embed(payload)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self._webhook_url,
                    json={"embeds": [embed]},
                    timeout=30.0,
                )
                # Discord returns 204 No Content on success
                return response.status_code in (200, 204)
            except Exception:
                return False

    def get_name(self) -> str:
        """Return channel name."""
        return "discord"

    def _format_embed(self, payload: NotificationPayload) -> dict:
        """Format the notification as a Discord embed."""
        is_available = payload.status == AvailabilityStatus.AVAILABLE.value
        formatted_time = payload.get_formatted_timestamp()
        time_label = "Zeit" if payload.language == "de" else "Time"

        if payload.language == "de":
            title = "Domain verfügbar!" if is_available else "Domain-Status geändert"
            status_text = "Verfügbar" if is_available else payload.status
        else:
            title = "Domain available!" if is_available else "Domain status changed"
            status_text = "Available" if is_available else payload.status

        return {
            "title": f"{'🟢' if is_available else '🔴'} {title}",
            "color": 0x00FF00 if is_available else 0xFF0000,
            "fields": [
                {"name": "Domain", "value": payload.domain, "inline": True},
                {"name": "Status", "value": status_text, "inline": True},
                {"name": time_label, "value": formatted_time, "inline": True},
            ],
        }


class EmailChannel:
    """Email notification channel using SMTP."""

    def __init__(
        self, config: EmailConfig, simulation_mode: bool = False
    ) -> None:
        """
        Initialize Email channel.

        Args:
            config: Email configuration with SMTP settings
            simulation_mode: If True, no real network requests are made
        """
        self._smtp_host = config.smtp_host
        self._smtp_port = config.smtp_port
        self._username = config.username
        self._password = config.password
        self._from_address = config.from_address
        self._to_addresses = config.to_addresses
        self._simulation_mode = simulation_mode

    async def send(self, payload: NotificationPayload) -> bool:
        """Send notification via Email."""
        if self._simulation_mode:
            # In simulation mode, return success without making network request
            return True

        # Run SMTP in executor to avoid blocking
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                None, self._send_sync, payload
            )
        except Exception:
            return False

    def _send_sync(self, payload: NotificationPayload) -> bool:
        """Synchronous email sending."""
        try:
            msg = self._format_email(payload)

            context = ssl.create_default_context()
            with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
                server.starttls(context=context)
                server.login(self._username, self._password)
                server.sendmail(
                    self._from_address,
                    self._to_addresses,
                    msg.as_string(),
                )
            return True
        except Exception:
            return False

    def get_name(self) -> str:
        """Return channel name."""
        return "email"

    def _format_email(self, payload: NotificationPayload) -> MIMEMultipart:
        """Format the notification as an email message."""
        is_available = payload.status == AvailabilityStatus.AVAILABLE.value
        formatted_time = payload.get_formatted_timestamp()

        if payload.language == "de":
            subject = (
                f"Domain {payload.domain} ist verfügbar!"
                if is_available
                else f"Domain-Status geändert: {payload.domain}"
            )
            body = (
                f"Domain: {payload.domain}\n"
                f"Status: {'Verfügbar' if is_available else payload.status}\n"
                f"Zeit: {formatted_time}\n"
            )
        else:
            subject = (
                f"Domain {payload.domain} is available!"
                if is_available
                else f"Domain status changed: {payload.domain}"
            )
            body = (
                f"Domain: {payload.domain}\n"
                f"Status: {'Available' if is_available else payload.status}\n"
                f"Time: {formatted_time}\n"
            )

        msg = MIMEMultipart()
        msg["From"] = self._from_address
        msg["To"] = ", ".join(self._to_addresses)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        return msg


class WebhookChannel:
    """Generic webhook notification channel using HTTP POST."""

    def __init__(
        self, config: WebhookConfig, simulation_mode: bool = False
    ) -> None:
        """
        Initialize Webhook channel.

        Args:
            config: Webhook configuration with URL and optional headers
            simulation_mode: If True, no real network requests are made
        """
        self._url = config.url
        self._headers = config.headers.copy()
        self._simulation_mode = simulation_mode

    async def send(self, payload: NotificationPayload) -> bool:
        """Send notification via HTTP POST webhook."""
        if self._simulation_mode:
            # In simulation mode, return success without making network request
            return True

        data = {
            "domain": payload.domain,
            "status": payload.status,
            "timestamp": payload.timestamp,
            "timestamp_formatted": payload.get_formatted_timestamp(),
            "language": payload.language,
        }

        headers = {"Content-Type": "application/json"}
        headers.update(self._headers)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self._url,
                    json=data,
                    headers=headers,
                    timeout=30.0,
                )
                return 200 <= response.status_code < 300
            except Exception:
                return False

    def get_name(self) -> str:
        """Return channel name."""
        return "webhook"



@dataclass
class RetryAttempt:
    """Record of a single retry attempt."""

    attempt_number: int
    error: str
    timestamp: str


class NotificationRouter:
    """
    Routes notifications to registered channels with retry logic.

    Implements:
    - Notification suppression for unchanged status (Req 7.3, 9.2)
    - First availability notification (Req 9.1)
    - Retry with exponential backoff (Req 9.4)
    - Error logging with full details (Req 9.5)
    """

    def __init__(
        self,
        retry_config: RetryConfig,
        logger: Optional["AuditLogger"] = None,
    ) -> None:
        """
        Initialize the notification router.

        Args:
            retry_config: Configuration for retry behavior
            logger: Optional audit logger for error logging
        """
        self._channels: list[NotificationChannel] = []
        self._retry_config = retry_config
        self._logger = logger

    def register_channel(self, channel: NotificationChannel) -> None:
        """
        Register a notification channel.

        Args:
            channel: The notification channel to register
        """
        self._channels.append(channel)

    def unregister_channel(self, channel_name: str) -> bool:
        """
        Unregister a notification channel by name.

        Args:
            channel_name: Name of the channel to unregister

        Returns:
            True if channel was found and removed, False otherwise
        """
        for i, channel in enumerate(self._channels):
            if channel.get_name() == channel_name:
                self._channels.pop(i)
                return True
        return False

    @property
    def channels(self) -> list[NotificationChannel]:
        """Get list of registered channels."""
        return self._channels.copy()

    def should_notify(
        self,
        current_status: AvailabilityStatus,
        previous_state: Optional[DomainState],
    ) -> bool:
        """
        Determine if a notification should be sent.

        Requirement 9.1: Notify when domain is first detected as available
        Requirement 9.2: Suppress when domain was previously available and remains available

        Args:
            current_status: The current availability status
            previous_state: The previous domain state (None if first check)

        Returns:
            True if notification should be sent, False otherwise
        """
        # Only notify for AVAILABLE status
        if current_status != AvailabilityStatus.AVAILABLE:
            return False

        # First check (no previous state) - notify
        if previous_state is None:
            return True

        # Previous status was not available, now available - notify
        if previous_state.last_status != AvailabilityStatus.AVAILABLE.value:
            return True

        # Previous status was available, still available - suppress
        return False

    async def notify(
        self,
        payload: NotificationPayload,
        current_status: AvailabilityStatus,
        previous_state: Optional[DomainState] = None,
    ) -> list[NotificationResult]:
        """
        Send notification to all registered channels with retry logic.

        Implements notification suppression based on status changes.

        Args:
            payload: The notification payload
            current_status: Current availability status
            previous_state: Previous domain state for suppression logic

        Returns:
            List of NotificationResult for each channel
        """
        # Check if notification should be suppressed
        if not self.should_notify(current_status, previous_state):
            return []

        results = []
        for channel in self._channels:
            result = await self._send_with_retry(channel, payload)
            results.append(result)

        return results

    async def notify_without_suppression(
        self,
        payload: NotificationPayload,
    ) -> list[NotificationResult]:
        """
        Send notification to all channels without suppression logic.

        Useful for testing or forced notifications.

        Args:
            payload: The notification payload

        Returns:
            List of NotificationResult for each channel
        """
        results = []
        for channel in self._channels:
            result = await self._send_with_retry(channel, payload)
            results.append(result)

        return results

    async def _send_with_retry(
        self,
        channel: NotificationChannel,
        payload: NotificationPayload,
    ) -> NotificationResult:
        """
        Send notification to a single channel with retry logic.

        Requirement 9.4: Retry with exponential backoff on failure
        Requirement 9.5: Log failure with full details when all retries fail

        Args:
            channel: The notification channel
            payload: The notification payload

        Returns:
            NotificationResult with success status and attempt count
        """
        channel_name = channel.get_name()
        max_attempts = self._retry_config.max_retries + 1
        attempts = 0
        retry_attempts: list[RetryAttempt] = []
        last_error: Optional[str] = None

        while attempts < max_attempts:
            attempts += 1
            try:
                success = await channel.send(payload)
                if success:
                    return NotificationResult(
                        channel=channel_name,
                        success=True,
                        error=None,
                        attempts=attempts,
                    )
                else:
                    last_error = "Channel returned failure"
                    retry_attempts.append(
                        RetryAttempt(
                            attempt_number=attempts,
                            error=last_error,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                        )
                    )
            except Exception as e:
                last_error = str(e)
                retry_attempts.append(
                    RetryAttempt(
                        attempt_number=attempts,
                        error=last_error,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )

            # Don't delay after the last attempt
            if attempts < max_attempts:
                delay = self._calculate_delay(attempts - 1)
                await asyncio.sleep(delay)

        # All retries failed - log error with full details
        self._log_all_retries_failed(
            channel_name=channel_name,
            payload=payload,
            retry_attempts=retry_attempts,
        )

        return NotificationResult(
            channel=channel_name,
            success=False,
            error=last_error,
            attempts=attempts,
        )

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay with exponential backoff.

        Args:
            attempt: The attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = self._retry_config.base_delay_seconds * (2 ** attempt)
        return min(delay, self._retry_config.max_delay_seconds)

    def _log_all_retries_failed(
        self,
        channel_name: str,
        payload: NotificationPayload,
        retry_attempts: list[RetryAttempt],
    ) -> None:
        """
        Log error when all notification retries fail.

        Requirement 9.5: Log failure with full error details

        Args:
            channel_name: Name of the failed channel
            payload: The original notification payload
            retry_attempts: List of all retry attempts with errors
        """
        if self._logger is None:
            return

        error_data = {
            "channel": channel_name,
            "domain": payload.domain,
            "status": payload.status,
            "timestamp": payload.timestamp,
            "language": payload.language,
            "total_attempts": len(retry_attempts),
            "attempts": [
                {
                    "attempt": attempt.attempt_number,
                    "error": attempt.error,
                    "timestamp": attempt.timestamp,
                }
                for attempt in retry_attempts
            ],
        }

        self._logger.log(
            level=LogLevel.ERROR,
            component="NotificationRouter",
            message=f"All notification retries failed for channel '{channel_name}'",
            data=error_data,
        )


# Type hint for circular import avoidance
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .audit_logger import AuditLogger
