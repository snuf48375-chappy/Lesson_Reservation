"""Closed-schema observation only. Never consumes field values or exception text."""
from transition_diagnostic import notify

# Exception-only observation. No decision, browser, retry or journal operations.
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

_FET = None
_RES_FET = None
_RES_ACTIVE = False
_FET_CHANNELS = {'RUNTIME_ORIGINAL', 'CLEANUP', 'WORKER_ABORT'}
_FET_REASONS = frozenset(('CONTINUATION_SOURCE_UNKNOWN DETAIL_RECOVERY_FAILED '
    'AG01_MENU_RECOVERY_FAILED LIST_NAVIGATION_FAILED LIST_DOCUMENT_CHANGED LIST_DEADLINE '
    'AUTOMATIC_LOGIN_FAIL_CLOSED IDENTITY_EXACT_MISMATCH LOGIN_FORM_EXACT_BINDING '
    'MENU_LINK_EXACT_BINDING MENU_SESSION_INVALID MENU_ARRIVAL_UNKNOWN '
    'MENU_STRUCTURE_NOT_READY MENU_SESSION_NOT_READY REQUESTS_UNRESOLVED '
    'ACK_UNKNOWN DURABLE_READBACK_FAILED').split())
_FET_STAGES = frozenset(('WORKER_START WORKER_RUN WORKER_FINAL_CHECK WORKER_TERMINAL '
    'REQUEST LOOP_RECONCILIATION RECONCILIATION_COLLECT RECONCILIATION_APPLY '
    'FINALIZATION FAIL_ATTEMPT FAIL_STATE_CHECK FAIL_BACK FAIL_CONTINUATION_CHECK '
    'RUNTIME_QUIT WORKER_QUIT OPEN_SCHEDULE OBSERVE_DATE OBSERVE_LESSON '
    'POSITION NEXT FINAL_SUBMIT').split())
_FET_STATES = frozenset(('IN_PROGRESS PRE_SUBMIT_FAILED ACTION_INTENT SUBMIT_INTENT '
    'CONFIRMED ALREADY_RESERVED UNKNOWN_AFTER_SUBMIT PRESERVATION_UNKNOWN').split())
_FET_FIELDS = set(('schema_version session worker event_seq channel observed_at_utc '
    'monotonic_ns request_id active_checkpoint last_persisted_checkpoint manifest_sha '
    'exception_type safe_reason_code frames exception_chain payload_sha256 truncated context_status').split())

def _fet_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True).encode('utf-8')).hexdigest().upper()

def fet_start(root, session, worker, manifest_sha, writer=None):
    global _FET, _RES_FET, _RES_ACTIVE
    _RES_FET=None
    _RES_ACTIVE=False
    _FET = None
    try:
        if not re.fullmatch('[0-9a-f]{32}', session) or worker not in ('A', 'B'):
            return
        if not re.fullmatch('[0-9A-F]{64}', manifest_sha):
            return
        _FET = dict(root=Path(root), session=session, worker=worker, manifest=manifest_sha,
                    writer=writer, seq=0, request=None, stage='WORKER_START', persisted=None,
                    original=False, cleanup=None, busy=False, package=Path(__file__).resolve().parents[1])
    except BaseException:
        _FET = None

def fet_context(stage, request_id=None):
    try:
        if _RES_ACTIVE:
            fet_resolution_context(stage, request_id, worker='A')
            return
        if _FET is None:
            return
        _FET['stage'] = stage if stage in _FET_STAGES or stage in CHECKPOINTS else 'UNKNOWN'
        _FET['request'] = (request_id if type(request_id) is str and
            re.fullmatch(_FET['worker']+'[1-7]', request_id) else None)
    except BaseException:
        pass

def fet_persisted(event, record_sha):
    # Called only after the Journal's successful durable readback/ACK check.
    try:
        if _FET is None or event['execution_id'] != _FET['session'] or event['worker'] != _FET['worker']:
            return
        rid = event.get('logical_request_id')
        state = event['payload'].get('state') if type(event['payload']) is dict else None
        value = dict(sequence=event['sequence'], record_sha=record_sha,
                     request_id=rid, state=state if state in _FET_STATES else None)
        if (type(value['sequence']) is int and value['sequence'] > 0 and
            re.fullmatch('[0-9A-F]{64}', record_sha) and
            (rid is None or re.fullmatch(_FET['worker']+'[1-7]', rid))):
            _FET['persisted'] = value
    except BaseException:
        pass

def _fet_exception(exc, package):
    name = type(exc).__name__
    name = name if name in CLASSES else 'OTHER_EXCEPTION_CLASS'
    reason = 'UNCLASSIFIED'
    frames = []
    truncated = False
    tb = exc.__traceback__
    trusted = False
    while tb is not None:
        if len(frames) == 32:
            truncated = True
            break
        code = tb.tb_frame.f_code
        try:
            relative = Path(code.co_filename).resolve().relative_to(package).as_posix()
            trusted = True
            function = code.co_name if re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', code.co_name) else '<anonymous>'
        except (ValueError, OSError):
            relative, function = '<external>', '<external>'
        frames.append(dict(file=relative, function=function, line=tb.tb_lineno))
        tb = tb.tb_next
    if trusted and type(exc) is ValueError and len(exc.args) == 1 and type(exc.args[0]) is str:
        if exc.args[0] in _FET_REASONS:
            reason = exc.args[0]
    return dict(exception_type=name, safe_reason_code=reason, frames=frames), truncated

