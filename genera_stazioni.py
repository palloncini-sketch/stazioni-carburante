#!/usr/bin/env python3
"""Legge i due CSV del MIMIT e crea stazioni.json con i soli impianti IP."""
import csv
import json
import re
import sys
from datetime import date

FILE_ANAGRAFICA = "anagrafica_impianti_attivi.csv"
FILE_PREZZI = "prezzo_alle_8.csv"
FILE_OUT = "stazioni.json"

# Nome del carburante nel CSV (minuscolo) -> chiave usata dalla pagina
CARBURANTI = {"benzina": "benzina", "gasolio": "gasolio", "gpl": "gpl", "metano": "metano"}


def leggi_righe(percorso):
    """Restituisce (prima_riga, lista_di_dizionari). Gestisce BOM e codifiche diverse."""
    try:
        with open(percorso, encoding="utf-8-sig") as f:
            testo = f.read()
    except UnicodeDecodeError:
        with open(percorso, encoding="latin-1") as f:
            testo = f.read()
    righe = testo.splitlines()
    prima = righe[0] if righe else ""
    # la prima riga è "Estrazione del ...", la seconda è l'intestazione
    reader = csv.reader(righe[1:], delimiter=";", quoting=csv.QUOTE_NONE)
    intestazione = [h.strip().lower() for h in next(reader)]
    dati = []
    for r in reader:
        if len(r) < len(intestazione):
            continue
        dati.append({intestazione[i]: r[i].strip() for i in range(len(intestazione))})
    return prima, dati


def numero(testo):
    try:
        return float(testo.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def data_estrazione(riga):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", riga)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", riga)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return date.today().isoformat()


def main():
    _, anagrafica = leggi_righe(FILE_ANAGRAFICA)
    riga_prezzi, prezzi_righe = leggi_righe(FILE_PREZZI)

    # 1) stazioni IP con coordinate valide (Italia)
    stazioni = {}
    for a in anagrafica:
        if a.get("bandiera", "").strip().lower() != "ip":
            continue
        lat, lon = numero(a.get("latitudine")), numero(a.get("longitudine"))
        if lat is None or lon is None or not (35 <= lat <= 48 and 6 <= lon <= 19):
            continue
        stazioni[a["idimpianto"]] = {
            "id": a["idimpianto"],
            "n": a.get("nome impianto", ""),
            "a": a.get("indirizzo", ""),
            "c": a.get("comune", ""),
            "p": a.get("provincia", ""),
            "la": round(lat, 6),
            "lo": round(lon, 6),
            "pr": {},
        }

    # 2) prezzi: per ogni carburante [self, servito]
    for p in prezzi_righe:
        st = stazioni.get(p.get("idimpianto"))
        if st is None:
            continue
        chiave = CARBURANTI.get(p.get("desccarburante", "").strip().lower())
        prezzo = numero(p.get("prezzo"))
        if chiave is None or prezzo is None or not (0.3 < prezzo < 5):
            continue
        posizione = 0 if p.get("isself", "").strip() == "1" else 1
        coppia = st["pr"].setdefault(chiave, [None, None])
        if coppia[posizione] is None or prezzo < coppia[posizione]:
            coppia[posizione] = prezzo

    # 3) tieni solo le stazioni che hanno almeno un prezzo
    elenco = [s for s in stazioni.values() if s["pr"]]

    with open(FILE_OUT, "w", encoding="utf-8") as f:
        json.dump({"aggiornato": data_estrazione(riga_prezzi), "stazioni": elenco},
                  f, ensure_ascii=False, separators=(",", ":"))
    print(f"Stazioni IP trovate: {len(stazioni)} - con prezzi: {len(elenco)}")
    if not elenco:
        sys.exit("ERRORE: nessuna stazione IP trovata, controlla i file CSV.")


if __name__ == "__main__":
    main()
