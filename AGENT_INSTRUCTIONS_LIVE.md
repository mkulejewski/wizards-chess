Implement a new **live engine analysis mode** for the Wizard Chess Set application. The feature should integrate cleanly with the existing Stockfish/engine infrastructure and graphical game window, while preserving the current fixed-time engine-analysis behavior as an alternative.

The goal is to make engine evaluation behave similarly to analysis in modern chess GUIs: while a position is displayed, Stockfish analyzes continuously in the background, progressively reaching greater depth and updating the UI as stronger results become available. Evaluations should be retained for the duration of the game/session and reused for post-game analysis.

## 1. Scope and design constraints

Before modifying code:

1. Inspect the existing engine integration, configuration system, game-state model, GUI architecture, threading/async model, and tests.
2. Reuse existing abstractions where possible rather than introducing a parallel engine subsystem.
3. Preserve all existing behavior and CLI/configuration compatibility unless explicitly changed below.
4. Keep engine computation completely off the GUI/event-loop thread.
5. Do not allow stale Stockfish results for an earlier position to overwrite the evaluation of a newer position.
6. Ensure engine processes and analysis tasks are always cancelled/terminated cleanly when:
   - a move is made,
   - another position is selected,
   - live analysis is disabled,
   - a game is closed,
   - the application exits.
7. Keep the implementation engine-agnostic where practical, although Stockfish remains the currently supported engine.

Implement the work as a coherent incremental feature, with tests added alongside each major component.

---

# 2. New analysis mode: continuous/live analysis

Add an engine-analysis mode corresponding conceptually to:

```text
live analysis
```

Unlike the existing fixed-time analysis mode, this mode must **not stop after a configured number of milliseconds**.

Instead:

- start analyzing the current position immediately;
- allow Stockfish to continue searching;
- receive intermediate analysis information as the search progresses;
- publish updated evaluation results whenever the engine reaches a new useful depth;
- stop only when:
  - the configured maximum depth is reached,
  - the position changes,
  - the user disables analysis,
  - the game/window closes.

The analysis should therefore naturally produce updates resembling:

```text
depth 8   +0.21
depth 10  +0.17
depth 12  +0.24
depth 15  +0.31
depth 18  +0.28
...
```

Do not simulate this by repeatedly starting independent short searches. Use the engine's streaming/continuous analysis functionality if supported by the existing chess/Stockfish integration.

## Configuration

Extend the application's settings/configuration system with appropriate settings such as:

```text
analysis mode = off | fixed_time | live
live analysis max depth = N
```

Choose names consistent with the existing configuration conventions rather than blindly adopting these exact identifiers.

If a distinction already exists between an engine **playing moves** and an engine **analyzing positions**, preserve it.

Live analysis must work independently from whether White or Black is controlled by an engine.

For example, these should be conceptually valid combinations:

```text
Human vs Human + live analysis
Human vs Engine + live analysis
Engine vs Human + live analysis
```

The existing fixed-time engine settings should continue to work for computer move selection.

Avoid coupling the engine's playing strength/time control with the live-analysis depth unless the existing architecture strongly requires it.

---

# 3. Analysis result model

Introduce or extend a structured analysis result type.

At minimum, each published result should contain:

```text
position identifier
ply / move number
FEN or equivalent position representation
search depth
evaluation
mate information if applicable
principal variation, if cheaply available
timestamp or monotonic sequencing information if useful
```

Evaluation should have a canonical representation internally.

Prefer a model that explicitly distinguishes:

```text
centipawn evaluation
mate-in-N evaluation
```

rather than representing mate as an arbitrary huge centipawn number.

Normalize evaluation consistently from **White's perspective** for storage and plotting:

```text
positive = advantage White
negative = advantage Black
0 = equal
```

If the engine library returns scores from the side-to-move perspective, normalize them before exposing them to the rest of the application.

---

# 4. Live evaluation sidebar

Add a graphical evaluation indicator to the game window.

The visual design should resemble the vertical evaluation bars used in chess GUIs:

```text
White
████████
████████
████████
--------
████████
████████
Black
```

More precisely:

- place a vertical evaluation bar/sidebar immediately adjacent to the chessboard;
- White occupies one side/end of the bar and Black the other;
- the dividing line moves according to the current engine evaluation;
- an equal position should show approximately 50/50;
- increasing White advantage expands White's portion;
- increasing Black advantage expands Black's portion;
- the bar should update smoothly or at least without distracting visual flicker when deeper engine evaluations arrive.

