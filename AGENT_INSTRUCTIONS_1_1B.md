# AGENT_INSTRUCTIONS — Stage 1.1B: Graphical Chess Interface

## Mission

Implement **Wizard Chess Stage 1.1B** by adding a desktop graphical interface on top of the existing authoritative digital chess application.

Stage 1.1B must make Wizard Chess usable as a conventional graphical chess application while preserving the architecture established in Stage 1 and extended in Stage 1.1A.

The GUI must support, at minimum:

- an interactive 8×8 chessboard;
- click-to-move interaction;
- legal-destination highlighting;
- last-move highlighting;
- typed move commands;
- both SAN and existing coordinate command syntax;
- move history;
- side-to-move and game-status display;
- New Game;
- Undo;
- Redo;
- board orientation / flip;
- basic FEN interaction;
- correct check, checkmate, stalemate, and game-over presentation.

The GUI is a **presentation/input adapter**. It must not become a second chess engine or a second source of game state.

Do not implement voice recognition, microphone input, Stockfish analysis, serial communication, motors, sensors, GPIO, physical-board calibration, or networking in this stage.

---

## Starting assumptions

Before making changes, inspect the repository as it exists after Stage 1.1A.

Do not assume that the internal structure is identical to the original Stage 1 scaffolding.

In particular:

- inspect the current `domain` API;
- inspect the current `commands` parser/resolver;
- inspect how SAN support was implemented;
- inspect `main.py`;
- inspect how undo/redo and FEN/PGN are exposed;
- inspect the current hardware-independent move-event flow;
- inspect existing tests before introducing a GUI-facing application API.

Preserve working Stage 1 and Stage 1.1A behavior.

The project uses:

- Python 3.12+;
- `uv`;
- a `src/` package layout;
- `python-chess` as the sole source of chess rules.

---

# Core architectural rule

The GUI must **not own an independent chess game state**.

There must be only one authoritative chess position.

Conceptually:

```text
                   ┌──────── CLI
                   │
User input ────────┼──────── GUI
                   │
                   └──── future voice
                            │
                            ▼
                   application/session layer
                            │
                            ▼
                  authoritative domain game
                            │
                            ▼
                         MoveEvent
                            │
                            ▼
                 physical-board output port
```

The GUI may keep ephemeral presentation state such as:

- currently selected square;
- board orientation;
- hover state;
- widget dimensions;
- whether a dialog is open.

It must not keep an independent authoritative representation of:

- piece positions;
- side to move;
- castling rights;
- en passant state;
- legal moves;
- move history;
- game result.

Those must come from the authoritative application/domain state.

---

# Architectural boundaries

Preserve the existing repository boundaries:

- `domain` owns authoritative chess state, chess values, results, errors, and move events.
- `commands` interprets textual move/control input.
- `hardware` remains a replaceable output adapter.
- `speech` remains a replaceable future input adapter.
- `persistence` owns filesystem access where applicable.
- GUI code belongs in a dedicated adapter/package.
- `main.py` remains composition/bootstrap code rather than business logic.
- `python-chess` remains the only source of chess rules.

Domain code must not import the GUI.

The GUI may depend on application/domain-facing interfaces, but the domain must remain unaware that a GUI exists.

---

# Application/session layer

Stage 1.1B is the point at which a reusable application-facing orchestration API is justified.

If the current repository already has an application/session abstraction, reuse and extend it rather than creating a parallel one.

If it does not, introduce the smallest clean application layer needed to prevent GUI callbacks from directly coordinating parser, game, history, and hardware behavior.

A reasonable target structure is conceptually:

```text
src/wizard_chess/
├── application/
│   └── session.py
├── commands/
├── domain/
├── gui/
│   ├── main_window.py
│   ├── board_widget.py
│   └── ...
├── hardware/
├── persistence/
├── speech/
└── main.py
```

Exact filenames are not mandatory. Follow the project's existing naming conventions.

The application/session abstraction should expose coherent operations required by multiple interfaces, conceptually similar to:

```python
play_text(command: str)
play_move(...)
undo()
redo()
new_game()
load_fen(...)
current_position(...)
```

