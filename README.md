# Kafka CSV Stream + Smart Order Router (SOR)

Complete end-to-end trading system featuring CSV data streaming and real-time Smart Order Router with the Cont & Kukanov cost model.

##  Quick Start (Cloud Ready)

**Get the complete system running in 30 seconds:**

```bash
# Clone and start the full SOR system
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
docker-compose -f docker-compose-sor.yml up

# With both brute-force and L2 algorithms
docker-compose -f docker-compose-sor.yml --profile l2 up
```

### Option 2: Original Producer/Viewer Only
```bash
# Legacy system for basic streaming
docker-compose up
```

### Option 3: Local Development
```bash
# Test SOR module standalone
python smart_order_router.py

# Run individual components
python kafka_producer.py --file l1_day.csv --topic market_data
python kafka_viewer.py --topic market_data
python kafka_sor_consumer.py --topic market_data --order-size 5000
```

##  Configuration Options

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

##  Cloud Deployment

### AWS ECS/Fargate
```bash
# Build and push to ECR
docker build -t sor-system .
docker tag sor-system:latest <aws-account>.dkr.ecr.us-east-1.amazonaws.com/sor-system:latest
docker push <aws-account>.dkr.ecr.us-east-1.amazonaws.com/sor-system:latest
```

### Google Cloud Run
```bash
# Build and deploy
gcloud builds submit --tag gcr.io/<project-id>/sor-system
gcloud run deploy --image gcr.io/<project-id>/sor-system --platform managed
```

### Azure Container Instances
```bash
# Build and deploy
az acr build --registry <registry-name> --image sor-system .
az container create --resource-group <group> --name sor-system --image <registry>.azurecr.io/sor-system:latest
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
        - name: ORDER_SIZE
          value: "5000"
        - name: GREEDY_L2
          value: "true"
```

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


