# Tron Legacy LE v1.74: service menu, adjustments and audits
Read from the ROM (`trn_174h`). The menu tree, item texts, adjustment table (88 entries), value
labels and audit names come from the ROM's own tables; the value labels were produced by running the
ROM's own formatting code in the emulator. Your MPF service mode can look different, but it should
offer the same options. `config/settings.yaml` has every adjustment as an MPF setting.

## Buttons

The coin door has four service buttons: BACK, MINUS, PLUS and SELECT (SAM dedicated switches).
SELECT enters the menu from attract mode and opens an item, MINUS/PLUS move or change a value, BACK leaves.
Every menu ends with a return item, EXIT SERVICE MENU and DISPLAY HELP SCREEN.

## Menu tree

Items marked *(Tron)* are added by the game code; the rest are the Stern SAM operating system.
Items marked *(only when …)* are hidden unless that feature is on.
- GO TO DIAGNOSTICS MENU
  - GO TO SWITCH MENU
    - SWITCH TEST
    - ACTIVE SWITCH TEST
    - SWITCH ALERTS
  - GO TO COIL MENU
    - SINGLE COIL TEST
    - CYCLING COIL TEST
  - GO TO FLASH LAMPS MENU
    - SINGLE FLASH LAMP TEST
    - CYCLING FLASH LAMP TEST
  - GO TO LAMP MENU
    - SINGLE LAMP TEST
    - TEST ALL LAMPS
    - LAMP ROW TEST
    - LAMP COLUMN TEST
  - BALL TROUGH TEST
  - TECHNICIAN ALERTS
  - KNOCKER TEST
  - SOUND/SPEAKER TEST
  - BEGIN BURN-IN
  - DOT MATRIX TEST
  - DISPLAY SOFTWARE ERRORS *(only when errors were logged)*
  - GAME-SPECIFIC TESTS *(Tron)*
    - 3-BANK MOTOR TEST *(Tron)*
    - DISC MOTOR TEST *(Tron)*
    - RECOGNIZER MOTOR TEST *(Tron)*
    - FIBER OPTIC LIGHT TUBE TEST *(Tron)*
- GO TO AUDITS MENU
  - EARNINGS AUDITS
    - audits 1-13
  - STANDARD AUDITS
    - audits 14-72
  - FEATURE AUDITS *(Tron)*
    - audits 73-150
  - DUMP AUDITS TO USB
- GO TO ADJUSTMENTS MENU
  - STANDARD ADJUSTMENTS
    - adjustments 1-64, listed below
  - FEATURE ADJUSTMENTS *(Tron)*
    - adjustments 65-88, listed below
- GO TO UTILITIES MENU
  - GO TO INSTALLS MENU
    - INSTALL EXTRA EASY
    - INSTALL EASY
    - INSTALL MEDIUM
    - INSTALL HARD
    - INSTALL EXTRA HARD
    - INSTALL 3-BALL
    - INSTALL 5-BALL
    - INSTALL COMPETITION
    - INSTALL DIRECTOR'S CUT
    - INSTALL HOME PLAY
    - INSTALL NOVELTY
    - INSTALL ADD-A-BALL
    - INSTALL FACTORY
  - ENTER CUSTOM MESSAGE
  - SET CUSTOM PRICING
  - SET DATE/TIME
  - GO TO RESETS MENU
    - RESET COIN AUDITS
    - RESET GAME AUDITS
    - RESET GRAND CHAMPION
    - RESET HIGH SCORES
    - RESET CREDITS
    - RESET FACTORY SETTINGS
  - GO TO USB MENU
    - UPDATE GAME CODE
    - BACKUP TO USB MEMORY STICK
- GO TO TOURNAMENT MENU *(only when tournament mode is available)*
  - START TOURNAMENT *(only when no tournament runs)*
  - STOP TOURNAMENT *(only when a tournament runs)*
  - VIEW TOURNAMENT DATA *(only when tournament data exists)*
  - SIGN MESSAGES A-B
