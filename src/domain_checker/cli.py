"""
Command-line interface for the domain checker system.

This module provides the main CLI entry point with commands for:
- check: Check a single domain for availability
- check-list: Check multiple domains from a file
- config: Configuration management

Implements Requirements:
- 12.2: Simulation mode (--dry-run flag)
- 12.3: Historical data analysis support
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .audit_logger import AuditLogger
from .config import (
    DiscordConfig,
    EmailConfig,
    LoggingConfig,
    NotificationConfig,
    PersistenceConfig,
    RateLimitConfig,
    RateLimitRule,
    RetryConfig,
    SystemConfig,
    TelegramConfig,
    TLDConfig,
    WebhookConfig,
)
from .enums import AvailabilityStatus, LogLevel
from .i18n import get_message
from .notifications import (
    DiscordChannel,
    EmailChannel,
    NotificationRouter,
    TelegramChannel,
    WebhookChannel,
)
from .orchestrator import CheckOrchestrator
from .self_test import SelfTest, run_self_test
from .state_store import StateStore


# Default TLD configurations
DEFAULT_TLDS = [
    TLDConfig(
        tld="de",
        rdap_endpoint="https://rdap.denic.de/domain/",
        whois_server="whois.denic.de",
        whois_enabled=True,
    ),
    TLDConfig(
        tld="com",
        rdap_endpoint="https://rdap.verisign.com/com/v1/domain/",
        whois_server="whois.verisign-grs.com",
        whois_enabled=True,
    ),
    TLDConfig(
        tld="net",
        rdap_endpoint="https://rdap.verisign.com/net/v1/domain/",
        whois_server="whois.verisign-grs.com",
        whois_enabled=True,
    ),
    TLDConfig(
        tld="org",
        rdap_endpoint="https://rdap.publicinterestregistry.org/rdap/domain/",
        whois_server="whois.pir.org",
        whois_enabled=True,
    ),
    TLDConfig(
        tld="eu",
        rdap_endpoint="https://rdap.eurid.eu/domain/",
        whois_server="whois.eu",
        whois_enabled=True,
    ),
]


def create_notification_router(
    config: SystemConfig,
    logger: Optional[AuditLogger] = None,
) -> Optional[NotificationRouter]:
    """
    Create a notification router from configuration.

    Args:
        config: System configuration with notification settings
        logger: Optional audit logger for error logging

    Returns:
        NotificationRouter if any channels are configured, None otherwise
    """
    notifications = config.notifications
    if not notifications:
        return None

    # Check if any channel is configured
    has_channels = any([
        notifications.telegram,
        notifications.discord,
        notifications.email,
        notifications.webhook,
    ])

    if not has_channels:
        return None

    router = NotificationRouter(
        retry_config=config.retry,
        logger=logger,
    )

    # Register Telegram channel
    if notifications.telegram:
        channel = TelegramChannel(
            config=notifications.telegram,
            simulation_mode=config.simulation_mode,
        )
        router.register_channel(channel)

    # Register Discord channel
    if notifications.discord:
        channel = DiscordChannel(
            config=notifications.discord,
            simulation_mode=config.simulation_mode,
        )
        router.register_channel(channel)

    # Register Email channel
    if notifications.email:
        channel = EmailChannel(
            config=notifications.email,
            simulation_mode=config.simulation_mode,
        )
        router.register_channel(channel)

    # Register Webhook channel
    if notifications.webhook:
        channel = WebhookChannel(
            config=notifications.webhook,
            simulation_mode=config.simulation_mode,
        )
        router.register_channel(channel)

    return router


def create_default_config(
    simulation_mode: bool = False,
    language: str = "de",
    state_file: Optional[Path] = None,
    hmac_secret: str = "default-secret-change-me",
) -> SystemConfig:
    """
    Create a default system configuration.

    Args:
        simulation_mode: Enable simulation mode (no real network requests)
        language: Output language ('de' or 'en')
        state_file: Path to state file for persistence
        hmac_secret: Secret for HMAC protection

    Returns:
        SystemConfig with default settings
    """
    if state_file is None:
        state_file = Path.home() / ".domain_checker" / "state.json"

    return SystemConfig(
        tlds=DEFAULT_TLDS,
        rate_limits=RateLimitConfig(
            global_limit=RateLimitRule(
                max_requests=10,
                window_seconds=60.0,
                min_delay_seconds=1.0,
            ),
        ),
        retry=RetryConfig(
            max_retries=3,
            base_delay_seconds=1.0,
            max_delay_seconds=60.0,
        ),
        notifications=NotificationConfig(),
        persistence=PersistenceConfig(
            state_file_path=state_file,
            hmac_secret=hmac_secret,
        ),
        logging=LoggingConfig(
            level="info",
            output_format="text",
        ),
        language=language,
        simulation_mode=simulation_mode,
        startup_self_test=False,
    )


def load_config_from_file(config_path: Path) -> Optional[SystemConfig]:
    """
    Load configuration from a JSON file.

    Args:
        config_path: Path to the configuration file

    Returns:
        SystemConfig if successful, None otherwise
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Parse TLD configs
        tlds = []
        for tld_data in data.get("tlds", []):
            tlds.append(TLDConfig(
                tld=tld_data["tld"],
                rdap_endpoint=tld_data["rdap_endpoint"],
                secondary_rdap_endpoint=tld_data.get("secondary_rdap_endpoint"),
                whois_server=tld_data.get("whois_server"),
                whois_enabled=tld_data.get("whois_enabled", False),
            ))

        if not tlds:
            tlds = DEFAULT_TLDS

        # Parse rate limits
        rate_limits_data = data.get("rate_limits", {})
        global_limit_data = rate_limits_data.get("global_limit")
        global_limit = None
        if global_limit_data:
            global_limit = RateLimitRule(
                max_requests=global_limit_data.get("max_requests", 10),
                window_seconds=global_limit_data.get("window_seconds", 60.0),
                min_delay_seconds=global_limit_data.get("min_delay_seconds", 1.0),
            )

        rate_limits = RateLimitConfig(global_limit=global_limit)

        # Parse retry config
        retry_data = data.get("retry", {})
        retry = RetryConfig(
            max_retries=retry_data.get("max_retries", 3),
            base_delay_seconds=retry_data.get("base_delay_seconds", 1.0),
            max_delay_seconds=retry_data.get("max_delay_seconds", 60.0),
        )

        # Parse persistence config
        persistence_data = data.get("persistence", {})
        state_file_path = persistence_data.get("state_file_path")
        if state_file_path:
            state_file_path = Path(state_file_path)
        else:
            state_file_path = Path.home() / ".domain_checker" / "state.json"

        persistence = PersistenceConfig(
            state_file_path=state_file_path,
            hmac_secret=persistence_data.get("hmac_secret", "default-secret-change-me"),
        )

        # Parse logging config
        logging_data = data.get("logging", {})
        logging_config = LoggingConfig(
            level=logging_data.get("level", "info"),
            audit_mode=logging_data.get("audit_mode", False),
            audit_signing_key=logging_data.get("audit_signing_key"),
            output_format=logging_data.get("output_format", "text"),
        )

        # Parse notification config
        notifications_data = data.get("notifications", {})
        notifications = NotificationConfig()

        # Telegram
        telegram_data = notifications_data.get("telegram", {})
        if telegram_data.get("enabled") and telegram_data.get("bot_token") and telegram_data.get("chat_id"):
            notifications.telegram = TelegramConfig(
                bot_token=telegram_data["bot_token"],
                chat_id=telegram_data["chat_id"],
            )

        # Discord
        discord_data = notifications_data.get("discord", {})
        if discord_data.get("enabled") and discord_data.get("webhook_url"):
            notifications.discord = DiscordConfig(
                webhook_url=discord_data["webhook_url"],
            )

        # Email
        email_data = notifications_data.get("email", {})
        if email_data.get("enabled") and email_data.get("smtp_host"):
            notifications.email = EmailConfig(
                smtp_host=email_data["smtp_host"],
                smtp_port=email_data.get("smtp_port", 587),
                username=email_data.get("username", ""),
                password=email_data.get("password", ""),
                from_address=email_data.get("from_address", ""),
                to_addresses=email_data.get("to_addresses", []),
            )

        # Webhook
        webhook_data = notifications_data.get("webhook", {})
        if webhook_data.get("enabled") and webhook_data.get("url"):
            notifications.webhook = WebhookConfig(
                url=webhook_data["url"],
                headers=webhook_data.get("headers", {}),
            )

        return SystemConfig(
            tlds=tlds,
            rate_limits=rate_limits,
            retry=retry,
            notifications=notifications,
            persistence=persistence,
            logging=logging_config,
            language=data.get("language", "de"),
            simulation_mode=data.get("simulation_mode", False),
            startup_self_test=data.get("startup_self_test", False),
        )

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return None
    except FileNotFoundError:
        return None


