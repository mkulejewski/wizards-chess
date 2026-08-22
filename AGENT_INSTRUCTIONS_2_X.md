# AGENT_INSTRUCTION — Stage 2.x Software Expansion

## Objective

Extend the completed Stage 2 voice-controlled chess application into a substantially more capable software platform before physical-board integration begins.

Implement the following increments:

- **Stage 2.1 — Stockfish integration**
- **Stage 2.2 — Full game/application features**
- **Stage 2.3 — Advanced voice UX and contextual interpretation**
- **Stage 2.4 — Game analysis**
- **Stage 2.5 — Software hardening and developer tooling**
- **Stage 2.6 — Polish-language voice support**

The finished application should remain suitable for later connection to Stage 3 physical-motion and hardware abstractions.

Do **not** couple any new functionality directly to future hardware.

---

# 1. General implementation principles

Before changing code:

1. Read:
   - `README.md`
   - `AGENTS.md`
   - existing Stage 1 / Stage 1.1 / Stage 2 implementation
   - existing tests
   - existing configuration files

2. Identify the current architecture and preserve established conventions unless there is a strong technical reason to refactor.

3. Prefer incremental refactoring over rewriting working functionality.

4. Maintain a strict separation between:
   - chess rules/state,
   - GUI,
   - voice transcription,
   - voice-command parsing,
   - engine analysis,
   - persistence,
   - application configuration,
   - future hardware integration.

5. `python-chess` or the project's existing chess-state layer must remain the authoritative source for:
   - legal moves,
   - position state,
   - check/checkmate,
   - draw conditions,
   - SAN/UCI conversion.

6. Never duplicate chess legality logic in:
   - voice parsers,
   - GUI,
   - Stockfish integration,
   - analysis code.

7. New subsystems must expose clean interfaces and be independently testable.

8. Do not introduce network dependencies for core gameplay.

9. The application should remain usable without Stockfish installed. Engine-dependent features must fail gracefully and clearly.

10. English behavior implemented during Stage 2 must continue working unless explicitly superseded by this specification.

---

# 2. Target architecture

The application should evolve toward approximately the following dependency structure:

```text
                           ┌───────────────────┐
                           │ Application / GUI │
                           └─────────┬─────────┘
                                     │
                              GameController
                                     │
          ┌──────────────────────────┼─────────────────────────┐
          │                          │                         │
          ▼                          ▼                         ▼
   Game / Chess State          Voice System              EngineService
          │                          │                         │
          │                   Speech Recognizer               │
          │                          │                         │
          │                   Language Parser                 │
          │                          │                         │
          │                    MoveIntent                     │
          │                          │                         │
          └─────────────── Legality Resolver ─────────────────┘
                                     │
                                     ▼
                                Move execution

Additional services:

GamePersistenceService
AnalysisService
ConfigurationService
Logging / Diagnostics
```

The exact class/module names may differ if the repository already establishes a naming convention.

The architectural requirement is separation of responsibilities, not literal adherence to these names.

---

# 3. Stage 2.1 — Stockfish integration

## 3.1 Goal

Integrate Stockfish through the UCI protocol without exposing UCI-specific implementation details throughout the application.

Introduce an engine abstraction such as:

```python
class ChessEngine:
    def analyse_position(...): ...
    def get_best_move(...): ...
    def get_top_moves(...): ...
    def play_move(...): ...
```

Use an implementation such as:

```python
class StockfishEngine(ChessEngine):
    ...
```

Prefer the engine facilities already provided by `python-chess` unless the current project architecture gives a compelling reason not to.

---

## 3.2 Engine configuration

Support configurable engine settings including at minimum:

- executable path;
- analysis enabled/disabled;
- analysis time and/or depth;
- number of principal variations;
- engine opponent strength where supported;
- engine thread count where appropriate;
- hash size where appropriate.

Do not hard-code a platform-specific Stockfish path.

Configuration may come from the project's existing settings mechanism or a newly introduced configuration layer.

Example conceptual configuration:

```yaml
engine:
  enabled: true
  type: stockfish
  path: /usr/bin/stockfish
  analysis_time_ms: 500
  multipv: 3
```

Do not require YAML specifically if another format is already used.

---

## 3.3 Position evaluation

Expose normalized engine analysis to the rest of the program.

Do not make GUI components interpret raw UCI output.

A normalized result should contain information conceptually equivalent to:

```python
EngineEvaluation(
    score_cp=84,
    mate_in=None,
    perspective="white",
)
```

