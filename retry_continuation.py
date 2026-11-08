"""OR-RC-20260921 append-only request/attempt and worker-pass contracts.

No browser creation or production I/O occurs on import.
"""
import copy
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 'CLA1_REQUEST_LOCAL_V1'
DESIGN = 'SRLR-20260922-01+R5R6-20260923'
NAMESPACE = 'schema-v2/cla1-request-local-v1'
MAX_ATTEMPTS = 3

# Immutable historical publication semantics; exact history comparison remains intact.
LEGACY_POSITION_REVIEW_MANIFESTS = frozenset(['327C919D948060CD0C1EE2E04A6C5F257E74356FB2C6394892469BB4898AFAB9', '3283B7BA23EED485CEB1AF656C568A4E97914000E105EEA2565F00D0BD829ADA', '80A2BD36A4B9D576175827994C981622E810D9A84607C5E1AE8EE232AA3B52FC', 'B149400FD946B4C125C11FA6B5A2E1F8F18E78D5342B7459D80A77B7DAA08989'])
SAFE_PATHS = set(range(4, 19)) - {6} | {21, 27}


def require(value, reason):
    if not value:
        raise ValueError(reason)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True).encode()).hexdigest().upper()


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs)


def publish(path, value):
    path = Path(path)
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, sort_keys=True, separators=(',', ':'))
        f.flush()
        os.fsync(f.fileno())
    require(read(path) == value, 'DURABLE_READBACK_FAILED')


def safe(attempt):
    return (attempt.get('state') == 'PRE_SUBMIT_FAILED' and
            all(attempt.get(k) is False for k in ('action_intent', 'submit_intent_durable',
                'submission_attempted', 'submission_possible', 'mutation_possible')) and
            attempt.get('selected_position') is None and
            isinstance(attempt.get('safe_certificate'), dict) and
            attempt['safe_certificate'].get('path') in SAFE_PATHS and
            all(attempt['safe_certificate'].get(k) is True for k in
                ('binding_verified', 'chain_verified', 'write_before_action', 'checkpoint_known')))


def fresh_request_ids(rows):
    """Only fully reduced, proven safe FAILED_FINAL requests may start anew."""
    eligible = []
    for rid, row in rows.items():
        if row['result'] == 'FAILED_FINAL':
            require(len(row['attempts']) == MAX_ATTEMPTS and all(safe(a) for a in row['attempts']), 'FRESH_SAFE_PROVENANCE_REQUIRED')
            eligible.append(rid)
    return sorted(eligible)


def continuation_admission(rows, rid):
    """Same execution only. NOT_STARTED is not an unresolved attempt.

    Provisional Complete is the existing bounded exception; no other active
    intent can be bypassed by selecting a different request.
    """
    require(rid in rows, 'UNREGISTERED_REQUEST')
    proof = []
    for key, row in rows.items():
        if key == rid:
            continue
        require(not row.get('worker_stop'), 'RESOLVED_UNKNOWN_WORKER_REMAINS_STOPPED')
        require(row['result'] != 'HOLD', 'UNSAFE_PREVIOUS_REQUEST')
        for attempt in row['attempts']:
            provisional = (attempt['state'] == 'SUBMIT_INTENT' and
                attempt.get('provisional_evidence_state') == 'PROVISIONAL_ACCEPTED' and
                (attempt.get('complete_evidence') or {}).get('positive') is True and
                attempt.get('submission_attempted') is True)
            require(safe(attempt) or attempt['state'] in ('CONFIRMED', 'ALREADY_RESERVED') or provisional or row['result']=='ALREADY_RESERVED' and row.get('reconciliation',{}).get('origin')=='INQUIRY_RESERVED',
                    'UNRESOLVED_PREVIOUS_REQUEST')
        proof.append(dict(request_id=key, result=row['result'],
                          attempt_shas=[digest(a) for a in row['attempts']]))
    return proof