def fet_validate(value):
    """Diagnostic validity only; never a reservation/admission predicate."""
    try:
        if type(value) is not dict or set(value) != _FET_FIELDS:
            return False
        unsigned = {k:v for k,v in value.items() if k != 'payload_sha256'}
        if value['payload_sha256'] != _fet_digest(unsigned) or value['schema_version'] != 1:
            return False
        if (not re.fullmatch('[0-9a-f]{32}', value['session']) or value['worker'] not in ('A','B') or
            not re.fullmatch('[0-9A-F]{64}', value['manifest_sha']) or
            type(value['event_seq']) is not int or not 1 <= value['event_seq'] <= 16 or
            type(value['monotonic_ns']) is not int or value['monotonic_ns'] < 0 or
            value['channel'] not in _FET_CHANNELS or type(value['truncated']) is not bool or
            value['context_status'] not in ('AVAILABLE','NO_PERSISTED_CHECKPOINT')):
            return False
        if not value['observed_at_utc'].endswith('+00:00'):
            return False
        datetime.fromisoformat(value['observed_at_utc'])
        if value['request_id'] is not None and not re.fullmatch(value['worker']+'[1-7]', value['request_id']):
            return False
        if value['active_checkpoint'] not in _FET_STAGES | set(CHECKPOINTS) | {'UNKNOWN'}:
            return False
        persisted = value['last_persisted_checkpoint']
        if persisted is not None:
            if (type(persisted) is not dict or set(persisted) != {'sequence','record_sha','request_id','state'} or
                type(persisted['sequence']) is not int or persisted['sequence'] < 1 or
                not re.fullmatch('[0-9A-F]{64}', persisted['record_sha']) or
                persisted['state'] not in _FET_STATES | {None} or
                (persisted['request_id'] is not None and not re.fullmatch(value['worker']+'[1-7]', persisted['request_id']))):
                return False
        if value['context_status'] != ('AVAILABLE' if persisted is not None else 'NO_PERSISTED_CHECKPOINT'):
            return False
        chain = value['exception_chain']
        if type(chain) is not list or len(chain) > 7:
            return False
        for item in [value] + chain:
            if item is not value and (set(item) != {'relation','suppressed','exception_type','safe_reason_code','frames'} or
                item['relation'] not in ('cause','context') or type(item['suppressed']) is not bool):
                return False
            if item['exception_type'] not in set(CLASSES) | {'OTHER_EXCEPTION_CLASS'} or item['safe_reason_code'] not in _FET_REASONS | {'UNCLASSIFIED'}:
                return False
            if type(item['frames']) is not list or len(item['frames']) > 32:
                return False
            for frame in item['frames']:
                if set(frame) != {'file','function','line'} or type(frame['line']) is not int or frame['line'] < 1:
                    return False
                if frame['file'] != '<external>' and (not re.fullmatch('[A-Za-z0-9_./-]+',frame['file']) or
                    frame['file'].startswith('/') or '..' in frame['file'].split('/')):
                    return False
                if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*|<anonymous>|<external>',frame['function']):
                    return False
        return True
    except BaseException:
        return False

def fet_capture(channel, exc):
    """Best effort: a probe failure must never replace the observed exception."""
    try:
        if _RES_ACTIVE:
            return fet_resolution_capture(channel, exc)
        ctx = _FET
        if ctx is None or ctx['busy'] or channel not in _FET_CHANNELS or ctx['seq'] >= 16:
            return False
        if channel == 'RUNTIME_ORIGINAL' and (ctx['original'] or ctx['cleanup'] is exc):
            return False
        ctx['busy'] = True
        try:
            if channel == 'RUNTIME_ORIGINAL':
                ctx['original'] = True
            if channel == 'CLEANUP':
                ctx['cleanup'] = exc
            ctx['seq'] += 1
            observed = datetime.now(timezone.utc).isoformat()
            tick = time.monotonic_ns()
            item, truncated = _fet_exception(exc, ctx['package'])
            chain, seen, current = [], {id(exc)}, exc
            while current.__cause__ is not None or current.__context__ is not None:
                relation = 'cause' if current.__cause__ is not None else 'context'
                next_exc = current.__cause__ if relation == 'cause' else current.__context__
                if id(next_exc) in seen or len(chain) == 7:
                    truncated = True
                    break
                seen.add(id(next_exc))
                child, cut = _fet_exception(next_exc, ctx['package'])
                child.update(relation=relation, suppressed=bool(current.__suppress_context__))
                chain.append(child)
                truncated |= cut
                current = next_exc
            value = dict(schema_version=1, session=ctx['session'], worker=ctx['worker'],
                event_seq=ctx['seq'], channel=channel, observed_at_utc=observed, monotonic_ns=tick,
                request_id=ctx['request'], active_checkpoint=ctx['stage'],
                last_persisted_checkpoint=ctx['persisted'], manifest_sha=ctx['manifest'],
                **item, exception_chain=chain, truncated=truncated,
                context_status='AVAILABLE' if ctx['persisted'] is not None else 'NO_PERSISTED_CHECKPOINT')
            value['payload_sha256'] = _fet_digest(value)
            if not fet_validate(value):
                return False
            path = ctx['root'] / 'native_logs' / ('exception-'+ctx['worker']+'-'+str(ctx['seq']).zfill(6)+'.json')
            if ctx['writer'] is None:
                from retry_continuation import publish
                path.parent.mkdir(parents=True, exist_ok=True)
                publish(path, value)
            else:
                ctx['writer'](path, value)
            def unique(pairs):
                out = {}
                for key, val in pairs:
                    if key in out:
                        raise ValueError('DUPLICATE_KEY')
                    out[key] = val
                return out
            readback = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)
            return readback == value and fet_validate(readback)
        finally:
            ctx['busy'] = False
    except BaseException:
        return False

