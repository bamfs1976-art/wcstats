#!/usr/bin/env python3
"""
Draft RESULTS entries (score, scorers, desk-style note) for played matches
using the Claude API, grounded in ESPN's public match summaries — the pattern
neilkpatel/worldcup-2026-dashboard uses for AI match recaps.

For every finished knockout tie in FD_KNOCKOUT whose manual RESULTS entry is
missing or has no scorer detail, the script:
  1. finds the ESPN event and pulls its summary (goals, cards, stats, refs)
  2. asks Claude to draft a {s, ga, gb, note} entry in the desk's house style
     (few-shot from the existing RESULTS entries, structured-output enforced)
  3. writes the drafts to recaps_suggested.js for review

Nothing touches index.html unless --apply is passed, and even then only keys
that do NOT already exist in RESULTS are inserted — manual entries are never
overridden, matching the FD_RESULTS merge philosophy.

Usage:
  python3 build_recaps.py                 # draft for all finished KO ties needing detail
  python3 build_recaps.py --keys ARG|ENG ESP|FRA
  python3 build_recaps.py --apply         # also insert missing keys into index.html

Auth: ANTHROPIC_API_KEY env var (or an `ant auth login` profile).
Deps: pip install anthropic  (plus network access to ESPN + the Claude API).
"""
import argparse, json, re, sys
from pathlib import Path

import anthropic

from build_espn import BASE, WINDOWS, fetch, load_desk, desk_team

DATA = Path(__file__).resolve().parent
INDEX = DATA.parent / "index.html"
OUT = DATA / "recaps_suggested.js"

MODEL = "claude-opus-4-8"

ENTRY_SCHEMA = {
    "type": "object",
    "properties": {
        "s": {"type": "string", "description": "Score in sorted-key order, e.g. '2-1', with a trailing 'p' only for shootouts, e.g. '0-0p'"},
        "ga": {"type": "array", "items": {"type": "string"}, "description": "Goalscorers for the FIRST team code in the key, e.g. \"Bellingham 45+2'\""},
        "gb": {"type": "array", "items": {"type": "string"}, "description": "Goalscorers for the SECOND team code in the key"},
        "note": {"type": "string", "description": "One- to two-sentence desk note in house style"},
    },
    "required": ["s", "ga", "gb", "note"],
    "additionalProperties": False,
}


def parse_results_block(html):
    """Return (block_text, {key: entry_text}) for the manual RESULTS const."""
    m = re.search(r"const RESULTS=\{(.*?)\n\};", html, re.S)
    block = m.group(1)
    entries = dict(re.findall(r'"([A-Z]+\|[A-Z]+)":(\{.*?\}),?\n', block))
    return block, entries


def finished_knockout_pairs(html):
    """[(sorted_key, hc, ac, sc, stage)] for FINISHED FD_KNOCKOUT rows."""
    rows = re.findall(
        r'\{st:"([A-Z_]+)",d:"[^"]+",hc:"([A-Z]+)",[^}]*?ac:"([A-Z]+)",[^}]*?sc:"([^"]+)",status:"FINISHED"\}',
        html,
    )
    out = []
    for st, hc, ac, sc in rows:
        a, b = sorted([hc, ac])
        out.append(("|".join([a, b]), hc, ac, sc, st))
    return out


def espn_event_index():
    """(frozenset of desk codes) -> event dict, from the two scoreboard windows."""
    by_key = load_desk()
    index = {}
    for win in WINDOWS:
        payload = fetch(f"{BASE}/scoreboard?dates={win}&limit=200")
        for ev in payload.get("events", []):
            comp = (ev.get("competitions") or [{}])[0]
            sides = {c.get("homeAway"): c for c in comp.get("competitors", [])}
            names = []
            for side in ("home", "away"):
                c = sides.get(side) or {}
                code, _, _ = desk_team(by_key, (c.get("team") or {}).get("displayName") or "")
                names.append(code)
            if all(names):
                index[frozenset(names)] = ev
    return index


def match_context(event):
    """Compact factual grounding for the recap prompt from ESPN's summary."""
    summary = fetch(f"{BASE}/summary?event={event['id']}")
    ctx = {"header": {}, "goals": [], "cards": [], "stats": {}, "info": {}}
    comp = (event.get("competitions") or [{}])[0]
    for c in comp.get("competitors", []):
        ctx["header"][(c.get("team") or {}).get("displayName")] = c.get("score")
    for ev in (summary.get("keyEvents") or []):
        text = (ev.get("type") or {}).get("text", "").lower()
        clock = (ev.get("clock") or {}).get("displayValue", "")
        who = ", ".join(p.get("athlete", {}).get("displayName", "") for p in ev.get("participants", []))
        team = (ev.get("team") or {}).get("displayName", "")
        if "goal" in text:
            ctx["goals"].append(f"{clock} {who} ({team}) [{text}]")
        elif "yellow" in text or "red" in text:
            ctx["cards"].append(f"{clock} {who} ({team}) [{text}]")
    for t in (summary.get("boxscore") or {}).get("teams", []):
        name = (t.get("team") or {}).get("displayName")
        ctx["stats"][name] = {s.get("name"): s.get("displayValue") for s in t.get("statistics", [])}
    info = summary.get("gameInfo") or {}
    officials = info.get("officials") or []
    if officials:
        ctx["info"]["referee"] = officials[0].get("displayName") or officials[0].get("fullName")
    if info.get("attendance"):
        ctx["info"]["attendance"] = info["attendance"]
    return ctx


