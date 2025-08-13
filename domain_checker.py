#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Domain Checker
- Reads domains from .env (DOMAINS)
- Uses RDAP for .de/.net/.eu with python-whois fallback
- Sends Telegram alerts when a domain becomes available (first time only)
- i18n (de/en), Debug logs, and optional startup test message

Author: FlexKleks 🦊
Contact: jd@jo-da.eu
"""

import os
import json
from datetime import datetime
from pathlib import Path
import requests
from dotenv import load_dotenv

# Load .env (must live next to this script)
load_dotenv()

try:
    import whois  # optional fallback
except Exception:
    whois = None

# ====================== CONFIG ===============================================
# Language: "de" or "en" (default: de)
LANG = (os.getenv("LANG", "de") or "de").lower()
if LANG not in ("de", "en"):
    LANG = "en"

# Debug mode (more logs)
DEBUG = (os.getenv("DEBUG", "0") == "1")

# Optional: send a Telegram "I'm alive" on start
TELEGRAM_TEST_ON_START = (os.getenv("TELEGRAM_TEST_ON_START", "0") == "1")

# Domains from .env (DOMAINS="a.de, b.net; c.eu   d.de")
def parse_domains(env_val: str) -> list[str]:
    if not env_val:
        return []
    raw = [p.strip() for chunk in env_val.replace(";", ",").split(",") for p in chunk.split()]
    seen, out = set(), []
    for d in raw:
        if not d or d.startswith("#"):
            continue
        lc = d.lower()
        if lc not in seen:
            out.append(d)
            seen.add(lc)
    return out

DOMAINS = parse_domains(os.getenv("DOMAINS", ""))

# Telegram (from .env)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Persistence
STATE_DIR = Path(__file__).resolve().parent
NOTIFIED_FILE = STATE_DIR / ".notified.json"

# Timeouts/Retry
HTTP_TIMEOUT  = int(os.getenv("HTTP_TIMEOUT", "15"))
WHOIS_TIMEOUT = int(os.getenv("WHOIS_TIMEOUT", "20"))
RETRY_COUNT   = int(os.getenv("RETRY_COUNT", "2"))

# RDAP endpoints (try rdap.org first, then registry-native)
RDAP_ENDPOINTS = {
    ".de":  [
        "https://rdap.org/domain/{d}",
        "https://rdap.denic.de/domain/{d}",
    ],
    ".net": [
        "https://rdap.org/domain/{d}",
        "https://rdap.verisign.com/net/v1/domain/{d}",
    ],
    ".eu":  [
        "https://rdap.org/domain/{d}",
        "https://rdap.eurid.eu/rdap/domain/{d}",
        "https://rdap.eurid.eu/domain/{d}",
    ],
}

UA_HEADERS = {
    "User-Agent": "DomainChecker/1.1 (+contact: admin@example.invalid)"
}
# ============================================================================

# --------- i18n ----------
TXT = {
    "de": {
        "start":       "Starte einmalige Domain-Prüfung für: {list}",
        "no_domains":  "Hinweis: Trage Domains in der .env unter DOMAINS ein.",
        "available":   "VERFÜGBAR",
        "taken":       "vergeben",
        "new_avail":   "Neue verfügbare Domains: {list}",
        "sent":        "Telegram-Benachrichtigung gesendet.",
        "send_fail":   "Telegram-Senden fehlgeschlagen: {err}",
        "missing_tok": "⚠️ TELEGRAM_BOT_TOKEN fehlt.",
        "missing_id":  "⚠️ TELEGRAM_CHAT_ID fehlt.",
        "none_new":    "Keine neuen verfügbaren Domains.",
        "done":        "Fertig.",
        "alert_title": "🚨 Domain(s) verfügbar!",
        "timestamp":   "Stand",
        "rdap_log":    "RDAP {tld}: {dom} -> {state} ({diag}, URL {url})",
        "dbg_env":     "DEBUG: ENV ok? token={tok}, chat_id={cid}, domains={n}",
        "dbg_test_ok": "Debug: Starttest an Telegram gesendet.",
        "dbg_test_no": "Debug: Starttest übersprungen (fehlende Telegram-ENV).",
    },
    "en": {
        "start":       "Starting one-time domain check for: {list}",
        "no_domains":  "Hint: Add domains in .env under DOMAINS.",
        "available":   "AVAILABLE",
        "taken":       "taken",
        "new_avail":   "Newly available domains: {list}",
        "sent":        "Telegram notification sent.",
        "send_fail":   "Telegram send failed: {err}",
        "missing_tok": "⚠️ TELEGRAM_BOT_TOKEN missing.",
        "missing_id":  "⚠️ TELEGRAM_CHAT_ID missing.",
        "none_new":    "No newly available domains.",
        "done":        "Done.",
        "alert_title": "🚨 Domain(s) available!",
        "timestamp":   "As of",
        "rdap_log":    "RDAP {tld}: {dom} -> {state} ({diag}, URL {url})",
        "dbg_env":     "DEBUG: ENV ok? token={tok}, chat_id={cid}, domains={n}",
        "dbg_test_ok": "Debug: Startup test message sent to Telegram.",
        "dbg_test_no": "Debug: Startup test skipped (Telegram ENV missing).",
    },
}

def tr(key: str, **kw) -> str:
    return TXT[LANG][key].format(**kw)

# --------- Logging ----------
def now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def log(msg: str):
    print(f"[{now()}] {msg}")

def debug(msg: str):
    if DEBUG:
        log(msg)

# --------- Core helpers ----------
def load_notified() -> set:
    if NOTIFIED_FILE.exists():
        try:
            return set(json.loads(NOTIFIED_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()

def save_notified(notified: set):
    NOTIFIED_FILE.write_text(
        json.dumps(sorted(list(notified)), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def mask_token(t: str) -> str:
    if not t:
        return "no"
    if len(t) <= 6:
        return "***"
    return f"***{t[-4:]}"

def telegram_send(token: str, chat_id: str, text: str):
    if not token or not chat_id:
        raise RuntimeError("Telegram: BOT_TOKEN or CHAT_ID missing.")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
                      timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()

def tld_of(domain: str) -> str:
    d = domain.lower().strip()
    for tld in RDAP_ENDPOINTS.keys():
        if d.endswith(tld):
            return tld
    return ""

def rdap_query_once(url: str):
    """
    Return: ('free' | 'taken' | 'unknown', http_status:int|None, diag:str)
    """
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            r = requests.get(url, timeout=HTTP_TIMEOUT, headers=UA_HEADERS)
            status = r.status_code
            if status == 404:
                return "free", status, "HTTP 404"
            if status == 200:
                try:
                    data = r.json()
                except ValueError:
                    return "taken", status, "200 no-json"
                if isinstance(data, dict) and data.get("objectClassName") == "domain":
                    return "taken", status, "200 RDAP domain"
                if isinstance(data, dict) and "errorCode" in data:
                    if int(data.get("errorCode") or 0) == 404:
                        return "free", status, "200 RDAP errorCode=404"
                    return "unknown", status, f"200 RDAP errorCode={data.get('errorCode')}"
                return "taken", status, "200 unknown-json"
            if status in (400, 429, 500, 502, 503, 504):
                return "unknown", status, f"HTTP {status}"
            return "unknown", status, f"HTTP {status}"
        except requests.RequestException as e:
            if attempt == RETRY_COUNT:
                return "unknown", None, f"EXC {type(e).__name__}: {e}"
            # retry
    return "unknown", None, "unreachable"

def rdap_check(domain: str) -> bool | None:
    tld = tld_of(domain)
    if not tld:
        return None
    for tpl in RDAP_ENDPOINTS.get(tld, []):
        url = tpl.format(d=domain)
        state, http_status, diag = rdap_query_once(url)
        log(tr("rdap_log", tld=tld, dom=domain, state=state, diag=diag, url=url))
        if state == "free":
            return True
        if state == "taken":
            return False
    return None

def whois_fallback(domain: str) -> bool | None:
    if whois is None:
        return None
    try:
        w = whois.whois(domain, timeout=WHOIS_TIMEOUT)
        if not getattr(w, "registrar", None) and not getattr(w, "creation_date", None):
            return True
        return False
    except Exception as e:
        s = str(e).lower()
        hints = ["no match", "not found", "no entries found", "status: free", "available"]
        if any(h in s for h in hints):
            return True
        return False

def is_domain_available(domain: str) -> bool:
    rd = rdap_check(domain)
    if rd is not None:
        return rd
    wf = whois_fallback(domain)
    if wf is not None:
        return wf
    return False  # conservative

# --------- Main ----------
def main():
    # Debug summary of environment (without leaking secrets)
    debug(tr("dbg_env", tok=mask_token(TELEGRAM_BOT_TOKEN), cid=TELEGRAM_CHAT_ID or "no", n=len(DOMAINS)))

    if TELEGRAM_TEST_ON_START and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            telegram_send(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
                          "✅ Domain-Checker started – Telegram OK.")
            debug(tr("dbg_test_ok"))
        except Exception as e:
            log(tr("send_fail", err=e))
    else:
        debug(tr("dbg_test_no"))

    dom_list_str = ", ".join(DOMAINS) if DOMAINS else "(none / keine)"
    log(tr("start", list=dom_list_str))
    if not DOMAINS:
        log(tr("no_domains"))

    notified = load_notified()
    newly = []

    for d in DOMAINS:
        avail = is_domain_available(d)
        log(f"{d}: {tr('available') if avail else tr('taken')}")
        if avail and d not in notified:
            newly.append(d)

    if newly:
        log(tr("new_avail", list=", ".join(newly)))
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            try:
                stamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                msg = tr("alert_title") + "\n" + "\n".join(f"• {x}" for x in newly) + f"\n\n{tr('timestamp')}: {stamp}"
                telegram_send(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, msg)
                log(tr("sent"))
            except Exception as e:
                log(tr("send_fail", err=e))
        else:
            if not TELEGRAM_BOT_TOKEN:
                log(tr("missing_tok"))
            if not TELEGRAM_CHAT_ID:
                log(tr("missing_id"))
        notified.update(newly)
        save_notified(notified)
    else:
        log(tr("none_new"))

    log(tr("done"))

if __name__ == "__main__":
    main()
