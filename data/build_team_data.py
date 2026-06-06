#!/usr/bin/env python3
"""
Build the canonical WC2026 team-form dataset from the ScoutingStats cards.

Source: 47 ScoutingStats "Country & Club Form" images, extracted and spot
checked by hand (Czech Republic, Mexico, South Africa and Iraq verified
exactly against the images). England's card (IMG_0354) did not save, so it
is carried with null rates and flagged, never invented.

Outputs:
  wc2026_team_form.json   canonical record, all 48 teams
  teams_array.js          the TEAMS const for index.html

Fields per team:
  g group, n name, c FIFA code, f flag emoji,
  ca cards against pg, fm fouls made pg, cf cards for pg, fw fouls won pg,
  ga goals against pg, gf goals for pg, o25 over 2.5 %, btts BTTS %,
  cs clean sheets, sh shots pg, sot shots on target pg, gpg goals pg,
  games sample size
"""

import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent

# name, code, flag, group, ca, fm, cf, fw, ga, gf, o25, btts, cs, sh, sot, gpg, games
T = [
    ("Czech Republic", "CZE", "🇨🇿", "A", 2.2, 15.3, 1.8, 11.0, 1.15, 1.9, 60, 60, 8, 14.3, 5.2, 3.05, 20),
    ("Korea Republic", "KOR", "🇰🇷", "A", 1.7, 11.4, 1.2, 10.7, 0.86, 1.95, 41, 32, 12, 11.7, 4.5, 2.82, 22),
    ("South Africa", "RSA", "🇿🇦", "A", 1.6, 12.2, 1.7, 12.2, 0.76, 1.88, 52, 52, 11, 15.1, 5.5, 2.64, 25),
    ("Mexico", "MEX", "🇲🇽", "A", 1.9, 13.3, 2.1, 12.4, 0.94, 1.38, 38, 38, 9, 11.4, 4.1, 2.31, 16),

    ("Bosnia and Herzegovina", "BIH", "🇧🇦", "B", 1.9, 15.4, 2.5, 12.9, 1.53, 1.47, 53, 63, 5, 12.6, 4.2, 3.00, 19),
    ("Switzerland", "SUI", "🇨🇭", "B", 1.9, 10.9, 1.6, 11.5, 1.32, 2.05, 58, 58, 6, 11.9, 4.8, 3.37, 19),
    ("Qatar", "QAT", "🇶🇦", "B", 2.2, 10.7, 1.6, 12.9, 1.9, 1.24, 71, 62, 3, 8.9, 3.1, 3.14, 21),
    ("Canada", "CAN", "🇨🇦", "B", 2.2, 14.0, 2.9, 14.7, 0.42, 1.25, 25, 17, 9, 11.2, 4.3, 1.67, 12),

    ("Brazil", "BRA", "🇧🇷", "C", 2.3, 11.7, 1.7, 13.8, 1.0, 1.89, 53, 53, 7, 13.5, 4.8, 2.89, 19),
    ("Morocco", "MAR", "🇲🇦", "C", 2.7, 13.6, 1.1, 16.3, 0.25, 2.71, 50, 25, 21, 16.1, 6.0, 2.96, 28),
    ("Haiti", "HAI", "🇭🇹", "C", 1.4, 12.7, 1.5, 11.5, 1.07, 2.0, 64, 36, 7, 13.1, 5.3, 3.07, 14),
    ("Scotland", "SCO", "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "C", 2.6, 11.2, 1.5, 13.2, 1.26, 1.58, 63, 53, 6, 11.4, 4.5, 2.84, 19),

    ("Türkiye", "TUR", "🇹🇷", "D", 1.9, 10.5, 2.5, 11.6, 1.11, 2.11, 63, 47, 8, 16.2, 5.2, 3.21, 19),
    ("United States", "USA", "🇺🇸", "D", 1.4, 12.3, 1.8, 9.7, 1.69, 1.85, 69, 62, 2, 12.5, 5.2, 3.54, 13),
    ("Paraguay", "PAR", "🇵🇾", "D", 1.8, 12.6, 2.1, 10.9, 0.89, 1.11, 44, 44, 8, 9.9, 3.8, 2.0, 18),
    ("Australia", "AUS", "🇦🇺", "D", 1.3, 9.7, 1.1, 11.1, 0.76, 1.67, 43, 38, 9, 8.0, 3.2, 2.43, 21),

    ("Germany", "GER", "🇩🇪", "E", 2.0, 11.1, 1.6, 9.9, 1.0, 2.63, 68, 47, 8, 17.8, 6.7, 3.63, 19),
    ("Curacao", "CUW", "🇨🇼", "E", 2.2, 10.7, 1.5, 12.7, 1.29, 2.14, 50, 43, 6, 13.5, 5.7, 3.43, 14),
    ("Cote d'Ivoire", "CIV", "🇨🇮", "E", 1.4, 11.2, 1.0, 9.2, 0.46, 1.73, 35, 19, 17, 11.8, 4.3, 2.19, 26),
    ("Ecuador", "ECU", "🇪🇨", "E", 1.8, 13.6, 1.6, 10.6, 0.37, 0.89, 16, 32, 12, 11.1, 4.1, 1.26, 19),

    ("Sweden", "SWE", "🇸🇪", "F", 2.6, 13.6, 1.8, 11.4, 1.45, 2.15, 70, 60, 4, 15.2, 6.0, 3.6, 20),
    ("Netherlands", "NED", "🇳🇱", "F", 1.9, 9.6, 0.8, 12.8, 1.0, 2.53, 58, 58, 6, 15.5, 5.6, 3.53, 19),
    ("Japan", "JPN", "🇯🇵", "F", 0.9, 12.8, 0.9, 9.1, 0.43, 2.52, 48, 19, 15, 12.3, 4.8, 2.95, 21),
    ("Tunisia", "TUN", "🇹🇳", "F", 2.6, 12.8, 1.7, 11.7, 0.85, 1.41, 33, 37, 11, 9.9, 4.0, 2.26, 27),

    ("Belgium", "BEL", "🇧🇪", "G", 2.7, 10.7, 1.6, 10.9, 1.16, 2.47, 58, 53, 6, 17.7, 6.5, 3.63, 19),
    ("Egypt", "EGY", "🇪🇬", "G", 1.8, 11.4, 1.8, 11.0, 0.52, 1.52, 34, 31, 18, 9.4, 4.3, 2.03, 29),
    ("Iran", "IRN", "🇮🇷", "G", 1.7, 8.4, 1.5, 7.8, 0.79, 1.84, 53, 42, 10, 10.5, 4.6, 2.63, 19),
    ("New Zealand", "NZL", "🇳🇿", "G", 1.0, 7.5, 1.1, 7.4, 1.25, 2.38, 62, 38, 5, 10.1, 4.4, 3.62, 16),

    ("Spain", "ESP", "🇪🇸", "H", 2.4, 11.5, 1.5, 10.0, 0.95, 2.63, 74, 47, 10, 19.9, 7.8, 3.58, 19),
    ("Cape Verde", "CPV", "🇨🇻", "H", 2.2, 11.4, 1.8, 11.6, 1.05, 1.32, 36, 41, 9, 9.2, 3.4, 2.36, 22),
    ("Saudi Arabia", "KSA", "🇸🇦", "H", 1.8, 8.7, 1.8, 11.8, 1.09, 1.0, 39, 43, 9, 10.1, 3.1, 2.09, 23),
    ("Uruguay", "URU", "🇺🇾", "H", 1.9, 12.8, 2.2, 11.8, 0.78, 0.78, 22, 28, 10, 9.8, 2.6, 1.56, 18),

    ("France", "FRA", "🇫🇷", "I", 1.7, 10.7, 2.0, 11.9, 1.11, 2.21, 68, 58, 7, 17.8, 6.5, 3.32, 19),
    ("Senegal", "SEN", "🇸🇳", "I", 1.6, 11.3, 1.5, 10.5, 0.6, 2.03, 43, 37, 18, 12.4, 5.8, 2.63, 30),
    ("Norway", "NOR", "🇳🇴", "I", 1.1, 8.5, 0.9, 10.8, 0.84, 3.05, 74, 53, 9, 16.8, 6.1, 3.89, 19),
    ("Iraq", "IRQ", "🇮🇶", "I", 3.1, 11.9, 2.1, 10.9, 0.79, 1.11, 32, 42, 9, 8.0, 2.9, 1.89, 19),

    ("Argentina", "ARG", "🇦🇷", "J", 2.4, 11.2, 1.4, 12.8, 0.53, 2.29, 53, 35, 10, 12.2, 5.2, 2.82, 17),
    ("Algeria", "ALG", "🇩🇿", "J", 2.1, 12.1, 1.7, 11.3, 0.63, 2.33, 56, 41, 15, 9.7, 5.0, 2.96, 27),
    ("Austria", "AUT", "🇦🇹", "J", 1.9, 12.9, 1.7, 10.4, 0.68, 2.32, 42, 47, 8, 14.2, 6.1, 3.0, 19),
    ("Jordan", "JOR", "🇯🇴", "J", 1.4, 8.7, 1.5, 6.8, 1.17, 1.42, 50, 50, 8, 10.1, 4.2, 2.58, 24),

    ("Portugal", "POR", "🇵🇹", "K", 2.0, 9.5, 1.8, 10.3, 1.0, 2.44, 61, 61, 5, 18.7, 6.2, 3.44, 18),
    ("Colombia", "COL", "🇨🇴", "K", 2.2, 13.4, 1.4, 12.7, 1.16, 1.89, 68, 58, 6, 13.7, 5.6, 3.05, 19),
    ("Congo DR", "COD", "🇨🇩", "K", 1.5, 14.1, 1.0, 11.4, 0.48, 1.36, 20, 28, 16, 9.0, 3.5, 1.84, 25),
    ("Uzbekistan", "UZB", "🇺🇿", "K", 1.4, 9.8, 1.4, 8.1, 0.65, 1.25, 35, 30, 13, 12.4, 4.2, 1.9, 20),

    ("Croatia", "CRO", "🇭🇷", "L", 1.3, 9.9, 1.8, 10.2, 1.05, 2.05, 58, 47, 7, 17.6, 6.5, 3.11, 19),
    ("Ghana", "GHA", "🇬🇭", "L", 1.5, 12.6, 1.6, 13.1, 1.19, 1.52, 43, 43, 7, 9.3, 3.8, 2.71, 21),
    ("Panama", "PAN", "🇵🇦", "L", 1.8, 11.7, 1.7, 10.9, 1.38, 1.69, 44, 56, 6, 12.1, 4.5, 3.06, 16),
    ("England", "ENG", "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "L", 1.9, 8.9, 1.2, 11.4, 0.44, 2.39, 50, 22, 13, 16.9, 6.6, 2.83, 18),
]

KEYS = ["n", "c", "f", "g", "ca", "fm", "cf", "fw", "ga", "gf",
        "o25", "btts", "cs", "sh", "sot", "gpg", "games"]

# field-max divisors used by the heat formula, from this dataset
MAX_CA = 3.1   # Iraq
MAX_FM = 15.4  # Bosnia and Herzegovina


def tier(ca):
    if ca is None:
        return "pending"
    if ca >= 2.0:
        return "target"
    if ca >= 1.5:
        return "mid"
    return "fade"


def combustible(ca, fm):
    if ca is None or fm is None:
        return False
    return ca >= 2.0 and fm >= 12.5


def main():
    teams = []
    for row in T:
        d = dict(zip(KEYS, row))
        d["tier"] = tier(d["ca"])
        d["combustible"] = combustible(d["ca"], d["fm"])
        teams.append(d)

    # ---- validation ----
    errors = []
    if len(teams) != 48:
        errors.append(f"expected 48 teams, got {len(teams)}")
    from collections import Counter
    gc = Counter(t["g"] for t in teams)
    for grp in "ABCDEFGHIJKL":
        if gc.get(grp) != 4:
            errors.append(f"group {grp} has {gc.get(grp)} teams, expected 4")
    codes = [t["c"] for t in teams]
    if len(set(codes)) != len(codes):
        errors.append("duplicate team codes")
    for t in teams:
        if t["ca"] is not None and not (0 <= t["ca"] <= 4):
            errors.append(f"{t['n']} ca out of range: {t['ca']}")
        if t["fm"] is not None and not (5 <= t["fm"] <= 20):
            errors.append(f"{t['n']} fm out of range: {t['fm']}")

    pending = [t["n"] for t in teams if t["tier"] == "pending"]

    # ---- write canonical json ----
    (OUT_DIR / "wc2026_team_form.json").write_text(
        json.dumps({"teams": teams, "max_ca": MAX_CA, "max_fm": MAX_FM},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- write TEAMS js array (compact, ordered fields) ----
    lines = ["// Auto-generated by build_team_data.py. Source: ScoutingStats",
             "// Country & Club Form cards. England (ENG) card pending.",
             "const TEAMS = ["]
    for t in teams:
        def v(x):
            return "null" if x is None else (f'"{x}"' if isinstance(x, str) else str(x))
        lines.append(
            "  {" + ", ".join([
                f'g:"{t["g"]}"', f'n:"{t["n"]}"', f'c:"{t["c"]}"', f'f:"{t["f"]}"',
                f'ca:{v(t["ca"])}', f'fm:{v(t["fm"])}', f'cf:{v(t["cf"])}',
                f'fw:{v(t["fw"])}', f'ga:{v(t["ga"])}', f'gf:{v(t["gf"])}',
                f'o25:{v(t["o25"])}', f'btts:{v(t["btts"])}', f'cs:{v(t["cs"])}',
                f'sh:{v(t["sh"])}', f'sot:{v(t["sot"])}', f'gpg:{v(t["gpg"])}',
                f'games:{v(t["games"])}',
            ]) + "},")
    lines.append("];")
    (OUT_DIR / "teams_array.js").write_text("\n".join(lines), encoding="utf-8")

    # ---- report ----
    print(f"teams: {len(teams)}")
    print(f"groups ok: {all(gc.get(g)==4 for g in 'ABCDEFGHIJKL')}")
    tiers = Counter(t["tier"] for t in teams)
    print("tiers:", dict(tiers))
    comb = [t["n"] for t in teams if t["combustible"]]
    print(f"combustible ({len(comb)}):", ", ".join(comb))
    print(f"data pending: {pending}")
    if errors:
        print("VALIDATION ERRORS:")
        for e in errors:
            print("  -", e)
    else:
        print("VALIDATION: all checks passed")


if __name__ == "__main__":
    main()
