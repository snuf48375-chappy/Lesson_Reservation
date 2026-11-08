"""Default is local-only preflight. --live requires separate Stage C authority.

The two worker process_user calls retain the locked Batch algorithm. An empty
worker joins both barriers without starting Chrome. Human GO releases phase 2.
"""
import argparse
import contextlib
import ctypes
import multiprocessing
import os
import sys
import time
import uuid
import importlib.metadata
from pathlib import Path
import runtime as rt
from runtime_config import require
from credentials import WindowsCredentials, binding_for
from login_control import automatic_login, menu_ready
from go_control import HumanGate, WorkerBarrier, stamp, console_enter
from final_guard import FinalGuard
from frozen_inputs import FrozenInputs
import safe_quit as sq
from diagnostic import fet_start, fet_context, fet_capture

def empty_worker(barrier):
    barrier.wait()
    barrier.wait()

def worker(alias, session, expected_binding, barrier, counts, results, final_requested, ack, timings, quit_requested):
    root = rt.STATE / session
    a, driver_ref = None, []
    safe_selected, quit_owned = False, None
    fet_start(root, session, alias, expected_binding.get('manifest_sha', ''))
    try:
        a, m, binding, path = rt.context()
        fet_start(root, session, alias, expected_binding.get('manifest_sha', ''), a.publish)
        require(a.exact(binding, expected_binding), 'WORKER_CONFIGURATION_CHANGED')
        s = rt.make_store(a, m, binding, path, root)
        user = m.users[0 if alias == 'A' else 1]
        original_profile = user['profile_path']
        def binding_check():
            rt.configure_adapter(a, m, binding)
            require(a.exact(binding, expected_binding), 'WORKER_CONFIGURATION_CHANGED')
            binding_for(m, alias, user)
            require(user['profile_path'] == original_profile, 'WORKER_PROFILE_BINDING_CHANGED')
        def final_verify():
            nonlocal quit_owned
            binding_check()
            if quit_requested.is_set():
                sq.verify_request(root, expected_binding)
                require(len(driver_ref) == 1, 'QUIT_BROWSER_REQUIRED')
                quit_owned = sq.capture_owned_processes(driver_ref[0])
                raise sq.SafeQuitRequested()
            if user['lesson_requests']:
                require(len(driver_ref) == 1, 'BROWSER_SESSION_LOST')
                menu_ready(m, driver_ref[0], user, binding_check)
        gate = WorkerBarrier(barrier, final_requested, ack, alias, final_verify, s.activate_go)
        def mark(name):
            timings[alias + '_' + name] = dict(timestamp=stamp(), monotonic=time.perf_counter())
        if not user['lesson_requests']:
            s.claim(session, alias)
            a.publish(root / ('login-' + alias + '.json'), dict(state='EMPTY_WORKER', code='OK'))
            mark('menu_ready')
            empty_worker(gate)
            counts[user['username']] = 0
        else:
            rt.install(a, m, s, session, alias)
            def login(driver, wait, login_user, max_attempts=3):
                require(login_user is user, 'LOGIN_USER_BINDING')
                driver_ref[:] = [driver]
                return automatic_login(m, driver, user, alias, WindowsCredentials(), binding_check, mark)
            m.login_and_verify = login
            m._cla1_relogin = login  # same account/profile/binding; no new GO or claim
            native_log = m.log_event
            def event(name, result=None, **kw):
                if name == 'browser_started':
                    mark('chrome_started')
                if name == 'login_verification':
                    a.publish(root / ('login-' + alias + '.json'), dict(code=result.code, state=result.state))
                native_log(name, result, **kw)
            m.log_event = event
            with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                fet_context('WORKER_RUN')
                m.process_user(user, gate, counts, results)
        fet_context('WORKER_FINAL_CHECK')
        s.check()
        a.publish(root / ('worker-' + alias + '.json'), dict(status='COMPLETED'))
    except sq.SafeQuitRequested:
        safe_selected = True
    except BaseException as exc:
        fet_capture('RUNTIME_ORIGINAL', exc)
        fet_capture('WORKER_ABORT', exc)
        if a is not None:
            a.publish(root / ('worker-' + alias + '.json'), dict(status='ABORT', exception_type=type(exc).__name__))
        barrier.abort()
        raise SystemExit(1)
    finally:
        if not safe_selected:
            sq.close_handles(quit_owned)
            for driver in driver_ref:
                with contextlib.suppress(Exception):
                    fet_context('WORKER_QUIT')
                    try:
                        driver.quit()
                    except BaseException as exc:
                        fet_capture('CLEANUP', exc)
                        raise
    if safe_selected:
        # retry_worker finally has already returned from driver.quit().
        sq.worker_complete(root, alias, expected_binding, quit_owned)


