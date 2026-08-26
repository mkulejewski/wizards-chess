# AGENT_INSTRUCTION — Stage 2.7: Launch Configuration and Game Setup

## Mission

Improve Wizard Chess launch and game-configuration usability so that a normal graphical session can be started with:

```bash
uv run wizard-chess
```

without requiring the user to repeatedly enter long environment-variable invocations such as:

```bash
env \
  WIZARD_CHESS_ENGINE_ENABLED=true \
  WIZARD_CHESS_ENGINE_PATH=/home/mkulejewski/.local/bin/stockfish \
  WIZARD_CHESS_WHITE_PLAYER=engine \
  WIZARD_CHESS_ENGINE_STRENGTH=strong_club \
  WIZARD_CHESS_ENGINE_TIME_MS=2500 \
  uv run wizard-chess
```

The application already has:

- centralized/version-tolerant settings;
- XDG-backed `settings.json` persistence;
- configurable human/engine player types;
- Stockfish configuration;
- GUI controls;
- environment-variable configuration;
- a PySide6 desktop application.

Extend those existing mechanisms. Do not introduce a parallel configuration architecture merely for this feature.

The principal UX target is:

> Configure the desired game and Stockfish options graphically once; thereafter launch Wizard Chess normally with `uv run wizard-chess`.

---

# 1. Design decision

Do **not** treat `uv` configuration as the application's primary configuration mechanism.

`uv` is responsible for running/managing the Python project. Player type, Stockfish strength, engine path, clocks, analysis settings, etc. are application preferences and should be represented by Wizard Chess itself.

Do not solve the task merely by:

- adding a shell alias;
- adding a shell script containing hard-coded environment variables;
- adding a `.env` file as the main UI;
- adding project-specific configuration to the user's shell startup;
- hard-coding the developer's Stockfish path;
- adding a second configuration file unrelated to the existing settings persistence.

Such conveniences may hide the original command but do not solve the application's configuration UX.

---

# 2. Target configuration model

Use three configuration layers, from lowest to highest precedence:

```text
built-in defaults
        ↓
persistent Wizard Chess settings
        ↓
environment-variable / explicit CLI overrides
```

The exact implementation should follow the repository's existing settings architecture, but the intended precedence is:

```text
explicit CLI override, where applicable
    >
WIZARD_CHESS_* environment variable
    >
persisted user preference
    >
application default
```

This preserves current scripting/testing/developer workflows while allowing ordinary GUI users to stop using environment variables.

Do not duplicate parsing of configuration values across GUI, CLI, and composition code.

There should remain one typed settings/configuration model.

---

# 3. Persistent settings

Wizard Chess already persists preferences under the XDG configuration location, typically:

```text
~/.config/wizard-chess/settings.json
```

Extend the existing version-tolerant settings mechanism.

Do not replace it.

At minimum, make the following existing configuration persistable where it is not already persistable:

```text
engine enabled / available
engine executable path
live analysis enabled
engine time per move/request
engine depth, if set
MultiPV
engine strength
engine threads
engine hash size

default White player type
default Black player type
White player name
Black player name

clock enabled
clock initial time
clock increment

voice language where appropriate
```

Preserve compatibility with old settings files.

Missing fields from an older schema must load using current defaults.

Unknown/nonessential older settings should not make the application unlaunchable.

Do not store machine-specific values in the repository.

The user's local Stockfish path may be persisted in their own settings file, but must never be committed as a project default.

---

# 4. Add a Game Setup dialog

Introduce a clean PySide6 **Game Setup** dialog.

This dialog represents the configuration for starting a new chess game rather than general application internals.

Use it at application startup according to the startup behavior described below, and expose the same dialog from the normal GUI for starting a new game.

A suitable menu/button name is:

```text
New Game…
```

or:

```text
Game Setup…
```

Prefer one coherent workflow rather than separate competing dialogs.

## Required primary controls

At minimum show:

### White

```text
Player:
  Human
  Stockfish

Name:
  <text field>
```

### Black

```text
Player:
  Human
  Stockfish

Name:
  <text field>
```

### Engine settings relevant to this game

When at least one side is Stockfish, expose the important engine choices prominently:

```text
Strength:
  beginner
  casual
  club
  strong_club
  expert
  master
  maximum

Think time:
  <milliseconds or a user-friendly seconds control>
```

