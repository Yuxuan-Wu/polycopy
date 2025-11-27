"""
Database manager for storing and exporting trade data
"""
import sqlite3
import csv
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database and CSV export for trade data"""

    def __init__(self, db_path: str, csv_path: str, auto_export: bool = True):
        """
        Initialize Database Manager

        Args:
            db_path: Path to SQLite database file
            csv_path: Path to CSV export file
            auto_export: Automatically export to CSV on every insert
        """
        self.db_path = db_path
        self.csv_path = csv_path
        self.auto_export = auto_export

        # Ensure parent directories exist
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(csv_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_database()
        self._init_csv()

    def _init_database(self):
        """Initialize SQLite database and create tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tx_hash TEXT UNIQUE NOT NULL,
                    block_number INTEGER NOT NULL,
                    timestamp INTEGER NOT NULL,
                    from_address TEXT NOT NULL,
                    to_address TEXT NOT NULL,
                    method TEXT,
                    token_id TEXT,
                    amount TEXT,
                    price TEXT,
                    side TEXT,
                    gas_used TEXT,
                    gas_price TEXT,
                    value TEXT,
                    status TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(tx_hash)
                )
            """)

            # Create index for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_from_address ON trades(from_address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_block_number ON trades(block_number)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON trades(timestamp)
            """)

            # Add capture_delay_seconds column if it doesn't exist (migration)
            try:
                cursor.execute("""
                    ALTER TABLE trades ADD COLUMN capture_delay_seconds INTEGER
                """)
                logger.info("✓ Added capture_delay_seconds column to trades table")
            except sqlite3.OperationalError as e:
                # Column already exists, that's fine
                if "duplicate column" not in str(e).lower():
                    logger.debug(f"Column migration: {e}")

            conn.commit()
            conn.close()
            logger.info(f"✓ Database initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def _init_csv(self):
        """Initialize CSV file with headers if it doesn't exist"""
        csv_file = Path(self.csv_path)
        if not csv_file.exists():
            try:
                with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'tx_hash', 'block_number', 'timestamp', 'datetime',
                        'from_address', 'to_address', 'method', 'token_id',
                        'amount', 'price', 'side', 'gas_used', 'gas_price',
                        'value', 'status', 'capture_delay_seconds'
                    ])
                logger.info(f"✓ CSV file initialized: {self.csv_path}")
            except Exception as e:
                logger.error(f"Failed to initialize CSV: {e}")
                raise

    def insert_trade(self, trade_data: Dict) -> bool:
        """
        Insert a new trade record

        Args:
            trade_data: Dictionary containing trade information

        Returns:
            bool: True if insert successful
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR IGNORE INTO trades (
                    tx_hash, block_number, timestamp, from_address, to_address,
                    method, token_id, amount, price, side, gas_used, gas_price,
                    value, status, created_at, capture_delay_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_data.get('tx_hash'),
                trade_data.get('block_number'),
                trade_data.get('timestamp'),
                trade_data.get('from_address'),
                trade_data.get('to_address'),
                trade_data.get('method'),
                trade_data.get('token_id'),
                trade_data.get('amount'),
                trade_data.get('price'),
                trade_data.get('side'),
                trade_data.get('gas_used'),
                trade_data.get('gas_price'),
                trade_data.get('value'),
                trade_data.get('status'),
                datetime.utcnow().isoformat(),
                trade_data.get('capture_delay_seconds')
            ))

            inserted = cursor.rowcount > 0
            conn.commit()
            conn.close()

            if inserted:
                logger.info(f"✓ Trade recorded: {trade_data.get('tx_hash')[:10]}...")

                if self.auto_export:
                    self._append_to_csv(trade_data)

            return inserted

        except Exception as e:
            logger.error(f"Failed to insert trade: {e}")
            return False

    def _append_to_csv(self, trade_data: Dict):
        """
        Append trade data to CSV file

        Args:
            trade_data: Dictionary containing trade information
        """
        try:
            with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    trade_data.get('tx_hash'),
                    trade_data.get('block_number'),
                    trade_data.get('timestamp'),
                    datetime.fromtimestamp(trade_data.get('timestamp', 0)).isoformat(),
                    trade_data.get('from_address'),
                    trade_data.get('to_address'),
                    trade_data.get('method'),
                    trade_data.get('token_id'),
                    trade_data.get('amount'),
                    trade_data.get('price'),
                    trade_data.get('side'),
                    trade_data.get('gas_used'),
                    trade_data.get('gas_price'),
                    trade_data.get('value'),
                    trade_data.get('status'),
                    trade_data.get('capture_delay_seconds')
                ])
        except Exception as e:
            logger.error(f"Failed to append to CSV: {e}")

    def export_all_to_csv(self, output_path: Optional[str] = None):
        """
        Export all trades from database to CSV

        Args:
            output_path: Optional custom output path
        """
        output_path = output_path or self.csv_path

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT tx_hash, block_number, timestamp, from_address, to_address,
                       method, token_id, amount, price, side, gas_used, gas_price,
                       value, status, capture_delay_seconds
                FROM trades
                ORDER BY timestamp DESC
            """)

            rows = cursor.fetchall()
            conn.close()

            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'tx_hash', 'block_number', 'timestamp', 'datetime',
                    'from_address', 'to_address', 'method', 'token_id',
                    'amount', 'price', 'side', 'gas_used', 'gas_price',
                    'value', 'status', 'capture_delay_seconds'
                ])

                for row in rows:
                    row_list = list(row)
                    # Insert datetime after timestamp
                    row_list.insert(3, datetime.fromtimestamp(row[2]).isoformat())
                    writer.writerow(row_list)

            logger.info(f"✓ Exported {len(rows)} trades to {output_path}")

        except Exception as e:
            logger.error(f"Failed to export to CSV: {e}")

    def get_trade_count(self) -> int:
        """
        Get total number of trades in database

        Returns:
            int: Number of trades
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trades")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            logger.error(f"Failed to get trade count: {e}")
            return 0

    def get_latest_block(self) -> Optional[int]:
        """
        Get the latest block number processed

        Returns:
            Optional[int]: Latest block number or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(block_number) FROM trades")
            result = cursor.fetchone()[0]
            conn.close()
            return result
        except Exception as e:
            logger.error(f"Failed to get latest block: {e}")
            return None
