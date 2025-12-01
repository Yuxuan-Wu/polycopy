# Polymarket Metadata Integration Guide

## 概述

我们的Polycopy系统现在集成了Polymarket Gamma API，可以自动获取和存储市场元数据（market metadata），包括市场问题、结果选项、类别等信息。

## 核心组件

### 1. Gamma API Client (`src/gamma_client.py`)

负责与Polymarket Gamma API通信：

```python
from gamma_client import GammaClient

client = GammaClient()

# 通过token_id查询市场
market_data = client.get_market_by_token_id("0x123...")

# 批量查询
markets = client.batch_get_markets(["0x123...", "0x456..."])
```

**主要功能：**
- `get_market_by_token_id()` - 单个token查询
- `get_market_by_condition_id()` - 通过condition ID查询
- `batch_get_markets()` - 批量查询（自动处理API限制）

### 2. Metadata Manager (`src/metadata_manager.py`)

管理metadata的存储和检索：

```python
from metadata_manager import MetadataManager

mgr = MetadataManager('data/trades.db')

# 获取某个token的市场信息
market_info = mgr.get_market_for_token("0x123...")

# 执行backfill
stats = mgr.backfill_metadata()

# 获取统计信息
stats = mgr.get_metadata_stats()
```

**主要功能：**
- 自动创建metadata相关数据表
- 保存market和token映射
- backfill历史数据
- 查询market信息

### 3. 数据库Schema

#### `markets` 表
存储市场元数据：

```sql
CREATE TABLE markets (
    id INTEGER PRIMARY KEY,
    market_id TEXT UNIQUE,      -- Gamma API的市场ID
    condition_id TEXT,          -- 链上condition ID
    question TEXT,              -- 市场问题
    slug TEXT,                  -- URL slug
    description TEXT,           -- 详细描述
    outcomes TEXT,              -- JSON: ["Yes", "No"]
    outcome_prices TEXT,        -- JSON: 当前价格
    clob_token_ids TEXT,        -- JSON: token ID列表
    category TEXT,              -- 分类
    image TEXT,                 -- 图片URL
    icon TEXT,                  -- 图标URL
    start_date TEXT,
    end_date TEXT,
    volume REAL,                -- 总交易量
    liquidity REAL,             -- 流动性
    active INTEGER,             -- 是否活跃
    closed INTEGER,             -- 是否关闭
    event_slug TEXT,
    event_title TEXT,
    neg_risk INTEGER,
    market_type TEXT,
    fetched_at TEXT,
    updated_at TEXT
)
```

#### `token_outcomes` 表
映射token_id到市场和结果：

```sql
CREATE TABLE token_outcomes (
    id INTEGER PRIMARY KEY,
    token_id TEXT UNIQUE,       -- 十六进制token ID
    market_id TEXT,             -- 关联的market_id
    condition_id TEXT,
    outcome_index INTEGER,      -- 结果索引 (0=Yes, 1=No)
    outcome_name TEXT,          -- 结果名称
    created_at TEXT
)
```

## 使用方法

### 方式1: 自动集成（推荐）

主监控程序会自动获取新交易的metadata：

```bash
# 启动监控程序（自动获取metadata）
python3 main.py
```

当检测到新交易时，系统会：
1. 保存交易到数据库
2. 检查该token_id是否有metadata
3. 如果没有，自动从Gamma API获取
4. 保存到markets和token_outcomes表
5. 在日志中显示完整的市场信息

### 方式2: 手动Backfill

为历史数据补充metadata：

```bash
# 查看当前覆盖率
python3 backfill_metadata.py --stats

# 执行backfill
python3 backfill_metadata.py

# 强制刷新所有metadata
python3 backfill_metadata.py --force
```

### 方式3: 查询脚本

查看带有完整metadata的交易记录：

```bash
# 查看最近10笔交易
python3 query_trades.py

# 查看最近20笔交易
python3 query_trades.py --limit 20

# 查看市场汇总
python3 query_trades.py --markets
```

## Gamma API参考

### Base URL
```
https://gamma-api.polymarket.com
```

### 关键Endpoints

#### 获取市场列表
```
GET /markets?clob_token_ids=TOKEN_ID&limit=10
```

**重要参数：**
- `clob_token_ids` - token ID（十进制格式）
- `condition_ids` - condition ID
- `limit` - 返回数量限制
- `closed` - 过滤关闭/开放的市场
- `active` - 过滤活跃市场

