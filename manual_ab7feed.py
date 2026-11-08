"""Exact ab7feed supplemental resolution. No browser or reservation interfaces.

Candidate formal issuance is disabled. Fixture publication is restricted to this
review workspace's work directory. Checksums protect bytes, not server truth.
"""
import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
import retry_continuation as rc
from runtime_config import digest as binding_digest
from package_authority import OPERATIONAL_ROOT

SESSION = 'ab7feed24d2440dcb37c4e054ecd473e'
SCHEMA = 'AB7FEED_OWNER_CLOSEOUT_V1'
AUTHORITY = 'AB7FEED-CLOSEOUT-REVISED-DRAFT-20261014-02'
APP = Path(__file__).resolve().parent
ROOT = OPERATIONAL_ROOT
STATE = ROOT / 'runtime/reservation_journal/schema-v2/cla1-request-local-v1'
RECEIPT = ROOT / 'runtime/supplemental_resolution_ab7feed_owner'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()

def plain(p):
    p = Path(p).absolute()
    rc.require(p.resolve() == p, 'AB7_PATH_REDIRECTED')
    for part in (p, *p.parents):
        rc.require(not part.is_symlink() and not (hasattr(part, 'is_junction') and part.is_junction()), 'AB7_PATH_REDIRECTED')
    return p

def inventory(p):
    p = plain(p)
    return {f.relative_to(p).as_posix(): sha(plain(f)) for f in sorted(p.rglob('*')) if f.is_file()}

def contract():
    manifest = rc.read(APP.parent / 'OPERATIONAL_MANIFEST.json')
    ref = manifest['manual_ab7feed_contract']
    path = plain(ref['path'])
    rc.require(sha(path) == ref['sha256'], 'AB7_CONTRACT_IDENTITY')
    c = rc.read(path)
    rc.require(c['session'] == SESSION and c['schema'] == SCHEMA and c['authority'] == AUTHORITY
               and type(c['max_age_seconds']) is int and c['max_age_seconds'] == 300, 'AB7_CONTRACT_SCOPE')
    for name, expected in c['documents'].items():
        rc.require(sha(plain(path.parent / name)) == expected, 'AB7_DOCUMENT_CHANGED')
    for name, expected in c['authority_refs'].items():
        rc.require(sha(plain(path.parent/'baseline'/name)) == expected, 'AB7_BASELINE_AUTHORITY_CHANGED')
        if name.endswith('.md'):
            rc.require(sha(plain(ROOT/name)) == expected, 'AB7_ACTIVE_AUTHORITY_CHANGED')
    for name, expected in manifest['runtime_files'].items():
        rc.require(sha(plain(APP.parent / name)) == expected, 'AB7_SOURCE_CHANGED')
    rc.require(set(inventory(APP.parent)) == set(manifest['runtime_files']) | {'OPERATIONAL_MANIFEST.json'}, 'AB7_PACKAGE_INVENTORY')
    return c

def original(directory=None):
    directory = plain(directory or STATE / SESSION)
    rc.require(directory == STATE / SESSION, 'AB7_SESSION_PATH')
    c = contract(); files = inventory(directory)
    rc.require(files == c['original_inventory'], 'AB7_ORIGINAL_CHANGED')
    a = rc.read(directory / 'admission.json'); b = a['binding']
    from admission_control import entries, GO_SEMANTIC
    rc.require(a['schema'] == rc.SCHEMA and a['session'] == SESSION and a['ordinal'] == 23
               and a['previous_run'] is None and a['entries'] == entries(b) == c['target_entries'], 'AB7_ADMISSION')
    rc.require(rc.digest(b) == c['journal_binding_sha'] and binding_digest(b) == c['admission_binding_sha']
               and b['manifest_sha'] == c['original_manifest_sha']
               and b['reservation_list_file_sha'] == c['original_list_sha'], 'AB7_BINDING')
    rc.require(rc.read(directory / 'consumed.json') == dict(session=SESSION, binding_sha=binding_digest(b)), 'AB7_CONSUMED')
    go = rc.read(directory / 'human_go.json')
    rc.require(go.get('semantic') == GO_SEMANTIC and go.get('binding_sha') == binding_digest(b), 'AB7_GO')
    models = {}; tails = {}
    for w, count in [('A', 3), ('B', 11)]:
        es = [dict(e, canonical_lesson=b['request_keys'][w][i][1]) for i, e in enumerate(e for e in a['entries'] if e['worker'] == w)]
        rc.require(len(es) == 1 and es[0]['request_id'] == w+'1' and es[0]['user_binding'] == 'FIXED_USER_'+w, 'AB7_TARGET')
        j = rc.Journal(directory / 'request_attempts' / w, w, es, b, SESSION)
        events = j.events(); model, _, registered = j.view()
        rc.require(registered and len(events) == count and events[0]['event_type'] == 'REGISTER', 'AB7_CHAIN')
        rc.require(rc.read(directory / ('claim-'+w+'.json')) == dict(session=SESSION, worker=w)
                   and rc.read(directory / ('login-'+w+'.json')) == dict(code='OK', state='LOGINED'), 'AB7_WORKER')
        models[w] = model[w+'1']; tails[w] = rc.digest(events[-1])
    a1 = models['A']; b1 = models['B']
    rc.require(len(a1['attempts']) == 1 and rc.safe(a1['attempts'][0])
               and a1['attempts'][0]['phase'] == 'P14'
               and a1['attempts'][0]['failure_reason'] == 'LESSON_DETAIL_UNKNOWN', 'AB7_A_UNSENT')
    rc.require(b1['result'] == 'CONFIRMED' and len(b1['attempts']) == 1
               and b1['attempts'][0]['submission_attempted'] is True
               and b1['attempts'][0]['selected_position'] == 17
               and b1['attempts'][0]['complete_evidence']['positive'] is True
               and b1['attempts'][0]['confirmation_evidence']['positive'] is True, 'AB7_B_CONFIRMED')
    rc.require(rc.read(directory / 'worker-A.json') == dict(status='ABORT', exception_type='ValueError')
               and rc.read(directory / 'worker-B.json') == dict(status='COMPLETED')
               and rc.read(directory / 'results.json')['worker_exit_codes'] == [1, 0], 'AB7_ABNORMAL_HISTORY')
    rc.require(inventory(directory) == files, 'AB7_ORIGINAL_CHANGED_DURING_READ')
    return dict(session=SESSION, original_evidence_digest=rc.digest(files),
                journal_binding_sha=rc.digest(b), admission_binding_sha=binding_digest(b),
                target_entries=a['entries'], event_tails=tails,
                a1_historical='SAFE_PRE_SUBMIT_FAILED_ATTEMPT_1', b1_historical='CONFIRMED', historical_closed=False)

def timestamp(value):
    rc.require(type(value) is str, 'AB7_TIMESTAMP')
    d = datetime.fromisoformat(value)
    rc.require(d.tzinfo is not None, 'AB7_TIMESTAMP_ZONE')
    return d.astimezone(timezone.utc)

def declaration(worker, observed, mode):
    rc.require(worker in ('A', 'B') and mode in ('ACTUAL', 'OFFLINE_FIXTURE'), 'AB7_DECLARATION_MODE')
    c = contract()
    return dict(request_id=worker+'1', session=SESSION, target=c['target_entries'][0 if worker=='A' else 1],
                owner='たかし' if mode=='ACTUAL' else 'FIXTURE_OWNER', evidence_class='OWNER_DECLARED',
                origin='OWNER_CURRENT_STATE' if mode=='ACTUAL' else 'OFFLINE_FIXTURE',
                observed_at=observed, identity_verified=True, target_unambiguous=True,
                current_not_reserved=True, no_changes_since_observation=True,
                manual_cancellation_completed=(worker=='B'), cancellation_actual_at='NOT_PROVIDED')

# Fixture controls exist only for an explicitly selected isolated test adapter.
FIXTURE_ISSUER_ENABLED = False

def canonical_bytes(value):
    import json
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')

