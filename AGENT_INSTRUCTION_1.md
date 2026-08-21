# AGENT_INSTRUCTION_1.md — Wizard Chess Repository Bootstrap

## Objective

Create the initial Git repository for **Wizard Chess**, a voice-controlled physical chessboard project.

This first implementation is the software foundation for the project. Build a clean, testable Python application whose chess state will later act as the authoritative digital twin of a physical chessboard.

For this task, implement only:

1. Repository structure and Python project configuration.
2. Chess domain model using `python-chess`.
3. Text/CLI move input.
4. Move execution and validation.
5. Undo/redo support.
6. FEN and PGN support.
7. Game-state and game-result detection.
8. Hardware-independent move events.
9. Unit tests.
10. Architectural interfaces/stubs for future GUI, speech, and hardware layers.

Do **not** implement the graphical interface, microphone integration, speech recognition, Stockfish analysis, serial communication, motors, or physical-board logic yet.

---

# 1. Technology

Use:

- Python 3.12+
- `python-chess`
- `pytest`
- `ruff`
- Pyright or `mypy`
- `uv` for dependency and virtual-environment management
- Git

Use modern Python:

- type hints throughout
- `dataclasses` where appropriate
- `Enum` where appropriate
- `pathlib`
- small cohesive modules
- explicit public interfaces
- dependency inversion between domain logic and external systems

Avoid unnecessary frameworks.

---

# 2. Repository Structure

Create approximately the following structure:

```text
wizard-chess/
├── .gitignore
├── README.md
├── AGENTS.md
├── pyproject.toml
├── src/
│   └── wizard_chess/
│       ├── __init__.py
│       ├── main.py
│       │
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── game.py
│       │   ├── move.py
│       │   ├── events.py
│       │   └── results.py
│       │
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── intents.py
│       │   ├── normalizer.py
│       │   ├── parser.py
│       │   └── resolver.py
│       │
│       ├── speech/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   └── mock.py
│       │
│       ├── hardware/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   └── simulated_board.py
│       │
│       └── persistence/
│           ├── __init__.py
│           └── pgn_store.py
│
└── tests/
    ├── unit/
    │   ├── test_game.py
    │   ├── test_move.py
    │   ├── test_parser.py
    │   └── test_resolver.py
    └── integration/
        └── test_cli_game.py
```

You may adjust the structure where there is a strong architectural reason, but preserve the separation between:

- chess/domain logic
- command interpretation
- speech
- hardware
- persistence
- application/UI entry points

The domain layer must not import GUI, speech-recognition, or hardware-specific libraries.

---

# 3. ChessGame

Implement a `ChessGame` class as the authoritative owner of chess state.

It should wrap `python-chess` rather than duplicate chess-rule implementation.

Required capabilities:

```python
game = ChessGame()

game.board
game.turn
game.legal_moves()

game.make_move(...)
game.undo()
game.redo()

game.fen()
game.load_fen(...)

game.is_check()
game.is_checkmate()
game.is_stalemate()
game.is_game_over()
game.result()
```

Use a clean API rather than exposing arbitrary mutation of the underlying `python-chess.Board`.

---

# 4. Move Representation

Create an application-level move representation.

For example:

```python
@dataclass(frozen=True)
class ChessMove:
    source: str
    target: str
    promotion: str | None = None
```

The exact naming may differ if there is a good reason.

Accepted coordinates use lowercase algebraic square names internally:

```text
e2
e4
g1
f3
```

Provide conversion to/from `python-chess.Move`.

Provide UCI output.

Provide SAN output when the position context permits it.

---

# 5. Move Events

The architecture must already support the future physical chessboard.

After every accepted move, produce a hardware-independent event similar to:

```python
@dataclass(frozen=True)
class MoveExecuted:
    source_square: str
    target_square: str
    captured_square: str | None
    promotion: str | None
    is_castling: bool
    is_en_passant: bool
    san: str
    uci: str
```

Design this carefully.

Future hardware code should be able to consume this event without understanding `python-chess`.

Do not put motor coordinates or physical-board implementation details in this event yet.

---

# 6. Undo and Redo

Implement undo and redo at the application level.

Requirements:

- `undo()` returns to the previous chess position.
- `redo()` reapplies the undone move.
- Making a new move after undo clears the redo history.
- Move history remains internally consistent.
- Special moves must work correctly.

