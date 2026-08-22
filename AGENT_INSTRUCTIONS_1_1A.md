# AGENT_INSTRUCTION — Stage 1.1A: Expanded Chess Command Language

## Mission

Implement **Wizard Chess Stage 1.1A** by expanding the accepted move-command language while preserving the existing Stage 1 architecture and behavior.

The primary user-facing goal is to allow concise chess notation such as:

- `e4`
- `Nf3`
- `Bc4`
- `exd5`
- `Nxe5`
- `O-O`
- `O-O-O`
- `e8=Q`
- `exd8=Q`

Existing coordinate-oriented commands such as `e2 e4`, `e2-e4`, `e2 to e4`, and `move e2 to e4` must continue to work.

This stage is **command-language expansion only**. Do not implement the GUI, microphone input, speech recognition, chess engine analysis, serial communication, sensors, motors, or networking.

---

## Existing architectural constraints

The repository currently uses Python 3.12+, `uv`, a `src/` package layout, and `python-chess` as the sole source of chess rules.

Preserve these boundaries:

- `domain` owns authoritative game state, chess values, results, errors, and move events.
- `commands` turns text into state-free intents and resolves them against legal moves.
- `speech` and `hardware` remain replaceable adapters.
- `persistence` owns filesystem access.
- `main.py` remains composition / temporary CLI code rather than business logic.
- Domain code must not import GUI, speech, hardware, persistence, or other adapters.
- Do not duplicate chess legality rules already provided by `python-chess`.

The authoritative digital chess state must remain the single source of truth.

---

## Stage 1.1A target behavior

### 1. Preserve all current coordinate forms

All currently supported move commands must remain valid, including at minimum:

```text
e2 e4
e2-e4
e2 to e4
move e2 to e4
```

Promotion forms currently supported by the application must also remain valid.

No regression in undo, redo, FEN, PGN, legal-move validation, result detection, or emitted move events is acceptable.

### 2. Add Standard Algebraic Notation input

Accept legal moves written in SAN, using `python-chess` wherever practical rather than reimplementing SAN rules.

Required examples include:

```text
e4
Nf3
Bc4
exd5
Nxe5
O-O
O-O-O
e8=Q
exd8=Q
```

Also support SAN markers that naturally occur in valid notation, including:

```text
+
#
```

Examples:

```text
Qh5+
Qxf7#
```

Whether a move contains `+` or `#` must not bypass normal legality checking.

### 3. Resolve SAN against the current position

SAN is position-dependent. The implementation must therefore resolve SAN using the authoritative current game state.

Example:

From the initial position:

```text
e4
```

must resolve to the legal move:

```text
e2 -> e4
```

Do not hard-code source-square inference for pawns or pieces. Use the current legal position and `python-chess`.

### 4. Do not create a second chess-rules implementation

The command layer may normalize syntax, classify input, and delegate move resolution.

It must not independently implement:

- legal move generation;
- check detection;
- checkmate detection;
- castling legality;
- en passant legality;
- promotion legality;
- SAN disambiguation rules.

Those belong to `python-chess` and the existing authoritative domain state.

### 5. Preserve the command architecture

The preferred conceptual flow is:

```text
raw text
  ↓
command normalization / classification
  ↓
coordinate intent OR SAN intent
  ↓
resolution against authoritative game state
  ↓
domain Move
  ↓
existing game mutation / MoveEvent flow
```

Do not let SAN parsing mutate game state directly.

Do not add chess state to parser objects that are intended to remain state-free.

If the existing interfaces make SAN support awkward, introduce the smallest clean abstraction necessary rather than collapsing parsing, resolution, and mutation into one layer.

---

## Suggested implementation approach

Inspect the current `commands` package before making structural changes.

A reasonable design is to represent SAN as a distinct intent, for example conceptually:

```python
SanMoveIntent(notation="Nf3")
```

The parser / normalizer can recognize candidate SAN text without needing board state.

The resolver can then use the authoritative current board to translate the SAN intent into the application's existing move value.

This is a suggested architecture, not a mandatory class name. Follow existing project naming and style where possible.

Prefer `python-chess` APIs for SAN parsing and conversion.

Do not introduce a parallel move representation if the existing domain `Move` value can represent the resolved result.

---

## Input normalization

Maintain current normalization behavior.

For SAN, be conservative. Avoid inventing broad natural-language interpretation in this stage.

Accept standard chess notation, not arbitrary phrases such as:

```text
move the knight to f3
pawn to e4
take the bishop with my knight
king side castle
```

unless such phrases are already supported by the existing command grammar.

Do not silently transform arbitrary text into SAN guesses.

Reasonable normalization such as trimming surrounding whitespace is expected.

Coordinate parsing must continue to take precedence where necessary to preserve existing behavior.

---

## SAN specifics

Support standard SAN semantics through `python-chess`, including:

### Pawn moves

```text
e4
d5
a6
```

### Piece moves

```text
Nf3
Bc4
Qh5
Ke2
```

