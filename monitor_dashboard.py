#!/usr/bin/env python3
"""
Real-time Monitoring Dashboard - Shows process status, recent trades, and current positions
Includes Clash proxy status and connectivity monitoring
"""
import sys
import os
import time
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import DatabaseManager
from metadata_manager import MetadataManager
from gamma_client import GammaClient

# Try to import clash proxy manager
try:
    from clash_proxy_manager import get_proxy_manager
    CLASH_AVAILABLE = True
except ImportError:
    CLASH_AVAILABLE = False


def clear_screen():
    """Clear terminal screen"""
    os.system('clear' if os.name != 'nt' else 'cls')


def get_clash_status():
    """Get Clash proxy status"""
    status = {
        'running': False,
        'pid': None,
        'region': None,
        'connected': None,
        'error': None
    }

    # Check if Clash process is running
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'clash'],
            capture_output=True,
            text=True,
            timeout=3
        )
        if result.returncode == 0 and result.stdout.strip():
            status['running'] = True
            status['pid'] = result.stdout.strip().split('\n')[0]
    except:
        pass

    # Get proxy details if available
    if CLASH_AVAILABLE and status['running']:
        try:
            pm = get_proxy_manager()
            status['region'] = pm.get_current_proxy()

            # Quick connectivity test (with short timeout)
            connected, error = pm.test_connectivity(timeout=5)
            status['connected'] = connected
            if not connected:
                status['error'] = error
        except Exception as e:
            status['error'] = str(e)

    return status


def get_process_info():
    """Get monitor process information"""
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'main.py'],
            capture_output=True,
            text=True
        )

        if result.returncode == 0 and result.stdout.strip():
            pid = result.stdout.strip().split('\n')[0]

            # Get process stats
            ps_result = subprocess.run(
                ['ps', '-p', pid, '-o', 'pid,etime,%cpu,%mem,cmd'],
                capture_output=True,
                text=True
            )

            if ps_result.returncode == 0:
                lines = ps_result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    return {
                        'running': True,
                        'pid': pid,
                        'info': lines[1]
                    }

        return {'running': False}
    except Exception as e:
        return {'running': False, 'error': str(e)}


def format_number(num):
    """Format large numbers with commas"""
    return f"{num:,}"


def format_datetime(timestamp):
    """Format unix timestamp"""
    if timestamp:
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    return 'N/A'


def get_database_stats(db_path):
    """Get database statistics"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Total trades
        cursor.execute("SELECT COUNT(*) FROM trades")
        total_trades = cursor.fetchone()[0]

        # Unique addresses
        cursor.execute("SELECT COUNT(DISTINCT from_address) FROM trades")
        unique_addresses = cursor.fetchone()[0]

        # Unique markets
        cursor.execute("SELECT COUNT(DISTINCT token_id) FROM trades WHERE token_id IS NOT NULL")
        unique_markets = cursor.fetchone()[0]

        # Latest trade
        cursor.execute("SELECT timestamp FROM trades ORDER BY timestamp DESC LIMIT 1")
        latest_trade = cursor.fetchone()
        latest_trade_ts = latest_trade[0] if latest_trade else None

        # Capture delay distribution
        cursor.execute("""
            SELECT
                COUNT(CASE WHEN capture_delay_seconds < 60 THEN 1 END) as realtime,
                COUNT(CASE WHEN capture_delay_seconds >= 60 AND capture_delay_seconds < 300 THEN 1 END) as slow,
                COUNT(CASE WHEN capture_delay_seconds >= 300 AND capture_delay_seconds < 3600 THEN 1 END) as delayed,
                COUNT(CASE WHEN capture_delay_seconds >= 3600 THEN 1 END) as historical
            FROM trades
            WHERE capture_delay_seconds IS NOT NULL
        """)

        delay_stats = cursor.fetchone()

        conn.close()

        return {
            'total_trades': total_trades,
            'unique_addresses': unique_addresses,
            'unique_markets': unique_markets,
            'latest_trade': latest_trade_ts,
            'delay_stats': {
                'realtime': delay_stats[0] if delay_stats else 0,
                'slow': delay_stats[1] if delay_stats else 0,
                'delayed': delay_stats[2] if delay_stats else 0,
                'historical': delay_stats[3] if delay_stats else 0
            }
        }
    except Exception as e:
        return {'error': str(e)}


def get_copy_order_stats(db_path):
    """Get copy trading statistics"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if copy_orders table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='copy_orders'")
        if not cursor.fetchone():
            conn.close()
            return None

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
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
        return None


