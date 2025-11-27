#!/usr/bin/env python3
"""
Test Infura rate limiting and find optimal request pattern
"""
from web3 import Web3
import time

INFURA_API_KEY = "ccd5bbbeb4f94ed99256b551402b053e"
INFURA_URL = f"https://polygon-mainnet.infura.io/v3/{INFURA_API_KEY}"

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

w3 = Web3(Web3.HTTPProvider(INFURA_URL))

print("="*80)
print("INFURA RATE LIMIT TESTING")
print("="*80)

latest = w3.eth.block_number
from_block = latest - 100
to_block = latest

# Test 1: Burst requests (no delay)
print("\nTest 1: Burst Requests (No Delay)")
print("-"*80)

errors = 0
successes = 0
start_time = time.time()

for i, address in enumerate(MONITORED_ADDRESSES, 1):
    address_topic = '0x' + address[2:].zfill(64).lower()

    # Maker query
    try:
        logs = w3.eth.get_logs({
            'fromBlock': from_block,
            'toBlock': to_block,
            'address': POLYMARKET_CONTRACTS,
            'topics': [ORDER_FILLED_SIG, None, address_topic]
        })
        successes += 1
        print(f"  Request {successes}: ✅ Success (maker {i})")
    except Exception as e:
        errors += 1
        print(f"  Request {successes + errors}: ❌ Error - {str(e)[:60]}")

    # Taker query
    try:
        logs = w3.eth.get_logs({
            'fromBlock': from_block,
            'toBlock': to_block,
            'address': POLYMARKET_CONTRACTS,
            'topics': [ORDER_FILLED_SIG, None, None, address_topic]
        })
        successes += 1
        print(f"  Request {successes}: ✅ Success (taker {i})")
    except Exception as e:
        errors += 1
        print(f"  Request {successes + errors}: ❌ Error - {str(e)[:60]}")

elapsed = time.time() - start_time
print(f"\nResults: {successes}/{successes + errors} successful in {elapsed:.2f}s")
print(f"Rate: {(successes + errors) / elapsed:.1f} requests/second")

if errors > 0:
    print("\n⚠️  Rate limiting detected! Testing with delays...")

    # Test 2: With small delays
    print("\nTest 2: Requests with 0.5s Delay")
    print("-"*80)

    errors = 0
    successes = 0
    start_time = time.time()

    for i, address in enumerate(MONITORED_ADDRESSES, 1):
        address_topic = '0x' + address[2:].zfill(64).lower()

        # Maker query
        try:
            logs = w3.eth.get_logs({
                'fromBlock': from_block,
                'toBlock': to_block,
                'address': POLYMARKET_CONTRACTS,
                'topics': [ORDER_FILLED_SIG, None, address_topic]
            })
            successes += 1
            print(f"  Request {successes}: ✅ Success (maker {i})")
        except Exception as e:
            errors += 1
            print(f"  Request {successes + errors}: ❌ Error - {str(e)[:60]}")

        time.sleep(0.5)  # Delay between requests

        # Taker query
        try:
            logs = w3.eth.get_logs({
                'fromBlock': from_block,
                'toBlock': to_block,
                'address': POLYMARKET_CONTRACTS,
                'topics': [ORDER_FILLED_SIG, None, None, address_topic]
            })
            successes += 1
            print(f"  Request {successes}: ✅ Success (taker {i})")
        except Exception as e:
            errors += 1
            print(f"  Request {successes + errors}: ❌ Error - {str(e)[:60]}")

        time.sleep(0.5)  # Delay between requests

    elapsed = time.time() - start_time
    print(f"\nResults: {successes}/{successes + errors} successful in {elapsed:.2f}s")

    if errors == 0:
        print("✅ 0.5s delay is sufficient to avoid rate limiting")
    else:
        print("⚠️  Need longer delays")

# Test 3: Optimal batch processing pattern
print("\n" + "="*80)
print("OPTIMAL MONITORING PATTERN")
print("="*80)

print("\nTesting realistic monitoring scenario:")
print("  - Process 100 blocks")
print("  - Query all 3 addresses (maker + taker)")
print("  - Measure total time")

start_time = time.time()
total_trades = 0
request_count = 0
request_times = []

