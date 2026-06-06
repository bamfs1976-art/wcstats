WC26 raw data drop

Put the raw source files in this folder. I parse them offline, no network
needed. Anything you cannot get, leave out, I will mark it null and flag it
in data_sources. Do not edit or clean the files, raw is fine, I adapt the
parser to whatever shape they arrive in.

WHAT TO DROP

1. SOFASCORE QUALIFICATION, PLAYER LEVEL
   For player yellow cards and fouls. Save the JSON responses from the
   statistics endpoint. One file per confederation is ideal.
   Suggested names:
     sofa_player_UEFA.json
     sofa_player_CONMEBOL.json
     sofa_player_CONCACAF.json
     sofa_player_CAF.json
     sofa_player_AFC.json
   Each file is the raw JSON from a URL like:
     https://www.sofascore.com/api/v1/unique-tournament/11/season/69427/statistics?limit=100&offset=0&order=-yellowCards&accumulation=total&group=summary&fields=yellowCards,redCards,yellowRedCards,fouls,wasFouled,minutesPlayed,appearances
   If a confederation needs more than one page, append offset 100, 200 and
   save them as _p1, _p2 and so on. I will stitch the pages.

2. SOFASCORE QUALIFICATION, TEAM LEVEL  (best source for the tool)
   For the TEAMS array cards-against and fouls-made per game. The team
   statistics endpoint gives matches played, fouls and cards per team
   directly, which is cleaner than aggregating players.
   Suggested names:
     sofa_team_UEFA.json ... sofa_team_AFC.json
   Endpoint shape:
     https://www.sofascore.com/api/v1/unique-tournament/11/season/69427/team/statistics?...
   If you can only get player-level, that is fine, I will aggregate to team
   totals and derive per game from matches played, and I will flag the basis
   so the numbers stay honest.

3. CLUB SEASON 2025-26, CSV
   The Kaggle dataset file. Drop the CSV as is.
   Suggested name:
     club_2025_26.csv

4. FIFA CONFIRMED SQUADS, PDF
   The squad lists PDF, used only to filter to confirmed WC2026 players.
   Suggested name:
     SquadLists-English.pdf

WHEN THE FILES ARE IN
Tell me they are dropped. I will read what is here, report exactly what I
found and what is missing, then run the join, the risk scoring and the team
cards-against and fouls-made aggregation, and hand you the CSVs plus the
TEAMS data block for the bookings tool.
