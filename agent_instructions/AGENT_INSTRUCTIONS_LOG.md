# Codex Task: Configurable Runtime Logging and Expanded Diagnostic Output

Implement a coherent logging system for Wizard Chess that:

1. allows the user to control logging verbosity from the terminal;
2. emits substantially more useful information about what the application is processing;
3. outputs logs to the terminal;
4. can simultaneously persist logs to a file;
5. allows file logging to be enabled, disabled, and configured independently of terminal verbosity.

The implementation should use Python's standard `logging` infrastructure unless the repository already has an established logging abstraction that should be extended instead.

## 1. Command-line interface

Add standard command-line logging options to the Wizard Chess launcher.

Preferred syntax:

```bash
wizard-chess --log-level DEBUG
wizard-chess --log-level INFO
wizard-chess --log-level WARNING
wizard-chess --log-level ERROR
wizard-chess --log-level OFF
```

Equivalent invocation through the current project environment should work, e.g.:

```bash
uv run wizard-chess --log-level DEBUG
```

Supported levels:

- `DEBUG` — detailed internal processing and diagnostic information;
- `INFO` — normal operational information;
- `WARNING` — warnings and recoverable abnormal situations;
- `ERROR` — errors only;
- `OFF` — disable normal application logging.

Make parsing case-insensitive if straightforward, so that e.g. `--log-level debug` also works.

Default:

```text
INFO
```

Do not invent custom terms such as `high`, `low`, etc. if the standard Python logging terminology can be used cleanly.

Provide a short alias only if it fits the existing CLI conventions; otherwise prefer the explicit `--log-level`.

## 2. File logging

Support simultaneous logging to a persistent file.

Preferred interface:

```bash
wizard-chess --log-file logs/wizard-chess.log
```

The user should be able to disable persistent file logging explicitly:

```bash
wizard-chess --no-log-file
```

Choose a sensible default based on the existing application architecture.

Preferred behaviour:

- terminal logging: enabled by default;
- file logging: enabled by default if there is already a suitable application-data/log directory;
- otherwise file logging may be opt-in until a clean default path is established.

If file logging is enabled by default, place logs somewhere appropriate rather than casually writing them into the repository root.

For example, use a platform/user application-data location or an existing Wizard Chess data directory if one already exists.

Do not hard-code a developer-specific absolute path.

When `--log-file PATH` is supplied:

- create parent directories when appropriate;
- write logs to that file;
- retain terminal logging as well unless explicitly disabled.

Add a terminal-output toggle if this can be done without complicating the interface unnecessarily:

```bash
--terminal-log
--no-terminal-log
```

If implementing this option, terminal logging should remain enabled by default.

The logging destinations should therefore be orthogonal:

```text
log level
    ↓
DEBUG / INFO / WARNING / ERROR / OFF

destinations
    ↓
terminal: on/off
file:     on/off/path
```

Do not implement logging as a collection of scattered `print()` statements.

## 3. Configuration architecture

Integrate logging with the existing Wizard Chess configuration system rather than creating an isolated parallel configuration mechanism.

If the project already supports configuration through environment variables and/or the startup settings UI, design the logging settings so they can later be exposed there as well.

CLI arguments should take precedence over defaults and environment/configuration values according to the project's existing precedence rules.

Possible internal configuration representation:

```python
@dataclass
class LoggingConfig:
    level: LogLevel
    terminal_enabled: bool = True
    file_enabled: bool = True
    file_path: Path | None = None
```

This is illustrative rather than mandatory.

Avoid passing raw CLI strings throughout the application.

Resolve logging configuration once during startup and configure the logging subsystem centrally.

## 4. Logging module

Create or extend a dedicated infrastructure module, e.g.:

```text
wizard_chess/
    logging_config.py
```

or another location consistent with the current package architecture.

It should be responsible for:

- translating configuration into Python logging levels;
- creating handlers;
- setting formatters;
- avoiding duplicate handlers;
- configuring the application/root logger appropriately;
- creating the file handler when enabled;
- disabling logging cleanly when level is `OFF`.

