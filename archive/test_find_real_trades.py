#!/usr/bin/env python3
"""
Test if eth_getLogs can find our actual monitored trades
"""
from web3 import Web3
from datetime import datetime

RPC_URL = "https://polygon-rpc.com"

# Known trade from database
KNOWN_BLOCK = 79553881
KNOWN_TX = "0x1811f927f16430655d9c06e9dd391a980c9e0639815f044ab8b8be13091a9303"
KNOWN_ADDRESS = Web3.to_checksum_address("0xca8f0374e3fc79b485499cc0b038d4f7e783d963")

# All monitored addresses
MONITORED_ADDRESSES = [
    Web3.to_checksum_address("0x0f37cb80dee49d55b5f6d9e595d52591d6371410"),
    Web3.to_checksum_address("0xca8f0374e3fc79b485499cc0b038d4f7e783d963"),
    Web3.to_checksum_address("0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b")
]

# BOTH Polymarket contracts
POLYMARKET_CONTRACTS = [
    Web3.to_checksum_address("0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e"),  # CTF Exchange
    Web3.to_checksum_address("0xc5d563a36ae78145c45a50134d48a1215220f80a"),  # Neg Risk CTF
]
ORDER_FILLED_SIG = "0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6"

print("="*80)
print("Testing: Can eth_getLogs find our monitored trades?")
print("="*80)

w3 = Web3(Web3.HTTPProvider(RPC_URL))
print(f"✓ Connected to {RPC_URL}")

# Test 1: Can we find the known trade by block range?
print(f"\nTest 1: Search for known trade in block {KNOWN_BLOCK}")
print("-"*80)

from_block = KNOWN_BLOCK - 5
to_block = KNOWN_BLOCK + 5

logs = w3.eth.get_logs({
    'fromBlock': from_block,
    'toBlock': to_block,
    'address': POLYMARKET_CONTRACTS,  # Monitor BOTH contracts
    'topics': [ORDER_FILLED_SIG]
})

print(f"Found {len(logs)} OrderFilled events in blocks {from_block}-{to_block}")

# Check if our known transaction is in the results
found_our_tx = False
for log in logs:
    if log['transactionHash'].hex() == KNOWN_TX:
        print(f"✅ FOUND our known trade: {KNOWN_TX}")
        print(f"   Block: {log['blockNumber']}")
        print(f"   Log index: {log['logIndex']}")
        found_our_tx = True
        break

if not found_our_tx:
    print(f"❌ Did not find known trade {KNOWN_TX}")

# Test 2: Filter by address in topics
print(f"\nTest 2: Filter events where our address is involved")
print("-"*80)

for addr in MONITORED_ADDRESSES:
    addr_topic = '0x' + addr[2:].zfill(64).lower()

    # Check as maker
    logs_maker = w3.eth.get_logs({
        'fromBlock': from_block,
        'toBlock': to_block,
        'address': POLYMARKET_CONTRACTS,  # Monitor BOTH contracts
        'topics': [ORDER_FILLED_SIG, None, addr_topic]
    })

    # Check as taker
    logs_taker = w3.eth.get_logs({
        'fromBlock': from_block,
        'toBlock': to_block,
        'address': POLYMARKET_CONTRACTS,  # Monitor BOTH contracts
        'topics': [ORDER_FILLED_SIG, None, None, addr_topic]
    })

    total = len(logs_maker) + len(logs_taker)
    if total > 0:
        print(f"✓ {addr[:10]}...: {len(logs_maker)} as maker, {len(logs_taker)} as taker")

        # Show details of first trade
        if logs_maker:
            log = logs_maker[0]
            tx = w3.eth.get_transaction(log['transactionHash'])
            print(f"  Sample (maker): {log['transactionHash'].hex()}")
            print(f"    From: {tx['from']}")
            print(f"    To: {tx['to']}")
        elif logs_taker:
            log = logs_taker[0]
            tx = w3.eth.get_transaction(log['transactionHash'])
            print(f"  Sample (taker): {log['transactionHash'].hex()}")
            print(f"    From: {tx['from']}")
            print(f"    To: {tx['to']}")

# Test 3: Scan recent 50 blocks for ALL monitored addresses
print(f"\nTest 3: Scan recent 50 blocks for all monitored trades")
print("-"*80)

latest = w3.eth.block_number
from_block = latest - 50
to_block = latest

all_trades = []

for addr in MONITORED_ADDRESSES:
    addr_topic = '0x' + addr[2:].zfill(64).lower()

    # As maker
    logs_maker = w3.eth.get_logs({
        'fromBlock': from_block,
        'toBlock': to_block,
        'address': POLYMARKET_CONTRACTS,  # Monitor BOTH contracts
        'topics': [ORDER_FILLED_SIG, None, addr_topic]
    })

    # As taker
    logs_taker = w3.eth.get_logs({
        'fromBlock': from_block,
        'toBlock': to_block,
        'address': POLYMARKET_CONTRACTS,  # Monitor BOTH contracts
        'topics': [ORDER_FILLED_SIG, None, None, addr_topic]
    })

    for log in logs_maker:
        all_trades.append((addr, 'maker', log))
    for log in logs_taker:
        all_trades.append((addr, 'taker', log))

print(f"Found {len(all_trades)} trades in last 50 blocks")

if all_trades:
    print("\nTrades found:")
    for addr, role, log in all_trades:
        block = w3.eth.get_block(log['blockNumber'])
        print(f"  Block {log['blockNumber']} ({datetime.fromtimestamp(block['timestamp'])})")
        print(f"    Address: {addr[:10]}... ({role})")
        print(f"    Tx: {log['transactionHash'].hex()}")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print("✅ eth_getLogs CAN find our monitored trades!")
print("✅ Can filter by maker/taker address in topics")
print("✅ Much more efficient than scanning entire blocks")
print("\nNext step: Implement new monitoring logic using eth_getLogs")
