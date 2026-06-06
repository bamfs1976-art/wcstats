#!/usr/bin/env python3
"""
WC2026 pre-tournament disciplinary pipeline.

Runs the five-step brief: pull qualification stats from Sofascore, pull
2025-26 club stats from the Kaggle dataset, filter by the confirmed FIFA
squad lists, join, calculate per90 rates and a risk score, then write two
CSVs.

WHY THIS IS A SCRIPT, NOT A CHAT ACTION
The harvesting steps need outbound network and, for Kaggle, auth. Run this
on a machine with network, or paste it into a Kaggle or Colab notebook where
the dataset is one import away and Sofascore is reachable.

RULES HONOURED
- 1 second delay between every API request
- User-Agent: Mozilla/5.0 on every request
- player in only one source is flagged in data_sources
- missing values are left null, never invented or interpolated
- prints a completion summary: total players, coverage %, nulls by column

DEPENDENCIES
    pip install requests pandas pdfplumber unidecode
    # Kaggle download path also needs one of:
    pip install kagglehub          # simplest, no token prompt on Kaggle
    # or the kaggle CLI with ~/.kaggle/kaggle.json credentials

FIELD NAMES MAY NEED A ONE LINE TWEAK
Sofascore's exact field keys can shift. The disciplinary projection is set
in SOFA_FIELDS below. To verify, open one endpoint in a browser, for example
https://www.sofascore.com/api/v1/unique-tournament/11/season/69427/statistics?limit=5&offset=0&order=-yellowCards&accumulation=total&group=summary
and read the keys on each results row. Adjust SOFA_FIELDS to match.
"""

import csv
import json
import time
import sys
import os
from pathlib import Path

import requests

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from unidecode import unidecode
except ImportError:
    def unidecode(s):  # graceful fallback, keeps ascii only
        return s.encode("ascii", "ignore").decode("ascii")


# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------

HEADERS = {"User-Agent": "Mozilla/5.0"}
REQUEST_DELAY_SECONDS = 1.0          # rule: 1s between every request
PAGE_SIZE = 100
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3

OUT_DIR = Path(__file__).resolve().parent
FULL_OUT = OUT_DIR / "wc2026_pre_tournament_disciplinary.csv"
HIGH_RISK_OUT = OUT_DIR / "wc2026_high_risk_players.csv"

# Confederation qualifying tournaments. CONCACAF/CAF/AFC season ids are
# resolved at runtime by matching a 2026 season; UEFA is known good as 69427.
TOURNAMENTS = {
    "UEFA": 11,
    "CONMEBOL": 42,
    "CONCACAF": 678,
    "CAF": 427,
    "AFC": 559,
}

# Stat keys to pull per the brief. The left side is the brief's name, the
# right side is the Sofascore field key. Verify against a live response.
STAT_KEYS = {
    "foulsCommitted": "fouls",
    "foulsReceived": "wasFouled",
    "yellowCards": "yellowCards",
    "yellowRedCards": "yellowRedCards",
    "redCards": "redCards",
}
# Extra fields needed for per90 maths.
EXTRA_FIELDS = ["minutesPlayed", "appearances"]

# The full field projection requested from Sofascore.
SOFA_FIELDS = list(STAT_KEYS.values()) + EXTRA_FIELDS

BASE = "https://www.sofascore.com/api/v1"

# Kaggle dataset for 2025-26 club stats.
KAGGLE_DATASET = "hubertsidorowicz/football-players-stats-2025-2026"
# If you have already downloaded the CSV, set its local path here to skip
# the network/auth step entirely.
KAGGLE_LOCAL_CSV = os.environ.get("WC26_CLUB_CSV", "")

# FIFA confirmed squad lists PDF.
FIFA_PDF_URL = "https://fdp.fifa.org/assetspublic/ce281/pdf/SquadLists-English.pdf"
FIFA_LOCAL_PDF = os.environ.get("WC26_SQUAD_PDF", "")


# --------------------------------------------------------------------------
# HTTP helper, one place that enforces the delay and the UA
# --------------------------------------------------------------------------

_session = requests.Session()
_session.headers.update(HEADERS)


def get_json(url):
    """GET with retries and a mandatory post-request delay."""
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = _session.get(url, timeout=REQUEST_TIMEOUT)
            time.sleep(REQUEST_DELAY_SECONDS)  # rule: 1s between requests
            if r.status_code == 200:
                return r.json()
            last_err = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            time.sleep(REQUEST_DELAY_SECONDS)
        print(f"   retry {attempt}/{MAX_RETRIES} for {url} ({last_err})",
              file=sys.stderr)
    print(f"   FAILED {url} ({last_err})", file=sys.stderr)
    return None


