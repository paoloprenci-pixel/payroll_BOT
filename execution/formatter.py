"""
formatter.py — Formattazione risposta in italiano tramite Gemini.

Riceve il risultato della query BigQuery e genera una risposta
in linguaggio naturale, chiara e comprensibile, che include
sempre il mese o periodo di riferimento usato.
"""
import requests
import logging
from config import GEMINI_API_KEY, GEMINI_API_URL

logger = logging.getLogger(__name__)

FORMATTER_SYSTEM = """Sei un assistente HR che risponde in italiano in modo chiaro e professionale.
Ricevi:
1. La domanda originale dell'utente
2. Il mese o periodo di riferimento usato
3. Il risultato di una query SQL su dati HR aziendali

Il tuo compito:
- Riformula il risultato in linguaggio naturale, chiaro e conciso
- Includi SEMPRE il mese o periodo di riferimento nella risposta (es. "A febbraio 2026..." oppure "Nel periodo gennaio–marzo 2025...")
- Arrotonda i numeri in modo leggibile (es. €45.230 invece di 45230.00)
- Se il risultato è vuoto, rispondi "Nessun dato trovato per il periodo richiesto."
- Non aggiungere informazioni che non sono nei dati ricevuti
- Non esporre dati nominativi insieme a dati retributivi se non presenti entrambi nel risultato"""


def format_response(user_question: str, resolved_month: str, query_result: list[dict]) -> str:
    """
    Genera una risposta in italiano dal risultato della query BigQuery.

    Args:
        user_question: domanda originale dell'utente
        resolved_month: mese usato nel formato 'YYYY-MM-01' (es. '2026-02-01')
        query_result: lista di dict restituita da BigQuery

    Returns:
        Risposta in italiano pronta per essere inviata via Telegram

    Raises:
        RuntimeError: se Gemini non risponde
    """
    if not query_result:
        return f"Nessun dato trovato per il periodo richiesto (riferimento: {_format_month(resolved_month)})."

    result_text = str(query_result)

    prompt = (
        f"{FORMATTER_SYSTEM}\n\n"
        f"DOMANDA UTENTE: {user_question}\n"
        f"MESE/PERIODO DI RIFERIMENTO: {_format_month(resolved_month)}\n"
        f"RISULTATO QUERY: {result_text}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 512,
        },
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }

    try:
        response = requests.post(GEMINI_API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        answer = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        logger.info("Formatter OK | month=%s | answer_len=%d", resolved_month, len(answer))
        return answer

    except requests.RequestException as e:
        logger.error("Gemini API error in formatter: %s", str(e))
        raise RuntimeError(f"Errore nella formattazione della risposta: {type(e).__name__}") from e


def _format_month(month_str: str) -> str:
    """Converte '2026-02-01' in 'febbraio 2026' per la risposta."""
    months_it = {
        "01": "gennaio", "02": "febbraio", "03": "marzo",
        "04": "aprile", "05": "maggio", "06": "giugno",
        "07": "luglio", "08": "agosto", "09": "settembre",
        "10": "ottobre", "11": "novembre", "12": "dicembre",
    }
    try:
        year, month, _ = month_str.split("-")
        return f"{months_it.get(month, month)} {year}"
    except Exception:
        return month_str
