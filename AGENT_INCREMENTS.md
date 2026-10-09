# Wizard Chess development increments

This ledger tracks delivered development stages and their verification status. It was created
for the Stage 2.x expansion on 2026-08-24. Earlier entries were reconstructed from Git history,
the stage instruction files, source, and tests; they do not invent commit boundaries that are
not present in the repository.

Status meanings:

- **Complete** — implemented and covered by the repository's automated quality suite.
- **Complete; manual acceptance pending** — implementation and fakes pass, but an external
  executable/device was not available in this development environment.
- **Deferred** — intentionally belongs to a later stage.

## Completed foundation

| Increment | Status | Delivered evidence |
| --- | --- | --- |
| Stage 1 — authoritative chess foundation | Complete | `ChessGame`, `ChessMove`, legal move validation, FEN/PGN rendering, undo/redo, result detection, hardware-neutral `MoveExecuted`, CLI, tests. Git history: `2d1796e`. |
| Stage 1.1A — expanded command language | Complete | SAN and coordinate intents, conservative normalization, position-aware resolution through `python-chess`, ambiguity and promotion handling. Reconstructed from current code/tests. |
| Stage 1.1B — PySide6 desktop adapter | Complete | Authoritative board rendering, click-to-move, promotion, history, status, New/Undo/Redo/Flip, typed commands, FEN controls, GUI tests. Reconstructed from current code/tests. |
| Stage 2 — English voice control | Complete; manual acceptance pending | Replaceable audio/recognizer ports, bounded local recording, lazy faster-whisper, transcript normalization, shared session submission, CLI/GUI worker, deterministic fakes. Git history: `200ed02`; hardware/model acceptance remains local. |

## Stage 2.x software expansion

