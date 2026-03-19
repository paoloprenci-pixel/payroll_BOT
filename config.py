"""
config.py — Costanti e variabili d'ambiente per HR Director Bot
Nessun valore hardcodato: tutto letto da env var o Secret Manager.
"""
import os

# ── GCP ─────────────────────────────────────────────────────────────────────
GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "gen-lang-client-0296046668")
GCP_REGION: str = os.getenv("GCP_REGION", "europe-west1")

# ── BigQuery ─────────────────────────────────────────────────────────────────
BQ_DATASET: str = os.getenv("BQ_DATASET", "hr_analytics")
BQ_TABLE: str = os.getenv("BQ_TABLE", "dipendenti_storico")
BQ_FULL_TABLE: str = f"{BQ_DATASET}.{BQ_TABLE}"

# ── Gemini (Google AI Studio REST API) ───────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_URL: str = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

# ── Telegram ─────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_API_URL: str = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
)

# ── Autenticazione HR Bot ─────────────────────────────────────────────────────
AUTHORIZED_EMAILS: set[str] = {
    os.getenv("AUTHORIZED_EMAIL", "paoloprenci@gmail.com").strip().lower()
}

# ── Default temporale ─────────────────────────────────────────────────────────
# Aggiornare SOLO questa costante quando il dataset viene esteso.
# L'intero sistema usa questo valore quando l'utente non specifica un periodo.
LAST_AVAILABLE_MONTH: str = os.getenv("LAST_AVAILABLE_MONTH", "2026-02-01")
