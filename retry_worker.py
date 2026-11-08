"""Worker-local three-pass execution using the existing guarded action functions."""
import copy
from diagnostic import fet_context, fet_capture
import time
from pathlib import Path
import ag01_ui_back as navigation
import retry_continuation as rc
from safe_quit import SafeQuitRequested


def install(m, store, session, alias):
    journal = store.retry_journal(alias)
    user = m.users[0 if alias == 'A' else 1]
    requests = user['lesson_requests']

    def rid(request):
        matches = [i for i, r in enumerate(requests) if m._journal_identity(user['username'], r) ==
                   m._journal_identity(user['username'], request)]
        rc.require(len(matches) == 1, 'REQUEST_IDENTITY')
        return alias+str(matches[0]+1)

    def compat(attempt, request):
        value = copy.deepcopy(attempt)
        value.update(identity=m._journal_identity(user['username'], request),
                     request_fingerprint=m._request_fingerprint(user['username'], request),
                     preferred_positions=list(request['positions']), attempt_count=attempt['attempt_no'],
                     run_id=session, action_boundary='POSITION_NATIVE_CLICK' if attempt['action_intent'] else None)
        return value

    def reader(username):
        store.check()
        rc.require(username == user['username'], 'CROSS_USER_ACCESS')
        out = m._empty_journal(username)
        rows = journal.view()[0]
        for request in requests:
            row = rows[rid(request)]
            if row['attempts']:
                value=compat(row['attempts'][-1], request)
                if row['result']=='ALREADY_RESERVED' and value['state']!='ALREADY_RESERVED':
                    value.update(original_attempt_state=value['state'],state='ALREADY_RESERVED',reservation_origin='INQUIRY_RESERVED')
                out['requests'][m._journal_request_key(m._journal_identity(username, request))] = value
        return out, rc.SCHEMA

    def writer(username, request, state, selected_position=None, **fields):
        store.check()
        rc.require(username == user['username'], 'CROSS_USER_ACCESS')
        key = rid(request)
        prior = journal.view()[0][key]['attempts'][-1]
        # A missing position argument never erases an already durable selection.
        if selected_position is not None:
            fields['selected_position'] = selected_position
        if state == 'ACTION_INTENT':
            fields.update(action_intent=True, mutation_possible=True)
        if state == 'SUBMIT_INTENT':
            fields.update(submit_intent_durable=True, submission_possible=True)
        if prior['submit_intent_durable'] and state == 'PRESERVATION_UNKNOWN':
            state = 'UNKNOWN_AFTER_SUBMIT'
        return compat(journal.update(key, state, **fields), request)

    m._read_journal = reader
    m._journal_write_state = writer
    m.JOURNAL_MAX_ATTEMPTS = 3
    m._rc_runtime = dict(store=store, journal=journal, alias=alias, session=session, rid=rid)


def collect(m, driver, user, request):
    """Reuse exact positive snapshots; absence requires explicit coverage input."""
    fet_context('RECONCILIATION_COLLECT')
    deadline = time.monotonic()+15
    evidence = []
    complete = m._cla1_normal_ui_state(driver,
        '/DSPWebUser/LESSON/ReserveLessonSchedule/Complete', 'レッスン予約完了')
    listing = m._cla1_normal_ui_state(driver,
        '/DSPWebUser/LESSON/LessonList/ShowList', '予約の確認・キャンセル')
    if not all(listing.get(k) is True for k in ('origin', 'path', 'title', 'ready')):
        if not (complete.get('origin') and complete.get('path') and complete.get('ready')):
            rc.require(navigation.to_menu(m, driver, user, request, deadline, evidence), 'AG01_MENU_RECOVERY_FAILED')
        rc.require(m._cla1_normal_ui_to_list(driver, deadline, {'ag01': evidence}), 'LIST_NAVIGATION_FAILED')
    document = driver.find_element('tag name', 'html')
    started_at = rc.datetime.now(rc.timezone.utc).isoformat()
    first = m._phase810_read_raw_snapshot(driver)
    time.sleep(min(m.RECONCILIATION_OBSERVATION_DELAY_SECONDS, max(0, deadline-time.monotonic())))
    second = m._phase810_read_raw_snapshot(driver)
    rc.require(driver.execute_script('return arguments[0] === document.documentElement && arguments[0].isConnected;', document) is True,
               'LIST_DOCUMENT_CHANGED')
    rc.require(time.monotonic() < deadline, 'LIST_DEADLINE')
    normalized = []
    generation = __import__('uuid').uuid4().hex
    for raw in (first, second):
        parsed = m._phase810_snapshot_from_raw(raw, user.get('expected_member_identifier'))
        normalized.append(dict(worker=m._rc_runtime['alias'], user_binding='FIXED_USER_'+m._rc_runtime['alias'],
            generation=generation, document_id=getattr(document, 'id', None),
            page_verified=parsed.page_identity_verified, identity_verified=parsed.user_identity_verified,
            render_complete=parsed.render_complete, parser_complete=isinstance(raw.get('rows'), list)
                and len(parsed.reservations) == len(raw['rows'])
                and all(r.normalized_date and r.canonical_lesson and type(r.position) is int
                        and r.status == '予約中' and ('start_time' not in request or r.start_time is not None) for r in parsed.reservations),
            rows=[dict(date=r.normalized_date, lesson=r.canonical_lesson, position=r.position,
                       **({'start_time': r.start_time} if 'start_time' in request else {}),
                       status='ACTIVE' if r.status=='予約中' else r.status) for r in parsed.reservations],
            coverage=raw.get('coverage'), normalization_version='phase810',
            started_at=started_at, ended_at=rc.datetime.now(rc.timezone.utc).isoformat()))
    return normalized


