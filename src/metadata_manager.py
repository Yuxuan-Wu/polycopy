"""
Market Metadata Manager
Handles fetching and storing market metadata from Gamma API
"""
import sqlite3
import logging
import json
from typing import List, Dict, Optional, Set
from pathlib import Path
from gamma_client import GammaClient

logger = logging.getLogger(__name__)


class MetadataManager:
    """Manages market metadata storage and backfilling"""

    def __init__(self, db_path: str, gamma_client: Optional[GammaClient] = None):
        """
        Initialize Metadata Manager

        Args:
            db_path: Path to SQLite database
            gamma_client: Optional GammaClient instance (creates new if None)
        """
        self.db_path = db_path
        self.gamma_client = gamma_client or GammaClient()

        # Ensure database exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_metadata_table()

    def _init_metadata_table(self):
        """Initialize markets metadata table"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create markets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS markets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT UNIQUE NOT NULL,
                    condition_id TEXT,
                    question TEXT,
                    slug TEXT,
                    description TEXT,
                    outcomes TEXT,
                    outcome_prices TEXT,
                    clob_token_ids TEXT,
                    category TEXT,
                    image TEXT,
                    icon TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    volume REAL,
                    liquidity REAL,
                    active INTEGER,
                    closed INTEGER,
                    event_slug TEXT,
                    event_title TEXT,
                    neg_risk INTEGER,
                    market_type TEXT,
                    fetched_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(market_id)
                )
            """)

            # Create index on condition_id for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_condition_id ON markets(condition_id)
            """)

            # Create token_outcomes table to map token_id -> market + outcome
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS token_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_id TEXT UNIQUE NOT NULL,
                    market_id TEXT NOT NULL,
                    condition_id TEXT,
                    outcome_index INTEGER,
                    outcome_name TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (market_id) REFERENCES markets(market_id),
                    UNIQUE(token_id)
                )
            """)

            # Create index on token_id for fast lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_id ON token_outcomes(token_id)
            """)

            conn.commit()
            conn.close()
            logger.info("✓ Metadata tables initialized")

        except Exception as e:
            logger.error(f"Failed to initialize metadata tables: {e}")
            raise

    def save_market_metadata(self, market_data: Dict, token_id: Optional[str] = None) -> bool:
        """
        Save market metadata to database

        Args:
            market_data: Parsed market data from GammaClient
            token_id: Optional specific token_id that triggered this fetch

        Returns:
            bool: True if saved successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            from datetime import datetime
            now = datetime.utcnow().isoformat()

            # Insert or update market
            cursor.execute("""
                INSERT INTO markets (
                    market_id, condition_id, question, slug, description,
                    outcomes, outcome_prices, clob_token_ids, category,
                    image, icon, start_date, end_date, volume, liquidity,
                    active, closed, event_slug, event_title, neg_risk,
                    market_type, fetched_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market_id) DO UPDATE SET
                    question=excluded.question,
                    description=excluded.description,
                    outcome_prices=excluded.outcome_prices,
                    volume=excluded.volume,
                    liquidity=excluded.liquidity,
                    active=excluded.active,
                    closed=excluded.closed,
                    updated_at=excluded.updated_at
            """, (
                market_data.get('market_id'),
                market_data.get('condition_id'),
                market_data.get('question'),
                market_data.get('slug'),
                market_data.get('description'),
                json.dumps(market_data.get('outcomes', [])),
                json.dumps(market_data.get('outcome_prices', [])),
                json.dumps(market_data.get('clob_token_ids', [])),
                market_data.get('category'),
                market_data.get('image'),
                market_data.get('icon'),
                market_data.get('start_date'),
                market_data.get('end_date'),
                market_data.get('volume'),
                market_data.get('liquidity'),
                1 if market_data.get('active') else 0,
                1 if market_data.get('closed') else 0,
                market_data.get('event_slug'),
                market_data.get('event_title'),
                1 if market_data.get('neg_risk') else 0,
                market_data.get('market_type'),
                now,
                now
            ))

            # If we have token_id and outcome info, save token mapping
            if token_id and market_data.get('outcome_index') is not None:
                cursor.execute("""
                    INSERT INTO token_outcomes (
                        token_id, market_id, condition_id, outcome_index, outcome_name, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(token_id) DO UPDATE SET
                        outcome_name=excluded.outcome_name
                """, (
                    token_id,
                    market_data.get('market_id'),
                    market_data.get('condition_id'),
                    market_data.get('outcome_index'),
                    market_data.get('outcome_name'),
                    now
                ))

            # Also save all token IDs from this market
            for idx, token_id_dec in enumerate(market_data.get('clob_token_ids', [])):
                # Convert decimal back to hex
                token_id_hex = hex(int(token_id_dec))
                outcome_name = market_data.get('outcomes', [])[idx] if idx < len(market_data.get('outcomes', [])) else None

                cursor.execute("""
                    INSERT INTO token_outcomes (
                        token_id, market_id, condition_id, outcome_index, outcome_name, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(token_id) DO NOTHING
                """, (
                    token_id_hex,
                    market_data.get('market_id'),
                    market_data.get('condition_id'),
                    idx,
                    outcome_name,
                    now
                ))

            conn.commit()
            conn.close()

            logger.info(f"✓ Saved metadata for market: {market_data.get('market_id')} - {market_data.get('question', 'N/A')[:50]}")
            return True

        except Exception as e:
            logger.error(f"Failed to save market metadata: {e}")
            return False

    def get_missing_token_ids(self) -> List[str]:
        """
        Get list of token_ids from trades that don't have metadata

        Returns:
            List of token_ids needing metadata
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Find token_ids in trades that are not in token_outcomes
            cursor.execute("""
                SELECT DISTINCT t.token_id
                FROM trades t
                LEFT JOIN token_outcomes o ON t.token_id = o.token_id
                WHERE o.token_id IS NULL
                  AND t.token_id IS NOT NULL
                  AND t.token_id != ''
            """)

            rows = cursor.fetchall()
            conn.close()

            token_ids = [row[0] for row in rows]
            logger.info(f"Found {len(token_ids)} token_ids missing metadata")
            return token_ids

        except Exception as e:
            logger.error(f"Error finding missing token_ids: {e}")
            return []

    def backfill_metadata(self, force_refresh: bool = False) -> Dict[str, int]:
        """
        Backfill metadata for all trades in database

        Args:
            force_refresh: If True, refresh all metadata even if already exists

        Returns:
            Dictionary with stats: {'success': int, 'failed': int, 'skipped': int}
        """
        stats = {'success': 0, 'failed': 0, 'skipped': 0, 'total': 0}

        try:
            # Get token_ids to process
            if force_refresh:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT token_id FROM trades
                    WHERE token_id IS NOT NULL AND token_id != ''
                """)
                rows = cursor.fetchall()
                conn.close()
                token_ids = [row[0] for row in rows]
            else:
                token_ids = self.get_missing_token_ids()

            stats['total'] = len(token_ids)

            if not token_ids:
                logger.info("No token_ids need metadata backfill")
                return stats

            logger.info("=" * 60)
            logger.info(f"METADATA BACKFILL STARTING")
            logger.info(f"Token IDs to process: {len(token_ids)}")
            logger.info("=" * 60)

            # Batch fetch markets
            logger.info("Fetching market data from Gamma API...")
            market_data_map = self.gamma_client.batch_get_markets(token_ids)

            # Save to database
            for token_id in token_ids:
                if token_id in market_data_map:
                    market_data = market_data_map[token_id]
                    if self.save_market_metadata(market_data, token_id):
                        stats['success'] += 1
                    else:
                        stats['failed'] += 1
                else:
                    logger.warning(f"No market data found for token_id: {token_id}")
                    stats['failed'] += 1

            logger.info("=" * 60)
            logger.info("BACKFILL COMPLETE")
            logger.info(f"Total: {stats['total']}")
            logger.info(f"✓ Success: {stats['success']}")
            logger.info(f"✗ Failed: {stats['failed']}")
            logger.info("=" * 60)

            return stats

        except Exception as e:
            logger.error(f"Error during metadata backfill: {e}")
            return stats

    def get_market_for_token(self, token_id: str) -> Optional[Dict]:
        """
        Get market metadata for a specific token_id

        Args:
            token_id: Token ID to lookup

        Returns:
            Dictionary with market and outcome info, or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    m.market_id, m.condition_id, m.question, m.slug,
                    m.description, m.outcomes, m.outcome_prices,
                    m.category, m.image, m.icon, m.end_date,
                    m.volume, m.liquidity, m.active, m.closed,
                    m.event_title,
                    o.outcome_index, o.outcome_name
                FROM token_outcomes o
                JOIN markets m ON o.market_id = m.market_id
                WHERE o.token_id = ?
            """, (token_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return {
                    'market_id': row[0],
                    'condition_id': row[1],
                    'question': row[2],
                    'slug': row[3],
                    'description': row[4],
                    'outcomes': json.loads(row[5]) if row[5] else [],
                    'outcome_prices': json.loads(row[6]) if row[6] else [],
                    'category': row[7],
                    'image': row[8],
                    'icon': row[9],
                    'end_date': row[10],
                    'volume': row[11],
                    'liquidity': row[12],
                    'active': bool(row[13]),
                    'closed': bool(row[14]),
                    'event_title': row[15],
                    'outcome_index': row[16],
                    'outcome_name': row[17]
                }
            else:
                return None

        except Exception as e:
            logger.error(f"Error getting market for token_id {token_id}: {e}")
            return None

    def get_metadata_stats(self) -> Dict:
        """
        Get statistics about metadata coverage

        Returns:
            Dictionary with coverage stats
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Count trades
            cursor.execute("SELECT COUNT(*) FROM trades WHERE token_id IS NOT NULL AND token_id != ''")
            total_trades = cursor.fetchone()[0]

            # Count unique token_ids in trades
            cursor.execute("SELECT COUNT(DISTINCT token_id) FROM trades WHERE token_id IS NOT NULL AND token_id != ''")
            unique_tokens = cursor.fetchone()[0]

            # Count token_ids with metadata
            cursor.execute("SELECT COUNT(*) FROM token_outcomes")
            tokens_with_metadata = cursor.fetchone()[0]

            # Count markets
            cursor.execute("SELECT COUNT(*) FROM markets")
            total_markets = cursor.fetchone()[0]

            conn.close()

            coverage_pct = (tokens_with_metadata / unique_tokens * 100) if unique_tokens > 0 else 0

            return {
                'total_trades': total_trades,
                'unique_tokens': unique_tokens,
                'tokens_with_metadata': tokens_with_metadata,
                'total_markets': total_markets,
                'coverage_percent': round(coverage_pct, 2)
            }

        except Exception as e:
            logger.error(f"Error getting metadata stats: {e}")
            return {}