and:

```python
EngineLine(
    move=...,
    score=...,
    principal_variation=[...],
)
```

Correctly handle:

- centipawn evaluations;
- mate scores;
- white/black perspective;
- terminal positions;
- unavailable engine;
- engine crashes;
- analysis cancellation.

Choose one documented score convention and use it consistently throughout the application.

Prefer evaluations normalized from **White's perspective** for presentation and historical comparison unless the existing architecture strongly favors another convention.

---

## 3.4 Best moves and MultiPV

Implement:

- best move;
- configurable top-N candidate moves;
- principal variation for each candidate where available.

The API should support operations conceptually similar to:

```python
engine.get_best_move(board)
engine.get_top_moves(board, count=3)
engine.analyse_position(board)
```

Never mutate the live game board while analysing it.

Use board copies where necessary.

---

## 3.5 GUI integration

Where the existing GUI architecture permits, add an engine-analysis area containing useful information such as:

```text
Evaluation: +0.84

1. Nf3   +0.84
2. d4    +0.61
3. Bc4   +0.44

PV:
Nf3 Nc6 Bb5 a6
```

Do not allow engine analysis to freeze the UI.

Long-running engine work must occur asynchronously relative to the GUI event loop.

When a new move is played:

1. cancel or ignore stale analysis;
2. analyse the new position;
3. update the GUI only if the result still corresponds to the current position.

Avoid race conditions where analysis for an old position overwrites current data.

---

## 3.6 Evaluation bar

If practical in the existing GUI, implement an evaluation bar.

It must:

- represent the normalized engine evaluation;
- handle mate scores;
- remain stable for very large centipawn values;
- update after moves;
- clearly indicate which side has the advantage.

The evaluation model must not be GUI-specific because Stage 9 may later render the same value through physical LEDs.

Use an abstraction similar to:

```text
Stockfish
   ↓
Evaluation model
   ├── GUI evaluation bar
   └── future physical LED renderer
```

---

## 3.7 Engine opponent

Add support for human-vs-engine play.

The engine should be usable as either:

- White;
- Black.

The application flow should support:

```text
Human move
   ↓
validate
   ↓
apply
   ↓
detect terminal state
   ↓
request engine reply
   ↓
apply engine move
   ↓
detect terminal state
```

Engine calculations must not freeze the GUI.

Provide configurable strength.

Prefer a user-friendly abstraction such as:

```text
Beginner
Casual
Club
Strong Club
Expert
Master
Maximum
```

Internally map these levels to supported Stockfish/UCI parameters.

Do not promise exact Elo equivalence unless the underlying engine configuration supports it reliably.

---

## 3.8 Engine lifecycle

Ensure proper handling of:

- startup;
- process ownership;
- shutdown;
- application exit;
- unexpected engine termination;
- invalid executable;
- configuration changes.

No zombie Stockfish processes should remain after normal application termination.

---

# 4. Stage 2.2 — Full chess application features

## 4.1 Goal

Evolve the application from a voice-driven chess demonstrator into a complete local chess application.

---

## 4.2 PGN support

Implement:

- PGN export;
- PGN import;
- preservation of game metadata;
- preservation of move history.

Support metadata such as:

```text
Event
Site
Date
Round
White
Black
Result
```

where applicable.

Do not invent metadata that is unknown.

---

## 4.3 Automatic game saving

Implement automatic persistence of games.

A game should be recoverable after:

- normal application exit;
- accidental closure;
- unexpected interruption where feasible.

Do not silently overwrite unrelated saved games.

Use clear save identifiers or timestamps.

---

## 4.4 FEN support

Implement:

- loading a game position from FEN;
- copying/exporting current FEN;
- validation of supplied FEN.

Invalid FEN must produce a user-visible error rather than corrupting application state.

---

## 4.5 Move history

Maintain a canonical move history.

The GUI should support inspecting previous moves/positions without altering the authoritative live game unless the user explicitly chooses an operation such as undo.

Prefer separating:

```text
live game state
```

from:

```text
currently viewed historical position
```

so clicking an old move does not accidentally rewrite the game.

---

## 4.6 Undo and redo

Implement safe undo/redo.

Undo must correctly restore:

- board position;
- side to move;
- castling rights;
- en passant status;
- move counters;
- relevant engine-analysis state;
- game termination state.

Redo should restore the undone move when possible.

