# Tron Legacy LE v1.74: asset package for an MPF rebuild

Everything here was pulled from the original ROM (`trn_174h.bin`, Stern SAM, PinMAME set `trn_174h`).
It gives an MPF (Mission Pinball Framework) project the original sounds, DMD animations,
ramp fiber optic light shows, hardware names and a map of what triggers each effect.

Each fact is marked by where it came from:
- **observed**: seen while running the ROM in PinMAME.
- **code**: read from the decompiled game code (`../code/tron_game_decompiled.c`).
- **inferred**: a reasonable guess from on-screen text or code location. Check it before relying on it.

## Layout

```
mpf_package/
  README.md              this file
  event_map.csv          one row per ROM display effect: what it shows, what triggers it,
                         its sounds, tube light show, lamp effect, shaker, animation and timing
  lamp_effects.csv       one row per ROM lamp effect (171): what it does, its show, who starts it
  service_menu.md        the ROM's service menu tree, all 88 adjustments with their values,
                         install presets and all 150 audits (service_menu.json: same, as data)
  animation_map.csv      one row per ROM animation (145): which effects use it and how the
                         ROM picks it, with its own MPF event
  config/
    switches.yaml        64 ROM switches (SAM numbers)
    coils.yaml           coils and flashers (SAM driver numbers)
    lights.yaml          80-lamp matrix, plus the two RGB ramp tubes
    sounds.yaml          1,090 sounds and 254 sound pools (one pool per ROM "sound call")
    dmd_slides.yaml      animated images and one slide per effect that has graphics
    show_player.yaml     event -> show, one per effect
    game_flow.yaml       attract, game start, ball start, ball end and game over, on MPF's own events
    dmd_variants.yaml    effects that pick a different film clip each time (random or by mode level)
    dmd_library.yaml     one slide, show and event (tron_lib_anim_NNN) for every ROM animation
    lamp_effects.yaml    event -> lamp effect show (tron_lampfx_NNN_*), for effects your modes start
    shaker.yaml          shaker motor runs, on the effects that run it in the ROM, gated by the setting
    settings.yaml        all 88 operator adjustments as MPF machine settings
    shows/
      deff_NNN_<name>.yaml   one show per effect: slide + sounds + tube show, timed
      deff_NNN_<name>_vNN.yaml / _level_N.yaml   the same effect with each film clip it can pick
      flow_*.yaml            game flow shows (see game_flow.yaml)
      lib_anim_NNN_*.yaml    one show per library animation
      leff_NNN.yaml          99 ramp tube light shows (from the IO thread)
      lampfx_NNN_<name>.yaml 130 playfield lamp and flasher effects (lamp matrix + flashers)
      shaker_strength_N.yaml the three shaker run lengths
  media/
    sounds/{speech,sfx,music}/XXXX.wav   mono WAV (most speech 12 kHz; 53 speech samples and all sfx/music 24 kHz), file name = ROM sample id
    dmd/deff_NNN_<name>/                 one folder per display effect (145)
      animation.gif          graphics layer, 128x32, real frame timing, transparent background
      frames/NNN.png         same frames as PNG (grey, alpha = drawn pixels)
      timing.json            per-frame start and duration (ms), sounds and tube shows with offsets
      reference_capture.gif  the full DMD as the emulator showed it (graphics + text + score panel)
      reference_capture_x4.gif  same, 4x size for viewing
      variants/              one GIF per film clip the effect can pick (128x32)
    dmd/flow_attract_cycle/              the full attract mode display cycle (25.9 s)
    dmd_library/anim_NNN_imgXXXX/        all 145 full-size ROM animations, including ones no
      animation.gif, frames/              effect played during capture (native size)
      animation_128x32.gif   on the 128x32 canvas at the ROM's position and frame time
    dmd_library/index.json               one entry per library animation: frame range, size, and
                                         which effects were seen using it
    rom_images_all.zip       every one of the ROM's 8,181 images as PNG (fonts, icons, sprites,
                             frames) with index.json
  tools/                 the scripts and emulator patch that produced all of this
```

## How to wire it into MPF

Target is current MPF (0.80) conventions; the YAML also loads in 0.57 with MPF-MC.

1. Machine config: copy `config/switches.yaml`, `coils.yaml`, `lights.yaml` into your machine
   config (or include them with `config:`). The `number:` values are the original SAM numbers.
   Replace them with your platform's addresses. Letter targets and lamps are named by their letter
   (`s_tron_t` is switch 1 "(T)RON"; `l_tron_n` is lamp 1 "TRO(N)"; lamp order is the reverse of the
   switches). Motors and relays have `default_hold_power` so MPF can hold them on. Flipper buttons, flipper EOS and coin door are SAM
   "dedicated" switches and are not in the ROM's switch table, so add those yourself.
