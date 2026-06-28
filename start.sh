#!/bin/bash
# EcoVision 一键启动
cd "$(dirname "$0")"
PID_FILE="/tmp/ecovision.pid"
PORT=8765

# 检测可用的虚拟环境
if [ -d ".venv11/bin" ]; then
    PYTHON=".venv11/bin/python3"
elif [ -d ".venv/bin" ]; then
    PYTHON=".venv/bin/python3"
else
    PYTHON="python3"
fi

# 如果已有进程则先汇报
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[ZH] EcoVision 已在运行中 → http://localhost:$PORT"
echo "[EN] EcoVision is already running → http://localhost:$PORT"
        IP=$(ifconfig en0 2>/dev/null | grep 'inet ' | awk '{print $2}')
        [ -n "$IP" ] && echo "[ZH] 局域网访问 → http://$IP:$PORT"
echo "[EN] LAN access → http://$IP:$PORT"
        exit 0
    fi
fi

# 检查数据库
if [ ! -f "ecovision_stats.db" ]; then
    echo "[ZH] 首次启动，初始化统计数据库..."
echo "[EN] First launch, initializing statistics database..."
fi

# 启动
nohup "$PYTHON" -m uvicorn server:app --host 0.0.0.0 --port $PORT > /tmp/ecovision.log 2>&1 &
echo $! > "$PID_FILE"
echo "[ZH] EcoVision 启动中（首次加载模型约需 25 秒，请稍候）..."
echo "[EN] EcoVision starting (first launch loads model ~25s, please wait)..."
sleep 4
echo "[ZH] 启动完成 → http://localhost:$PORT"
echo "[EN] Server ready → http://localhost:$PORT"
IP=$(ifconfig en0 2>/dev/null | grep 'inet ' | awk '{print $2}')
[ -n "$IP" ] && echo "[ZH] 手机访问 → http://$IP:$PORT"
echo "[EN] Mobile access → http://$IP:$PORT"
