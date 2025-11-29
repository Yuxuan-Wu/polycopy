#!/usr/bin/env python3
"""
Trader Behavior Analysis Tool
Analyzes trading patterns, atomicity, and market positioning
"""
import sqlite3
import requests
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import sys

# Polymarket Gamma API endpoint
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"

# Cache for market metadata
market_cache = {}


class TraderAnalyzer:
    """Analyze trader behavior and patterns"""

    def __init__(self, db_path: str = "data/trades.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()

    def get_market_info(self, token_id: str) -> Optional[Dict]:
        """
        Fetch market information from Polymarket API
        Uses CLOB API to get token info
        """
        if token_id in market_cache:
            return market_cache[token_id]

        try:
            # Convert hex token_id to decimal
            token_id_decimal = int(token_id, 16) if token_id.startswith('0x') else token_id

            # Try CLOB API for token info
            url = f"{CLOB_API_BASE}/markets/{token_id_decimal}"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                market_cache[token_id] = data
                return data

            # Fallback: return basic info
            return {
                'token_id': token_id,
                'question': 'Unknown Market',
                'error': f'API returned {response.status_code}'
            }

        except Exception as e:
            return {
                'token_id': token_id,
                'question': 'Unknown Market',
                'error': str(e)
            }

    def get_trader_summary(self, address: str) -> Dict:
        """Get overall summary for a trader"""
        cursor = self.conn.cursor()

        # Basic stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN side = 'buy' THEN 1 ELSE 0 END) as buys,
                SUM(CASE WHEN side = 'sell' THEN 1 ELSE 0 END) as sells,
                COUNT(DISTINCT token_id) as unique_markets,
                SUM(CAST(amount AS REAL)) as total_volume,
                AVG(CAST(amount AS REAL)) as avg_trade_size,
                AVG(capture_delay_seconds) as avg_capture_delay,
                MIN(timestamp) as first_trade_ts,
                MAX(timestamp) as last_trade_ts,
                MAX(timestamp) - MIN(timestamp) as trading_period_seconds
            FROM trades
            WHERE from_address = ?
        """, (address,))

        row = cursor.fetchone()

        return {
            'address': address,
            'total_trades': row['total_trades'],
            'buys': row['buys'],
            'sells': row['sells'],
            'unique_markets': row['unique_markets'],
            'total_volume': round(row['total_volume'], 2),
            'avg_trade_size': round(row['avg_trade_size'], 2),
            'avg_capture_delay': round(row['avg_capture_delay'], 1),
            'first_trade': datetime.fromtimestamp(row['first_trade_ts']).isoformat(),
            'last_trade': datetime.fromtimestamp(row['last_trade_ts']).isoformat(),
            'trading_period_hours': round(row['trading_period_seconds'] / 3600, 1)
        }

    def calculate_trading_frequency(self, address: str) -> Dict:
        """Calculate trading frequency metrics"""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT timestamp, block_number
            FROM trades
            WHERE from_address = ?
            ORDER BY timestamp ASC
        """, (address,))

        trades = cursor.fetchall()

        if len(trades) < 2:
            return {
                'classification': 'insufficient_data',
                'trades_per_hour': 0,
                'avg_time_between_trades_minutes': 0
            }

        # Calculate time between trades
        intervals = []
        for i in range(1, len(trades)):
            interval = trades[i]['timestamp'] - trades[i-1]['timestamp']
            intervals.append(interval)

        avg_interval = sum(intervals) / len(intervals)

        # Calculate trades per hour
        total_period = trades[-1]['timestamp'] - trades[0]['timestamp']
        trades_per_hour = len(trades) / (total_period / 3600) if total_period > 0 else 0

        # Classification
        if trades_per_hour > 10:
            classification = 'high_frequency'
        elif trades_per_hour > 1:
            classification = 'active'
        elif trades_per_hour > 0.1:
            classification = 'moderate'
        else:
            classification = 'low_frequency'

        return {
            'classification': classification,
            'trades_per_hour': round(trades_per_hour, 3),
            'avg_time_between_trades_minutes': round(avg_interval / 60, 1),
            'median_time_between_trades_minutes': round(sorted(intervals)[len(intervals)//2] / 60, 1),
            'min_time_between_trades_seconds': min(intervals),
            'max_time_between_trades_seconds': max(intervals)
        }

    def analyze_market_atomicity(self, address: str) -> Dict:
        """
        Analyze if trader is atomic (only trades one side per market)
        Atomic = only buys OR only sells in each market, doesn't switch sides frequently
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                token_id,
                side,
                COUNT(*) as trade_count,
                MIN(timestamp) as first_trade,
                MAX(timestamp) as last_trade
            FROM trades
            WHERE from_address = ?
            GROUP BY token_id, side
            ORDER BY token_id, first_trade
        """, (address,))

        rows = cursor.fetchall()

        # Group by market
        markets = defaultdict(list)
        for row in rows:
            markets[row['token_id']].append({
                'side': row['side'],
                'count': row['trade_count'],
                'first_trade': row['first_trade'],
                'last_trade': row['last_trade']
            })

        atomic_markets = 0
        non_atomic_markets = 0
        position_flips = []

        for token_id, sides in markets.items():
            if len(sides) == 1:
                # Only one side traded - atomic
                atomic_markets += 1
            else:
                # Multiple sides - check for flips
                non_atomic_markets += 1

                # Sort by first trade time
                sides_sorted = sorted(sides, key=lambda x: x['first_trade'])

                # Count position flips
                for i in range(1, len(sides_sorted)):
                    if sides_sorted[i]['side'] != sides_sorted[i-1]['side']:
                        position_flips.append({
                            'token_id': token_id,
                            'from_side': sides_sorted[i-1]['side'],
                            'to_side': sides_sorted[i]['side'],
                            'flip_time': datetime.fromtimestamp(sides_sorted[i]['first_trade']).isoformat(),
                            'time_held_seconds': sides_sorted[i]['first_trade'] - sides_sorted[i-1]['first_trade']
                        })

        total_markets = atomic_markets + non_atomic_markets
        atomicity_ratio = atomic_markets / total_markets if total_markets > 0 else 0

        # Classification
        if atomicity_ratio >= 0.9:
            classification = 'highly_atomic'
        elif atomicity_ratio >= 0.7:
            classification = 'mostly_atomic'
        elif atomicity_ratio >= 0.5:
            classification = 'mixed'
        else:
            classification = 'non_atomic'

        return {
            'classification': classification,
            'atomic_markets': atomic_markets,
            'non_atomic_markets': non_atomic_markets,
            'atomicity_ratio': round(atomicity_ratio, 3),
            'total_position_flips': len(position_flips),
            'avg_hold_time_before_flip_hours': round(
                sum(f['time_held_seconds'] for f in position_flips) / len(position_flips) / 3600, 1
            ) if position_flips else 0,
            'position_flips': position_flips[:5]  # Return first 5 flips as examples
        }

    def analyze_position_management(self, address: str) -> Dict:
        """Analyze how trader manages positions (entry/exit patterns)"""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                token_id,
                side,
                CAST(amount AS REAL) as amount,
                CAST(price AS REAL) as price,
                timestamp,
                block_number
            FROM trades
            WHERE from_address = ?
            ORDER BY token_id, timestamp
        """, (address,))

        rows = cursor.fetchall()

        # Group by market and calculate net position changes
        markets_analysis = defaultdict(lambda: {
            'trades': [],
            'net_position': 0,
            'total_buys': 0,
            'total_sells': 0,
            'rebalances': 0
        })

        for row in rows:
            token_id = row['token_id']
            side = row['side']
            amount = row['amount']

            markets_analysis[token_id]['trades'].append({
                'side': side,
                'amount': amount,
                'price': row['price'],
                'timestamp': row['timestamp']
            })

            if side == 'buy':
                markets_analysis[token_id]['net_position'] += amount
                markets_analysis[token_id]['total_buys'] += amount
            elif side == 'sell':
                markets_analysis[token_id]['net_position'] -= amount
                markets_analysis[token_id]['total_sells'] += amount

        # Calculate rebalancing frequency
        total_rebalances = 0
        markets_with_rebalancing = 0

        for token_id, data in markets_analysis.items():
            trades = data['trades']
            if len(trades) > 1:
                # Check for direction changes
                for i in range(1, len(trades)):
                    if trades[i]['side'] != trades[i-1]['side']:
                        data['rebalances'] += 1
                        total_rebalances += 1

                if data['rebalances'] > 0:
                    markets_with_rebalancing += 1

        total_markets = len(markets_analysis)
        rebalancing_ratio = markets_with_rebalancing / total_markets if total_markets > 0 else 0

        # Classification
        if rebalancing_ratio < 0.2:
            rebalancing_style = 'buy_and_hold'
        elif rebalancing_ratio < 0.5:
            rebalancing_style = 'occasional_rebalancer'
        else:
            rebalancing_style = 'active_rebalancer'

        return {
            'rebalancing_style': rebalancing_style,
            'total_markets_traded': total_markets,
            'markets_with_rebalancing': markets_with_rebalancing,
            'rebalancing_ratio': round(rebalancing_ratio, 3),
            'total_rebalances': total_rebalances,
            'avg_rebalances_per_market': round(total_rebalances / total_markets, 2) if total_markets > 0 else 0
        }

    def get_market_breakdown(self, address: str, limit: int = 10) -> List[Dict]:
        """Get detailed breakdown by market"""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                token_id,
                COUNT(*) as trade_count,
                SUM(CASE WHEN side = 'buy' THEN 1 ELSE 0 END) as buys,
                SUM(CASE WHEN side = 'sell' THEN 1 ELSE 0 END) as sells,
                SUM(CAST(amount AS REAL)) as total_volume,
                AVG(CAST(price AS REAL)) as avg_price,
                MIN(timestamp) as first_trade,
                MAX(timestamp) as last_trade
            FROM trades
            WHERE from_address = ?
            GROUP BY token_id
            ORDER BY trade_count DESC
            LIMIT ?
        """, (address, limit))

        markets = []
        for row in cursor.fetchall():
            is_atomic = (row['buys'] == 0 or row['sells'] == 0)

            markets.append({
                'token_id': row['token_id'][:20] + '...',  # Truncate for display
                'trade_count': row['trade_count'],
                'buys': row['buys'],
                'sells': row['sells'],
                'is_atomic': is_atomic,
                'total_volume': round(row['total_volume'], 2),
                'avg_price': round(row['avg_price'], 3),
                'first_trade': datetime.fromtimestamp(row['first_trade']).strftime('%Y-%m-%d %H:%M'),
                'last_trade': datetime.fromtimestamp(row['last_trade']).strftime('%Y-%m-%d %H:%M')
            })

        return markets

    def generate_report(self, address: str, output_file: Optional[str] = None) -> str:
        """Generate comprehensive analysis report"""
        print(f"\n{'='*80}")
        print(f"TRADER BEHAVIOR ANALYSIS REPORT")
        print(f"{'='*80}\n")

        # 1. Summary
        print("1. TRADER SUMMARY")
        print("-" * 80)
        summary = self.get_trader_summary(address)
        for key, value in summary.items():
            print(f"  {key:30s}: {value}")

        # 2. Trading Frequency
        print(f"\n2. TRADING FREQUENCY ANALYSIS")
        print("-" * 80)
        frequency = self.calculate_trading_frequency(address)
        for key, value in frequency.items():
            print(f"  {key:30s}: {value}")

        # 3. Atomicity Analysis
        print(f"\n3. MARKET ATOMICITY ANALYSIS")
        print("-" * 80)
        atomicity = self.analyze_market_atomicity(address)

        print(f"  Classification: {atomicity['classification']}")
        print(f"  Atomic Markets: {atomicity['atomic_markets']} ({atomicity['atomicity_ratio']*100:.1f}%)")
        print(f"  Non-Atomic Markets: {atomicity['non_atomic_markets']}")
        print(f"  Total Position Flips: {atomicity['total_position_flips']}")

        if atomicity['position_flips']:
            print(f"\n  Example Position Flips:")
            for flip in atomicity['position_flips']:
                print(f"    - {flip['from_side']} → {flip['to_side']} after {flip['time_held_seconds']/3600:.1f}h")

        # 4. Position Management
        print(f"\n4. POSITION MANAGEMENT ANALYSIS")
        print("-" * 80)
        position = self.analyze_position_management(address)
        for key, value in position.items():
            print(f"  {key:30s}: {value}")

        # 5. Top Markets
        print(f"\n5. TOP MARKETS BY ACTIVITY")
        print("-" * 80)
        markets = self.get_market_breakdown(address, limit=10)

        print(f"  {'Token ID':<25} {'Trades':>7} {'Buys':>5} {'Sells':>6} {'Atomic':>7} {'Volume':>10}")
        print(f"  {'-'*25} {'-'*7} {'-'*5} {'-'*6} {'-'*7} {'-'*10}")
        for m in markets:
            atomic_str = "YES" if m['is_atomic'] else "NO"
            print(f"  {m['token_id']:<25} {m['trade_count']:>7} {m['buys']:>5} {m['sells']:>6} {atomic_str:>7} {m['total_volume']:>10.1f}")

        # 6. Overall Classification
        print(f"\n6. OVERALL TRADER CLASSIFICATION")
        print("-" * 80)

        # Determine overall profile
        is_high_freq = frequency['classification'] in ['high_frequency', 'active']
        is_atomic = atomicity['classification'] in ['highly_atomic', 'mostly_atomic']
        is_low_rebalancing = position['rebalancing_style'] == 'buy_and_hold'

        if is_atomic and is_low_rebalancing:
            profile = "DIRECTIONAL TRADER (Atomic, Low Rebalancing)"
            description = "Takes single-sided positions and holds them. Likely has strong conviction."
        elif is_high_freq and not is_atomic:
            profile = "ACTIVE MARKET MAKER / ARBITRAGEUR"
            description = "High frequency trading on both sides. Likely providing liquidity or arbitraging."
        elif is_atomic and is_high_freq:
            profile = "MOMENTUM TRADER"
            description = "High frequency but directional. Likely trading on short-term signals."
        else:
            profile = "BALANCED TRADER"
            description = "Mix of directional and hedging strategies."

        print(f"  Profile: {profile}")
        print(f"  Description: {description}")

        print(f"\n{'='*80}\n")

        # Save to file if specified
        if output_file:
            # TODO: Implement file save
            pass

        return profile


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Analyze trader behavior')
    parser.add_argument('address', help='Ethereum address to analyze')
    parser.add_argument('--db', default='data/trades.db', help='Path to database')
    parser.add_argument('--output', '-o', help='Output file for report')

    args = parser.parse_args()

    analyzer = TraderAnalyzer(args.db)
    analyzer.generate_report(args.address, args.output)


if __name__ == '__main__':
    main()
