# Stage 2 — Voice Control

## Mission

Implement **Stage 2: Voice Control** for the Wizard Chess Set project.

The project already provides a working digital chess environment from Stage 1 and the Stage 1.1 quality-of-life improvements:

- playable chess game;
- legal move validation;
- terminal interface;
- expanded human-friendly command parsing;
- graphical interface.

Your task is to add **spoken chess commands** as another input mechanism.

The completed application must allow a player to activate a microphone, speak a chess move such as:

```text
e four
knight f three
bishop to c four
queen takes d five
castle kingside
```

and have that command processed through the **same command and game logic used by typed input**.

The central architectural invariant is:

> Voice is another way to submit a chess command. It is not another implementation of chess.

Do not begin later hardware, motor-control, Stockfish, wake-word, or conversational-assistant stages.

---

# 1. Before Editing the Repository

Inspect the repository before making architectural decisions.

Read at minimum:

```text
README.md
AGENTS.md
```

and inspect the existing source tree, tests, configuration, dependency files, terminal entry point, GUI entry point, command parser, and chess/game-state modules.

Determine:

- how the application is currently launched;
- where game state lives;
- where chess legality is enforced;
- how Stage 1.1A command parsing works;
- how terminal commands enter the application;
- how GUI moves enter the application;
- which GUI toolkit is used;
- how dependencies are managed;
- how tests, linting, formatting, and type checking are run.

Reuse existing architecture and naming conventions whenever reasonable.

Do not redesign unrelated parts of the project.

If the current repository differs from assumptions in this document, adapt the implementation to the actual architecture while preserving the requirements and invariants below.

---

# 2. End-State

At the end of Stage 2, all three interaction mechanisms must coexist:

```text
Typed terminal command ─┐
                        │
GUI interaction ────────┼──> shared application command path ──> chess core
                        │
Voice command ──────────┘
```

A typical voice pipeline should resemble:

```text
Microphone
    ↓
Audio capture
    ↓
Speech recognition
    ↓
Raw transcript
    ↓
Speech-specific normalization
    ↓
Existing command parser
    ↓
Existing legality validation
    ↓
Existing move execution
    ↓
Shared game state
    ↓
Terminal / GUI feedback
```

Do not duplicate chess parsing or move legality inside the voice subsystem.

---

# 3. Architectural Requirements

Implement voice support as a modular input adapter.

Prefer responsibilities similar to:

```text
AudioInput
SpeechRecognizer
TranscriptNormalizer
VoiceController
```

Exact names and file locations should follow the repository's conventions.

## 3.1 Audio input

The audio layer is responsible for:

- opening a microphone;
- recording a single utterance;
- returning audio in a recognizer-compatible form;
- ending recording safely;
- reporting audio-device failures;
- closing resources reliably.

It must know nothing about:

- chess rules;
- legal moves;
- notation parsing;
- game state.

---

## 3.2 Speech recognizer

The recognition layer performs:

```text
audio -> transcript
```

It must remain independent of chess logic.

Define an interface or protocol that allows the recognition implementation to be replaced later.

Possible future implementations may include:

- Whisper;
- faster-whisper;
- Vosk;
- operating-system speech APIs;
- cloud speech APIs;
- an embedded recognizer.

The rest of the application must not depend directly on backend-specific APIs.

---

## 3.3 Transcript normalizer

The normalization layer converts speech-recognition output into text that the existing Stage 1.1A command parser can understand.

Examples:

```text
e four
```

becomes:

```text
e4
```

and:

```text
knight f three
```

becomes approximately:

```text
knight f3
```

This layer may also correct common speech-recognition substitutions when the correction is sufficiently deterministic.

Example:

```text
night f three
```

may become:

```text
knight f3
```

The normalizer must **not** become a replacement chess parser.

Its responsibility is speech-specific cleanup only.

---

## 3.4 Voice controller

Create an orchestration layer responsible for the complete voice-input lifecycle:

```text
start recording
→ capture utterance
→ transcribe
→ normalize
→ submit command
→ report result
```

It should expose results in a form usable by both:

- terminal UI;
- graphical UI.

Avoid embedding GUI-specific behavior in the core voice implementation.

