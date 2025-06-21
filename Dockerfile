FROM python:3.9-slim

# Install netcat for connectivity testing
RUN apt-get update && apt-get install -y netcat-openbsd && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements-ec2.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the producer script and data files
COPY kafka_producer.py .
COPY *.csv .

# Set environment variables
ENV KAFKA_SERVERS=kafka:9092
ENV PYTHONUNBUFFERED=1

# Create entrypoint script
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Run the producer
ENTRYPOINT ["./entrypoint.sh"] 