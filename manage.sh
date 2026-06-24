#!/bin/bash

# API Server 管理脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/logs/server.pid"
LOGS_DIR="$SCRIPT_DIR/logs"
CONDA_ENV="api-server"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 函数：检查服务状态
check_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "${GREEN}● API Server 正在运行 (PID: $PID)${NC}"
            return 0
        else
            echo -e "${YELLOW}● API Server 已停止 (PID 文件存在但进程不存在)${NC}"
            rm -f "$PID_FILE"
            return 1
        fi
    else
        echo -e "${RED}● API Server 未运行${NC}"
        return 1
    fi
}

# 函数：启动服务
start() {
    if check_status > /dev/null 2>&1; then
        echo -e "${YELLOW}API Server 已经在运行${NC}"
        return 0
    fi

    echo -e "${GREEN}正在启动 API Server...${NC}"
    
    # 激活 conda 环境并启动
    source /home/cc/anaconda3/etc/profile.d/conda.sh
    conda activate $CONDA_ENV
    
    cd "$SCRIPT_DIR"
    gunicorn -c gunicorn_config.py main:app
    
    sleep 2
    
    if check_status > /dev/null 2>&1; then
        echo -e "${GREEN}✓ API Server 启动成功${NC}"
        return 0
    else
        echo -e "${RED}✗ API Server 启动失败${NC}"
        return 1
    fi
}

# 函数：停止服务
stop() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "${YELLOW}正在停止 API Server (PID: $PID)...${NC}"
            kill "$PID"
            sleep 2
            
            if ! ps -p "$PID" > /dev/null 2>&1; then
                echo -e "${GREEN}✓ API Server 已停止${NC}"
                rm -f "$PID_FILE"
                return 0
            fi
        fi
    fi
    
    # 如果 PID 文件不存在或进程已停止，尝试 pkill
    echo -e "${YELLOW}尝试强制停止...${NC}"
    pkill -f gunicorn
    rm -f "$PID_FILE"
    echo -e "${GREEN}✓ API Server 已停止${NC}"
    return 0
}

# 函数：重启服务
restart() {
    stop
    sleep 2
    start
}

# 函数：查看日志
logs() {
    local log_type="${1:-app}"
    
    case "$log_type" in
        app)
            tail -f "$LOGS_DIR/app.log"
            ;;
        access)
            tail -f "$LOGS_DIR/access.log"
            ;;
        error)
            tail -f "$LOGS_DIR/error.log"
            ;;
        *)
            echo -e "${RED}未知的日志类型：$log_type${NC}"
            echo -e "${YELLOW}可用的日志类型：app, access, error${NC}"
            return 1
            ;;
    esac
}

# 函数：显示使用帮助
help() {
    echo -e "${GREEN}API Server 管理脚本${NC}"
    echo ""
    echo "用法：$0 <命令>"
    echo ""
    echo "命令:"
    echo "  start       启动服务"
    echo "  stop        停止服务"
    echo "  restart     重启服务"
    echo "  status      查看服务状态"
    echo "  logs        查看日志 (app|access|error)"
    echo "  help        显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 start"
    echo "  $0 stop"
    echo "  $0 logs error"
    echo ""
}

# 主程序
case "${1:-}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        check_status
        exit $?
        ;;
    logs)
        logs "$2"
        ;;
    help|--help|-h)
        help
        ;;
    *)
        echo -e "${RED}未知命令：${1:-}${NC}"
        echo ""
        help
        exit 1
        ;;
esac
