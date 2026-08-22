from collections.abc import Iterator

from wizard_chess.application.session import GameSession
from wizard_chess.commands.intents import MoveIntent, SanMoveIntent
from wizard_chess.commands.parser import CommandParser
from wizard_chess.commands.resolver import MoveResolver
from wizard_chess.domain.game import ChessGame
from wizard_chess.hardware.simulated_board import SimulatedPhysicalBoard
from wizard_chess.main import CliApplication
from wizard_chess.speech.controller import VoiceController
from wizard_chess.speech.mock import MockAudioInput, MockSpeechRecognizer


def test_command_to_simulated_physical_board_pipeline() -> None:
    parser = CommandParser()
    resolver = MoveResolver()
    game = ChessGame()
    physical_board = SimulatedPhysicalBoard()

    for text in ("e4", "e7-e5", "Nf3", "b8-c6"):
        intent = parser.parse(text)
        assert isinstance(intent, (MoveIntent, SanMoveIntent))
        event = game.make_move(resolver.resolve(intent, game))
        physical_board.execute_move(event)

    assert [event.uci for event in physical_board.events] == [
        "e2e4",
        "e7e5",
        "g1f3",
        "b8c6",
    ]
    assert [event.san for event in physical_board.events] == ["e4", "e5", "Nf3", "Nc6"]
    assert "1. e4 e5 2. Nf3 Nc6" in game.to_pgn()


def test_cli_plays_moves_reports_pgn_and_quits() -> None:
    inputs: Iterator[str] = iter(["e2 e4", "e7-e5", "g1 f3", "pgn", "quit"])
    output: list[str] = []
    physical_board = SimulatedPhysicalBoard()
    app = CliApplication(
        input_fn=lambda _prompt: next(inputs),
        output_fn=output.append,
        physical_board=physical_board,
    )

    assert app.run() == 0
    assert "Played: e4" in output
    assert "Played: e5" in output
    assert "Played: Nf3" in output
    assert any("1. e4 e5 2. Nf3" in line for line in output)
    assert [event.uci for event in physical_board.events] == ["e2e4", "e7e5", "g1f3"]


def test_cli_recovers_from_illegal_move_and_supports_history() -> None:
    inputs: Iterator[str] = iter(["e2 e5", "e2 e4", "undo", "redo", "fen", "quit"])
    output: list[str] = []
    app = CliApplication(input_fn=lambda _prompt: next(inputs), output_fn=output.append)

    assert app.run() == 0
    assert any(line.startswith("Error: Illegal move") for line in output)
    assert "Undid: e2e4" in output
    assert "Redid: e4" in output
    assert app.game.turn.value == "black"


def test_cli_announces_check_from_a_played_sequence() -> None:
    inputs: Iterator[str] = iter(["e2 e4", "e7 e5", "d1 h5", "b8 c6", "h5 e5", "quit"])
    output: list[str] = []

    assert CliApplication(input_fn=lambda _prompt: next(inputs), output_fn=output.append).run() == 0
    assert "Played: Qxe5+" in output
    assert "Check." in output


def test_cli_announces_checkmate_for_corrected_screenshot_sequence() -> None:
    inputs: Iterator[str] = iter(["e2 e4", "f7 f6", "d2 d4", "g7 g5", "d1 h5", "quit"])
    output: list[str] = []
    prompts: list[str] = []

    def input_move(prompt: str) -> str:
        prompts.append(prompt)
        return next(inputs)

    assert CliApplication(input_fn=input_move, output_fn=output.append).run() == 0
    assert "Played: Qh5#" in output
    assert "Checkmate: 1-0" in output
    assert prompts[-1] == "\nGame over > "


def test_cli_explains_the_illegal_moves_from_the_screenshot() -> None:
    inputs: Iterator[str] = iter(
        ["e2 e4", "f7 f6", "d2 d4", "g7 g5", "d1 h4", "d1 g4", "e8 e7", "quit"]
    )
    output: list[str] = []

    assert CliApplication(input_fn=lambda _prompt: next(inputs), output_fn=output.append).run() == 0
    assert any("queen cannot move from d1 to h4" in line for line in output)
    assert any("e7 is occupied by Black's own pawn" in line for line in output)


def test_san_and_coordinate_moves_have_equivalent_state_and_events() -> None:
    parser = CommandParser()
    resolver = MoveResolver()
    san_game = ChessGame()
    coordinate_game = ChessGame()

    san_intent = parser.parse("e4")
    coordinate_intent = parser.parse("e2 e4")
    assert isinstance(san_intent, SanMoveIntent)
    assert isinstance(coordinate_intent, MoveIntent)

    san_event = san_game.make_move(resolver.resolve(san_intent, san_game))
    coordinate_event = coordinate_game.make_move(
        resolver.resolve(coordinate_intent, coordinate_game)
    )

    assert san_event == coordinate_event
    assert san_game.fen() == coordinate_game.fen()
    assert san_game.to_pgn() == coordinate_game.to_pgn()


def test_cli_undo_and_redo_after_san_moves() -> None:
    inputs: Iterator[str] = iter(["e4", "e5", "Nf3", "undo", "redo", "quit"])
    output: list[str] = []
    app = CliApplication(input_fn=lambda _prompt: next(inputs), output_fn=output.append)

    assert app.run() == 0
    assert "Undid: g1f3" in output
    assert "Redid: Nf3" in output
    assert "1. e4 e5 2. Nf3" in app.game.to_pgn()


def test_rejected_san_does_not_emit_physical_board_event() -> None:
    inputs: Iterator[str] = iter(["e5", "quit"])
    output: list[str] = []
    physical_board = SimulatedPhysicalBoard()
    app = CliApplication(
        input_fn=lambda _prompt: next(inputs),
        output_fn=output.append,
        physical_board=physical_board,
    )
    original_fen = app.game.fen()

    assert app.run() == 0
    assert any(line.startswith("Error: Illegal SAN move") for line in output)
    assert app.game.fen() == original_fen
    assert physical_board.events == []


def test_cli_mixes_voice_and_typed_commands_in_one_session() -> None:
    inputs: Iterator[str] = iter(["voice", "e7 e5", "quit"])
    output: list[str] = []
    session = GameSession()
    voice_controller = VoiceController(
        MockAudioInput(),
        MockSpeechRecognizer(["e four"]),
        session.play_text,
    )
    app = CliApplication(
        input_fn=lambda _prompt: next(inputs),
        output_fn=output.append,
        session=session,
        voice_controller=voice_controller,
    )

    assert app.run() == 0
    assert "Listening..." in output
    assert "Processing..." in output
    assert 'Heard: "e four"' in output
    assert "Played: e4" in output
    assert session.snapshot().move_history == ("e4", "e5")


def test_cli_voice_failure_keeps_typed_input_available() -> None:
    inputs: Iterator[str] = iter(["voice", "e2 e4", "quit"])
    output: list[str] = []
    session = GameSession()
    voice_controller = VoiceController(
        MockAudioInput(),
        MockSpeechRecognizer(["knight before"]),
        session.play_text,
    )
    app = CliApplication(
        input_fn=lambda _prompt: next(inputs),
        output_fn=output.append,
        session=session,
        voice_controller=voice_controller,
    )

    assert app.run() == 0
    assert 'Heard: "knight before"' in output
    assert "Please try again." in output
    assert session.snapshot().move_history == ("e4",)
