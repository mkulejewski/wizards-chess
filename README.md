# Wizard Chess

Wizard Chess is a local, voice-capable chess application and the authoritative software
digital twin for a future physical chessboard. The Stage 2.x application supports terminal,
PySide6 GUI, English and Polish voice commands, optional Stockfish play/analysis, PGN/FEN,
autosave recovery, clocks, and deterministic developer workflows.

Every input path converges on one `GameSession` and one `ChessGame`. `python-chess` remains
the sole source of legality, position state, SAN/UCI, check, mate, and draw rules. Optional
engine and speech failures never prevent ordinary typed or graphical human-vs-human play.

## Architecture

```text
CLI / GUI / English voice / Polish voice / script / engine reply
                              │
                              ▼
                   language-independent intent
                              │
                              ▼
                    position-aware resolver
                              │
                              ▼
                         GameSession
                  ┌───────────┼───────────┐
                  ▼           ▼           ▼
             ChessGame    persistence   engine/analysis
                  │
                  ▼
             MoveExecuted event
                  │
                  ▼
              HardwareCoordinator
             ┌────────┴────────┐
             ▼                 ▼
    PhysicalBoardState  PhysicalMovePlanner
                                │
                                ▼
                          HardwarePort
                                │
                                ▼
                         FakeHardware
```

- `domain` owns authoritative chess state, metadata, termination states, and move events.
- `commands` produces state-free coordinate, SAN, contextual move, and application intents.
- `application` coordinates all moves, clocks, scripts, autosave, engine moves, and adapters.
- `engine` contains the replaceable engine port, lazy Stockfish/UCI adapter, normalized
  White-perspective evaluations, candidate lines, and deterministic fake.
- `analysis` owns live-result orchestration and the temporary per-game cache, and separately
  replays copies of games, classifies moves, calculates statistics, and persists optional
  versioned annotations.
- `speech` owns bounded capture, recognizers, English/Polish normalization, confidence data,
  confirmation policy, and test doubles.
- `gui` renders only authoritative snapshots and runs voice, live analysis, engine replies,
  and post-game analysis outside the Qt event thread.
- `persistence` owns PGN, recovery, settings, and analysis filesystem access.
- `hardware` consumes canonical move events through a replaceable coordinator; it never
  authorizes moves or mutates `ChessGame`.

## Stage 3.1 hardware foundation

Stage 3.1 models physical-board control without connecting to real hardware. Four state domains
remain deliberately separate:

- `ChessGame` / `GameSession` own the authoritative logical chess position, legality, notation,
  history, and results.
- `PhysicalBoardState` is an immutable belief about physical piece identities and locations.
- `HardwareControllerState` tracks the controller lifecycle from disconnected through homing,
  ready, executing, fault, and emergency stop.
- `PhysicalSynchronization` describes whether believed physical placement is synchronized,
  executing, desynchronized, or unknown relative to the digital position.

When hardware participation starts, physical placement is explicitly seeded from an
authoritative position. With no sensors in this stage, that seed is an assumption rather than
an observation. A canonical `MoveExecuted` event is converted to a hardware-neutral request;
`PhysicalMovePlanner` currently plans only ordinary non-capturing moves as `MoveTo`,
`SetMagnet(True)`, `MoveTo`, and `SetMagnet(False)`. `FakeHardware` executes and records this
typed sequence deterministically behind `HardwarePort`.

Physical placement changes only after every operation completes. A partial failure leaves the
already-legal digital move intact, faults or stops the controller as appropriate, marks the
moving piece's physical location unknown, and never generates a chess undo. Captures, castling,
en passant, and promotion are recognized but explicitly desynchronize the physical layer
because their movement sequences are deferred. New Game, FEN/PGN replacement, and Undo also
mark existing physical assumptions desynchronized; explicit initialization is required before
physical execution resumes.

There is no serial transport, Arduino firmware, GPIO, motor control, real homing, calibration,
obstacle avoidance, or board sensing yet. The Stage 3.1 fake, operation trace, failure injection,
reconciliation comparison, and lifecycle APIs are intended for deterministic testing and for a
future worker-backed adapter that does not block the Qt thread.

## Setup and launch

