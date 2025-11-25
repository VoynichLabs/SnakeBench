"""
Tests for main.py - Snake game engine.

These tests capture the current behavior of the game engine to ensure
refactoring doesn't break existing functionality.
"""

import pytest
import sys
import os
from collections import deque
from unittest.mock import Mock, patch, MagicMock

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import (
    Snake,
    GameState,
    Player,
    RandomPlayer,
    LLMPlayer,
    SnakeGame,
    UP, DOWN, LEFT, RIGHT,
    VALID_MOVES,
    APPLE_TARGET
)


class TestSnake:
    """Tests for the Snake class."""

    def test_snake_initialization_with_single_position(self):
        """Snake initializes with a single position."""
        snake = Snake([(5, 5)])
        assert list(snake.positions) == [(5, 5)]
        assert snake.alive is True
        assert snake.death_reason is None
        assert snake.death_round is None

    def test_snake_initialization_with_multiple_positions(self):
        """Snake initializes with multiple positions (body segments)."""
        positions = [(5, 5), (4, 5), (3, 5)]
        snake = Snake(positions)
        assert list(snake.positions) == positions
        assert snake.alive is True

    def test_snake_head_property(self):
        """Snake.head returns the first position (head)."""
        snake = Snake([(5, 5), (4, 5), (3, 5)])
        assert snake.head == (5, 5)

    def test_snake_positions_is_deque(self):
        """Snake positions are stored as a deque for efficient operations."""
        snake = Snake([(5, 5)])
        assert isinstance(snake.positions, deque)

    def test_snake_death_attributes(self):
        """Snake death attributes can be set."""
        snake = Snake([(5, 5)])
        snake.alive = False
        snake.death_reason = "wall"
        snake.death_round = 10

        assert snake.alive is False
        assert snake.death_reason == "wall"
        assert snake.death_round == 10


class TestGameState:
    """Tests for the GameState class."""

    def test_gamestate_initialization(self):
        """GameState initializes with all required attributes."""
        state = GameState(
            round_number=5,
            snake_positions={"0": [(3, 3), (2, 3)]},
            alive={"0": True},
            scores={"0": 2},
            width=10,
            height=10,
            apples=[(5, 5), (7, 7)],
            move_history=[],
            max_rounds=100
        )

        assert state.round_number == 5
        assert state.snake_positions == {"0": [(3, 3), (2, 3)]}
        assert state.alive == {"0": True}
        assert state.scores == {"0": 2}
        assert state.width == 10
        assert state.height == 10
        assert state.apples == [(5, 5), (7, 7)]
        assert state.max_rounds == 100

    def test_gamestate_print_board_returns_string(self):
        """GameState.print_board() returns a string representation."""
        state = GameState(
            round_number=0,
            snake_positions={"0": [(5, 5)]},
            alive={"0": True},
            scores={"0": 0},
            width=10,
            height=10,
            apples=[(3, 3)],
            move_history=[],
            max_rounds=100
        )

        board_str = state.print_board()
        assert isinstance(board_str, str)
        # Board should contain the snake head marker "0"
        assert "0" in board_str
        # Board should contain apple marker "A"
        assert "A" in board_str

    def test_gamestate_print_board_dead_snake_not_shown(self):
        """Dead snakes are not shown on the board."""
        state = GameState(
            round_number=0,
            snake_positions={"0": [(5, 5)]},
            alive={"0": False},
            scores={"0": 0},
            width=10,
            height=10,
            apples=[],
            move_history=[],
            max_rounds=100
        )

        board_str = state.print_board()
        # Dead snake should not appear - count occurrences of "0"
        # (Note: "0" appears in axis labels, so we check for snake head position)
        lines = board_str.split('\n')
        # Find the row where y=5 would be displayed
        # The snake head "0" should not be in the middle of the board
        assert board_str.count(' 0 ') == 0 or '0' not in [line.split()[1] for line in lines if len(line.split()) > 1]

    def test_gamestate_repr(self):
        """GameState has a useful string representation."""
        state = GameState(
            round_number=5,
            snake_positions={"0": [(3, 3)]},
            alive={"0": True},
            scores={"0": 2},
            width=10,
            height=10,
            apples=[(5, 5)],
            move_history=[],
            max_rounds=100
        )

        repr_str = repr(state)
        assert "round=5" in repr_str
        assert "apples=" in repr_str


