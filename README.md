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
        future Stage 3 physical-board seam
```

- `domain` owns authoritative chess state, metadata, termination states, and move events.
- `commands` produces state-free coordinate, SAN, contextual move, and application intents.
- `application` coordinates all moves, clocks, scripts, autosave, engine moves, and adapters.
- `engine` contains the replaceable engine port, lazy Stockfish/UCI adapter, normalized
  White-perspective evaluations, candidate lines, and deterministic fake.
- `analysis` replays copies of games, classifies moves, calculates transparent statistics,
  and persists optional versioned annotations.
- `speech` owns bounded capture, recognizers, English/Polish normalization, confidence data,
  confirmation policy, and test doubles.
- `gui` renders only authoritative snapshots and runs voice, live analysis, engine replies,
  and post-game analysis outside the Qt event thread.
- `persistence` owns PGN, recovery, settings, and analysis filesystem access.
- `hardware` remains a replaceable event consumer; no Stage 3 control is implemented here.

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

## Desktop usability

The GUI provides:

- click-to-move with legal destinations, last-move highlighting, promotion choice, and flip;
- offline Tatiana or classic-symbol pieces plus five persistent board color themes;
- typed SAN, coordinate syntax, and application commands;
- move history plus a ply slider for inspecting old positions without changing the live game;
- Game Setup/New Game, Engine Preferences, Undo, Redo, FEN load/copy, and PGN import/export;
- optional clock start/pause/reset and English/Polish voice-language selection;
- non-blocking live evaluation, MultiPV candidates, principal variation, and evaluation bar;
- non-blocking engine opponent replies and post-game analysis with progress and summaries;
- visible, recoverable errors when voice, microphone, model, or engine is unavailable.

Moves accept SAN (`e4`, `Nf3`, `exd5`, `O-O`, `e8=Q`) and coordinate forms (`e2 e4`,
`e2-e4`, `move e2 to e4`). Contextual phrases are resolved only against current legal moves;
ambiguous phrases are rejected with legal origin squares rather than guessed.

Application commands include `undo`, `redo`, `new game`, `resign`, `draw`, `save`, `repeat`,
`fen`, `pgn`, `legal`, `help`, and `quit`. `draw` records an agreed draw; it is not represented
as a fake move.

## Stockfish

Install Stockfish using the operating system package manager or an official compatible
distribution. Wizard Chess does not bundle a binary. The normal graphical workflow is:

1. Launch `uv run wizard-chess`.
2. Open **Preferences…** and select the Stockfish executable if it is not already on `PATH`.
3. Use **Test Engine** to validate the executable.
4. In **Game Setup**, choose Human or Stockfish for White and Black.
5. Choose strength and either **Fixed analysis time per move** or **Game-clock time
   management**. Clock-managed Stockfish requires the game clock and receives both remaining
   times and increments on every move.
6. Remember the setup and choose whether to show Game Setup or reuse it automatically.

Engine Preferences also contains a separate after-game analysis budget, live analysis,
MultiPV, depth, threads, hash size, and an optional local Syzygy directory. Syzygy files are
not bundled or downloaded; an unavailable or unsupported directory falls back to normal
search. The
preferences are persisted in Wizard Chess's existing XDG-backed `settings.json`; future starts
then require only `uv run wizard-chess`. Choosing Stockfish as either player enables the engine
implicitly. If no path is saved, Wizard Chess discovers `stockfish` on `PATH`.

### Advanced environment configuration

Environment variables remain available for CI, scripts, development, headless launches, and
one-shot overrides. For example:

```bash
WIZARD_CHESS_ENGINE_ENABLED=true \
WIZARD_CHESS_ENGINE_PATH=/usr/bin/stockfish \
WIZARD_CHESS_ANALYSIS_ENABLED=true \
uv run wizard-chess
```

If no path is supplied, enabled mode tries `stockfish` on `PATH`. Configuration is external;
there is no platform-specific hard-coded path.

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
| `WIZARD_CHESS_ENGINE_PATH` | discovered | UCI executable path |
| `WIZARD_CHESS_ANALYSIS_ENABLED` | engine setting | Live analysis |
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
| `WIZARD_CHESS_VOICE_MODEL` | `base.en` (`base` for Polish) |
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
than arbitrary raw UCI values. Post-game analysis evaluates positions on copies, caches exact
FENs, records before/after evaluation, preferred move, principal variation, and mover-relative
centipawn loss, and never changes the live game.

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

- Real Stockfish and microphone/model acceptance depend on locally installed external systems;
  automated tests use controlled fakes.
- Engine cancellation marks results stale immediately, while an in-flight synchronous UCI call
  may finish before the worker exits.
- Confirmation policy is modeled and testable, but the current GUI executes uniquely resolved
  voice moves directly; ambiguous commands are rejected for clarification.
- There is no wake word, speech synthesis, speaker identification, online play, cloud account,
  physical motion, GPIO, motor, sensor, RFID, or path-planning implementation.

Those physical concerns belong to Stage 3 and must attach to canonical `MoveExecuted` events
rather than mutate the authoritative chess state through a new path.
