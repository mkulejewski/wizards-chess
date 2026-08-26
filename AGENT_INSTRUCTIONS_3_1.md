# Wizard Chess — Stage 3.1: Hardware Abstraction, Physical Board State, Protocol Model, Simulator, and Physical-Move Planning Seam

Implement **Stage 3.1** of Wizard Chess: establish the software architecture for future physical-board control without requiring any actual Arduino, Raspberry Pi GPIO, motors, serial device, sensors, electromagnet, or other physical hardware.

This increment must create a clean, testable hardware abstraction beneath the existing authoritative chess application.

The central architectural rule is:

> `ChessGame` / `GameSession` remain the sole authorities for chess state, legality, SAN/UCI, check, mate, draws, and game history.  
> `PhysicalBoardState` represents what the software currently believes is physically present on the board.  
> The hardware subsystem consumes canonical application events and attempts to reproduce already-authorized moves physically. It must never become an alternative path for making or validating chess moves.

The current application already has a `MoveExecuted` event specifically intended as the Stage 3 physical-board seam. Build on that seam rather than bypassing it.

---

# 1. Goals

Stage 3.1 should provide the software foundation required for later stages to add:

- serial communication with an Arduino;
- XY carriage motion;
- electromagnet control;
- homing;
- calibration;
- path planning;
- captures;
- castling;
- physical board sensing;
- fault recovery;
- expected-vs-observed board reconciliation.

However, **none of those physical implementations belongs in this increment**.

By the end of Stage 3.1, Wizard Chess should be able to:

1. receive a canonical executed chess move from the existing application;
2. maintain a distinct model of the believed physical board state;
3. convert an executed chess move into a hardware-neutral physical-move request;
4. generate a deterministic sequence of abstract machine operations for simple moves;
5. execute those operations against a fake/simulated hardware controller;
6. track hardware-controller lifecycle independently from physical-board occupancy;
7. distinguish digital chess state from physical-board state;
8. distinguish synchronized, executing, desynchronized, and unknown physical states;
9. report success or failure without corrupting chess state;
10. expose deterministic traces suitable for automated tests;
11. preserve all existing CLI, GUI, voice, engine, persistence, and analysis functionality.

---

# 2. Architectural boundaries

Maintain the existing flow:

```text
CLI / GUI / voice / script / engine
                │
                ▼
            GameSession
                │
                ▼
            ChessGame
                │
                ▼
          MoveExecuted
                │
                ▼
       HardwareCoordinator
          ┌─────┴─────┐
          ▼           ▼
PhysicalBoardState   PhysicalMovePlanner
                          │
                          ▼
                     HardwarePort
                          │
                   ┌──────┴──────┐
                   ▼             ▼
             FakeHardware    future adapters
```

Treat these as separate state domains:

```text
ChessGame
    "What should the chess position be?"

PhysicalBoardState
    "What do we currently believe is physically on the board?"

HardwareControllerState
    "What is the machine/controller doing?"

PhysicalSynchronization
    "Does the believed physical state correspond to the digital state?"
```

Do not collapse these concepts into one object.

Do not allow hardware code to:

- call `ChessGame.push()` directly;
- submit user commands;
- resolve chess legality;
- calculate check or mate;
- maintain castling rights;
- act as another `python-chess.Board`;
- create chess moves independently.

The domain layer must remain independent of concrete hardware dependencies.

Prefer dependency inversion:

```text
application/hardware orchestration
        ↓
abstract hardware port
        ↓
fake now / serial later
```

Do not import `pyserial`, GPIO libraries, Arduino libraries, or platform-specific hardware packages in Stage 3.1.

---

# 3. Introduce or expand the hardware package

Add a coherent package under the existing project structure, following repository conventions.

A likely structure is:

```text
src/wizard_chess/hardware/
    __init__.py
    models.py
    board_state.py
    port.py
    geometry.py
    planner.py
    coordinator.py
    fake.py
```

Exact filenames may differ if the existing architecture suggests a cleaner fit.

Responsibilities should remain separated.