The existing strength semantics must remain unchanged.

If the UI presents time in seconds, convert it to the existing internal millisecond representation rather than changing engine semantics.

### Clock

Expose the existing clock configuration compactly:

```text
[ ] Use clock

Initial time:
Increment:
```

Do not overload the primary dialog with every low-level UCI tuning option.

MultiPV, threads, hash size, depth, etc. can belong to Preferences / Advanced Engine Settings.

---

# 5. Add persistent Engine Preferences

Add a Preferences/Settings UI for Stockfish configuration.

A reasonable structure is:

```text
Preferences
└── Engine
```

or an equivalent idiomatic Qt structure.

Required controls:

```text
Stockfish executable:
[path field] [Browse…]

[Test Engine] / [Validate]

Default strength:
[combo box]

Default think time:
[value]

[ ] Enable live analysis

Advanced:
  MultiPV
  Depth
  Threads
  Hash size
```

Follow the repository's current engine configuration semantics.

## Stockfish executable behavior

Do not hard-code:

```text
/home/mkulejewski/.local/bin/stockfish
```

or:

```text
/usr/bin/stockfish
```

as an application requirement.

Preferred resolution behavior:

1. use an explicit environment/CLI override if supplied;
2. otherwise use the persisted path if configured;
3. otherwise try the existing `stockfish` discovery on `PATH`;
4. otherwise report that Stockfish is unavailable.

The Browse button should let the user select a local executable.

The selected path should be saved in the application's persistent user settings.

---

# 6. Engine validation

Provide a small, non-destructive way to validate the configured executable.

For example:

```text
Test Engine
```

The operation should:

1. check that the executable can be resolved/launched using the existing engine adapter;
2. perform the smallest reasonable UCI handshake or equivalent existing initialization;
3. report success cleanly;
4. close any temporary process it owns;
5. report a controlled, user-readable error on failure.

Do not leave a Stockfish process running merely because the Preferences dialog tested it.

Do not duplicate UCI protocol code in the GUI.

Use the existing engine abstraction/adapters.

---

# 7. Avoid contradictory engine settings

The GUI should not permit a nonsensical configuration such as:

```text
White = Stockfish
Engine disabled
```

Selecting Stockfish as either player should imply that the engine is required.

Prefer deriving engine necessity from the selected features rather than forcing the user to understand a low-level `ENGINE_ENABLED` flag.

Conceptually:

```text
engine_required =
    white_player == engine
    or black_player == engine
    or live_analysis_enabled
```

The existing lower-level setting may remain internally/backward-compatibly if needed.

Do not require the user to separately check "Enable Engine" after already choosing "Stockfish" as a player.

If the engine cannot be resolved, explain the issue and allow the user to:

- configure the engine path; or
- change the affected player back to Human.

Do not crash the entire application.

---

# 8. Startup behavior

Implement a comfortable first-run and subsequent-run workflow.

## First run / no saved setup

When no meaningful saved game setup exists, launching:

```bash
uv run wizard-chess
```

should open the GUI and present the Game Setup dialog before starting ordinary play.

The user can choose, for example:

```text
White: Stockfish
Black: Human
Strength: strong_club
Think time: 2.5 s
```

and start the game.

## Remembering setup

Provide a clearly named option such as:

```text
[x] Remember these choices
```

and/or:

```text
[x] Start with this setup automatically next time
```

Do not make the exact checkbox wording architecturally significant.

The important behavior is that a user can configure Wizard Chess once and subsequently launch with:

```bash
uv run wizard-chess
```

without entering engine environment variables again.

## Startup-dialog preference

Support both reasonable workflows:

### Workflow A — ask every launch

```text
uv run wizard-chess
→ Game Setup
→ Start Game
```

### Workflow B — reuse last setup automatically

```text
uv run wizard-chess
→ board opens using saved setup
```

A user preference should select between them.

Do not force one extra setup click on every launch if the user explicitly chooses to reuse their last configuration automatically.

Provide a normal GUI action to reopen Game Setup later.

---

# 9. Useful game presets

If this can be implemented cleanly without substantial complexity, add quick presets to Game Setup:

```text
Human vs Human
Human vs Stockfish
Stockfish vs Human
Stockfish vs Stockfish
```