When future physical-board integration exists, undo will eventually require physical reversal. Therefore keep undo semantics in the game/application layer rather than embedding them in GUI controls.

---

## 4.7 New game / restart

Support:

- new standard game;
- restart;
- abandoning current game;
- clearing analysis state;
- clearing stale voice state;
- resetting clocks where enabled.

Avoid accidental game loss where practical.

---

## 4.8 Game termination commands

Support proper application-level handling of:

- checkmate;
- stalemate;
- automatic draw conditions handled by the chess library;
- resignation;
- agreed draw where supported.

Commands such as:

```text
resign
draw
new game
```

must be modeled as application commands rather than fake chess moves.

---

## 4.9 Chess clocks

Add optional chess clocks.

Support at minimum:

- clocks disabled;
- fixed initial time;
- optional increment if practical.

Clock operations should support:

```text
start
pause
switch active player
reset
```

Clock timing must not depend on GUI frame rate.

Use a monotonic time source.

The game controller should own clock semantics; the GUI should render them.

---

## 4.10 Player settings

Support configuration of:

- White player name;
- Black player name;
- human/engine status;
- engine level;
- voice language.

Persist appropriate preferences between sessions.

---

# 5. Stage 2.3 — Advanced voice UX

## 5.1 Goal

Move from basic speech-to-command matching toward robust chess-specific interpretation.

The voice system must explicitly separate:

```text
audio
  ↓
speech recognition
  ↓
transcription
  ↓
language-specific parsing
  ↓
MoveIntent / ApplicationIntent
  ↓
position-aware resolution
  ↓
validated action
```

---

## 5.2 Intent model

Introduce language-independent intent representations.

For chess moves, use a model conceptually similar to:

```python
MoveIntent(
    piece=None,
    origin=None,
    destination="e4",
    capture=None,
    promotion=None,
    castle=None,
    check_claim=None,
)
```

The exact fields may differ.

For application-level commands use something like:

```python
ApplicationIntent(
    command="new_game",
)
```

Possible commands include:

- new game;
- undo;
- redo;
- resign;
- draw;
- save;
- repeat;
- enable/disable analysis;
- possibly help.

Parsers must output intents, not manipulate game state directly.

---

## 5.3 Position-aware move resolution

Resolve spoken move intents against the current set of legal moves.

Example:

```text
spoken:
"knight f3"

parsed:
piece = knight
destination = f3

legal moves:
Ng1-f3
...

resolved:
g1f3
```

Use current legal moves as a constraint.

This allows recovery from incomplete notation.

---

## 5.4 Ambiguity detection

Do not guess when multiple legal moves satisfy the same intent.

Example:

```text
"rook e1"
```

may be ambiguous if two rooks can legally move to e1.

Return an explicit ambiguity result.

The UI/voice layer should request clarification.

Examples:

```text
"Which rook?"
```

or equivalent localized feedback.

Do not arbitrarily choose the first legal candidate.

---

## 5.5 Recognition confidence and error handling

Where the speech-recognition backend exposes confidence or candidate information, preserve it.

Distinguish between:

- transcription failure;
- unrecognized command;
- syntactically valid but illegal move;
- ambiguous move;
- successfully resolved move.

These should not collapse into one generic failure.

---

## 5.6 Confirmation strategy

Implement a configurable confirmation policy.

Suggested modes:

```text
off
ambiguous_or_low_confidence
always
```

In normal play, a high-confidence, uniquely legal move should be executable without unnecessary confirmation.

Low-confidence or ambiguous input should require clarification.

---

## 5.7 Voice command variants

English parsing should recognize common variations such as:

```text
e4
e four
pawn e4
pawn to e4

knight f3
knight to f3

bishop takes f7
bishop captures f7

castle kingside
short castle

castle queenside
long castle
```

Support equivalent reasonable variants already established during Stage 2.

Do not attempt unrestricted natural-language understanding. Prefer a deterministic domain grammar supplemented by chess legality.

---

## 5.8 Spoken feedback

Where speech output exists or is practical within Stage 2 architecture, structure responses so they can later support localized voice feedback.

Examples:

```text
Knight to f3.
Illegal move.
Which knight?
Check.
Checkmate.
```

Do not tightly couple these messages to English strings.

---

# 6. Stage 2.4 — Game analysis

## 6.1 Goal

Provide post-game and move-by-move Stockfish analysis while keeping the analysis subsystem distinct from live-engine functionality.

Introduce an `AnalysisService` or equivalent abstraction.

---

