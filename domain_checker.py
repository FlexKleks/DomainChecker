#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Domain Checker (hardened, multi-TLD, with per-check delay)
- Reads domains from .env (DOMAINS)
- Authoritative RDAP first (.de/.net/.eu/.com/.at/.org)
- Only 'free' if:
   A) official RDAP returns 404  -> free
   B) official RDAP is unknown, AND rdap.org == free AND WHOIS == free  -> free
- Else -> not free (conservative)
- Telegram alert once per domain (persisted in .notified.json)
- i18n (de/en), Debug logs, optional startup test
- NEW: Delay between checks via CHECK_DELAY_SECONDS

Author: FlexKleks 🦊
Contact: jd@jo-da.eu
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

try:
    import whois  # optional fallback
except Exception:
    whois = None

# ====================== CONFIG ===============================================
LANG = (os.getenv("LANG", "de") or "de").lower()
if LANG not in ("de", "en"):
    LANG = "en"

DEBUG = (os.getenv("DEBUG", "0") == "1")
TELEGRAM_TEST_ON_START = (os.getenv("TELEGRAM_TEST_ON_START", "0") == "1")

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
            out.append(lc)
            seen.add(lc)
    return out

DOMAINS = parse_domains(os.getenv("DOMAINS", ""))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "").strip()

STATE_DIR = Path(__file__).resolve().parent
NOTIFIED_FILE = STATE_DIR / ".notified.json"

def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default

def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default

HTTP_TIMEOUT  = _int_env("HTTP_TIMEOUT", 15)
WHOIS_TIMEOUT = _int_env("WHOIS_TIMEOUT", 20)
RETRY_COUNT   = _int_env("RETRY_COUNT", 2)

# NEW: Delay zwischen Domain-Checks (Sekunden, float möglich)
CHECK_DELAY_SECONDS = _float_env("CHECK_DELAY_SECONDS", 2.0)

# ---------------- Authoritative RDAP endpoints ----------------
OFFICIAL_RDAP = {
    ".de":  "https://rdap.denic.de/domain/{d}",                           # DENIC
    ".net": "https://rdap.verisign.com/net/v1/domain/{d}",                # Verisign
    ".eu":  "https://rdap.eurid.eu/rdap/domain/{d}",                      # EURid
    ".com": "https://rdap.verisign.com/com/v1/domain/{d}",                # Verisign
    ".at":  "https://rdap.nic.at/domain/{d}",                             # nic.at
    ".org": "https://rdap.publicinterestregistry.net/rdap/org/domain/{d}" # PIR
}

# Helper RDAP (non-authoritative)
HELPER_RDAP = "https://rdap.org/domain/{d}"

UA_HEADERS = {"User-Agent": "DomainChecker/2.2 (+contact: admin@example.invalid)"}
# ============================================================================

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
    },
}
def tr(key: str, **kw) -> str:
    return TXT[LANG][key].format(**kw)

# ---------------- Logging ----------------
def now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def log(msg: str):  print(f"[{now()}] {msg}")
def debug(msg: str):
    if DEBUG: log(f"DEBUG: {msg}")