class TestRandomPlayer:
    """Tests for the RandomPlayer class."""

    def test_random_player_initialization(self):
        """RandomPlayer initializes with a snake_id."""
        player = RandomPlayer("0")
        assert player.snake_id == "0"

    def test_random_player_returns_valid_move(self):
        """RandomPlayer.get_move() returns a valid direction."""
        player = RandomPlayer("0")
        state = GameState(
            round_number=0,
            snake_positions={"0": [(5, 5)]},
            alive={"0": True},
            scores={"0": 0},
            width=10,
            height=10,
            apples=[(3, 3)],
            move_history=[],
            max_rounds=100
        )

        move = player.get_move(state)
        assert move in VALID_MOVES

    def test_random_player_avoids_walls_when_possible(self):
        """RandomPlayer avoids walls when there are safe moves available."""
        player = RandomPlayer("0")
        # Snake in corner - only RIGHT and UP are safe
        state = GameState(
            round_number=0,
            snake_positions={"0": [(0, 0)]},
            alive={"0": True},
            scores={"0": 0},
            width=10,
            height=10,
            apples=[(5, 5)],
            move_history=[],
            max_rounds=100
        )

        # Run multiple times to verify it always picks safe moves
        for _ in range(20):
            move = player.get_move(state)
            assert move in {UP, RIGHT}, f"Expected UP or RIGHT, got {move}"

    def test_random_player_avoids_self_collision(self):
        """RandomPlayer avoids running into its own body."""
        player = RandomPlayer("0")
        # Snake going right, body behind and below
        state = GameState(
            round_number=0,
            snake_positions={"0": [(5, 5), (4, 5), (4, 4)]},
            alive={"0": True},
            scores={"0": 0},
            width=10,
            height=10,
            apples=[(7, 7)],
            move_history=[],
            max_rounds=100
        )

        # Run multiple times
        for _ in range(20):
            move = player.get_move(state)
            # Should not go LEFT (into body at 4,5)
            assert move != LEFT or move in {UP, DOWN, RIGHT}


class TestSnakeGame:
    """Tests for the SnakeGame class."""

    @patch('main.DB_AVAILABLE', False)
    def test_game_initialization(self):
        """SnakeGame initializes with correct default values."""
        game = SnakeGame(width=10, height=10)

        assert game.width == 10
        assert game.height == 10
        assert game.max_rounds == 150
        assert game.num_apples == 5
        assert game.round_number == 0
        assert game.game_over is False
        assert len(game.apples) == 5

    @patch('main.DB_AVAILABLE', False)
    def test_game_custom_parameters(self):
        """SnakeGame accepts custom parameters."""
        game = SnakeGame(
            width=20,
            height=15,
            max_rounds=200,
            num_apples=10
        )

        assert game.width == 20
        assert game.height == 15
        assert game.max_rounds == 200
        assert game.num_apples == 10
        assert len(game.apples) == 10

    @patch('main.DB_AVAILABLE', False)
    def test_add_snake(self):
        """add_snake() adds a snake and player to the game."""
        game = SnakeGame(width=10, height=10)
        player = RandomPlayer("0")

        game.add_snake("0", player)

        assert "0" in game.snakes
        assert "0" in game.players
        assert "0" in game.scores
        assert game.scores["0"] == 0
        assert game.snakes["0"].alive is True

    @patch('main.DB_AVAILABLE', False)
    def test_add_duplicate_snake_raises(self):
        """add_snake() raises ValueError for duplicate snake_id."""
        game = SnakeGame(width=10, height=10)
        player1 = RandomPlayer("0")
        player2 = RandomPlayer("0")

        game.add_snake("0", player1)

        with pytest.raises(ValueError):
            game.add_snake("0", player2)

    @patch('main.DB_AVAILABLE', False)
    def test_get_current_state(self):
        """get_current_state() returns a GameState snapshot."""
        game = SnakeGame(width=10, height=10)
        player = RandomPlayer("0")
        game.add_snake("0", player)

        state = game.get_current_state()

        assert isinstance(state, GameState)
        assert state.width == 10
        assert state.height == 10
        assert "0" in state.snake_positions
        assert "0" in state.alive
        assert "0" in state.scores

    @patch('main.DB_AVAILABLE', False)
    def test_random_free_cell_not_on_snake(self):
        """_random_free_cell() returns a cell not occupied by snakes."""
        game = SnakeGame(width=10, height=10)
        player = RandomPlayer("0")
        game.add_snake("0", player)

        snake_positions = set(game.snakes["0"].positions)

        for _ in range(50):
            cell = game._random_free_cell()
            assert cell not in snake_positions

    @patch('main.DB_AVAILABLE', False)
    def test_random_free_cell_not_on_apple(self):
        """_random_free_cell() returns a cell not occupied by apples."""
        game = SnakeGame(width=10, height=10)

        for _ in range(50):
            cell = game._random_free_cell()
            assert cell not in game.apples

    @patch('main.DB_AVAILABLE', False)
    def test_set_apples(self):
        """set_apples() places apples at specified positions."""
        game = SnakeGame(width=10, height=10, num_apples=0)
        game.apples = []  # Clear initial apples

        apple_positions = [(1, 1), (2, 2), (3, 3)]
        game.set_apples(apple_positions)

        assert game.apples == apple_positions

    @patch('main.DB_AVAILABLE', False)
    def test_set_apples_out_of_bounds_raises(self):
        """set_apples() raises ValueError for out-of-bounds positions."""
        game = SnakeGame(width=10, height=10)

        with pytest.raises(ValueError):
            game.set_apples([(15, 15)])