## 6.2 Per-position analysis

For each played move, analysis should be capable of recording:

- engine evaluation before move;
- engine evaluation after move;
- engine-preferred move;
- principal variation;
- evaluation change.

Do not analyse duplicate positions unnecessarily.

---

## 6.3 Post-game analysis

Implement an operation to analyse a completed or loaded game.

The process should:

1. replay the game from the starting position;
2. analyse each relevant position;
3. compare played moves with engine recommendations;
4. produce structured analysis results;
5. avoid modifying the original game.

Provide progress information if the analysis can take noticeable time.

The GUI must remain responsive.

---

## 6.4 Move classifications

Support classifications such as:

```text
Best
Excellent
Good
Inaccuracy
Mistake
Blunder
```

Do not implement these as arbitrary fixed labels scattered through GUI code.

Create a dedicated classification component/policy.

Classification should consider evaluation changes and, where appropriate, mate transitions.

Document the classification thresholds.

Treat them as project-defined heuristics rather than claiming they reproduce Chess.com, Lichess, or another external service exactly.

---

## 6.5 Accuracy / centipawn-loss statistics

Where feasible, calculate useful metrics such as:

- average centipawn loss for White;
- average centipawn loss for Black;
- inaccuracies;
- mistakes;
- blunders;
- best-move matches.

If an "accuracy" percentage is implemented, document its formula.

Do not present a proprietary service's accuracy calculation unless it is actually reproduced from a documented compatible algorithm.

---

## 6.6 Analysis persistence

Allow analysed games to retain their analysis where practical so the entire game does not have to be recalculated every time it is opened.

The persistence format should be versionable.

Do not corrupt ordinary PGN compatibility.

If engine annotations are stored in PGN comments, keep them parseable and optional.

---

# 7. Stage 2.5 — Software hardening and developer tooling

## 7.1 Goal

Prepare the software for Stage 3 hardware development by making behavior deterministic, observable, testable and replayable.

---

## 7.2 Structured logging

Introduce or improve structured logging.

Log important events such as:

```text
application startup
configuration loaded
new game
voice transcription
parsed intent
resolved move
move rejected
move executed
engine request
engine result
engine failure
game saved
game loaded
game ended
```

Do not log excessive raw audio data.

Avoid logging sensitive filesystem or environment information unnecessarily.

Support configurable log levels.

---

## 7.3 Error model

Create clear exceptions/result types for major subsystems.

Avoid broad patterns such as:

```python
except Exception:
    pass
```

Failures should be:

- handled where recovery is possible;
- logged;
- communicated to the user where relevant;
- propagated where the caller must decide.

---

## 7.4 Scripted-game runner

Implement a developer-facing mechanism for automatically playing scripted games.

Example input:

```text
e4
e5
Nf3
Nc6
Bb5
a6
```

or an equivalent structured format.

The runner should pass through the same game controller used by interactive play.

Do not implement a separate shortcut that bypasses ordinary validation.

This becomes a major integration-test tool for later physical-board work.

---

## 7.5 Deterministic voice input adapter

Provide a mock/test voice source capable of supplying known transcriptions without requiring a microphone.

For example:

```python
FakeSpeechRecognizer([
    "e four",
    "e five",
    "knight f three",
])
```

This should allow integration testing of:

```text
transcription
→ parser
→ resolver
→ game state
```

without audio hardware.

---

## 7.6 Mock engine

Provide an engine abstraction suitable for tests.

Tests should not require a real Stockfish process unless specifically marked as engine integration tests.

Example capabilities:

```python
FakeEngine(
    evaluations={...},
    best_moves={...},
)
```

---

## 7.7 Future actuator seam

Do **not** implement Stage 3 hardware control.

However, verify that move execution occurs through a sufficiently centralized path that a future physical-board observer/actuator can attach cleanly.

The architecture should make this future sequence possible:

```text
validated chess move
       ↓
GameController
       ↓
move committed
       ↓
future PhysicalMovePlanner
```

Avoid introducing new GUI shortcuts that mutate the board directly.

---

## 7.8 Configuration system

Centralize runtime configuration.

Support settings including:

```text
voice language
speech backend/model
engine path
engine enabled
analysis settings
engine opponent strength
logging level
game autosave
```

Validate configuration.

Provide sane defaults.

Where paths are platform-dependent, use discovery/configuration rather than hard-coded user-specific paths.

---

## 7.9 Graceful degradation

The application should remain partially usable when optional components are unavailable.

