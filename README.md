# Wizard Chess

Wizard Chess is a voice-controlled physical chessboard project. This repository currently
contains the **Stage 1.1B digital prototype**: a testable Python application whose digital
chess state will remain authoritative as speech, electronics, and motorized movement are
added later.

Stage 1.1B adds a local PySide6 desktop interface with click-to-move play, legal-destination
and last-move highlighting, typed commands, history, status, board flip, undo/redo, and FEN
loading. Complete legal-move validation remains in `python-chess`. The project deliberately
has no microphone, chess engine, serial, sensor, network, or motor dependencies.

## Architecture

The application follows a ports-and-adapters shape:

- `domain` owns the authoritative game, values, results, errors, and move events.
- `commands` normalizes text into state-free intents and resolves them against legal moves.
- `application` provides one shared game session for all input adapters.
- `gui` is the PySide6 desktop presentation/input adapter.
- `main.py` selects the GUI or CLI and composes their dependencies.
- `hardware` defines an output port and an in-memory simulated board.
- `speech` defines a future input port and a deterministic mock recognizer.
- `persistence` keeps filesystem operations outside the domain.

The current adapter flow is:

```text
CLI ───────┐
           ├── shared application session ── authoritative game
GUI ───────┘                  │                       │
                             └──── MoveExecuted ─────┘
                                        │
                              simulated physical board
```

The GUI rerenders from an immutable snapshot of the authoritative game after every action;
it does not keep a second chess position. `SimulatedPhysicalBoard` records move events but
does not move physical pieces.

## Setup and CLI

Install Python 3.12+ and [`uv`](https://docs.astral.sh/uv/), then launch the desktop GUI:

```bash
uv sync
uv run wizard-chess
```

Use the retained terminal adapter when needed:

```bash
uv run wizard-chess --cli
```

In the GUI, select one of the side-to-move's pieces to highlight its legal destinations,
then select a destination to move. Promotion opens an explicit Queen/Rook/Bishop/Knight
choice. Use **New Game**, **Undo**, **Redo**, and **Flip Board** for game controls. The FEN
field displays the current position and supports copying or loading a replacement position.

Moves accept SAN, including captures, castling, promotions, check, checkmate, and standard
disambiguation. Representative inputs are:

```text
e4
Nf3
exd5
O-O
e8=Q
```

Source and target coordinates remain supported. These inputs are equivalent:

```text
e2 e4
e2-e4
e2 to e4
move e2 to e4
```

Promotions accept full names or `q`, `r`, `b`, and `n`. CLI commands are `undo`, `redo`,
`fen`, `pgn`, `new`, `legal`, `help`, and `quit`.

## Quality checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

## Project structure

```text
src/wizard_chess/
├── commands/       # text normalization, intents, parsing, resolution
├── application/    # shared session orchestration for every interface
├── domain/         # authoritative chess state, moves, events, results
├── gui/            # PySide6 board, interaction model, and main window
├── hardware/       # physical-board protocol and simulation
├── persistence/    # PGN filesystem service
├── speech/         # recognizer protocol and deterministic mock
└── main.py         # minimal development CLI
tests/
├── unit/
└── integration/
```

## Future stages

Later stages may add offline speech recognition, engine analysis, serial protocols, board
sensing, calibration, path planning, and motor control. Those systems must consume or
validate the digital state rather than duplicating chess rules or becoming their source.