def reduce_events(events, entries):
    """Validate every transition; history, counts and summaries are reconstructed."""
    model = {e['request_id']: dict(entry=e, result='NOT_STARTED', attempts=[], reconciliation=None, position_result='UNKNOWN', actual_position=None)
             for e in entries}
    registered = False
    sealed_pass = 0
    reconciled = set()
    for seq, event in enumerate(events, 1):
        require(type(event.get('sequence')) is int and event['sequence'] == seq, 'SEQUENCE_GAP')
        kind, payload, rid = event['event_type'], event['payload'], event.get('logical_request_id')
        if kind == 'REGISTER':
            require(seq == 1 and payload == entries, 'REGISTRATION_INVALID')
            registered = True
            continue
        require(registered, 'INITIALIZATION_INCOMPLETE')
        if kind == 'CONTINUATION':
            require(seq == 2 and payload.get('source_session') and payload.get('source_sha'), 'CONTINUATION_BINDING')
            prior=payload['events']
            require(all(e['schema']==SCHEMA for e in prior), 'HISTORICAL_SCHEMA')
            model,sealed_pass,complete=reduce_events(prior,entries)
            require(complete, 'REGISTRATION_INCOMPLETE')
            if 'execution_mode' in payload:
                require(payload['execution_mode'] == 'NEW', 'FRESH_EXECUTION_MODE')
                require(payload.get('authority') == 'SFF-NEW-20260924-01', 'FRESH_AUTHORITY')
                require(all(r['result'] in ('CONFIRMED','ALREADY_RESERVED','FAILED_FINAL') for r in model.values()), 'FRESH_PREDECESSOR_NOT_TERMINAL')
                eligible = fresh_request_ids(model)
                require(eligible and payload.get('fresh_requests') == eligible, 'FRESH_REQUEST_SET')
                for key in eligible:
                    model[key] = dict(entry=model[key]['entry'], result='NOT_STARTED', attempts=[],
                                      reconciliation=None, position_result='UNKNOWN', actual_position=None)
                # A new execution has its own passes. Successful requests remain
                # terminal; old failure evidence stays only in the source payload.
                sealed_pass = 0
            for row in model.values():
                require(row['result'] in ('NOT_STARTED','RETRY_PENDING','FINALIZATION_PENDING','CONFIRMED','ALREADY_RESERVED','FAILED_FINAL'), 'UNRESOLVED_RESTART')
                row.pop('eligibility',None)
                row.pop('worker_stop',None)
            continue
        if kind == 'SNAPSHOT':
            require(isinstance(payload, dict) and bool(payload.get('generation')), 'SNAPSHOT_BINDING_REQUIRED')
            continue
        if kind == 'PASS_SEAL':
            require(type(payload['pass_no']) is int and payload['pass_no'] == sealed_pass + 1 <= 3,
                    'PASS_SEQUENCE')
            require(payload.get('results') == {k: digest(r) for k,r in model.items()}, 'PASS_RESULT_BINDING')
            require(all(r['result'] in ('CONFIRMED', 'ALREADY_RESERVED', 'FAILED_FINAL', 'RETRY_PENDING') for r in model.values()),
                    'UNRESOLVED_PASS')
            sealed_pass += 1
            reconciled.clear()
            continue
        require(rid in model, 'UNREGISTERED_REQUEST')
        row = model[rid]
        attempts = row['attempts']
        if kind == 'ELIGIBILITY':
            require(row['result'] == 'RETRY_PENDING' and sealed_pass > 0 and len(attempts) < 3
                    and all(safe(a) for a in attempts), 'INELIGIBLE_RETRY')
            require(payload == eligibility_proof(events[:seq-1], row, sealed_pass), 'SAFE_HISTORY_AND_PASS_REQUIRED')
            row['eligibility'] = payload
        elif kind == 'ATTEMPT_BEGIN':
            require(payload.get('continuation') == continuation_admission(model, rid),
                    'CONTINUATION_BINDING')
            n = payload['attempt_no']
            require(type(n) is int and n == len(attempts)+1 and n <= 3, 'ATTEMPT_LIMIT')
            require(row['result'] in ('NOT_STARTED', 'RETRY_PENDING'), 'REQUEST_NOT_STARTABLE')
            require(type(payload['pass_no']) is int and payload['pass_no'] == sealed_pass+1, 'RECONCILE_BEFORE_RETRY')
            require(not attempts or all(safe(a) for a in attempts), 'PREVIOUS_ATTEMPT_UNRESOLVED')
            require(not attempts or attempts[-1]['pass_no'] < payload['pass_no'], 'SAME_PASS_RETRY')
            require(payload['attempt_id'] not in [a['attempt_id'] for r in model.values() for a in r['attempts']], 'DUPLICATE_ATTEMPT_ID')
            if attempts:
                require(row.get('eligibility') == payload['eligibility'], 'ELIGIBILITY_NOT_CONSUMABLE')
                row.pop('eligibility')
            require(payload['state'] == 'IN_PROGRESS' and payload['selected_position'] is None
                    and all(payload.get(k) is False for k in ('action_intent', 'submit_intent_durable',
                        'submission_attempted', 'submission_possible', 'mutation_possible')), 'INITIAL_ATTEMPT')
            attempts.append(copy.deepcopy(payload))
            row['result'] = 'ACTIVE'
            row['position_result'] = 'UNKNOWN'
        elif kind == 'ATTEMPT_STATE':
            require(bool(attempts), 'BEGIN_REQUIRED')
            prior = attempts[-1]
            require(payload['attempt_id'] == prior['attempt_id'] and payload['attempt_no'] == prior['attempt_no']
                    and payload['pass_no'] == prior['pass_no'], 'ATTEMPT_IDENTITY')
            allowed = {'IN_PROGRESS': {'PRE_SUBMIT_FAILED', 'ALREADY_RESERVED', 'ACTION_INTENT', 'PRESERVATION_UNKNOWN'},
                       'ACTION_INTENT': {'SUBMIT_INTENT', 'PRESERVATION_UNKNOWN'},
                       'SUBMIT_INTENT': {'SUBMIT_INTENT', 'CONFIRMED', 'UNKNOWN_AFTER_SUBMIT'}}
            require(payload['state'] in allowed.get(prior['state'], set()), 'IMMUTABLE_TERMINAL_OR_INVALID_TRANSITION')
            if prior['selected_position'] is not None:
                require(payload['selected_position'] == prior['selected_position'], 'SELECTED_POSITION_CHANGED')
            for flag in ('action_intent', 'submit_intent_durable', 'submission_attempted', 'submission_possible', 'mutation_possible'):
                require(type(payload[flag]) is bool and (not prior[flag] or payload[flag]), 'INTENT_ROLLBACK')
            if payload['state'] == 'PRE_SUBMIT_FAILED':
                require(safe(payload) and payload['safe_certificate']['path'] in SAFE_PATHS,
                        'SAFE_CERTIFICATE_REQUIRED')
                require(all(payload['safe_certificate'].get(k) is True for k in
                            ('binding_verified', 'chain_verified', 'write_before_action', 'checkpoint_known')),
                        'SAFE_CERTIFICATE_INCOMPLETE')
                row['result'] = 'RETRY_PENDING' if len(attempts) < 3 else 'FINALIZATION_PENDING'
                row['position_result'] = 'N/A'
            if payload['state'] == 'ALREADY_RESERVED':
                require(all(payload.get(k) is False for k in ('action_intent','submit_intent_durable','submission_attempted','submission_possible','mutation_possible')) and payload['selected_position'] is None, 'RESERVED_PRE_ACTION_REQUIRED')
                validate_reserved(payload.get('reserved_evidence'), row['entry'], prior, events[:seq-1])
                row.update(result='ALREADY_RESERVED', confirmation_origin='INQUIRY_RESERVED')
            if payload['state'] in ('ACTION_INTENT', 'SUBMIT_INTENT', 'CONFIRMED'):
                require(payload['action_intent'] is True and type(payload['selected_position']) is int
                        and payload['selected_position'] in row['entry']['positions'], 'ACTION_BOUNDARY')
            if payload['state'] in ('SUBMIT_INTENT', 'CONFIRMED'):
                require(payload['submit_intent_durable'] and payload['submission_possible'], 'SUBMIT_BOUNDARY')
            if payload.get('provisional_evidence_state') == 'PROVISIONAL_ACCEPTED':
                require(payload['state'] in ('SUBMIT_INTENT', 'CONFIRMED') and payload['submission_attempted']
                        and (payload.get('complete_evidence') or {}).get('positive') is True, 'COMPLETE_REQUIRED')
                row['result'] = 'AWAITING_RECONCILIATION'
            if payload['state'] == 'CONFIRMED':
                require(prior.get('provisional_evidence_state') == 'PROVISIONAL_ACCEPTED'
                        and (payload.get('confirmation_evidence') or {}).get('positive') is True,
                        'COMPLETE_AND_LIST_REQUIRED')
                row.update(result='CONFIRMED', confirmation_origin='AUTOMATION_COMPLETE_AND_LIST')
            if payload['state'] in ('PRESERVATION_UNKNOWN', 'UNKNOWN_AFTER_SUBMIT'):
                row['result'] = payload['state'] if payload['state']=='UNKNOWN_AFTER_SUBMIT' else 'HOLD'
            attempts[-1] = copy.deepcopy(payload)
        elif kind == 'RECONCILIATION':
            result = payload['result']
            require(result in ('CONFIRMED', 'NOT_RESERVED', 'AMBIGUOUS', 'RECONCILIATION_FAILED'), 'UNKNOWN_LIST_RESULT')
            require(attempts and attempts[-1]['state'] in ('SUBMIT_INTENT','CONFIRMED') and row['result'] in ('AWAITING_RECONCILIATION','CONFIRMED'), 'POSITIVE_COMPLETION_FLOW_ONLY')
            row['reconciliation'] = copy.deepcopy(payload)
            reconciled.add(rid)
            if attempts[-1]['state']=='CONFIRMED':
                require(result=='CONFIRMED' and payload==attempts[-1]['confirmation_evidence']['reconciliation'], 'FINAL_RECONCILIATION_CONTRADICTION')
                row.update(result='CONFIRMED', confirmation_origin='AUTOMATION_COMPLETE_AND_LIST')
            else:
                row['result'] = 'UNKNOWN_AFTER_SUBMIT'
        elif kind == 'FAILED_FINAL':
            require(len(attempts) == 3 and all(safe(a) for a in attempts) and row['result']=='FINALIZATION_PENDING', 'FAILED_FINAL_PROOF')
            require(payload['attempt_shas'] == [digest(a) for a in attempts]
                    and payload['reason'] == 'ATTEMPT_LIMIT_REACHED_SAFE_PRE_SUBMIT_FAILURE', 'FINAL_EVIDENCE_BINDING')
            row.update(result='FAILED_FINAL', position_result='N/A')
        elif kind == 'RESERVED_RESOLUTION':
            require(row['result']=='UNKNOWN_AFTER_SUBMIT' and attempts[-1]['state'] in ('UNKNOWN_AFTER_SUBMIT','SUBMIT_INTENT') and attempts[-1]['submit_intent_durable'] is True, 'UNKNOWN_RESOLUTION_ONLY')
            validate_reserved(payload, row['entry'], attempts[-1], events[:seq-1])
            row.update(result='ALREADY_RESERVED', confirmation_origin='INQUIRY_RESERVED', reconciliation=copy.deepcopy(payload), worker_stop=True)
        elif kind == 'POSITION_RESULT':
            require(row['result'] in ('CONFIRMED','ALREADY_RESERVED'), 'RESERVATION_POSITIVE_REQUIRED')
            require(payload.get('reservation_result')==row['result'] and payload.get('attempt_shas')==[digest(a) for a in attempts], 'POSITION_RESULT_BINDING')
            actual = payload.get('actual_position')
            require(actual is None or type(actual) is int and actual>0, 'POSITION_VALUE')
            require(payload.get('result')==position_rank(row['entry'], actual), 'POSITION_RANK')
            if actual is not None:
                first, second = payload['snapshots']
                proof = classify_position(first, second, row['entry'])
                require(proof.get('position')==actual and proof.get('result')=='CONFIRMED', 'POSITIVE_POSITION_REQUIRED')
            if row['actual_position'] is not None and actual != row['actual_position']:
                row['position_review']='CONFLICT' if actual is not None else 'UNVERIFIED'
            else:
                row.update(actual_position=actual, position_result=payload['result'], position_evidence=copy.deepcopy(payload))
        else:
            raise ValueError('UNKNOWN_EVENT_TYPE')
    return model, sealed_pass, registered


