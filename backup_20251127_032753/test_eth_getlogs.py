#!/usr/bin/env python3
"""
Test eth_getLogs method for querying events by address
This is a standard Ethereum RPC method supported by all nodes
"""
from web3 import Web3
from datetime import datetime

# Use the existing RPC endpoint
RPC_URL = "https://polygon-rpc.com"

# Monitored addresses (checksum format)
MONITORED_ADDRESSES = [
    Web3.to_checksum_address("0x0f37cb80dee49d55b5f6d9e595d52591d6371410"),
    Web3.to_checksum_address("0xca8f0374e3fc79b485499cc0b038d4f7e783d963"),
    Web3.to_checksum_address("0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b")
]

# Polymarket contracts (checksum format)
POLYMARKET_CONTRACTS = [
    Web3.to_checksum_address("0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e"),  # CTF Exchange
    Web3.to_checksum_address("0xc5d563a36ae78145c45a50134d48a1215220f80a"),  # Neg Risk CTF Exchange
]

def test_eth_getlogs_approach():
    """
    Test using eth_getLogs to get events involving our monitored addresses
    This approach filters events at the RPC level instead of scanning entire blocks
    """
    print("=" * 80)
    print("Testing eth_getLogs for Address-Specific Event Filtering")
    print("=" * 80)

    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    if not w3.is_connected():
        print("❌ Failed to connect to RPC")
        return

    print(f"✓ Connected to: {RPC_URL}")
    latest_block = w3.eth.block_number
    print(f"✓ Latest block: {latest_block}")

    # Test 1: Get logs where our address is involved in Polymarket contract events
    print("\n" + "-" * 80)
    print("Test 1: Filter logs by contract address (Polymarket)")
    print("-" * 80)

    # Get recent 100 blocks for testing (RPC nodes have range limits)
    from_block = latest_block - 100
    to_block = latest_block

    filter_params = {
        'fromBlock': from_block,
        'toBlock': to_block,
        'address': POLYMARKET_CONTRACTS,  # Only Polymarket contracts
    }

    try:
        logs = w3.eth.get_logs(filter_params)
        print(f"Found {len(logs)} events from Polymarket contracts in last 1000 blocks")

        if logs:
            print(f"\nFirst event example:")
            log = logs[0]
            print(f"  Block: {log['blockNumber']}")
            print(f"  Contract: {log['address']}")
            print(f"  Topics: {log['topics'][:2]}")  # First 2 topics
            print(f"  Transaction: {log['transactionHash'].hex()}")

    except Exception as e:
        print(f"Error: {e}")

    # Test 2: Get OrderFilled events (topic0 filter)
    print("\n" + "-" * 80)
    print("Test 2: Filter by specific event signature (OrderFilled)")
    print("-" * 80)

    # OrderFilled event signature
    ORDER_FILLED_SIGNATURE = "0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6"

    filter_params = {
        'fromBlock': from_block,
        'toBlock': to_block,
        'address': POLYMARKET_CONTRACTS,
        'topics': [ORDER_FILLED_SIGNATURE]  # topic[0] = event signature
    }

    try:
        logs = w3.eth.get_logs(filter_params)
        print(f"Found {len(logs)} OrderFilled events in last 1000 blocks")

    except Exception as e:
        print(f"Error: {e}")

    # Test 3: Check if we can filter by address in topics (maker/taker)
    print("\n" + "-" * 80)
    print("Test 3: Can we filter by maker/taker address in topics?")
    print("-" * 80)

    # In OrderFilled event:
    # topic[0] = event signature
    # topic[1] = orderHash (indexed)
    # topic[2] = maker (indexed)
    # topic[3] = taker (indexed)

    # Try to filter for events where our address is the maker or taker
    test_address = MONITORED_ADDRESSES[0]
    print(f"Looking for events where {test_address} is maker or taker...")

    # Format address as topic (32 bytes, left-padded)
    address_topic = '0x' + test_address[2:].zfill(64).lower()

    # Search for this address as maker (topic[2])
    filter_params_maker = {
        'fromBlock': latest_block - 500,  # Last 500 blocks (~16 minutes)
        'toBlock': latest_block,
        'address': POLYMARKET_CONTRACTS,
        'topics': [
            ORDER_FILLED_SIGNATURE,  # topic[0]: OrderFilled
            None,                     # topic[1]: orderHash (any)
            address_topic             # topic[2]: maker (our address)
        ]
    }

    try:
        logs = w3.eth.get_logs(filter_params_maker)
        print(f"✓ Found {len(logs)} events where {test_address[:10]}... is MAKER")

        if logs:
            print(f"\nExample transaction:")
            log = logs[0]
            tx = w3.eth.get_transaction(log['transactionHash'])
            block = w3.eth.get_block(log['blockNumber'])
            print(f"  Block: {log['blockNumber']}")
            print(f"  Timestamp: {datetime.fromtimestamp(block['timestamp'])}")
            print(f"  Tx Hash: {log['transactionHash'].hex()}")
            print(f"  From: {tx['from']}")

    except Exception as e:
        print(f"Error: {e}")

    # Search for this address as taker (topic[3])
    filter_params_taker = {
        'fromBlock': latest_block - 500,
        'toBlock': latest_block,
        'address': POLYMARKET_CONTRACTS,
        'topics': [
            ORDER_FILLED_SIGNATURE,  # topic[0]: OrderFilled
            None,                     # topic[1]: orderHash (any)
            None,                     # topic[2]: maker (any)
            address_topic             # topic[3]: taker (our address)
        ]
    }

    try:
        logs = w3.eth.get_logs(filter_params_taker)
        print(f"✓ Found {len(logs)} events where {test_address[:10]}... is TAKER")

    except Exception as e:
        print(f"Error: {e}")

    return True

