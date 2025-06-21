# Smart Order Router (SOR) with Cont & Kukanov Cost Model

A complete end-to-end implementation of a Smart Order Router using the Cont & Kukanov cost model, integrated with Kafka for real-time market data processing.

## Overview

This system implements optimal order allocation across multiple venues using:

- **Brute-force allocation search** over step-sized chunks
- **Greedy Level-2 allocation** with level flattening for deep order books
- **Comprehensive penalty model** including over/under execution and queue risk
- **Real-time Kafka integration** for market data processing
- **Cloud-ready deployment** with Docker and Docker Compose

## Core Features

### Cost Model Components

The Cont & Kukanov cost model includes:

- **Cash spent**: `executed_shares * (price + fee) - over_allocation * rebate`
- **Under-execution penalty**: `λ_under * underfill_shares`
- **Over-execution penalty**: `λ_over * overfill_shares`
- **Queue risk penalty**: `θ_queue * (underfill + overfill)`

### Allocation Algorithms

1. **Brute-Force Search**: Exhaustive search over all possible allocations in step-sized increments
2. **Greedy L2**: Efficient level-flattening approach for deep order books

## Architecture

```
Market Data (CSV) → Kafka Producer → Kafka Topic → SOR Consumer → Allocation Results
                                         ↓
                                    Zookeeper
                                         ↓
                                    Kafka UI (Optional)
```

## Quick Start

### 1. Test the SOR Module

```bash
# Run the standalone SOR test harness
python smart_order_router.py
```

This will run a test with 3 venues and display optimal allocation results.

### 2. Run End-to-End with Docker Compose

```bash
# Start the complete system
docker-compose -f docker-compose-sor.yml up

# Or run with both brute-force and L2 algorithms
docker-compose -f docker-compose-sor.yml --profile l2 up
```

### 3. Monitor via Kafka UI

Access Kafka UI at http://localhost:8080 to monitor:
- Topics and messages
- Consumer groups
- Real-time throughput

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORDER_SIZE` | 5000 | Total shares to execute |
| `LAMBDA_OVER` | 0.01 | Over-execution penalty per share |
| `LAMBDA_UNDER` | 0.005 | Under-execution penalty per share |
| `THETA_QUEUE` | 0.002 | Queue risk penalty per share |
| `STEP` | 100 | Allocation step size (brute-force only) |
| `GREEDY_L2` | false | Use greedy L2 allocation |
| `TOPIC_NAME` | market_data | Kafka topic name |
| `CSV_FILE` | sample.csv | Market data file |

### Example Configurations

#### Conservative Trading
```bash
export ORDER_SIZE=1000
export LAMBDA_OVER=0.02
export LAMBDA_UNDER=0.01
export THETA_QUEUE=0.005
```

#### Aggressive Trading
```bash
export ORDER_SIZE=10000
export LAMBDA_OVER=0.005
export LAMBDA_UNDER=0.002
export THETA_QUEUE=0.001
export GREEDY_L2=true
```

## Usage Examples

### 1. Standalone SOR Testing

```python
from smart_order_router import Venue, allocate

# Define venues
venues = [
    Venue(ask=100.10, ask_size=500, fee=0.003, rebate=0.001),
    Venue(ask=100.11, ask_size=300, fee=0.002, rebate=0.0015),
    Venue(ask=100.12, ask_size=800, fee=0.0025, rebate=0.001),
]

# Run optimization
best_split, best_cost = allocate(
    order_size=1000,
    venues=venues,
    lambda_over=0.01,
    lambda_under=0.005,
    theta_queue=0.002,
    step=100
)

print(f"Optimal allocation: {best_split}")
print(f"Total cost: ${best_cost:.2f}")
```

### 2. Kafka Consumer

```bash
# Start SOR consumer with custom parameters
python kafka_sor_consumer.py \
    --topic market_data \
    --order-size 3000 \
    --lambda-over 0.015 \
    --lambda-under 0.008 \
    --theta-queue 0.003 \
    --greedy-l2
```

### 3. Level-2 Allocation

```python
from smart_order_router import Level2Venue, allocate_greedy_l2

# Define L2 venues with multiple price levels
venues = [
    Level2Venue(
        venue_id="BATS",
        levels=[(100.10, 200), (100.11, 300)],
        fee=0.003,
        rebate=0.001
    ),
    Level2Venue(
        venue_id="ARCA",
        levels=[(100.11, 400), (100.12, 500)],
        fee=0.002,
        rebate=0.0015
    )
]