# A distinct diagnostic schema/context. It is never a Resolution/Admission input.
_RES_CHANNELS = {'RUNTIME_ORIGINAL','CLEANUP','RESOLUTION_ABORT'}
_RES_STAGES = set(('RESOLUTION_START ORIGINAL_VERIFIED ADMISSION_WRITE OWNER_EVENTS_WRITE '
    'INQUIRY_OPEN INQUIRY_OBSERVE OBSERVATION_WRITE PRE_SEAL_BROWSER_CLOSE '
    'SEAL_PUBLISH SEAL_PUBLISHED PRE_SEAL_BROWSER_FINALLY PRE_SEAL_LEASE_CLOSE '
    'POST_SEAL_LEASE_CLOSE PRE_SEAL_LOCK_RELEASE POST_SEAL_LOCK_RELEASE '
    'OPEN_BROWSER_CLEANUP UNKNOWN').split())
_RES_FIELDS = _FET_FIELDS | {'execution_kind','resolution_id','binding_sha'}

def fet_resolution_enter():
    global _RES_FET, _RES_ACTIVE
    _RES_FET=None
    _RES_ACTIVE=True

def fet_resolution_capture(channel, exc):
    try: return _resolution_capture(channel,exc)
    except BaseException: return False

def fet_resolution_start(root, session, resolution_id, manifest_path):
    global _RES_FET
    _RES_FET = None
    try:
        if session != '3851e654c248413cbaf8b2e1dec17099' or not re.fullmatch('[0-9a-f]{32}',resolution_id):
            return
        root=Path(root).absolute()
        if root.resolve()!=root or root.name!='diagnostic_evidence':
            return
        manifest=None
        try: manifest=hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest().upper()
        except BaseException: pass
        _RES_FET=dict(root=root/resolution_id,session=session,resolution_id=resolution_id,
            worker=None,binding=None,manifest=manifest,request=None,stage='RESOLUTION_START',
            persisted=None,seq=0,busy=False,original=False,cleanup=None,
            package=Path(__file__).resolve().parents[1])
    except BaseException:
        _RES_FET=None

def fet_resolution_stop():
    global _RES_FET, _RES_ACTIVE
    _RES_FET=None
    _RES_ACTIVE=False

def fet_resolution_context(stage, request_id=None, worker=None, binding_sha=None):
    try:
        if _RES_FET is None: return
        if stage!=_RES_FET['stage'] or request_id!=_RES_FET['request']:
            _RES_FET.pop('predicate_failure',None)
            _RES_FET.pop('navigation_failure',None)
        _RES_FET['stage']=stage if stage in _RES_STAGES | set(CHECKPOINTS) else 'UNKNOWN'
        _RES_FET['worker']=worker if worker=='A' else None
        _RES_FET['request']=request_id if type(request_id) is str and re.fullmatch('A[1-7]',request_id) else None
        if type(binding_sha) is str and re.fullmatch('[0-9A-F]{64}',binding_sha):
            _RES_FET['binding']=binding_sha
    except BaseException: pass

def fet_resolution_persisted(kind, request_id, evidence_hash):
    try:
        if _RES_FET is None: return
        if kind not in ('ADMISSION','OWNER_EVENTS','OBSERVATION','SEAL'): return
        if not re.fullmatch('[0-9A-F]{64}',evidence_hash): return
        if kind=='OBSERVATION':
            if type(request_id) is not str or not re.fullmatch('A[1-7]',request_id): return
        elif request_id is not None: return
        _RES_FET['persisted']=dict(kind=kind,request_id=request_id,evidence_hash=evidence_hash)
    except BaseException: pass

_NAV_REASON = 'RESOLUTION_NAVIGATION_BINDING'
_NAV_VERSION = 'NAVIGATION_BINDING_P1_P15_V1'
_NAV_FIELDS = {'first_failed_predicate','predicate_definition_version'}
_SCROLL_FIELDS = {'scroll_attempted','revalidation_generation'}
_VIEWPORT_STATUSES = {'VIEWPORT_TRUE','VIEWPORT_FALSE','VIEWPORT_MISSING','VIEWPORT_INVALID'}

