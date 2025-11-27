#!/usr/bin/env python3
"""
Simple test of eth_getLogs with minimal range
"""
from web3 import Web3
import time

# Test multiple RPC endpoints
RPC_ENDPOINTS = [
    "https://polygon-rpc.com",
    "https://rpc-mainnet.matic.network",
    "https://polygon-mainnet.public.blastapi.io",
]

POLYMARKET_CTF = Web3.to_checksum_address("0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e")
TEST_ADDRESS = Web3.to_checksum_address("0x0f37cb80dee49d55b5f6d9e595d52591d6371410")

def test_rpc_endpoint(rpc_url):
    print(f"\n{'='*80}")
    print(f"Testing: {rpc_url}")
    print('='*80)

    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 15}))

    if not w3.is_connected():
        print("❌ Connection failed")
        return None

    latest = w3.eth.block_number
    print(f"✓ Connected, latest block: {latest}")

    # Test 1: Try different block ranges to find the limit
    ranges = [10, 50, 100, 500, 1000, 2000]
    max_working_range = 0

    for range_size in ranges:
        try:
            start = time.time()
            logs = w3.eth.get_logs({
                'fromBlock': latest - range_size,
                'toBlock': latest,
                'address': POLYMARKET_CTF
            })
            elapsed = time.time() - start
            print(f"  ✓ Range {range_size:4d} blocks: {len(logs):4d} events ({elapsed:.2f}s)")
            max_working_range = range_size
        except Exception as e:
            error_msg = str(e)
            if 'too large' in error_msg.lower():
                print(f"  ❌ Range {range_size:4d} blocks: TOO LARGE")
                break
            else:
                print(f"  ❌ Range {range_size:4d} blocks: {error_msg[:50]}")
                break

    print(f"\n  Maximum working range: {max_working_range} blocks")

    # Test 2: Filter by address in topics (maker/taker)
    if max_working_range > 0:
        print(f"\n  Testing address filtering in topics (last {max_working_range} blocks)...")

        ORDER_FILLED_SIG = "0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6"
        address_topic = '0x' + TEST_ADDRESS[2:].zfill(64).lower()

        try:
            # Search as maker
            logs_maker = w3.eth.get_logs({
                'fromBlock': latest - max_working_range,
                'toBlock': latest,
                'address': POLYMARKET_CTF,
                'topics': [ORDER_FILLED_SIG, None, address_topic]
            })
            print(f"  ✓ As MAKER: {len(logs_maker)} trades")

            # Search as taker
            logs_taker = w3.eth.get_logs({
                'fromBlock': latest - max_working_range,
                'toBlock': latest,
                'address': POLYMARKET_CTF,
                'topics': [ORDER_FILLED_SIG, None, None, address_topic]
            })
            print(f"  ✓ As TAKER: {len(logs_taker)} trades")

            if logs_maker or logs_taker:
                print(f"\n  🎯 FOUND TRADES for {TEST_ADDRESS[:10]}...!")
                if logs_maker:
                    log = logs_maker[0]
                    tx = w3.eth.get_transaction(log['transactionHash'])
                    print(f"     Sample trade (maker): {log['transactionHash'].hex()}")
                    print(f"     Block: {log['blockNumber']}")
                    print(f"     From: {tx['from']}")

        except Exception as e:
            print(f"  ❌ Topic filtering error: {str(e)[:80]}")

    return max_working_range

if __name__ == "__main__":
    print("Testing eth_getLogs capabilities across different RPC nodes...")

    results = {}
    for rpc in RPC_ENDPOINTS:
        try:
            max_range = test_rpc_endpoint(rpc)
            results[rpc] = max_range
        except Exception as e:
            print(f"Error: {e}")
            results[rpc] = 0

    print(f"\n{'='*80}")
    print("SUMMARY")
    print('='*80)
    for rpc, max_range in results.items():
        if max_range:
            print(f"✓ {rpc}")
            print(f"  Max range: {max_range} blocks (~{max_range*2/60:.1f} minutes)")
        else:
            print(f"❌ {rpc}: Not working or very limited")

    best_rpc = max(results.items(), key=lambda x: x[1] if x[1] else 0)
    if best_rpc[1]:
        print(f"\n🏆 Best RPC: {best_rpc[0]}")
        print(f"   Max range: {best_rpc[1]} blocks")
        print(f"\n📊 Conclusion:")
        print(f"   - eth_getLogs WORKS with address filtering")
        print(f"   - Can filter by contract address + topics (maker/taker)")
        print(f"   - Limitation: {best_rpc[1]} block range per query")
        print(f"   - Solution: Query in chunks of {best_rpc[1]} blocks")
    else:
        print("\n❌ None of the free RPC nodes support large eth_getLogs queries")
        print("   Consider using paid RPC service (Alchemy, Infura) or Polygonscan API")
