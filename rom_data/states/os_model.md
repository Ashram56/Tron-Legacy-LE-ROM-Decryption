# OS model (SAM OS in trn_174h, as used by Tron 1.74)

Data: `os_model.json`, which `rom_data/tools/states_build.py` builds. Its sections are `tick`, `rng`, `events`,
`tasks`, `switch_dispatch`, `deff_scheduler`, `rule_lists`, `game_flags` and `table_of_tables`.

Each section holds fact rows `{id, fact, value, address, tag, evidence}` plus tables:
- `events.events`: one row per event id, with its posters, its runtime hook order and its static hooks.
- `tasks.ids`: 137 task ids.
- `rule_lists.lists`: the 85 rule objects in RAM order.
- `game_flags.flags`: 56 flag descriptors.

## Tick
- **Tick length.** The tick is the 64th IO interrupt. The IRQ counter reloads to 0x40 at 0x120bc, and RAM 0x37364
  counts the ticks.
  - Nominal: 16.0 ms (15.97 ms in PinMAME).
  - Measured: 16.13 ms on average (attract 16.02, game 16.19). The ROM treats 62 ticks as one second.
- **Tick pass.** The scheduler 0x15a7c waits for the counter to change, then runs the tick pass 0x3405c:
  1. event 0x20;
  2. service calls, including the deff queue 0x27ff0;
  3. `rng_next`;
  4. the switch dispatcher 0xeadc → 0xe85c;
  5. 0xfec0;
  6. then the ready tasks run.

## RNG
- `seed = seed * 0x19660d + 1` (RAM 0x372c4). The seed is set to 0x4277dc9 at boot (0xc668).
- `random(n) = (n * next) >> 32`.
- `percent(p) = ((next * 100) >> 32) + 1 <= p`.
- The OS also advances the RNG once per tick, so results depend on timing. To force one result in the emulator, poke the
  seed at the call site (see match.md).

## Events
- `event_hook_add` 0x7944 keeps each list (RAM 0x3e3a0[id], id < 0x6d) sorted by **descending priority**. On equal
  priority, a new hook goes **after** the existing ones.
- `event_post` 0x79ec calls the hooks in that order. A hook that returns 0 **vetoes**: the chain stops and the post
  returns 0.
- Counts: 131 hook nodes in RAM, which equals the 131 static `event_hook_add` sites. There are 136 `event_post` sites.
- Many OS steps first post a "may I?" event and skip the step on a veto: 0x12 ball start, 0x1e end of ball, 0x2f game
  start, 0x47 next player, 0x55 slam, 0x14 bonus.

Ball/game event order (observed, see multiplayer.md):