def fet_resolution_predicate(exc, predicate, version, *, viewport_status=None,
                             scroll_attempted=None, revalidation_generation=None):
    """Latch only the exception identity and fixed identifiers; no raw values."""
    try:
        ctx=_RES_FET
        if (not _RES_ACTIVE or ctx is None or ctx['stage']!='INQUIRY_OBSERVE'
            or ctx['worker']!='A' or ctx['request'] is None): return
        if (type(exc) is not ValueError or exc.args!=(_NAV_REASON,)
            or type(predicate) is not str or not re.fullmatch(r'P([1-9]|1[0-5])',predicate)
            or version!=_NAV_VERSION): return
        extra=None
        if scroll_attempted is not None or revalidation_generation is not None:
            if type(scroll_attempted) is not bool: return
            if revalidation_generation!=('POST_SCROLL' if scroll_attempted else 'INITIAL'): return
            if viewport_status is not None and viewport_status not in _VIEWPORT_STATUSES: return
            # An unreached P8 has no status field; it is not MISSING or FALSE.
            if (int(predicate[1:])>=8)!=(viewport_status is not None): return
            if predicate=='P8' and viewport_status=='VIEWPORT_TRUE': return
            if int(predicate[1:])>8 and viewport_status!='VIEWPORT_TRUE': return
            extra=dict(scroll_attempted=scroll_attempted,revalidation_generation=revalidation_generation)
            if viewport_status is not None: extra['viewport_status']=viewport_status
        if 'predicate_failure' not in ctx:
            ctx['predicate_failure']=(exc,predicate,version,ctx['request'],extra)
    except BaseException: pass

_OVERLAY_STATUSES = {'CLEAR','PRESENT','MISSING','INVALID'}
_OVERLAY_FIELDS = {'overlay_poll_attempted','overlay_poll_count'}
_NAV_VERSION_V2 = 'NAVIGATION_BINDING_P1_P15_V2'

def _navigation_metadata_valid(value):
    try:
        if type(value['scroll_attempted']) is not bool: return False
        count=value['overlay_poll_count']
        if type(count) is not int or count not in (0,1): return False
        if type(value['overlay_poll_attempted']) is not bool or value['overlay_poll_attempted']!=(count==1): return False
        generation=value['revalidation_generation']
        if generation not in ('INITIAL','POST_SCROLL','POST_OVERLAY_POLL'): return False
        if generation=='POST_OVERLAY_POLL':
            if count!=1: return False
        elif (generation=='POST_SCROLL')!=value['scroll_attempted']: return False
        if 'overlay_status' in value and value['overlay_status'] not in _OVERLAY_STATUSES: return False
        if 'viewport_status' in value and value['viewport_status'] not in _VIEWPORT_STATUSES: return False
        if 'first_failed_predicate' in value:
            p=value['first_failed_predicate']
            if type(p) is not str or not re.fullmatch(r'P([1-9]|1[0-5])',p): return False
            n=int(p[1:])
            if (n>=7)!=('overlay_status' in value): return False
            if n==7 and value['overlay_status']=='CLEAR': return False
            if n>7 and value['overlay_status']!='CLEAR': return False
            if (n>=8)!=('viewport_status' in value): return False
            if n==8 and value['viewport_status']=='VIEWPORT_TRUE': return False
            if n>8 and value['viewport_status']!='VIEWPORT_TRUE': return False
        return True
    except BaseException: return False

def fet_resolution_navigation_failure(exc,predicate,viewport,overlay,scroll,polls,generation,wait=None,rebind=None):
    """Exception-local safe metadata; never read by runtime decision code."""
    try:
        ctx=_RES_FET
        if (not _RES_ACTIVE or ctx is None or ctx['stage']!='INQUIRY_OBSERVE'
            or ctx['worker']!='A' or ctx['request'] is None): return
        extra=dict(scroll_attempted=scroll,overlay_poll_attempted=polls==1,
            overlay_poll_count=polls,revalidation_generation=generation)
        if viewport is not None: extra['viewport_status']=viewport
        if overlay is not None: extra['overlay_status']=overlay
        if predicate is not None:
            if type(exc) is not ValueError or exc.args!=(_NAV_REASON,): return
            extra.update(first_failed_predicate=predicate,predicate_definition_version=_NAV_VERSION_V2)
        if not _navigation_metadata_valid(extra): return
        if wait is not None:
            attempted,result,origin=wait
            if type(attempted) is not bool or result not in ('CLEAR','TIMEOUT','CHECK_FAILED'): return
            if origin!=('POST_SCROLL' if scroll else 'INITIAL'): return
            if (generation=='POST_OVERLAY_POLL')!=(result=='CLEAR'): return
            extra.pop('overlay_poll_attempted'); extra.pop('overlay_poll_count')
            extra.update(overlay_wait_attempted=attempted,overlay_wait_result=result,overlay_wait_generation=origin)
            if generation=='POST_OVERLAY_POLL': extra['revalidation_generation']='POST_OVERLAY_WAIT'
        if rebind is not None:
            if rebind not in ('SUCCESS','NOT_FOUND','MULTIPLE','IDENTITY_MISMATCH','FAILED'): return
            extra.update(stale_rebind_attempted=True,stale_rebind_count=1,stale_rebind_result=rebind,
                revalidation_generation='POST_STALE_REBIND')
        if 'navigation_failure' not in ctx:
            ctx['navigation_failure']=(exc,ctx['request'],extra)
    except BaseException: pass