class Journal:
    def __init__(self, root, alias, entries, binding, execution):
        self.root, self.alias = Path(root), alias
        self.entries, self.binding, self.execution = copy.deepcopy(entries), copy.deepcopy(binding), execution
        self.seen = []
        self.current_eligibility = {}

    def events(self):
        events, previous, ids = [], None, set()
        if not self.root.exists():
            return events
        files = sorted(self.root.iterdir())
        for n, path in enumerate(files, 1):
            require(path.name == str(n).zfill(6)+'.json', 'UNKNOWN_OR_PARTIAL_JOURNAL_ARTIFACT')
            e = read(path)
            require(e['schema'] == SCHEMA and e['design'] == DESIGN and e['worker'] == self.alias
                    and e['binding_sha'] == digest(self.binding) and e['execution_id'] == self.execution
                    and e['previous_record_sha'] == previous, 'JOURNAL_BINDING_OR_CHAIN')
            require(e['event_id'] not in ids, 'DUPLICATE_EVENT')
            ids.add(e['event_id'])
            previous = digest(e)
            events.append(e)
        require(events[:len(self.seen)] == self.seen, 'JOURNAL_PREFIX_CHANGED')
        reduce_events(events, self.entries)
        self.seen = copy.deepcopy(events)
        return events

    def view(self):
        return reduce_events(self.events(), self.entries)

    def append(self, kind, payload, rid=None):
        events = self.events()
        e = dict(schema=SCHEMA, design=DESIGN, worker=self.alias,
            execution_id=self.execution, logical_batch_id=self.binding.get('logical_batch_id', self.execution),
            predecessor_execution_hash=self.binding.get('predecessor_execution_hash'),
            binding_sha=digest(self.binding), component_shas=self.binding.get('component_shas'),
            manifest_sha=self.binding.get('manifest_sha'), list_sha=self.binding.get('reservation_list_file_sha'),
            go_binding_sha=digest(self.binding), event_id=uuid.uuid4().hex,
            sequence=len(events)+1, previous_record_sha=digest(events[-1]) if events else None,
            timestamp=datetime.now(timezone.utc).isoformat(), logical_request_id=rid,
            event_type=kind, payload=copy.deepcopy(payload))
        reduce_events(events+[e], self.entries)
        self.root.mkdir(parents=True, exist_ok=True)
        publish(self.root / (str(len(events)+1).zfill(6)+'.json'), e)
        self.seen = copy.deepcopy(events+[e])
        require(self.events() == events+[e], 'ACK_UNKNOWN')
        # Observation only, after durable readback; never invent a saved state.
        try:
            from diagnostic import fet_persisted
            fet_persisted(e, digest(e))
        except BaseException:
            pass
        if kind == 'ELIGIBILITY':
            self.current_eligibility[rid] = digest(payload)

    def register(self):
        require(not self.root.exists(), 'REGISTRATION_REPLAY')
        self.append('REGISTER', self.entries)

    def begin(self, rid):
        rows, sealed, registered = self.view()
        require(registered, 'INITIALIZATION_INCOMPLETE')
        row = rows[rid]
        n = len(row['attempts'])+1
        if row['attempts']:
            require(self.current_eligibility.pop(rid, None) == digest(row.get('eligibility')),
                    'FRESH_EXECUTION_ELIGIBILITY_REQUIRED')
        payload = dict(attempt_no=n, pass_no=sealed+1, attempt_id=uuid.uuid4().hex,
            continuation=continuation_admission(rows, rid),
            first_started_at=datetime.now(timezone.utc).isoformat(), state='IN_PROGRESS',
            phase='BEGIN', selected_position=None, action_intent=False, submit_intent_durable=False,
            submission_attempted=False, submission_possible=False, mutation_possible=False,
            safe_certificate=None, result_code=None, failure_reason=None, observation_status=None,
            eligibility=row.get('eligibility'), request_fingerprint=digest(row['entry']))
        self.append('ATTEMPT_BEGIN', payload, rid)
        return payload

    def update(self, rid, state, **fields):
        row = self.view()[0][rid]
        value = copy.deepcopy(row['attempts'][-1])
        value.update(state=state, **fields)
        self.append('ATTEMPT_STATE', value, rid)
        return value

    def summary(self):
        model, _, registered = self.view()
        legacy_position_review = self.binding.get('manifest_sha') in LEGACY_POSITION_REVIEW_MANIFESTS
        rows = [dict(request=rid, lesson=row['entry']['lesson'], **({'date':row['entry']['date'], 'start_time':row['entry']['start_time']} if 'start_time' in row['entry'] else {}), final_result=row['result'],
                     attempts=len(row['attempts']), last_failure_reason=next((a.get('failure_reason')
                         for a in reversed(row['attempts']) if a.get('failure_reason')), None),
                     reconciliation_result=(row['reconciliation'] or {}).get('result'),
                     remaining_ambiguity=row['result'] not in ('CONFIRMED', 'ALREADY_RESERVED', 'FAILED_FINAL'),
                     position_result=row['position_result'], actual_position=row['actual_position'], position_review=row.get('position_review'),
                     position_reason=(row.get('position_evidence') or {}).get('reason') or ('FINAL_POSITIVE_LIST_NOT_OBSERVED' if row['position_result']=='UNKNOWN' else 'SAFE_FAILURE_NOT_APPLICABLE' if row['position_result']=='N/A' else 'POSITIVE_LIST_MATCH'),
                     position_owner_review_required=bool(row.get('position_review')) or (row['result']=='CONFIRMED' or legacy_position_review and row['result']=='ALREADY_RESERVED') and row['position_result']=='UNKNOWN',
                     owner_action_required=row['result'] not in ('CONFIRMED','ALREADY_RESERVED','FAILED_FINAL'),
                     attempt_records=copy.deepcopy(row['attempts'])) for rid, row in model.items()]
        complete = registered and all(r['final_result'] in ('CONFIRMED', 'ALREADY_RESERVED', 'FAILED_FINAL') for r in rows)
        confirmed = sum(r['final_result'] == 'CONFIRMED' for r in rows)
        return dict(runtime='COMPLETED' if complete else 'HOLD', all_requests_confirmed=complete and confirmed==len(rows),
                    all_reservation_results_ok=all(r['final_result'] in ('CONFIRMED','ALREADY_RESERVED') for r in rows),
                    position_verification_complete=all(r['position_result'] not in ('UNKNOWN',) and not r['position_review'] for r in rows),
                    already_reserved_count=sum(r['final_result']=='ALREADY_RESERVED' for r in rows),
                    confirmed_count=confirmed, failed_final_count=sum(r['final_result']=='FAILED_FINAL' for r in rows),
                    not_started_count=sum(r['final_result']=='NOT_STARTED' for r in rows), requests=rows)