Do not adopt these exact signatures blindly. Inspect the current domain and command APIs and expose the minimum appropriate surface.

The essential property is:

> CLI, GUI, and future voice input must all drive the same authoritative game behavior.

---

# GUI technology

Use **PySide6 / Qt for Python** for Stage 1.1B unless the current repository already contains an explicitly chosen GUI framework.

Add the dependency through the project's normal `uv` / `pyproject.toml` workflow.

Do not introduce multiple GUI frameworks.

Do not build the primary interface as a web application.

The GUI should remain compatible with the project's intended local desktop / embedded-computer deployment model.

---

# Stage 1.1B target interface

The first GUI should be functional and clean rather than visually elaborate.

A conceptual layout is:

```text
┌─────────────────────────────────────────────────────┐
│ Wizard Chess                  New  Undo  Redo  Flip │
├──────────────────────────────┬──────────────────────┤
│                              │                      │
│                              │   Move history       │
│                              │                      │
│        Chess board           │   1. e4     e5       │
│                              │   2. Nf3    Nc6      │
│                              │                      │
│                              │                      │
├──────────────────────────────┴──────────────────────┤
│ Move: [ Nf3____________________________ ] [ Play ] │
│ White to move                                      │
└─────────────────────────────────────────────────────┘
```

Exact layout may differ if a cleaner Qt implementation suggests a better structure.

Keep the interface straightforward and usable.

---

# 1. Chessboard rendering

Render a complete 8×8 chessboard.

Required behavior:

- exactly 64 visible squares;
- alternating light/dark square appearance;
- all pieces displayed according to the authoritative current position;
- board refreshes after every state-changing operation;
- White-oriented board by default;
- support flipped Black orientation;
- orientation changes must not change chess state.

The board must render from authoritative game state whenever it refreshes.

Do not update graphical piece positions as the primary source of truth and then attempt to synchronize the domain afterward.

The direction must be:

```text
domain position
      ↓
GUI rendering
```

not:

```text
GUI position
      ↓
domain synchronization
```

---

# 2. Piece rendering

Use a clean and distributable representation of chess pieces.

Suitable approaches include:

- Unicode chess symbols if they render reliably under Qt;
- project-owned / appropriately licensed SVG or image assets;
- Qt-native rendering using local project assets.

Do not introduce remote image dependencies.

Do not require network access to render pieces.

If external piece assets are added to the repository:

- ensure they are legally redistributable;
- record attribution/license information where required;
- keep assets local;
- avoid excessive asset complexity.

Prioritize correctness and clarity over visual sophistication.

---

# 3. Square coordinate mapping

The GUI must correctly map screen squares to chess squares in both orientations.

For White orientation:

```text
a8 ... h8
...
a1 ... h1
```

For Black orientation the visible board should rotate appropriately.

Coordinate transformation belongs in GUI/presentation code.

Chess legality must not.

Add direct tests for coordinate/orientation mapping if the mapping logic is implemented as testable pure functions.

---

# 4. Click-to-move interaction

Implement conventional two-click move input.

Expected interaction:

```text
click source square
        ↓
source becomes selected
        ↓
legal destinations are highlighted
        ↓
click legal destination
        ↓
move submitted through shared application flow
```

After a completed legal move:

- the authoritative game state changes;
- the board rerenders;
- the move appears in history;
- game status updates;
- last-move highlighting updates;
- the same hardware-independent move event is emitted as for equivalent typed input.

The GUI must not perform the actual chess mutation itself.

---

# 5. Piece selection behavior

When the user clicks one of the side-to-move's pieces:

- select it;
- visually indicate selection;
- obtain its legal destinations from authoritative/current legal-move information;
- highlight those destinations.

If the user selects another movable friendly piece:

- move selection to that piece;
- update legal destinations.

If the user clicks an irrelevant square:

- handle it predictably;
- do not mutate game state.

After:

- a completed move;
- undo;
- redo;
- new game;
- FEN load;
- game-over state change;

clear or appropriately recompute selection state.

---