class TestCollisionDetection:
    """Tests for collision detection in the game engine."""

    @patch('main.DB_AVAILABLE', False)
    def test_wall_collision_detected(self):
        """Snake dies when hitting a wall."""
        game = SnakeGame(width=10, height=10, num_apples=0)
        game.apples = []

        # Create a mock player that always moves LEFT
        mock_player = Mock()
        mock_player.get_move = Mock(return_value={
            "direction": LEFT,
            "rationale": "test",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0
        })
        mock_player.name = "TestPlayer"

        # Place snake at left edge
        game.snakes["0"] = Snake([(0, 5)])
        game.players["0"] = mock_player
        game.scores["0"] = 0
        game.player_costs["0"] = 0.0

        # Run one round - snake should hit wall
        game.run_round()

        assert game.snakes["0"].alive is False
        assert game.snakes["0"].death_reason == "wall"

    @patch('main.DB_AVAILABLE', False)
    def test_head_collision_both_die(self):
        """Both snakes die in head-to-head collision."""
        game = SnakeGame(width=10, height=10, num_apples=0)
        game.apples = []

        # Two snakes about to collide head-on
        # Snake 0 at (4,5) moving RIGHT
        # Snake 1 at (6,5) moving LEFT
        # They will both move to (5,5)

        mock_player_0 = Mock()
        mock_player_0.get_move = Mock(return_value={
            "direction": RIGHT,
            "rationale": "test",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0
        })
        mock_player_0.name = "Player0"

        mock_player_1 = Mock()
        mock_player_1.get_move = Mock(return_value={
            "direction": LEFT,
            "rationale": "test",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0
        })
        mock_player_1.name = "Player1"

        game.snakes["0"] = Snake([(4, 5)])
        game.snakes["1"] = Snake([(6, 5)])
        game.players["0"] = mock_player_0
        game.players["1"] = mock_player_1
        game.scores["0"] = 0
        game.scores["1"] = 0
        game.player_costs["0"] = 0.0
        game.player_costs["1"] = 0.0

        game.run_round()

        assert game.snakes["0"].alive is False
        assert game.snakes["1"].alive is False
        assert game.snakes["0"].death_reason == "head_collision"
        assert game.snakes["1"].death_reason == "head_collision"

    @patch('main.DB_AVAILABLE', False)
    def test_body_collision_attacker_dies(self):
        """Snake dies when running into another snake's body."""
        game = SnakeGame(width=10, height=10, num_apples=0)
        game.apples = []

        # Snake 0 is long and horizontal
        # Snake 1 will run into snake 0's body

        mock_player_0 = Mock()
        mock_player_0.get_move = Mock(return_value={
            "direction": UP,  # Moving away
            "rationale": "test",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0
        })
        mock_player_0.name = "Player0"

        mock_player_1 = Mock()
        mock_player_1.get_move = Mock(return_value={
            "direction": DOWN,  # Moving into snake 0's body
            "rationale": "test",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0
        })
        mock_player_1.name = "Player1"

        # Snake 0: horizontal at y=5, head at (7,5), body extending left
        game.snakes["0"] = Snake([(7, 5), (6, 5), (5, 5), (4, 5)])
        # Snake 1: above snake 0's body, about to move down into it
        game.snakes["1"] = Snake([(5, 6)])

        game.players["0"] = mock_player_0
        game.players["1"] = mock_player_1
        game.scores["0"] = 0
        game.scores["1"] = 0
        game.player_costs["0"] = 0.0
        game.player_costs["1"] = 0.0

        game.run_round()

        # Snake 1 should die (ran into body)
        assert game.snakes["1"].alive is False
        assert game.snakes["1"].death_reason == "body_collision"
        # Snake 0 should survive
        assert game.snakes["0"].alive is True


