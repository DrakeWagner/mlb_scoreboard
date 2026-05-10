#!/bin/bash
# MLB Scoreboard Launcher
# Starts both Producer and Consumer

PROJECT_DIR="/home/drakewagner/mlb_scoreboard"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

# Start Producer in background
echo "Starting Producer..."
python3 "$PROJECT_DIR/producer.py" > "$LOG_DIR/producer.log" 2>&1 &
PRODUCER_PID=$!
echo "Producer started (PID: $PRODUCER_PID)"

# Give producer a moment to start
sleep 3

# Start Consumer
echo "Starting Consumer..."
python3 "$PROJECT_DIR/scoreboard_consumer.py"

# If consumer dies, kill producer too
kill $PRODUCER_PID 2>/dev/null
echo "Scoreboard stopped."