---

# 4. Shared Command Entry Point

Voice commands must converge on the existing command-processing path.

Inspect how Stage 1.1A handles text commands and refactor only as much as necessary to establish a common application-level entry point.

Conceptually, all textual command sources should eventually reach something resembling:

```python
submit_command(text)
```

The exact API may differ.

The important requirement is:

```text
typed command
     ↓
shared parser / command processor
     ↓
game logic
```

and:

```text
spoken command
     ↓
transcript normalization
     ↓
same shared parser / command processor
     ↓
same game logic
```

Do not write special-case voice code that directly manipulates the board.

Forbidden architecture:

```python
if transcript == "knight f three":
    board.push(...)
```

Voice input must not contain its own move-execution logic.

---

# 5. Speech Recognition Backend

Use a **local speech-recognition implementation** for the default Stage 2 backend.

Priorities:

1. Linux compatibility;
2. local processing;
3. no paid API requirement;
4. no account requirement;
5. no audio upload by default;
6. acceptable recognition quality for short English chess commands;
7. maintainable Python integration.

A Whisper-family implementation is preferred if compatible with the repository and current Python environment.

Investigate a maintained option such as:

```text
faster-whisper
```

before selecting the backend.

Do not assume that the first candidate is automatically correct. Check compatibility with:

- the project's Python version;
- package-management approach;
- Linux;
- CPU-only development where relevant;
- testability;
- model-loading behavior.

Document the final backend choice and rationale.

---

# 6. Optional Voice Dependencies

Voice recognition introduces platform-sensitive and potentially heavy dependencies.

Keep them isolated from the core chess application where practical.

Missing voice dependencies must **not** prevent the user from:

- importing the chess core;
- running non-voice tests;
- playing through keyboard input;
- using the GUI without voice where possible.

Fail gracefully.

Example:

```text
Voice control is unavailable because optional speech dependencies are not installed.

Install the voice dependencies with:
<repository-specific command>
```

Use the project's actual package-management conventions.

If the repository already supports dependency groups or extras, prefer a voice-specific optional group.

Do not invent an entirely new package-management system.

---

# 7. Voice Interaction Model

Stage 2 uses **explicit single-utterance recording**.

Do not implement continuous passive listening.

Do not implement a wake word.

Preferred lifecycle:

```text
user activates voice input
↓
application starts recording
↓
user speaks one command
↓
recording ends
↓
application processes speech
↓
result is shown
↓
application returns to idle
```

The application must never remain listening indefinitely.

---

# 8. Terminal Voice UX

Add voice invocation to the terminal interface without replacing typed commands.

Prefer a command such as:

```text
voice
```

unless repository conventions suggest a better name.

Expected interaction:

```text
White> voice
Listening...
Processing...
Heard: "e four"
Played: e4

Black>
```

Another command may immediately be typed normally:

```text
Black> e5
```

and the next one may again be spoken.

Voice and keyboard input must remain interchangeable.

For a failed transcription:

```text
White> voice
Listening...
Processing...
Could not understand speech.
Please try again.

White>
```

For a recognized but invalid command:

```text
White> voice
Listening...
Processing...
Heard: "knight before"
Command not understood.

White>
```

For a recognized but illegal move:

```text
White> voice
Listening...
Processing...
Heard: "bishop c4"
Illegal move: <existing application error>

White>
```

Reuse existing application error messages where appropriate.

---

# 9. GUI Voice UX

Extend the Stage 1.1B GUI with voice input.

Add an obvious microphone control, such as:

```text
Speak Move
```

or a microphone button with an accessible text label.

At minimum expose these states:

```text
Idle
Listening
Processing
Success
Error
```

The user should be able to tell whether the microphone is active.

Show the recognized transcript.

Example:

```text
Listening...
```

then:

```text
Heard: "knight f three"
Played: Nf3
```

For failure:

```text
Heard: "knight before"
Command not understood.
```

Do not obscure the board unnecessarily.

Preserve the existing GUI's visual language rather than redesigning the whole interface.

---

# 10. GUI Responsiveness

Audio capture, model initialization, and speech transcription may block for noticeable periods.

Do not perform long-running recognition work directly on the GUI event thread.