def _navigation_record_valid(value):
    try:
        if value['payload_sha256']!=_fet_digest({k:v for k,v in value.items() if k!='payload_sha256'}): return False
        fields=_RES_FIELDS|_SCROLL_FIELDS|_OVERLAY_FIELDS
        if 'overlay_status' in value: fields=fields|{'overlay_status'}
        if 'viewport_status' in value: fields=fields|{'viewport_status'}
        nav='first_failed_predicate' in value
        if nav:
            fields=fields|_NAV_FIELDS
            if (value['predicate_definition_version']!=_NAV_VERSION_V2 or value['safe_reason_code']!=_NAV_REASON
                or value['exception_type']!='ValueError'): return False
        if set(value)!=fields or not _navigation_metadata_valid(value): return False
        if (value['worker']!='A' or value['request_id'] is None or value['active_checkpoint']!='INQUIRY_OBSERVE'
            or value['channel'] not in ('RUNTIME_ORIGINAL','RESOLUTION_ABORT')): return False
        # Reuse unchanged schema-2 checks for timestamps, frames, chain and context.
        base={k:value[k] for k in _RES_FIELDS}
        base['schema_version']=2
        if nav: base['safe_reason_code']='UNCLASSIFIED'
        base['payload_sha256']=_fet_digest({k:v for k,v in base.items() if k!='payload_sha256'})
        return fet_resolution_validate(base)
    except BaseException: return False

_WAIT_FIELDS={'overlay_wait_attempted','overlay_wait_result','overlay_wait_generation'}

def _wait_record_valid(value):
    try:
        if value['payload_sha256']!=_fet_digest({k:v for k,v in value.items() if k!='payload_sha256'}): return False
        if not _WAIT_FIELDS<=set(value) or _OVERLAY_FIELDS & set(value): return False
        attempted=value['overlay_wait_attempted']; result=value['overlay_wait_result']
        if type(attempted) is not bool or result not in ('CLEAR','TIMEOUT','CHECK_FAILED'): return False
        if value['overlay_wait_generation']!=('POST_SCROLL' if value['scroll_attempted'] else 'INITIAL'): return False
        post=value['revalidation_generation']=='POST_OVERLAY_WAIT'
        if post != (result=='CLEAR') or (not attempted and result!='CHECK_FAILED'): return False
        base={k:v for k,v in value.items() if k not in _WAIT_FIELDS}
        base.update(schema_version=5,overlay_poll_attempted=attempted,overlay_poll_count=int(attempted))
        if post: base['revalidation_generation']='POST_OVERLAY_POLL'
        base['payload_sha256']=_fet_digest({k:v for k,v in base.items() if k!='payload_sha256'})
        return _navigation_record_valid(base)
    except BaseException: return False

_REBIND_FIELDS={'stale_rebind_attempted','stale_rebind_count','stale_rebind_result'}

def _rebind_record_valid(value):
    try:
        if value['payload_sha256']!=_fet_digest({k:v for k,v in value.items() if k!='payload_sha256'}): return False
        if value['stale_rebind_attempted'] is not True or type(value['stale_rebind_count']) is not int or value['stale_rebind_count']!=1: return False
        if value['stale_rebind_result'] not in ('SUCCESS','NOT_FOUND','MULTIPLE','IDENTITY_MISMATCH','FAILED'): return False
        if value['revalidation_generation']!='POST_STALE_REBIND': return False
        base={k:v for k,v in value.items() if k not in _REBIND_FIELDS}
        wait='overlay_wait_attempted' in base
        base['schema_version']=6 if wait else 5
        base['revalidation_generation']=('POST_OVERLAY_WAIT' if base.get('overlay_wait_result')=='CLEAR' else
            'POST_SCROLL' if base['scroll_attempted'] else 'INITIAL')
        base['payload_sha256']=_fet_digest({k:v for k,v in base.items() if k!='payload_sha256'})
        return _wait_record_valid(base) if wait else _navigation_record_valid(base)
    except BaseException: return False