| Increment | Status | Delivered evidence |
| --- | --- | --- |
| Increment A — architectural preparation | Complete | Central settings, language-independent contextual/application intents, centralized `GameSession`, engine port, language router, localization catalog, error types. |
| Stage 2.1 / Increment B — Stockfish | Complete; manual acceptance pending | Lazy UCI process via `python-chess`, external path/discovery, time/depth/MultiPV/threads/hash/strength, White-perspective cp/mate normalization, best/top/PV, terminal/crash/unavailable behavior, process cleanup, fake engine, async GUI evaluation and engine opponent. Real-binary acceptance is pending. |
| Stage 2.2 / Increment C — full application | Complete | PGN import/export and metadata round trip, FEN, unique saves, recovery autosave, version-tolerant settings, non-mutating history browsing, undo/redo/new, resignation/agreed draw, monotonic clocks, player names/types, GUI controls. |
| Stage 2.3 / Increment D — advanced voice UX | Complete with documented limitation | Shared contextual intents, legality-constrained English phrases, explicit ambiguity and error distinctions, confidence preservation, confirmation policy seam, application commands, localized message keys. A confirmation dialog is not yet wired; unique commands execute directly. |
| Stage 2.6 / Increment E — Polish core | Complete; manual acceptance pending | Explicit Polish recognizer hint/model selection, deterministic normalizer, targeted piece/rank/file inflections and ASR forms, moves/captures/origins/castling/check/promotion/application commands, GUI language selection, English fallback, equivalence and full-pipeline tests. Live microphone acceptance is pending. |
| Stage 2.4 / Increment F — game analysis | Complete; manual acceptance pending | Immutable replay, FEN cache, before/after score, preferred move/PV, deterministic classification policy, ACPL/count statistics, versioned JSON, async GUI progress/summary. Real-Stockfish performance acceptance is pending. |
| Stage 2.5 / Increment G — hardening/tooling | Complete | Configurable logging, controlled subsystem errors, scripted-game CLI through `GameSession`, fake engine and speech, autosave/schema defaults, graceful optional-component failure, integration coverage, Stage 3 event seam, updated documentation. |
| Stage 2.7 — launch configuration and game setup | Complete; manual acceptance pending | XDG-persisted game/setup defaults, corrected default/persistent/environment precedence, first-run or automatic-reuse startup policy, Game Setup presets/player names/clocks/strength/think time, Engine Preferences path/validation/live/advanced controls, atomic `GameSession` reconfiguration, async engine-as-White coverage, headless CLI/script preservation. A real Stockfish handshake and offscreen async White move passed; interactive browse/save/relaunch acceptance remains pending. |
| Board graphics | Complete | Additional graphics for the board and pieces |
| Stockfish clock/adjudication and diagnostics hardening | Complete; real-tablebase acceptance pending | Explicit fifty-move and threefold claims with bot pre-adjudication and undo/redo/PGN restoration; fixed-time versus game-clock UCI play limits; authoritative clock debit, increment, timeout, cancellation, and revision-guarded late-result rejection; separate player/post-game budgets with schema-4 migration and environment/UI wiring; optional validated Syzygy options with normal-search fallback and hit diagnostics; structured engine decisions; enriched PGN player/engine/options/termination headers plus `%emt`, `%clk`, evaluation, depth, nodes, and tablebase-hit annotations; focused supplied-FEN, migration, limit, timeout, Syzygy, and PGN round-trip tests. Stockfish 16 returned legal moves in both fixed and clock-managed real-process acceptance checks. |
| Live engine analysis | Complete; real-Stockfish acceptance pending | Backward-compatible `off`/`fixed_time`/`live` settings with independent live depth; one continuous UCI streaming search; White-centric cp/mate result model; legality-safe per-game deepest-result cache; generation/FEN stale rejection; position-change/disable/reset/close cancellation; vertical nonlinear evaluation sidebar; historical cache reuse; bounded mate-aware graph sourced exclusively from a successfully completed full post-game analysis, with explicit gaps and click navigation; deterministic stream/cache/mapping/cancellation/GUI tests; README workflow and performance documentation. |
| Undo during engine search | Complete | Engine move searches keep Undo enabled when history exists; clicking it cancels the pending worker before mutation, while existing FEN/revision guards reject queued late decisions. Engine-vs-engine cancellation and undo behavior is covered by GUI integration tests. |
| Post-game analysis presentation | Complete | **Analyse game** synchronously cancels and invalidates any active live-position worker before starting full-game analysis, including after resignation without a FEN change. Completed move-by-move text reports remain visible through terminal-position refreshes and history navigation while cached/live evaluations continue updating the sidebar and the completed-analysis graph remains available. |
| Bundled Stockfish distribution | Complete for Linux x86-64 | Official, unmodified Stockfish 18 baseline binary stored as a checksummed XZ asset; atomic first-use extraction to the XDG cache; explicit executable override, platform bundle, and system `PATH` precedence; corrupt/unsupported-bundle fallback; GPLv3, authorship, exact source archive, build target, and hashes documented. Other OS/CPU targets use the existing custom path or `PATH` until a matching release bundle is added. |
| Human draw offers and resignation controls | Complete | Replaced immediate command draws with a pending offer/accept/reject state machine; a legal move rejects an offer, while consecutive `draw` actions agree it. Added English and Polish command variants, human-player enforcement, immediate human claims when threefold/fifty-move rules apply, and an unchanged-position-only lockout after rejection that clears on the next position mutation. Snapshot capabilities/status drive state-aware PySide6 **Offer Draw**/**Accept Draw**/**Claim Draw**, **Reject Draw**, and **Resign** buttons. **New Game…** remains available during full-game analysis and safely cancels that worker before setup opens. Domain, application, parser, view-model, cancellation, and GUI paths are covered. |
| Configurable runtime logging and diagnostic expansion | Complete | Case-insensitive `DEBUG`/`INFO`/`WARNING`/`ERROR`/`OFF` launcher levels; independent terminal and XDG-state rotating-file destinations; CLI/environment/persisted/default precedence; compact terminal and timestamped UTF-8 file formats; idempotent central handler configuration; startup, command, move, voice, engine, analysis, GUI-worker, hardware, persistence, and shutdown diagnostics; focused handler/filter/file/CLI/persistence tests and README documentation. |
| Polish voice recognizer configuration fix | Complete; live microphone acceptance pending | The GUI and CLI now configure their owned recognizer from the authoritative session language. Polish and automatic recognition select the multilingual `base` model by default, English selects `base.en`, explicit model overrides remain supported, and GUI startup/language-switch regressions are covered. |
| Agent instruction interoperability | Complete | Added a minimal root `CLAUDE.md` entry point that delegates to the canonical `AGENTS.md`, avoiding duplicated guidance that could drift between agents. |