def generation(mode):
    rc.require(mode in ('ACTUAL', 'OFFLINE_FIXTURE'), 'AB7_MODE')
    ref = rc.read(APP.parent/'OPERATIONAL_MANIFEST.json')['manual_ab7feed_contract']['issuance_generation']
    path = plain(ref['path'])
    rc.require(sha(path) == ref['sha256'], 'AB7_GENERATION_CHANGED')
    g = rc.read(path)
    rc.require(g['schema']=='AB7_FIXED_ISSUANCE_GENERATION_V1' and g['session']==SESSION
               and g['authority']==AUTHORITY and g['contract_sha']==sha(plain(rc.read(APP.parent/'OPERATIONAL_MANIFEST.json')['manual_ab7feed_contract']['path'])), 'AB7_GENERATION_BINDING')
    policy=rc.read(plain(path.parent/'chat_policy.json'))
    rc.require(sha(plain(path.parent/'chat_policy.json'))==g['chat_policy_sha'] and policy==short_policy(g),'AB7_CHAT_POLICY')
    rc.require(g['signature_method']==SHORT_METHOD and g['generation_id']==policy['generation_id'],'AB7_CHAT_GENERATION_SCOPE')
    rc.require(g['resolution_id']==APPROVED_RESOLUTION_ID,'AB7_RESOLUTION_FIXED')
    rc.require(g['source_identity']==rc.digest(g['source_files']), 'AB7_ISSUANCE_SOURCE_IDENTITY')
    rc.require(inventory(path.parent/'generation_source')==g['source_files'], 'AB7_ISSUANCE_SOURCE_CHANGED')
    for name, expected in g['source_files'].items():
        rc.require(sha(plain(path.parent/'generation_source'/name))==expected, 'AB7_ISSUANCE_SOURCE_CHANGED')
    return g, path.parent

CHAT_METHOD = 'OWNER_CHAT_EXPLICIT_V1'
APPROVED_RESOLUTION_ID = '3916fc8c00524e768bdf56a0d932b5da'

# Inserted into the isolated manual_ab7feed.py only.
SHORT_METHOD = 'OWNER_SHORT_CHAT_T0_INTERVAL_V2'
SHORT_TEXT = 'A1未予約、B1取消済み・非保持を今確認。今回のAB7R Closeoutを承認します。'

def short_policy(g):
    return dict(schema='AB7_SHORT_T0_POLICY_V2',session=SESSION,method=SHORT_METHOD,
                contract_sha=g['contract_sha'],generation_id='AB7-IR-SEPARATION-20261015-01',
                approved_resolution_id=APPROVED_RESOLUTION_ID,max_age_seconds=300,
                changes='SHORT_APPROVAL_AND_CONSERVATIVE_T0_PROOF',historical_closed=False,scope='NEW_ONLY',
                observation_time='UNKNOWN_OWNER_ATTESTED_AFTER_CARD',expiry='T0_TO_PRESEAL_UPPER_BOUND')

def short_clock_valid(p,mode):
    rc.require(type(p) is dict and set(p)=={'utc','monotonic_ns','boot_id','source','verified','uncertainty_ms'},'AB7_T0_CLOCK_SCHEMA')
    timestamp(p['utc'])
    rc.require(type(p['monotonic_ns']) is int and p['monotonic_ns']>=0
               and type(p['uncertainty_ms']) is int and 0<=p['uncertainty_ms']<=1000
               and type(p['boot_id']) is str and bool(p['boot_id']) and p['verified'] is True,'AB7_T0_CLOCK_TRUST')
    sources=('OFFLINE_FIXTURE',) if mode=='OFFLINE_FIXTURE' else ('TRUSTED_UTC_CAPTURE_V1','HOST_UTC_ANCHORED_V1')
    rc.require(p['source'] in sources,'AB7_T0_CLOCK_SOURCE')

def short_elapsed(start,end,mode):
    short_clock_valid(start,mode);short_clock_valid(end,mode)
    rc.require(start['boot_id']==end['boot_id'],'AB7_T0_BOOT_CHANGED')
    wall=(timestamp(end['utc'])-timestamp(start['utc'])).total_seconds()
    mono=(end['monotonic_ns']-start['monotonic_ns'])/1_000_000_000
    uncertainty=(start['uncertainty_ms']+end['uncertainty_ms'])/1000
    rc.require(wall>=0 and mono>=0 and abs(wall-mono)<=uncertainty+0.001,'AB7_T0_CLOCK_DISCONTINUITY')
    # Never grant extra freshness because a clock has uncertainty.
    upper=max(mono,wall+uncertainty)
    rc.require(upper<=300,'AB7_T0_EXPIRED')
    return upper

def short_card_text(targets):
    a,b=targets
    return ('今回のAB7R Closeout確認。案内を受け取ってから、次の両対象をOwner本人が確認してください。\n'
            'A1: 固定A / '+a['date']+' / '+a['lesson']+' が未予約。\n'
            'B1: 固定B / '+b['date']+' / '+b['lesson']+' がOwner手動取消済み・現在非保持。\n'
            '確認後の変更なし、A1残作業放棄、今回1件の補足発行を承認する場合だけ、指定の短文をこのカードへ返信してください。\n'
            '通常BAT再開は別承認。T0から300秒超過は発行しません。')

def short_card(snapshot,card_id,t0,delivery,mode,resolution_id=None,reference=None):
    g,_=generation(mode)
    rc.require(type(card_id) is str and re.fullmatch('[0-9a-f]{32}',card_id),'AB7_SHORT_CARD_ID')
    short_clock_valid(t0,mode)
    if reference is None and mode=='OFFLINE_FIXTURE':
        reference=dict(source='OFFLINE_FIXTURE',before_utc=t0['utc'],after_utc=t0['utc'],root_id=delivery['root_id'],trusted_capture=True)
    rc.require(reference is not None,'AB7_T0_REFERENCE_MISSING')
    rid=g['resolution_id'] if mode=='ACTUAL' else resolution_id
    rc.require(type(rid) is str and re.fullmatch('[0-9a-f]{32}',rid),'AB7_SHORT_RESOLUTION_ID')
    return dict(schema='AB7_CONFIRMATION_CARD_V2',mode=mode,session=SESSION,card_id=card_id,
                contract_sha=g['contract_sha'],generation_id=g['generation_id'],resolution_id=rid,
                source_identity=g['source_identity'],policy_sha=g['chat_policy_sha'],snapshot_sha=rc.digest(snapshot),
                original_evidence_digest=snapshot['original_evidence_digest'],journal_binding_sha=snapshot['journal_binding_sha'],
                admission_binding_sha=snapshot['admission_binding_sha'],target_entries=snapshot['target_entries'],
                t0=t0,t0_reference=reference,delivery=delivery,text=short_card_text(snapshot['target_entries']),expected_reply=SHORT_TEXT,
                abandon_a1_remaining_work=True,authorize_one_issuance=True,normal_operation_authorized=False)

def verify_short_card(card,snapshot,mode):
    rc.require(type(card) is dict,'AB7_SHORT_CARD_SCHEMA')
    expected=short_card(snapshot,card['card_id'],card['t0'],card['delivery'],mode,card['resolution_id'],card['t0_reference'])
    rc.require(card==expected,'AB7_SHORT_CARD_BINDING')
    d=card['delivery']
    rc.require(type(d) is dict and set(d)=={'conversation_id','message_id','capture_id','channel','trusted_capture','root_id'},'AB7_SHORT_DELIVERY')
    for key in ('conversation_id','capture_id','root_id'):
        rc.require(type(d[key]) is str and bool(d[key].strip()),'AB7_SHORT_DELIVERY_SOURCE')
    rc.require(d['message_id'] is None or (type(d['message_id']) is str and bool(d['message_id'].strip())),'AB7_SHORT_DELIVERY_SOURCE')
    rc.require(d['trusted_capture'] is True and d['channel']==('OFFLINE_FIXTURE' if mode=='OFFLINE_FIXTURE' else 'OWNER_DIRECT_CHAT'),'AB7_SHORT_DELIVERY_SOURCE')
    reference=card['t0_reference']
    rc.require(type(reference) is dict and set(reference)=={'source','before_utc','after_utc','root_id','trusted_capture'}
               and reference['root_id']==d['root_id'] and reference['trusted_capture'] is True
               and reference['source']==('OFFLINE_FIXTURE' if mode=='OFFLINE_FIXTURE' else 'INDEPENDENT_UTC_REFERENCE_V1'),'AB7_T0_REFERENCE_SOURCE')
    before=timestamp(reference['before_utc']);after=timestamp(reference['after_utc']);point=timestamp(card['t0']['utc'])
    rc.require(before<=point<=after and (after-before).total_seconds()<=2,'AB7_T0_REFERENCE_INTERVAL')
    required=max((point-before).total_seconds(),(after-point).total_seconds())*1000
    rc.require(card['t0']['uncertainty_ms']>=required,'AB7_T0_REFERENCE_UNCERTAINTY')
    rc.require(point<=datetime.now(timezone.utc),'AB7_T0_FUTURE')
    if mode=='ACTUAL':
        g,directory=generation(mode)
        ref=g['capture_root_sha'];rc.require(type(ref) is str and re.fullmatch('[0-9A-F]{64}',ref),'AB7_CAPTURE_NOT_CONFIGURED')
        p=plain(directory/'capture_root.json');rc.require(sha(p)==ref,'AB7_CAPTURE_ROOT_CHANGED')
        root=rc.read(p)
        rc.require(root==dict(schema='AB7_TRUSTED_CAPTURE_ROOT_V1',mode='ACTUAL',session=SESSION,root_id=d['root_id'],
                   owner='たかし',channel='OWNER_DIRECT_CHAT',clock_source='INDEPENDENT_UTC_REFERENCE',approved=True),'AB7_CAPTURE_ROOT_SCOPE')
        rc.require(card['t0']['source']=='TRUSTED_UTC_CAPTURE_V1','AB7_T0_REFERENCE_REQUIRED')
        rc.require(g['active_card_id']==card['card_id'] and type(g['active_card_sha']) is str
                   and sha(plain(directory/'confirmation_cards'/(card['card_id']+'.json')))==g['active_card_sha']
                   and rc.read(directory/'confirmation_cards'/(card['card_id']+'.json'))==card,'AB7_SHORT_ACTIVE_CARD_REQUIRED')
        short_elapsed(card['t0'],g['active_card_clock'],mode)