def preflight():
    a, m, binding, path = rt.context()
    latest, chain = rt.history_preflight(m, binding)
    return a, m, binding, path, latest, chain


def reservation_summary(binding, latest, canonical):
    lines = ['CURRENT RESERVATION LIST (this exact snapshot will execute)',
             'Path: ' + rt.RESERVATION_LIST_RELATIVE_PATH,
             'Month: ' + binding['configuration']['month']]
    for w in ('A', 'B'):
        for i, request in enumerate(binding['configuration']['requests'][w], 1):
            past = latest.get((w, request['date'], canonical(request['name'])), {})
            lines.append(w + str(i) + ': ' + request['date'] + ' | ' + request['start_time'] + ' | ' + request['name'] + ' | ' +
                         ','.join(map(str, request['positions'])) + ' | history=' + past.get('state', 'NO_RELEVANT_HISTORY'))
    lines += ['Current server/manual reservation state is Owner-verified, not inferred from Journal absence.',
              'For historical CONFIRMED targets, confirm cancellation/current non-held state explicitly before Enter.',
              'If held, uncertain, manually changed, or interrupted: stop. Never override an unresolved Journal.']
    return '\n'.join(lines)


def verify_live_environment():
    expected = rt.read(rt.MANIFEST)['fixed_configuration']['live_environment']
    require(sys.version.split()[0] == expected['python'], 'LIVE_PYTHON_VERSION_MISMATCH')
    for name, version in expected['packages'].items():
        require(importlib.metadata.version(name) == version, 'LIVE_DEPENDENCY_VERSION_MISMATCH')


def readonly_quit(_prompt):
    choice = console_enter('読取専用確認を終える場合は Q または q + Enter: ')
    require(choice in ('Q', 'q'), 'READONLY_Q_REQUIRED')
    return choice