def norm_name(name):
    """Normalise a player name for joining: ascii, lower, single spaces."""
    if not name:
        return ""
    return " ".join(unidecode(name).lower().split())


def norm_nat(nation):
    if not nation:
        return ""
    return unidecode(nation).strip().lower()


# --------------------------------------------------------------------------
# STEP 1, Sofascore qualification stats
# --------------------------------------------------------------------------

def resolve_season_id(tid):
    """Pick the 2026 qualification season for a tournament."""
    data = get_json(f"{BASE}/unique-tournament/{tid}/seasons")
    if not data:
        return None
    seasons = data.get("seasons", [])
    # Prefer a season whose name mentions 2026, else year == 2026.
    for s in seasons:
        if "2026" in (s.get("name", "") or ""):
            return s.get("id")
    for s in seasons:
        if str(s.get("year", "")) == "2026":
            return s.get("id")
    return None


def pull_tournament(conf, tid):
    """Return {player_id: row dict} for one qualifying tournament."""
    sid = resolve_season_id(tid)
    if not sid:
        print(f"[{conf}] no 2026 season found, skipping")
        return {}
    print(f"[{conf}] tid={tid} season={sid}")
    players = {}
    offset = 0
    fields_param = ",".join(SOFA_FIELDS)
    while True:
        url = (
            f"{BASE}/unique-tournament/{tid}/season/{sid}/statistics"
            f"?limit={PAGE_SIZE}&offset={offset}"
            f"&order=-yellowCards&accumulation=total&group=summary"
            f"&fields={fields_param}"
        )
        data = get_json(url)
        if not data:
            break
        results = data.get("results", [])
        if not results:
            break
        for row in results:
            p = row.get("player", {}) or {}
            t = row.get("team", {}) or {}
            pid = p.get("id")
            if pid is None:
                continue
            rec = {
                "player_name": p.get("name"),
                "team": t.get("name"),
                "confederation": conf,
                "position": p.get("position"),
            }
            # Pull each disciplinary stat, leaving null when absent.
            for brief_key, sofa_key in STAT_KEYS.items():
                rec[f"qual_{brief_key}"] = row.get(sofa_key, None)
            rec["qual_minutes"] = row.get("minutesPlayed", None)
            rec["qual_appearances"] = row.get("appearances", None)
            players[pid] = rec
        offset += PAGE_SIZE
        # pagination stops when a short page or empty page is returned
        if len(results) < PAGE_SIZE:
            break
    print(f"[{conf}] pulled {len(players)} players")
    return players


def step1_qualification():
    all_players = {}
    for conf, tid in TOURNAMENTS.items():
        all_players.update({f"{conf}:{k}": v
                            for k, v in pull_tournament(conf, tid).items()})
    return all_players


# --------------------------------------------------------------------------
# STEP 2, Kaggle 2025-26 club stats
# --------------------------------------------------------------------------

CLUB_COLUMNS = [
    "player_name", "team", "nationality", "position", "minutes",
    "yellow_cards", "red_cards", "fouls_committed", "fouls_drawn",
]