def fail_attempt(m, driver, user, request, result, path):
    runtime = m._rc_runtime
    journal, rid = runtime['journal'], runtime['rid'](request)
    fet_context('FAIL_ATTEMPT', rid)
    runtime['store'].check()
    reason_code = str(result.details.get('reason_code') or '')
    rc.require(not any(word in reason_code or word in result.state for word in
        ('JOURNAL_', 'ALREADY_RESERVED', 'IDENTITY', 'LOGIN_REQUIRED',
         'ACTION_BOUNDARY', 'FINAL_RESEND', 'PRIMARY_GUARD_REJECTED')),
        'UNSAFE_FAILURE_CLASSIFICATION')
    prior = journal.view()[0][rid]['attempts'][-1]
    rc.require(path in rc.SAFE_PATHS and prior['state'] == 'IN_PROGRESS'
        and all(prior[k] is False for k in ('action_intent', 'submit_intent_durable',
            'submission_attempted', 'submission_possible', 'mutation_possible'))
        and prior['selected_position'] is None, 'PRE_ACTION_PROOF_REQUIRED')
    rc.require(m._cla1_identity_guard(driver, user) is None, 'IDENTITY_UNKNOWN')
    # Recovery cannot consume/rebuild an admission, alter this chain, or change users.
    checkpoint = (rc.digest(journal.events()), rc.digest(runtime['store'].snapshot()),
                  rc.digest(user), rc.digest(request))
    def binding_check():
        store = runtime['store']
        store.check()
        store.validate_admission()
        admission = store.admission(runtime['session'])
        rc.require(m._rc_runtime is runtime and runtime['alias'] in ('A', 'B')
            and m.users[0 if runtime['alias'] == 'A' else 1] is user
            and runtime['session'] == store.root.name == journal.execution
            and runtime['rid'](request) == rid
            and rc.digest(admission['binding']) == checkpoint[1]
            and (rc.digest(journal.events()), rc.digest(store.snapshot()),
                 rc.digest(user), rc.digest(request)) == checkpoint, 'RECOVERY_BINDING_CHANGED')
        rc.continuation_admission(journal.view()[0], rid)
    binding_check()
    recovery = continuation_source(m, driver, user, request, rid, binding_check)
    binding_check()
    rc.require(m._cla1_identity_guard(driver, user) is None, 'IDENTITY_UNKNOWN')
    certificate = dict(path=path, binding_verified=True, chain_verified=True,
                       write_before_action=True, checkpoint_known=True)
    journal.update(rid, 'PRE_SUBMIT_FAILED', safe_certificate=certificate,
        phase='P'+str(path).zfill(2), result_code=result.code,
        failure_reason=result.details.get('reason_code') or result.state,
        original_reason=result.reason,
        observation_status=result.state, observation_details=m._cla1_redact(result.details))
    row=journal.view()[0][rid]
    if len(row['attempts'])==3:
        journal.append('FAILED_FINAL',dict(reason='ATTEMPT_LIMIT_REACHED_SAFE_PRE_SUBMIT_FAILURE',
            attempt_shas=[rc.digest(a) for a in row['attempts']]),rid)
    m.log_event('request_result', m.make_result('NG', 'REQUEST_FAILED_PRE_SUBMIT'), user=user, request=request)
    m.log_event('worker_recovery', m.make_result('OK', 'WORKER_RECOVERED', recovery_method=recovery), user=user)


