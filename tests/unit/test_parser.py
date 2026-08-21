import pytest

from wizard_chess.commands.intents import CommandIntent, CommandName, MoveIntent, SanMoveIntent
from wizard_chess.commands.parser import CommandParser
from wizard_chess.domain.exceptions import InvalidCommandError


@pytest.mark.parametrize(
    "text",
    ["e2 e4", "E2 E4", "e2-e4", "e2 to e4", "move e2 to e4", "  E2   to   E4  "],
)
def test_parser_accepts_coordinate_variants(text: str) -> None:
    assert CommandParser().parse(text) == MoveIntent("e2", "e4")


@pytest.mark.parametrize(
    ("text", "promotion"),
    [
        ("e7 e8 queen", "q"),
        ("e7 to e8 promote queen", "q"),
        ("e7 e8 q", "q"),
        ("move e7 to e8 promote to knight", "n"),
        ("e7-e8 rook", "r"),
        ("e7 e8 bishop", "b"),
    ],
)
def test_parser_accepts_promotions(text: str, promotion: str) -> None:
    assert CommandParser().parse(text) == MoveIntent("e7", "e8", promotion)


@pytest.mark.parametrize(
    "notation",
    [
        "e4",
        "Nf3",
        "Bc4",
        "exd5",
        "Nxe5",
        "O-O",
        "O-O-O",
        "e8=Q",
        "exd8=Q",
        "Qh5+",
        "Qxf7#",
        "Nbd2",
        "R1e2",
    ],
)
def test_parser_accepts_standard_algebraic_notation(notation: str) -> None:
    assert CommandParser().parse(f"  {notation}  ") == SanMoveIntent(notation)


@pytest.mark.parametrize("command", list(CommandName))
def test_parser_recognizes_cli_commands(command: CommandName) -> None:
    assert CommandParser().parse(command.value) == CommandIntent(command)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "move",
        "e9 e4",
        "e2 e4 dragon",
        "knight to f3",
        "e2 e4 extra words",
        "Nh9",
        "e9",
        "Bx",
        "pawn to e4",
    ],
)
def test_parser_rejects_malformed_commands(text: str) -> None:
    with pytest.raises(InvalidCommandError):
        CommandParser().parse(text)
