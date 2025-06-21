#!/usr/bin/env python3

import json
import pandas as pd
import numpy as np
from kafka import KafkaProducer, KafkaConsumer
import logging
import argparse
import time
from datetime import datetime, timedelta
import itertools
from typing import Dict, List, Tuple, Any
import sys
import os

# Import existing SOR components
sys.path.append('.')
from smart_order_router import SmartOrderRouter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BenchmarkSOR:
    def __init__(self, kafka_servers='localhost:9092', order_size=5000, fast_mode=False):
        self.kafka_servers = kafka_servers
        self.order_size = order_size
        self.fast_mode = fast_mode
        self.producer = None
        self.venues_data = []
        
    def parse_l1_data(self, csv_file='l1_day.csv'):
        """Parse CSV and create venue snapshots per timestamp"""
        logger.info(f"Loading and parsing {csv_file}...")
        
        df = pd.read_csv(csv_file)
        
        # Convert timestamps
        df['ts_event'] = pd.to_datetime(df['ts_event'])
        df = df.sort_values('ts_event')
        
        venues_data = []
        for _, row in df.iterrows():
            timestamp = row['ts_event'].isoformat() + 'Z'
            
            # Extract venue info using publisher_id, ask_px_00, ask_sz_00
            venue = {
                'timestamp': timestamp,
                'publisher_id': str(row.get('publisher_id', 'venue_0')),
                'ask_price': float(row['ask_px_00']) if pd.notna(row['ask_px_00']) else None,
                'ask_size': int(row['ask_sz_00']) if pd.notna(row['ask_sz_00']) and row['ask_sz_00'] > 0 else None,
                'symbol': row.get('symbol', 'AAPL')
            }
            
            # Only include venues with valid ask data
            if venue['ask_price'] and venue['ask_size']:
                venues_data.append(venue)
        
        logger.info(f"Parsed {len(venues_data)} valid venue snapshots")
        self.venues_data = venues_data
        return venues_data
    
    def stream_to_kafka(self, topic='mock_l1_stream'):
        """Stream venue snapshots to Kafka"""
        self.producer = KafkaProducer(
            bootstrap_servers=self.kafka_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            # Optimization settings for faster throughput
            batch_size=65536,  # Larger batch size
            linger_ms=5,       # Small delay to batch messages
            compression_type='gzip',  # Compress messages
            max_in_flight_requests_per_connection=20,  # More concurrent requests
            buffer_memory=67108864,  # 64MB buffer
            acks=1  # Don't wait for all replicas
        )
        
        logger.info(f"Streaming {len(self.venues_data)} snapshots to topic '{topic}'...")
        
        # Stream with progress updates
        batch_size = 5000 if self.fast_mode else 1000
        
        for i, venue in enumerate(self.venues_data):
            key = f"{venue['publisher_id']}_{venue['timestamp']}"
            self.producer.send(topic, key=key, value=venue)
            
            if (i + 1) % batch_size == 0:
                logger.info(f"Streamed {i + 1}/{len(self.venues_data)} snapshots")
                if self.fast_mode:
                    self.producer.flush()  # Flush more frequently in fast mode
        
        self.producer.flush()
        logger.info("Streaming completed")
    
    def parameter_search(self, param_ranges):
        """Search over parameter combinations"""
        logger.info("Starting parameter optimization...")
        
        best_params = None
        best_cost = float('inf')
        best_result = None
        
        # Generate parameter combinations
        lambda_over_vals = np.linspace(param_ranges['lambda_over'][0], param_ranges['lambda_over'][1], 5)
        lambda_under_vals = np.linspace(param_ranges['lambda_under'][0], param_ranges['lambda_under'][1], 5)
        theta_queue_vals = np.linspace(param_ranges['theta_queue'][0], param_ranges['theta_queue'][1], 5)
        
        total_combinations = len(lambda_over_vals) * len(lambda_under_vals) * len(theta_queue_vals)
        logger.info(f"Testing {total_combinations} parameter combinations")
        
        for i, (lambda_over, lambda_under, theta_queue) in enumerate(
            itertools.product(lambda_over_vals, lambda_under_vals, theta_queue_vals)
        ):
            if i % 10 == 0:
                logger.info(f"Testing combination {i+1}/{total_combinations}")
            
            # Test current parameters
            result = self._test_parameters(lambda_over, lambda_under, theta_queue)
            
            if result and result['total_cost'] < best_cost:
                best_cost = result['total_cost']
                best_params = {
                    'lambda_over': round(lambda_over, 3),
                    'lambda_under': round(lambda_under, 3),
                    'theta_queue': round(theta_queue, 3)
                }
                best_result = result
        
        logger.info(f"Best parameters found: {best_params} with cost: {best_cost}")
        return best_params, best_result
    
    def _test_parameters(self, lambda_over, lambda_under, theta_queue):
        """Test specific parameter combination"""
        try:
            # Create SOR with these parameters
            sor = SmartOrderRouter(
                order_size=self.order_size,
                lambda_over=lambda_over,
                lambda_under=lambda_under,
                theta_queue=theta_queue
            )
            
            # Sample some venue snapshots for testing (use first 100 for speed)
            test_snapshots = self.venues_data[:100] if len(self.venues_data) > 100 else self.venues_data
            
            total_cost = 0
            total_executed = 0
            num_tests = 0
            
            for snapshot in test_snapshots[::10]:  # Test every 10th snapshot
                venues = [{
                    'venue_id': snapshot['publisher_id'],
                    'ask': snapshot['ask_price'],
                    'ask_size': snapshot['ask_size'],
                    'fee': 0.003,  # Default fee
                    'rebate': 0.001  # Default rebate
                }]
                
                if len(venues) > 0 and venues[0]['ask_size'] >= 100:
                    allocation_result = sor.optimize_allocation(venues)
                    if allocation_result:
                        total_cost += allocation_result['total_cost']
                        total_executed += allocation_result['execution_summary']['total_executed']
                        num_tests += 1
            
            if num_tests > 0:
                avg_cost = total_cost / num_tests
                avg_fill_price = total_cost / total_executed if total_executed > 0 else 0
                
                return {
                    'total_cost': avg_cost,
                    'avg_fill_price': avg_fill_price,
                    'total_executed': total_executed,
                    'num_tests': num_tests
                }
        except Exception as e:
            logger.warning(f"Error testing parameters: {e}")
        
        return None
    
    def compute_baselines(self):
        """Compute baseline algorithms: Best Ask, TWAP, VWAP"""
        logger.info("Computing baseline algorithms...")
        
        baselines = {
            'best_ask': self._compute_best_ask(),
            'twap': self._compute_twap(),
            'vwap': self._compute_vwap()
        }
        
        return baselines
    
    def _compute_best_ask(self):
        """Naive best ask strategy - fill at lowest available ask"""
        total_cost = 0
        total_executed = 0
        
        # Group by timestamp and find best ask
        timestamps = {}
        for venue in self.venues_data:
            ts = venue['timestamp']
            if ts not in timestamps:
                timestamps[ts] = []
            timestamps[ts].append(venue)
        
        for ts, venues in list(timestamps.items())[:100]:  # Sample for speed
            if venues:
                best_venue = min(venues, key=lambda v: v['ask_price'])
                
                # Execute as much as possible at best ask
                executed = min(self.order_size, best_venue['ask_size'])
                cost = executed * (best_venue['ask_price'] + 0.003)  # Price + fee
                
                total_cost += cost
                total_executed += executed
        
        avg_fill_price = total_cost / total_executed if total_executed > 0 else 0
        
        return {
            'total_cash': total_cost,
            'avg_fill_px': round(avg_fill_price, 4)
        }
    
    def _compute_twap(self):
        """TWAP strategy - execute in equal intervals over 60 seconds"""
        total_cost = 0
        total_executed = 0
        
        # Sample data for 60-second intervals
        timestamps = sorted(set(venue['timestamp'] for venue in self.venues_data))
        
        if len(timestamps) >= 60:
            interval_size = self.order_size // 60  # Equal intervals
            
            for i in range(0, min(60, len(timestamps))):
                ts = timestamps[i]
                venues_at_ts = [v for v in self.venues_data if v['timestamp'] == ts]
                
                if venues_at_ts:
                    # Execute at average price of available venues
                    avg_price = np.mean([v['ask_price'] for v in venues_at_ts])
                    cost = interval_size * (avg_price + 0.003)
                    
                    total_cost += cost
                    total_executed += interval_size
        
        avg_fill_price = total_cost / total_executed if total_executed > 0 else 0
        
        return {
            'total_cash': total_cost,
            'avg_fill_px': round(avg_fill_price, 4)
        }
    
    def _compute_vwap(self):
        """VWAP strategy - weighted by displayed size"""
        total_cost = 0
        total_executed = 0
        
        # Calculate VWAP across all venues
        total_notional = 0
        total_volume = 0
        
        for venue in self.venues_data[:1000]:  # Sample for speed
            notional = venue['ask_price'] * venue['ask_size']
            total_notional += notional
            total_volume += venue['ask_size']
        
        if total_volume > 0:
            vwap_price = total_notional / total_volume
            total_cost = self.order_size * (vwap_price + 0.003)
            total_executed = self.order_size
        
        avg_fill_price = total_cost / total_executed if total_executed > 0 else 0
        
        return {
            'total_cash': total_cost,
            'avg_fill_px': round(avg_fill_price, 4)
        }
    
    def calculate_savings_bps(self, optimized_result, baselines):
        """Calculate savings in basis points vs baselines"""
        opt_cost = optimized_result['total_cost']
        
        savings = {}
        for baseline_name, baseline_result in baselines.items():
            baseline_cost = baseline_result['total_cash']
            if baseline_cost > 0:
                savings_bps = ((baseline_cost - opt_cost) / baseline_cost) * 10000
                savings[baseline_name] = round(savings_bps, 1)
            else:
                savings[baseline_name] = 0.0
        
        return savings
    
    def run_full_benchmark(self, csv_file='l1_day.csv', kafka_topic='mock_l1_stream'):
        """Run complete benchmark process"""
        logger.info("Starting full benchmark process...")
        
        # 1. Parse data and stream to Kafka
        self.parse_l1_data(csv_file)
        self.stream_to_kafka(kafka_topic)
        
        # 2. Parameter search
        param_ranges = {
            'lambda_over': (0.001, 0.02),
            'lambda_under': (0.001, 0.015),
            'theta_queue': (0.001, 0.01)
        }
        
        best_params, optimized_result = self.parameter_search(param_ranges)
        
        # 3. Compute baselines
        baselines = self.compute_baselines()
        
        # 4. Calculate savings
        savings = self.calculate_savings_bps(optimized_result, baselines)
        
        # 5. Format final JSON output
        final_result = {
            "best_parameters": best_params,
            "optimized": {
                "total_cash": round(optimized_result['total_cost'], 0),
                "avg_fill_px": round(optimized_result['avg_fill_price'], 4)
            },
            "baselines": baselines,
            "savings_vs_baselines_bps": savings
        }
        
        # Print final JSON to stdout
        print(json.dumps(final_result, indent=2))
        
        return final_result

def main():
    parser = argparse.ArgumentParser(description='SOR Benchmark System')
    parser.add_argument('--kafka-servers', default='localhost:9092', help='Kafka servers')
    parser.add_argument('--csv-file', default='l1_day.csv', help='CSV file to process')
    parser.add_argument('--topic', default='mock_l1_stream', help='Kafka topic')
    parser.add_argument('--order-size', type=int, default=5000, help='Order size')
    parser.add_argument('--fast-mode', action='store_true', help='Enable fast mode for quicker execution')
    
    args = parser.parse_args()
    
    benchmark = BenchmarkSOR(
        kafka_servers=args.kafka_servers,
        order_size=args.order_size,
        fast_mode=args.fast_mode
    )
    
    try:
        benchmark.run_full_benchmark(args.csv_file, args.topic)
    except KeyboardInterrupt:
        logger.info("Benchmark interrupted")
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        raise

if __name__ == '__main__':
    main() 