### `models`

Hardware-neutral value objects, machine operations, controller states, synchronization states, results, and errors.

### `board_state`

`PhysicalBoardState` and related physical piece/location abstractions.

### `port`

Abstract controller interface / protocol.

### `geometry`

Logical chess-square to physical-coordinate conversion.

### `planner`

Translation from canonical chess movement information into abstract physical operations.

### `coordinator`

Lifecycle and orchestration between chess move events, `PhysicalBoardState`, planner, and hardware port.

### `fake`

Deterministic in-memory hardware implementation for testing and later simulator/debug tooling.

Avoid one large module containing all behavior.

---

# 4. PhysicalBoardState

Introduce a first-class `PhysicalBoardState`.

Its purpose is:

> Represent the software's current belief about where physical chess pieces are.

It is **not** a second chess rules engine.

It must not know about:

- legal moves;
- check;
- checkmate;
- stalemate;
- repetition;
- castling legality;
- SAN;
- PGN;
- Stockfish;
- clocks.

Those remain exclusively under `ChessGame` / `GameSession`.

A conceptual model may resemble:

```python
@dataclass(frozen=True)
class PhysicalBoardState:
    pieces: Mapping[Square, PhysicalPiece]
    synchronization: PhysicalSynchronization
```

Adapt the exact implementation to repository conventions.

Prefer immutable snapshots or controlled state transitions over publicly mutable dictionaries.

---

# 5. Physical piece identity

Do not assume that square occupancy alone will be sufficient forever.

A future physical system may need to distinguish individual pieces because:

- captured pieces may enter graveyard locations;
- rooks may need identity during castling/recovery;
- promotion may introduce replacement pieces;
- sensors may distinguish occupancy but not identity;
- a piece may temporarily be in transit.

For Stage 3.1, keep this minimal.

A physical piece should at least preserve enough identity to distinguish:

```text
color
piece type
```

If introducing a lightweight stable piece identifier is straightforward and useful, do so.

Do not build a complete inventory-management system yet.

---

# 6. Physical locations and uncertainty

The physical model must be capable of representing the fact that hardware can enter states that are impossible in ordinary chess.

Examples:

```text
piece between squares
piece being carried
piece removed from the board
piece location uncertain
physical execution failed halfway
```

Do not model `PhysicalBoardState` simply as another `python-chess.Board`.

For Stage 3.1, use the simplest representation that supports correct failure semantics.

At minimum, the architecture must be able to say:

```text
known synchronized board
```

versus:

```text
physical piece location cannot currently be trusted
```

A future-compatible representation may use concepts equivalent to:

```text
OnSquare(square)
InTransit
OffBoard(location)
Unknown
```

but do not over-engineer these types if Stage 3.1 only requires `OnSquare` and `Unknown`.

The important requirement is:

> after a partial physical failure, do not falsely claim that the physical board still matches either the old or new digital position.

---

# 7. Initializing PhysicalBoardState

When hardware participation begins, `PhysicalBoardState` may initially be seeded from the authoritative `ChessGame` position.

This represents an **assumption**, not a sensor observation.

For Stage 3.1 this is acceptable because no physical sensing exists yet.

The implementation should make it conceptually possible for future stages to distinguish:

```text
expected physical state
observed physical state
```

but do not implement sensor reconciliation now.

Initialization should not create another chess-authority path.

If a FEN/PGN/new-game operation replaces the authoritative game position, the hardware subsystem must not silently assume the real physical board changed with it.

Choose a conservative policy.

For example:

- mark the physical board as `UNKNOWN` or `DESYNCHRONIZED`;
- require explicit reinitialization of physical assumptions.

Do not claim synchronization when the software has no reason to know that the physical pieces changed.

---

# 8. Physical synchronization status

Introduce an explicit synchronization model.

At minimum distinguish states equivalent to:

```text
SYNCHRONIZED
EXECUTING
DESYNCHRONIZED
UNKNOWN
```

Semantics:

### `SYNCHRONIZED`