class TestAppleEating:
    """Tests for apple eating and scoring."""

    @patch('main.DB_AVAILABLE', False)
    def test_eating_apple_increases_score(self):
        """Eating an apple increases the snake's score."""
        game = SnakeGame(width=10, height=10, num_apples=0)
        game.apples = [(5, 6)]  # Apple directly above snake

        mock_player = Mock()
        mock_player.get_move = Mock(return_value={
            "direction": UP,
            "rationale": "test",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0
        })
        mock_player.name = "TestPlayer"

        game.snakes["0"] = Snake([(5, 5)])
        game.players["0"] = mock_player
        game.scores["0"] = 0
        game.player_costs["0"] = 0.0

        initial_score = game.scores["0"]
        game.run_round()

        assert game.scores["0"] == initial_score + 1

    @patch('main.DB_AVAILABLE', False)
    def test_eating_apple_grows_snake(self):
        """Eating an apple makes the snake longer."""
        game = SnakeGame(width=10, height=10, num_apples=0)
        game.apples = [(5, 6)]  # Apple directly above snake

        mock_player = Mock()
        mock_player.get_move = Mock(return_value={
            "direction": UP,
            "rationale": "test",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0
        })
        mock_player.name = "TestPlayer"

        game.snakes["0"] = Snake([(5, 5), (5, 4)])  # Length 2
        game.players["0"] = mock_player
        game.scores["0"] = 0
        game.player_costs["0"] = 0.0

        initial_length = len(game.snakes["0"].positions)
        game.run_round()

        assert len(game.snakes["0"].positions) == initial_length + 1

    @patch('main.DB_AVAILABLE', False)
    def test_new_apple_spawns_after_eating(self):
        """A new apple spawns after one is eaten."""
        game = SnakeGame(width=10, height=10, num_apples=3)

        mock_player = Mock()
        mock_player.get_move = Mock(return_value={
            "direction": UP,
            "rationale": "test",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0
        })
        mock_player.name = "TestPlayer"

        # Position snake to eat an apple
        apple_pos = game.apples[0]
        snake_pos = (apple_pos[0], apple_pos[1] - 1)  # Below the apple

        game.snakes["0"] = Snake([snake_pos])
        game.players["0"] = mock_player
        game.scores["0"] = 0
        game.player_costs["0"] = 0.0

        initial_apple_count = len(game.apples)
        game.run_round()

        # Should still have same number of apples
        assert len(game.apples) == initial_apple_count


