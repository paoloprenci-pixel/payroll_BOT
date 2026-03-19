# PROJECT.md — Descrizione Progetto
# ✏️ FILE SPECIFICO DI PROGETTO — DA AGGIORNARE SE CAMBIANO I REQUISITI

---

## IDENTIFICAZIONE

| Campo | Valore |
|---|---|
| **PROJECT_NAME** | HR Director Bot |
| **PROJECT_TYPE** | chatbot |
| **LINGUA OUTPUT** | it |
| **VERSIONE** | 0.1.0 |

---

## OBIETTIVO

**Problema da risolvere:**
> Il Direttore HR di un'azienda necessita di accesso rapido e immediato alle informazioni anagrafiche e retributive dei propri dipendenti, anche da smartphone, senza dover aprire gestionali o richiedere report all'ufficio paghe. Il sistema deve permettere domande in linguaggio naturale tramite Telegram e restituire risposte precise basate sui dati reali del database aziendale, storicizzati mese per mese.

**Comportamento atteso — gestione del periodo temporale:**
- **Nessun periodo specificato** (es. "qual è la RAL più alta a Milano?"): il chatbot risponde automaticamente usando l'**ultimo mese disponibile = febbraio 2026** (`2026-02-01`), senza chiedere chiarimenti. La risposta deve esplicitare sempre il mese usato (es. "A febbraio 2026, la RAL più alta a Milano è...").
- **Periodo specifico indicato** (singolo mese o intervallo di mesi): il chatbot risponde esattamente sul periodo richiesto, senza sostituirlo con il default.
- **`LAST_AVAILABLE_MONTH`** = `2026-02-01` — costante definita nel codice del webhook e iniettata nel prompt NL2SQL. Se il dataset viene aggiornato in futuro, aggiornare solo questa costante.

**Utenti target:**
- Ruolo: Direttore del Personale / HR Director (utente singolo, accesso esclusivo)
- Competenza tecnica: bassa — interagisce solo in linguaggio naturale via chat
- Dispositivi principali: mobile (smartphone), compatibile anche desktop

---

## STACK TECNOLOGICO

| Layer | Scelta | Motivazione |
|---|---|---|
| **Interfaccia utente** | Telegram Bot API | Gratuita, mobile-first, zero app da installare |
| **Backend / Webhook** | Google Cloud Functions (Python 3.12) | Free tier: 2M invocazioni/mese — serverless, no gestione server |
| **NL2SQL + risposta LLM** | Gemini 2.0 Flash via Google AI Studio API | Free tier: 1.500 req/giorno — sufficiente per uso monoutente |
| **Database** | BigQuery | Free tier: 10 GB storage + 1 TB query/mese — adeguato per dati mock |
| **CI/CD** | GitHub + GitHub Actions | Gratuito, deploy automatico su Cloud Functions al push su `main` |
| **Secrets** | Google Secret Manager | Gratuito fino a 6 secret — copre `payroll-telegram-bot-token` + `payroll-gemini-api-key` |
| **Session state** | Stateless (nessuna persistenza) | Sufficiente per MVP monoutente, semplifica il deploy |

> **Supabase:** non utilizzato in questa versione. Potrebbe sostituire BigQuery in futuro se si preferisce PostgreSQL standard con query più familiari.
> **Firebase:** non utilizzato in questa versione. Da valutare solo se si aggiunge gestione dello stato conversazionale multi-turno in versioni successive.
> **Cloud Run vs Cloud Functions:** si usa Cloud Functions per semplicità di deploy. Migrare a Cloud Run se emergono esigenze di middleware più complessi o cold start ridotto.

---

## ARCHITETTURA DEL FLUSSO