def short_declarations(record,mode):
    card=record['card'];message=record['owner_message']
    return {w+'1':dict(request_id=w+'1',session=SESSION,target=card['target_entries'][i],
                owner='たかし' if mode=='ACTUAL' else 'FIXTURE_OWNER',evidence_class='OWNER_DECLARED',
                observation_time='UNKNOWN_NOT_ASSIGNED',observation_window=dict(start=card['t0']['utc'],end=message['captured']['utc']),
                attestation='CHECKED_AFTER_THIS_CARD',current_not_reserved=True,manual_cancellation_completed=(w=='B'),
                no_changes_since_observation=True,identity_verified=True,target_unambiguous=True,cancellation_actual_at='NOT_PROVIDED')
            for i,w in enumerate(('A','B'))}

def short_system_claims(snapshot,card,message,mode):
    return dict(generated_by='SYSTEM_NOT_OWNER_ORIGINAL',session=SESSION,mode=mode,method=SHORT_METHOD,
                card_sha=rc.digest(card),owner_message_sha=rc.digest(message),snapshot_sha=rc.digest(snapshot),
                contract_sha=card['contract_sha'],policy_sha=card['policy_sha'],source_identity=card['source_identity'],
                generation_id=card['generation_id'],resolution_id=card['resolution_id'],
                approval_received_at=message['captured']['utc'],abandon_a1_remaining_work=True,authorize_one_issuance=True)

def make_short_record(snapshot,card,message,mode):
    record=dict(schema='AB7_SHORT_APPROVAL_V2',card=card,owner_message=message,
                system_claims=short_system_claims(snapshot,card,message,mode))
    verify_short_record(record,snapshot,mode)
    return record

def verify_short_record(record,snapshot,mode):
    rc.require(type(record) is dict and set(record)=={'schema','card','owner_message','system_claims'}
               and record['schema']=='AB7_SHORT_APPROVAL_V2','AB7_SHORT_RECORD_SCHEMA')
    c=record['card'];verify_short_card(c,snapshot,mode)
    m=record['owner_message']
    keys={'raw_text','raw_text_sha','owner','role','channel','conversation_id','message_id','capture_id','reply_to_message_id',
          'reply_card_id','card_sha','root_id','linkage','direct_owner_confirmed','trusted_capture','forwarded','captured'}
    rc.require(type(m) is dict and set(m)==keys,'AB7_SHORT_MESSAGE_SCHEMA')
    rc.require(m['raw_text']==SHORT_TEXT and m['raw_text_sha']==hashlib.sha256(SHORT_TEXT.encode('utf-8')).hexdigest().upper(),'AB7_SHORT_EXPLICIT_TEXT')
    rc.require(m['owner']==('たかし' if mode=='ACTUAL' else 'FIXTURE_OWNER') and m['role']=='user'
               and m['channel']==c['delivery']['channel'] and m['trusted_capture'] is True
               and m['direct_owner_confirmed'] is True and m['forwarded'] is False,'AB7_SHORT_OWNER_SOURCE')
    rc.require(m['conversation_id']==c['delivery']['conversation_id'] and m['root_id']==c['delivery']['root_id']
               and m['reply_card_id']==c['card_id'] and m['card_sha']==rc.digest(c),'AB7_SHORT_REPLY_BINDING')
    rc.require(type(m['capture_id']) is str and bool(m['capture_id']) and m['capture_id']!=c['delivery']['capture_id'],'AB7_SHORT_CAPTURE_ID')
    if c['delivery']['message_id'] is not None:
        rc.require(type(m['message_id']) is str and bool(m['message_id']) and m['message_id']!=c['delivery']['message_id']
                   and m['reply_to_message_id']==c['delivery']['message_id'] and m['linkage']=='PLATFORM_REPLY_V1','AB7_SHORT_REPLY_RELATION')
    else:
        rc.require(m['message_id'] is None and m['reply_to_message_id'] is None
                   and m['linkage']=='TRUSTED_DIRECT_CONTEXT_V1','AB7_SHORT_REPLY_RELATION')
    short_elapsed(c['t0'],m['captured'],mode)
    rc.require(timestamp(m['captured']['utc'])<=datetime.now(timezone.utc),'AB7_SHORT_FUTURE_CAPTURE')
    if mode=='ACTUAL':short_elapsed(generation(mode)[0]['active_card_clock'],m['captured'],mode)
    rc.require(record['system_claims']==short_system_claims(snapshot,c,m,mode),'AB7_SHORT_SYSTEM_BINDING')

def short_authorization(snapshot,record,mode):
    verify_short_record(record,snapshot,mode);c=record['card'];ds=short_declarations(record,mode)
    return dict(owner='たかし' if mode=='ACTUAL' else 'FIXTURE_OWNER',session=SESSION,mode=mode,
                approval_method=SHORT_METHOD,contract_sha=c['contract_sha'],source_identity=c['source_identity'],
                generation_id=c['generation_id'],snapshot_sha=rc.digest(snapshot),declarations_sha=rc.digest(ds),
                approval_received_at=record['owner_message']['captured']['utc'],chat_record=record,
                abandon_a1_remaining_work=True,authorize_issuance=True)

def verify_short_pin(approval,g,directory,mode):
    rc.require(g['owner_registration_approved'] is True,'AB7_CHAT_OWNER_NOT_AUTHORIZED')
    record=approval['chat_record'];card=record['card']
    rc.require(g['signature_method']==SHORT_METHOD and g['resolution_id']==card['resolution_id']
               and g['active_card_id']==card['card_id'],'AB7_SHORT_REGISTERED_CARD')
    short_elapsed(card['t0'],g['active_card_clock'],mode)
    short_elapsed(g['active_card_clock'],record['owner_message']['captured'],mode)
    files=[('chat_approval_sha','owner_chat_approval.json'),('short_message_sha','owner_short_message.txt'),
           ('system_claims_sha','owner_system_claims.json'),('active_card_sha','confirmation_cards/'+card['card_id']+'.json')]
    for key,name in files:
        rc.require(type(g[key]) is str and re.fullmatch('[0-9A-F]{64}',g[key])
                   and sha(plain(directory/name))==g[key],'AB7_SHORT_PIN_CHANGED')
    rc.require(rc.read(directory/'owner_chat_approval.json')==record
               and (directory/'owner_short_message.txt').read_bytes()==record['owner_message']['raw_text'].encode('utf-8')
               and rc.read(directory/'owner_system_claims.json')==record['system_claims']
               and rc.read(directory/'confirmation_cards'/ (card['card_id']+'.json'))==card
               and g['approved_authorization_sha']==rc.digest(approval)
               and g['approval_received_at']==approval['approval_received_at'],'AB7_SHORT_REGISTERED_APPROVAL')

