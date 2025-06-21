#!/usr/bin/env python3
"""
Smart Order Router (SOR) with Cont & Kukanov Cost Model

Implements optimal allocation logic using brute-force search and
efficient level-2 cost computation with greedy level flattening.

Core Features:
- Brute-force allocation search over step-sized chunks
- Level-2 order book cost computation with queue risk
- Support for both single-level and multi-level venues
- Comprehensive penalty model (over/under execution, queue risk)
"""

from typing import List, NamedTuple, Tuple, Optional
import itertools
from dataclasses import dataclass
import logging

# Setup logging
logger = logging.getLogger(__name__)

class Venue(NamedTuple):
    """Single-level venue representation"""
    ask: float
    ask_size: int
    fee: float
    rebate: float

@dataclass
class Level2Venue:
    """Multi-level venue representation for L2 order books"""
    venue_id: str
    levels: List[Tuple[float, int]]  # [(price, size), ...]
    fee: float
    rebate: float

@dataclass
class PriceLevel:
    """Price level for greedy allocation"""
    venue_id: int
    level: int
    price: float
    size: int
    effective_cost: float  # price + fee - rebate


def compute_cost(
    split: List[int],
    venues: List[Venue],
    order_size: int,
    lambda_over: float,
    lambda_under: float,
    theta_queue: float
) -> float:
    """
    Compute total cost for a given split allocation using Cont & Kukanov model.
    
    Args:
        split: List of shares allocated to each venue
        venues: List of venue objects with ask, ask_size, fee, rebate
        order_size: Total shares to execute
        lambda_over: Penalty per share over-executed
        lambda_under: Penalty per share under-executed
        theta_queue: Linear queue-risk penalty per mis-executed share
        
    Returns:
        Total expected cost (cash spent + penalties + queue risk)
    """
    executed = 0
    cash_spent = 0.0
    
    for i, venue in enumerate(venues):
        allocation = split[i]
        if allocation <= 0:
            continue
            
        # Shares actually executed at this venue
        venue_executed = min(allocation, venue.ask_size)
        executed += venue_executed
        
        # Cash spent: executed shares pay taker fees
        cash_spent += venue_executed * (venue.ask + venue.fee)
        
        # Over-allocation beyond available liquidity earns maker rebates
        over_allocation = max(allocation - venue.ask_size, 0)
        cash_spent -= over_allocation * venue.rebate
    
    # Penalty calculations
    underfill = max(order_size - executed, 0)
    overfill = max(executed - order_size, 0)
    
    # Queue risk penalty
    risk_penalty = theta_queue * (underfill + overfill)
    
    # Cost penalties
    cost_penalty = lambda_under * underfill + lambda_over * overfill
    
    total_cost = cash_spent + risk_penalty + cost_penalty
    
    logger.debug(f"Split {split}: executed={executed}, cash={cash_spent:.2f}, "
                f"under={underfill}, over={overfill}, risk={risk_penalty:.2f}, "
                f"cost_pen={cost_penalty:.2f}, total={total_cost:.2f}")
    
    return total_cost


def compute_cost_l2(
    allocation: int,
    venue: Level2Venue,
    order_size: int,
    lambda_over: float,
    lambda_under: float,
    theta_queue: float
) -> float:
    """
    Compute cost for Level-2 venue with multiple price levels.
    
    Args:
        allocation: Total shares to allocate to this venue
        venue: Level2Venue with multiple price levels
        order_size: Total order size
        lambda_over: Over-execution penalty
        lambda_under: Under-execution penalty
        theta_queue: Queue risk penalty
        
    Returns:
        Total cost for this venue allocation
    """
    executed = 0
    cash = 0.0
    remain = allocation
    
    # Fill through price levels sequentially
    for price, size in venue.levels:
        if remain <= 0:
            break
            
        exe = min(remain, size)
        executed += exe
        cash += exe * (price + venue.fee)  # Taker cost
        remain -= exe
    
    # Any leftover allocation beyond available liquidity becomes maker rebate
    maker = max(allocation - executed, 0)
    cash -= maker * venue.rebate
    
    # Penalties (computed per venue for aggregation later)
    under = max(order_size - executed, 0)
    over = max(executed - order_size, 0)
    risk = theta_queue * (under + over)
    cost_penalty = lambda_under * under + lambda_over * over
    
    return cash + risk + cost_penalty