Examples:

```text
Stockfish missing
→ human-vs-human remains available
→ engine features disabled with explanation

microphone unavailable
→ GUI/terminal move input remains available

speech model unavailable
→ non-voice chess remains available
```

A failure in an optional subsystem must not unnecessarily terminate the entire application.

---

# 8. Stage 2.6 — Polish-language voice support

## 8.1 Goal

Make Polish a first-class supported voice language.

The application must support at least:

```text
English
Polish
```

with a configurable language preference.

Do not implement Polish by translating Polish commands into English strings.

Both English and Polish should produce the same internal language-independent intents.

Architecture:

```text
                    transcription
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
        EnglishParser            PolishParser
             │                       │
             └───────────┬───────────┘
                         ▼
                    MoveIntent
                         ▼
                  LegalityResolver
```

---

## 8.2 Speech-recognition language

Configure the speech-recognition backend so Polish can be explicitly selected.

Prefer explicit language configuration over automatic detection for chess commands because utterances may be extremely short.

Example setting:

```text
Voice language:

Polish
English
Auto
```

`Auto` may exist if the backend supports it, but explicit modes are the primary supported workflow.

---

# 9. Polish chess grammar

## 9.1 Piece names

Recognize at minimum:

```text
król
hetman
wieża
goniec
skoczek
pion
```

Allow common inflected forms where they naturally occur and are useful.

Do not attempt to build a general Polish morphological analyser unless necessary.

Use targeted chess-domain normalization.

---

## 9.2 Squares

Recognize spoken ranks:

```text
jeden
dwa
trzy
cztery
pięć
sześć
siedem
osiem
```

Normalize them to:

```text
1 2 3 4 5 6 7 8
```

Recognize files:

```text
a
b
c
d
e
f
g
h
```

including likely ASR spellings or Polish letter-name renderings where the chosen speech model produces them.

Examples that should resolve correctly where reasonable:

```text
e cztery
e4

ef trzy
f trzy
f3

gie sześć
g sześć
g6
```

Do not assume only one transcription spelling.

Build normalization from observed/expected ASR output.

---

## 9.3 Basic moves

Recognize:

```text
e cztery
pion e cztery
pion na e cztery

skoczek f trzy
skoczek na f trzy

goniec c cztery
goniec na c cztery

hetman h pięć
hetman na h pięć
```

Resolve these against the current legal position.

---

## 9.4 Captures

Recognize capture verbs including at minimum:

```text
bije
bierze
```

Examples:

```text
skoczek bije e pięć
skoczek bierze e pięć

goniec bije f siedem
wieża bierze e pięć
```

Normalize both to the same capture intent.

The explicit word for capture may be omitted if the destination uniquely determines a legal move.

Do not reject a legal chess command solely because the speaker omitted "bije".

---

## 9.5 Origin-square specification

Support more explicit commands such as:

```text
goniec z c cztery na f siedem
wieża z a jeden na e jeden
skoczek z g jeden na f trzy
```

Use origin information to resolve ambiguity.

---

## 9.6 Castling

Recognize:

```text
roszada krótka
krótka roszada

roszada długa
długa roszada
```

Map them to the appropriate castling intents.

Legality remains determined by the chess-state layer.

---

## 9.7 Check and checkmate words

Recognize optional spoken suffixes such as:

```text
szach
mat
szach mat
```

Examples:

```text
hetman h pięć szach
wieża e osiem mat
```

Treat these primarily as optional semantic assertions.

Do not require the user to say them.

Do not accept an otherwise illegal move because the speaker said "szach" or "mat".

---

## 9.8 Promotion

Support Polish promotion commands.

Examples should include forms equivalent to:

```text
e osiem hetman
e osiem promocja na hetmana
pion na e osiem hetman
```

Support promotion to:

- hetman;
- wieża;
- goniec;
- skoczek.

Normalize grammatical cases as necessary, e.g. forms corresponding to:

```text
hetman
hetmana
wieża
wieżę
goniec
gońca
skoczek
skoczka
```

Do so through targeted normalization.

---

## 9.9 Polish application commands

Support useful Polish application commands including at minimum reasonable variants of:

```text
nowa gra
cofnij
ponów
powtórz
zapisz grę
poddaję się
remis
```

Where appropriate also support natural variants such as:

```text
cofnij ruch
powtórz ruch
nową grę
zapisz
```

These should map to language-independent application intents.

Example:

```text
"cofnij"
      ↓
ApplicationIntent(command="undo")
```

