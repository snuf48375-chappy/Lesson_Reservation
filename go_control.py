"""One-use Human GO and post-Enter, same-thread worker observations."""
import time
from datetime import datetime, timezone
from runtime_config import require


def stamp():
    return datetime.now(timezone.utc).isoformat()


def console_enter(prompt):
    import sys
    import msvcrt
    require(sys.stdin.isatty(), 'INTERACTIVE_OWNER_CONSOLE_REQUIRED')
    # Discard keystrokes queued before READY. Piped/pre-READY Enter is not authority.
    while msvcrt.kbhit():
        msvcrt.getwch()
    return input(prompt)


class WorkerBarrier:
    """Retains two waits / three parties; verifies on the owning Selenium thread."""
    def __init__(self, barrier, final_requested, ack, alias, verify, activate=None):
        self.barrier, self.final_requested, self.ack = barrier, final_requested, ack
        self.alias, self.verify, self.phase = alias, verify, 0
        self.activate = activate

    def wait(self):
        self.phase += 1
        require(self.phase <= 2, 'BARRIER_REUSE')
        if self.phase == 2:
            require(self.final_requested.wait(720), 'HUMAN_GO_TIMEOUT')
            self.verify()
            self.ack[self.alias] = dict(state='PASS', timestamp=stamp())
        result = self.barrier.wait()
        if self.phase == 2 and self.activate is not None:
            self.activate()
        return result

    def abort(self):
        self.barrier.abort()


class HumanGate:
    def __init__(self):
        self.used = False

    def release(self, barrier, ready, final_requested, ack, final_check, record,
                ask=console_enter, on_quit=None):
        require(not self.used, 'HUMAN_GO_ALREADY_USED')
        self.used = True  # Invalid input also burns this in-process gate.
        barrier.wait()
        ready()
        print('Worker A: READY\nWorker B: READY')
        both_ready = stamp()
        choice = ask('Current Listを確認し予約実行を承認する場合だけ Enter。予約せず安全に終了する場合は Q + Enter: ')
        if choice in ('Q', 'q'):
            require(on_quit is not None, 'SAFE_QUIT_HANDLER_REQUIRED')
            return on_quit(choice, both_ready)
        require(choice == '', 'EMPTY_ENTER_REQUIRED')
        entered = time.perf_counter()
        human_go_timestamp = stamp()
        final_requested.set()
        deadline = time.monotonic() + 10
        while not all(w in ack for w in ('A', 'B')):
            require(not barrier.broken and time.monotonic() < deadline, 'WORKER_FINAL_VERIFICATION_TIMEOUT')
            time.sleep(0.001)
        require(all(ack[w].get('state') == 'PASS' for w in ('A', 'B')), 'WORKER_FINAL_VERIFICATION_FAILED')
        final_check()
        verified = time.perf_counter()
        value = dict(human_go_timestamp=human_go_timestamp, both_ready_timestamp=both_ready,
                     semantic='OWNER_CURRENT_LIST_CURRENT_STATE_AND_ONE_BATCH_AUTHORIZED',
                     enter_to_final_verification_ms=(verified-entered)*1000)
        record(value)  # exclusive durable human_go publication before release
        barrier.wait()
        value['enter_to_barrier_release_ms'] = (time.perf_counter()-entered)*1000
        value['barrier_release_observed_timestamp'] = stamp()
        return value