# 6. Legal-move highlighting

Highlight legal destinations for the selected source square.

Do **not** calculate piece movement rules in the GUI.

Legal destinations must come from the existing authoritative chess rules / legal move set.

The GUI may transform legal domain moves into destination-square presentation data.

It must not independently determine:

- rook lines;
- bishop diagonals;
- knight jumps;
- pawn rules;
- castling legality;
- en passant legality;
- promotion legality;
- king safety.

Those remain the responsibility of `python-chess` through the authoritative game/domain layer.

---

# 7. Last-move highlighting

After a legal move, visually highlight:

- the source square;
- the destination square.

Example:

```text
e2 → e4
```

should highlight `e2` and `e4`.

Undo and redo must update last-move highlighting to reflect the authoritative current history.

Loading a position from FEN may legitimately result in no known last-move highlight unless the existing domain state can determine one.

Do not invent a previous move from a FEN string.

---

# 8. Promotion interaction

Click-to-move must support pawn promotion.

When a clicked move reaches a promotion square and multiple legal promotion moves exist, present an explicit promotion choice.

At minimum offer:

- Queen;
- Rook;
- Bishop;
- Knight.

Do not silently force queen promotion.

The selected promotion must then be submitted through the same authoritative move pipeline used by all other moves.

Typed promotion syntax from Stage 1.1A must remain functional, for example:

```text
e8=Q
exd8=N
```

---

# 9. Castling

Castling through click input must work naturally by selecting the king and selecting the legal castling destination.

Do not require the user to click the rook.

Do not implement castling rules in the GUI.

Use the authoritative legal move set.

Typed SAN forms must continue to work:

```text
O-O
O-O-O
```

---

# 10. En passant

Legal en passant moves must work through click-to-move interaction.

The GUI must not special-case en passant legality itself.

If the authoritative legal move set says an en passant capture is available, the corresponding destination should be highlighted and the move should execute correctly.

After execution, rerender from the authoritative position so the captured pawn disappears correctly.

---

# 11. Typed move command input

Provide a text input field and a submission action.

The command field must use the **same shared command-processing path** as existing terminal input.

Stage 1.1A syntax must work from the GUI, including representative commands such as:

```text
e4
Nf3
exd5
O-O
e8=Q
```

and existing coordinate forms such as:

```text
e2 e4
e2-e4
e2 to e4
move e2 to e4
```

Do not implement a second parser inside GUI code.

After successful submission:

- clear the input field;
- update board;
- update move history;
- update status;
- update last move;
- preserve the normal event flow.

On rejected input:

- do not mutate state;
- show concise user-facing feedback;
- leave the application usable.

---

# 12. Application/control commands

Do not blindly expose every terminal control command through the GUI text box if dedicated GUI controls provide the same action.

The GUI should have explicit controls for at least:

- New Game;
- Undo;
- Redo;
- Flip Board.

If the shared text command input still accepts existing control commands, that is acceptable, but do not create divergent behavior.

For example:

```text
undo
```

and clicking the Undo button must ultimately use the same application operation.

---

# 13. Move history

Display move history in normal chess notation.

The move-history view should resemble conventional numbered chess moves:

```text
1. e4 e5
2. Nf3 Nc6
3. Bb5 a6
```

Generate history from authoritative game state / existing move history.

Do not use the raw strings originally typed by the user.

Therefore:

```text
e2 e4
```

and:

```text
e4
```

must both appear consistently as:

```text
e4
```

in move history.

Use `python-chess` / existing domain functionality rather than constructing SAN manually.

---

# 14. Side-to-move display

Clearly indicate whose turn it is.

For example:

```text
White to move
```

or:

```text
Black to move
```

This status must derive from authoritative state.

It must update after:

- moves;
- undo;
- redo;
- new game;
- FEN load.

---

# 15. Game-status display

Display meaningful game state when applicable.

At minimum support presentation of:

- normal play;
- check;
- checkmate;
- stalemate;
- draw / terminal result where already detected by the domain.

Examples:

```text
White to move
```

```text
Black to move — Check
```

