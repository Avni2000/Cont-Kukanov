#!/bin/bash

# Wait for Kafka to be ready
echo "Waiting for Kafka to be ready..."
while ! nc -z kafka 9092; do
  sleep 1
done

echo "Kafka is ready. Starting SOR Benchmark System..."

# Use environment variables with defaults
KAFKA_SERVERS=${KAFKA_SERVERS:-kafka:29092}
CSV_FILE=${CSV_FILE:-l1_day.csv}
TOPIC_NAME=${TOPIC_NAME:-mock_l1_stream}
ORDER_SIZE=${ORDER_SIZE:-5000}

echo "=== SOR Benchmark Configuration ==="
echo "Kafka Servers: $KAFKA_SERVERS"
echo "CSV File: $CSV_FILE"
echo "Topic: $TOPIC_NAME"
echo "Order Size: $ORDER_SIZE"
echo "=================================="

# Run the benchmark system
python benchmark_sor.py \
  --kafka-servers "$KAFKA_SERVERS" \
  --csv-file "$CSV_FILE" \
  --kafka-topic "$TOPIC_NAME" \
  --order-size "$ORDER_SIZE" 