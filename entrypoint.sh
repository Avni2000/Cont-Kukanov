#!/bin/bash

# Wait for Kafka to be ready
echo "Waiting for Kafka to be ready..."
while ! nc -z kafka 9092; do
  sleep 1
done

echo "Kafka is ready. Starting producer..."

# Use environment variables with defaults
KAFKA_SERVERS=${KAFKA_SERVERS:-kafka:9092}
TOPIC_NAME=${TOPIC_NAME:-market_data}
CSV_FILE=${CSV_FILE:-l1_day.csv}

# Start the producer
python kafka_producer.py \
  --file "$CSV_FILE" \
  --topic "$TOPIC_NAME" \
  --kafka-servers "$KAFKA_SERVERS" \
  --fast-mode 