def fet_resolution_validate(value):
    try:
        if type(value) is not dict: return False
        if value.get('schema_version')==7: return _rebind_record_valid(value)
        if value.get('schema_version')==6: return _wait_record_valid(value)
        if value.get('schema_version')==5: return _navigation_record_valid(value)
        nav=value.get('schema_version') in (3,4)
        scroll=value.get('schema_version')==4
        fields=_RES_FIELDS|_NAV_FIELDS if nav else _RES_FIELDS
        if scroll:
            fields=fields|_SCROLL_FIELDS
            if 'viewport_status' in value: fields=fields|{'viewport_status'}
            if type(value.get('scroll_attempted')) is not bool: return False
            if value.get('revalidation_generation')!=('POST_SCROLL' if value['scroll_attempted'] else 'INITIAL'): return False
            predicate=value.get('first_failed_predicate','')
            if type(predicate) is not str or not re.fullmatch(r'P([1-9]|1[0-5])',predicate): return False
            if (int(predicate[1:])>=8)!=('viewport_status' in value): return False
            if 'viewport_status' in value and value['viewport_status'] not in _VIEWPORT_STATUSES: return False
            if predicate=='P8' and value.get('viewport_status')=='VIEWPORT_TRUE': return False
            if int(predicate[1:])>8 and value.get('viewport_status')!='VIEWPORT_TRUE': return False
        if set(value)!=fields: return False
        if nav and (value['safe_reason_code']!=_NAV_REASON or value['exception_type']!='ValueError'
            or value['channel'] not in ('RUNTIME_ORIGINAL','RESOLUTION_ABORT')
            or value['worker']!='A' or value['request_id'] is None
            or value['active_checkpoint']!='INQUIRY_OBSERVE'
            or type(value['first_failed_predicate']) is not str
            or not re.fullmatch(r'P([1-9]|1[0-5])',value['first_failed_predicate'])
            or value['predicate_definition_version']!=_NAV_VERSION): return False
        if value['payload_sha256']!=_fet_digest({k:v for k,v in value.items() if k!='payload_sha256'}): return False
        if value['schema_version'] not in (2,3,4) or value['execution_kind']!='RESOLUTION': return False
        if value['session']!='3851e654c248413cbaf8b2e1dec17099' or not re.fullmatch('[0-9a-f]{32}',value['resolution_id']): return False
        if value['worker'] not in (None,'A') or value['channel'] not in _RES_CHANNELS: return False
        if type(value['event_seq']) is not int or not 1<=value['event_seq']<=16: return False
        if type(value['monotonic_ns']) is not int or value['monotonic_ns']<0 or type(value['truncated']) is not bool: return False
        if not value['observed_at_utc'].endswith('+00:00'): return False
        datetime.fromisoformat(value['observed_at_utc'])
        for name in ('manifest_sha','binding_sha'):
            if value[name] is not None and not re.fullmatch('[0-9A-F]{64}',value[name]): return False
        if value['request_id'] is not None and not re.fullmatch('A[1-7]',value['request_id']): return False
        if value['active_checkpoint'] not in _RES_STAGES | set(CHECKPOINTS): return False
        p=value['last_persisted_checkpoint']
        if p is not None:
            if type(p) is not dict or set(p)!={'kind','request_id','evidence_hash'}: return False
            if p['kind'] not in ('ADMISSION','OWNER_EVENTS','OBSERVATION','SEAL') or not re.fullmatch('[0-9A-F]{64}',p['evidence_hash']): return False
            if p['kind']=='OBSERVATION':
                if type(p['request_id']) is not str or not re.fullmatch('A[1-7]',p['request_id']): return False
            elif p['request_id'] is not None: return False
        status='PARTIAL' if value['manifest_sha'] is None or value['binding_sha'] is None else ('AVAILABLE' if p else 'NO_PERSISTED_CHECKPOINT')
        if value['context_status']!=status: return False
        chain=value['exception_chain']
        if type(chain) is not list or len(chain)>7: return False
        for item in [value]+chain:
            if item is not value and (set(item)!={'relation','suppressed','exception_type','safe_reason_code','frames'} or
                item['relation'] not in ('cause','context') or type(item['suppressed']) is not bool): return False
            if item['exception_type'] not in set(CLASSES)|{'OTHER_EXCEPTION_CLASS'} or item['safe_reason_code'] not in _FET_REASONS|{'UNCLASSIFIED'}|({_NAV_REASON} if nav and item is value else set()): return False
            if type(item['frames']) is not list or len(item['frames'])>32: return False
            for f in item['frames']:
                if set(f)!={'file','function','line'} or type(f['line']) is not int or f['line']<1: return False
                if f['file']!='<external>' and (not re.fullmatch('[A-Za-z0-9_./-]+',f['file']) or f['file'].startswith('/') or '..' in f['file'].split('/')): return False
                if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*|<anonymous>|<external>',f['function']): return False
        return True
    except BaseException: return False

def _resolution_capture(channel, exc):
    ctx=_RES_FET
    if ctx is None or ctx['busy'] or channel not in _RES_CHANNELS or ctx['seq']>=16: return False
    if channel=='RUNTIME_ORIGINAL' and (ctx['original'] or ctx['cleanup'] is exc): return False
    ctx['busy']=True
    try:
        if channel=='RUNTIME_ORIGINAL': ctx['original']=True
        if channel=='CLEANUP': ctx['cleanup']=exc
        ctx['seq']+=1
        item,truncated=_fet_exception(exc,ctx['package'])
        chain=[]; seen={id(exc)}; current=exc
        while current.__cause__ is not None or current.__context__ is not None:
            relation='cause' if current.__cause__ is not None else 'context'
            child_exc=current.__cause__ if relation=='cause' else current.__context__
            if id(child_exc) in seen or len(chain)==7:
                truncated=True; break
            seen.add(id(child_exc))
            child,cut=_fet_exception(child_exc,ctx['package'])
            child.update(relation=relation,suppressed=bool(current.__suppress_context__))
            chain.append(child); truncated|=cut; current=child_exc
        value=dict(schema_version=2,execution_kind='RESOLUTION',session=ctx['session'],resolution_id=ctx['resolution_id'],
            worker=ctx['worker'],binding_sha=ctx['binding'],event_seq=ctx['seq'],channel=channel,
            observed_at_utc=datetime.now(timezone.utc).isoformat(),monotonic_ns=time.monotonic_ns(),
            request_id=ctx['request'],active_checkpoint=ctx['stage'],last_persisted_checkpoint=ctx['persisted'],
            manifest_sha=ctx['manifest'],**item,exception_chain=chain,truncated=truncated,
            context_status='PARTIAL' if ctx['manifest'] is None or ctx['binding'] is None else ('AVAILABLE' if ctx['persisted'] else 'NO_PERSISTED_CHECKPOINT'))
        failure=ctx.get('predicate_failure')
        if (failure is not None and failure[0] is exc and failure[3]==ctx['request']
            and ctx['stage']=='INQUIRY_OBSERVE' and channel in ('RUNTIME_ORIGINAL','RESOLUTION_ABORT')):
            value.update(schema_version=3,safe_reason_code=_NAV_REASON,
                first_failed_predicate=failure[1],predicate_definition_version=failure[2])
            if failure[4] is not None:
                value.update(schema_version=4,**failure[4])
        navigation=ctx.get('navigation_failure')
        if (navigation is not None and navigation[0] is exc and navigation[1]==ctx['request']
            and ctx['stage']=='INQUIRY_OBSERVE' and channel in ('RUNTIME_ORIGINAL','RESOLUTION_ABORT')):
            value.update(schema_version=7 if 'stale_rebind_attempted' in navigation[2] else 6 if 'overlay_wait_attempted' in navigation[2] else 5,**navigation[2])
            if 'first_failed_predicate' in navigation[2]: value['safe_reason_code']=_NAV_REASON
        value['payload_sha256']=_fet_digest(value)
        if not fet_resolution_validate(value): return False
        path=ctx['root']/'native_logs'/('exception-resolution-'+str(ctx['seq']).zfill(6)+'.json')
        if path.resolve()!=path.absolute(): return False
        path.parent.mkdir(parents=True,exist_ok=True)
        from retry_continuation import publish, read
        publish(path,value)
        actual=read(path)
        return actual==value and fet_resolution_validate(actual)
    finally:
        ctx['busy']=False
