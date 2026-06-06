#!/usr/bin/env python3
"""
Club-form player disciplinary dataset, 2025-26.

Reads the FBref-style club season CSV, aggregates each player across any
transfer rows, and computes per90 booking-risk rates. Standalone, no network.

If a FIFA confirmed-squad file is present it filters to confirmed WC2026
players, otherwise it keeps everyone and flags that in data_sources.

RULES
- missing values left null, never invented or interpolated
- per90 only computed when minutes > 0
- low_sample flag when total minutes < 450, so noisy rates are visible
- prints total, coverage and nulls-by-column summary

USAGE
    python club_form_discipline.py
"""

import csv
import sys
import unicodedata
from pathlib import Path

# Windows consoles default to cp1252 and choke on accented names. Force a
# tolerant utf-8 stream so the sanity print can never crash the run.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

# ---- paths ----------------------------------------------------------------
DOWNLOADS = Path(r"C:\Users\abamf\Downloads")
SRC_CSV = DOWNLOADS / "players_data-2025_2026.csv"
DATA_DIR = Path(__file__).resolve().parent
RAW_DIR = DATA_DIR / "raw"
OUT_FULL = DATA_DIR / "wc2026_club_form_discipline.csv"
OUT_HIGH = DATA_DIR / "wc2026_club_form_high_risk.csv"

# optional confirmed-squad filter, produced from the FIFA PDF when available
SQUAD_KEYS_FILE = RAW_DIR / "confirmed_squad_keys.csv"  # cols: name,nation

LOW_SAMPLE_MINUTES = 450  # five full matches

# ---- helpers --------------------------------------------------------------

def strip_accents(s):
    if not s:
        return ""
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def norm_name(s):
    return " ".join(strip_accents(s).lower().split())


def nation_code(raw):
    """'dz ALG' -> 'ALG'. Returns '' if absent."""
    if not raw:
        return ""
    parts = raw.split()
    for tok in reversed(parts):
        if tok.isupper() and len(tok) == 3:
            return tok
    return strip_accents(raw).upper().strip()


def num(v):
    if v in (None, "", "NA", "nan"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def per90(count, minutes):
    if count is None or not minutes or minutes <= 0:
        return None
    return round((count / minutes) * 90.0, 4)


# ---- load optional squad filter ------------------------------------------

def load_squad_keys():
    if not SQUAD_KEYS_FILE.exists():
        return None
    keys = set()
    with open(SQUAD_KEYS_FILE, encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        for row in r:
            keys.add((norm_name(row.get("name")), (row.get("nation") or "").upper().strip()))
    print(f"[squad] loaded {len(keys)} confirmed-squad keys")
    return keys or None


# ---- aggregate club rows --------------------------------------------------

def aggregate():
    players = {}
    with open(SRC_CSV, encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        for row in r:
            name = (row.get("Player") or "").strip()
            if not name:
                continue
            nat = nation_code(row.get("Nation"))
            key = (norm_name(name), nat)
            mins = num(row.get("Min")) or 0
            rec = players.get(key)
            if rec is None:
                rec = {
                    "player_name": name,
                    "nation": nat,
                    "rows": [],
                    "min": 0.0, "crdy": 0.0, "crdr": 0.0,
                    "fls": 0.0, "fld": 0.0,
                    "squads": [], "comps": [], "pos": [],
                    "_best_min": -1, "_best_pos": "",
                }
                players[key] = rec
            rec["min"] += mins
            for src, dst in (("CrdY", "crdy"), ("CrdR", "crdr"),
                             ("Fls", "fls"), ("Fld", "fld")):
                v = num(row.get(src))
                if v is not None:
                    rec[dst] += v
            sq = (row.get("Squad") or "").strip()
            cp = (row.get("Comp") or "").strip()
            ps = (row.get("Pos") or "").strip()
            if sq and sq not in rec["squads"]:
                rec["squads"].append(sq)
            if cp and cp not in rec["comps"]:
                rec["comps"].append(cp)
            # primary position taken from the row with most minutes
            if mins > rec["_best_min"]:
                rec["_best_min"] = mins
                rec["_best_pos"] = ps
    return players


# ---- build output rows ----------------------------------------------------

OUTPUT_COLUMNS = [
    "player_name", "nation", "position", "squads", "comps",
    "club_minutes", "club_yellow_cards", "club_red_cards",
    "club_fouls_committed", "club_fouls_drawn",
    "club_yc_per90", "club_fouls_per90", "risk_score",
    "low_sample", "data_sources",
]


def build_rows(players, squad_keys):
    rows = []
    for (nm, nat), rec in players.items():
        if squad_keys is not None:
            if (nm, nat) not in squad_keys and not any(
                    n == nm for (n, _) in squad_keys):
                continue  # not confirmed, drop
        mins = rec["min"]
        yc90 = per90(rec["crdy"], mins)
        fl90 = per90(rec["fls"], mins)
        risk = round((yc90 * 2) + fl90, 4) if (yc90 is not None and fl90 is not None) else None
        sources = ["club"]
        if squad_keys is not None:
            sources.append("fifa_squad")
        rows.append({
            "player_name": rec["player_name"],
            "nation": nat,
            "position": rec["_best_pos"],
            "squads": " | ".join(rec["squads"]),
            "comps": " | ".join(rec["comps"]),
            "club_minutes": int(mins) if mins else 0,
            "club_yellow_cards": int(rec["crdy"]),
            "club_red_cards": int(rec["crdr"]),
            "club_fouls_committed": int(rec["fls"]),
            "club_fouls_drawn": int(rec["fld"]),
            "club_yc_per90": yc90,
            "club_fouls_per90": fl90,
            "risk_score": risk,
            "low_sample": "yes" if mins < LOW_SAMPLE_MINUTES else "no",
            "data_sources": "+".join(sources),
        })
    return rows


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k))
                        for k in OUTPUT_COLUMNS})


