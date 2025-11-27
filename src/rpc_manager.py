"""
RPC Manager with multiple endpoints and automatic failover
Optimized for Infura + eth_getLogs
"""
import logging
import os
import time
from typing import List, Optional, Dict, Any
from web3 import Web3
from web3.exceptions import Web3Exception
from web3.middleware import ExtraDataToPOAMiddleware

logger = logging.getLogger(__name__)


class RPCManager:
    """Manages multiple RPC endpoints with automatic failover"""

    def __init__(self, rpc_endpoints: List[str], max_retry: int = 3, retry_delay: int = 5):
        """
        Initialize RPC Manager

        Args:
            rpc_endpoints: List of RPC endpoint URLs (can include "infura")
            max_retry: Maximum number of retries per endpoint
            retry_delay: Delay between retries in seconds
        """
        self.rpc_endpoints = self._process_endpoints(rpc_endpoints)
        self.max_retry = max_retry
        self.retry_delay = retry_delay
        self.current_index = 0
        self.w3: Optional[Web3] = None

        # Track max block range for each endpoint
        self.max_ranges = [100, 50, 50, 50, 50]  # Infura=100, others=50

        self._connect()

    def _process_endpoints(self, endpoints: List[str]) -> List[str]:
        """
        Process endpoint list, replace "infura" with actual URL from env

        Args:
            endpoints: List of endpoint URLs or "infura" placeholder

        Returns:
            List of processed endpoint URLs
        """
        processed = []
        for endpoint in endpoints:
            if endpoint.lower() == "infura":
                api_key = os.getenv('INFURA_API_KEY')
                if not api_key:
                    logger.warning("INFURA_API_KEY not found in environment, skipping Infura")
                    continue
                infura_url = f"https://polygon-mainnet.infura.io/v3/{api_key}"
                processed.append(infura_url)
                logger.info("Using Infura RPC (from INFURA_API_KEY)")
            else:
                processed.append(endpoint)

        if not processed:
            raise ValueError("No valid RPC endpoints available")

        return processed

    def _connect(self) -> bool:
        """
        Connect to an RPC endpoint

        Returns:
            bool: True if connection successful
        """
        for _ in range(len(self.rpc_endpoints)):
            endpoint = self.rpc_endpoints[self.current_index]
            try:
                # Mask API key in logs
                display_endpoint = self._mask_api_key(endpoint)
                logger.info(f"Attempting to connect to RPC: {display_endpoint}")

                self.w3 = Web3(Web3.HTTPProvider(endpoint, request_kwargs={'timeout': 30}))

                # Inject POA middleware for Polygon compatibility
                self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

                # Test connection
                if self.w3.is_connected():
                    chain_id = self.w3.eth.chain_id
                    logger.info(f"✓ Connected to RPC: {display_endpoint} (Chain ID: {chain_id})")
                    return True
                else:
                    logger.warning(f"✗ Failed to connect to RPC: {display_endpoint}")
            except Exception as e:
                display_endpoint = self._mask_api_key(endpoint)
                logger.warning(f"✗ Error connecting to RPC {display_endpoint}: {str(e)}")

            # Rotate to next endpoint
            self._rotate_endpoint()

        logger.error("Failed to connect to any RPC endpoint")
        return False

    def _mask_api_key(self, url: str) -> str:
        """Mask API key in URL for logging"""
        if 'infura.io/v3/' in url:
            parts = url.split('/v3/')
            if len(parts) == 2:
                return f"{parts[0]}/v3/***{parts[1][-4:]}"
        return url

    def _rotate_endpoint(self):
        """Rotate to the next RPC endpoint"""
        self.current_index = (self.current_index + 1) % len(self.rpc_endpoints)
        logger.info(f"Rotating to RPC endpoint {self.current_index + 1}/{len(self.rpc_endpoints)}")

    def get_max_block_range(self) -> int:
        """Get maximum block range for current endpoint"""
        if self.current_index < len(self.max_ranges):
            return self.max_ranges[self.current_index]
        return 50  # Default for unknown endpoints

    def execute_with_retry(self, func, *args, **kwargs):
        """
        Execute a function with retry logic and automatic failover

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Result of the function execution
        """
        last_exception = None

        for attempt in range(self.max_retry):
            try:
                # Only check connection if w3 is None (first call)
                if not self.w3:
                    if not self._connect():
                        raise ConnectionError("Failed to connect to RPC")

                result = func(*args, **kwargs)
                return result

            except (Web3Exception, ConnectionError, Exception) as e:
                last_exception = e
                error_msg = str(e)

                # Check if it's a rate limit error - switch back to Infura immediately
                if '429' in error_msg or 'Too many requests' in error_msg or 'rate limit' in error_msg.lower():
                    logger.warning(f"⚠️ Rate limit detected on attempt {attempt + 1}/{self.max_retry}: {error_msg[:150]}")

                    # If not on Infura (endpoint 0), switch to it immediately
                    if self.current_index != 0:
                        logger.info("Switching back to Infura due to rate limit on free RPC...")
                        self.current_index = 0
                        self._connect()
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        # Already on Infura and hit rate limit, wait longer
                        logger.warning("Rate limit on Infura, waiting...")
                        time.sleep(self.retry_delay * 3)
                        continue

                # For other errors, log and retry on same endpoint
                logger.warning(f"Attempt {attempt + 1}/{self.max_retry} failed: {error_msg[:150]}")

                if attempt < self.max_retry - 1:
                    time.sleep(self.retry_delay)

        # All retries exhausted on current endpoint
        if len(self.rpc_endpoints) > 1:
            logger.warning(f"All {self.max_retry} retries failed on current endpoint, trying next RPC...")
            self._rotate_endpoint()
            self._connect()

            # Try once on new endpoint
            try:
                result = func(*args, **kwargs)
                logger.info("✓ Successfully executed on fallback RPC endpoint")
                return result
            except Exception as e:
                logger.error(f"Fallback endpoint also failed: {str(e)[:200]}")
                last_exception = e

        # All retries and fallback exhausted
        logger.error(f"All retry attempts exhausted. Last error: {str(last_exception)[:200]}")
        raise last_exception

    def get_web3(self) -> Web3:
        """
        Get the current Web3 instance

        Returns:
            Web3: Current Web3 instance
        """
        if not self.w3:
            self._connect()
        return self.w3

    def get_latest_block(self) -> int:
        """
        Get the latest block number with retry

        Returns:
            int: Latest block number
        """
        return self.execute_with_retry(lambda: self.w3.eth.block_number)

    def get_block(self, block_number: int):
        """
        Get block by number with retry

        Args:
            block_number: Block number to fetch

        Returns:
            Block data
        """
        return self.execute_with_retry(lambda: self.w3.eth.get_block(block_number, full_transactions=True))

    def get_transaction(self, tx_hash: str):
        """
        Get transaction by hash with retry

        Args:
            tx_hash: Transaction hash

        Returns:
            Transaction data
        """
        return self.execute_with_retry(lambda: self.w3.eth.get_transaction(tx_hash))

    def get_transaction_receipt(self, tx_hash: str):
        """
        Get transaction receipt with retry

        Args:
            tx_hash: Transaction hash

        Returns:
            Transaction receipt
        """
        return self.execute_with_retry(lambda: self.w3.eth.get_transaction_receipt(tx_hash))

    def get_logs(self, filter_params: Dict[str, Any]) -> List:
        """
        Get logs using eth_getLogs with retry

        Args:
            filter_params: Filter parameters for eth_getLogs

        Returns:
            List of log entries
        """
        def _get_logs():
            return self.w3.eth.get_logs(filter_params)

        return self.execute_with_retry(_get_logs)
