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

from wizard_chess.configuration import ApplicationSettings, EngineSettings, EngineStrength
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
        self.path_edit.setPlaceholderText("Discover stockfish on PATH")
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
        self.live_analysis_checkbox = QCheckBox("Enable live analysis")

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

        self._build_layout()
        self._load_settings(settings.engine)
        self.browse_button.clicked.connect(self._browse)
        self.test_button.clicked.connect(self._test_engine)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def selected_settings(self) -> ApplicationSettings:
        """Build typed persistent preferences from the current widget values."""
        engine = EngineSettings(
            enabled=(self._base_settings.engine.enabled or self.live_analysis_checkbox.isChecked()),
            path=self.path_edit.text().strip() or None,
            analysis_enabled=self.live_analysis_checkbox.isChecked(),
            analysis_time_ms=max(1, round(self.think_time_spin.value() * 1000)),
            analysis_depth=self.depth_spin.value() or None,
            multipv=self.multipv_spin.value(),
            strength=EngineStrength(str(self.strength_combo.currentData())),
            threads=self.threads_spin.value(),
            hash_mb=self.hash_spin.value(),
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
        defaults_form.addRow("Think time:", self.think_time_spin)
        defaults_form.addRow(self.live_analysis_checkbox)
        layout.addWidget(defaults_group)

        advanced_group = QGroupBox("Advanced")
        advanced_form = QFormLayout(advanced_group)
        advanced_form.addRow("MultiPV:", self.multipv_spin)
        advanced_form.addRow("Depth:", self.depth_spin)
        advanced_form.addRow("Threads:", self.threads_spin)
        advanced_form.addRow("Hash size:", self.hash_spin)
        layout.addWidget(advanced_group)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(self.button_box)

    def _load_settings(self, settings: EngineSettings) -> None:
        self.path_edit.setText(settings.path or "")
        self.strength_combo.setCurrentIndex(
            max(0, self.strength_combo.findData(settings.strength.value))
        )
        self.think_time_spin.setValue(settings.analysis_time_ms / 1000)
        self.live_analysis_checkbox.setChecked(settings.analysis_enabled)
        self.multipv_spin.setValue(settings.multipv)
        self.depth_spin.setValue(settings.analysis_depth or 0)
        self.threads_spin.setValue(settings.threads)
        self.hash_spin.setValue(settings.hash_mb)

    def _browse(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Select Stockfish executable",
            self.path_edit.text(),
            "Executables (*)",
        )
        if path:
            self.path_edit.setText(path)

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