# ---------------- Persistence ----------------
def load_notified() -> set:
    if NOTIFIED_FILE.exists():
        try:
            return set(json.loads(NOTIFIED_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()

def save_notified(s: set):
    NOTIFIED_FILE.write_text(json.dumps(sorted(list(s)), ensure_ascii=False, indent=2), encoding="utf-8")

def mask_token(t: str) -> str:
    if not t: return "no"
    return f"***{t[-4:]}" if len(t) > 4 else "***"

# ---------------- Telegram ----------------
def telegram_send(token: str, chat_id: str, text: str):
    if not token or not chat_id:
        raise RuntimeError("Telegram: BOT_TOKEN or CHAT_ID missing.")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
                      timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()

# ---------------- RDAP / WHOIS ----------------
def tld_of(domain: str) -> str:
    for t in (".de", ".net", ".eu", ".com", ".at", ".org"):
        if domain.endswith(t):
            return t
    return ""

def rdap_fetch(url: str):
    """Return tuple (state, http_status, diag).
       state in {'free','taken','unknown'}"""
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            r = requests.get(url, timeout=HTTP_TIMEOUT, headers=UA_HEADERS)
            st = r.status_code
            if st == 404:
                return "free", 404, "HTTP 404"
            if st == 200:
                try:
                    data = r.json()
                except ValueError:
                    return "taken", 200, "200 no-json"
                if isinstance(data, dict) and data.get("objectClassName") == "domain":
                    return "taken", 200, "RDAP domain"
                if isinstance(data, dict) and "errorCode" in data:
                    code = int(data.get("errorCode") or 0)
                    if code == 404:
                        return "free", 200, "RDAP errorCode=404"
                    return "unknown", 200, f"RDAP errorCode={code}"
                return "taken", 200, "200 unknown-json"
            if st in (400, 429, 500, 502, 503, 504):
                return "unknown", st, f"HTTP {st}"
            return "unknown", st, f"HTTP {st}"
        except requests.RequestException as e:
            if attempt == RETRY_COUNT:
                return "unknown", None, f"EXC {type(e).__name__}: {e}"
    return "unknown", None, "unreachable"

def whois_check(domain: str) -> str:
    """Return 'free'|'taken'|'unknown' using python-whois."""
    if whois is None:
        return "unknown"
    try:
        w = whois.whois(domain, timeout=WHOIS_TIMEOUT)
        if not getattr(w, "registrar", None) and not getattr(w, "creation_date", None):
            return "free"
        return "taken"
    except Exception as e:
        s = str(e).lower()
        hints = ["no match","not found","no entries found","status: free","available"]
        if any(h in s for h in hints):
            return "free"
        return "unknown"

def is_domain_available(domain: str) -> bool:
    """Hardened decision:
       1) Official RDAP -> free => FREE; taken => TAKEN; unknown => step 2
       2) Consensus (rdap.org == free AND whois == free) => FREE
       else => TAKEN (conservative)
    """
    tld = tld_of(domain)
    off_url = OFFICIAL_RDAP.get(tld)
    if off_url:
        state_off, st_off, diag_off = rdap_fetch(off_url.format(d=domain))
        debug(f"[official] {domain} -> {state_off} ({diag_off})")
        if state_off == "free":  return True
        if state_off == "taken": return False
    else:
        debug(f"No official RDAP for {domain}; skipping to consensus.")

    # Consensus fallback
    state_helper, st_helper, diag_helper = rdap_fetch(HELPER_RDAP.format(d=domain))
    state_whois = whois_check(domain)
    debug(f"[helper]   {domain} -> {state_helper} ({diag_helper})")
    debug(f"[whois]    {domain} -> {state_whois}")

    if state_helper == "free" and state_whois == "free":
        return True
    return False

# ---------------- Main ----------------
def main():
    debug(f"ENV check: token={mask_token(TELEGRAM_BOT_TOKEN)}, chat_id={TELEGRAM_CHAT_ID or 'no'}, domains={len(DOMAINS)}, delay={CHECK_DELAY_SECONDS}s")

    if TELEGRAM_TEST_ON_START and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            telegram_send(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, "✅ Domain-Checker started – Telegram OK.")
            debug("Startup test sent.")
        except Exception as e:
            log(f"Telegram test failed: {e}")

    list_str = ", ".join(DOMAINS) if DOMAINS else "(none)"
    log(tr("start", list=list_str))
    if not DOMAINS:
        log(tr("no_domains"))

    notified = load_notified()
    newly = []

    for idx, d in enumerate(DOMAINS):
        # Delay vor JEDEM Check ab dem zweiten Eintrag
        if idx > 0 and CHECK_DELAY_SECONDS > 0:
            debug(f"Delay {CHECK_DELAY_SECONDS:.2f}s before checking next domain…")
            time.sleep(CHECK_DELAY_SECONDS)

        free = is_domain_available(d)
        log(f"{d}: {tr('available') if free else tr('taken')}")
        if free and d not in notified:
            newly.append(d)

    if newly:
        log(tr("new_avail", list=", ".join(newly)))
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            try:
                ts = datetime.now().strftime('%Y-%m-%d %H:%M')
                title = "🚨 Domain(s) available!" if LANG == "en" else "🚨 Domain(s) verfügbar!"
                stamp = "As of" if LANG == "en" else "Stand"
                msg = title + "\n" + "\n".join(f"• {x}" for x in newly) + f"\n\n{stamp}: {ts}"
                telegram_send(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, msg)
                log(tr("sent"))
            except Exception as e:
                log(tr("send_fail", err=e))
        else:
            if not TELEGRAM_BOT_TOKEN: log(tr("missing_tok"))
            if not TELEGRAM_CHAT_ID:   log(tr("missing_id"))
        notified.update(newly)
        save_notified(notified)
    else:
        log(tr("none_new"))

    log(tr("done"))

if __name__ == "__main__":
    main()
