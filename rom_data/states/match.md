# Match

Data: `match.json`. Scenarios: `traces/match_natural.txt`, `match_win.txt` and `match_forced_loss.txt`. All three play
the same 1-player game: final score 757,740, last two digits 40.

## Code (0x1b660, `code`)
1. **Skip conditions.** Skip if adj 30 MATCH PERCENTAGE = 11 (off) or in tournament mode (0x252a0(1)). Otherwise set
   `gf_state` bit 0x80.
2. **Draw first, always:** `m = random(10) * 10` at 0x1b6ac (00, 10, ..., 90).
3. **Rate:** `rate = audit 0xf (TOTAL MATCHES) * 100 / audit 0x11 (GAMES STARTED)`, or 0 when no games.
4. **If rate < adj 30:** every player whose `score % 100 == m` wins. The winners are collected as a bit mask (deff
   +0x30), and their count goes to 0x3743e.
5. **Else (forced loss):** `m += 10` (99 → 0) is repeated until no player matches. It always moves at least once, so
   the shown number is never the drawn one. Error 0xb1 is raised if it wraps fully.
6. **Display.** Deff 38 gets the mask (+0x30) and the number (+0x34). After the deff, 0x1b954 pays every winner, one
   every 31 ticks, via `match_award` 0x1b86c. The payout depends on adj 29:

   | adj 29 | Payout |
   |---|---|
   | 0 | credit 0x4cf0 + knocker (sound 0x019) |
   | 1 | ticket 0x100f8 |
   | 2 | nothing |

   Each payout also counts audit 0xf.

**Odds (`inferred`).**
- Below the target, each player wins with probability 1/10 per game. Scores always end in x0 here, so the draw can
  match.
- Once the lifetime rate reaches adj 30 %, matching is blocked until more games bring the rate back down.
- In the long run the rate therefore stays just under adj 30 % (factory 9 %).

## Observed

| Run | Pokes | Draw | Result | Media |
|---|---|---|---|---|
| natural | adj 38 0 | random(10) = 5 → 50 (seed 0xdc7f07ea) | no winner | deff 38 6.24 s: music 0x01c, sfx 0x041 0x03f 0x040 0x042; then attract + speech 0x01e + music 0x01d |
| win | `pokeat 1b6ac 372c4 2814350714 4` (seed 0xa7bf957a) | 4 → 40 | winners = 1; at +4.19 s audit 15, credits 0 → 1, sound 0x043 and knocker 0x019; 0x045 at +5.8 s | deff 38 7.84 s |
| forced loss | as win + `adj 30 0` | 4 → 40 (would match) | no winner (number stepped to 50: code, not visible in the trace) | same as natural |

**Forcing a digit d in the emulator.** Choose `next` in `[d*2^32/10, (d+1)*2^32/10)` and poke
`seed = (next - 1) * inverse(0x19660d) mod 2^32` into 0x372c4 when execution reaches 0x1b6ac (states_ref `pokeat`).

## Open
- **The displayed number.** In the forced-loss run the stepped value (+0x34 of the deff task) was not logged.
  States_ref has no register-at-PC dump for r6.