# Run greedy L2 allocation
allocation, cost = allocate_greedy_l2(
    order_size=1000,
    venues=venues,
    lambda_over=0.01,
    lambda_under=0.005,
    theta_queue=0.002
)
```

## Output Format

The SOR consumer outputs detailed JSON results:

```json
{
  "symbol": "AAPL",
  "timestamp": "2024-08-01T13:36:32.491911683Z",
  "order_size": 5000,
  "algorithm": "brute_force",
  "venues": [
    {
      "venue_id": "venue_0",
      "ask": 222.83,
      "ask_size": 36,
      "fee": 0.003,
      "rebate": 0.001,
      "allocation": 0
    }
  ],
  "allocation": [0, 1600, 3400],
  "total_cost": 757891.234,
  "execution_summary": {
    "total_executed": 5000,
    "underfill": 0,
    "overfill": 0,
    "cash_spent": 757891.234,
    "fill_rate": 1.0
  },
  "parameters": {
    "lambda_over": 0.01,
    "lambda_under": 0.005,
    "theta_queue": 0.002,
    "step": 100
  }
}
```

## Performance Considerations

### Brute-Force vs Greedy L2

| Algorithm | Time Complexity | Use Case |
|-----------|----------------|----------|
| Brute-Force | O(n^k) where n=order_size/step, k=venues | Small venue count, guaranteed optimal |
| Greedy L2 | O(m log m) where m=total_levels | Large venue count, near-optimal |

### Optimization Tips

1. **Use larger step sizes** for brute-force with large orders
2. **Use greedy L2** when venue count > 5 or order size > 10,000
3. **Tune penalties** based on market conditions and trading style
4. **Monitor fill rates** to adjust order sizing

## Cloud Deployment

### AWS ECS/Fargate

```bash
# Build and push to ECR
docker build -t sor-system .
docker tag sor-system:latest <aws-account>.dkr.ecr.us-east-1.amazonaws.com/sor-system:latest
docker push <aws-account>.dkr.ecr.us-east-1.amazonaws.com/sor-system:latest
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: smart-order-router
spec:
  replicas: 2
  selector:
    matchLabels:
      app: sor
  template:
    metadata:
      labels:
        app: sor
    spec:
      containers:
      - name: sor
        image: sor-system:latest
        env:
        - name: KAFKA_SERVERS
          value: "kafka-cluster:9092"
        - name: ORDER_SIZE
          value: "5000"
        - name: GREEDY_L2
          value: "true"
```

## Monitoring and Observability

### Key Metrics

- **Allocation latency**: Time to compute optimal allocation
- **Fill rate**: Percentage of order executed
- **Cost efficiency**: Total cost vs benchmark
- **Message throughput**: Kafka messages processed per second

### Logging

The system provides structured logging:

```
2024-01-15 10:30:45 - INFO - SOR Configuration: Order size: 5000
2024-01-15 10:30:45 - INFO - Optimizing allocation for 5000 shares across 3 venues
2024-01-15 10:30:45 - INFO - Evaluating 1331 possible allocations
2024-01-15 10:30:45 - INFO - Optimal allocation: [0, 1600, 3400] with cost 757891.23
2024-01-15 10:30:45 - INFO - SOR Result [AAPL]: allocation=[0, 1600, 3400], cost=$757891.23, fill_rate=100.0%
```

## Troubleshooting

### Common Issues

1. **No venues extracted from market data**
   - Check CSV format and ask price/size columns
   - Verify market data contains valid numeric values

2. **Kafka connection errors**
   - Ensure Kafka is running: `docker-compose ps`
   - Check network connectivity between containers

3. **High allocation latency**
   - Reduce order size or increase step size for brute-force
   - Switch to greedy L2 for better performance

4. **Poor fill rates**
   - Adjust penalty parameters (λ_over, λ_under)
   - Check venue liquidity in market data

### Debug Mode

Enable debug logging:

```bash
export PYTHONPATH=.
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from smart_order_router import run_test_harness
run_test_harness()
"
```

## API Reference

### Core Functions

#### `allocate(order_size, venues, lambda_over, lambda_under, theta_queue, step=100)`

Brute-force optimal allocation search.

**Parameters:**
- `order_size` (int): Total shares to execute
- `venues` (List[Venue]): List of venue objects
- `lambda_over` (float): Over-execution penalty per share
- `lambda_under` (float): Under-execution penalty per share
- `theta_queue` (float): Queue risk penalty per share
- `step` (int): Allocation granularity

**Returns:** `(best_split: List[int], best_cost: float)`

#### `allocate_greedy_l2(order_size, venues, lambda_over, lambda_under, theta_queue)`

Greedy Level-2 allocation with level flattening.

**Parameters:**
- `order_size` (int): Total shares to execute
- `venues` (List[Level2Venue]): List of L2 venue objects
- `lambda_over` (float): Over-execution penalty per share
- `lambda_under` (float): Under-execution penalty per share
- `theta_queue` (float): Queue risk penalty per share

**Returns:** `(allocation: List[int], total_cost: float)`

#### `compute_cost(split, venues, order_size, lambda_over, lambda_under, theta_queue)`

Compute total cost for a given allocation.

**Returns:** `float` - Total expected cost

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `python -m pytest`
5. Submit a pull request

## License

MIT License - see LICENSE file for details. 