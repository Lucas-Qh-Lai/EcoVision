#!/bin/bash
# EcoVision 一键关闭 - 彻底杀死所有相关进程
set -e

cd "$(dirname "$0")"
PID_FILE="/tmp/ecovision.pid"
PORT=${1:-8765}

echo "[ZH] 正在查找 EcoVision 进程..."
echo "[EN] Looking for EcoVision processes..."

# 1. 从 PID 文件杀
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "  → [ZH] 终止进程 PID=$OLD_PID"
echo "  → [EN] Killing process PID=$OLD_PID"
        kill "$OLD_PID" 2>/dev/null
        sleep 1
        # 如果没死透就强杀
        if kill -0 "$OLD_PID" 2>/dev/null; then
            echo "  → [ZH] 强制终止 PID=$OLD_PID"
echo "  → [EN] Force killing PID=$OLD_PID"
            kill -9 "$OLD_PID" 2>/dev/null
        fi
    else
        echo "  → [ZH] PID 文件中的进程 ($OLD_PID) 已不存在"
echo "  → [EN] Process in PID file ($OLD_PID) no longer exists"
    fi
    rm -f "$PID_FILE"
fi

# 2. 找所有 uvicorn server:app 进程（同一端口）
PIDS=$(ps aux | grep "uvicorn server:app" | grep -v grep | awk '{print $2}')
if [ -n "$PIDS" ]; then
    echo "  → [ZH] 清理残留进程: $PIDS"
echo "  → [EN] Cleaning remaining processes: $PIDS"
    kill $PIDS 2>/dev/null || true
    sleep 0.5
    # 查漏补缺
    PIDS=$(ps aux | grep "uvicorn server:app" | grep -v grep | awk '{print $2}')
    if [ -n "$PIDS" ]; then
        echo "  → [ZH] 强制清理: $PIDS"
echo "  → [EN] Force cleaning: $PIDS"
        kill -9 $PIDS 2>/dev/null || true
    fi
fi

# 3. 确认端口已释放
if lsof -i :$PORT 2>/dev/null | grep -q LISTEN; then
    echo "  ⚠ [ZH] 端口 $PORT 仍被占用，尝试通过 lsof 杀..."
echo "  ⚠ [EN] Port $PORT still in use, attempting lsof kill..."
    lsof -i :$PORT -t 2>/dev/null | xargs kill -9 2>/dev/null || true
    sleep 0.5
fi

echo "[ZH] ✅ EcoVision 已彻底关闭 (port $PORT)"
echo "[EN] ✅ EcoVision fully stopped (port $PORT)"