Show the current numerical evaluation near or within the sidebar, for example:

```text
+0.35
```

or:

```text
-1.42
```

For mate scores, use chess-standard notation such as:

```text
M3
-M2
```

Do not expose implementation-specific centipawn integers such as `+35` to the user.

## Evaluation-to-bar mapping

Do **not** map centipawn evaluation linearly all the way to infinity.

Use a bounded transformation so that, for example:

```text
0.00    -> 50/50
small advantage -> modest visual displacement
+/- 2–3 pawns -> substantial advantage
very large advantage -> approaches but does not numerically overflow the endpoint
mate -> effectively full winning side
```

A logistic/tanh-style mapping is appropriate.

Centralize this transformation in a reusable/testable function rather than embedding it in GUI code.

---

# 5. Position changes and concurrency

When the board position changes:

1. cancel or stop analysis of the previous position;
2. start analysis of the new position;
3. immediately show any cached evaluation already available for the new position;
4. replace it with progressively deeper results as live analysis proceeds.

There must be explicit protection against this race condition:

```text
Position A starts analysis
Position B becomes current
Position B analysis starts
late result from Position A arrives
Position A result incorrectly appears in Position B UI
```

Use a position key, generation ID, task ID, FEN comparison, or equivalent robust mechanism.

This behavior requires automated tests.

---

# 6. Temporary per-game analysis cache

Add a temporary in-memory analysis cache associated with the current game/session.

The purpose is to retain engine evaluations for positions that have already been analyzed.

The cache should:

- live for the duration of the game and its post-game analysis session;
- require no database or permanent disk persistence;
- be discarded when the game/session is finally closed or reset;
- retain the **best/deepest available result** for each position;
- optionally retain intermediate depth results if this is useful architecturally, but the deepest result must be directly accessible.

Use a stable position identifier. FEN may be suitable, but account for whether move counters or other FEN fields should affect cache identity.

Avoid incorrectly merging positions when state relevant to chess legality differs, especially:

- side to move;
- castling rights;
- en-passant state.

The cache should provide operations conceptually similar to:

```python
store(position, analysis_result)
get_best(position)
get_all_for_game()
clear()
```

Do not make GUI widgets themselves own the analysis cache.

---

# 7. Cache evaluations as the game progresses

Every time a live-analysis result reaches a greater depth than the best cached result for the current position:

- update the cache;
- update the sidebar if that position is currently displayed.

When the player makes a move, retain the previous position's analysis.

Thus by the end of a game, the cache should contain an evaluation history resembling:

```text
initial position -> +0.10 depth 18
after 1.e4       -> +0.21 depth 20
after ...c5      -> +0.15 depth 19
after 2.Nf3      -> +0.24 depth 21
...
```

A position that has already reached the configured maximum depth should not need to be recomputed merely because the user navigates away and back to it.

---

# 8. Finished-game analysis mode

Extend the GUI so that when a game is finished, the user can inspect the game move-by-move.

Reuse the existing game-history/navigation system if one exists.

When viewing any historical position:

- display that board position;
- display its cached engine evaluation in the sidebar;
- display the corresponding numerical evaluation;
- optionally display depth, e.g.:

```text
+0.42
depth 19
```

If a historical position has not yet been sufficiently analyzed, live analysis should be able to resume for that position while the user is viewing it.

Do not throw away the game cache immediately when checkmate/draw/resignation occurs. It must remain available for post-game analysis until the game/session is actually closed/reset.

---

# 9. Post-game advantage graph

Once the game has finished, add a graphical plot to the game window representing evaluation over the course of the game.

The graph should be integrated into the application's GUI rather than opening an unrelated external plotting window.

Conceptually:

```text
White advantage
  ^
+5|              /\
+3|       /\    /  \
+1|__/\__/  \__/    \__
 0|-----------------------
-1|                     \
-3|                      \___
-5|
  +--------------------------> moves
Black advantage
```

Requirements:

- x-axis = game progression, preferably ply or move number;
- y-axis = evaluation from White's perspective;
- positive values = White advantage;
- negative values = Black advantage;
- zero line clearly visible;
- derive values from the per-game analysis cache;
- use the deepest available evaluation for each position;
- clearly represent missing/unanalysed positions rather than silently converting them to zero.

For mate evaluations, choose a deterministic bounded representation for plotting, for example a configurable/display-only equivalent such as:

```text
mate for White -> +MATE_PLOT_VALUE
mate for Black -> -MATE_PLOT_VALUE
```

Do not alter the canonical mate representation stored in the analysis model merely to make plotting easier.

