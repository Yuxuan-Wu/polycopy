# 监控脚本使用指南
# Monitor Scripts Usage Guide

## 📊 可用的监控脚本

### 1. `./watch.sh` - 持续实时监控（推荐）

**功能：**
- 🔄 持续刷新显示系统状态
- 📡 实时监控进程运行状态
- 🌐 检查RPC连接状态
- ⛓️ 显示最新处理的区块
- 💰 实时显示捕获的交易数量
- 👁️ 监控3个地址的交易情况
- 📝 显示最近的日志活动

**使用方法：**
```bash
# 默认每10秒刷新一次
./watch.sh

# 自定义刷新间隔（秒）
./watch.sh 5    # 每5秒刷新
./watch.sh 30   # 每30秒刷新

# 停止监控
按 Ctrl+C
```

**实时显示内容：**
```
╔═══════════════════════════════════════════════════════════╗
║     POLYMARKET MONITOR - LIVE DASHBOARD                  ║
║     实时监控面板                                            ║
╚═══════════════════════════════════════════════════════════╝

📡 Process Status    - 进程是否运行
🌐 RPC Connection    - RPC连接状态和端点
⛓️  Block Processing - 最新处理的区块号
📝 Log Activity      - 日志活动和错误统计
💰 Trades Captured   - 捕获的交易总数
👁️  Monitored Addresses - 3个监控地址的交易数量
📊 Recent Log Activity - 最近3条日志
```

---

### 2. `./status.sh` - 完整状态报告

**功能：**
- 一次性显示完整的系统状态
- 详细的诊断信息
- 适合问题排查

**使用方法：**
```bash
./status.sh
```

**显示内容：**
- 进程状态（PID、运行时间、内存）
- 日志文件状态和更新时间
- 数据库统计（大小、交易数）
- CSV文件状态
- 配置验证（监控地址）
- 最近5条日志

---

### 3. `./quick_check.sh` - 快速检查

**功能：**
- 快速检查系统是否运行
- 显示基本信息
- 适合快速确认

**使用方法：**
```bash
./quick_check.sh
```

**显示内容：**
- 进程状态
- 运行时间
- 内存使用
- 监控地址列表
- 交易总数

---

## 🎯 使用场景推荐

### 场景1：长期监控（推荐）
```bash
# 在SSH会话中运行持续监控
./watch.sh 10
```
保持终端开启，实时查看系统状态和交易捕获情况。

### 场景2：后台运行+定期检查
```bash
# 主程序在后台运行
python3 main.py &

# 需要时快速检查状态
./quick_check.sh

# 或查看完整报告
./status.sh
```

### 场景3：问题排查
```bash
# 1. 查看完整状态
./status.sh

# 2. 如果发现问题，查看详细日志
tail -100 logs/polycopy.log

# 3. 或实时查看日志
tail -f logs/polycopy.log
```

---

## 📈 监控指标说明

### 进程状态
- **✓ RUNNING** - 系统正常运行
- **✗ STOPPED** - 系统未运行，需要启动

### RPC连接
- **✓ Connected** - 已连接到Polygon RPC节点
- **✗ No connection** - 连接失败，会自动切换到备用节点

### 日志活动
- **✓ Active (Xs ago)** - 最近X秒内有日志更新
- **⚠ Idle (Xs ago)** - 超过30秒未更新（正常，因为INFO级别只记录重要事件）
- **✗ Stale (Xs ago)** - 超过120秒未更新（可能存在问题）

### 错误状态
- **✓ No recent errors** - 最近100条日志无错误
- **⚠ N errors** - 发现错误，需要查看日志

### 交易捕获
- **Total: N** - 总共捕获的交易数
- **⚡ N new in last minute** - 最近1分钟新捕获的交易
- **No trades yet** - 还未捕获到交易（正常）

### 监控地址状态
- **✓ address (N trades)** - 该地址已有N笔交易被捕获
- **○ address (no trades)** - 该地址暂无交易（正常）

---

## 🔍 常见问题

### Q: 为什么日志显示"Stale"？
**A:** 这是正常的。日志级别设置为INFO，只记录重要事件（启动、交易、错误）。系统在正常监控时不会频繁写日志。

### Q: 如何确认系统在正常工作？
**A:** 运行 `./watch.sh`，检查：
1. Process Status = ✓ RUNNING
2. RPC Connection = ✓ Connected
3. Errors = ✓ No recent errors

### Q: 一直没有捕获到交易是否正常？
**A:** 是正常的。只有当监控的3个地址进行Polymarket交易时才会记录。如果这些地址没有交易，就不会有记录。

### Q: 如何查看实时日志？
**A:**
```bash
tail -f logs/polycopy.log
```

### Q: 如何停止系统？
**A:**
```bash
pkill -f 'python3 main.py'
```

### Q: 如何重启系统？
**A:**
```bash
# 先停止
pkill -f 'python3 main.py'

# 再启动
python3 main.py
```

---

## 📱 推荐的日常使用流程

### 启动系统
```bash
cd /root/polycopy
python3 main.py &
```

### 开启持续监控
```bash
./watch.sh 10
```

### 定期检查（不需要持续监控时）
```bash
# 每隔一段时间运行
./quick_check.sh
```

### 查看捕获的交易
```bash
cat data/trades.csv
# 或
sqlite3 data/trades.db "SELECT * FROM trades;"
```

---

## 🛠️ 高级技巧

### 在screen中运行持续监控
```bash
# 创建screen会话
screen -S polymarket

# 运行监控
./watch.sh 5

# 分离会话: Ctrl+A 然后按 D
# 重新连接: screen -r polymarket
```

### 设置开机自启动
```bash
# 编辑crontab
crontab -e

# 添加这一行
@reboot cd /root/polycopy && python3 main.py
```

### 导出特定地址的交易
```bash
# 导出某个地址的所有交易
sqlite3 data/trades.db << EOF
.mode csv
.headers on
.output address_trades.csv
SELECT * FROM trades WHERE from_address='0x你的地址';
.quit
EOF
```

---

## 📞 支持

如果遇到问题：
1. 运行 `./status.sh` 查看详细状态
2. 检查 `logs/polycopy.log` 查看错误信息
3. 确认配置文件 `config.yaml` 中的地址正确

系统设计为24/7不间断运行，会自动处理RPC故障切换和错误恢复。
