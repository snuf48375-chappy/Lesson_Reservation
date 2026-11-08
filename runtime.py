"""Pre-GO static context; immutable request snapshot; dynamic append-only Journal."""
import copy
import hashlib
import contextlib
import io
import os
import re
import sys
import uuid
from pathlib import Path
import runtime_config as cfg

HERE = Path(__file__).resolve().parent
from package_authority import PACKAGE_ROOT, OPERATIONAL_ROOT, BINDING_PATH, deployment, package_path
ROOT = OPERATIONAL_ROOT
MANIFEST = PACKAGE_ROOT / 'OPERATIONAL_MANIFEST.json'
OLD_STATE = ROOT / 'runtime/reservation_journal/schema-v1/stage-c-minimum-safe-v3'
STATE = ROOT / 'runtime/reservation_journal/schema-v2/cla1-request-local-v1'
IDENTITY = ROOT / 'runtime/config/stage_a_identity.json'
sys.dont_write_bytecode = True

def sha(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()

def read(path):
    import json
    def pairs(items):
        result = {}
        for key, value in items:
            cfg.require(key not in result, 'DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs)

def load(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(module)
    return module

def verify_package():
    manifest = read(MANIFEST)
    deployment()
    authority=manifest['request_local_authority']
    cfg.require(sha(Path(authority['path']))==authority['sha256'], 'REQUEST_LOCAL_AUTHORITY_CHANGED')
    resolution=manifest['resolution_contract']
    cfg.require(sha(Path(resolution['authority_path']))==resolution['authority_sha'], 'RESOLUTION_AUTHORITY_CHANGED')
    cfg.require(manifest['deployment_binding_sha'] == sha(BINDING_PATH), 'DEPLOYMENT_BINDING_MISMATCH')
    for path, expected in manifest['runtime_files'].items():
        cfg.require(sha(package_path(path)) == expected, 'PACKAGE_REVISION_MISMATCH')
    actual_package = {p.relative_to(PACKAGE_ROOT).as_posix() for p in PACKAGE_ROOT.rglob('*') if p.is_file()}
    cfg.require(actual_package == set(manifest['runtime_files']) | {'OPERATIONAL_MANIFEST.json'}, 'PACKAGE_INVENTORY_MISMATCH')
    cfg.require(sha(IDENTITY) == manifest['identity_config_sha'], 'IDENTITY_CONFIG_MISMATCH')
    # Historical namespaces are frozen read-only dependencies, never reset.
    history = ROOT / 'runtime/reservation_journal/schema-v1'
    actual = {p.relative_to(ROOT).as_posix(): sha(p) for p in history.rglob('*')
              if p.is_file() and not p.is_relative_to(OLD_STATE)}
    cfg.require(actual == manifest['historical_journal_files'], 'HISTORICAL_JOURNAL_CHANGED')
    return manifest

RESERVATION_LIST_RELATIVE_PATH = 'reservation_lists/reservation_list.txt'

def fixed_list_path():
    path = ROOT / RESERVATION_LIST_RELATIVE_PATH
    # Reject redirection through symlinks/junctions to another authority.
    cfg.require(path.resolve() == path.absolute(), 'RESERVATION_LIST_PATH_REDIRECTED')
    cfg.require(path.is_file(), 'RESERVATION_LIST_NOT_FOUND')
    return path

def context(include_authorization=True):
    path = fixed_list_path()
    manifest = verify_package()
    a = load('stage_c_locked_adapter', package_path(manifest['adapter_path']))
    os.environ['LESSON_RESERVATION_IDENTITY_CONFIG'] = str(IDENTITY)
    import credential_source
    m = credential_source.load('stage_c_locked_batch', a.CAND)
    # Never use legacy source credentials; preserve immutable files.
    for collection in (m._FIXED_USER_SETTINGS, getattr(m, 'users', [])):
        for user in collection:
            user.pop('password', None)
    usernames = [u['username'] for u in m._FIXED_USER_SETTINGS]
    from lesson_target import canonical_name
    canonical = lambda lesson: canonical_name(lesson, m.normalize_lesson_name)
    # Parse and hash exactly the same immutable byte snapshot.
    content = path.read_bytes()
    data = cfg.parse(content.decode('utf-8-sig'), usernames, canonical)
    content_sha = hashlib.sha256(content).hexdigest().upper()
    cfg.require(sha(fixed_list_path()) == content_sha, 'RESERVATION_LIST_CHANGED')
    m.users = m.build_internal_users(dict(zip(usernames, [data['requests'][a] for a in ('A', 'B')])))
    cfg.require(len(m.users) == 2, 'WORKER_COUNT')
    cfg.require(len({str(Path(u['profile_path']).resolve()) for u in m.users}) == 2,
                'WORKER_PROFILE_ISOLATION')
    for u in m.users:
        cfg.require(re.fullmatch(r'[0-9]{12}', u.get('expected_member_identifier') or ''), 'IDENTITY_BINDING')
    m.LESSON_LIST_FILE, m.LESSON_LIST_MONTH = path, data['month']
    # Sanitized identity binds aliases, exact active requests and textual order.
    m.LESSON_LIST_SHA256 = cfg.digest(data)
    binding = dict(manifest_sha=sha(MANIFEST), configuration=data,
                   request_keys={w: [[r['date'], r['start_time'], canonical(r['name'])] for r in data['requests'][w]] for w in ('A', 'B')},
                   reservation_list_identity=cfg.digest(data),
                   reservation_list_file_sha=content_sha,
                   reservation_list_path=RESERVATION_LIST_RELATIVE_PATH, identity_config_sha=sha(IDENTITY),
                   journal_namespace=STATE.relative_to(ROOT).as_posix())
    binding['component_shas'] = dict(batch=sha(a.CAND), adapter=sha(package_path(manifest['adapter_path'])),
                                    launcher=sha(HERE / 'launch.py'), runtime=sha(HERE / 'runtime.py'),
                                    authorization_control=sha(HERE / 'admission_control.py'))
    binding['worker_bindings'] = [dict(worker=w, fixed_user_slot=i, identity_config_sha=sha(IDENTITY))
                                  for i, w in enumerate(('A', 'B'))]
    binding['accepted_c2'] = manifest['accepted_c2']
    binding.update(design='SRLR-20260922-01+R5R6-20260923', schema='CLA1_REQUEST_LOCAL_V1', max_total_attempts=3, max_passes=3)
    from admission_control import entries
    entries(binding)
    return a, m, binding, path

def configure_adapter(a, m, binding):
    data = binding['configuration']
    # Private tuples sever all links to the mutable caller binding.
    frozen = {w: tuple((r['date'], r['start_time'], r['name'], tuple(r['positions'])) for r in data['requests'][w]) for w in ('A', 'B')}
    a.requests = lambda alias: [dict(date=d, start_time=t, name=n, positions=list(p)) for d, t, n, p in frozen[alias]]
    def scope(module, users):
        cfg.require(len(users) == 2, 'WORKER_COUNT')
        for alias, user, fixed in zip(('A', 'B'), users, module._FIXED_USER_SETTINGS):
            cfg.require(user['username'] == fixed['username'], 'WORKER_BINDING')
            cfg.require(a.exact(user['lesson_requests'], a.requests(alias)), 'REQUEST_ORDER_BINDING')
            cfg.require(user.get('expected_member_identifier') == module._cla1_identity_bindings().get(user['username'])
                        and bool(user.get('expected_member_identifier')), 'IDENTITY_BINDING')
    a.scope = scope
    scope(m, m.users)


def resolution_context(snapshot):
    """Fixed incident A identity; independent of the current reservation list."""
    manifest=verify_package()
    cfg.require(sha(IDENTITY)==snapshot['binding']['identity_config_sha'], 'RESOLUTION_IDENTITY_CHANGED')
    a=load('resolution_locked_adapter',package_path(manifest['adapter_path']))
    os.environ['LESSON_RESERVATION_IDENTITY_CONFIG']=str(IDENTITY)
    import credential_source
    m=credential_source.load('resolution_observation_source',a.CAND)
    for collection in (m._FIXED_USER_SETTINGS,getattr(m,'users',[])):
        for user in collection:
            user.pop('password',None)
    names=[u['username'] for u in m._FIXED_USER_SETTINGS]
    users=m.build_internal_users(dict(zip(names,[snapshot['binding']['configuration']['requests'][w] for w in 'AB'])))
    cfg.require(len(users)==2 and len({str(Path(u['profile_path']).resolve()) for u in users})==2,
                'RESOLUTION_IDENTITY_OR_PROFILE')
    from credentials import binding_for
    binding_for(m,'A',users[0])
    # This private module instance has no Journal hooks. Legacy native logging
    # would save raw DOM diagnostics; only the resolution writer may persist.
    m.log_event=lambda *args,**kwargs:None
    return m,users[0]


def history_preflight(m, binding=None, active_session=None):
    from admission_control import startup_history
    cfg.require(not (STATE / 'execution.lock').exists() or active_session is not None and read(STATE / 'execution.lock')['session']==active_session, 'ACTIVE_OR_STALE_EXECUTION_LOCK')
    from admission_control import entries
    if binding is None:
        binding=context()[2]
    request_keys={(e['worker'], e['date'], m.normalize_lesson_name(e['lesson'])) for e in entries(binding)}
    from lesson_target import canonical_name
    for entry in entries(binding):
        if canonical_name(entry['lesson'], m.normalize_lesson_name) in (
                'サンデープログラム', 'サンデープログラム1', 'サンデープログラム2'):
            request_keys.update((entry['worker'],entry['date'],name) for name in
                                ('サンデープログラム','サンデープログラム1','サンデープログラム2'))
    prior = startup_history(ROOT, OLD_STATE, read(HERE / 'seed_history.json'), read, sha, m.normalize_lesson_name, request_keys)
    # New execution continuation requires a distinct admission. Never silently
    # ignore a v2 run, reset its budget, or append to its historical execution.
    old_retry = ROOT / 'runtime/reservation_journal/schema-v2/cla1-retry-continuation-v1'
    cfg.require(not old_retry.exists() or not list(old_retry.iterdir()), 'OLD_SCHEMA_CONTINUATION_REQUIRES_SEPARATE_ADMISSION')
    from admission_control import entries
    from request_local_admission import scan
    from lesson_target import canonical_name
    bound_entries=[dict(e, canonical_lesson=canonical_name(e['lesson'], m.normalize_lesson_name)) for e in entries(binding)]
    chain=_quick_connection().scan(binding,bound_entries)
    return prior[0],chain


def input_paths():
    manifest = read(MANIFEST)
    files = {package_path(p) for p in manifest['runtime_files']}
    files.update(ROOT / p for p in manifest['historical_journal_files'])
    files.update((MANIFEST, IDENTITY, fixed_list_path()))
    files.add(Path(manifest['request_local_authority']['path']))
    files.add(Path(manifest['resolution_contract']['authority_path']))
    for directory in (ROOT / 'runtime/reservation_journal/schema-v1',
                      ROOT / 'runtime/rebooking_authorizations',
                      ROOT / 'runtime/reservation_journal/schema-v2',
                      ROOT / 'runtime/resolution_evidence'):
        files.update(p for p in directory.rglob('*') if p.is_file() and 'native_logs' not in p.parts)
    import manual_ab7feed
    files.update(manual_ab7feed.protected_paths())
    files.update(_quick_connection().input_paths())
    return files


def journal_inventory(exclude=None):
    """Names only at GO: leased historical bytes cannot change. No hash/replay."""
    result = set()
    for directory in (ROOT / 'runtime/reservation_journal/schema-v1',
                      ROOT / 'runtime/rebooking_authorizations',
                      ROOT / 'runtime/reservation_journal/schema-v2',
                      ROOT / 'runtime/resolution_evidence'):
        for p in directory.rglob('*'):
            if p.is_file() and 'native_logs' not in p.parts and not (exclude and p.is_relative_to(exclude)):
                result.add(p.relative_to(ROOT).as_posix())
    import manual_ab7feed
    result.update(manual_ab7feed.protected_inventory())
    result.update(_quick_connection().inventory())
    return frozenset(result)


def install(a, m, store, session, alias):
    """Retain proven Journal hooks; remove adapter's repeated static batch admission."""
    original_start = m._batch_start
    # Scope is checked before READY; FinalGuard requires no pre-GO action events.
    a.scope(m, m.users)
    a.install(m, store, session, alias)
    # The unchanged core still performs its dynamic pending/duplicate-key check.
    # The old wrapper's N repeated JOURNAL_MISS checks no longer run after GO.
    m._batch_start = original_start
    if store.snapshot().get('schema') == 'CLA1_REQUEST_LOCAL_V1':
        import retry_worker
        retry_worker.install(m, store, session, alias)


def make_store(a, m, binding, list_path, root, package_check=None):
    """Static checks belong to context/FinalGuard; current Journal checks stay here."""
    import json
    from admission_control import entries, validate_chain, SCHEMA, GO_SEMANTIC
    cfg.require(Path(list_path) == fixed_list_path(), 'RESERVATION_LIST_AUTHORITY_MISMATCH')
    configure_adapter(a, m, binding)
    expected_binding = json.dumps(binding, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    expected_digest = cfg.digest(binding)  # once, before GO
    ordered_entries = entries(binding)
    frozen_entries = tuple((e['worker'], e['user_binding'], e['request_id'], e['date'],
                           e['start_time'], e['lesson'], tuple(e['positions']), e['candidate_sha']) for e in ordered_entries)

    class RuntimeStore(a.Store):
        def __init__(self):
            self.m, self.root = m, Path(root)
            self.bindings = {u['username']: w for w, u in zip(('A', 'B'), m.users)}
            self._active = False; self._claimed = None; self._seen = {'A': (), 'B': ()}
            self._admission = None
            self.binding_sha = expected_digest

        def all_entries(self):
            return [dict(worker=w, user_binding=u, request_id=i, date=d, start_time=t, lesson=n,
                          positions=list(p), candidate_sha=c) for w, u, i, d, t, n, p, c in frozen_entries]

        def snapshot(self):
            return json.loads(expected_binding)

        def binding(self, alias, index):
            return [e for e in self.all_entries() if e['worker'] == alias][index]

        def check(self):
            cfg.require(self._active and self._claimed in ('A', 'B'), 'HUMAN_GO_REQUIRED')
            cfg.require(not (self.root / 'finished.json').exists(), 'CONSUMED_ADMISSION')

        def validate_admission(self):
            admission = a.read(self.root / 'admission.json')
            cfg.require(admission.get('schema') == binding.get('schema', SCHEMA) and admission['session'] == self.root.name,
                        'ADMISSION_SESSION')
            cfg.require(json.dumps(admission['binding'], ensure_ascii=False, sort_keys=True,
                        separators=(',', ':')) == expected_binding, 'ADMISSION_BINDING')
            cfg.require(a.exact(admission['entries'], self.all_entries()), 'ADMISSION_EXACT_BINDING')
            cfg.require(not (self.root / 'finished.json').exists(), 'CONSUMED_ADMISSION')
            return admission

        def prepare(self, history, chain):
            cfg.require(not self.root.exists(), 'REPLAYED_ADMISSION')
            cfg.require(a.read(STATE / 'execution.lock')['session'] == self.root.name, 'EXCLUSIVE_LOCK_REQUIRED')
            self.root.mkdir(parents=True, exist_ok=False)
            a.publish(self.root / 'admission.json', dict(schema=binding.get('schema', SCHEMA), session=self.root.name,
                binding=json.loads(expected_binding), entries=self.all_entries(), history=history,
                ordinal=chain['ordinal'], previous_run=chain['previous_run'], created=a.now()))
            if binding.get('schema') == 'CLA1_REQUEST_LOCAL_V1':
                for w in ('A', 'B'):
                    j=self.retry_journal(w)
                    j.register()
                    from request_local_admission import restore
                    restore(j,chain.get('predecessor'))
            return self.root.name

        def retry_journal(self, alias):
            import retry_continuation as rc
            from lesson_target import canonical_name
            return rc.Journal(self.root / 'request_attempts' / alias, alias,
                [dict(e, canonical_lesson=canonical_name(e['lesson'], m.normalize_lesson_name))
                 for e in self.all_entries() if e['worker'] == alias], self.snapshot(), self.root.name)

        def consume(self, session):
            cfg.require(session == self.root.name, 'SESSION_MISMATCH')
            self.validate_admission()
            a.publish(self.root / 'consumed.json', dict(session=session, binding_sha=expected_digest))

        def claim(self, session, alias):
            cfg.require(session == self.root.name and alias in ('A', 'B'), 'WORKER_SESSION')
            self._admission = self.validate_admission()
            cfg.require(a.read(self.root / 'consumed.json') == dict(session=session, binding_sha=expected_digest),
                        'NOT_CONSUMED_FOR_EXECUTION')
            a.publish(self.root / ('claim-' + alias + '.json'), dict(session=session, worker=alias))
            self._claimed = alias

        def activate_go(self):
            cfg.require(not self._active and self._claimed in ('A', 'B'), 'GO_REPLAY_OR_NO_CLAIM')
            value = a.read(self.root / 'human_go.json')
            cfg.require(value.get('semantic') == GO_SEMANTIC and value.get('binding_sha') == expected_digest
                and value.get('approval_semantic') == 'OWNER_CURRENT_LIST_EXECUTION_APPROVAL'
                and value.get('session') == self.root.name
                and value.get('approved_requests') == [e['request_id'] for e in self.all_entries()], 'HUMAN_GO_BINDING')
            cfg.require(not (self.root / 'finished.json').exists(), 'CONSUMED_ADMISSION')
            self._active = True

        def admission(self, session):
            self.check()
            cfg.require(session == self.root.name and self._admission is not None, 'ADMISSION_SESSION')
            # This record's bytes are held under a coordinator Windows read lease.
            # Returning a private copy prevents callers mutating the frozen snapshot.
            return copy.deepcopy(self._admission)

        def events(self, alias):
            cfg.require(alias == self._claimed, 'CROSS_USER_ACCESS')
            events = []
            for n, path in enumerate(sorted(self.root.glob(alias + '-*.json')), 1):
                cfg.require(path.name == alias + '-' + str(n).zfill(6) + '.json', 'CORRUPT_SEQUENCE')
                event = a.read(path); i = event['index']
                cfg.require(type(i) is int and 0 <= i < len(a.requests(alias)), 'EVENT_INDEX')
                cfg.require(type(event['sequence']) is int and event['sequence'] == n
                    and a.exact(event['binding'], self.binding(alias, i)), 'EVENT_BINDING')
                events.append(event)
            observed = self._seen[alias]
            cfg.require(len(events) >= len(observed) and all(a.exact(e, old)
                for e, old in zip(events, observed)), 'JOURNAL_TRUNCATED_OR_CHANGED')
            for i in range(len(a.requests(alias))):
                chain = [e['record'] for e in events if e['index'] == i]
                if chain:
                    validate_chain(chain, self.binding(alias, i))
            self._seen[alias] = tuple(copy.deepcopy(events))
            return events

        def write(self, username, journal, session, crash_hook=None):
            # Adapter Store.write invariants retained; transition validation is
            # performed BEFORE durable publication, never after the action.
            alias = self.bindings[username]; old, _ = self.view(username, session)
            cfg.require(a.exact(journal.get('user_key'), old['user_key']) and
                journal.get('schema_version') == old['schema_version'], 'WRONG_USER')
            keys = {m._journal_request_key(m._journal_identity(username, r)): i
                    for i, r in enumerate(a.requests(alias))}
            cfg.require(set(journal['requests']) <= set(keys) and set(old['requests']) <= set(journal['requests']), 'WRONG_REQUEST')
            changed = [k for k, v in journal['requests'].items() if not a.exact(v, old['requests'].get(k))]
            cfg.require(len(changed) == 1, 'CROSS_REQUEST_WRITE')
            key = changed[0]; index = keys[key]; rec = journal['requests'][key]; request = a.requests(alias)[index]
            cfg.require(a.exact(rec.get('identity'), m._journal_identity(username, request)) and
                rec.get('request_fingerprint') == m._request_fingerprint(username, request) and
                a.exact(rec.get('preferred_positions'), request['positions']), 'WRITE_BINDING')
            prior = old['requests'].get(key)
            if prior and (prior.get('submit_intent_durable') or prior.get('submission_attempted')):
                cfg.require(rec['state'] in ('SUBMIT_INTENT', 'CONFIRMED', 'PRESERVATION_UNKNOWN', 'FAILED_FINAL')
                    and rec['attempt_count'] == prior['attempt_count'], 'PROVISIONAL_RESUBMIT')
            events = self.events(alias)
            chain = [e['record'] for e in events if e['index'] == index] + [self.sanitize(rec)]
            validate_chain(chain, self.binding(alias, index))
            n = len(events) + 1
            a.publish(self.root / (alias + '-' + str(n).zfill(6) + '.json'),
                dict(sequence=n, index=index, binding=self.binding(alias, index), record=self.sanitize(rec)))
            # Pin the just-written event in the observed prefix even if the next
            # operation is the native click and the file is externally truncated.
            self._seen[alias] = tuple(copy.deepcopy(events + [dict(sequence=n, index=index,
                binding=self.binding(alias, index), record=self.sanitize(rec))]))

    return RuntimeStore()


def _quick_connection():
    from quick_recovery.placement import PlacementConnection
    return PlacementConnection(PACKAGE_ROOT)