def step2_club_stats():
    """Return a list of club stat dicts, or [] if the source is unavailable."""
    csv_path = None
    if KAGGLE_LOCAL_CSV and Path(KAGGLE_LOCAL_CSV).exists():
        csv_path = Path(KAGGLE_LOCAL_CSV)
    else:
        try:
            import kagglehub
            path = kagglehub.dataset_download(KAGGLE_DATASET)
            # find the first csv in the download
            for f in Path(path).rglob("*.csv"):
                csv_path = f
                break
        except Exception as e:  # noqa: BLE001
            print(f"[club] kaggle download unavailable: {e}")
            print("[club] set WC26_CLUB_CSV to a local CSV path to proceed")
            return []
    if not csv_path:
        print("[club] no club CSV found")
        return []

    print(f"[club] reading {csv_path}")
    rows = []
    # tolerant column matching, dataset headers vary by release
    with open(csv_path, newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        header_map = _map_club_headers(reader.fieldnames or [])
        for r in reader:
            rows.append({k: r.get(v) if v else None
                         for k, v in header_map.items()})
    print(f"[club] read {len(rows)} club rows")
    return rows


def _map_club_headers(fieldnames):
    """Best-effort map of brief column -> actual CSV header."""
    lower = {f.lower(): f for f in fieldnames}

    def pick(*cands):
        for c in cands:
            if c in lower:
                return lower[c]
        return None

    return {
        "player_name": pick("player", "player_name", "name"),
        "team": pick("team", "squad", "club"),
        "nationality": pick("nation", "nationality", "country"),
        "position": pick("pos", "position"),
        "minutes": pick("min", "minutes", "minutes_played", "90s"),
        "yellow_cards": pick("crdy", "yellow_cards", "cards_yellow"),
        "red_cards": pick("crdr", "red_cards", "cards_red"),
        "fouls_committed": pick("fls", "fouls", "fouls_committed"),
        "fouls_drawn": pick("fld", "fouls_drawn", "fouled"),
    }


# --------------------------------------------------------------------------
# STEP 3, FIFA confirmed squad filter
# --------------------------------------------------------------------------

def step3_squad_filter():
    """Return a set of (norm_name, norm_nat) for confirmed WC2026 players.

    Returns None if the squad list could not be read, meaning no filter is
    applied and every player is kept with a note in data_sources.
    """
    pdf_path = None
    if FIFA_LOCAL_PDF and Path(FIFA_LOCAL_PDF).exists():
        pdf_path = Path(FIFA_LOCAL_PDF)
    else:
        # try to download to a temp file
        try:
            r = _session.get(FIFA_PDF_URL, timeout=REQUEST_TIMEOUT)
            time.sleep(REQUEST_DELAY_SECONDS)
            if r.status_code == 200:
                pdf_path = OUT_DIR / "SquadLists-English.pdf"
                pdf_path.write_bytes(r.content)
        except Exception as e:  # noqa: BLE001
            print(f"[squad] FIFA PDF download failed: {e}")

    if not pdf_path or not pdf_path.exists():
        print("[squad] no squad PDF, skipping the confirmed-squad filter")
        return None

    try:
        import pdfplumber
    except ImportError:
        print("[squad] pdfplumber not installed, skipping squad filter")
        return None

    squad = set()
    current_nation = None
    print(f"[squad] parsing {pdf_path}")
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                # NOTE: tune these two heuristics to the real PDF layout.
                # A team header line tends to be a short all-caps country.
                if line.isupper() and len(line.split()) <= 4:
                    current_nation = line.title()
                    continue
                # A player line tends to contain a name; keep the last token
                # group as the name. This is best-effort and should be
                # checked against the actual PDF formatting.
                name = _extract_player_name(line)
                if name and current_nation:
                    squad.add((norm_name(name), norm_nat(current_nation)))
    print(f"[squad] parsed {len(squad)} confirmed players")
    return squad or None


def _extract_player_name(line):
    """Pull a plausible player name from a squad-list line.

    The FIFA list rows usually look like: number, position, name, club,
    date of birth. This keeps the alphabetic middle. Tune to the real PDF.
    """
    tokens = [t for t in line.split() if any(ch.isalpha() for ch in t)]
    # drop common position codes and noise
    noise = {"GK", "DF", "MF", "FW", "DEF", "MID", "FWD", "POS", "NO"}
    tokens = [t for t in tokens if t.upper() not in noise]
    if len(tokens) < 2:
        return None
    return " ".join(tokens[:3])  # first few alpha tokens as the name


# --------------------------------------------------------------------------
# STEP 4, join and calculate
# --------------------------------------------------------------------------

def per90(count, minutes):
    if count is None or minutes in (None, 0, "0", ""):
        return None
    try:
        c = float(count)
        m = float(minutes)
    except (TypeError, ValueError):
        return None
    if m <= 0:
        return None
    return round((c / m) * 90.0, 4)


def to_num(v):
    if v in (None, "", "null"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def step4_join(qual_players, club_rows, squad):
    # index club rows by (norm_name, norm_nat) and by norm_name alone
    club_by_key = {}
    club_by_name = {}
    for r in club_rows:
        nm = norm_name(r.get("player_name"))
        nat = norm_nat(r.get("nationality"))
        if nm:
            club_by_key[(nm, nat)] = r
            club_by_name.setdefault(nm, r)

    joined = []
    seen_keys = set()

    # start from qualification players
    for rec in qual_players.values():
        nm = norm_name(rec.get("player_name"))
        nat = norm_nat(rec.get("team"))  # national team == nationality here
        key = (nm, nat)
        seen_keys.add(key)

        # confirmed-squad filter
        if squad is not None and key not in squad and (nm, "") not in {
                (n, "") for (n, _) in squad if n == nm}:
            # not in a confirmed squad, drop per the brief
            continue

        club = club_by_key.get(key) or club_by_name.get(nm)
        out = _build_row(rec, club, squad)
        joined.append(out)

    return joined


def _build_row(qual, club, squad):
    sources = []
    if qual:
        sources.append("qualification")
    if club:
        sources.append("club")
    if squad is not None:
        sources.append("fifa_squad")

    q = qual or {}
    c = club or {}

    qual_min = to_num(q.get("qual_minutes"))
    club_min = to_num(c.get("minutes"))
    qual_yc = to_num(q.get("qual_yellowCards"))
    qual_fouls = to_num(q.get("qual_foulsCommitted"))
    club_yc = to_num(c.get("yellow_cards"))
    club_fouls = to_num(c.get("fouls_committed"))

    # combined per90 across both sources where minutes exist, else null
    tot_min = (qual_min or 0) + (club_min or 0)
    tot_yc = (qual_yc or 0) + (club_yc or 0) if (qual_yc is not None or club_yc is not None) else None
    tot_fouls = (qual_fouls or 0) + (club_fouls or 0) if (qual_fouls is not None or club_fouls is not None) else None
    combined_yc90 = per90(tot_yc, tot_min) if tot_min else None
    combined_fouls90 = per90(tot_fouls, tot_min) if tot_min else None

    risk = None
    if combined_yc90 is not None and combined_fouls90 is not None:
        risk = round((combined_yc90 * 2) + combined_fouls90, 4)

    return {
        "player_name": q.get("player_name") or c.get("player_name"),
        "team": q.get("team") or c.get("team"),
        "confederation": q.get("confederation"),
        "position": q.get("position") or c.get("position"),
        "qual_minutes": q.get("qual_minutes"),
        "qual_yellow_cards": q.get("qual_yellowCards"),
        "qual_red_cards": q.get("qual_redCards"),
        "qual_fouls_committed": q.get("qual_foulsCommitted"),
        "qual_fouls_drawn": q.get("qual_foulsReceived"),
        "club_minutes": c.get("minutes"),
        "club_yellow_cards": c.get("yellow_cards"),
        "club_fouls_committed": c.get("fouls_committed"),
        "combined_yc_per90": combined_yc90,
        "combined_fouls_per90": combined_fouls90,
        "risk_score": risk,
        "data_sources": "+".join(sources) if sources else "none",
    }


OUTPUT_COLUMNS = [
    "player_name", "team", "confederation", "position",
    "qual_minutes", "qual_yellow_cards", "qual_red_cards",
    "qual_fouls_committed", "qual_fouls_drawn",
    "club_minutes", "club_yellow_cards", "club_fouls_committed",
    "combined_yc_per90", "combined_fouls_per90", "risk_score",
    "data_sources",
]


# --------------------------------------------------------------------------
# STEP 5, output and summary
# --------------------------------------------------------------------------

def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k))
                        for k in OUTPUT_COLUMNS})


