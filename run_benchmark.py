#!/usr/bin/env python3
"""
Simple script to run SOR benchmarking
"""

import subprocess
import sys
import argparse
import json
import os

def main():
    parser = argparse.ArgumentParser(description="Run SOR Benchmark")
    parser.add_argument('--csv-file', default='l1_day.csv', help='CSV file path')
    parser.add_argument('--sample-data', action='store_true', help='Use sample.csv for testing')
    parser.add_argument('--no-kafka', action='store_true', help='Skip Kafka streaming')
    parser.add_argument('--order-size', type=int, default=1000, help='Order size')
    
    args = parser.parse_args()
    
    # Use sample data if specified
    csv_file = 'sample.csv' if args.sample_data else args.csv_file
    
    # Check if file exists
    if not os.path.exists(csv_file):
        print(f"Error: File {csv_file} not found")
        sys.exit(1)
    
    # Build command
    cmd = [
        'python3', 'benchmark_sor.py',
        '--csv-file', csv_file,
        '--order-size', str(args.order_size)
    ]
    
    if args.no_kafka:
        cmd.append('--no-kafka')
    
    print(f"Running benchmark with command: {' '.join(cmd)}")
    print(f"Using CSV file: {csv_file}")
    print("-" * 50)
    
    try:
        # Run the benchmark
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Print the JSON output
        print(result.stdout)
        
        # Try to parse and validate JSON
        try:
            json_data = json.loads(result.stdout)
            print("\n✓ Benchmark completed successfully!")
            print(f"✓ Best parameters: {json_data.get('best_parameters', {})}")
            
            if 'optimized' in json_data:
                opt = json_data['optimized']
                print(f"✓ Optimized cost: ${opt.get('total_cash', 0):.2f}")
                print(f"✓ Average fill price: ${opt.get('avg_fill_px', 0):.4f}")
            
            if 'savings_vs_baselines_bps' in json_data:
                savings = json_data['savings_vs_baselines_bps']
                print(f"✓ Savings vs baselines: {savings}")
                
        except json.JSONDecodeError:
            print("Warning: Output is not valid JSON, but benchmark may have completed")
            
    except subprocess.CalledProcessError as e:
        print(f"Error running benchmark: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user")
        sys.exit(1)

if __name__ == '__main__':
    main() 