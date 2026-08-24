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

## Verification record

The final verification commands for this increment are:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

Final clean run on 2026-08-24:

- `uv run pytest` — **267 passed**.
- `uv run ruff check .` — **passed**.
- `uv run ruff format --check .` — **81 files already formatted**.
- `uv run pyright` — **0 errors, 0 warnings**.
- `uv run wizard-chess --script examples/game.txt` — completed Scholar's mate and produced
  the expected final FEN.

Manual acceptance still required on a machine with the relevant optional systems:

1. Start the GUI with a real configured Stockfish binary.
2. Verify live evaluation, MultiPV, engine-as-White and engine-as-Black, post-game analysis,
   cancellation/stale-result handling, and clean process shutdown.
3. Install the voice extra and exercise English and Polish commands using a microphone.
4. Verify recovery after terminating an autosave-enabled session.

## Deferred stages

| Stage | Status | Boundary |
| --- | --- | --- |
| Stage 3 — physical-board integration | Deferred | Serial/GPIO, motor drivers, XY carriage, electromagnet, sensors, captures, calibration, and physical path planning are explicitly not part of Stage 2.x. They must consume the canonical application move-event seam. |
| Online/cloud/multiplayer services | Deferred | Core gameplay remains local and has no account or network dependency. |