Use the concurrency mechanism appropriate to the existing GUI toolkit.

Possible approaches include:

- worker thread;
- toolkit task abstraction;
- background executor.

Keep the design simple.

Do not convert the entire application to a new asynchronous architecture solely to support Stage 2.

UI mutation must occur through the thread/event mechanism required by the GUI framework.

Prevent simultaneous recordings.

If the user attempts to activate voice while voice capture or processing is already active, either:

- ignore the duplicate activation safely; or
- display a short "already listening/processing" state.

Do not start overlapping recognizer operations.

---

# 11. Audio Capture

Select a maintained Linux-compatible audio-capture solution consistent with the project's dependency constraints.

Requirements:

- default to the system's default microphone;
- open the device only when needed;
- release it reliably;
- expose controlled errors;
- support test doubles/mocking;
- avoid binding game logic to audio-library objects.

If practical without significant complexity, allow microphone-device configuration.

Do not require microphone configuration for normal use.

---

# 12. Recording Termination

A spoken command must have a finite recording period.

Implement a dependable stopping strategy.

Possible approaches:

- silence detection;
- voice activity detection;
- press-and-hold;
- explicit stop;
- bounded recording followed by silence handling.

Prefer automatic single-utterance behavior if practical.

Regardless of implementation:

- use a hard maximum recording duration;
- never listen forever;
- stop cleanly after normal short commands;
- close streams after completion;
- handle silent recordings without crashing.

Avoid overengineering sophisticated audio analysis at this stage.

---

# 13. Transcript Normalization

Create a deterministic chess-speech normalization layer.

Support spoken coordinates and piece commands including at least:

```text
e four
e five
knight f three
bishop c four
rook e one
queen h five
king g one
bishop to b five
queen takes d five
rook takes e eight
castle kingside
castle queenside
check
checkmate
promote to queen
```

Normalize coordinates such as:

```text
a one -> a1
b two -> b2
c three -> c3
d four -> d4
e five -> e5
f six -> f6
g seven -> g7
h eight -> h8
```

Account for common recognition substitutions when doing so is safe.

Candidate corrections include:

```text
night -> knight
bee -> b
see -> c
dee -> d
gee -> g
for -> four
ate -> eight
```

Do not blindly replace words globally if doing so can corrupt valid phrases.

Context-sensitive normalization is acceptable.

All non-trivial rules must have automated tests.

---

# 14. Avoid a Second Chess Parser

The transcript normalizer must not attempt to independently solve arbitrary chess language.

For example, Stage 2 should not need an algorithm that derives complete SAN from arbitrary English speech.

Normalize the transcript enough for the already-existing command parser to handle it.

Preferred:

```text
"knight f three"
↓
"knight f3"
↓
existing Stage 1.1A parser
↓
Nf3
```

Avoid:

```text
"knight f three"
↓
voice subsystem independently finds legal knight
↓
voice subsystem executes Nf3
```

Chess meaning remains the responsibility of the command parser and chess core.

---

# 15. Spoken Move Forms

Preserve forms already supported by Stage 1.1A after normalization.

Examples that should work when compatible with the existing parser:

```text
e four
pawn e four
pawn to e four
knight f three
knight to f three
bishop c four
bishop to c four
queen h five
queen takes d five
rook takes e eight check
castle kingside
castle queenside
promote to queen
```

Do not unnecessarily extend the Stage 1.1A grammar solely because speech recognition exists.

If normalization exposes a small obvious parser gap that materially blocks standard spoken chess commands, implement the narrowest coherent parser improvement and cover it with tests.

---

# 16. Source and Destination Squares

If Stage 1.1A already supports coordinate/source-destination commands, spoken forms should normalize into them.

For example:

```text
e two e four
```

should become something equivalent to:

```text
e2 e4
```

if this syntax is accepted by the current parser.

Likewise:

```text
knight g one f three
```

may normalize toward the existing source-destination notation if supported.

Do not create a new notation format unnecessarily.

---

# 17. Legality

Voice input must never bypass legality validation.

A perfectly recognized spoken move may still be illegal.

Example:

```text
Heard: "bishop c4"
```

