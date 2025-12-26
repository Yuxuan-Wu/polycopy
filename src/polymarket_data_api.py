"""
Polymarket Data API Client
用于获取用户交易、持仓和活动数据
支持 MAKER/TAKER 交易类型检测
"""

import logging
import time
import requests
from datetime import datetime
from typing import List, Dict, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """交易数据结构"""
    id: str
    timestamp: int
    side: str  # 'BUY' or 'SELL'
    size: float
    price: float
    is_maker: bool  # True = 挂单被执行, False = 主动吃单
    title: str
    token_id: str
    tx_hash: Optional[str] = None

    @property
    def trade_type(self) -> str:
        """返回交易类型: MAKER 或 TAKER"""
        return 'MAKER' if self.is_maker else 'TAKER'

    @property
    def datetime(self) -> datetime:
        """返回交易时间"""
        return datetime.fromtimestamp(self.timestamp)


class PolymarketDataAPI:
    """
    Polymarket Data API 客户端

    提供公开 API 访问:
    - /trades - 用户交易历史 (含 MAKER/TAKER 标识)
    - /positions - 用户当前持仓
    - /activity - 用户活动 (交易、赎回等)
    """

    BASE_URL = "https://data-api.polymarket.com"

    def __init__(
        self,
        user_address: str,
        poll_interval: float = 5.0,
        use_proxy: bool = False
    ):
        """
        初始化 Data API 客户端

        Args:
            user_address: 要监控的用户地址
            poll_interval: 轮询间隔 (秒)
            use_proxy: 是否使用代理
        """
        self.user_address = user_address.lower()
        self.poll_interval = poll_interval
        self.use_proxy = use_proxy

        # 已处理的交易 ID 集合 (防止重复)
        self.processed_trade_ids: Set[str] = set()

        # 上次获取到的最新交易时间戳
        self.last_trade_timestamp: int = 0

        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PolyCopy/1.0',
            'Accept': 'application/json'
        })

    def _get_proxies(self) -> Optional[Dict[str, str]]:
        """获取代理配置"""
        if not self.use_proxy:
            return None
        return {
            'http': 'http://127.0.0.1:7890',
            'https': 'http://127.0.0.1:7890'
        }

    def get_trades(self, limit: int = 50) -> List[Trade]:
        """
        获取用户最近的交易列表

        Args:
            limit: 返回数量限制

        Returns:
            List[Trade]: 交易列表
        """
        try:
            url = f"{self.BASE_URL}/trades"
            params = {
                'user': self.user_address,
                'limit': limit
            }

            resp = self.session.get(
                url,
                params=params,
                proxies=self._get_proxies(),
                timeout=15
            )
            resp.raise_for_status()

            data = resp.json()
            trades = []

            for t in data:
                trade = Trade(
                    id=t.get('id', ''),
                    timestamp=t.get('timestamp', 0),
                    side=t.get('side', '').upper(),
                    size=float(t.get('size', 0)),
                    price=float(t.get('price', 0)),
                    is_maker=t.get('isMaker', False),
                    title=t.get('title', ''),
                    token_id=t.get('asset', '') or t.get('tokenId', ''),
                    tx_hash=t.get('transactionHash')
                )
                trades.append(trade)

            return trades

        except Exception as e:
            logger.error(f"[DATA-API] Failed to get trades: {e}")
            return []

    def get_new_trades(self) -> List[Trade]:
        """
        获取自上次检查以来的新交易

        Returns:
            List[Trade]: 新交易列表
        """
        all_trades = self.get_trades(limit=20)

        new_trades = []
        for trade in all_trades:
            # 跳过已处理的交易
            if trade.id in self.processed_trade_ids:
                continue

            # 跳过旧交易 (首次运行时初始化)
            if self.last_trade_timestamp == 0:
                # 首次运行，记录当前最新时间戳，不处理历史交易
                self.processed_trade_ids.add(trade.id)
                continue

            # 检查是否是新交易
            if trade.timestamp > self.last_trade_timestamp:
                new_trades.append(trade)
                self.processed_trade_ids.add(trade.id)

        # 更新最新时间戳
        if all_trades:
            max_ts = max(t.timestamp for t in all_trades)
            if max_ts > self.last_trade_timestamp:
                self.last_trade_timestamp = max_ts

        # 首次运行时设置初始时间戳
        if self.last_trade_timestamp == 0 and all_trades:
            self.last_trade_timestamp = max(t.timestamp for t in all_trades)
            logger.info(f"[DATA-API] Initialized with {len(all_trades)} historical trades")
            logger.info(f"[DATA-API] Latest trade at: {datetime.fromtimestamp(self.last_trade_timestamp)}")

        return new_trades

    def get_positions(self) -> List[Dict]:
        """
        获取用户当前持仓

        Returns:
            List[Dict]: 持仓列表
        """
        try:
            url = f"{self.BASE_URL}/positions"
            params = {'user': self.user_address}

            resp = self.session.get(
                url,
                params=params,
                proxies=self._get_proxies(),
                timeout=15
            )
            resp.raise_for_status()

            return resp.json()

        except Exception as e:
            logger.error(f"[DATA-API] Failed to get positions: {e}")
            return []

    def get_activity(self, limit: int = 20) -> List[Dict]:
        """
        获取用户活动 (交易、赎回等)

        Args:
            limit: 返回数量限制

        Returns:
            List[Dict]: 活动列表
        """
        try:
            url = f"{self.BASE_URL}/activity"
            params = {
                'user': self.user_address,
                'limit': limit
            }

            resp = self.session.get(
                url,
                params=params,
                proxies=self._get_proxies(),
                timeout=15
            )
            resp.raise_for_status()

            return resp.json()

        except Exception as e:
            logger.error(f"[DATA-API] Failed to get activity: {e}")
            return []

    def start_polling(self, callback):
        """
        开始轮询新交易

        Args:
            callback: 发现新交易时调用的回调函数
                      签名: callback(trade: Trade) -> None
        """
        logger.info(f"[DATA-API] Starting trade polling for {self.user_address}")
        logger.info(f"[DATA-API] Poll interval: {self.poll_interval}s")

        # 初始化 - 获取当前交易状态
        self.get_new_trades()

        while True:
            try:
                new_trades = self.get_new_trades()

                for trade in new_trades:
                    logger.info(
                        f"[DATA-API] 📊 NEW TRADE: {trade.trade_type} | "
                        f"{trade.side} {trade.size:.2f} @ ${trade.price:.4f} | "
                        f"{trade.title[:30]}..."
                    )

                    try:
                        callback(trade)
                    except Exception as e:
                        logger.error(f"[DATA-API] Callback error: {e}")

                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("[DATA-API] Polling stopped by user")
                break
            except Exception as e:
                logger.error(f"[DATA-API] Polling error: {e}")
                time.sleep(self.poll_interval * 2)  # 错误时延长等待


def test_api():
    """测试 API 功能"""
    address = "0x0f37Cb80DEe49D55B5F6d9E595D52591D6371410"
    api = PolymarketDataAPI(address)

    print(f"Testing Polymarket Data API for {address[:10]}...")

    # Test trades
    print("\n=== Recent Trades ===")
    trades = api.get_trades(limit=10)
    for t in trades[:5]:
        print(f"  {t.datetime} | {t.trade_type:5} | {t.side:4} | "
              f"{t.size:>10.2f} @ ${t.price:.4f} | {t.title[:35]}...")

    # Test positions
    print("\n=== Current Positions ===")
    positions = api.get_positions()
    for p in positions[:5]:
        print(f"  {p.get('size', 0):>12.2f} | {p.get('title', 'N/A')[:50]}")

    print("\n✓ API test complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_api()