2. Sounds: put `media/sounds/*/*.wav` in your sounds folder and include `config/sounds.yaml`.
   Tracks used: `voice`, `sfx`, `music`. The ROM never plays a sample directly; it plays a
   "sound call" that picks one sample from a list, so each call is a `sound_pools:` entry named
   `call_XXX` (hex call id). Play `call_0f0`, not a single `snd_`.
3. DMD: the display is 128x32 with 16 grey levels. Most game animations are 87x32 drawn at x=41;
   the left 41 columns are the score/status panel. The GIFs and PNGs already sit on a full
   128x32 canvas at the right position. Colour them with your DMD widget's tint.
   - MPF-MC (0.57): include `config/dmd_slides.yaml`; images load by name from `media/dmd`.
   - GMC (0.80, Godot): build one slide scene per effect using `frames/` and `timing.json`
     (an AnimatedSprite2D with per-frame durations), named like the slide in `dmd_slides.yaml`.
   - Text is **not** in the animation images. The ROM draws it on top with its fonts. The
     strings are in `event_map.csv` (`rom_text`) and as comments in `dmd_slides.yaml`; `%,02lu` is
     a score, `%d`/`%u` a count. Use `reference_capture.gif` to copy the layout.
4. Effects as shows: include `config/show_player.yaml` and `config/shows/`. Posting
   `tron_disc_multiball_intro` plays `deff_046_disc_multiball_intro`: slide at 0 ms, sound call
   `0x056` and tube show `leff_042` at their observed offsets, slide removed at the end.
   Effects marked `background_loop` in `event_map.csv` (score display, "shoot X" mode status)
   run until the mode stops them: stop the show from the mode instead of waiting for it to end.
5. Game flow: include `config/game_flow.yaml`. It plays the attract cycle on `mode_attract_started`,
   the start-of-game show on `game_started`, the next-ball show on `ball_started`, the bonus on
   `ball_ending` and the match on `game_ending`. The ROM has no separate "start" animation: at game
   start it plays main play music `call_01a` and tube show 10. Effect 104 ("FLYNN'S ARCADE IS LIT",
   the Flynn's sign animation) also shows at game start, but only because the arcade starts lit: the
   ROM plays it whenever the player's arcade flag turns on (code: FUN_0100ddb0). So `flow_game_start`
   leaves it out; post `tron_arcade_lit` from your arcade logic. Effect 26 (shoot again) plays after
   an extra ball.
   Before the bonus, each mode that ran during the ball shows its total (effects 70, 74, 79, 90, 99).
6. Film clip effects: 19 effects show a different movie clip each time. `config/dmd_variants.yaml`
   keeps the original event name (for example `tron_disc_multiball_jackpot`) and turns it into a
   `random_event_player` that plays one clip variant, as the ROM does. The show captured in emulation
   is still there as `<event>_as_captured`. Light Cycle jackpots are not random: post
   `tron_light_cycle_jackpot_level_<level>_<n>` (the n-th jackpot of that level; past the last one the
   ROM goes back to the first) and `tron_light_cycle_super_jackpot_level_<level>` /
   `tron_light_cycle_double_super_jackpot_level_<level>`. "Level" is the value the ROM keeps for the
   Light Cycle round (code, table 0x40d2ffc); that it counts Light Cycle multiballs played is inferred.
   Effect 108 (disc access progress) picks one of 4 clips; two are full width at 49 ms per frame and
   two sit at x=41 at 33 ms.
   Sea of Simulation stages pick one of two clips, or a third (`_alt`) when the caller sets a flag
   whose meaning was not traced.
7. Flynn's Arcade award (effect 105): a mystery award, not a video mode. When the ball enters the
   VUK (sw11) while the arcade is lit, the ROM picks 1 of 12 awards by weighted random (weights not
   verified) and effect 105 scrolls in 3 cabinets showing 2 decoy awards and the chosen one, then
   blinks the chosen icon. The exported GIF is one random capture; to build it properly use the parts
   in `media/dmd/deff_105_flynns_arcade_award/parts/` (4 cabinets, both blink states of the 12 award
   icons, and `index.json` with the award names and the timing).
8. Any single animation: post `tron_lib_anim_NNN` (see `animation_map.csv`).
9. Triggers: the event names are suggestions. Post them from your modes using the
   `rom_trigger`, `observed_on_switches` and `started_by_code` columns of `event_map.csv`.
   Example: in a Disc Multiball mode, `events_when_started: tron_disc_multiball_intro`.

## Ramp fiber optic tubes

The two ramp tubes are RGB lights on the SAM IO board's aux bus, not on the lamp matrix. The ROM
calls them "ramp light tubes". `lights.yaml` defines them as `l_left_ramp_tube` and
`l_right_ramp_tube` (4-bit RGB per channel in the ROM, scaled to 0-255 in the shows). The bus
protocol and wiring are in `../io/README.md`. The `leff_NNN` shows were generated from emulation by
the IO thread; `../io/light_effects.csv` describes each one. Shows 36 and 88 are incomplete.
In this package each effect's show already starts the tube show the ROM starts with it (observed).

## Playfield lamp effects and flashers

The ROM has a second light effect system for the lamp matrix ("lamp effects", 171 entries, table
0x040e23e4, started by OS function 0x87ac). Many of them also pulse the flashers. Each one was
started on its own in the emulator during a game, and the lamps it took over and the flashers it
pulsed were logged every frame (observed). They are the `lampfx_NNN_<name>` shows; `leff_NNN` stays
the ramp tube shows.

- **Already wired**: 53 display effect shows start their lamp effect at 0 ms (observed when the effect
  was forced; from code where it was not), for example jackpots and mode intros. The attract show
  (`lampfx_001_attract`) runs with attract mode in `game_flow.yaml`, and the game over show starts
  `lampfx_133_game_over` with the attract hand-off.
- **Started by your modes**: the rest are started by switch handlers or by "while this mode state is
  true" rules in the ROM. `lamp_effects.yaml` gives each one an event (`tron_lampfx_NNN_<name>`, plus
  `_stop` for the looping ones), and `lamp_effects.csv` column `started_by` says what starts it:
  a function name, or `rule: while <condition>` (play it while that mode state holds, stop it after).