def get_recent_copy_orders(db_path, limit=5):
    """Get recent copy orders"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if copy_orders table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='copy_orders'")
        if not cursor.fetchone():
            conn.close()
            return []

        cursor.execute(f"""
            SELECT token_id, side, amount, price, status, error_message, created_at
            FROM copy_orders
            ORDER BY created_at DESC
            LIMIT {limit}
        """)

        orders = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return orders
    except Exception as e:
        return []


def get_recent_trades(db_path, limit=5):
    """Get recent trades with metadata"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT tx_hash, timestamp, from_address, token_id, amount, price, side, capture_delay_seconds
            FROM trades
            ORDER BY timestamp DESC
            LIMIT {limit}
        """)

        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return trades
    except Exception as e:
        return []


def display_dashboard(db_path, metadata_manager, db_manager, refresh_interval=5, show_positions=True):
    """Display the monitoring dashboard"""

    while True:
        clear_screen()

        # Header
        print("=" * 100)
        print(f"{'🎯 POLYCOPY MONITORING DASHBOARD':^100}")
        print("=" * 100)
        print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Process Status
        proc_info = get_process_info()
        clash_info = get_clash_status()

        print("📊 SYSTEM STATUS")
        print("-" * 100)

        # Monitor process
        if proc_info['running']:
            print(f"Monitor:     🟢 RUNNING (PID {proc_info['info'].split()[0]})")
        else:
            print(f"Monitor:     🔴 STOPPED")

        # Clash proxy
        if clash_info['running']:
            region_text = clash_info['region'] or 'Unknown'
            if clash_info['connected']:
                print(f"Proxy:       🟢 CONNECTED via {region_text}")
            elif clash_info['connected'] is False:
                print(f"Proxy:       🟡 RUNNING but NOT CONNECTED - {clash_info['error'] or 'Unknown error'}")
            else:
                print(f"Proxy:       🟡 RUNNING ({region_text}) - connectivity unknown")
        else:
            print(f"Proxy:       ⚪ NOT RUNNING (copy trading may fail)")

        # RPC status (inferred from process running)
        if proc_info['running']:
            print(f"RPC:         🟢 DIRECT (Infura)")
        print()

        # Database Statistics
        db_stats = get_database_stats(db_path)
        print("📈 DATABASE STATISTICS")
        print("-" * 100)

        if 'error' not in db_stats:
            print(f"Total Trades:      {format_number(db_stats['total_trades'])}")
            print(f"Unique Addresses:  {db_stats['unique_addresses']}")
            print(f"Unique Markets:    {db_stats['unique_markets']}")

            if db_stats['latest_trade']:
                print(f"Latest Trade:      {format_datetime(db_stats['latest_trade'])}")

            delay = db_stats['delay_stats']
            print(f"\nCapture Delay Distribution:")
            print(f"  ⚡ Real-time (<60s):     {delay['realtime']}")
            print(f"  ⏱️  Slow (60s-5m):        {delay['slow']}")
            print(f"  ⚠️  Delayed (5m-1h):      {delay['delayed']}")
            print(f"  ⏰ Historical (>1h):     {delay['historical']}")
        else:
            print(f"Error: {db_stats['error']}")
        print()

        # Copy Trading Statistics
        copy_stats = get_copy_order_stats(db_path)
        if copy_stats is not None:
            print("🤖 COPY TRADING STATUS")
            print("-" * 100)
            if copy_stats['total'] > 0:
                print(f"Total Orders: {copy_stats['total']} | "
                      f"✅ Success: {copy_stats['success']} | "
                      f"❌ Failed: {copy_stats['failed']} | "
                      f"⏳ Pending: {copy_stats['pending']} | "
                      f"Success Rate: {copy_stats['success_rate']:.1f}%")
            else:
                print("No copy orders yet (waiting for target trades...)")
            print()

        # Recent Trades (Target Address)
        print("📋 TARGET TRADES (Last 5)")
        print("-" * 100)

        recent = get_recent_trades(db_path, limit=5)

        if recent:
            for trade in recent:
                token_id = trade['token_id']
                market_info = metadata_manager.get_market_for_token(token_id) if token_id else None

                # Show full question (up to 80 chars) with ellipsis if needed
                if market_info:
                    full_question = market_info.get('question', 'N/A')
                    market_question = full_question if len(full_question) <= 80 else full_question[:77] + '...'
                else:
                    market_question = 'N/A'

                outcome = market_info.get('outcome_name', 'N/A') if market_info else 'N/A'

                delay_emoji = "⚡" if trade['capture_delay_seconds'] and trade['capture_delay_seconds'] < 60 else \
                             "⏱️" if trade['capture_delay_seconds'] and trade['capture_delay_seconds'] < 300 else \
                             "⚠️" if trade['capture_delay_seconds'] and trade['capture_delay_seconds'] < 3600 else "⏰"

                print(f"{delay_emoji} {format_datetime(trade['timestamp'])} | {trade['side'].upper():4} | "
                      f"{float(trade['amount']):>10.2f} @ ${float(trade['price']):<6.4f} | {outcome:8}")
                print(f"   Market: {market_question}")
        else:
            print("No trades found")
        print()

        # Recent Copy Orders (My Trades)
        if copy_stats is not None:
            print("🔄 MY COPY ORDERS (Last 5)")
            print("-" * 100)

            copy_orders = get_recent_copy_orders(db_path, limit=5)

            if copy_orders:
                for order in copy_orders:
                    token_id = order['token_id']
                    market_info = metadata_manager.get_market_for_token(token_id) if token_id else None

                    if market_info:
                        full_question = market_info.get('question', 'N/A')
                        market_question = full_question if len(full_question) <= 60 else full_question[:57] + '...'
                    else:
                        market_question = f"Token {token_id[:20]}..."

                    status_emoji = "✅" if order['status'] == 'success' else \
                                  "❌" if order['status'] == 'failed' else "⏳"

                    amount = order['amount'] or 0
                    price = order['price'] or 0

                    print(f"{status_emoji} {order['created_at'][:19]} | {order['side'].upper():4} | "
                          f"{amount:>8.2f} shares @ ${price:<6.4f} | {order['status'].upper()}")
                    if order['status'] == 'failed' and order['error_message']:
                        print(f"   Error: {order['error_message'][:70]}")
                    else:
                        print(f"   Market: {market_question}")
            else:
                print("No copy orders yet")
            print()

        # Current Positions
        if show_positions:
            print("💼 CURRENT POSITIONS (Active only)")
            print("-" * 100)

            positions = db_manager.get_active_positions()

            if positions:
                total_value = 0
                total_cost = 0
                total_realized_pnl = sum(p['realized_pnl'] for p in positions)
                incomplete_count = 0

                for pos in positions:
                    token_id = pos['token_id']
                    market_info = metadata_manager.get_market_for_token(token_id) if token_id else None

                    if market_info:
                        question = market_info.get('question', 'N/A')
                        outcome = market_info.get('outcome_name', 'N/A')
                        current_price = market_info.get('outcome_price', 0)
                    else:
                        question = f"Token {token_id[:20]}..."
                        outcome = 'N/A'
                        current_price = 0

                    current_value = pos['current_position'] * current_price
                    cost_basis = pos['current_position'] * (pos['avg_buy_price'] or 0)
                    unrealized_pnl = current_value - cost_basis

                    total_value += current_value
                    total_cost += cost_basis

                    # Status emoji with incomplete warning
                    if pos.get('is_complete') == 0:
                        status_emoji = '⚠️'
                        incomplete_count += 1
                        status_text = 'INCOMPLETE'
                    elif pos['status'] == 'active':
                        status_emoji = '🟢'
                        status_text = 'ACTIVE'
                    else:
                        status_emoji = '⚪'
                        status_text = pos['status'].upper()

                    # Display full question (no truncation)
                    print(f"{status_emoji} [{status_text}] {question}")
                    print(f"   Outcome: {outcome:10} | Position: {pos['current_position']:>10.2f} tokens | "
                          f"Avg: ${pos['avg_buy_price'] or 0:.4f} | Current: ${current_price:.4f}")
                    print(f"   Bought: {pos['total_bought']:.2f} | Sold: {pos['total_sold']:.2f} | "
                          f"Cost: ${cost_basis:.2f} | Value: ${current_value:.2f} | Unrealized: ${unrealized_pnl:+.2f}")
                    print()

                total_unrealized_pnl = total_value - total_cost
                total_pnl = total_realized_pnl + total_unrealized_pnl

                print("-" * 100)
                print(f"SUMMARY: {len(positions)} active positions", end='')
                if incomplete_count > 0:
                    print(f" (⚠️  {incomplete_count} incomplete - missing trades >7 days old)")
                else:
                    print()
                print(f"Total Cost Basis: ${total_cost:.2f} | Current Value: ${total_value:.2f}")
                print(f"Realized P&L: ${total_realized_pnl:+.2f} | Unrealized P&L: ${total_unrealized_pnl:+.2f} | "
                      f"Total P&L: ${total_pnl:+.2f}")
            else:
                print("No active positions")
            print()

        print("=" * 100)
        print(f"Press Ctrl+C to exit | Refreshing every {refresh_interval} seconds")
        print("=" * 100)

        try:
            time.sleep(refresh_interval)
        except KeyboardInterrupt:
            print("\n\nExiting dashboard...")
            break


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Real-time monitoring dashboard')
    parser.add_argument('--refresh', type=int, default=5, help='Refresh interval in seconds (default: 5)')
    parser.add_argument('--no-positions', action='store_true', help='Hide positions section')

    args = parser.parse_args()

    # Initialize managers
    db_path = 'data/trades.db'
    db_manager = DatabaseManager(db_path, 'data/trades.csv', auto_export=False)
    gamma_client = GammaClient(timeout=30)
    metadata_manager = MetadataManager(db_path, gamma_client)

    # Display dashboard
    display_dashboard(
        db_path,
        metadata_manager,
        db_manager,
        refresh_interval=args.refresh,
        show_positions=not args.no_positions
    )


if __name__ == '__main__':
    main()