```
[Direttore HR su Telegram]
        │
        │  messaggio in linguaggio naturale
        ▼
[Telegram Bot API]
        │
        │  webhook POST
        ▼
[Cloud Function: hr_bot_webhook]
        │
        ├─► STEP 1 — Primo contatto: l'utente ha già superato l'autenticazione email?
        │           NO  → invia "Ciao! Per accedere inserisci la tua email:" → attende
        │           SÌ  → continua
        │
        ├─► STEP 1b — Verifica email (solo al primo messaggio della sessione)
        │           Email ricevuta = "paoloprenci@gmail.com" → segna sessione come autenticata → continua
        │           Email diversa → risponde "Utente non autorizzato." → termina, non elaborare oltre
        │
        ├─► STEP 2 — Periodo temporale: la domanda specifica un mese o intervallo?
        │           NO  → usa LAST_AVAILABLE_MONTH = '2026-02-01' come default silenzioso
        │           SÌ  → usa il periodo indicato nella domanda
        │
        ├─► STEP 3 — Prompt NL2SQL: schema tabella + domanda + mese risolto → Gemini 2.0 Flash
        │           Output atteso: query SQL BigQuery valida
        │
        ├─► STEP 4 — Esecuzione SQL su BigQuery
        │           Errore SQL → log + risposta generica di errore all'utente
        │
        ├─► STEP 5 — Formattazione: risultato query → Gemini → risposta in italiano
        │           La risposta include sempre il mese di riferimento usato
        │
        └─► STEP 6 — Risposta inviata tramite Telegram
```

---

## DATABASE — SCHEMA E DATA DICTIONARY

**Dataset BigQuery:** `hr_analytics`
**Tabella:** `dipendenti_storico`
**Granularità:** 1 record per dipendente per mese
**Volume mock:** 50 dipendenti × 14 mesi = 700 record totali
**Periodo mock:** gennaio 2025 – febbraio 2026
**Ultimo mese disponibile (`LAST_AVAILABLE_MONTH`):** `2026-02-01`

---

### ⚠️ ISTRUZIONE CRITICA PER L'LLM (da includere verbatim nel system prompt NL2SQL)

```
Ogni riga della tabella `hr_analytics.dipendenti_storico` rappresenta la
fotografia della situazione contrattuale e anagrafica di UN dipendente in
UN determinato mese. I dati possono variare mese per mese (la RAL può
essere aggiornata, il centro di costo può cambiare, ecc.).

REGOLE OBBLIGATORIE per generare SQL corretto:
1. Filtrare SEMPRE su `mese_riferimento` usando il formato DATE 'YYYY-MM-01'
   (es. dicembre 2025 = '2025-12-01', febbraio 2026 = '2026-02-01').
2. Se la domanda NON specifica alcun periodo, usa automaticamente il mese
   di default: LAST_AVAILABLE_MONTH = '2026-02-01'. Non chiedere chiarimenti.
3. Se la domanda specifica un singolo mese, usa esattamente quel mese.
4. Se la domanda specifica un intervallo (es. "da gennaio a marzo 2025"),
   usa BETWEEN '2025-01-01' AND '2025-03-01' su `mese_riferimento`.
5. La risposta in linguaggio naturale deve SEMPRE indicare il mese o
   periodo a cui si riferisce (es. "A febbraio 2026..." oppure "Nel periodo
   gennaio–marzo 2025...").
6. Per ricerche per nome usare LOWER(nominativo) LIKE '%cognome%nome%'
   per gestire maiuscole/minuscole e ordine variabile.
7. Non restituire mai dati retributivi e nominativo nella stessa query
   se non esplicitamente richiesto.
8. Il nome completo della tabella è sempre: `hr_analytics.dipendenti_storico`
```

---

### Colonne e descrizioni semantiche

