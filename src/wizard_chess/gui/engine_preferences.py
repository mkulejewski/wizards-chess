"""Persistent Stockfish preferences dialog."""

from collections.abc import Callable
from dataclasses import replace

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wizard_chess.configuration import (
    ApplicationSettings,
    EngineAnalysisMode,
    EngineSettings,
    EngineStrength,
    StockfishPlayerMode,
)
from wizard_chess.engine.factory import validate_stockfish_engine

EngineValidator = Callable[[EngineSettings], None]


class EnginePreferencesDialog(QDialog):
    """Edit persistent engine defaults without changing the active game."""

    def __init__(
        self,
        settings: ApplicationSettings,
        parent: QWidget | None = None,
        *,
        validator: EngineValidator = validate_stockfish_engine,
    ) -> None:
        super().__init__(parent)
        self._base_settings = settings
        self._validator = validator
        self.setWindowTitle("Engine Preferences")
        self.setModal(True)
        self.setMinimumWidth(520)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Automatic: bundled Stockfish, then system PATH")
        self.browse_button = QPushButton("Browse…")
        self.test_button = QPushButton("Test Engine")

        self.strength_combo = QComboBox()
        for strength in EngineStrength:
            self.strength_combo.addItem(strength.value.replace("_", " ").title(), strength.value)
        self.think_time_spin = QDoubleSpinBox()
        self.think_time_spin.setRange(0.05, 120.0)
        self.think_time_spin.setDecimals(2)
        self.think_time_spin.setSingleStep(0.25)
        self.think_time_spin.setSuffix(" s")
        self.post_game_time_spin = QDoubleSpinBox()
        self.post_game_time_spin.setRange(0.05, 120.0)
        self.post_game_time_spin.setDecimals(2)
        self.post_game_time_spin.setSingleStep(0.25)
        self.post_game_time_spin.setSuffix(" s per position")
        self.player_mode_combo = QComboBox()
        self.player_mode_combo.addItem(
            "Fixed analysis time per move",
            StockfishPlayerMode.FIXED_ANALYSIS_TIME.value,
        )
        self.player_mode_combo.addItem(
            "Game-clock time management",
            StockfishPlayerMode.GAME_CLOCK.value,
        )
        self.analysis_mode_combo = QComboBox()
        self.analysis_mode_combo.addItem("Disabled", EngineAnalysisMode.OFF.value)
        self.analysis_mode_combo.addItem(
            "Fixed time per displayed position",
            EngineAnalysisMode.FIXED_TIME.value,
        )
        self.analysis_mode_combo.addItem(
            "Continuous live analysis",
            EngineAnalysisMode.LIVE.value,
        )
        self.live_depth_spin = QSpinBox()
        self.live_depth_spin.setRange(1, 100)

        self.multipv_spin = QSpinBox()
        self.multipv_spin.setRange(1, 20)
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(0, 100)
        self.depth_spin.setSpecialValueText("Automatic")
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 256)
        self.hash_spin = QSpinBox()
        self.hash_spin.setRange(1, 1_048_576)
        self.hash_spin.setSuffix(" MB")
        self.syzygy_path_edit = QLineEdit()
        self.syzygy_path_edit.setPlaceholderText("Optional local Syzygy directory")
        self.syzygy_browse_button = QPushButton("Choose…")
        self.syzygy_clear_button = QPushButton("Clear")
        self.syzygy_probe_limit_spin = QSpinBox()
        self.syzygy_probe_limit_spin.setRange(0, 7)
        self.syzygy_50_move_rule_checkbox = QCheckBox("Respect the 50-move rule")

        self._build_layout()
        self._load_settings(settings.engine)
        self.browse_button.clicked.connect(self._browse)
        self.syzygy_browse_button.clicked.connect(self._browse_syzygy)
        self.syzygy_clear_button.clicked.connect(self.syzygy_path_edit.clear)
        self.test_button.clicked.connect(self._test_engine)
        self.player_mode_combo.currentIndexChanged.connect(self._update_mode_controls)
        self.analysis_mode_combo.currentIndexChanged.connect(self._update_mode_controls)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def selected_settings(self) -> ApplicationSettings:
        """Build typed persistent preferences from the current widget values."""
        analysis_mode = EngineAnalysisMode(str(self.analysis_mode_combo.currentData()))
        engine = EngineSettings(
            enabled=(
                self._base_settings.engine.enabled or analysis_mode is not EngineAnalysisMode.OFF
            ),
            path=self.path_edit.text().strip() or None,
            analysis_mode=analysis_mode,
            analysis_enabled=analysis_mode is not EngineAnalysisMode.OFF,
            live_analysis_max_depth=self.live_depth_spin.value(),
            player_mode=StockfishPlayerMode(str(self.player_mode_combo.currentData())),
            player_move_analysis_time_ms=max(1, round(self.think_time_spin.value() * 1000)),
            post_game_analysis_time_ms=max(1, round(self.post_game_time_spin.value() * 1000)),
            analysis_depth=self.depth_spin.value() or None,
            multipv=self.multipv_spin.value(),
            strength=EngineStrength(str(self.strength_combo.currentData())),
            threads=self.threads_spin.value(),
            hash_mb=self.hash_spin.value(),
            syzygy_path=self.syzygy_path_edit.text().strip() or None,
            syzygy_probe_limit=self.syzygy_probe_limit_spin.value(),
            syzygy_50_move_rule=self.syzygy_50_move_rule_checkbox.isChecked(),
        )
        return replace(self._base_settings, engine=engine).with_required_engine()

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        path_form = QFormLayout()
        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(self.browse_button)
        path_form.addRow(QLabel("Stockfish executable:"), path_row)
        path_form.addRow(self.test_button)
        layout.addLayout(path_form)

        defaults_group = QGroupBox("Defaults")
        defaults_form = QFormLayout(defaults_group)
        defaults_form.addRow("Strength:", self.strength_combo)
        defaults_form.addRow("Stockfish player mode:", self.player_mode_combo)
        defaults_form.addRow("Fixed bot analysis time:", self.think_time_spin)
        defaults_form.addRow("After-game analysis time:", self.post_game_time_spin)
        defaults_form.addRow("Displayed-position analysis:", self.analysis_mode_combo)
        defaults_form.addRow("Live maximum depth:", self.live_depth_spin)
        layout.addWidget(defaults_group)

        advanced_group = QGroupBox("Advanced")
        advanced_form = QFormLayout(advanced_group)
        advanced_form.addRow("MultiPV:", self.multipv_spin)
        advanced_form.addRow("Depth:", self.depth_spin)
        advanced_form.addRow("Threads:", self.threads_spin)
        advanced_form.addRow("Hash size:", self.hash_spin)
        layout.addWidget(advanced_group)

        syzygy_group = QGroupBox("Syzygy tablebases")
        syzygy_form = QFormLayout(syzygy_group)
        syzygy_path_row = QHBoxLayout()
        syzygy_path_row.addWidget(self.syzygy_path_edit, 1)
        syzygy_path_row.addWidget(self.syzygy_browse_button)
        syzygy_path_row.addWidget(self.syzygy_clear_button)
        syzygy_form.addRow("Directory:", syzygy_path_row)
        syzygy_form.addRow("Probe limit:", self.syzygy_probe_limit_spin)
        syzygy_form.addRow(self.syzygy_50_move_rule_checkbox)
        layout.addWidget(syzygy_group)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(self.button_box)

    def _load_settings(self, settings: EngineSettings) -> None:
        self.path_edit.setText(settings.path or "")
        self.strength_combo.setCurrentIndex(
            max(0, self.strength_combo.findData(settings.strength.value))
        )
        self.player_mode_combo.setCurrentIndex(
            max(0, self.player_mode_combo.findData(settings.player_mode.value))
        )
        self.think_time_spin.setValue(settings.player_move_analysis_time_ms / 1000)
        self.post_game_time_spin.setValue(settings.post_game_analysis_time_ms / 1000)
        self.analysis_mode_combo.setCurrentIndex(
            max(0, self.analysis_mode_combo.findData(settings.analysis_mode.value))
        )
        self.live_depth_spin.setValue(settings.live_analysis_max_depth)
        self.multipv_spin.setValue(settings.multipv)
        self.depth_spin.setValue(settings.analysis_depth or 0)
        self.threads_spin.setValue(settings.threads)
        self.hash_spin.setValue(settings.hash_mb)
        self.syzygy_path_edit.setText(settings.syzygy_path or "")
        self.syzygy_probe_limit_spin.setValue(settings.syzygy_probe_limit)
        self.syzygy_50_move_rule_checkbox.setChecked(settings.syzygy_50_move_rule)
        self._update_mode_controls()

    def _browse(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Select Stockfish executable",
            self.path_edit.text(),
            "Executables (*)",
        )
        if path:
            self.path_edit.setText(path)

    def _browse_syzygy(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Syzygy tablebase directory",
            self.syzygy_path_edit.text(),
        )
        if path:
            self.syzygy_path_edit.setText(path)

    def _update_mode_controls(self) -> None:
        self.think_time_spin.setEnabled(
            self.player_mode_combo.currentData() == StockfishPlayerMode.FIXED_ANALYSIS_TIME.value
        )
        self.live_depth_spin.setEnabled(
            self.analysis_mode_combo.currentData() == EngineAnalysisMode.LIVE.value
        )

    def _test_engine(self) -> None:
        try:
            self._validator(self.selected_settings().engine)
        except Exception as error:  # Adapter failures are always presented as configuration errors.
            QMessageBox.warning(self, "Engine test failed", str(error))
            return
        QMessageBox.information(
            self,
            "Engine test successful",
            "Stockfish started successfully and the temporary process was closed.",
        )