def assemble_short(snapshot,declarations,approval,mode,issued_at,resolution_id,issuance_clock):
    g,directory=generation(mode)
    rc.require(approval.get('approval_method')==SHORT_METHOD,'AB7_SHORT_METHOD_REQUIRED')
    verify_short_record(approval['chat_record'],snapshot,mode)
    if mode=='ACTUAL':verify_short_pin(approval,g,directory,mode)
    else:
        rc.require(SHORT_FIXTURE_REGISTRATION is not None and plain(ROOT).is_relative_to(APP.parents[2]/'work'),'AB7_SHORT_FIXTURE_REGISTRATION')
        fg,fd=SHORT_FIXTURE_REGISTRATION
        verify_short_pin(approval,fg,fd,mode)
    record=approval['chat_record'];card=record['card']
    rc.require(rc.digest(snapshot)==rc.digest(original()),'AB7_SNAPSHOT_CHANGED')
    rc.require(resolution_id==card['resolution_id'] and (mode!='ACTUAL' or resolution_id==g['resolution_id']),'AB7_ONE_APPROVED_RESOLUTION')
    rc.require(declarations==short_declarations(record,mode) and approval==short_authorization(snapshot,record,mode),'AB7_SHORT_AUTHORIZATION')
    rc.require(issuance_clock is not None and issued_at==issuance_clock['utc'],'AB7_T0_ISSUANCE_CLOCK')
    short_elapsed(card['t0'],issuance_clock,mode)
    short_elapsed(record['owner_message']['captured'],issuance_clock,mode)
    rc.require(timestamp(issued_at)<=datetime.now(timezone.utc),'AB7_FUTURE_ISSUANCE')
    return dict(snapshot,schema=SCHEMA,authority=AUTHORITY,mode=mode,generation_id=g['generation_id'],
                source_identity=g['source_identity'],contract_sha=g['contract_sha'],declarations=declarations,
                authorization=approval,issued_at=issued_at,issuance_clock=issuance_clock,resolution_id=resolution_id,
                logical_obligation='RESOLVED_FOR_NEW_ONLY',production_operations_by_codex=0)

SHORT_FIXTURE_CLOCK = None
SHORT_FIXTURE_REGISTRATION = None

def probe_short_clock(mode,fixture_point=None):
    if mode=='OFFLINE_FIXTURE':
        rc.require(type(fixture_point) is dict,'AB7_SHORT_FIXTURE_PROBE')
        p=dict(fixture_point)
    else:
        rc.require(mode=='ACTUAL','AB7_CLOCK_MODE')
        import subprocess,time
        completed=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
            "(Get-CimInstance -ClassName Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')"],
            capture_output=True,text=True,timeout=10,creationflags=0x08000000)
        rc.require(completed.returncode==0,'AB7_T0_BOOT_QUERY')
        p=dict(utc=datetime.now(timezone.utc).isoformat(),monotonic_ns=time.monotonic_ns(),
               boot_id=completed.stdout.strip(),uncertainty_ms=1)
    p.update(source='UNVERIFIED_HOST_PROBE',verified=False)
    return p

def bind_short_t0(probe,before_reference,after_reference,mode):
    # System caller obtains independent UTC before and after probe_short_clock;
    # Owner supplies neither these timestamps nor the internal evidence JSON.
    provider='OFFLINE_FIXTURE' if mode=='OFFLINE_FIXTURE' else 'CLOCK_TOOL_UTC_V1'
    for ref in (before_reference,after_reference):
        rc.require(type(ref) is dict and set(ref)=={'provider','root_id','utc'}
                   and ref['provider']==provider and type(ref['root_id']) is str and bool(ref['root_id']),'AB7_T0_CAPTURE_REFERENCE')
    rc.require(before_reference['root_id']==after_reference['root_id'],'AB7_T0_CAPTURE_ROOT')
    if mode=='ACTUAL':
        g,directory=generation(mode)
        rc.require(type(g['capture_root_sha']) is str and sha(plain(directory/'capture_root.json'))==g['capture_root_sha'],'AB7_CAPTURE_NOT_CONFIGURED')
        root=rc.read(directory/'capture_root.json')
        rc.require(root.get('approved') is True and root.get('mode')=='ACTUAL' and root.get('session')==SESSION
                   and root.get('root_id')==before_reference['root_id'] and root.get('clock_source')=='INDEPENDENT_UTC_REFERENCE','AB7_CAPTURE_ROOT_SCOPE')
    rc.require(probe.get('source')=='UNVERIFIED_HOST_PROBE' and probe.get('verified') is False,'AB7_T0_UNVERIFIED_PROBE_REQUIRED')
    # clock__curr_time supplies seconds: preserve its full possible final second.
    from datetime import timedelta
    before=timestamp(before_reference['utc']);after=timestamp(after_reference['utc'])+timedelta(seconds=0 if mode=='OFFLINE_FIXTURE' else 1)
    point=timestamp(probe['utc'])
    rc.require(before<=point<=after and 0<=(after-before).total_seconds()<=2,'AB7_T0_REFERENCE_INTERVAL')
    import math
    uncertainty=math.ceil(max((point-before).total_seconds(),(after-point).total_seconds())*1000)
    p=dict(probe,source='OFFLINE_FIXTURE' if mode=='OFFLINE_FIXTURE' else 'TRUSTED_UTC_CAPTURE_V1',verified=True,uncertainty_ms=uncertainty)
    short_clock_valid(p,mode)
    ref=dict(source='OFFLINE_FIXTURE' if mode=='OFFLINE_FIXTURE' else 'INDEPENDENT_UTC_REFERENCE_V1',before_utc=before.isoformat(),
             after_utc=after.isoformat(),root_id=before_reference['root_id'],trusted_capture=True)
    return p,ref

def short_live_clock(mode,card):
    if mode=='OFFLINE_FIXTURE':
        rc.require(callable(SHORT_FIXTURE_CLOCK) and plain(ROOT).is_relative_to(APP.parents[2]/'work'),'AB7_SHORT_FIXTURE_CLOCK')
        p=SHORT_FIXTURE_CLOCK()
    else:
        p=probe_short_clock(mode);p.update(source='HOST_UTC_ANCHORED_V1',verified=True)
    short_elapsed(card['t0'],p,mode)
    return p

def chat_claims(snapshot, declarations, g, approved_at, mode):
    return dict(owner='たかし' if mode=='ACTUAL' else 'FIXTURE_OWNER', session=SESSION, mode=mode,
                method=CHAT_METHOD, contract_sha=g['contract_sha'], generation_id=g['generation_id'],
                resolution_id=g['resolution_id'] if mode=='ACTUAL' else 'OFFLINE_FIXTURE_ONLY',
                source_identity=g['source_identity'], policy_sha=g['chat_policy_sha'],
                snapshot_sha=rc.digest(snapshot), original_evidence_digest=snapshot['original_evidence_digest'],
                journal_binding_sha=snapshot['journal_binding_sha'], admission_binding_sha=snapshot['admission_binding_sha'],
                target_entries=snapshot['target_entries'], declarations=declarations, approved_at=approved_at,
                abandon_a1_remaining_work=True, authorize_one_supplemental_issuance=True)

def chat_text(claims):
    # Exact complete statement, prepared before the Owner observes current state.
    # A bare OK or a quoted partial statement cannot match these bytes.
    return '以下の対象・申告を確認し、今回1件の補足Closeout発行を明示承認します。\n'+canonical_bytes(claims).decode('ascii')

def fixture_chat_record(snapshot, declarations, g):
    rc.require(type(declarations) is dict and set(declarations)=={'A1','B1'},'AB7_COMPLETE_DECLARATIONS')
    t=declarations.get('B1',{}).get('observed_at')
    claims=chat_claims(snapshot,declarations,g,t,'OFFLINE_FIXTURE');raw=chat_text(claims)
    return dict(schema='AB7_OWNER_CHAT_APPROVAL_V1', claims=claims, raw_text=raw,
                raw_text_sha=hashlib.sha256(raw.encode('utf-8')).hexdigest().upper(),
                provenance=dict(role='user', channel='OFFLINE_FIXTURE', direct_owner_confirmed=True,
                                thread_id=None, message_id=None, platform_timestamp=None,
                                received_at=t, timestamp_source='OWNER_EXPLICIT_TIMESTAMP'))

def authorization(snapshot, declarations, mode):
    g,directory=generation(mode)
    record=rc.read(plain(directory/'owner_chat_approval.json')) if mode=='ACTUAL' else fixture_chat_record(snapshot,declarations,g)
    if mode=='ACTUAL':
        value=short_authorization(snapshot,record,mode)
        rc.require(declarations==short_declarations(record,mode),'AB7_SHORT_AUTHORIZATION')
        return value
    return dict(owner='たかし' if mode=='ACTUAL' else 'FIXTURE_OWNER',session=SESSION,mode=mode,
                generation_id=g['generation_id'],contract_sha=g['contract_sha'],source_identity=g['source_identity'],
                snapshot_sha=rc.digest(snapshot),declarations_sha=rc.digest(declarations),
                abandon_a1_remaining_work=True,authorize_issuance=True,
                signed_at=record['claims']['approved_at'], # Legacy envelope key means Chat approval time; no signature.
                signature_method=CHAT_METHOD,electronic_signature=rc.digest(record),chat_record=record)