English:

```text
"undo"
      ↓
ApplicationIntent(command="undo")
```

Both must invoke the same application behavior.

---

# 10. Polish normalization layer

Implement a dedicated normalization layer rather than filling the parser with ad hoc string replacements.

Responsibilities may include:

```text
lowercasing
Unicode normalization where needed
punctuation removal
rank-word normalization
ASR spelling normalization
piece-name normalization
capture-verb normalization
common inflection normalization
```

Examples:

```text
"Skoczek na F trzy."
→ "skoczek na f 3"

"Wieża bierze E pięć"
→ normalized capture intent
```

Keep normalization deterministic and heavily unit-tested.

---

# 11. Voice language configuration

The selected language must be available through application settings.

Conceptual API:

```python
VoiceLanguage.ENGLISH
VoiceLanguage.POLISH
VoiceLanguage.AUTO
```

`AUTO` is optional.

When Polish is explicitly selected:

- speech recognition should receive the Polish language hint/configuration where supported;
- Polish parser should run;
- user-facing voice messages should use Polish where localization exists.

When English is selected, existing English behavior should remain unchanged.

---

# 12. Localization

Do not scatter literal English and Polish strings throughout business logic.

Introduce a lightweight localization mechanism for user-facing messages that need translation.

Example keys:

```text
voice.illegal_move
voice.ambiguous_move
voice.unrecognized
voice.confirm_move
game.check
game.checkmate
game.stalemate
game.resigned
engine.unavailable
```

Example conceptual translations:

```text
voice.illegal_move

en: "Illegal move."
pl: "Nielegalny ruch."
```

Do not over-engineer a full internationalization framework if the current application does not require one.

The objective is simply to prevent business logic from depending on English strings.

---

# 13. Tests

All new functionality requires automated tests.

Maintain existing tests.

Add tests at several levels.

---

## 13.1 Stockfish abstraction tests

Test:

- score normalization;
- mate score handling;
- best-move conversion;
- MultiPV normalization;
- engine unavailable;
- engine crash handling;
- lifecycle cleanup.

Most tests should use mocks.

Add a small number of optional real-Stockfish integration tests if practical.

---

## 13.2 Game-feature tests

Test:

- PGN export/import round trip;
- FEN loading;
- invalid FEN;
- undo;
- redo;
- new game;
- resignation;
- draw handling;
- autosave/load;
- clock switching where implemented.

---

## 13.3 English voice tests

Preserve tests for existing Stage 2 commands.

Add tests for:

- shorthand commands;
- captures;
- castling;
- ambiguous moves;
- illegal moves;
- application commands.

---

## 13.4 Polish parser tests

Include direct tests for at least:

```text
e cztery
pion na e cztery
skoczek f trzy
skoczek na f trzy
goniec c cztery
goniec na c cztery
skoczek bije e pięć
skoczek bierze e pięć
goniec z c cztery na f siedem
roszada krótka
krótka roszada
roszada długa
długa roszada
hetman h pięć szach
cofnij
nowa gra
zapisz grę
poddaję się
```

Test realistic alternate ASR spellings where identified.

---

## 13.5 Contextual-resolution tests

Create positions where:

### Exactly one move matches

```text
"skoczek f trzy"
→ Nf3
```

### Multiple moves match

Parser/resolver must return ambiguity.

### No legal move matches

Return an illegal/unresolvable result.

### Spoken capture marker is incorrect

The system must respect actual chess legality/state rather than blindly trusting the spoken wording.

---

## 13.6 Full pipeline tests

Use fake speech recognition:

```text
spoken Polish
→ Polish transcription
→ Polish parser
→ MoveIntent
→ legal move resolution
→ board update
```

Test the equivalent English path.

Verify equivalent English and Polish commands produce identical chess moves.

Example:

```text
"knight f3"
"skoczek f trzy"
```

must resolve to the same canonical move from the same position.

---

## 13.7 Scripted full-game tests

Include at least one legal complete or substantial game that can be replayed automatically.

Test:

```text
new game
→ sequence of moves
→ expected final FEN
→ expected move history
```

Where reasonable include:

- capture;
- castling;
- check;
- checkmate.

---

# 14. Concurrency and responsiveness

Engine analysis and speech recognition may be expensive operations.

Do not block the main GUI event loop.

Ensure stale asynchronous results cannot modify newer game state.

Use position/game identifiers, generation counters, cancellation tokens or another clear mechanism.