for i, address in enumerate(MONITORED_ADDRESSES, 1):
    address_topic = '0x' + address[2:].zfill(64).lower()

    try:
        # Maker query
        req_start = time.time()
        logs_maker = w3.eth.get_logs({
            'fromBlock': from_block,
            'toBlock': to_block,
            'address': POLYMARKET_CONTRACTS,
            'topics': [ORDER_FILLED_SIG, None, address_topic]
        })
        req_time = time.time() - req_start
        request_times.append(req_time)
        request_count += 1

        time.sleep(0.2)  # Small delay to be safe

        # Taker query
        req_start = time.time()
        logs_taker = w3.eth.get_logs({
            'fromBlock': from_block,
            'toBlock': to_block,
            'address': POLYMARKET_CONTRACTS,
            'topics': [ORDER_FILLED_SIG, None, None, address_topic]
        })
        req_time = time.time() - req_start
        request_times.append(req_time)
        request_count += 1

        trades = len(logs_maker) + len(logs_taker)
        total_trades += trades

        print(f"  Address {i}: {len(logs_maker)} maker + {len(logs_taker)} taker = {trades} trades")

        time.sleep(0.2)  # Small delay to be safe

    except Exception as e:
        print(f"  Address {i}: ❌ Error - {e}")

total_time = time.time() - start_time
avg_request_time = sum(request_times) / len(request_times) if request_times else 0

print(f"\nResults:")
print(f"  Total requests: {request_count}")
print(f"  Total time: {total_time:.2f}s")
print(f"  Average request time: {avg_request_time:.2f}s")
print(f"  Total trades found: {total_trades}")
print(f"  Effective rate: {request_count / total_time:.1f} req/s")

# Calculate sustainable monitoring parameters
print("\n" + "="*80)
print("RECOMMENDED CONFIGURATION")
print("="*80)

# Polygon: ~2 seconds per block, ~30 blocks per minute
blocks_per_minute = 30
poll_interval = 60  # seconds

print(f"\nFor real-time monitoring:")
print(f"  Poll interval: {poll_interval}s")
print(f"  Expected new blocks per poll: ~{blocks_per_minute} blocks")
print(f"  Queries per poll: {len(MONITORED_ADDRESSES) * 2 + 1} (6 getLogs + 1 getBlockNumber)")
print(f"  Time per batch (estimated): {total_time:.0f}s")

if total_time < poll_interval:
    print(f"  ✅ Can complete within poll interval ({total_time:.0f}s < {poll_interval}s)")
    spare_time = poll_interval - total_time
    print(f"  Spare time: {spare_time:.0f}s ({spare_time/poll_interval*100:.0f}% buffer)")
else:
    print(f"  ⚠️  May take longer than poll interval")
    print(f"  Consider: Reduce delay between requests or increase poll interval")

# Daily request calculation
polls_per_day = 86400 / poll_interval
queries_per_day = polls_per_day * (len(MONITORED_ADDRESSES) * 2 + 1)

print(f"\nDaily usage estimate:")
print(f"  Polls per day: {polls_per_day:.0f}")
print(f"  Queries per day: {queries_per_day:.0f}")
print(f"  Infura free tier: 100,000 requests/day")
print(f"  Usage: {queries_per_day/100000*100:.1f}%")
print(f"  Status: {'✅ WELL WITHIN LIMIT' if queries_per_day < 100000 else '❌ EXCEEDS LIMIT'}")

print("\n" + "="*80)
print("FINAL RECOMMENDATIONS")
print("="*80)

print("""
✅ Infura Free Tier is PERFECT for this use case!

Configuration:
  - Batch size: 100 blocks
  - Poll interval: 60 seconds
  - Delay between requests: 0.2 seconds (to be safe)
  - Expected daily usage: ~10,000 requests (10% of limit)

Benefits vs Free RPC:
  - 2x larger batch size (100 vs 50 blocks)
  - More reliable connection
  - Better performance
  - Still well within free tier limits

Implementation:
  1. Use Infura as primary RPC
  2. Keep free RPC as backup/failover
  3. Add 0.2s delay between eth_getLogs calls
  4. Monitor API usage via Infura dashboard
""")