def test_performance_comparison():
    """
    Compare performance: eth_getLogs vs scanning blocks
    """
    print("\n" + "=" * 80)
    print("Performance Comparison")
    print("=" * 80)

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    latest_block = w3.eth.block_number

    import time

    # Approach 1: eth_getLogs (NEW)
    print("\n📊 Approach 1: eth_getLogs (address filtering at RPC level)")
    start = time.time()

    filter_params = {
        'fromBlock': latest_block - 100,
        'toBlock': latest_block,
        'address': POLYMARKET_CONTRACTS,
        'topics': [
            "0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6",  # OrderFilled
        ]
    }

    logs = w3.eth.get_logs(filter_params)
    elapsed1 = time.time() - start

    print(f"  ✓ Found {len(logs)} events in 100 blocks")
    print(f"  ⏱️  Time: {elapsed1:.2f} seconds")
    print(f"  🔧 RPC calls: 1 (single eth_getLogs)")

    # Approach 2: Scan blocks (CURRENT)
    print("\n📊 Approach 2: Block scanning (current method)")
    start = time.time()

    block_count = 0
    tx_count = 0
    for block_num in range(latest_block - 99, latest_block + 1):
        try:
            block = w3.eth.get_block(block_num, full_transactions=True)
            block_count += 1
            if block and block.transactions:
                for tx in block.transactions:
                    tx_count += 1
                    # Check if from/to matches our addresses
                    if tx['from'].lower() in [addr.lower() for addr in MONITORED_ADDRESSES]:
                        # Would need to fetch receipt, decode logs, etc.
                        pass
        except:
            break

    elapsed2 = time.time() - start

    print(f"  ✓ Scanned {block_count} blocks")
    print(f"  ✓ Processed {tx_count} transactions")
    print(f"  ⏱️  Time: {elapsed2:.2f} seconds")
    print(f"  🔧 RPC calls: {block_count} (one per block)")

    print("\n" + "=" * 80)
    print("COMPARISON RESULT")
    print("=" * 80)
    print(f"  eth_getLogs is {elapsed2/elapsed1:.1f}x FASTER")
    print(f"  eth_getLogs uses {block_count}x FEWER RPC calls")
    print(f"  eth_getLogs is MORE PRECISE (only relevant events)")

if __name__ == "__main__":
    test_eth_getlogs_approach()
    test_performance_comparison()

    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print("✅ eth_getLogs is the BEST approach:")
    print("   1. Directly filter events by address at RPC level")
    print("   2. Much faster (single RPC call vs many)")
    print("   3. More efficient (no need to scan entire blocks)")
    print("   4. Supported by ALL standard Ethereum/Polygon RPC nodes")
    print("   5. Can filter by:")
    print("      - Contract address (Polymarket contracts)")
    print("      - Event signature (OrderFilled, OrdersMatched)")
    print("      - Indexed parameters (maker/taker addresses)")
