"""Helper module for decoding Polymarket events"""
import json
import logging
from typing import Dict, List, Optional
from web3 import Web3

logger = logging.getLogger(__name__)

# Polymarket token decimals
USDC_DECIMALS = 6  # USDC has 6 decimals
OUTCOME_TOKEN_DECIMALS = 6  # Polymarket outcome tokens typically have 6 decimals

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

                maker_amount_raw = decoded['args']['makerAmountFilled']
                taker_amount_raw = decoded['args']['takerAmountFilled']
                maker_asset_id = decoded['args']['makerAssetId']
                taker_asset_id = decoded['args']['takerAssetId']

                # Determine side and calculate price correctly
                price = None
                amount_tokens = None
                side = None
                token_id = None

                if maker_asset_id == 0:
                    # Maker selling outcome tokens for USDC
                    side = 'sell'
                    token_id = taker_asset_id

                    usdc_amount = maker_amount_raw / (10 ** USDC_DECIMALS)
                    token_amount = taker_amount_raw / (10 ** OUTCOME_TOKEN_DECIMALS)
                    amount_tokens = token_amount

                    if token_amount > 0:
                        price = usdc_amount / token_amount

                elif taker_asset_id == 0:
                    # Maker buying outcome tokens with USDC
                    side = 'buy'
                    token_id = maker_asset_id

                    usdc_amount = taker_amount_raw / (10 ** USDC_DECIMALS)
                    token_amount = maker_amount_raw / (10 ** OUTCOME_TOKEN_DECIMALS)
                    amount_tokens = token_amount

                    if token_amount > 0:
                        price = usdc_amount / token_amount

                else:
                    # Token-to-token swap
                    side = 'swap'
                    token_id = maker_asset_id
                    amount_tokens = maker_amount_raw / (10 ** OUTCOME_TOKEN_DECIMALS)
                    price = None

                trade_data = {
                    'order_hash': decoded['args']['orderHash'].hex(),
                    'maker': decoded['args']['maker'].lower(),
                    'taker': decoded['args']['taker'].lower(),
                    'token_id': hex(token_id) if token_id else None,
                    'amount': f"{amount_tokens:.6f}" if amount_tokens else "0",
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

    def decode_order_filled(self, log) -> Dict:
        """
        Decode a single OrderFilled event log

        Args:
            log: Event log from eth_getLogs

        Returns:
            Dictionary with decoded trade data
        """
        try:
            # Decode using contract ABI
            decoded = self.contract.events.OrderFilled().process_log(log)

            maker_amount_raw = decoded['args']['makerAmountFilled']
            taker_amount_raw = decoded['args']['takerAmountFilled']
            maker_asset_id = decoded['args']['makerAssetId']
            taker_asset_id = decoded['args']['takerAssetId']

            # Determine side and calculate price correctly
            # Price should always be in USDC per outcome token
            price = None
            amount_tokens = None
            side = None
            token_id = None

            if maker_asset_id == 0:
                # Maker selling outcome tokens for USDC
                # maker_amount_raw = USDC received (raw, 6 decimals)
                # taker_amount_raw = outcome tokens sold (raw, 6 decimals)
                side = 'sell'
                token_id = taker_asset_id

                # Convert amounts from raw values
                usdc_amount = maker_amount_raw / (10 ** USDC_DECIMALS)
                token_amount = taker_amount_raw / (10 ** OUTCOME_TOKEN_DECIMALS)
                amount_tokens = token_amount

                # Price = USDC per token
                if token_amount > 0:
                    price = usdc_amount / token_amount

            elif taker_asset_id == 0:
                # Maker buying outcome tokens with USDC
                # maker_amount_raw = outcome tokens bought (raw, 6 decimals)
                # taker_amount_raw = USDC paid (raw, 6 decimals)
                side = 'buy'
                token_id = maker_asset_id

                # Convert amounts from raw values
                usdc_amount = taker_amount_raw / (10 ** USDC_DECIMALS)
                token_amount = maker_amount_raw / (10 ** OUTCOME_TOKEN_DECIMALS)
                amount_tokens = token_amount

                # Price = USDC per token
                if token_amount > 0:
                    price = usdc_amount / token_amount

            else:
                # Token-to-token swap (rare)
                side = 'swap'
                token_id = maker_asset_id
                amount_tokens = maker_amount_raw / (10 ** OUTCOME_TOKEN_DECIMALS)
                price = None  # Can't determine price without knowing which is USDC

            trade_data = {
                'order_hash': decoded['args']['orderHash'].hex(),
                'maker': decoded['args']['maker'].lower(),
                'taker': decoded['args']['taker'].lower(),
                'token_id': hex(token_id) if token_id else None,
                'amount': f"{amount_tokens:.6f}" if amount_tokens else "0",
                'price': f"{price:.6f}" if price else None,
                'side': side,
                'fee': str(decoded['args']['fee']),
                'maker_asset_id': str(maker_asset_id),
                'taker_asset_id': str(taker_asset_id)
            }

            return trade_data

        except Exception as e:
            logger.warning(f"Failed to decode OrderFilled event: {e}")
            return {}