### Configurable runtime logging modification record

- Added `src/wizard_chess/logging_config.py` with typed log levels, resolved destination
  configuration, compact terminal formatting, 10 MiB UTF-8 rotating files with five backups,
  clean `OFF` handling, and duplicate-safe handler replacement.
- Extended `configuration.py` and `persistence/settings_store.py` with logging level,
  terminal/file toggles, optional file path, environment overlays, schema-6 persistence, and
  recoverable settings-load diagnostics.
- Expanded `main.py` with `--log-level`, `--log-file`, `--no-log-file`, `--terminal-log`, and
  `--no-terminal-log`; CLI values override environment/persisted defaults, and the default log is
  under the existing XDG state directory.
- Instrumented `application/session.py`, `application/scripted_game.py`, `commands/parser.py`,
  `commands/resolver.py`, `engine/factory.py`, `engine/stockfish.py`, `analysis/service.py`,
  `analysis/live.py`, `speech/controller.py`, `speech/factory.py`, `hardware/coordinator.py`, and
  the GUI application/engine/analysis/live-analysis/voice workers at meaningful processing and
  failure boundaries without changing gameplay behavior.
- Added `tests/unit/test_logging_config.py` for defaults, CLI parsing/errors/precedence, handler
  toggles, custom paths, parent creation, UTF-8 writes, filtering, `OFF`, repeated configuration,
  XDG defaults, and settings persistence; updated `README.md` with usage, levels, destinations,
  rotation, paths, and environment controls.

### Polish voice recognizer configuration modification record

- Extended `speech/config.py` so adapter settings can be resolved for the application's effective
  voice language, selecting a multilingual default model for Polish and automatic detection while
  retaining explicit `WIZARD_CHESS_VOICE_MODEL` overrides.
- Updated the PySide6 window's startup and live language-switch composition, plus CLI composition,
  so recognizer language/model settings cannot silently diverge from the session parser language.
- Added unit coverage for language-compatible default models and custom model overrides, plus a GUI
  regression covering saved Polish startup and English/Polish switching.
- Clarified automatic-detection model selection in `README.md`.

## Stage 3 hardware foundation

| Increment | Status | Delivered evidence |
| --- | --- | --- |
| Stage 3.1 — first hardware abstraction layer | Complete; physical acceptance deferred | Hardware-neutral immutable operation/result models; idealized board geometry; stable physical piece identity with known/unknown locations; immutable `PhysicalBoardState`; separate controller and synchronization state machines; pure simple-move planner with explicit capture/castling/en-passant/promotion rejection; narrow `HardwarePort`; deterministic `FakeHardware` lifecycle, trace, failure/timeout injection, stop, and E-stop; transaction-like `HardwareCoordinator`; placement-only reconciliation; canonical `MoveExecuted` integration; conservative Undo/New Game/FEN/PGN replacement notifications; adapter failure isolation and explicit shutdown. No serial, GPIO, motor, sensor, or physical device is claimed. |

Stage 3.1 added `hardware/models.py`, `errors.py`, `board_state.py`, `port.py`, `geometry.py`,
`planner.py`, `fake.py`, and `coordinator.py`; expanded the package exports and compatibility
simulator; integrated optional move, replacement, and close notifications in `GameSession`;
added four focused hardware test modules; and updated the README architecture and limitations.

## Verification record

The final verification commands for this increment are:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

Final clean run on 2026-08-25:

- `uv run pytest` — **323 passed**.
- `uv run ruff check .` — **passed**.
- `uv run ruff format --check .` — **95 files already formatted**.
- `uv run pyright` — **0 errors, 0 warnings**.
- `uv build --wheel --out-dir /tmp/wizard-chess-dist` — **passed**; the wheel contains the
  compressed Stockfish asset, manifest, GPLv3 text, authors, and upstream README.
- `uv run wizard-chess --script examples/game.txt` — completed Scholar's mate and produced
  the expected final FEN.
- Bundled Stockfish 18 — checksum validation and fresh XDG-cache extraction completed in 5.77
  seconds; a real `python-chess` UCI startup/cleanup handshake passed outside the restricted
  subprocess sandbox. Real streaming acceptance remains pending; deterministic streaming and
  cancellation adapters passed automatically.

