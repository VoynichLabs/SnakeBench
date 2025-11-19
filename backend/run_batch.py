import argparse
import concurrent.futures
import os
import json
from typing import Dict, List, Any, Tuple # Added Tuple

# Import data access functions for loading models from Supabase
from data_access.api_queries import get_model_by_name, get_all_models 
# Assuming main.py is in the same directory or accessible via PYTHONPATH
from main import run_simulation, LLMPlayer # Import LLMPlayer for type hinting if needed later

# Optional: Import tqdm if you plan to add it later for progress bars
# from tqdm import tqdm 

def run_batch_simulations():
    parser = argparse.ArgumentParser(
        description="Run batch Snake game simulations for a target model against others."
    )
    # Batch configuration arguments
    parser.add_argument("--target-model", type=str, required=True,
                        help="The primary model ID to test against others.")
    parser.add_argument("--num-simulations", type=int, required=True,
                        help="Number of times to run the simulation for EACH opponent matchup.")
    parser.add_argument("--max-output-cost-per-million", type=float, default=None,
                        help="Maximum output cost per million tokens allowed for OPPONENT models. "
                             "Opponents without pricing info or exceeding this cost will be excluded.")
    parser.add_argument("--max-workers", type=int, default=os.cpu_count(),
                        help="Maximum number of parallel simulation workers (threads).")

    # Game configuration arguments (mirroring main.py)
    parser.add_argument("--width", type=int, default=10,
                        help="Width of the board (default: 10).")
    parser.add_argument("--height", type=int, default=10,
                        help="Height of the board (default: 10).")
    parser.add_argument("--max_rounds", type=int, default=100,
                        help="Maximum number of rounds per game (default: 100).")
    parser.add_argument("--num_apples", type=int, default=5,
                        help="Number of apples on the board (default: 5).")

    args = parser.parse_args()

    # 1. Load all model configurations from Supabase
    print("Loading model configurations from database...")
    all_models_list = get_all_models(active_only=True)
    print(f"Loaded {len(all_models_list)} model configurations.")

    # 2. Find the target model configuration
    target_config = get_model_by_name(args.target_model)
    if target_config is None:
        raise ValueError(f"Target model '{args.target_model}' not found in database.")
    print(f"Found target model: {args.target_model}")

    # 3. Filter opponent models
    print("Filtering opponent models...")
    opponent_configs: List[Dict[str, Any]] = []
    for model in all_models_list:
        if model['name'] == args.target_model:
            continue # Don't play against self

        # Check if pricing info exists
        if model.get("pricing_output") is None:
            print(f" - Skipping opponent {model['name']}: Missing pricing_output.")
            continue

        output_cost = model["pricing_output"]

        # Check against cost threshold if provided
        if args.max_output_cost_per_million is not None and output_cost > args.max_output_cost_per_million:
            print(f" - Skipping opponent {model['name']}: Output cost ({output_cost:.2f}) exceeds threshold ({args.max_output_cost_per_million:.2f}).")
            continue

        # If checks pass, add to valid opponents
        print(f" + Including opponent: {model['name']} (Output Cost: {output_cost:.2f})")
        opponent_configs.append(model)
        
    if not opponent_configs:
        print("No valid opponents found after filtering. Exiting.")
        return
        
    print(f"Found {len(opponent_configs)} valid opponents after filtering.")
    print(f"Opponent configs: {[x['name'] for x in opponent_configs]}")

    # 4. Generate list of simulation tasks
    print(f"Generating simulation tasks ({args.num_simulations} runs per opponent)...")
    simulation_tasks: List[Tuple[Dict, Dict, argparse.Namespace]] = []
    for opponent_config in opponent_configs:
        for i in range(args.num_simulations):
            # Append tuple: (target_config, opponent_config, game_params)
            simulation_tasks.append((target_config, opponent_config, args)) 
            # Could also add opponent_config vs target_config if needed, but sticking to target vs opponent for now

    print(f"Generated {len(simulation_tasks)} total simulation tasks.")

    # 5. Execute simulations in parallel using ThreadPoolExecutor
    print(f"Starting simulations with up to {args.max_workers} workers...")
    futures = []
    results = [] # To store results later if needed

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        for task_index, (config1, config2, params) in enumerate(simulation_tasks):
            print(f"Submitting task {task_index+1}/{len(simulation_tasks)}: {config1['name']} vs {config2['name']}")
            # Submit the run_simulation function with the task arguments
            future = executor.submit(run_simulation, config1, config2, params)
            futures.append(future)

        # Process results as they complete (Basic structure, can be expanded)
        print("Waiting for simulations to complete...")
        # Example using as_completed (without tqdm yet)
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                results.append(result)
                print(f"Completed game {result.get('game_id', 'UNKNOWN')}. Final scores: {result.get('final_scores', {})}")
            except Exception as exc:
                print(f'A simulation generated an exception: {exc}')
                # Handle exceptions appropriately, maybe log them
        
    print("\nAll batch simulations completed.")
    # Optional: Add summary logic here based on the collected 'results' list

if __name__ == "__main__":
    run_batch_simulations()