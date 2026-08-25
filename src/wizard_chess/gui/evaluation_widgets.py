"""Compact in-window widgets for live evaluation and post-game history."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from wizard_chess.analysis.live import LiveAnalysisResult
from wizard_chess.analysis.models import GameAnalysis
from wizard_chess.engine.models import EngineEvaluation, evaluation_share

MATE_PLOT_VALUE = 10.0


def evaluation_plot_value(evaluation: EngineEvaluation) -> float:
    """Convert canonical evaluations to bounded pawn units only for plotting."""
    if evaluation.mate_in is not None:
        return MATE_PLOT_VALUE if evaluation.mate_in >= 0 else -MATE_PLOT_VALUE
    assert evaluation.score_cp is not None
    return max(-MATE_PLOT_VALUE, min(MATE_PLOT_VALUE, evaluation.score_cp / 100.0))


def game_analysis_evaluations(
    analysis: GameAnalysis,
) -> tuple[EngineEvaluation | None, ...]:
    """Return initial-through-final evaluations from one completed game analysis."""
    if not analysis.moves:
        return ()
    return (
        analysis.moves[0].evaluation_before,
        *(move.evaluation_after for move in analysis.moves),
    )


class EvaluationSidebar(QWidget):
    """Paint a flicker-free vertical White/Black evaluation split."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(72)
        self.setMaximumWidth(92)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setAccessibleName("Live engine evaluation")
        self._result: LiveAnalysisResult | None = None
        self._status = "—"

    @property
    def result(self) -> LiveAnalysisResult | None:
        return self._result

    @property
    def white_share(self) -> float:
        return evaluation_share(self._result.evaluation if self._result is not None else None)

    def value(self) -> int:
        """Return a 0..1000 value for compatibility and deterministic tests."""
        return round(self.white_share * 1000)

    def format(self) -> str:
        return f"Evaluation: {self._status}"

    def set_result(self, result: LiveAnalysisResult) -> None:
        self._result = result
        self._status = result.evaluation.display()
        self.setToolTip(
            f"White-perspective evaluation {self._status}, depth {result.depth}, ply {result.ply}"
        )
        self.update()

    def clear(self, status: str = "—") -> None:
        self._result = None
        self._status = status
        self.setToolTip(status)
        self.update()

    def set_unavailable(self) -> None:
        self.clear("unavailable")

    def sizeHint(self) -> QSize:
        return QSize(78, 520)

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#171717"))
        width = float(self.width())
        height = float(self.height())
        top = 30.0
        bottom = max(top + 40.0, height - 72.0)
        bar = QRectF(15.0, top, max(22.0, width - 30.0), bottom - top)

        painter.fillRect(bar, QColor("#222222"))
        white_height = bar.height() * self.white_share
        painter.fillRect(
            QRectF(bar.left(), bar.bottom() - white_height, bar.width(), white_height),
            QColor("#f1f0e8"),
        )
        divider_y = bar.bottom() - white_height
        painter.setPen(QPen(QColor("#c79b3b"), 2.0))
        painter.drawLine(QPointF(bar.left(), divider_y), QPointF(bar.right(), divider_y))
        painter.setPen(QPen(QColor("#737373"), 1.0))
        painter.drawRect(bar)

        label_font = QFont()
        label_font.setBold(True)
        label_font.setPixelSize(12)
        painter.setFont(label_font)
        painter.setPen(QColor("#f1f0e8"))
        painter.drawText(QRectF(0.0, 5.0, width, 20.0), Qt.AlignmentFlag.AlignCenter, "Black")
        painter.drawText(
            QRectF(0.0, bottom + 2.0, width, 20.0), Qt.AlignmentFlag.AlignCenter, "White"
        )

        score_font = QFont()
        score_font.setBold(True)
        score_font.setPixelSize(13)
        painter.setFont(score_font)
        painter.drawText(
            QRectF(0.0, height - 45.0, width, 20.0),
            Qt.AlignmentFlag.AlignCenter,
            self._status,
        )
        if self._result is not None:
            depth_text = f"depth {self._result.depth}" if self._result.depth else "terminal"
            painter.setFont(QFont())
            painter.drawText(
                QRectF(0.0, height - 25.0, width, 18.0),
                Qt.AlignmentFlag.AlignCenter,
                depth_text,
            )
        painter.end()


