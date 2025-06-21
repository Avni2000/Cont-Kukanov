#!/usr/bin/env python3
"""
Kafka Smart Order Router Consumer

Real-time market data consumer that processes Level-1 order book data
and executes Smart Order Router allocation logic using the Cont & Kukanov cost model.

Features:
- Consumes market data from Kafka streams
- Extracts venue information from order book levels
- Executes SOR optimization in real-time
- Outputs allocation decisions and trade instructions
- Supports both brute-force and greedy L2 allocation strategies
"""

import argparse
import json
import signal
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional
import logging

try:
    from kafka import KafkaConsumer
    from kafka.errors import KafkaError
    KAFKA_AVAILABLE = True
except ImportError as e:
    print(f"Kafka not available: {e}")
    KAFKA_AVAILABLE = False

from smart_order_router import (
    Venue, Level2Venue, allocate, allocate_greedy_l2, 
    compute_cost, logger as sor_logger
)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MarketDataProcessor:
    """Processes market data messages to extract venue information"""
    
    @staticmethod
    def extract_venues_from_l1(market_data: Dict) -> List[Venue]:
        """
        Extract venue information from Level-1 market data.
        
        Creates venues from ask price levels in the order book data.
        Assumes standard fee/rebate structure.
        
        Args:
            market_data: Dictionary containing L1 order book data
            
        Returns:
            List of Venue objects extracted from market data
        """
        venues = []
        
        # Extract ask levels (ask_px_xx, ask_sz_xx)
        ask_levels = []
        
        for i in range(10):  # Support up to 10 levels
            price_key = f'ask_px_{i:02d}'
            size_key = f'ask_sz_{i:02d}'
            
            if price_key in market_data and size_key in market_data:
                price = market_data[price_key]
                size = market_data[size_key]
                
                if price and size and price > 0 and size > 0:
                    ask_levels.append((float(price), int(size)))
        
        # Create venues from ask levels
        # Use different fee/rebate structures for different levels to simulate different venues
        fee_schedules = [0.003, 0.002, 0.0025, 0.0035, 0.0015]
        rebate_schedules = [0.001, 0.0015, 0.001, 0.0008, 0.002]
        
        for i, (price, size) in enumerate(ask_levels):
            fee = fee_schedules[i % len(fee_schedules)]
            rebate = rebate_schedules[i % len(rebate_schedules)]
            
            venues.append(Venue(
                ask=price,
                ask_size=size,
                fee=fee,
                rebate=rebate
            ))
        
        return venues
    
    @staticmethod
    def extract_l2_venues_from_l1(market_data: Dict, num_venues: int = 3) -> List[Level2Venue]:
        """
        Extract Level-2 venues by grouping price levels.
        
        Args:
            market_data: Dictionary containing L1 order book data
            num_venues: Number of venues to create
            
        Returns:
            List of Level2Venue objects
        """
        # Extract all ask levels
        ask_levels = []
        
        for i in range(10):
            price_key = f'ask_px_{i:02d}'
            size_key = f'ask_sz_{i:02d}'
            
            if price_key in market_data and size_key in market_data:
                price = market_data[price_key]
                size = market_data[size_key]
                
                if price and size and price > 0 and size > 0:
                    ask_levels.append((float(price), int(size)))
        
        if not ask_levels:
            return []
        
        # Group levels into venues
        venues = []
        levels_per_venue = max(1, len(ask_levels) // num_venues)
        
        fee_schedules = [0.003, 0.002, 0.0025]
        rebate_schedules = [0.001, 0.0015, 0.001]
        
        for i in range(num_venues):
            start_idx = i * levels_per_venue
            end_idx = min((i + 1) * levels_per_venue, len(ask_levels))
            
            if start_idx >= len(ask_levels):
                break
                
            venue_levels = ask_levels[start_idx:end_idx]
            
            venues.append(Level2Venue(
                venue_id=f"venue_{i}",
                levels=venue_levels,
                fee=fee_schedules[i % len(fee_schedules)],
                rebate=rebate_schedules[i % len(rebate_schedules)]
            ))
        
        return venues


class KafkaSORConsumer:
    """Kafka consumer that executes Smart Order Router logic on market data"""
    
    def __init__(self, bootstrap_servers: str = 'localhost:9092'):
        """
        Initialize the Kafka SOR consumer
        
        Args:
            bootstrap_servers: Kafka bootstrap servers
        """
        self.bootstrap_servers = bootstrap_servers
        self.consumer = None
        self.running = False
        self.message_count = 0
        self.processor = MarketDataProcessor()
        
        # SOR Parameters (configurable)
        self.order_size = 5000  # Default order size
        self.lambda_over = 0.01  # Over-execution penalty
        self.lambda_under = 0.005  # Under-execution penalty
        self.theta_queue = 0.002  # Queue risk penalty
        self.step = 100  # Allocation step size
        self.use_greedy_l2 = False  # Use greedy L2 allocation
        
    def setup_consumer(self, topics: List[str]) -> bool:
        """
        Setup Kafka consumer
        
        Args:
            topics: List of Kafka topics to consume from
            
        Returns:
            bool: True if consumer setup successfully
        """
        if not KAFKA_AVAILABLE:
            logger.error("Kafka library not available. Please install kafka-python-ng")
            return False
        
        try:
            self.consumer = KafkaConsumer(
                *topics,
                bootstrap_servers=self.bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                group_id='sor_consumer_group',
                auto_offset_reset='latest'
            )
            logger.info(f"Kafka consumer connected to {self.bootstrap_servers}")
            logger.info(f"Subscribed to topics: {', '.join(topics)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup Kafka consumer: {e}")
            return False
    
    def configure_sor(self, order_size: int = None, lambda_over: float = None, 
                     lambda_under: float = None, theta_queue: float = None,
                     step: int = None, use_greedy_l2: bool = None):
        """Configure SOR parameters"""
        if order_size is not None:
            self.order_size = order_size
        if lambda_over is not None:
            self.lambda_over = lambda_over
        if lambda_under is not None:
            self.lambda_under = lambda_under
        if theta_queue is not None:
            self.theta_queue = theta_queue
        if step is not None:
            self.step = step
        if use_greedy_l2 is not None:
            self.use_greedy_l2 = use_greedy_l2
            
        logger.info(f"SOR Configuration:")
        logger.info(f"  Order size: {self.order_size}")
        logger.info(f"  λ_over: {self.lambda_over}")
        logger.info(f"  λ_under: {self.lambda_under}")
        logger.info(f"  θ_queue: {self.theta_queue}")
        logger.info(f"  Step: {self.step}")
        logger.info(f"  Greedy L2: {self.use_greedy_l2}")
    
    def process_market_data(self, market_data: Dict) -> Optional[Dict]:
        """
        Process market data and execute SOR logic
        
        Args:
            market_data: Market data message from Kafka
            
        Returns:
            Dictionary with allocation results or None if processing failed
        """
        try:
            # Extract symbol for context
            symbol = market_data.get('symbol', 'UNKNOWN')
            timestamp = market_data.get('ts_event', datetime.now().isoformat())
            
            if self.use_greedy_l2:
                # Use greedy L2 allocation
                venues = self.processor.extract_l2_venues_from_l1(market_data)
                if not venues:
                    logger.warning(f"No venues extracted from market data for {symbol}")
                    return None
                
                allocation, total_cost = allocate_greedy_l2(
                    order_size=self.order_size,
                    venues=venues,
                    lambda_over=self.lambda_over,
                    lambda_under=self.lambda_under,
                    theta_queue=self.theta_queue
                )
                
                # Convert venues for response
                venue_info = []
                for i, venue in enumerate(venues):
                    venue_info.append({
                        'venue_id': venue.venue_id,
                        'levels': venue.levels,
                        'fee': venue.fee,
                        'rebate': venue.rebate,
                        'allocation': allocation[i] if i < len(allocation) else 0
                    })
                
            else:
                # Use brute-force allocation
                venues = self.processor.extract_venues_from_l1(market_data)
                if not venues:
                    logger.warning(f"No venues extracted from market data for {symbol}")
                    return None
                
                allocation, total_cost = allocate(
                    order_size=self.order_size,
                    venues=venues,
                    lambda_over=self.lambda_over,
                    lambda_under=self.lambda_under,
                    theta_queue=self.theta_queue,
                    step=self.step
                )
                
                # Convert venues for response
                venue_info = []
                for i, venue in enumerate(venues):
                    venue_info.append({
                        'venue_id': f'venue_{i}',
                        'ask': venue.ask,
                        'ask_size': venue.ask_size,
                        'fee': venue.fee,
                        'rebate': venue.rebate,
                        'allocation': allocation[i] if i < len(allocation) else 0
                    })
            
            # Calculate execution summary
            total_executed = 0
            total_cash = 0.0
            
            if self.use_greedy_l2:
                for i, venue in enumerate(venues):
                    if i >= len(allocation):
                        continue
                        
                    alloc = allocation[i]
                    executed = 0
                    cash = 0.0
                    remain = alloc
                    
                    for price, size in venue.levels:
                        if remain <= 0:
                            break
                        exe = min(remain, size)
                        executed += exe
                        cash += exe * (price + venue.fee)
                        remain -= exe
                    
                    # Maker rebates for over-allocation
                    maker = max(alloc - executed, 0)
                    cash -= maker * venue.rebate
                    
                    total_executed += executed
                    total_cash += cash
            else:
                for i, venue in enumerate(venues):
                    if i >= len(allocation):
                        continue
                        
                    alloc = allocation[i]
                    executed = min(alloc, venue.ask_size)
                    cash = executed * (venue.ask + venue.fee)
                    over_alloc = max(alloc - venue.ask_size, 0)
                    cash -= over_alloc * venue.rebate
                    
                    total_executed += executed
                    total_cash += cash
            
            underfill = max(self.order_size - total_executed, 0)
            overfill = max(total_executed - self.order_size, 0)
            
            result = {
                'symbol': symbol,
                'timestamp': timestamp,
                'order_size': self.order_size,
                'algorithm': 'greedy_l2' if self.use_greedy_l2 else 'brute_force',
                'venues': venue_info,
                'allocation': allocation,
                'total_cost': total_cost,
                'execution_summary': {
                    'total_executed': total_executed,
                    'underfill': underfill,
                    'overfill': overfill,
                    'cash_spent': total_cash,
                    'fill_rate': total_executed / self.order_size if self.order_size > 0 else 0
                },
                'parameters': {
                    'lambda_over': self.lambda_over,
                    'lambda_under': self.lambda_under,
                    'theta_queue': self.theta_queue,
                    'step': self.step if not self.use_greedy_l2 else None
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing market data: {e}")
            return None
    
    def consume_and_route(self, topics: List[str]) -> None:
        """
        Start consuming market data and executing SOR logic
        
        Args:
            topics: List of Kafka topics to consume from
        """
        if not self.setup_consumer(topics):
            return
        
        self.running = True
        
        # Setup signal handlers
        def signal_handler(signum, frame):
            logger.info("Stopping SOR consumer...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("=== Kafka SOR Consumer Started ===")
        logger.info(f"Topics: {', '.join(topics)}")
        logger.info("Press Ctrl+C to stop...")
        logger.info("-" * 50)
        
        try:
            while self.running:
                # Poll for messages with timeout
                message_batch = self.consumer.poll(timeout_ms=1000)
                
                if not message_batch:
                    continue
                
                for topic_partition, messages in message_batch.items():
                    for message in messages:
                        if not self.running:
                            break
                        
                        self.message_count += 1
                        
                        try:
                            # Process market data and execute SOR
                            result = self.process_market_data(message.value)
                            
                            if result:
                                # Log allocation result
                                symbol = result['symbol']
                                allocation = result['allocation']
                                cost = result['total_cost']
                                fill_rate = result['execution_summary']['fill_rate']
                                
                                logger.info(f"SOR Result [{symbol}]: allocation={allocation}, "
                                          f"cost=${cost:.2f}, fill_rate={fill_rate:.1%}")
                                
                                # Output complete result as JSON
                                print(json.dumps(result, indent=2))
                                print("-" * 50)
                            
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            continue
        
        except KeyboardInterrupt:
            logger.info("Consumer interrupted by user")
        
        except Exception as e:
            logger.error(f"Error in consumer loop: {e}")
        
        finally:
            self.stop()
        
        logger.info(f"Total messages processed: {self.message_count}")
    
    def stop(self) -> None:
        """Stop the consumer"""
        self.running = False
        if self.consumer:
            self.consumer.close()
            logger.info("Kafka consumer closed")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Kafka Smart Order Router Consumer')
    
    # Required arguments
    parser.add_argument('--topic', required=True,
                        help='Kafka topic to consume market data from')
    
    # Optional Kafka configuration
    parser.add_argument('--kafka-servers', default='localhost:9092',
                        help='Kafka bootstrap servers')
    
    # SOR configuration
    parser.add_argument('--order-size', type=int, default=5000,
                        help='Order size in shares')
    parser.add_argument('--lambda-over', type=float, default=0.01,
                        help='Over-execution penalty per share')
    parser.add_argument('--lambda-under', type=float, default=0.005,
                        help='Under-execution penalty per share')
    parser.add_argument('--theta-queue', type=float, default=0.002,
                        help='Queue risk penalty per share')
    parser.add_argument('--step', type=int, default=100,
                        help='Allocation step size (for brute-force)')
    parser.add_argument('--greedy-l2', action='store_true',
                        help='Use greedy L2 allocation instead of brute-force')
    
    args = parser.parse_args()
    
    # Create and configure SOR consumer
    consumer = KafkaSORConsumer(bootstrap_servers=args.kafka_servers)
    
    consumer.configure_sor(
        order_size=args.order_size,
        lambda_over=args.lambda_over,
        lambda_under=args.lambda_under,
        theta_queue=args.theta_queue,
        step=args.step,
        use_greedy_l2=args.greedy_l2
    )
    
    logger.info(f"Starting Kafka SOR Consumer for topic: {args.topic}")
    
    # Start consuming and routing
    consumer.consume_and_route(topics=[args.topic])


if __name__ == '__main__':
    main() 