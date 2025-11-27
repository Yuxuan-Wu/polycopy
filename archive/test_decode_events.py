#!/usr/bin/env python3
"""Test decoding Polymarket OrderFilled events"""
import sys
sys.path.insert(0, 'src')

from rpc_manager import RPCManager
import yaml
import json
from web3 import Web3

# Load config
with open('config.yaml') as f:
    config = yaml.safe_load(f)

rpc = RPCManager(config['rpc_endpoints'], 3, 5)
w3 = rpc.get_web3()

# Load ABI
with open('neg_risk_events_abi.json') as f:
    abi = json.load(f)

# Create contract instance
neg_risk_exchange = '0xc5d563a36ae78145c45a50134d48a1215220f80a'
contract = w3.eth.contract(address=Web3.to_checksum_address(neg_risk_exchange), abi=abi)

# Test transaction
tx_hash = '0x8d3bd1bfb6fd0da5f1a99c571b605fb3a0aa4aeddb57dc36bc6e91cb2175d1e5'
receipt = w3.eth.get_transaction_receipt(tx_hash)

print(f"Transaction: {tx_hash}\n")

# Process logs
for log in receipt['logs']:
    if log['address'].lower() == neg_risk_exchange.lower():
        try:
            # Try to decode as OrderFilled
            decoded = contract.events.OrderFilled().process_log(log)
            print("✅ OrderFilled Event Decoded:")
            print(f"   Order Hash: {decoded['args']['orderHash'].hex()}")
            print(f"   Maker: {decoded['args']['maker']}")
            print(f"   Taker: {decoded['args']['taker']}")
            print(f"   Maker Asset ID: {decoded['args']['makerAssetId']}")
            print(f"   Taker Asset ID: {decoded['args']['takerAssetId']}")
            print(f"   Maker Amount: {decoded['args']['makerAmountFilled']}")
            print(f"   Taker Amount: {decoded['args']['takerAmountFilled']}")
            print(f"   Fee: {decoded['args']['fee']}")
            
            # Calculate price
            if decoded['args']['takerAmountFilled'] > 0:
                # USDC has 6 decimals
                maker_usdc = decoded['args']['makerAmountFilled'] / 1e6
                taker_amount = decoded['args']['takerAmountFilled'] / 1e6
                price = maker_usdc / taker_amount
                print(f"   💰 Price: ${price:.4f} per token")
            print()
        except:
            try:
                # Try OrdersMatched
                decoded = contract.events.OrdersMatched().process_log(log)
                print("✅ OrdersMatched Event Decoded:")
                print(f"   Order Hash: {decoded['args']['orderHash'].hex()}")
                print(f"   Maker: {decoded['args']['maker']}")
                print(f"   Maker Asset ID: {decoded['args']['makerAssetId']}")
                print(f"   Taker Asset ID: {decoded['args']['takerAssetId']}")
                print(f"   Maker Amount: {decoded['args']['makerAmountFilled']}")
                print(f"   Taker Amount: {decoded['args']['takerAmountFilled']}")
                print()
            except:
                pass

