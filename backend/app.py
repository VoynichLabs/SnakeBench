import os
import json
import random
import logging
from flask import Flask, jsonify, request
from dotenv import load_dotenv

# Import database query functions
from data_access.api_queries import (
    get_all_models,
    get_model_by_name,
    get_games,
    get_game_by_id,
    get_total_games_count
)

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


# New DB-backed endpoints for Phase 3

@app.route("/api/models", methods=["GET"])
def get_models():
    """
    Get all models with their statistics, sorted by ELO rating.

    Query parameters:
    - active_only: If true, only return active models (default: false)

    Returns models list similar to stats_simple.json format.
    """
    try:
        active_only = request.args.get("active_only", default=False, type=bool)
        models = get_all_models(active_only=active_only)

        # Transform to match stats_simple.json format for compatibility
        aggregated_data = {}
        for model in models:
            aggregated_data[model['name']] = {
                'elo_rating': model['elo_rating'],
                'wins': model['wins'],
                'losses': model['losses'],
                'ties': model['ties'],
                'apples_eaten': model['apples_eaten'],
                'games_played': model['games_played'],
                'provider': model['provider'],
                'test_status': model['test_status'],
                'is_active': model['is_active']
            }

        total_games = get_total_games_count()

        return jsonify({
            "totalGames": total_games,
            "models": models,
            "aggregatedData": aggregated_data
        })

    except Exception as error:
        logging.error(f"Error fetching models: {error}")
        return jsonify({"error": "Failed to load models"}), 500


@app.route("/api/models/<model_name>", methods=["GET"])
def get_model_details(model_name):
    """
    Get detailed statistics for a specific model.

    Returns:
    - Model stats
    - Recent games involving this model
    """
    try:
        model = get_model_by_name(model_name)

        if model is None:
            return jsonify({"error": f"Model '{model_name}' not found"}), 404

        # Get recent games for this model
        # TODO: Add a specialized query for model-specific games
        # For now, return just the model stats

        total_games = model['games_played']

        return jsonify({
            "totalGames": total_games,
            "model": model,
            "aggregatedData": {
                model_name: {
                    'elo_rating': model['elo_rating'],
                    'wins': model['wins'],
                    'losses': model['losses'],
                    'ties': model['ties'],
                    'apples_eaten': model['apples_eaten'],
                    'games_played': model['games_played'],
                    'provider': model['provider'],
                    'test_status': model['test_status'],
                    'is_active': model['is_active']
                }
            }
        })

    except Exception as error:
        logging.error(f"Error fetching model details for {model_name}: {error}")
        return jsonify({"error": "Failed to load model details"}), 500


# Endpoint to get a list of games - now DB-backed with replay file loading
# Mimics functionality in frontend/src/app/api/games/route.ts
@app.route("/api/games", methods=["GET"])
def get_games_endpoint():
    try:
        print("Getting games from database")
        # Get the number of games to return from query parameters, default to 10
        limit = request.args.get("limit", default=10, type=int)
        offset = request.args.get("offset", default=0, type=int)
        sort_by = request.args.get("sort_by", default="start_time", type=str)

        # Get games from database
        games_data = get_games(limit=limit, offset=offset, sort_by=sort_by)

        # Load replay files for each game to maintain compatibility with frontend
        valid_games = []
        for game_data in games_data:
            replay_path = game_data.get('replay_path')
            if replay_path and os.path.exists(replay_path):
                try:
                    with open(replay_path, "r", encoding="utf-8") as f:
                        replay_json = json.load(f)
                        valid_games.append(replay_json)
                except Exception as e:
                    logging.error(f"Error reading replay file {replay_path}: {e}")
                    continue
            else:
                logging.warning(f"Replay file not found: {replay_path}")

        print(f"Returning {len(valid_games)} games")
        return jsonify({"games": valid_games})

    except Exception as error:
        logging.error(f"Error fetching games: {error}")
        return jsonify({"error": "Failed to load game list"}), 500


# Endpoint for stats API - now DB-backed
# Mimics functionality in frontend/src/app/api/stats/route.ts
@app.route("/api/stats", methods=["GET"])
def get_stats():
    # Get the query parameters: simple for summary stats,
    # model for full stats for a single model
    simple = request.args.get("simple", default=False, type=bool)
    model = request.args.get("model", default=None, type=str)

    try:
        if simple:
            # Return simple stats from database
            models = get_all_models()
            total_games = get_total_games_count()

            # Transform to match stats_simple.json format
            aggregated_data = {}
            for model_data in models:
                aggregated_data[model_data['name']] = {
                    'elo_rating': model_data['elo_rating'],
                    'wins': model_data['wins'],
                    'losses': model_data['losses'],
                    'ties': model_data['ties'],
                    'apples_eaten': model_data['apples_eaten'],
                    'games_played': model_data['games_played']
                }

            return jsonify({
                "totalGames": total_games,
                "aggregatedData": aggregated_data
            })

        # For full stats, we require a model parameter.
        if model is None:
            return jsonify({"error": "Please provide a model parameter for full stats."}), 400

        # Get model stats from database
        model_data = get_model_by_name(model)

        if model_data is None:
            return jsonify({"error": f"Stats for model '{model}' not found."}), 404

        total_games = model_data['games_played']

        # Return in the same format as before
        return jsonify({
            "totalGames": total_games,
            "aggregatedData": {
                model: {
                    'elo_rating': model_data['elo_rating'],
                    'wins': model_data['wins'],
                    'losses': model_data['losses'],
                    'ties': model_data['ties'],
                    'apples_eaten': model_data['apples_eaten'],
                    'games_played': model_data['games_played']
                }
            }
        })

    except Exception as e:
        logging.error(f"Error loading stats data: {e}")
        return jsonify({"error": "Failed to load stats data."}), 500


# Endpoint to get details for a single game by id - now DB-backed with replay loading
# Mimics functionality in frontend/src/app/api/games/[gameId]/route.ts
@app.route("/api/matches/<match_id>", methods=["GET"])
def get_game_by_id_endpoint(match_id):
    try:
        # Get game metadata from database
        game_data = get_game_by_id(match_id)

        if game_data is None:
            return jsonify({"error": f"Match '{match_id}' not found"}), 404

        # Load the replay file via replay_path
        replay_path = game_data.get('replay_path')

        if not replay_path or not os.path.exists(replay_path):
            logging.error(f"Replay file not found: {replay_path}")
            return jsonify({"error": "Replay file not found"}), 404

        with open(replay_path, "r", encoding="utf-8") as f:
            match_data = json.load(f)

        return jsonify(match_data)

    except Exception as error:
        logging.error(f"Error reading match data for match id {match_id}: {error}")
        return jsonify({"error": "Failed to load match data"}), 500

if __name__ == "__main__":
    # Run the Flask app in debug mode.
    app.run(debug=os.getenv("FLASK_DEBUG"))