def classify_list(first, second, entry, selected=None):
    """Negative is impossible without the complete, explicit coverage certificate."""
    bad = lambda reason: dict(result='RECONCILIATION_FAILED', reason=reason)
    if not isinstance(first, dict) or not isinstance(second, dict):
        return bad('ACQUISITION_FAILED')
    keys = ('worker', 'user_binding', 'generation', 'document_id', 'rows', 'coverage')
    if any(first.get(k) != second.get(k) for k in keys):
        return bad('UNSTABLE_OR_DOCUMENT_CHANGED')
    if any(second.get(k) != entry[k] for k in ('worker', 'user_binding')):
        return bad('IDENTITY_MISMATCH')
    if not all(s.get(k) is True for s in (first, second) for k in
               ('page_verified', 'identity_verified', 'render_complete', 'parser_complete')):
        return bad('PAGE_RENDER_OR_PARSE_FAILED')
    rows = second.get('rows')
    if not isinstance(rows, list):
        return bad('PARSE_FAILED')
    target = []
    for row in rows:
        if not all(k in row for k in ('date', 'lesson', 'position', 'status')):
            return bad('PARSE_FAILED')
        if 'start_time' in entry:
            from lesson_target import valid_time
            if not valid_time(row.get('start_time')):
                return bad('START_TIME_UNPROVEN')
            from lesson_target import names_match
            matched = (row['date'] == entry['date'] and row['start_time'] == entry['start_time']
                and names_match(row['lesson'], entry['lesson'], entry['date'], entry['start_time'], lambda x: x))
        else:
            matched = row['date'] == entry['date'] and row['lesson'] == entry.get('canonical_lesson', entry['lesson'])
        if matched:
            target.append(row)
    proof = dict(snapshot_sha=digest(second), generation=second.get('generation'), coverage=second.get('coverage'))
    if target:
        if len(target) != 1 or target[0]['status'] != 'ACTIVE' or type(target[0]['position']) is not int:
            return dict(result='AMBIGUOUS', reason='MULTIPLE_OR_CONFLICTING_MATCH', **proof)
        if selected is not None and target[0]['position'] != selected or selected is None and target[0]['position'] not in entry['positions']:
            return dict(result='AMBIGUOUS', reason='POSITION_MISMATCH', **proof)
        return dict(result='CONFIRMED', reason='EXACT_ACTIVE_MATCH', position=target[0]['position'], **proof)
    coverage = second.get('coverage') or {}
    if not all(coverage.get(k) is True for k in ('account_exact', 'date_range_complete', 'filters_complete',
            'tabs_complete', 'pages_complete', 'all_active_covered', 'hidden_rows_absent', 'pagination_absent',
            'virtualization_absent', 'lazy_rows_absent', 'loading_finished', 'parser_complete')):
        return bad('COVERAGE_UNPROVEN')
    if not rows and coverage.get('explicit_empty') is not True:
        return bad('EMPTY_UNKNOWN')
    if not all(second.get(k) for k in ('generation', 'document_id', 'normalization_version', 'started_at', 'ended_at')):
        return bad('SNAPSHOT_METADATA_INCOMPLETE')
    return dict(result='NOT_RESERVED', reason='PROVEN_ABSENCE', **proof)


