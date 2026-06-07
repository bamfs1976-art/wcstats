# WC26 Bookings Desk

A single-file tool for World Cup 2026 player-bookings analysis. Team discipline rates, a same-group matchup heat calculator and a referee watchlist.

## What it is

- One `index.html`, vanilla JavaScript, Tailwind via CDN, no build step, no API keys.
- All 48 team form rates are baked in from ScoutingStats country form cards.
- Targets and per-team notes save to your browser under `wc26_desk_v2`.

## Tabs

- **Teams** sortable table of cards against, fouls made and cards for per game, with tier badges and a combustible flag. Star your targets, add notes.
- **Matchups** pick Team A, Team B is locked to the same group so every pairing is a real fixture. Shows the kick-off date, time in BST and venue. Any fixture falling 5 to 14 July 2026 also shows Seychelles time (SCT, UTC+4). Note the current schedule is the group stage, all in June, so the Seychelles line activates only when knockout fixtures are added. Transparent heat score out of 10. Below the heat, a per-fixture player layer ranks each squad by club-form booking risk (yellow rate per 90 weighted double plus fouls per 90), a risk-by-line positional view, and a PNG export of the matchup card.
- **Referees** a working watchlist, figures flagged where the sample is small.
- **Tracker** log each pick with odds and stake, settle it won, lost or void, and see a running hit-rate, staked total, P/L and ROI. For the group-stage hit-rate trial.
- **Guide** the method, the tiers, the heat formula and the known limits.

## Tiers and heat

Tiers run off cards against per game. Target 2.0 and above, mid 1.5 to 1.9, fade 1.4 and below. Combustible means 2.0 plus cards against and 12.5 plus fouls made.

Heat for a fixture:

    heat = (avgCards / 3.1 × 6) + (avgFouls / 15.4 × 4), clamped 0 to 10

Cards weighted 60 per cent, fouls 40 per cent. The divisors are the field maximums (Iraq 3.1 cards against, Bosnia and Herzegovina 15.4 fouls made).

## Deploy to Netlify

Drag the project root to drop.netlify.com, or connect the repo. Publish directory is the root, no build command. The `data` folder holds the working sources and is kept out of the published site by `.gitignore`. For a Netlify Drop, drag only `index.html` and the support files, not the `data` folder.

## Data notes

- Team rates are per game from ScoutingStats country form. Sample sizes vary from 12 to 30 games.
- Spot checked by hand against the source cards: Czech Republic, Mexico, South Africa and Iraq, all exact.
- All 48 teams carry form data, including England (Group L, 1.9 cards against, 8.9 fouls made, mid tier).
- Referee figures are blended estimates with varying samples, several small. The list fills out as FIFA confirms appointments.
- The per-fixture player layer has two sources, both ScoutingStats: 2025-26 club form (broad league coverage, 1,163 players across all 48 nations, so it reaches non-European-league players such as Edson Álvarez at Fenerbahçe) for the risk ranking, and qualifying-campaign leaders (most cards and most fouls per team). Qualifying figures are a separate basis from the country-form team rates and never feed the tiers or heat.

## Working data and pipelines

The `data` folder holds the source material and the scripts that built the dataset:

- `build_team_data.py` builds the canonical `wc2026_team_form.json` and the `TEAMS` array from the ScoutingStats cards, with validation.
- `build_squad_dataset.py` parses the FIFA squad PDF and joins to club-form discipline.
- `club_form_discipline.py` builds the club-form player risk dataset.
- `wc2026_discipline_pipeline.py` the full Sofascore plus club plus squad pipeline, for running where there is network.
