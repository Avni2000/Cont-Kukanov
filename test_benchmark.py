#!/usr/bin/env python3
"""
Test script to validate the SOR benchmarking system with sample data
"""

import sys
import json
import time
import logging
from benchmark_sor import TimeAccurateBenchmarkSOR

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_sample_data():
    """Test the benchmarking system with sample.csv"""
    logger.info("=== Testing SOR Benchmark with Sample Data ===")
    
    # Initialize benchmark system
    benchmark = TimeAccurateBenchmarkSOR(
        kafka_servers='localhost:9092',
        order_size=500  # Smaller order size for testing
    )
    
    # Test parameter ranges
    param_ranges = {
        'lambda_over': (0.1, 0.5),
        'lambda_under': (0.1, 0.5), 
        'theta_queue': (0.1, 0.3)
    }
    
    try:
        # Run benchmark without Kafka streaming
        results = benchmark.run_full_benchmark(
            csv_file='sample.csv',
            kafka_topic='test_topic',
            stream_to_kafka=False,  # Skip Kafka for this test
            param_ranges=param_ranges
        )
        
        if results:
            # Pretty print results
            print("\n" + "="*60)
            print("SAMPLE DATA BENCHMARK RESULTS")
            print("="*60)
            print(json.dumps(results, indent=2))
            print("="*60)
            
            # Validate structure
            expected_keys = ['best_parameters', 'optimized', 'baselines', 'savings_vs_baselines_bps']
            for key in expected_keys:
                if key not in results:
                    logger.error(f"Missing key in results: {key}")
                    return False
                    
            # Validate best_parameters
            best_params = results['best_parameters']
            param_keys = ['lambda_over', 'lambda_under', 'theta_queue']
            for param in param_keys:
                if param not in best_params:
                    logger.error(f"Missing parameter: {param}")
                    return False
                    
            # Validate optimized results
            optimized = results['optimized']
            if 'total_cash' not in optimized or 'avg_fill_px' not in optimized:
                logger.error("Missing optimized results")
                return False
                
            # Validate baselines
            baselines = results['baselines']
            baseline_names = ['best_ask', 'twap', 'vwap']
            for baseline in baseline_names:
                if baseline not in baselines:
                    logger.error(f"Missing baseline: {baseline}")
                    return False
                    
            logger.info("✓ All validation checks passed!")
            return True
            
        else:
            logger.error("No results returned from benchmark")
            return False
            
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        return False

def test_kafka_streaming():
    """Test Kafka streaming functionality"""
    logger.info("=== Testing Kafka Streaming ===")
    
    # This test requires Kafka to be running
    benchmark = TimeAccurateBenchmarkSOR(
        kafka_servers='localhost:9092',
        order_size=500
    )
    
    try:
        # Parse sample data
        venues_data = benchmark.parse_l1_data('sample.csv')
        if not venues_data:
            logger.error("Failed to parse sample data")
            return False
            
        logger.info(f"Parsed {len(venues_data)} venue snapshots")
        
        # Test Kafka streaming (non-time-accurate for speed)
        if benchmark.setup_kafka_producer():
            logger.info("✓ Kafka producer setup successful")
            
            # Stream a few messages
            success = benchmark.stream_to_kafka('test_topic', time_accurate=False)
            if success:
                logger.info("✓ Kafka streaming test passed")
                return True
            else:
                logger.warning("Kafka streaming failed (Kafka may not be running)")
                return False
        else:
            logger.warning("Kafka producer setup failed (Kafka may not be running)")
            return False
            
    except Exception as e:
        logger.error(f"Kafka streaming test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Starting SOR Benchmark Tests...")
    
    # Test 1: Sample data benchmark
    test1_passed = test_sample_data()
    
    # Test 2: Kafka streaming (optional)
    print("\nTesting Kafka streaming (requires Kafka to be running)...")
    test2_passed = test_kafka_streaming()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Sample Data Benchmark: {'✓ PASSED' if test1_passed else '✗ FAILED'}")
    print(f"Kafka Streaming: {'✓ PASSED' if test2_passed else '✗ FAILED (optional)'}")
    print("="*60)
    
    if test1_passed:
        print("\n✓ Core benchmarking system is working correctly!")
        print("You can now run the full benchmark with:")
        print("  python benchmark_sor.py --csv-file l1_day.csv --no-kafka")
        print("  python run_benchmark.py --sample-data --no-kafka")
    else:
        print("\n✗ Core benchmarking system has issues that need to be fixed.")
        sys.exit(1)

if __name__ == '__main__':
    main() 