def verify_chat_record(record,g,snapshot,declarations,mode):
    rc.require(type(record) is dict and set(record)=={'schema','claims','raw_text','raw_text_sha','provenance'},'AB7_CHAT_RECORD_SCHEMA')
    rc.require(record['schema']=='AB7_OWNER_CHAT_APPROVAL_V1','AB7_CHAT_RECORD_SCHEMA')
    claims=record['claims'];rc.require(type(claims) is dict,'AB7_CHAT_CLAIMS')
    expected=chat_claims(snapshot,declarations,g,claims.get('approved_at'),mode)
    rc.require(claims==expected,'AB7_CHAT_BINDING')
    raw=record['raw_text']
    rc.require(type(raw) is str and raw==chat_text(expected)
               and record['raw_text_sha']==hashlib.sha256(raw.encode('utf-8')).hexdigest().upper(),'AB7_CHAT_EXPLICIT_TEXT')
    pr=record['provenance']
    rc.require(type(pr) is dict and set(pr)=={'role','channel','direct_owner_confirmed','thread_id','message_id','platform_timestamp','received_at','timestamp_source'},'AB7_CHAT_PROVENANCE')
    rc.require(pr['role']=='user' and pr['channel']==('OWNER_DIRECT_CHAT' if mode=='ACTUAL' else 'OFFLINE_FIXTURE')
               and pr['direct_owner_confirmed'] is True,'AB7_CHAT_OWNER_SOURCE')
    for k in ('thread_id','message_id'):
        rc.require(pr[k] is None or (type(pr[k]) is str and bool(pr[k].strip())),'AB7_CHAT_IDENTIFIER')
    approved=timestamp(claims['approved_at']);received=timestamp(pr['received_at'])
    rc.require(approved<=received<=datetime.now(timezone.utc),'AB7_CHAT_TIMESTAMP')
    rc.require(pr['timestamp_source'] in ('PLATFORM_TIMESTAMP','OWNER_EXPLICIT_TIMESTAMP'),'AB7_CHAT_TIMESTAMP_SOURCE')
    if pr['platform_timestamp'] is not None:
        rc.require(timestamp(pr['platform_timestamp'])==approved,'AB7_CHAT_PLATFORM_TIMESTAMP')
    if pr['timestamp_source']=='PLATFORM_TIMESTAMP':
        rc.require(pr['platform_timestamp'] is not None,'AB7_CHAT_PLATFORM_TIMESTAMP')
    # Provenance is trusted only after external direct-Owner capture and fixed pin registration.
    # These fields and SHA are not cryptographic proof of account/person identity.

def verify_chat_pin(approval,g,directory):
    rc.require(g['owner_registration_approved'] is True,'AB7_CHAT_OWNER_NOT_AUTHORIZED')
    rc.require(g['signature_method']==CHAT_METHOD and g['resolution_id']==APPROVED_RESOLUTION_ID,'AB7_CHAT_GENERATION_SCOPE')
    p=plain(directory/'owner_chat_approval.json')
    rc.require(type(g['chat_approval_sha']) is str and re.fullmatch('[0-9A-F]{64}',g['chat_approval_sha']) is not None
               and sha(p)==g['chat_approval_sha'],'AB7_CHAT_PIN_CHANGED')
    rc.require(rc.read(p)==approval['chat_record'] and g['approved_authorization_sha']==rc.digest(approval)
               and g['approved_at']==approval['signed_at'],'AB7_CHAT_REGISTERED_APPROVAL')

def verify_owner_registration(approval,g,directory,mode,snapshot=None,declarations=None):
    if mode=='ACTUAL':
        rc.require(g['owner_registration_approved'] is True,'AB7_CHAT_OWNER_NOT_AUTHORIZED')
        verify_short_pin(approval,g,directory,mode)
        return
    verify_chat_record(approval['chat_record'],g,snapshot,declarations,mode)

def publication_freshness(declarations,now):
    rc.require(all(0<=(now-timestamp(d['observed_at'])).total_seconds()<=300 for d in declarations.values()),'AB7_PREPUBLICATION_FRESHNESS')

def assemble(snapshot, declarations, approval, mode, issued_at, resolution_id, issuance_clock=None):
    if approval.get('approval_method')==MANUAL_METHOD:
        return assemble_manual(snapshot,declarations,approval,mode,issued_at,resolution_id,issuance_clock)
    if approval.get('approval_method')==SHORT_METHOD:
        return assemble_short(snapshot,declarations,approval,mode,issued_at,resolution_id,issuance_clock)
    # Pure record validation: intentionally never reads issuance enable flags.
    g, directory = generation(mode)
    verify_owner_registration(approval,g,directory,mode,snapshot,declarations)
    rc.require(rc.digest(snapshot)==rc.digest(original()), 'AB7_SNAPSHOT_CHANGED')
    rc.require(type(resolution_id) is str and re.fullmatch('[0-9a-f]{32}', resolution_id), 'AB7_RESOLUTION_ID')
    rc.require(mode!='ACTUAL' or resolution_id==g['resolution_id'], 'AB7_ONE_APPROVED_RESOLUTION')
    rc.require(type(declarations) is dict and set(declarations)=={'A1','B1'}, 'AB7_COMPLETE_DECLARATIONS')
    rc.require(rc.digest(approval)==rc.digest(authorization(snapshot,declarations,mode)), 'AB7_AUTHORIZATION')
    end=timestamp(issued_at)
    rc.require(end<=datetime.now(timezone.utc), 'AB7_FUTURE_ISSUANCE')
    signed=timestamp(approval['signed_at'])
    rc.require(signed<=end, 'AB7_ISSUANCE_FRESHNESS_SIGNATURE')
    rc.require(timestamp(approval['chat_record']['provenance']['received_at'])<=end, 'AB7_ISSUANCE_FRESHNESS_CHAT_CAPTURE')
    for w in ('A','B'):
        d=declarations[w+'1']
        rc.require(type(d) is dict and rc.digest(d)==rc.digest(declaration(w,d.get('observed_at'),mode)), 'AB7_EXACT_DECLARATION')
        observed=timestamp(d['observed_at'])
        rc.require(observed<=signed and 0<=(end-observed).total_seconds()<=300, 'AB7_ISSUANCE_FRESHNESS')
    return dict(snapshot,schema=SCHEMA,authority=AUTHORITY,mode=mode,generation_id=g['generation_id'],
                source_identity=g['source_identity'],contract_sha=g['contract_sha'],declarations=declarations,
                authorization=approval,issued_at=issued_at,resolution_id=resolution_id,
                logical_obligation='RESOLVED_FOR_NEW_ONLY',production_operations_by_codex=0)

def envelope(payload):return dict(payload=payload,digest=rc.digest(payload))

def validate(value,snapshot,mode='ACTUAL'):
    rc.require(type(value) is dict and set(value)=={'payload','digest'}, 'AB7_RECEIPT_SCHEMA')
    p=value['payload']
    rc.require(type(p) is dict and value['digest']==rc.digest(p) and p.get('mode')==mode, 'AB7_RECEIPT_DIGEST_OR_MODE')
    expected=assemble(snapshot,p['declarations'],p['authorization'],mode,p['issued_at'],p['resolution_id'],p.get('issuance_clock'))
    rc.require(rc.digest(p)==rc.digest(expected), 'AB7_RECEIPT_CONTENT')
    return p

def receipt_valid(snapshot,mode='ACTUAL'):
    directory=plain(RECEIPT)
    if not directory.exists():return False
    before=inventory(directory)
    manual=rc.read(directory/'pending.json').get('payload',{}).get('authorization',{}).get('approval_method')==MANUAL_METHOD if (directory/'pending.json').is_file() else False
    required={'pending.json','seal.json'}|({'manual_publication_clock.json'} if manual else set())
    rc.require(set(before)==required, 'AB7_PARTIAL_OR_CONFLICT')
    if manual:
        p=rc.read(directory/'pending.json')['payload'];w=rc.read(directory/'manual_publication_clock.json')
        rc.require(set(w)=={'clock','seal_sha'} and w['seal_sha']==sha(directory/'seal.json'), 'AB7_MANUAL_PUBLICATION_WITNESS')
        manual_elapsed(p['authorization']['chat_record']['card']['t0'],w['clock'],mode)
        manual_elapsed(p['issuance_clock'],w['clock'],mode)
    rc.require(os.path.samefile(plain(directory/'pending.json'),plain(directory/'seal.json')), 'AB7_PUBLICATION_IDENTITY')
    rc.require(rc.read(directory/'pending.json')==rc.read(directory/'seal.json'), 'AB7_ALTERED_RECEIPT')
    validate(rc.read(directory/'seal.json'),snapshot,mode)
    rc.require(inventory(directory)==before, 'AB7_RECEIPT_CHANGED_DURING_READ')
    return True

