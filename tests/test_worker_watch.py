import datetime as dt
import os
import signal
import sys

import pytest

from lv import site, worker
from test_worker import DECK, QUESTIONS, _claude_writing, _turn, lessons, lv_pid  # noqa: F401  (fixtures)


class Awake:
    def __init__(self):
        self.on = self.off = 0

    def keep(self, out=print):
        self.on += 1
        return "handle"

    def release(self, h):
        assert h == "handle"
        self.off += 1


def _watch(claude, **kw):
    a, lines, sleeps = Awake(), [], []
    code = worker.watch(claude=claude, out=lines.append, sleep=sleeps.append, awake_on=a.keep, awake_off=a.release, **kw)
    return code, lines, sleeps, a


def test_watch_runs_queued_turns_back_to_back_then_stops(paired, lessons):
    for i in range(2):
        paired.turns.append(_turn(tid=f"trn_{i}123456789abcdefghijkl"))
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    paired.stop_next = False
    fake = _claude_writing(QUESTIONS)

    def stop_after_turns(seconds):  # the first idle wait: ask the site to stop
        paired.stop_next = True
    a, lines = Awake(), []
    code = worker.watch(claude=fake, out=lines.append, sleep=stop_after_turns, awake_on=a.keep, awake_off=a.release)
    assert code == 0 and len(paired.finished) == 2 and len(fake.calls) == 2
    assert any("Disconnected from the website" in l and "/lesson-videos:serve" in l for l in lines)
    assert a.on == 1 and a.off == 1
    assert not (lessons / ".worker-watch.lock").exists() and not (lessons / ".worker.lock").exists()


def test_watch_first_call_sends_start_so_a_stale_stop_is_ignored(paired, lessons):
    paired.stop_next = True  # Disconnect pressed while this computer was off

    def sleep(s):  # first idle wait: now a real Disconnect
        paired.stop_next = True
    a = Awake()
    code = worker.watch(claude=_claude_writing(QUESTIONS), out=lambda l: None, sleep=sleep, awake_on=a.keep, awake_off=a.release)
    assert code == 0 and paired.next_queries == ["start=1", ""]  # did not stop on the stale mark


def test_watch_waits_on_a_once_run_and_still_sends_start_first(paired, lessons, lv_pid):
    lessons.mkdir(parents=True)
    lock = lessons / ".worker.lock"
    lock.write_text(str(lv_pid), encoding="utf-8")  # a live `worker --once` holds the lock
    paired.stop_next = True  # stale Disconnect mark
    n, lines = {"n": 0}, []

    def sleep(s):
        n["n"] += 1
        if n["n"] == 1:
            lock.unlink()
        elif n["n"] == 3:
            paired.stop_next = True  # a real Disconnect ends the run
    a = Awake()
    code = worker.watch(claude=_claude_writing(QUESTIONS), out=lines.append, sleep=sleep, awake_on=a.keep, awake_off=a.release)
    assert code == 0 and paired.next_queries[0] == "start=1" and n["n"] == 3
    assert lines.count("Another worker run is still going.") == 1


def test_watch_idles_with_the_poll_interval(paired, lessons):
    calls = {"n": 0}

    def sleep(s):
        assert s == worker.POLL
        calls["n"] += 1
        if calls["n"] == 3:
            paired.stop_next = True
    a = Awake()
    worker.watch(claude=_claude_writing(QUESTIONS), out=lambda l: None, sleep=sleep, awake_on=a.keep, awake_off=a.release)
    assert paired.next_queries == ["start=1", "", "", ""]  # only the first call says start=1


def test_watch_backs_off_on_network_errors_and_recovers(paired, lessons, monkeypatch):
    monkeypatch.setattr(worker.net, "request", _no_retry(worker.net.request))
    paired.fail_next = 5
    waits = []

    def sleep(s):
        waits.append(s)
        if paired.fail_next == 0 and len(waits) > 5:
            paired.stop_next = True
    a = Awake()
    code = worker.watch(claude=_claude_writing(QUESTIONS), out=lambda l: None, sleep=sleep, awake_on=a.keep, awake_off=a.release)
    assert code == 0
    assert waits[:6] == [30, 60, 120, 300, 300, worker.POLL]  # back-off caps at 300, then the normal poll again
    assert paired.next_queries[:6] == ["start=1"] * 6  # start stays set across back-offs


