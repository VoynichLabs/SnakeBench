import random
from collections import deque
from typing import List, Tuple, Dict, Set, Optional, Any
import time
from datetime import datetime
import os
from dotenv import load_dotenv
from openai import OpenAI
import json
import uuid
import argparse
from utils.utils import load_model_configs
from llm_providers import create_llm_provider
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

# Directions
UP = "UP"
DOWN = "DOWN"
LEFT = "LEFT"
RIGHT = "RIGHT"
VALID_MOVES = {UP, DOWN, LEFT, RIGHT}

class Snake:
    """
    Represents a snake on the board.
    positions: deque of (x, y) from head at index 0 to tail at the end
    alive: whether this snake is still alive
    """
    def __init__(self, positions: List[Tuple[int, int]]):
        self.positions = deque(positions)
        self.alive = True
        self.death_reason = None   # e.g., 'wall', 'self', 'collision'
        self.death_round = None    # The round number when the snake died

    @property
    def head(self) -> Tuple[int, int]:
        return self.positions[0]


class GameState:
    """
    A snapshot of the game at a specific point in time:
      - round_number: which round we are in (0-based)
      - snake_positions: dict of snake_id -> list of (x, y)
      - alive: dict of snake_id -> bool
      - scores: dict of snake_id -> int
      - width, height: board dimensions
      - apples: list of (x, y) positions of all apples on the board
      - move_history: list of dicts (one per round), each mapping snake_id -> move
    """
    def __init__(self,
                 round_number: int,
                 snake_positions: Dict[str, List[Tuple[int, int]]],
                 alive: Dict[str, bool],
                 scores: Dict[str, int],
                 width: int,
                 height: int,
                 apples: List[Tuple[int, int]],
                 move_history: List[Dict[str, str]]):
        self.round_number = round_number
        self.snake_positions = snake_positions
        self.alive = alive
        self.scores = scores
        self.width = width
        self.height = height
        self.apples = apples
        self.move_history = move_history

    def print_board(self) -> str:
        """
        Returns a string representation of the board with:
        . = empty space
        A = apple
        T = snake tail
        1,2,3... = snake head (showing player number)
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
                    board[y][x] = str(i)  # Use snake number (1, 2, 3...) for head
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

class Player:
    """
    Base class/interface for player logic.
    Each player is responsible for returning a move for its snake_id 
    given the current game state.
    """
    def __init__(self, snake_id: str):
        self.snake_id = snake_id

    def get_move(self, game_state: GameState) -> str:
        raise NotImplementedError


class RandomPlayer(Player):
    """
    Example: a random AI that picks a valid direction that avoids walls and self-collisions.
    """
    def get_move(self, game_state: GameState) -> str:
        snake_positions = game_state.snake_positions[self.snake_id]
        head_x, head_y = snake_positions[0]
        
        # Calculate all possible next positions
        possible_moves = {
            UP:    (head_x, head_y + 1),  # Up => y + 1
            DOWN:  (head_x, head_y - 1),  # Down => y - 1
            LEFT:  (head_x - 1, head_y),
            RIGHT: (head_x + 1, head_y)
        }
        
        # Filter out moves that:
        # 1. Hit walls
        # 2. Hit own body (except tail, which will move)
        valid_moves = []
        for move, (new_x, new_y) in possible_moves.items():
            # Check wall collisions
            if (new_x < 0 or new_x >= game_state.width or 
                new_y < 0 or new_y >= game_state.height):
                continue
                
            # Check self collisions (excluding tail which will move)
            if (new_x, new_y) in snake_positions[:-1]:
                continue
                
            valid_moves.append(move)
        
        # If no valid moves, just return a random move (we'll die anyway)
        if not valid_moves:
            return random.choice(list(VALID_MOVES))
            
        return random.choice(valid_moves)


class LLMPlayer(Player):
    """
    LLM-based player that delegates the API call details to the provider abstraction.
    """
    def __init__(self, snake_id: str, player_config: Dict[str, Any]):
        super().__init__(snake_id)
        self.name = player_config['name']
        self.config = player_config
        self.move_history = []
        # Instantiate the correct provider based on the player_config.
        self.provider = create_llm_provider(player_config)

    def get_direction_from_response(self, response: str) -> Optional[str]:
        # Convert response to uppercase for case-insensitive comparison.
        response = response.upper()
        # Starting from the end, find the last occurrence of any valid move.
        for i in range(len(response) - 1, -1, -1):
            for move in VALID_MOVES:
                if response[i:].startswith(move):
                    return move.upper()
        return None

    def get_move(self, game_state: GameState) -> dict:
        """
        Construct the prompt, call the generic provider, and then parse the response.
        Returns a dictionary containing the move and rationale.
        """
        prompt = self._construct_prompt(game_state)

        try:
            # Use the abstracted provider to get the response.
            response_text = self.provider.get_response(prompt)
        except Exception as exc:  # noqa: BLE001 - ensure the game continues
            print(
                f"Provider error for player {self.snake_id} ({self.name}): {exc}. "
                "Falling back to a random move."
            )
            direction = random.choice(list(VALID_MOVES))
            move_data = {
                "direction": direction,
                "rationale": (
                    f"Provider error: {exc}. Generated random move {direction} to continue the game."
                ),
            }
            self.move_history.append({self.snake_id: move_data})
            return move_data

        direction = self.get_direction_from_response(response_text)

        if direction is None:
            print(f"Player {self.snake_id} returned an invalid direction. Choosing a random move.")
            direction = random.choice(list(VALID_MOVES))
            response_text += f"\n\nThis is a random move: {direction}"

        move_data = {
            "direction": direction,
            "rationale": response_text
        }

        self.move_history.append({self.snake_id: move_data})
        return move_data

    def _construct_prompt(self, game_state: GameState) -> str:
        # Summarize the multiple apples
        apples_str = ", ".join(str(a) for a in game_state.apples)
        prompt = (
            f"You are controlling a snake in a multi-apple Snake game. "
            f"The board size is {game_state.width}x{game_state.height}. Normal X,Y coordinates are used. Coordinates range from (0,0) at bottom left to ({game_state.width-1},{game_state.height-1}) at top right.\n"
            f"Apples at: {apples_str}\n\n"
            f"Your snake ID: {self.snake_id} which is currently positioned at {game_state.snake_positions[self.snake_id][0]} with body at {game_state.snake_positions[self.snake_id][1:]}\n\n"
            f"Enemy snakes positions:\n" + 
            "\n".join([f"* Snake #{sid} is at position {pos[0]} with body at {pos[1:]}" for sid, pos in game_state.snake_positions.items() if sid != self.snake_id]) + "\n\n"
            f"Board state:\n"
            f"{game_state.print_board()}\n\n"
            f"--Your last move information:--\n\n"
            f"Direction: {self.move_history[-1][self.snake_id]['direction'] if self.move_history else 'None'}\n"
            f"Rationale: {self.move_history[-1][self.snake_id]['rationale'] if self.move_history else 'None'}\n\n"
            f"--End of your last move information.--\n\n"
            "Rules:\n"
            "1) If you move onto an apple, you grow and gain 1 point.\n"
            "2) If you run into a wall (outside the range of the listed coordinates), another snake, or yourself (like go backwards), you die.\n"
            "3) The goal is to have the most points by the end.\n\n"
            "Decreasing your x coordinate is to the left, increasing your x coordinate is to the right.\n"
            "Decreasing your y coordinate is down, increasing your y coordinate is up.\n"
            "You may think out loud first then respond with the direction.\n"
            "You may also state a strategy you want to tell yourself next turn.\n"
            "End your response with your decided next move: UP, DOWN, LEFT, or RIGHT.\n"
        )
        print(f"----------Prompt:\n\n {prompt}\n\n------------")
        return prompt

class SnakeGame:
    """
    Manages:
      - Board (width, height)
      - Snakes
      - Players
      - Multiple apples
      - Scores
      - Rounds
      - History for replay
    """
    def __init__(self, width: int, height: int, max_rounds: int = 20, num_apples: int = 3, game_id: str = None):
        self.width = width
        self.height = height
        self.snakes: Dict[str, Snake] = {}
        self.players: Dict[str, Player] = {}
        self.scores: Dict[str, int] = {}
        self.round_number = 0
        self.max_rounds = max_rounds
        self.game_over = False
        self.start_time = time.time()
        self.game_result = None 

        if game_id is None:
            self.game_id = str(uuid.uuid4())
        else:
            self.game_id = game_id
        print(f"Game ID: {self.game_id}")

        # Store how many apples we want to keep on the board at all times
        self.num_apples = num_apples
        
        # We store multiple apples as a set of (x, y) or a list.
        # Here, let's keep them as a list to preserve GameState JSON-friendliness.
        self.apples: List[Tuple[int,int]] = []

        # For replay or for the LLM context
        self.move_history: List[Dict[str, str]] = []
        self.history: List[GameState] = []

        # Place initial apples
        for _ in range(self.num_apples):
            cell = self._random_free_cell()
            self.apples.append(cell)

    def add_snake(self, snake_id: str, player: Player):
        if snake_id in self.snakes:
            raise ValueError(f"Snake with id {snake_id} already exists.")
        
        positions = self._random_free_cell()

        self.snakes[snake_id] = Snake([positions])
        self.players[snake_id] = player
        self.scores[snake_id] = 0
        print(f"Added snake '{snake_id}' ({player.model_name if hasattr(player, 'model_name') else player.__class__.__name__}) at {positions}.")

    def set_apples(self, apple_positions: List[Tuple[int,int]]):
        """
        Initialize the board with multiple apples at specified positions.
        If you want random generation, you can do that here.
        """
        for (ax, ay) in apple_positions:
            if not (0 <= ax < self.width and 0 <= ay < self.height):
                raise ValueError(f"Apple out of bounds at {(ax, ay)}.")
        self.apples = list(apple_positions)
        print(f"Set {len(self.apples)} apples on the board: {self.apples}")

    def _random_free_cell(self) -> Tuple[int,int]:
        """
        Return a random cell (x, y) not occupied by any snake or apple.
        We'll do a simple loop to find one. 
        """
        while True:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            # Check if occupied by a snake
            occupied_by_snake = any((x, y) in snake.positions for snake in self.snakes.values())
            # Check if there's already an apple here
            occupied_by_apple = (x, y) in self.apples

            if not occupied_by_snake and not occupied_by_apple:
                return (x, y)
    
    def get_current_state(self) -> GameState:
        """
        Return a snapshot of the current board as a GameState.
        """
        snake_positions = {}
        alive_dict = {}
        for sid, snake in self.snakes.items():
            snake_positions[sid] = list(snake.positions)
            alive_dict[sid] = snake.alive

        return GameState(
            round_number=self.round_number,
            snake_positions=snake_positions,
            alive=alive_dict,
            scores=self.scores.copy(),
            width=self.width,
            height=self.height,
            apples=self.apples.copy(),
            move_history=list(self.move_history)
        )

    def gather_moves_in_parallel(self, game):
        """
        Gathers each snake's move in parallel using threads.
        game: the SnakeGame instance
        Returns a dictionary: { snake_id: { "move": ..., "rationale": ... }, ... }
        """
        round_moves = {}
        # Take one snapshot of the state to pass to each player
        state_snapshot = game.get_current_state()
        
        # We'll limit max_workers to the number of alive snakes (or just len of all snakes).
        # If you have many snakes, you can set a higher or lower limit based on preference.
        alive_snakes = [sid for sid, s in game.snakes.items() if s.alive]

        with ThreadPoolExecutor(max_workers=len(alive_snakes)) as executor:
            # Schedule all get_move calls
            futures = {}
            for snake_id in alive_snakes:
                player = game.players[snake_id]
                futures[executor.submit(player.get_move, state_snapshot)] = snake_id
            
            # Collect results as they complete
            for future in as_completed(futures):
                snake_id = futures[future]
                move_data = future.result()  # This is the dict returned by LLMPlayer.get_move
                round_moves[snake_id] = {
                    "move": move_data["direction"],
                    "rationale": move_data["rationale"]
                }
                print(f"Player {snake_id} chose move: {move_data['direction']}")

        return round_moves

    def run_round(self):
        """
        Execute one round:
          1) If game is over, do nothing
          2) Ask each alive snake for their move
          3) Apply moves simultaneously
          4) Handle apple-eating (grow + score)
          5) Check collisions
          6) Possibly end game if round limit reached or 1 snake left, etc.
        """
        if self.game_over:
            print("Game is already over. No more rounds.")
            return
        
        self.print_board()

        # --- PARALLEL GATHER OF MOVES ---
        round_moves = self.gather_moves_in_parallel(self)
        # Store the moves of this round
        self.move_history.append(round_moves)

        self.record_history()

        # 2) Compute the intended new head for every snake
        new_heads: Dict[str, Optional[Tuple[int, int]]] = {}
        for sid, move_data in round_moves.items():
            snake = self.snakes[sid]
            if not snake.alive or move_data is None:
                new_heads[sid] = None
                continue

            hx, hy = snake.head
            move = move_data["move"]
            if move == UP:       hy += 1
            elif move == DOWN:   hy -= 1
            elif move == LEFT:   hx -= 1
            elif move == RIGHT:  hx += 1
            new_heads[sid] = (hx, hy)

        # --------------------------------------------------
        # 3) Build the *proposed* board after every snake moves
        # --------------------------------------------------
        eats_apple: Dict[str, bool] = {}
        proposed_bodies: Dict[str, List[Tuple[int, int]]] = {}

        for sid, snake in self.snakes.items():
            head = new_heads.get(sid)
            alive_and_moved = snake.alive and head is not None
            eats_apple[sid] = alive_and_moved and head in self.apples

            if not alive_and_moved:
                proposed_bodies[sid] = list(snake.positions)
                continue

            original_body = list(snake.positions)
            if eats_apple[sid]:
                # grow: keep the tail
                new_body = [head] + original_body
            else:
                # normal move: drop the tail
                new_body = [head] + original_body[:-1]

            proposed_bodies[sid] = new_body

        # --------------------------------------------------
        # 4) Collision detection on that proposed board
        # --------------------------------------------------
        # a) wall collisions
        for sid, head in new_heads.items():
            snake = self.snakes[sid]
            if not snake.alive or head is None:
                continue
            x, y = head
            if x < 0 or x >= self.width or y < 0 or y >= self.height:
                snake.alive = False
                snake.death_reason = "wall"
                snake.death_round  = self.round_number

        # b) head-to-head collisions
        head_counts: Dict[Tuple[int, int], List[str]] = {}
        for sid, head in new_heads.items():
            if head is not None and self.snakes[sid].alive:
                head_counts.setdefault(head, []).append(sid)

        for same_cell_snakes in head_counts.values():
            if len(same_cell_snakes) > 1:
                for sid in same_cell_snakes:
                    snake = self.snakes[sid]
                    snake.alive = False
                    snake.death_reason = "head_collision"
                    snake.death_round  = self.round_number

        # c) head-into-body collisions
        body_cells: Set[Tuple[int, int]] = set()
        for sid, body in proposed_bodies.items():
            if self.snakes[sid].alive:
                body_cells.update(body[1:])   # exclude each snake's head

        for sid, head in new_heads.items():
            snake = self.snakes[sid]
            if not snake.alive or head is None:
                continue
            if head in body_cells:
                snake.alive = False
                snake.death_reason = "body_collision"
                snake.death_round  = self.round_number

        # Which snakes died this round?
        snakes_died_this_round = [
            sid for sid, s in self.snakes.items()
            if not s.alive and s.death_round == self.round_number
        ]

        # If exactly two snakes total, handle immediate win / tie logic
        if len(snakes_died_this_round) > 0 and len(self.snakes) == 2:
            if len(snakes_died_this_round) == 1:
                survivor = [sid for sid in self.snakes if self.snakes[sid].alive][0]
                self.game_over = True
                self.game_result = {snakes_died_this_round[0]: "lost", survivor: "won"}
            else:  # both died
                self.game_over = True
                self.game_result = {sid: "tied" for sid in self.snakes}

            self.round_number += 1
            self.record_history()
            return

        # --------------------------------------------------
        # 5) Commit the moves & handle apples for the survivors
        # --------------------------------------------------
        for sid, snake in self.snakes.items():
            if not snake.alive or new_heads.get(sid) is None:
                continue

            snake.positions = deque(proposed_bodies[sid])

            if eats_apple[sid]:
                self.scores[sid] += 1
                self.apples.remove(new_heads[sid])

        # keep apple count constant
        while len(self.apples) < self.num_apples:
            self.apples.append(self._random_free_cell())

        # --------------------------------------------------
        # 6) End-of-round bookkeeping (round limit / last snake)
        # --------------------------------------------------
        self.round_number += 1
        alive_snakes = [sid for sid, s in self.snakes.items() if s.alive]

        if self.round_number >= self.max_rounds:
            self.end_game("Reached max rounds.")
        elif len(alive_snakes) <= 1:
            self.end_game("All but one snake are dead.")

        print(f"Finished round {self.round_number}. Alive: {alive_snakes}, Scores: {self.scores}")
        time.sleep(0.3)

    def serialize_history(self, history):
        """
        Convert the list of GameState objects to a JSON-serializable list of dicts.
        """
        output = []
        for state in history:
            # Build a dictionary representation
            state_dict = {
                "round_number": state.round_number,
                "snake_positions": {
                    sid: positions  # positions is already a list of (x, y)
                    for sid, positions in state.snake_positions.items()
                },
                "alive": state.alive,         # dict of snake_id -> bool
                "scores": state.scores,       # dict of snake_id -> int
                "width": state.width,
                "height": state.height,
                "apples": state.apples,       # list of (x, y)
                "move_history": state.move_history
            }
            # Note: If any data is in tuples, it's okay because JSON
            # can store them as lists. But Python's json library will 
            # automatically convert (x, y) to [x, y].
            output.append(state_dict)
        return output
    
    def clean_model_name(self, model_name: str) -> str:
        # Check if the model name contains a provider prefix (e.g., "mistral/")
        if '/' in model_name:
            # Return everything after the last '/'
            return model_name.split('/')[-1]
        # If no provider prefix, return the original name
        return model_name


    def save_history_to_json(self, filename=None):
        if filename is None:
            filename = f"snake_game_{self.game_id}.json"

        model_names = {
            sid: self.clean_model_name(player.name if hasattr(player, "name") else player.__class__.__name__)
            for sid, player in self.players.items()
        }
        
        # Build metadata for the game
        metadata = {
            "game_id": self.game_id,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(time.time()).isoformat(),
            "models": model_names,
            "game_result": self.game_result,
            "final_scores": self.scores,
            "death_info": {
                sid: {
                    "reason": snake.death_reason,
                    "round": snake.death_round
            }
            for sid, snake in self.snakes.items()
            if not snake.alive  # you could record info for dead snakes only
        },
            "max_rounds": self.max_rounds,
            "actual_rounds": self.round_number
        }
        
        data = {
            "metadata": metadata,
            "rounds": self.serialize_history(self.history)
        }
        
        # Ensure the output directory exists
        os.makedirs('completed_games', exist_ok=True)
        
        with open(f'completed_games/{filename}', "w") as f:
            json.dump(data, f, indent=2)
    
    def print_board(self):
        """
        Prints a visual representation of the current board state.
        """
        print("\n" + self.get_current_state().print_board() + "\n")

    def end_game(self, reason: str):
        self.game_over = True
        print(f"Game Over: {reason}")
        # Decide winner by highest score
        top_score = max(self.scores.values()) if self.scores else 0
        winners = [sid for sid, sc in self.scores.items() if sc == top_score]
        
        # Record the game result per snake
        self.game_result = {}
        for sid in self.scores:
            if sid in winners:
                self.game_result[sid] = "tied" if len(winners) > 1 else "won"
            else:
                self.game_result[sid] = "lost"
        
        if len(winners) == 1:
            print(f"The winner is {winners[0]} with score {top_score}.")
        else:
            print(f"Tie! Winners: {winners} with score {top_score}.")

    def record_history(self):
        state = self.get_current_state()
        self.history.append(state)


# -------------------------------
# Simulation Function
# -------------------------------

def run_simulation(model_config_1: Dict, model_config_2: Dict, game_params: argparse.Namespace) -> Dict:
    """
    Runs a single snake game simulation between two models.

    Args:
        model_config_1: Configuration dictionary for the first player.
        model_config_2: Configuration dictionary for the second player.
        game_params: An object (like argparse.Namespace) containing game settings
                     (width, height, max_rounds, num_apples).

    Returns:
        A dictionary summarizing the game results (game_id, final_scores, game_result).
    """
    # Create a game instance using parameters from game_params
    game = SnakeGame(
        width=game_params.width, 
        height=game_params.height, 
        max_rounds=game_params.max_rounds, 
        num_apples=game_params.num_apples
    )

    # Add two snakes with LLM players using the provided model configurations
    player_configs = [model_config_1, model_config_2]
    for i, player_config in enumerate(player_configs):
        game.add_snake(
            snake_id=str(i),
            player=LLMPlayer(str(i), player_config=player_config)
        )

    # Run the game loop
    while not game.game_over:
        game.run_round()

    # Print final status and save history
    print("\nFinal Scores:", game.scores)
    print(f"Game history (ID: {game.game_id}):")
    game.save_history_to_json()

    # Return the results summary
    return {
        "game_id": game.game_id,
        "final_scores": game.scores,
        "game_result": game.game_result
    }


# -------------------------------
# Example Usage (Main Entry Point)
# -------------------------------
def main():
    # Parse command line arguments for model ids for each snake
    parser = argparse.ArgumentParser(
        description="Run Snake Game with two distinctive LLM models as players."
    )
    parser.add_argument("--models", type=str, nargs='+', required=True,
                        help="2 model IDs for the snakes (e.g. 'gpt-4o-mini-2024-07-18 llama3-8b-8192')")
    parser.add_argument("--width", type=int, required=False, default=10,
                        help="Width of the board from 0 to N")
    parser.add_argument("--height", type=int, required=False, default=10,
                        help="Height of the board from 0 to N")
    parser.add_argument("--max_rounds", type=int, required=False, default=100,
                        help="Maximum number of rounds")
    parser.add_argument("--num_apples", type=int, required=False, default=5,
                        help="Number of apples on the board")
                        
    args = parser.parse_args()

    if len(args.models) != 2: # Ensure exactly two models for single run
        raise ValueError("Exactly two models must be provided for a single game run.")
    
    model_configs = load_model_configs()
    
    # Get the specific configurations for the requested models
    try:
        config1 = model_configs[args.models[0]]
        config2 = model_configs[args.models[1]]
    except KeyError as e:
        raise ValueError(f"Model '{e}' not found in model_list.yaml") from e

    # Call the simulation function (Logic moved here)
    result = run_simulation(config1, config2, args) # This line will be uncommented in the next step
    
    # Print the summary (Logic moved here)
    print("\nSimulation Result Summary:") # This line will be uncommented in the next step
    print(json.dumps(result, indent=2)) # This line will be uncommented in the next step


if __name__ == "__main__":
    main()
