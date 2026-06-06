#!/usr/bin/env python3
"""
WC2026 confirmed-squad disciplinary dataset.

Parses the FIFA squad-list PDF (48 teams), aggregates the FBref club season
CSV per player across transfers, then matches confirmed squad players to
their club-form discipline.

Outputs:
  wc2026_squad_master.csv       every confirmed player, identity + club + team
  wc2026_squad_club_form.csv    confirmed players joined to club discipline
  prints a coverage report and nulls-by-column

RULES
- missing values left null, never invented
- per90 only when minutes > 0
- low_sample flag under 450 club minutes
- data_sources flags fifa_squad only vs club+fifa_squad
"""

import csv
import re
import sys
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DOWNLOADS = Path(r"C:\Users\abamf\Downloads")
PDF = DOWNLOADS / "SquadLists-English.pdf"
CLUB_CSV = DOWNLOADS / "players_data-2025_2026.csv"
OUT_DIR = Path(__file__).resolve().parent
OUT_MASTER = OUT_DIR / "wc2026_squad_master.csv"
OUT_JOINED = OUT_DIR / "wc2026_squad_club_form.csv"

POS_CODES = {"GK", "DF", "MF", "FW"}
LOW_SAMPLE_MINUTES = 450

# FIFA code -> any alternative codes seen in FBref nation field, soft aliases
NATION_ALIASES = {
    # most align; add here only where a real mismatch is found
}


# ---- normalisation --------------------------------------------------------

def strip_accents(s):
    if not s:
        return ""
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def norm(s):
    return " ".join(strip_accents(s).lower().replace("-", " ").split())


def nation_code(raw):
    if not raw:
        return ""
    for tok in reversed(raw.split()):
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


def per90(c, m):
    if c is None or not m or m <= 0:
        return None
    return round((c / m) * 90.0, 4)


# ---- parse FIFA squad PDF -------------------------------------------------

def parse_squads():
    doc = fitz.open(PDF)
    players = []
    header_rx = re.compile(r"^(.*?)\s*\(([A-Z]{3})\)\s*$")
    for page in doc:
        lines = [l.rstrip() for l in page.get_text().split("\n")]
        if not lines:
            continue
        m = header_rx.match(lines[0].strip())
        if not m:
            continue
        team_name, code = m.group(1).strip(), m.group(2)
        i = 0
        while i < len(lines):
            if lines[i].strip() in POS_CODES and i + 7 < len(lines):
                pos = lines[i].strip()
                player_name = lines[i + 1].strip()
                first = lines[i + 2].strip()
                last = lines[i + 3].strip()
                shirt = lines[i + 4].strip()
                dob = lines[i + 5].strip()
                club = lines[i + 6].strip()
                height = lines[i + 7].strip()
                # validate: dob should look like a date
                if re.match(r"\d{2}/\d{2}/\d{4}", dob):
                    players.append({
                        "team": team_name, "code": code, "pos": pos,
                        "player_name": player_name, "first": first,
                        "last": last, "shirt": shirt, "dob": dob,
                        "club": club, "height": height,
                    })
                    i += 8
                    continue
            i += 1
    return players


# ---- aggregate club CSV ---------------------------------------------------

def despace(s):
    return s.replace(" ", "")


def aggregate_club():
    players = {}          # (norm full name, nation) -> rec
    by_name = {}          # norm full name -> list of recs
    with open(CLUB_CSV, encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        for row in r:
            name = (row.get("Player") or "").strip()
            if not name:
                continue
            nat = nation_code(row.get("Nation"))
            key = (norm(name), nat)
            mins = num(row.get("Min")) or 0
            rec = players.get(key)
            if rec is None:
                rec = {"player_name": name, "nation": nat, "min": 0.0,
                       "crdy": 0.0, "crdr": 0.0, "fls": 0.0, "fld": 0.0,
                       "squads": [], "_best_min": -1, "pos": ""}
                players[key] = rec
                by_name.setdefault(norm(name), []).append(rec)
            rec["min"] += mins
            for src, dst in (("CrdY", "crdy"), ("CrdR", "crdr"),
                             ("Fls", "fls"), ("Fld", "fld")):
                v = num(row.get(src))
                if v is not None:
                    rec[dst] += v
            sq = (row.get("Squad") or "").strip()
            if sq and sq not in rec["squads"]:
                rec["squads"].append(sq)
            if mins > rec["_best_min"]:
                rec["_best_min"] = mins
                rec["pos"] = (row.get("Pos") or "").strip()
    # despaced index for compound-name spacing differences (Korea, Japan)
    by_despaced = {}
    for rec in players.values():
        by_despaced.setdefault(despace(norm(rec["player_name"])), []).append(rec)
    return players, by_name, by_despaced


# ---- match squad player to club record ------------------------------------

def match(sq, club_by_key, club_by_name, club_by_despaced):
    code = sq["code"]
    cand_codes = [code] + NATION_ALIASES.get(code, [])
    name_variants = []
    # PLAYER NAME as printed, natural order, common name for many federations
    name_variants.append(norm(sq["player_name"]))
    if sq["first"] and sq["last"]:
        name_variants.append(norm(f"{sq['first']} {sq['last']}"))
    name_variants.append(norm(f"{sq['first']} {sq['shirt']}"))
    name_variants.append(norm(sq["shirt"]))
    name_variants.append(norm(sq["last"]))
    # reversed "LAST First" -> "First Last"
    pn = sq["player_name"].split()
    if len(pn) >= 2:
        name_variants.append(norm(" ".join(pn[1:] + [pn[0]])))
    # first given name + shirt surname, strips initials like "M. SALAH"
    first_given = sq["first"].split()[0] if sq["first"] else ""
    shirt_surname = sq["shirt"].split()[-1] if sq["shirt"] else ""
    if first_given and shirt_surname and "." not in shirt_surname:
        name_variants.append(norm(f"{first_given} {shirt_surname}"))
    seen = set()
    variants = [v for v in name_variants if v and not (v in seen or seen.add(v))]

    # 1) full-name + nation
    for v in variants:
        for c in cand_codes:
            rec = club_by_key.get((v, c))
            if rec:
                return rec, "name+nation"
    # 2) unique full-name across dataset
    for v in variants:
        recs = club_by_name.get(v)
        if recs and len(recs) == 1:
            return recs[0], "name_only"
    # 3) full-name with multiple matches, pick the one matching nation
    for v in variants:
        recs = club_by_name.get(v)
        if recs:
            for rec in recs:
                if rec["nation"] in cand_codes:
                    return rec, "name+nation_multi"
    # 4) despaced match for compound-given-name spacing, e.g. Kang-in vs Kangin
    for v in variants:
        recs = club_by_despaced.get(despace(v))
        if recs:
            # prefer a nation match, else accept only if unique
            for rec in recs:
                if rec["nation"] in cand_codes:
                    return rec, "despaced+nation"
            if len(recs) == 1:
                return recs[0], "despaced_only"
    return None, "unmatched"


# ---- output ---------------------------------------------------------------

MASTER_COLS = ["team", "code", "pos", "player_name", "first", "last",
               "shirt", "dob", "club", "height"]

JOINED_COLS = ["player_name", "team", "code", "squad_pos", "club", "club_league_pos",
               "club_minutes", "club_yellow_cards", "club_red_cards",
               "club_fouls_committed", "club_fouls_drawn",
               "club_yc_per90", "club_fouls_per90", "risk_score",
               "low_sample", "match_method", "data_sources"]


def write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in cols})


