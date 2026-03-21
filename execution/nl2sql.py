"""
nl2sql.py — Traduzione domanda in linguaggio naturale → SQL BigQuery.

Chiama Gemini 2.0 Flash via REST API con un prompt strutturato che include:
- Data dictionary completo della tabella
- Regole obbligatorie per filtrare su mese_riferimento
- Esempi SQL di riferimento
- Il mese risolto (default o indicato dall'utente)
"""
import re
import time
import requests
import logging
from config import OPENROUTER_API_KEY, OPENROUTER_API_URL, OPENROUTER_MODEL, LAST_AVAILABLE_MONTH, BQ_FULL_TABLE
from execution.errors import OutOfScopeError

logger = logging.getLogger(__name__)

# ── System prompt NL2SQL (da PROJECT.md — incluso verbatim) ──────────────────

SYSTEM_PROMPT = f"""Sei un esperto di SQL BigQuery. Devi tradurre domande in italiano sul personale aziendale in query SQL valide per BigQuery.

Ogni riga della tabella `{BQ_FULL_TABLE}` rappresenta la fotografia della situazione contrattuale e anagrafica di UN dipendente in UN determinato mese. I dati possono variare mese per mese (la RAL può essere aggiornata, il centro di costo può cambiare, ecc.).

REGOLE OBBLIGATORIE per generare SQL corretto:
1. Filtrare SEMPRE su `mese_riferimento` usando il formato DATE 'YYYY-MM-01' (es. dicembre 2025 = '2025-12-01', febbraio 2026 = '2026-02-01').
2. Se la domanda NON specifica alcun periodo, usa automaticamente il mese di default: LAST_AVAILABLE_MONTH = '{LAST_AVAILABLE_MONTH}'. Non chiedere chiarimenti.
3. Se la domanda specifica un singolo mese, usa esattamente quel mese.
4. Se la domanda specifica un intervallo (es. "da gennaio a marzo 2025"), usa BETWEEN '2025-01-01' AND '2025-03-01' su `mese_riferimento`.
5. La risposta in linguaggio naturale deve SEMPRE indicare il mese o periodo a cui si riferisce.
6. Per ricerche per nome usare LOWER(nominativo) LIKE '%cognome%nome%' per gestire maiuscole/minuscole e ordine variabile.
7. Non restituire mai dati retributivi e nominativo nella stessa query se non esplicitamente richiesto.
8. Il nome completo della tabella è sempre: `{BQ_FULL_TABLE}`

SCHEMA DELLA TABELLA `{BQ_FULL_TABLE}`:

| Colonna | Tipo | Descrizione |
|---|---|---|
| mese_riferimento | DATE | Primo giorno del mese. Formato: YYYY-MM-01. SEMPRE usare per filtrare per periodo. |
| matricola | STRING | Codice univoco dipendente. Formato: MAT-XXXXX |
| nominativo | STRING | Nome e cognome. Formato: COGNOME Nome |
| citta_residenza | STRING | Comune di residenza. Valori: Milano, Roma, Torino, Bologna, Napoli, Firenze, Venezia, Verona |
| sede_lavoro | STRING | Sede aziendale. Valori: Milano, Roma, Torino, Napoli, Bologna |
| centro_costo | STRING | Dipartimento. Valori: CC-001 Amministrazione, CC-002 Commerciale, CC-003 IT, CC-004 Operations, CC-005 Marketing, CC-006 HR, CC-007 Direzione |
| eta_anagrafica | INTEGER | Età in anni. Range: 22-65 |
| ral | NUMERIC | Retribuzione Annua Lorda in euro. Range: 22000-120000 |
| retribuzione_netta_mensile | NUMERIC | Netto mensile in euro. Range: 1300-5800 |

ESEMPI DI QUERY SQL:

-- RAL media a Milano in un mese specifico
SELECT ROUND(AVG(ral), 2) AS ral_media
FROM `{BQ_FULL_TABLE}`
WHERE sede_lavoro = 'Milano'
  AND mese_riferimento = '2025-12-01';

-- Ricerca dipendente per nome
SELECT matricola, nominativo
FROM `{BQ_FULL_TABLE}`
WHERE LOWER(nominativo) LIKE '%pinco%pallino%'
  AND mese_riferimento = '{LAST_AVAILABLE_MONTH}'
LIMIT 1;

-- Dipendente con RAL più alta in una sede
SELECT nominativo, ral
FROM `{BQ_FULL_TABLE}`
WHERE sede_lavoro = 'Milano'
  AND mese_riferimento = '2025-10-01'
ORDER BY ral DESC
LIMIT 1;

-- Numero dipendenti per sede
SELECT sede_lavoro, COUNT(*) AS num_dipendenti
FROM `{BQ_FULL_TABLE}`
WHERE mese_riferimento = '2025-12-01'
GROUP BY sede_lavoro
ORDER BY num_dipendenti DESC;

-- Intervallo di mesi
SELECT sede_lavoro, ROUND(AVG(ral), 2) AS ral_media
FROM `{BQ_FULL_TABLE}`
WHERE mese_riferimento BETWEEN '2025-01-01' AND '2025-03-01'
GROUP BY sede_lavoro;

-- Cambiamenti sede per un dipendente nel corso di un anno (query storica corretta)
SELECT mese_riferimento, sede_lavoro
FROM `{BQ_FULL_TABLE}`
WHERE LOWER(nominativo) LIKE '%neri%giorgio%'
  AND mese_riferimento BETWEEN '2025-01-01' AND '2025-12-01'
ORDER BY mese_riferimento;

ISTRUZIONE FINALE:
- Restituisci SOLO la query SQL, senza markdown, senza commenti, senza spiegazioni.
- Solo il testo SQL puro che inizia con SELECT.
- NON usare apostrofi o virgolette singole all'interno dei valori stringa. Usa solo virgolette singole per delimitare le stringhe SQL (es: WHERE nominativo LIKE '%neri%').
- Per query storiche (es. "ha cambiato sede nel 2025?"), usa BETWEEN '2025-01-01' AND '2025-12-01' e ORDER BY mese_riferimento.
- Se la domanda NON è pertinente ai dati HR o non può essere risposta con la tabella fornita, rispondi ESATTAMENTE con `OUT_OF_SCOPE`. Non provare a inventare SQL."""



