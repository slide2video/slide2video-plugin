"""Keep this computer awake while `worker --watch` runs: a sleeping computer can't see new lessons. The display may
still turn off. macOS: caffeinate, tied to this process so it ends with it even if the worker is killed. Windows:
the thread execution state (it belongs to the calling thread, so call both functions from the main thread)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
WINDOWS = object()
WARNING = "This computer may sleep while waiting for lessons; keep it awake yourself."


def keep_awake(out=print, platform=sys.platform, popen=subprocess.Popen, which=shutil.which, kernel32=None):
    if platform == "darwin":
        exe = which("caffeinate")
        if exe:
            try:
                return popen([exe, "-i", "-w", str(os.getpid())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass
    elif platform == "win32":
        try:
            k = kernel32 or __import__("ctypes").windll.kernel32
            if k.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED):
                return WINDOWS
        except (AttributeError, OSError):
            pass
    out(WARNING)
    return None


def release(handle, kernel32=None) -> None:
    if handle is None:
        return
    if handle is WINDOWS:
        try:
            (kernel32 or __import__("ctypes").windll.kernel32).SetThreadExecutionState(ES_CONTINUOUS)
        except (AttributeError, OSError):
            pass
        return
    try:
        handle.terminate()
    except OSError:
        pass
