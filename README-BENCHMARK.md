# Smart Order Router Benchmarking System

## Overview

This system implements a time-accurate Kafka-based benchmarking framework for the Smart Order Router (SOR) that includes:

- **L1 Data Parsing**: Parse `l1_day.csv` and create venue snapshots using `publisher_id`, `ask_px_00`, `ask_sz_00`
- **Time-Accurate Kafka Streaming**: Stream venue snapshots to topic `mock_l1_stream` with original timing
- **Parameter Optimization**: Search over `lambda_over`, `lambda_under`, `theta_queue` parameters
- **Baseline Comparisons**: Benchmark against Best Ask, TWAP, and VWAP strategies
- **JSON Output**: Results in specified format with savings calculations in basis points

## Quick Start

### 1. Test with Sample Data (No Kafka Required)
```bash
# Run quick test with sample.csv
python test_benchmark.py

# Or use the convenience script
python run_benchmark.py --sample-data --no-kafka --order-size 500
```

### 2. Full Benchmark without Kafka
```bash
# Run full benchmark on l1_day.csv without Kafka streaming
python benchmark_sor.py --csv-file l1_day.csv --no-kafka --order-size 5000
```

### 3. Full Benchmark with Kafka Streaming
```bash
# First start Kafka (if using Docker)
docker-compose up -d kafka zookeeper

# Run benchmark with Kafka streaming
python benchmark_sor.py --csv-file l1_day.csv --kafka-topic mock_l1_stream --order-size 5000
```

## Core Components

### 1. `benchmark_sor.py` - Main Benchmarking System

**Key Features:**
- `TimeAccurateBenchmarkSOR` class handles all benchmarking operations
- Parses L1 CSV data and extracts venue snapshots
- Streams to Kafka with optional time-accurate replay
- Performs parameter optimization using grid search
- Computes baseline algorithms (Best Ask, TWAP, VWAP)
- Calculates savings in basis points

**Usage:**
```bash
python benchmark_sor.py [OPTIONS]

Options:
  --csv-file CSV_FILE          L1 data CSV file (default: l1_day.csv)
  --kafka-servers SERVERS      Kafka bootstrap servers (default: localhost:9092)  
  --kafka-topic TOPIC          Kafka topic name (default: mock_l1_stream)
  --order-size SIZE            Order size for execution (default: 5000)
  --no-kafka                   Skip Kafka streaming
  --output-file FILE           Output JSON file path
```

### 2. `smart_order_router.py` - Enhanced SOR Implementation

**Enhancements Made:**
- Fixed `cash_spent` calculation to separate actual cash from penalties
- Improved execution summary with accurate cost breakdown
- Maintains compatibility with existing SOR algorithms

### 3. Supporting Scripts

- **`run_benchmark.py`** - Convenience wrapper script
- **`test_benchmark.py`** - Validation and testing script  
- **`entrypoint_benchmark.sh`** - Docker entrypoint for containerized runs

## Data Format

### Input: L1 CSV Data
Expected columns from `l1_day.csv`:
- `ts_event` - Event timestamp
- `publisher_id` - Venue identifier  
- `ask_px_00` - Best ask price
- `ask_sz_00` - Best ask size
- `symbol` - Trading symbol

### Output: JSON Results Format
```json
{
  "best_parameters": {
    "lambda_over": 0.4,
    "lambda_under": 0.6, 
    "theta_queue": 0.3
  },
  "optimized": {
    "total_cash": 248750.00,
    "avg_fill_px": 49.75
  },
  "baselines": {
    "best_ask": {"total_cash": 250000.00, "avg_fill_px": 50.00},
    "twap": {"total_cash": 251000.00, "avg_fill_px": 50.20},
    "vwap": {"total_cash": 249800.00, "avg_fill_px": 49.96}
  },
  "savings_vs_baselines_bps": {
    "best_ask": 5.0,
    "twap": 15.0, 
    "vwap": 4.2
  }
}
```

## Algorithm Details

### Parameter Optimization
- **Grid Search**: Tests 5x5x5 = 125 parameter combinations
- **Parameters**:
  - `lambda_over`: Over-execution penalty (default range: 0.1 - 1.0)
  - `lambda_under`: Under-execution penalty (default range: 0.1 - 1.0) 
  - `theta_queue`: Queue risk penalty (default range: 0.1 - 0.5)

