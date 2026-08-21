"""Qt chessboard renderer driven entirely by session snapshots."""

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from wizard_chess.application.session import PositionSnapshot
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


class ChessBoardWidget(QWidget):
    """Paint a square chessboard and report clicks as chess coordinates."""

    square_clicked = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(360, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._pieces: dict[str, str] = {}
        self._selected: str | None = None
        self._legal_destinations: set[str] = set()
        self._last_move: tuple[str, str] | None = None
        self._orientation = BoardOrientation.WHITE

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
    def last_move_squares(self) -> tuple[str, str] | None:
        """Expose the authoritative last-move highlight for widget-state tests."""
        return self._last_move

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        offset_x, offset_y, board_size = self._board_geometry()
        cell_size = board_size / 8

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

        painter.setPen(QPen(QColor("#3c3228"), 2))
        painter.drawRect(QRectF(offset_x, offset_y, board_size, board_size))
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
        color = QColor("#f0d9b5" if (file_index + rank_index) % 2 else "#b58863")
        if self._last_move is not None and square in self._last_move:
            color = QColor("#d8c85a")
        if square == self._selected:
            color = QColor("#83b86c")
        painter.fillRect(rectangle, color)

        if square in self._legal_destinations:
            painter.save()
            painter.setBrush(QColor("#4f7f46"))
            painter.setPen(Qt.PenStyle.NoPen)
            radius = cell_size * 0.12
            center = rectangle.center()
            painter.drawEllipse(
                QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
            )
            painter.restore()

        symbol = self._pieces.get(square)
        if symbol is not None:
            font = QFont("DejaVu Sans")
            font.setPixelSize(max(18, int(cell_size * 0.7)))
            painter.setFont(font)
            painter.setPen(QColor("#181512"))
            painter.drawText(rectangle, Qt.AlignmentFlag.AlignCenter, _PIECES[symbol])

        label_font = QFont()
        label_font.setPixelSize(max(8, int(cell_size * 0.14)))
        painter.setFont(label_font)
        painter.setPen(QColor("#40372e"))
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

    def _board_geometry(self) -> tuple[float, float, float]:
        board_size = float(min(self.width(), self.height()) - 4)
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