def resolved(root,directory,mode='ACTUAL'):
    rc.require(plain(root)==STATE and plain(directory)==STATE/SESSION, 'AB7_SESSION_BINDING')
    return receipt_valid(original(directory),mode)

def protected_paths():
    ref = rc.read(APP.parent/'OPERATIONAL_MANIFEST.json')['manual_ab7feed_contract']
    c = contract(); path = plain(ref['path'])
    files = {path, *(plain(path.parent/name) for name in c['documents'])}
    gref = ref['issuance_generation']; gp = plain(gref['path'])
    files.add(gp)
    files.update(p for p in (gp.parent/'generation_source').rglob('*') if p.is_file())
    for name in ('owner_chat_approval.json','chat_policy.json','owner_short_message.txt','owner_system_claims.json','capture_root.json'):
        if (gp.parent/name).exists():files.add(plain(gp.parent/name))
    if 'manual_supplement' in ref:
        files.add(plain(ref['manual_supplement']['path']))
        source=ref.get('adoption_source')
        if source is not None:
            files.update((plain(source['path']),plain(source['text_path'])))
        for name in ('manual_adoption.json','manual_card.json','manual_approval.json','manual_system_claims.json','manual_owner_text.txt','manual_read_thread.txt'):
            if (gp.parent/name).exists():files.add(plain(gp.parent/name))
    cards=gp.parent/'confirmation_cards'
    if cards.exists():files.update(p for p in cards.rglob('*') if p.is_file())
    files.update(plain(path.parent/'baseline'/name) for name in c['authority_refs'])
    files.update(plain(ROOT/name) for name in c['authority_refs'] if name.endswith('.md'))
    files.update(p for p in (STATE/SESSION).rglob('*') if p.is_file())
    files.update(p for p in RECEIPT.rglob('*') if p.is_file())
    return files

def protected_inventory():
    # Includes directories and native logs; detects additions even before a seal.
    return frozenset(str(p.absolute()) for d in (STATE/SESSION, RECEIPT) for p in d.rglob('*')) | frozenset(
        str(d.absolute()) for d in (STATE/SESSION, RECEIPT) if d.exists())

def issue(declarations, approval, issued_at, resolution_id, mode='ACTUAL'):
    c = contract()
    ref = rc.read(APP.parent/'OPERATIONAL_MANIFEST.json')['manual_ab7feed_contract']
    if mode=='OFFLINE_FIXTURE':
        rc.require(FIXTURE_ISSUER_ENABLED is True, 'AB7_ISSUER_DISABLED')
        rc.require(plain(ROOT).is_relative_to(APP.parents[2]/'work'), 'AB7_FIXTURE_ROOT_REQUIRED')
    else:
        rc.require(mode=='ACTUAL' and ref['formal_issuance_enabled'] is True, 'AB7_CANDIDATE_FORMAL_ISSUER_DISABLED')
        generation(mode)
    # Reader validity is independent of the issuance enable state.
    g, _ = generation(mode)
    current_sources = rc.read(APP.parent/'OPERATIONAL_MANIFEST.json')['runtime_files']
    rc.require(current_sources == g['source_files'], 'AB7_ISSUER_SOURCE_GENERATION_CHANGED')
    rc.require(not (STATE/'execution.lock').exists(), 'AB7_ACTIVE_EXECUTION')
    if mode=='ACTUAL':
        # Actual issue time comes from this process, not an Owner-supplied old date.
        issued_at=datetime.now(timezone.utc).isoformat()
    clock=None
    if approval.get('approval_method')==MANUAL_METHOD:
        clock=manual_live_clock(mode);issued_at=clock['utc']
    if approval.get('approval_method')==SHORT_METHOD:
        clock=short_live_clock(mode,approval['chat_record']['card']);issued_at=clock['utc']
    snapshot=original();value=envelope(assemble(snapshot,declarations,approval,mode,issued_at,resolution_id,clock))
    if RECEIPT.exists():
        rc.require(receipt_valid(snapshot, mode) and rc.read(RECEIPT/'seal.json') == value, 'AB7_ISSUANCE_CONFLICT')
        return value
    # The unchanged operational lock excludes admission; the receipt directory
    # excludes another publication. Only our own lock may be removed afterward.
    lock = STATE/'execution.lock'
    lock_value = dict(session=SESSION, kind='AB7_OFFLINE_SUPPLEMENTAL', token=resolution_id)
    rc.publish(lock, lock_value)
    try:
        from frozen_inputs import FrozenInputs
        with FrozenInputs() as lease:
            lease.add(protected_paths() | {p for p in APP.parent.rglob('*') if p.is_file()})
            lease.require_open()
            plain(RECEIPT).mkdir()
            rc.publish(RECEIPT/'pending.json', value)
            rc.require(rc.digest(original()) == rc.digest(snapshot) and rc.read(lock) == lock_value, 'AB7_PREPUBLICATION_CHANGED')
            if approval.get('approval_method')==MANUAL_METHOD:
                manual_elapsed(approval['chat_record']['card']['t0'],manual_live_clock(mode),mode)
            elif approval.get('approval_method')==SHORT_METHOD:
                short_live_clock(mode,approval['chat_record']['card'])
            elif mode=='ACTUAL':
                now=datetime.now(timezone.utc)
                publication_freshness(declarations,now)
            os.link(RECEIPT/'pending.json', RECEIPT/'seal.json')
            if approval.get('approval_method')==MANUAL_METHOD:
                publication_clock=manual_live_clock(mode)
                manual_elapsed(approval['chat_record']['card']['t0'],publication_clock,mode)
                rc.publish(RECEIPT/'manual_publication_clock.json',dict(clock=publication_clock,seal_sha=sha(RECEIPT/'seal.json')))
            rc.require(receipt_valid(snapshot, mode), 'AB7_PUBLICATION_READBACK')
            return value
    finally:
        rc.require(rc.read(lock) == lock_value, 'AB7_PUBLICATION_LOCK_CHANGED')
        lock.unlink()


# AB7R-only proposed manual supplement. No Chat polling or automatic capture.
MANUAL_METHOD = 'OWNER_SUPERVISED_CODEX_MONOTONIC_V1'
MANUAL_THREAD = '01a13a8b-15b4-7531-aab3-3e77ee6ecf9c'
MANUAL_FIXTURE_REGISTRATION = None
MANUAL_FIXTURE_CLOCK = None


def manual_policy():
    ref = rc.read(APP.parent/'OPERATIONAL_MANIFEST.json')['manual_ab7feed_contract']['manual_supplement']
    p = plain(ref['path'])
    rc.require(sha(p) == ref['sha256'], 'AB7_MANUAL_POLICY_CHANGED')
    v = rc.read(p)
    rc.require(v == dict(schema='AB7_MANUAL_SUPPLEMENT_PROPOSAL_V1', session=SESSION,
        parent_contract_sha=contract_sha(), method=MANUAL_METHOD, thread_id=MANUAL_THREAD,
        identity_basis='OWNER_ADOPTED_SAME_CODEX_CONTEXT_NOT_ACCOUNT_AUTHENTICATION',
        clock_basis='SAME_BOOT_MONOTONIC_300_SECONDS', utc_trust='UNVERIFIED_AUDIT_ONLY',
        max_age_seconds=300, requires_separate_owner_adoption=True,
        generation_id='AB7-IR-SEPARATION-20261015-01', resolution_id=APPROVED_RESOLUTION_ID,
        historical_closed=False, scope='NEW_ONLY', normal_operation_authorized=False), 'AB7_MANUAL_POLICY_SCOPE')
    return v, ref['sha256']


def contract_sha():
    return sha(plain(rc.read(APP.parent/'OPERATIONAL_MANIFEST.json')['manual_ab7feed_contract']['path']))


def manual_clock_valid(p, mode):
    rc.require(type(p) is dict and set(p) == {'utc','monotonic_ns','boot_id','uncertainty_ns','source','utc_trust'}, 'AB7_MANUAL_CLOCK_SCHEMA')
    timestamp(p['utc'])
    rc.require(type(p['monotonic_ns']) is int and p['monotonic_ns'] >= 0
        and type(p['uncertainty_ns']) is int and 0 <= p['uncertainty_ns'] <= 1_000_000_000
        and type(p['boot_id']) is str and bool(p['boot_id'])
        and p['source'] == ('OFFLINE_FIXTURE' if mode == 'OFFLINE_FIXTURE' else 'HOST_MONOTONIC_SUPERVISED_V1')
        and p['utc_trust'] == 'UNVERIFIED_AUDIT_ONLY', 'AB7_MANUAL_CLOCK_SOURCE')