### Baseline Algorithms

1. **Best Ask (Naive)**: Always execute at the lowest available ask price
2. **TWAP**: Execute in equal 60-second intervals using volume-weighted average price
3. **VWAP**: Execute using volume-weighted average price across all venues

### Cost Model (Cont & Kukanov)
```
Total Cost = Cash Spent + Risk Penalty + Cost Penalty

Where:
- Cash Spent = Σ(executed_shares × (price + fee)) - Σ(over_allocation × rebate)
- Risk Penalty = θ_queue × (underfill + overfill)  
- Cost Penalty = λ_under × underfill + λ_over × overfill
```

## Kafka Integration

### Topic: `mock_l1_stream`
**Message Format:**
```json
{
  "timestamp": "2024-08-01T13:36:32.491911683",
  "publisher_id": "2", 
  "ask_px_00": 222.83,
  "ask_sz_00": 36,
  "symbol": "AAPL",
  "sequence": 46542624
}
```

**Key Features:**
- Time-accurate replay maintains original inter-message timing
- Optimized for throughput with batching and compression
- Graceful handling of Kafka unavailability

## Performance Considerations

### Data Sampling
- Parameter optimization uses every 50th snapshot for speed
- Baseline calculations use every 100th snapshot  
- Full data processing available but may be slow for large datasets

### Memory Usage
- Large CSV files (like `l1_day.csv` at 21MB) are loaded entirely into memory
- Consider data chunking for very large datasets (>100MB)

### Execution Time
- Sample data test: ~10-30 seconds
- Full `l1_day.csv` benchmark: ~5-15 minutes (depending on data size)
- Kafka streaming adds minimal overhead when disabled for benchmarking

## Docker Support

### Using Docker Compose
```bash
# Start Kafka infrastructure
docker-compose up -d kafka zookeeper

# Run benchmark in container
docker-compose -f docker-compose-benchmark.yml up benchmark
```

### Environment Variables
- `KAFKA_SERVERS` - Kafka bootstrap servers (default: kafka:29092)
- `CSV_FILE` - Input CSV file path (default: l1_day.csv)  
- `TOPIC_NAME` - Kafka topic (default: mock_l1_stream)
- `ORDER_SIZE` - Order size (default: 5000)

## Troubleshooting

### Common Issues

1. **"File not found" errors**
   ```bash
   # Ensure CSV file exists in current directory
   ls -la *.csv
   ```

2. **Kafka connection failures**
   ```bash
   # Test Kafka connectivity
   nc -zv localhost 9092
   
   # Or run without Kafka
   python benchmark_sor.py --no-kafka
   ```

3. **Memory issues with large CSV files**
   ```bash
   # Check file size
   du -h l1_day.csv
   
   # Use smaller order size to reduce computation
   python benchmark_sor.py --order-size 1000
   ```

4. **No valid venue data**
   ```bash
   # Check CSV format matches expected columns
   head -n 1 your_file.csv
   ```

### Debug Mode
Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   L1 CSV Data   │───▶│  Venue Snapshot  │───▶│ Kafka Streaming │
│   (l1_day.csv)  │    │     Parser       │    │ (mock_l1_stream)│
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ JSON Results    │◀───│   Parameter      │───▶│ SOR Optimization│
│ with BPS Savings│    │   Optimization   │    │   (Grid Search) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │    Baseline      │
                       │   Algorithms     │
                       │ (Best/TWAP/VWAP) │
                       └──────────────────┘
```

## Next Steps

1. **Scale Testing**: Test with larger datasets and different market conditions
2. **Advanced Baselines**: Implement more sophisticated baseline algorithms
3. **Real-time Integration**: Connect to live market data feeds
4. **Performance Optimization**: Implement parallel parameter search
5. **Visualization**: Add charts and graphs for result analysis

## Contributing

When modifying the benchmarking system:
1. Ensure backward compatibility with existing SOR algorithms
2. Add comprehensive tests for new features
3. Update this documentation
4. Validate JSON output format compliance
5. Test both with and without Kafka integration 