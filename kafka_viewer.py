#!/usr/bin/env python3
"""
Kafka Viewer for JSON Messages

Simple viewer for consuming JSON messages from Kafka topics.

Usage:
    python kafka_viewer.py --topic market_data
"""

import argparse
import json
import signal
import sys
import time
from datetime import datetime

try:
    from kafka import KafkaConsumer
    from kafka.errors import KafkaError
    KAFKA_AVAILABLE = True
except ImportError as e:
    print(f"Kafka not available: {e}")
    KAFKA_AVAILABLE = False

class KafkaJSONViewer:
    """
    Simple Kafka consumer for viewing JSON messages
    """
    
    def __init__(self, bootstrap_servers: str = 'localhost:9092'):
        """
        Initialize the Kafka JSON viewer
        
        Args:
            bootstrap_servers: Kafka bootstrap servers
        """
        self.bootstrap_servers = bootstrap_servers
        self.consumer = None
        self.running = False
        self.message_count = 0
    
    def setup_consumer(self, topics: list) -> bool:
        """
        Setup Kafka consumer
        
        Args:
            topics: List of Kafka topics to consume from
            
        Returns:
            bool: True if consumer setup successfully
        """
        if not KAFKA_AVAILABLE:
            print("Kafka library not available. Please install kafka-python-ng")
            return False
        
        try:
            self.consumer = KafkaConsumer(
                *topics,
                bootstrap_servers=self.bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                group_id='json_viewer_group',
                auto_offset_reset='latest'
            )
            print(f"Kafka consumer connected to {self.bootstrap_servers}")
            print(f"Subscribed to topics: {', '.join(topics)}")
            return True
            
        except Exception as e:
            print(f"Failed to setup Kafka consumer: {e}")
            return False
    
    def view_messages(self, topics: list) -> None:
        """
        Start consuming and displaying messages from Kafka
        
        Args:
            topics: List of Kafka topics to consume from
        """
        if not self.setup_consumer(topics):
            return self.setup_consumer(topics).astype(str)
        
        self.running = True
        
        # Setup signal handlers
        def signal_handler(signum, frame):
            print("Stopping viewer...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        print("-----------------Kafka JSON Viewer Started-----------------")
        print("Press Ctrl+C to stop...")
        print("-" * 50)
        
        try:
            while self.running:
                # Poll for messages with timeout
                message_batch = self.consumer.poll(timeout_ms=1000)
                
                if not message_batch:
                    continue
                
                for topic_partition, messages in message_batch.items():
                    for message in messages:
                        if not self.running:
                            break
                        
                        self.message_count += 1
                        
                        try:
                            # Display the JSON message
                            print(json.dumps(message.value, indent=2))
                            print()  # Empty line for separation
                            
                        except Exception as e:
                            print(f"Error processing message: {e}")
                            continue
        
        except KeyboardInterrupt:
            print("Viewer interrupted by user")
        
        except Exception as e:
            print(f"Error in viewer loop: {e}")
        
        finally:
            self.stop()
        
        print(f" Total messages processed: {self.message_count}")
    
    def stop(self) -> None:
        """Stop the consumer"""
        self.running = False
        if self.consumer:
            self.consumer.close()
            print("Kafka consumer closed")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Kafka JSON Viewer')
    
    # Required arguments
    parser.add_argument('--topic', required=True,
                        help='Kafka topic to consume from')
    
    # Optional Kafka configuration
    parser.add_argument('--kafka-servers', default='localhost:9092',
                        help='Kafka bootstrap servers')
    
    args = parser.parse_args()
    
    # Create and start viewer
    viewer = KafkaJSONViewer(bootstrap_servers=args.kafka_servers)
    
    print(f"Starting Kafka JSON Viewer for topic: {args.topic}")
    
    viewer.view_messages(topics=[args.topic])

if __name__ == '__main__':
    main() 