def _no_retry(request):
    def call(*a, **kw):
        kw["retries"] = 0
        return request(*a, **kw)
    return call


def test_watch_start_line_names_the_site_teacher_and_computer(paired, lessons):
    paired.stop_next = True  # stale: cleared by start=1

    def sleep(s):
        paired.stop_next = True
    a, lines = Awake(), []
    code = worker.watch(claude=_claude_writing(QUESTIONS), out=lines.append, sleep=sleep, awake_on=a.keep, awake_off=a.release)
    assert code == 0
    assert lines[0] == (f"Making videos for {paired.url} as teacher@example.org on Test Mac with lesson-videos 1.0.0. "
                        "Waiting for lessons… (stop with Ctrl-C, or Disconnect on the website)")
    assert paired.next_queries[0] == "start=1"  # status is not /next: the first /next still says start=1


def test_watch_stops_when_not_paired(paired, lessons):
    paired.token = "something-else"  # the site no longer accepts this computer's token (Remove on the website)
    code, lines, sleeps, a = _watch(_claude_writing(QUESTIONS))
    assert code == 1 and "isn't connected to slide2video.com" in lines[-1]
    assert a.on == 0 and a.off == 0 and paired.next_queries == []  # found out before keep-awake started
    assert not any(l.startswith("Making videos for") for l in lines)
    assert not (lessons / ".worker-watch.lock").exists()


def test_watch_stops_with_the_websites_refusal(paired, lessons):
    paired.refuse = ("This computer has lesson-videos 1.0.0; slide2video.com needs 2.x. To update: run /plugin update "
                     "lesson-videos, then close and reopen Claude Code, then run /lesson-videos:serve.")
    code, lines, sleeps, a = _watch(_claude_writing(QUESTIONS))
    assert code == 1 and lines[-1] == paired.refuse and a.on == 0


def test_watch_stops_on_contract_mismatch_from_an_older_website(paired, lessons):
    paired.contract = 2
    code, lines, sleeps, a = _watch(_claude_writing(QUESTIONS))
    assert code == 1 and "Update the lesson-videos plugin" in lines[-1] and a.on == 0


def test_second_watcher_is_refused(paired, lessons, lv_pid):
    lessons.mkdir(parents=True)
    (lessons / ".worker-watch.lock").write_text(str(lv_pid), encoding="utf-8")
    code, lines, sleeps, a = _watch(_claude_writing(QUESTIONS))
    assert code == 0 and "already making videos" in lines[-1] and a.on == 0 and paired.next_queries == []


def test_watch_cleans_up_on_sigterm_style_interrupt(paired, lessons):
    def interrupted(seconds):
        raise KeyboardInterrupt  # SIGTERM is turned into KeyboardInterrupt by watch()
    a = Awake()
    code = worker.watch(claude=_claude_writing(QUESTIONS), out=lambda l: None, sleep=interrupted,
                        awake_on=a.keep, awake_off=a.release)
    assert code == 0 and a.off == 1 and not (lessons / ".worker-watch.lock").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="no SIGTERM to send to oneself on Windows")
def test_watch_turns_a_real_sigterm_into_a_clean_stop_and_restores_the_handler(paired, lessons):
    def ours(signum, frame):
        raise AssertionError("the previous handler ran while watch() was going")
    before = signal.signal(signal.SIGTERM, ours)
    try:
        def terminated(seconds):
            os.kill(os.getpid(), signal.SIGTERM)  # what Claude Code sends when it stops a background task
        a, lines = Awake(), []
        code = worker.watch(claude=_claude_writing(QUESTIONS), out=lines.append, sleep=terminated,
                            awake_on=a.keep, awake_off=a.release)
        assert code == 0 and a.off == 1 and lines[-1].startswith("Stopped.")
        assert not (lessons / ".worker-watch.lock").exists()
        assert signal.getsignal(signal.SIGTERM) is ours
    finally:
        signal.signal(signal.SIGTERM, before)


def _stopped_claude(cmd, cwd, logfile):
    logfile.write_text("making chapter 1\n", encoding="utf-8")
    raise KeyboardInterrupt  # "Stop" in Claude Code while Claude was working on the step