#### Token ID格式转换

数据库存储的是十六进制格式：
```
0xc435629199c23a6be37cbd84cd55d7044dc8cf80a0f1bc9c657a9a99e17921c8
```

API需要十进制格式：
```python
token_hex = "0xc435629199c23a6be37cbd84cd55d7044dc8cf80a0f1bc9c657a9a99e17921c8"
token_dec = int(token_hex, 16)
# 88747641513280400178687141315496855423288441644476781622350185851556682342856
```

## 数据查询示例

### SQL查询：获取交易的完整market信息

```sql
SELECT
    t.timestamp,
    t.from_address,
    t.side,
    t.amount,
    t.price,
    m.question,
    o.outcome_name,
    m.category,
    m.volume as market_volume
FROM trades t
LEFT JOIN token_outcomes o ON t.token_id = o.token_id
LEFT JOIN markets m ON o.market_id = m.market_id
ORDER BY t.timestamp DESC
LIMIT 10;
```

### Python查询：使用MetadataManager

```python
from metadata_manager import MetadataManager

mgr = MetadataManager('data/trades.db')

# 获取token的市场信息
token_id = "0x123..."
market_info = mgr.get_market_for_token(token_id)

print(f"Market: {market_info['question']}")
print(f"Outcome: {market_info['outcome_name']}")
print(f"Category: {market_info['category']}")
print(f"Volume: ${market_info['volume']:,.2f}")
```

## 性能优化

### 批量查询优化

GammaClient使用批量查询来减少API调用：

```python
# 一次查询多个token
token_ids = ["0x123...", "0x456...", "0x789..."]
results = client.batch_get_markets(token_ids)

# 自动分批处理（每批20个）
# 出错时自动回退到单个查询
```

### 缓存策略

1. **数据库缓存** - metadata保存后不会重复获取
2. **检查before fetch** - 监控程序会先检查是否已有metadata
3. **批量backfill** - 历史数据一次性批量获取

## 错误处理

### 常见问题

1. **Token ID不存在于Gamma API**
   - 某些旧市场可能未被索引
   - 日志会显示warning但不影响交易记录

2. **API Rate Limit**
   - GammaClient自动处理批量请求
   - 出错时回退到单个查询

3. **网络超时**
   - 默认超时30秒
   - 可在GammaClient初始化时调整

## 监控和维护

### 检查覆盖率

```bash
python3 backfill_metadata.py --stats
```

输出示例：
```
Total trades:              60
Unique token IDs:          8
Token IDs with metadata:   8
Total markets:             7
Coverage:                  100.00%
```

### 日志监控

监控程序会记录metadata获取情况：

```
✓ Metadata saved: Will Donald Trump rank in Google's Top 5...
⚠️  No market data found for token_id: 0x123...
```

## 相关文档

- [Polymarket Gamma API文档](https://docs.polymarket.com/developers/gamma-markets-api/overview)
- [Gamma API Swagger](https://gamma-api.polymarket.com/)
- [ANALYSIS_GUIDE.md](./ANALYSIS_GUIDE.md) - 数据分析指南

## 依赖项

新增依赖：
```
httpx>=0.28.0
```

已添加到 `requirements.txt`

## 示例输出

### 交易日志（带metadata）

```
================================================================================
📊 TRADE DETECTED | Block: 79,696,234
   Tx Hash: 60d9684df808db86eb833e44d8a1c0e5f96d8b9f0a1e8f9c0c1d2e3f4a5b6c7d
   Address: 0xc9b6227a... (maker)
   Market: Will Donald Trump rank in Google's Top 5 Most Searche
   Outcome: No
   Side: buy
   Price: 0.66 USDC
   Amount: 5.4 tokens
   Time: 2025-11-29 11:14:41
   ⚡ Capture delay: 28s - REAL-TIME
================================================================================
```

### 市场汇总

```
📈 Will Donald Trump rank in Google's Top 5 Most Searched People of 2025?
   Options: Yes vs No
   Category: Politics
   Status: OPEN
   Total Volume: $2,017,304.06
   Our Trades: 28
```

## 未来增强

可能的改进方向：

1. **缓存热门市场** - 减少API调用
2. **定期刷新** - 更新volume和price
3. **Market事件通知** - 市场关闭/解决时通知
4. **更丰富的分析** - 基于metadata的策略分析

---

**最后更新**: 2025-11-29
**作者**: Claude Code
