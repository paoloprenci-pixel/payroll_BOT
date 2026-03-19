# Sintesi Errori Regionali — Vertex AI / Gemini SDK
> Documento generato il 2026-03-19 per uso da parte di agenti AI futuri.
> Progetto: **CHATBOT HR TELEGRAM** (GCP Project: `gen-lang-client-0296046668`)

---

## Contesto del Progetto

Il chatbot HR usa due sotto-sistemi Vertex AI con **regioni diverse**:

| Sotto-sistema | Libreria SDK | Regione corretta |
|---|---|---|
| Gemini (LLM generation) | `vertexai` (`vertexai.init`) | `us-central1` |
| Embeddings (`text-embedding-004`) | `vertexai` (`vertexai.init`) | `us-central1` |
| Vector Search (ANN index + endpoint) | `google-cloud-aiplatform` (`aiplatform.init`) | `europe-west1` |

> **REGOLA FONDAMENTALE**: Gemini e Embeddings devono girare su `us-central1`.
> Vector Search (infrastruttura index/endpoint) gira su `europe-west1`.
> Queste due configurazioni NON devono mai interferire tra loro.

---

## ERRORE 1 — Gemini 404 in `europe-west1`

### Sintomo
```
google.api_core.exceptions.NotFound: 404 — Publisher Model `gemini-1.5-flash` not found
```
oppure errore generico `generation error` dal bot.

### Causa
`vertexai.init` veniva chiamato con `location="europe-west1"` (la regione del Cloud Run e del Vector Search).
Il modello `gemini-1.5-flash` **non è disponibile** in `europe-west1` — esiste solo in `us-central1`.

### Fix Applicato
1. Aggiunta variabile d'ambiente separata `GEMINI_REGION=us-central1` in `config.py` e in `cloudbuild.yaml`.
2. In `gemini_client.py`: `vertexai.init(project=PROJECT_ID, location=GEMINI_REGION)` usando esplicitamente `GEMINI_REGION`.
3. In `embeddings_client.py`: stessa logica — `vertexai.init(project=PROJECT_ID, location=GEMINI_REGION)` nella funzione `_get_model()`.

```python
# config.py
REGION = os.getenv("REGION", "europe-west1")        # Vector Search, infrastruttura
GEMINI_REGION = os.getenv("GEMINI_REGION", "us-central1")  # Gemini + Embeddings

# gemini_client.py
vertexai.init(project=PROJECT_ID, location=GEMINI_REGION)

# embeddings_client.py — dentro _get_model()
vertexai.init(project=PROJECT_ID, location=GEMINI_REGION)
```

---

## ERRORE 2 — Conflitto Globale tra `vertexai.init` e `aiplatform.init`

### Sintomo
```
google.api_core.exceptions.NotFound: 404 — Index endpoint not found in us-central1
```
oppure Vector Search smette di rispondere dopo che Gemini è stato chiamato correttamente.

### Causa Profonda
Il Vertex AI SDK usa uno **stato globale singleton** per `project` e `location`.
Entrambi `vertexai.init` e `aiplatform.init` modificano lo stesso stato globale.

**Sequenza problematica:**
1. `aiplatform.init(location="europe-west1")` → Vector Search funziona ✅
2. `vertexai.init(location="us-central1")` → **sovrascrive** il globale ⚠️
3. Chiamata successiva a Vector Search → cerca l'index in `us-central1` → **404** ❌

Questo avveniva perché `gemini_client.py` e `vector_search_client.py` / `embeddings_client.py`
usavano la cache lazy (variabili `_model`, `_index` a livello di modulo): la prima chiamata
inizializzava il client, ma le chiamate successive potevano trovare il globale SDK già
modificato da un'altra inizializzazione.

### Fix Applicato
Chiamare **esplicitamente** `aiplatform.init` o `vertexai.init` con la regione corretta
**prima di ogni operazione sensibile**, non solo alla prima inizializzazione:

```python
# vector_search_client.py — prima di ogni operazione
from google.cloud import aiplatform
aiplatform.init(project=PROJECT_ID, location=REGION)  # forza europe-west1

# embeddings_client.py — dentro _get_model()
import vertexai
vertexai.init(project=PROJECT_ID, location=GEMINI_REGION)  # forza us-central1

# gemini_client.py — dentro _get_model() o generate()
import vertexai
vertexai.init(project=PROJECT_ID, location=GEMINI_REGION)  # forza us-central1
```

> **LEZIONE**: Non fidarsi mai della cache lazy del SDK Vertex AI in ambienti
> multi-regione. Richiamare `vertexai.init` / `aiplatform.init` con i parametri
> espliciti prima di ogni blocco di operazioni critiche.

---

## ERRORE 3 — Model ID non valido (`gemini-3.0-flash`)

### Sintomo
```
google.api_core.exceptions.NotFound: 404 — Model gemini-3.0-flash not found
```

### Causa
Il model ID `gemini-3.0-flash` non esiste. Era un errore di battitura/confusione versione.

### Fix Applicato
Usare sempre il model ID verificato: **`gemini-1.5-flash`**

```python
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
```

Verificare i model ID disponibili qui:
https://cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions

---

