"""CLA-1 admission facts and dynamic Journal invariants. No Owner time/window/grant."""
import copy
import re
from pathlib import Path
from runtime_config import require, digest
from lesson_target import valid_time

SCHEMA = 'CLA1_MINIMUM_SAFE_V3'
GO_SEMANTIC = 'OWNER_CURRENT_LIST_CURRENT_STATE_AND_ONE_BATCH_AUTHORIZED'
UNAVAILABLE = 'ALL_PREFERRED_POSITIONS_CONCLUSIVELY_UNAVAILABLE'


def same(a, b):
    return type(a) is type(b) and a == b


def entries(binding):
    data = binding['configuration']
    require(data['active_users'] == ['A', 'B'], 'TWO_ACTIVE_WORKERS_REQUIRED')
    result = []
    for worker in ('A', 'B'):
        rows = data['requests'][worker]
        require(0 < len(rows) <= 7, 'WORKER_REQUEST_COUNT')
        for i, request in enumerate(rows, 1):
            positions = request['positions']
            require(bool(positions) and all(type(p) is int and p > 0 for p in positions)
                    and len(set(positions)) == len(positions), 'RANKING_BINDING')
            entry = dict(worker=worker, user_binding='FIXED_USER_' + worker,
                request_id=worker + str(i), date=request['date'], lesson=request['name'],
                positions=list(positions), candidate_sha=binding['component_shas']['batch'])
            if 'start_time' in request:
                require(valid_time(request['start_time']), 'START_TIME_BINDING')
                entry['start_time'] = request['start_time']
            result.append(entry)
    require(data['order'] == [r['request_id'] for r in result] and
            data['active_count'] == len(result), 'REQUEST_ORDER_BINDING')
    require(binding['reservation_list_identity'] == digest(data), 'CONFIGURATION_IDENTITY')
    keys = [(w, *key) for w in ('A', 'B') for key in binding['request_keys'][w]]
    require(len(keys) == len(result) == len(set(keys)), 'DUPLICATE_REQUEST')
    return result


def validate_chain(records, entry, terminal=False):
    """Current records may be pending; a past run must have a safe final outcome."""
    require(bool(records), 'MISSING_REQUEST_OUTCOME')
    previous = None
    for record in records:
        state = record.get('state')
        require(type(record.get('attempt_count')) is int and record['attempt_count'] == 1,
                'ATTEMPT_LIMIT')
        require(record.get('preferred_positions') == entry['positions'], 'RECORD_RANKING')
        require(bool(record.get('run_id')) and bool(record.get('first_started_at')),
                'RECORD_RUN_BINDING')
        selected = record.get('selected_position')
        require(selected is None or type(selected) is int and selected in entry['positions'],
                'RECORD_POSITION')
        if previous is None:
            require(state == 'IN_PROGRESS' and selected is None and
                    record.get('submit_intent_durable') is False and
                    record.get('submission_attempted') is False and not record.get('action_boundary'),
                    'INITIAL_RECORD_INVALID')
        else:
            require(record['run_id'] == previous['run_id'] and
                    record['first_started_at'] == previous['first_started_at'], 'RECORD_RUN_CHANGED')
            allowed = {'IN_PROGRESS': {'ACTION_INTENT', 'FAILED_FINAL', 'RETRY_EXHAUSTED', 'PRESERVATION_UNKNOWN'},
                       'ACTION_INTENT': {'SUBMIT_INTENT', 'PRESERVATION_UNKNOWN'},
                       'SUBMIT_INTENT': {'SUBMIT_INTENT', 'CONFIRMED'}}
            require(state in allowed.get(previous['state'], set()), 'JOURNAL_TRANSITION')
            if previous.get('selected_position') is not None:
                require(selected == previous['selected_position'], 'SELECTED_POSITION_CHANGED')
            if previous.get('submit_intent_durable'):
                require(record.get('submit_intent_durable') is True, 'INTENT_ROLLBACK')
            if previous.get('submission_attempted'):
                require(record.get('submission_attempted') is True, 'SUBMISSION_ROLLBACK')
        if state == 'ACTION_INTENT':
            require(selected is not None and record.get('action_boundary') == 'POSITION_NATIVE_CLICK',
                    'ACTION_INTENT_BINDING')
        if state in {'SUBMIT_INTENT', 'CONFIRMED'}:
            require(selected is not None and record.get('submit_intent_durable') is True
                    and record.get('action_boundary') == 'POSITION_NATIVE_CLICK', 'SUBMIT_INTENT_BINDING')
        if state == 'SUBMIT_INTENT' and previous and previous['state'] == 'SUBMIT_INTENT':
            require(record.get('provisional_evidence_state') == 'PROVISIONAL_ACCEPTED'
                    and (record.get('complete_evidence') or {}).get('positive') is True
                    and record.get('submission_attempted') is True
                    and record.get('reconciliation_pending') is True and bool(record.get('batch_id')),
                    'PROVISIONAL_EVIDENCE_REQUIRED')
        if state == 'CONFIRMED':
            proof = record.get('confirmation_evidence') or {}
            require(previous and previous.get('provisional_evidence_state') == 'PROVISIONAL_ACCEPTED'
                    and (previous.get('complete_evidence') or {}).get('positive') is True
                    and record.get('batch_id') == previous.get('batch_id') and bool(record.get('batch_id'))
                    and proof.get('positive') is True and proof.get('date') == entry['date']
                    and proof.get('lesson') == entry['lesson'] and proof.get('selected_position') == selected
                    and record.get('reconciliation_pending') is False
                    and record.get('submission_attempted') is True, 'POSITIVE_RECONCILIATION_REQUIRED')
        previous = record
    if not terminal:
        return
    if previous['state'] == 'CONFIRMED':
        return 'CONFIRMED'
    if [r['state'] for r in records] == ['IN_PROGRESS', 'FAILED_FINAL']:
        require(previous.get('last_reason_code') == UNAVAILABLE and all(
            r.get('submit_intent_durable') is False and r.get('submission_attempted') is False
            and not r.get('action_boundary') and not r.get('reconciliation_pending')
            and not r.get('provisional_evidence_state') for r in records), 'SAFE_UNSENT_PROOF_REQUIRED')
        return 'SAFE_UNSENT'
    raise ValueError('UNRESOLVED_OR_CRASHED_REQUEST')