- GO TO REDEMPTION MENU *(only when a redemption system is installed or the ticket dispenser is on)*
  - INSTALL REDEMPTION SYSTEM *(only when enabled)*
  - CHANGE REDEMPTION SETTINGS *(only when enabled)*
  - VIEW REDEMPTION DATA *(only when enabled)*
  - UNINSTALL REDEMPTION SYSTEM *(only when enabled)*

Notes:
- GO TO FUSE TABLE, SINGLE SWITCH TEST and the three FLOW CHART items open help pages, not a menu.
- ORDERED LAMP TEST (item 37) exists in the ROM but is not in the lamp menu list, so it cannot be reached in v1.74.
- GAME-SPECIFIC TESTS, FEATURE AUDITS and FEATURE ADJUSTMENTS are inserted by the game at run time; their position in the menu is inferred.
- The four lamp tests drive the ROM lamp effects 3 to 7 (`lampfx_003`-`lampfx_007`); BEGIN BURN-IN uses lamp effect 8.
- FIBER OPTIC LIGHT TUBE TEST cycles the two ramp tubes through their colours (ROM function 0x1012b50).

## Adjustments

`setting` is the key in `config/settings.yaml`. Values: the ROM label for each value, "a..b" for a plain number range.

| # | Name | Menu | Default | Values | Setting | Used by |
|---|---|---|---|---|---|---|
| 11 | REPLAY TYPE | standard | AUTO | 0=NONE, 1=FIXED, 2=DYNAMIC, 3=AUTO | `replay_type` |  |
| 12 | REPLAY PERCENTAGE | standard | 10% | 1%..50% step 1 (e.g. 1%, 2%, 3%, 4%) | `replay_percentage` |  |
| 13 | REPLAY AWARD | standard | CREDIT | 0=CREDIT, 1=TICKET, 2=TOKEN, 3=EXTRA BALL | `replay_award` |  |
| 14 | REPLAY LEVELS | standard | 1 | 1..4 step 1 | `replay_levels` |  |
| 15 | AUTO REPLAY START | standard | 20,000,000 | 5,000,000..150,000,000 step 1,000,000 | `auto_replay_start` |  |
| 16 | DYNAMIC REPLAY START | standard | 60,000,000 | 5,000,000..150,000,000 step 1,000,000 | `dynamic_replay_start` |  |
| 17 | REPLAY LEVEL #1 | standard | 15,000,000 | 5,000,000..150,000,000 step 1,000,000 | `replay_level_1` |  |
| 18 | REPLAY LEVEL #2 | standard | 30,000,000 | 5,000,000..300,000,000 step 1,000,000 | `replay_level_2` |  |
| 19 | REPLAY LEVEL #3 | standard | 45,000,000 | 5,000,000..450,000,000 step 1,000,000 | `replay_level_3` |  |
| 20 | REPLAY LEVEL #4 | standard | 60,000,000 | 5,000,000..600,000,000 step 1,000,000 | `replay_level_4` |  |
| 21 | REPLAY BOOST | standard | YES | 0=NO, 1=YES | `replay_boost` |  |
| 22 | SPECIAL LIMIT | standard | 1 | 0=NO SPECIALS, 1=1, 2=2, 3=3, 4=4, 5=5, 6=UNLIMITED | `special_limit` |  |
| 24 | SPECIAL PERCENTAGE | standard | 10% | 1%..50% step 1 (e.g. 1%, 2%, 3%, 4%) | `special_percentage` |  |
| 23 | SPECIAL AWARD | standard | CREDIT | 0=CREDIT, 1=TICKET, 2=TOKEN, 3=POINTS, 4=EXTRA BALL | `special_award` |  |
| 25 | FREE GAME LIMIT | standard | 5 | 0=NO FREE GAMES, 1=1, 2=2, 3=3, 4=4, 5=5, 6=6, 7=7, 8=8, 9=9, 10=UNLIMITED | `free_game_limit` |  |
| 26 | EXTRA BALL LIMIT | standard | 5 | 0=NO EXTRA BALLS, 1=1, 2=2, 3=3, 4=4, 5=5, 6=6, 7=7, 8=8, 9=9, 10=UNLIMITED | `extra_ball_limit` | game_flow, flynns_arcade |
| 27 | EXTRA BALL PERCENTAGE | standard | 25% | 1%..50% step 1 (e.g. 1%, 2%, 3%, 4%) | `extra_ball_percentage` | game_flow, flynns_arcade |
| 28 | GAME PRICING | standard | USA 10 | AUSTRALIA 1..CUSTOM step 1 (e.g. AUSTRALIA 1, AUSTRALIA 2, AUSTRALIA 3, AUSTRALIA 4) | `game_pricing` |  |
| 30 | MATCH PERCENTAGE | standard | 9% | 0=0%, 1=1%, 2=2%, 3=3%, 4=4%, 5=5%, 6=6%, 7=7%, 8=8%, 9=9%, 10=10%, 11=OFF | `match_percentage` |  |
| 29 | MATCH AWARD | standard | CREDIT | 0=CREDIT, 1=TICKET, 2=TOKEN | `match_award` |  |
| 31 | BALLS PER GAME | standard | 3 | 1..10 step 1 | `balls_per_game` | game_flow |
| 32 | TILT WARNINGS | standard | 2 | 0..3 step 1 | `tilt_warnings` | game_flow |
| 33 | CREDIT LIMIT | standard | 30 | 4..50 step 1 | `credit_limit` |  |
| 48 | ALLOW HIGH SCORES | standard | YES | 0=NO, 1=YES | `allow_high_scores` |  |
| 54 | HIGH SCORE AWARD | standard | CREDIT | 0=CREDIT, 1=TICKET, 2=TOKEN | `high_score_award` |  |
| 55 | GRAND CHAMPION AWARDS | standard | 1 | 0..5 step 1 | `grand_champion_awards` |  |
| 56 | HIGH SCORE #1 AWARDS | standard | 1 | 0..3 step 1 | `high_score_1_awards` |  |
| 57 | HIGH SCORE #2 AWARDS | standard | 0 | 0..2 step 1 | `high_score_2_awards` |  |
| 58 | HIGH SCORE #3 AWARDS | standard | 0 | 0..1 step 1 | `high_score_3_awards` |  |
| 59 | HIGH SCORE #4 AWARDS | standard | 0 | 0..1 step 1 | `high_score_4_awards` |  |
| 49 | GRAND CHAMPION SCORE | standard | 75,000,000 | 1,000,000..1,000,000,000 step 1,000,000 | `grand_champion_score` |  |
| 50 | HIGH SCORE #1 | standard | 55,000,000 | 1,000,000..1,000,000,000 step 1,000,000 | `high_score_1` |  |
| 51 | HIGH SCORE #2 | standard | 40,000,000 | 1,000,000..1,000,000,000 step 1,000,000 | `high_score_2` |  |
| 52 | HIGH SCORE #3 | standard | 30,000,000 | 1,000,000..1,000,000,000 step 1,000,000 | `high_score_3` |  |
| 53 | HIGH SCORE #4 | standard | 25,000,000 | 1,000,000..1,000,000,000 step 1,000,000 | `high_score_4` |  |
| 60 | HSTD INITIALS | standard | 3 INITIALS | 0=3 INITIALS, 1=10 LETTER NAME | `hstd_initials` |  |
| 61 | HSTD RESET COUNT | standard | 2000 | OFF..9900 step 100 (e.g. OFF, 100, 200, 300) | `hstd_reset_count` |  |
| 34 | FREE PLAY | standard | NO | 0=NO, 1=YES | `free_play` |  |
| 7 | LANGUAGE | standard | ENGLISH | 0=ENGLISH, 1=DEUTSCH, 2=FRANCAIS, 3=ESPANOL, 4=ITALIANO | `language` | language |
| 10 | PLAYER LANGUAGE SELECT | standard | NO | 0=NO, 1=YES | `player_language_select` |  |
| 2 | CUSTOM MESSAGE | standard | ON | 0=OFF, 1=ON, 2=CHANGE | `custom_message` |  |
| 5 | FLASH LAMP POWER | standard | NORMAL | 0=OFF, 1=DIM, 2=NORMAL | `flash_lamp_power` |  |
| 1 | COIL PULSE POWER | standard | NORMAL | 0=HARD, 1=SOFT, 2=NORMAL | `coil_pulse_power` |  |
| 35 | KNOCKER VOLUME | standard | NORMAL | 0=OFF, 1=LOW, 2=NORMAL | `knocker_volume` |  |
| 36 | GAME RESTART | standard | YES | 0=NO, 1=YES | `game_restart` |  |
| 37 | BILL VALIDATOR | standard | NO | 0=NO, 1=YES | `bill_validator` |  |
| 9 | MUSIC VOLUME | standard | 1 | 1..15 step 1 | `music_volume` |  |
| 38 | BALL SAVE TIME | standard |  0:05 | NO BALL SAVES..AUTO step 1 (e.g. NO BALL SAVES,  0:01,  0:02,  0:03) | `ball_save_time` | game_flow |
| 39 | TIMED PLUNGER | standard | OFF | OFF..1:00 step 1 (e.g. OFF, 0:01, 0:02, 0:03) | `timed_plunger` |  |
| 40 | FLIPPER BALL LAUNCH | standard | OFF | 0=OFF, 1=LEFT FLIPPER, 2=RIGHT FLIPPER, 3=EITHER FLIPPER, 4=BOTH FLIPPERS | `flipper_ball_launch` |  |
| 41 | COINDOOR BALL SAVER | standard | NO | 0=NO, 1=YES | `coindoor_ball_saver` |  |
| 42 | COMPETITION MODE | standard | NO | 0=NO, 1=YES | `competition_mode` | flynns_arcade |
| 43 | CONSOLATION BALL | standard | YES | 0=NO, 1=YES | `consolation_ball` |  |
| 4 | FAST BOOT | standard | YES | 0=NO, 1=YES | `fast_boot` |  |
| 44 | Q24 OPTION | standard | COIN METER | 0=COIN METER, 1=TOKEN DISPENSER, 2=KNOCKER | `q24_option` |  |
| 45 | TICKET DISPENSER | standard | NONE | 0=NONE, 1=DELTRONIC DL-1275 WIDE, 2=DELTRONIC DL-1275 STD., 3=ENTROPY 2000 TD-963CR, 4=BENCHMARK INTELLI-DUAL | `ticket_dispenser` |  |
| 46 | PLAYER COMPETITION | standard | YES | 0=NO, 1=YES | `player_competition` |  |
| 47 | TEAM SCORES | standard | NO | 0=NO, 1=YES | `team_scores` |  |
| 8 | LOCATION ID | standard | 0 | 0..9999 step 1 | `location_id` |  |
| 6 | GAME ID | standard | 0 | 0..9999 step 1 | `game_id` |  |
| 3 | TIME FORMAT | standard | 12-HOUR | 0=12-HOUR, 1=24-HOUR | `time_format` |  |
| 62 | COIN INPUT DELAY | standard | 30 | 30..OFF step 1 (e.g. 30, 31, 32, 33) | `coin_input_delay` |  |
| 63 | LOST BALL RECOVERY | standard | YES | 0=NO, 1=YES | `lost_ball_recovery` |  |
| 64 | COIN DOOR DISABLE TILT | standard | NO | 0=NO, 1=YES | `coin_door_disable_tilt` |  |
| 65 | POP BUMPER DIFFICULTY | feature | MEDIUM | 0=EASY, 1=MEDIUM, 2=HARD | `pop_bumper_difficulty` | switches_and_shots |
| 66 | ZUSE FAST SCORING TIMER | feature | 25 | 15..45 step 1 | `zuse_fast_scoring_timer` | zuse_fast_scoring |
| 67 | RECOGNIZER DIFFICULTY | feature | MEDIUM | 0=EASY, 1=MEDIUM, 2=HARD | `recognizer_difficulty` | recognizer_and_disc_battle |
| 68 | DISC MULTIBALL DISC SHOTS | feature | 6 | 4..8 step 1 | `disc_multiball_disc_shots` | disc_multiball |
| 69 | DISC MULTIBALL RECOGNIZER SHOTS | feature | 3 | 1..5 step 1 | `disc_multiball_recognizer_shots` | disc_multiball |
| 70 | DISC M.B. RESTART TIMER | feature | 10 | NONE..20 step 1 (e.g. NONE, 5, 6, 7) | `disc_mb_restart_timer` | disc_multiball |
| 71 | DISC M.B. RESTART AUTOFIRE TIMER | feature | 10 SECONDS | NONE..20 SECONDS step 1 (e.g. NONE, 1 SECOND, 2 SECONDS, 3 SECONDS) | `disc_mb_restart_autofire_timer` | disc_multiball |
| 72 | TRON "SPINNERS" TIMER | feature | 30 | 20..40 step 1 | `tron_spinners_timer` | tron_targets |
| 73 | TRON "BUMPERS" TIMER | feature | 30 | 20..40 step 1 | `tron_bumpers_timer` | tron_targets |
| 74 | TRON "DOUBLE SCORING" TIMER | feature | 30 | 20..40 step 1 | `tron_double_scoring_timer` | tron_targets |
| 75 | ABORT ANIMATIONS | feature | ONE | 0=NONE, 1=ONE, 2=ALL | `abort_animations` | display effects (abort on flipper) |
| 76 | DISABLE RECOGNIZER 3-BANK MOTOR | feature | NO | 0=NO, 1=YES | `disable_recognizer_3_bank_motor` | recognizer_and_disc_battle |
| 77 | DISABLE DISC MOTOR | feature | NO | 0=NO, 1=YES | `disable_disc_motor` | disc_multiball |
| 78 | DISABLE ORBIT UP-POST | feature | NO | 0=NO, 1=YES | `disable_orbit_up_post` |  |
| 79 | DISABLE PLUNGE POST | feature | NO | 0=NO, 1=YES | `disable_plunge_post` | skill_shots |
| 80 | DISABLE DROP TARGETS | feature | NO | 0=NO, 1=YES | `disable_drop_targets` | tron_targets |
| 81 | DISABLE RECOGNIZER MOTOR | feature | NO | 0=NO, 1=YES | `disable_recognizer_motor` | recognizer_and_disc_battle |
| 82 | INSULT LEVEL | feature | MEDIUM | 0=LOW, 1=MEDIUM, 2=HIGH | `insult_level` | speech (insult callouts) |
| 83 | 1ST END OF LINE M.B. LETTERS | feature | 2 | 1..2 step 1 | `end_of_line_mb_letters_first` | end_of_line_multiball |
| 84 | 2ND+ END OF LINE M.B. LETTERS | feature | 8 | 4..10 step 1 | `end_of_line_mb_letters_later` | end_of_line_multiball |
| 85 | END OF LINE EXTRA BALL | feature | 1 | 1..3 step 1 | `end_of_line_extra_ball` | end_of_line_multiball |
| 86 | SHAKER MOTOR (OPTIONAL) | feature | MAXIMAL USE | 0=NONE, 1=MINIMAL USE, 2=MODERATE USE, 3=MAXIMAL USE | `shaker_motor` | shaker (config/shaker.yaml) |
| 87 | MUSIC VOLUME | feature | 0 | -60..60 step 1 | `music_volume_trim` |  |
| 88 | SPEECH VOLUME | feature | 0 | -60..60 step 1 | `speech_volume_trim` |  |

