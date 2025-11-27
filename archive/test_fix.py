#!/usr/bin/env python3
"""Test the updated monitoring logic"""
import sys
sys.path.insert(0, 'src')

from rpc_manager import RPCManager
from monitor import PolymarketMonitor
import yaml

# Load config
with open('config.yaml') as f:
    config = yaml.safe_load(f)

# Initialize RPC
rpc = RPCManager(config['rpc_endpoints'], 3, 5)
w3 = rpc.get_web3()

# Create monitor instance
class MockDB:
    def insert_trade(self, data):
        print(f"\n✅ TRADE WOULD BE CAPTURED!")
        print(f"   TX Hash: {data['tx_hash'][:20]}...")
        print(f"   Block: {data['block_number']}")
        print(f"   From: {data['from_address']}")
        print(f"   Method: {data['method']}")
        return True
    
    def get_trade_count(self):
        return 0
    
    def get_latest_block(self):
        return None

monitor = PolymarketMonitor(
    rpc_manager=rpc,
    database_manager=MockDB(),
    monitored_addresses=config['monitored_addresses'],
    polymarket_contract=config['polymarket_ctf_exchange'],
    poll_interval=12
)

# Test with a known transaction
test_txs = [
    '0x8d3bd1bfb6fd0da5f1a99c571b605fb3a0aa4aeddb57dc36bc6e91cb2175d1e5',  # Block 79517527
    '0xe416c6596d67120f0ef3752baa3552e05e80c1b193e80050a03023374a9b5ff4',  # Block 79523365
]

for tx_hash in test_txs:
    print(f"\n{'='*60}")
    print(f"Testing: {tx_hash}")
    print(f"{'='*60}")
    
    tx = w3.eth.get_transaction(tx_hash)
    block = w3.eth.get_block(tx['blockNumber'])
    
    print(f"From: {tx['from'].lower()}")
    print(f"To: {tx['to'].lower() if tx['to'] else 'None'}")
    print(f"Block: {tx['blockNumber']}")
    
    # Test the processing
    monitor._process_transaction(tx, block)
    
print(f"\n{'='*60}")
print("Test complete!")
print(f"{'='*60}")