Stage 3.1 clean run on 2026-08-26:

- `uv run pytest` — **360 passed**.
- `uv run ruff check .` — **passed**.
- `uv run ruff format --check .` — **107 files already formatted**.
- `uv run pyright` — **0 errors, 0 warnings**.
- No physical hardware acceptance was attempted; all controller behavior used deterministic
  in-memory fakes.

Human draw-offer and resignation controls clean run on 2026-08-26:

- `uv run pytest` — **389 passed**.
- `uv run ruff check .` — **passed**.
- `uv run ruff format --check .` — **108 files already formatted**.
- `uv run pyright` — **0 errors, 0 warnings**.

Configurable runtime logging clean run on 2026-08-28:

- `uv run pytest` — **405 passed**.
- `uv run ruff check .` — **passed**.
- `uv run ruff format --check .` — **110 files already formatted**.
- `uv run pyright` — **0 errors, 0 warnings**.
- Scripted launcher acceptance with isolated XDG directories confirmed simultaneous DEBUG file
  diagnostics, a custom nested log path with terminal output disabled, the default XDG-state log
  destination, clean checkmate/shutdown events, and `OFF` suppression without creating a file.

Polish voice recognizer configuration fix clean run on 2026-09-04:

- `uv run pytest` — **410 passed**.
- `uv run ruff check .` — **passed**.
- `uv run ruff format --check .` — **110 files already formatted**.
- `uv run pyright` — **0 errors, 0 warnings**.
- Real microphone/model acceptance remains pending; deterministic configuration and GUI switching
  paths passed automatically.

Commit preparation verification on 2026-10-09:

- Included the logging task instructions, canonical-guidance `CLAUDE.md` entry point,
  and `examples/am_kc.pgn` sample game alongside the recorded implementation changes.
- `uv run --no-sync python -m pytest` — **410 passed**.
- `uv run ruff check .` — **passed**.
- `uv run ruff format --check .` — **111 files already formatted**.
- `uv run --no-sync python -m pyright` — **0 errors, 0 warnings**.
- Validation used the existing Python 3.13.5 environment and a writable temporary uv cache;
  module invocation bypassed tool launchers referencing the checkout's previous location.

Manual acceptance still required on a machine with the relevant optional systems:

1. Start the GUI with a real configured Stockfish binary.
2. Verify live evaluation, MultiPV, engine-as-White and engine-as-Black, post-game analysis,
   cancellation/stale-result handling, and clean process shutdown.
3. Install the voice extra and exercise English and Polish commands using a microphone.
4. Verify recovery after terminating an autosave-enabled session.
5. Configure `/home/mkulejewski/.local/bin/stockfish` in Engine Preferences, select Stockfish
   as White with `strong_club` strength and 2.5 seconds, remember/reuse the setup, relaunch
   with only `uv run wizard-chess`, then repeat with Stockfish as Black.

### Local-only Stockfish executable — 2026-10-09

- Removed `src/wizard_chess/engine/bundled/stockfish-18/linux-x86_64/stockfish.xz`
  from Git tracking while preserving the local file.
- Added explicit `.gitignore` rules for compressed and extracted platform executables;
  retained the manifest, checksums, and licensing documents in Git.
- Updated `README.md` and `THIRD_PARTY_NOTICES.md` to describe local-only engine assets
  and Stockfish installation/selection for fresh checkouts.
- Existing commits still contain the previously tracked archive; no history rewrite was performed.
- Validation: **410 tests passed**, Ruff lint/format passed, and pyright reported **0 errors,
  0 warnings** using the existing environment and module-based pytest/pyright launchers.
- Confirmed the retained local archive matches its manifest checksum and is ignored by Git.

## Deferred stages

| Stage | Status | Boundary |
| --- | --- | --- |
| Stage 3.2 — physical-board implementation | Deferred | Serial transport and firmware, GPIO/motor drivers, real homing/calibration, XY carriage and electromagnet control, sensing/observed state, captures and special-move sequences, obstacle-aware paths, reconciliation, recovery movement, and hardware GUI controls remain outside Stage 3.1. They must implement or compose beneath the new hardware port/coordinator seam. |
| Online/cloud/multiplayer services | Deferred | Core gameplay remains local and has no account or network dependency. |