def reconcile(journal, first=None, second=None, fresh_only=None):
    rows, pass_no, _ = journal.view()
    if fresh_only is not None:
        row=rows[fresh_only]
        journal.append('ELIGIBILITY', eligibility_proof(journal.events(), row, pass_no), fresh_only)
        return {}
    if first is not None:
        journal.append('SNAPSHOT', first)
        journal.append('SNAPSHOT', second)
    outcomes={}
    for rid, row in rows.items():
        attempt = row['attempts'][-1] if row['attempts'] else {}
        if row['result'] == 'FINALIZATION_PENDING':
            journal.append('FAILED_FINAL', dict(reason='ATTEMPT_LIMIT_REACHED_SAFE_PRE_SUBMIT_FAILURE', attempt_shas=[digest(a) for a in row['attempts']]), rid)
        elif row['result']=='AWAITING_RECONCILIATION':
            result=classify_list(first,second,row['entry'],attempt.get('selected_position'))
            outcomes[rid]=result
            if result['result']=='CONFIRMED' and attempt.get('state')=='SUBMIT_INTENT' and attempt.get('provisional_evidence_state')=='PROVISIONAL_ACCEPTED':
                journal.update(rid,'CONFIRMED',reconciliation_pending=False,confirmation_evidence=dict(positive=True,reconciliation=result,date=row['entry']['date'],lesson=row['entry']['lesson'],selected_position=attempt['selected_position']))
            journal.append('RECONCILIATION',result,rid)
        if journal.view()[0][rid]['result'] in ('CONFIRMED','ALREADY_RESERVED') and first is not None:
            record_position(journal,rid,first,second)
    model=journal.view()[0]
    if not all(r['result'] in ('CONFIRMED', 'ALREADY_RESERVED', 'FAILED_FINAL', 'RETRY_PENDING')
               for r in model.values()):
        return outcomes  # The durable reconciliation remains unresolved; no pass is sealed.
    journal.append('PASS_SEAL',dict(pass_no=pass_no+1,results={k:digest(r) for k,r in model.items()}))
    return outcomes

