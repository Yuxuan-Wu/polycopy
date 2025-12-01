# Polycopy 快速参考

## 🎯 两个核心工具

### 监控仪表板（实时查看）
```bash
python3 monitor_dashboard.py
```
显示：进程状态、最新交易、当前持仓、盈亏

### 交易者分析（跟单评估）
```bash
python3 analyze_trader.py --quick    # 快速摘要
python3 analyze_trader.py            # 完整报告
```
输出：跟单可行性评分（0-100分）+ 详细分析

---

## 📊 评分解读

| 分数 | 评级 | 建议 |
|------|------|------|
| 75-100 | 🟢 高度推荐 | 可以跟单，适度仓位 |
| 60-74 | 🟡 推荐 | 谨慎跟单，减小仓位 |
| 45-59 | 🟠 谨慎推荐 | 仅限有经验者 |
| 0-44 | 🔴 不推荐 | 避免跟单 |

---

## 🔧 其他命令

```bash
# 启动监控
python3 main.py

# 重启监控
./restart.sh

# 检查状态
./status.sh

# 回填持仓
python3 backfill_positions.py

# 回填元数据
python3 backfill_metadata.py
```

---

## 📁 数据位置

- 数据库: `data/trades.db`
- CSV: `data/trades.csv`
- 日志: `logs/polycopy.log`
- 配置: `config.yaml`

---

详细说明请查看 `USAGE_GUIDE.md`
