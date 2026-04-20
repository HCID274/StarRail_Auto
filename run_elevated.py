"""统一的管理员提权入口，用当前 uv Python 运行目标脚本。"""

import argparse
import ctypes
import subprocess
import sys
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parent
SEE_MASK_NOCLOSEPROCESS = 0x00000040
SW_SHOWNORMAL = 1
INFINITE = 0xFFFFFFFF


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("fMask", ctypes.c_ulong),
        ("hwnd", ctypes.c_void_p),
        ("lpVerb", ctypes.c_wchar_p),
        ("lpFile", ctypes.c_wchar_p),
        ("lpParameters", ctypes.c_wchar_p),
        ("lpDirectory", ctypes.c_wchar_p),
        ("nShow", ctypes.c_int),
        ("hInstApp", ctypes.c_void_p),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", ctypes.c_wchar_p),
        ("hkeyClass", ctypes.c_void_p),
        ("dwHotKey", ctypes.c_ulong),
        ("hIconOrMonitor", ctypes.c_void_p),
        ("hProcess", ctypes.c_void_p),
    ]


def _is_running_as_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # pragma: no cover - 依赖宿主环境
        return False


def _resolve_script(script: str) -> Path:
    path = Path(script)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"target script not found: {path}")
    return path


def _run_target(script: Path, script_args: Sequence[str]) -> int:
    completed = subprocess.run(
        [sys.executable, str(script), *script_args],
        cwd=PROJECT_ROOT,
    )
    return completed.returncode


def _relaunch_self_elevated(raw_args: Sequence[str]) -> int:
    shell32 = ctypes.windll.shell32
    kernel32 = ctypes.windll.kernel32

    execute_info = SHELLEXECUTEINFOW()
    execute_info.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
    execute_info.fMask = SEE_MASK_NOCLOSEPROCESS
    execute_info.hwnd = None
    execute_info.lpVerb = "runas"
    execute_info.lpFile = sys.executable
    execute_info.lpParameters = subprocess.list2cmdline(
        [str(Path(__file__).resolve()), "--already-elevated", *raw_args]
    )
    execute_info.lpDirectory = str(PROJECT_ROOT)
    execute_info.nShow = SW_SHOWNORMAL

    success = shell32.ShellExecuteExW(ctypes.byref(execute_info))
    if not success:
        raise RuntimeError("failed to relaunch elevated process")

    kernel32.WaitForSingleObject(execute_info.hProcess, INFINITE)
    exit_code = ctypes.c_ulong()
    kernel32.GetExitCodeProcess(execute_info.hProcess, ctypes.byref(exit_code))
    kernel32.CloseHandle(execute_info.hProcess)
    return int(exit_code.value)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a project Python script in an elevated process",
    )
    parser.add_argument(
        "--already-elevated",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "script",
        help="project-local Python script to run, for example uu_accel.py",
    )
    parser.add_argument(
        "script_args",
        nargs=argparse.REMAINDER,
        help="arguments passed through to the target script",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    script = _resolve_script(args.script)

    if args.already_elevated or _is_running_as_admin():
        return _run_target(script, args.script_args)

    return _relaunch_self_elevated(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
