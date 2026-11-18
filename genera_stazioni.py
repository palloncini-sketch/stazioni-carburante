#!/usr/bin/env python3
"""Legge i due CSV del MIMIT e crea stazioni.json con i soli impianti IP."""
import csv
import json
import re
import sys
from collections import Counter
from datetime import date

FILE_ANAGRAFICA = "anagrafica_impianti_attivi.csv"
FILE_PREZZI = "prezzo_alle_8.csv"
FILE_OUT = "stazioni.json"

# Nome del carburante nel CSV (minuscolo) -> chiave usata dalla pagina
CARBURANTI = {"benzina": "benzina", "gasolio": "gasolio", "gpl": "gpl", "metano": "metano"}


def e_ip(bandiera):
    """True per 'Ip', 'IP', 'Api-Ip', 'Italiana Petroli'... ma non per 'Api' o 'Tamoil'."""
    b = bandiera.strip().lower()
    return bool(re.search(r"(^|[^a-z])ip([^a-z]|$)", b)) or "italiana petroli" in b


def leggi_righe(percorso):
    """Restituisce (prima_riga, intestazione, lista_di_dizionari)."""
    try:
        with open(percorso, encoding="utf-8-sig") as f:
            testo = f.read()
    except UnicodeDecodeError:
        with open(percorso, encoding="latin-1") as f:
            testo = f.read()
    righe = testo.splitlines()
    print(f"\n== {percorso}: {len(righe)} righe")
    for r in righe[:3]:
        print("   ", r[:200])
    prima = righe[0] if righe else ""
    # la prima riga è "Estrazione del ...", la seconda è l'intestazione
    # (se la prima riga è già l'intestazione, la si usa)
    inizio = 1 if prima.lower().startswith("estrazione") else 0
    testa = righe[inizio]
    sep = max(";,|\t", key=testa.count)
    reader = csv.reader(righe[inizio + 1:], delimiter=sep, quoting=csv.QUOTE_NONE)
    intestazione = [h.strip().lower() for h in testa.split(sep)]
    print("    separatore:", repr(sep), "- colonne:", intestazione)
    dati = []
    for r in reader:
        if len(r) < len(intestazione):
            continue
        dati.append({intestazione[i]: r[i].strip() for i in range(len(intestazione))})
    print("    righe lette:", len(dati))
    return prima, intestazione, dati


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
    _, _, anagrafica = leggi_righe(FILE_ANAGRAFICA)
    riga_prezzi, _, prezzi_righe = leggi_righe(FILE_PREZZI)

    bandiere = Counter(a.get("bandiera", "?") for a in anagrafica)
    print("\nBandiere più frequenti:", bandiere.most_common(15))
    print("Bandiere riconosciute come IP:", {b: n for b, n in bandiere.items() if e_ip(b)})

    # 1) stazioni IP con coordinate valide (Italia)
    stazioni = {}
    scartate_coordinate = 0
    for a in anagrafica:
        if not e_ip(a.get("bandiera", "")):
            continue
        lat, lon = numero(a.get("latitudine")), numero(a.get("longitudine"))
        if lat is None or lon is None or not (35 <= lat <= 48 and 6 <= lon <= 19):
            scartate_coordinate += 1
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
    print("Stazioni IP scartate per coordinate non valide:", scartate_coordinate)

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
    print(f"\nStazioni IP trovate: {len(stazioni)} - con prezzi: {len(elenco)}")
    if not elenco:
        sys.exit("ERRORE: nessuna stazione IP trovata, controlla i file CSV.")


if __name__ == "__main__":
    main()