If the current position does not permit that move, route it through the same legality handling as keyboard input.

Voice must not modify the game state unless the shared application command path accepts the command.

Never execute a move merely because the transcript resembles a legal-looking chess phrase.

---

# 18. Ambiguous Speech

Do not guess when speech or parsing is ambiguous.

A false positive will eventually translate into incorrect physical movement in later hardware stages.

Therefore:

```text
failure to execute
```

is safer than:

```text
executing an uncertain move
```

If recognition produces uncertain or unusable text, report it and ask the player to repeat the move.

Example:

```text
Heard: "night before"
Command not understood.
Please try again.
```

Do not arbitrarily select a legal move that seems closest.

---

# 19. Recognition Result

Use a small structured result model rather than passing loose tuples.

A suitable conceptual model is:

```python
@dataclass
class RecognitionResult:
    transcript: str
    normalized_text: str
    confidence: float | None = None
```

Additional fields may be added if useful, for example:

```text
duration
backend
language
```

Do not overengineer the model.

The application should preserve both:

- raw recognizer transcript;
- normalized command text.

This distinction is important for diagnostics.

---

# 20. Confidence

If the selected recognition backend provides useful confidence-related information, preserve it.

Do not assume that every backend exposes a reliable single confidence value.

Do not build core application behavior around a backend-specific confidence metric unless strongly justified.

Parser success and command unambiguity remain the main safety gate.

---

# 21. Model Initialization

Do not reload a speech model for every spoken command.

Use an appropriate lifecycle such as lazy initialization.

Preferred behavior:

```text
application starts normally
↓
no speech model loaded
↓
user invokes voice for first time
↓
recognizer/model initializes
↓
same instance is reused for later utterances
```

This avoids penalizing users who do not use voice control.

Handle model-loading failure gracefully.

Example:

```text
Voice recognition could not be initialized.
Keyboard input remains available.
```

---

# 22. Configuration

Add only configuration justified by Stage 2.

Potential settings include:

```text
recognition backend
speech model
language
microphone device
maximum recording duration
silence duration
silence threshold
```

Defaults should work without configuration on a typical development machine.

Default language:

```text
English
```

Do not build a large generic settings framework unless one already exists.

Use existing configuration conventions when available.

---

# 23. Error Model

Create clear failure boundaries between stages of the pipeline.

The application should distinguish, where practical:

```text
audio-device failure
recording failure
recognizer initialization failure
speech recognition failure
empty transcript
normalization failure
command parsing failure
illegal move
```

Voice-specific failures should be represented cleanly rather than leaking low-level library exceptions into UI code.

Use project conventions for custom exceptions or result types.

---

# 24. Required Failure Handling

Handle at least these cases without crashing the game:

```text
no microphone detected
microphone cannot be opened
microphone permissions unavailable
recording fails
silence / empty recording
speech recognizer unavailable
speech model unavailable
model initialization fails
transcription raises an exception
empty transcript returned
transcript cannot be normalized
normalized text cannot be parsed
parsed move is illegal
voice command invoked while another is active
```

Whenever possible, keep typed and GUI interaction available after a voice failure.

Example:

```text
Voice input unavailable: no microphone device could be opened.
Keyboard input remains available.
```

---

# 25. Logging

Add diagnostic logging around the voice pipeline.

Useful events include:

```text
voice recording started
voice recording stopped
recording duration
speech recognizer initialization started
speech recognizer initialized
raw transcript
normalized transcript
recognition failure
audio-device failure
model initialization failure
```

Use the repository's existing logging system.

Do not:

- dump raw audio;
- log large binary objects;
- expose enormous third-party model logs by default;
- add noisy debug output to ordinary UI behavior.

---

# 26. Privacy

Local processing is the default requirement.

Do not silently send microphone audio to external services.

Do not add a cloud API as the default recognizer.

Do not require:

- an account;
- API keys;
- network connectivity;
- a paid speech service.

Avoid retaining recorded audio.

If temporary files are technically necessary:

- use secure temporary-file handling;
- delete them reliably;
- document the behavior.

Prefer in-memory audio processing where practical.

---

# 27. Dependency Boundaries

Maintain approximately these dependency directions:

```text
Chess Core
↑
Application / Game Controller
↑
Command Processor
↑
Input adapters
```

Voice-specific dependencies should remain near the voice subsystem.

In particular:

```text
Chess engine
    must not import
speech-recognition code
```

```text
Command parser
    must not import
microphone code
```

```text
Speech recognizer
    must not import
game-state code
```

```text
Audio capture
    must not know
whose turn it is
```

If the existing repository already has an application/controller layer, integrate there instead of inventing another competing abstraction.

---

# 28. Testing Requirements

Automated tests must not require:

- a real microphone;
- ALSA/PulseAudio/PipeWire availability;
- downloaded speech models;
- network access;
- speakers;
- audio hardware.

Design the voice components to support dependency injection or fakes.

---

# 29. Transcript Normalization Tests

Add comprehensive unit tests for speech normalization.

Cover at minimum examples similar to:

```text
"e four"              -> "e4"
"e five"              -> "e5"
"knight f three"      -> parser-compatible "knight f3"
"night f three"       -> parser-compatible "knight f3"
"bishop c four"       -> parser-compatible "bishop c4"
"bishop to c four"    -> parser-compatible "bishop to c4"
"queen h five"        -> parser-compatible "queen h5"
"castle kingside"     -> parser-compatible castling command
"castle queenside"    -> parser-compatible castling command
```

Add tests for:

- capitalization;
- extra whitespace;
- punctuation returned by recognizers;
- supported number homophones;
- supported file-letter homophones;
- commands that should remain unchanged;
- inputs that must not be aggressively rewritten.

---

# 30. Voice Controller Tests

Use fake implementations of audio and recognition layers.

Test the orchestration:

```text
fake audio
↓
fake recognizer transcript
↓
normalizer
↓
shared command submission
```

Verify:

- successful command submission;
- raw transcript preservation;
- normalized transcript preservation;
- correct success result;
- command parser receives normalized text.

Do not require actual inference.

---

# 31. Voice Failure Tests

Simulate at minimum:

```text
microphone unavailable
recording exception
recognizer initialization exception
recognizer exception
empty transcript
unsupported transcript
```

Verify that:

- errors are controlled;
- game state remains unchanged;
- application remains usable;
- raw third-party exceptions do not unexpectedly crash UI code.

---

# 32. Illegal Move Test

Simulate a voice recognizer that returns a perfectly valid transcript representing an illegal move in the current board position.

Verify that:

```text
voice input
↓
normalization succeeds
↓
parsing succeeds
↓
existing legality validation rejects move
↓
board does not change
```

This test demonstrates that voice input does not bypass the chess core.

---

# 33. Optional Dependency Test

Where practical, verify that missing voice dependencies do not break non-voice functionality.

At minimum ensure that importing and testing core modules does not eagerly require the speech backend.

Use lazy imports or isolated backend modules where useful.

---

# 34. GUI Integration Tests

Use the GUI testing strategy already present in the repository.

Where feasible, test:

- microphone control triggers the voice controller;
- GUI enters listening state;
- GUI enters processing state;
- transcript is displayed;
- successful command updates shared board state;
- failure is displayed without crashing;
- duplicate activation is prevented;
- background recognition does not directly mutate UI state from an invalid thread.

Do not introduce brittle pixel-level tests.

---

# 35. Speech Command Corpus

Create a small reusable corpus of representative voice phrases.

Include examples such as:

```text
e four
e five
pawn to e four
knight f three
night f three
knight c six
bishop c four
bishop to b five
queen h five
queen takes d five
rook takes e eight check
castle kingside
castle queenside
promote to queen
```

Store expected normalized/parser-compatible forms.

Use this corpus where practical for normalization tests and future backend evaluation.

Do not build a large language dataset during this stage.

---

# 36. Manual Acceptance Test

Automated tests cannot establish whether a real microphone works satisfactorily.

Document a manual Stage 2 acceptance procedure.

At minimum test the following opening by voice:

```text
1. e4 e5
2. Nf3 Nc6
3. Bc4
```

Spoken approximately as:

```text
e four
e five
knight f three
knight c six
bishop c four
```

Confirm after each move that:

