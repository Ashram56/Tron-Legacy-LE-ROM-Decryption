# Multi-player games (2, 3 and 4 players)

Data: `multiplayer.json`. It holds:
- `facts`: tagged fact rows;
- `state_scope`: 294 RAM variables from `rules/work/ram/*.tsv` plus OS ones, each classed per_player /
  per_player_swapped / per_ball_shared / shared / transient_shared;
- `rotation`: the observed (t, cur_player, ball_num, marks) sequence per scenario.

Scenarios (fresh NVRAM, ball save set to 0 with `adj 38 0` so every drain ends the ball):

| Scenario | What it shows |
|---|---|
| `traces/multiplayer_2p.txt` | 2 players, extra ball collected on ball 2, short START press on ball 2 |
| `traces/multiplayer_3p.txt` | 2 players + a 3rd added during ball 1 after valid playfield; P2 tilts; a 4th player refused on ball 2 |
| `traces/multiplayer_4p.txt` | 4 players; P3 extra ball (poke) on ball 1; P3 score poked to 60 M on ball 3 → replay + high-score entry |

## Adding players
- **Ball 1.** START with a credit adds a player while the current ball is **1**, even after the playfield is valid
  (3p: player 3 added at t 19.02, 3 s into P1's ball). Each add takes a credit and counts audit 0x11
  (`observed`, 0x20c5c).
- **Ball 2 and later.** The same press does nothing, and the credit stays (3p t 57.70). Holding START for 1 s there
  restarts the game instead (adj 36; game_flow.md).

## Rotation (0x214d0, `code`; observed in all three scenarios)
At the end of each ball:
1. The OS posts event 0x47, which can veto.
2. **Extra ball pending** (0x1a27c, RAM 0x37430): flag 9 is set and the **same player** shoots again on the same ball
   number (deff 26 "SHOOT AGAIN", leff 16, speech 0x11b).
3. **Otherwise** the next player is up. After the last player, it goes back to player 1 with ball + 1. Past the
   balls-per-game limit (adj 31, or the tournament value), the game is over (0x20a64).
4. The old player's game flags and lamps are saved, `cur_player` (0x3817c) is set, the new player's are restored, and
   event 0x48 is posted.

Observed rotations:

| Game | Sequence |
|---|---|
| 4p | P1 P2 P3 **P3 (shoot again)** P4 / P1 P2 P3 P4 / P1 P2 P3 P4 → end. `ball_num` changes only when P1 comes up. |
| 2p | P1 P2 / P1 **P1 (shoot again)** P2 / P1 P2 → match. |
| 3p | P1 **P2 (tilted)** P3 / P1 P2 P3 / P1 P2 P3. |

## Per-player vs shared state
| Kind | How it is kept | Examples | Tag |
|---|---|---|---|
| Per player, in NVRAM arrays [p-1] | Indexed by the player; reset on event 0x26 (that player's first ball) or at game start | Item ladders, TRON letters, ZEN charges, MB lit flags, SOS items, arcade lit (0x211166c), extra balls lit / collected [p-1] (0x3d46c / 0x3d470) | code (`state_scope`) |
| Game flags | One block, **saved and restored per player**, except flags with class bit 0 | Per player: 16-27, 32-35, 38, 40, 44, 45, 47-49, 51. Global: the others (e.g. 0x24/0x25 Disc MB running, 0x34 SOS running) | code (0x6700/0x6744) |
| Lamp states | Saved and restored per player except lamps 26, 65, 66 | Every insert lamp follows the player who is up | code (0x21080/0x210d4) |
| Per ball, shared | Reset at every ball start (event 0x11, class-4 flags) | Bonus X, playfield multiplier, tilt warnings 0x3d4f8, valid playfield 0x372e8, ball save, skill shots | observed |
| Machine / game | Single copy | `num_players` 0x2110900, `cur_player` 0x3817c, `ball_num` 0x3817d, shoot-again pending 0x37430, `gf_state` | observed |

Seen in play: `deff 104` "ARCADE IS LIT" shows at P1's and P2's first ball, but not at P1's ball 2. The per-player
arcade flag was already set for P1 and still clear for P2.

## Player-up media
There is no dedicated "PLAYER n UP" effect (`observed`). At every ball start the game:
- starts the score display deff 19 (it shows the current player);
- plays music call 0x01a;
- starts leffs 159/99/113 through rules and leff 14 (ball save).

`deff 104` appears at a player's first ball only because that player's arcade flag goes 0 → 1, not because of a
player change.

## Extra ball in multi-player
When the extra ball is collected:
- `shoot_again_pending` = 1 and `eb_collected_p1` = 1;
- deff 133, leff 153, sounds 0x119/0x11a.

At that player's drain the bonus runs, then deff 26 SHOOT AGAIN plays with the same ball number. The next drain passes
play to the next player as usual (2p t 56.18 → 66.75 → 83.00, `observed`).

## End of game (4p, `observed`, t 145.78-171)
1. The last player's bonus (deff 25).
2. Audit 46 once per player, then audit 32. Sound 0x039, deff 31, `gf_state` 88.
3. 1.8 s later: deff 32 with sound 0x01f. The initials are entered while deff 32 runs; each START press plays sound
   0x035.
4. After the 4th press: audit 16, sound 0x036, deff 33, high-score credit (credits +1) and knocker sound 0x019.
5. Match deff 38 (state 152, music 0x01c).
6. Attract deff 1 + leff 1, game-over music 0x01d with leff 133 (GI off about 10 s). Speech 0x01e plays at some game
   overs (countdown 0x3afec).

A replay reached in a multi-player game is awarded at that player's bonus end: credit, knocker 0x019, deff 28,
leff 17.

## Open
- **High-score deff names.** `deffs.json` calls deff 31 "enter initials" and 32 "high score value", but the initials
  were entered while deff 32 was active. The names may be swapped, or deff 31 may be the "congratulations" lead-in.
- **Tilt or slam during another player's turn** is not checked for its effect on that player's per-player data. The
  code suggests none.
