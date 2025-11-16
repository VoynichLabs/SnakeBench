#!/bin/bash
# Tmux script to run 5 evaluation workers in separate panes
# Each worker starts with a 2-second delay to avoid race conditions

SESSION_NAME="snake-eval"

# Check if tmux session already exists
tmux has-session -t $SESSION_NAME 2>/dev/null

if [ $? == 0 ]; then
    echo "Session '$SESSION_NAME' already exists. Attaching..."
    tmux attach-session -t $SESSION_NAME
    exit 0
fi

# Create new session with first worker
tmux new-session -d -s $SESSION_NAME -n "workers"

# Split into 5 panes
# First split horizontally to create top and bottom
tmux split-window -h -t $SESSION_NAME:0

# Split top pane vertically twice (creates 3 panes on top)
tmux select-pane -t 0
tmux split-window -v
tmux select-pane -t 0
tmux split-window -v

# Split bottom pane vertically once (creates 2 panes on bottom)
tmux select-pane -t 3
tmux split-window -v

# Now we have 5 panes. Let's start the workers with staggered delays
cd "$(dirname "$0")"

# Pane 0: Worker 1 (no delay)
tmux send-keys -t $SESSION_NAME:0.0 "cd $(pwd) && echo 'Worker 1 starting immediately...' && venv/bin/python cli/run_evaluation_worker.py" C-m

# Pane 1: Worker 2 (2 second delay)
tmux send-keys -t $SESSION_NAME:0.1 "cd $(pwd) && echo 'Worker 2 waiting 2 seconds...' && sleep 2 && venv/bin/python cli/run_evaluation_worker.py" C-m

# Pane 2: Worker 3 (4 second delay)
tmux send-keys -t $SESSION_NAME:0.2 "cd $(pwd) && echo 'Worker 3 waiting 4 seconds...' && sleep 4 && venv/bin/python cli/run_evaluation_worker.py" C-m

# Pane 3: Worker 4 (6 second delay)
tmux send-keys -t $SESSION_NAME:0.3 "cd $(pwd) && echo 'Worker 4 waiting 6 seconds...' && sleep 6 && venv/bin/python cli/run_evaluation_worker.py" C-m

# Pane 4: Worker 5 (8 second delay)
tmux send-keys -t $SESSION_NAME:0.4 "cd $(pwd) && echo 'Worker 5 waiting 8 seconds...' && sleep 8 && venv/bin/python cli/run_evaluation_worker.py" C-m

# Tile all panes evenly
tmux select-layout -t $SESSION_NAME:0 tiled

# Attach to the session
tmux attach-session -t $SESSION_NAME
