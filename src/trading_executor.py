"""
Polymarket 跟单执行器
使用 py-clob-client 执行市场订单
集成 Clash 代理管理，自动区域轮换
"""

import logging
import math
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

from clash_proxy_manager import get_proxy_manager, ClashProxyManager

logger = logging.getLogger(__name__)


class TradingExecutor:
    """Polymarket 跟单执行器（带 Clash 代理管理）"""

    CLOB_API_URL = "https://clob.polymarket.com"
    POLYGON_CHAIN_ID = 137

    def __init__(
        self,
        private_key: str,
        funder_address: str,
        database=None,
        min_shares: float = 5.0,
        min_usd: float = 1.0,
        retry_count: int = 3,
        retry_delay: float = 2.0,
        use_proxy: bool = True
    ):
        """
        初始化跟单执行器

        Args:
            private_key: Polygon 钱包私钥
            funder_address: 资金地址（你的钱包地址）
            database: 数据库实例，用于记录跟单状态
            min_shares: 最小跟单份额（默认 5）
            min_usd: 最小美元金额（默认 1.0）
            retry_count: 重试次数
            retry_delay: 重试延迟（秒）
            use_proxy: 是否使用 Clash 代理
        """
        self.private_key = private_key
        self.funder_address = funder_address
        self.database = database
        self.min_shares = min_shares
        self.min_usd = min_usd
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.use_proxy = use_proxy

        self.client: Optional[ClobClient] = None
        self._initialized = False

        # 代理管理器
        self.proxy_manager: Optional[ClashProxyManager] = None
        if use_proxy:
            self.proxy_manager = get_proxy_manager()

    def initialize(self) -> bool:
        """
        初始化 CLOB 客户端和 API 凭证
        如果启用代理，先确保代理连通

        Returns:
            bool: 初始化是否成功
        """
        if self._initialized:
            return True

        try:
            # 如果使用代理，先确保连通性
            if self.use_proxy and self.proxy_manager:
                logger.info("Checking proxy connectivity...")

                if not self.proxy_manager.ensure_connectivity():
                    logger.error("Cannot establish proxy connectivity")
                    return False

                # 设置环境变量代理（py-clob-client 会使用）
                self.proxy_manager.set_env_proxy()
                logger.info(f"Proxy enabled: {self.proxy_manager.CLASH_PROXY_HTTP}")

            logger.info("Initializing CLOB client...")

            # 创建客户端 (signature_type=2 for Gnosis Safe Proxy wallet)
            # 当用户通过 Polymarket UI 存款时，资金在 proxy wallet 中
            self.client = ClobClient(
                self.CLOB_API_URL,
                key=self.private_key,
                chain_id=self.POLYGON_CHAIN_ID,
                signature_type=2,  # Gnosis Safe Proxy (browser wallet)
                funder=self.funder_address  # Proxy wallet address from polymarket.com/settings
            )

            # 创建或派生 API 凭证
            api_creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(api_creds)

            self._initialized = True
            logger.info("CLOB client initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize CLOB client: {e}")

            # 如果初始化失败且使用代理，尝试切换区域
            if self.use_proxy and self.proxy_manager:
                logger.info("Attempting region rotation...")
                success, region = self.proxy_manager.rotate_region()
                if success:
                    logger.info(f"Switched to {region}, retrying initialization...")
                    # 递归重试一次
                    return self._retry_initialize()

            return False

    def _retry_initialize(self) -> bool:
        """重试初始化（切换区域后）"""
        try:
            self.proxy_manager.set_env_proxy()

            self.client = ClobClient(
                self.CLOB_API_URL,
                key=self.private_key,
                chain_id=self.POLYGON_CHAIN_ID,
                signature_type=2,
                funder=self.funder_address
            )

            api_creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(api_creds)

            self._initialized = True
            logger.info("CLOB client initialized successfully after region switch")
            return True

        except Exception as e:
            logger.error(f"Retry initialization failed: {e}")
            return False

    def get_current_price(self, token_id: str) -> Optional[float]:
        """
        获取 token 的当前价格

        Args:
            token_id: 代币 ID（十进制字符串）

        Returns:
            float: 当前价格，失败返回 None
        """
        try:
            if not self._initialized:
                self.initialize()

            # 从订单簿获取最佳价格
            orderbook = self.client.get_order_book(token_id)

            # OrderBookSummary 是对象，用属性访问
            if orderbook and hasattr(orderbook, 'asks') and orderbook.asks:
                best_ask = float(orderbook.asks[0].price)
                return best_ask

            # 尝试获取最后成交价
            try:
                last_trade = self.client.get_last_trade_price(token_id)
                if last_trade and 'price' in last_trade:
                    return float(last_trade['price'])
            except Exception:
                pass

            return None

        except Exception as e:
            logger.error(f"Failed to get price for token {token_id}: {e}")
            return None

    def calculate_min_order(self, token_id: str, side: str) -> Tuple[float, float]:
        """
        计算最小订单数量

        确保满足：
        1. 至少 5 shares
        2. 总金额 > $1

        Args:
            token_id: 代币 ID
            side: 'buy' 或 'sell'

        Returns:
            Tuple[shares, usd_amount]: 份额和美元金额
        """
        price = self.get_current_price(token_id)

        if price is None:
            logger.warning(f"Cannot get price for {token_id}, using min_shares={self.min_shares}")
            return self.min_shares, 0.0

        shares = self.min_shares
        usd_amount = shares * price

        # 如果金额不足 $1，增加份额
        if usd_amount < self.min_usd:
            shares = math.ceil(self.min_usd / price)
            usd_amount = shares * price

        logger.info(f"Calculated min order: {shares} shares @ ${price:.4f} = ${usd_amount:.2f}")
        return shares, usd_amount

    def execute_copy_trade(
        self,
        token_id: str,
        side: str,
        original_tx_hash: str = None
    ) -> Dict[str, Any]:
        """
        执行跟单交易

        Args:
            token_id: 代币 ID（十六进制或十进制）
            side: 'buy' 或 'sell'
            original_tx_hash: 原始交易哈希（用于记录）

        Returns:
            dict: 执行结果
        """
        result = {
            'success': False,
            'order_id': None,
            'token_id': token_id,
            'side': side,
            'amount': 0,
            'price': 0,
            'error': None,
            'original_tx_hash': original_tx_hash
        }

        # 重置区域追踪（每次新交易都从头开始尝试）
        self._regions_tried = set()

        try:
            # 确保已初始化
            if not self._initialized:
                if not self.initialize():
                    result['error'] = "Failed to initialize client"
                    self._save_copy_order(result)
                    return result

            # 转换 token_id 格式（如果是十六进制）
            if token_id.startswith('0x'):
                token_id_decimal = str(int(token_id, 16))
            else:
                token_id_decimal = token_id

            # 计算最小订单
            shares, usd_amount = self.calculate_min_order(token_id_decimal, side)
            result['amount'] = shares

            # 确定订单方向
            order_side = BUY if side.lower() == 'buy' else SELL

            # 对于买入，amount 是美元金额；对于卖出，amount 是份额
            if side.lower() == 'buy':
                order_amount = usd_amount
            else:
                order_amount = shares

            logger.info(f"[COPY] Executing {side} order: {order_amount} for token {token_id_decimal[:16]}...")
            logger.info(f"[COPY] Order details: shares={shares}, usd=${usd_amount:.2f}, proxy={self.use_proxy}")

            # 创建市场订单
            order_args = MarketOrderArgs(
                token_id=token_id_decimal,
                amount=order_amount,
                side=order_side,
            )

            # 带智能重试的执行（网络错误时自动切换区域）
            last_error = None
            total_attempts = self.retry_count * len(ClashProxyManager.REGIONS) if self.use_proxy else self.retry_count

            logger.info(f"[COPY] Starting execution with max {total_attempts} attempts")

            for attempt in range(total_attempts):
                try:
                    logger.debug(f"[COPY] Attempt {attempt + 1}/{total_attempts} - creating signed order...")

                    # 创建签名订单
                    signed_order = self.client.create_market_order(order_args)
                    logger.debug(f"[COPY] Signed order created, posting to CLOB...")

                    # 提交订单 (FOK - Fill or Kill)
                    response = self.client.post_order(signed_order, OrderType.FOK)

                    if response:
                        result['success'] = True
                        result['order_id'] = response.get('orderID') or response.get('id')
                        result['price'] = self.get_current_price(token_id_decimal) or 0

                        logger.info(f"[COPY] ✅ SUCCESS - Order ID: {result['order_id']}")
                        logger.info(f"[COPY] Filled: {shares} shares @ ${result['price']:.4f}")
                        break

                except Exception as e:
                    last_error = str(e)
                    error_lower = last_error.lower()
                    logger.warning(f"[COPY] ❌ Attempt {attempt + 1}/{total_attempts} FAILED: {e}")

                    # 检查是否是Cloudflare阻止 (403 + HTML响应)
                    is_cloudflare_block = (
                        "403" in last_error and
                        ("cloudflare" in error_lower or
                         "blocked" in error_lower or
                         "<!doctype html" in error_lower or
                         "security service" in error_lower)
                    )

                    # 检查是否是网络相关错误
                    network_errors = ["connection", "timeout", "proxy", "refused",
                                     "network", "unreachable", "ssl", "reset", "request exception"]
                    is_network_error = any(err in error_lower for err in network_errors)

                    # Cloudflare阻止需要立即轮换，不需要测试连通性
                    if is_cloudflare_block and self.use_proxy and self.proxy_manager:
                        logger.warning(f"[COPY] 🚫 Cloudflare blocking detected! Current region may be banned for POST requests")

                        # 检查是否已经尝试了所有区域
                        regions_tried = getattr(self, '_regions_tried', set())
                        current_region = self.proxy_manager.get_current_proxy()
                        if current_region:
                            regions_tried.add(current_region)
                        self._regions_tried = regions_tried

                        if len(regions_tried) >= len(ClashProxyManager.REGIONS):
                            logger.warning(f"[COPY] All {len(regions_tried)} regions tried and blocked by Cloudflare!")
                            logger.info("[COPY] Attempting Clash restart to get new IPs...")
                            if self.proxy_manager.restart_clash():
                                self._regions_tried = set()  # 重置尝试记录
                                logger.info("[COPY] Clash restarted, waiting 10s for IP refresh...")
                                time.sleep(10)
                                self.proxy_manager.set_env_proxy()
                                self._initialized = False
                                if self.initialize():
                                    continue
                            logger.error("[COPY] All proxy regions exhausted after restart!")
                            break

                        logger.info("[COPY] Rotating to next region...")
                        success, new_region = self.proxy_manager.rotate_region()

                        if success:
                            logger.info(f"[COPY] Switched to {new_region}, waiting 5s before retry...")
                            time.sleep(5)  # 等待让 Cloudflare 刷新 IP 信誉
                            self.proxy_manager.set_env_proxy()
                            # 重新初始化client以使用新代理
                            self._initialized = False
                            if not self.initialize():
                                logger.error("[COPY] Failed to reinitialize after region switch")
                                break
                            continue
                        else:
                            logger.error("[COPY] Region rotation failed!")
                            break

                    elif is_network_error and self.use_proxy and self.proxy_manager:
                        logger.info(f"[COPY] Network error detected, testing proxy connectivity...")
                        # 测试连通性
                        is_connected, conn_error = self.proxy_manager.test_connectivity()

                        if not is_connected:
                            logger.warning(f"[COPY] Proxy connectivity lost: {conn_error}")
                            logger.info("[COPY] Rotating to next region...")
                            success, new_region = self.proxy_manager.rotate_region()

                            if success:
                                logger.info(f"[COPY] Switched to {new_region}, retrying...")
                                self.proxy_manager.set_env_proxy()
                                continue
                            else:
                                # 所有区域都失败，尝试重启 Clash
                                logger.warning("[COPY] All proxy regions exhausted! Attempting Clash restart...")
                                if self.proxy_manager.restart_clash():
                                    logger.info("[COPY] Clash restarted successfully, retrying...")
                                    self.proxy_manager.set_env_proxy()
                                    # 重新初始化 client
                                    self._initialized = False
                                    if self.initialize():
                                        continue
                                logger.error("[COPY] Clash restart failed, giving up")
                                break
                        else:
                            logger.info("[COPY] Proxy still connected, error may be API-side")
                            # 如果连续多次 "connected but error"，可能 Clash 状态异常
                            if attempt > 0 and (attempt + 1) % 4 == 0:
                                logger.warning("[COPY] Multiple API errors with proxy connected, trying Clash restart...")
                                if self.proxy_manager.restart_clash():
                                    logger.info("[COPY] Clash restarted, retrying...")
                                    self.proxy_manager.set_env_proxy()
                                    self._initialized = False
                                    self.initialize()

                    if attempt < total_attempts - 1:
                        logger.debug(f"[COPY] Waiting {self.retry_delay}s before next attempt...")
                        time.sleep(self.retry_delay)

            if not result['success']:
                result['error'] = last_error or "Order execution failed"
                logger.error(f"[COPY] ❌ FINAL FAILURE after {total_attempts} attempts: {result['error']}")

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"[COPY] ❌ Copy trade exception: {e}")

        # 保存跟单记录
        self._save_copy_order(result)

        return result

    def _save_copy_order(self, result: Dict[str, Any]):
        """保存跟单订单到数据库"""
        if self.database is None:
            return

        try:
            status = 'success' if result['success'] else 'failed'

            self.database.save_copy_order(
                original_tx_hash=result.get('original_tx_hash'),
                token_id=result['token_id'],
                side=result['side'],
                amount=result['amount'],
                price=result.get('price', 0),
                order_id=result.get('order_id'),
                status=status,
                error_message=result.get('error')
            )

        except Exception as e:
            logger.error(f"Failed to save copy order: {e}")

    def get_balance(self) -> Optional[float]:
        """获取 USDC 余额"""
        try:
            if not self._initialized:
                self.initialize()

            # py-clob-client 可能没有直接获取余额的方法
            # 这里返回 None，实际使用时需要通过 web3 查询
            return None

        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return None