### Captures

```text
exd5
Nxe5
Bxf7+
Qxf7#
```

### Castling

```text
O-O
O-O-O
```

Use the letter `O` form required by SAN.

Supporting common zero variants such as `0-0` or `0-0-0` is optional unless already supported by current normalization. Do not expand scope solely to add informal notation variants.

### Promotions

```text
e8=Q
e8=R
e8=B
e8=N
```

and capture promotions such as:

```text
exd8=Q
```

### Check and checkmate suffixes

```text
+
#
```

must be accepted where the resulting move actually has the indicated SAN representation.

Do not manually determine check or checkmate.

### Disambiguation

Support SAN disambiguation according to the current legal position, e.g. forms conceptually like:

```text
Nbd2
R1e2
```

where required.

Do not implement the disambiguation algorithm manually.

---

## Command classification

The command system needs to distinguish among:

1. existing application/control commands;
2. existing coordinate-style move commands;
3. SAN move commands;
4. invalid/unrecognized input.

Do not allow a new SAN fallback to consume application commands such as:

```text
undo
redo
fen
pgn
new
legal
help
quit
```

Existing command semantics must remain unchanged.

The exact classifier design is up to the implementation, but errors should remain predictable and typed according to existing project conventions.

---

## Errors and invalid input

Invalid SAN must fail without changing authoritative game state.

Examples include malformed notation such as:

```text
Nh9
e9
Bx
```

and notation that is syntactically plausible but illegal in the current position.

Use the project's existing error/result conventions wherever possible.

Do not expose raw `python-chess` exceptions through the normal application interface if the current architecture already translates parsing/resolution failures into project-level errors.

After any rejected command:

- board state must be unchanged;
- move history must be unchanged;
- redo/undo state must not be corrupted;
- no physical-board move event may be emitted.

Failure handling should remain deterministic and testable.

---

## State and event invariants

A SAN-originated move and its coordinate-originated equivalent must produce equivalent application behavior.

For example, from the initial position:

```text
e4
```

and:

```text
e2 e4
```

must ultimately result in the same:

- authoritative board position;
- side to move;
- move history entry;
- undo behavior;
- redo behavior;
- FEN;
- PGN semantics;
- game-status evaluation;
- hardware-independent move event.

The input notation is an interface concern. It must not create a second move execution path.

---

## Required tests

Add or update tests at the most appropriate unit and integration levels.

### SAN parsing / resolution

Cover at least the following cases.

#### 1. Simple pawn move

From the initial position:

```text
e4
```

resolves to:

```text
e2e4
```

#### 2. Simple piece move

After a suitable position:

```text
Nf3
```

resolves correctly.

#### 3. Pawn capture

Test a legal:

```text
exd5
```

#### 4. Piece capture

Test a legal capture such as:

```text
Nxe5
```

#### 5. Kingside castling

Construct a legal position and verify:

```text
O-O
```

#### 6. Queenside castling

Construct a legal position and verify:

```text
O-O-O
```

#### 7. Promotion

Construct a legal position and verify:

```text
e8=Q
```

#### 8. Capture promotion

Construct a legal position and verify:

```text
exd8=Q
```

#### 9. Check suffix

Verify a legal SAN command ending in:

```text
+
```

#### 10. Checkmate suffix

Verify a legal SAN command ending in:

```text
#
```

#### 11. SAN disambiguation

Construct a position in which two identical pieces can legally move to the same destination.

Verify:

- correctly disambiguated SAN resolves;
- insufficiently or incorrectly disambiguated notation is rejected;
- resolution follows `python-chess`.

#### 12. Illegal SAN in the current position

Verify rejection and confirm state remains unchanged.

#### 13. Malformed SAN

Verify rejection and confirm state remains unchanged.

#### 14. Whitespace handling

Verify harmless surrounding whitespace is normalized consistently, for example:

```text
  e4
```

and:

```text
e4  
```

if consistent with existing command normalization.

---

## Backward-compatibility tests

Retain or add regression coverage for existing move forms:

```text
e2 e4
e2-e4
e2 to e4
move e2 to e4
```

Existing promotion syntax must remain covered.

Do not remove existing tests merely because SAN provides another way to enter the same move.

All existing Stage 1 functionality must continue to pass its tests unchanged unless a test genuinely needs extension for the new feature.

---

## Mixed-style integration test

Add at least one integration test that mixes command styles within the same game, for example:

```text
White: e4
Black: e7 e5
White: Nf3
Black: b8-c6
```

Verify that all commands modify one coherent authoritative game.

At minimum, verify the final board position and move history.

Where the existing integration suite checks hardware-independent move events, verify that SAN-originated moves emit the same event type and semantics as equivalent coordinate-originated moves.

---

## Undo and redo interaction

SAN must not bypass or alter the existing history model.

Test at least one flow such as:

```text
e4
e5
Nf3
undo
redo
```

and verify that the same state is recovered.