The believed physical board state agrees with the authoritative digital game state.

### `EXECUTING`

A physical move corresponding to an already-executed digital move is currently being reproduced.

### `DESYNCHRONIZED`

The physical layer is known or strongly believed not to match the digital position.

### `UNKNOWN`

The physical position cannot currently be trusted.

Keep synchronization distinct from controller lifecycle state.

For example:

```text
HardwareControllerState.READY
PhysicalSynchronization.DESYNCHRONIZED
```

is valid.

The machine can be mechanically healthy while the pieces are in the wrong places.

---

# 9. Hardware controller lifecycle state

Introduce a separate explicit hardware/controller state model.

At minimum distinguish states equivalent to:

```text
DISCONNECTED
CONNECTED
UNCALIBRATED
READY
EXECUTING
FAULT
ESTOP
```

If `CONNECTED` and `UNCALIBRATED` overlap awkwardly, use a cleaner equivalent state representation, but keep the same semantic distinctions.

Transitions must be explicit and testable.

For example:

```text
DISCONNECTED
    ↓ connect
CONNECTED / UNCALIBRATED
    ↓ simulated readiness/home
READY
    ↓ execute operation sequence
EXECUTING
    ↓ success
READY
```

Failures should move the controller to an appropriate fault state.

Illegal operations must be rejected predictably.

Examples:

- move while disconnected;
- execute while already executing;
- execute while in fault;
- physical motion before readiness;
- commands after emergency stop.

Do not silently ignore invalid state transitions.

---

# 10. Hardware-neutral machine operations

Create typed operation models representing commands that a future physical controller can execute.

Do **not** make Arduino firmware understand chess notation such as:

```text
e2e4
Nf3
O-O
```

The low-level hardware layer should operate using machine-level concepts.

For Stage 3.1, support abstractions approximately equivalent to:

```text
MoveTo
MagnetOn
MagnetOff
Home
Stop
```

The exact model may use dataclasses, enums, discriminated unions, or another repository-consistent pattern.

Conceptually:

```python
MoveTo(x=..., y=...)
SetMagnet(enabled=True)
MoveTo(x=..., y=...)
SetMagnet(enabled=False)
```

Operations must be:

- immutable where practical;
- strongly typed;
- equality-comparable for deterministic tests;
- serializable/debuggable enough to generate traces later;
- independent of transport details.

Do not encode serial strings in the domain operation models.

---

# 11. Separate protocol semantics from transport

Stage 3.1 should establish a protocol-level command/result vocabulary without implementing actual serial communication.

Model result concepts such as:

```text
ACK
COMPLETED
REJECTED
FAULT
TIMEOUT
```

or a cleaner equivalent.

A future serial adapter should eventually map:

```text
HardwareOperation
      ↓
wire message
      ↓
Arduino
      ↓
wire response
      ↓
HardwareResult
```

For now, only the Python-side semantic representation and fake implementation are needed.

Do not prematurely define a brittle textual wire format unless it materially benefits the design.

If a minimal protocol version identifier is useful, add one without tying the software to an unimplemented Arduino transport.

---

# 12. HardwarePort interface

Define a replaceable hardware port/interface.

It should support lifecycle and execution functionality equivalent to:

```python
connect()
disconnect()
home()
execute(...)
stop()
emergency_stop()
status()
```

Use the narrowest interface appropriate to the current architecture.

Important constraints:

- no chess semantics in the port;
- no `PhysicalBoardState` mutation inside the low-level port;
- no Qt dependency;
- no serial dependency;
- no global singleton;
- no implicit connection during import;
- no hardware side effects during construction;
- explicit shutdown/cleanup.

The port controls machinery.

The coordinator controls the relationship between machine execution and `PhysicalBoardState`.

The port should return typed results or raise controlled subsystem errors according to existing repository conventions.

Unexpected implementation exceptions should not leak throughout the application.

---

# 13. Physical board geometry abstraction

Introduce a minimal geometry abstraction that can translate chess squares into **logical physical coordinates**.

Do not implement real calibration yet.