## Install presets

INSTALL items (UTILITIES > GO TO INSTALLS MENU) set several adjustments at once. Lists read from emulator RAM after boot. In v1.74 the difficulty presets (EXTRA EASY to EXTRA HARD, DIRECTOR'S CUT) change nothing: both their OS and game lists are empty. INSTALL FACTORY resets every adjustment to its default.

- **INSTALL EXTRA EASY**: no changes
- **INSTALL EASY**: no changes
- **INSTALL MEDIUM**: no changes
- **INSTALL HARD**: no changes
- **INSTALL EXTRA HARD**: no changes
- **INSTALL DIRECTOR'S CUT**: no changes
- **INSTALL HOME PLAY**: no changes
- **INSTALL 3-BALL**: BALLS PER GAME = 3
- **INSTALL 5-BALL**: BALLS PER GAME = 5
- **INSTALL ADD-A-BALL**: REPLAY AWARD = EXTRA BALL, SPECIAL AWARD = EXTRA BALL, FREE GAME LIMIT = NO FREE GAMES, EXTRA BALL LIMIT = 9, MATCH PERCENTAGE = OFF, GRAND CHAMPION AWARDS = 0, HIGH SCORE #1 AWARDS = 0, HIGH SCORE #2 AWARDS = 0, HIGH SCORE #3 AWARDS = 0, HIGH SCORE #4 AWARDS = 0
- **INSTALL COMPETITION**: PLAYER LANGUAGE SELECT = NO, TILT WARNINGS = 2, FREE PLAY = YES, GAME RESTART = NO, COINDOOR BALL SAVER = YES, COMPETITION MODE = YES, LOST BALL RECOVERY = NO, COIN DOOR DISABLE TILT = YES
- **INSTALL NOVELTY**: REPLAY TYPE = NONE, SPECIAL AWARD = POINTS, FREE GAME LIMIT = NO FREE GAMES, EXTRA BALL LIMIT = NO EXTRA BALLS, MATCH PERCENTAGE = OFF, GRAND CHAMPION AWARDS = 0, HIGH SCORE #1 AWARDS = 0, HIGH SCORE #2 AWARDS = 0, HIGH SCORE #3 AWARDS = 0, HIGH SCORE #4 AWARDS = 0

## Audits

| # | Name | Menu |
|---|---|---|
| 1 | TOTAL PAID CREDITS | earnings |
| 2 | FREE GAME PERCENTAGE | earnings |
| 3 | AVERAGE BALL TIME | earnings |
| 4 | AVERAGE GAME TIME | earnings |
| 5 | COINS THROUGH LEFT SLOT | earnings |
| 6 | COINS THROUGH RIGHT SLOT | earnings |
| 7 | COINS THROUGH CENTER SLOT | earnings |
| 8 | COINS THROUGH FOURTH SLOT | earnings |
| 9 | COINS THROUGH FIFTH SLOT | earnings |
| 10 | TOTAL COINS | earnings |
| 11 | TOTAL EARNINGS | earnings |
| 12 | METER CLICKS | earnings |
| 13 | SOFTWARE METER | earnings |
| 14 | TOTAL BALLS PLAYED | standard |
| 15 | TOTAL EXTRA BALLS | standard |
| 16 | EXTRA BALL PERCENTAGE | standard |
| 17 | REPLAY 1 AWARDS | standard |
| 18 | REPLAY 2 AWARDS | standard |
| 19 | REPLAY 3 AWARDS | standard |
| 20 | REPLAY 4 AWARDS | standard |
| 21 | TOTAL REPLAYS | standard |
| 22 | REPLAY PERCENTAGE | standard |
| 23 | TOTAL SPECIALS | standard |
| 24 | SPECIAL PERCENTAGE | standard |
| 25 | TOTAL MATCHES | standard |
| 26 | HIGH SCORE AWARDS | standard |
| 27 | HIGH SCORE PERCENT | standard |
| 28 | TOTAL FREE PLAYS | standard |
| 29 | TOTAL PLAYS | standard |
| 30 | 0.0M-1.99M SCORES | standard |
| 31 | 2.0M-3.99M SCORES | standard |
| 32 | 4.0M-5.99M SCORES | standard |
| 33 | 6.0M-7.99M SCORES | standard |
| 34 | 8.0M-9.99M SCORES | standard |
| 35 | 10.0M-12.49M SCORES | standard |
| 36 | 12.5M-14.99M SCORES | standard |
| 37 | 15.0M-17.49M SCORES | standard |
| 38 | 17.5M-19.99M SCORES | standard |
| 39 | 20.0M-24.99M SCORES | standard |
| 40 | 25.0M-29.99M SCORES | standard |
| 41 | 30.0M-39.99M SCORES | standard |
| 42 | 40.0M-49.99M SCORES | standard |
| 43 | 50.0M-74.99M SCORES | standard |
| 44 | 75.0M-99.99M SCORES | standard |
| 45 | 100.0M-149.99M SCORES | standard |
| 46 | 150.0+M SCORES | standard |
| 47 | AVERAGE SCORES | standard |
| 48 | SERVICE CREDITS | standard |
| 49 | BALL SEARCH STARTED | standard |
| 50 | LOST BALL FEEDS | standard |
| 51 | LOST BALL GAME STARTS | standard |
| 52 | LEFT DRAINS | standard |
| 53 | CENTER DRAINS | standard |
| 54 | RIGHT DRAINS | standard |
| 55 | TILTS | standard |
| 56 | TOTAL BALLS SAVED | standard |
| 57 | LEFT FLIPPER USED | standard |
| 58 | RIGHT FLIPPER USED | standard |
| 59 | 0 - 1 MINUTE GAMES | standard |
| 60 | 1 - 1.5 MINUTE GAMES | standard |
| 61 | 1.5 - 2 MINUTE GAMES | standard |
| 62 | 2 - 2.5 MINUTE GAMES | standard |
| 63 | 2.5 - 3 MINUTE GAMES | standard |
| 64 | 3 - 3.5 MINUTE GAMES | standard |
| 65 | 3.5 - 4 MINUTE GAMES | standard |
| 66 | 4 - 5 MINUTE GAMES | standard |
| 67 | 5 - 6 MINUTE GAMES | standard |
| 68 | 6 - 8 MINUTE GAMES | standard |
| 69 | 8 - 10 MINUTE GAMES | standard |
| 70 | 10 - 15 MINUTE GAMES | standard |
| 71 | 15+ MINUTE GAMES | standard |
| 72 | RECENT REPLAY PERCENT | standard |
| 73 | DISC MULTIBALL STARTED | feature (Tron) |
| 74 | DISC M.B. SPINNING DISC JACKPOTS | feature (Tron) |
| 75 | DISC M.B. BLUE DISC SHOTS | feature (Tron) |
| 76 | DISC M.B. RECOGNIZER HITS | feature (Tron) |
| 77 | DISC M.B. SUPER JACKPOTS | feature (Tron) |
| 78 | DISC M.B. RESTARTED | feature (Tron) |
| 79 | QUORRA MULTIBALL STARTED | feature (Tron) |
| 80 | QUORRA MULTIBALL JACKPOTS | feature (Tron) |
| 81 | QUORRA M.B. SUPER JACKPOTS | feature (Tron) |
| 82 | LIGHT CYCLE MULTIBALL STARTED | feature (Tron) |
| 83 | LIGHT CYCLE MULTIBALL JACKPOTS | feature (Tron) |
| 84 | LIGHT CYCLE MBALL SUPER JACKPOTS | feature (Tron) |
| 85 | LIGHT CYCLE MBALL 2X SUPER JPS | feature (Tron) |
| 86 | CLU HURRYUP STARTED | feature (Tron) |
| 87 | CLU HURRYUP AWARDS | feature (Tron) |
| 88 | GEM HURRYUP STARTED | feature (Tron) |
| 89 | GEM HURRYUP AWARDS | feature (Tron) |
| 90 | ZUSE FASTSCORING STARTED | feature (Tron) |
| 91 | FLYNN'S ARCADE: 500K | feature (Tron) |
| 92 | FLYNN'S ARCADE: ADV. GEM | feature (Tron) |
| 93 | FLYNN'S ARCADE: ADV. CLU | feature (Tron) |
| 94 | FLYNN'S ARCADE: ADV. ZUSE | feature (Tron) |
| 95 | FLYNN'S ARCADE: ADV. QUORRA | feature (Tron) |
| 96 | FLYNN'S ARCADE: ADV. DISC | feature (Tron) |
| 97 | FLYNN'S ARCADE: ADV. LIGHT CYCLE | feature (Tron) |
| 98 | FLYNN'S ARCADE: ADV. RECOGNIZER | feature (Tron) |
| 99 | FLYNN'S ARCADE: ADV. SEA OF SIMUL. | feature (Tron) |
| 100 | FLYNN'S ARCADE: MORE TIME | feature (Tron) |
| 101 | FLYNN'S ARCADE: LIGHT EXTRA BALL | feature (Tron) |
| 102 | FLYNN'S ARCADE: LIGHT SPECIAL | feature (Tron) |
| 103 | EXTRA BALLS LIT | feature (Tron) |
| 104 | LEFT ORBIT | feature (Tron) |
| 105 | RIGHT ORBIT | feature (Tron) |
| 106 | LEFT RAMP | feature (Tron) |
| 107 | RIGHT RAMP | feature (Tron) |
| 108 | L. INNER LOOP | feature (Tron) |
| 109 | R. INNER LOOP | feature (Tron) |
| 110 | VUK | feature (Tron) |
| 111 | SOS STARTS | feature (Tron) |
| 112 | ITEMS LIT: FLYNN | feature (Tron) |
| 113 | ITEMS COLLECTED: FLYNN | feature (Tron) |
| 114 | ITEMS LIT: GEM | feature (Tron) |
| 115 | ITEMS COLLECTED: GEM | feature (Tron) |
| 116 | ITEMS LIT: CLU | feature (Tron) |
| 117 | ITEMS COLLECTED: CLU | feature (Tron) |
| 118 | ITEMS LIT: ZUSE | feature (Tron) |
| 119 | ITEMS COLLECTED: ZUSE | feature (Tron) |
| 120 | ITEMS LIT: QUORRA | feature (Tron) |
| 121 | ITEMS COLLECTED: QUORRA | feature (Tron) |
| 122 | ITEMS LIT: DISC | feature (Tron) |
| 123 | ITEMS COLLECTED: DISC | feature (Tron) |
| 124 | ITEMS LIT: LIGHT CYCLE | feature (Tron) |
| 125 | ITEMS COLLECTED: LIGHT CYCLE | feature (Tron) |
| 126 | ITEMS LIT: RECOGNIZER | feature (Tron) |
| 127 | ITEMS COLLECTED: RECOGNIZER | feature (Tron) |
| 128 | ITEMS LIT: TRON | feature (Tron) |
| 129 | ITEMS COLLECTED: TRON | feature (Tron) |
| 130 | COMBO AWARDS | feature (Tron) |
| 131 | CASTOR COMBO | feature (Tron) |
| 132 | LAST ISO COMBO | feature (Tron) |
| 133 | THE OUTLANDS COMBO | feature (Tron) |
| 134 | LIGHT CYCLE COMBO | feature (Tron) |
| 135 | LIGHT RUNNER COMBO | feature (Tron) |
| 136 | THE GRID COMBO | feature (Tron) |
| 137 | SIREN COMBO | feature (Tron) |
| 138 | JARVIS COMBO | feature (Tron) |
| 139 | THREE MAN LIGHT JET COMBO | feature (Tron) |
| 140 | RICOCHET COMBO | feature (Tron) |
| 141 | END OF LINE COMBO | feature (Tron) |
| 142 | RINZLER COMBO | feature (Tron) |
| 143 | FIND FLYNN STARTED | feature (Tron) |
| 144 | FIND FLYNN COMPLETED | feature (Tron) |
| 145 | PORTAL MULTIBALL STARTED | feature (Tron) |
| 146 | PORTAL MULTIBALL AWARDS | feature (Tron) |
| 147 | PORTAL MULTIBALL SUPER JACKPOTS | feature (Tron) |
| 148 | PORTAL MULTIBALL BONUS AWARDS | feature (Tron) |
| 149 | RECOGNIZER BATTLE STARTED | feature (Tron) |
| 150 | DAFT PUNK MULTIBALL STARTED | feature (Tron) |