def style_examples(entries, limit=4):
    """Existing entries with scorers, as few-shot house-style examples."""
    rich = [(k, v) for k, v in entries.items() if "ga:[" in v and "note:" in v]
    return "\n".join(f'"{k}":{v},' for k, v in rich[-limit:])


def draft_entry(client, key, stage_label, sc, context, examples):
    a, b = key.split("|")
    system = (
        "You write one-line match entries for a World Cup 2026 stats desk. "
        "House style, learned from these existing entries (key is the sorted "
        "team-code pair; ga = goals for the first code, gb = for the second; "
        "minutes use apostrophes, pens marked '(pen)' or 'pen', own goals 'OG'):\n"
        f"{examples}\n"
        "Notes open with the round, state who won and who was eliminated, and "
        "may add ONE notable fact from the data (red card, comeback, record, "
        "hat-trick). Never invent facts not present in the match data."
    )
    prompt = (
        f"Write the RESULTS entry for key \"{key}\" ({stage_label}).\n"
        f"First code {a}, second code {b}. Regulation score for the key order: {sc}.\n"
        f"Match data (ESPN):\n{json.dumps(context, ensure_ascii=False, indent=1)}"
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": ENTRY_SCHEMA}},
    )
    if response.stop_reason == "refusal":
        print(f"  {key}: model declined ({response.stop_details and response.stop_details.category})")
        return None
    if response.stop_reason == "max_tokens":
        print(f"  {key}: truncated — skipping")
        return None
    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)


def entry_literal(e):
    ga = ",".join(json.dumps(x, ensure_ascii=False) for x in e["ga"])
    gb = ",".join(json.dumps(x, ensure_ascii=False) for x in e["gb"])
    note = json.dumps(e["note"], ensure_ascii=False)
    return f'{{s:{json.dumps(e["s"])},ga:[{ga}],gb:[{gb}],note:{note}}}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", nargs="*", help="only these sorted-pair keys (e.g. 'ARG|ENG')")
    ap.add_argument("--apply", action="store_true",
                    help="insert drafts for keys MISSING from RESULTS into index.html")
    args = ap.parse_args()

    html = INDEX.read_text(encoding="utf-8")
    _, entries = parse_results_block(html)
    stage_labels = dict(re.findall(r'"([A-Z_]+)": "([^"]+)"', re.search(r"const FD_STAGE_LABELS=\{(.*?)\};", html).group(1)))

    targets = []
    for key, hc, ac, sc, st in finished_knockout_pairs(html):
        if args.keys and key not in args.keys:
            continue
        existing = entries.get(key)
        if existing and "ga:[" in existing:
            continue  # already has scorer detail — nothing to draft
        targets.append((key, hc, ac, sc, stage_labels.get(st, st)))
    if not targets:
        print("nothing to draft — all finished ties have detailed RESULTS entries")
        return

    print(f"drafting {len(targets)} entries with {MODEL}...")
    index = espn_event_index()
    examples = style_examples(entries)
    client = anthropic.Anthropic()

    drafts = {}
    for key, hc, ac, sc, label in targets:
        event = index.get(frozenset((hc, ac)))
        if not event:
            print(f"  {key}: no ESPN event found — skipped")
            continue
        # sc is in KO_META home/away order; re-express for the sorted key
        gh, ga_ = re.match(r"(\d+)-(\d+)", sc).groups()
        a, _ = sorted([hc, ac])
        key_sc = f"{gh}-{ga_}" if hc == a else f"{ga_}-{gh}"
        entry = draft_entry(client, key, label, key_sc, match_context(event), examples)
        if entry:
            drafts[key] = entry
            print(f"  {key}: {entry['s']}  {entry['note'][:70]}")

    lines = ["// Draft RESULTS entries generated by build_recaps.py (Claude Opus 4.8,",
             "// grounded in ESPN match summaries). Review, then paste into RESULTS in",
             "// index.html — or re-run with --apply to insert keys not already present.",
             "const RECAPS_SUGGESTED={"]
    for key, e in drafts.items():
        lines.append(f'  "{key}":{entry_literal(e)},')
    lines.append("};")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT.name} ({len(drafts)} drafts)")

    if args.apply:
        missing = {k: e for k, e in drafts.items() if k not in entries}
        if not missing:
            print("--apply: no missing keys (existing entries are never overridden)")
            return
        insert = "".join(f'  "{k}":{entry_literal(e)},\n' for k, e in missing.items())
        anchor = re.search(r"(const RESULTS=\{.*?\n)(\};)", html, re.S)
        html = html[:anchor.end(1)] + insert + html[anchor.end(1):]
        INDEX.write_text(html, encoding="utf-8")
        print(f"--apply: inserted {len(missing)} new entries into index.html")


if __name__ == "__main__":
    main()
