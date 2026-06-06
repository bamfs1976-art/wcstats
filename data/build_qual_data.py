#!/usr/bin/env python3
"""
Build the qualifying-campaign discipline dataset (QUAL) from the 48
ScoutingStats "Team Cheat Sheet" cards (World Cup qualifying campaign,
players with at least 180 minutes).

This is a SEPARATE basis from the TEAMS country-form data (which is all
internationals from the ScoutingStats country cards). Qualifying cards
against differ from country-form cards against, so this never overwrites
TEAMS. It feeds the per-fixture player layer with international card leaders.

Per team: qualifying team per-game fouls/cards, and the qualifying leaders
for most fouls committed, most fouls won and most yellow cards per 90.

Hand spot-checked against the cards: Japan, South Korea, South Africa exact.
Output: qual_array.js holding QUAL keyed by team code.
"""

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent
TEAMFORM = DATA / "wc2026_team_form.json"
OUT = DATA / "qual_array.js"

NAME2CODE = {
    "Mexico": "MEX", "South Korea": "KOR", "South Africa": "RSA", "Czechia": "CZE",
    "Canada": "CAN", "Bosnia and Herzegovina": "BIH", "Qatar": "QAT", "Switzerland": "SUI",
    "Brazil": "BRA", "Morocco": "MAR", "Scotland": "SCO", "Haiti": "HAI",
    "USA": "USA", "Paraguay": "PAR", "Australia": "AUS", "Türkiye": "TUR",
    "Germany": "GER", "Curaçao": "CUW", "Côte d'Ivoire": "CIV", "Ecuador": "ECU",
    "Netherlands": "NED", "Japan": "JPN", "Sweden": "SWE", "Tunisia": "TUN",
    "Belgium": "BEL", "Egypt": "EGY", "IR Iran": "IRN", "New Zealand": "NZL",
    "Spain": "ESP", "Cabo Verde": "CPV", "Saudi Arabia": "KSA", "Uruguay": "URU",
    "France": "FRA", "Senegal": "SEN", "Iraq": "IRQ", "Norway": "NOR",
    "Argentina": "ARG", "Austria": "AUT", "Algeria": "ALG", "Jordan": "JOR",
    "Portugal": "POR", "Congo DR": "COD", "Uzbekistan": "UZB", "Colombia": "COL",
    "England": "ENG", "Croatia": "CRO", "Ghana": "GHA", "Panama": "PAN",
}