def test_stop_during_a_step_hands_the_step_back_to_start_again(paired, lessons):
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    before = dt.datetime.now().astimezone()
    code, lines, sleeps, a = _watch(_stopped_claude)
    assert code == 0 and a.off == 1 and lines[-1].startswith("Stopped.")
    [(tid, card)] = paired.finished
    assert tid == "trn_0123456789abcdefghijkl" and card["kind"] == "error"
    assert "starts again" in card["message"]
    retry = dt.datetime.fromisoformat(card["retry_after"])
    assert before - dt.timedelta(seconds=1) <= retry <= dt.datetime.now().astimezone() + dt.timedelta(seconds=1)
    assert not (lessons / ".worker-watch.lock").exists() and not (lessons / ".worker.lock").exists()


def test_stop_during_a_step_sends_once_quickly_and_never_waits_on_a_failure(paired, lessons, monkeypatch):
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    paired.finish_statuses = [503]  # the site is busy just then: no retry, the lease runs out instead
    seen, request = [], worker.net.request

    def spy(url, *a, **kw):
        if url.endswith("/finish"):
            seen.append((kw.get("timeout"), kw.get("retries")))
        return request(url, *a, **kw)
    monkeypatch.setattr(worker.net, "request", spy)
    code, lines, sleeps, a = _watch(_stopped_claude)
    assert code == 0 and paired.finished == [] and a.off == 1
    assert seen == [(10, 0)]
    assert not (lessons / ".worker-watch.lock").exists() and not (lessons / ".worker.lock").exists()


def test_run_once_says_disconnected_on_a_stop(paired, lessons):
    paired.stop_next = True
    lines = []
    assert worker.run_once(claude=_claude_writing(QUESTIONS), out=lines.append) == 0
    assert lines == ["Disconnected from the website. To start again, run /lesson-videos:serve."]


def test_run_once_still_reports_idle_as_zero(paired, lessons):
    assert worker.run_once(claude=_claude_writing(QUESTIONS)) == 0


def test_cli_worker_watch_is_wired(monkeypatch):
    from lv import cli
    seen = {}
    monkeypatch.setattr(worker, "watch", lambda **kw: seen.setdefault("called", 0) or 0)
    assert cli.main(["worker", "--watch"]) == 0 and "called" in seen


UPDATE_11 = ("A newer lesson-videos (1.1.0) is available. To update: run /plugin update lesson-videos, then close "
             "and reopen Claude Code, then run /lesson-videos:serve.")


def test_watch_says_once_that_an_update_is_available_and_keeps_working(paired, lessons, monkeypatch):
    monkeypatch.setattr(site, "LATEST", None)
    paired.latest = "1.1.0"
    polls = []

    def sleep(s):  # three idle polls, then Disconnect
        polls.append(s)
        if len(polls) == 3:
            paired.stop_next = True
    a, lines = Awake(), []
    assert worker.watch(claude=_claude_writing(QUESTIONS), out=lines.append, sleep=sleep,
                        awake_on=a.keep, awake_off=a.release) == 0
    assert lines[1] == UPDATE_11 and lines.count(UPDATE_11) == 1
    assert lines[-1].startswith("Disconnected from the website")


def test_watch_says_it_again_when_the_website_moves_on_while_it_runs(paired, lessons, monkeypatch):
    monkeypatch.setattr(site, "LATEST", None)
    polls = []

    def sleep(s):
        polls.append(s)
        if len(polls) == 1:
            paired.latest = "1.1.0"
        if len(polls) == 3:
            paired.latest = "1.2.0"
        if len(polls) == 5:
            paired.stop_next = True
    a, lines = Awake(), []
    worker.watch(claude=_claude_writing(QUESTIONS), out=lines.append, sleep=sleep, awake_on=a.keep, awake_off=a.release)
    updates = [l for l in lines if l.startswith("A newer lesson-videos")]
    assert [u.split(")")[0] for u in updates] == ["A newer lesson-videos (1.1.0", "A newer lesson-videos (1.2.0"]


def test_watch_says_nothing_when_the_plugin_is_as_new_or_newer(paired, lessons, monkeypatch):
    monkeypatch.setattr(site, "LATEST", None)
    for latest in ("1.0.0", "0.9.0", "2.0.0", "junk"):
        paired.latest, paired.stop_next = latest, False

        def sleep(s):
            paired.stop_next = True
        a, lines = Awake(), []
        worker.watch(claude=_claude_writing(QUESTIONS), out=lines.append, sleep=sleep, awake_on=a.keep, awake_off=a.release)
        assert not any("newer lesson-videos" in l for l in lines), latest