| Colonna | Tipo BigQuery | Descrizione semantica per LLM |
|---|---|---|
| `mese_riferimento` | `DATE` | Primo giorno del mese a cui si riferisce il record. Formato: `YYYY-MM-01`. Esempi: `2025-01-01` = gennaio 2025, `2025-12-01` = dicembre 2025. Usare **sempre** questa colonna per filtrare per periodo. |
| `matricola` | `STRING` | Codice identificativo univoco e immutabile del dipendente nel sistema HR. Formato: `MAT-XXXXX` (es. `MAT-00042`). Non cambia nel tempo né al variare del mese. |
| `nominativo` | `STRING` | Nome e cognome completo del dipendente nel formato `COGNOME Nome` (cognome in maiuscolo). Per ricerche parziali usare `LOWER(nominativo) LIKE '%termine%'`. |
| `citta_residenza` | `STRING` | Comune di residenza anagrafica del dipendente nel mese di riferimento. Può variare nel tempo (es. cambio di residenza). Valori mock: `Milano`, `Roma`, `Torino`, `Bologna`, `Napoli`, `Firenze`, `Venezia`, `Verona`. |
| `sede_lavoro` | `STRING` | Nome della sede aziendale fisica presso cui il dipendente presta servizio nel mese di riferimento. Indipendente dalla città di residenza. Valori mock: `Milano`, `Roma`, `Torino`, `Napoli`, `Bologna`. |
| `centro_costo` | `STRING` | Centro di costo organizzativo che identifica il dipartimento di appartenenza. Formato: `CC-XXX - Nome`. Valori mock: `CC-001 - Amministrazione`, `CC-002 - Commerciale`, `CC-003 - IT`, `CC-004 - Operations`, `CC-005 - Marketing`, `CC-006 - HR`, `CC-007 - Direzione`. |
| `eta_anagrafica` | `INTEGER` | Età del dipendente in anni compiuti alla data del mese di riferimento. Può incrementare di 1 nel mese del compleanno. Range mock: 22–65 anni. |
| `ral` | `NUMERIC` | **Retribuzione Annua Lorda** in euro: somma annua di tutti gli elementi retributivi fissi (stipendio base, superminimo, EDR) al lordo di IRPEF e contributi INPS lavoratore, esclusi i contributi previdenziali datoriali. Espressa con 2 decimali. Range mock: €22.000 – €120.000. Per medie usare `AVG(ral)`, per massimi `MAX(ral)`. |
| `retribuzione_netta_mensile` | `NUMERIC` | **Retribuzione netta mensile** in euro: importo effettivamente accreditato al dipendente dopo detrazione di IRPEF, addizionali regionali e comunali, e contributi INPS lavoratore. Espressa con 2 decimali. Range mock: €1.300 – €5.800. Nota: non è la RAL divisa per 13/14: include la mensilizzazione delle mensilità aggiuntive. |

---

### Esempi di query SQL attese (da includere nel prompt NL2SQL)

```sql
-- Retribuzione lorda media nella sede di Milano a dicembre 2025
SELECT ROUND(AVG(ral), 2) AS ral_media_annua_lorda
FROM `hr_analytics.dipendenti_storico`
WHERE sede_lavoro = 'Milano'
  AND mese_riferimento = '2025-12-01';

-- Matricola di un dipendente cercato per nome
SELECT matricola, nominativo
FROM `hr_analytics.dipendenti_storico`
WHERE LOWER(nominativo) LIKE '%pinco%pallino%'
  AND mese_riferimento = (
      SELECT MAX(mese_riferimento) FROM `hr_analytics.dipendenti_storico`
  )
LIMIT 1;

-- Centro di costo di un dipendente in un mese specifico
SELECT centro_costo, nominativo
FROM `hr_analytics.dipendenti_storico`
WHERE LOWER(nominativo) LIKE '%tizio%caio%'
  AND mese_riferimento = '2025-11-01';

-- Dipendente con RAL più alta a Milano (mese specificato dopo chiarimento)
SELECT nominativo, ral
FROM `hr_analytics.dipendenti_storico`
WHERE sede_lavoro = 'Milano'
  AND mese_riferimento = '2025-10-01'
ORDER BY ral DESC
LIMIT 1;

-- Numero dipendenti per sede in un mese
SELECT sede_lavoro, COUNT(*) AS num_dipendenti
FROM `hr_analytics.dipendenti_storico`
WHERE mese_riferimento = '2025-12-01'
GROUP BY sede_lavoro
ORDER BY num_dipendenti DESC;
```

