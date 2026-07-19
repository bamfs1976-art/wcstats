#!/usr/bin/env python3
"""
Tokenless replacement for the football-data.org harvest (build_fd.py +
build_fd_standings.py), built on ESPN's public Site API — the same source
tbayryyev/worldcup-dashboard and neilkpatel/worldcup-2026-dashboard run on.
No API key, ~1-2 min behind live (vs ~6 min for football-data).

Endpoints (competition slug fifa.world):
  scoreboard: https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=YYYYMMDD-YYYYMMDD
  standings:  https://site.api.espn.com/apis/v2/sports/soccer/fifa.world/standings
  summary:    https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={id}
ESPN caps responses at ~100 events, so the 104-match schedule is fetched in
two date windows.

Outputs (byte-compatible with the existing pipeline, consumed by index.html
after data/sync_inline.py):
  fd_extra.js      FD_RESULTS + FD_STAGE_LABELS + FD_KNOCKOUT
  fd_standings.js  FD_UPDATED + FD_STANDINGS
  espn_match_refs.json   (--refs only) referee per finished match, for
                         manually updating TOURN_REFS / KO_META

Knockout rows join KO_META in index.html by exact kickoff string, so each
knockout kickoff is snapped to the nearest KO_META key within 3 hours; rows
that can't snap keep the ESPN time and are WARNed loudly.

Usage:
  python3 build_espn.py [--refs] [--fixtures DIR]
--fixtures DIR reads scoreboard-1.json / scoreboard-2.json / standings.json
from DIR instead of the network (offline testing).
No third-party dependencies.
"""
import json, re, sys, unicodedata, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent
TEAMFORM = DATA / "wc2026_team_form.json"
INDEX = DATA.parent / "index.html"
OUT_EXTRA = DATA / "fd_extra.js"
OUT_STAND = DATA / "fd_standings.js"
OUT_REFS = DATA / "espn_match_refs.json"

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
STAND_URL = "https://site.api.espn.com/apis/v2/sports/soccer/fifa.world/standings"
WINDOWS = ["20260611-20260710", "20260711-20260719"]

STAGE = {"LAST_32": "Round of 32", "LAST_16": "Round of 16",
         "QUARTER_FINALS": "Quarter-finals", "SEMI_FINALS": "Semi-finals",
         "THIRD_PLACE": "Third place", "FINAL": "Final"}
ORDER = ["LAST_32", "LAST_16", "QUARTER_FINALS", "SEMI_FINALS", "THIRD_PLACE", "FINAL"]

# ESPN round/note text -> our stage keys (matched lowercase, first hit wins)
ROUND_MAP = [("32", "LAST_32"), ("16", "LAST_16"), ("quarter", "QUARTER_FINALS"),
             ("semi", "SEMI_FINALS"), ("third", "THIRD_PLACE"), ("final", "FINAL")]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "wcstats-build/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def norm(s):
    s = "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c)).lower().strip()
    return re.sub(r"[^a-z0-9 ]", "", s)


def teamkey(n):
    x = norm(n)
    if "ivoir" in x or "ivory" in x: return "ivory"
    if "turk" in x: return "turkiye"
    if "verde" in x: return "capeverde"
    if "korea" in x: return "korea"
    if "bosnia" in x: return "bosnia"
    if "iran" in x: return "iran"
    if x in ("usa", "united states"): return "usa"
    if "congo" in x: return "congo"
    if "czech" in x: return "czech"
    return x.replace(" ", "")


def load_desk():
    teams = json.loads(TEAMFORM.read_text(encoding="utf-8"))["teams"]
    return {teamkey(t["n"]): t for t in teams}


def desk_team(by_key, name):
    t = by_key.get(teamkey(name))
    if t:
        return t["c"], t["f"], t["n"]
    return None, "", name


def ko_meta_kickoffs():
    """KO_META keys from index.html: kickoff string -> match number."""
    html = INDEX.read_text(encoding="utf-8")
    block = re.search(r"const KO_META=\{(.*?)\n\};", html, re.S).group(1)
    return {d: int(m) for d, m in re.findall(r'"([^"]+)":\{m:(\d+)', block)}


