#!/usr/bin/env python3
"""
Smart Order Router Benchmark with Time-Accurate Kafka Streaming

This module implements a comprehensive benchmarking system for the Smart Order Router
that includes:
- Time-accurate parsing of l1_day.csv and streaming to Kafka
- Parameter optimization over lambda_over, lambda_under, theta_queue
- Baseline algorithm comparisons (Best Ask, TWAP, VWAP)
- JSON output in specified format with savings calculations
"""

import json
import pandas as pd
import numpy as np
from kafka import KafkaProducer, KafkaConsumer
import logging
import argparse
import time
from datetime import datetime, timedelta
import itertools
from typing import Dict, List, Tuple, Any, Optional
import sys
import os
from collections import defaultdict
import signal

# Import existing SOR components
sys.path.append('.')
from smart_order_router import SmartOrderRouter, Venue

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TimeAccurateBenchmarkSOR:
    """
    Time-accurate benchmarking system for Smart Order Router
    """
    
    def __init__(self, kafka_servers='localhost:9092', order_size=5000):
        self.kafka_servers = kafka_servers
        self.order_size = order_size
        self.producer = None
        self.consumer = None
        self.venues_data = []
        self.running = False
        
    def parse_l1_data(self, csv_file='l1_day.csv') -> List[Dict]:
        """
        Parse l1_day.csv and create per-timestamp venue snapshots
        
        Args:
            csv_file: Path to L1 data CSV file
            
        Returns:
            List of venue snapshots with timestamp, publisher_id, ask_px_00, ask_sz_00
        """
        logger.info(f"Loading and parsing {csv_file}...")
        
        try:
            # Read CSV with chunking for large files
            df = pd.read_csv(csv_file)
            logger.info(f"Loaded {len(df)} rows from {csv_file}")
            
            # Convert timestamps
            df['ts_event'] = pd.to_datetime(df['ts_event'])
            df = df.sort_values('ts_event').reset_index(drop=True)
            
            venues_data = []
            
            for _, row in df.iterrows():
                # Create venue snapshot using specified fields
                if pd.notna(row['ask_px_00']) and pd.notna(row['ask_sz_00']) and row['ask_sz_00'] > 0:
                    venue_snapshot = {
                        'timestamp': row['ts_event'].isoformat(),
                        'publisher_id': str(row['publisher_id']),
                        'ask_px_00': float(row['ask_px_00']),
                        'ask_sz_00': int(row['ask_sz_00']),
                        'symbol': row.get('symbol', 'AAPL'),
                        'sequence': row.get('sequence', 0)
                    }
                    venues_data.append(venue_snapshot)
            
            logger.info(f"Created {len(venues_data)} valid venue snapshots")
            self.venues_data = venues_data
            return venues_data
            
        except Exception as e:
            logger.error(f"Error parsing L1 data: {e}")
            return []
    
    def setup_kafka_producer(self):
        """Setup Kafka producer with optimization settings"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                batch_size=65536,
                linger_ms=5,
                compression_type='gzip',
                max_in_flight_requests_per_connection=20,
                buffer_memory=67108864,
                acks=1
            )
            logger.info(f"Kafka producer connected to {self.kafka_servers}")
            return True
        except Exception as e:
            logger.error(f"Failed to setup Kafka producer: {e}")
            return False
    
    def stream_to_kafka(self, topic='mock_l1_stream', time_accurate=True):
        """
        Stream venue snapshots to Kafka with optional time-accurate replay
        
        Args:
            topic: Kafka topic name
            time_accurate: If True, maintain original timing between messages
        """
        if not self.producer and not self.setup_kafka_producer():
            return False
        
        logger.info(f"Streaming {len(self.venues_data)} snapshots to topic '{topic}'")
        logger.info(f"Time-accurate replay: {time_accurate}")
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info("Stopping Kafka streaming...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        
        self.running = True
        start_time = time.time()
        first_timestamp = None
        
        if time_accurate and self.venues_data:
            first_timestamp = pd.to_datetime(self.venues_data[0]['timestamp'])
            logger.info(f"First timestamp: {first_timestamp}")
        
        try:
            for i, venue_snapshot in enumerate(self.venues_data):
                if not self.running:
                    break
                
                # Time-accurate replay
                if time_accurate and first_timestamp:
                    current_timestamp = pd.to_datetime(venue_snapshot['timestamp'])
                    elapsed_data_time = (current_timestamp - first_timestamp).total_seconds()
                    elapsed_real_time = time.time() - start_time
                    
                    if elapsed_data_time > elapsed_real_time:
                        sleep_time = elapsed_data_time - elapsed_real_time
                        if sleep_time > 0:
                            time.sleep(sleep_time)
                
                # Create message key
                key = f"{venue_snapshot['publisher_id']}_{venue_snapshot['timestamp']}"
                
                # Send message
                self.producer.send(topic, key=key, value=venue_snapshot)
                
                # Progress logging
                if (i + 1) % 5000 == 0:
                    logger.info(f"Streamed {i + 1}/{len(self.venues_data)} snapshots")
            
            self.producer.flush()
            logger.info("Kafka streaming completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error during Kafka streaming: {e}")
            return False
    
    def parameter_search(self, param_ranges: Dict) -> Tuple[Dict, Dict]:
        """
        Search over parameter combinations to find optimal configuration
        
        Args:
            param_ranges: Dictionary with parameter ranges:
                         {'lambda_over': (min, max), 'lambda_under': (min, max), 'theta_queue': (min, max)}
        
        Returns:
            Tuple of (best_parameters, best_result)
        """
        logger.info("Starting parameter optimization...")
        
        # Generate parameter combinations
        lambda_over_vals = np.linspace(param_ranges['lambda_over'][0], param_ranges['lambda_over'][1], 5)
        lambda_under_vals = np.linspace(param_ranges['lambda_under'][0], param_ranges['lambda_under'][1], 5)
        theta_queue_vals = np.linspace(param_ranges['theta_queue'][0], param_ranges['theta_queue'][1], 5)
        
        total_combinations = len(lambda_over_vals) * len(lambda_under_vals) * len(theta_queue_vals)
        logger.info(f"Testing {total_combinations} parameter combinations")
        
        best_params = None
        best_cost = float('inf')
        best_result = None
        
        # Use a subset of data for parameter optimization (for speed)
        test_data = self.venues_data[::50]  # Every 50th snapshot
        logger.info(f"Using {len(test_data)} snapshots for parameter optimization")
        
        for i, (lambda_over, lambda_under, theta_queue) in enumerate(
            itertools.product(lambda_over_vals, lambda_under_vals, theta_queue_vals)
        ):
            if i % 10 == 0:
                logger.info(f"Testing combination {i+1}/{total_combinations}")
            
            # Test current parameters
            result = self._test_sor_parameters(lambda_over, lambda_under, theta_queue, test_data)
            
            if result and result['total_cash'] < best_cost:
                best_cost = result['total_cash']
                best_params = {
                    'lambda_over': round(lambda_over, 3),
                    'lambda_under': round(lambda_under, 3),
                    'theta_queue': round(theta_queue, 3)
                }
                best_result = result
        
        logger.info(f"Best parameters: {best_params} with cost: {best_cost}")
        return best_params, best_result
    
    def _test_sor_parameters(self, lambda_over: float, lambda_under: float, theta_queue: float, 
                           test_data: List[Dict]) -> Optional[Dict]:
        """Test specific parameter combination"""
        try:
            sor = SmartOrderRouter(
                order_size=self.order_size,
                lambda_over=lambda_over,
                lambda_under=lambda_under,
                theta_queue=theta_queue
            )
            
            total_cash = 0
            total_shares = 0
            num_executions = 0
            
            # Group snapshots by timestamp to create market snapshots
            timestamp_groups = defaultdict(list)
            for snapshot in test_data:
                timestamp_groups[snapshot['timestamp']].append(snapshot)
            
            # Test on market snapshots
            for timestamp, venues_at_time in list(timestamp_groups.items())[:100]:  # Limit for speed
                if len(venues_at_time) >= 2:  # Need multiple venues
                    venues_data = []
                    for venue in venues_at_time:
                        venues_data.append({
                            'venue_id': venue['publisher_id'],
                            'ask': venue['ask_px_00'],
                            'ask_size': min(venue['ask_sz_00'], self.order_size),  # Cap at order size
                            'fee': 0.003,
                            'rebate': 0.001
                        })
                    
                    result = sor.optimize_allocation(venues_data)
                    if result:
                        total_cash += result['execution_summary']['cash_spent']
                        total_shares += result['execution_summary']['total_executed']
                        num_executions += 1
            
            if num_executions > 0:
                avg_fill_px = total_cash / total_shares if total_shares > 0 else 0
                return {
                    'total_cash': total_cash,
                    'avg_fill_px': avg_fill_px,
                    'num_executions': num_executions
                }
                
        except Exception as e:
            logger.debug(f"Error testing parameters: {e}")
        
        return None
    
    def compute_baselines(self) -> Dict[str, Dict]:
        """
        Compute baseline algorithms: Best Ask, TWAP, VWAP
        
        Returns:
            Dictionary with baseline results
        """
        logger.info("Computing baseline algorithms...")
        
        baselines = {
            'best_ask': self._compute_best_ask(),
            'twap': self._compute_twap(),
            'vwap': self._compute_vwap()
        }
        
        return baselines
    
    def _compute_best_ask(self) -> Dict:
        """Naive best ask strategy - always fill at lowest available ask"""
        total_cash = 0
        total_shares = 0
        
        # Group snapshots by timestamp
        timestamp_groups = defaultdict(list)
        for snapshot in self.venues_data[::100]:  # Sample for speed
            timestamp_groups[snapshot['timestamp']].append(snapshot)
        
        for timestamp, venues_at_time in timestamp_groups.items():
            if venues_at_time:
                # Find best (lowest) ask
                best_venue = min(venues_at_time, key=lambda x: x['ask_px_00'])
                shares_to_fill = min(self.order_size, best_venue['ask_sz_00'])
                
                cash_cost = shares_to_fill * (best_venue['ask_px_00'] + 0.003)  # Add fee
                total_cash += cash_cost
                total_shares += shares_to_fill
        
        avg_fill_px = total_cash / total_shares if total_shares > 0 else 0
        
        return {
            'total_cash': total_cash,
            'avg_fill_px': avg_fill_px
        }
    
    def _compute_twap(self) -> Dict:
        """TWAP strategy - execute in equal 60-second intervals"""
        total_cash = 0
        total_shares = 0
        
        # Group snapshots into 60-second intervals
        if not self.venues_data:
            return {'total_cash': 0, 'avg_fill_px': 0}
        
        start_time = pd.to_datetime(self.venues_data[0]['timestamp'])
        current_interval = start_time
        interval_duration = timedelta(seconds=60)
        
        interval_data = defaultdict(list)
        
        for snapshot in self.venues_data[::100]:  # Sample for speed
            snapshot_time = pd.to_datetime(snapshot['timestamp'])
            interval_key = int((snapshot_time - start_time).total_seconds() // 60)
            interval_data[interval_key].append(snapshot)
        
        # Execute equal amounts in each interval
        shares_per_interval = self.order_size // len(interval_data) if interval_data else 0
        
        for interval_key, venues_in_interval in interval_data.items():
            if venues_in_interval:
                # Use volume-weighted average price in interval
                total_value = sum(v['ask_px_00'] * v['ask_sz_00'] for v in venues_in_interval)
                total_volume = sum(v['ask_sz_00'] for v in venues_in_interval)
                
                if total_volume > 0:
                    vwap_price = total_value / total_volume
                    shares_executed = min(shares_per_interval, total_volume)
                    cash_cost = shares_executed * (vwap_price + 0.003)  # Add fee
                    
                    total_cash += cash_cost
                    total_shares += shares_executed
        
        avg_fill_px = total_cash / total_shares if total_shares > 0 else 0
        
        return {
            'total_cash': total_cash,
            'avg_fill_px': avg_fill_px
        }
    
    def _compute_vwap(self) -> Dict:
        """VWAP strategy - weight execution by displayed size"""
        total_cash = 0
        total_shares = 0
        
        # Group snapshots by timestamp
        timestamp_groups = defaultdict(list)
        for snapshot in self.venues_data[::100]:  # Sample for speed
            timestamp_groups[snapshot['timestamp']].append(snapshot)
        
        for timestamp, venues_at_time in timestamp_groups.items():
            if venues_at_time:
                # Calculate VWAP for this timestamp
                total_value = sum(v['ask_px_00'] * v['ask_sz_00'] for v in venues_at_time)
                total_volume = sum(v['ask_sz_00'] for v in venues_at_time)
                
                if total_volume > 0:
                    vwap_price = total_value / total_volume
                    shares_to_execute = min(self.order_size, total_volume)
                    cash_cost = shares_to_execute * (vwap_price + 0.003)  # Add fee
                    
                    total_cash += cash_cost
                    total_shares += shares_to_execute
        
        avg_fill_px = total_cash / total_shares if total_shares > 0 else 0
        
        return {
            'total_cash': total_cash,
            'avg_fill_px': avg_fill_px
        }
    
    def calculate_savings_bps(self, optimized_result: Dict, baselines: Dict) -> Dict:
        """
        Calculate savings in basis points vs baselines
        
        Args:
            optimized_result: SOR optimization result
            baselines: Baseline algorithm results
            
        Returns:
            Dictionary with savings in basis points
        """
        optimized_cost = optimized_result['total_cash']
        savings_bps = {}
        
        for baseline_name, baseline_result in baselines.items():
            baseline_cost = baseline_result['total_cash']
            if baseline_cost > 0:
                savings = (baseline_cost - optimized_cost) / baseline_cost * 10000  # Convert to bps
                savings_bps[baseline_name] = round(savings, 1)
            else:
                savings_bps[baseline_name] = 0.0
        
        return savings_bps
    
    def run_full_benchmark(self, csv_file='l1_day.csv', kafka_topic='mock_l1_stream',
                          stream_to_kafka=True, param_ranges=None) -> Dict:
        """
        Run complete benchmarking pipeline
        
        Args:
            csv_file: L1 data CSV file path
            kafka_topic: Kafka topic for streaming
            stream_to_kafka: Whether to stream data to Kafka
            param_ranges: Parameter search ranges
            
        Returns:
            Complete benchmark results in JSON format
        """
        logger.info("=== Starting Full SOR Benchmark ===")
        
        # Default parameter ranges
        if param_ranges is None:
            param_ranges = {
                'lambda_over': (0.1, 1.0),
                'lambda_under': (0.1, 1.0),
                'theta_queue': (0.1, 0.5)
            }
        
        # 1. Parse L1 data
        logger.info("Step 1: Parsing L1 data...")
        venues_data = self.parse_l1_data(csv_file)
        if not venues_data:
            logger.error("Failed to parse L1 data")
            return {}
        
        # 2. Stream to Kafka (optional)
        if stream_to_kafka:
            logger.info("Step 2: Streaming to Kafka...")
            self.stream_to_kafka(kafka_topic, time_accurate=False)  # Disable timing for benchmark
        
        # 3. Parameter search
        logger.info("Step 3: Parameter optimization...")
        best_params, optimized_result = self.parameter_search(param_ranges)
        
        if not best_params or not optimized_result:
            logger.error("Parameter optimization failed")
            return {}
        
        # 4. Compute baselines
        logger.info("Step 4: Computing baselines...")
        baselines = self.compute_baselines()
        
        # 5. Calculate savings
        logger.info("Step 5: Calculating savings...")
        savings_bps = self.calculate_savings_bps(optimized_result, baselines)
        
        # 6. Format final results
        results = {
            "best_parameters": best_params,
            "optimized": {
                "total_cash": round(optimized_result['total_cash'], 2),
                "avg_fill_px": round(optimized_result['avg_fill_px'], 4)
            },
            "baselines": {
                baseline_name: {
                    "total_cash": round(result['total_cash'], 2),
                    "avg_fill_px": round(result['avg_fill_px'], 4)
                }
                for baseline_name, result in baselines.items()
            },
            "savings_vs_baselines_bps": savings_bps
        }
        
        logger.info("=== Benchmark Complete ===")
        return results


def main():
    """Main entry point for benchmarking"""
    parser = argparse.ArgumentParser(description="Smart Order Router Benchmark")
    parser.add_argument('--csv-file', default='l1_day.csv', help='L1 data CSV file')
    parser.add_argument('--kafka-servers', default='localhost:9092', help='Kafka bootstrap servers')
    parser.add_argument('--kafka-topic', default='mock_l1_stream', help='Kafka topic name')
    parser.add_argument('--order-size', type=int, default=5000, help='Order size for execution')
    parser.add_argument('--no-kafka', action='store_true', help='Skip Kafka streaming')
    parser.add_argument('--output-file', help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Initialize benchmark system
    benchmark = TimeAccurateBenchmarkSOR(
        kafka_servers=args.kafka_servers, 
        order_size=args.order_size
    )
    
    # Run full benchmark
    results = benchmark.run_full_benchmark(
        csv_file=args.csv_file,
        kafka_topic=args.kafka_topic,
        stream_to_kafka=not args.no_kafka
    )
    
    if results:
        # Output results as JSON
        json_output = json.dumps(results, indent=2)
        
        if args.output_file:
            with open(args.output_file, 'w') as f:
                f.write(json_output)
            logger.info(f"Results saved to {args.output_file}")
        
        # Always print to stdout as required
        print(json_output)
    else:
        logger.error("Benchmark failed to produce results")
        sys.exit(1)


if __name__ == '__main__':
    main() 