def eligibility_proof(events,row,sealed):
    seals=[e for e in events if e['event_type']=='PASS_SEAL']
    if not seals:
        imports=[e for e in events if e['event_type']=='CONTINUATION']
        if imports:
            return eligibility_proof(imports[-1]['payload']['events'],row,sealed)
    require(sealed>0 and seals and seals[-1]['payload']['pass_no']==sealed, 'PASS_SEAL_REQUIRED')
    return dict(next_attempt_no=len(row['attempts'])+1,attempt_shas=[digest(a) for a in row['attempts']],pass_seal_sha=digest(seals[-1]))

def validate_reserved(proof,entry,attempt,events):
    require(isinstance(proof,dict), 'RESERVED_PROOF_REQUIRED')
    require(proof.get('entry_sha')==digest(entry) and proof.get('attempt_sha')==digest(attempt) and proof.get('previous_record_sha')==digest(events[-1]), 'RESERVED_EVIDENCE_BINDING')
    raw=proof.get('snapshot')
    require(isinstance(raw,dict) and proof.get('snapshot_sha')==digest(raw), 'RESERVED_RAW_HASH')
    require(raw.get('target')==dict(date=entry['date'],lesson=entry['lesson'], **({'start_time':entry['start_time']} if 'start_time' in entry else {})), 'RESERVED_TARGET_BINDING')
    require(all(raw.get(k) is True for k in ('page_verified','identity_verified','target_verified','render_verified','marker_exact','marker_associated','fresh')), 'RESERVED_POSITIVE_REQUIRED')
    require(raw.get('marker_text')=='「予約中」' and type(raw.get('marker_count')) is int and raw['marker_count']==1 and raw.get('generation') and raw.get('observed_at'), 'RESERVED_MARKER_EXACT_REQUIRED')

