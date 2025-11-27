"""Helper module for decoding Polymarket events"""
import json
import logging
from typing import Dict, List, Optional
from web3 import Web3

logger = logging.getLogger(__name__)

# Minimal ABI for NegRisk CTF Exchange events
NEG_RISK_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "orderHash", "type": "bytes32"},
            {"indexed": True, "name": "maker", "type": "address"},
            {"indexed": True, "name": "taker", "type": "address"},
            {"indexed": False, "name": "makerAssetId", "type": "uint256"},
            {"indexed": False, "name": "takerAssetId", "type": "uint256"},
            {"indexed": False, "name": "makerAmountFilled", "type": "uint256"},
            {"indexed": False, "name": "takerAmountFilled", "type": "uint256"},
            {"indexed": False, "name": "fee", "type": "uint256"}
        ],
        "name": "OrderFilled",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "orderHash", "type": "bytes32"},
            {"indexed": True, "name": "maker", "type": "address"},
            {"indexed": False, "name": "makerAssetId", "type": "uint256"},
            {"indexed": False, "name": "takerAssetId", "type": "uint256"},
            {"indexed": False, "name": "makerAmountFilled", "type": "uint256"},
            {"indexed": False, "name": "takerAmountFilled", "type": "uint256"}
        ],
        "name": "OrdersMatched",
        "type": "event"
    }
]

class EventDecoder:
    """Decode Polymarket CTF Exchange events"""
    
    def __init__(self, w3: Web3, neg_risk_exchange: str):
        """
        Initialize event decoder
        
        Args:
            w3: Web3 instance
            neg_risk_exchange: NegRisk CTF Exchange contract address
        """
        self.w3 = w3
        self.neg_risk_exchange = neg_risk_exchange.lower()
        self.contract = w3.eth.contract(
            address=Web3.to_checksum_address(neg_risk_exchange),
            abi=NEG_RISK_ABI
        )
    
    def decode_trade_events(self, receipt) -> List[Dict]:
        """
        Decode OrderFilled events from transaction receipt
        
        Args:
            receipt: Transaction receipt
            
        Returns:
            List of decoded trade data dictionaries
        """
        trades = []
        
        for log in receipt.get('logs', []):
            if log['address'].lower() != self.neg_risk_exchange:
                continue
                
            try:
                # Try to decode as OrderFilled
                decoded = self.contract.events.OrderFilled().process_log(log)
                
                maker_amount = decoded['args']['makerAmountFilled']
                taker_amount = decoded['args']['takerAmountFilled']
                
                # Calculate price (USDC has 6 decimals)
                price = None
                if taker_amount > 0:
                    price = maker_amount / taker_amount
                
                # Determine side based on asset IDs
                # If makerAssetId is 0, maker is selling outcome tokens for USDC (sell)
                # If takerAssetId is 0, taker is selling outcome tokens for USDC (maker is buying)
                maker_asset_id = decoded['args']['makerAssetId']
                taker_asset_id = decoded['args']['takerAssetId']
                
                if maker_asset_id == 0:
                    side = 'sell'  # Maker selling outcome tokens for USDC
                    token_id = taker_asset_id
                elif taker_asset_id == 0:
                    side = 'buy'   # Maker buying outcome tokens with USDC
                    token_id = maker_asset_id
                else:
                    side = 'swap'  # Token-to-token swap
                    token_id = maker_asset_id
                
                trade_data = {
                    'order_hash': decoded['args']['orderHash'].hex(),
                    'maker': decoded['args']['maker'].lower(),
                    'taker': decoded['args']['taker'].lower(),
                    'token_id': hex(token_id),
                    'amount': str(taker_amount),
                    'price': f"{price:.6f}" if price else None,
                    'side': side,
                    'fee': str(decoded['args']['fee']),
                    'maker_asset_id': str(maker_asset_id),
                    'taker_asset_id': str(taker_asset_id)
                }
                
                trades.append(trade_data)
                
            except Exception as e:
                # Not an OrderFilled event or couldn't decode
                logger.debug(f"Could not decode log as OrderFilled: {e}")
                continue
        
        return trades
