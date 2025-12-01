# Polycopy 使用指南

## 快速开始

Polycopy 现在有两个主要的工具脚本，功能清晰且易于使用。

## 🎯 核心工具

### 1. 监控仪表板 - `monitor_dashboard.py`

**用途**: 实时监控交易活动和持仓状态

```bash
# 启动实时仪表板（默认5秒刷新）
python3 monitor_dashboard.py

# 自定义刷新间隔（10秒）
python3 monitor_dashboard.py --refresh 10

# 只显示监控状态，不显示持仓
python3 monitor_dashboard.py --no-positions
```

**显示内容**:
- 📊 进程状态（运行中/停止）
- 📈 数据库统计（总交易数、市场数等）
- 📋 最近5笔交易
- 💼 当前持仓及盈亏
- ⚡ 捕获延迟分布

**使用场景**:
- 实时监控系统运行状态
- 查看最新交易活动
- 跟踪当前持仓变化
- 监控系统性能

---

### 2. 交易者分析 - `analyze_trader.py`

**用途**: 深度分析交易者行为和跟单可行性

```bash
# 完整分析报告
python3 analyze_trader.py

# 快速摘要
python3 analyze_trader.py --quick

# 分析特定地址
python3 analyze_trader.py --address 0x0f37Cb80DEe49D55B5F6d9E595D52591D6371410
```

**分析内容**:
- 📈 交易者概览（交易数、频率、时间段）
- 💰 表现指标（胜率、ROI、已实现盈亏）
- 🎯 交易模式（原子性、频率分类、交易者类型）
- 🎓 **跟单可行性评分**（0-100分）
- 🏆 最活跃的5个市场

**跟单可行性评分**:
- **75-100分**: 🟢 高度推荐 - 强劲表现和一致性
- **60-74分**: 🟡 推荐 - 有前景的结果
- **45-59分**: 🟠 谨慎推荐 - 结果参差不齐
- **0-44分**: 🔴 不推荐 - 缺乏盈利证据

**评分因素**:
1. 胜率（0-30分）
2. ROI（0-25分）
3. 样本量（0-20分）
4. 交易活跃度（0-15分）
5. 一致性/原子性（0-10分）

---

## 🛠️ 维护工具

### 持仓回填 - `backfill_positions.py`

从历史交易数据重建持仓表：

```bash
python3 backfill_positions.py
```

### 元数据回填 - `backfill_metadata.py`

获取市场元数据：

```bash
# 查看覆盖率
python3 backfill_metadata.py --stats

# 执行回填
python3 backfill_metadata.py

# 强制刷新
python3 backfill_metadata.py --force
```

---

## 📊 运维工具

### 启动监控

```bash
python3 main.py
```

### 重启监控

```bash
./restart.sh
```

### 检查状态

```bash
./status.sh
```

---

## 📁 项目结构

```
/root/polycopy/
├── main.py                      # 主监控程序
├── monitor_dashboard.py         # 🎯 实时监控仪表板
├── analyze_trader.py            # 🎯 交易者分析工具
├── backfill_positions.py        # 持仓回填
├── backfill_metadata.py         # 元数据回填
├── restart.sh                   # 重启脚本
├── status.sh                    # 状态检查
├── config.yaml                  # 配置文件
├── src/                         # 核心模块
│   ├── monitor.py
│   ├── database.py
│   ├── metadata_manager.py
│   └── ...
├── data/                        # 数据存储
│   ├── trades.db               # SQLite数据库
│   └── trades.csv              # CSV导出
└── logs/                        # 日志
```

---

## 🚀 典型工作流程

### 场景1: 首次启动

```bash
# 1. 启动监控程序
python3 main.py

# 2. 在另一个终端查看实时状态
python3 monitor_dashboard.py
```

### 场景2: 评估跟单可行性

```bash
# 1. 快速查看评分
python3 analyze_trader.py --quick

# 2. 如果感兴趣，查看完整报告
python3 analyze_trader.py
```

### 场景3: 每日监控

```bash
# 打开实时仪表板
python3 monitor_dashboard.py

# 按 Ctrl+C 退出
```

### 场景4: 定期分析

```bash
# 每周运行一次完整分析
python3 analyze_trader.py > reports/weekly_analysis_$(date +%Y%m%d).txt
```

---

## 📖 详细文档

- `README.md` - 项目总览
- `POSITION_TRACKING.md` - 持仓跟踪系统说明
- `METADATA_GUIDE.md` - 元数据系统说明
- `QUICK_REFERENCE.md` - 快速参考卡片

---

## 💡 提示

1. **实时监控**: `monitor_dashboard.py` 适合放在分屏终端持续运行
2. **定期分析**: 每周运行 `analyze_trader.py` 评估交易者表现
3. **样本量**: 跟单可行性评分需要至少5个已结算的交易才有参考价值
4. **刷新间隔**: 监控仪表板默认5秒刷新，可根据需要调整

---

## ⚠️ 注意事项

1. 跟单有风险，评分仅供参考
2. 小样本量可能导致评分不准确
3. 历史表现不代表未来收益
4. 建议从小仓位开始测试跟单策略

---

## 🆘 问题排查

**仪表板显示"STOPPED"**:
```bash
# 检查主程序是否运行
./status.sh

# 重启主程序
./restart.sh
```

**分析报告显示"No positions"**:
```bash
# 运行持仓回填
python3 backfill_positions.py
```

**市场信息显示"N/A"**:
```bash
# 运行元数据回填
python3 backfill_metadata.py
```