- **Effects that take a lamp**: 17 effects flash or set a lamp the caller passes (TRON, ZUSE and CLU
  letters, recognizer targets). Their shows use the token `(lamp)`; four take a lamp group and use
  `(lamps)`, a light tag (`rom_group_31` TRON letters, `rom_group_50` CLU, `rom_group_54` ZUSE,
  `rom_group_52`), now tagged in `lights.yaml`. Pass it with `show_tokens`.
- **Lamps off**: 15 effects hold a set of lamps off while they run (blackouts: attract, tilt, slam
  tilt, bonus count, the End of Line intro). Their show sets those lamps to black at the ROM's
  priority, so give them a priority above your mode lamps.
- **Looping effects** were cut to one loop when the capture repeated exactly; 9 that never settle
  are the full 12 s capture, looped. The CSV says which.
- **Not exported** (34 + 7): 34 entries are empty in v1.74 (the task ends at once), and 7 only draw
  from live mode state (combo arrows, Disc Multiball status, Light Cycle children). The CSV
  describes each, so your mode code can draw them.
- Three flasher effects that only run with a validated ball in play were rebuilt from code (57, 134
  breathing zen/video game flashers; 167 disc flashers); they are marked `code` in the CSV.
- Flashers are pulsed with the ROM's pulse time (`f_name: 64ms`). A few ROM pulses use a PWM
  pattern for brightness; those are approximated by a shorter pulse (inferred).

## Shaker motor

The ROM runs the shaker (coil 8) with `shaker_run(strength, min_setting)` from 46 display effects and
two switch handlers (drop targets, every ZUSE Fast Scoring hit). It only runs when adjustment 86
SHAKER MOTOR is at least `min_setting` (0 none, 1 minimal, 2 moderate, 3 maximal; default 3) and the
game is not tilted or over. Strength 1, 2 and 3 run the motor for about 75, 265 and 1100 ms (observed
on coil 8 in emulated play). `shaker.yaml` plays `shaker_strength_N` on each effect's event with a
condition on the `shaker_motor` setting, for example
`tron_gem_intro{settings.shaker_motor>=2}: shaker_strength_2`. Post `tron_shaker_drop_target` and
`tron_shaker_zuse_score` from those switch handlers. The shows enable and then disable coil 8, which
already has `default_hold_power` in `coils.yaml`.

## Service menu and settings

`service_menu.md` lists the ROM's full service menu: diagnostics (switch, coil, flasher, lamp,
trough, knocker, sound, display and burn-in tests, plus Tron's 3-bank motor, disc motor, recognizer
motor and fiber optic tube tests), audits, adjustments, utilities (install presets, custom message,
custom pricing, date and time, resets, USB) and the tournament and redemption menus. All 88
adjustments are in `config/settings.yaml` as MPF settings with the ROM's labels, defaults and
ranges; `setting_type` is `standard` or `feature` as in the ROM's two adjustment menus, and `sort`
keeps the ROM order. Settings with a very long range (scores, location ID) list a coarser ladder of
values; the ROM range is in the comment. The install presets and the 150 audit names are in
`service_menu.md` and `service_menu.json`.

## event_map.csv columns

