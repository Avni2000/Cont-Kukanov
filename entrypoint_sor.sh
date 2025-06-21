#!/bin/bash

# Wait for Kafka to be ready
echo "Waiting for Kafka to be ready..."
while ! nc -z kafka 9092; do
  sleep 1
done

echo "Kafka is ready. Starting SOR Consumer..."

# Use environment variables with defaults
KAFKA_SERVERS=${KAFKA_SERVERS:-kafka:9092}
TOPIC_NAME=${TOPIC_NAME:-market_data}
ORDER_SIZE=${ORDER_SIZE:-5000}
LAMBDA_OVER=${LAMBDA_OVER:-0.01}
LAMBDA_UNDER=${LAMBDA_UNDER:-0.005}
THETA_QUEUE=${THETA_QUEUE:-0.002}
STEP=${STEP:-100}
GREEDY_L2=${GREEDY_L2:-false}

# Build command arguments
CMD_ARGS="--topic $TOPIC_NAME --kafka-servers $KAFKA_SERVERS --order-size $ORDER_SIZE"
CMD_ARGS="$CMD_ARGS --lambda-over $LAMBDA_OVER --lambda-under $LAMBDA_UNDER --theta-queue $THETA_QUEUE"
CMD_ARGS="$CMD_ARGS --step $STEP"

if [ "$GREEDY_L2" = "true" ]; then
    CMD_ARGS="$CMD_ARGS --greedy-l2"
fi

# Start the SOR consumer
echo "Starting SOR with arguments: $CMD_ARGS"
python kafka_sor_consumer.py $CMD_ARGS 