A preset must simply populate the ordinary typed settings.

Do not introduce a second game-mode state machine.

For example:

```text
Human vs Stockfish
```

should be semantically identical to setting:

```text
White player = human
Black player = engine
```

manually.

Preserve support for both engine-as-White and engine-as-Black.

---

# 10. New Game semantics

Applying Game Setup should create/reset the game through the existing application/session architecture.

Do not have the dialog mutate `ChessGame` directly.

Preserve the existing hierarchy where authoritative chess mutation flows through `GameSession` / application services.

Starting a configured new game must:

1. atomically apply the intended player/session settings;
2. create/reset the authoritative game using the existing workflow;
3. correctly start an engine move when Stockfish is to move;
4. preserve clocks, metadata, events, autosave, GUI refresh, and analysis behavior;
5. avoid accidentally creating two sessions or two competing authoritative boards.

Do not create a GUI-owned chess state.

---

# 11. Special case: engine as White

This workflow must be explicitly tested:

```text
White: Stockfish
Black: Human
```

After the game starts from the ordinary initial position:

- the authoritative game is initialized once;
- the engine asynchronously calculates White's first move;
- the GUI remains responsive;
- the move goes through the normal `GameSession` engine-move path;
- a normal `MoveExecuted` event is produced;
- future Stage 3 consumers would see exactly the same canonical move event as before.

Do not implement a special GUI-only mutation path for the first engine move.

---

# 12. Environment variables remain supported

All currently documented `WIZARD_CHESS_*` configuration must continue to work.

In particular preserve compatibility with at least:

```text
WIZARD_CHESS_ENGINE_ENABLED
WIZARD_CHESS_ENGINE_PATH
WIZARD_CHESS_ANALYSIS_ENABLED
WIZARD_CHESS_ENGINE_TIME_MS
WIZARD_CHESS_ENGINE_DEPTH
WIZARD_CHESS_ENGINE_MULTIPV
WIZARD_CHESS_ENGINE_STRENGTH
WIZARD_CHESS_ENGINE_THREADS
WIZARD_CHESS_ENGINE_HASH_MB

WIZARD_CHESS_WHITE_PLAYER
WIZARD_CHESS_BLACK_PLAYER
WIZARD_CHESS_WHITE_NAME
WIZARD_CHESS_BLACK_NAME

WIZARD_CHESS_CLOCK_ENABLED
WIZARD_CHESS_CLOCK_SECONDS
WIZARD_CHESS_CLOCK_INCREMENT_SECONDS
```

Do not remove environment-variable support merely because the GUI can now edit the corresponding preferences.

Environment variables are valuable for:

- tests;
- CI;
- development;
- scripts;
- reproducible demonstrations;
- headless launches.

An explicitly supplied environment variable must override the saved preference for that process.

Example:

if persistent settings contain:

```text
engine strength = club
```

but the process is launched with:

```bash
WIZARD_CHESS_ENGINE_STRENGTH=expert uv run wizard-chess
```

that process must use `expert`.

The persistent preference itself need not be overwritten merely because a one-shot environment override was supplied.

---

# 13. CLI behavior

Do not make `--cli` display a Qt setup dialog.

This must remain valid:

```bash
uv run wizard-chess --cli
```

The retained CLI may consume persisted defaults through the central settings system where appropriate, but it must remain headless.

Likewise:

```bash
uv run wizard-chess --script examples/game.txt
```

must not unexpectedly open GUI configuration windows.

Preserve deterministic scripted-game behavior.

If useful and easy to integrate, add:

```bash
uv run wizard-chess --setup
```

to force the GUI Game Setup dialog at launch.

This flag is optional if the GUI already makes setup easily discoverable. Do not expand the task into a large CLI redesign.

---

# 14. Settings architecture

Inspect the repository before implementing this.

Reuse the existing:

- settings dataclasses/models;
- persistence layer;
- environment parsing;
- composition root;
- GUI architecture;
- engine port/adapter;
- player-type representation.

Do not create GUI-specific duplicate settings objects unless they are temporary editable/view-model values.

A good conceptual flow is:

```text
defaults
   ↓
persistent SettingsStore
   ↓
environment / CLI overrides
   ↓
effective typed application settings
   ↓
composition root
   ↓
GameSession + adapters
```