| Moment | Events in order |
|---|---|
| Game start | 0x2f, 0x2e, then ball start, then 0x30 |
| Ball start | 0x12, [0x26 only on that player's first ball], 0x11, 0x27, ..., 0x13 |
| Drain | 0x1e, 0x1d, [bonus 0x14/0x16/0x15], 0x1f, next player 0x47/0x48, ball start |
| Tilt | 0x66, 0x65, 0x67 |
| Tilt warning | 0x68, 0x69 |
| Slam | 0x55, 0x54 |
| Switches | 0x6c (instant), 0x6b (counting), 0x6a (playfield validated) |

The event names in `os_model.json` are short labels taken from `game_flow.md`, `developer_guide.md` and these
traces. The posting function and site are listed next to each id.

## Tasks
- Task ids are u16 numbers that the caller picks; they are not handles.
- API:

  | Function | Address |
  |---|---|
  | `task_create` | 0xb624 |
  | `create_unique` | 0xb718 |
  | `recreate` | 0xb76c |
  | `timer_start` | 0xb7d0 |
  | `timer_restart` | 0xb808 |
  | `set_id` | 0xc0d0 |
  | `kill(id, mask)` | 0xba3c |
  | `kill_range` | 0xbb40 |
  | `running` | 0xbe68 |
  | `running_range` | 0xbecc |
  | `spawn_child` | 0xb840 |

- Fixed ids:
  - 2 = the running display effect (deff);
  - 3 = lamp effects (leffs);
  - 0x29 = game start;
  - 0x2a = end of ball;
  - 0x2b = ball search;
  - 0x39 = slam reset.
- Each switch handler runs as a task. Its id comes from switch descriptor +0x14.
- `tasks.ids` merges every static creation site that has a constant id with every `task_start` seen in all traces:
  the 30 in `rules/traces` plus the 11 here. That gives 137 ids, 100 of them observed.

## Switch dispatch order
For each switch, once per tick, the dispatcher (0xe85c):
1. Debounces it (counters at desc +0x1b and +0x1c).
2. Reports the edge only if it is enabled: a close needs desc flags (+0xe) & 0x400; an open needs & 0x800.
3. **Applies the game-state gate:** the edge passes if `gf_state == 0` or `(flags & gf_state) != 0`. While tilted
   (0x200) or in attract (0x10), only switches that carry that bit run.
4. Calls `task_create(desc+0x14, handler, desc+0xc, 0x300)`, with the switch number at task +0x30. This only queues
   the task.
5. Synchronously posts event **0x6c** (flag 0x2000, instant/force switch) or **0x6b** (flag 0x1000, counting
   switch).
6. The handler task body runs later, in the task pass. So the valid-playfield hooks on 0x6b/0x6c always run **before**
   the switch's own handler.

## Deff scheduler

| Item | Rule |
|---|---|
| Table | Entry 0x36c54 of the table of tables → 0x040e1350 (146 entries): `{fn, u16 flags, u8 prio}` |
| Start | `deff_start` 0x280b0 starts a deff only if all of these hold: (1) the caller is not a deff task; (2) no deff is running, OR the running one is the background deff, OR the new one is not a background deff; (3) force, OR new prio > current prio (0x381aa), OR the prio is equal and the current deff has flags & 3. |
| Effects of a start | All deff tasks are killed. Then `task_create(2, fn, 0x806 [+0x2000 if !(flags & 5)])`, the id is stored at 0x381a8, event 0x1b is posted, and DMD pages are allocated (unless flags & 0x10). |
| Queue | A deff that cannot start, has (arg a OR flags 0x20), and is not a background deff goes into a ring at 0x3d540: 12 slots of 0x6c B (11 usable), head 0x381b0, tail 0x381b4. A full ring raises error 0x23. Every tick, 0x27ff0 starts the head of the queue when no deff runs; otherwise it restarts the background deff (flag bit 0, id at 0x381ae). |
| Stop | `deff_stop` 0x282e0(id, run_queue, restart_background) |

## Rule lists (RAM 0x3e560[0..5])
Each rule object holds `{fn, mode_mask u16 +4, p6, prio +7, vtable +8, cond +0xc, id +0x10}`.
- `rule_obj_init` 0x194f8 keeps each list sorted by priority.
- `rules_refresh_request` 0x19648 (116 call sites) triggers a re-evaluation: every rule whose mode mask matches and
  whose `cond()` is true gets its effect started, and the others are stopped.

| List | Kind | vtable | Count in RAM | Static init sites |
|---|---|---|---|---|
| 0 | task rule | 0x39fa8 | 1 | |
| 1 | function rules, mask 0x3ff (mech upkeep) | 0x39fa8 | 6 | |
| 2 | **deff rules**: id = deff number, started at 0x19940. The init 0x1982c is named `lamp_rule_init` in the decompile, but it builds deff rules. | 0x39f60 | 16 | 16 |
| 3 | leff rules (init 0x19740), started at 0x19814 | 0x39f88 | 32 | 32 |
| 4 | tube-show rules (init 0xda4), started at 0xe78 | 0x39b08 | 18 | 18 |
| 5 | lamp functions, mask 0x20 | 0x39fa8 | 12 | |

## Game flags and per-player swap
- **Storage.** The 56 game flags live in one 8-byte block (pointer 0x37268). There are four 8-byte player slots at
  0x3c188[0..3].
- **Descriptors.** Table 0x040e1f6c has 4 B per flag: a u16 class and a u8 default (all defaults are 0).
- **Class bits:**

  | Bit | Meaning |
  |---|---|
  | 0 | global: not swapped between players |
  | 1 | reset at game start (0x205f4) |
  | 2 | reset at every ball start (0x206ac) |
  | 3 | reset at tilt (flag 46 only) |

- **Swap on a player change.** 0x214d0 calls these in order:
  1. 0x6700 saves the block into the old player's slot;
  2. 0x6744 restores every flag whose bit 0 is clear from the new player's slot;
  3. the same is done for the lamp states (0x21080 / 0x210d4); lamps 26 SHOOT AGAIN, 65 START and 66 TOURNAMENT are
     global and are not swapped.
- **Per-player flags:** 16-27, 32-35, 38, 40, 44, 45, 47, 48, 49 and 51. All the others are global.
- `developer_guide.md` already says flags are saved per player but marks it "inferred, not tested". The code now
  confirms it, and multiplayer.md shows it in play.

## Open
- Most event ids have only a posting-site name, not a meaning.
- The `dump_tasks` layout (task id offset) is not verified, so `os_model.json` uses `task_start` events instead.
- The exact semantics of deff flags 0x2 and 0x4 beyond the start rule are not traced.
