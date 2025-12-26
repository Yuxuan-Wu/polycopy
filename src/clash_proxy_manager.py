"""
Clash Proxy Manager for Polymarket Copy Trading
Manages proxy connectivity and region rotation
"""

import logging
import os
import subprocess
import time
import requests
from typing import List, Optional, Dict, Tuple

logger = logging.getLogger(__name__)


class ClashProxyManager:
    """
    Clash代理管理器
    - 启动/检测Clash进程
    - 通过API切换节点
    - 检测连通性
    - 自动区域轮换
    """

    # Clash API配置
    CLASH_API_URL = "http://127.0.0.1:9091"
    CLASH_PROXY_HTTP = "http://127.0.0.1:7890"
    CLASH_PROXY_SOCKS = "socks5://127.0.0.1:7891"

    # Polymarket API (用于连通性测试)
    POLYMARKET_TEST_URL = "https://clob.polymarket.com/time"

    # 区域优先级 (不包含美国) - 日本最稳定，放第一位
    REGIONS = ["日本", "新加坡", "台湾", "香港"]

    # 区域对应的proxy-group名称
    REGION_GROUPS = {
        "新加坡": "🇸🇬 新加坡节点",
        "日本": "🇯🇵 日本节点",
        "台湾": "🇹🇼 台湾节点",
        "香港": "🇭🇰 香港节点",
    }

    def __init__(
        self,
        config_path: str = "/root/.config/clash/config.yaml",
        test_timeout: int = 10,
        max_retries: int = 3
    ):
        """
        初始化Clash代理管理器

        Args:
            config_path: Clash配置文件路径
            test_timeout: 连通性测试超时（秒）
            max_retries: 最大重试次数
        """
        self.config_path = config_path
        self.test_timeout = test_timeout
        self.max_retries = max_retries
        self.current_region_index = 0
        self._clash_process = None

    def start_clash(self) -> bool:
        """
        启动Clash进程

        Returns:
            bool: 启动是否成功
        """
        # 检查是否已经在运行
        if self.is_clash_running():
            logger.info("Clash is already running")
            return True

        try:
            logger.info("Starting Clash process...")

            # 启动Clash后台进程
            self._clash_process = subprocess.Popen(
                ["clash", "-d", os.path.dirname(self.config_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

            # 等待启动
            time.sleep(3)

            if self.is_clash_running():
                logger.info("Clash started successfully")
                return True
            else:
                logger.error("Clash process exited unexpectedly")
                return False

        except Exception as e:
            logger.error(f"Failed to start Clash: {e}")
            return False

    def is_clash_running(self) -> bool:
        """
        检查Clash是否在运行（并检测僵尸进程）

        Returns:
            bool: Clash是否在运行
        """
        try:
            # 首先检查是否有僵尸进程
            if self._has_zombie_clash():
                logger.warning("[CLASH] Detected zombie Clash process!")
                return False

            # 检查API是否响应 (must bypass proxy for localhost)
            resp = requests.get(
                f"{self.CLASH_API_URL}/version",
                timeout=3,
                proxies={}  # Force direct connection
            )
            return resp.status_code == 200
        except:
            # 尝试检查进程（排除僵尸）
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "clash"],
                    capture_output=True,
                    timeout=3
                )
                if result.returncode == 0:
                    # 再次检查是否是僵尸进程
                    if self._has_zombie_clash():
                        return False
                    return True
                return False
            except:
                return False

    def _has_zombie_clash(self) -> bool:
        """检查是否存在僵尸Clash进程"""
        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                timeout=5
            )
            for line in result.stdout.split('\n'):
                if 'clash' in line.lower() and '<defunct>' in line:
                    return True
            return False
        except:
            return False

    def cleanup_zombie(self):
        """清理僵尸进程"""
        try:
            # 找到僵尸进程的PID
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                timeout=5
            )
            for line in result.stdout.split('\n'):
                if 'clash' in line.lower() and '<defunct>' in line:
                    parts = line.split()
                    if len(parts) > 1:
                        pid = parts[1]
                        logger.info(f"[CLASH] Cleaning up zombie process PID: {pid}")
                        subprocess.run(["kill", "-9", pid], timeout=3, capture_output=True)
            time.sleep(1)
        except Exception as e:
            logger.warning(f"[CLASH] Failed to cleanup zombie: {e}")

    def stop_clash(self):
        """停止Clash进程"""
        try:
            subprocess.run(["pkill", "-f", "clash"], timeout=5)
            time.sleep(1)
            logger.info("Clash stopped")
        except Exception as e:
            logger.warning(f"Failed to stop Clash: {e}")

    def restart_clash(self) -> bool:
        """
        重启Clash进程并确保连通性

        Returns:
            bool: 重启是否成功
        """
        logger.info("=" * 50)
        logger.info("[CLASH] 🔄 RESTARTING CLASH PROCESS")
        logger.info("=" * 50)

        try:
            # 先清理僵尸进程
            if self._has_zombie_clash():
                logger.info("[CLASH] Cleaning up zombie processes first...")
                self.cleanup_zombie()

            # 停止现有进程
            logger.info("[CLASH] Stopping existing Clash process...")
            self.stop_clash()
            time.sleep(2)

            # 确保进程已完全停止
            for _ in range(3):
                if not self.is_clash_running():
                    break
                logger.info("[CLASH] Waiting for Clash to fully stop...")
                subprocess.run(["pkill", "-9", "-f", "clash"], timeout=5, capture_output=True)
                time.sleep(1)

            # 启动新进程
            logger.info("[CLASH] Starting new Clash process...")
            clash_dir = os.path.dirname(self.config_path)
            self._clash_process = subprocess.Popen(
                ["/usr/local/bin/clash", "-d", clash_dir],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

            # 等待启动
            time.sleep(4)

            # 验证启动成功
            if not self.is_clash_running():
                logger.error("[CLASH] ❌ Clash failed to start after restart")
                return False

            logger.info("[CLASH] ✓ Clash process started")

            # 测试并选择最佳区域
            logger.info("[CLASH] Testing connectivity to all regions...")
            for region in self.REGIONS:
                if self.switch_to_region(region):
                    logger.info(f"[CLASH] ✓ Restart complete, using region: {region}")
                    logger.info("=" * 50)
                    return True

            logger.error("[CLASH] ❌ No working region found after restart")
            logger.info("=" * 50)
            return False

        except Exception as e:
            logger.error(f"[CLASH] ❌ Restart failed with error: {e}")
            logger.info("=" * 50)
            return False

    def test_connectivity(self, timeout: int = None) -> Tuple[bool, Optional[str]]:
        """
        测试代理连通性（访问Polymarket API）

        Args:
            timeout: 超时时间（秒）

        Returns:
            Tuple[bool, Optional[str]]: (是否连通, 错误信息)
        """
        timeout = timeout or self.test_timeout

        try:
            proxies = {
                "http": self.CLASH_PROXY_HTTP,
                "https": self.CLASH_PROXY_HTTP,
            }

            logger.debug(f"[DIAG] Testing connectivity to {self.POLYMARKET_TEST_URL} via {self.CLASH_PROXY_HTTP}")

            resp = requests.get(
                self.POLYMARKET_TEST_URL,
                proxies=proxies,
                timeout=timeout
            )

            if resp.status_code == 200:
                logger.info(f"[DIAG] Proxy connectivity OK - Response: {resp.json()}")
                return True, None
            else:
                logger.warning(f"[DIAG] Proxy connectivity FAIL - HTTP {resp.status_code}")
                return False, f"HTTP {resp.status_code}"

        except requests.exceptions.Timeout:
            logger.warning(f"[DIAG] Proxy connectivity FAIL - Timeout after {timeout}s")
            return False, "Connection timeout"
        except requests.exceptions.ProxyError as e:
            logger.warning(f"[DIAG] Proxy connectivity FAIL - ProxyError: {e}")
            return False, f"Proxy error: {e}"
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"[DIAG] Proxy connectivity FAIL - ConnectionError: {e}")
            return False, f"Connection error: {e}"
        except Exception as e:
            logger.warning(f"[DIAG] Proxy connectivity FAIL - Unknown: {e}")
            return False, f"Unknown error: {e}"

    def get_current_proxy(self) -> Optional[str]:
        """
        获取当前使用的代理节点

        Returns:
            str: 当前节点名称
        """
        try:
            # Clash API must bypass proxy (direct connection to localhost)
            resp = requests.get(
                f"{self.CLASH_API_URL}/proxies/🚀 节点选择",
                timeout=5,
                proxies={}  # Force direct connection
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("now")
            return None
        except Exception as e:
            logger.warning(f"Failed to get current proxy: {e}")
            return None

    def set_proxy_group(self, group_name: str, proxy_name: str) -> bool:
        """
        设置代理组的选中节点

        Args:
            group_name: 代理组名称
            proxy_name: 要选择的节点名称

        Returns:
            bool: 是否成功
        """
        try:
            # Clash API must bypass proxy (direct connection to localhost)
            resp = requests.put(
                f"{self.CLASH_API_URL}/proxies/{group_name}",
                json={"name": proxy_name},
                timeout=5,
                proxies={}  # Force direct connection
            )
            return resp.status_code == 204
        except Exception as e:
            logger.warning(f"Failed to set proxy group: {e}")
            return False

    def switch_to_region(self, region: str) -> bool:
        """
        切换到指定区域

        Args:
            region: 区域名称（新加坡/日本/台湾/香港）

        Returns:
            bool: 是否成功
        """
        if region not in self.REGION_GROUPS:
            logger.error(f"Unknown region: {region}")
            return False

        group_name = self.REGION_GROUPS[region]

        # 先设置主选择器到该区域的节点组
        success = self.set_proxy_group("🚀 节点选择", group_name)

        if success:
            logger.info(f"Switched to region: {region} ({group_name})")

            # 等待一下让切换生效
            time.sleep(1)

            # 验证连通性
            is_connected, error = self.test_connectivity()
            if is_connected:
                logger.info(f"Region {region} connectivity verified")
                return True
            else:
                logger.warning(f"Region {region} connectivity failed: {error}")
                return False
        else:
            logger.warning(f"Failed to switch to region: {region}")
            return False

    def rotate_region(self) -> Tuple[bool, str]:
        """
        轮换到下一个区域

        注意：每次调用都会先递增索引，确保真正切换到不同区域
        这对于处理 Cloudflare 阻止 POST 但 GET 仍可用的情况很重要

        Returns:
            Tuple[bool, str]: (是否成功, 当前区域)
        """
        # 先递增索引，确保切换到不同区域
        self.current_region_index = (self.current_region_index + 1) % len(self.REGIONS)
        logger.info(f"[DIAG] Region rotation started - new index: {self.current_region_index}")

        for i in range(len(self.REGIONS)):
            region = self.REGIONS[self.current_region_index]
            logger.info(f"[DIAG] Trying region {i+1}/{len(self.REGIONS)}: {region}")

            if self.switch_to_region(region):
                logger.info(f"[DIAG] Region rotation SUCCESS - now using: {region}")
                return True, region

            # 尝试下一个区域
            self.current_region_index = (self.current_region_index + 1) % len(self.REGIONS)
            logger.info(f"[DIAG] Region {region} failed, rotating to next...")

        logger.error("[DIAG] Region rotation FAILED - all regions exhausted")
        return False, ""

    def smart_retry(self, func, *args, **kwargs):
        """
        智能重试：失败时自动切换区域重试

        Args:
            func: 要执行的函数
            *args, **kwargs: 函数参数

        Returns:
            函数返回值
        """
        last_error = None

        for attempt in range(self.max_retries * len(self.REGIONS)):
            try:
                result = func(*args, **kwargs)
                return result

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # 检查是否是网络相关错误
                network_errors = [
                    "connection", "timeout", "proxy", "refused",
                    "network", "unreachable", "ssl", "reset"
                ]

                is_network_error = any(err in error_str for err in network_errors)

                if is_network_error:
                    logger.warning(f"Network error on attempt {attempt + 1}: {e}")

                    # 测试当前连通性
                    is_connected, _ = self.test_connectivity()

                    if not is_connected:
                        logger.info("Connectivity lost, rotating region...")
                        success, new_region = self.rotate_region()

                        if success:
                            logger.info(f"Switched to {new_region}, retrying...")
                            continue
                        else:
                            logger.error("All regions exhausted")
                            break
                    else:
                        # 连通性OK，可能是其他问题
                        time.sleep(2)
                        continue
                else:
                    # 非网络错误，直接抛出
                    raise e

        # 所有重试都失败
        raise last_error

    def ensure_connectivity(self) -> bool:
        """
        确保代理连通性（启动时调用）

        Returns:
            bool: 是否连通
        """
        logger.info("Ensuring proxy connectivity...")

        # 确保Clash在运行
        if not self.is_clash_running():
            if not self.start_clash():
                logger.error("Cannot start Clash")
                return False

        # 测试当前连通性
        is_connected, error = self.test_connectivity()

        if is_connected:
            current = self.get_current_proxy()
            logger.info(f"Proxy connectivity OK (current: {current})")
            return True

        # 当前不通，尝试轮换区域
        logger.warning(f"Current proxy not working: {error}")
        success, region = self.rotate_region()

        if success:
            logger.info(f"Connectivity established via {region}")
            return True
        else:
            logger.error("Cannot establish proxy connectivity")
            return False

    def get_proxies_for_requests(self) -> Dict[str, str]:
        """
        获取用于requests库的代理配置

        Returns:
            dict: 代理配置字典
        """
        return {
            "http": self.CLASH_PROXY_HTTP,
            "https": self.CLASH_PROXY_HTTP,
        }

    def set_env_proxy(self):
        """设置环境变量代理（用于子进程）"""
        os.environ["HTTP_PROXY"] = self.CLASH_PROXY_HTTP
        os.environ["HTTPS_PROXY"] = self.CLASH_PROXY_HTTP
        os.environ["http_proxy"] = self.CLASH_PROXY_HTTP
        os.environ["https_proxy"] = self.CLASH_PROXY_HTTP

    def clear_env_proxy(self):
        """清除环境变量代理"""
        for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
            if key in os.environ:
                del os.environ[key]

    def health_check(self) -> bool:
        """
        执行健康检查，检测僵尸进程并自动重启

        Returns:
            bool: 健康检查是否通过
        """
        # 检查僵尸进程
        if self._has_zombie_clash():
            logger.warning("[CLASH] Health check: Zombie process detected!")
            logger.info("[CLASH] Attempting auto-restart...")
            return self.restart_clash()

        # 检查进程是否在运行
        if not self.is_clash_running():
            logger.warning("[CLASH] Health check: Clash not running!")
            logger.info("[CLASH] Attempting to start...")
            return self.start_clash()

        # 检查代理连通性
        is_connected, error = self.test_connectivity(timeout=5)
        if not is_connected:
            logger.warning(f"[CLASH] Health check: Connectivity failed - {error}")
            # 尝试切换区域
            success, region = self.rotate_region()
            if success:
                logger.info(f"[CLASH] Health check: Recovered via {region}")
                return True
            else:
                logger.warning("[CLASH] Health check: All regions failed, restarting...")
                return self.restart_clash()

        return True


# 全局单例
_proxy_manager: Optional[ClashProxyManager] = None


def get_proxy_manager() -> ClashProxyManager:
    """获取全局代理管理器实例"""
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ClashProxyManager()
    return _proxy_manager
