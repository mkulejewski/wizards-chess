"""Game Setup dialog for starting one configured game."""

from collections.abc import Callable
from dataclasses import replace
from typing import ClassVar

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wizard_chess.configuration import (
    ApplicationSettings,
    ClockSettings,
    EngineStrength,
    PlayerKind,
    PlayerSettings,
)

EngineAvailabilityCheck = Callable[[str | None], bool]


class GameSetupDialog(QDialog):
    """Edit typed player, game-engine, clock, and startup choices."""

    engine_preferences_requested = Signal()
    _PRESETS: ClassVar[tuple[tuple[PlayerKind, PlayerKind], ...]] = (
        (PlayerKind.HUMAN, PlayerKind.HUMAN),
        (PlayerKind.HUMAN, PlayerKind.ENGINE),
        (PlayerKind.ENGINE, PlayerKind.HUMAN),
        (PlayerKind.ENGINE, PlayerKind.ENGINE),
    )

    def __init__(
        self,
        settings: ApplicationSettings,
        parent: QWidget | None = None,
        *,
        engine_available: EngineAvailabilityCheck | None = None,
    ) -> None:
        super().__init__(parent)
        self._base_settings = settings
        self._engine_available = engine_available
        self.setWindowTitle("Game Setup")
        self.setModal(True)
        self.setMinimumWidth(460)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Choose a preset…", None)
        self.preset_combo.addItem(
            "Human vs Human", (PlayerKind.HUMAN.value, PlayerKind.HUMAN.value)
        )
        self.preset_combo.addItem(
            "Human vs Stockfish", (PlayerKind.HUMAN.value, PlayerKind.ENGINE.value)
        )
        self.preset_combo.addItem(
            "Stockfish vs Human", (PlayerKind.ENGINE.value, PlayerKind.HUMAN.value)
        )
        self.preset_combo.addItem(
            "Stockfish vs Stockfish", (PlayerKind.ENGINE.value, PlayerKind.ENGINE.value)
        )

        self.white_player_combo = _player_combo()
        self.white_name_edit = QLineEdit()
        self.black_player_combo = _player_combo()
        self.black_name_edit = QLineEdit()

        self.strength_combo = QComboBox()
        for strength in EngineStrength:
            self.strength_combo.addItem(_strength_label(strength), strength.value)
        self.think_time_spin = QDoubleSpinBox()
        self.think_time_spin.setRange(0.05, 120.0)
        self.think_time_spin.setDecimals(2)
        self.think_time_spin.setSingleStep(0.25)
        self.think_time_spin.setSuffix(" s")

        self.clock_enabled_checkbox = QCheckBox("Use clock")
        self.initial_time_spin = QDoubleSpinBox()
        self.initial_time_spin.setRange(1.0, 86_400.0)
        self.initial_time_spin.setDecimals(0)
        self.initial_time_spin.setSuffix(" s")
        self.increment_spin = QDoubleSpinBox()
        self.increment_spin.setRange(0.0, 600.0)
        self.increment_spin.setDecimals(1)
        self.increment_spin.setSuffix(" s")

        self.remember_checkbox = QCheckBox("Remember these choices")
        self.auto_start_checkbox = QCheckBox("Start with this setup automatically next time")
        self.engine_preferences_button = QPushButton("Engine Preferences…")

        self._build_layout()
        self._load_settings(settings)
        self._connect_signals()
        self._update_engine_controls()
        self._update_clock_controls()
        self._update_remember_controls()

    @property
    def requires_engine(self) -> bool:
        """Return whether a selected player or live analysis requires Stockfish."""
        return (
            self._base_settings.engine.analysis_enabled
            or self._player_kind(self.white_player_combo) is PlayerKind.ENGINE
            or self._player_kind(self.black_player_combo) is PlayerKind.ENGINE
        )

    def selected_settings(self) -> ApplicationSettings:
        """Build a validated typed settings value without mutating persistence."""
        players = PlayerSettings(
            white_name=self.white_name_edit.text().strip() or "White",
            black_name=self.black_name_edit.text().strip() or "Black",
            white_kind=self._player_kind(self.white_player_combo),
            black_kind=self._player_kind(self.black_player_combo),
        )
        strength = EngineStrength(str(self.strength_combo.currentData()))
        engine = replace(
            self._base_settings.engine,
            strength=strength,
            analysis_time_ms=max(1, round(self.think_time_spin.value() * 1000)),
        )
        clock = ClockSettings(
            enabled=self.clock_enabled_checkbox.isChecked(),
            initial_seconds=self.initial_time_spin.value(),
            increment_seconds=self.increment_spin.value(),
        )
        remember = self.remember_checkbox.isChecked()
        return replace(
            self._base_settings,
            engine=engine,
            players=players,
            clock=clock,
            game_setup_saved=remember,
            show_game_setup_on_startup=(
                not self.auto_start_checkbox.isChecked() if remember else True
            ),
        ).with_required_engine()

    def set_engine_settings(self, settings: ApplicationSettings) -> None:
        """Refresh engine defaults after the nested Preferences workflow."""
        self._base_settings = replace(self._base_settings, engine=settings.engine)
        strength_index = self.strength_combo.findData(settings.engine.strength.value)
        self.strength_combo.setCurrentIndex(max(0, strength_index))
        self.think_time_spin.setValue(settings.engine.analysis_time_ms / 1000)
        self._update_engine_controls()

    def accept(self) -> None:
        """Keep the dialog open when an engine player has no resolvable executable."""
        if (
            self.requires_engine
            and self._engine_available is not None
            and not self._engine_available(self._base_settings.engine.path)
        ):
            QMessageBox.warning(
                self,
                "Stockfish unavailable",
                "Stockfish could not be found. Open Engine Preferences to choose an "
                "executable, or change the affected player to Human.",
            )
            return
        super().accept()

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        preset_row = QFormLayout()
        preset_row.addRow("Quick preset:", self.preset_combo)
        layout.addLayout(preset_row)

        players_row = QHBoxLayout()
        players_row.addWidget(_player_group("White", self.white_player_combo, self.white_name_edit))
        players_row.addWidget(_player_group("Black", self.black_player_combo, self.black_name_edit))
        layout.addLayout(players_row)

        self.engine_group = QGroupBox("Engine settings for this game")
        engine_form = QFormLayout(self.engine_group)
        engine_form.addRow("Strength:", self.strength_combo)
        engine_form.addRow("Think time:", self.think_time_spin)
        engine_form.addRow(self.engine_preferences_button)
        layout.addWidget(self.engine_group)

        clock_group = QGroupBox("Clock")
        clock_form = QFormLayout(clock_group)
        clock_form.addRow(self.clock_enabled_checkbox)
        clock_form.addRow("Initial time:", self.initial_time_spin)
        clock_form.addRow("Increment:", self.increment_spin)
        layout.addWidget(clock_group)

        layout.addWidget(self.remember_checkbox)
        layout.addWidget(self.auto_start_checkbox)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Start Game")
        layout.addWidget(self.button_box)

    def _load_settings(self, settings: ApplicationSettings) -> None:
        _select_player(self.white_player_combo, settings.players.white_kind)
        _select_player(self.black_player_combo, settings.players.black_kind)
        self.white_name_edit.setText(settings.players.white_name)
        self.black_name_edit.setText(settings.players.black_name)
        strength_index = self.strength_combo.findData(settings.engine.strength.value)
        self.strength_combo.setCurrentIndex(max(0, strength_index))
        self.think_time_spin.setValue(settings.engine.analysis_time_ms / 1000)
        self.clock_enabled_checkbox.setChecked(settings.clock.enabled)
        self.initial_time_spin.setValue(settings.clock.initial_seconds)
        self.increment_spin.setValue(settings.clock.increment_seconds)
        self.remember_checkbox.setChecked(True)
        self.auto_start_checkbox.setChecked(
            not settings.game_setup_saved or not settings.show_game_setup_on_startup
        )

    def _connect_signals(self) -> None:
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)
        self.white_player_combo.currentIndexChanged.connect(self._update_engine_controls)
        self.black_player_combo.currentIndexChanged.connect(self._update_engine_controls)
        self.clock_enabled_checkbox.toggled.connect(self._update_clock_controls)
        self.remember_checkbox.toggled.connect(self._update_remember_controls)
        self.engine_preferences_button.clicked.connect(self.engine_preferences_requested)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _apply_preset(self, index: int) -> None:
        if not 1 <= index <= len(self._PRESETS):
            return
        white, black = self._PRESETS[index - 1]
        _select_player(self.white_player_combo, white)
        _select_player(self.black_player_combo, black)

    def _update_engine_controls(self) -> None:
        self.engine_group.setEnabled(self.requires_engine)

    def _update_clock_controls(self) -> None:
        enabled = self.clock_enabled_checkbox.isChecked()
        self.initial_time_spin.setEnabled(enabled)
        self.increment_spin.setEnabled(enabled)

    def _update_remember_controls(self) -> None:
        remember = self.remember_checkbox.isChecked()
        self.auto_start_checkbox.setEnabled(remember)
        if not remember:
            self.auto_start_checkbox.setChecked(False)

    @staticmethod
    def _player_kind(combo: QComboBox) -> PlayerKind:
        return PlayerKind(str(combo.currentData()))


def _player_combo() -> QComboBox:
    combo = QComboBox()
    combo.addItem("Human", PlayerKind.HUMAN.value)
    combo.addItem("Stockfish", PlayerKind.ENGINE.value)
    return combo


def _select_player(combo: QComboBox, kind: PlayerKind) -> None:
    combo.setCurrentIndex(max(0, combo.findData(kind.value)))


def _player_group(title: str, player_combo: QComboBox, name_edit: QLineEdit) -> QGroupBox:
    group = QGroupBox(title)
    form = QFormLayout(group)
    form.addRow(QLabel("Player:"), player_combo)
    form.addRow(QLabel("Name:"), name_edit)
    return group


def _strength_label(strength: EngineStrength) -> str:
    return strength.value.replace("_", " ").title()