# name, qca, qcf, qfc, qfw, [mf_player,mf_v], [mw_player,mw_v], [yc_player,yc_v]
# qca qualifying cards against pg, qcf cards for pg, qfc fouls committed pg,
# qfw fouls won pg. mf most fouls committed/90, mw most fouls won/90,
# yc most yellow cards/90. None where the card omitted the row.
R = [
 ("Mexico",2.50,2.17,13.50,10.70,["Raúl Jiménez",2.20],["Gilberto Mora",2.00],["César Montes",0.61]),
 ("South Korea",2.57,1.00,9.19,9.25,["Lee Taeseok",1.93],["Hwang Hee-Chan",1.94],["Lee Taeseok",0.49]),
 ("South Africa",1.89,1.45,12.12,13.78,["Thalente Mbatha",2.33],["Sphepelo Sithole",2.11],["Teboho Mokoena",0.34]),
 ("Czechia",2.30,0.90,15.60,9.40,["Tomáš Chorý",2.94],["Lukáš Černý",2.90],["Jaroslav Zelený",0.27]),
 ("Canada",2.50,1.50,12.00,14.20,["Nathan Saliba",2.73],["Richie Laryea",3.33],["Jacob Shaffelburg",0.77]),
 ("Bosnia and Herzegovina",2.60,2.80,17.70,12.90,["Ivan Šunjić",3.29],["Kerim Alajbegović",2.53],["Dženis Burnić",0.45]),
 ("Qatar",2.78,1.95,10.23,13.34,["Mohammad Al Mannai",3.50],["Edmilson Junior",5.50],["Mohammad Al Mannai",1.00]),
 ("Switzerland",1.67,0.67,9.67,12.50,["Fabian Rieder",1.58],["Breel Embolo",3.52],["Dan Ndoye",0.21]),
 ("Brazil",2.06,2.33,12.73,14.73,["Matheus Cunha",2.96],["Neymar",2.86],["Lucas Paquetá",0.82]),
 ("Morocco",2.63,1.38,9.88,9.50,["Noussair Mazraoui",2.00],["Brahim Díaz",1.80],["Sofyan Amrabat",0.35]),
 ("Scotland",2.34,2.00,12.67,12.50,["Lewis Ferguson",3.00],["John McGinn",3.00],["Lewis Ferguson",0.60]),
 ("Haiti",1.60,1.50,14.60,12.60,["Josue Casimir",3.64],["Jean Ricner Bellegarde",3.26],["Hannes Delcroix",0.40]),
 ("USA",1.50,1.50,11.50,11.20,["Malik Tillman",2.50],["Malik Tillman",2.50],["Tyler Adams",0.50]),
 ("Paraguay",2.12,2.12,13.73,9.73,["Matías Galarza",2.78],["Alex Arce",2.86],["Gustavo Velásquez",0.53]),
 ("Australia",1.19,1.50,10.13,10.75,["Connor Metcalfe",1.76],["Ajdin Hrustic",3.21],["Alessandro Circati",0.25]),
 ("Türkiye",1.63,2.63,9.25,10.75,["Barış Alper Yılmaz",3.75],["Arda Güler",2.20],["İsmail Yüksek",0.56]),
 ("Germany",2.34,1.34,12.00,9.50,["Nick Woltemade",2.25],["Joshua Kimmich",1.70],["Leon Goretzka",0.21]),
 ("Curaçao",1.90,1.30,12.60,11.40,["Godfried Roemeratoe",2.99],["Jürgen Locadia",2.73],["Gervane Kastaneer",0.81]),
 ("Côte d'Ivoire",1.20,1.00,14.10,11.50,None,None,["Nicolas Pépé",0.44]),
 ("Ecuador",2.17,1.34,12.89,10.84,["Gonzalo Plata",2.41],["Kevin Rodríguez",4.46],["Angelo Preciado",0.34]),
 ("Netherlands",2.00,0.75,10.00,11.38,["Jan Paul van Hecke",2.56],["Cody Gakpo",1.80],["Jan Paul van Hecke",1.03]),
 ("Japan",1.34,0.54,11.27,8.27,["Ayumu Seko",2.00],["Ayase Ueda",1.70],["Daizen Maeda",0.31]),
 ("Sweden",2.00,2.00,13.88,12.25,["Jesper Karlström",3.16],["Daniel Svensson",1.89],["Jesper Karlström",0.58]),
 ("Tunisia",2.20,1.90,17.60,14.20,None,None,["Yan Valery",0.25]),
 ("Belgium",2.88,1.13,9.63,10.25,["Thomas Meunier",2.31],["Jeremy Doku",3.35],["Thomas Meunier",0.52]),
 ("Egypt",1.70,1.40,14.50,10.50,None,None,["Marwan Attia",0.59]),
 ("IR Iran",1.38,1.57,6.32,6.19,["Alireza Jahanbakhsh",1.40],["Saleh Hardani",1.10],["Ramin Rezaeian",0.34]),
 ("New Zealand",0.80,0.20,None,None,None,None,["Chris Wood",0.28]),
 ("Spain",0.84,0.67,9.84,6.34,["Mikel Merino",2.32],["Mikel Merino",1.74],["Álex Baena",0.44]),
 ("Cabo Verde",2.20,1.10,15.80,14.00,None,None,["Hélio Varela",0.47]),
 ("Saudi Arabia",2.34,1.67,9.17,10.56,["Abdullah Al Hamdan",2.55],["Abdullah Al Hamdan",2.55],["Ziyad Al Johani",0.43]),
 ("Uruguay",2.34,2.12,13.17,12.39,["Nicolás De La Cruz",2.38],["Nicolás De La Cruz",3.81],["Matías Viña",0.44]),
 ("France",1.50,1.17,10.17,12.17,["Manu Koné",1.80],["Michael Olise",2.32],["Manu Koné",0.52]),
 ("Senegal",1.70,1.00,13.60,13.30,None,None,["Pape Gueye",0.57]),
 ("Iraq",2.80,1.40,8.45,7.55,["Ali Al Hamadi",1.40],["Youssef Amyn",1.67],["Mustafa Saadoon",0.74]),
 ("Norway",1.00,1.00,8.88,10.63,["Julian Ryerson",1.63],["Oscar Bobb",3.31],["Patrick Berg",0.25]),
 ("Argentina",2.78,1.62,10.73,15.56,["Lautaro Martínez",2.32],["Giovani Lo Celso",4.74],["Leandro Paredes",0.50]),
 ("Austria",2.13,1.75,14.38,10.63,["Stefan Posch",3.11],["Romano Schmid",2.60],["David Alaba",0.60]),
 ("Algeria",1.90,1.60,13.00,11.50,None,None,["Ramy Bensebaini",0.50]),
 ("Jordan",1.44,1.38,9.50,6.94,["Amer Jamous",2.50],["Musa Al-Taamari",1.56],["Mohammad Abu Hasheesh",0.37]),
 ("Portugal",2.17,1.50,7.00,8.00,["João Cancelo",1.57],["Nuno Mendes",2.21],["João Félix",0.47]),
 ("Congo DR",1.25,0.92,15.00,10.50,None,None,["Fiston Mayele",0.40]),
 ("Uzbekistan",1.50,1.50,7.00,5.32,["Akmal Mozgovoy",1.46],["Otabek Shukurov",1.25],["Akmal Mozgovoy",0.49]),
 ("Colombia",1.89,2.00,14.06,11.56,["Jorge Carrascal",3.72],["Jorge Carrascal",3.31],["Jhon Córdoba",0.54]),
 ("England",1.50,0.75,9.50,9.75,["Elliot Anderson",1.95],["Jude Bellingham",2.54],["Jude Bellingham",0.61]),
 ("Croatia",1.38,0.75,8.88,10.38,["Marin Pongračić",3.48],["Petar Sučić",2.08],["Marin Pongračić",0.32]),
 ("Ghana",1.50,1.10,13.40,14.00,None,None,["Kwasi Sibo",0.36]),
 ("Panama",1.90,1.40,14.10,11.60,["Azarias Londoño",3.81],["Cristian Martínez",2.79],["Anibal Godoy",0.67]),
]