For edits from the GUI:

```text
Preferences / Game Setup
   ↓
validated typed values
   ↓
existing settings persistence
   ↓
new/effective session configuration
```

Keep filesystem access inside the persistence boundary.

Do not make Qt widgets write JSON directly.

---

# 15. Distinguish preferences from active game state

Be careful not to conflate:

```text
saved defaults
```

with:

```text
currently running game
```

Changing a default player type in Preferences should not silently replace a player in a game already underway unless the existing UX explicitly supports such a transition.

Prefer applying player/setup choices when starting a new game.

General preferences such as live-analysis display may remain dynamically adjustable if the existing implementation already supports that safely.

When a setting requires a fresh session/game to take effect, make that behavior explicit.

---

# 16. Persistence semantics

When the user accepts a Preferences dialog:

- validate values;
- write them using the existing settings store;
- use atomic/safe persistence if already provided by the repository;
- keep older settings schema compatibility.

When the user cancels the dialog:

- do not persist partial changes;
- do not partially reconfigure a running engine;
- preserve the previous effective configuration.

Likewise, cancelling Game Setup should not partially reset the existing game.

---

# 17. Error handling

Configuration errors must be controlled application errors, not uncaught exceptions.

Handle at minimum:

### Missing saved executable

A previously persisted Stockfish binary may later be deleted or moved.

Report that clearly.

Allow the user to browse for another executable.

### Invalid executable

If the selected file is not a working UCI engine, report a useful error.

### Permission denied

Report the failure rather than crashing.

### Engine process failure

Preserve the existing graceful optional-component behavior.

### Invalid numeric settings

Do not allow nonsensical values such as:

```text
think time <= 0
threads <= 0
hash <= 0
MultiPV <= 0
negative clock values
```

Use appropriate Qt controls/ranges and domain/settings validation.

---

# 18. UX requirements

The default Game Setup dialog should be comprehensible without knowing any environment-variable names.

Do not expose labels such as:

```text
WIZARD_CHESS_ENGINE_TIME_MS
```

as the primary GUI terminology.

Prefer:

```text
Think time
Strength
White player
Black player
Stockfish executable
Live analysis
```

The README may continue documenting environment-variable names for advanced users.

Make common choices visible and advanced engine tuning secondary.

The user's most common engine launch:

```text
White: Stockfish
Strength: strong_club
Think time: 2500 ms
```

should require only a few obvious GUI interactions.

---

# 19. Optional polish: last configuration summary

If it fits naturally, display the effective game configuration in a compact location before/after starting, for example:

```text
White: Stockfish — Strong Club — 2.5 s
Black: Human
```

or equivalent.

This is optional.

Do not clutter the chessboard UI merely to implement it.

---

# 20. Documentation

Update `README.md`.

The primary launch documentation should become:

```bash
uv sync
uv run wizard-chess
```

Explain that game and engine settings can be configured from the GUI and are persisted.

Document the intended flow, for example:

```text
1. Launch Wizard Chess.
2. Open Game Setup / Preferences.
3. Select the Stockfish executable if it is not on PATH.
4. Choose Human or Stockfish for each player.
5. Choose strength and think time.
6. Save the configuration.
7. Future launches require only `uv run wizard-chess`.
```

Retain an **Advanced / environment configuration** section documenting the `WIZARD_CHESS_*` variables.

Do not remove those examples.

Clarify the precedence of:

```text
CLI/environment override
persistent settings
defaults
```

Update the development increment ledger with this usability increment and its verification status.

Do not claim manual real-Stockfish verification if it has not actually been performed.

---

# 21. Required tests

Add focused unit, persistence, GUI, and integration tests.

At minimum cover:

## Settings persistence

1. Engine path round-trips through the existing settings store.
2. Engine strength round-trips.
3. Engine think time round-trips.
4. White/Black default player types round-trip.
5. startup setup preference round-trips.
6. old settings files without the new fields still load.
7. malformed optional settings fail gracefully according to existing conventions.

## Precedence

Given:

```text
persisted strength = club
environment strength = expert
```

verify the effective value is:

```text
expert
```

Without the environment value, verify it is:

```text
club
```

## Game Setup GUI

Test at least:

```text
Human vs Human
Human vs Stockfish
Stockfish vs Human
Stockfish vs Stockfish
```

