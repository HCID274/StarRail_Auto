"""核心执行器 — UU 加速 + M7A 启动 + 看门狗监控."""

import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil

from uu_accel import ensure_uu_connected

# ── 配置 ──────────────────────────────────────────────
M7A_LAUNCHER = Path(
    r"D:\2_Software\4_Games\StarRail\Auto\March7thAssistant_full\March7th Launcher.exe"
)
M7A_LOG_DIR = Path(
    r"D:\2_Software\4_Games\StarRail\Auto\March7thAssistant_full\logs"
)
LOGS_DIR = Path(__file__).parent / "logs"

# 看门狗参数
GRACE_PERIOD = 60          # 启动宽限期（秒）
CPU_IDLE_THRESHOLD = 2.0   # CPU 使用率阈值（%）
CPU_IDLE_WINDOW = 900      # CPU 空闲持续时间（秒）= 15 分钟
LOG_HEARTBEAT_TIMEOUT = 600  # 日志无更新超时（秒）= 10 分钟
WATCHDOG_INTERVAL = 30     # 看门狗检查间隔（秒）

# 默认超时
DEFAULT_TIMEOUTS = {
    "universe": 7200,
    "main": 1800,
}

log = logging.getLogger("m7a_runner")

# ── 日志配置 ───────────────────────────────────────────

def _setup_logging() -> None:
    """按天写日志到 logs/ 目录."""
    LOGS_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.log"

    formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


# ── 看门狗 ─────────────────────────────────────────────

def _get_m7a_latest_log() -> Path | None:
    """获取 M7A 最新日志文件."""
    if not M7A_LOG_DIR.exists():
        return None
    logs = sorted(M7A_LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0] if logs else None


def _kill_process_tree(pid: int) -> None:
    """Kill 进程树."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            child.kill()
        parent.kill()
        log.info("killed process tree (pid=%d, children=%d)", pid, len(children))
    except psutil.NoSuchProcess:
        log.info("process %d already exited", pid)


def _watchdog(proc: subprocess.Popen, timeout: int) -> int:
    """看门狗监控 M7A 进程。返回退出码（0=正常, 1=异常）."""
    start_time = time.monotonic()
    cpu_idle_since: float | None = None

    log.info("watchdog started: timeout=%ds, grace=%ds", timeout, GRACE_PERIOD)

    while True:
        # 进程已退出
        ret = proc.poll()
        if ret is not None:
            log.info("M7A exited with code %d", ret)
            return 0 if ret == 0 else 1

        elapsed = time.monotonic() - start_time
        in_grace = elapsed < GRACE_PERIOD

        # 硬超时
        if elapsed >= timeout:
            log.warning("HARD TIMEOUT reached (%ds), killing", timeout)
            _kill_process_tree(proc.pid)
            return 1

        if not in_grace:
            # CPU 空闲检测
            try:
                p = psutil.Process(proc.pid)
                cpu = p.cpu_percent(interval=1)
                if cpu < CPU_IDLE_THRESHOLD:
                    if cpu_idle_since is None:
                        cpu_idle_since = time.monotonic()
                    elif time.monotonic() - cpu_idle_since >= CPU_IDLE_WINDOW:
                        log.warning(
                            "CPU idle for %ds (<%s%%), killing",
                            CPU_IDLE_WINDOW, CPU_IDLE_THRESHOLD,
                        )
                        _kill_process_tree(proc.pid)
                        return 1
                else:
                    cpu_idle_since = None
            except psutil.NoSuchProcess:
                continue

            # 日志心跳检测
            m7a_log = _get_m7a_latest_log()
            if m7a_log:
                last_modified = m7a_log.stat().st_mtime
                if time.time() - last_modified > LOG_HEARTBEAT_TIMEOUT:
                    log.warning(
                        "M7A log not updated for %ds, killing",
                        LOG_HEARTBEAT_TIMEOUT,
                    )
                    _kill_process_tree(proc.pid)
                    return 1

        time.sleep(WATCHDOG_INTERVAL)


# ── 主流程 ─────────────────────────────────────────────

def run(task: str, timeout: int) -> int:
    """执行完整流程：UU加速 → M7A启动 → 看门狗监控."""
    log.info("=== task: %s, timeout: %ds ===", task, timeout)

    # 1. 确保 UU 加速器已连接
    try:
        ensure_uu_connected()
    except RuntimeError as e:
        log.error("UU acceleration failed: %s", e)
        return 1

    # 2. 启动 M7A
    # 当前版本实测需要走 Launcher.exe 才能正确接收任务参数并启动游戏
    # 注意：需要管理员权限，Windows 任务计划程序设置"使用最高权限运行"
    exe = M7A_LAUNCHER
    cmd = [str(exe), task, "-e"]
    log.info("launching M7A: %s", " ".join(cmd))
    proc = subprocess.Popen(cmd)
    log.info("M7A started (pid=%d)", proc.pid)

    # 3. 看门狗监控
    return _watchdog(proc, timeout)


def main() -> None:
    parser = argparse.ArgumentParser(description="Star Rail automation runner")
    parser.add_argument(
        "task",
        choices=["universe", "main"],
        help="task to run",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="hard timeout in seconds (default: per-task)",
    )
    args = parser.parse_args()

    _setup_logging()

    timeout = args.timeout or DEFAULT_TIMEOUTS.get(args.task, 1800)
    exit_code = run(args.task, timeout)

    log.info("=== finished with code %d ===", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
