#!/usr/bin/env python3
"""
Find optimal delay to avoid 429 errors
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

latest = w3.eth.block_number
from_block = latest - 100
to_block = latest

print("="*80)
print("FINDING OPTIMAL REQUEST DELAY")
print("="*80)

# Test different delays
delays_to_test = [0.1, 0.2, 0.3, 0.5, 1.0]

for delay in delays_to_test:
    print(f"\n{'='*80}")
    print(f"Testing {delay}s delay between requests")
    print('='*80)

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
            print(f"  ✅ Request {successes + errors}: Success")
        except Exception as e:
            errors += 1
            error_msg = str(e)
            if '429' in error_msg:
                print(f"  ❌ Request {successes + errors}: RATE LIMITED")
            else:
                print(f"  ❌ Request {successes + errors}: {error_msg[:40]}")

        if i < len(MONITORED_ADDRESSES) or True:  # Always delay
            time.sleep(delay)

        # Taker query
        try:
            logs = w3.eth.get_logs({
                'fromBlock': from_block,
                'toBlock': to_block,
                'address': POLYMARKET_CONTRACTS,
                'topics': [ORDER_FILLED_SIG, None, None, address_topic]
            })
            successes += 1
            print(f"  ✅ Request {successes + errors}: Success")
        except Exception as e:
            errors += 1
            error_msg = str(e)
            if '429' in error_msg:
                print(f"  ❌ Request {successes + errors}: RATE LIMITED")
            else:
                print(f"  ❌ Request {successes + errors}: {error_msg[:40]}")

        if i < len(MONITORED_ADDRESSES):
            time.sleep(delay)

    elapsed = time.time() - start_time
    success_rate = successes / (successes + errors) * 100 if successes + errors > 0 else 0

    print(f"\n  Results:")
    print(f"    Success: {successes}/{successes + errors} ({success_rate:.0f}%)")
    print(f"    Time: {elapsed:.2f}s")
    print(f"    Rate: {(successes + errors) / elapsed:.2f} req/s")

    if errors == 0:
        print(f"  ✅ {delay}s delay is SUFFICIENT - no errors!")

        # Calculate impact on monitoring
        requests_per_batch = len(MONITORED_ADDRESSES) * 2
        time_per_batch = elapsed
        poll_interval = 60

        print(f"\n  Impact on monitoring:")
        print(f"    Requests per batch: {requests_per_batch}")
        print(f"    Time per batch: {time_per_batch:.1f}s")
        print(f"    Overhead: {time_per_batch / poll_interval * 100:.1f}% of poll interval")

        if time_per_batch < poll_interval * 0.5:
            print(f"    ✅ Comfortably fits in {poll_interval}s poll interval")

        # This is our answer, we can stop
        print(f"\n{'='*80}")
        print(f"RECOMMENDATION: Use {delay}s delay between requests")
        print('='*80)
        break
    else:
        print(f"  ❌ {delay}s delay is NOT sufficient - {errors} errors")

        # If this is the last delay and still getting errors
        if delay == delays_to_test[-1]:
            print(f"\n  ⚠️  Even {delay}s delay has errors!")
            print(f"  Recommendation: Use 1.0s delay or implement retry logic")