RECOVERY_SNAPSHOT = r'''/* CLA1_CONTINUATION_SNAPSHOT: existing Core runtime selectors */
const visible=e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();
  return s.display!=='none'&&s.visibility!=='hidden'&&s.visibility!=='collapse'&&
    Number(s.opacity||1)!==0&&s.pointerEvents!=='none'&&r.width>0&&r.height>0;};
return {document:document.documentElement, complete:document.readyState==='complete',
  jquery_active:window.jQuery&&Number.isInteger(window.jQuery.active)?window.jQuery.active:null,
  overlay_count:Array.from(document.querySelectorAll('.blockUI,.blockOverlay,.modal-backdrop,.loading,.overlay,[aria-busy="true"]')).filter(visible).length,
  unselected:document.querySelectorAll('input[id^="LessonPosNo"]:checked').length===0};
'''


def recovery_snapshot(m, driver, user):
    rc.require(m._cla1_identity_guard(driver, user) is None, 'IDENTITY_UNKNOWN')
    rc.require(driver.current_url in tuple(navigation.ORIGIN + path for path in
        (navigation.SCHEDULE, navigation.DETAIL, navigation.MENU)), 'CONTINUATION_SOURCE_UNKNOWN')
    value = driver.execute_script(RECOVERY_SNAPSHOT)
    rc.require(isinstance(value, dict) and value.get('document') is not None
        and type(value.get('complete')) is bool and type(value.get('overlay_count')) is int
        and value['overlay_count'] >= 0 and value.get('unselected') is True,
        'CONTINUATION_SNAPSHOT_UNSAFE')
    return value


def settled_source(m, driver, user, request, snapshot):
    if not (snapshot['complete'] and type(snapshot.get('jquery_active')) is int
            and snapshot['jquery_active'] == 0 and snapshot['overlay_count'] == 0):
        return 'UNKNOWN'
    current = navigation.state(m, driver, user, request)
    rc.require(m._cla1_identity_guard(driver, user) is None, 'IDENTITY_UNKNOWN')
    if driver.execute_script('return arguments[0] === document.documentElement && arguments[0].isConnected;', snapshot['document']) is not True:
        return 'UNKNOWN'
    fresh = recovery_snapshot(m, driver, user)
    if not (fresh['document'] == snapshot['document'] and fresh['complete']
            and type(fresh.get('jquery_active')) is int and fresh['jquery_active'] == 0
            and fresh['overlay_count'] == 0):
        return 'UNKNOWN'
    return current


