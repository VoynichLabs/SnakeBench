"""
GameState entity - a snapshot of the game at a point in time.
"""

from typing import List, Tuple, Dict, Optional


class GameState:
    """
    A snapshot of the game at a specific point in time.

    Attributes:
        round_number: which round we are in (0-based)
        snake_positions: dict of snake_id -> list of (x, y)
        alive: dict of snake_id -> bool
        scores: dict of snake_id -> int
        width, height: board dimensions
        apples: list of (x, y) positions of all apples on the board
        move_history: list of dicts (one per round), each mapping snake_id -> move
        max_rounds: optional upper limit on total rounds
    """

    def __init__(
        self,
        round_number: int,
        snake_positions: Dict[str, List[Tuple[int, int]]],
        alive: Dict[str, bool],
        scores: Dict[str, int],
        width: int,
        height: int,
        apples: List[Tuple[int, int]],
        move_history: List[Dict[str, str]],
        max_rounds: Optional[int] = None
    ):
        self.round_number = round_number
        self.snake_positions = snake_positions
        self.alive = alive
        self.scores = scores
        self.width = width
        self.height = height
        self.apples = apples
        self.move_history = move_history
        self.max_rounds = max_rounds

    def print_board(self) -> str:
        """
        Returns a string representation of the board with:
        . = empty space
        A = apple
        T = snake tail
        0,1,2... = snake head (showing player number)
        Now with (0,0) at bottom left and x-axis labels at bottom
        """
        # Create empty board
        board = [['.' for _ in range(self.width)] for _ in range(self.height)]

        # Place apples
        for ax, ay in self.apples:
            board[ay][ax] = 'A'

        # Place snakes
        for i, (snake_id, positions) in enumerate(self.snake_positions.items(), start=0):
            if not self.alive[snake_id]:
                continue

            # Place snake body
            for pos_idx, (x, y) in enumerate(positions):
                if pos_idx == 0:  # Head
                    board[y][x] = str(i)  # Use snake number (0, 1, 2...) for head
                else:  # Body/tail
                    board[y][x] = 'T'

        # Build the string representation
        result = []
        # Print rows in reverse order (bottom to top)
        for y in range(self.height - 1, -1, -1):
            result.append(f"{y:2d} {' '.join(board[y])}")

        # Add x-axis labels at the bottom
        result.append("   " + " ".join(str(i) for i in range(self.width)))

        return "\n".join(result)

    def __repr__(self):
        return (
            f"<GameState round={self.round_number}, apples={self.apples}, "
            f"snakes={len(self.snake_positions)}, scores={self.scores}>"
        )
