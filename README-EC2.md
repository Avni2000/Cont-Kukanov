# EC2 Docker Deployment Guide

This guide shows how to deploy your Kafka producer on EC2 using Docker, **without the kafka_viewer**.

## Architecture

- **Zookeeper**: Coordination service for Kafka
- **Kafka**: Message broker running on port 9092 (internal) and 29092 (external)
- **Producer**: Your CSV-to-Kafka streaming service
- **No Viewer**: The kafka_viewer.py is intentionally excluded from EC2 deployment

## Quick Start on EC2

### 1. Launch EC2 Instance

Choose an Amazon Linux 2 instance (t3.small or larger recommended).

### 2. Upload Your Files

Transfer these files to your EC2 instance:
```bash
scp -i your-key.pem *.py *.csv *.sh docker compose.yml Dockerfile ec2-user@your-ec2-ip:~/
```

### 3. Run Setup Script

```bash
chmod +x ec2-setup.sh
./ec2-setup.sh
```

**Important**: Log out and back in after the setup script completes.

### 4. Start Services

```bash
# Start all services (Zookeeper, Kafka, and Producer)
docker compose up -d

# Check that services are running
docker compose ps

# View producer logs
docker compose logs -f producer
```

## Configuration

### Environment Variables

You can customize the deployment by setting environment variables in `docker compose.yml`:

- `KAFKA_SERVERS`: Kafka broker address (default: kafka:9092)
- `TOPIC_NAME`: Kafka topic name (default: market_data)
- `CSV_FILE`: CSV file to stream (default: l1_day.csv)

### Accessing Kafka from Outside EC2

If you need external access to Kafka (for testing with your local kafka_viewer):

1. Update EC2 security group to allow port 29092
2. Connect using: `--kafka-servers your-ec2-public-ip:29092`

## Monitoring and Management

### View Logs
```bash
# All services
docker compose logs

# Just the producer
docker compose logs -f producer

# Just Kafka
docker compose logs -f kafka
```

### Restart Services
```bash
# Restart all
docker compose restart

# Restart just producer
docker compose restart producer
```

### Stop Services
```bash
# Stop all services
docker compose down

# Stop and remove volumes (cleans up completely)
docker compose down -v
```

## Production Considerations

1. **Security Groups**: Configure EC2 security groups appropriately
2. **Data Persistence**: Consider mounting volumes for Kafka data
3. **Monitoring**: Add health checks and monitoring
4. **Auto-restart**: The producer is configured with `restart: unless-stopped`
5. **Resource Sizing**: Monitor CPU/memory usage and scale accordingly

## Troubleshooting

### Producer Won't Start
```bash
# Check if Kafka is ready
docker compose exec kafka kafka-topics --list --bootstrap-server localhost:9092

# Check producer logs
docker compose logs producer
```

### Connection Issues
```bash
# Test Kafka connectivity
docker compose exec producer nc -z kafka 9092
```

### View Topics and Messages
```bash
# List topics
docker compose exec kafka kafka-topics --list --bootstrap-server localhost:9092

# View messages (first 10)
docker compose exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic market_data --from-beginning --max-messages 10
``` 