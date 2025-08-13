# 🛡️ Domain Availability Checker (with Telegram Alerts)

A hardened Python tool to monitor **domain name availability** for multiple TLDs and notify you via **Telegram**.
Uses **official RDAP** + a **WHOIS fallback** to reduce false positives and supports a configurable **delay between checks** to avoid rate-limiting.

---

## ✨ Features

- Supports **.de, .net, .eu, .com, .at, .org**
- **Authoritative RDAP first**, then fallback to **rdap.org + WHOIS** (two-source consensus) to avoid false positives
- **False-positive protection**: only reports “free” when authoritative RDAP says 404 or both fallback sources agree
- **Telegram bot notifications**
- **No spam**: each domain triggers an alert only **once** (tracked in `.notified.json`)
- **Configurable delay** between checks via `CHECK_DELAY_SECONDS`
- **Multilingual logs**: German 🇩🇪 / English 🇬🇧 (`LANG=de|en`)
- **Debug mode** for detailed decision traces
- Simple **`.env` configuration** for domains and secrets
- **`.env.example` included** — copy/rename to `.env` and fill your values

---

## 📦 Requirements

```
requests>=2.31.0
python-whois>=0.8
python-dotenv>=1.0.0
```

Install:

```
pip install -r requirements.txt
```

---

## ⚙️ Setup

### 1) Clone & install

```
git clone https://github.com/FlexKleks/DomainChecker.git
cd DomainChecker
pip install -r requirements.txt
```

### 2) Configure environment

Copy the template and **rename** it to `.env`:

```
cp .env.example .env
```

Open `.env` and edit:

```
# Language (de/en)
LANG=de

# Debug logging (0 = off, 1 = on)
DEBUG=1

# Send a Telegram test message on startup (0/1)
TELEGRAM_TEST_ON_START=0

# Domains to check (comma, space, or semicolon separated)
DOMAINS=example.de example.com test.org

# Telegram bot token (create via @BotFather)
TELEGRAM_BOT_TOKEN=123456789:ABCDEF...

# Your numeric Telegram chat ID (see "Get Chat ID" below)
TELEGRAM_CHAT_ID=123456789

# Delay between checks in seconds (float allowed)
CHECK_DELAY_SECONDS=2
```

> **Note:** Do **not** commit your real `.env`. Keep secrets local. Use `.env.example` for sharing defaults.

---

## 📲 Get your Telegram Chat ID

1. Start a chat with your bot (created via **@BotFather**) and send any message (e.g., `/start`).
2. Open in your browser:
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
3. Look for:
   ```
   "chat": { "id": 123456789, "type": "private", ... }
   ```
   Use that number as `TELEGRAM_CHAT_ID`.

(Alternatively, message `@userinfobot` to get your user ID.)

---

## 🚀 Run

```
python3 domain_checker.py
```

You should see logs in the console. If any domain is detected as newly available, you’ll receive a Telegram alert.

---

## 🔍 How it works (decision logic)

1. For each domain, query the **authoritative RDAP** for its TLD:
   - `.de` → DENIC
   - `.net` / `.com` → Verisign
   - `.eu` → EURid
   - `.at` → nic.at
   - `.org` → PIR
2. If authoritative RDAP returns **404** (or RDAP errorCode 404) → **FREE**.
3. If authoritative RDAP is **unknown/unreachable**, check **rdap.org** and **WHOIS**:
   - Only if **both** say “free” → **FREE**.
4. Otherwise → **TAKEN** (conservative).
5. Newly free domains trigger **one-time notifications**, tracked in `.notified.json`.

---

## 🛠 Maintenance & Testing

- **Reset all notification markers** (so next run alerts again for free domains):
  ```
  rm -f .notified.json
  ```

- **Force notify all currently-free domains (for testing)**:
  - Add this env var just for a test run:
    ```
    FORCE_NOTIFY_ALL_AVAILABLE=1 python3 domain_checker.py
    ```
  - (Requires a tiny optional patch in code; omit in production to prevent spam.)

- **Increase delay** if you monitor many domains:
  ```
  CHECK_DELAY_SECONDS=5
  ```

- **Enable debug logs** to see full decision paths:
  ```
  DEBUG=1
  ```

---

## 📄 License

This project is licensed under the **MIT License**. See `LICENSE` for details.

---

## 💡 Tips

- Keep your `.env` **private** (contains your bot token).
- If you run via cron/systemd, make sure the working directory contains `.env` (or set explicit environment variables in your unit).
- Use `TELEGRAM_TEST_ON_START=1` once to verify that Telegram delivery works.

---

## 🌐 Supported TLDs

```
.de   (DENIC)
.net  (Verisign)
.eu   (EURid)
.com  (Verisign)
.at   (nic.at)
.org  (Public Interest Registry)
```