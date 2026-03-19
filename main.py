"""
main.py — Entry point webhook Cloud Function per HR Director Bot.

Flusso:
1. Autenticazione email (prima sessione)
2. Risoluzione periodo temporale
3. NL2SQL via Gemini
4. Esecuzione query BigQuery
5. Formattazione risposta in italiano via Gemini
6. Invio risposta via Telegram
"""
import json
import logging
import functions_framework
import requests
from flask import Request

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_API_URL
from execution.auth_handler import is_authenticated, try_authenticate
from execution.nl2sql import generate_sql, resolve_month
from execution.bq_client import run_query
from execution.formatter import format_response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Stato in memoria: utenti in attesa di inserire l'email
pending_auth: dict[int, bool] = {}


def send_message(chat_id: int, text: str) -> None:
    """Invia un messaggio Telegram al chat_id specificato."""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Telegram send error | chat_id=%d | error=%s", chat_id, str(e))


@functions_framework.http
def hr_bot_webhook(request: Request):
    """Entry point Cloud Function — riceve webhook POST da Telegram."""

    # Gestione health check
    if request.method == "GET":
        return "HR Bot OK", 200

    try:
        body = request.get_json(silent=True)
        if not body or "message" not in body:
            return "OK", 200

        message = body["message"]
        chat_id: int = message["chat"]["id"]
        user_text: str = message.get("text", "").strip()

        if not user_text:
            return "OK", 200

        logger.info("Messaggio ricevuto | chat_id=%d | len=%d", chat_id, len(user_text))

        # ── STEP 1 — Autenticazione ────────────────────────────────────────────
        if not is_authenticated(chat_id):
            if pending_auth.get(chat_id):
                # L'utente sta fornendo l'email
                if try_authenticate(chat_id, user_text):
                    pending_auth.pop(chat_id, None)
                    send_message(chat_id, "✅ Accesso confermato. Puoi chiedere qualsiasi informazione sui dipendenti.")
                else:
                    send_message(chat_id, "❌ Utente non autorizzato.")
                    pending_auth.pop(chat_id, None)
                return "OK", 200
            else:
                # Prima interazione: chiedi email
                pending_auth[chat_id] = True
                send_message(chat_id, "Ciao! Per accedere inserisci la tua email aziendale:")
                return "OK", 200

        # ── STEP 2 — Risoluzione periodo temporale ────────────────────────────
        resolved_month = resolve_month(user_text)

        # ── STEP 3 — NL2SQL ───────────────────────────────────────────────────
        try:
            sql = generate_sql(user_text, resolved_month)
            logger.info("SQL generato | chat_id=%d", chat_id)
        except RuntimeError as e:
            logger.error("NL2SQL error | chat_id=%d | %s", chat_id, str(e))
            send_message(chat_id, "⚠️ Non sono riuscito a interpretare la domanda. Prova a riformularla.")
            return "OK", 200

        # ── STEP 4 — Esecuzione query BigQuery ───────────────────────────────
        try:
            results = run_query(sql)
            logger.info("BQ query OK | chat_id=%d | rows=%d", chat_id, len(results))
        except RuntimeError as e:
            logger.error("BQ error | chat_id=%d | %s", chat_id, str(e))
            send_message(chat_id, "⚠️ Si è verificato un errore nell'accesso al database. Riprova tra qualche secondo.")
            return "OK", 200

        # ── STEP 5 — Formattazione risposta ──────────────────────────────────
        try:
            answer = format_response(user_text, resolved_month, results)
        except RuntimeError as e:
            logger.error("Formatter error | chat_id=%d | %s", chat_id, str(e))
            answer = f"Risultato grezzo: {results}"

        # ── STEP 6 — Risposta Telegram ────────────────────────────────────────
        send_message(chat_id, answer)
        return "OK", 200

    except Exception as e:
        logger.error("Unhandled error in webhook: %s", str(e), exc_info=True)
        return "OK", 200  # Sempre 200 per evitare retry loop di Telegram
