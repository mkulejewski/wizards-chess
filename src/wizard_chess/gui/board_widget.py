"""Qt chessboard renderer driven entirely by session snapshots."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QSizePolicy, QWidget

from wizard_chess.application.session import PositionSnapshot
from wizard_chess.configuration import AppearanceSettings, BoardTheme, PieceSet
from wizard_chess.gui.interaction import BoardOrientation, square_for_cell

_PIECES = {
    "K": "♔",
    "Q": "♕",
    "R": "♖",
    "B": "♗",
    "N": "♘",
    "P": "♙",
    "k": "♚",
    "q": "♛",
    "r": "♜",
    "b": "♝",
    "n": "♞",
    "p": "♟",
}

_PIECE_ASSET_ROOT = Path(__file__).with_name("assets") / "pieces"


@dataclass(frozen=True, slots=True)
class BoardPalette:
    """Paint values for one board look."""

    light: str
    dark: str
    frame: str
    surround: str


BOARD_PALETTES = {
    BoardTheme.WALNUT: BoardPalette("#e2c79b", "#8a5a3b", "#503321", "#201812"),
    BoardTheme.BROWN: BoardPalette("#f0d9b5", "#b58863", "#6d4d35", "#2b211b"),
    BoardTheme.GREEN: BoardPalette("#e8edcf", "#779556", "#4b6035", "#182016"),
    BoardTheme.BLUE: BoardPalette("#dee3e6", "#8295a5", "#4a5b68", "#172029"),
    BoardTheme.SLATE: BoardPalette("#d8dce3", "#657080", "#383f49", "#15181d"),
}


class ChessBoardWidget(QWidget):
    """Paint a square chessboard and report clicks as chess coordinates."""

    square_clicked = Signal(str)

    def __init__(self, appearance: AppearanceSettings | None = None) -> None:
        super().__init__()
        selected_appearance = appearance or AppearanceSettings()
        self.setMinimumSize(360, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self._pieces: dict[str, str] = {}
        self._selected: str | None = None
        self._legal_destinations: set[str] = set()
        self._last_move: tuple[str, str] | None = None
        self._orientation = BoardOrientation.WHITE
        self._piece_set = selected_appearance.piece_set
        self._board_theme = selected_appearance.board_theme
        self._piece_renderers: dict[str, QSvgRenderer] = {}

    def sizeHint(self) -> QSize:
        return QSize(640, 640)

    def render_position(
        self,
        snapshot: PositionSnapshot,
        selected: str | None,
        legal_destinations: tuple[str, ...],
        orientation: BoardOrientation,
    ) -> None:
        """Replace presentation data from one authoritative snapshot and repaint."""
        self._pieces = dict(snapshot.pieces)
        self._selected = selected
        self._legal_destinations = set(legal_destinations)
        self._orientation = orientation
        self._last_move = (
            (snapshot.last_move.source, snapshot.last_move.target)
            if snapshot.last_move is not None
            else None
        )
        self.update()

    def piece_at(self, square: str) -> str | None:
        """Expose rendered piece data for meaningful widget-state tests."""
        return self._pieces.get(square.lower())

    def displayed_square(self, row: int, column: int) -> str:
        """Expose current orientation mapping for widget-state tests."""
        return square_for_cell(row, column, self._orientation)

    @property
    def piece_set(self) -> PieceSet:
        """Return the active presentation-only piece artwork choice."""
        return self._piece_set

    @property
    def board_theme(self) -> BoardTheme:
        """Return the active presentation-only board palette."""
        return self._board_theme

    @property
    def last_move_squares(self) -> tuple[str, str] | None:
        """Expose the authoritative last-move highlight for widget-state tests."""
        return self._last_move

    def set_appearance(self, appearance: AppearanceSettings) -> None:
        """Apply a new local board look without changing position data."""
        if appearance.piece_set is not self._piece_set:
            self._piece_renderers.clear()
        self._piece_set = appearance.piece_set
        self._board_theme = appearance.board_theme
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        palette = BOARD_PALETTES[self._board_theme]
        painter.fillRect(self.rect(), QColor(palette.surround))
        offset_x, offset_y, board_size = self._board_geometry()
        cell_size = board_size / 8
        board_rectangle = QRectF(offset_x, offset_y, board_size, board_size)
        corner_radius = max(4.0, cell_size * 0.055)

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 100))
        painter.drawRoundedRect(
            board_rectangle.translated(0, max(2.0, cell_size * 0.045)),
            corner_radius,
            corner_radius,
        )
        painter.restore()

        board_clip = QPainterPath()
        board_clip.addRoundedRect(board_rectangle, corner_radius, corner_radius)
        painter.save()
        painter.setClipPath(board_clip)

        for row in range(8):
            for column in range(8):
                square = square_for_cell(row, column, self._orientation)
                rectangle = QRectF(
                    offset_x + column * cell_size,
                    offset_y + row * cell_size,
                    cell_size,
                    cell_size,
                )
                self._paint_square(painter, rectangle, square, row, column, cell_size)
        painter.restore()

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(palette.frame), max(1.5, cell_size * 0.025)))
        painter.drawRoundedRect(board_rectangle, corner_radius, corner_radius)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            cell = self._cell_at(event.position())
            if cell is not None:
                self.square_clicked.emit(square_for_cell(*cell, self._orientation))
        super().mousePressEvent(event)

    def _paint_square(
        self,
        painter: QPainter,
        rectangle: QRectF,
        square: str,
        row: int,
        column: int,
        cell_size: float,
    ) -> None:
        file_index = ord(square[0]) - ord("a")
        rank_index = int(square[1]) - 1
        palette = BOARD_PALETTES[self._board_theme]
        is_light = bool((file_index + rank_index) % 2)
        color = QColor(palette.light if is_light else palette.dark)
        painter.fillRect(rectangle, color)
        if self._last_move is not None and square in self._last_move:
            painter.fillRect(rectangle, QColor(246, 203, 67, 125))
        if square == self._selected:
            painter.fillRect(rectangle, QColor(74, 176, 120, 150))

        if square in self._legal_destinations:
            painter.save()
            marker = QColor(24, 36, 28, 105)
            center = rectangle.center()
            if square in self._pieces:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(marker, max(3.0, cell_size * 0.075)))
                inset = cell_size * 0.08
                painter.drawEllipse(rectangle.adjusted(inset, inset, -inset, -inset))
            else:
                painter.setBrush(marker)
                painter.setPen(Qt.PenStyle.NoPen)
                radius = cell_size * 0.115
                painter.drawEllipse(
                    QRectF(
                        center.x() - radius,
                        center.y() - radius,
                        radius * 2,
                        radius * 2,
                    )
                )
            painter.restore()

        symbol = self._pieces.get(square)
        if symbol is not None:
            self._paint_piece(painter, rectangle, symbol, cell_size)

        label_font = QFont()
        label_font.setBold(True)
        label_font.setPixelSize(max(8, int(cell_size * 0.14)))
        painter.setFont(label_font)
        painter.setPen(self._coordinate_color(is_light))
        if row == 7:
            painter.drawText(
                rectangle.adjusted(3, 0, -3, -2),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
                square[0],
            )
        if column == 0:
            painter.drawText(
                rectangle.adjusted(3, 2, -3, 0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                square[1],
            )

    def _paint_piece(
        self,
        painter: QPainter,
        rectangle: QRectF,
        symbol: str,
        cell_size: float,
    ) -> None:
        if self._piece_set is PieceSet.TATIANA:
            renderer = self._renderer_for(symbol)
            if renderer is not None:
                inset = cell_size * 0.025
                renderer.render(painter, rectangle.adjusted(inset, inset, -inset, -inset))
                return
        self._paint_classic_symbol(painter, rectangle, symbol, cell_size)

    def _renderer_for(self, symbol: str) -> QSvgRenderer | None:
        asset_name = f"{'w' if symbol.isupper() else 'b'}{symbol.upper()}"
        renderer = self._piece_renderers.get(asset_name)
        if renderer is None:
            asset_path = _PIECE_ASSET_ROOT / self._piece_set.value / f"{asset_name}.svg"
            renderer = QSvgRenderer(str(asset_path))
            if not renderer.isValid():
                return None
            self._piece_renderers[asset_name] = renderer
        return renderer

    @staticmethod
    def _paint_classic_symbol(
        painter: QPainter,
        rectangle: QRectF,
        symbol: str,
        cell_size: float,
    ) -> None:
        font = QFont("DejaVu Sans")
        font.setPixelSize(max(18, int(cell_size * 0.73)))
        path = QPainterPath()
        path.addText(0, 0, font, _PIECES[symbol])
        bounds = path.boundingRect()

        painter.save()
        painter.translate(
            rectangle.center().x() - bounds.center().x(),
            rectangle.center().y() - bounds.center().y(),
        )
        if symbol.isupper():
            painter.setBrush(QColor("#f7f3e8"))
            painter.setPen(QPen(QColor("#24211e"), max(1.0, cell_size * 0.018)))
        else:
            painter.setBrush(QColor("#2a2928"))
            painter.setPen(QPen(QColor("#11100f"), max(1.0, cell_size * 0.018)))
        painter.drawPath(path)
        painter.restore()

    def _coordinate_color(self, is_light: bool) -> QColor:
        palette = BOARD_PALETTES[self._board_theme]
        color = QColor(palette.dark if is_light else palette.light)
        color.setAlpha(215)
        return color

    def _board_geometry(self) -> tuple[float, float, float]:
        board_size = float(max(0, min(self.width(), self.height()) - 18))
        return (self.width() - board_size) / 2, (self.height() - board_size) / 2, board_size

    def _cell_at(self, position: QPointF) -> tuple[int, int] | None:
        offset_x, offset_y, board_size = self._board_geometry()
        if not (
            offset_x <= position.x() < offset_x + board_size
            and offset_y <= position.y() < offset_y + board_size
        ):
            return None
        cell_size = board_size / 8
        return int((position.y() - offset_y) / cell_size), int(
            (position.x() - offset_x) / cell_size
        )