def generate_splits(order_size: int, num_venues: int, step: int = 100) -> List[List[int]]:
    """
    Generate all possible splits that sum to order_size.
    
    Args:
        order_size: Total shares to allocate
        num_venues: Number of venues
        step: Allocation granularity
        
    Returns:
        List of all valid splits (each sums to order_size)
    """
    if num_venues == 1:
        return [[order_size]]
    
    splits = []
    max_allocation = order_size
    
    # Generate allocations for first venue: 0, step, 2*step, ..., order_size
    for first_venue_alloc in range(0, max_allocation + 1, step):
        if first_venue_alloc > order_size:
            break
            
        remaining = order_size - first_venue_alloc
        
        # Recursively generate splits for remaining venues
        sub_splits = generate_splits(remaining, num_venues - 1, step)
        
        for sub_split in sub_splits:
            splits.append([first_venue_alloc] + sub_split)
    
    return splits


def allocate(
    order_size: int,
    venues: List[Venue],
    lambda_over: float,
    lambda_under: float,
    theta_queue: float,
    step: int = 100
) -> Tuple[List[int], float]:
    """
    Find optimal allocation using brute-force search over all possible splits.
    
    Args:
        order_size: Total shares to execute
        venues: List of venues with ask, ask_size, fee, rebate
        lambda_over: Penalty per share over-executed
        lambda_under: Penalty per share under-executed
        theta_queue: Linear queue-risk penalty per mis-executed share
        step: Allocation granularity (shares)
        
    Returns:
        Tuple of (best_split, best_cost)
    """
    if not venues:
        return [], float('inf')
    
    logger.info(f"Optimizing allocation for {order_size} shares across {len(venues)} venues")
    logger.info(f"Parameters: λ_over={lambda_over}, λ_under={lambda_under}, θ_queue={theta_queue}, step={step}")
    
    # Generate all possible splits
    splits = generate_splits(order_size, len(venues), step)
    logger.info(f"Evaluating {len(splits)} possible allocations")
    
    best_split = None
    best_cost = float('inf')
    
    for split in splits:
        cost = compute_cost(split, venues, order_size, lambda_over, lambda_under, theta_queue)
        
        if cost < best_cost:
            best_cost = cost
            best_split = split
    
    logger.info(f"Optimal allocation: {best_split} with cost {best_cost:.2f}")
    return best_split, best_cost


def allocate_greedy_l2(
    order_size: int,
    venues: List[Level2Venue],
    lambda_over: float,
    lambda_under: float,
    theta_queue: float
) -> Tuple[List[int], float]:
    """
    Greedy allocation using level flattening for L2 order books.
    
    This approach flattens all (venue, level) pairs into a sorted list
    and greedily fills from the cheapest effective cost slices.
    
    Args:
        order_size: Total shares to execute
        venues: List of Level2Venue objects
        lambda_over: Over-execution penalty
        lambda_under: Under-execution penalty
        theta_queue: Queue risk penalty
        
    Returns:
        Tuple of (allocation_per_venue, total_cost)
    """
    if not venues:
        return [], float('inf')
    
    # Build flattened price levels
    price_levels = []
    for venue_idx, venue in enumerate(venues):
        for level_idx, (price, size) in enumerate(venue.levels):
            effective_cost = price + venue.fee - venue.rebate
            price_levels.append(PriceLevel(
                venue_id=venue_idx,
                level=level_idx,
                price=price,
                size=size,
                effective_cost=effective_cost
            ))
    
    # Sort by effective cost (cheapest first)
    price_levels.sort(key=lambda x: x.effective_cost)
    
    # Greedy allocation
    allocation = [0] * len(venues)
    executed = 0
    cash_spent = 0.0
    remaining_order = order_size
    
    for level in price_levels:
        if remaining_order <= 0:
            break
            
        # Take as much as possible from this level
        take = min(remaining_order, level.size)
        allocation[level.venue_id] += take
        executed += take
        cash_spent += take * (level.price + venues[level.venue_id].fee)
        remaining_order -= take
    
    # Calculate penalties
    underfill = max(order_size - executed, 0)
    overfill = max(executed - order_size, 0)
    risk_penalty = theta_queue * (underfill + overfill)
    cost_penalty = lambda_under * underfill + lambda_over * overfill
    
    total_cost = cash_spent + risk_penalty + cost_penalty
    
    logger.info(f"Greedy L2 allocation: {allocation}")
    logger.info(f"Executed: {executed}/{order_size}, Cost: {total_cost:.2f}")
    
    return allocation, total_cost