The plot should be recomputable when additional historical positions receive deeper analysis.

---

# 10. Interaction between graph and position navigation

If practical within the existing GUI architecture, make the post-game graph useful for navigation.

Preferred behavior:

- selecting/clicking a point or region of the graph navigates the board to the corresponding ply;
- the evaluation sidebar updates to that position's cached evaluation.

If this requires disproportionately invasive GUI work, structure the graph component so this can be added later, but implement it now if reasonably straightforward.

At minimum, navigating through moves using existing previous/next/start/end controls must update both:

```text
board position
evaluation sidebar
```

and preferably indicate the current ply on the graph.

---

# 11. Analysis lifecycle

Create a clear lifecycle for the analysis subsystem.

Conceptually:

```text
Game starts
    ↓
analysis session/cache created
    ↓
position displayed
    ↓
cached evaluation? ── yes ──> display immediately
    │
    no / insufficient depth
    ↓
start live engine analysis
    ↓
new depth result
    ↓
normalize evaluation
    ↓
update cache
    ↓
publish UI update
    ↓
position changes
    ↓
cancel old analysis
    ↓
repeat
    ↓
game ends
    ↓
cache remains alive
    ↓
post-game navigation + graph
    ↓
game/session closed or reset
    ↓
analysis session/cache destroyed
```

Keep these responsibilities separated:

```text
engine communication
analysis orchestration
analysis/result models
per-game cache
GUI presentation
plotting/navigation
```

Avoid putting the entire feature into the game-window class.

---

# 12. Engine failures

Live analysis must degrade gracefully.

Handle at minimum:

- Stockfish executable unavailable;
- engine crashes;
- malformed/unsupported analysis response;
- analysis task cancellation;
- GUI closes while analysis is running.

The chess game itself should remain usable if live analysis fails.

Show a non-disruptive status such as:

```text
Analysis unavailable
```

rather than crashing the application.

Reuse existing engine-error handling where appropriate.

---

# 13. Performance

Live analysis is intentionally CPU-intensive, but the application must remain responsive.

Ensure that:

- GUI rendering never waits synchronously for Stockfish;
- only the currently relevant position is actively analyzed unless there is an explicitly designed background post-game analysis queue;
- rapidly playing/navigating moves does not leave multiple engine searches running;
- UI updates are throttled if Stockfish produces excessively frequent info messages.

It is acceptable to publish only:

```text
new maximum depth results
```

or otherwise coalesce redundant updates.

Do not unnecessarily redraw the complete board when only the evaluation bar changes.

---

# 14. Optional completion of missing positions after the game

If the architecture permits it cleanly, add a post-game analysis process that can fill gaps in the evaluation history.

For example:

```text
game finished
↓
identify positions with no analysis or insufficient depth
↓
analyze them sequentially
↓
update cache
↓
update graph progressively
```

Do not run multiple Stockfish searches concurrently against the same engine process unless the engine abstraction explicitly supports that.

Treat this as secondary to correct interactive live analysis. Do not compromise the core implementation to add aggressive background analysis.

---

# 15. GUI layout

Update the existing graphical layout coherently.

A reasonable target is:

```text
+------------------------------------------------------+
|                    Wizard Chess                      |
+--------------------------------------+---------------+
|                                      | evaluation    |
|                                      |     bar       |
|                                      |               |
|             CHESSBOARD               |    +0.42      |
|                                      |   depth 18    |
|                                      |               |
+--------------------------------------+---------------+
|                                                      |
|             evaluation history graph                 |
|            (visible after game/end analysis)         |
|                                                      |
+------------------------------------------------------+
| controls / move history / status                     |
+------------------------------------------------------+
```

Adapt this to the actual GUI toolkit and layout conventions already used in the project.

Do not arbitrarily redesign unrelated application UI.

---

# 16. Settings/UI controls

Expose live analysis through the application's normal settings/launch configuration mechanism.

The user should be able to choose at least:

```text
analysis disabled
live analysis
maximum live-analysis depth
```

If the recently introduced launch/settings UI is already present, integrate these options there instead of requiring additional environment-variable boilerplate.

If configuration is currently represented through environment variables internally, preserve compatibility, but expose ergonomic settings through the higher-level configuration interface.

Provide sensible defaults.

Avoid enabling continuous Stockfish analysis by surprise on machines where the engine feature was previously disabled.

---

# 17. Testing

Add thorough automated tests.

At minimum cover:

### Evaluation normalization

