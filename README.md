# 🛡️ Domain Availability Checker

[![Tests](https://github.com/FlexKleks/DomainChecker/actions/workflows/test.yml/badge.svg)](https://github.com/FlexKleks/DomainChecker/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/FlexKleks/DomainChecker?style=social)](https://github.com/FlexKleks/DomainChecker/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/FlexKleks/DomainChecker?style=social)](https://github.com/FlexKleks/DomainChecker/network/members)

> 🔔 **Get notified instantly when your dream domain becomes available!**

A powerful Python CLI tool that monitors domain availability across multiple TLDs and sends real-time alerts via **Telegram**, **Discord**, **Email**, or **Webhooks**.

<p align="center">
  <img src="https://img.shields.io/badge/Telegram-Notifications-blue?logo=telegram" alt="Telegram">
  <img src="https://img.shields.io/badge/Discord-Webhooks-5865F2?logo=discord&logoColor=white" alt="Discord">
  <img src="https://img.shields.io/badge/Email-SMTP-red?logo=gmail" alt="Email">
  <img src="https://img.shields.io/badge/Webhooks-Custom-green" alt="Webhooks">
</p>

---

## 🎯 Why Use This?

- **Never miss a domain drop** - Get instant notifications when domains become available
- **No false positives** - Two-source verification (RDAP + WHOIS) ensures accuracy
- **Multiple alert channels** - Telegram, Discord, Email, or custom webhooks
- **Set it and forget it** - Run on a schedule and get notified automatically
- **Privacy-focused** - Self-hosted, your data stays with you

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🌐 **Multi-TLD** | `.de`, `.com`, `.net`, `.org`, `.eu`, `.at` |
| 🔍 **RDAP + WHOIS** | Official registry queries with fallback |
| 📱 **Telegram** | Instant mobile notifications |
| 💬 **Discord** | Webhook integration for servers |
| 📧 **Email** | SMTP support for email alerts |
| 🔗 **Webhooks** | Custom HTTP endpoints |
| 🚫 **No Spam** | Smart deduplication - alert only once per domain |
| ⏱️ **Rate Limiting** | Respects registry limits automatically |
| 🔄 **Retry Logic** | Handles transient errors gracefully |
| 🌍 **Multilingual** | German 🇩🇪 & English 🇬🇧 |

---

## 📦 Quick Install

```bash
git clone https://github.com/FlexKleks/DomainChecker.git
cd DomainChecker
pip install -e .
```

---

## 🚀 Quick Start

### 1️⃣ Configure

```bash
cp config.example.json config.json
# Edit config.json - add your Telegram token, domains, etc.
```

### 2️⃣ Add Domains

```bash
cp domains.example.txt domains.txt
# Add domains to monitor (one per line)
```

### 3️⃣ Run

```bash
python -m domain_checker.cli check-list domains.txt --config config.json
```

### 📱 Example Telegram Notification

```
🟢 Domain available!

Domain: mydream-domain.com
Status: Available
Time: Dec 10, 2025, 5:30 AM
```

---

## ⚙️ Configuration

```json
{
  "language": "en",
  "notifications": {
    "telegram": {
      "enabled": true,
      "bot_token": "YOUR_BOT_TOKEN",
      "chat_id": "YOUR_CHAT_ID"
    }
  }
}
```

<details>
<summary>📲 <b>Telegram Setup Guide</b></summary>

1. Message [@BotFather](https://t.me/BotFather) → `/newbot`
2. Save the bot token
3. Start a chat with your bot, send any message
4. Get chat ID: `https://api.telegram.org/bot<TOKEN>/getUpdates`
5. Add both to your `config.json`

</details>

<details>
<summary>💬 <b>Discord Setup Guide</b></summary>

1. Server Settings → Integrations → Webhooks
2. Create Webhook → Copy URL
3. Add to config:
```json
"discord": {
  "enabled": true,
  "webhook_url": "https://discord.com/api/webhooks/..."
}
```

</details>

---

## 🛠️ CLI Commands

```bash
# Check single domain
python -m domain_checker.cli check example.com --config config.json

# Check multiple domains
python -m domain_checker.cli check-list domains.txt --config config.json

# Test mode (no real requests)
python -m domain_checker.cli check example.com --dry-run

# Verify connectivity
python -m domain_checker.cli self-test --config config.json
```

---

## 🔄 Automated Monitoring

### Windows Task Scheduler
```powershell
# Create scheduled task to run every 6 hours
python -m domain_checker.cli check-list domains.txt --config config.json
```

### Linux Cron
```bash
# Every 6 hours
0 */6 * * * cd /path/to/DomainChecker && python -m domain_checker.cli check-list domains.txt --config config.json
```

### Systemd Service (Linux)

<details>
<summary><b>Click to expand systemd setup</b></summary>

1. Create service file `/etc/systemd/system/domain-checker.service`:
```ini
[Unit]
Description=Domain Availability Checker
After=network.target

[Service]
Type=oneshot
User=your-user
WorkingDirectory=/path/to/DomainChecker
ExecStart=/usr/bin/python3 -m domain_checker.cli check-list domains.txt --config config.json
```

2. Create timer file `/etc/systemd/system/domain-checker.timer`:
```ini
[Unit]
Description=Run Domain Checker every 6 hours

[Timer]
OnBootSec=5min
OnUnitActiveSec=6h
Persistent=true

[Install]
WantedBy=timers.target
```

3. Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable domain-checker.timer
sudo systemctl start domain-checker.timer
```

</details>

### Pelican Panel / Pterodactyl

<details>
<summary><b>Click to expand Pelican Panel setup</b></summary>

#### Option 1: Using Startup Command

1. Create a new server with a **Python** egg
2. Set the startup command:
```bash
cd /home/container && pip install -e . && python -m domain_checker.cli check-list domains.txt --config config.json
```

#### Option 2: Using a Startup Script

1. Create `start.sh` in your server files:
```bash
#!/bin/bash
cd /home/container

# Install dependencies (first run only)
if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -e .
else
    source venv/bin/activate
fi

# Run the checker in a loop
while true; do
    echo "[$(date)] Starting domain check..."
    python -m domain_checker.cli check-list domains.txt --config config.json
    echo "[$(date)] Check complete. Sleeping for 6 hours..."
    sleep 21600  # 6 hours in seconds
done
```

2. Set startup command to: `bash start.sh`

#### Option 3: Using Schedule Feature

If your panel supports schedules:
1. Go to **Schedules** in your server panel
2. Create a new schedule (e.g., every 6 hours)
3. Add a task with command:
```bash
python -m domain_checker.cli check-list domains.txt --config config.json
```

#### File Structure for Pelican
```
/home/container/
├── config.json          # Your configuration
├── domains.txt          # Domains to monitor
├── start.sh             # Startup script (optional)
├── src/
│   └── domain_checker/  # Application code
└── .domain_checker/     # State files (auto-created)
```

</details>

### Docker (Coming Soon)
```bash
docker run -v ./config.json:/app/config.json flexkleks/domain-checker
```

---

## 🌐 Supported TLDs (193)

> 📋 See [SUPPORTED_TLDS.md](SUPPORTED_TLDS.md) for the complete list with RDAP/WHOIS endpoints.

<details>
<summary><b>Click to expand full list</b></summary>

| Category | TLDs |
|----------|------|
| **Generic** | `.com`, `.net`, `.org`, `.info`, `.biz`, `.name`, `.mobi`, `.pro` |
| **Tech** | `.io`, `.co`, `.app`, `.dev`, `.ai`, `.tech`, `.cloud`, `.digital`, `.software`, `.systems`, `.network`, `.solutions`, `.agency`, `.studio`, `.design`, `.media` |
| **Popular New** | `.xyz`, `.online`, `.site`, `.store`, `.shop`, `.club`, `.live`, `.life`, `.world`, `.today`, `.space`, `.fun`, `.top`, `.vip`, `.one`, `.blog`, `.news`, `.email`, `.link`, `.click` |
| **Europe** | `.de`, `.eu`, `.at`, `.ch`, `.li`, `.nl`, `.be`, `.fr`, `.it`, `.es`, `.pt`, `.pl`, `.cz`, `.sk`, `.hu`, `.ro`, `.bg`, `.hr`, `.si`, `.rs`, `.gr`, `.tr` |
| **Nordic** | `.se`, `.dk`, `.no`, `.fi`, `.is` |
| **UK & Ireland** | `.uk`, `.co.uk`, `.org.uk`, `.me.uk`, `.ie` |
| **Americas** | `.us`, `.ca`, `.mx`, `.br`, `.ar`, `.cl`, `.co`, `.pe` |
| **Asia Pacific** | `.au`, `.com.au`, `.nz`, `.jp`, `.cn`, `.hk`, `.tw`, `.kr`, `.in`, `.sg`, `.my`, `.th`, `.id`, `.ph`, `.vn` |
| **Middle East & Africa** | `.ae`, `.sa`, `.il`, `.za`, `.ng`, `.ke`, `.eg`, `.ma` |
| **CIS** | `.ru`, `.ua`, `.by`, `.kz`, `.uz` |
| **Special** | `.me`, `.tv`, `.cc`, `.ws`, `.fm`, `.gg`, `.to`, `.la`, `.ly`, `.vc`, `.gl`, `.im`, `.sh`, `.ac` |
| **Business** | `.company`, `.business`, `.consulting`, `.services`, `.group`, `.team`, `.work`, `.jobs`, `.careers`, `.finance`, `.money`, `.capital`, `.ventures`, `.holdings`, `.partners`, `.legal`, `.law`, `.tax`, `.accountant`, `.insurance` |
| **Lifestyle** | `.art`, `.music`, `.video`, `.photo`, `.photography`, `.gallery`, `.fashion`, `.style`, `.fitness`, `.health`, `.yoga`, `.travel`, `.holiday`, `.restaurant`, `.cafe`, `.bar`, `.beer`, `.wine`, `.pizza`, `.game`, `.games`, `.casino`, `.bet` |
| **Real Estate** | `.house`, `.homes`, `.property`, `.properties`, `.land`, `.estate`, `.apartments`, `.rent` |
| **Education** | `.edu`, `.academy`, `.school`, `.university`, `.college`, `.training`, `.courses`, `.community`, `.social`, `.chat`, `.forum` |
| **Google** | `.page`, `.new`, `.how`, `.soy`, `.foo` |

</details>

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

- ⭐ **Star this repo** if you find it useful!
- 🐛 **Report bugs** via [Issues](https://github.com/FlexKleks/DomainChecker/issues)
- 💡 **Request features** via [Issues](https://github.com/FlexKleks/DomainChecker/issues)
- 🔀 **Submit PRs** for improvements

---

## 📄 License

[MIT License](LICENSE) - Free for personal and commercial use.

---

## ⭐ Star History

If this project helped you, please consider giving it a ⭐!

<a href="https://www.star-history.com/#FlexKleks/DomainChecker&type=date&legend=top-left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=FlexKleks/DomainChecker&type=date&theme=dark&legend=top-left" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=FlexKleks/DomainChecker&type=date&legend=top-left" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=FlexKleks/DomainChecker&type=date&legend=top-left" />
  </picture>
</a>

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/FlexKleks">FlexKleks</a>
</p>
