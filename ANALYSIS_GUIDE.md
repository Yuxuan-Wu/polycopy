# Trader Analysis Guide

这是一套完整的交易者行为分析工具，用于深入理解Polymarket交易者的策略和模式。

## 📊 工具概览

### 1. **trader_analysis.py** - 交易者行为分析
全面分析交易者的交易模式、频率和策略定位。

### 2. **market_analysis.py** - 市场级别分析
深入分析特定市场的交易模式和持仓变化。

### 3. **analyze.sh** - 统一分析入口
便捷的命令行工具，整合所有分析功能。

---

## 🚀 快速开始

### 基础用法

```bash
# 查看帮助
./analyze.sh help

# 快速查看所有监控地址的摘要
./analyze.sh summary

# 分析某个交易者
./analyze.sh trader 0xCA8F0374E3Fc79b485499CC0b038D4F7e783D963
```

---

## 📖 详细功能

### 1. 交易者综合分析

```bash
./analyze.sh trader <address>
```

**输出内容**:
- **基础统计**: 总交易数、买卖比例、交易市场数、总成交量
- **交易频率**: 每小时交易数、交易间隔时间、频率分类
- **Atomicity分析**: 是否只做单边交易、换边频率
- **持仓管理**: 调仓频率、持仓管理风格
- **热门市场**: Top 10市场的交易分布
- **整体定位**: 交易者类型分类

**交易者分类**:
- `DIRECTIONAL TRADER` - 方向性交易者（Atomic，低调仓）
- `ACTIVE MARKET MAKER / ARBITRAGEUR` - 做市商/套利者（高频，双边）
- `MOMENTUM TRADER` - 动量交易者（高频，单边）
- `BALANCED TRADER` - 均衡交易者（混合策略）

### 2. 市场级别深度分析

```bash
./analyze.sh market <address> <token_id>
```

**输出内容**:
- 该市场的所有交易明细
- 买入/卖出总量和净持仓
- 平均买入/卖出价格和价差
- 持仓变化时间线
- 换边次数（判断是否atomic）

**示例**:
```bash
./analyze.sh market 0xCA8F0374... 0x19193375897d6ef21b2464a9e89c32e6dbc2e8af90c20b63b7a3b903ff4d881b
```

### 3. 交易簇分析

```bash
./analyze.sh clusters <address>
```

找出在短时间内（默认60秒）发生的相关交易，识别交易策略模式。

**识别的模式**:
- `single_market_buy_accumulation` - 单市场快速买入
- `single_market_sell_accumulation` - 单市场快速卖出
- `single_market_hedging` - 单市场对冲
- `multi_market_hedging` - 跨市场对冲
- `multi_market_buying` - 跨市场买入
- `multi_market_selling` - 跨市场卖出

### 4. 交易者对比

```bash
./analyze.sh compare <address1> <address2>
```

并排对比两个交易者的行为特征。

### 5. 数据导出

```bash
./analyze.sh export <address>
```

导出交易者的所有交易数据为JSON格式，保存在`reports/`目录。

---

## 🔍 核心指标说明

### Atomicity（原子性）

**定义**: 交易者在每个市场是否只做单边（只买或只卖）

**计算方法**:
```
Atomicity Ratio = Atomic Markets / Total Markets
```

**分类**:
- `highly_atomic` (≥90%) - 几乎所有市场都是单边
- `mostly_atomic` (70-90%) - 大部分市场单边
- `mixed` (50-70%) - 混合策略
- `non_atomic` (<50%) - 频繁换边

**意义**:
- **高Atomicity** = 方向性强，有明确观点，低频调仓
- **低Atomicity** = 对冲策略，做市或套利

### 交易频率分类

**分类标准**（基于每小时交易数）:
- `high_frequency` (>10/小时) - 高频交易
- `active` (1-10/小时) - 活跃交易
- `moderate` (0.1-1/小时) - 中等频率
- `low_frequency` (<0.1/小时) - 低频交易

### 调仓风格

**分类**:
- `buy_and_hold` - 买入持有（调仓比例<20%）
- `occasional_rebalancer` - 偶尔调仓（20-50%）
- `active_rebalancer` - 主动调仓（>50%）

**计算方法**:
```
Rebalancing Ratio = Markets with Rebalancing / Total Markets
```

---

## 📈 实际案例

### 案例1: 高频做市商识别

```bash
./analyze.sh trader 0xCA8F0374E3Fc79b485499CC0b038D4F7e783D963
```

