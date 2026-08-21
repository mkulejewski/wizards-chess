# Wizard Chess contributor guide

Wizard Chess uses Python 3.12, `uv`, a `src/` package layout, and `python-chess` as the
only source of chess rules.

Keep these architectural boundaries intact:

- `domain` owns authoritative game state and application-level chess values/events.
- `commands` turns text into intents and resolves them without owning state.
- `application` coordinates commands, domain mutation, and hardware events for every UI.
- `gui` is a PySide6 adapter and must render from authoritative application/domain snapshots.
- `speech` and `hardware` are replaceable adapters. Domain code must not import them.
- `persistence` owns filesystem access; the domain only renders PGN text.
- `main.py` is composition and GUI/CLI entry-point selection, not business logic.

Before completing a change, run:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

PySide6 is the sole approved GUI framework for the Stage 1.1B desktop adapter. Do not add
other GUI frameworks, audio, engine-analysis, serial, motor, sensor, or network dependencies
without an explicit later project-stage requirement.
