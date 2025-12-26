#!/bin/bash
# Polycopy Health Check Script
# 检查 Clash 代理和 Polycopy 服务的健康状态
# 自动修复常见问题

LOG_FILE="/root/polycopy/logs/health_check.log"
CLASH_CONFIG="/root/.config/clash"
POLYMARKET_API="https://clob.polymarket.com/time"
PROXY_ADDR="127.0.0.1:7890"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') | $1" | tee -a "$LOG_FILE"
}

# 检查 Clash 进程
check_clash_process() {
    if pgrep -f "clash" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# 检查 Clash API
check_clash_api() {
    response=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:9091/version" --connect-timeout 5)
    if [ "$response" = "200" ]; then
        return 0
    else
        return 1
    fi
}

# 检查代理连通性
check_proxy_connectivity() {
    response=$(curl -s -o /dev/null -w "%{http_code}" --proxy "http://$PROXY_ADDR" "$POLYMARKET_API" --connect-timeout 10)
    if [ "$response" = "200" ]; then
        return 0
    else
        return 1
    fi
}

# 重启 Clash
restart_clash() {
    log "🔄 Restarting Clash..."

    # 停止现有进程
    pkill -f clash 2>/dev/null
    sleep 2
    pkill -9 -f clash 2>/dev/null
    sleep 1

    # 启动新进程
    /usr/local/bin/clash -d "$CLASH_CONFIG" &>/dev/null &
    sleep 5

    if check_clash_process && check_clash_api; then
        log "✓ Clash restarted successfully"
        return 0
    else
        log "✗ Clash restart failed"
        return 1
    fi
}

# 检查 Polycopy 服务
check_polycopy_service() {
    if systemctl is-active --quiet polycopy.service; then
        return 0
    else
        return 1
    fi
}

# 主健康检查逻辑
main() {
    log "========== HEALTH CHECK START =========="

    errors=0

    # 1. 检查 Clash 进程
    if check_clash_process; then
        log "✓ Clash process: Running"
    else
        log "✗ Clash process: NOT running"
        restart_clash
        ((errors++))
    fi

    # 2. 检查 Clash API
    if check_clash_api; then
        log "✓ Clash API: Responding"
    else
        log "✗ Clash API: Not responding"
        restart_clash
        ((errors++))
    fi

    # 3. 检查代理连通性
    if check_proxy_connectivity; then
        log "✓ Proxy connectivity: OK"
    else
        log "✗ Proxy connectivity: FAILED"

        # 尝试重启 Clash
        if restart_clash; then
            # 再次测试
            sleep 3
            if check_proxy_connectivity; then
                log "✓ Proxy connectivity restored after restart"
            else
                log "✗ Proxy still not working after restart"
                ((errors++))
            fi
        else
            ((errors++))
        fi
    fi

    # 4. 检查 Polycopy 服务
    if check_polycopy_service; then
        log "✓ Polycopy service: Running"
    else
        log "✗ Polycopy service: NOT running"
        log "  Attempting to restart..."
        systemctl restart polycopy.service
        sleep 5
        if check_polycopy_service; then
            log "✓ Polycopy service restarted"
        else
            log "✗ Polycopy service restart failed"
            ((errors++))
        fi
    fi

    log "========== HEALTH CHECK END (errors: $errors) =========="

    # 返回错误数（0 = 健康）
    return $errors
}

# 运行主函数
main
exit $?