def leader(x):
    if not x:
        return "null"
    return f'{{p:{json.dumps(x[0], ensure_ascii=False)},v:{x[1]}}}'


def main():
    teams = json.loads(TEAMFORM.read_text(encoding="utf-8"))["teams"]
    code2group = {t["c"]: t["g"] for t in teams}
    codes_all = set(code2group)

    seen = set()
    errors = []
    lines = ["// Auto-generated by build_qual_data.py from ScoutingStats Team",
             "// Cheat Sheets (WC qualifying campaign, 180+ min players).",
             "// Separate basis from TEAMS country form. Player card leaders.",
             "const QUAL = {"]
    for rec in R:
        name, qca, qcf, qfc, qfw, mf, mw, yc = rec
        code = NAME2CODE.get(name)
        if not code:
            errors.append(f"no code for {name}")
            continue
        if code not in codes_all:
            errors.append(f"code {code} not in team data")
        seen.add(code)
        def v(x):
            return "null" if x is None else x
        lines.append(
            f'  {code}:{{qca:{v(qca)},qcf:{v(qcf)},qfc:{v(qfc)},qfw:{v(qfw)},'
            f'mf:{leader(mf)},mw:{leader(mw)},yc:{leader(yc)}}},')
    lines.append("};")
    OUT.write_text("\n".join(lines), encoding="utf-8")

    missing = codes_all - seen
    print(f"teams with qual data: {len(seen)}/48")
    if missing:
        print("MISSING:", sorted(missing))
    print(f"output: {OUT.name} ({OUT.stat().st_size/1024:.1f} KB)")
    # quick sanity: opener cards
    for c in ["RSA", "MEX", "ENG", "ARG", "BRA"]:
        r = next((x for x in R if NAME2CODE[x[0]] == c), None)
        if r:
            print(f"  {c}: yellows={r[7]} fouls={r[5]}")
    if errors:
        print("ERRORS:", errors)
    else:
        print("VALIDATION: all codes resolved and in team data")


if __name__ == "__main__":
    main()