def snap_kickoff(dt_utc, meta_keys):
    """Snap an ESPN kickoff to the nearest KO_META key within 3 hours."""
    best, best_gap = None, timedelta(hours=3)
    for key in meta_keys:
        kdt = datetime.strptime(key, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        gap = abs(kdt - dt_utc)
        if gap <= best_gap:
            best, best_gap = key, gap
    return best


def classify_stage(event):
    """Stage key for a knockout event from its round/note text, else None (group)."""
    texts = []
    comp = (event.get("competitions") or [{}])[0]
    for note in event.get("notes", []) + comp.get("notes", []):
        texts.append(str(note.get("headline") or note.get("text") or ""))
    season_type = (event.get("season") or {}).get("slug") or ""
    texts.append(season_type)
    blob = " ".join(texts).lower()
    if "group" in blob:
        return None
    for frag, stage in ROUND_MAP:
        if frag in blob:
            return stage
    return None


def main():
    args = sys.argv[1:]
    want_refs = "--refs" in args
    fixtures = None
    if "--fixtures" in args:
        fixtures = Path(args[args.index("--fixtures") + 1])

    by_key = load_desk()
    meta_keys = ko_meta_kickoffs()

    events = []
    for i, win in enumerate(WINDOWS, 1):
        if fixtures:
            payload = json.loads((fixtures / f"scoreboard-{i}.json").read_text(encoding="utf-8"))
        else:
            payload = fetch(f"{BASE}/scoreboard?dates={win}&limit=200")
        events.extend(payload.get("events", []))
    print(f"scoreboard events: {len(events)}")

    results = {}   # sorted code pair -> "H-A"
    knockout = []
    refs = {}
    for ev in events:
        comp = (ev.get("competitions") or [{}])[0]
        sides = {c.get("homeAway"): c for c in comp.get("competitors", [])}
        home, away = sides.get("home"), sides.get("away")
        if not home or not away:
            continue
        status = ((ev.get("status") or {}).get("type") or {})
        finished = bool(status.get("completed"))
        state = status.get("state")           # pre / in / post
        fd_status = "FINISHED" if finished else ("IN_PLAY" if state == "in" else "TIMED")

        hname = (home.get("team") or {}).get("displayName") or ""
        aname = (away.get("team") or {}).get("displayName") or ""
        hc, hf, hn = desk_team(by_key, hname)
        ac, af, an = desk_team(by_key, aname)
        if not hc or not ac:
            # TBD placeholders (unset knockout slots) come through without real teams
            hc = ac = None

        def score_of(side):
            v = side.get("score")
            try:
                return int(v)
            except (TypeError, ValueError):
                return None
        hs, as_ = (score_of(home), score_of(away)) if finished else (None, None)
        # penalty shootout, if ESPN carries it on the competitor
        hp, ap = home.get("shootoutScore"), away.get("shootoutScore")

        stage = classify_stage(ev)
        if stage is None:
            if finished and hc and ac and hs is not None:
                a, b = sorted([hc, ac])
                results["|".join([a, b])] = f"{hs}-{as_}" if hc == a else f"{as_}-{hs}"
            continue

        dt = datetime.strptime(ev["date"].replace("Z", "+00:00"), "%Y-%m-%dT%H:%M%z").astimezone(timezone.utc)
        key = snap_kickoff(dt, meta_keys)
        if key is None:
            key = dt.strftime("%Y-%m-%d %H:%M")
            print(f"  WARN: no KO_META kickoff within 3h of {key} ({hname} v {aname}) — row will not join KO_META")
        sc = None
        if finished and hs is not None:
            sc = f"{hs}-{as_}"
            if hs == as_ and hp is not None and ap is not None:
                sc += f" ({hp}-{ap}p)"
        knockout.append({"st": stage, "d": key, "hc": hc, "hf": hf, "hn": hn if hc else None,
                         "ac": ac, "af": af, "an": an if ac else None,
                         "sc": sc, "status": fd_status})
        if finished and hc and ac and hs is not None:
            a, b = sorted([hc, ac])
            results["|".join([a, b])] = f"{hs}-{as_}" if hc == a else f"{as_}-{hs}"
        if want_refs and finished and not fixtures:
            summary = fetch(f"{BASE}/summary?event={ev['id']}")
            officials = (summary.get("gameInfo") or {}).get("officials") or []
            if officials:
                refs[key] = {"fixture": f"{hname} v {aname}",
                             "referee": officials[0].get("displayName") or officials[0].get("fullName")}

    knockout.sort(key=lambda k: (ORDER.index(k["st"]) if k["st"] in ORDER else 9, k["d"]))

    # ---- standings ----
    if fixtures:
        stand = json.loads((fixtures / "standings.json").read_text(encoding="utf-8"))
    else:
        stand = fetch(STAND_URL)
    groups = []
    for child in stand.get("children", []):
        gname = (child.get("name") or child.get("abbreviation") or "").replace("Group ", "").strip()
        rows = []
        for entry in ((child.get("standings") or {}).get("entries") or []):
            name = (entry.get("team") or {}).get("displayName") or ""
            c, f, n = desk_team(by_key, name)
            st = {s.get("name") or s.get("type"): s.get("value") for s in entry.get("stats", [])}
            rows.append({"c": c or name, "f": f, "n": n,
                         "p": int(st.get("gamesPlayed", 0)), "w": int(st.get("wins", 0)),
                         "d": int(st.get("ties", 0)), "l": int(st.get("losses", 0)),
                         "gf": int(st.get("pointsFor", 0)), "ga": int(st.get("pointsAgainst", 0)),
                         "gd": int(st.get("pointDifferential", 0)), "pts": int(st.get("points", 0))})
        if gname and rows:
            groups.append({"g": gname, "rows": rows})
    groups.sort(key=lambda g: g["g"])
    print(f"groups: {len(groups)}  knockout rows: {len(knockout)}  results: {len(results)}")

    js = lambda x: json.dumps(x, ensure_ascii=False)

    lines = ["// Auto-generated by build_espn.py from ESPN's public Site API.",
             "// FD_RESULTS: finished scores by sorted team-code pair (auto-merged",
             "// into RESULTS, never overriding manual entries). FD_KNOCKOUT: bracket.",
             "const FD_RESULTS=" + js(results) + ";",
             "const FD_STAGE_LABELS=" + js(STAGE) + ";",
             "const FD_KNOCKOUT=["]
    for k in knockout:
        lines.append("  {" + ",".join([
            f'st:{js(k["st"])}', f'd:{js(k["d"])}',
            f'hc:{js(k["hc"])}', f'hf:{js(k["hf"])}', f'hn:{js(k["hn"])}',
            f'ac:{js(k["ac"])}', f'af:{js(k["af"])}', f'an:{js(k["an"])}',
            f'sc:{js(k["sc"])}', f'status:{js(k["status"])}',
        ]) + "},")
    lines.append("];")
    OUT_EXTRA.write_text("\n".join(lines), encoding="utf-8")

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:00Z")
    slines = ["// Auto-generated by build_espn.py from ESPN's public Site API.",
              "// Live World Cup group tables. Refresh by re-running build_espn.py.",
              f"const FD_UPDATED={js(updated)};",
              "const FD_STANDINGS=["]
    for g in groups:
        rws = ",".join("{" + ",".join([
            f'c:{js(r["c"])}', f'f:{js(r["f"])}', f'n:{js(r["n"])}',
            f'p:{r["p"]}', f'w:{r["w"]}', f'd:{r["d"]}', f'l:{r["l"]}',
            f'gf:{r["gf"]}', f'ga:{r["ga"]}', f'gd:{r["gd"]}', f'pts:{r["pts"]}',
        ]) + "}" for r in g["rows"])
        slines.append(f'  {{g:{js(g["g"])},rows:[{rws}]}},')
    slines.append("];")
    OUT_STAND.write_text("\n".join(slines), encoding="utf-8")

    if want_refs and refs:
        OUT_REFS.write_text(json.dumps(refs, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"refs written for {len(refs)} matches -> {OUT_REFS.name}")

    played = sum(1 for k in knockout if k["sc"])
    print(f"wrote {OUT_EXTRA.name} + {OUT_STAND.name}  (KO played: {played})")


if __name__ == "__main__":
    main()