## ERRORE 4 — `DEPLOYED_INDEX_ID` con formato sbagliato (underscore vs dash)

### Sintomo
```
google.api_core.exceptions.NotFound: Deployed index hr_docs_deployed not found
```

### Causa
Il deployed index creato sulla console GCP usa i **dash** (`-`) nel nome,
ma il codice usava underscore (`_`).

### Fix Applicato
Correggere la variabile d'ambiente per matchare esattamente il nome reale:

```bash
# SBAGLIATO
DEPLOYED_INDEX_ID=hr_docs_deployed

# CORRETTO
DEPLOYED_INDEX_ID=hr-docs-deployed
```

> **LEZIONE**: Verificare sempre i nomi esatti delle risorse GCP dalla console
> o con `gcloud ai index-endpoints describe` prima di hardcodarli.

---

## ERRORE 5 — Secret Manager su Windows: CRLF nei token

### Sintomo
Il webhook secret o admin token viene riconosciuto con lunghezza errata
(es. 34 char invece di 32, o 133 byte invece di 32).

### Causa
Su Windows, `echo "mytoken" | gcloud secrets versions add ...` aggiunge `\r\n`
(CRLF) in coda. Anche il piping con PowerShell `[System.Text.Encoding]::UTF8.GetBytes()`
invia un JSON array invece dei byte raw.

### Fix Applicato
Scrivere il secret su file con encoding ASCII puro, poi passare il file a gcloud:

```powershell
[System.IO.File]::WriteAllText("C:\temp\my-secret.txt", "mytoken32charexact", [System.Text.Encoding]::ASCII)
gcloud secrets versions add my-secret-name --data-file="C:\temp\my-secret.txt"
```

Nel codice applicativo, aggiungere `.strip()` al caricamento delle variabili critiche:

```python
# config.py
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()
```

---

## ERRORE 6 — `$PROJECT_ID` non espanso nelle substitutions di Cloud Build

### Sintomo
Il `cloudbuild.yaml` fallisce con variabile non risolta o immagine Docker con nome letterale `$PROJECT_ID`.

### Causa
Cloud Build **non fa double-substitution**: se usi `$PROJECT_ID` come valore
di una substitution `_IMAGE_URI`, il valore non viene ulteriormente espanso nei comandi.

### Fix Applicato
Eliminare le substitutions intermedie. Usare `$PROJECT_ID` e le altre variabili
**direttamente** nei comandi `docker build`, `docker push`, `gcloud run deploy`:

```yaml
# SBAGLIATO
substitutions:
  _IMAGE_URI: "gcr.io/$PROJECT_ID/hr-assistant"  # non funziona

# CORRETTO — usare direttamente nei comandi:
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/hr-assistant:$_TAG', '.']
```

---

## ERRORE 7 — `gcloud run services update --update-env-vars` cancella i secrets montati

### Sintomo
Dopo un `gcloud run services update --update-env-vars KEY=VAL`, il servizio
non trova più le variabili iniettate da Secret Manager (es. `TELEGRAM_BOT_TOKEN`).

### Causa
`--update-env-vars` **non preserva** i secrets montati con `--set-secrets` della
revisione precedente. I secrets devono essere ri-specificati ad ogni update.

### Fix Applicato
Ogni comando `gcloud run services update` deve includere esplicitamente `--set-secrets`:

```bash
gcloud run services update hr-assistant \
  --region=europe-west1 \
  --update-env-vars="KEY=VAL" \
  --set-secrets="TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,ADMIN_TOKEN=admin-token:latest,..."
```

---

## Riepilogo Variabili d'Ambiente Critiche

```bash
# Regioni
REGION=europe-west1           # Cloud Run, Vector Search, infrastruttura GCP
GEMINI_REGION=us-central1     # Gemini LLM + Embeddings (OBBLIGATORIO)

# Modelli
GEMINI_MODEL=gemini-1.5-flash
EMBEDDING_MODEL=text-embedding-004

# Vector Search — verificare nomi esatti dalla console GCP
VERTEX_AI_INDEX_ID=<id numerico dell'index>
VERTEX_AI_ENDPOINT_ID=<id numerico dell'endpoint>
DEPLOYED_INDEX_ID=hr-docs-deployed   # attenzione: dash, non underscore
```

---

## Pattern Consigliato per i Client Vertex AI

Questo è il pattern **sicuro** per evitare conflitti di stato globale SDK:

```python
# embeddings_client.py
import vertexai
from google.cloud.aiplatform.gapic import PredictionServiceClient
from config import PROJECT_ID, GEMINI_REGION

def get_embedding(text: str) -> list[float]:
    # Forza sempre la regione corretta prima dell'operazione
    vertexai.init(project=PROJECT_ID, location=GEMINI_REGION)
    model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    return model.get_embeddings([text])[0].values

# vector_search_client.py
from google.cloud import aiplatform
from config import PROJECT_ID, REGION

def query_index(embedding: list[float], top_k: int = 5):
    # Forza sempre europe-west1 per Vector Search
    aiplatform.init(project=PROJECT_ID, location=REGION)
    index_endpoint = aiplatform.MatchingEngineIndexEndpoint(ENDPOINT_ID)
    return index_endpoint.find_neighbors(...)
```