def main():
    squads = parse_squads()
    print(f"parsed {len(squads)} squad players from {PDF.name}")
    teams = sorted({s["team"] for s in squads})
    print(f"teams: {len(teams)}")
    write_csv(OUT_MASTER, MASTER_COLS, squads)
    print(f"wrote {OUT_MASTER.name}")

    club_by_key, club_by_name, club_by_despaced = aggregate_club()
    print(f"aggregated {len(club_by_key)} club players")

    joined = []
    matched = 0
    for sq in squads:
        rec, method = match(sq, club_by_key, club_by_name, club_by_despaced)
        if rec:
            matched += 1
            mins = rec["min"]
            yc90 = per90(rec["crdy"], mins)
            fl90 = per90(rec["fls"], mins)
            risk = round((yc90 * 2) + fl90, 4) if (yc90 is not None and fl90 is not None) else None
            joined.append({
                "player_name": sq["player_name"], "team": sq["team"],
                "code": sq["code"], "squad_pos": sq["pos"], "club": sq["club"],
                "club_league_pos": rec["pos"],
                "club_minutes": int(mins), "club_yellow_cards": int(rec["crdy"]),
                "club_red_cards": int(rec["crdr"]),
                "club_fouls_committed": int(rec["fls"]),
                "club_fouls_drawn": int(rec["fld"]),
                "club_yc_per90": yc90, "club_fouls_per90": fl90,
                "risk_score": risk,
                "low_sample": "yes" if mins < LOW_SAMPLE_MINUTES else "no",
                "match_method": method, "data_sources": "club+fifa_squad",
            })
        else:
            joined.append({
                "player_name": sq["player_name"], "team": sq["team"],
                "code": sq["code"], "squad_pos": sq["pos"], "club": sq["club"],
                "club_league_pos": None, "club_minutes": None,
                "club_yellow_cards": None, "club_red_cards": None,
                "club_fouls_committed": None, "club_fouls_drawn": None,
                "club_yc_per90": None, "club_fouls_per90": None,
                "risk_score": None, "low_sample": None,
                "match_method": "unmatched", "data_sources": "fifa_squad",
            })

    joined.sort(key=lambda x: (x["risk_score"] is None, -(x["risk_score"] or 0)))
    write_csv(OUT_JOINED, JOINED_COLS, joined)
    print(f"wrote {OUT_JOINED.name}")

    # ---- report ----
    total = len(joined)
    print("\n==================== COVERAGE ====================")
    print(f"confirmed squad players: {total}")
    print(f"matched to club data: {matched} ({100*matched/total:.1f}%)")
    print(f"club data missing (other leagues): {total-matched}")
    methods = {}
    for r in joined:
        methods[r["match_method"]] = methods.get(r["match_method"], 0) + 1
    print("match methods:")
    for k in sorted(methods):
        print(f"   {k}: {methods[k]}")
    # unmatched by team, to spot systematic gaps
    unm = {}
    for r in joined:
        if r["match_method"] == "unmatched":
            unm[r["team"]] = unm.get(r["team"], 0) + 1
    print("unmatched per team (top 12):")
    for t, n in sorted(unm.items(), key=lambda x: -x[1])[:12]:
        print(f"   {t}: {n}")
    print("=================================================\n")

    print("Top 20 confirmed-squad players by club-form risk (sample >=450 min):")
    shown = [r for r in joined if r["risk_score"] is not None
             and r["low_sample"] == "no"][:20]
    for r in shown:
        print(f"   {r['risk_score']:.2f}  {r['player_name']:<24} {r['code']}  "
              f"{r['team']:<16} yc90={r['club_yc_per90']} fls90={r['club_fouls_per90']} "
              f"min={r['club_minutes']}")


if __name__ == "__main__":
    main()
