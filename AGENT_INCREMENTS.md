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

## Verification record

The final verification commands for this increment are:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

Final clean run on 2026-08-24:

- `uv run pytest` — **296 passed**.
- `uv run ruff check .` — **passed**.
- `uv run ruff format --check .` — **88 files already formatted**.
- `uv run pyright` — **0 errors, 0 warnings**.
- `uv run wizard-chess --script examples/game.txt` — completed Scholar's mate and produced
  the expected final FEN.
- Installed Stockfish — validation handshake passed; an offscreen GUI session produced `e4`
  through canonical event `e2e4` as White and closed cleanly.

Manual acceptance still required on a machine with the relevant optional systems:

1. Start the GUI with a real configured Stockfish binary.
2. Verify live evaluation, MultiPV, engine-as-White and engine-as-Black, post-game analysis,
   cancellation/stale-result handling, and clean process shutdown.
3. Install the voice extra and exercise English and Polish commands using a microphone.
4. Verify recovery after terminating an autosave-enabled session.
5. Configure `/home/mkulejewski/.local/bin/stockfish` in Engine Preferences, select Stockfish
   as White with `strong_club` strength and 2.5 seconds, remember/reuse the setup, relaunch
   with only `uv run wizard-chess`, then repeat with Stockfish as Black.

## Deferred stages

| Stage | Status | Boundary |
| --- | --- | --- |
| Stage 3 — physical-board integration | Deferred | Serial/GPIO, motor drivers, XY carriage, electromagnet, sensors, captures, calibration, and physical path planning are explicitly not part of Stage 2.x. They must consume the canonical application move-event seam. |
| Online/cloud/multiplayer services | Deferred | Core gameplay remains local and has no account or network dependency. |