```text
engine side-to-move score -> White-centric score
White advantage -> positive
Black advantage -> negative
mate scores preserved correctly
```

### Evaluation-bar mapping

Test representative values:

```text
0.00
+0.5
-0.5
+3
-3
large scores
mate White
mate Black
```

Verify symmetry and bounds.

### Cache

Test:

```text
store result
retrieve result
deeper result replaces shallower result
shallower result does not replace deeper result
different positions remain separate
cache survives game termination state
cache clears at session reset/close
```

### Live-analysis orchestration

Using a fake/mock engine:

```text
depth 5 emitted
depth 8 emitted
depth 12 emitted
```

verify progressively updated results.

### Stale-result protection

Explicitly simulate:

```text
start position A
switch to B
late A result arrives
```

and verify the UI/model remains on B.

### Cancellation

Verify changing positions stops/cancels the previous analysis cleanly.

### GUI behavior

Where the GUI framework permits practical testing:

- evaluation widget reflects current cached score;
- historical navigation changes evaluation;
- finished-game graph receives the correct sequence;
- missing evaluations are handled appropriately.

Avoid making tests depend on a locally installed Stockfish binary unless clearly marked as optional integration tests.

---

# 18. Documentation

Update the README and relevant developer documentation.

Document:

- what live analysis does;
- how it differs from fixed-time engine move calculation;
- how to enable it;
- how to configure maximum depth;
- interpretation of the sidebar;
- interpretation of positive/negative evaluation;
- mate notation;
- post-game graph;
- temporary nature of the analysis cache;
- any performance implications.

Include an example configuration/launch workflow using the project's current preferred settings mechanism.

---

# 19. Backward compatibility

Do not regress:

- terminal chess;
- graphical chess without engine analysis;
- engine-controlled players;
- existing Stockfish strength presets;
- fixed-time move calculation;
- voice-control functionality;
- Polish-language functionality;
- game termination/checkmate handling;
- current configuration loading.

Live analysis is an additive feature.

---

# 20. Architectural preference

Aim for an architecture conceptually similar to:

```text
EngineBackend
    │
    ▼
LiveAnalysisController
    │
    ├── AnalysisResult
    │
    ├── GameAnalysisCache
    │
    └── analysis update signal/event
             │
             ▼
        GameController
             │
      ┌──────┴─────────┐
      ▼                ▼
EvaluationBar    EvaluationGraph
```

Names should follow the existing repository conventions.

The GUI should consume analysis state; it should not directly manage Stockfish protocol details.

---

# 21. Definition of done

The increment is complete when I can:

1. Launch a graphical game with live analysis enabled.
2. Start from the initial position and see an evaluation sidebar.
3. Observe the displayed Stockfish depth increase while I remain on the same position.
4. Observe the evaluation change as deeper results arrive.
5. Make a move without freezing the GUI.
6. See analysis of the old position stop and analysis of the new position begin.
7. Play multiple moves and have their deepest evaluations retained in memory.
8. Navigate back to an earlier position and immediately see its cached evaluation.
9. Finish the game without losing the cached analysis.
10. Navigate through the finished game and see the evaluation sidebar update for each position.
11. See an in-window graph of White/Black advantage across the game.
12. Have deeper/missing post-game analysis update the corresponding cached values and graph.
13. Disable live analysis and continue using the application normally.
14. Exit the application without orphaned Stockfish processes or analysis tasks.
15. Run the full automated test suite successfully.

---

# 22. Implementation procedure

Work incrementally.

Before coding, inspect the repository and briefly identify:

- relevant engine modules;
- GUI modules;
- game-history/state modules;
- configuration modules;
- current threading/async approach;
- tests that should be extended.

Then implement in logical increments, preferably approximately:

```text
A. analysis domain model + score normalization
B. per-game analysis cache
C. streaming/live engine API
D. live-analysis controller and cancellation semantics
E. evaluation-bar mapping
F. evaluation sidebar GUI
G. settings integration
H. historical-position integration
I. post-game evaluation graph
J. optional gap-filling analysis
K. tests and documentation
```

After each major increment, run the relevant tests.

After implementation:

1. run formatting/linting/type checks used by the repository;
2. run the full automated test suite;
3. report any failures;
4. inspect the final diff for accidental unrelated changes;
5. summarize the architecture and notable implementation decisions.

Do not merely scaffold interfaces or add TODOs. Implement the complete usable feature.

When an architectural choice is ambiguous, prefer the smallest design that cleanly separates live engine analysis from UI presentation and will remain suitable for later Wizard Chess Set stages.