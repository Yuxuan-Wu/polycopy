#!/usr/bin/env python3
"""
Market-Level Analysis Tool
Deep dive into specific markets and trading patterns
"""
import sqlite3
import json
from datetime import datetime
from collections import defaultdict
from typing import Dict, List
import sys


class MarketAnalyzer:
    """Analyze trading patterns within specific markets"""

    def __init__(self, db_path: str = "data/trades.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()

    def analyze_market_for_address(self, address: str, token_id: str) -> Dict:
        """
        Deep analysis of how an address trades a specific market
        """
        cursor = self.conn.cursor()

        # Get all trades for this market
        cursor.execute("""
            SELECT
                timestamp,
                block_number,
                side,
                CAST(amount AS REAL) as amount,
                CAST(price AS REAL) as price,
                tx_hash
            FROM trades
            WHERE from_address = ? AND token_id = ?
            ORDER BY timestamp ASC
        """, (address, token_id))

        trades = [dict(row) for row in cursor.fetchall()]

        if not trades:
            return {'error': 'No trades found'}

        # Calculate metrics
        total_bought = sum(t['amount'] for t in trades if t['side'] == 'buy')
        total_sold = sum(t['amount'] for t in trades if t['side'] == 'sell')
        net_position = total_bought - total_sold

        # Price analysis
        buy_prices = [t['price'] for t in trades if t['side'] == 'buy']
        sell_prices = [t['price'] for t in trades if t['side'] == 'sell']

        avg_buy_price = sum(buy_prices) / len(buy_prices) if buy_prices else 0
        avg_sell_price = sum(sell_prices) / len(sell_prices) if sell_prices else 0

        # Timing analysis
        position_changes = []
        current_position = 0

        for i, trade in enumerate(trades):
            previous_position = current_position

            if trade['side'] == 'buy':
                current_position += trade['amount']
            else:
                current_position -= trade['amount']

            # Detect significant position changes
            if i > 0:
                time_since_last = trade['timestamp'] - trades[i-1]['timestamp']
                position_changes.append({
                    'trade_num': i + 1,
                    'timestamp': datetime.fromtimestamp(trade['timestamp']).isoformat(),
                    'side': trade['side'],
                    'amount': trade['amount'],
                    'price': trade['price'],
                    'position_before': round(previous_position, 2),
                    'position_after': round(current_position, 2),
                    'time_since_last_seconds': time_since_last
                })

        # Side switching analysis
        side_switches = 0
        for i in range(1, len(trades)):
            if trades[i]['side'] != trades[i-1]['side']:
                side_switches += 1

        return {
            'token_id': token_id,
            'total_trades': len(trades),
            'total_bought': round(total_bought, 2),
            'total_sold': round(total_sold, 2),
            'net_position': round(net_position, 2),
            'avg_buy_price': round(avg_buy_price, 4) if avg_buy_price else None,
            'avg_sell_price': round(avg_sell_price, 4) if avg_sell_price else None,
            'spread': round(avg_sell_price - avg_buy_price, 4) if (avg_sell_price and avg_buy_price) else None,
            'side_switches': side_switches,
            'is_atomic': side_switches == 0,
            'first_trade': datetime.fromtimestamp(trades[0]['timestamp']).isoformat(),
            'last_trade': datetime.fromtimestamp(trades[-1]['timestamp']).isoformat(),
            'position_changes': position_changes
        }

    def find_correlated_trades(self, address: str, time_window_seconds: int = 60) -> List[Dict]:
        """
        Find trades that happen in quick succession
        Useful for identifying strategy patterns
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                timestamp,
                block_number,
                token_id,
                side,
                CAST(amount AS REAL) as amount,
                CAST(price AS REAL) as price
            FROM trades
            WHERE from_address = ?
            ORDER BY timestamp ASC
        """, (address,))

        trades = [dict(row) for row in cursor.fetchall()]

        # Find clustered trades
        clusters = []
        i = 0

        while i < len(trades):
            cluster = [trades[i]]
            j = i + 1

            while j < len(trades) and (trades[j]['timestamp'] - trades[i]['timestamp']) <= time_window_seconds:
                cluster.append(trades[j])
                j += 1

            if len(cluster) > 1:
                # Analyze cluster
                unique_markets = len(set(t['token_id'] for t in cluster))
                buy_count = sum(1 for t in cluster if t['side'] == 'buy')
                sell_count = sum(1 for t in cluster if t['side'] == 'sell')

                clusters.append({
                    'timestamp': datetime.fromtimestamp(cluster[0]['timestamp']).isoformat(),
                    'trade_count': len(cluster),
                    'unique_markets': unique_markets,
                    'buys': buy_count,
                    'sells': sell_count,
                    'time_span_seconds': cluster[-1]['timestamp'] - cluster[0]['timestamp'],
                    'pattern': self._identify_cluster_pattern(cluster)
                })

            i = j if j > i + 1 else i + 1

        return clusters

    def _identify_cluster_pattern(self, cluster: List[Dict]) -> str:
        """Identify the pattern in a trade cluster"""
        unique_markets = len(set(t['token_id'] for t in cluster))
        sides = [t['side'] for t in cluster]

        if unique_markets == 1:
            if all(s == sides[0] for s in sides):
                return f"single_market_{sides[0]}_accumulation"
            else:
                return "single_market_hedging"
        else:
            buy_count = sum(1 for s in sides if s == 'buy')
            sell_count = len(sides) - buy_count

            if buy_count > 0 and sell_count > 0:
                return "multi_market_hedging"
            elif buy_count > 0:
                return "multi_market_buying"
            else:
                return "multi_market_selling"

    def generate_market_report(self, address: str, token_id: str):
        """Generate detailed market-specific report"""
        print(f"\n{'='*80}")
        print(f"MARKET-LEVEL ANALYSIS")
        print(f"Address: {address[:10]}...{address[-4:]}")
        print(f"Token ID: {token_id[:20]}...")
        print(f"{'='*80}\n")

        analysis = self.analyze_market_for_address(address, token_id)

        if 'error' in analysis:
            print(f"Error: {analysis['error']}")
            return

        print("OVERVIEW")
        print("-" * 80)
        print(f"  Total Trades: {analysis['total_trades']}")
        print(f"  Total Bought: {analysis['total_bought']:.2f}")
        print(f"  Total Sold: {analysis['total_sold']:.2f}")
        print(f"  Net Position: {analysis['net_position']:.2f}")
        print(f"  Is Atomic: {'YES' if analysis['is_atomic'] else 'NO'}")
        print(f"  Side Switches: {analysis['side_switches']}")

        print(f"\nPRICING")
        print("-" * 80)
        if analysis['avg_buy_price']:
            print(f"  Avg Buy Price: {analysis['avg_buy_price']:.4f}")
        if analysis['avg_sell_price']:
            print(f"  Avg Sell Price: {analysis['avg_sell_price']:.4f}")
        if analysis['spread']:
            print(f"  Spread (Sell - Buy): {analysis['spread']:.4f}")

        print(f"\nTIMING")
        print("-" * 80)
        print(f"  First Trade: {analysis['first_trade']}")
        print(f"  Last Trade: {analysis['last_trade']}")

        print(f"\nPOSITION CHANGES (Last 10)")
        print("-" * 80)
        for change in analysis['position_changes'][-10:]:
            print(f"  #{change['trade_num']:3d} | {change['side']:4s} | "
                  f"Amt: {change['amount']:8.2f} | Price: {change['price']:.4f} | "
                  f"Pos: {change['position_before']:8.2f} → {change['position_after']:8.2f} | "
                  f"Δt: {change['time_since_last_seconds']}s")

        print(f"\n{'='*80}\n")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Analyze market-level trading patterns')
    parser.add_argument('address', help='Ethereum address to analyze')
    parser.add_argument('--market', '-m', help='Token ID to analyze')
    parser.add_argument('--clusters', '-c', action='store_true', help='Find trade clusters')
    parser.add_argument('--db', default='data/trades.db', help='Path to database')

    args = parser.parse_args()

    analyzer = MarketAnalyzer(args.db)

    if args.market:
        analyzer.generate_market_report(args.address, args.market)
    elif args.clusters:
        print(f"\nTRADE CLUSTERS FOR {args.address[:10]}...{args.address[-4:]}")
        print("="*80)
        clusters = analyzer.find_correlated_trades(args.address, time_window_seconds=60)

        for i, cluster in enumerate(clusters[:20], 1):
            print(f"\nCluster #{i}")
            print(f"  Time: {cluster['timestamp']}")
            print(f"  Trades: {cluster['trade_count']} across {cluster['unique_markets']} market(s)")
            print(f"  Composition: {cluster['buys']} buys, {cluster['sells']} sells")
            print(f"  Time span: {cluster['time_span_seconds']}s")
            print(f"  Pattern: {cluster['pattern']}")
    else:
        print("Please specify --market or --clusters")


if __name__ == '__main__':
    main()
