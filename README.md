# Kafka CSV Stream + Smart Order Router (SOR)

Complete end-to-end trading system featuring CSV data streaming and real-time Smart Order Router with the Cont & Kukanov cost model.

##  Quick Start (Cloud Ready)

**Get the complete system running in 30 seconds:**

```bash
# Clone and start the full SOR system
sudo apt-get docker-compose-v2 
git clone https://github.com/Avni2000/Cont-Kukanov
cd Cont-Kukanov
docker-compose -f docker-compose-sor.yml up
```

 **Access Points:**
- **SOR Results**: Console output with real-time allocation decisions
- **Kafka UI**: http://localhost:8080 (monitor streams and topics)
- **Market Data**: Streaming from CSV to Kafka automatically

##  System Components

This project provides a complete trading infrastructure:

### Core Market Data Infrastructure
1. **kafka_producer.py** - Streams CSV order book data to Kafka topics as JSON
2. **kafka_viewer.py** - Consumes and displays JSON messages from Kafka topics

### Smart Order Router (SOR) System  
3. **smart_order_router.py** - Core SOR module with Cont & Kukanov cost model
4. **kafka_sor_consumer.py** - Real-time SOR consumer processing live market data
5. **Complete Docker deployment** with Kafka, Zookeeper, and monitoring

##  Requirements

### For Local Development
```bash
pip install -r requirements.txt
```

### For Cloud Deployment (Recommended)
- Docker & Docker Compose
- 2GB+ RAM for Kafka
- Available ports: 8080, 9092, 2181

**No Python setup needed for Docker deployment!**

##  Smart Order Router Features

###  Real-Time Optimization
- **Brute-force allocation**: Guaranteed optimal solution for small venue counts
- **Greedy L2 allocation**: Near-optimal performance for large order books
- **Cost model**: Complete Cont & Kukanov implementation with penalties

###  Cost Model Components
```
Total Cost = Cash Spent + Penalties + Queue Risk

Where:
- Cash Spent = executed × (price + fee) - over_allocation × rebate
- Penalties = λ_under × underfill + λ_over × overfill  
- Queue Risk = θ_queue × (underfill + overfill)
```

###  Configurable Parameters
- **Order Size**: 1,000 - 50,000 shares
- **Risk Penalties**: Over/under execution λ values
- **Queue Risk**: θ parameter for market impact
- **Algorithms**: Brute-force or Greedy L2

##  Deployment Options

### Option 1: Full SOR System (Recommended)
```bash
# Complete system with SOR + market data
docker compose -f docker-compose-sor.yml up

# With both brute-force and L2 algorithms
docker compose -f docker-compose-sor.yml --profile l2 up
```

### Option 2: SOR Benchmark System
```bash
# Run complete benchmark with parameter optimization
docker compose -f docker-compose-sor.yml --profile benchmark up

# This will:
# - Parse l1_day.csv and stream to mock_l1_stream topic
# - Optimize lambda_over, lambda_under, theta_queue parameters
# - Compare against Best Ask, TWAP, VWAP baselines
# - Output final JSON with savings in basis points
```

### Option 3: Original Producer/Viewer Only
```bash
# Legacy system for basic streaming made for kafka debugging
docker compose up
```




##  Configuration Options

All of the variables above are highly mutable. To test with different strategies, we can easily change the variables in our ec2 instance. For the sake of time + the scope of this project, I won't make this interactive. 


### Environment Variables (Docker)

| Variable | Default | Description |
|----------|---------|-------------|
| `ORDER_SIZE` | 5000 | Total shares to execute |
| `LAMBDA_OVER` | 0.01 | Over-execution penalty per share |
| `LAMBDA_UNDER` | 0.005 | Under-execution penalty per share |
| `THETA_QUEUE` | 0.002 | Queue risk penalty per share |
| `STEP` | 100 | Allocation step size (brute-force) |
| `GREEDY_L2` | false | Use greedy L2 allocation |
| `CSV_FILE` | l1_day.csv | Market data file |

### Example Configurations


**Conservative Trading:**
```bash
export ORDER_SIZE=1000
export LAMBDA_OVER=0.02
export LAMBDA_UNDER=0.01
export THETA_QUEUE=0.005
```

**Aggressive Trading:**
```bash
export ORDER_SIZE=10000
export LAMBDA_OVER=0.005
export LAMBDA_UNDER=0.002
export THETA_QUEUE=0.001
export GREEDY_L2=true
```

##  Live System Output

### SOR Allocation Results
The Smart Order Router outputs detailed JSON decisions in real-time:

```json
{
  "symbol": "AAPL",
  "timestamp": "2024-08-01T13:36:32.491911683Z",
  "order_size": 5000,
  "algorithm": "brute_force",
  "allocation": [0, 1600, 3400],
  "total_cost": 757891.234,
  "execution_summary": {
    "total_executed": 5000,
    "underfill": 0,
    "overfill": 0,
    "cash_spent": 757891.234,
    "fill_rate": 1.0
  },
  "venues": [
    {
      "venue_id": "venue_0",
      "ask": 222.83,
      "ask_size": 36,
      "fee": 0.003,
      "rebate": 0.001,
      "allocation": 0
    }
  ]
}
```

### Console Logs
```bash
2024-01-15 10:30:45 - INFO - SOR Configuration: Order size: 5000
2024-01-15 10:30:45 - INFO - Optimizing allocation for 5000 shares across 3 venues
2024-01-15 10:30:45 - INFO - Evaluating 1331 possible allocations
2024-01-15 10:30:45 - INFO - Optimal allocation: [0, 1600, 3400] with cost 757891.23
2024-01-15 10:30:45 - INFO - SOR Result [AAPL]: allocation=[0, 1600, 3400], cost=$757891.23, fill_rate=100.0%
```

##  Benchmark System Output

### Parameter Optimization Results
The benchmark system outputs a comprehensive JSON report after optimizing parameters and comparing against baselines:

```json
{
  "best_parameters": {
    "lambda_over": 0.012,
    "lambda_under": 0.008,
    "theta_queue": 0.005
  },
  "optimized": {
    "total_cash": 248750,
    "avg_fill_px": 49.75
  },
  "baselines": {
    "best_ask": {
      "total_cash": 250000,
      "avg_fill_px": 50.00
    },
    "twap": {
      "total_cash": 251000,
      "avg_fill_px": 50.20
    },
    "vwap": {
      "total_cash": 249800,
      "avg_fill_px": 49.96
    }
  },
  "savings_vs_baselines_bps": {
    "best_ask": 50.0,
    "twap": 89.6,
    "vwap": 21.2
  }
}
```

### Benchmark Process
1. **Data Parsing**: Extracts venue snapshots from `l1_day.csv` using `publisher_id`, `ask_px_00`, `ask_sz_00`
2. **Kafka Streaming**: Publishes snapshots to `mock_l1_stream` topic
3. **Parameter Search**: Tests combinations of λ_over, λ_under, θ_queue across defined ranges
4. **Baseline Comparison**: 
   - **Best Ask**: Greedy fill at lowest available ask price
   - **TWAP**: Time-weighted average price over 60-second intervals
   - **VWAP**: Volume-weighted average price by displayed size
5. **Savings Calculation**: Reports improvement in basis points vs each baseline

##  Cloud Deployment

##  Performance & Monitoring

### Algorithm Performance
| Algorithm | Time Complexity | Recommended Use |
|-----------|----------------|-----------------|
| Brute-Force | O(n^k) | Small venues (<5), guaranteed optimal |
| Greedy L2 | O(m log m) | Large venues (5+), near-optimal |

### Key Metrics
- **Allocation Latency**: Time to compute optimal allocation
- **Fill Rate**: Percentage of order executed  
- **Cost Efficiency**: Total cost vs benchmark
- **Throughput**: Messages processed per second

##  Data Format

The system processes CSV files with Level-1 order book data:

- `ts_recv`, `ts_event` - Timestamp columns (automatically converted)
- `symbol` - Symbol identifier  
- `ask_px_XX`, `ask_sz_XX` - Ask prices/sizes for level XX (XX = 00-09)
- `bid_px_XX`, `bid_sz_XX` - Bid prices/sizes for level XX
- `publisher_id`, `instrument_id` - Market data identifiers

##  Troubleshooting

### Common Issues

**No venues extracted from market data:**
- Check CSV format has `ask_px_XX` and `ask_sz_XX` columns
- Verify price/size values are numeric and positive

**Kafka connection errors:**
- Ensure Docker containers are running: `docker-compose ps`
- Check port availability: `netstat -an | grep 9092`

**High allocation latency:**
- Reduce order size or increase step size for brute-force
- Switch to greedy L2: `export GREEDY_L2=true`

**Poor fill rates:**
- Adjust penalty parameters (λ_over, λ_under)
- Check venue liquidity in market data

##  Additional Resources

- **Detailed SOR Documentation**: `README-SOR.md`
- **Docker Compose Files**: 
  - `docker-compose-sor.yml` (Full SOR system)
  - `docker-compose.yml` (Legacy producer/viewer)
- **Core Modules**:
  - `smart_order_router.py` (Standalone SOR)
  - `kafka_sor_consumer.py` (Real-time consumer)