- transcript is visible;
- command is interpreted correctly;
- board state is updated correctly;
- turn changes correctly.

Also establish a legal castling position and test:

```text
castle kingside
```

Test these failure cases:

```text
illegal spoken move
unclear speech
silence
no usable microphone
```

Document expected behavior.

---

# 37. Backward Compatibility

Do not regress earlier stages.

Before declaring Stage 2 complete, verify that the following still work:

- typed terminal moves;
- Stage 1.1A shorthand commands;
- existing non-move terminal commands;
- GUI move entry;
- board rendering;
- turn handling;
- illegal-move rejection;
- check;
- checkmate;
- stalemate/draw handling already implemented;
- game reset/restart behavior already implemented;
- quit behavior;
- existing tests.

Voice support is additive.

---

# 38. Out of Scope — Wake Word

Do not implement:

```text
"Wizard..."
"Chessboard..."
"Hey board..."
```

or any permanent ambient listening mechanism.

Stage 2 recording must be explicitly initiated by the user.

---

# 39. Out of Scope — Speech Synthesis

Do not make the application speak responses aloud.

No text-to-speech system is required during Stage 2.

Visual/terminal feedback is sufficient.

---

# 40. Out of Scope — Speaker Identification

Do not identify players from their voices.

Do not train speaker profiles.

The current player remains determined entirely by chess game state.

---

# 41. Out of Scope — Conversational Chess Assistant

Do not attempt to understand arbitrary questions such as:

```text
What should I play?
Can I castle?
Which knight should move?
Move the piece attacking his queen.
What's the best move?
```

Stage 2 supports spoken chess commands, not free-form chess conversation.

---

# 42. Out of Scope — Stockfish

Do not add:

- engine evaluation;
- suggested moves;
- analysis bars;
- Stockfish;
- hints.

Those features belong to future stages.

---

# 43. Out of Scope — Hardware Movement

Do not implement:

- motors;
- gantry control;
- electromagnets;
- physical board coordinates;
- motion planning;
- piece detection;
- GPIO;
- microcontroller communication.

Stage 2 ends once the spoken command has successfully updated the digital chess game.

---

# 44. Out of Scope — Cloud Infrastructure

Do not introduce:

- backend servers;
- user accounts;
- authentication;
- hosted databases;
- cloud audio storage;
- external control services.

The Stage 2 prototype should remain a local application.

---

# 45. Out of Scope — General Noise Robustness

Do not attempt to solve speech recognition in arbitrary noisy environments.

The acceptance target is reasonable close-range English speech in ordinary development conditions.

Architecture should allow future improvement, but Stage 2 should favor a dependable prototype over advanced DSP.

---

# 46. Documentation

Update `README.md` and any relevant developer documentation.

Document:

1. Stage 2 voice capabilities;
2. speech backend selected;
3. installation command;
4. optional voice dependencies;
5. any Linux system audio dependencies;
6. microphone requirements;
7. terminal voice command;
8. GUI microphone control;
9. model selection/default;
10. first-use model behavior if relevant;
11. offline/local processing behavior;
12. microphone-device configuration if supported;
13. troubleshooting;
14. current limitations.

Use exact commands matching the repository.

Do not provide speculative commands.

---

# 47. Linux Considerations

Stage 2's primary development target is Linux.

When selecting audio dependencies, account for likely Linux audio environments such as:

```text
ALSA
PulseAudio
PipeWire
```

Do not hard-code the application to one developer's device name.

Use the audio library's default-device mechanism where possible.

If native system packages are required, document them clearly rather than attempting fragile automatic installation.

---

# 48. Code Quality

Follow the repository's existing:

- formatting;
- lint rules;
- naming conventions;
- typing style;
- module layout;
- testing style.

Prefer:

- small modules;
- explicit dependencies;
- testable interfaces;
- simple state management;
- clear error handling.

Avoid:

- global mutable voice state;
- duplicated command parsing;
- backend-specific logic leaking across the application;
- large unrelated refactors;
- premature abstraction;
- speculative infrastructure.

---

# 49. Implementation Sequence

Implement Stage 2 incrementally.

## Stage 2.1 — Inspect and establish integration point

Identify the existing shared path through which text commands should enter the application.

