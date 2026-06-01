#!/usr/bin/env python3
"""
Trump Stock Alert
=================
Überwacht Donald Trumps Truth-Social-Posts und schickt dir eine
Telegram-Push-Nachricht aufs Handy, sobald er eine Aktie / ein
börsennotiertes Unternehmen (positiv) erwähnt.

Du musst NUR die 3 Tokens unten eintragen (siehe README.md).
Alles andere ist fertig.

Autor-Hinweis: Das ist ein Lern-/Info-Tool, KEINE Anlageberatung.
"""

import os
import re
import sys
import json
import time
import html
import requests

# ============================================================
#  1) CONFIG  -  HIER deine Tokens eintragen (oder per Env-Var)
# ============================================================
# Lokal:  einfach hier zwischen die Anführungszeichen einsetzen.
# GitHub: leer lassen und stattdessen "Secrets" benutzen (siehe README).

SCRAPE_CREATORS_API_KEY = os.environ.get("SCRAPE_CREATORS_API_KEY", "HIER_DEIN_SCRAPECREATORS_KEY")
TELEGRAM_BOT_TOKEN      = os.environ.get("TELEGRAM_BOT_TOKEN",      "HIER_DEIN_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID        = os.environ.get("TELEGRAM_CHAT_ID",        "HIER_DEINE_CHAT_ID")

# OPTIONAL: macht die Erkennung "schlau" (versteht Kontext + Stimmung).
# Wenn leer, wird die einfache Stichwort-Liste unten benutzt.
ANTHROPIC_API_KEY       = os.environ.get("ANTHROPIC_API_KEY", "")

# Wie oft prüfen (Sekunden), wenn das Skript dauerhaft läuft.
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "60"))

# RUN_ONCE=1  -> einmal prüfen und beenden (für GitHub Actions Cron)
# sonst       -> Dauerschleife (für PC / Server / Raspberry Pi)
RUN_ONCE = os.environ.get("RUN_ONCE", "0") == "1"

# ============================================================
#  2) WATCHLIST  -  welche Firmen / Ticker dich interessieren
# ============================================================
# Format:  "TICKER": ["schreibweise1", "schreibweise2", ...]
# Wird nur für den einfachen Modus (ohne Anthropic-Key) genutzt.
# Erweitere die Liste beliebig.
WATCHLIST = {
    # --- Big Tech / Megacaps ---
    "AAPL":  ["apple"],
    "MSFT":  ["microsoft"],
    "GOOGL": ["google", "alphabet"],
    "META":  ["meta", "facebook"],
    "AMZN":  ["amazon"],
    "NFLX":  ["netflix"],
    "TSLA":  ["tesla"],
 
    # --- KI-Chips & Halbleiter ---
    "NVDA":  ["nvidia"],
    "AMD":   ["amd", "advanced micro"],
    "AVGO":  ["broadcom"],
    "TSM":   ["tsmc", "taiwan semiconductor"],
    "INTC":  ["intel"],
    "MU":    ["micron"],
    "QCOM":  ["qualcomm"],
    "ARM":   ["arm holdings"],
    "MRVL":  ["marvell"],
    "TXN":   ["texas instruments"],
    "SMCI":  ["super micro", "supermicro"],
    "ASML":  ["asml"],
    "AMAT":  ["applied materials"],
    "LRCX":  ["lam research"],
    "ON":    ["on semiconductor", "onsemi"],
    "GFS":   ["globalfoundries"],
 
    # --- KI-Infrastruktur / Rechenzentren ---
    "DELL":  ["dell"],
    "VRT":   ["vertiv"],
    "ANET":  ["arista"],
    "CRWV":  ["coreweave"],
    "NBIS":  ["nebius"],
    "ALAB":  ["astera labs"],
 
    # --- KI Pure-Plays ---
    "PLTR":  ["palantir"],
    "AI":    ["c3.ai", "c3 ai"],
    "BBAI":  ["bigbear.ai", "bigbear ai"],
    "SOUN":  ["soundhound"],
    "PATH":  ["uipath"],
    "UPST":  ["upstart"],
 
    # --- Cybersecurity ---
    "CRWD":  ["crowdstrike"],
    "PANW":  ["palo alto networks", "palo alto"],
    "ZS":    ["zscaler"],
    "FTNT":  ["fortinet"],
    "NET":   ["cloudflare"],
 
    # --- Enterprise-Software / Cloud ---
    "IBM":   ["ibm"],
    "NOW":   ["servicenow"],
    "ORCL":  ["oracle"],
    "CRM":   ["salesforce"],
    "CSCO":  ["cisco"],
    "ADBE":  ["adobe"],
    "SNOW":  ["snowflake"],
    "DDOG":  ["datadog"],
    "MDB":   ["mongodb"],
    "WDAY":  ["workday"],
    "INTU":  ["intuit"],
    "SHOP":  ["shopify"],
    "UBER":  ["uber"],
 
    # --- Quantencomputing ---
    "IONQ":  ["ionq"],
    "RGTI":  ["rigetti"],
    "QBTS":  ["d-wave", "dwave"],
 
    # --- Trump-Media / MAGA ---
    "DJT":   ["trump media", "truth social"],
    "RUM":   ["rumble"],
 
    # --- Space / Defense ---
    "RKLB":  ["rocket lab", "rocketlab"],
    "LMT":   ["lockheed", "lockheed martin"],
    "NOC":   ["northrop"],
    "RTX":   ["raytheon", "rtx"],
    "GD":    ["general dynamics"],
    "BA":    ["boeing"],
    "ASTS":  ["ast spacemobile", "ast space"],
    "LUNR":  ["intuitive machines"],
    "PL":    ["planet labs"],
 
    # --- Energie ("drill baby drill") ---
    "XOM":   ["exxon", "exxonmobil"],
    "CVX":   ["chevron"],
    "OXY":   ["occidental"],
 
    # --- Stahl / Industrie ---
    "X":     ["us steel", "u.s. steel"],
    "NUE":   ["nucor"],
    "CLF":   ["cleveland-cliffs", "cleveland cliffs"],
 
    # --- Krypto-Aktien ---
    "COIN":  ["coinbase"],
    "MSTR":  ["microstrategy"],
    "MARA":  ["marathon digital"],
    "RIOT":  ["riot platforms"],
 
    # --- Autos ---
    "F":     ["ford"],
    "GM":    ["general motors"],
    "STLA":  ["stellantis", "chrysler"],
 
    # --- Pharma ---
    "PFE":   ["pfizer"],
    "LLY":   ["eli lilly"],
    "MRNA":  ["moderna"],
 
    # --- Finanz / Retail ---
    "JPM":   ["jpmorgan", "jp morgan"],
    "GS":    ["goldman"],
    "WMT":   ["walmart"],
    "HD":    ["home depot"],
}