Application modules should then obtain loggers conventionally:

```python
import logging

logger = logging.getLogger(__name__)
```

and emit messages such as:

```python
logger.debug(...)
logger.info(...)
logger.warning(...)
logger.error(...)
```

Do not make modules depend directly on CLI parsing.

## 5. Terminal log format

Use a compact and readable terminal format.

For example:

```text
09:42:13 INFO     wizard_chess.game - Game started: human vs engine
09:42:18 INFO     wizard_chess.input - Move accepted: e2e4
09:42:18 DEBUG    wizard_chess.engine - Position submitted to Stockfish
09:42:21 INFO     wizard_chess.engine - Engine move: e7e5
```

Avoid excessive metadata in normal terminal output.

At `DEBUG`, module/logger names should make it possible to determine which subsystem produced the message.

## 6. File log format

File logs should contain somewhat more diagnostic information than terminal logs.

Include at least:

- full timestamp;
- log level;
- logger/module;
- message.

For example:

```text
2026-08-28 09:42:18.321 INFO wizard_chess.input Move accepted: e2e4
```

Exception logging should include tracebacks.

Use UTF-8.

Consider using a rotating file handler rather than an indefinitely growing file.

A reasonable default might be:

```text
maxBytes = 5–10 MB
backupCount = 3–5
```

Use conventional values and document them.

## 7. Expand logging throughout the application

Add useful logging at the major processing boundaries of Wizard Chess.

The goal is to make it possible to understand what the program is doing during a game and diagnose failures without stepping through the debugger.

Do not log every trivial function call.

### Application startup

Log:

- application startup;
- resolved major configuration;
- enabled subsystems;
- engine enabled/disabled;
- physical-board/hardware backend selected;
- speech recognition enabled/disabled;
- language;
- player configuration;
- relevant engine configuration;
- GUI/terminal mode where applicable.

Example:

```text
INFO  Starting Wizard Chess
INFO  Game configuration: White=human, Black=engine
INFO  Stockfish enabled: strength=strong_club, time=2500ms
INFO  Physical board backend: simulated
```

Do not log secrets or sensitive credentials.

### Game lifecycle

Log:

- new game creation;
- initial position;
- game mode/player types;
- move number;
- accepted moves;
- rejected/illegal moves;
- check;
- checkmate;
- stalemate;
- draw conditions;
- resignation or termination where applicable;
- game completion/result.

Example:

```text
INFO  Move 12 White: Nf3
DEBUG Board FEN after move: ...
INFO  Black is in check
```

FEN and similarly verbose state dumps should normally be `DEBUG`, not `INFO`.

### Command processing

Log the pipeline from raw input to game action.

For terminal input:

```text
DEBUG Raw command received: "e4"
DEBUG Command parser result: MoveCommand(...)
INFO  Move command accepted: e2e4
```

For invalid input:

```text
WARNING Command rejected: unrecognized command "..."
```

Do not duplicate user-facing error text unnecessarily.

### Voice recognition

Where Stage 2 voice control exists, log:

- listening started/stopped;
- speech recognizer activation;
- recognised transcription;
- confidence where available;
- language/model selection;
- parsed candidate move;
- failed recognition;
- ambiguity;
- retry/fallback behaviour.

Example:

```text
DEBUG Speech transcription: "knight f three"
DEBUG Parsed speech command: Nf3
INFO  Voice move accepted: Nf3
```

Avoid dumping raw audio data.

### Chess parsing

At `DEBUG`, log useful information around:

- SAN/UCI parsing;
- shorthand command interpretation;
- ambiguous commands;
- legal move candidate generation;
- final resolved move.

For example:

```text
DEBUG Parsing move input: "e4"
DEBUG Candidate legal moves: [e2e4]
DEBUG Resolved move: e2e4 / SAN=e4
```

Avoid logging enormous legal-move collections at `INFO`.

### Stockfish / engine integration

Log:

- engine startup;
- engine executable/path validation;
- engine configuration;
- engine process startup/shutdown;
- position submission;
- requested depth/time/limits;
- analysis start/end;
- current analysis depth where useful;
- evaluation updates where useful;
- engine-selected move;
- engine errors or timeout;
- engine restart/fallback where applicable.

