# Domain Checker

A tiny Python utility to watch domain availability and notify you on Telegram when a domain becomes available.
It uses RDAP (official registry protocol) for `.de`, `.net`, `.eu` and falls back to `python-whois` if needed.

- Works on Python 3.12+
- i18n: LANG=de or LANG=en
- Optional startup test ping to Telegram
- Debug logs with DEBUG=1
- Designed for cron/systemd (runs once per invocation; no rate-limit issues)

---

## Features

- RDAP-first for accuracy:
  - `.de` → rdap.org, then rdap.denic.de
  - `.net` → rdap.org, then Verisign
  - `.eu` → rdap.org, then EURid
- whois fallback if RDAP is unreachable
- Idempotent alerts: a domain triggers one alert the first time it’s seen as available
- Config via `.env` (no secrets in code)

---

## Quick Start

```bash
git clone https://github.com/FlexKleks/DomainChecker.git
cd domain-checker
python -m venv .venv && source .venv/bin/activate   # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
cp .env.example .env                                # rename .env.example to .env
python domain_checker.py
```

**Note:**  
The `.env.example` file is just a template.  
Copy it to `.env` **and rename it** before running the script:
```bash
cp .env.example .env
```
Edit `.env` with your settings.

You should see logs in the console. If a domain becomes available, you’ll get a Telegram message.

---

## Configuration (.env)

Example `.env` file:

```ini
LANG=en                    # Language: de or en
DEBUG=0                    # Debug logs (0/1)
TELEGRAM_TEST_ON_START=0   # Optional: send a Telegram test message on startup (0/1)
DOMAINS=example.net, my-project.de; cool-name.eu
TELEGRAM_BOT_TOKEN=123456:ABCDEF_your_token
TELEGRAM_CHAT_ID=YOUR_FUNNY_CHAT_ID
```

---

### How to create a Telegram bot

1. Open Telegram and talk to @BotFather.
2. Send `/newbot`, follow the prompts, and copy your bot token.
3. Important: A bot cannot message you first. You must start the conversation:
   - Search your bot by its name, click Start, or send `/start`.

---

### How to find your Chat ID

**Method A: getUpdates**

After you've sent `/start` to your bot:
```bash
curl -s "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates"
```

Look for:
```json
"chat": { "id": 123456789, "type": "private", ... }
```
`123456789` is your TELEGRAM_CHAT_ID.

**Method B: helper bots**
- Talk to @userinfobot or @RawDataBot — they’ll show your user ID (works as chat ID for direct bot messages).

---

## Running on a schedule

This script is single-run by design. Use cron/systemd to schedule it to avoid rate limits.

### Cron (Linux)

**Once per day at 08:00**
```cron
0 8 * * * /usr/bin/python3 /opt/domain-checker/domain_checker.py >> /opt/domain-checker/check.log 2>&1
```

**Four times per day (00:00, 06:00, 12:00, 18:00)**
```cron
0 0,6,12,18 * * * /usr/bin/python3 /opt/domain-checker/domain_checker.py >> /opt/domain-checker/check.log 2>&1
```

Set environment via `.env` (loaded automatically) or your service/unit.

---

### systemd (recommended)

Create `/etc/systemd/system/domain-checker.service`:
```ini
[Unit]
Description=Domain Checker (one-shot)

[Service]
Type=oneshot
WorkingDirectory=/opt/domain-checker
ExecStart=/usr/bin/python3 /opt/domain-checker/domain_checker.py
# If you don't use .env, uncomment and set Env vars here:
# Environment=LANG=en
# Environment=DOMAINS=example.net,my-domain.de
# Environment=TELEGRAM_BOT_TOKEN=123456:ABCDEF
# Environment=TELEGRAM_CHAT_ID=123456789
```

Create `/etc/systemd/system/domain-checker.timer`:
```ini
[Unit]
Description=Run Domain Checker periodically

[Timer]
OnCalendar=*-*-* 00,06,12,18:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable & start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now domain-checker.timer
sudo systemctl status domain-checker.timer
```

---

## Troubleshooting

- **No Telegram message?**
  - Make sure you sent `/start` to your bot at least once.
  - Check `.env`: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
  - Run with DEBUG=1 and/or TELEGRAM_TEST_ON_START=1 to verify Telegram connectivity.
- **RDAP lines show `unknown (HTTP 429)` or exceptions**
  - That’s a rate limit or network hiccup. The script retried; schedule runs less frequently.
- **A domain is “available” but no alert arrives**
  - Alerts fire once per domain. Delete `.notified.json` to reset, or wait until it flips back to taken then free again.
- **Windows**
  - Use `python -m venv .venv && .venv\Scripts\activate` and `pip install -r requirements.txt`.
- **Security**
  - Rotate your bot token if it ever leaks. Never commit real tokens.

---

## How it works (technical)

- **RDAP**: queries rdap.org first for fast, unified responses; then official registries:
  - `.de` → rdap.denic.de
  - `.net` → Verisign RDAP
  - `.eu` → EURid RDAP
- **Availability logic**
  - HTTP 404 (or 200 with `errorCode=404`) → free
  - 200 with `objectClassName="domain"` → taken
  - Anything else → unknown → try next endpoint → finally fallback to python-whois.

---

## License

MIT – do whatever, just be nice. :)
