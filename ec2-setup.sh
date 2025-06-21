#!/bin/bash

# EC2 Setup Script for Kafka Producer
# Run this on your EC2 instance to set up Docker and start the services

set -e

echo "=== EC2 Kafka Producer Setup ==="

# Update the system
echo "Updating system packages..."
sudo yum update -y

# Install Docker
echo "Installing Docker..."
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -a -G docker ec2-user

# Install Docker Compose
echo "Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create symbolic link
sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

echo "Docker and Docker Compose installed successfully!"

# Note: You'll need to log out and back in for docker group permissions
echo ""
echo "IMPORTANT: Log out and back in to apply Docker group permissions"
echo "Then run: docker-compose up -d to start the services"
echo ""
echo "Services will include:"
echo "- Zookeeper (port 2181)"
echo "- Kafka (ports 9092, 29092)" 
echo "- Kafka Producer (automatically starts producing data)"
echo ""
echo "To check logs: docker-compose logs -f producer"
echo "To stop: docker-compose down" 