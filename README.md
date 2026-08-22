# Wizard Chess

Wizard Chess is a voice-controlled physical chessboard project. This repository contains the
**Stage 2 voice-control prototype**: a local Python application with terminal, PySide6 GUI,
and explicitly activated microphone input. Its digital chess state remains authoritative as
electronics and motorized movement are added later.

Voice is an input adapter, not a second chess implementation. Spoken commands are cleaned up
and submitted to the same parser, legality validation, game session, and move-event path as
typed input. Complete chess legality remains in `python-chess`.

## Architecture

The application follows a ports-and-adapters shape:

- `domain` owns the authoritative game, values, results, errors, and move events.
- `commands` normalizes text into state-free intents and resolves them against legal moves.
- `application` provides one shared game session for all input adapters.
- `gui` is the PySide6 desktop presentation/input adapter and runs recognition in a worker.
- `main.py` selects the GUI or CLI and composes their dependencies.
- `hardware` defines an output port and an in-memory simulated board.
- `speech` owns audio/recognizer ports, bounded capture, transcript normalization, voice
  orchestration, the optional local backend, and deterministic test doubles.
- `persistence` keeps filesystem operations outside the domain.

The current adapter flow is:

```text
Typed CLI ───────────────┐
GUI text/click ──────────┼── GameSession ── authoritative game
Microphone ── speech ────┘        │                 │
                                  └── MoveExecuted ─┘
                                           │
                                 simulated physical board
```

The GUI rerenders from an immutable snapshot of the authoritative game after every action;
it does not keep a second chess position. `SimulatedPhysicalBoard` records move events but
does not move physical pieces.

## Setup

Install Python 3.12+ and [`uv`](https://docs.astral.sh/uv/). Keyboard and GUI play do not need
the optional voice packages:

```bash
uv sync
uv run wizard-chess
```

For microphone input, install the isolated voice extra:

```bash
uv sync --extra voice
```

Voice uses `python-sounddevice` with the system's default PortAudio input. On Linux, PortAudio
may also need to be installed through the distribution package manager. For Debian/Ubuntu:

```bash
sudo apt install libportaudio2
```

The default recognizer is `faster-whisper` with the English `base.en` model on CPU using
INT8 compute. It supports Python 3.12+, runs inference locally, does not upload recordings,
does not keep audio files, and requires no account or API key. The model is loaded lazily on
the first voice command and reused thereafter. If `base.en` is not already cached,
`faster-whisper` downloads it from Hugging Face on first use; subsequent cached use can be
offline. Set `WIZARD_CHESS_VOICE_MODEL` to a local CTranslate2 model directory when first-use
network access is unavailable.

## Terminal and GUI use

Launch the terminal adapter with:

```bash
uv run wizard-chess --cli
```

Type `voice` at a turn prompt to record one utterance. The terminal reports `Listening...`,
`Processing...`, the raw transcript, and the shared command result. Typed commands remain
available before and after every voice attempt.

In the GUI, choose **Speak Move**. The voice status shows Idle, Listening, Processing,
Success, or Error and preserves the recognized transcript. Capture and inference run outside
the GUI event thread, overlapping recordings are prevented, and normal controls are restored
after failures.

Recording is explicitly initiated and finite: it waits up to 3 seconds for speech, stops
after about 0.8 seconds of trailing silence, and has a hard 6-second limit. There is no wake
word, passive listening, cloud recognition, or speech synthesis.

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
`fen`, `pgn`, `new`, `legal`, `help`, `voice`, and `quit`.

Representative spoken commands are:

```text
e four
e two e four
pawn to e four
knight f three
bishop to c four
queen takes d five
rook takes e eight check
castle kingside
castle queenside
```

Speech cleanup is deliberately conservative. It joins spoken coordinates (`e four` to `e4`),
handles coordinate homophones in context (`bee two`, `see four`, `for`, `ate`), and corrects
`night` to `knight` only when a square is present. Ambiguous or unsupported text is rejected;
the application never guesses a legal move.

## Voice configuration

Environment variables provide the small set of Stage 2 overrides:

| Variable | Default | Purpose |
| --- | --- | --- |
| `WIZARD_CHESS_VOICE_MODEL` | `base.en` | faster-whisper model ID or local model directory |
| `WIZARD_CHESS_VOICE_LANGUAGE` | `en` | recognition language |
| `WIZARD_CHESS_MICROPHONE` | system default | sounddevice input ID or name substring |
| `WIZARD_CHESS_VOICE_MAX_SECONDS` | `6.0` | hard recording limit |
| `WIZARD_CHESS_VOICE_START_TIMEOUT_SECONDS` | `3.0` | wait for speech before reporting silence |
| `WIZARD_CHESS_VOICE_SILENCE_SECONDS` | `0.8` | trailing silence that ends an utterance |
| `WIZARD_CHESS_VOICE_SILENCE_THRESHOLD` | `0.015` | simple RMS speech threshold |

For example:

```bash
WIZARD_CHESS_MICROPHONE=2 uv run wizard-chess
```

List PortAudio devices and their IDs with:

```bash
uv run python -m sounddevice
```

## Troubleshooting

- If voice dependencies are missing, run `uv sync --extra voice`. Keyboard input still works.
- If PortAudio cannot load on Debian/Ubuntu, install `libportaudio2` and restart the app.
- If no microphone opens, use `uv run python -m sounddevice`, verify that PipeWire,
  PulseAudio, or ALSA exposes an input, then set `WIZARD_CHESS_MICROPHONE` if needed.
- If quiet speech is reported as silence, lower
  `WIZARD_CHESS_VOICE_SILENCE_THRESHOLD`; raise it if background noise starts recording.
- If model initialization fails, verify first-use network access or set
  `WIZARD_CHESS_VOICE_MODEL` to an existing local faster-whisper/CTranslate2 model directory.
- CPU recognition latency depends on the machine. The GUI remains responsive, but the first
  use also includes model initialization.

## Manual voice acceptance

Automated tests use fakes and never require audio hardware or model downloads. On a Linux
machine with a usable microphone, run `uv sync --extra voice`, launch either UI, and speak:

```text
1. e four, e five
2. knight f three, knight c six
3. bishop c four
```

After each utterance, verify that the raw transcript is visible, the expected SAN appears,
the board changes, and the turn changes. Continue with `knight f six`, then say
`castle kingside` for White and verify castling. Also verify that an illegal move, unclear
speech, silence, and an unavailable microphone all leave the board unchanged and keep typed
input usable.

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
├── speech/         # capture, recognition, normalization, controller, and test doubles
└── main.py         # GUI/CLI composition and terminal voice invocation
tests/
├── unit/
└── integration/
```

## Current limitations and future stages

Stage 2 targets short English chess commands in ordinary close-range conditions. Silence
detection is threshold-based, recognition quality varies by microphone/CPU, the default model
needs a one-time download, and recognition cannot be interrupted once an inference call has
started. There is no wake word, conversation, speaker identification, engine analysis, or
physical movement.

A later project stage can add hardware communication and physical-board behavior while
continuing to consume authoritative application/domain events rather than duplicating chess
rules.
