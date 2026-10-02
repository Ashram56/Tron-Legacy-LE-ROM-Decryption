# Tron Legacy LE 1.74: callouts and the switches that trigger them

## Files
- `samples/{speech,sfx,music}/XXXX.wav`: all 1,090 decoded samples (mono; speech is 12 kHz, sfx and music 24 kHz). The file name is the sample id.
- `samples_index.csv`: one row per sample, with its kind, duration and the sound calls that use it.
- `sound_calls.csv`: the game's 299 "sound calls". The code plays a call id, and the call picks one sample from its list.
- `switch_names.json`: switch number to name, taken from the ROM.
- `switch_sound_map.csv`: **the main result**. Each row links a switch to a sound call.
  - `source`: how the link was found.
    - `static(depth N)`: found by reading the switch handler's code, N calls deep.
    - `emulated`: heard when the switch was hit during a game in PinMAME.
  - `times_heard` / `hits`: how many plays were logged over how many hits of that switch.
  - `samples_heard`: the sample ids that actually played.
  - `all_samples`: every sample the call can pick from.
  - `wav`: the matching WAV files.
  - `generic = yes`: calls that sound for many switches, such as 0x0b1.

## How it was built
1. Decoded the sample directory and the IMA ADPCM streams from the ROM.
2. Traced static call paths from each switch handler to the play function `0x2c8f4`, which leads to `0x2c744` and then `0x2c1e4`.
3. Ran the ROM in libpinmame with a hook on the play function, after simulating the trough and plunger and starting a game. Each playfield switch was pulsed once in a sweep, then 6 times in a row in a second sweep.

## Caveats
- A rule only fires in the game state it needs. Callouts for modes, multiball, wizard modes and the video game will be missing until those states are reached.
- A few rows are sounds that happened to fire inside that switch's time window, such as music changes. They show up with a low `times_heard`.
- Speech often plays only on the hit that completes a target set. Example: TRON letters, where call 0x102 plays on completion.

## Decompiled game code (added later)
- `code/tron_game_decompiled.c`: all ~3,900 functions of the OS and game-rules code, decompiled by Ghidra into pseudo-C. It is readable but does not compile.
  - Functions renamed during analysis:
    - `swNN_*`: switch handlers.
    - `on_*`: the function that increments a named audit counter, such as `on_disc_multiball_started`.
    - `deff_N`: display effect N. These are DMD animations, and many of them play their own callouts.
    - `snd_play*`: plays a sound call. Each constant call id has a comment listing its kind and samples.
- `callout_triggers.csv`: one row per sound call (298 rows).
  - `heard_on_switches`: switches the call was heard on in the emulator.
  - `code_switches_direct`: switches whose handler plays the call within one step.
  - `code_switches_via_rules`: switches that reach the call through shot or mode logic, 2 to 5 steps away.
  - `feature`: the audit-counted feature that reaches the call within one step, for example Portal Multiball Awards.
  - `feature_guess_by_code_location`: the feature whose code sits right next to the call's code. Treat this as a likely guess, not a proof.
  - `display_effects`: display effects that play the call.
  - `code`: addresses of the functions that play the call, for looking them up in the C file.