def top20pct_per_team(rows):
    by_team = {}
    for r in rows:
        if r.get("risk_score") is None:
            continue
        by_team.setdefault(r["team"], []).append(r)
    high = []
    for team, players in by_team.items():
        players.sort(key=lambda x: x["risk_score"], reverse=True)
        n = max(1, round(len(players) * 0.2))
        high.extend(players[:n])
    high.sort(key=lambda x: (x["team"] or "", -x["risk_score"]))
    return high


def print_summary(rows):
    total = len(rows)
    print("\n==================== SUMMARY ====================")
    print(f"total players: {total}")
    if total == 0:
        print("no rows produced, check the source steps above")
        return
    # coverage: share with a usable risk score
    scored = sum(1 for r in rows if r.get("risk_score") is not None)
    print(f"risk-scored coverage: {scored}/{total} "
          f"({100.0 * scored / total:.1f}%)")
    src_counts = {}
    for r in rows:
        src_counts[r["data_sources"]] = src_counts.get(r["data_sources"], 0) + 1
    print("rows by data_sources:")
    for k in sorted(src_counts):
        print(f"   {k}: {src_counts[k]}")
    print("nulls by column:")
    for col in OUTPUT_COLUMNS:
        nulls = sum(1 for r in rows if r.get(col) in (None, ""))
        print(f"   {col}: {nulls}")
    print("================================================\n")


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------

def main():
    print("STEP 1, Sofascore qualification stats")
    qual_players = step1_qualification()

    print("\nSTEP 2, Kaggle 2025-26 club stats")
    club_rows = step2_club_stats()

    print("\nSTEP 3, FIFA confirmed squad filter")
    squad = step3_squad_filter()

    print("\nSTEP 4, join and calculate")
    rows = step4_join(qual_players, club_rows, squad)

    print("\nSTEP 5, output")
    write_csv(FULL_OUT, rows)
    high = top20pct_per_team(rows)
    write_csv(HIGH_RISK_OUT, high)
    print(f"wrote {FULL_OUT} ({len(rows)} rows)")
    print(f"wrote {HIGH_RISK_OUT} ({len(high)} rows)")

    print_summary(rows)


if __name__ == "__main__":
    main()
