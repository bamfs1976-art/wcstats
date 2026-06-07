ScoutingStats API notes

Reverse-engineered from the site's own calls. Underlying data is Sportmonks.
For research use. Be considerate with request volume. Some responses depend on
being logged in, so harvest in a real browser session and bake the result into
static files rather than calling at runtime.

THE WORKHORSE ENDPOINT
GET https://scoutingstats.ai/api/hub/{LEAGUE_ID}/squad-form-stats

Query parameters
  season_id    required for most leagues. World Cup (732) defaults if omitted,
               other leagues return 400 without it.
  scope        club    = players' club-season stats
               country = players' national-team stats
  page         1-based
  per_page     up to 100 works
  sort_by      any stat key with sortable:true (see categories), e.g.
               fouls_committed_p90, yellow_cards, goals_p90, tackles_p90
  sort_order   asc | desc
  min_minutes  integer filter, use 300+ to cut per-90 noise from tiny samples
  leagues      filter players by the competition they play in, e.g. leagues=8
               returns only players in the Premier League

Response envelope keys
  players, page, per_page, total_count, total_pages, scope, season_label,
  leagues_available, stat_categories, is_logged_in, is_premium, can_filter

WORLD CUP HUB (league 732, season_id 26618)
  scope=club    1163 players, 2025/26 club season
  scope=country  922 players, 2026 national-team form (425 with 300+ min)
  Both carry the full metric set per player. This is the source for the
  WC26 Bookings Desk player layer.

PER-PLAYER METRICS (45 keys, most also have a _p90 variant, ~90 fields)
  Attacking  goals, assists, xg, xgot, shots, shots_on_target,
             chances_created, big_chances_created, big_chances_missed, offsides
  Defending  tackles, interceptions, blocks, clearances, ball_recoveries,
             duels_won, duels_won_pct, aerials_won
  Discipline fouls_committed, fouls_drawn, yellow_cards, red_cards,
             penalty_won, penalty_committed
  Dribbling  dribbles, dribble_attempts, dribble_success_rate, touches,
             dispossessed, possession_lost
  Passing    key_passes, passes, passes_accurate, pass_accuracy,
             passes_final_third, crosses, long_balls, through_balls
  Goalkeeper saves, saves_insidebox, goals_conceded, penalty_saved
  General    appearances, minutes_played, rating
  Plus identity: player_name, player_id, nation, nation_code, nation_flag,
  club_name, team_name, position, detailed_position, age, club_image.

LEAGUES AVAILABLE (87 competitions, Sportmonks IDs)
  Full list in scoutingstats_api_catalogue.json. Major ones:
  Champions League 2, Premier League 8, La Liga 564, Bundesliga 82,
  Serie A 384, Ligue 1 301, Eredivisie 72, Liga Portugal 462,
  Championship 9, MLS 779, Liga MX 743, Saudi Pro League 944, Super Lig 600,
  Europa League 5, Conference League 2286, Copa Libertadores 1122,
  Persian Gulf Pro League 902, K League 1 1034, A-League 1356, plus domestic
  cups and super cups.

CONFIRMED vs UNCONFIRMED
  Confirmed: WC hub club and country scopes, the leagues= filter, sorting and
  pagination across the full metric set.
  Unconfirmed: querying a non-WC league hub end to end. It accepts the path but
  needs that league's season_id, which is not exposed by this endpoint. The
  leagues= filter on the WC hub only slices WC players, not the whole league.
  To pull a full league you would need its season_id, likely from another site
  call or the Sportmonks season catalogue.

WIDER FOOTBALL DATA IDEAS
  - Booking and foul models for any competition the platform exposes.
  - Cross-competition player comparison on a single consistent metric set.
  - Squad recruitment or scouting boards, per-90 normalised.
  - Discipline or tackling leaderboards by league.
  - Reuse the same harvest-in-browser then bake-static pattern used here.
