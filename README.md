# HR Payroll Bot - HR Director Dashboard

Questo progetto è un chatbot Telegram basato su AI (Gemini 2.5 Flash) che permette di interrogare i dati HR archiviati su BigQuery tramite linguaggio naturale.

## Architettura
- **Frontend**: Telegram Bot API
- **Compute**: Google Cloud Functions (Gen2, Python 3.12)
- **AI**: Gemini 2.5 Flash via Vertex AI / Generative AI SDK
- **Database**: Google BigQuery
- **Security**: Google Secret Manager per credenziali (API Keys, Bot Token)
- **CI/CD**: GitHub Actions

## Prerequisiti
1. Progetto Google Cloud attivo.
2. Bot Telegram creato tramite [@BotFather](https://t.me/BotFather).
3. API Gemini abilitata (Vertex AI o Generative AI).

## Setup Ambiente Locale
1. Clona il repository.
2. Crea un ambiente virtuale: `python -m venv venv`.
3. Attivalo e installa le dipendenze: `pip install -r requirements.txt`.
4. Configura le variabili d'ambiente nel file `.env` (basati su `.env.template`).

## Deployment
Il deploy è automatizzato tramite GitHub Actions dopo ogni push sul branch `main`.

### Variabili GitHub Secrets
- `GCP_SA_KEY`: Chiave JSON del Service Account con i permessi necessari.

## Verifica
Esegui lo script di validazione per controllare la connettività:
```bash
python scripts/validate_env.py
```

## Collaborazione
Segui le direttive in `AGENTS.md` per lo sviluppo.
