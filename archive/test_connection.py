#!/usr/bin/env python3
"""
Test script to verify RPC connections and configuration
"""
import sys
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from rpc_manager import RPCManager


def test_rpc_connection():
    """Test RPC connection"""
    print("=" * 60)
    print("Testing RPC Connections")
    print("=" * 60)

    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    rpc_endpoints = config['rpc_endpoints']
    print(f"\nTesting {len(rpc_endpoints)} RPC endpoints...")

    # Test each endpoint
    for i, endpoint in enumerate(rpc_endpoints, 1):
        print(f"\n[{i}/{len(rpc_endpoints)}] Testing: {endpoint}")
        try:
            rpc = RPCManager([endpoint], max_retry=1, retry_delay=3)
            w3 = rpc.get_web3()

            if w3.is_connected():
                chain_id = w3.eth.chain_id
                latest_block = w3.eth.block_number
                print(f"  ✓ Connected")
                print(f"  ✓ Chain ID: {chain_id}")
                print(f"  ✓ Latest Block: {latest_block:,}")
            else:
                print(f"  ✗ Failed to connect")
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)


if __name__ == '__main__':
    test_rpc_connection()