def top20pct_per_nation(rows):
    """Top 20% by risk per nation, excluding low-sample and unscored."""
    by_nat = {}
    for r in rows:
        if r["risk_score"] is None or r["low_sample"] == "yes":
            continue
        by_nat.setdefault(r["nation"], []).append(r)
    high = []
    for nat, players in by_nat.items():
        players.sort(key=lambda x: x["risk_score"], reverse=True)
        n = max(1, round(len(players) * 0.2))
        high.extend(players[:n])
    high.sort(key=lambda x: (x["nation"], -x["risk_score"]))
    return high


def summary(rows):
    total = len(rows)
    print("\n==================== SUMMARY ====================")
    print(f"total players: {total}")
    if not total:
        print("no rows produced")
        return
    scored = sum(1 for r in rows if r["risk_score"] is not None)
    low = sum(1 for r in rows if r["low_sample"] == "yes")
    print(f"risk-scored: {scored}/{total} ({100*scored/total:.1f}%)")
    print(f"low_sample (<{LOW_SAMPLE_MINUTES} min): {low}")
    print("nulls by column:")
    for c in OUTPUT_COLUMNS:
        nulls = sum(1 for r in rows if r.get(c) in (None, ""))
        print(f"   {c}: {nulls}")
    print("================================================\n")


def main():
    print(f"reading {SRC_CSV.name}")
    squad_keys = load_squad_keys()
    if squad_keys is None:
        print("[squad] no confirmed-squad file, keeping all players, "
              "filter will apply once the FIFA squad PDF is parsed")
    players = aggregate()
    print(f"aggregated to {len(players)} unique players (transfers merged)")
    rows = build_rows(players, squad_keys)
    rows.sort(key=lambda x: (x["risk_score"] is None, -(x["risk_score"] or 0)))
    write_csv(OUT_FULL, rows)
    high = top20pct_per_nation(rows)
    write_csv(OUT_HIGH, high)
    print(f"wrote {OUT_FULL.name} ({len(rows)} rows)")
    print(f"wrote {OUT_HIGH.name} ({len(high)} rows)")
    summary(rows)
    # show the top 15 by risk as a sanity check
    print("Top 15 by club-form risk (excluding low sample):")
    shown = [r for r in rows if r["low_sample"] == "no"][:15]
    for r in shown:
        print(f"   {r['risk_score']:.2f}  {r['player_name']:<26} "
              f"{r['nation']:<4} yc90={r['club_yc_per90']} "
              f"fls90={r['club_fouls_per90']} min={r['club_minutes']}")


if __name__ == "__main__":
    main()