Add tests.

---

# 7. Game Result

Represent game state clearly.

Support detection of at least:

- ongoing game
- check
- checkmate
- stalemate
- insufficient material
- seventy-five-move automatic draw if provided by the underlying rules engine
- fivefold repetition automatic draw if provided by the underlying rules engine

Also expose claimable draw status where reasonably supported by `python-chess`.

Do not implement chess-rule logic manually when `python-chess` already provides it.

---

# 8. FEN

Implement:

```python
game.fen()
game.load_fen(fen)
```

Loading a FEN should reset redo/undo state unless there is a compelling reason not to.

Validate invalid FEN input and raise an application-specific exception.

---

# 9. PGN

Implement PGN export.

At minimum:

```python
game.to_pgn()
```

Also create a simple persistence service that can save PGN to a specified file.

Avoid embedding filesystem operations directly inside the domain object.

---

# 10. Command Parsing

Implement the initial typed command parser.

The first supported syntax is coordinate-based:

```text
e2 e4
e2-e4
e2 to e4
move e2 to e4
```

Normalize these to a structured intent.

For example:

```python
MoveIntent(
    source="e2",
    target="e4",
    promotion=None,
)
```

Also support promotion forms such as:

```text
e7 e8 queen
e7 to e8 promote queen
e7 e8 q
```

The parser must not modify chess state.

---

# 11. Move Resolver

Create a separate resolver responsible for comparing an intent against the current legal moves.

Example:

```python
resolved = resolver.resolve(intent, game)
```

For coordinate moves, resolution should normally produce exactly one legal `ChessMove`.

Define application-level exceptions/results for:

- malformed command
- illegal move
- ambiguous move

Even though ambiguity is uncommon for source/destination coordinate commands, design the API for future natural-language commands such as:

```text
knight to f3
```

Do not yet implement the full natural-language chess grammar unless it is trivial to do without compromising the initial scope.

---

# 12. CLI

Provide a minimal playable command-line application.

Running:

```bash
uv run wizard-chess
```

or an equivalent configured project entry point should start the game.

Example interaction:

```text
Wizard Chess

White to move > e2 e4
Played: e4

Black to move > e7 e5
Played: e5

White to move > g1 f3
Played: Nf3
```

Support commands:

```text
undo
redo
fen
pgn
new
quit
help
```

Optional:

```text
legal
```

The CLI is only a development interface. Keep its logic separate from the chess domain so it can later be replaced by PySide6.

---

# 13. Speech Interface Stub

Do not integrate Vosk yet.

Create an abstraction suitable for future speech recognizers.

For example:

```python
class SpeechRecognizer(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...
```

Add a simple mock implementation that can supply predetermined transcripts for testing.

Do not add audio dependencies in this task.

---

# 14. Hardware Interface Stub

Create a future-facing physical-board interface.

For example:

```python
class PhysicalBoard(Protocol):
    def execute_move(self, event: MoveExecuted) -> None:
        ...
```

Provide:

```python
SimulatedPhysicalBoard
```

It should record received move events but perform no physical actions.

This gives us a testable seam for Stage 2.

The chess domain must not depend on a concrete hardware implementation.

---

# 15. Error Model

Do not use generic `Exception` for expected application failures.

Create sensible project exceptions, potentially including:

```python
WizardChessError
InvalidMoveError
InvalidCommandError
InvalidFenError
NoMoveToUndoError
NoMoveToRedoError
```

Names may be adjusted.

Keep the exception hierarchy simple.

---

# 16. Tests

Write comprehensive tests.

At minimum test:

## Normal movement

- e2-e4
- e7-e5
- knight movement
- bishop movement
- queen movement
- king movement

## Illegal moves

- moving opponent's piece
- impossible piece movement
- moving into check
- moving while king remains in check

## Captures

- normal capture
- captured-square information in `MoveExecuted`

## Castling

- kingside
- queenside
- illegal castling conditions

## En passant

Verify:

- legal en passant
- captured square in move event

## Promotion

Verify promotion to:

- queen
- rook
- bishop
- knight

## Game endings

Test at least:

- check
- checkmate
- stalemate
- insufficient material

Use known compact FEN positions where appropriate.

## History

Test:

- undo
- redo
- redo invalidation after a different move

## FEN

Test:

- export
- import
- invalid FEN

## PGN

Verify that a short known sequence produces valid PGN.

## Parser

Test multiple textual variants:

```text
e2 e4
E2 E4
e2-e4
e2 to e4
move e2 to e4
```

## Integration

Run at least one short game sequence through:

```text
text command
→ parser
→ resolver
→ game
→ MoveExecuted
→ simulated physical board
```

---

# 17. Code Quality

Configure Ruff.

Configure static type checking.

Aim for:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

and the configured type checker to pass.

Use docstrings where they clarify public interfaces, not mechanically on every trivial function.

Avoid giant modules.

Avoid global mutable state.

Avoid circular dependencies.

---

# 18. README

Create a concise but useful README.

Include:

- Wizard Chess project description.
- Current Stage 1 scope.
- Architecture overview.
- Installation instructions.
- Running the CLI.
- Running tests.
- Project structure.
- Planned future stages.

Mention that the eventual system is intended to support:

```text
Voice command
    ↓
Speech recognition
    ↓
Chess command interpretation
    ↓
Authoritative digital chess state
    ↓
Physical board controller
    ↓
Motorized piece movement
```

But make clear that physical movement is not implemented yet.

---

# 19. Git

Initialize the repository if it is not already initialized.

Create an appropriate Python `.gitignore`.

Do not commit:

- virtual environments
- IDE state
- caches
- build artifacts
- speech models
- recordings
- secrets

After implementation, inspect the resulting diff and ensure no generated junk has been included.

If Git identity is available and repository policy permits it, create an initial commit with a descriptive message such as:

```text
feat: bootstrap Wizard Chess core
```

Do not overwrite existing Git configuration.

---

# 20. Architectural Constraints

These constraints are important.

### The chess state is authoritative

Future motors and sensors must reflect or validate the digital chess state. Hardware must not become the source of chess-rule logic.

### Chess rules belong to `python-chess`

Do not reimplement legal-move generation.

### Speech is an input adapter

Speech recognition will eventually produce text/intent. It must not directly manipulate the board.

### Hardware is an output adapter

Motor control will eventually consume structured chess events. It must not be embedded in the chess engine.

### GUI is replaceable

The CLI is temporary. Do not couple business logic to terminal I/O.

### Testability is mandatory

Every major component should be testable without:

- microphone
- GUI
- serial port
- motors
- network connection

---

# 21. Out of Scope

Do not implement in this task:

- PySide6 GUI
- Vosk
- Whisper
- microphone capture
- wake-word detection
- text-to-speech
- Stockfish
- chess evaluation
- LED evaluation indicators
- Raspberry Pi code
- Arduino/ESP32 firmware
- serial communication
- motor control
- electromagnets
- Hall sensors
- reed switches
- board calibration
- physical path planning
- collision avoidance
- online multiplayer
- accounts
- cloud services

Create architectural seams for some of these where specified, but no implementation.

---

# 22. Completion Criteria

The task is complete when:

1. The repository is correctly structured.
2. Dependencies install through `uv`.
3. The CLI starts successfully.
4. Two players can play a legal chess game using coordinate commands.
5. Illegal moves are rejected.
6. Checkmate and other game-ending conditions are detected.
7. Undo and redo work.
8. FEN import/export works.
9. PGN export works.
10. Every accepted move generates a structured `MoveExecuted` event.
11. A simulated physical-board adapter can consume those events.
12. Parser, resolver, game logic, and integration tests pass.
13. Ruff passes.
14. Static type checking passes.
15. README documentation is present.
16. No GUI, speech engine, or real hardware dependencies have been introduced.

---

# 23. Execution Instructions

Work autonomously through the repository.

Before editing, inspect the existing repository and preserve any useful existing files.

Then:

1. Create or update the project structure.
2. Implement the chess domain first.
3. Add tests for the domain.
4. Implement command parsing and resolution.
5. Add the CLI.
6. Add persistence.
7. Add speech and hardware abstractions.
8. Add integration tests.
9. Configure linting and type checking.
10. Run the complete test/tooling suite.
11. Fix failures.
12. Review the resulting architecture for unnecessary coupling.
13. Update README.
14. Report the final repository structure, commands run, test results, and any architectural decisions that deserve attention.

Do not stop after scaffolding. Produce a working Stage 1 software foundation satisfying the completion criteria.