For Stage 3.1, support deterministic idealized board geometry such as:

```text
a1 → (0, 0)
b1 → (1, 0)
...
h8 → (7, 7)
```

or square-center coordinates based on a configurable square pitch.

Prefer a reusable model such as:

```python
BoardGeometry
square_to_position(square)
```

The design should anticipate future calibration fields such as:

- board origin;
- square pitch;
- X inversion;
- Y inversion;
- carriage/magnet offset;
- physical bounds;
- steps per millimetre.

But do not implement unnecessary calibration machinery now.

Do not scatter coordinate conversion formulas throughout planner code.

---

# 14. PhysicalMovePlanner

Implement a deterministic planner that translates a canonical chess move into abstract machine operations.

For **Stage 3.1**, fully support only:

```text
ordinary non-capturing moves
```

Conceptually:

```text
move carriage to source
enable magnet
move carriage to destination
disable magnet
```

Example:

```text
e2 → e4
```

may plan as:

```python
[
    MoveTo(position_of_e2),
    SetMagnet(True),
    MoveTo(position_of_e4),
    SetMagnet(False),
]
```

The planner must be pure or near-pure.

It must not:

- execute hardware commands;
- mutate `PhysicalBoardState`;
- mutate `ChessGame`;
- depend on Qt;
- query mutable current game state in a way that makes the historical event ambiguous.

It should operate from an immutable description of the executed move.

If needed, derive a physical move descriptor from `MoveExecuted` at event time.

---

# 15. Explicit handling of unsupported move types

Do **not** fake support for:

- captures;
- castling;
- en passant;
- promotion.

Stage 3.1 should recognize when a move requires future physical logic and report this explicitly.

Represent unsupported planning conditions using controlled errors or results such as:

```text
UnsupportedPhysicalMove
```

with specific reasons where appropriate:

```text
CAPTURE_NOT_IMPLEMENTED
CASTLING_NOT_IMPLEMENTED
EN_PASSANT_NOT_IMPLEMENTED
PROMOTION_NOT_IMPLEMENTED
```

Do not produce an unsafe direct source→destination path for captures merely because the chess move is legal.

If such a move occurs digitally while physical hardware is active, the digital move remains valid, but the physical layer must enter an appropriate `DESYNCHRONIZED` or `UNKNOWN` state rather than pretending physical execution occurred.

---

# 16. HardwareCoordinator

Introduce an application-level coordinator responsible for consuming executed moves and coordinating the physical subsystem.

Responsibilities should include:

1. accept a canonical `MoveExecuted` notification;
2. determine the current `PhysicalBoardState`;
3. derive/request a physical plan;
4. validate hardware readiness;
5. mark physical synchronization as `EXECUTING`;
6. execute the plan through `HardwarePort`;
7. update `PhysicalBoardState` only when execution completes successfully;
8. mark synchronization appropriately after success or failure;
9. record success/failure;
10. preserve controller state;
11. prevent overlapping execution;
12. expose deterministic status useful to future GUI integration.

The coordinator must **not**:

- decide whether a chess move is legal;
- alter chess history;
- automatically undo chess moves;
- submit engine/user commands;
- know about Qt widgets;
- know about serial byte framing.

---

# 17. Successful physical-state transition

For a normal non-capturing move such as:

```text
e2 → e4
```

the expected logical sequence is:

```text
ChessGame executes e2e4
        ↓
MoveExecuted
        ↓
PhysicalBoardState still represents pre-motion physical state
        ↓
synchronization = EXECUTING
        ↓
physical plan executes
        ↓
all operations succeed
        ↓
PhysicalBoardState moves pawn e2 → e4
        ↓
synchronization = SYNCHRONIZED
```

The state update must occur only after successful physical completion.

Do not mutate `PhysicalBoardState` optimistically before execution succeeds.

---

# 18. Partial failure semantics

This is a core Stage 3.1 requirement.

Example:

```text
MOVE_TO e2       succeeds
MAGNET_ON        succeeds
MOVE_TO e4       fails
```