```text
Checkmate — White wins
```

```text
Stalemate — Draw
```

Use existing domain result/status semantics.

Do not independently calculate game results inside GUI code.

---

# 16. Game-over behavior

Once the authoritative game reports a terminal result:

- show the result clearly;
- do not allow further chess moves unless the existing domain explicitly permits them;
- keep New Game available;
- keep appropriate history/FEN/PGN inspection available;
- keep Undo available if existing application behavior permits undoing a terminal move.

Do not create separate GUI-only game-over rules.

---

# 17. New Game

Provide a visible New Game action.

When invoked:

- reset the authoritative game using the existing/new shared application API;
- clear selection;
- clear last-move highlighting;
- clear move history;
- restore appropriate status;
- rerender the starting position.

If accidental activation is easy and destructive, a lightweight confirmation dialog is acceptable.

Avoid elaborate workflow.

---

# 18. Undo

Provide a visible Undo action.

Undo must:

- use existing authoritative undo behavior;
- rerender the resulting position;
- update move history;
- update side to move;
- update game status;
- update last-move highlighting;
- clear stale square selection.

Disable or otherwise make Undo clearly unavailable when no undo is possible.

Do not maintain a GUI-specific undo stack.

---

# 19. Redo

Provide a visible Redo action.

Redo must mirror authoritative redo behavior.

After redo:

- rerender board;
- refresh move history;
- refresh status;
- refresh last-move highlighting;
- clear stale selection.

Disable or otherwise make Redo unavailable when no redo is possible.

Do not maintain a GUI-specific redo stack.

---

# 20. Board flip

Provide an action that changes board orientation.

Board flip is presentation-only.

It must not:

- change side to move;
- alter game state;
- alter move history;
- emit a move event;
- change FEN;
- change PGN.

After flipping, click-to-square mapping must remain correct.

---

# 21. FEN interaction

Provide basic FEN support in the GUI.

At minimum, users should be able to:

- inspect/copy the current FEN;
- load a FEN position.

A compact dialog/menu action is sufficient.

Use the existing domain/application FEN functionality.

On valid FEN load:

- authoritative state changes;
- board rerenders;
- status updates;
- current selection clears;
- move-history behavior follows existing domain semantics;
- last-move highlighting is cleared unless legitimately available.

On invalid FEN:

- authoritative state remains unchanged;
- display a concise error.

Do not implement FEN parsing manually in the GUI.

---

# 22. PGN

Do not build a full PGN management interface unless it follows naturally from the existing application with minimal scope.

If Stage 1 already exposes PGN export and it is trivial to expose through a menu/dialog, preserving access is desirable.

However, the core Stage 1.1B acceptance criteria concern the playable GUI.

Do not let PGN file management expand the stage into a large persistence/UI project.

---

# 23. Error feedback

Provide concise, non-blocking feedback for common rejected actions.

Examples:

- illegal move;
- malformed typed move;
- invalid FEN;
- attempted move after game over.

A status area, message label, or lightweight dialog is acceptable depending on severity.

Do not expose raw Python tracebacks to normal GUI users.

Do not swallow unexpected programming errors merely to keep the GUI open.

Project-level errors should be translated into appropriate presentation messages at the GUI boundary.

---

# 24. Hardware-independent event invariants

Stage 1.1B must preserve the hardware-independent move-event architecture.

A move made via:

```text
typed SAN
```

```text
typed coordinates
```

or:

```text
mouse clicks
```

must ultimately produce the same domain move and equivalent move event.

Example:

```text
typed: e4
```

```text
typed: e2 e4
```

```text
clicked: e2 then e4
```

must all result in equivalent:

- board state;
- history;
- FEN;
- PGN semantics;
- side to move;
- game status;
- MoveEvent.

The future physical board must not need to know which UI mechanism originated the move.

---

# 25. Keep the CLI

Do not delete the terminal interface.

The CLI remains useful for:

- development;
- automated testing;
- future hardware debugging;
- environments where the GUI cannot launch.

Refactor it only as necessary to share the same application/session layer with the GUI.