class TestGameEnd:
    """Tests for game ending conditions."""

    @patch('main.DB_AVAILABLE', False)
    def test_game_ends_on_max_rounds(self):
        """Game ends when max_rounds is reached."""
        game = SnakeGame(width=10, height=10, max_rounds=3, num_apples=0)
        game.apples = []

        # Need two snakes so game doesn't end on "last snake standing"
        mock_player_0 = Mock()
        mock_player_1 = Mock()

        # Both players move safely (alternating up/down)
        directions = [UP, DOWN]
        call_count = [0]

        def get_move_side_effect(state):
            direction = directions[call_count[0] % 2]
            call_count[0] += 1
            return {
                "direction": direction,
                "rationale": "test",
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0
            }

        mock_player_0.get_move = Mock(side_effect=get_move_side_effect)
        mock_player_0.name = "TestPlayer0"
        mock_player_1.get_move = Mock(side_effect=get_move_side_effect)
        mock_player_1.name = "TestPlayer1"

        # Place snakes far apart so they don't collide
        game.snakes["0"] = Snake([(2, 5)])
        game.snakes["1"] = Snake([(8, 5)])
        game.players["0"] = mock_player_0
        game.players["1"] = mock_player_1
        game.scores["0"] = 0
        game.scores["1"] = 0
        game.player_costs["0"] = 0.0
        game.player_costs["1"] = 0.0

        # Run until game ends
        while not game.game_over and game.round_number < 10:
            game.run_round()

        assert game.game_over is True
        assert game.round_number >= game.max_rounds

    @patch('main.DB_AVAILABLE', False)
    def test_game_ends_when_all_snakes_die(self):
        """Game ends when all snakes are dead."""
        game = SnakeGame(width=10, height=10, num_apples=0)
        game.apples = []

        # Create two snakes that will collide head-on
        mock_player_0 = Mock()
        mock_player_0.get_move = Mock(return_value={
            "direction": RIGHT,
            "rationale": "test",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0
        })
        mock_player_0.name = "Player0"

        mock_player_1 = Mock()
        mock_player_1.get_move = Mock(return_value={
            "direction": LEFT,
            "rationale": "test",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0
        })
        mock_player_1.name = "Player1"

        game.snakes["0"] = Snake([(4, 5)])
        game.snakes["1"] = Snake([(6, 5)])
        game.players["0"] = mock_player_0
        game.players["1"] = mock_player_1
        game.scores["0"] = 0
        game.scores["1"] = 0
        game.player_costs["0"] = 0.0
        game.player_costs["1"] = 0.0

        game.run_round()

        assert game.game_over is True

    @patch('main.DB_AVAILABLE', False)
    def test_last_snake_standing_wins(self):
        """Game ends and remaining snake wins when opponent dies."""
        game = SnakeGame(width=10, height=10, num_apples=0)
        game.apples = []

        # Snake 0 plays safe, Snake 1 runs into wall
        mock_player_0 = Mock()
        mock_player_0.get_move = Mock(return_value={
            "direction": UP,
            "rationale": "test",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0
        })
        mock_player_0.name = "Player0"

        mock_player_1 = Mock()
        mock_player_1.get_move = Mock(return_value={
            "direction": LEFT,  # Will hit wall
            "rationale": "test",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0
        })
        mock_player_1.name = "Player1"

        game.snakes["0"] = Snake([(5, 5)])
        game.snakes["1"] = Snake([(0, 5)])  # At left edge
        game.players["0"] = mock_player_0
        game.players["1"] = mock_player_1
        game.scores["0"] = 0
        game.scores["1"] = 0
        game.player_costs["0"] = 0.0
        game.player_costs["1"] = 0.0

        game.run_round()

        assert game.game_over is True
        assert game.snakes["0"].alive is True
        assert game.snakes["1"].alive is False
        assert game.game_result["0"] == "won"
        assert game.game_result["1"] == "lost"


