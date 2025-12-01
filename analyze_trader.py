#!/usr/bin/env python3
"""
Comprehensive Trader Analysis and Copy Trading Feasibility Tool
Analyzes trader behavior, performance, and provides copy trading recommendations
"""
import sys
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import DatabaseManager
from metadata_manager import MetadataManager
from gamma_client import GammaClient


class TraderAnalyzer:
    """Comprehensive trader analysis"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.db_manager = DatabaseManager(db_path, 'data/trades.csv', auto_export=False)
        self.gamma_client = GammaClient(timeout=30)
        self.metadata_manager = MetadataManager(db_path, self.gamma_client)

    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()

    def get_trader_overview(self, address: str) -> Dict:
        """Get comprehensive trader overview"""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN side = 'buy' THEN 1 ELSE 0 END) as buys,
                SUM(CASE WHEN side = 'sell' THEN 1 ELSE 0 END) as sells,
                COUNT(DISTINCT token_id) as unique_markets,
                MIN(timestamp) as first_trade,
                MAX(timestamp) as last_trade
            FROM trades
            WHERE from_address = ?
        """, (address,))

        row = cursor.fetchone()

        trading_period_days = (row['last_trade'] - row['first_trade']) / 86400 if row['first_trade'] else 0

        return {
            'address': address,
            'total_trades': row['total_trades'],
            'buys': row['buys'],
            'sells': row['sells'],
            'unique_markets': row['unique_markets'],
            'first_trade': datetime.fromtimestamp(row['first_trade']) if row['first_trade'] else None,
            'last_trade': datetime.fromtimestamp(row['last_trade']) if row['last_trade'] else None,
            'trading_period_days': trading_period_days,
            'avg_trades_per_day': row['total_trades'] / trading_period_days if trading_period_days > 0 else 0
        }

    def get_position_performance(self, address: str) -> Dict:
        """Analyze position performance"""
        positions = self.db_manager.get_all_positions(address)

        if not positions:
            return {'error': 'No positions found'}

        total_positions = len(positions)
        active_positions = sum(1 for p in positions if p['status'] == 'active')
        settled_win = sum(1 for p in positions if p['status'] == 'settled_win')
        settled_loss = sum(1 for p in positions if p['status'] == 'settled_loss')
        closed_positions = sum(1 for p in positions if p['status'] == 'closed')

        total_realized_pnl = sum(p['realized_pnl'] for p in positions)
        total_invested = sum(p['total_buy_value'] for p in positions)
        total_returned = sum(p['total_sell_value'] for p in positions)

        # Calculate win rate from settled positions
        settled_total = settled_win + settled_loss
        win_rate = (settled_win / settled_total * 100) if settled_total > 0 else 0

        # Calculate ROI
        roi = ((total_returned - total_invested) / total_invested * 100) if total_invested > 0 else 0

        return {
            'total_positions': total_positions,
            'active': active_positions,
            'closed': closed_positions,
            'settled_win': settled_win,
            'settled_loss': settled_loss,
            'win_rate': win_rate,
            'total_realized_pnl': total_realized_pnl,
            'total_invested': total_invested,
            'total_returned': total_returned,
            'roi_percent': roi
        }

    def analyze_trading_patterns(self, address: str) -> Dict:
        """Analyze trading patterns and behavior"""
        cursor = self.conn.cursor()

        # Get trades grouped by market
        cursor.execute("""
            SELECT
                token_id,
                COUNT(*) as trade_count,
                SUM(CASE WHEN side = 'buy' THEN 1 ELSE 0 END) as buys,
                SUM(CASE WHEN side = 'sell' THEN 1 ELSE 0 END) as sells,
                AVG(CAST(price AS REAL)) as avg_price
            FROM trades
            WHERE from_address = ?
            GROUP BY token_id
        """, (address,))

        markets = [dict(row) for row in cursor.fetchall()]

        # Calculate atomicity (single-sided trading)
        atomic_markets = sum(1 for m in markets if m['buys'] == 0 or m['sells'] == 0)
        atomicity_ratio = (atomic_markets / len(markets) * 100) if markets else 0

        # Analyze time between trades
        cursor.execute("""
            SELECT timestamp
            FROM trades
            WHERE from_address = ?
            ORDER BY timestamp ASC
        """, (address,))

        timestamps = [row['timestamp'] for row in cursor.fetchall()]
        time_diffs = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)] if len(timestamps) > 1 else []

        avg_time_between_trades = sum(time_diffs) / len(time_diffs) if time_diffs else 0

        # Classify trading frequency
        if avg_time_between_trades < 3600:  # < 1 hour
            frequency_class = "high_frequency"
        elif avg_time_between_trades < 86400:  # < 1 day
            frequency_class = "active"
        elif avg_time_between_trades < 604800:  # < 1 week
            frequency_class = "moderate"
        else:
            frequency_class = "low_frequency"

        # Classify trader type
        buy_sell_ratio = markets[0]['buys'] / markets[0]['sells'] if markets and markets[0]['sells'] > 0 else float('inf')

        if atomicity_ratio >= 70:
            if frequency_class in ['high_frequency', 'active']:
                trader_type = "MOMENTUM_TRADER"
            else:
                trader_type = "DIRECTIONAL_TRADER"
        else:
            if frequency_class == 'high_frequency':
                trader_type = "MARKET_MAKER"
            else:
                trader_type = "BALANCED_TRADER"

        return {
            'total_markets_traded': len(markets),
            'atomic_markets': atomic_markets,
            'atomicity_ratio': atomicity_ratio,
            'avg_time_between_trades_seconds': avg_time_between_trades,
            'frequency_class': frequency_class,
            'trader_type': trader_type
        }

    def calculate_copy_trading_score(self, address: str) -> Dict:
        """
        Calculate copy trading feasibility score (0-100)
        Based on multiple factors
        """
        overview = self.get_trader_overview(address)
        performance = self.get_position_performance(address)
        patterns = self.analyze_trading_patterns(address)

        if 'error' in performance:
            return {'score': 0, 'recommendation': 'NOT_RECOMMENDED', 'reason': 'No position data available'}

        score = 0
        factors = []

        # 1. Win Rate (0-30 points)
        win_rate = performance['win_rate']
        if win_rate >= 70:
            score += 30
            factors.append(f"✅ Excellent win rate ({win_rate:.1f}%)")
        elif win_rate >= 60:
            score += 20
            factors.append(f"✓ Good win rate ({win_rate:.1f}%)")
        elif win_rate >= 50:
            score += 10
            factors.append(f"~ Fair win rate ({win_rate:.1f}%)")
        else:
            factors.append(f"❌ Poor win rate ({win_rate:.1f}%)")

        # 2. ROI (0-25 points)
        roi = performance['roi_percent']
        if roi >= 20:
            score += 25
            factors.append(f"✅ Strong ROI ({roi:+.1f}%)")
        elif roi >= 10:
            score += 20
            factors.append(f"✓ Positive ROI ({roi:+.1f}%)")
        elif roi >= 0:
            score += 10
            factors.append(f"~ Break-even ROI ({roi:+.1f}%)")
        else:
            factors.append(f"❌ Negative ROI ({roi:+.1f}%)")

        # 3. Sample Size (0-20 points)
        settled_total = performance['settled_win'] + performance['settled_loss']
        if settled_total >= 20:
            score += 20
            factors.append(f"✅ Large sample size ({settled_total} settled)")
        elif settled_total >= 10:
            score += 15
            factors.append(f"✓ Good sample size ({settled_total} settled)")
        elif settled_total >= 5:
            score += 10
            factors.append(f"~ Small sample size ({settled_total} settled)")
        else:
            score += 5
            factors.append(f"⚠️  Very small sample size ({settled_total} settled)")

        # 4. Trading Activity (0-15 points)
        trades_per_day = overview['avg_trades_per_day']
        if trades_per_day >= 5:
            score += 15
            factors.append(f"✅ Very active ({trades_per_day:.1f} trades/day)")
        elif trades_per_day >= 1:
            score += 12
            factors.append(f"✓ Active ({trades_per_day:.1f} trades/day)")
        elif trades_per_day >= 0.5:
            score += 8
            factors.append(f"~ Moderate activity ({trades_per_day:.1f} trades/day)")
        else:
            score += 5
            factors.append(f"⚠️  Low activity ({trades_per_day:.1f} trades/day)")

        # 5. Consistency (0-10 points)
        atomicity = patterns['atomicity_ratio']
        if atomicity >= 80:
            score += 10
            factors.append(f"✅ High atomicity ({atomicity:.1f}%) - Strong conviction")
        elif atomicity >= 60:
            score += 7
            factors.append(f"✓ Good atomicity ({atomicity:.1f}%)")
        else:
            score += 5
            factors.append(f"~ Mixed strategy ({atomicity:.1f}% atomicity)")

        # Determine recommendation
        if score >= 75:
            recommendation = "HIGHLY_RECOMMENDED"
            confidence = "High"
        elif score >= 60:
            recommendation = "RECOMMENDED"
            confidence = "Medium-High"
        elif score >= 45:
            recommendation = "CAUTIOUSLY_RECOMMENDED"
            confidence = "Medium"
        elif score >= 30:
            recommendation = "NOT_RECOMMENDED"
            confidence = "Low"
        else:
            recommendation = "STRONGLY_NOT_RECOMMENDED"
            confidence = "Very Low"

        return {
            'score': score,
            'recommendation': recommendation,
            'confidence': confidence,
            'factors': factors,
            'trader_type': patterns['trader_type']
        }

    def get_top_markets(self, address: str, limit: int = 5) -> List[Dict]:
        """Get top markets by trade count"""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                token_id,
                COUNT(*) as trade_count,
                SUM(CASE WHEN side = 'buy' THEN 1 ELSE 0 END) as buys,
                SUM(CASE WHEN side = 'sell' THEN 1 ELSE 0 END) as sells,
                AVG(CAST(price AS REAL)) as avg_price
            FROM trades
            WHERE from_address = ?
            GROUP BY token_id
            ORDER BY trade_count DESC
            LIMIT ?
        """, (address, limit))

        markets = []
        for row in cursor.fetchall():
            token_id = row['token_id']
            market_info = self.metadata_manager.get_market_for_token(token_id)

            markets.append({
                'token_id': token_id,
                'question': market_info.get('question', 'N/A') if market_info else 'N/A',
                'outcome': market_info.get('outcome_name', 'N/A') if market_info else 'N/A',
                'trade_count': row['trade_count'],
                'buys': row['buys'],
                'sells': row['sells'],
                'avg_price': row['avg_price']
            })

        return markets

    def generate_full_report(self, address: str):
        """Generate comprehensive analysis report"""
        print("=" * 100)
        print(f"{'📊 TRADER ANALYSIS & COPY TRADING FEASIBILITY REPORT':^100}")
        print("=" * 100)
        print(f"Address: {address}")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Overview
        overview = self.get_trader_overview(address)
        print("📈 TRADER OVERVIEW")
        print("-" * 100)
        print(f"Total Trades:        {overview['total_trades']}")
        print(f"Buy Trades:          {overview['buys']}")
        print(f"Sell Trades:         {overview['sells']}")
        print(f"Unique Markets:      {overview['unique_markets']}")
        print(f"First Trade:         {overview['first_trade'].strftime('%Y-%m-%d %H:%M:%S') if overview['first_trade'] else 'N/A'}")
        print(f"Last Trade:          {overview['last_trade'].strftime('%Y-%m-%d %H:%M:%S') if overview['last_trade'] else 'N/A'}")
        print(f"Trading Period:      {overview['trading_period_days']:.1f} days")
        print(f"Avg Trades/Day:      {overview['avg_trades_per_day']:.2f}")
        print()

        # Performance
        performance = self.get_position_performance(address)
        if 'error' not in performance:
            print("💰 PERFORMANCE METRICS")
            print("-" * 100)
            print(f"Total Positions:     {performance['total_positions']}")
            print(f"  🟢 Active:         {performance['active']}")
            print(f"  ⚪ Closed:         {performance['closed']}")
            print(f"  🟩 Settled (Win):  {performance['settled_win']}")
            print(f"  🟥 Settled (Loss): {performance['settled_loss']}")
            print()
            print(f"Win Rate:            {performance['win_rate']:.1f}%")
            print(f"Total Invested:      ${performance['total_invested']:.2f}")
            print(f"Total Returned:      ${performance['total_returned']:.2f}")
            print(f"Realized P&L:        ${performance['total_realized_pnl']:+.2f}")
            print(f"ROI:                 {performance['roi_percent']:+.1f}%")
            print()

        # Trading Patterns
        patterns = self.analyze_trading_patterns(address)
        print("🎯 TRADING PATTERNS")
        print("-" * 100)
        print(f"Markets Traded:      {patterns['total_markets_traded']}")
        print(f"Atomic Markets:      {patterns['atomic_markets']} ({patterns['atomicity_ratio']:.1f}%)")
        print(f"Avg Time Between:    {patterns['avg_time_between_trades_seconds']:.0f}s ({patterns['avg_time_between_trades_seconds']/3600:.1f}h)")
        print(f"Frequency Class:     {patterns['frequency_class'].replace('_', ' ').upper()}")
        print(f"Trader Type:         {patterns['trader_type']}")
        print()

        # Copy Trading Score
        score_data = self.calculate_copy_trading_score(address)
        print("🎓 COPY TRADING FEASIBILITY SCORE")
        print("-" * 100)
        print(f"Score: {score_data['score']}/100")
        print(f"Recommendation: {score_data['recommendation'].replace('_', ' ')}")
        print(f"Confidence: {score_data['confidence']}")
        print()
        print("Factors:")
        for factor in score_data['factors']:
            print(f"  {factor}")
        print()

        # Score interpretation
        print("📊 SCORE INTERPRETATION")
        print("-" * 100)
        if score_data['score'] >= 75:
            print("🟢 HIGH CONFIDENCE - This trader shows strong performance and consistency.")
            print("   Recommended for copy trading with moderate position sizing.")
        elif score_data['score'] >= 60:
            print("🟡 MEDIUM CONFIDENCE - This trader shows promising results.")
            print("   Consider copy trading with reduced position sizing and close monitoring.")
        elif score_data['score'] >= 45:
            print("🟠 LOW CONFIDENCE - This trader has mixed results.")
            print("   Only for experienced traders willing to accept higher risk.")
        else:
            print("🔴 NOT RECOMMENDED - This trader does not show sufficient evidence of profitability.")
            print("   Avoid copy trading or conduct further research.")
        print()

        # Top Markets
        print("🏆 TOP 5 MARKETS BY ACTIVITY")
        print("-" * 100)
        top_markets = self.get_top_markets(address, limit=5)
        for i, market in enumerate(top_markets, 1):
            print(f"{i}. {market['question']}")
            print(f"   Outcome: {market['outcome']} | Trades: {market['trade_count']} "
                  f"(Buy: {market['buys']}, Sell: {market['sells']}) | Avg Price: ${market['avg_price']:.4f}")
            print()

        print("=" * 100)


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Comprehensive trader analysis and copy trading feasibility')
    parser.add_argument('--address', type=str, help='Trader address to analyze')
    parser.add_argument('--quick', action='store_true', help='Show quick summary only')

    args = parser.parse_args()

    db_path = 'data/trades.db'

    # Get address from args or database
    if args.address:
        address = args.address
    else:
        # Get first address from database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT from_address FROM trades LIMIT 1")
        result = cursor.fetchone()
        conn.close()

        if not result:
            print("No trades found in database")
            return

        address = result[0]
        print(f"Analyzing default address: {address}\n")

    # Initialize analyzer
    analyzer = TraderAnalyzer(db_path)

    if args.quick:
        # Quick summary
        score_data = analyzer.calculate_copy_trading_score(address)
        print(f"\n{'🎯 QUICK ANALYSIS':^60}")
        print("=" * 60)
        print(f"Address: {address[:10]}...{address[-8:]}")
        print(f"Score: {score_data['score']}/100")
        print(f"Recommendation: {score_data['recommendation'].replace('_', ' ')}")
        print(f"Trader Type: {score_data['trader_type']}")
        print("=" * 60)
    else:
        # Full report
        analyzer.generate_full_report(address)


if __name__ == '__main__':
    main()