---

## DATI E INTEGRAZIONI

| Fonte | Tipo | Note |
|---|---|---|
| BigQuery `hr_analytics.dipendenti_storico` | Database principale HR | Generato da `execution/seed_mock_data.py` |
| Telegram Bot API | Interfaccia conversazionale | `payroll-telegram-bot-token` via Secret Manager |
| Google AI Studio (Gemini 2.0 Flash) | NL2SQL + formattazione risposta | `payroll-gemini-api-key` via Secret Manager |

**API esterne:**
- Telegram Bot API: `https://api.telegram.org/bot{TOKEN}/sendMessage` — auth via token nel path URL
- Gemini API: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent` — auth via `x-goog-api-key` header

---

## KPI DI SUCCESSO

- [ ] Il chatbot risponde a domande con periodo specificato in **< 5 secondi** end-to-end (webhook → BigQuery → Telegram)
- [ ] Il chatbot usa `LAST_AVAILABLE_MONTH = 2026-02-01` come default nel **100% dei casi** in cui la domanda non specifica un periodo (verificabile su test set di 20 domande senza periodo)
- [ ] Il chatbot risponde sul periodo corretto nel **100% dei casi** in cui la domanda specifica un mese o intervallo
- [ ] La risposta include sempre il mese o periodo di riferimento usato, in linguaggio naturale
- [ ] SQL generato da Gemini eseguito senza errori su BigQuery in **≥ 90%** delle domande del test set (30 domande di test)
- [ ] **Zero** risposte a utenti che forniscono un'email diversa da `paoloprenci@gmail.com`
- [ ] **Zero** dati retributivi con nominativo esposti nei log di Cloud Functions (verifica manuale su Cloud Logging)
- [ ] Database mock completo: **700 record** (50 dipendenti × 14 mesi), zero valori null nelle colonne obbligatorie

---

## VINCOLI

**Tecnici:**
- Tutto il backend su GCP: nessun servizio AWS o Azure
- **Free tier obbligatorio** su tutti i servizi: costo mensile ricorrente = €0 per l'MVP
- Region GCP: `europe-west1` (Belgio) per conformità GDPR
- Il bot autentica ogni nuova sessione tramite email: solo `paoloprenci@gmail.com` è autorizzata — qualsiasi altra email riceve "Utente non autorizzato." e la sessione non procede

**Sicurezza / GDPR:**
- I dati retributivi sono dati personali sensibili (GDPR Art. 9): mai includere nominativo + importi retributivi in chiaro nei log applicativi
- Il payload inviato a Gemini contiene solo: schema tabella, query SQL, risultato aggregato — mai dump di righe con dati nominativi completi
- Nessuna credenziale hardcodata nel codice sorgente o nel repository GitHub

**Di progetto:**
- MVP monoutente: un solo `chat_id` Telegram autorizzato
- Interfaccia esclusivamente Telegram: nessuna UI web o API REST esposta
- Database è mock: nessuna connessione a sistemi HR reali in questa versione

---

## FUORI SCOPE (versione corrente)

- Integrazione con sistemi HR reali (Zucchetti, SAP HR, Personio, ecc.)
- Multi-utente con gestione dei ruoli e viste parziali per HRBP
- Dashboard web o app mobile nativa
- Notifiche proattive (es. alert su variazioni retributive anomale mese su mese)
- Storico conversazioni persistente e ricercabile
- Export dei risultati in PDF o Excel direttamente da Telegram
- Gestione di dati non strutturati (contratti, lettere di assunzione, note disciplinari)
- Calcolo di elaborazioni complesse lato LLM (proiezioni, simulazioni retributive)

---

## NOTE AGGIUNTIVE PER ANTIGRAVITY

**Sul prompt NL2SQL:**
Il system prompt da passare a Gemini per generare SQL deve includere obbligatoriamente: (1) l'intero data dictionary con le descrizioni semantiche, (2) il nome completo della tabella `hr_analytics.dipendenti_storico`, (3) la regola sul formato `YYYY-MM-01` per `mese_riferimento`, (4) il valore di `LAST_AVAILABLE_MONTH = '2026-02-01'` da usare come default quando nessun periodo è specificato, (5) gli esempi di query SQL di riferimento incluse le query con BETWEEN per intervalli. Questo è il principale strumento di riduzione delle allucinazioni SQL.

**Sul default temporale `LAST_AVAILABLE_MONTH`:**
Definire questa costante in un unico punto del codice (es. `config.py` o variabile d'ambiente `LAST_AVAILABLE_MONTH=2026-02-01`). Il webhook la inietta nel prompt NL2SQL ad ogni chiamata. Quando il dataset viene esteso, basta aggiornare questa costante senza toccare il resto del codice.

**Sul meccanismo di autenticazione email:**
Poiché Telegram Bot API è stateless, lo stato "autenticato" della sessione va gestito in memoria (dizionario Python in-process `authenticated_sessions: dict[int, bool]` keyed sul `chat_id` numerico di Telegram). Al primo messaggio di ogni sessione: il bot chiede la email, verifica contro la whitelist `AUTHORIZED_EMAILS = {"paoloprenci@gmail.com"}` definita in `config.py`, e salva il flag in memoria. Implementare in `execution/auth_handler.py`. Nota: lo stato si resetta al riavvio della Cloud Function (comportamento accettabile per MVP monoutente).

**Sul seed del database mock:**
Lo script `execution/seed_mock_data.py` deve generare dati verosimili su 14 mesi (gennaio 2025 – febbraio 2026): nomi e cognomi italiani reali, città italiane reali, RAL coerenti con il centro di costo (CC-003 IT e CC-007 Direzione hanno RAL più alte, CC-001 Amministrazione più basse), variazioni mensili plausibili (±0–2% mese su mese per simulare aumenti contrattuali e una tantum). Almeno 3 dipendenti per sede e 2 per centro di costo per rendere significative le query aggregate.

**Repository GitHub:**
Branch `main` per produzione (trigger deploy automatico), branch `dev` per sviluppo. Il file `.env` e `credentials.json` devono essere in `.gitignore` dal primo commit.

---

## LEZIONI APPRESE (da ERRORI_REGIONALI_VERTEX_AI.md — 2026-03-19)

> Queste lezioni derivano da errori reali incontrati su questo stesso progetto GCP (`gen-lang-client-0296046668`) in un progetto precedente. Sono già incorporate nelle scelte architetturali di questo progetto.

**L1 — Secret Manager su Windows: CRLF nei token (ERRORE 5)**
Su Windows, `echo "token" | gcloud secrets versions add ...` aggiunge `\r\n` in coda, corrompendo il valore. **Fix obbligatorio**: scrivere sempre il secret su file ASCII puro, poi passare il file a gcloud:
```powershell
[System.IO.File]::WriteAllText("C:\temp\secret.txt", "valore_esatto", [System.Text.Encoding]::ASCII)
gcloud secrets versions add nome-secret --data-file="C:\temp\secret.txt"
```
Nel codice Python, aggiungere sempre `.strip()` al caricamento di ogni secret critico in `config.py`.

**L2 — `--update-env-vars` cancella i secrets montati (ERRORE 7)**
Ogni comando `gcloud functions deploy` o `gcloud run services update` deve sempre ri-specificare esplicitamente `--set-secrets`. Non farlo cancella silenziosamente i secrets della revisione precedente.

**L3 — Cloud Build substitutions annidate non funzionano (ERRORE 6)**
Cloud Build non espande `$PROJECT_ID` usato come valore di una substitution `_IMAGE_URI`. Usare `$PROJECT_ID` e le altre variabili di sistema **direttamente** nei comandi, senza substitution intermedie.

**L4 — Model ID Gemini: usare sempre la stringa verificata (ERRORE 3)**
Model ID da usare: `gemini-2.0-flash`. Non inventare versioni (es. `gemini-3.0-flash` non esiste). In `config.py`: `GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")`.
