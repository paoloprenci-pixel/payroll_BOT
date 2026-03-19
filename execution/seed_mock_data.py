"""
seed_mock_data.py — Generazione e caricamento dati mock su BigQuery.

Genera 50 dipendenti × 14 mesi (gen 2025 – feb 2026) = 700 record.
Caratteristiche dei dati mock:
- Nomi e cognomi italiani realistici
- Città di residenza e sedi di lavoro italiane
- RAL coerente con il centro di costo (IT e Direzione più alte, Amministrazione più basse)
- Variazioni mensili plausibili (±0–2% mese su mese)
- Zero valori null nelle colonne obbligatorie
- Almeno 3 dipendenti per sede, 2 per centro di costo

USO: python execution/seed_mock_data.py
PREREQUISITO: GCP_PROJECT_ID configurato, BigQuery API abilitata, credenziali attive.
"""
import random
from datetime import date
from dateutil.relativedelta import relativedelta
from google.cloud import bigquery
from config import GCP_PROJECT_ID, BQ_DATASET, BQ_TABLE, BQ_FULL_TABLE

random.seed(42)  # Riproducibilità

# ── Dati anagrafici mock ──────────────────────────────────────────────────────
COGNOMI = [
    "Rossi", "Ferrari", "Esposito", "Bianchi", "Romano", "Colombo", "Ricci",
    "Marino", "Greco", "Bruno", "Gallo", "Conti", "De Luca", "Mancini", "Costa",
    "Giordano", "Rizzo", "Lombardi", "Moretti", "Barbieri", "Fontana", "Santoro",
    "Mariani", "Rinaldi", "Caruso", "Ferrara", "Gatti", "Pellegrini", "Palumbo",
    "Sanna", "Fabbri", "Coppola", "Villa", "Cattaneo", "Longo", "Leone", "Gentile",
    "Martinelli", "Vitale", "Conte", "Neri", "Valente", "Ferretti", "Testa", "Fiore",
    "Basile", "Negri", "Bianco", "Amato", "Silvestri",
]
NOMI = [
    "Marco", "Luca", "Giulia", "Sara", "Andrea", "Maria", "Matteo", "Anna",
    "Davide", "Laura", "Simone", "Elena", "Alessandro", "Francesca", "Roberto",
    "Chiara", "Stefano", "Valentina", "Fabio", "Paola", "Daniele", "Monica",
    "Michele", "Federica", "Giorgio", "Silvia", "Lorenzo", "Barbara", "Nicola",
    "Roberta", "Emanuele", "Serena", "Riccardo", "Claudia", "Antonio", "Beatrice",
    "Massimo", "Irene", "Paolo", "Diana", "Francesco", "Elisa", "Alberto", "Martina",
    "Cristiano", "Alessia", "Enrico", "Giovanna", "Vincenzo", "Lucia",
]
CITTA_RESIDENZA = [
    "Milano", "Roma", "Torino", "Bologna", "Napoli",
    "Firenze", "Venezia", "Verona",
]
SEDI_LAVORO = ["Milano", "Roma", "Torino", "Napoli", "Bologna"]
CENTRI_COSTO = [
    "CC-001 - Amministrazione",
    "CC-002 - Commerciale",
    "CC-003 - IT",
    "CC-004 - Operations",
    "CC-005 - Marketing",
    "CC-006 - HR",
    "CC-007 - Direzione",
]

# RAL base per centro di costo (media indicativa)
RAL_BASE = {
    "CC-001 - Amministrazione": 28000,
    "CC-002 - Commerciale":     38000,
    "CC-003 - IT":              55000,
    "CC-004 - Operations":      32000,
    "CC-005 - Marketing":       40000,
    "CC-006 - HR":              35000,
    "CC-007 - Direzione":       80000,
}
RAL_SPREAD = 0.25  # ±25% attorno alla media del CC


def _generate_dipendenti(n: int = 50) -> list[dict]:
    """Genera n dipendenti con attributi stabili (non variano mese per mese)."""
    dipendenti = []
    used_cognomi = random.sample(COGNOMI, n)
    used_nomi = random.sample(NOMI, n)

    # Garantiamo almeno 3 dipendenti per sede e 2 per CC
    sedi_garantite = SEDI_LAVORO * 3        # 15 dipendenti
    cc_garantiti = CENTRI_COSTO * 2         # 14 dipendenti
    random.shuffle(sedi_garantite)
    random.shuffle(cc_garantiti)

    for i in range(n):
        matricola = f"MAT-{i + 1:05d}"
        cognome = used_cognomi[i]
        nome = used_nomi[i]
        nominativo = f"{cognome.upper()} {nome}"
        eta_base = random.randint(22, 65)
        citta = random.choice(CITTA_RESIDENZA)
        sede = sedi_garantite[i] if i < len(sedi_garantite) else random.choice(SEDI_LAVORO)
        cc = cc_garantiti[i] if i < len(cc_garantiti) else random.choice(CENTRI_COSTO)
        ral_base = RAL_BASE[cc] * random.uniform(1 - RAL_SPREAD, 1 + RAL_SPREAD)
        ral_base = round(ral_base / 100) * 100  # Arrotonda a centinaia

        dipendenti.append({
            "matricola": matricola,
            "nominativo": nominativo,
            "citta_residenza": citta,
            "sede_lavoro": sede,
            "centro_costo": cc,
            "eta_base": eta_base,
            "ral_iniziale": ral_base,
        })
    return dipendenti


