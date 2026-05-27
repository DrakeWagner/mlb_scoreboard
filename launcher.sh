#!/bin/bash
# MLB Scoreboard Launcher
# start producer and consumer

PROJECT_DIR="/home/drakewagner/mlb_scoreboard"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

# start producer
echo "Starting Producer..."
python3 "$PROJECT_DIR/producer.py" > "$LOG_DIR/producer.log" 2>&1 &
PRODUCER_PID=$!
echo "Producer started (PID: $PRODUCER_PID)"

# allow producer to start
sleep 5

# start consumer
echo "Starting Consumer..."
python3 "$PROJECT_DIR/scoreboard_consumer.py"

# kill producer if consumer dies
kill $PRODUCER_PID 2>/dev/null
echo "Scoreboard stopped."