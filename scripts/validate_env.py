"""
validate_env.py — Verifica che tutte le env var siano presenti e le connessioni funzionino.

Eseguire prima del go-live e dopo ogni modifica alle configurazioni:
    python scripts/validate_env.py

Output atteso: ✅ Tutti i controlli superati.
"""
import sys
import os

# Aggiungi root al path per importare config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import (
    GCP_PROJECT_ID, GEMINI_API_KEY, TELEGRAM_BOT_TOKEN,
    BQ_FULL_TABLE, GEMINI_API_URL, GEMINI_MODEL,
    LAST_AVAILABLE_MONTH,
)

errors: list[str] = []
warnings: list[str] = []


def check(condition: bool, name: str, detail: str = "") -> bool:
    if condition:
        print(f"  ✅ {name}")
        return True
    else:
        msg = f"  ❌ {name}" + (f" — {detail}" if detail else "")
        print(msg)
        errors.append(name)
        return False


def warn(condition: bool, name: str, detail: str = "") -> None:
    if not condition:
        msg = f"  ⚠️  {name}" + (f" — {detail}" if detail else "")
        print(msg)
        warnings.append(name)


# ── 1. Variabili d'ambiente obbligatorie ─────────────────────────────────────
print("\n1️⃣  Variabili d'ambiente")
check(bool(GCP_PROJECT_ID), "GCP_PROJECT_ID", f"valore: {GCP_PROJECT_ID}")
check(bool(GEMINI_API_KEY), "GEMINI_API_KEY", "vuota — caricarla da Secret Manager")
check(bool(TELEGRAM_BOT_TOKEN), "TELEGRAM_BOT_TOKEN", "vuota — caricarla da Secret Manager")
check(bool(BQ_FULL_TABLE), "BQ_FULL_TABLE", f"valore: {BQ_FULL_TABLE}")
check(LAST_AVAILABLE_MONTH.count("-") == 2, "LAST_AVAILABLE_MONTH", f"valore: {LAST_AVAILABLE_MONTH}")

# ── 2. Connessione Gemini API ─────────────────────────────────────────────────
print("\n2️⃣  Connessione Gemini API")
if GEMINI_API_KEY:
    try:
        import requests as req
        payload = {
            "contents": [{"parts": [{"text": "rispondi solo con OK"}]}],
            "generationConfig": {"maxOutputTokens": 10},
        }
        headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
        r = req.post(GEMINI_API_URL, json=payload, headers=headers, timeout=15)
        check(r.status_code == 200, f"Gemini {GEMINI_MODEL} raggiungibile", f"status={r.status_code}")
    except Exception as e:
        check(False, "Gemini API", str(e))
else:
    warnings.append("Gemini API: skippato (GEMINI_API_KEY vuota)")
    print("  ⚠️  Gemini API: skippato (GEMINI_API_KEY non configurata)")

# ── 3. Connessione BigQuery ───────────────────────────────────────────────────
print("\n3️⃣  Connessione BigQuery")
try:
    from google.cloud import bigquery
    client = bigquery.Client(project=GCP_PROJECT_ID)
    test_query = f"SELECT COUNT(*) as tot FROM `{GCP_PROJECT_ID}.{BQ_FULL_TABLE}` LIMIT 1"
    result = list(client.query(test_query).result())
    check(True, f"BigQuery '{BQ_FULL_TABLE}' accessibile", f"{result[0]['tot']} record")
except Exception as e:
    check(False, "BigQuery", str(e))

# ── 4. Connessione Telegram ───────────────────────────────────────────────────
print("\n4️⃣  Connessione Telegram Bot API")
if TELEGRAM_BOT_TOKEN:
    try:
        import requests as req
        r = req.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe",
            timeout=10,
        )
        data = r.json()
        check(data.get("ok"), "Telegram Bot Token valido", f"bot: @{data.get('result', {}).get('username', '?')}")
    except Exception as e:
        check(False, "Telegram Bot API", str(e))
else:
    warnings.append("Telegram: skippato (TELEGRAM_BOT_TOKEN vuoto)")
    print("  ⚠️  Telegram: skippato (TELEGRAM_BOT_TOKEN non configurato)")

# ── Riepilogo ─────────────────────────────────────────────────────────────────
print("\n" + "─" * 50)
if errors:
    print(f"❌ {len(errors)} controllo/i fallito/i: {', '.join(errors)}")
    sys.exit(1)
elif warnings:
    print(f"⚠️  Completato con {len(warnings)} avviso/i ({'; '.join(warnings)})")
    print("✅ Controli principali superati.")
else:
    print("✅ Tutti i controlli superati.")
