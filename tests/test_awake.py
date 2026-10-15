import os

from lv import awake


class FakeProc:
    def __init__(self, argv, **kw):
        self.argv, self.kw, self.terminated = argv, kw, False

    def terminate(self):
        self.terminated = True


def test_macos_runs_caffeinate_tied_to_this_process():
    lines = []
    h = awake.keep_awake(out=lines.append, platform="darwin", popen=FakeProc, which=lambda n: "/usr/bin/caffeinate")
    assert h.argv == ["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())]
    assert lines == []
    awake.release(h)
    assert h.terminated


def test_windows_sets_and_clears_the_execution_state():
    calls = []

    class K:
        def SetThreadExecutionState(self, flags):
            calls.append(flags)
            return 1
    k = K()
    h = awake.keep_awake(out=print, platform="win32", kernel32=k)
    assert h is awake.WINDOWS and calls == [awake.ES_CONTINUOUS | awake.ES_SYSTEM_REQUIRED]
    awake.release(h, kernel32=k)
    assert calls[-1] == awake.ES_CONTINUOUS


def test_other_systems_warn_and_continue():
    lines = []
    assert awake.keep_awake(out=lines.append, platform="linux") is None
    assert lines == [awake.WARNING]
    awake.release(None)  # no error


def test_macos_without_caffeinate_warns():
    lines = []
    assert awake.keep_awake(out=lines.append, platform="darwin", which=lambda n: None) is None
    assert lines == [awake.WARNING]
