#!/usr/bin/env python3
"""
Test Infura RPC capabilities and limits
"""
from web3 import Web3
import time
from datetime import datetime

# Infura configuration
INFURA_API_KEY = "ccd5bbbeb4f94ed99256b551402b053e"
INFURA_URL = f"https://polygon-mainnet.infura.io/v3/{INFURA_API_KEY}"

# Test addresses and contracts
MONITORED_ADDRESSES = [
    Web3.to_checksum_address("0x0f37cb80dee49d55b5f6d9e595d52591d6371410"),
    Web3.to_checksum_address("0xca8f0374e3fc79b485499cc0b038d4f7e783d963"),
    Web3.to_checksum_address("0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b")
]

POLYMARKET_CONTRACTS = [
    Web3.to_checksum_address("0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e"),
    Web3.to_checksum_address("0xc5d563a36ae78145c45a50134d48a1215220f80a"),
]

ORDER_FILLED_SIG = "0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6"

print("="*80)
print("INFURA RPC TESTING")
print("="*80)

# Test 1: Basic connection
print("\nTest 1: Connection Test")
print("-"*80)

try:
    w3 = Web3(Web3.HTTPProvider(INFURA_URL))
    if w3.is_connected():
        print("✅ Connected to Infura Polygon RPC")
        latest = w3.eth.block_number
        print(f"   Latest block: {latest}")
    else:
        print("❌ Failed to connect")
        exit(1)
except Exception as e:
    print(f"❌ Connection error: {e}")
    exit(1)

# Test 2: eth_getLogs block range limit
print("\nTest 2: Block Range Limits")
print("-"*80)

latest = w3.eth.block_number
ranges_to_test = [100, 500, 1000, 2000, 3000, 5000, 10000]
max_working_range = 0

for range_size in ranges_to_test:
    try:
        start_time = time.time()
        logs = w3.eth.get_logs({
            'fromBlock': latest - range_size,
            'toBlock': latest,
            'address': POLYMARKET_CONTRACTS,
            'topics': [ORDER_FILLED_SIG]
        })
        elapsed = time.time() - start_time
        print(f"  ✅ Range {range_size:5d} blocks: {len(logs):5d} events ({elapsed:.2f}s)")
        max_working_range = range_size
    except Exception as e:
        error_msg = str(e)
        if 'query returned more than' in error_msg.lower() or 'too large' in error_msg.lower():
            print(f"  ❌ Range {range_size:5d} blocks: TOO LARGE")
            print(f"     Error: {error_msg[:100]}")
            break
        elif 'exceeds' in error_msg.lower():
            print(f"  ❌ Range {range_size:5d} blocks: EXCEEDS LIMIT")
            print(f"     Error: {error_msg[:100]}")
            break
        else:
            print(f"  ❌ Range {range_size:5d} blocks: {error_msg[:80]}")
            break

print(f"\n  🎯 Maximum working range: {max_working_range} blocks")
print(f"     ({max_working_range * 2 / 60:.1f} minutes of blockchain time)")

# Test 3: Query monitored addresses
print("\nTest 3: Query Monitored Addresses")
print("-"*80)

test_range = min(max_working_range, 1000) if max_working_range > 0 else 100
from_block = latest - test_range
to_block = latest

total_trades_found = 0

for i, address in enumerate(MONITORED_ADDRESSES, 1):
    print(f"\nAddress {i}: {address[:10]}...")
    address_topic = '0x' + address[2:].zfill(64).lower()

    try:
        # As maker
        start_time = time.time()
        logs_maker = w3.eth.get_logs({
            'fromBlock': from_block,
            'toBlock': to_block,
            'address': POLYMARKET_CONTRACTS,
            'topics': [ORDER_FILLED_SIG, None, address_topic]
        })
        elapsed_maker = time.time() - start_time

        # As taker
        start_time = time.time()
        logs_taker = w3.eth.get_logs({
            'fromBlock': from_block,
            'toBlock': to_block,
            'address': POLYMARKET_CONTRACTS,
            'topics': [ORDER_FILLED_SIG, None, None, address_topic]
        })
        elapsed_taker = time.time() - start_time

        total = len(logs_maker) + len(logs_taker)
        total_trades_found += total

        print(f"  Maker: {len(logs_maker)} trades ({elapsed_maker:.2f}s)")
        print(f"  Taker: {len(logs_taker)} trades ({elapsed_taker:.2f}s)")
        print(f"  Total: {total} trades")

    except Exception as e:
        print(f"  ❌ Error: {e}")

print(f"\n  Total trades found (last {test_range} blocks): {total_trades_found}")

# Test 4: Calculate API usage for full monitoring
print("\n" + "="*80)
print("INFURA FREE TIER ANALYSIS")
print("="*80)

print("\nInfura Free Tier Limits:")
print("  - 100,000 requests per day")
print("  - No credit card required")
print("  - Rate limit: ~25-30 requests/second")

print("\nOur Monitoring Requirements:")
print(f"  - Monitored addresses: {len(MONITORED_ADDRESSES)}")
print(f"  - Contracts to query: {len(POLYMARKET_CONTRACTS)}")
print(f"  - Roles to check: 2 (maker + taker)")
print(f"  - Total queries per batch: {len(MONITORED_ADDRESSES)} addresses × 2 roles = {len(MONITORED_ADDRESSES) * 2}")

# Calculate based on different batch sizes
print("\n" + "-"*80)
print("Scenario Analysis:")
print("-"*80)

batch_sizes = [50, 100, 500, 1000, max_working_range] if max_working_range > 0 else [50, 100, 500]

# Polygon block time: ~2 seconds
# Blocks per day: 24*60*60/2 = 43,200 blocks
blocks_per_day = 43200
blocks_per_hour = 1800