def scan_run(directory, read, canonical, request_keys=None):
    """No old Owner receipts/windows/package reconstruction: only durable run safety."""
    require(directory.is_dir() and re.fullmatch('[a-f0-9]{32}', directory.name), 'UNKNOWN_RUN')
    admission = read(directory / 'admission.json')
    require(admission.get('schema') == SCHEMA and admission['session'] == directory.name, 'RUN_BINDING')
    bound = admission['binding']; expected = entries(bound)
    require(admission['entries'] == expected, 'HISTORICAL_REQUEST_BINDING')
    require(read(directory / 'consumed.json') == dict(session=directory.name, binding_sha=digest(bound)),
            'RUN_NOT_CONSUMED')
    go = read(directory / 'human_go.json')
    require(go.get('semantic') == GO_SEMANTIC and go.get('binding_sha') == digest(bound)
            and go.get('owner_current_absent') == [r['request_id'] for r in expected], 'HISTORICAL_GO_BINDING')
    require(read(directory / 'finished.json').get('lifecycle') == 'CONSUMED_NO_RESTART', 'RUN_NOT_FINISHED')
    require(read(directory / 'results.json').get('worker_exit_codes') == [0, 0], 'ABNORMAL_WORKER_EXIT')
    known = {'admission.json', 'consumed.json', 'human_go.json', 'finished.json', 'results.json', 'operational_timing.json'}
    known.update(prefix + '-' + w + '.json' for prefix in ('claim', 'login', 'worker') for w in ('A', 'B'))
    require(all((p.name == 'native_logs' and p.is_dir()) or (p.is_file() and
        (p.name in known or re.fullmatch('[AB]-[0-9]{6}\\.json', p.name))) for p in directory.iterdir()),
        'UNKNOWN_JOURNAL_ARTIFACT')
    outcomes = []
    for worker in ('A', 'B'):
        require(read(directory / ('claim-' + worker + '.json')) == dict(session=directory.name, worker=worker), 'WORKER_CLAIM')
        require(read(directory / ('login-' + worker + '.json')) == dict(code='OK', state='LOGINED'), 'WORKER_LOGIN')
        require(read(directory / ('worker-' + worker + '.json')).get('status') == 'COMPLETED', 'WORKER_INCOMPLETE')
        targets = [r for r in expected if r['worker'] == worker]; chains = [[] for _ in targets]
        for seq, path in enumerate(sorted(directory.glob(worker + '-*.json')), 1):
            event = read(path); i = event['index']
            require(type(i) is int and 0 <= i < len(targets) and type(event['sequence']) is int
                    and event['sequence'] == seq and path.name == worker + '-' + str(seq).zfill(6) + '.json'
                    and event['binding'] == targets[i], 'HISTORICAL_EVENT_BINDING')
            chains[i].append(event['record'])
        for target, chain in zip(targets, chains):
            if request_keys is not None and (worker, target['date'], canonical(target['lesson'])) not in request_keys:
                if chain:
                    validate_chain(chain, target, terminal=False)
                continue
            category = validate_chain(chain, target, terminal=True)
            outcomes.append(dict(worker=worker, date=target['date'], lesson=target['lesson'],
                                 canonical_lesson=canonical(target['lesson']), state=category,
                                 source_run=directory.name))
    return admission, outcomes


def startup_history(root, state, seed, read, sha, canonical, request_keys=None):
    """Validate every run; require safe outcomes for the admitted logical requests."""
    latest = {}
    for row in seed['latest']:
        require(row['state'] in {'CONFIRMED', 'SAFE_UNSENT', 'OWNER_VERIFIED_CANCELLED'}, 'UNSAFE_SEED')
        require(sha(root / row['source']['path']) == row['source']['sha256'] == row['token'], 'SEED_CHANGED')
        key = (row['worker'], row['date'], canonical(row['lesson']))
        require(key not in latest, 'AMBIGUOUS_SEED')
        latest[key] = copy.deepcopy(row)
    runs = []
    if state.exists():
        for directory in state.iterdir():
            if directory.name == 'execution.lock':
                continue
            admission, outcomes = scan_run(directory, read, canonical, request_keys)
            runs.append((admission, outcomes))
    runs.sort(key=lambda x: x[0]['ordinal'])
    previous = None
    for ordinal, (admission, outcomes) in enumerate(runs, 1):
        require(type(admission['ordinal']) is int and admission['ordinal'] == ordinal
                and admission['previous_run'] == previous, 'RUN_ORDER_OR_FORK')
        for row in outcomes:
            latest[(row['worker'], row['date'], row['canonical_lesson'])] = row
        previous = admission['session']
    return latest, dict(ordinal=len(runs) + 1, previous_run=previous)