Refactor minimally if terminal and GUI currently duplicate command submission.

Verify existing behavior before adding voice.

---

## Stage 2.2 — Voice domain interfaces

Create abstractions for:

- audio capture;
- speech recognition;
- recognition result;
- voice orchestration;
- voice errors.

Keep them independent of concrete ML/audio libraries.

Add tests with fakes.

---

## Stage 2.3 — Transcript normalization

Implement deterministic speech normalization.

Add comprehensive unit tests before integrating a microphone.

Ensure output is compatible with Stage 1.1A.

---

## Stage 2.4 — Recognition backend

Integrate the selected local recognition backend behind the recognizer abstraction.

Implement reusable/lazy model loading.

Ensure non-voice imports remain functional without the optional backend installed.

---

## Stage 2.5 — Audio capture

Implement single-utterance microphone recording.

Add:

- maximum duration;
- safe resource cleanup;
- controlled failure handling.

Keep hardware code isolated.

---

## Stage 2.6 — End-to-end voice controller

Connect:

```text
audio
→ recognizer
→ transcript
→ normalization
→ shared command processor
```

Test using fakes first.

Then manually validate using a real microphone.

---

## Stage 2.7 — Terminal integration

Add explicit voice invocation to the terminal REPL.

Preserve all existing typed commands.

Display:

- listening state;
- processing state;
- transcript;
- result/error.

---

## Stage 2.8 — GUI integration

Add microphone controls and status feedback.

Move blocking work away from the GUI event thread.

Ensure board/game state remains synchronized with typed and GUI input.

---

## Stage 2.9 — Hardening

Handle:

- dependency absence;
- microphone absence;
- audio errors;
- recognition errors;
- empty transcripts;
- concurrency;
- model-load errors;
- application shutdown during voice operations.

Add relevant logging.

---

## Stage 2.10 — Documentation and acceptance

Update documentation.

Run the full automated suite.

Perform the manual microphone acceptance sequence.

Review the diff for accidental unrelated changes.

---

# 50. Definition of Done

Stage 2 is complete only when all of the following are true:

- [ ] The application can capture a spoken chess command from a Linux microphone.
- [ ] Voice recording is explicitly initiated by the player.
- [ ] The application does not continuously listen.
- [ ] Audio capture is isolated behind a testable abstraction.
- [ ] Speech recognition is isolated behind a replaceable abstraction.
- [ ] Local speech recognition is the default implementation.
- [ ] Voice usage does not require a paid API.
- [ ] Voice usage does not upload audio by default.
- [ ] Speech-model initialization is reused rather than repeated for each move.
- [ ] Model loading does not unnecessarily delay normal non-voice startup.
- [ ] Raw transcripts are preserved.
- [ ] Spoken chess coordinates are normalized correctly.
- [ ] Common chess piece names are supported.
- [ ] Common capture terminology is supported.
- [ ] Kingside castling can be spoken.
- [ ] Queenside castling can be spoken.
- [ ] Promotion speech supported by the existing parser can be normalized appropriately.
- [ ] Voice commands use the existing Stage 1.1A parser.
- [ ] Voice commands use the existing legality validation.
- [ ] Voice commands use the existing move-execution path.
- [ ] Legal voice moves modify the exact same shared game state as typed moves.
- [ ] Illegal voice moves do not modify game state.
- [ ] Ambiguous recognition does not cause guessed moves.
- [ ] Terminal voice input works.
- [ ] Typed terminal input still works.
- [ ] GUI voice input works.
- [ ] Existing GUI interaction still works.
- [ ] GUI clearly indicates listening state.
- [ ] GUI clearly indicates processing state.
- [ ] GUI displays recognized speech.
- [ ] GUI displays voice errors.
- [ ] GUI remains responsive during recognition.
- [ ] Concurrent voice captures are prevented.
- [ ] Missing microphone hardware is handled gracefully.
- [ ] Recording errors are handled gracefully.
- [ ] Recognition errors are handled gracefully.
- [ ] Empty transcripts are handled gracefully.
- [ ] Missing optional voice dependencies do not break the chess core.
- [ ] Automated tests do not require microphone hardware.
- [ ] Automated tests do not require downloaded ML models.
- [ ] Transcript normalization has dedicated unit tests.
- [ ] Voice orchestration has fake-backed tests.
- [ ] Illegal spoken move handling is tested.
- [ ] Existing Stage 1 and Stage 1.1 tests still pass.
- [ ] README documentation is updated.
- [ ] A manual real-microphone acceptance procedure is documented.
- [ ] A real-microphone acceptance test has been performed where the environment permits it.