Examples:

```text
INFO  Starting Stockfish
DEBUG Engine position updated: FEN=...
DEBUG Analysis request: time=2500ms
DEBUG Analysis depth=16 evaluation=+0.34
INFO  Engine move selected: c7c5
```

For live analysis, avoid generating a flood of redundant log entries. Log meaningful evaluation/depth transitions rather than every low-level engine protocol message by default.

Raw UCI traffic, if logged at all, should be `DEBUG`.

### Physical-board abstraction

For Stage 3.1 and later hardware abstraction, add logs around the boundary between logical chess state and physical execution.

Examples:

```text
DEBUG PhysicalBoardState before move: ...
INFO  Physical move requested: e2 -> e4
DEBUG Motion command produced: ...
INFO  Physical move completed: e2 -> e4
```

Log:

- backend initialization;
- simulated vs real hardware selection;
- requested physical moves;
- physical board state updates;
- logical/physical state mismatch;
- synchronization/reconciliation operations;
- failed physical commands;
- unavailable hardware.

State dumps should generally be `DEBUG`.

A physical/logical board mismatch should be at least `WARNING`, and potentially `ERROR` if gameplay cannot safely continue.

### Robot/motion controller

Where already implemented or stubbed, provide logging interfaces suitable for future Arduino/motion-control integration.

Examples:

```text
INFO  Executing movement e2 -> e4
DEBUG Motion plan: ...
DEBUG Sending command to controller: ...
DEBUG Controller acknowledgement: ...
INFO  Movement complete
```

Do not introduce fake hardware behaviour solely to create logs.

### Application shutdown

Log:

- normal shutdown;
- engine shutdown;
- hardware backend shutdown;
- file/resource cleanup;
- abnormal termination.

Example:

```text
INFO Wizard Chess shutting down normally
```

## 8. Log-level discipline

Apply consistent semantics.

### DEBUG

Use for:

- internal state;
- parsed objects;
- FEN;
- state transitions;
- engine analysis details;
- physical-board state;
- hardware command payloads;
- detailed speech/parser processing;
- configuration-resolution details.

### INFO

Use for meaningful application events:

- application startup;
- game started;
- move accepted;
- engine move;
- hardware move started/completed;
- check/checkmate/result;
- component initialization;
- clean shutdown.

### WARNING

Use for recoverable abnormal situations:

- invalid command;
- ambiguous input;
- speech recognition failure;
- unavailable optional feature;
- transient engine/hardware issue;
- physical/logical state inconsistency that can be recovered.

### ERROR

Use for failures that prevent an operation from succeeding:

- engine cannot start;
- hardware command fails;
- unrecoverable board synchronization error;
- configuration cannot be loaded;
- unexpected subsystem failure.

When catching exceptions:

```python
logger.exception("...")
```

should be used when a traceback is useful.

Do not silently swallow exceptions after logging unless that behaviour is intentionally recoverable.

## 9. Avoid excessive log spam

"More logging" should mean better observability, not indiscriminate output.

Do not:

- log every render frame;
- log every GUI event;
- log every polling iteration;
- repeatedly log unchanged engine evaluation;
- repeatedly log the same hardware state;
- emit multi-line board dumps at INFO;
- emit normal expected events as warnings/errors.

At normal `INFO` level, a user should be able to follow the meaningful lifecycle of the application and game without being overwhelmed.

At `DEBUG`, a developer should be able to reconstruct the major processing pipeline.

## 10. Optional dedicated subsystem loggers

Use hierarchical module logger names naturally, for example:

```text
wizard_chess
wizard_chess.game
wizard_chess.commands
wizard_chess.voice
wizard_chess.engine
wizard_chess.hardware
wizard_chess.motion
wizard_chess.ui
```

Do not build an elaborate custom category system if standard Python logger hierarchy already solves the problem.

## 11. Tests

Add unit/integration tests for logging configuration.

At minimum test:

1. default logging level;
2. `--log-level DEBUG`;
3. lowercase level input;
4. `--log-level OFF`;
5. invalid log level produces a clear CLI error;
6. terminal handler is created when enabled;
7. terminal handler is absent when explicitly disabled;
8. file handler is created when file logging is enabled;
9. file logging is absent with `--no-log-file`;
10. custom `--log-file` path is respected;
11. parent directory creation where applicable;
12. log messages are actually written to the file;
13. `DEBUG` messages are omitted at `INFO`;
14. `DEBUG` messages appear at `DEBUG`;
15. repeated logger configuration does not accidentally duplicate handlers.

Use temporary directories/files in tests.

Do not write tests into the user's real log directory.

Also update existing CLI tests if the argument parser changes.

## 12. Documentation

Update `README.md` with a concise logging section.

Document commands such as:

```bash
uv run wizard-chess
uv run wizard-chess --log-level DEBUG
uv run wizard-chess --log-level WARNING
uv run wizard-chess --log-level OFF
uv run wizard-chess --log-file ./logs/session.log
uv run wizard-chess --no-log-file
```

If terminal logging can be disabled:

```bash
uv run wizard-chess --no-terminal-log --log-file ./logs/session.log
```

Explain the intended use of each level.

Also update `AGENT_INCREMENTS.md` or the project's equivalent implementation-history/roadmap document to record this increment.

## 13. Backward compatibility

Existing commands must continue to work without requiring new logging options.

For example:

```bash
uv run wizard-chess
```

should still launch the application normally.

Do not require callers or tests to manually configure logging before importing application modules.

Avoid changing game behaviour merely because logging was introduced.

## 14. Architecture constraints

Keep logging an infrastructure concern.

Do not:

- put CLI parsing into game-domain classes;
- pass logger instances throughout the domain model unless there is a compelling architectural reason;
- replace domain exceptions with log messages;
- make gameplay logic depend on the selected logging level;
- introduce global mutable application state beyond what Python's logging system conventionally requires.

Domain modules should normally just use:

```python
logger = logging.getLogger(__name__)
```

Configuration belongs at the application composition/startup boundary.

## 15. Suggested implementation order

1. Inspect the current launcher/configuration architecture.
2. Identify any existing logging or `print()`-based diagnostics.
3. Introduce the central logging configuration.
4. Add CLI/configuration options.
5. Configure terminal logging.
6. Configure rotating file logging.
7. Replace diagnostic `print()` calls with proper logging where appropriate.
8. Add logging at the major processing boundaries listed above.
9. Add tests.
10. Update documentation.
11. Run the complete test suite and lint/type-check commands used by the repository.
12. Fix regressions before finishing.

## 16. Acceptance criteria

The increment is complete when all of the following work:

```bash
uv run wizard-chess
```

produces normal `INFO`-level operational logs.

```bash
uv run wizard-chess --log-level DEBUG
```

produces detailed diagnostic output describing the processing pipeline.

```bash
uv run wizard-chess --log-level WARNING
```

shows only warnings and errors.

```bash
uv run wizard-chess --log-level OFF
```

suppresses normal application logs.

File logging can independently be enabled, disabled, and directed to a chosen path.

Both terminal and file output can operate simultaneously.

A developer reading a DEBUG log should be able to follow approximately:

```text
application startup
→ configuration resolution
→ game creation
→ user/voice command received
→ command parsing
→ chess move resolution
→ logical board update
→ engine processing if applicable
→ physical-board request if applicable
→ physical state update
→ next turn
→ game termination
→ subsystem shutdown
```

without adding ad-hoc debugging `print()` calls.

## 17. Scope restraint

Do not perform unrelated refactors.

If implementation reveals architectural issues relevant to future logging, leave concise TODOs or document them rather than substantially restructuring unrelated systems.

Preserve current behaviour and tests wherever possible.

At completion, provide a short summary containing:

- files added/changed;
- CLI options introduced;
- default logging behaviour;
- log-file location/default;
- major subsystems instrumented;
- tests added;
- any intentionally deferred logging areas.