Example:

```text
analyse position A
player makes move
analyse position B

result for A arrives late
→ discard

result for B arrives
→ display
```

Apply similar reasoning to voice events where necessary.

---

# 15. Persistence and schema evolution

If persisted settings/game data gain new fields, introduce a migration/defaulting strategy.

Older save files should not crash merely because they lack:

```text
voice_language
engine_settings
analysis_data
```

Prefer versioned persisted data where practical.

---

# 16. Documentation

Update `README.md` to document:

- Stockfish installation/configuration;
- engine features;
- engine-opponent mode;
- PGN/FEN features;
- analysis features;
- English voice commands;
- Polish voice commands;
- language selection;
- limitations;
- running without Stockfish;
- developer test utilities.

Document example Polish commands.

Also update architecture/developer documentation where appropriate.

---

# 17. Dependency policy

Before adding a dependency:

1. determine whether existing dependencies already provide the required functionality;
2. prefer mature, maintained packages;
3. avoid large frameworks for small tasks;
4. keep optional subsystems optional where practical;
5. document external system dependencies such as Stockfish.

Do not bundle arbitrary Stockfish binaries into the repository unless the project explicitly adopts a redistribution strategy compatible with licensing requirements.

---

# 18. Compatibility requirements

The implementation must preserve:

- terminal/manual chess input from Stage 1 where still supported;
- GUI play from Stage 1.1;
- English voice play from Stage 2;
- standard legal chess behavior;
- tests for previously implemented functionality.

New features must augment these pathways rather than create separate competing implementations of chess logic.

All input modes should eventually converge on the same controller:

```text
Terminal input ──────┐
GUI move ────────────┤
English voice ───────┤
Polish voice ────────┤
Scripted test ───────┤
Engine move ─────────┘
                     ↓
               GameController
                     ↓
               legal move/state
```

This convergence is a major architectural requirement.

---

# 19. Explicit non-goals

Do **not** implement as part of Stage 2.x:

- physical chessboard control;
- GPIO;
- motor drivers;
- XY carriage logic;
- electromagnet control;
- Hall sensors;
- RFID;
- physical capture storage;
- physical path planning;
- Raspberry Pi-specific hardware assumptions;
- cloud accounts;
- multiplayer servers;
- arbitrary conversational AI;
- online chess-service integration.

Those belong to later stages.

Do not allow speculative future features to delay completion of this stage.

---

# 20. Recommended implementation sequence

Implement in dependency-aware increments.

## Increment A — Architectural preparation

- inspect existing architecture;
- centralize move execution;
- introduce intent models;
- introduce configuration layer if needed;
- introduce engine interface;
- introduce language abstraction.

Run all existing tests.

Commit only once existing behavior remains stable.

---

## Increment B — Stage 2.1

Implement:

- Stockfish adapter;
- engine lifecycle;
- evaluation;
- best move;
- MultiPV;
- GUI engine analysis;
- engine opponent;
- engine configuration;
- tests.

---

## Increment C — Stage 2.2

Implement:

- PGN;
- FEN;
- save/load;
- history navigation;
- undo/redo;
- game commands;
- clocks;
- player settings.

---

## Increment D — Stage 2.3

Implement:

- language-independent intents;
- legality-based resolver;
- ambiguity handling;
- confidence/error states;
- confirmations;
- richer English grammar.

Refactor existing Stage 2 voice functionality onto this architecture.

---

## Increment E — Stage 2.6 Polish core

Implement:

- explicit Polish ASR configuration;
- Polish normalization;
- Polish piece vocabulary;
- squares/ranks;
- ordinary moves;
- captures;
- castling;
- promotions;
- application commands;
- Polish tests;
- UI language setting.

Stage 2.6 is listed here before analysis because it depends directly on the Stage 2.3 parser architecture and can be implemented independently of post-game analysis.

---

## Increment F — Stage 2.4

Implement:

- analysis service;
- per-move evaluation;
- post-game analysis;
- move classifications;
- centipawn-loss statistics;
- analysis persistence;
- GUI presentation.

---

## Increment G — Stage 2.5

Complete:

- structured logging;
- scripted-game runner;
- fake speech recognizer;
- mock engine;
- integration tests;
- persistence compatibility;
- graceful failure handling;
- documentation;
- cleanup.

---

# 21. Acceptance criteria

Stage 2.x is complete only when the following are true.

## Core chess