Avoid maintaining duplicated orchestration code.

Conceptually:

```text
CLI ──┐
      ├── application/session ── domain
GUI ──┘
```

---

# 26. Application entry point

The default project entry behavior should become the GUI unless the current packaging structure makes a transitional alternative substantially cleaner.

A preferred user-facing behavior is:

```bash
uv run wizard-chess
```

launching the GUI.

Retain an explicit way to run the CLI, for example conceptually:

```bash
uv run wizard-chess --cli
```

The exact command-line shape may follow the project's existing entry-point design.

Do not add a second unrelated executable unless there is a clear reason.

Argument parsing belongs in composition/bootstrap code, not in the domain.

---

# 27. GUI shutdown

Closing the main window should shut the application down cleanly.

Stage 1.1B has no background microphone, serial, or motor threads, so shutdown should remain simple.

Do not add unnecessary asynchronous infrastructure.

---

# 28. Responsiveness

All Stage 1.1B operations should be effectively local and immediate.

Avoid unnecessary threads or async frameworks.

Do not introduce concurrency simply because Qt supports it.

The current game operations are small and deterministic.

Future speech, engine analysis, and hardware I/O may require background execution, but those belong to later stages.

---

# 29. Visual design

Aim for a clear, restrained desktop interface.

Priorities:

1. board readability;
2. obvious selected square;
3. obvious legal destinations;
4. visible last move;
5. readable pieces;
6. readable move history;
7. clear game status;
8. consistent controls.

Do not spend substantial project scope on:

- animations;
- themes;
- elaborate transitions;
- custom window chrome;
- sound effects;
- advanced responsive layouts;
- extensive preferences.

Stage 1.1B is a functional GUI foundation.

---

# 30. Window resizing

The GUI should remain usable when resized.

The chessboard should preserve square geometry rather than stretching individual squares into obvious rectangles.

Move history and controls should remain accessible.

Do not over-engineer responsive behavior, but avoid a layout that works only at one exact window size.

---

# 31. Keyboard usability

Basic keyboard interaction should work naturally where Qt provides it.

At minimum:

- move command field should submit on Enter/Return;
- standard text editing shortcuts should work in text fields.

Additional hotkeys such as Ctrl+Z for Undo are optional.

Do not make extensive keyboard-shortcut design a requirement for this stage.

---

# 32. Testing strategy

Do not attempt to verify the entire feature exclusively through manual GUI testing.

Separate testable logic from Qt rendering where practical.

The test suite should cover:

- application/session orchestration;
- click-to-move translation;
- coordinate mapping;
- board orientation mapping;
- GUI-triggered authoritative moves;
- state refresh after undo/redo/new/FEN load;
- event equivalence across input methods.

Use GUI-level tests for essential UI wiring where practical, but do not create brittle pixel-perfect screenshot tests.

---

# Required tests

## A. Application/session integration

Verify that the shared application layer supports equivalent behavior for:

```text
e4
```

```text
e2 e4
```

and an equivalent direct/click move submission.

Assert equivalent authoritative final state.

Where possible also assert equivalent hardware-independent move events.

---

## B. GUI board rendering

Test that a new game represents the correct initial position.

At minimum verify meaningful square/piece mappings such as:

```text
a1 = White rook
e1 = White king
e2 = White pawn
e7 = Black pawn
e8 = Black king
a8 = Black rook
```

Prefer testing underlying board-view data or widget state over screenshot matching.

---

## C. White orientation mapping

Verify displayed square coordinates map correctly to chess squares when White is at the bottom.

---

## D. Black orientation mapping

Verify square mapping after board flip.

A click on a visible square after flipping must resolve to the correct chess square.

---

## E. Piece selection

From the initial position:

- select `e2`;
- verify it becomes selected;
- verify legal destinations include `e3` and `e4`.

Do not test by recreating pawn rules in test code unnecessarily; assert expected authoritative behavior.

---

## F. Click-to-move

From the initial position:

```text
click e2
click e4
```

must result in the authoritative move:

```text
e2e4
```

and the correct resulting board state.

---

## G. Illegal click move

