"""
bq_client.py — Esecuzione query SQL su BigQuery.

Riceve una stringa SQL, la esegue, restituisce lista di dict.
In caso di errore: logga e solleva eccezione strutturata (mai dati sensibili nei log).
"""
import logging
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError
from config import GCP_PROJECT_ID

logger = logging.getLogger(__name__)

_client: bigquery.Client | None = None


def _get_client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=GCP_PROJECT_ID)
    return _client


def run_query(sql: str) -> list[dict]:
    """
    Esegue la query SQL su BigQuery.
    Restituisce una lista di dict (una per riga).
    Solleva RuntimeError in caso di errore SQL.
    """
    client = _get_client()
    try:
        query_job = client.query(sql)
        rows = query_job.result()
        return [dict(row) for row in rows]
    except GoogleAPIError as e:
        # Log senza dati nominativi: solo il tipo di errore e la query (non i risultati)
        logger.error("BigQuery error | query_hash=%s | error=%s", hash(sql), str(e))
        raise RuntimeError(f"Errore nell'esecuzione della query: {type(e).__name__}") from e
