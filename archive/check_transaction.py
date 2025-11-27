#!/usr/bin/env python3
"""
Check the details of a known trade transaction
"""
from web3 import Web3
import json

RPC_URL = "https://polygon-rpc.com"
TX_HASH = "0x1811f927f16430655d9c06e9dd391a980c9e0639815f044ab8b8be13091a9303"

w3 = Web3(Web3.HTTPProvider(RPC_URL))

print("="*80)
print(f"Analyzing transaction: {TX_HASH}")
print("="*80)

# Get transaction
tx = w3.eth.get_transaction(TX_HASH)
print(f"\nTransaction details:")
print(f"  Block: {tx['blockNumber']}")
print(f"  From: {tx['from']}")
print(f"  To: {tx['to']}")
print(f"  Value: {tx['value']}")
print(f"  Input (first 10 bytes): {tx['input'][:20]}")

# Get receipt
receipt = w3.eth.get_transaction_receipt(TX_HASH)
print(f"\nReceipt:")
print(f"  Status: {receipt['status']}")
print(f"  Logs: {len(receipt['logs'])}")

# Analyze logs
ORDER_FILLED_SIG = "0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6"
POLYMARKET_CTF = "0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e"
NEG_RISK_CTF = "0xc5d563a36ae78145c45a50134d48a1215220f80a"

print(f"\nEvent logs:")
for i, log in enumerate(receipt['logs']):
    print(f"\nLog {i}:")
    print(f"  Address: {log['address']}")
    print(f"  Topics[0]: {log['topics'][0].hex() if log['topics'] else 'None'}")

    if log['topics'] and log['topics'][0].hex() == ORDER_FILLED_SIG:
        print(f"  ✓ This is an OrderFilled event!")
        print(f"  Topic[1] (orderHash): {log['topics'][1].hex() if len(log['topics']) > 1 else 'N/A'}")
        print(f"  Topic[2] (maker): 0x{log['topics'][2].hex()[-40:] if len(log['topics']) > 2 else 'N/A'}")
        print(f"  Topic[3] (taker): 0x{log['topics'][3].hex()[-40:] if len(log['topics']) > 3 else 'N/A'}")

# Check which contract emitted the event
print(f"\n" + "="*80)
print("Contract Analysis:")
print("="*80)
print(f"Transaction to: {tx['to']}")
print(f"Polymarket CTF: {POLYMARKET_CTF}")
print(f"Neg Risk CTF:   {NEG_RISK_CTF}")

if tx['to'].lower() == POLYMARKET_CTF.lower():
    print("✓ Direct transaction to Polymarket CTF")
elif tx['to'].lower() == NEG_RISK_CTF.lower():
    print("✓ Direct transaction to Neg Risk CTF Exchange")
else:
    print(f"⚠️ Transaction to OTHER contract: {tx['to']}")
    print("This might be a router or proxy contract!")

# Check where OrderFilled event came from
for log in receipt['logs']:
    if log['topics'] and log['topics'][0].hex() == ORDER_FILLED_SIG:
        print(f"\nOrderFilled event emitted by: {log['address']}")
        if log['address'].lower() == POLYMARKET_CTF.lower():
            print("  ✓ Emitted by Polymarket CTF")
        elif log['address'].lower() == NEG_RISK_CTF.lower():
            print("  ✓ Emitted by Neg Risk CTF")
        else:
            print(f"  ⚠️ Emitted by UNKNOWN contract!")

print("\n" + "="*80)
print("DIAGNOSIS")
print("="*80)
print("If the event was emitted by Neg Risk CTF Exchange, we need to")
print("also monitor that contract address in our eth_getLogs queries!")
