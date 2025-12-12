"""
Video Generation Service for Snake Game Replays

This service generates MP4 videos from game replay JSON files by:
1. Rendering each frame using PIL (Pillow)
2. Encoding frames to video using MoviePy/FFmpeg
3. Saving the video to local completed_games directory

The rendering matches the frontend design with:
- Canvas game board with grid
- Snake rendering (body and head with eyes)
- Apple rendering
- Player thoughts panels on sides
- Score and alive status
"""

import os
import json
import logging
import tempfile
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageSequenceClip
import numpy as np

import sys
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

logger = logging.getLogger(__name__)

# Video settings
DEFAULT_FPS = 2  # Matches frontend playback speed (500ms = 2 FPS)
DEFAULT_VIDEO_WIDTH = 1920
DEFAULT_VIDEO_HEIGHT = 1080
CELL_SIZE = 40  # Size of each grid cell in pixels


class ColorScheme:
    """Color configuration matching frontend design"""

    # Player 1 (Green/Olive theme) - matches frontend colorConfig
    PLAYER1_SNAKE = "#4F7022"  # Green/olive - matches frontend player1.main
    PLAYER1_PANEL_BG = "#1a1f2e"
    PLAYER1_PANEL_BORDER = "#4F7022"
    PLAYER1_TEXT = "#FFFFFF"

    # Player 2 (Blue/Teal theme) - matches frontend colorConfig
    PLAYER2_SNAKE = "#036C8E"  # Blue/teal - matches frontend player2.main
    PLAYER2_PANEL_BG = "#1a1f2e"
    PLAYER2_PANEL_BORDER = "#036C8E"
    PLAYER2_TEXT = "#FFFFFF"

    # Game board
    BACKGROUND = "#FFFFFF"
    GRID_LINE = "#E5E7EB"
    APPLE = "#EA2014"

    # UI
    SCORE_TEXT = "#FFFFFF"
    THOUGHT_TEXT = "#D1D5DB"


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def darken_color(hex_color: str, amount: float = 0.3) -> Tuple[int, int, int]:
    """Darken a hex color by a given amount"""
    r, g, b = hex_to_rgb(hex_color)
    r = max(0, int(r * (1 - amount)))
    g = max(0, int(g * (1 - amount)))
    b = max(0, int(b * (1 - amount)))
    return (r, g, b)