def continuation_source(m, driver, user, request, rid, binding_check):
    """State-driven recovery, then one bound automatic login if needed; no action replay."""
    deadline = time.monotonic() + 15
    evidence = []
    fet_context('FAIL_STATE_CHECK', rid)
    back_used = False
    while time.monotonic() < deadline:
        try:
            snapshot = recovery_snapshot(m, driver, user)
            current = settled_source(m, driver, user, request, snapshot)
            if time.monotonic() >= deadline:
                break
            if current in ('SCHEDULE', 'MENU'):
                binding_check()
                rc.require(navigation.state(m, driver, user, request) in ('SCHEDULE', 'MENU')
                    and time.monotonic() < deadline, 'CONTINUATION_SOURCE_UNKNOWN')
                return 'DETAIL_BACK' if back_used else 'OBSERVED'
            if current == 'DETAIL':
                rc.require(not back_used, 'DETAIL_RECOVERY_FAILED')
                binding_check()
                fet_context('FAIL_BACK', rid)
                back_used = True
                if not navigation.back(m, driver, user, request, 'DETAIL', deadline, evidence):
                    break  # never replay an uncertain Back
                continue
        except (m.StaleElementReferenceException, m.TimeoutException):
            pass  # observation only; reacquire from the new document on the next poll
        time.sleep(min(.25, max(0, deadline - time.monotonic())))
    # This request is still IN_PROGRESS with positive pre-action proof. Abandoning
    # a pending Schedule Ajax never resends it or a reservation POST.
    snapshot = recovery_snapshot(m, driver, user)
    current = navigation.state(m, driver, user, request)
    known_schedule = (driver.current_url == navigation.ORIGIN + navigation.SCHEDULE
        and m.classify_reservation_page_state(driver).state in
            ('RESERVATION_PAGE_READY', 'PAGE_LOADING_OR_INCOMPLETE', 'CONGESTED'))
    rc.require(current in ('DETAIL', 'SCHEDULE', 'MENU') or known_schedule, 'CONTINUATION_SOURCE_UNKNOWN')
    binding_check()
    relogin = getattr(m, '_cla1_relogin', None)
    rc.require(callable(relogin), 'SAFE_RELOGIN_UNAVAILABLE')
    login = relogin(driver, m.WebDriverWait(driver, 10), user)
    rc.require(login.code == 'OK' and login.state == 'LOGINED', 'SAFE_RELOGIN_FAILED')
    binding_check()
    rc.require(m._cla1_identity_guard(driver, user) is None, 'IDENTITY_UNKNOWN')
    driver._request_local_inquiry = None
    page = m.open_reservation_page(driver, m.WebDriverWait(driver, 10), max_retries=1)
    rc.require(page.code == 'OK' and page.state == 'RESERVATION_PAGE_READY', 'SCHEDULE_RECOVERY_FAILED')
    fet_context('FAIL_CONTINUATION_CHECK', rid)
    snapshot = recovery_snapshot(m, driver, user)
    rc.require(settled_source(m, driver, user, request, snapshot) == 'SCHEDULE', 'CONTINUATION_SOURCE_UNKNOWN')
    binding_check()
    return 'RELOGIN'


def request_status(row):
    """Display names derived from existing authoritative states; no new Journal schema."""
    if row['result'] in ('CONFIRMED', 'ALREADY_RESERVED'):
        return 'REQUEST_' + row['result']
    attempt = row['attempts'][-1] if row['attempts'] else {}
    if row['result'] == 'UNKNOWN_AFTER_SUBMIT' or (attempt.get('submit_intent_durable') is True
            and attempt.get('provisional_evidence_state') != 'PROVISIONAL_ACCEPTED'):
        return 'REQUEST_UNKNOWN_AFTER_SUBMIT'
    if row['attempts'] and rc.safe(row['attempts'][-1]):
        return 'REQUEST_FAILED_PRE_SUBMIT'


def report_requests(m, user, journal):
    for row in journal.view()[0].values():
        status = request_status(row)
        if status:
            m.log_event('request_result', m.make_result('OBSERVED', status), user=user,
                request=dict(date=row['entry']['date'], name=row['entry']['lesson']))


def failure_path(stage, result):
    """Map existing observable branches, preserving their original reason data."""
    if stage == 'date':
        if result.state == 'SCHEDULE_RANGE_INSPECTED' and result.code != 'DATE_OUT_OF_RANGE':
            return 7
        if result.state in ('SCHEDULE_PAGE_MOVED', 'SCHEDULE_NAVIGATION_UNKNOWN') and \
                'budget exceeded' not in (result.reason or ''):
            return 8
        return 9
    if stage == 'lesson':
        if result.code == 'AMBIGUOUS' or 'AMBIGUOUS' in result.state:
            return 13
        if result.code == 'NOT_FOUND':
            return 10
        if result.code == 'UNKNOWN' and result.details.get('candidate_count') == 0:
            return 12
        return 11
    raise ValueError('UNKNOWN_FAILURE_STAGE')


def observe_before_action(m, driver, user, request, checkpoint, operation):
    """P27 only around known non-reservation observation/navigation calls.

    No Journal writes, position operations, finalizer, or diagnostic handler are
    inside this catch. Their failures must propagate with last durable state.
    """
    rc.require(checkpoint in ('OPEN_SCHEDULE', 'OBSERVE_DATE', 'OBSERVE_LESSON'),
               'UNKNOWN_PRE_ACTION_CHECKPOINT')
    try:
        return operation()
    except Exception as exc:
        result = m.make_result('UNKNOWN', 'PRE_ACTION_EXCEPTION', reason=type(exc).__name__,
            reason_code='PRE_ACTION_EXCEPTION_' + checkpoint, control_checkpoint=checkpoint)
        fail_attempt(m, driver, user, request, result, 27)
        return None


