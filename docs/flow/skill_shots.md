# Flow: skill shots (spec `rules/modes/skill_shots.md`, code block 0x01028a00-0x01029768)

```mermaid
flowchart TD
  S["Serve event 0xf, reason 3/4/5<br/>hook 0x01029148"] -->|"reason 1"| K["Kill all three<br/>0x010291a4"]
  S --> A0["Arm A: game flag 0x1e<br/>0x01028b58"]
  S -->|"adj 79 = 1"| B1["Start B now<br/>0x01028e04"]
  S -->|"adj 79 = 0"| B0["Arm B: flag 0x1f<br/>0x01028d44"]
  S --> C1["Start C now (task 0x74)<br/>0x01028f9c"]
  A0 -->|"sw12 ZEN closes, flag 0x1e"| A1["Start A (task 0x70)<br/>0x01028b74, 0x01028c18"]
  B0 -->|"sw23 opens + left flipper held, flag 0x1f"| B2["Start B (task 0x72)<br/>0x01028d60"]
  A1 --> T["Timeout objects: 3 distinct counting switches (event 0x6b)<br/>or one instant switch (0x6c)<br/>0x01028a00, 0x01028a84, 0x01028b04"]
  B1 --> T
  B2 --> T
  C1 --> T
  T -->|"done"| G["Grace: task id +1, sleep 93 ticks<br/>(still collectable, lamps off)"]
  T -->|"hook kills"| X["Skill shot gone"]
  A1 -->|"sw37 left ramp exit"| CA["Collect A: min(250k+50k*A,500k), deff 101<br/>0x010290ec counters"]
  B1 -->|"sw34 right ramp exit"| CB["Collect B: min(300k+50k*B,500k), deff 102"]
  C1 -->|"VUK sw11"| CC["Collect C: min(500k+50k*C,750k), deff 103<br/>held via 0x0100fbb0"]
  CA --> K
  CB --> K
  CC --> K
  G --> CA
  K --> E["Lamp/tube rules<br/>0x0102976c"]
```

Counters skA/skB/skC (RAM 0x2111814/18/1c + p-1) reset at the player's first ball (event 0x26, 0x010290ec).