def generate_sql(user_question: str, resolved_month: str) -> str:
    """
    Genera una query SQL BigQuery dalla domanda dell'utente.

    Args:
        user_question: domanda in italiano dell'utente
        resolved_month: mese risolto in formato 'YYYY-MM-01'

    Returns:
        Stringa SQL pronta per BigQuery

    Raises:
        RuntimeError: se Gemini non risponde o non genera SQL valido
    """
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"MESE RISOLTO DA USARE SE NON SPECIFICATO NELLA DOMANDA: {resolved_month}\n\n"
        f"DOMANDA UTENTE: {user_question}"
    )

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 1024,
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/paoloprenci-pixel/payroll_BOT", # Optional but good practice
        "X-Title": "HR Director Bot",
    }

    max_retries = 5
    retry_delay = 3  # secondi iniziali più alti per i rate limit

    for attempt in range(max_retries):
        try:
            response = requests.post(OPENROUTER_API_URL, json=payload, headers=headers, timeout=30)
            
            # Gestione rate limit: OpenRouter usa 429 per rate limit
            if response.status_code == 429:
                wait = retry_delay * (2 ** attempt)
                logger.warning("OpenRouter rate limit (429) | attempt=%d/%d | wait=%ds | model=%s", attempt + 1, max_retries, wait, OPENROUTER_MODEL)
                time.sleep(wait)
                continue
            
            response.raise_for_status()
            data = response.json()
            
            # Parsing risposta formato OpenAI/OpenRouter
            choices = data.get("choices", [])
            if not choices:
                logger.error("OpenRouter: nessuna scelta nella risposta | data=%s", str(data)[:500])
                raise RuntimeError("Il modello non ha restituito scelte.")
            
            sql = choices[0].get("message", {}).get("content", "").strip()
            logger.info("NL2SQL raw output | month=%s | model=%s | raw=%s", resolved_month, OPENROUTER_MODEL, sql[:300])

            # Pulizia: rimuovi eventuali blocchi markdown (```sql ... ```)
            sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
            sql = re.sub(r"\s*```$", "", sql)
            sql = sql.strip()

            if sql.upper() == "OUT_OF_SCOPE":
                logger.info("Question detected as OUT_OF_SCOPE | question=%s", user_question)
                raise OutOfScopeError("La domanda non è pertinente ai dati HR.")

            if not sql.upper().startswith("SELECT"):
                logger.error("LLM NL2SQL non ha restituito un SELECT valido | model=%s | sql=%s", OPENROUTER_MODEL, sql[:200])
                raise RuntimeError("Il modello non ha generato una query SQL valida.")

            logger.info("NL2SQL OK | month=%s | model=%s | sql=%s", resolved_month, OPENROUTER_MODEL, sql[:300])
            return sql

        except requests.HTTPError as e:
            body = response.text if 'response' in locals() else "Unknown"
            logger.error("OpenRouter HTTP Error (attempt %d/%d) | model=%s | error=%s | Body: %s", attempt + 1, max_retries, OPENROUTER_MODEL, str(e), body)
            if attempt == max_retries - 1:
                raise RuntimeError(f"Errore HTTP OpenRouter ({OPENROUTER_MODEL}) dopo {max_retries} tentativi: {str(e)} | Body: {body}") from e
            time.sleep(retry_delay * (2 ** attempt))
        except requests.RequestException as e:
            logger.error("OpenRouter Request Error (attempt %d/%d) | model=%s | error=%s", attempt + 1, max_retries, OPENROUTER_MODEL, str(e))
            if attempt == max_retries - 1:
                raise RuntimeError(f"Errore nella chiamata a OpenRouter ({OPENROUTER_MODEL}) dopo {max_retries} tentativi: {type(e).__name__}") from e
            time.sleep(retry_delay * (2 ** attempt))

    raise RuntimeError(f"Errore nella chiamata a OpenRouter ({OPENROUTER_MODEL}): tentativi esauriti.")


def resolve_month(user_question: str) -> str:
    """
    Determina il mese di riferimento dalla domanda.
    Se non è specificato, restituisce LAST_AVAILABLE_MONTH.

    Questa funzione usa una detection semplice basata su keyword.
    Il raffinamento del periodo avviene nel prompt NL2SQL di Gemini.
    """
    # Se la domanda contiene riferimenti a mesi o anni, lascia che Gemini li risolva
    # e usa il default solo come fallback nel prompt
    return LAST_AVAILABLE_MONTH