Attempt an illegal destination.

Verify:

- authoritative state remains unchanged;
- no move event is emitted;
- GUI remains usable.

---

## H. Selection switching

Select one friendly movable piece, then another.

Verify the selected source and destination highlights update correctly.

---

## I. Typed SAN

Through the GUI command field submit:

```text
e4
```

Verify the same authoritative result as click `e2 → e4`.

---

## J. Typed coordinate command

Through the GUI command field submit:

```text
e2 e4
```

Verify normal Stage 1/1.1A behavior remains intact.

---

## K. Mixed GUI interaction

Play part of a game using mixed mechanisms, for example:

```text
White: type e4
Black: click e7 → e5
White: type Nf3
Black: click b8 → c6
```

Verify:

- one coherent authoritative game;
- correct board position;
- correct history;
- correct side to move.

---

## L. Undo

Make multiple moves, trigger GUI Undo, and verify:

- authoritative board state;
- side to move;
- history;
- status;
- last-move presentation.

---

## M. Redo

After Undo, trigger GUI Redo and verify the authoritative state is restored.

---

## N. New Game

After several moves, trigger New Game.

Verify:

- initial position restored;
- move history cleared;
- White to move;
- selection cleared;
- no stale last-move highlight remains.

---

## O. Board flip

Flip the board.

Verify:

- visible orientation changes;
- authoritative FEN is unchanged;
- move history is unchanged;
- no move event is emitted;
- clicks still map correctly.

---

## P. Promotion

Construct/load a position permitting promotion.

Through click interaction:

- select pawn;
- select promotion square;
- choose a promotion piece;
- verify correct authoritative promotion.

Include at least one underpromotion test.

---

## Q. Castling

Construct/load a legal castling position.

Verify click-to-move castling works using king source/destination and results in the correct authoritative position.

Do not manually reposition the rook in GUI code.

The board must rerender from the domain result.

---

## R. En passant

Construct/load a legal en passant position.

Verify it appears as a legal destination and executes correctly.

---

## S. Check display

Create a position resulting in check.

Verify GUI status reflects check according to authoritative game status.

---

## T. Checkmate display

Play or load a position where a legal move produces checkmate.

Verify:

- result shown correctly;
- board matches authoritative state;
- additional normal move attempts are rejected.

---

## U. Stalemate display

Load or reach a stalemate position.

Verify correct draw/stalemate presentation.

---

## V. FEN load

Load a valid FEN.

Verify:

- position rendered correctly;
- side to move correct;
- status correct;
- no stale selection remains.

---

## W. Invalid FEN

Submit invalid FEN.

Verify:

- current state is unchanged;
- user-facing error is produced;
- application remains usable.

---

## X. Move history

Mix SAN, coordinate, and click input.

Verify move history is normalized to standard chess notation rather than displaying raw input strings.

---

## Y. Move-event equivalence

For equivalent moves made through:

- SAN input;
- coordinate input;
- click interaction;

verify emitted hardware-independent event semantics are equivalent.

This is a key architectural acceptance test.

---

# PySide6 test considerations

Use a testing approach compatible with the project's dependency discipline.

If Qt test utilities are sufficient, prefer them.

Add a dedicated GUI-testing dependency only if it materially improves stable automated testing.

Do not introduce a large browser-style or end-to-end automation framework.

Tests should run without requiring manual interaction.

Where CI/headless execution requires a Qt platform configuration, configure tests appropriately and document it.

Avoid making the normal domain/unit test suite dependent on an available physical display server.

---

# Error and state invariants

For every rejected GUI operation:

```text
illegal move
malformed command
invalid FEN
invalid promotion selection
```

verify that:

- authoritative board state remains unchanged;
- move history remains unchanged;
- undo/redo state remains coherent;
- no physical move event is emitted;
- GUI presentation can refresh from authoritative state.

---

# Documentation updates

Update `README.md` to describe Stage 1.1B.

Document:

- that Wizard Chess now has a desktop GUI;
- how to launch it;
- how to launch the retained CLI;
- click-to-move interaction;
- typed SAN input;
- typed coordinate input;
- Undo/Redo/New Game;
- board flip;
- basic FEN interaction.