class SnakeVideoGenerator:
    """Generate MP4 videos from Snake game replays"""

    def __init__(
        self,
        width: int = DEFAULT_VIDEO_WIDTH,
        height: int = DEFAULT_VIDEO_HEIGHT,
        fps: int = DEFAULT_FPS,
        cell_size: int = CELL_SIZE
    ):
        self.width = width
        self.height = height
        self.fps = fps
        self.cell_size = cell_size

        # Calculate layout dimensions
        self.panel_width = 400  # Width of each side panel
        self.canvas_size = min(
            self.height - 200,  # Leave room for controls
            self.width - (2 * self.panel_width) - 100  # Space between panels
        )

        # Try to load a font, fallback to default if not available
        try:
            self.font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
            self.font_medium = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 26)
            self.font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
        except Exception:
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

    def _normalize_replay(self, replay_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Accept both the new schema (frames + game + players) and the legacy
        schema (metadata + rounds) and return a normalized tuple of
        (metadata_like, rounds_like).
        """
        if "frames" in replay_data and "game" in replay_data:
            board = replay_data.get("game", {}).get("board", {})
            players = replay_data.get("players", {}) or {}

            metadata = {
                "game_id": replay_data.get("game", {}).get("id"),
                "models": {pid: pdata.get("name", f"Player {pid}") for pid, pdata in players.items()},
                "board": board
            }

            rounds: List[Dict[str, Any]] = []
            for idx, frame in enumerate(replay_data.get("frames", [])):
                state = frame.get("state", {}) or {}
                rounds.append({
                    "round_number": frame.get("round", idx),
                    "snake_positions": state.get("snakes", {}),
                    "alive": state.get("alive", {}),
                    "scores": state.get("scores", {}),
                    "apples": state.get("apples", []),
                    "width": board.get("width"),
                    "height": board.get("height"),
                    # Legacy renderer expects a list of move histories
                    "move_history": [frame.get("moves", {})] if frame.get("moves") else []
                })

            return metadata, rounds

        # Legacy schema fallback
        return replay_data.get("metadata", {}), replay_data.get("rounds", [])

    def render_frame(
        self,
        round_data: Dict[str, Any],
        model_ids: List[str],
        model_names: List[str],
        round_number: int,
        total_rounds: int
    ) -> Image.Image:
        """Render a single frame of the game"""

        # Create base image
        img = Image.new('RGB', (self.width, self.height), hex_to_rgb(ColorScheme.BACKGROUND))
        draw = ImageDraw.Draw(img)

        # Calculate positions
        left_panel_x = 50
        canvas_x = left_panel_x + self.panel_width + 50
        right_panel_x = canvas_x + self.canvas_size + 50
        panel_y = 50

        # Draw left player panel
        self._draw_player_panel(
            draw,
            left_panel_x,
            panel_y,
            model_names[0],
            round_data['scores'].get(model_ids[0], 0),
            round_data['alive'].get(model_ids[0], False),
            self._get_thoughts(round_data, model_ids[0]),
            ColorScheme.PLAYER1_PANEL_BORDER,
            is_left=True
        )

        # Draw game canvas
        self._draw_game_canvas(
            draw,
            img,
            canvas_x,
            panel_y,
            round_data,
            model_ids
        )

        # Draw right player panel
        self._draw_player_panel(
            draw,
            right_panel_x,
            panel_y,
            model_names[1],
            round_data['scores'].get(model_ids[1], 0),
            round_data['alive'].get(model_ids[1], False),
            self._get_thoughts(round_data, model_ids[1]),
            ColorScheme.PLAYER2_PANEL_BORDER,
            is_left=False
        )

        # Draw round counter at bottom
        round_text = f"Round {round_number + 1} / {total_rounds}"
        bbox = draw.textbbox((0, 0), round_text, font=self.font_medium)
        text_width = bbox[2] - bbox[0]
        draw.text(
            (self.width // 2 - text_width // 2, self.height - 80),
            round_text,
            fill=(100, 100, 100),
            font=self.font_medium
        )

        return img

    def _draw_player_panel(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        model_name: str,
        score: int,
        is_alive: bool,
        thoughts: List[str],
        border_color: str,
        is_left: bool
    ):
        """Draw a player information panel"""
        panel_height = self.canvas_size

        # Draw panel background
        draw.rectangle(
            [x, y, x + self.panel_width, y + panel_height],
            fill=hex_to_rgb(ColorScheme.PLAYER1_PANEL_BG),
            outline=hex_to_rgb(border_color),
            width=2
        )

        # Draw model name header
        header_height = 60
        draw.rectangle(
            [x, y, x + self.panel_width, y + header_height],
            fill=hex_to_rgb(border_color)
        )

        # Model name (truncate if too long)
        name_display = model_name if len(model_name) <= 25 else model_name[:22] + "..."
        bbox = draw.textbbox((0, 0), name_display, font=self.font_medium)
        text_width = bbox[2] - bbox[0]
        draw.text(
            (x + self.panel_width // 2 - text_width // 2, y + 20),
            name_display,
            fill=hex_to_rgb(ColorScheme.PLAYER1_TEXT),
            font=self.font_medium
        )

        # Draw score and status
        status_text = f"Score: {score} | {'Alive' if is_alive else 'Dead'}"
        status_color = (100, 200, 100) if is_alive else (200, 100, 100)
        draw.text(
            (x + 20, y + header_height + 20),
            status_text,
            fill=status_color,
            font=self.font_small
        )

        # Draw thoughts
        thoughts_y = y + header_height + 60
        draw.text(
            (x + 20, thoughts_y),
            "Thoughts:",
            fill=hex_to_rgb(ColorScheme.PLAYER1_TEXT),
            font=self.font_medium
        )

        thoughts_y += 40
        # Join all thoughts and limit to 700 characters
        full_text = " ".join(thoughts)[:700]
        # Wrap the text to fit panel width
        wrapped_lines = self._wrap_text(full_text, self.panel_width - 60)
        for line in wrapped_lines:
            draw.text(
                (x + 20, thoughts_y),
                line,
                fill=hex_to_rgb(ColorScheme.THOUGHT_TEXT),
                font=self.font_small
            )
            thoughts_y += 30
            # Stop if we're running out of panel space
            if thoughts_y > y + panel_height - 60:
                break

    def _wrap_text(self, text: str, max_width: int) -> List[str]:
        """Wrap text to fit within max_width"""
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            current_line.append(word)
            # Rough estimate: 10 pixels per character for larger font
            if len(' '.join(current_line)) * 10 > max_width:
                if len(current_line) > 1:
                    current_line.pop()
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word[:max_width // 10])
                    current_line = []

        if current_line:
            lines.append(' '.join(current_line))

        return lines

    def _get_thoughts(self, round_data: Dict[str, Any], model_id: str) -> List[str]:
        """Extract thoughts from round data and clean up markdown formatting"""
        if 'move_history' in round_data and round_data['move_history']:
            move_history = round_data['move_history']

            if isinstance(move_history, list) and len(move_history) > 0:
                last_move = move_history[-1]
                if model_id in last_move and 'rationale' in last_move[model_id]:
                    rationale = last_move[model_id]['rationale']
                    thoughts = []
                    for line in rationale.split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                        # Remove markdown bullet points (-, *, or numbered lists)
                        if line.startswith('- '):
                            line = line[2:]
                        elif line.startswith('* '):
                            line = line[2:]
                        elif len(line) > 2 and line[0].isdigit() and line[1] in '.):':
                            line = line[2:].strip()
                        elif len(line) > 3 and line[0:2].isdigit() and line[2] in '.):':
                            line = line[3:].strip()
                        # Remove markdown bold/italic markers
                        line = line.replace('**', '').replace('__', '').replace('*', '').replace('_', '')
                        if line:
                            thoughts.append(line)
                    return thoughts if thoughts else ["No thoughts available"]

        return ["No thoughts available"]

    def _draw_game_canvas(
        self,
        draw: ImageDraw.Draw,
        img: Image.Image,
        x: int,
        y: int,
        round_data: Dict[str, Any],
        model_ids: List[str]
    ):
        """Draw the game board canvas"""
        board_width = round_data['width']
        board_height = round_data['height']

        # Calculate cell size to fit canvas
        cell_size = min(
            self.canvas_size // board_width,
            self.canvas_size // board_height
        )

        # Center the board in the canvas
        board_pixel_width = board_width * cell_size
        board_pixel_height = board_height * cell_size
        board_x = x + (self.canvas_size - board_pixel_width) // 2
        board_y = y + (self.canvas_size - board_pixel_height) // 2

        # Draw canvas background
        draw.rectangle(
            [x, y, x + self.canvas_size, y + self.canvas_size],
            fill=(240, 240, 240),
            outline=(200, 200, 200),
            width=2
        )

        # Draw game board background
        draw.rectangle(
            [board_x, board_y, board_x + board_pixel_width, board_y + board_pixel_height],
            fill=hex_to_rgb(ColorScheme.BACKGROUND),
            outline=(100, 100, 100),
            width=4
        )

        # Draw grid
        for i in range(board_width + 1):
            draw.line(
                [board_x + i * cell_size, board_y, board_x + i * cell_size, board_y + board_pixel_height],
                fill=hex_to_rgb(ColorScheme.GRID_LINE),
                width=1
            )

        for i in range(board_height + 1):
            draw.line(
                [board_x, board_y + i * cell_size, board_x + board_pixel_width, board_y + i * cell_size],
                fill=hex_to_rgb(ColorScheme.GRID_LINE),
                width=1
            )

        # Draw apples
        for apple_x, apple_y in round_data['apples']:
            flipped_y = board_height - 1 - apple_y
            self._draw_cell(
                draw,
                board_x + apple_x * cell_size,
                board_y + flipped_y * cell_size,
                cell_size,
                hex_to_rgb(ColorScheme.APPLE)
            )

        # Draw snakes
        snake_colors = [ColorScheme.PLAYER1_SNAKE, ColorScheme.PLAYER2_SNAKE]
        for idx, model_id in enumerate(model_ids):
            snake = round_data['snake_positions'].get(model_id, [])
            if not snake:
                continue

            color = hex_to_rgb(snake_colors[idx])

            # Draw body
            for i in range(1, len(snake)):
                pos_x, pos_y = snake[i]
                flipped_y = board_height - 1 - pos_y
                self._draw_cell(
                    draw,
                    board_x + pos_x * cell_size,
                    board_y + flipped_y * cell_size,
                    cell_size,
                    color,
                    padding=1
                )

            # Draw head with eyes
            if len(snake) > 0:
                head_x, head_y = snake[0]
                flipped_head_y = board_height - 1 - head_y
                head_color = darken_color(snake_colors[idx], 0.3)

                # Head
                self._draw_cell(
                    draw,
                    board_x + head_x * cell_size,
                    board_y + flipped_head_y * cell_size,
                    cell_size,
                    head_color,
                    padding=0
                )

                # Eyes
                eye_size = max(2, cell_size // 5)
                eye_y = board_y + flipped_head_y * cell_size + cell_size // 3

                # Left eye
                draw.ellipse(
                    [
                        board_x + head_x * cell_size + cell_size // 4,
                        eye_y,
                        board_x + head_x * cell_size + cell_size // 4 + eye_size,
                        eye_y + eye_size
                    ],
                    fill=(255, 255, 255)
                )

                # Right eye
                draw.ellipse(
                    [
                        board_x + head_x * cell_size + 3 * cell_size // 4 - eye_size,
                        eye_y,
                        board_x + head_x * cell_size + 3 * cell_size // 4,
                        eye_y + eye_size
                    ],
                    fill=(255, 255, 255)
                )

    def _draw_cell(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        size: int,
        color: Tuple[int, int, int],
        padding: int = 1
    ):
        """Draw a single cell (for snake body or apple)"""
        draw.rectangle(
            [x + padding, y + padding, x + size - padding, y + size - padding],
            fill=color
        )

    def generate_video(
        self,
        game_id: str,
        replay_data: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate a video from a game replay

        Args:
            game_id: The game ID to generate video for
            replay_data: Optional replay data (if None, will load from local completed_games)
            output_path: Optional output path (if None, uses temp file)

        Returns:
            Path to the generated video file
        """
        logger.info(f"Starting video generation for game {game_id}")

        # Load replay data if not provided
        if replay_data is None:
            logger.info(f"Loading replay data for game {game_id} from local files")
            replay_path = os.path.join(backend_path, "completed_games", f"snake_game_{game_id}.json")
            if not os.path.exists(replay_path):
                raise ValueError(f"Could not find replay data for game {game_id} at {replay_path}")
            with open(replay_path, 'r') as f:
                replay_data = json.load(f)

        metadata, rounds = self._normalize_replay(replay_data)
        model_ids = list(metadata.get('models', {}).keys())
        model_names = list(metadata.get('models', {}).values())
        if len(model_ids) < 2:
            # Ensure we always have two placeholders to render
            while len(model_ids) < 2:
                model_ids.append(str(len(model_ids)))
        if len(model_names) < 2:
            while len(model_names) < 2:
                model_names.append(f"Player {len(model_names)}")

        logger.info(f"Rendering {len(rounds)} frames for {model_names[0]} vs {model_names[1]}")

        # Generate frames
        frames = []
        for i, round_data in enumerate(rounds):
            if i % 10 == 0:
                logger.info(f"Rendering frame {i + 1}/{len(rounds)}")

            frame = self.render_frame(
                round_data,
                model_ids,
                model_names,
                i,
                len(rounds)
            )
            frames.append(np.array(frame))

        logger.info(f"Rendered {len(frames)} frames, creating video...")

        # Create output path if not provided
        if output_path is None:
            temp_dir = tempfile.gettempdir()
            output_path = os.path.join(temp_dir, f"{game_id}_replay.mp4")

        # Create video using MoviePy
        clip = ImageSequenceClip(frames, fps=self.fps)
        clip.write_videofile(
            output_path,
            codec='libx264',
            audio=False,
            verbose=False,
            logger=None
        )

        logger.info(f"Video created successfully at {output_path}")
        return output_path

    def generate_and_save(self, game_id: str, output_dir: Optional[str] = None) -> str:
        """
        Generate video and save to local completed_games directory

        Args:
            game_id: The game ID to process
            output_dir: Optional output directory (defaults to completed_games)

        Returns:
            Path to the saved video file
        """
        if output_dir is None:
            output_dir = os.path.join(backend_path, "completed_games")
        
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{game_id}_replay.mp4")
        
        video_path = self.generate_video(game_id, output_path=output_path)
        logger.info(f"Video saved to {video_path}")
        return video_path


def get_video_local_path(game_id: str) -> str:
    """
    Get the local path for a game's video

    Args:
        game_id: The game ID

    Returns:
        Local path to the video file
    """
    return os.path.join(backend_path, "completed_games", f"{game_id}_replay.mp4")