def run_test_harness():
    """Test harness for validating SOR algorithms"""
    print("Running SOR Test Harness...")
    
    # Test venues
    venues = [
        Venue(ask=100.0, ask_size=1000, fee=0.003, rebate=0.001),
        Venue(ask=100.1, ask_size=2000, fee=0.003, rebate=0.001),
        Venue(ask=100.2, ask_size=1500, fee=0.003, rebate=0.001)
    ]
    
    order_size = 5000
    lambda_over = 0.01
    lambda_under = 0.005
    theta_queue = 0.002
    step = 100
    
    print(f"\nTest Configuration:")
    print(f"Order Size: {order_size}")
    print(f"Venues: {len(venues)}")
    print(f"λ_over: {lambda_over}, λ_under: {lambda_under}, θ_queue: {theta_queue}")
    
    # Run brute-force allocation
    print("\n--- Brute-Force Allocation ---")
    best_split, best_cost = allocate(order_size, venues, lambda_over, lambda_under, theta_queue, step)
    print(f"Optimal allocation: {best_split}")
    print(f"Total cost: ${best_cost:.2f}")
    
    # Test Level-2 venues
    l2_venues = [
        Level2Venue(
            venue_id="venue_0",
            levels=[(100.0, 500), (100.05, 500)],
            fee=0.003,
            rebate=0.001
        ),
        Level2Venue(
            venue_id="venue_1", 
            levels=[(100.1, 1000), (100.15, 1000)],
            fee=0.003,
            rebate=0.001
        )
    ]
    
    print("\n--- Greedy L2 Allocation ---")
    l2_allocation, l2_cost = allocate_greedy_l2(order_size, l2_venues, lambda_over, lambda_under, theta_queue)
    print(f"L2 allocation: {l2_allocation}")
    print(f"L2 cost: ${l2_cost:.2f}")


class SmartOrderRouter:
    """
    Smart Order Router class that wraps the allocation functions
    for easier integration with other systems.
    """
    
    def __init__(self, order_size=5000, lambda_over=0.01, lambda_under=0.005, 
                 theta_queue=0.002, step=100, greedy_l2=False):
        """
        Initialize Smart Order Router
        
        Args:
            order_size: Total shares to execute
            lambda_over: Over-execution penalty per share
            lambda_under: Under-execution penalty per share  
            theta_queue: Queue risk penalty per share
            step: Allocation step size for brute-force
            greedy_l2: Use greedy L2 algorithm instead of brute-force
        """
        self.order_size = order_size
        self.lambda_over = lambda_over
        self.lambda_under = lambda_under
        self.theta_queue = theta_queue
        self.step = step
        self.greedy_l2 = greedy_l2
        
    def optimize_allocation(self, venues_data):
        """
        Optimize allocation across venues
        
        Args:
            venues_data: List of venue dictionaries with keys:
                        venue_id, ask, ask_size, fee, rebate
                        
        Returns:
            Dictionary with allocation results
        """
        try:
            # Convert venue data to Venue objects
            venues = []
            for v in venues_data:
                venue = Venue(
                    ask=float(v['ask']),
                    ask_size=int(v['ask_size']),
                    fee=float(v.get('fee', 0.003)),
                    rebate=float(v.get('rebate', 0.001))
                )
                venues.append(venue)
            
            if not venues:
                return None
                
            # Run optimization
            allocation, total_cost = allocate(
                self.order_size, venues, self.lambda_over, 
                self.lambda_under, self.theta_queue, self.step
            )
            
            # Calculate execution summary
            total_executed = 0
            for i, venue in enumerate(venues):
                executed_at_venue = min(allocation[i], venue.ask_size)
                total_executed += executed_at_venue
            
            underfill = max(self.order_size - total_executed, 0)
            overfill = max(total_executed - self.order_size, 0)
            fill_rate = total_executed / self.order_size if self.order_size > 0 else 0
            
            # Format venue details
            venue_details = []
            for i, (venue_data, alloc) in enumerate(zip(venues_data, allocation)):
                venue_details.append({
                    'venue_id': venue_data.get('venue_id', f'venue_{i}'),
                    'ask': venues[i].ask,
                    'ask_size': venues[i].ask_size,
                    'fee': venues[i].fee,
                    'rebate': venues[i].rebate,
                    'allocation': alloc
                })
            
            return {
                'allocation': allocation,
                'total_cost': total_cost,
                'execution_summary': {
                    'total_executed': total_executed,
                    'underfill': underfill,
                    'overfill': overfill,
                    'cash_spent': total_cost,  # Simplified for now
                    'fill_rate': fill_rate
                },
                'venues': venue_details
            }
            
        except Exception as e:
            logger.error(f"Error in optimize_allocation: {e}")
            return None


if __name__ == '__main__':
    run_test_harness() 