Update the architecture description to show that GUI and CLI are adapters over shared application/domain behavior.

For example conceptually:

```text
CLI ───────┐
           │
GUI ───────┼→ application/session
           │          ↓
future     │   authoritative game
speech ────┘          ↓
                    MoveEvent
                       ↓
                physical board
```

Do not describe voice recognition or physical movement as implemented.

---

# AGENTS.md update

If Stage 1.1B permanently changes repository-level contributor rules, update `AGENTS.md` accordingly.

In particular, the old restriction against adding GUI dependencies is superseded by the explicit Stage 1.1B requirement.

Preserve the spirit of the dependency boundary:

- PySide6 is now permitted for the GUI adapter;
- domain code must remain GUI-independent;
- additional unrelated GUI frameworks remain prohibited;
- audio, engine, serial, motor, sensor, and network dependencies remain outside current scope.

Do not remove architectural constraints merely because the GUI now exists.

---

# Dependency policy

Stage 1.1B may add the GUI dependency required to implement the desktop application.

Do not add dependencies for:

- microphone/audio capture;
- speech recognition;
- Stockfish;
- serial communication;
- GPIO;
- motor control;
- sensors;
- networking;
- cloud services.

Do not add a second chess-rules implementation.

Do not replace `python-chess`.

---

# Explicit non-goals

Do **not** implement any of the following in Stage 1.1B:

- voice commands;
- microphone input;
- speech recognition;
- text-to-speech;
- Stockfish evaluation;
- engine suggestions;
- evaluation bars;
- physical motor movement;
- serial communication;
- USB controller protocols;
- GPIO;
- reed switches;
- Hall sensors;
- piece-recognition sensors;
- physical board calibration;
- XY path planning;
- electromagnet control;
- LED Stockfish indicators;
- multiplayer networking;
- online chess services;
- account systems;
- cloud storage;
- web frontend;
- mobile application;
- elaborate animation system;
- sound effects;
- theme marketplace;
- extensive settings system.

Do not begin Stage 2 as part of this task.

---

# Scope discipline

The purpose of Stage 1.1B is:

> Make the authoritative digital Wizard Chess game comfortably playable through a desktop graphical interface.

It is not a general rewrite.

Prefer:

- small reusable application abstractions;
- thin GUI adapters;
- deterministic rendering from authoritative state;
- clear tests;
- limited dependency growth.

Avoid:

- duplicating chess logic;
- moving domain behavior into widgets;
- large speculative abstractions for future hardware;
- redesigning unrelated persistence or speech modules;
- adding features merely because Qt makes them easy.

---

# Quality requirements

Before considering Stage 1.1B complete, run:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

All checks must pass.

Additionally, manually launch the application and verify the main GUI path works:

```bash
uv run wizard-chess
```

and verify the retained CLI invocation works using the implemented CLI-selection mechanism.

Do not weaken:

- Ruff configuration;
- Pyright configuration;
- existing tests;
- architecture boundaries;

merely to make the GUI implementation pass.

Keep new code typed consistently with the rest of the project.

---

# Manual smoke test

Before completion, manually exercise at least this sequence through the GUI:

```text
1. Launch application.
2. Confirm starting board is correct.
3. Click e2 → e4.
4. Type e5.
5. Click g1 → f3.
6. Type Nc6.
7. Undo.
8. Redo.
9. Flip board.
10. Make another legal move while flipped.
11. Inspect move history.
12. Inspect current FEN.
13. Start a new game.
14. Confirm starting state is restored.
```

Also manually verify at least one:

- castling interaction;
- promotion interaction;
- checkmate presentation.

Do not rely on manual testing instead of automated tests; both are required where practical.

---

# Acceptance criteria

Stage 1.1B is complete only when all of the following are true:

1. `uv run wizard-chess` launches a functional desktop GUI, unless an equivalent documented entry-point structure is justified by the existing project.

2. The GUI renders the authoritative initial chess position correctly.

