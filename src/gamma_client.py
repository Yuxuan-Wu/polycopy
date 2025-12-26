"""
Polymarket Gamma API Client
Fetches market metadata from Gamma API
"""
import logging
import httpx
import json
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class GammaClient:
    """Client for Polymarket Gamma Markets API"""

    BASE_URL = "https://gamma-api.polymarket.com"
    MARKETS_ENDPOINT = f"{BASE_URL}/markets"

    def __init__(self, timeout: int = 30):
        """
        Initialize Gamma API client

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        # Explicitly bypass proxy - Gamma API should always go direct
        # This prevents issues when HTTP_PROXY is set for copy trading
        # Use mounts to force direct transport without proxy
        self.client = httpx.Client(
            timeout=timeout,
            mounts={'all://': httpx.HTTPTransport()}  # Force direct connection
        )
        logger.info("Gamma API client initialized (direct connection)")

    def get_market_by_token_id(self, token_id: str) -> Optional[Dict]:
        """
        Get market information by CLOB token ID

        Args:
            token_id: Hexadecimal token ID (e.g., 0x123...)

        Returns:
            Market data dictionary or None if not found
        """
        try:
            # Convert hex token_id to decimal
            token_id_int = int(token_id, 16)

            # Query Gamma API
            params = {
                'clob_token_ids': str(token_id_int),
                'limit': 1
            }

            logger.debug(f"Querying Gamma API for token_id: {token_id} (decimal: {token_id_int})")
            response = self.client.get(self.MARKETS_ENDPOINT, params=params)
            response.raise_for_status()

            markets = response.json()
            if markets and len(markets) > 0:
                market = markets[0]
                logger.info(f"Found market: {market.get('question', 'N/A')[:50]}...")
                return self._parse_market(market, token_id)
            else:
                logger.warning(f"No market found for token_id: {token_id}")
                return None

        except Exception as e:
            logger.error(f"Error fetching market for token_id {token_id}: {e}")
            return None

    def get_market_by_condition_id(self, condition_id: str) -> Optional[Dict]:
        """
        Get market information by condition ID

        Args:
            condition_id: Condition ID (e.g., 0x123...)

        Returns:
            Market data dictionary or None if not found
        """
        try:
            params = {
                'condition_ids': condition_id,
                'limit': 10  # May return multiple markets for same condition
            }

            logger.debug(f"Querying Gamma API for condition_id: {condition_id}")
            response = self.client.get(self.MARKETS_ENDPOINT, params=params)
            response.raise_for_status()

            markets = response.json()
            if markets and len(markets) > 0:
                # Return the first active market
                for market in markets:
                    if market.get('active'):
                        return self._parse_market(market)
                # If no active market, return first one
                return self._parse_market(markets[0])
            else:
                logger.warning(f"No market found for condition_id: {condition_id}")
                return None

        except Exception as e:
            logger.error(f"Error fetching market for condition_id {condition_id}: {e}")
            return None

    def _parse_market(self, market_data: Dict, specific_token_id: Optional[str] = None) -> Dict:
        """
        Parse and extract relevant market information

        Args:
            market_data: Raw market data from Gamma API
            specific_token_id: Specific token ID to determine outcome

        Returns:
            Parsed market dictionary
        """
        try:
            # Parse outcomes and token IDs
            outcomes = json.loads(market_data.get('outcomes', '[]'))
            clob_token_ids_str = market_data.get('clobTokenIds', '[]')
            clob_token_ids = json.loads(clob_token_ids_str) if clob_token_ids_str else []

            # Parse outcome prices
            outcome_prices = json.loads(market_data.get('outcomePrices', '[]'))

            # Determine which outcome this token_id represents
            outcome_index = None
            outcome_name = None
            if specific_token_id:
                token_id_int = int(specific_token_id, 16)
                try:
                    outcome_index = clob_token_ids.index(str(token_id_int))
                    if outcome_index < len(outcomes):
                        outcome_name = outcomes[outcome_index]
                except (ValueError, IndexError):
                    logger.warning(f"Could not determine outcome for token_id: {specific_token_id}")

            # Get event data
            events = market_data.get('events', [])
            event_slug = events[0].get('slug') if events else None
            event_title = events[0].get('title') if events else market_data.get('question')

            parsed = {
                'market_id': str(market_data.get('id')),
                'condition_id': market_data.get('conditionId'),
                'question': market_data.get('question'),
                'slug': market_data.get('slug'),
                'description': market_data.get('description', ''),
                'outcomes': outcomes,
                'outcome_prices': outcome_prices,
                'clob_token_ids': clob_token_ids,
                'outcome_index': outcome_index,
                'outcome_name': outcome_name,
                'category': market_data.get('category', ''),
                'image': market_data.get('image', ''),
                'icon': market_data.get('icon', ''),
                'start_date': market_data.get('startDate'),
                'end_date': market_data.get('endDate'),
                'volume': float(market_data.get('volumeNum', 0)),
                'liquidity': float(market_data.get('liquidityNum', 0)),
                'active': market_data.get('active', False),
                'closed': market_data.get('closed', False),
                'event_slug': event_slug,
                'event_title': event_title,
                'neg_risk': market_data.get('negRisk', False),
                'market_type': market_data.get('marketType', 'normal'),
            }

            return parsed

        except Exception as e:
            logger.error(f"Error parsing market data: {e}")
            return {}

    def batch_get_markets(self, token_ids: List[str]) -> Dict[str, Dict]:
        """
        Batch fetch market data for multiple token IDs

        Args:
            token_ids: List of hexadecimal token IDs

        Returns:
            Dictionary mapping token_id -> market data
        """
        results = {}

        # Convert all token IDs to decimal
        token_id_decimals = []
        token_id_map = {}  # decimal -> hex
        for token_id in token_ids:
            try:
                token_id_int = int(token_id, 16)
                token_id_decimals.append(str(token_id_int))
                token_id_map[str(token_id_int)] = token_id
            except ValueError:
                logger.warning(f"Invalid token_id format: {token_id}")

        # Batch query (API supports multiple clob_token_ids parameters)
        # Note: We'll query in batches to avoid URL length limits
        batch_size = 20  # Smaller batch to avoid URL length issues
        for i in range(0, len(token_id_decimals), batch_size):
            batch = token_id_decimals[i:i+batch_size]

            try:
                # Build params with multiple clob_token_ids parameters
                # Format: ?clob_token_ids=ID1&clob_token_ids=ID2&...
                params = [('clob_token_ids', token_id) for token_id in batch]
                params.append(('limit', str(len(batch) * 2)))  # Allow room for multi-outcome markets

                logger.info(f"Batch querying {len(batch)} token IDs...")
                response = self.client.get(self.MARKETS_ENDPOINT, params=params)
                response.raise_for_status()

                markets = response.json()

                # Map markets back to token IDs
                for market in markets:
                    market_token_ids = json.loads(market.get('clobTokenIds', '[]'))
                    for token_id_dec in batch:
                        if token_id_dec in market_token_ids:
                            token_id_hex = token_id_map[token_id_dec]
                            results[token_id_hex] = self._parse_market(market, token_id_hex)

            except Exception as e:
                logger.error(f"Error in batch query: {e}")
                # Fall back to individual queries on error
                logger.info("Falling back to individual queries...")
                for token_id_hex in [token_id_map[tid] for tid in batch if tid in token_id_map]:
                    if token_id_hex not in results:
                        market_data = self.get_market_by_token_id(token_id_hex)
                        if market_data:
                            results[token_id_hex] = market_data

        logger.info(f"Successfully fetched {len(results)}/{len(token_ids)} markets")
        return results

    def close(self):
        """Close HTTP client"""
        self.client.close()