def manual_elapsed(start, end, mode):
    manual_clock_valid(start, mode); manual_clock_valid(end, mode)
    rc.require(start['boot_id'] == end['boot_id'], 'AB7_MANUAL_BOOT_CHANGED')
    delta = end['monotonic_ns'] - start['monotonic_ns']
    error = start['uncertainty_ns'] + end['uncertainty_ns']
    wall = (timestamp(end['utc']) - timestamp(start['utc'])).total_seconds()
    rc.require(delta >= 0 and wall >= 0 and abs(wall-delta/1e9) <= error/1e9+0.001, 'AB7_MANUAL_CLOCK_DISCONTINUITY')
    rc.require(delta+error <= 300_000_000_000, 'AB7_MANUAL_EXPIRED')
    return (delta+error)/1e9


def manual_live_clock(mode):
    if mode == 'OFFLINE_FIXTURE':
        rc.require(callable(MANUAL_FIXTURE_CLOCK) and plain(ROOT).is_relative_to(APP.parents[2]/'work'), 'AB7_MANUAL_FIXTURE_CLOCK')
        p = MANUAL_FIXTURE_CLOCK()
    else:
        rc.require(mode == 'ACTUAL', 'AB7_MANUAL_MODE')
        import time
        before = time.monotonic_ns()
        probe = probe_short_clock(mode)  # read-only host/boot query; no trusted UTC assertion
        after = time.monotonic_ns()
        p = dict(utc=probe['utc'], monotonic_ns=probe['monotonic_ns'], boot_id=probe['boot_id'],
            uncertainty_ns=after-before, source='HOST_MONOTONIC_SUPERVISED_V1', utc_trust='UNVERIFIED_AUDIT_ONLY')
    manual_clock_valid(p, mode)
    return p


def manual_card(snapshot, card_id, t0, mode):
    g, _ = generation(mode); _, policy_sha = manual_policy()
    rc.require(type(card_id) is str and re.fullmatch('[0-9a-f]{32}', card_id), 'AB7_MANUAL_CARD_ID')
    manual_clock_valid(t0, mode)
    return dict(schema='AB7_MANUAL_CARD_V1', mode=mode, session=SESSION, card_id=card_id,
        thread_id=MANUAL_THREAD, contract_sha=g['contract_sha'], supplement_sha=policy_sha,
        generation_id=g['generation_id'], resolution_id=APPROVED_RESOLUTION_ID,
        source_identity=g['source_identity'], snapshot=snapshot, t0=t0, expected_reply=SHORT_TEXT,
        text=short_card_text(snapshot['target_entries'])+'\n確認カード '+card_id,
        abandon_a1_remaining_work=True, authorize_one_issuance=True, normal_operation_authorized=False)


def manual_transcript(raw, card):
    # Raw read_thread response is retained separately. IDs are never omitted or fabricated.
    import json
    rc.require(type(raw) is str, 'AB7_MANUAL_TRANSCRIPT')
    response = json.loads(raw)
    rc.require(response['schemaVersion'] == 1 and response['thread']['id'] == MANUAL_THREAD
        and response['thread']['kind'] == 'codex' and response['thread']['hostId'] == 'local'
        and response['page']['order'] == 'newest_first', 'AB7_MANUAL_TRANSCRIPT_SOURCE')
    items = [item for turn in reversed(response['turns']) for item in turn['items']]
    messages = [i for i in items if i['type'] in ('agentMessage','userMessage')]
    ids = [i['id'] for i in messages]
    rc.require(all(type(i) is str and bool(i) for i in ids) and len(ids) == len(set(ids)), 'AB7_MANUAL_DUPLICATE_ID')
    cards = [i for i, item in enumerate(messages) if item['type'] == 'agentMessage' and item.get('text') == card['text']]
    rc.require(len(cards) == 1, 'AB7_MANUAL_CARD_CAPTURE')
    index = cards[0]
    # Only the immediately following chat message may approve; tool/reasoning items are not user speech.
    rc.require(index+1 < len(messages) and not any(i['type']=='userMessage' for i in messages[index+2:]), 'AB7_MANUAL_CONTEXT_ORDER')
    rc.require(not any('確認カード ' in i.get('text','') for i in messages[index+2:]), 'AB7_MANUAL_CONTEXT_ORDER')
    user = messages[index+1]
    content = user.get('content')
    rc.require(user['type'] == 'userMessage' and (content == [{'type':'text','text':SHORT_TEXT}]
        or content == [{'type':'text','text':SHORT_TEXT+'\n'}]), 'AB7_MANUAL_EXPLICIT_USER_TEXT')
    return dict(card_message_id=messages[index]['id'], owner_message_id=user['id'],
        raw_text=content[0]['text'], platform_reply_to=None, platform_owner_identity=None,
        binding_basis='SUPERVISED_ORDERED_CONTEXT_NOT_PLATFORM_REPLY')


def manual_record(snapshot, card, raw_response, captured, mode):
    parsed = manual_transcript(raw_response, card)
    manual_elapsed(card['t0'], captured, mode)
    return dict(schema='AB7_MANUAL_APPROVAL_V1', mode=mode, card=card,
        raw_response=raw_response, raw_response_sha=hashlib.sha256(raw_response.encode('utf-8')).hexdigest().upper(),
        owner_message=parsed, captured=captured,
        system_claims=dict(generated_by='SYSTEM_NOT_OWNER_ORIGINAL', card_sha=rc.digest(card),
            owner_text_sha=hashlib.sha256(parsed['raw_text'].encode('utf-8')).hexdigest().upper(),
            observation_time='UNKNOWN_NOT_ASSIGNED', observation_window='AFTER_CARD_BEFORE_CAPTURE',
            owner_basis='OWNER_ADOPTED_SAME_CODEX_CONTEXT_NOT_ACCOUNT_AUTHENTICATION'))


def verify_manual_record(record, snapshot, mode):
    c = record['card']
    rc.require(c == manual_card(snapshot, c['card_id'], c['t0'], mode), 'AB7_MANUAL_CARD_BINDING')
    expected = manual_record(snapshot, c, record['raw_response'], record['captured'], mode)
    rc.require(record == expected, 'AB7_MANUAL_RECORD_CHANGED')


def manual_declarations(record, mode):
    # Reuse truthful UNKNOWN observation time semantics; never claim account authentication.
    shim = dict(card=dict(record['card'], target_entries=record['card']['snapshot']['target_entries']),
        owner_message=dict(captured=record['captured']))
    ds = short_declarations(shim, mode)
    for d in ds.values():
        d.pop('identity_verified')
        d['identity_basis'] = 'OWNER_ADOPTED_SAME_CODEX_CONTEXT_NOT_ACCOUNT_AUTHENTICATION'
    return ds


def manual_authorization(snapshot, record, mode):
    verify_manual_record(record, snapshot, mode)
    c = record['card']
    return dict(approval_method=MANUAL_METHOD, owner='たかし' if mode == 'ACTUAL' else 'FIXTURE_OWNER',
        session=SESSION, mode=mode, contract_sha=c['contract_sha'], supplement_sha=c['supplement_sha'],
        source_identity=c['source_identity'], generation_id=c['generation_id'],
        snapshot_sha=rc.digest(snapshot), declarations_sha=rc.digest(manual_declarations(record,mode)),
        approval_received_at=record['captured']['utc'], chat_record=record,
        abandon_a1_remaining_work=True, authorize_issuance=True)