Install Python 3.12+ and [`uv`](https://docs.astral.sh/uv/):

```bash
uv sync
uv run wizard-chess
```

The GUI is the default. Start the retained terminal adapter with:

```bash
uv run wizard-chess --cli
```

On the first graphical launch, **Game Setup** asks who controls White and Black, player names,
Stockfish strength/think time when needed, and clock settings. Keep **Remember these choices**
and **Start with this setup automatically next time** selected to make later launches open the
saved game configuration immediately. Use **New Game…** to change sides later, or launch with
`uv run wizard-chess --setup` to force the dialog once.

Keyboard, GUI, PGN/FEN, clocks, and human-vs-human play do not require a microphone or
Stockfish.

## Logging

Wizard Chess logs meaningful startup, game, command, voice, engine, analysis, hardware, and
shutdown events to the terminal at `INFO` by default. It simultaneously writes a more detailed
UTF-8 log to `$XDG_STATE_HOME/wizard-chess/logs/wizard-chess.log`, or
`~/.local/state/wizard-chess/logs/wizard-chess.log` when `XDG_STATE_HOME` is unset. The file
rotates at 10 MiB and retains five backups.

```bash
uv run wizard-chess
uv run wizard-chess --log-level DEBUG
uv run wizard-chess --log-level WARNING
uv run wizard-chess --log-level ERROR
uv run wizard-chess --log-level OFF
uv run wizard-chess --log-file ./logs/session.log
uv run wizard-chess --no-log-file
uv run wizard-chess --no-terminal-log --log-file ./logs/session.log
```

`DEBUG` adds parsed intents, resolved legal-move candidates, FEN/state transitions, engine search
details, speech-pipeline state, and physical motion plans. `INFO` follows normal operation;
`WARNING` shows recoverable problems; `ERROR` shows failed operations; and `OFF` suppresses normal
application logging. Level names are case-insensitive. `--log-file PATH` creates missing parent
directories and does not disable terminal output. `--no-log-file` and `--no-terminal-log` control
the two destinations independently; `--terminal-log` can explicitly re-enable terminal output.

The equivalent environment settings are `WIZARD_CHESS_LOG_LEVEL`,
`WIZARD_CHESS_TERMINAL_LOG`, `WIZARD_CHESS_LOG_FILE_ENABLED`, and `WIZARD_CHESS_LOG_FILE`.
Launcher options take precedence over these environment values and persisted/default settings.
File entries include full timestamps, logger names, and exception tracebacks where applicable.

## Desktop usability

The GUI provides:

- click-to-move with legal destinations, last-move highlighting, promotion choice, and flip;
- offline Tatiana or classic-symbol pieces plus five persistent board color themes;
- typed SAN, coordinate syntax, and application commands;
- move history plus a ply slider for inspecting old positions without changing the live game;
- Game Setup/New Game, Engine Preferences, Undo, Redo, FEN load/copy, and PGN import/export;
- optional clock start/pause/reset and English/Polish voice-language selection;
- non-blocking fixed-time or continuous live evaluation, principal variation, and a vertical
  White/Black evaluation sidebar;
- cached historical evaluations and an in-window advantage graph after the game ends;
- non-blocking engine opponent replies and post-game analysis with progress and summaries;
  **Analyse game** immediately preempts any ongoing live-position analysis;
- Undo remains available while an engine is thinking and cancels the pending engine result;
- visible, recoverable errors when voice, microphone, model, or engine is unavailable.

Moves accept SAN (`e4`, `Nf3`, `exd5`, `O-O`, `e8=Q`) and coordinate forms (`e2 e4`,
`e2-e4`, `move e2 to e4`). Contextual phrases are resolved only against current legal moves;
ambiguous phrases are rejected with legal origin squares rather than guessed.

Application commands include `undo`, `redo`, `new game`, `resign`, `draw`, `propose draw`,
`accept draw`, `reject draw`, `save`, `repeat`, `fen`, `pgn`, `legal`, `help`, and `quit`.
In a human-vs-human game, the first `draw` offers and a consecutive second `draw` accepts;
an intervening legal move rejects the offer. English variants such as `offer a draw`,
`accept the draw`, and `decline draw`, plus equivalent Polish phrases, use the same flow.
The desktop **Offer Draw** button becomes **Accept Draw** while an offer is pending, and the
answering player can use **Reject Draw**. Another offer is blocked while the rejected position
remains unchanged; after any position change, an offer is possible again—even if play or history
later returns to the same position. When threefold repetition or the fifty-move rule is claimable,
the button becomes **Claim Draw** and a human player's draw action ends the game immediately,
without opponent acceptance. Ordinary offers require two human players, while **Resign** is
available only when the side to move is human-controlled. During full-game analysis,
**New Game…** remains available and cancels the running analysis before opening game setup.

## Stockfish

Wizard Chess bundles the official Stockfish 18 baseline build for Linux x86-64. The compressed
asset is verified and extracted on first use to
`$XDG_CACHE_HOME/wizard-chess/engines` or `~/.cache/wizard-chess/engines`; it is not added to or
allowed to mutate the process-wide `PATH`. Platforms for which a bundle is not present retain
system `PATH` discovery and the graphical executable selector. The normal graphical workflow is:

1. Launch `uv run wizard-chess`.
2. Leave the executable blank to use automatic discovery, or open **Preferences…** and select a
   different Stockfish or compatible UCI executable.
3. Use **Test Engine** to validate the executable.
4. In **Game Setup**, choose Human or Stockfish for White and Black.
5. Choose strength and either **Fixed analysis time per move** or **Game-clock time
   management**. Clock-managed Stockfish requires the game clock and receives both remaining
   times and increments on every move.
6. Choose **Disabled**, **Fixed time**, or **Continuous live** displayed-position analysis.
   Live analysis has its own maximum depth and works with any Human/Stockfish side pairing.
7. Remember the setup and choose whether to show Game Setup or reuse it automatically.

Engine Preferences also contains the displayed-position analysis mode, separate fixed-time
and live-depth budgets, MultiPV, depth, threads, hash size, and an optional local Syzygy
directory. Syzygy files are not bundled or downloaded; an unavailable or unsupported
directory falls back to normal search. The preferences are persisted in Wizard Chess's
existing XDG-backed `settings.json`; future starts then require only `uv run wizard-chess`.
Choosing Stockfish as either player or enabling analysis enables the engine implicitly. If no
path is saved, Wizard Chess uses the matching bundled Stockfish and otherwise discovers
`stockfish` on `PATH`.

Engine executable resolution is deliberately separate from configuration precedence:

```text
explicit environment or saved Preferences path
> verified bundled Stockfish for this OS and CPU
> stockfish discovered on the system PATH
> unavailable with graceful fallback to ordinary chess
```

An explicit selection is never silently replaced by the bundle when it later becomes invalid.
The current bundle is the unmodified official Stockfish 18 Linux x86-64 baseline executable,
recompressed with XZ for repository distribution. Its exact executable/archive checksums,
GPLv3 license, authors, and reproducible source pointer live under
`src/wizard_chess/engine/bundled/stockfish-18/` and in `THIRD_PARTY_NOTICES.md`.

### Live engine analysis

Displayed-position analysis is independent of who controls White and Black:

- **Disabled** starts no position-analysis search.
- **Fixed time** preserves the earlier bounded request for each newly displayed position.
- **Continuous live** starts one UCI streaming search, publishes only useful new maximum
  depths, and stops at the live maximum depth or when the displayed position changes.

The vertical bar is always White-centric: `+0.35` means a 0.35-pawn White advantage and
`-1.42` means a 1.42-pawn Black advantage. `M3` is mate for White and `-M2` is mate for Black.
The bar uses a bounded nonlinear mapping, so large scores approach a fully winning side
without treating centipawns as a linear percentage.

The deepest result for every visited position is kept in memory for the current game. Moving
the history slider displays that cached result immediately and resumes live search if its depth
is still below the configured maximum. The cache remains after checkmate, draw, or resignation,
then is discarded on New Game, FEN/PGN replacement, or session close. It is never written to a
database or settings file.

After a game ends, the graph remains hidden until **Analyse game** has successfully completed
the full fixed post-game analysis. It plots the before/after evaluations from that completed
analysis—not the temporary in-game live cache—so partial live depths cannot distort the game
summary. Missing post-game evaluations remain gaps rather than becoming false zero values;
mate is mapped only for display to a bounded graph endpoint. Click a graph region, or use the
existing history slider, to navigate the board and sidebar together. Live analysis intentionally
uses CPU continuously until its depth target, but all engine communication remains outside the
Qt event thread and only one position is searched at a time.

### Advanced environment configuration

Environment variables remain available for CI, scripts, development, headless launches, and
one-shot overrides. For example:

```bash
WIZARD_CHESS_ENGINE_ENABLED=true \
WIZARD_CHESS_ENGINE_PATH=/usr/bin/stockfish \
WIZARD_CHESS_ANALYSIS_MODE=live \
WIZARD_CHESS_LIVE_ANALYSIS_MAX_DEPTH=22 \
uv run wizard-chess
```

If no path is supplied, enabled mode tries the platform bundle and then `stockfish` on `PATH`.
Bundle lookup is based on the detected OS and CPU rather than a developer-specific absolute
path.

Configuration precedence is:

```text
explicit CLI override (where applicable)
> WIZARD_CHESS_* environment variable
> persistent Wizard Chess preference
> built-in default
```

An environment override changes only the current process and is not written back merely by
launching the application.

| Variable | Default | Purpose |
| --- | --- | --- |
| `WIZARD_CHESS_ENGINE_ENABLED` | `false` | Enable the lazy Stockfish adapter |
| `WIZARD_CHESS_ENGINE_PATH` | automatic | Explicit UCI executable; otherwise bundle then `PATH` |
| `WIZARD_CHESS_ANALYSIS_MODE` | `off` | `off`, `fixed_time`, or `live` |
| `WIZARD_CHESS_LIVE_ANALYSIS_MAX_DEPTH` | `20` | Continuous-analysis stop depth |
| `WIZARD_CHESS_ANALYSIS_ENABLED` | unset | Legacy boolean mapped to `fixed_time`/`off` |
| `WIZARD_CHESS_PLAYER_MOVE_ANALYSIS_TIME_MS` | `500` | Fixed Stockfish-player time per move |
| `WIZARD_CHESS_POST_GAME_ANALYSIS_TIME_MS` | `500` | Completed-game time per position |
| `WIZARD_CHESS_STOCKFISH_PLAYER_MODE` | `fixed_analysis_time` | `fixed_analysis_time` or `game_clock` |
| `WIZARD_CHESS_ENGINE_TIME_MS` | unset | Legacy value migrated to both analysis budgets |
| `WIZARD_CHESS_ENGINE_DEPTH` | unset | Optional depth limit |
| `WIZARD_CHESS_ENGINE_MULTIPV` | `3` | Candidate line count |
| `WIZARD_CHESS_ENGINE_STRENGTH` | `club` | Strength band |
| `WIZARD_CHESS_ENGINE_THREADS` | `1` | UCI thread count |
| `WIZARD_CHESS_ENGINE_HASH_MB` | `128` | UCI hash size |
| `WIZARD_CHESS_SYZYGY_PATH` | unset | Optional local Syzygy directory |
| `WIZARD_CHESS_SYZYGY_PROBE_LIMIT` | `7` | Maximum pieces probed when supported |
| `WIZARD_CHESS_SYZYGY_50_MOVE_RULE` | `true` | Respect the 50-move rule in tablebase probing |

Strength values are `beginner`, `casual`, `club`, `strong_club`, `expert`, `master`, and
`maximum`. They map to supported engine controls and are not advertised as exact Elo ratings.

Choose an engine side from a script or other environment-only launch:

```bash
WIZARD_CHESS_ENGINE_ENABLED=true \
WIZARD_CHESS_ENGINE_PATH=/usr/bin/stockfish \
WIZARD_CHESS_BLACK_PLAYER=engine \
uv run wizard-chess
```

`WIZARD_CHESS_WHITE_PLAYER` and `WIZARD_CHESS_BLACK_PLAYER` accept `human` or `engine`.
Unexpected process termination is reported and ordinary chess remains usable. The owned UCI
process is closed on normal application exit.

## Voice: English and Polish

Install local voice dependencies:

```bash
uv sync --extra voice
```

Voice uses `sounddevice` and `faster-whisper`, records only explicitly initiated bounded
utterances, runs locally, and keeps no audio files. A model may download on first use unless
`WIZARD_CHESS_VOICE_MODEL` points to a cached/local CTranslate2 model. Polish defaults to the
multilingual `base` model; English defaults to `base.en`.

English examples:

```text
e four
pawn to e four
knight to f three
bishop takes f seven
castle kingside
undo
new game
```

Polish examples:

```text
e cztery
pion na e cztery
skoczek na f trzy
skoczek bierze e pięć
goniec z c cztery na f siedem
roszada krótka
roszada długa
e osiem promocja na hetmana
cofnij
nowa gra
zapisz grę
poddaję się
```

Select **English** or **Polski** in the GUI, or set
`WIZARD_CHESS_VOICE_LANGUAGE=en|pl|auto`. Explicit language hints are passed to the recognizer
because chess utterances are short. Polish normalization handles targeted ranks, file-name
spellings, piece inflections, captures, castling, promotion, check/mate, and application
commands. Both languages emit the same internal intent types.

Existing capture/ambiguity/illegal-move distinctions and recognizer confidence are preserved.
The confirmation policy values are `off`, `ambiguous_or_low_confidence`, and `always`; the
pure policy seam is available for adapters that implement a confirmation dialog.

The original bounded-capture settings remain available:

| Variable | Default |
| --- | --- |
| `WIZARD_CHESS_VOICE_MODEL` | `base.en` (`base` for Polish or automatic detection) |
| `WIZARD_CHESS_MICROPHONE` | system default |
| `WIZARD_CHESS_VOICE_MAX_SECONDS` | `6.0` |
| `WIZARD_CHESS_VOICE_START_TIMEOUT_SECONDS` | `3.0` |
| `WIZARD_CHESS_VOICE_SILENCE_SECONDS` | `0.8` |
| `WIZARD_CHESS_VOICE_SILENCE_THRESHOLD` | `0.015` |

## Games, settings, clocks, and recovery

PGN import preserves known `Event`, `Site`, `Date`, `Round`, `White`, `Black`, result, starting
position, and main-line moves. Invalid PGN/FEN is rejected atomically. New saves use unique
timestamped identifiers; the optional recovery slot never overwrites unrelated games.

Enable autosave with `WIZARD_CHESS_AUTOSAVE=true`. State defaults to
`$XDG_STATE_HOME/wizard-chess` or `~/.local/state/wizard-chess`. Preferences use
`$XDG_CONFIG_HOME/wizard-chess/settings.json` or `~/.config/wizard-chess/settings.json` and
load missing old fields from current defaults.

Board appearance is also stored in `settings.json`. The bundled Tatiana SVG artwork is used
under its original license; see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

Player names use `WIZARD_CHESS_WHITE_NAME` and `WIZARD_CHESS_BLACK_NAME`. Optional clocks use:

```text
WIZARD_CHESS_CLOCK_ENABLED=true
WIZARD_CHESS_CLOCK_SECONDS=600
WIZARD_CHESS_CLOCK_INCREMENT_SECONDS=5
```

Clock timing uses a monotonic source and is independent of GUI frame rate.

## Analysis heuristics

All scores are normalized from White's perspective. Mate scores remain mate scores rather
than arbitrary raw UCI values. Live results use a position key that retains side to move,
castling, en-passant, and the fifty-move clock while ignoring only the irrelevant fullmove
number. Fixed post-game analysis evaluates positions on copies, caches exact FENs, records
before/after evaluation, preferred move, principal variation, and mover-relative centipawn
loss, and never changes the live game.

Wizard Chess classifications are documented project heuristics, not Chess.com or Lichess
replicas:

| Classification | Mover-relative loss |
| --- | --- |
| Best | engine match or ≤ 15 cp |
| Excellent | ≤ 35 cp |
| Good | ≤ 75 cp |
| Inaccuracy | ≤ 150 cp |
| Mistake | ≤ 300 cp |
| Blunder | > 300 cp |

The summary reports average centipawn loss, best-move matches, inaccuracies, mistakes, and
blunders by side. Optional analysis JSON has an explicit schema version and stays separate
from compatible PGN.

## Developer tooling

Replay a UTF-8 command file through the same controller as interactive play:

```bash
uv run wizard-chess --script examples/game.txt
```

Blank lines and `#` comments are ignored. Invalid commands stop through the ordinary parser or
legality error; the runner has no validation shortcut. `FakeEngine`, `MockAudioInput`, and
`MockSpeechRecognizer` keep tests deterministic and free of Stockfish/audio hardware.

Run the complete required suite:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

## Known limitations

- Real Stockfish acceptance outside the bundled Linux x86-64 target and microphone/model
  acceptance depend on local external systems; automated engine tests use controlled fakes.
- Fixed-time engine cancellation marks results stale immediately, while an in-flight bounded
  synchronous UCI call may finish before that worker exits. Continuous live search uses the
  streaming UCI cancellation path.
- Confirmation policy is modeled and testable, but the current GUI executes uniquely resolved
  voice moves directly; ambiguous commands are rejected for clarification.
- There is no wake word, speech synthesis, speaker identification, online play, cloud account,
  real physical motion, serial/GPIO adapter, motor, sensor, RFID, calibration, capture handling,
  obstacle avoidance, or general path-planning implementation.

Those physical concerns belong to later Stage 3 increments and must remain beneath canonical
`MoveExecuted` events rather than mutate the authoritative chess state through a new path.