At this point:

```text
ChessGame:
    pawn legally exists on e4

HardwareControllerState:
    FAULT

PhysicalBoardState:
    must not falsely claim a reliable synchronized square state

PhysicalSynchronization:
    DESYNCHRONIZED or UNKNOWN
```

Do not:

- roll back `ChessGame`;
- generate an undo move;
- pretend the pawn remains safely on e2;
- pretend the pawn reached e4;
- automatically continue the remaining normal operations.

The actual physical pawn may be somewhere between squares.

Represent this uncertainty explicitly.

---

# 19. Transaction-like physical execution

Treat each physical move as a transaction-like operation:

```text
PLAN
  ↓
VALIDATE
  ↓
MARK EXECUTING
  ↓
EXECUTE
  ↓
UPDATE PhysicalBoardState
  ↓
MARK SYNCHRONIZED
```

If any operation fails:

```text
FAULT
+
DESYNCHRONIZED / UNKNOWN
```

and remaining ordinary operations should not continue unless explicitly required by a future recovery policy.

For Stage 3.1, deterministic fail-fast behavior is preferred.

Keep recovery policy separate enough that later stages can improve it.

---

# 20. Comparing ChessGame and PhysicalBoardState

Provide a minimal reconciliation mechanism.

It should answer conceptually:

```text
Does PhysicalBoardState represent the same piece placement
as the authoritative digital chess position?
```

This comparison is informational only.

It must not make `PhysicalBoardState` authoritative.

For example:

```python
coordinator.is_synchronized()
```

or an equivalent API may compare physical and logical placement.

Do not compare chess metadata such as:

- side to move;
- castling rights;
- en-passant square;
- clocks;
- repetition counters.

Physical synchronization concerns physical piece placement.

Future sensor stages may compare:

```text
expected physical state
vs
observed physical state
```

but Stage 3.1 uses believed state only.

---

# 21. New Game / FEN / PGN replacement semantics

Handle authoritative game replacement conservatively.

Examples:

```text
New Game
Load FEN
Import PGN
```

These operations change the digital chess state but do not physically rearrange the real board.

Therefore, when hardware state exists, do not silently reset `PhysicalBoardState` and declare it synchronized.

Prefer one of:

```text
PhysicalSynchronization.UNKNOWN
```

or:

```text
PhysicalSynchronization.DESYNCHRONIZED
```

until an explicit physical initialization/reconciliation action occurs.

Tests should cover this behavior where practical.

---

# 22. Emergency stop semantics

Model emergency-stop behavior now even though there is no physical motor yet.

An emergency stop should:

- immediately mark the hardware controller as stopped/faulted;
- reject further motion execution;
- be distinct from an ordinary recoverable command failure;
- mark physical synchronization as uncertain where appropriate;
- require an explicit reset/reconnect/recovery action before returning to `READY`.

The fake hardware should support testing this behavior.

Do not rely on ordinary cancellation alone to model an E-stop.

---

# 23. Deterministic FakeHardware

Implement a first-class deterministic fake.

It should support:

- connection state;
- readiness/homing state;
- operation recording;
- configurable success;
- failure injection at a chosen operation;
- optional timeout simulation;
- emergency-stop simulation;
- execution trace inspection.

For example, tests should be able to configure:

```python
fake.fail_on_operation(2)
```

and verify coordinator behavior.

The fake should keep a trace conceptually like:

```text
CONNECT
HOME
MOVE_TO (...)
MAGNET ON
MOVE_TO (...)
MAGNET OFF
```

Do not use sleeps or timing-dependent behavior in ordinary tests.

The fake should be reusable by later:

- hardware simulator UI;
- integration tests;
- scripted demonstrations;
- serial adapter tests.

The fake hardware should model the controller, not silently mutate authoritative chess state.

---

# 24. Event integration

Connect Stage 3.1 to the existing canonical `MoveExecuted` seam in a minimal, dependency-safe manner.

Requirements:

- hardware is optional;
- ordinary Wizard Chess behavior remains unchanged when hardware is absent/disabled;
- a hardware failure must not crash ordinary gameplay;
- engine, GUI, CLI, voice, and scripts should continue using `GameSession`;
- no input path receives special hardware-aware chess logic;
- one executed move must produce at most one physical execution attempt.

If enabling automatic event subscription now would introduce awkward coupling, establish the coordinator and tested event-consumer seam without forcing hardware into default application startup.

Prefer clean architecture over premature GUI wiring.

---

# 25. No GUI control panel yet

Do not implement the full future hardware developer panel in this increment.

A later stage may add controls such as:

```text
Connect
Disconnect
Home
Jog X/Y
Magnet On/Off
Move to square
Calibration
Emergency stop
Physical board status
Reconcile
```

Stage 3.1 only needs clean application APIs that such a GUI can consume later.

If a tiny developer/debug CLI improves testability and fits naturally, keep it optional and minimal.

Do not expand scope into major UI work.

---

# 26. Configuration

Add only configuration needed for the abstraction.

Possible settings include:

```text
hardware enabled
hardware backend = fake/off
```

Do not add:

- serial port;
- baud rate;
- GPIO pins;
- motor speeds;
- acceleration;
- real calibration values.

Follow the current Wizard Chess settings architecture and precedence rules.

Defaults must preserve current software-only behavior.

---

# 27. Error model

Introduce controlled hardware subsystem errors consistent with the rest of Wizard Chess.

Distinguish meaningful conditions such as:

```text
HardwareUnavailable
HardwareNotReady
HardwareBusy
HardwareFault
HardwareEmergencyStop
UnsupportedPhysicalMove
HardwareExecutionFailed
HardwareTimeout
PhysicalBoardUnknown
PhysicalBoardDesynchronized
```

Exact names may differ.

Do not expose raw implementation exceptions to high-level application code.

Errors should carry useful diagnostic context where possible:

```text
operation index
failed operation
hardware controller state
physical synchronization state
reason
```

---

# 28. Logging and diagnostics

Use the existing logging infrastructure.

Log important lifecycle events:

```text
hardware connected
hardware ready
physical board initialized
physical move plan generated
physical execution started
physical board marked EXECUTING
operation completed
physical execution completed
PhysicalBoardState updated
board synchronized
physical execution failed
board desynchronized
controller entered fault
emergency stop
```

Do not spam normal logs with excessive low-level noise.

Detailed operation traces should be available at an appropriate debug level or through the fake trace.

---

# 29. Concurrency expectations

Keep Stage 3.1 compatible with future asynchronous hardware operation.

Do not assume that real motor execution will complete instantaneously.

The coordinator API should not be architected in a way that requires future motor movement to block the Qt event thread.

However:

- do not introduce unnecessary threading complexity merely for `FakeHardware`;
- preserve deterministic tests;
- clearly separate planning from execution;
- clearly separate controller state from physical-board state;
- structure APIs so that a future worker/task adapter can wrap blocking serial execution.

If existing application async patterns provide an obvious reusable approach, follow them.

---

# 30. Tests

Add comprehensive deterministic tests.

At minimum cover:

## PhysicalBoardState

- initialization from a standard game position;
- correct piece placement representation;
- immutable or controlled mutation semantics;
- successful physical move updates source and destination correctly;
- board state remains distinct from `ChessGame`;
- physical state does not provide chess-legality operations;
- unknown/desynchronized state can be represented;
- digital game replacement does not silently claim physical synchronization.

## Geometry

- square→coordinate mapping;
- orientation consistency;
- invalid square behavior if applicable.

## Planner

- ordinary move produces expected operation sequence;
- planner is deterministic;
- source and target coordinates are correct;
- magnet activation/deactivation ordering is correct;
- captures rejected explicitly;
- castling rejected explicitly;
- en passant rejected explicitly;
- promotion rejected explicitly.

## FakeHardware

- connect/disconnect;
- home/readiness transition;
- successful operation execution;
- operation trace;
- injected failure;
- timeout simulation;
- emergency stop;
- commands rejected in invalid states.