def verify_manual_pin(approval, g, directory, mode):
    _, policy_sha = manual_policy()
    reg = g.get('manual_registration')
    rc.require(g.get('manual_policy_adopted') is True and type(reg) is dict, 'AB7_MANUAL_ADOPTION_REQUIRED')
    a = approval; r = a['chat_record']; c = r['card']
    expected_adoption = dict(schema='AB7_MANUAL_ADOPTION_V1', mode=mode, session=SESSION,
        supplement_sha=policy_sha, parent_contract_sha=c['contract_sha'], source_identity=c['source_identity'],
        thread_id=MANUAL_THREAD, generation_id=c['generation_id'], resolution_id=APPROVED_RESOLUTION_ID,
        owner_accepts_context_trust=True, owner_accepts_monotonic_duration=True,
        formal_issuance_approved=False, normal_operation_approved=False)
    adoption = rc.read(plain(directory/'manual_adoption.json'))
    verify_existing_manual_adoption(adoption, expected_adoption)
    files = {'manual_adoption.json':adoption, 'manual_card.json':c, 'manual_approval.json':r,
        'manual_system_claims.json':r['system_claims']}
    pins = reg['files']
    rc.require(set(pins) == set(files) | {'manual_owner_text.txt','manual_read_thread.txt'}, 'AB7_MANUAL_PIN_INVENTORY')
    for name, value in files.items():
        rc.require(sha(plain(directory/name)) == pins[name] and rc.read(directory/name) == value, 'AB7_MANUAL_PIN_CHANGED')
    for name, value in [('manual_owner_text.txt',r['owner_message']['raw_text']),('manual_read_thread.txt',r['raw_response'])]:
        rc.require(sha(plain(directory/name)) == pins[name] and (directory/name).read_bytes() == value.encode('utf-8'), 'AB7_MANUAL_PIN_CHANGED')
    rc.require(reg['authorization_sha'] == rc.digest(a) and reg['card_id'] == c['card_id'], 'AB7_MANUAL_REGISTERED_APPROVAL')
    manual_elapsed(c['t0'], reg['card_registered_clock'], mode)
    manual_elapsed(reg['card_registered_clock'], r['captured'], mode)


def assemble_manual(snapshot, declarations, approval, mode, issued_at, resolution_id, issuance_clock):
    g, directory = generation(mode)
    rc.require(approval.get('approval_method') == MANUAL_METHOD, 'AB7_MANUAL_METHOD')
    r = approval['chat_record']; verify_manual_record(r, snapshot, mode)
    if mode == 'ACTUAL':
        verify_manual_pin(approval, g, directory, mode)
    else:
        rc.require(MANUAL_FIXTURE_REGISTRATION is not None and plain(ROOT).is_relative_to(APP.parents[2]/'work'), 'AB7_MANUAL_FIXTURE_ROOT')
        fg, fd = MANUAL_FIXTURE_REGISTRATION; verify_manual_pin(approval, fg, fd, mode)
    rc.require(snapshot == original() and declarations == manual_declarations(r,mode)
        and approval == manual_authorization(snapshot,r,mode), 'AB7_MANUAL_AUTHORIZATION')
    rc.require(resolution_id == APPROVED_RESOLUTION_ID == r['card']['resolution_id'], 'AB7_MANUAL_RESOLUTION')
    rc.require(issuance_clock is not None and issuance_clock['utc'] == issued_at, 'AB7_MANUAL_ISSUANCE_CLOCK')
    manual_elapsed(r['card']['t0'], issuance_clock, mode)
    manual_elapsed(r['captured'], issuance_clock, mode)
    return dict(snapshot, schema=SCHEMA, authority=AUTHORITY, mode=mode, generation_id=g['generation_id'],
        source_identity=g['source_identity'], contract_sha=g['contract_sha'], declarations=declarations,
        authorization=approval, issued_at=issued_at, issuance_clock=issuance_clock,
        resolution_id=resolution_id, logical_obligation='RESOLVED_FOR_NEW_ONLY', production_operations_by_codex=0)


def manual_supervised_issue(declarations, approval, controls, mode='ACTUAL'):
    # controls is the explicit local operator's enable/disable/readback adapter, never a Chat watcher.
    rc.require(approval.get('approval_method') == MANUAL_METHOD, 'AB7_MANUAL_METHOD')
    if mode == 'ACTUAL':
        g, directory = generation(mode)
        verify_manual_pin(approval,g,directory,mode)  # adoption must precede any enabling
    status = None
    try:
        rc.require(controls('read') is False, 'AB7_MANUAL_ISSUER_NOT_DISABLED')
        controls('enable'); rc.require(controls('read') is True, 'AB7_MANUAL_ENABLE_FAILED')
        status = issue(declarations,approval,None,APPROVED_RESOLUTION_ID,mode)
    finally:
        controls('disable')
        rc.require(controls('read') is False, 'AB7_MANUAL_DISABLE_FAILED')
    rc.require(receipt_valid(original(),mode), 'AB7_MANUAL_READER_FAILED')
    return status


# Exact already-received adoption; source chat differs from the issuance chat.
ADOPTION_SOURCE_THREAD = '01a13da6-3893-76c2-a30e-7a5dca4376e5'
ADOPTION_SOURCE_MESSAGE = '01a13da6-3ca6-7de3-9509-1574889cfe9a'
ADOPTION_RAW_SHA = '3B057D7BA029DEE328E060E85DB54AA920E933C6B545CDC09A56D6732B179891'
ADOPTION_CAPTURE_SHA = '7EDB481063114C62AA40B37F9D94D96B6843A2CF6354ABD1865B5EEB0ADB65F7'
ADOPTION_PARENT_CANDIDATE = 'E37ECF61489BE2BEF9CB84CA20BAFA918C55D228C8F415A9DB21A6F94AADF143'
ADOPTION_PARENT_SOURCE = '76651399B69F9F65031495F08B5C7211124DD4A5B9E165B6BAB7B83B0F8EBD12'


def manual_adoption_source():
    ref = rc.read(APP.parent/'OPERATIONAL_MANIFEST.json')['manual_ab7feed_contract']['adoption_source']
    rc.require(type(ref) is dict and set(ref) == {'path','sha256','text_path','text_sha256','approved_candidate_sha','approved_source_identity'}, 'AB7_MANUAL_ADOPTION_SOURCE')
    rc.require(ref['sha256'] == ADOPTION_CAPTURE_SHA and ref['text_sha256'] == ADOPTION_RAW_SHA
        and ref['approved_candidate_sha'] == ADOPTION_PARENT_CANDIDATE
        and ref['approved_source_identity'] == ADOPTION_PARENT_SOURCE, 'AB7_MANUAL_ADOPTION_SOURCE')
    p = plain(ref['path']); text_path = plain(ref['text_path'])
    rc.require(sha(p) == ADOPTION_CAPTURE_SHA and sha(text_path) == ADOPTION_RAW_SHA, 'AB7_MANUAL_ADOPTION_SOURCE_CHANGED')
    captured = rc.read(p)
    rc.require(type(captured) is dict and set(captured) == {'schema','source_tool','source_thread_id','source_kind','source_host','user_message'}
        and captured['schema'] == 'AB7_EXISTING_ADOPTION_CAPTURE_V1'
        and captured['source_tool'] == 'mcp__codex_app__read_thread'
        and captured['source_thread_id'] == ADOPTION_SOURCE_THREAD
        and captured['source_kind'] == 'codex' and captured['source_host'] == 'local', 'AB7_MANUAL_ADOPTION_SOURCE')
    item = captured['user_message']
    rc.require(type(item) is dict and set(item) == {'type','id','content'} and item['type'] == 'userMessage'
        and item['id'] == ADOPTION_SOURCE_MESSAGE and type(item['content']) is list and len(item['content']) == 1
        and set(item['content'][0]) == {'type','text'} and item['content'][0]['type'] == 'text', 'AB7_MANUAL_ADOPTION_SOURCE')
    raw = item['content'][0]['text']
    rc.require(type(raw) is str and raw.encode('utf-8') == text_path.read_bytes()
        and hashlib.sha256(raw.encode('utf-8')).hexdigest().upper() == ADOPTION_RAW_SHA
        and raw.startswith('CLA-1 AB7R Incident Recoveryについて、今回限定の簡素化契約差分およびCandidateの限定Promotionを承認します。')
        and SESSION in raw and ADOPTION_PARENT_CANDIDATE in raw, 'AB7_MANUAL_ADOPTION_INTENT')
    owner_message = dict(role='user', thread_id=ADOPTION_SOURCE_THREAD, message_id=ADOPTION_SOURCE_MESSAGE,
        raw_text=raw, raw_text_sha=ADOPTION_RAW_SHA, source_tool=captured['source_tool'],
        capture_sha=ADOPTION_CAPTURE_SHA)
    # This approval adopted the existing policy/Q8 package only; never assert it approved later code or issuance.
    approved_parent = dict(candidate_sha=ADOPTION_PARENT_CANDIDATE, source_identity=ADOPTION_PARENT_SOURCE,
        supplement_sha=manual_policy()[1], scope='EXISTING_POLICY_ADOPTION_NOT_REMEDIATION_PROMOTION_OR_ISSUANCE')
    return owner_message, approved_parent


def verify_existing_manual_adoption(adoption, expected_claims):
    owner_message, approved_parent = manual_adoption_source()
    # claims are system bindings to the currently registered card/source, not a rewrite of Owner's text.
    rc.require(adoption == dict(claims=expected_claims, owner_message=owner_message, approved_parent=approved_parent),
        'AB7_MANUAL_ADOPTION_BINDING')
