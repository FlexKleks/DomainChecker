# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-12-10

### Added
- Initial release
- Multi-TLD domain availability checking (`.de`, `.com`, `.net`, `.org`, `.eu`, `.at`)
- RDAP protocol support with official registry endpoints
- WHOIS fallback for secondary confirmation
- Notification channels: Telegram, Discord, Email, Webhooks
- Rate limiting with configurable delays
- Retry logic with exponential backoff
- State persistence to prevent duplicate notifications
- CLI with `check`, `check-list`, `config`, and `self-test` commands
- Multilingual support (German/English)
- Simulation mode for testing
- JSON configuration file support
