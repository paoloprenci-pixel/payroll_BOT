"""
auth_handler.py — Gestione autenticazione email per sessione.

Meccanismo: dizionario in-memory keyed su chat_id (int).
Lo stato si azzera al riavvio della Cloud Function (accettabile per MVP).
"""
from config import AUTHORIZED_EMAILS

# Stato autenticazione in memoria: {chat_id: True}
authenticated_sessions: dict[int, bool] = {}


def is_authenticated(chat_id: int) -> bool:
    """Restituisce True se il chat_id ha già superato l'autenticazione."""
    return authenticated_sessions.get(chat_id, False)


def try_authenticate(chat_id: int, email_input: str) -> bool:
    """
    Verifica l'email fornita dall'utente.
    Se autorizzata, salva la sessione e restituisce True.
    Altrimenti restituisce False.
    """
    email_normalized = email_input.strip().lower()
    if email_normalized in AUTHORIZED_EMAILS:
        authenticated_sessions[chat_id] = True
        return True
    return False


def reset_session(chat_id: int) -> None:
    """Rimuove lo stato autenticato per un chat_id (utile per test)."""
    authenticated_sessions.pop(chat_id, None)
