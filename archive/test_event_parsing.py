#!/usr/bin/env python3
"""Test parsing Polymarket trade events from transaction logs"""
import sys
sys.path.insert(0, 'src')

from rpc_manager import RPCManager
import yaml
from web3 import Web3

# Load config
with open('config.yaml') as f:
    config = yaml.safe_load(f)

rpc = RPCManager(config['rpc_endpoints'], 3, 5)
w3 = rpc.get_web3()

# Test with a known transaction
tx_hash = '0x8d3bd1bfb6fd0da5f1a99c571b605fb3a0aa4aeddb57dc36bc6e91cb2175d1e5'
receipt = w3.eth.get_transaction_receipt(tx_hash)

print(f"Transaction: {tx_hash}")
print(f"Total logs: {len(receipt['logs'])}\n")

# NegRisk CTF Exchange contract
neg_risk_exchange = '0xc5d563a36ae78145c45a50134d48a1215220f80a'

# Event signatures (keccak256 of event signature)
# OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256,uint256,uint256)
ORDER_FILLED_TOPIC = '0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6'

# OrdersMatched(bytes32,address,uint256,uint256,uint256)
ORDERS_MATCHED_TOPIC = '0x63bf4d16b7fa898ef4c4e6bae7c6f9e05ec3aa35684f52b7c5ba62113db00c83'

for i, log in enumerate(receipt['logs']):
    log_address = log['address'].lower()
    
    if log_address == neg_risk_exchange.lower():
        print(f"Log {i} from NegRisk CTF Exchange:")
        print(f"  Topics: {len(log['topics'])}")
        
        if len(log['topics']) > 0:
            topic0 = log['topics'][0].hex()
            print(f"  Event signature: {topic0}")
            
            if topic0 == ORDER_FILLED_TOPIC:
                print(f"  ✅ ORDER FILLED EVENT!")
                print(f"  Data length: {len(log['data'].hex())} chars")
                
                # Decode the data manually
                data_hex = log['data'].hex()
                if len(data_hex) >= 2:
                    data_hex = data_hex[2:] if data_hex.startswith('0x') else data_hex
                    
                    # Each parameter is 32 bytes (64 hex chars)
                    # OrderFilled has: makerAssetId, takerAssetId, makerAmountFilled, takerAmountFilled, fee
                    chunks = [data_hex[i:i+64] for i in range(0, len(data_hex), 64)]
                    print(f"  Data chunks: {len(chunks)}")
                    
                    if len(chunks) >= 4:
                        maker_amount = int(chunks[2], 16) if chunks[2] else 0
                        taker_amount = int(chunks[3], 16) if chunks[3] else 0
                        
                        print(f"  Maker amount: {maker_amount}")
                        print(f"  Taker amount: {taker_amount}")
                        
                        if taker_amount > 0:
                            price = maker_amount / taker_amount
                            print(f"  Price: {price:.6f}")
                
            elif topic0 == ORDERS_MATCHED_TOPIC:
                print(f"  ✅ ORDERS MATCHED EVENT!")
                
        print()