If the execution environment does not expose a real microphone, do not fabricate acceptance results. State clearly that automated integration is complete but physical microphone validation remains an external manual step.

---

# 51. Representative Acceptance Scenario

The following scenario defines expected Stage 2 behavior.

Launch the GUI.

Initial state:

```text
White to move
```

Activate voice input.

The application displays:

```text
Listening...
```

Say:

```text
e four
```

The application processes the recording and shows approximately:

```text
Heard: "e four"
Played: e4
```

The board now contains the white pawn on `e4`.

Black activates voice input and says:

```text
e five
```

The application shows:

```text
Heard: "e five"
Played: e5
```

White says:

```text
knight f three
```

The application performs conceptually:

```text
audio
↓
"knight f three"
↓
"knight f3"
↓
existing Stage 1.1A parser
↓
Nf3
↓
existing legality validator
↓
existing move executor
```

The knight appears on `f3`.

Black may then type a move manually.

White may then use the GUI directly.

All inputs must continue the **same game**, with one authoritative board state.

---

# 52. Commands and Validation

Before finishing, run all repository-provided quality checks.

Discover the actual commands from the repository rather than guessing.

Run as applicable:

```text
tests
formatter
lint
type checker
other repository validation
```

Fix failures introduced by Stage 2.

Do not silently ignore failing existing tests.

If an existing unrelated test is already broken before your changes, verify and document that fact rather than modifying unrelated behavior merely to force a green suite.

---

# 53. Diff Review

Before completion, inspect the final diff.

Remove:

- debug prints;
- temporary files;
- experimental code;
- dead abstractions;
- commented-out implementations;
- accidental generated artifacts;
- unrelated formatting changes;
- unnecessary dependency additions.

Ensure every new dependency has a clear Stage 2 purpose.

---

# 54. README Update

The README should make it possible for another developer to clone the repository and determine:

```text
how to install normal dependencies
how to install voice dependencies
how to start the terminal application
how to start the GUI
how to invoke voice control
what model/backend is used
whether speech remains local
what happens on first model use
how to troubleshoot microphone problems
```

Keep setup instructions synchronized with actual implementation.

---

# 55. Final Codex Report

When the implementation is complete, return a concise implementation report containing:

## Architecture

State:

- voice modules added;
- recognition backend chosen;
- how the shared command pipeline works.

## User experience

State:

- terminal invocation;
- GUI invocation;
- visible status behavior.

## Normalization

Summarize supported speech transformations and important ambiguity safeguards.

## Testing

Report:

- tests added;
- full test-suite result;
- lint/format/type-check results where applicable.

## Manual validation

Report whether real microphone testing was actually possible.

Do not claim physical microphone validation if the execution environment did not provide working audio hardware.

## Files changed

List the principal files created or modified.

## Limitations

State remaining known Stage 2 limitations.

## Next stage

Briefly identify the logical next project stage without implementing it.

---

# 56. Working Rules for Codex

Work autonomously from the repository.

Do not stop to request approval for ordinary implementation decisions that can be resolved from:

- existing architecture;
- repository conventions;
- this specification;
- tests.

Prefer the smallest coherent implementation satisfying this stage.

Do not perform speculative work for later stages.

Do not rewrite major subsystems merely because another design might be cleaner.

Preserve existing public behavior unless Stage 2 explicitly requires a change.

When uncertain between:

```text
clever / broad / speculative
```

and:

```text
simple / explicit / testable
```

choose the latter.

When uncertain whether a voice transcript should trigger a move, choose the safer behavior:

```text
reject and ask for repetition
```

rather than:

```text
guess and execute
```

The final Stage 2 architecture must preserve this invariant:

> Microphone input produces text. Existing application logic decides what that text means and whether it is legal.