CHECKPOINTS = ('CREDENTIAL_PREVALIDATION CHROME_CREATED LOGIN_GET_START LOGIN_GET_RETURN '
 'LOGIN_PAGE_SNAPSHOT LOGIN_FORM_INITIAL_BINDING USERNAME_FIELD_INITIAL_BINDING '
 'PASSWORD_FIELD_INITIAL_BINDING SUBMIT_ELEMENT_INITIAL_BINDING CREDENTIAL_RUNTIME_RETRIEVAL '
 'USERNAME_INPUT_COMPLETE PASSWORD_INPUT_COMPLETE LOGIN_FORM_REBIND SUBMIT_GUARD_PASS '
 'LOGIN_SUBMIT_INVOCATION LOGIN_SUBMIT_RETURN POST_LOGIN_PAGE_WAIT IDENTITY_EXACT_MATCH MENU_READY').split()
REASONS = set(('LOGIN_GET_FAILED LOGIN_PAGE_MISMATCH LOGIN_FORM_COUNT_MISMATCH '
 'LOGIN_FORM_CONTRACT_MISMATCH USERNAME_FIELD_MISMATCH PASSWORD_FIELD_MISMATCH '
 'SUBMIT_ELEMENT_MISMATCH ELEMENT_NOT_DISPLAYED ELEMENT_DISABLED '
 'CREDENTIAL_RUNTIME_RETRIEVAL_FAILED USERNAME_INPUT_FAILED PASSWORD_INPUT_FAILED '
 'FORM_REBIND_MISMATCH SUBMIT_GUARD_FAILED LOGIN_SUBMIT_FAILED POST_LOGIN_TIMEOUT '
 'IDENTITY_MISMATCH MENU_READY_FAILED UNCLASSIFIED_EXCEPTION').split())
CLASSES = set(('ValueError RuntimeError TypeError KeyError OSError PermissionError '
 'TimeoutException WebDriverException JavascriptException NoSuchElementException '
 'StaleElementReferenceException ElementNotInteractableException ElementClickInterceptedException '
 'InvalidSessionIdException NoSuchWindowException KeyboardInterrupt SystemExit').split())
BOOLS = ('origin_match path_match exact_url_match title_match method_post action_match target_allowed '
 'override_absent username_displayed password_displayed submit_displayed username_enabled '
 'password_enabled submit_enabled username_type password_type submit_type username_id_name '
 'password_id_name submit_id_name username_same_form password_same_form submit_same_form same_elements').split()
COUNTS = ('form_count document_form_count username_count password_count submit_count').split()