class TestLLMPlayerDirectionParsing:
    """Tests for LLMPlayer direction parsing logic."""

    def test_get_direction_from_response_up(self):
        """Parses UP direction from response."""
        # Create minimal player config
        player_config = {
            'name': 'test-model',
            'model_name': 'test-model',
            'provider': 'openrouter'
        }

        with patch('players.llm_player.create_llm_provider'):
            player = LLMPlayer("0", player_config)

        assert player.get_direction_from_response("I'll move UP") == UP
        assert player.get_direction_from_response("up") == UP
        assert player.get_direction_from_response("The best move is UP") == UP

    def test_get_direction_from_response_down(self):
        """Parses DOWN direction from response."""
        player_config = {
            'name': 'test-model',
            'model_name': 'test-model',
            'provider': 'openrouter'
        }

        with patch('players.llm_player.create_llm_provider'):
            player = LLMPlayer("0", player_config)

        assert player.get_direction_from_response("DOWN") == DOWN
        assert player.get_direction_from_response("I should go down") == DOWN

    def test_get_direction_from_response_left(self):
        """Parses LEFT direction from response."""
        player_config = {
            'name': 'test-model',
            'model_name': 'test-model',
            'provider': 'openrouter'
        }

        with patch('players.llm_player.create_llm_provider'):
            player = LLMPlayer("0", player_config)

        assert player.get_direction_from_response("LEFT") == LEFT
        assert player.get_direction_from_response("Going left") == LEFT

    def test_get_direction_from_response_right(self):
        """Parses RIGHT direction from response."""
        player_config = {
            'name': 'test-model',
            'model_name': 'test-model',
            'provider': 'openrouter'
        }

        with patch('players.llm_player.create_llm_provider'):
            player = LLMPlayer("0", player_config)

        assert player.get_direction_from_response("RIGHT") == RIGHT
        assert player.get_direction_from_response("Moving right now") == RIGHT

    def test_get_direction_from_response_last_occurrence(self):
        """Parses the last direction mentioned in response."""
        player_config = {
            'name': 'test-model',
            'model_name': 'test-model',
            'provider': 'openrouter'
        }

        with patch('players.llm_player.create_llm_provider'):
            player = LLMPlayer("0", player_config)

        # Should pick "DOWN" as it's the last valid direction
        response = "I could go UP but I'll choose DOWN"
        assert player.get_direction_from_response(response) == DOWN

    def test_get_direction_from_response_invalid(self):
        """Returns None for invalid response."""
        player_config = {
            'name': 'test-model',
            'model_name': 'test-model',
            'provider': 'openrouter'
        }

        with patch('players.llm_player.create_llm_provider'):
            player = LLMPlayer("0", player_config)

        assert player.get_direction_from_response("I don't know") is None
        assert player.get_direction_from_response("") is None


class TestGameHistory:
    """Tests for game history and serialization."""

    @patch('main.DB_AVAILABLE', False)
    def test_record_history(self):
        """record_history() adds current state to history."""
        game = SnakeGame(width=10, height=10)
        player = RandomPlayer("0")
        game.add_snake("0", player)

        initial_history_len = len(game.history)
        game.record_history()

        assert len(game.history) == initial_history_len + 1
        assert isinstance(game.history[-1], GameState)

    @patch('main.DB_AVAILABLE', False)
    def test_serialize_history(self):
        """serialize_history() converts GameState objects to dicts."""
        game = SnakeGame(width=10, height=10)
        player = RandomPlayer("0")
        game.add_snake("0", player)
        game.record_history()

        serialized = game.serialize_history(game.history)

        assert isinstance(serialized, list)
        assert len(serialized) == len(game.history)
        assert isinstance(serialized[0], dict)
        assert "round_number" in serialized[0]
        assert "snake_positions" in serialized[0]
        assert "alive" in serialized[0]
        assert "scores" in serialized[0]


class TestMoveDirections:
    """Tests for movement direction constants."""

    def test_valid_moves_set(self):
        """VALID_MOVES contains all four directions."""
        assert UP in VALID_MOVES
        assert DOWN in VALID_MOVES
        assert LEFT in VALID_MOVES
        assert RIGHT in VALID_MOVES
        assert len(VALID_MOVES) == 4

    def test_direction_values(self):
        """Direction constants have expected string values."""
        assert UP == "UP"
        assert DOWN == "DOWN"
        assert LEFT == "LEFT"
        assert RIGHT == "RIGHT"

    def test_apple_target_constant(self):
        """APPLE_TARGET constant exists and is reasonable."""
        assert isinstance(APPLE_TARGET, int)
        assert APPLE_TARGET > 0
