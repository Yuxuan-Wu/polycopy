# Polymarket Monitor - Optimized

高性能的Polymarket交易监控系统，使用eth_getLogs直接查询链上事件，支持24小时滚动窗口。

## 快速开始

```bash
# 启动监控
python3 main.py

# 后台运行
nohup python3 main.py > /dev/null 2>&1 &

# 查看实时状态
./watch.sh

# 查看日志
tail -f logs/polycopy.log
```

## 核心特性

- ✅ **eth_getLogs精准查询** - 直接过滤相关交易，减少99%网络流量
- ✅ **24小时滚动窗口** - 启动时回溯24小时，持续监控新交易
- ✅ **Infura集成** - 100区块批次，自动故障转移
- ✅ **双合约监控** - CTF Exchange + Neg Risk CTF
- ✅ **智能速率控制** - 0.1秒延迟，避免API限流
- ✅ **实时CSV导出** - 每笔交易自动导出

## 系统架构

```
Infura RPC (主) + 4个备用RPC
    ↓
eth_getLogs (3地址 × 2角色)
    ↓
Event Decoder (买卖方向识别)
    ↓
SQLite + CSV自动导出
```

## 配置文件

### config.yaml

```yaml
monitored_addresses:
  - "0x..." # 你的监控地址

monitoring:
  method: eth_getLogs
  poll_interval: 60
  batch_size: 100
  request_delay: 0.1
  use_rolling_window: true
  window_hours: 24
```

### .env

```bash
INFURA_API_KEY=你的key
```

## 性能指标

| 指标 | 值 |
|------|-----|
| 批次大小 | 100 blocks |
| 处理速度 | ~100 blocks/分钟 |
| RPC调用 | ~7次/分钟 |
| API使用 | 10% (免费额度) |
| 实时延迟 | <5秒 |

## 监控命令

```bash
# 实时仪表板
./watch.sh [刷新间隔秒数]

# 查看进程
ps aux | grep "python3.*main.py"

# 统计交易
sqlite3 data/trades.db "SELECT COUNT(*) FROM trades;"

# 停止监控
pkill -f 'python3 main.py'
```

## 数据库

**位置**: `data/trades.db`

**表结构**:
- tx_hash (唯一)
- block_number, timestamp
- from_address, to_address
- side (buy/sell/swap)
- token_id, amount, price
- gas_used, gas_price
- capture_delay_seconds

**CSV导出**: `data/trades.csv` (自动同步)

## 系统要求

- Python 3.10+
- SQLite3
- 依赖: `pip3 install -r requirements.txt`

## 故障排查

**问题**: 进程未运行
```bash
# 检查日志
tail -50 logs/polycopy.log

# 手动启动
python3 main.py
```

**问题**: RPC连接失败
- 自动切换到备用RPC
- 检查.env中的INFURA_API_KEY

**问题**: 交易遗漏
- 确保监控两个合约（config.yaml中的polymarket_contracts）
- 检查24小时窗口是否覆盖时间段

## 文档

- **DEPLOYMENT_SUCCESS.md** - 完整部署报告
- **OPTIMIZATION_PROPOSAL.md** - 技术优化方案
- **INFURA_STRATEGY.md** - API使用策略

## 许可

Private use only.