# ============================================================
#  Ab hier musst du nichts mehr anfassen.
# ============================================================

# Trumps echte Truth-Social-User-ID
TRUMP_USER_ID = "107780257626128497"
SCRAPECREATORS_URL = "https://api.scrapecreators.com/v1/truthsocial/user/posts"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_posts.json")
MAX_SEEN = 300  # wie viele Post-IDs wir uns merken


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def load_seen():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"ids": [], "initialized": False}


def save_seen(state):
    state["ids"] = state["ids"][-MAX_SEEN:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def strip_html(text):
    """Truth-Social-Posts kommen teils als HTML -> in sauberen Text wandeln."""
    text = re.sub(r"<br\s*/?>", "\n", text or "")
    text = re.sub(r"</p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def fetch_posts():
    """Holt Trumps neueste Posts von Truth Social."""
    try:
        r = requests.get(
            SCRAPECREATORS_URL,
            params={"user_id": TRUMP_USER_ID},
            headers={"x-api-key": SCRAPE_CREATORS_API_KEY},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log(f"FEHLER beim Abrufen der Posts: {e}")
        return []

    posts = data.get("posts") or data.get("data") or []
    normalized = []
    for p in posts:
        raw = p.get("text") or p.get("content") or ""
        normalized.append({
            "id": str(p.get("id", "")),
            "text": strip_html(raw),
            "created_at": p.get("created_at", ""),
        })
    return [p for p in normalized if p["id"] and p["text"]]


# ---------- Erkennung: einfacher Modus (Stichwortliste) ----------
def detect_keywords(text):
    """Findet Ticker anhand der WATCHLIST. Gibt Liste gefundener Ticker zurück."""
    found = set()
    low = text.lower()

    # $TICKER Erwähnungen (z.B. $DELL)
    for m in re.findall(r"\$([A-Za-z]{1,5})\b", text):
        found.add(m.upper())

    # Firmennamen aus der Watchlist
    for ticker, names in WATCHLIST.items():
        for name in names:
            if re.search(r"\b" + re.escape(name.lower()) + r"\b", low):
                found.add(ticker)
                break
    return sorted(found)


# ---------- Erkennung: schlauer Modus (Claude) ----------
def detect_with_claude(text):
    """
    Fragt Claude Haiku: Erwähnt der Post ein börsennotiertes Unternehmen
    UND ist die Stimmung positiv/werbend? Gibt (treffer: bool, tickers, grund).
    """
    prompt = (
        "Analysiere diesen Social-Media-Post. Antworte AUSSCHLIESSLICH mit JSON, "
        "kein Text drumherum, keine Markdown-Backticks.\n"
        "Format: {\"positive_mention\": true/false, \"tickers\": [\"...\"], \"reason\": \"kurz\"}\n"
        "positive_mention = true NUR wenn der Post ein konkretes boersennotiertes "
        "Unternehmen positiv, lobend oder werbend erwaehnt (nicht bei Kritik/neutral).\n"
        "tickers = Boersenticker der erwaehnten Firmen (z.B. DELL, RKLB, TSLA), leer wenn keine.\n\n"
        f"POST:\n{text}"
    )
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        r.raise_for_status()
        out = r.json()
        raw = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(raw)
        return (
            bool(parsed.get("positive_mention")),
            [t.upper() for t in parsed.get("tickers", [])],
            parsed.get("reason", ""),
        )
    except Exception as e:
        log(f"Claude-Analyse fehlgeschlagen, nutze Stichwort-Modus: {e}")
        tickers = detect_keywords(text)
        return (bool(tickers), tickers, "Stichwort-Treffer (Fallback)")


def send_telegram(message):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        r.raise_for_status()
        log("-> Telegram-Benachrichtigung gesendet.")
    except Exception as e:
        log(f"FEHLER beim Senden via Telegram: {e}")


def build_alert(post, tickers, reason):
    tick = ", ".join(tickers) if tickers else "?"
    preview = post["text"][:600]
    return (
        f"🚨 <b>TRUMP ERWÄHNT EINE AKTIE</b> 🚨\n\n"
        f"📈 <b>Ticker:</b> {html.escape(tick)}\n"
        f"🧠 <b>Grund:</b> {html.escape(reason)}\n\n"
        f"📝 <b>Post:</b>\n{html.escape(preview)}\n\n"
        f"⏰ {html.escape(str(post['created_at']))}\n"
        f"⚠️ Keine Anlageberatung. Selbst prüfen, Risiko bedenken."
    )


def check_once(state):
    posts = fetch_posts()
    if not posts:
        return

    # Erster Lauf: alte Posts merken, aber NICHT spammen.
    if not state["initialized"]:
        state["ids"] = [p["id"] for p in posts]
        state["initialized"] = True
        save_seen(state)
        log(f"Erster Lauf: {len(posts)} bestehende Posts gemerkt (kein Alarm).")
        return

    seen = set(state["ids"])
    new_posts = [p for p in posts if p["id"] not in seen]
    if not new_posts:
        log("Keine neuen Posts.")
        return

    log(f"{len(new_posts)} neue(r) Post(s) gefunden.")
    # älteste zuerst verarbeiten
    for post in reversed(new_posts):
        if ANTHROPIC_API_KEY:
            hit, tickers, reason = detect_with_claude(post["text"])
        else:
            tickers = detect_keywords(post["text"])
            hit, reason = bool(tickers), "Stichwort-Treffer aus Watchlist"

        if hit:
            log(f"TREFFER! Ticker: {tickers}")
            send_telegram(build_alert(post, tickers, reason))
        else:
            log(f"Post ohne relevante Aktien-Erwähnung: {post['text'][:60]!r}")

        state["ids"].append(post["id"])

    save_seen(state)


def check_config():
    missing = []
    if "HIER_DEIN" in SCRAPE_CREATORS_API_KEY:
        missing.append("SCRAPE_CREATORS_API_KEY")
    if "HIER_DEIN" in TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if "HIER_DEINE" in TELEGRAM_CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")
    if missing:
        log("STOPP: Diese Tokens fehlen noch (siehe README.md): " + ", ".join(missing))
        sys.exit(1)


def main():
    check_config()
    mode = "schlau (Claude)" if ANTHROPIC_API_KEY else "einfach (Stichwortliste)"
    log(f"Trump Stock Alert gestartet. Erkennungs-Modus: {mode}")
    state = load_seen()

    if RUN_ONCE:
        check_once(state)
        return

    log(f"Dauerbetrieb: prüfe alle {POLL_INTERVAL} Sekunden. (Strg+C zum Beenden)")
    while True:
        check_once(state)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