**关键指标**:
- Trading Frequency: `high_frequency` (68.4 trades/hour)
- Atomicity: `non_atomic` (41.5% atomic)
- Position Management: `active_rebalancer` (58.5%)
- **结论**: ACTIVE MARKET MAKER / ARBITRAGEUR

### 案例2: 方向性交易者

```bash
./analyze.sh trader 0x0f37Cb80DEe49D55B5F6d9E595D52591D6371410
```

**关键指标**:
- Trading Frequency: `active` (7.8 trades/hour)
- Atomicity: `highly_atomic` (100% atomic)
- Position Management: `buy_and_hold` (0% rebalancing)
- **结论**: DIRECTIONAL TRADER

---

## 🎯 使用场景

### 1. 跟单前筛选

**目标**: 找到高胜率的方向性交易者

**筛选条件**:
```bash
# 寻找 Atomicity > 80% 且不是高频的交易者
./analyze.sh trader <address>
```

看以下指标：
- Atomicity Ratio > 0.8 （强方向性）
- Trading Frequency: moderate或active （非高频）
- Rebalancing Style: buy_and_hold （持仓稳定）

### 2. 识别做市商

**目标**: 识别提供流动性的做市商

**特征**:
- Trading Frequency: high_frequency
- Atomicity: non_atomic
- Position Management: active_rebalancer
- 查看clusters: 频繁的multi_market_hedging模式

### 3. 分析调仓时机

```bash
./analyze.sh market <address> <token_id>
```

查看"POSITION CHANGES"部分，分析：
- 什么价格水平调仓
- 调仓频率
- 持仓大小变化

---

## 🔧 高级用法

### 自定义时间窗口（Trade Clusters）

编辑`market_analysis.py`，修改：
```python
def find_correlated_trades(self, address: str, time_window_seconds: int = 60):
```

改为更大的窗口（如300秒）来发现更长时间跨度的策略。

### 导出并进一步分析

```bash
# 导出数据
./analyze.sh export 0xCA8F0374...

# 用jq进一步处理
cat reports/trader_*.json | jq '.[] | select(.side == "buy") | .price' | stats
```

---

## 📊 输出示例

### Trader Analysis输出

```
================================================================================
TRADER BEHAVIOR ANALYSIS REPORT
================================================================================

1. TRADER SUMMARY
--------------------------------------------------------------------------------
  address                       : 0xCA8F...
  total_trades                  : 855
  buys                          : 337
  sells                         : 518
  unique_markets                : 229
  ...

3. MARKET ATOMICITY ANALYSIS
--------------------------------------------------------------------------------
  Classification: non_atomic
  Atomic Markets: 95 (41.5%)
  Non-Atomic Markets: 134
  Total Position Flips: 134
  ...

6. OVERALL TRADER CLASSIFICATION
--------------------------------------------------------------------------------
  Profile: ACTIVE MARKET MAKER / ARBITRAGEUR
  Description: High frequency trading on both sides. Likely providing liquidity.
```

---

## 🛠️ 故障排查

### 问题: "No trades found"

**原因**: 数据库中没有该地址的交易

**解决**:
```bash
# 检查数据库中的地址
./analyze.sh summary

# 确认地址格式（需要checksum格式）
```

### 问题: 分析速度慢

**原因**: 交易数据量大

**解决**: 针对性分析而非全量
```bash
# 只分析特定市场
./analyze.sh market <addr> <token_id>

# 而非全量trader分析
```

---

## 🔄 定期监控建议

### 每日检查

```bash
# 1. 快速摘要
./analyze.sh summary

# 2. 检查新交易模式
./analyze.sh clusters <your_main_address>
```

### 每周深度分析

```bash
# 完整分析所有监控地址
for addr in $(sqlite3 data/trades.db "SELECT DISTINCT from_address FROM trades;"); do
    ./analyze.sh trader $addr > reports/weekly_$(date +%Y%m%d)_${addr:0:10}.txt
done
```

---

## 📚 API集成

### Polymarket Gamma API

工具已集成Gamma API获取市场元数据（如市场标题、描述等）。

**端点**:
- Markets: `https://gamma-api.polymarket.com/markets`
- CLOB: `https://clob.polymarket.com/markets/{token_id}`

**缓存**: 自动缓存市场信息，避免重复请求

---

## 💡 最佳实践

1. **先看Summary** - 了解全局
2. **Trader Analysis** - 确定交易者类型
3. **Clusters Analysis** - 理解策略模式
4. **Market Analysis** - 深入特定市场

---

## 📝 数据隐私

- 所有分析在本地进行
- 不上传任何交易数据
- 仅API调用为获取公开市场元数据

---

**需要帮助?** 查看各个脚本的`--help`选项
