# Daft Punk Multiball (= End of Line Multiball)

Stern Tron Legacy LE 1.74. **Daft Punk Multiball and End of Line Multiball are the same
feature in this ROM.** The audit table calls it "DAFT PUNK MULTIBALL STARTED" (audit 0x8e), the
lighting letters on the display spell **DAFT** (left ramp) and **PUNK** (right ramp), and the
start/total screens and speech say "END OF LINE MULTIBALL". One start function
(`on_daft_punk_multiball_started` 0x01004cc0) bumps audit 0x8e, sets flag 0x27 and queues deff 56
"END OF LINE / MULTIBALL"; the operator settings for it are adjustments 83-85 "... END OF LINE ...".
There is no other multiball start that bumps 0x8e, and no separate End of Line multiball audit.

The complete rule (lighting, settings, scoring, add-a-ball, end, lamps, all media) is in
**`end_of_line_multiball.md`**. This page states the identity evidence and documents the parts
asked about specifically: the start, the audit, and the music and sound changes. Build one mode,
not two.

## 1. Summary

Spell DAFT with left ramps and PUNK with right ramps (2 complete spellings for the first
multiball, 8 for later ones), then shoot the VUK: a 2-ball multiball starts with Daft Punk music.
Switches score 10,000+ each, the left ramp a Jackpot (500,000+), the right ramp a Double
Jackpot, the disc 200,000 plus add-a-balls; **each disc hit switches to the next of four music
tracks**. Ends at one ball left plus a 5 s grace with a total screen.

## 2. Settings (operator adjustments)

| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| 83 | 1ST END OF LINE M.B. LETTERS | 2 | 1-2 | DAFT+PUNK spellings to light the first one [0x010042d0] |
| 84 | 2ND+ END OF LINE M.B. LETTERS | 8 | 4-10 | Spellings for later ones [0x010042d0] |
| 85 | END OF LINE EXTRA BALL | 1 | 1-3 | Spelling number (game total) that lights the extra ball [0x01004238] |
| 9 / 87 | MUSIC VOLUME | 1 / 0 | 1-15 / -60..60 | Global music volume (not specific) |

## 3. State

See `end_of_line_multiball.md` section 3. Running state used by the music: `eol_level`
(0x0003adf4, disc hits this multiball). Audit counter 0x8e. Flag 0x27 = running, flag 0x26 = lit.

## 4. How it starts

Lit by the DAFT/PUNK letters (end_of_line_multiball.md 4.1). Started from the VUK (sw11) by
`FUN_01004ddc` when flag 0x26 is set, if no multiball and no Sea of Simulation is running
[0x01004c68]. On start [0x01004cc0]: 2-ball multiball (`multiball_start(2 or balls_in_play+1,
save 625 ticks = 10.2 s, grace 125 ticks = 2.0 s)`), flag 0x27, audit 0x8e, 100,000 points,
running values reset (switch value 10,000, level 0, add-a-ball countdown 2, all three jackpot
shots lit), intro deff 56 queued (task 0xa6), background rule registered. Flag 0x26 is cleared by
the caller after a successful start.
(verified in emulator: traces/daft_punk_multiball.jsonl and traces/end_of_line_multiball.jsonl)

## 5. Behaviour while running: music and sound changes

