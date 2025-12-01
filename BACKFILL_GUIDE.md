# Position Backfill 机制说明

## 问题背景

当监控系统启动时，只能捕获启动后的交易。如果某个地址在启动前已经有交易历史，会导致position数据不完整：
- 卖出 > 买入（出现"负持仓"）
- 纯卖出无买入记录
- realized_pnl 计算不准确

## 解决方案

### 1. 检测不完整的Positions

运行检测脚本，标记所有不完整的positions：

```bash
python3 detect_incomplete_positions.py
```

这个脚本会：
- ✅ 添加3个新字段到positions表
  - `is_complete`: 是否完整（1=完整，0=不完整）
  - `backfill_attempted`: 是否尝试过backfill
  - `backfill_date`: backfill尝试日期
- ✅ 检测并标记所有 `sold > bought` 的positions
- ✅ 显示每个position的缺口大小

### 2. Backfill历史数据（未完成）

`backfill_positions.py` 脚本设计用于：
1. 向前回溯最多7天的区块链数据
2. 查找缺失的买入交易
3. 更新positions数据
4. 如果7天内仍找不到，标记为permanent incomplete

**注意**: 此功能还在开发中，需要解决：
- PolymarketMonitor的正确初始化
- 区块链历史查询优化
- Rate limiting处理

### 3. 当前检测结果

从我们的数据看，发现了 **10个不完整的positions**：

| Position | Bought | Sold | Gap | Status |
|----------|--------|------|-----|--------|
| 0x873b... | 0.00 | 494.64 | 494.64 | settled_loss |
| 0xdf5d... | 116.12 | 5221.47 | **5105.35** | settled_loss |
| 0xbfea... | 18.95 | 1538.72 | 1519.77 | settled_loss |
| 0x4b27... | 0.00 | 35.03 | 35.03 | settled_loss |
| 0x2bdd... | 0.00 | 2079.74 | 2079.74 | settled_loss |
| 0xbf4e... | 0.00 | 2099.98 | 2099.98 | **settled_win** |
| 0x315b... | 0.00 | 157.82 | 157.82 | settled_loss |
| 0x267d... | 466.95 | 999.99 | 533.04 | **active** |
| 0xc99d... | 0.00 | 29864.42 | **29864.42** | settled_win |
| 0x552d... | 0.00 | 770.24 | 770.24 | settled_loss |

**关键发现**：
- 最大缺口：29864.42 tokens (position 0xc99d...)
- 2个已结算为win的positions（0xbf4e..., 0xc99d...）
- 1个仍active的position（0x267d...）

## 数据库Schema更新

```sql
ALTER TABLE positions ADD COLUMN is_complete INTEGER DEFAULT NULL;
ALTER TABLE positions ADD COLUMN backfill_attempted INTEGER DEFAULT 0;
ALTER TABLE positions ADD COLUMN backfill_date TEXT DEFAULT NULL;
```

## 查询示例

### 查看所有不完整的positions
```sql
SELECT address, token_id, total_bought, total_sold,
       (total_sold - total_bought) as gap,
       status
FROM positions
WHERE is_complete = 0
ORDER BY gap DESC;
```

### 查看需要backfill的positions
```sql
SELECT *
FROM positions
WHERE is_complete = 0
  AND backfill_attempted = 0;
```

## 下一步

1. ✅ **已完成**: 检测和标记机制
2. 🚧 **进行中**: 自动backfill历史数据
3. 📝 **待办**: 定期检查新的incomplete positions
4. 📝 **待办**: 在monitor启动时自动运行检测

## 使用建议

**当前阶段**：
- 定期运行 `detect_incomplete_positions.py` 检查新的incomplete positions
- 注意到这些positions的realized_pnl可能不准确
- 在分析交易表现时，优先关注 `is_complete=1` 的positions

**未来**：
- 完成backfill脚本后，可以自动补全历史数据
- 监控系统启动时自动检测并标记
- Dashboard显示positions的完整性状态