Do not store SAN strings as an alternate authoritative history if the existing history is based on domain moves or board state.

---

## PGN behavior

SAN input should naturally result in valid PGN through the existing game model.

Do not build PGN by concatenating the user's original command strings.

For example, coordinate input:

```text
e2 e4
```

should still be represented appropriately in PGN using chess notation generated from the authoritative game state.

SAN input and coordinate input for the same move must not create different PGN semantics.

---

## CLI behavior

The existing development CLI should accept newly supported SAN commands through the shared command path.

Do not build a separate SAN-only CLI parser or execution path.

Update CLI help text if it currently documents accepted move syntax.

A suitable compact help section would communicate that both SAN and coordinate input are accepted, for example:

```text
Moves:
  e4
  Nf3
  exd5
  O-O
  e8=Q

Coordinate forms:
  e2 e4
  e2-e4
  e2 to e4
  move e2 to e4
```

Keep CLI changes minimal.

The terminal remains a development interface, not a new architectural layer.

---

## Documentation

Update `README.md` to document Stage 1.1A support for SAN in addition to coordinate-based commands.

Include a compact representative set of examples, at minimum:

```text
e4
Nf3
exd5
O-O
e8=Q
```

Preserve documentation for existing coordinate forms.

Do not describe GUI or voice functionality as implemented.

If architectural documentation changes because of a new intent or resolver abstraction, update only the relevant sections and preserve the existing ports-and-adapters framing.

---

## Dependency policy

Prefer implementing Stage 1.1A using the already-required `python-chess` library.

Do not add another chess-notation or chess-rules dependency.

Do not add dependencies for:

- GUI frameworks;
- audio;
- speech recognition;
- chess engines;
- serial communication;
- hardware;
- networking.

If no new dependency is required, do not modify dependencies unnecessarily.

---

## Non-goals

Do **not** add any of the following in Stage 1.1A:

- graphical interface;
- mouse interaction;
- drag-and-drop moves;
- microphone support;
- speech recognition;
- broad natural-language chess interpretation;
- Stockfish or other engine analysis;
- serial protocols;
- motors;
- sensors;
- GPIO;
- board calibration;
- physical path planning;
- networking;
- cloud services;
- a second chess-rules implementation.

Do not begin Stage 1.1B as part of this task.

---

## Scope discipline

Prefer a focused implementation over a broad refactor.

Refactor existing command code only where needed to support SAN cleanly.

Do not rewrite unrelated Stage 1 components.

Do not move responsibilities between architectural layers without a clear need.

Do not place business logic in `main.py`.

Do not introduce an application or GUI architecture merely in anticipation of Stage 1.1B unless Stage 1.1A demonstrably requires a small reusable abstraction.

If a larger architectural improvement appears desirable but is not required for SAN support, leave it for a later stage.

---

## Quality requirements

Before considering the task complete, run:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

All checks must pass.

Keep public types and functions typed consistently with the existing project.

Follow existing naming, package layout, testing style, and error conventions.

Prefer small cohesive functions and explicit types.

Do not weaken type checking or lint configuration to make the implementation pass.

Do not delete or weaken existing tests simply because they expose a regression.

---

## Acceptance criteria

Stage 1.1A is complete only when all of the following are true:

1. A new game accepts:

   ```text
   e4
   ```

   and produces the same domain move/state transition as:

   ```text
   e2 e4
   ```

2. Legal SAN for normal pawn moves is accepted.

3. Legal SAN for piece moves is accepted.

4. Legal SAN captures are accepted.

5. Legal kingside and queenside castling notation is accepted.

6. Legal promotions and capture promotions are accepted.

7. Legal SAN carrying check and checkmate suffixes is accepted.

8. SAN disambiguation follows standard chess rules through `python-chess`.

9. Illegal SAN is rejected without mutating authoritative state.

10. Malformed SAN is rejected without mutating authoritative state.

11. Rejected SAN emits no physical-board move event.

12. Existing coordinate command forms remain functional.

13. Existing application commands remain functional.

14. Coordinate and SAN commands can be mixed within one game.

15. SAN-originated moves use the same authoritative domain mutation and event flow as coordinate-originated moves.

16. Undo and redo continue to work after SAN-originated moves.

17. FEN and PGN behavior remains correct.

18. Existing game-result detection remains correct.

19. README and CLI help reflect the expanded command syntax.

20. No GUI, speech, engine, serial, sensor, motor, networking, or unrelated functionality is introduced.

21. `uv run pytest` passes.

22. `uv run ruff check .` passes.

23. `uv run ruff format --check .` passes.

24. `uv run pyright` passes.

---

## Final implementation report

When implementation is complete, report:

- files changed;
- command-language behavior added;
- architectural adjustments made, if any;
- how SAN is resolved using `python-chess`;
- notable edge cases covered by tests;
- whether existing coordinate commands remain unchanged;
- the exact result of:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

Do not claim Stage 1.1B or GUI work is complete or started as part of this task.