for batch_size in batch_sizes:
    if batch_size == 0:
        continue

    print(f"\nBatch size: {batch_size} blocks")

    # Queries needed per batch
    queries_per_batch = len(MONITORED_ADDRESSES) * 2  # maker + taker for each address

    # Batches needed to process one day of blocks
    batches_per_day = blocks_per_day / batch_size

    # Total queries per day
    queries_per_day = batches_per_day * queries_per_batch

    # Add overhead for get_latest_block calls (every poll)
    # Assume polling every 60 seconds = 1440 polls/day
    polls_per_day = 1440
    overhead_queries = polls_per_day * 1  # 1 query per poll

    total_queries_per_day = queries_per_day + overhead_queries

    # Check if within limit
    within_limit = total_queries_per_day <= 100000
    usage_percent = (total_queries_per_day / 100000) * 100

    print(f"  Batches/day: {batches_per_day:.1f}")
    print(f"  Queries/day: {queries_per_day:.0f} (monitoring) + {overhead_queries} (overhead) = {total_queries_per_day:.0f}")
    print(f"  Usage: {usage_percent:.1f}% of free tier")
    print(f"  Status: {'✅ WITHIN LIMIT' if within_limit else '❌ EXCEEDS LIMIT'}")

    if within_limit:
        # Calculate how much headroom we have
        remaining = 100000 - total_queries_per_day
        print(f"  Headroom: {remaining:.0f} requests/day ({remaining/100000*100:.1f}%)")

# Test 5: Real-time monitoring simulation
print("\n" + "="*80)
print("REAL-TIME MONITORING SIMULATION")
print("="*80)

optimal_batch = min(1000, max_working_range) if max_working_range > 0 else 100

print(f"\nSimulating monitoring with {optimal_batch}-block batches:")
print(f"  Poll interval: 60 seconds")
print(f"  Expected new blocks per poll: ~30 blocks (60s / 2s per block)")

# Simulate catching up from 100 blocks behind
catch_up_blocks = 100
batches_needed = (catch_up_blocks + optimal_batch - 1) // optimal_batch
queries_needed = batches_needed * len(MONITORED_ADDRESSES) * 2

print(f"\nCatch-up scenario (100 blocks behind):")
print(f"  Batches needed: {batches_needed}")
print(f"  Queries needed: {queries_needed}")
print(f"  Estimated time: {batches_needed * 2:.0f} seconds")

# Calculate real-time sustainability
print(f"\nSustainable monitoring:")
blocks_per_poll = 30  # ~60 seconds of blocks
batches_per_poll = (blocks_per_poll + optimal_batch - 1) // optimal_batch
queries_per_poll = batches_per_poll * len(MONITORED_ADDRESSES) * 2 + 1  # +1 for get_latest_block

polls_per_day = 1440  # Every 60 seconds
daily_queries_sustainable = polls_per_day * queries_per_poll

print(f"  Blocks per poll: {blocks_per_poll}")
print(f"  Batches per poll: {batches_per_poll}")
print(f"  Queries per poll: {queries_per_poll}")
print(f"  Daily queries: {daily_queries_sustainable}")
print(f"  Usage: {daily_queries_sustainable/100000*100:.1f}% of free tier")
print(f"  Status: {'✅ SUSTAINABLE' if daily_queries_sustainable < 100000 else '❌ NOT SUSTAINABLE'}")

# Test 6: Historical sync calculation
print("\n" + "="*80)
print("HISTORICAL SYNC CALCULATION")
print("="*80)

# From database, we know start block is 79517500
# Calculate how many blocks we need to sync
start_block = 79517500
current_block = latest
blocks_to_sync = current_block - start_block

print(f"\nHistorical sync requirements:")
print(f"  Start block: {start_block}")
print(f"  Current block: {current_block}")
print(f"  Blocks to sync: {blocks_to_sync:,}")

if max_working_range > 0:
    batches_needed = (blocks_to_sync + max_working_range - 1) // max_working_range
    queries_needed = batches_needed * len(MONITORED_ADDRESSES) * 2

    print(f"\nUsing {max_working_range}-block batches:")
    print(f"  Batches needed: {batches_needed:,}")
    print(f"  Queries needed: {queries_needed:,}")
    print(f"  Days to complete (at 100k/day): {queries_needed/100000:.1f} days")

    # If we spread it out
    queries_per_day_available = 80000  # Leave 20k for real-time monitoring
    days_to_sync = queries_needed / queries_per_day_available

    print(f"\nWith conservative approach (80k queries/day for sync):")
    print(f"  Days to complete: {days_to_sync:.1f} days")
    print(f"  Status: {'✅ FEASIBLE' if days_to_sync < 7 else '⚠️  WILL TAKE A WHILE'}")

print("\n" + "="*80)
print("RECOMMENDATIONS")
print("="*80)

if max_working_range >= 1000:
    print("\n✅ Infura is EXCELLENT for this use case!")
    print(f"   - Max range: {max_working_range} blocks (much better than free RPC)")
    print(f"   - Free tier: 100k requests/day is sufficient")
    print(f"   - Can monitor 3 addresses in real-time comfortably")
    print(f"\n💡 Suggested configuration:")
    print(f"   - Batch size: {min(1000, max_working_range)} blocks")
    print(f"   - Poll interval: 60 seconds")
    print(f"   - Expected usage: ~{daily_queries_sustainable:,.0f} queries/day ({daily_queries_sustainable/100000*100:.1f}%)")
else:
    print("\n⚠️  Infura has limitations similar to free RPC")
    print(f"   - Max range: {max_working_range} blocks")
    print("   - May need to use smaller batches")