## Coordinator

- successful ordinary move;
- correct controller-state transitions;
- correct synchronization transitions;
- physical board marked `EXECUTING` during execution where observable;
- successful execution updates `PhysicalBoardState`;
- planner failure does not execute hardware;
- unsupported move causes physical desynchronization rather than fake success;
- hardware failure produces desynchronization/fault;
- partial operation failure stops subsequent normal execution;
- partial failure does not falsely move the physical piece to the destination;
- overlapping execution rejected;
- execution while disconnected rejected;
- execution while unready rejected;
- E-stop behavior;
- `ChessGame` state remains authoritative after hardware failure.

## Reconciliation

Test:

```text
ChessGame placement == PhysicalBoardState placement
→ SYNCHRONIZED
```

and:

```text
ChessGame placement != PhysicalBoardState placement
→ DESYNCHRONIZED
```

without allowing physical state to mutate the game.

## Existing integration

Verify a normal chess move still flows through the authoritative application exactly once.

If event subscription is introduced, prove:

```text
GameSession move
→ one MoveExecuted
→ one hardware plan
→ one physical execution
```

without duplication.

---

# 31. Core acceptance scenarios

Implement deterministic integration tests or demonstrations for both success and failure.

## Successful move

```text
Start standard chess game
↓
initialize PhysicalBoardState from starting position
↓
Submit e4 through GameSession
↓
ChessGame legally executes e2e4
↓
MoveExecuted emitted
↓
HardwareCoordinator receives the event
↓
PhysicalMovePlanner produces:

MOVE_TO e2
MAGNET_ON
MOVE_TO e4
MAGNET_OFF

↓
PhysicalSynchronization = EXECUTING
↓
FakeHardware executes all four operations
↓
PhysicalBoardState updates pawn e2 → e4
↓
PhysicalSynchronization = SYNCHRONIZED
↓
ChessGame and PhysicalBoardState both contain the pawn on e4
```

## Partial hardware failure

```text
Start standard chess game
↓
Submit e4
↓
ChessGame legally records pawn on e4
↓
FakeHardware executes:

MOVE_TO e2       OK
MAGNET_ON        OK
MOVE_TO e4       FAIL

↓
remaining ordinary operations stop
↓
HardwareControllerState = FAULT
↓
PhysicalSynchronization = DESYNCHRONIZED or UNKNOWN
↓
PhysicalBoardState does NOT falsely assert a reliable pawn location
↓
ChessGame still legally contains the pawn on e4
↓
no undo or compensating chess move is generated
```

This second scenario is a central architectural acceptance requirement.

---

# 32. Regression requirements

All existing behavior must continue to work.

Run:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

Do not weaken existing tests or typing to accommodate Stage 3.1.

Add new tests rather than replacing existing coverage.

The new hardware subsystem must not require:

- Arduino;
- serial port;
- Raspberry Pi;
- microphone;
- Stockfish;
- network access.

The normal test suite must remain deterministic and hardware-free.

---

# 33. Documentation

Update `README.md` with a concise Stage 3.1 architecture section.

Document:

```text
ChessGame / GameSession
    ↓
MoveExecuted
    ↓
HardwareCoordinator
    ├── PhysicalBoardState
    └── PhysicalMovePlanner
             ↓
        HardwarePort
```

Explain explicitly:

```text
ChessGame:
    authoritative logical chess position

PhysicalBoardState:
    believed physical piece placement

HardwareControllerState:
    machine/controller lifecycle

PhysicalSynchronization:
    relation between digital and believed physical state
```

Also document:

- hardware reproduces moves but does not authorize them;
- Stage 3.1 uses only fake/simulated hardware;
- no sensors exist yet;
- initial physical state is assumed rather than observed;
- partial physical failures create uncertainty/desynchronization;
- real serial/Arduino support is deferred;
- simple non-capturing moves are the only physically planned chess moves in this increment;
- special moves and obstacle avoidance remain later work.

Update `AGENT_INCREMENTS.md` after implementation with:

- Stage 3.1 status;
- delivered architecture;
- `PhysicalBoardState` implementation;
- synchronization semantics;
- test/verification evidence;
- deferred Stage 3.2 scope.

Do not claim physical hardware acceptance.

---

# 34. Explicitly deferred from Stage 3.1

Do not implement:

- `pyserial`;
- Arduino firmware;
- USB device discovery;
- Raspberry Pi GPIO;
- motor drivers;
- stepper timings;
- acceleration profiles;
- XY carriage control;
- physical homing switches;
- electromagnet hardware;
- Hall/reed/RFID sensing;
- observed physical-board state;
- sensor fusion;
- capture graveyard mechanics;
- castling movement sequence;
- en passant physical sequence;
- promotion replacement;
- obstacle avoidance;
- A* path planning;
- board calibration wizard;
- real millimetre/step calibration;
- automatic physical board reconciliation;
- automatic recovery movement;
- hardware GUI developer panel;
- LEDs;
- speech synthesis.

Design Stage 3.1 so these can be added cleanly later, but do not pre-implement them.

---

# 35. Future physical-state architecture

Keep the Stage 3.1 model compatible with a later evolution toward:

```text
ChessGame
    authoritative desired position

ExpectedPhysicalBoardState
    what physical execution should have produced

ObservedPhysicalBoardState
    what sensors actually detect

Reconciler
    expected vs observed

HardwareControllerState
    state of carriage/magnet/controller
```

Do not implement this full structure now.

Stage 3.1 should only establish enough abstraction that adding observed sensor state later does not require replacing the current model.

---

# 36. Design quality expectations

Prefer:

- immutable value objects;
- narrow interfaces;
- explicit state transitions;
- dependency injection;
- deterministic fakes;
- pure planning logic;
- controlled errors;
- exhaustive typing;
- no hidden global state;
- explicit separation of logical, physical, and controller state.

Avoid:

- hardware calls directly from GUI widgets;
- hardware logic inside `ChessGame`;
- using `python-chess.Board` as the physical board representation;
- chess notation inside low-level controller APIs;
- serial strings embedded throughout application code;
- giant manager classes;
- state represented by unrelated booleans;
- silent failure;
- automatically undoing digital moves after hardware failure;
- optimistically updating physical state before motor completion;
- pretending unsupported special moves work.

Where repository architecture or naming differs from this prompt, adapt the implementation to the existing codebase rather than forcing these exact names.

---

# 37. Final deliverables

At completion, Stage 3.1 should contain:

1. hardware-neutral typed models;
2. explicit `HardwareControllerState`;
3. explicit `PhysicalSynchronization`;
4. first-class `PhysicalBoardState`;
5. minimal physical piece/location representation;
6. `HardwarePort` abstraction;
7. idealized `BoardGeometry`;
8. pure `PhysicalMovePlanner`;
9. `HardwareCoordinator`;
10. deterministic `FakeHardware`;
11. controlled hardware error hierarchy;
12. canonical `MoveExecuted` integration or tested event-consumer seam;
13. transaction-like physical execution semantics;
14. operation trace support;
15. failure injection;
16. explicit partial-failure uncertainty semantics;
17. minimal logical-vs-physical reconciliation;
18. comprehensive tests;
19. README documentation;
20. `AGENT_INCREMENTS.md` Stage 3.1 entry;
21. passing full repository quality suite.

Conclude implementation by reporting:

- files added/changed;
- architectural decisions;
- distinction between `ChessGame`, `PhysicalBoardState`, `HardwareControllerState`, and `PhysicalSynchronization`;
- lifecycle/state models;
- supported machine operation types;
- exact scope of simple-move planning;
- how `MoveExecuted` is integrated;
- how `PhysicalBoardState` is initialized and updated;
- how partial hardware failures affect physical versus digital state;
- how FEN/PGN/new-game replacement affects physical synchronization;
- tests added;
- final test counts;
- deferred work for Stage 3.2.

Do not proceed into Stage 3.2 implementation.