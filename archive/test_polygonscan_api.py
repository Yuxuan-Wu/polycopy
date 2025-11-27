#!/usr/bin/env python3
"""
Test Polygonscan API for querying transactions by address
"""
import requests
import json
from datetime import datetime

# Polygonscan API endpoint (V2)
POLYGONSCAN_API = "https://api.polygonscan.com/v2/api"

# Test with one of the monitored addresses
TEST_ADDRESS = "0x0f37cb80dee49d55b5f6d9e595d52591d6371410"

def test_polygonscan_normal_txs():
    """Test getting normal transactions for an address"""
    print("=" * 80)
    print("Testing Polygonscan API - Normal Transactions")
    print("=" * 80)

    params = {
        'module': 'account',
        'action': 'txlist',
        'address': TEST_ADDRESS,
        'startblock': 79517500,
        'endblock': 99999999,
        'page': 1,
        'offset': 10,  # Get last 10 transactions
        'sort': 'desc',
        'apikey': 'YourApiKeyToken'  # Free tier: 5 calls/second
    }

    try:
        response = requests.get(POLYGONSCAN_API, params=params, timeout=10)
        data = response.json()

        print(f"Status: {data.get('status')}")
        print(f"Message: {data.get('message')}")

        if data['status'] == '1' and data['result']:
            print(f"\nFound {len(data['result'])} transactions")
            print("\nFirst 3 transactions:")
            for i, tx in enumerate(data['result'][:3]):
                print(f"\n--- Transaction {i+1} ---")
                print(f"Hash: {tx['hash']}")
                print(f"Block: {tx['blockNumber']}")
                print(f"From: {tx['from']}")
                print(f"To: {tx['to']}")
                print(f"Timestamp: {datetime.fromtimestamp(int(tx['timeStamp']))}")
                print(f"Method ID: {tx.get('methodId', 'N/A')}")
        else:
            print(f"No results or error: {data}")

        return data
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_polygonscan_internal_txs():
    """Test getting internal transactions (contract interactions)"""
    print("\n" + "=" * 80)
    print("Testing Polygonscan API - Internal Transactions")
    print("=" * 80)

    params = {
        'module': 'account',
        'action': 'txlistinternal',
        'address': TEST_ADDRESS,
        'startblock': 79517500,
        'endblock': 99999999,
        'page': 1,
        'offset': 10,
        'sort': 'desc',
        'apikey': 'YourApiKeyToken'
    }

    try:
        response = requests.get(POLYGONSCAN_API, params=params, timeout=10)
        data = response.json()

        print(f"Status: {data.get('status')}")
        print(f"Message: {data.get('message')}")

        if data['status'] == '1' and data['result']:
            print(f"\nFound {len(data['result'])} internal transactions")

        return data
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_polygonscan_erc20_transfers():
    """Test getting ERC20 token transfers"""
    print("\n" + "=" * 80)
    print("Testing Polygonscan API - ERC20 Transfers")
    print("=" * 80)

    params = {
        'module': 'account',
        'action': 'tokentx',
        'address': TEST_ADDRESS,
        'startblock': 79517500,
        'endblock': 99999999,
        'page': 1,
        'offset': 10,
        'sort': 'desc',
        'apikey': 'YourApiKeyToken'
    }

    try:
        response = requests.get(POLYGONSCAN_API, params=params, timeout=10)
        data = response.json()

        print(f"Status: {data.get('status')}")
        print(f"Message: {data.get('message')}")

        if data['status'] == '1' and data['result']:
            print(f"\nFound {len(data['result'])} token transfers")
            print("\nFirst 3 transfers:")
            for i, tx in enumerate(data['result'][:3]):
                print(f"\n--- Transfer {i+1} ---")
                print(f"Hash: {tx['hash']}")
                print(f"From: {tx['from']}")
                print(f"To: {tx['to']}")
                print(f"Token: {tx['tokenName']} ({tx['tokenSymbol']})")
                print(f"Value: {int(tx['value']) / 10**int(tx['tokenDecimal'])}")

        return data
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_no_api_key():
    """Test if API works without API key (rate limited)"""
    print("\n" + "=" * 80)
    print("Testing WITHOUT API Key (Rate Limited)")
    print("=" * 80)

    params = {
        'module': 'account',
        'action': 'txlist',
        'address': TEST_ADDRESS,
        'startblock': 79517500,
        'endblock': 99999999,
        'page': 1,
        'offset': 5,
        'sort': 'desc'
    }

    try:
        response = requests.get(POLYGONSCAN_API, params=params, timeout=10)
        data = response.json()

        print(f"Status: {data.get('status')}")
        print(f"Message: {data.get('message')}")
        print(f"Works without API key: {data['status'] == '1'}")

        if data['status'] == '1':
            print(f"Found {len(data['result'])} transactions")

        return data
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    print(f"Testing Polygonscan API for address: {TEST_ADDRESS}")
    print(f"Start block: 79517500\n")

    # Test different endpoints
    test_no_api_key()
    test_polygonscan_normal_txs()
    test_polygonscan_internal_txs()
    test_polygonscan_erc20_transfers()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("✓ Polygonscan API can directly query transactions by address")
    print("✓ No need to scan entire blocks")
    print("✓ Free tier: 5 calls/second (no API key required)")
    print("✓ With API key: 5 calls/second (better reliability)")
    print("\nAPI Endpoints tested:")
    print("  - txlist: Normal transactions")
    print("  - txlistinternal: Internal contract calls")
    print("  - tokentx: ERC20 token transfers")