def run(m, user, barrier, counts, results, recovery_session=None):
    rc.require(recovery_session is None, 'HISTORICAL_SESSION_OUT_OF_SCOPE')
    runtime = m._rc_runtime
    journal, store, rid = runtime['journal'], runtime['store'], runtime['rid']
    m._configure_phase6_1_log()
    options = m.webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={user['profile_path']}")
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--log-level=3')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    from driver_selection import CHROME, chrome_service
    options.binary_location = str(CHROME)
    driver = m.webdriver.Chrome(service=chrome_service(), options=options)
    driver.phase8_1_username = user['username']
    driver._request_local_inquiry = None
    wait = m.WebDriverWait(driver, 10)
    try:
        m.log_event('browser_started', m.make_result('OK', 'BROWSER_STARTED'), user=user)
        login = m.login_and_verify(driver, wait, user)
        m.log_event('login_verification', login, user=user)
        barrier.wait()
        barrier.wait()
        rc.require(login.code == 'OK' and login.state == 'LOGINED', 'LOGIN_FAILED')
        m._phase7_1_barrier_release[user['username']] = time.perf_counter()
        counts[user['username']] = 0
        batch = m._batch_start(driver, user)
        rc.require(not batch['stop_reason'], 'BATCH_ADMISSION_REJECTED')
        held = False
        for pass_no in range(1, 4):
            if journal.summary()['runtime']=='COMPLETED':
                break
            for request_index, request in enumerate(user['lesson_requests'], 1):
                fet_context('REQUEST', runtime['alias'] + str(request_index))
                row = journal.view()[0][rid(request)]
                if row['result'] in ('CONFIRMED', 'ALREADY_RESERVED', 'FAILED_FINAL'):
                    continue
                store.check()
                if row['result']=='FINALIZATION_PENDING':
                    continue
                if row['attempts'] and row['attempts'][-1]['pass_no']==journal.view()[1]+1 and rc.safe(row['attempts'][-1]):
                    continue
                if row['attempts']:
                    rc.reconcile(journal, fresh_only=rid(request))
                # Validate all previous request lifecycles before any new begin.
                rc.continuation_admission(journal.view()[0], rid(request))
                journal.begin(rid(request))
                batch['previous'] = request
                batch['entered'].append(m._journal_request_key(m._journal_identity(user['username'], request)))
                m._latency_mark(user, request, 'request_started')
                page = observe_before_action(m, driver, user, request, 'OPEN_SCHEDULE',
                    lambda: m.open_reservation_page(driver, wait))
                if page is None:
                    continue
                if page.code != 'OK':
                    fail_attempt(m, driver, user, request, page, 4 if page.retryable else 5)
                    continue
                rc.require(m._cla1_identity_guard(driver, user) is None, 'SCHEDULE_IDENTITY_UNKNOWN')
                date = observe_before_action(m, driver, user, request, 'OBSERVE_DATE',
                    lambda: m.ensure_target_date_visible(driver, wait, request['date']))
                if date is None:
                    continue
                if date.code != 'OK':
                    fail_attempt(m, driver, user, request, date, failure_path('date', date))
                    continue
                lesson = observe_before_action(m, driver, user, request, 'OBSERVE_LESSON',
                    lambda: m.find_target_lesson(driver, wait, request))
                if lesson is None:
                    continue
                if lesson.code != 'OK' or lesson.value is None:
                    path = failure_path('lesson', lesson)
                    fail_attempt(m, driver, user, request, lesson, path)
                    continue
                guard = m.Phase87ActionGuard()
                detail = m.phase871_execute_stage('lesson', driver, wait, request, user,
                    lambda: m.open_lesson_detail(driver, wait, lesson.value, request, user=user),
                    lambda: m.open_lesson_detail(driver, wait, lesson.value, request, user=user), guard=guard)
                if detail.state == 'INQUIRY_RESERVED':
                    proof=detail.details['reserved_evidence']
                    rc.reserved_result(journal, rid(request), proof)
                    driver._request_local_inquiry=dict(request=request, verified=True, click_binding=proof['click_binding'])
                    evidence=[]
                    rc.require(navigation.back(m, driver, user, request, 'INQUIRY', time.monotonic()+25, evidence), 'INQUIRY_EXIT_FAILED')
                    continue
                rc.require(detail.state != 'INQUIRY_UNVERIFIED', 'INQUIRY_UNVERIFIED')
                if detail.state != 'DETAIL_READY':
                    fail_attempt(m, driver, user, request, detail, 15 if detail.state=='DETAIL_NOT_RESERVABLE' else 14)
                    continue
                selection = m.phase871_execute_stage('position', driver, wait, request, user,
                    lambda: m.select_preferred_position(driver, wait, request, detail, user=user),
                    lambda: m.select_preferred_position(driver, wait, request, detail, user=user), guard=guard)
                if selection.state != 'POSITION_SELECTED':
                    path = 17 if selection.state == 'NO_PREFERRED_POSITION_AVAILABLE' else 16
                    if any(a.get('action') == 'STOPPED_BEFORE_CLICK'
                           for a in selection.details.get('selection_attempts', [])):
                        path = 18
                    if selection.details.get('reason_code') == 'REOBSERVE_NON_SUCCESS':
                        path = 21
                    fail_attempt(m, driver, user, request, selection,
                                 path)
                    continue
                next_result = m.phase871_execute_stage('next', driver, wait, request, user,
                    lambda: m.click_next_and_diagnose(driver, wait, request, selection, user=user),
                    lambda: m.click_next_and_diagnose(driver, wait, request, selection, user=user),
                    selected_position=selection.details['selected_position'], guard=guard)
                final = m.diagnose_final_submit(driver, wait, request, selection, next_result, user=user)
                submit = m.submit_final_once_and_diagnose(driver, wait, request, selection, final, user=user)
                if submit.state != 'PROVISIONAL_ACCEPTED':
                    # The action boundary is durable. Preserve the failed observation
                    # as HOLD (or UNKNOWN_AFTER_SUBMIT when Submit intent exists),
                    # then return the request row without starting another attempt.
                    m._journal_write_state(user['username'], request, 'PRESERVATION_UNKNOWN',
                        failure_reason=submit.details.get('reason_code') or submit.state,
                        observation_status=submit.state, result_code=submit.code,
                        observation_details=m._cla1_redact(submit.details))
                    m.log_event('worker_result', m.make_result('STOP', 'WORKER_HELD'), user=user)
                    held = True
                    break
            if held:
                break
            fet_context('LOOP_RECONCILIATION')
            rows=journal.view()[0]
            snapshots=(None,None)
            if any(r['result']=='AWAITING_RECONCILIATION' for r in rows.values()):
                snapshots=collect(m,driver,user,user['lesson_requests'][-1])
            fet_context('RECONCILIATION_APPLY')
            rc.reconcile(journal,*snapshots)
            if journal.view()[1] < pass_no:
                m.log_event('worker_result', m.make_result('STOP', 'WORKER_HELD'), user=user)
                held = True
                break
            if journal.summary()['runtime'] == 'COMPLETED':
                break
        fet_context('FINALIZATION')
        summary = journal.summary()
        report_requests(m, user, journal)
        counts[user['username']] = summary['confirmed_count']
        for row in summary['requests']:
            results.append(dict(username=user['username'], **row))
        if not held:
            rc.require(summary['runtime'] == 'COMPLETED', 'REQUESTS_UNRESOLVED')
    except SafeQuitRequested:
        raise  # expected pre-GO path; finally still performs driver.quit
    except BaseException as exc:
        # Reporting must not replace the original fail-closed exception.
        try:
            m.log_event('worker_result', m.make_result('STOP', 'WORKER_ABORTED'), user=user)
            report_requests(m, user, journal)
            summary = journal.summary()
            counts[user['username']] = summary['confirmed_count']
            if not any(row.get('username') == user['username'] for row in list(results)):
                for row in summary['requests']:
                    results.append(dict(username=user['username'], **row))
        except Exception:
            pass
        fet_capture('RUNTIME_ORIGINAL', exc)
        raise
    finally:
        fet_context('RUNTIME_QUIT')
        try:
            driver.quit()
        except BaseException as exc:
            fet_capture('CLEANUP', exc)
            raise