def save_config_to_file(config: SystemConfig, config_path: Path) -> bool:
    """
    Save configuration to a JSON file.

    Args:
        config: SystemConfig to save
        config_path: Path to save the configuration

    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure parent directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "tlds": [
                {
                    "tld": tld.tld,
                    "rdap_endpoint": tld.rdap_endpoint,
                    "secondary_rdap_endpoint": tld.secondary_rdap_endpoint,
                    "whois_server": tld.whois_server,
                    "whois_enabled": tld.whois_enabled,
                }
                for tld in config.tlds
            ],
            "rate_limits": {
                "global_limit": {
                    "max_requests": config.rate_limits.global_limit.max_requests,
                    "window_seconds": config.rate_limits.global_limit.window_seconds,
                    "min_delay_seconds": config.rate_limits.global_limit.min_delay_seconds,
                } if config.rate_limits.global_limit else None,
            },
            "retry": {
                "max_retries": config.retry.max_retries,
                "base_delay_seconds": config.retry.base_delay_seconds,
                "max_delay_seconds": config.retry.max_delay_seconds,
            },
            "persistence": {
                "state_file_path": str(config.persistence.state_file_path),
                "hmac_secret": config.persistence.hmac_secret,
            },
            "logging": {
                "level": config.logging.level,
                "audit_mode": config.logging.audit_mode,
                "audit_signing_key": config.logging.audit_signing_key,
                "output_format": config.logging.output_format,
            },
            "language": config.language,
            "simulation_mode": config.simulation_mode,
            "startup_self_test": config.startup_self_test,
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return True

    except (OSError, TypeError) as e:
        print(f"Error saving config: {e}", file=sys.stderr)
        return False


async def check_single_domain(
    domain: str,
    config: SystemConfig,
    verbose: bool = False,
) -> int:
    """
    Check a single domain for availability.

    Args:
        domain: Domain to check
        config: System configuration
        verbose: Enable verbose output

    Returns:
        Exit code (0 for available, 1 for taken/error)
    """
    language = config.language

    # Run startup self-test if enabled
    if config.startup_self_test:
        self_test_result = await run_self_test(
            config=config,
            print_output=verbose,
            language=language,
        )
        if not self_test_result.success:
            print(get_message("selftest.failed", language), file=sys.stderr)
            return 1

    # Print simulation mode notice
    if config.simulation_mode:
        print(get_message("simulation.enabled", language))

    # Print checking message
    print(get_message("cli.checking_domain", language, domain=domain))

    # Create logger if verbose
    logger = None
    if verbose:
        logger = AuditLogger(output_format="text")

    # Create state store
    state_store = None
    try:
        config.persistence.state_file_path.parent.mkdir(parents=True, exist_ok=True)
        state_store = StateStore(
            file_path=config.persistence.state_file_path,
            hmac_secret=config.persistence.hmac_secret,
        )
        state_store.load()
    except Exception as e:
        if verbose:
            print(f"Warning: Could not load state store: {e}", file=sys.stderr)

    # Create notification router
    notification_router = create_notification_router(config, logger)
    if notification_router and verbose:
        channels = [ch.get_name() for ch in notification_router.channels]
        print(f"Notification channels: {', '.join(channels)}")

    # Create orchestrator and check domain
    async with CheckOrchestrator(
        config=config,
        state_store=state_store,
        notification_router=notification_router,
        logger=logger,
    ) as orchestrator:
        result = await orchestrator.check_domain(domain)

    # Save state
    if state_store:
        try:
            state_store.save()
        except Exception as e:
            if verbose:
                print(f"Warning: Could not save state: {e}", file=sys.stderr)

    # Print result
    status_key = f"status.{result.check_result.status.value}"
    status_text = get_message(status_key, language)
    print(get_message("cli.result", language, status=status_text))

    if verbose:
        print(f"  Confidence: {result.check_result.confidence.value}")
        print(f"  Duration: {result.check_result.metadata.total_duration_ms:.1f}ms")
        print(f"  Retries: {result.check_result.metadata.retry_count}")
        if result.notification_sent:
            print("  📨 Notification sent!")
        if result.errors:
            print("  Errors:")
            for error in result.errors:
                print(f"    - {error}")

    # Return exit code based on availability
    if result.check_result.status == AvailabilityStatus.AVAILABLE:
        return 0
    return 1


async def check_domain_list(
    domains_file: Path,
    config: SystemConfig,
    output_file: Optional[Path] = None,
    verbose: bool = False,
) -> int:
    """
    Check multiple domains from a file.

    Args:
        domains_file: Path to file containing domains (one per line)
        config: System configuration
        output_file: Optional path to write results as JSON
        verbose: Enable verbose output

    Returns:
        Exit code (0 if any available, 1 if all taken/error)
    """
    language = config.language

    # Read domains from file
    try:
        with open(domains_file, "r", encoding="utf-8") as f:
            domains = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except FileNotFoundError:
        print(f"Error: File not found: {domains_file}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1

    if not domains:
        print("Error: No domains found in file", file=sys.stderr)
        return 1

    # Run startup self-test if enabled
    if config.startup_self_test:
        self_test_result = await run_self_test(
            config=config,
            print_output=verbose,
            language=language,
        )
        if not self_test_result.success:
            print(get_message("selftest.failed", language), file=sys.stderr)
            return 1

    # Print simulation mode notice
    if config.simulation_mode:
        print(get_message("simulation.enabled", language))

    print(f"Checking {len(domains)} domain(s)...")

    # Create logger if verbose
    logger = None
    if verbose:
        logger = AuditLogger(output_format="text")

    # Create state store
    state_store = None
    try:
        config.persistence.state_file_path.parent.mkdir(parents=True, exist_ok=True)
        state_store = StateStore(
            file_path=config.persistence.state_file_path,
            hmac_secret=config.persistence.hmac_secret,
        )
        state_store.load()
    except Exception as e:
        if verbose:
            print(f"Warning: Could not load state store: {e}", file=sys.stderr)

    # Create notification router
    notification_router = create_notification_router(config, logger)
    if notification_router:
        channels = [ch.get_name() for ch in notification_router.channels]
        print(f"📨 Notification channels active: {', '.join(channels)}")

    results = []
    available_count = 0
    notifications_sent = 0

    # Create orchestrator and check domains
    async with CheckOrchestrator(
        config=config,
        state_store=state_store,
        notification_router=notification_router,
        logger=logger,
    ) as orchestrator:
        for domain in domains:
            print(get_message("cli.checking_domain", language, domain=domain))
            result = await orchestrator.check_domain(domain)

            status_key = f"status.{result.check_result.status.value}"
            status_text = get_message(status_key, language)
            notification_info = " 📨" if result.notification_sent else ""
            print(f"  {get_message('cli.result', language, status=status_text)}{notification_info}")

            if result.check_result.status == AvailabilityStatus.AVAILABLE:
                available_count += 1
            if result.notification_sent:
                notifications_sent += 1

            results.append({
                "domain": result.check_result.domain,
                "status": result.check_result.status.value,
                "confidence": result.check_result.confidence.value,
                "timestamp": result.check_result.timestamp,
                "duration_ms": result.check_result.metadata.total_duration_ms,
                "notification_sent": result.notification_sent,
                "errors": result.errors,
            })

    # Save state
    if state_store:
        try:
            state_store.save()
        except Exception as e:
            if verbose:
                print(f"Warning: Could not save state: {e}", file=sys.stderr)

    # Print summary
    print(f"\nSummary: {available_count}/{len(domains)} domain(s) available")
    if notifications_sent > 0:
        print(f"📨 Notifications sent: {notifications_sent}")

    # Write results to file if requested
    if output_file:
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"Results written to: {output_file}")
        except OSError as e:
            print(f"Error writing results: {e}", file=sys.stderr)

    return 0 if available_count > 0 else 1


def cmd_check(args: argparse.Namespace) -> int:
    """Handle the 'check' command."""
    # Load or create config
    config = None
    if args.config:
        config = load_config_from_file(Path(args.config))
        if config is None:
            print(f"Error: Could not load config from {args.config}", file=sys.stderr)
            return 1

    if config is None:
        config = create_default_config(
            simulation_mode=args.dry_run,
            language=args.language,
        )
    else:
        # Override with command line args
        if args.dry_run:
            config = SystemConfig(
                tlds=config.tlds,
                rate_limits=config.rate_limits,
                retry=config.retry,
                notifications=config.notifications,
                persistence=config.persistence,
                logging=config.logging,
                language=args.language or config.language,
                simulation_mode=True,
                startup_self_test=config.startup_self_test,
            )

    return asyncio.run(check_single_domain(
        domain=args.domain,
        config=config,
        verbose=args.verbose,
    ))


def cmd_check_list(args: argparse.Namespace) -> int:
    """Handle the 'check-list' command."""
    # Load or create config
    config = None
    if args.config:
        config = load_config_from_file(Path(args.config))
        if config is None:
            print(f"Error: Could not load config from {args.config}", file=sys.stderr)
            return 1

    if config is None:
        config = create_default_config(
            simulation_mode=args.dry_run,
            language=args.language,
        )
    else:
        # Override with command line args
        if args.dry_run:
            config = SystemConfig(
                tlds=config.tlds,
                rate_limits=config.rate_limits,
                retry=config.retry,
                notifications=config.notifications,
                persistence=config.persistence,
                logging=config.logging,
                language=args.language or config.language,
                simulation_mode=True,
                startup_self_test=config.startup_self_test,
            )

    output_file = Path(args.output) if args.output else None

    return asyncio.run(check_domain_list(
        domains_file=Path(args.file),
        config=config,
        output_file=output_file,
        verbose=args.verbose,
    ))


def cmd_self_test(args: argparse.Namespace) -> int:
    """Handle the 'self-test' command."""
    # Load or create config
    config = None
    if args.config:
        config = load_config_from_file(Path(args.config))
        if config is None:
            print(f"Error: Could not load config from {args.config}", file=sys.stderr)
            return 1

    if config is None:
        config = create_default_config(language=args.language)

    # Run self-test
    result = asyncio.run(run_self_test(
        config=config,
        print_output=True,
        language=args.language,
    ))

    return 0 if result.success else 1


def cmd_config(args: argparse.Namespace) -> int:
    """Handle the 'config' command."""
    config_path = Path(args.path) if args.path else Path.home() / ".domain_checker" / "config.json"

    if args.action == "show":
        config = load_config_from_file(config_path)
        if config is None:
            print(f"No configuration found at: {config_path}")
            print("Use 'config init' to create a default configuration.")
            return 1

        print(f"Configuration from: {config_path}")
        print(f"  Language: {config.language}")
        print(f"  Simulation mode: {config.simulation_mode}")
        print(f"  TLDs: {', '.join(tld.tld for tld in config.tlds)}")
        print(f"  State file: {config.persistence.state_file_path}")
        print(f"  Log level: {config.logging.level}")
        print(f"  Audit mode: {config.logging.audit_mode}")
        return 0

    elif args.action == "init":
        if config_path.exists() and not args.force:
            print(f"Configuration already exists at: {config_path}")
            print("Use --force to overwrite.")
            return 1

        config = create_default_config(language=args.language)
        if save_config_to_file(config, config_path):
            print(f"Configuration created at: {config_path}")
            return 0
        return 1

    elif args.action == "validate":
        config = load_config_from_file(config_path)
        if config is None:
            print(f"Error: Could not load config from {config_path}", file=sys.stderr)
            return 1

        print(f"Configuration at {config_path} is valid.")
        return 0

    return 1


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="domain-checker",
        description="High-security multi-TLD domain availability checker",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'check' command
    check_parser = subparsers.add_parser(
        "check",
        help="Check a single domain for availability",
    )
    check_parser.add_argument(
        "domain",
        help="Domain to check (e.g., example.com)",
    )
    check_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulation mode - no real network requests",
    )
    check_parser.add_argument(
        "--config", "-c",
        help="Path to configuration file",
    )
    check_parser.add_argument(
        "--language", "-l",
        choices=["de", "en"],
        default="de",
        help="Output language (default: de)",
    )
    check_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    check_parser.set_defaults(func=cmd_check)

    # 'check-list' command
    check_list_parser = subparsers.add_parser(
        "check-list",
        help="Check multiple domains from a file",
    )
    check_list_parser.add_argument(
        "file",
        help="Path to file containing domains (one per line)",
    )
    check_list_parser.add_argument(
        "--output", "-o",
        help="Path to write results as JSON",
    )
    check_list_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulation mode - no real network requests",
    )
    check_list_parser.add_argument(
        "--config", "-c",
        help="Path to configuration file",
    )
    check_list_parser.add_argument(
        "--language", "-l",
        choices=["de", "en"],
        default="de",
        help="Output language (default: de)",
    )
    check_list_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    check_list_parser.set_defaults(func=cmd_check_list)

    # 'config' command
    config_parser = subparsers.add_parser(
        "config",
        help="Configuration management",
    )
    config_parser.add_argument(
        "action",
        choices=["show", "init", "validate"],
        help="Configuration action",
    )
    config_parser.add_argument(
        "--path", "-p",
        help="Path to configuration file",
    )
    config_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force overwrite existing configuration",
    )
    config_parser.add_argument(
        "--language", "-l",
        choices=["de", "en"],
        default="de",
        help="Default language for new configuration",
    )
    config_parser.set_defaults(func=cmd_config)

    # 'self-test' command
    self_test_parser = subparsers.add_parser(
        "self-test",
        help="Run startup self-test to verify connectivity",
    )
    self_test_parser.add_argument(
        "--config", "-c",
        help="Path to configuration file",
    )
    self_test_parser.add_argument(
        "--language", "-l",
        choices=["de", "en"],
        default="de",
        help="Output language (default: de)",
    )
    self_test_parser.set_defaults(func=cmd_self_test)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """
    Main entry point for the CLI.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