Verify that accepting setup produces the expected application/session configuration.

Verify Cancel does not reset/mutate the game.

## Automatic startup

Test:

- first-run/default behavior;
- saved "show setup" behavior;
- saved "reuse last setup" behavior.

Keep GUI tests deterministic and independent of a real engine binary.

## Engine validation

Use fakes/mocks to test:

- successful validation;
- executable unavailable;
- startup failure;
- clean process closure.

## Engine as White

Use `FakeEngine` to verify:

```text
White = engine
Black = human
```

starts the ordinary asynchronous engine-reply workflow and eventually executes the fake engine's move through the canonical session path.

## Backward compatibility

Existing environment-only launches must still resolve to equivalent settings.

Existing human-vs-human defaults must still work without Stockfish.

Existing CLI and scripted runner tests must remain headless.

---

# 22. Real-machine acceptance scenario

After automated implementation, document this manual acceptance scenario without pretending it was run if the environment cannot run the real binary.

On the developer's machine:

1. Launch:

```bash
uv run wizard-chess
```

2. In Preferences select:

```text
/home/mkulejewski/.local/bin/stockfish
```

3. Configure:

```text
White: Stockfish
Black: Human
Strength: strong_club
Think time: 2.5 seconds
```

4. Choose to remember/reuse the setup.

5. Close Wizard Chess.

6. Relaunch using only:

```bash
uv run wizard-chess
```

7. Verify:
   - the saved setup is restored;
   - no environment variables are necessary;
   - Stockfish makes White's opening move;
   - the GUI stays responsive;
   - game state/history update normally;
   - exiting closes the engine process.

8. Open Game Setup and switch to:

```text
White: Human
Black: Stockfish
```

and verify the reverse opponent configuration works.

---

# 23. Non-goals

Do not add:

- a second chess engine;
- engine downloading/install management;
- cloud configuration;
- online accounts;
- networking;
- physical board controls;
- GPIO;
- motors;
- sensors;
- calibration;
- path planning;
- a new chess-rules implementation;
- a new persistence framework;
- a shell-specific mandatory launcher;
- hard-coded user paths.

Stage 3 physical-board work remains outside this increment.

Do not alter the canonical `MoveExecuted` seam.

---

# 24. Quality requirements

Run the complete repository quality suite:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

All checks must pass.

Also perform the repository's existing scripted-game smoke test if still applicable:

```bash
uv run wizard-chess --script examples/game.txt
```

Do not weaken existing tests to make the implementation pass.

Prefer small, cohesive changes over broad refactoring.

Preserve typing quality and the existing ports-and-adapters boundaries.

---

# 25. Acceptance criteria

This increment is complete when all of the following are true:

1. The normal GUI launch command is simply:

```bash
uv run wizard-chess
```

2. A user can configure Human/Stockfish player sides from the GUI.

3. The Stockfish executable can be selected graphically and persisted.

4. Strength and think time can be configured graphically and persisted.

5. Saved game/setup defaults can be reused on subsequent launches.

6. A user can choose whether Game Setup appears on startup or the last setup starts automatically.

7. Selecting Stockfish as a player does not require separately understanding an `ENGINE_ENABLED` environment variable.

8. Environment variables remain supported as process-level overrides.

9. Old settings files remain loadable.

10. No real Stockfish installation is necessary for automated tests.

11. Engine-as-White starts through the existing asynchronous `GameSession` path.

12. Engine-as-Black continues to work through the existing path.

13. `--cli` and `--script` remain headless.

14. The application behaves gracefully when a persisted engine path becomes unavailable.

15. README documents GUI configuration as the normal workflow and environment variables as an advanced override mechanism.

16. The development increment ledger is updated accurately.

17. `pytest`, Ruff, Ruff formatting check, and Pyright all pass.

---

# 26. Final implementation report

When finished, report:

- files changed;
- existing settings architecture reused;
- new persisted fields;
- Game Setup UX implemented;
- Preferences/Engine UX implemented;
- configuration precedence implemented;
- startup behavior;
- backward compatibility behavior;
- tests added or changed;
- whether a real Stockfish binary was available for manual acceptance;
- exact results of:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

- scripted-game smoke-test result, if applicable.

Do not claim functionality was manually verified with real Stockfish unless that verification was actually performed.