- A normal game can still be played without voice or Stockfish.
- Legal move enforcement remains centralized.
- No GUI, parser or engine component independently implements chess legality.

## Stockfish

- Stockfish can be configured externally.
- Current position evaluation can be displayed.
- Best move can be requested.
- Multiple candidate lines can be produced.
- Human-vs-engine play works.
- Missing Stockfish does not prevent ordinary chess play.
- Stockfish processes shut down cleanly.

## Game application

- Games can be exported to PGN.
- PGNs can be loaded.
- FEN can be loaded.
- Game history can be inspected.
- Undo works correctly.
- Redo works where applicable.
- New game works cleanly.
- resignation/end states are represented correctly.
- game settings persist appropriately.

## English voice

Commands such as:

```text
e4
e four
knight f3
knight to f3
bishop takes f7
castle kingside
undo
new game
```

work where legal and applicable.

## Polish voice

Commands such as:

```text
e cztery
pion na e cztery
skoczek f trzy
skoczek na f trzy
goniec c cztery
skoczek bije e pięć
skoczek bierze e pięć
roszada krótka
roszada długa
cofnij
nowa gra
zapisz grę
poddaję się
```

work where legal and applicable.

## Contextual resolution

- incomplete but uniquely resolvable chess commands are accepted;
- ambiguous commands are not guessed;
- illegal moves are rejected;
- English and Polish commands converge on the same intent/resolution system.

## Analysis

- a completed game can be analysed;
- evaluation swings are available;
- engine-preferred moves can be shown;
- move classifications are deterministic and documented;
- analysis does not alter the original game.

## Reliability

- GUI remains responsive during engine work;
- stale engine results are discarded;
- optional subsystem failures degrade gracefully;
- meaningful events are logged;
- automated integration tests cover major workflows.

---

# 22. Final validation

Before declaring the implementation complete:

1. Run the complete automated test suite.

2. Run static analysis/linting/type checking already used by the project.

3. Start the application with Stockfish available.

4. Play several moves manually.

5. Verify live evaluation updates.

6. Start a human-vs-engine game and verify engine replies.

7. Export and reload a PGN.

8. Load a valid FEN.

9. Verify invalid FEN handling.

10. Test undo/redo.

11. Test English voice commands.

12. Switch explicitly to Polish.

13. Test Polish commands including:
    - pawn move;
    - piece move;
    - capture;
    - castling;
    - application command.

14. Test an intentionally ambiguous spoken move.

15. Test an illegal spoken move.

16. Complete or load a game and run post-game analysis.

17. Start the application with Stockfish unavailable and verify graceful degradation.

18. Test the scripted-game runner.

19. Confirm no regression in Stage 1, Stage 1.1 or Stage 2 functionality.

20. Confirm the code contains a clean seam for future Stage 3 physical-move integration without implementing hardware behavior.

---

# 23. Deliverables

At completion, provide:

- implementation of Stages 2.1–2.6;
- updated automated tests;
- updated configuration;
- updated `README.md`;
- any necessary developer/architecture documentation;
- example English and Polish voice-command documentation;
- documented Stockfish setup;
- documented analysis heuristics;
- summary of significant architectural changes;
- known limitations;
- confirmation of test results.

Do not report a feature as complete unless it is implemented and tested.

---

# 24. Architectural end state

At the end of Stage 2.x, the Wizard Chess software should conceptually operate as:

```text
                          USER
                           │
            ┌──────────────┼───────────────┐
            │              │               │
            ▼              ▼               ▼
          GUI           English          Polish
                         voice            voice
            │              │               │
            │              ▼               ▼
            │           English          Polish
            │            parser           parser
            │              └───────┬───────┘
            │                      ▼
            │                    Intent
            │                      │
            └──────────────────────┤
                                   ▼
                         Position-aware resolver
                                   │
                                   ▼
                            GameController
                                   │
                     ┌─────────────┼─────────────┐
                     ▼             ▼             ▼
                 Chess state    Persistence   Stockfish
                     │                           │
                     │                      ┌────┴────┐
                     │                      ▼         ▼
                     │                  Live play  Analysis
                     │
                     ▼
               canonical move event
                     │
                     ▼
             [STAGE 3 INTEGRATION SEAM]
                     │
                     ▼
             Future physical board
```

The primary architectural outcome is that by the end of Stage 2.x, **all ways of playing chess — GUI, terminal, English speech, Polish speech and Stockfish — operate on one authoritative game model and produce canonical move events suitable for later physical execution.**