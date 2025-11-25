"""
Tests for data_access layer.

These tests mock the database connection to verify the logic
without requiring an actual database.
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# All tests now mock at the repository's base level (database_postgres.get_connection)
# since the wrapper functions now delegate to repositories


class TestApiQueries:
    """Tests for api_queries.py functions."""

    @patch('data_access.repositories.base.get_connection')
    def test_get_all_models_returns_list(self, mock_get_conn):
        """get_all_models returns a list of model dictionaries."""
        from data_access.api_queries import get_all_models

        # Setup mock cursor with sample data
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'name': 'test-model',
                'provider': 'openrouter',
                'model_slug': 'test/model',
                'is_active': True,
                'test_status': 'ranked',
                'elo_rating': 1500.0,
                'wins': 10,
                'losses': 5,
                'ties': 2,
                'apples_eaten': 100,
                'games_played': 17,
                'pricing_input': 0.001,
                'pricing_output': 0.002,
                'max_completion_tokens': 4096,
                'last_played_at': '2024-01-01T00:00:00',
                'discovered_at': '2024-01-01T00:00:00'
            }
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = get_all_models()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]['name'] == 'test-model'
        assert result[0]['elo_rating'] == 1500.0
        # Verify nested pricing dict is created
        assert 'pricing' in result[0]
        assert result[0]['pricing']['input'] == 0.001
        mock_conn.close.assert_called_once()

    @patch('data_access.repositories.base.get_connection')
    def test_get_all_models_active_only(self, mock_get_conn):
        """get_all_models with active_only=True filters inactive models."""
        from data_access.api_queries import get_all_models

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        get_all_models(active_only=True)

        # Check that the executed query contains is_active = TRUE
        call_args = mock_cursor.execute.call_args
        query = call_args[0][0]
        assert 'is_active = TRUE' in query
        mock_conn.close.assert_called_once()

    @patch('data_access.repositories.base.get_connection')
    def test_get_model_by_name_found(self, mock_get_conn):
        """get_model_by_name returns model when found."""
        from data_access.api_queries import get_model_by_name

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'name': 'test-model',
            'provider': 'openrouter',
            'model_slug': 'test/model',
            'is_active': True,
            'test_status': 'ranked',
            'elo_rating': 1600.0,
            'wins': 5,
            'losses': 3,
            'ties': 1,
            'apples_eaten': 50,
            'games_played': 9,
            'pricing_input': 0.001,
            'pricing_output': 0.002,
            'max_completion_tokens': 4096,
            'last_played_at': None,
            'discovered_at': '2024-01-01T00:00:00'
        }

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = get_model_by_name('test-model')

        assert result is not None
        assert result['name'] == 'test-model'
        assert result['elo_rating'] == 1600.0
        mock_conn.close.assert_called_once()

    @patch('data_access.repositories.base.get_connection')
    def test_get_model_by_name_not_found(self, mock_get_conn):
        """get_model_by_name returns None when model not found."""
        from data_access.api_queries import get_model_by_name

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = get_model_by_name('nonexistent-model')

        assert result is None
        mock_conn.close.assert_called_once()

    @patch('data_access.repositories.base.get_connection')
    def test_get_games_returns_paginated_list(self, mock_get_conn):
        """get_games returns paginated list of games."""
        from data_access.api_queries import get_games

        mock_cursor = MagicMock()
        # First call returns games, second call returns participants
        mock_cursor.fetchall.side_effect = [
            [
                {
                    'id': 'game-123',
                    'start_time': datetime(2024, 1, 1, 12, 0, 0),
                    'end_time': datetime(2024, 1, 1, 12, 5, 0),
                    'rounds': 50,
                    'replay_path': '/replays/game-123.json',
                    'board_width': 10,
                    'board_height': 10,
                    'num_apples': 5,
                    'total_score': 15,
                    'created_at': datetime(2024, 1, 1, 12, 0, 0)
                }
            ],
            [
                {
                    'name': 'model-1',
                    'provider': 'openrouter',
                    'player_slot': 0,
                    'score': 8,
                    'result': 'won',
                    'death_round': None,
                    'death_reason': None
                },
                {
                    'name': 'model-2',
                    'provider': 'openrouter',
                    'player_slot': 1,
                    'score': 7,
                    'result': 'lost',
                    'death_round': 45,
                    'death_reason': 'wall'
                }
            ]
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = get_games(limit=10, offset=0)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]['id'] == 'game-123'
        assert len(result[0]['participants']) == 2
        mock_conn.close.assert_called_once()

    @patch('data_access.repositories.base.get_connection')
    def test_get_total_games_count(self, mock_get_conn):
        """get_total_games_count returns correct count."""
        from data_access.api_queries import get_total_games_count

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'count': 42}

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = get_total_games_count()

        assert result == 42
        mock_conn.close.assert_called_once()


class TestGamePersistence:
    """Tests for game_persistence.py functions."""

    @patch('data_access.repositories.base.get_connection')
    def test_insert_game_success(self, mock_get_conn):
        """insert_game successfully inserts a game record."""
        from data_access.game_persistence import insert_game

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        insert_game(
            game_id='test-game-123',
            start_time=datetime(2024, 1, 1, 12, 0, 0),
            end_time=datetime(2024, 1, 1, 12, 5, 0),
            rounds=50,
            replay_path='/replays/test.json',
            board_width=10,
            board_height=10,
            num_apples=5,
            total_score=15,
            total_cost=0.01
        )

        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('data_access.repositories.base.get_connection')
    def test_insert_game_participants_success(self, mock_get_conn):
        """insert_game_participants inserts participant records."""
        from data_access.game_persistence import insert_game_participants

        mock_cursor = MagicMock()
        # First fetchone returns model_id for first participant
        # Second fetchone returns model_id for second participant
        mock_cursor.fetchone.side_effect = [
            {'id': 1},
            {'id': 2}
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        participants = [
            {
                'model_name': 'model-1',
                'player_slot': 0,
                'score': 8,
                'result': 'won',
                'death_round': None,
                'death_reason': None,
                'cost': 0.005
            },
            {
                'model_name': 'model-2',
                'player_slot': 1,
                'score': 7,
                'result': 'lost',
                'death_round': 45,
                'death_reason': 'wall',
                'cost': 0.005
            }
        ]

        insert_game_participants('test-game-123', participants)

        # Should have 2 SELECT calls (to get model_id) + 2 INSERT calls
        assert mock_cursor.execute.call_count == 4
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('data_access.repositories.base.get_connection')
    def test_insert_game_participants_model_not_found(self, mock_get_conn):
        """insert_game_participants skips participants with unknown models."""
        from data_access.game_persistence import insert_game_participants

        mock_cursor = MagicMock()
        # Model not found
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        participants = [
            {
                'model_name': 'unknown-model',
                'player_slot': 0,
                'score': 0,
                'result': 'lost'
            }
        ]

        # Should not raise, just skip
        insert_game_participants('test-game-123', participants)

        # Only 1 SELECT call, no INSERT
        assert mock_cursor.execute.call_count == 1
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()


class TestModelUpdates:
    """Tests for model_updates.py functions."""

    def test_get_pair_result_win(self):
        """get_pair_result returns (1, 0) when first player wins."""
        from data_access.model_updates import get_pair_result

        result = get_pair_result('won', 'lost')
        assert result == (1, 0)

    def test_get_pair_result_loss(self):
        """get_pair_result returns (0, 1) when first player loses."""
        from data_access.model_updates import get_pair_result

        result = get_pair_result('lost', 'won')
        assert result == (0, 1)

    def test_get_pair_result_tie(self):
        """get_pair_result returns (0.5, 0.5) for ties."""
        from data_access.model_updates import get_pair_result

        result = get_pair_result('tied', 'tied')
        assert result == (0.5, 0.5)

    def test_expected_score_equal_ratings(self):
        """expected_score returns 0.5 for equal ratings."""
        from data_access.model_updates import expected_score

        result = expected_score(1500, 1500)
        assert result == 0.5

    def test_expected_score_higher_rating(self):
        """expected_score returns > 0.5 for higher rated player."""
        from data_access.model_updates import expected_score

        result = expected_score(1600, 1400)
        assert result > 0.5
        # With 200 point difference, should be roughly 0.76
        assert 0.7 < result < 0.8

    def test_expected_score_lower_rating(self):
        """expected_score returns < 0.5 for lower rated player."""
        from data_access.model_updates import expected_score

        result = expected_score(1400, 1600)
        assert result < 0.5

    @patch('data_access.repositories.base.get_connection')
    def test_update_elo_ratings_two_players(self, mock_get_conn):
        """update_elo_ratings calculates and updates ELO for both players."""
        from data_access.model_updates import update_elo_ratings

        mock_cursor = MagicMock()
        # Return two participants with different results
        mock_cursor.fetchall.return_value = [
            {'model_id': 1, 'result': 'won', 'elo_rating': 1500.0, 'name': 'winner'},
            {'model_id': 2, 'result': 'lost', 'elo_rating': 1500.0, 'name': 'loser'}
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        update_elo_ratings('test-game-123')

        # Should have 1 SELECT + 2 UPDATE calls
        assert mock_cursor.execute.call_count == 3
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

        # Verify the UPDATE calls have correct ELO changes
        # Winner should gain rating, loser should lose rating
        update_calls = [call for call in mock_cursor.execute.call_args_list
                       if 'UPDATE models' in str(call)]
        assert len(update_calls) == 2

    @patch('data_access.repositories.base.get_connection')
    def test_update_model_aggregates(self, mock_get_conn):
        """update_model_aggregates updates win/loss/tie counts."""
        from data_access.model_updates import update_model_aggregates

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'model_id': 1, 'result': 'won', 'score': 10, 'name': 'winner'},
            {'model_id': 2, 'result': 'lost', 'score': 5, 'name': 'loser'}
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        update_model_aggregates('test-game-123')

        # Should have 1 SELECT + 2 UPDATE calls
        assert mock_cursor.execute.call_count == 3
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()


class TestLiveGame:
    """Tests for live_game.py functions."""

    @patch('data_access.repositories.base.get_connection')
    def test_insert_initial_game(self, mock_get_conn):
        """insert_initial_game creates initial game record."""
        from data_access.live_game import insert_initial_game

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        insert_initial_game(
            game_id='test-game-123',
            start_time=datetime(2024, 1, 1, 12, 0, 0),
            board_width=10,
            board_height=10,
            num_apples=5
        )

        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('data_access.repositories.base.get_connection')
    def test_insert_initial_participants(self, mock_get_conn):
        """insert_initial_participants creates placeholder participant records."""
        from data_access.live_game import insert_initial_participants

        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [{'id': 1}, {'id': 2}]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        participants = [
            {'model_name': 'model-1', 'player_slot': 0},
            {'model_name': 'model-2', 'player_slot': 1}
        ]

        insert_initial_participants('test-game-123', participants)

        # 2 SELECT + 2 INSERT
        assert mock_cursor.execute.call_count == 4
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('data_access.repositories.base.get_connection')
    def test_update_game_state(self, mock_get_conn):
        """update_game_state updates current_state JSON."""
        from data_access.live_game import update_game_state

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        current_state = {
            'round_number': 10,
            'scores': {'0': 5, '1': 3},
            'alive': {'0': True, '1': True}
        }

        update_game_state('test-game-123', current_state, rounds=10)

        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('data_access.repositories.base.get_connection')
    def test_complete_game(self, mock_get_conn):
        """complete_game marks game as completed."""
        from data_access.live_game import complete_game

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        complete_game(
            game_id='test-game-123',
            end_time=datetime(2024, 1, 1, 12, 5, 0),
            rounds=50,
            replay_path='/replays/test.json',
            total_score=15,
            total_cost=0.01
        )

        mock_cursor.execute.assert_called_once()
        # Check the UPDATE query sets status to 'completed'
        query = mock_cursor.execute.call_args[0][0]
        assert "status = 'completed'" in query
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('data_access.repositories.base.get_connection')
    def test_get_live_games(self, mock_get_conn):
        """get_live_games returns in-progress games."""
        from data_access.live_game import get_live_games

        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = [
            # First call: games
            [
                {
                    'id': 'game-123',
                    'status': 'in_progress',
                    'start_time': datetime(2024, 1, 1, 12, 0, 0),
                    'rounds': 10,
                    'board_width': 10,
                    'board_height': 10,
                    'num_apples': 5,
                    'current_state': '{"round_number": 10}'
                }
            ],
            # Second call: participants for first game
            [
                {'player_slot': 0, 'name': 'model-1', 'rank': 1},
                {'player_slot': 1, 'name': 'model-2', 'rank': 5}
            ]
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = get_live_games()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]['id'] == 'game-123'
        assert result[0]['status'] == 'in_progress'
        assert result[0]['models'] == {'0': 'model-1', '1': 'model-2'}
        mock_conn.close.assert_called_once()

    @patch('data_access.repositories.base.get_connection')
    def test_get_game_state_found(self, mock_get_conn):
        """get_game_state returns game state when found."""
        from data_access.live_game import get_game_state

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 'game-123',
            'status': 'in_progress',
            'start_time': datetime(2024, 1, 1, 12, 0, 0),
            'rounds': 10,
            'board_width': 10,
            'board_height': 10,
            'num_apples': 5,
            'current_state': '{"round_number": 10}',
            'total_score': None,
            'total_cost': None
        }
        mock_cursor.fetchall.return_value = [
            {'player_slot': 0, 'name': 'model-1', 'rank': 1},
            {'player_slot': 1, 'name': 'model-2', 'rank': 5}
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = get_game_state('game-123')

        assert result is not None
        assert result['id'] == 'game-123'
        assert result['current_state'] == {'round_number': 10}
        mock_conn.close.assert_called_once()

    @patch('data_access.repositories.base.get_connection')
    def test_get_game_state_not_found(self, mock_get_conn):
        """get_game_state returns None when game not found."""
        from data_access.live_game import get_game_state

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = get_game_state('nonexistent-game')

        assert result is None
        mock_conn.close.assert_called_once()


class TestConnectionManagement:
    """Tests to verify connection management patterns."""

    @patch('data_access.repositories.base.get_connection')
    def test_connection_closed_on_success(self, mock_get_conn):
        """Connection is closed after successful operation."""
        from data_access.api_queries import get_all_models

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        get_all_models()

        mock_conn.close.assert_called_once()

    @patch('data_access.repositories.base.get_connection')
    def test_connection_closed_on_exception(self, mock_get_conn):
        """Connection is closed even when exception occurs."""
        from data_access.api_queries import get_all_models

        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = Exception("Database error")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        with pytest.raises(Exception):
            get_all_models()

        # Connection should still be closed
        mock_conn.close.assert_called_once()

    @patch('data_access.repositories.base.get_connection')
    def test_rollback_on_insert_error(self, mock_get_conn):
        """Transaction is rolled back on insert error."""
        from data_access.game_persistence import insert_game

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Insert failed")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        with pytest.raises(Exception):
            insert_game(
                game_id='test',
                start_time=datetime.now(),
                end_time=datetime.now(),
                rounds=10,
                replay_path='/test',
                board_width=10,
                board_height=10,
                num_apples=5,
                total_score=0
            )

        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()
