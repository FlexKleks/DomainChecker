# 🛡️ Domain Availability Checker

[![Tests](https://github.com/FlexKleks/DomainChecker/actions/workflows/test.yml/badge.svg)](https://github.com/FlexKleks/DomainChecker/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A high-security Python tool to monitor **domain name availability** for multiple TLDs with notifications via **Telegram**, **Discord**, **Email**, or **Webhooks**.

Uses **official RDAP endpoints** with **WHOIS fallback** and two-source consensus to minimize false positives.

---

## ✨ Features

- **Multi-TLD Support**: `.de`, `.com`, `.net`, `.org`, `.eu`, `.at`
- **Authoritative RDAP**: Queries official registry endpoints (DENIC, Verisign, etc.)
- **False-Positive Protection**: Two-source consensus required for availability confirmation
- **Multiple Notification Channels**: Telegram, Discord, Email, Webhooks
- **No Spam**: Each domain triggers an alert only once (state persistence)
- **Rate Limiting**: Configurable delays to avoid registry rate limits
- **Retry Logic**: Exponential backoff for transient errors
- **Multilingual**: German 🇩🇪 / English 🇬🇧 output and notifications
- **Simulation Mode**: Test without real network requests

---

## 📦 Installation

```bash
git clone https://github.com/FlexKleks/DomainChecker.git
cd DomainChecker
pip install -e .
```

---

## 🚀 Quick Start

### 1. Setup Configuration

```bash
cp config.example.json config.json
# Edit config.json with your settings (Telegram token, etc.)
```

### 2. Add Domains to Monitor

```bash
cp domains.example.txt domains.txt
# Edit domains.txt - one domain per line
```

### 3. Run the Checker

```bash
# Using Python module (recommended)
python -m domain_checker.cli check-list domains.txt --config config.json

# Or if installed in PATH
domain-checker check-list domains.txt --config config.json
```

### 4. Check a Single Domain

```bash
python -m domain_checker.cli check example.de --config config.json
```

---

## ⚙️ Configuration

Copy `config.example.json` to `config.json` and customize:

```json
{
  "language": "en",
  "simulation_mode": false,
  
  "notifications": {
    "telegram": {
      "enabled": true,
      "bot_token": "YOUR_BOT_TOKEN",
      "chat_id": "YOUR_CHAT_ID"
    }
  }
}
```

### Notification Channels

| Channel | Required Fields |
|---------|-----------------|
| Telegram | `bot_token`, `chat_id` |
| Discord | `webhook_url` |
| Email | `smtp_host`, `smtp_port`, `username`, `password`, `from_address`, `to_addresses` |
| Webhook | `url`, optional `headers` |

---

## 📲 Telegram Setup

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → Save the token
2. Start a chat with your bot, send any message
3. Get your chat ID: `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Add to config:
   ```json
   "telegram": {
     "enabled": true,
     "bot_token": "123456789:ABCdef...",
     "chat_id": "123456789"
   }
   ```

---

## 🔍 How It Works

1. Query **authoritative RDAP** for each TLD
2. If RDAP returns **404** → Domain potentially available
3. Confirm with **secondary source** (WHOIS)
4. Only if **both agree** → Report as **AVAILABLE**
5. Send notification (only on first detection)

### Notification Example

```
🟢 Domain available!

Domain: example.de
Status: Available
Time: Dec 10, 2025, 5:30 AM
```

---

## 🛠️ CLI Reference

| Command | Description |
|---------|-------------|
| `check <domain>` | Check single domain |
| `check-list <file>` | Check multiple domains |
| `config init` | Create default config |
| `config show` | Display config |
| `self-test` | Test connectivity |

### Options

| Option | Description |
|--------|-------------|
| `-c, --config` | Config file path |
| `-l, --language` | Output language (`de`/`en`) |
| `-v, --verbose` | Verbose output |
| `--dry-run` | Simulation mode |
| `-o, --output` | JSON output file |

---

## 🌐 Supported TLDs

| TLD | Registry | RDAP Endpoint |
|-----|----------|---------------|
| `.de` | DENIC | rdap.denic.de |
| `.com` | Verisign | rdap.verisign.com |
| `.net` | Verisign | rdap.verisign.com |
| `.org` | PIR | rdap.publicinterestregistry.org |
| `.eu` | EURid | rdap.org (fallback) |
| `.at` | nic.at | rdap.org (fallback) |

---

## 🔄 Scheduled Execution

### Windows Task Scheduler

Create a scheduled task to run periodically:

```powershell
# Run every 6 hours
python -m domain_checker.cli check-list domains.txt --config config.json
```

### Linux Cron

```bash
# Add to crontab (every 6 hours)
0 */6 * * * cd /path/to/DomainChecker && python -m domain_checker.cli check-list domains.txt --config config.json
```

---

## 🧪 Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with verbose output
pytest -v --tb=short
```

---

## 📁 Project Structure

```
DomainChecker/
├── src/domain_checker/
│   ├── cli.py              # CLI interface
│   ├── orchestrator.py     # Main coordination
│   ├── rdap_client.py      # RDAP client
│   ├── whois_client.py     # WHOIS client
│   ├── notifications.py    # Alert channels
│   ├── decision_engine.py  # Availability logic
│   ├── rate_limiter.py     # Request throttling
│   └── state_store.py      # Persistence
├── tests/
├── config.example.json
├── domains.example.txt
├── pyproject.toml
└── README.md
```

---

## 📄 License

[MIT License](LICENSE) - see LICENSE file for details.

---

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 💡 Tips

- Reset notifications: Delete `.domain_checker/` folder
- Test setup: Use `--dry-run` flag
- Many domains: Increase `min_delay_seconds` in config
- Verify connectivity: Run `self-test` command