def main():
    from admission_control import startup_history
    launcher_started = dict(timestamp=stamp(), monotonic=time.perf_counter())
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Use only after separate Operational Release authorization')
    parser.add_argument('--readonly', action='store_true', help='Pre-GO Q/q only; no reservation GO')
    args = parser.parse_args()
    require(not (args.live and args.readonly), 'CONFLICTING_RUN_MODE')
    a, m, binding, path, latest, chain = preflight()
    print(reservation_summary(binding, latest, m.normalize_lesson_name))
    if not (args.live or args.readonly):
        from local_preflight import run
        run(rt, a, m, binding, verify_live_environment)
        print('LOCAL PREFLIGHT PASS (checked capabilities only); Human GO not recorded; no browser/admission/authorization.')
        print('LOCAL_PREFLIGHT_TOTAL_MS=' + str(round((time.perf_counter() - launcher_started['monotonic']) * 1000, 3)))
        return
    verify_live_environment()
    require(os.name == 'nt' and not ctypes.windll.shell32.IsUserAnAdmin(), 'STANDARD_WINDOWS_USER_REQUIRED')
    require(m.webdriver is not None and m.jaconv is not None, 'NATIVE_DEPENDENCIES_REQUIRED')
    require(sys.stdin.isatty(), 'INTERACTIVE_OWNER_CONSOLE_REQUIRED')
    for alias, user in zip(('A', 'B'), m.users):
        WindowsCredentials().validate(binding_for(m, alias, user))
    print('This program does not grant Operational Release. Read-only mode accepts Q/q only.')
    rt.STATE.mkdir(parents=True, exist_ok=True)
    session = uuid.uuid4().hex; lock = rt.STATE / 'execution.lock'
    a.publish(lock, dict(session=session, created=a.now()))
    owner_lock_bytes = lock.read_bytes()
    lease = FrozenInputs()
    root, processes, barrier, manager = None, [], None, None
    quit_selected, quit_requested = False, None
    try:
        lease.add(rt.input_paths())
        inventory = rt.journal_inventory()
        # One post-lease context validates exactly the bytes now pinned. Child
        # workers also validate their own startup context before their first Barrier.
        fresh = rt.context()
        require(a.exact(fresh[2], binding), 'CONFIGURATION_CHANGED_BEFORE_FREEZE')
        latest, chain = rt.history_preflight(m, binding, active_session=session)
        require(rt.journal_inventory() == inventory, 'HISTORY_CHANGED_DURING_FREEZE')
        root = rt.STATE / session
        store = rt.make_store(a, m, binding, path, root)
        current_history = []
        for entry in store.all_entries():
            old = latest.get((entry['worker'], entry['date'], m.normalize_lesson_name(entry['lesson'])))
            current_history.append(dict(request_id=entry['request_id'], prior=old))
        store.prepare(current_history, chain); store.consume(session)
        os.environ['PHASE8_4_MODE'] = 'production'
        os.environ['PHASE8_8_3_LOG_DIR'] = str(root / 'native_logs')
        os.environ['PHASE8_8_3_LOG_FILE'] = str(root / 'native_logs/production.log')
        manager = multiprocessing.Manager()
        counts, results = manager.dict(), manager.list()
        ack, timings = manager.dict(), manager.dict(launcher_started=launcher_started)
        final_requested = multiprocessing.Event()
        quit_requested = multiprocessing.Event()
        barrier = multiprocessing.Barrier(3, timeout=720)
        processes = [multiprocessing.Process(target=worker, args=(w, session, binding, barrier,
            counts, results, final_requested, ack, timings, quit_requested)) for w in ('A', 'B')]
        for process in processes:
            process.start()
        # Keep the inventory captured under the original leases. Taking a new
        # baseline here would accept an unvalidated historical addition during login.
        final_guard = FinalGuard(store, binding, root, lease, inventory)

        def ready():
            final_guard.prepare()
            print(reservation_summary(store.snapshot(), latest, m.normalize_lesson_name))

        def quit_before_go(choice, both_ready):
            nonlocal quit_selected
            quit_selected = True
            sq.request(root, binding, choice, both_ready, final_guard.check)
            quit_requested.set()
            final_requested.set()  # wake final_verify; never release GO barrier
            return dict(safe_quit=True)
        timing = HumanGate().release(barrier, ready, final_requested, ack, final_guard.check,
                                    final_guard.record,
                                    ask=readonly_quit if args.readonly else console_enter,
                                    on_quit=quit_before_go)
        if timing.get('safe_quit') is True:
            for process in processes:
                process.join(timeout=20)
            require(all(p.pid and not p.is_alive() and p.exitcode == 0 for p in processes), 'QUIT_WORKER_EXIT')
            manager.shutdown()
            manager = None
            sq.complete_quit(root, binding, processes, lock, owner_lock_bytes, lease.close)
            print('SAFE QUIT: Human GO not executed; Submit/Cancel 0; non-success closeout complete.')
            return
        # Measurement publication is deferred until workers complete; it is not
        # needed to authorize reservation or determine any reservation outcome.
        for process in processes:
            process.join()
        a.publish(root / 'operational_timing.json', dict(**timing, worker_timestamps=dict(timings)))
        rows = []
        for row in list(results):
            row = dict(row); row['worker'] = store.bindings.get(row.pop('username', None)); rows.append(row)
        a.publish(root / 'results.json', dict(results=rows, worker_exit_codes=[p.exitcode for p in processes]))
        require(all(p.exitcode == 0 for p in processes), 'WORKER_ABNORMAL_TERMINATION')
        require(all(row.get('final_result') in ('CONFIRMED', 'ALREADY_RESERVED', 'FAILED_FINAL')
                    for row in rows), 'REQUESTS_UNRESOLVED')
    finally:
        if quit_selected:
            if quit_requested is not None:
                quit_requested.set()
                final_requested.set()
            if barrier is not None:
                barrier.abort()
            for process in processes:
                if process.pid and process.is_alive():
                    process.join(timeout=20)
            if not any(p.pid and p.is_alive() for p in processes):
                lease.close()
                if manager is not None:
                    manager.shutdown()
        else:
            if barrier is not None:
                barrier.abort()
            for process in processes:
                if process.pid and process.is_alive():
                    process.join(timeout=20)
            active = any(p.pid and p.is_alive() for p in processes)
            if not active:
                if root is not None and root.exists():
                    a.publish(root / 'finished.json', dict(lifecycle='CONSUMED_NO_RESTART', created=a.now()))
                lease.close()
                lock.unlink()
                if manager is not None:
                    manager.shutdown()
            else:
                # Retain leases and the lock while a worker is active. Interruption
                # leaves a durable stale lock and incomplete run for manual recovery.
                for process in processes:
                    if process.pid and process.is_alive():
                        process.join()
                lease.close()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    try:
        main()
    except BaseException as exc:
        print('RUNTIME FAIL CLOSED: ' + type(exc).__name__ + ((': ' + str(exc)) if isinstance(exc, ValueError) else ''))
        raise SystemExit(1)

