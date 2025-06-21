#!/usr/bin/env python3
"""
Kafka Producer for ANY order book csv.

Quickstart:
    python kafka_producer.py --file <filename>.csv --topic <topic>
"""


"""
All this does is read a csv file and formats the output as json to a given kafka broker. 
Quite reusable, especially given any level of order book. If I had more time, I'd prettify/add sorting 
features (which I might later!) The stop function is kind of a hack, I'd imagine there's probably a better way to do this.
"""

import argparse # not really for this project :)
import json
import signal
import sys
import time
from datetime import datetime
from kafka import KafkaProducer
from kafka.errors import KafkaError
import pandas as pd



class CSVKafkaProducer:
    """
    Kafka producer for streaming CSV data as JSON messages with time-accurate replay
    """
    
    def __init__(self, bootstrap_servers: str = 'localhost:9092'):
        """
        Initialize the CSV Kafka producer
        
        Args:
            bootstrap_servers: Kafka bootstrap servers
        """
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self.running = False
        self.message_count = 0
    
    def setup_producer(self) -> bool:
        """
        Setup Kafka producer
        
        Returns:
            bool: True if producer setup successfully
        """
            
        try:
            print(f"Connecting to Kafka broker at {self.bootstrap_servers}...")
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda x: json.dumps(x, default=str).encode('utf-8')
            )
            print(f"Successfully connected to Kafka broker: {self.bootstrap_servers}")
            return True
            
        except Exception as e:
            print(f"Failed to connect to Kafka broker: {e}")
            return False
    
    def load_csv_file(self, file_path: str):
        """
        Load data from CSV file
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            DataFrame with loaded data or None if failed
        """
        
        try:
            if not file_path.lower().endswith('.csv'):
                print(f"ERROR: Only CSV files are supported. Got: {file_path}")
                return None
            
            print(f"Loading CSV file: {file_path}")
            df = pd.read_csv(file_path)
            
            # Convert timestamp columns
            timestamp_cols = ['ts_recv', 'ts_event', 'timestamp']
            for col in timestamp_cols:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col])
            
            # Sort by ts_event (preferred for time-accurate replay)
            if 'ts_event' in df.columns:
                df = df.sort_values('ts_event').reset_index(drop=True)
                print(f"Data sorted by ts_event for time-accurate replay")
            else:
                print("WARNING: No ts_event column found - will stream without timing")
            
            print(f"Loaded {len(df)} records")
            
            return df
            
        except Exception as e:
            print(f"ERROR: Failed to load CSV file {file_path}: {e}")
            return None
    
    def produce_from_csv(self, file_path: str, topic: str) -> None:
        """
        Read CSV and produce messages to Kafka with time-accurate replay
        
        Args:
            file_path: Path to CSV file
            topic: Kafka topic name
        """
        df = self.load_csv_file(file_path)
        if df is None:
            return
        
        if not self.setup_producer():
            return
        
        self.running = True
        
        # Setup signal handlers @exit (ctrl+c)
        def signal_handler(signum, frame):
            print("\nStopping producer...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        # prettify my info :)

        print(f"\n---------------Kafka Producer Started---------------")
        print(f"File: {file_path}")
        print(f"Topic: {topic}")
        print(f"Total records: {len(df)}")
        print("Press Ctrl+C to stop...")
        print("-" * 50)
        
        # Check if we have ts_event for time-accurate replay
        has_ts_event = 'ts_event' in df.columns
        if has_ts_event:
            print("Time-accurate replay enabled using ts_event timestamps")
        else:
            print("Streaming without timing (you messed up somewhere and we can't read the csv)")
        
        try:
            start_time = time.time()
            first_timestamp = None
            
            if has_ts_event:
                first_timestamp = df.iloc[0]['ts_event']
                print(f"First timestamp: {first_timestamp}")
            for _, row in df.iterrows():
                if not self.running:             # needed to stop the stream @exit
                    break
                
                # Time-accurate replay using ts_event
                if has_ts_event and first_timestamp:
                    current_timestamp = row['ts_event']
                    elapsed_data_time = (current_timestamp - first_timestamp).total_seconds()
                    elapsed_real_time = time.time() - start_time
                    
                    # Basic sleep block to maintain original timing
                    if elapsed_data_time > elapsed_real_time:
                        sleep_time = elapsed_data_time - elapsed_real_time
                        if sleep_time > 0:
                            time.sleep(sleep_time)
                
                # Let's convert row to dict for processing
                message_data = {}
                for k, v in row.to_dict().items():
                    if pd.isna(v):
                        message_data[k] = None
                    elif hasattr(v, 'isoformat'):  # Handle datetime objects
                        message_data[k] = v.isoformat()
                    else:
                        message_data[k] = v
                
                try:

                    self.producer.send(topic, value=message_data)
                    self.message_count += 1
                    
                    # Log progress because I'm impatient
                    if self.message_count % 1000 == 0:
                        print(f"Produced {self.message_count}/{len(df)} messages")
                        
                except KafkaError as e:
                    print(f"ERROR: Failed to send message: {e}")
                
                except Exception as e:
                    print(f"ERROR: Error processing message: {e}")
        
        except KeyboardInterrupt:
            print("\nProduction interrupted by user")
        
        except Exception as e:
            print(f"ERROR: Error in production loop: {e}")
        
        finally:
            self.stop()
        
        print(f"\nTotal messages produced: {self.message_count}")
    
    def stop(self) -> None:
        """Stop the producer"""
        self.running = False
        if self.producer:
            print("Flushing remaining messages...")
            self.producer.flush()
            self.producer.close()
            print("Kafka producer closed")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Kafka Producer for CSV Files')
    
    # Required arguments
    parser.add_argument('--file', required=True,
                        help='CSV file to read and produce to Kafka')
    
    parser.add_argument('--topic', required=True,
                        help='Kafka topic name')
    
    # Optional Kafka configuration
    parser.add_argument('--kafka-servers', default='localhost:9092',
                        help='Kafka bootstrap servers')
    
    args = parser.parse_args()
    
    # Create and start producer
    producer = CSVKafkaProducer(bootstrap_servers=args.kafka_servers)
    
    print(f"Starting Kafka Producer for CSV file: {args.file}")
    
    producer.produce_from_csv(
        file_path=args.file,
        topic=args.topic
    )

if __name__ == '__main__':
    main() 