3. The GUI does not maintain an independent authoritative chess model.

4. Pieces can be selected by clicking.

5. Legal destinations are visually highlighted.

6. Illegal destinations do not mutate game state.

7. Legal moves can be completed through click-to-move interaction.

8. Pawn promotion presents Queen, Rook, Bishop, and Knight choices.

9. Castling works through legal king click-to-move interaction.

10. En passant works when legal.

11. Typed SAN commands from Stage 1.1A remain functional in the GUI.

12. Existing coordinate command syntax remains functional in the GUI.

13. SAN, coordinate, and mouse input can be mixed within one game.

14. All input mechanisms modify the same authoritative game.

15. Equivalent moves through SAN, coordinates, and mouse interaction produce equivalent hardware-independent move events.

16. Last-move source and destination are highlighted.

17. Move history is displayed in normalized chess notation.

18. Side to move is clearly displayed.

19. Check is clearly displayed.

20. Checkmate and winner/result are clearly displayed.

21. Stalemate/draw terminal state is clearly displayed.

22. New Game correctly resets authoritative state and presentation.

23. Undo correctly restores authoritative state and presentation.

24. Redo correctly restores authoritative state and presentation.

25. GUI controls do not maintain separate undo/redo history.

26. Board orientation can be flipped without changing chess state.

27. Click mapping remains correct after flipping.

28. Current FEN can be inspected/copied.

29. Valid FEN can be loaded.

30. Invalid FEN does not mutate current state.

31. Game-over state prevents illegal continuation through normal move input.

32. The CLI remains available for development/debugging.

33. CLI and GUI use shared application/domain behavior rather than independent chess implementations.

34. The domain does not depend on PySide6 or GUI modules.

35. `python-chess` remains the sole source of chess legality.

36. No voice, engine, serial, sensor, motor, GPIO, networking, or unrelated Stage 2 functionality is introduced.

37. README accurately documents GUI operation and current architecture.

38. `AGENTS.md` is updated if necessary to reflect the now-approved GUI dependency while preserving other architectural restrictions.

39. `uv run pytest` passes.

40. `uv run ruff check .` passes.

41. `uv run ruff format --check .` passes.

42. `uv run pyright` passes.

---

# Definition of architectural success

The critical Stage 1.1B architecture can be demonstrated by this equivalence:

From the initial position, each of these:

```text
GUI text input: "e4"
```

```text
GUI text input: "e2 e4"
```

```text
GUI clicks: e2 → e4
```

```text
CLI input: "e4"
```

must ultimately produce the same authoritative chess move:

```text
e2e4
```

and equivalent:

- domain state;
- FEN;
- move history;
- PGN semantics;
- side-to-move state;
- result state;
- hardware-independent move event.

Only the input adapter differs.

This invariant is more important than the exact widget implementation.

---

# Stage boundary

When Stage 1.1B is finished, Wizard Chess should have a complete human-friendly **digital** prototype:

```text
                 ┌──── CLI
                 │
Human input ─────┤
                 │
                 └──── GUI
                        ↓
                shared application layer
                        ↓
                command interpretation
                        ↓
              authoritative chess state
                        ↓
                    MoveEvent
                        ↓
             SimulatedPhysicalBoard
```

Stage 2 can then add:

```text
Microphone
    ↓
Speech recognizer
    ↓
speech normalization
    ↓
shared application layer
```

without changing chess rules or creating another game implementation.

Stage 1.1B must stop before that work begins.

---

# Final implementation report

When implementation is complete, report:

- files added;
- files modified;
- dependencies added;
- GUI structure introduced;
- application/session abstraction introduced or reused;
- how board rendering obtains authoritative state;
- how click-to-move reaches the shared move pipeline;
- how legal-destination highlighting is obtained;
- how promotion is handled;
- how CLI and GUI share behavior;
- how move-event equivalence was tested;
- GUI test strategy used;
- manual smoke-test results;
- any known minor UI limitations deliberately deferred;
- exact results of:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

Do not claim that Stage 2 voice control, engine integration, or physical-board control has been started or completed as part of this task.