class EvaluationGraph(QWidget):
    """Plot completed post-game evaluations and navigate by clicked ply."""

    ply_selected = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(145)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName("Post-game evaluation history")
        self._values: tuple[float | None, ...] = ()
        self._current_ply = 0

    @property
    def values(self) -> tuple[float | None, ...]:
        return self._values

    @property
    def current_ply(self) -> int:
        return self._current_ply

    def set_evaluations(
        self,
        evaluations: tuple[EngineEvaluation | None, ...],
        current_ply: int,
    ) -> None:
        self._values = tuple(
            evaluation_plot_value(evaluation) if evaluation is not None else None
            for evaluation in evaluations
        )
        self._current_ply = max(0, min(current_ply, max(0, len(self._values) - 1)))
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(640, 160)

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f4f1e8"))
        plot = self._plot_rect()
        painter.setPen(QPen(QColor("#786d5c"), 1.0))
        painter.drawRect(plot)
        zero_y = plot.center().y()
        zero_pen = QPen(QColor("#6e6e6e"), 1.0, Qt.PenStyle.DashLine)
        painter.setPen(zero_pen)
        painter.drawLine(QPointF(plot.left(), zero_y), QPointF(plot.right(), zero_y))

        painter.setPen(QColor("#333333"))
        painter.drawText(QRectF(4.0, 2.0, 110.0, 18.0), "White advantage")
        painter.drawText(
            QRectF(4.0, float(self.height()) - 20.0, 110.0, 18.0),
            "Black advantage",
        )
        if not self._values:
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, "No post-game evaluations")
            painter.end()
            return

        maximum = max(
            3.0,
            min(
                MATE_PLOT_VALUE,
                max(
                    (abs(value) for value in self._values if value is not None),
                    default=0.0,
                ),
            ),
        )
        previous: QPointF | None = None
        line_pen = QPen(QColor("#2c6e49"), 2.0)
        missing_pen = QPen(QColor("#9a9184"), 1.0)
        for ply, value in enumerate(self._values):
            x = self._x_for_ply(ply, plot)
            if value is None:
                previous = None
                painter.setPen(missing_pen)
                painter.drawLine(QPointF(x - 2.5, zero_y - 2.5), QPointF(x + 2.5, zero_y + 2.5))
                painter.drawLine(QPointF(x - 2.5, zero_y + 2.5), QPointF(x + 2.5, zero_y - 2.5))
                continue
            y = zero_y - (value / maximum) * plot.height() / 2.0
            point = QPointF(x, y)
            painter.setPen(line_pen)
            if previous is not None:
                painter.drawLine(previous, point)
            painter.setBrush(QColor("#2c6e49"))
            painter.drawEllipse(point, 2.5, 2.5)
            previous = point

        marker_x = self._x_for_ply(self._current_ply, plot)
        painter.setPen(QPen(QColor("#c0442c"), 1.5))
        painter.drawLine(QPointF(marker_x, plot.top()), QPointF(marker_x, plot.bottom()))
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton and self._values:
            plot = self._plot_rect()
            fraction = (event.position().x() - plot.left()) / max(1.0, plot.width())
            ply = round(max(0.0, min(1.0, fraction)) * (len(self._values) - 1))
            self.ply_selected.emit(ply)
        super().mousePressEvent(event)

    def _plot_rect(self) -> QRectF:
        return QRectF(
            118.0,
            20.0,
            max(20.0, float(self.width()) - 132.0),
            max(30.0, float(self.height()) - 42.0),
        )

    def _x_for_ply(self, ply: int, plot: QRectF) -> float:
        denominator = max(1, len(self._values) - 1)
        return plot.left() + plot.width() * ply / denominator
