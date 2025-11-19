#!/bin/bash

# LLMSnake Development Environment Launcher
# This script starts both frontend and backend in a tmux session

SESSION_NAME="llmsnake-dev"

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "Error: tmux is not installed. Please install it first:"
    echo "  macOS: brew install tmux"
    echo "  Linux: sudo apt-get install tmux"
    exit 1
fi

# Kill existing session if it exists
tmux has-session -t $SESSION_NAME 2>/dev/null
if [ $? -eq 0 ]; then
    echo "Killing existing session: $SESSION_NAME"
    tmux kill-session -t $SESSION_NAME
fi

# Create new session with backend
echo "Starting $SESSION_NAME tmux session..."
tmux new-session -d -s $SESSION_NAME -n dev

# Start backend in first pane (activate venv first)
tmux send-keys -t $SESSION_NAME:dev "cd backend && source venv/bin/activate && python app.py" C-m

# Split window vertically and start frontend in the right pane
tmux split-window -h -t $SESSION_NAME:dev
tmux send-keys -t $SESSION_NAME:dev "cd frontend && npm run dev" C-m

# Split the right pane horizontally to add Celery worker at bottom
tmux split-window -v -t $SESSION_NAME:dev.1
tmux send-keys -t $SESSION_NAME:dev "cd backend && source venv/bin/activate && python3.11 -m celery -A celery_app worker --loglevel=info --concurrency=2 --max-tasks-per-child=10" C-m

# Select the left pane (backend) by default
tmux select-pane -t $SESSION_NAME:dev.0

# Attach to the session
echo ""
echo "====================================="
echo "LLMSnake Dev Environment Started!"
echo "====================================="
echo ""
echo "Backend API: Running in left pane"
echo "Frontend: Running in top-right pane"
echo "Celery Worker: Running in bottom-right pane"
echo ""
echo "Tmux Controls:"
echo "  - Switch panes: Ctrl+b then arrow keys or o"
echo "  - Detach session: Ctrl+b then d"
echo "  - Kill session: tmux kill-session -t $SESSION_NAME"
echo ""
echo "Note: Redis must be running for Celery worker"
echo "  Start Redis: brew services start redis"
echo ""
echo "Attaching to tmux session..."
sleep 2

tmux attach-session -t $SESSION_NAME