| column | meaning |
|---|---|
| `deff`, `name` | ROM display effect number and package name |
| `mpf_event` | suggested event that plays the show (blank if the effect has no graphics, sound or tube show to package) |
| `shows`, `rom_text` | what is on screen; text strings taken from the ROM's message table (code) |
| `rom_trigger` | what starts it in the original game. From text, code and emulation; **inferred** unless backed by the next columns |
| `priority`, `background_loop` | ROM display priority (higher wins) and whether it runs until stopped |
| `animation_frames`, `run_ms` | frames in the exported animation and how long it ran when forced (observed) |
| `seen_in_emulated_play` | how many times it started during the 4 emulated games (observed) |
| `rendered_in_emulation` | `no` means the effect quit at once when forced, because it needs a game state the emulator did not have. Its folder then shows whatever was on screen, not the effect |
| `sounds_heard` | sound calls it played and when (observed) |
| `sounds_in_code` | sound calls its code can play (code), from `../callout_triggers.csv` |
| `tube_light_show` | tube show it started and when (observed) |
| `lamp_effect_in_code` | matrix lamp effect id(s) its code starts (code) |
| `lamp_effect_show` | the `lampfx_` show(s) its show now starts |
| `shaker` | shaker strength it runs and the minimum shaker setting (code) |
| `observed_on_switches` | switches that started it when hit during an emulated game (observed) |
| `library_animations` | animations from `media/dmd_library` it was seen drawing, including variants picked at random or by game state |
| `started_by_code`, `switches_reaching_start (depth)` | functions that start it, and switch handlers that reach those within N calls (code) |
| `rom_function` | address of the effect's code |

## How it was extracted

- **Images**: the ROM keeps an image table (8,181 entries, pointer at RAM 0x36f50, data in flash
  banks). Each image has a 13-byte header (id, flags, width, height, format) and one of six
  formats: raw, two run-length encodings (row or column order), packed 4-bit, and two delta formats
  that patch the previous frame. Flag bit 1 marks the last frame of an animation; that is how
  `dmd_library` splits them.
- **Effects**: the 145 display effects come from the table at 0x040e1350. Each was forced in
  PinMAME during a running game, with an ARM hook that logged every image draw, frame flip, sound
  call and tube colour. That gives the exact frames, timing, sounds and tube shows (observed).
- **Switches**: every playfield switch was then hit 6 to 10 times in an emulated game to see which
  effects, sounds and tube shows it starts (observed). Modes needing many shots were not reached
  this way.
- **Emulated play**: four games were then played automatically for 25 minutes each (ball trough,
  shooter lane, scoop and random shots), which reached the multiballs, Sea of Simulation, Flynn's
  Arcade and end-of-game sequences. That gives the game flow shows, the `seen_in_emulated_play` count,
  and effects 85, 99, 111, 112 and 115, which only run with real game state (observed).
- **Film clips**: the clip lists come from pointer tables the effects index (code), for example
  effect 48 picks `random(12)` from the table at 0x40d2804.
- **Timing**: frames are flipped by the OS display task, which ran at about 16 ms per tick in
  emulation. Most animations run at 49 ms per frame.

## Known gaps

- 121 of the 145 library animations are now tied to an effect, the attract cycle or the power-on
  logo. The other 24 (animations 9, 19, 103, 106-108, 120, 123-130, 132-140) are never referenced
  by the v1.74 game code and were never drawn in emulation, so they are most likely unused leftovers
  in this ROM version. They still have their own event (`tron_lib_anim_NNN`).
- Effect 22 is an empty function (unused); the tilt warning is effect 23. Effect 27 (instant info)
  was not captured because the emulation did not hold the flipper buttons. Effect 45 (Light Cycle
  Maze video mode) was not captured either: its start path has no caller in v1.74, so it may be
  unused (not verified). It is not part of Flynn's Arcade.
- Effect 127 is a debug image-sequence viewer, and 128/129 are clip players by number; none of the
  three is started by the game code.
- Lamp effects: 41 are not shows (34 empty in v1.74, 7 drawn from live mode state, see
  `lamp_effects.csv`). Effects started by your modes need you to post their event.
- `settings.shaker_motor` in a show_player condition assumes MPF exposes machine settings to
  conditions as `settings.<name>`; check this on your MPF version. If not, gate the shaker in code.
- Settings are checked to load as YAML with no duplicate keys; they were not run in MPF.
- Music: whether the ROM loops music beds was not verified; add `loops: -1` to music you want looped.
- Sounds: 17 sample streams the first export missed (sfx 0x09-0x14, 0x16-0x19 and music 0x44d) are
  now decoded, so 36 more sound calls have pools (290 in total). Samples 0x01-0x08 are channel-stop
  stubs, not audio.
- Effects with only text (score, "n more to ...") have no `animation.gif`; only the reference
  capture and the text strings.
- Switch numbers, coil numbers and the tube bus addresses are the original hardware's. Map them to
  your controller.