class Trace:
    def __init__(self):
        self.data = dict(checkpoints={k:'NOT_REACHED' for k in CHECKPOINTS},
            last_completed_checkpoint='NOT_REACHED', failed_checkpoint='NOT_REACHED',
            reason_code='NOT_REACHED', exception_class='NOT_REACHED',
            credential=dict(prevalidation_retrieval='NOT_REACHED', automatic_prevalidation_retrieval='NOT_REACHED',
                runtime_retrieval='NOT_REACHED', worker_binding='UNKNOWN', expected_identity_binding='UNKNOWN'),
            initial={k:'NOT_REACHED' for k in BOOLS+COUNTS+['ready_state']},
            rebind={k:'NOT_REACHED' for k in BOOLS+COUNTS+['ready_state']},
            username_input_complete=False,password_input_complete=False,
            submit_guard_pass=False,submit_attempt_count=0,native_click_reached=False)
        self.active='CREDENTIAL_PREVALIDATION'
        self.reason='UNCLASSIFIED_EXCEPTION'
    def start(self, checkpoint, reason='UNCLASSIFIED_EXCEPTION'):
        self.active=checkpoint; self.reason=reason
        notify(self, 'start', checkpoint)
    def done(self, checkpoint):
        self.data['checkpoints'][checkpoint]='PASS'
        self.data['last_completed_checkpoint']=checkpoint
        notify(self, 'done', checkpoint)
    def fail(self, exc):
        if self.data['failed_checkpoint']!='NOT_REACHED': return
        self.data['failed_checkpoint']=self.active
        self.data['checkpoints'][self.active]='FAIL'
        self.data['reason_code']=self.reason if self.reason in REASONS else 'UNCLASSIFIED_EXCEPTION'
        name=type(exc).__name__
        self.data['exception_class']=name if name in CLASSES else 'OTHER_EXCEPTION_CLASS'
        notify(self, 'fail', self.active)
    def snapshot(self, stage, raw):
        target=self.data[stage]
        target['title_match']='UNKNOWN_NO_LOGIN_TITLE_CONTRACT'
        target['submit_id_name']='UNKNOWN_NO_SUBMIT_ID_NAME_CONTRACT'
        if not isinstance(raw,dict): return
        for k in BOOLS:
            if type(raw.get(k)) is bool: target[k]=raw[k]
        for k in COUNTS:
            if type(raw.get(k)) is int and 0<=raw[k]<=100000: target[k]=raw[k]
        if raw.get('ready_state') in ('loading','interactive','complete'): target['ready_state']=raw['ready_state']
    def initial_binding(self, accepted):
        s=self.data['initial']
        checks=[('LOGIN_PAGE_SNAPSHOT','LOGIN_PAGE_MISMATCH',all(s[k] is True for k in ('origin_match','path_match','exact_url_match')) and s['ready_state']=='complete'),
          ('LOGIN_FORM_INITIAL_BINDING','LOGIN_FORM_COUNT_MISMATCH',s['form_count']==1),
          ('LOGIN_FORM_INITIAL_BINDING','LOGIN_FORM_CONTRACT_MISMATCH',all(s[k] is True for k in ('method_post','action_match','target_allowed','override_absent')))]
        for role,cp,reason in [('username','USERNAME_FIELD_INITIAL_BINDING','USERNAME_FIELD_MISMATCH'),('password','PASSWORD_FIELD_INITIAL_BINDING','PASSWORD_FIELD_MISMATCH'),('submit','SUBMIT_ELEMENT_INITIAL_BINDING','SUBMIT_ELEMENT_MISMATCH')]:
            keys=[role+'_type',role+'_same_form']+([role+'_id_name'] if role!='submit' else [])
            checks.extend([(cp,reason,s[role+'_count']==1 and all(s[k] is True for k in keys)),
                           (cp,'ELEMENT_NOT_DISPLAYED',s[role+'_displayed'] is True),
                           (cp,'ELEMENT_DISABLED',s[role+'_enabled'] is True)])
        for i,(cp,reason,ok) in enumerate(checks):
            if not accepted and not ok:
                self.start(cp,reason); return
            if i==len(checks)-1 or checks[i+1][0]!=cp: self.done(cp)
        if not accepted: self.start('LOGIN_FORM_INITIAL_BINDING','UNCLASSIFIED_EXCEPTION')

# Runs in the same script call as the unchanged form predicate. No field value,
# text, DOM, HTML, URL, title, id or name is returned; only comparisons/counts.
SNAPSHOT_SCRIPT = r'''
const expected=new URL(arguments[0]), q=s=>Array.from(document.querySelectorAll(s));
const ns=q('#UserName,input[name="UserName"]'),ps=q('#Password,input[name="Password"],input[type="password"]'),bs=q('input.btn_conform');
const n=ns[0],p=ps[0],b=bs[0],f=n&&n.form;
const out={origin_match:location.origin===expected.origin,path_match:location.pathname===expected.pathname,
 exact_url_match:location.href===arguments[0],ready_state:document.readyState,
 form_count:new Set(ns.map(e=>e.form).filter(Boolean)).size,document_form_count:q('form').length,username_count:ns.length,password_count:ps.length,submit_count:bs.length};
if(typeof arguments[1]==='string')out.title_match=document.title===arguments[1];
for(const [role,e] of [['username',n],['password',p],['submit',b]]){
 if(!e)continue;const s=getComputedStyle(e),r=e.getBoundingClientRect();
 out[role+'_displayed']=r.width>0&&r.height>0&&s.visibility==='visible'&&s.display!=='none';
 out[role+'_enabled']=!e.disabled;out[role+'_same_form']=!!f&&e.form===f;
 out[role+'_type']=role==='username'?['text','tel','email'].includes(e.type):e.type===(role==='password'?'password':'submit');
 if(role!=='submit'){const wanted=role==='username'?'UserName':'Password';out[role+'_id_name']=e.id===wanted&&e.name===wanted;}
}
if(f){const u=new URL(f.action,location.href);out.method_post=f.method.toUpperCase()==='POST';
 out.action_match=u.origin===location.origin&&u.pathname==='/DSPWebUser/Account/Login'&&!u.search&&!u.hash;
 out.target_allowed=!f.target;}
if(b)out.override_absent=!b.hasAttribute('formaction')&&!b.hasAttribute('formmethod')&&!b.hasAttribute('formtarget');
return out;
'''

def form_observation_script(original):
    # Diagnostic errors cannot change the result of the original predicate.
    return ('/* STAGEC_DIAGNOSTIC_FORM */ const bound=(function(){'+original+
        '}).apply(null,arguments);let observation={};try{observation=(function(){'+SNAPSHOT_SCRIPT+
        '}).apply(null,arguments);}catch(e){}return {bound:bound,observation:observation};')