def reserved_result(journal,rid,snapshot,resolution=False):
    row=journal.view()[0][rid]
    proof=dict(entry_sha=digest(row['entry']),attempt_sha=digest(row['attempts'][-1]),previous_record_sha=digest(journal.events()[-1]),snapshot=copy.deepcopy(snapshot),snapshot_sha=digest(snapshot),origin='INQUIRY_RESERVED')
    if resolution:
        journal.append('RESERVED_RESOLUTION',proof,rid)
    else:
        journal.update(rid,'ALREADY_RESERVED',reserved_evidence=proof)

def position_rank(entry,actual):
    if actual is None: return 'UNKNOWN'
    return 'rank'+str(entry['positions'].index(actual)+1) if actual in entry['positions'][:3] else 'other'

def classify_position(first,second,entry):
    # Reuse the existing positive parser, allowing an actual position outside preferences.
    candidate=copy.deepcopy(entry)
    rows=(second or {}).get('rows') or []
    candidate['positions']=[r.get('position') for r in rows if type(r.get('position')) is int]
    return classify_list(first,second,candidate)

def record_position(journal,rid,first,second):
    row=journal.view()[0][rid]
    result=classify_position(first,second,row['entry'])
    actual=result.get('position') if result.get('result')=='CONFIRMED' else None
    payload=dict(reservation_result=row['result'],actual_position=actual,result=position_rank(row['entry'],actual),attempt_shas=[digest(a) for a in row['attempts']],snapshots=[first,second],reason=result.get('reason'))
    if row.get('position_evidence')!=payload:
        journal.append('POSITION_RESULT',payload,rid)


def restart_assessment(journals):
    """Read-only; never consumes old eligibility or silently restarts an execution."""
    summaries = []
    for journal in journals:
        rows, sealed, registered = journal.view()
        require(registered, 'INITIALIZATION_INCOMPLETE')
        for row in rows.values():
            require(row['result']=='ALREADY_RESERVED' or all(safe(a) or a['state'] in ('CONFIRMED','ALREADY_RESERVED') for a in row['attempts']),
                    'UNRESOLVED_RESTART')
        summaries.append(journal.summary())
    return dict(status='REQUIRES_NEW_CONTINUATION_ADMISSION_AND_FRESH_OWNER_GO', summaries=summaries,
                previous_eligibility_valid=False, automatic_restart=False)