def _generate_records(dipendenti: list[dict]) -> list[dict]:
    """Genera 700 record (50 dipendenti × 14 mesi)."""
    records = []
    start_month = date(2025, 1, 1)

    for d in dipendenti:
        ral_corrente = d["ral_iniziale"]
        compleanno_mese = random.randint(1, 12)

        for m in range(14):
            mese = start_month + relativedelta(months=m)

            # Variazione RAL mensile: ±0–2% (simula aumenti contrattuali)
            variazione = random.uniform(-0.005, 0.02)
            ral_corrente = round(ral_corrente * (1 + variazione), 2)
            ral_corrente = max(22000.0, min(120000.0, ral_corrente))

            # Netto mensile: approssimazione realistica (aliquota effettiva ~30-40%)
            aliquota = random.uniform(0.28, 0.40)
            netto_mensile = round(ral_corrente * (1 - aliquota) / 12, 2)
            netto_mensile = max(1300.0, min(5800.0, netto_mensile))

            # Età: incrementa nel mese del compleanno
            eta = d["eta_base"] + (1 if mese.month > compleanno_mese else 0)
            eta = min(eta, 65)

            records.append({
                "mese_riferimento": mese.isoformat(),
                "matricola": d["matricola"],
                "nominativo": d["nominativo"],
                "citta_residenza": d["citta_residenza"],
                "sede_lavoro": d["sede_lavoro"],
                "centro_costo": d["centro_costo"],
                "eta_anagrafica": eta,
                "ral": ral_corrente,
                "retribuzione_netta_mensile": netto_mensile,
            })

    return records


def create_table_if_not_exists(client: bigquery.Client) -> None:
    """Crea il dataset e la tabella BigQuery se non esistono."""
    # Dataset
    dataset_ref = bigquery.Dataset(f"{GCP_PROJECT_ID}.{BQ_DATASET}")
    dataset_ref.location = "EU"
    client.create_dataset(dataset_ref, exists_ok=True)
    print(f"✅ Dataset '{BQ_DATASET}' verificato.")

    # Schema tabella
    schema = [
        bigquery.SchemaField("mese_riferimento", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("matricola", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("nominativo", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("citta_residenza", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("sede_lavoro", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("centro_costo", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("eta_anagrafica", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("ral", "NUMERIC", mode="REQUIRED"),
        bigquery.SchemaField("retribuzione_netta_mensile", "NUMERIC", mode="REQUIRED"),
    ]

    table_ref = client.dataset(BQ_DATASET).table(BQ_TABLE)
    table = bigquery.Table(table_ref, schema=schema)
    table = client.create_table(table, exists_ok=True)
    print(f"✅ Tabella '{BQ_FULL_TABLE}' verificata.")


def seed(truncate: bool = True) -> None:
    """Esegue il seeding completo del database mock."""
    client = bigquery.Client(project=GCP_PROJECT_ID)

    print("🔧 Creazione dataset e tabella...")
    create_table_if_not_exists(client)

    print("🔧 Generazione dati mock (50 dipendenti × 14 mesi)...")
    dipendenti = _generate_dipendenti(50)
    records = _generate_records(dipendenti)
    print(f"   → {len(records)} record generati")

    if truncate:
        table_id = f"{GCP_PROJECT_ID}.{BQ_FULL_TABLE}"
        print(f"🔧 Svuotamento tabella '{BQ_FULL_TABLE}'...")
        client.query(f"TRUNCATE TABLE `{table_id}`").result()
        print("   → Tabella svuotata")

    print("🔧 Caricamento su BigQuery...")
    table_ref = client.dataset(BQ_DATASET).table(BQ_TABLE)
    errors = client.insert_rows_json(table_ref, records)

    if errors:
        print(f"❌ Errori durante il caricamento: {errors}")
    else:
        print(f"✅ {len(records)} record caricati con successo in '{BQ_FULL_TABLE}'")

    # Verifica rapida
    count_query = f"SELECT COUNT(*) as tot FROM `{GCP_PROJECT_ID}.{BQ_FULL_TABLE}`"
    result = list(client.query(count_query).result())
    print(f"✅ Verifica: {result[0]['tot']} record totali nel database")


if __name__ == "__main__":
    seed()
