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

            # Create positions table for tracking holdings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,
                    token_id TEXT NOT NULL,
                    market_id TEXT,
                    current_position REAL NOT NULL DEFAULT 0,
                    total_bought REAL NOT NULL DEFAULT 0,
                    total_sold REAL NOT NULL DEFAULT 0,
                    avg_buy_price REAL,
                    total_buy_value REAL NOT NULL DEFAULT 0,
                    total_sell_value REAL NOT NULL DEFAULT 0,
                    realized_pnl REAL NOT NULL DEFAULT 0,
                    first_trade_at INTEGER,
                    last_trade_at INTEGER,
                    status TEXT NOT NULL DEFAULT 'active',
                    settled_at INTEGER,
                    settlement_price REAL,
                    settlement_type TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(address, token_id)
                )
            """)

            # Create index for positions
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_positions_address ON positions(address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_positions_token ON positions(token_id)
            """)

            # Create copy_orders table for tracking copy trading execution
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS copy_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_tx_hash TEXT,
                    token_id TEXT NOT NULL,
                    side TEXT NOT NULL,
                    amount REAL,
                    price REAL,
                    order_id TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    executed_at TEXT
                )
            """)

            # Create index for copy_orders
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_copy_orders_status ON copy_orders(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_copy_orders_token ON copy_orders(token_id)
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

            # Add trade_type column (TAKER=主动交易, MAKER=挂单被执行)
            try:
                cursor.execute("""
                    ALTER TABLE trades ADD COLUMN trade_type TEXT DEFAULT 'TAKER'
                """)
                logger.info("✓ Added trade_type column to trades table")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    logger.debug(f"Column migration: {e}")

            # Add trade_type to copy_orders table
            try:
                cursor.execute("""
                    ALTER TABLE copy_orders ADD COLUMN trade_type TEXT DEFAULT 'TAKER'
                """)
                logger.info("✓ Added trade_type column to copy_orders table")
            except sqlite3.OperationalError as e:
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
                        'value', 'status', 'capture_delay_seconds', 'trade_type'
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
                    value, status, created_at, capture_delay_seconds, trade_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                trade_data.get('capture_delay_seconds'),
                trade_data.get('trade_type', 'TAKER')
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
                    trade_data.get('capture_delay_seconds'),
                    trade_data.get('trade_type', 'TAKER')
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

    def update_position(self, address: str, token_id: str, side: str,
                       amount: float, price: float, timestamp: int, market_id: str = None) -> bool:
        """
        Update position for an address and token based on a trade

        Args:
            address: Trader address
            token_id: Token ID
            side: 'buy' or 'sell'
            amount: Trade amount
            price: Trade price
            timestamp: Trade timestamp
            market_id: Market ID (optional)

        Returns:
            bool: True if update successful
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get current position
            cursor.execute("""
                SELECT current_position, total_bought, total_sold, avg_buy_price,
                       total_buy_value, total_sell_value, realized_pnl, first_trade_at
                FROM positions
                WHERE address = ? AND token_id = ?
            """, (address, token_id))

            row = cursor.fetchone()
            now = datetime.utcnow().isoformat()

            if row:
                # Update existing position
                current_pos, total_bought, total_sold, avg_buy_price, \
                total_buy_value, total_sell_value, realized_pnl, first_trade_at = row

                if side == 'buy':
                    new_position = current_pos + amount
                    new_total_bought = total_bought + amount
                    new_total_buy_value = total_buy_value + (amount * price)
                    new_avg_buy_price = new_total_buy_value / new_total_bought if new_total_bought > 0 else 0
                    new_total_sold = total_sold
                    new_total_sell_value = total_sell_value
                    new_realized_pnl = realized_pnl
                else:  # sell
                    new_position = current_pos - amount
                    new_total_sold = total_sold + amount
                    new_total_sell_value = total_sell_value + (amount * price)
                    # Calculate realized PnL for this sale
                    if avg_buy_price:
                        new_realized_pnl = realized_pnl + (amount * (price - avg_buy_price))
                    else:
                        new_realized_pnl = realized_pnl
                    new_total_bought = total_bought
                    new_total_buy_value = total_buy_value
                    new_avg_buy_price = avg_buy_price

                # Determine status
                if new_position <= 0.0001:  # Close enough to zero (accounting for floating point)
                    new_position = 0
                    status = 'closed'
                else:
                    status = 'active'

                cursor.execute("""
                    UPDATE positions
                    SET current_position = ?,
                        total_bought = ?,
                        total_sold = ?,
                        avg_buy_price = ?,
                        total_buy_value = ?,
                        total_sell_value = ?,
                        realized_pnl = ?,
                        last_trade_at = ?,
                        status = ?,
                        updated_at = ?,
                        market_id = COALESCE(?, market_id)
                    WHERE address = ? AND token_id = ?
                """, (new_position, new_total_bought, new_total_sold, new_avg_buy_price,
                      new_total_buy_value, new_total_sell_value, new_realized_pnl,
                      timestamp, status, now, market_id, address, token_id))

            else:
                # Create new position
                if side == 'buy':
                    current_pos = amount
                    total_bought = amount
                    total_sold = 0
                    avg_buy_price = price
                    total_buy_value = amount * price
                    total_sell_value = 0
                    realized_pnl = 0
                else:  # sell (unusual to start with a sell, but handle it)
                    current_pos = -amount
                    total_bought = 0
                    total_sold = amount
                    avg_buy_price = None
                    total_buy_value = 0
                    total_sell_value = amount * price
                    realized_pnl = 0

                cursor.execute("""
                    INSERT INTO positions (
                        address, token_id, market_id, current_position,
                        total_bought, total_sold, avg_buy_price,
                        total_buy_value, total_sell_value, realized_pnl,
                        first_trade_at, last_trade_at, status,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (address, token_id, market_id, current_pos,
                      total_bought, total_sold, avg_buy_price,
                      total_buy_value, total_sell_value, realized_pnl,
                      timestamp, timestamp, 'active', now, now))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"Failed to update position: {e}")
            return False

    def check_settlement(self, address: str, token_id: str, price: float, timestamp: int) -> Optional[str]:
        """
        Check if a sell transaction appears to be a settlement and update position accordingly

        Settlement detection:
        - Price >= 0.95: Winning settlement (market resolved in favor)
        - Price <= 0.05: Losing settlement (market resolved against)

        Args:
            address: Trader address
            token_id: Token ID
            price: Sale price
            timestamp: Settlement timestamp

        Returns:
            Optional[str]: Settlement type ('win', 'loss', None if not a settlement)
        """
        settlement_type = None

        # Detect settlement based on price
        if price >= 0.95:
            settlement_type = 'win'
            settlement_price = 1.0
        elif price <= 0.05:
            settlement_type = 'loss'
            settlement_price = 0.0
        else:
            return None  # Not a settlement

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()

            cursor.execute("""
                UPDATE positions
                SET status = ?,
                    settled_at = ?,
                    settlement_price = ?,
                    settlement_type = ?,
                    updated_at = ?
                WHERE address = ? AND token_id = ?
            """, (f'settled_{settlement_type}', timestamp, settlement_price,
                  settlement_type, now, address, token_id))

            conn.commit()
            conn.close()

            logger.info(f"📊 Position settled ({settlement_type.upper()}): {token_id[:10]}... at ${settlement_price}")
            return settlement_type

        except Exception as e:
            logger.error(f"Failed to mark settlement: {e}")
            return None

    def get_active_positions(self, address: str = None) -> List[Dict]:
        """
        Get all active positions (current_position > 0)

        Args:
            address: Optional address filter

        Returns:
            List of position dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if address:
                cursor.execute("""
                    SELECT * FROM positions
                    WHERE address = ? AND current_position > 0
                    ORDER BY last_trade_at DESC
                """, (address,))
            else:
                cursor.execute("""
                    SELECT * FROM positions
                    WHERE current_position > 0
                    ORDER BY last_trade_at DESC
                """)

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get active positions: {e}")
            return []

    def get_position(self, address: str, token_id: str) -> Optional[Dict]:
        """
        Get a specific position

        Args:
            address: Trader address
            token_id: Token ID

        Returns:
            Position dictionary or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM positions
                WHERE address = ? AND token_id = ?
            """, (address, token_id))

            row = cursor.fetchone()
            conn.close()

            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get position: {e}")
            return None

    def get_all_positions(self, address: str = None) -> List[Dict]:
        """
        Get all positions (active and closed)

        Args:
            address: Optional address filter

        Returns:
            List of position dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if address:
                cursor.execute("""
                    SELECT * FROM positions
                    WHERE address = ?
                    ORDER BY last_trade_at DESC
                """, (address,))
            else:
                cursor.execute("""
                    SELECT * FROM positions
                    ORDER BY last_trade_at DESC
                """)

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get all positions: {e}")
            return []

    def get_incomplete_positions(self, addresses: List[str] = None) -> List[Dict]:
        """
        Detect positions that are incomplete (sold > bought)
        These positions need backfilling from blockchain history

        Args:
            addresses: Optional list of addresses to filter

        Returns:
            List of incomplete position dictionaries with trade metadata
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build query
            query = """
                SELECT p.*,
                       (SELECT COUNT(*) FROM trades t
                        WHERE t.from_address = p.address
                        AND t.token_id = p.token_id) as trade_count,
                       (SELECT MIN(timestamp) FROM trades t
                        WHERE t.from_address = p.address
                        AND t.token_id = p.token_id) as first_trade_ts
                FROM positions p
                WHERE (p.total_sold > p.total_bought + 0.01
                       OR (p.total_bought = 0 AND p.total_sold > 0))
                  AND (p.is_complete IS NULL OR p.is_complete = 0)
                  AND (p.backfill_attempted = 0 OR p.backfill_attempted IS NULL)
            """

            if addresses:
                placeholders = ','.join('?' * len(addresses))
                query += f" AND p.address IN ({placeholders})"
                cursor.execute(query + " ORDER BY p.updated_at DESC", addresses)
            else:
                cursor.execute(query + " ORDER BY p.updated_at DESC")

            positions = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return positions

        except Exception as e:
            logger.error(f"Failed to get incomplete positions: {e}")
            return []

    def mark_position_backfill(self, address: str, token_id: str, success: bool):
        """
        Mark a position as backfill attempted

        Args:
            address: Trader address
            token_id: Token ID
            success: True if backfill found missing trades, False if not found after 7 days
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE positions
                SET backfill_attempted = 1,
                    backfill_date = ?,
                    is_complete = ?
                WHERE address = ? AND token_id = ?
            """, (datetime.utcnow().isoformat(), 1 if success else 0, address, token_id))

            conn.commit()
            conn.close()

            status = "COMPLETE" if success else "INCOMPLETE (>7 days old)"
            logger.info(f"✓ Position marked as {status}: {address[:10]}.../{token_id[:16]}...")

        except Exception as e:
            logger.error(f"Failed to mark backfill status: {e}")

    def save_copy_order(
        self,
        original_tx_hash: str,
        token_id: str,
        side: str,
        amount: float,
        price: float,
        order_id: str = None,
        status: str = 'pending',
        error_message: str = None,
        trade_type: str = 'TAKER'
    ) -> bool:
        """
        Save a copy trade order record

        Args:
            original_tx_hash: Hash of the original trade being copied
            token_id: Token ID
            side: 'buy' or 'sell'
            amount: Order amount
            price: Execution price
            order_id: Polymarket order ID
            status: 'pending', 'success', or 'failed'
            error_message: Error message if failed
            trade_type: 'TAKER' (主动交易) or 'MAKER' (挂单被执行)

        Returns:
            bool: True if save successful
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()

            executed_at = now if status in ('success', 'failed') else None

            cursor.execute("""
                INSERT INTO copy_orders (
                    original_tx_hash, token_id, side, amount, price,
                    order_id, status, error_message, created_at, executed_at, trade_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                original_tx_hash, token_id, side, amount, price,
                order_id, status, error_message, now, executed_at, trade_type
            ))

            conn.commit()
            conn.close()

            if status == 'success':
                logger.info(f"✓ Copy order saved: {side} {amount} @ ${price:.4f}")
            else:
                logger.warning(f"✗ Copy order failed: {error_message}")

            return True

        except Exception as e:
            logger.error(f"Failed to save copy order: {e}")
            return False

    def get_copy_orders(self, status: str = None, limit: int = 100) -> List[Dict]:
        """
        Get copy orders from database

        Args:
            status: Filter by status ('pending', 'success', 'failed')
            limit: Maximum number of orders to return

        Returns:
            List of copy order dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if status:
                cursor.execute("""
                    SELECT * FROM copy_orders
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (status, limit))
            else:
                cursor.execute("""
                    SELECT * FROM copy_orders
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get copy orders: {e}")
            return []

    def get_copy_order_stats(self) -> Dict:
        """
        Get copy order statistics

        Returns:
            Dictionary with success/failure counts and rates
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count
                FROM copy_orders
            """)

            row = cursor.fetchone()
            conn.close()

            total = row[0] or 0
            success = row[1] or 0
            failed = row[2] or 0
            pending = row[3] or 0

            return {
                'total': total,
                'success': success,
                'failed': failed,
                'pending': pending,
                'success_rate': (success / total * 100) if total > 0 else 0
            }

        except Exception as e:
            logger.error(f"Failed to get copy order stats: {e}")
            return {'total': 0, 'success': 0, 'failed': 0, 'pending': 0, 'success_rate': 0}