| Trigger | Condition | Effect | Display | Sound call(s) | Lamp / leff | Next state |
|---|---|---|---|---|---|---|
| Start | — | intro | deff 56 "END OF LINE / MULTIBALL" (4.1 s) | speech 0x024 -> 0x025 -> 0x026 chained (samples 0x320 2.56 s, 0x321 2.33 s, 0x322 4.63 s) | leff 58, tube 87 | running |
| Running (background rule, priority 7) | flag 0x27 set and intro not pending | background deff 57 "SWITCHES=value"; music **0x20 + (eol_level & 3)** started if not already playing | deff 57 | 0x020 (sample 0x447, 10.0 s), 0x021 (0x448, 22.0 s), 0x022 (0x449, 12.0 s), 0x023 (0x44a, 11.0 s) | leff 59/60, tube 88 | — |
| Disc hit | running or grace | `eol_level += 1` -> on the next rules refresh the rule starts the next music call (0x20 -> 0x21 -> 0x22 -> 0x23 -> 0x20 ...) | deff 60 | music change; disc sfx 0x052 + 0x053 come from the disc handler | leff 63, tube 91 | — |
| Left ramp jackpot | bit0 lit | 500,000 + 25,000 x level (max 1,250,000) | deff 58 | 0x027 (sfx 0x03c) | leff 61, tube 89 | — |
| Right ramp double | bit1 lit | 2 x the jackpot | deff 59 | 0x028 (sfx 0x03b) | leff 62, tube 90 | — |
| One ball left | — | flag 0x27 cleared -> background rule stops -> the normal game music rule takes over | — | normal play music (0x01b seen in the traces) | — | grace (312 ticks) |
| End of grace | `eol_total != 0`, not tilted | total | deff 61 | none | leff 64, tube 92 | ended |

Mechanism [0x01006298, 0x01005610]: the feature registers a background rule object
(`lamp_rule_init` = deff + music rule, list 2) with condition 0x010055d8 and a callback 0x01005610
that sets deff id 0x39 (57) and music call `0x20 + (*(u16*)0x3adf4 & 3)`. The OS rule pass
(`FUN_000198a8`) starts the deff if it is not running and plays the music call if it is not already
playing (`FUN_0002ccd4`). So the track change is immediate after each disc hit (the disc handler
requests a rules refresh), and the same track is not restarted while it plays. Whether a track
loops when it ends is not known (stream-level looping, see asset_audit M10).

Sound calls listed in `tron/sound_calls.csv`: 0x020-0x023 music (flags 0x101), 0x024-0x026
speech, 0x027/0x028 sfx. All of these samples are exported in `samples/` (none is in the
missing list of asset_audit W5).

## 6. How it ends

See end_of_line_multiball.md section 6: at one ball left the mode drops into a 312-tick
(5.07 s) grace (tasks 0xb0 187 ticks, then 0xb1 125 ticks) in which shots still score and an
add-a-ball restarts it; then deff 61 shows the total. The Daft Punk music stops at the start of
the grace because the background rule only tests flag 0x27.

## 7. Media

Full table in end_of_line_multiball.md section 7 (deffs 55-61, leffs 56-64, tube shows 86-92).

## 8. Lamps

No inserts; flashers 17/18 while lit (leff 57), disc flashers 31/32 and ramp tubes while running.
Details in end_of_line_multiball.md section 8.

## 9. Interactions

No stacking with any other multiball (end_of_line_multiball.md section 9). The music rule has
priority 7, the same as Portal's (call 0x076); since the two multiballs cannot run together the
two never compete.

## 10. Reference scenario

`traces/daft_punk_multiball.txt` / `.jsonl` (no pokes; `adj 83 1` so one spelling lights it).
8 alternating ramps (DAFT + PUNK), VUK, then 5 disc hits and a right ramp.
Expected: `flag_set 38` on the 8th ramp (with `flag_set 40`, extra ball, same set);
VUK: `multiball_start balls=2 save_ticks=625 grace_ticks=125`, `audit 142`, `score_add 100000`;
deff 56 with sound 0x024; deff 57 with sound 0x020; disc 1..5: `score_add 200000` each and music
0x021, 0x022, 0x023, 0x020, 0x021 in turn; `multiball_start balls=3` on disc 2 and `balls=4` on disc 5;
right ramp at level 5: 2 x 625,000 = 1,250,000.

## 11. Open questions

- The name split (Daft Punk in audits/letters, End of Line on screen/settings) is just labelling
  in this ROM; nothing else found that differs between "Daft Punk" and "End of Line" multiball.
- Music looping at the end of a track not verified.
