"""3851-only immutable, separate evidence. Never writes a reservation Journal."""
import hashlib
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
import retry_continuation as rc
from runtime_config import digest as binding_digest

SESSION = '3851e654c248413cbaf8b2e1dec17099'
SCHEMA = '3851_ZERO_SUBMIT_V1'
REQUESTS = tuple(w+str(i) for w in 'AB' for i in range(1,8))
APP = Path(__file__).resolve().parent
APPROVAL = '3851_INQUIRY_ONLY_NO_MANUAL_CHANGE_NO_RESERVATION_AUTHORITY'
OWNER_EVENTS = [dict(type='OWNER_DECLARED',event='A7_MANUAL_RESERVATION',incident_result_changed=False),
                dict(type='OWNER_DECLARED',event='A_AND_B_20261011_MANUAL_RESERVATION',in_scope=False),
                dict(type='OWNER_DECLARED',event='CURRENT_COUNTS_A9_B9',machine_evidence=False)]
CHECKS = ('page_verified','identity_verified','target_verified','render_verified','marker_exact','marker_associated','fresh')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()

def plain(path):
    path=Path(path).absolute()
    rc.require(path.resolve()==path, 'RESOLUTION_PATH_REDIRECTED')
    return path

def inventory(directory):
    root=plain(directory)
    return {p.relative_to(root).as_posix():sha(plain(p)) for p in sorted(root.rglob('*')) if p.is_file()}

def contract():
    manifest=rc.read(APP.parent/'OPERATIONAL_MANIFEST.json')
    c=manifest['resolution_contract']
    rc.require(c['session']==SESSION and c['schema']==SCHEMA, 'RESOLUTION_CONTRACT')
    for name,expected in manifest['runtime_files'].items():
        rc.require(sha(plain(APP.parent/name))==expected, 'RESOLUTION_SOURCE_CHANGED')
    rc.require({p.relative_to(APP.parent).as_posix() for p in APP.parent.rglob('*') if p.is_file()}
        ==set(manifest['runtime_files'])|{'OPERATIONAL_MANIFEST.json'}, 'RESOLUTION_SOURCE_INVENTORY')
    rc.require(sha(plain(c['authority_path']))==c['authority_sha'], 'RESOLUTION_AUTHORITY_CHANGED')
    return c

def original(directory):
    """Validate pinned bytes AND original reducer/chain; no state conversions."""
    directory=plain(directory)
    rc.require(directory.name==SESSION, 'RESOLUTION_SESSION')
    c=contract(); files=inventory(directory)
    rc.require(files==c['original_files'], 'RESOLUTION_ORIGINAL_CHANGED')
    a=rc.read(directory/'admission.json'); binding=a['binding']
    from admission_control import entries
    bound=entries(binding)
    rc.require(a['session']==SESSION and a['schema']==rc.SCHEMA and a['entries']==bound, 'RESOLUTION_ADMISSION')
    rc.require(rc.read(directory/'consumed.json')==dict(session=SESSION,binding_sha=binding_digest(binding)), 'RESOLUTION_CONSUMED')
    historical=[]
    for worker in 'AB':
        rows=[e for e in bound if e['worker']==worker]
        for e,key in zip(rows,binding['request_keys'][worker]):
            rc.require(e['date']==key[0], 'RESOLUTION_TARGET_BINDING')
            historical.append(dict(e,canonical_lesson=key[1]))
    rc.require(tuple(e['request_id'] for e in historical)==REQUESTS, 'RESOLUTION_REQUEST_SET')
    models={}; tails={}; refs={}
    for worker in 'AB':
        rows=[e for e in historical if e['worker']==worker]
        j=rc.Journal(directory/'request_attempts'/worker,worker,rows,binding,SESSION)
        events=j.events(); model,_,registered=rc.reduce_events(events,rows)
        rc.require(registered and events, 'RESOLUTION_CHAIN')
        models.update(model); tails[worker]=rc.digest(events[-1])
        for rid,row in model.items():
            attempts=row['attempts']; last=attempts[-1]
            submits=sum(x.get('submission_attempted') is True for x in attempts)
            if rid in REQUESTS[:6]:
                rc.require(row['result']=='AWAITING_RECONCILIATION' and len(attempts)==1 and submits==1
                    and last['state']=='SUBMIT_INTENT' and last['submit_intent_durable'] is True
                    and last['provisional_evidence_state']=='PROVISIONAL_ACCEPTED'
                    and last['complete_evidence']['positive'] is True and last['reconciliation_pending'] is True,
                    'RESOLUTION_A_PROVISIONAL_REQUIRED')
            elif rid=='A7':
                rc.require(len(attempts)==1 and submits==0 and rc.safe(last), 'RESOLUTION_A7_PRE_SUBMIT_REQUIRED')
            else:
                rc.require(row['result']=='CONFIRMED' and submits==1 and last['state']=='CONFIRMED'
                    and last['confirmation_evidence']['positive'] is True, 'RESOLUTION_B_CONFIRMED_REQUIRED')
            refs[rid]=dict(worker=worker,entry_sha=rc.digest(row['entry']),attempts_sha=rc.digest(attempts),
                attempt_id=last['attempt_id'],tail_sha=tails[worker],historical_result=row['result'],submits=submits)
    rc.require(rc.read(directory/'worker-A.json')==dict(status='ABORT',exception_type='ValueError')
        and rc.read(directory/'worker-B.json')==dict(status='COMPLETED'), 'RESOLUTION_WORKER_HISTORY')
    return dict(binding_sha=binding_digest(binding),original_sha=rc.digest(files),tails=tails,refs=refs,
                entries=historical,binding=binding)

def namespace(state_root):
    return plain(Path(state_root).parents[2]/'resolution_evidence'/'3851')

def utc():
    return datetime.now(timezone.utc).isoformat()

def timestamp(value):
    rc.require(type(value) is str, 'RESOLUTION_TIMESTAMP')
    t=datetime.fromisoformat(value)
    rc.require(t.tzinfo is not None and t.utcoffset().total_seconds()==0, 'RESOLUTION_UTC_REQUIRED')
    return t

def envelope(rid,kind,payload):
    rc.require(re.fullmatch('[0-9a-f]{32}',rid) is not None, 'RESOLUTION_ID')
    value=dict(resolution_schema=SCHEMA,resolution_id=rid,original_session=SESSION,kind=kind,payload=payload)
    return dict(value,evidence_hash=rc.digest(value))

def read_record(path,rid,kind):
    value=rc.read(plain(path))
    rc.require(set(value)=={'resolution_schema','resolution_id','original_session','kind','payload','evidence_hash'}, 'RESOLUTION_SCHEMA')
    rc.require(value==envelope(rid,kind,value['payload']), 'RESOLUTION_CHECKSUM_OR_BINDING')
    return value['payload']

def write_record(path,rid,kind,payload):
    value=envelope(rid,kind,payload)
    rc.publish(plain(path),value)  # exclusive creation, flush, fsync, duplicate-key readback
    rc.require(read_record(path,rid,kind)==payload, 'RESOLUTION_READBACK')

def admission_payload(snapshot,approval):
    c=contract()
    rc.require(approval==dict(semantic=APPROVAL,session=SESSION,binding_sha=snapshot['binding_sha']), 'RESOLUTION_OWNER_APPROVAL')
    return dict(binding_sha=snapshot['binding_sha'],original_sha=snapshot['original_sha'],tails=snapshot['tails'],
        source_sha=c.get('issuer_manifest_sha',sha(APP.parent/'OPERATIONAL_MANIFEST.json')),authority_sha=c['authority_sha'],
        owner_approval=approval,started_at=utc(),deadline_seconds=300)

def observation(snapshot,request_id,proof,elapsed):
    rc.require(request_id in REQUESTS[:7] and all(proof.get(k) is True for k in CHECKS), 'RESOLUTION_INQUIRY_REQUIRED')
    entry=next(e for e in snapshot['entries'] if e['request_id']==request_id)
    rc.require(proof.get('target')==dict(date=entry['date'],lesson=entry['lesson'])
        and proof.get('marker_text')=='「予約中」' and proof.get('marker_count')==1
        and proof.get('remaining_ambiguity',False) is False, 'RESOLUTION_INQUIRY_TARGET_OR_MARKER')
    rc.require(type(elapsed) in (int,float) and 0<=elapsed<300, 'RESOLUTION_DEADLINE')
    rc.require(re.fullmatch('[0-9a-f]{32}',proof['generation']) is not None, 'RESOLUTION_GENERATION')
    timestamp(proof['observed_at'])
    # Exact whitelist: never serialize raw, click_binding, HTML, URL, exception, identity values.
    return dict(request_id=request_id,worker='A',reference=snapshot['refs'][request_id],
        checks={k:True for k in CHECKS},generation=proof['generation'],observed_at=proof['observed_at'],
        elapsed_seconds=elapsed,remaining_ambiguity=False,observation_type='INQUIRY_RESERVED',
        resolution_result='CURRENT_STATE_RESOLUTION' if request_id=='A7' else 'ALREADY_RESERVED',
        origin='INQUIRY_RESERVED',historical_changed=False)

def validate_records(directory,snapshot):
    """Only this generation; no searching other partial generations for missing records."""
    directory=plain(directory); rid=directory.name
    a=read_record(directory/'admission.json',rid,'ADMISSION')
    expected=admission_payload(snapshot,a.get('owner_approval'))
    expected['started_at']=a.get('started_at')
    rc.require(a==expected, 'RESOLUTION_ADMISSION_BINDING')
    started=timestamp(a['started_at'])
    rc.require(read_record(directory/'owner-events.json',rid,'OWNER_EVENTS')==OWNER_EVENTS, 'RESOLUTION_OWNER_EVENT_SCHEMA')
    observations={}; generations=set(); prior=started; elapsed=-1
    for key in REQUESTS[:7]:
        v=read_record(directory/(key+'.json'),rid,'OBSERVATION')
        entry=next(e for e in snapshot['entries'] if e['request_id']==key)
        proof=dict(v['checks'],generation=v['generation'],observed_at=v['observed_at'],remaining_ambiguity=v['remaining_ambiguity'],
            target=dict(date=entry['date'],lesson=entry['lesson']),marker_text='「予約中」',marker_count=1)
        rc.require(v==observation(snapshot,key,proof,v['elapsed_seconds']), 'RESOLUTION_OBSERVATION_BINDING')
        t=timestamp(v['observed_at'])
        rc.require(prior<=t and 0<=(t-started).total_seconds()<300 and elapsed<=v['elapsed_seconds']<300
            and v['generation'] not in generations, 'RESOLUTION_STALE_OR_REUSED')
        generations.add(v['generation']); prior=t; elapsed=v['elapsed_seconds']
        observations[key]=sha(directory/(key+'.json'))
    return a,observations,prior,elapsed

def seal_payload(directory,snapshot,elapsed):
    a,observations,last,last_elapsed=validate_records(directory,snapshot)
    sealed=utc(); t=timestamp(sealed)
    rc.require(last<=t and (t-timestamp(a['started_at'])).total_seconds()<300
        and last_elapsed<=elapsed<300, 'RESOLUTION_DEADLINE')
    return dict(logical_obligation='RESOLVED',historical_closed=False,original_sha=snapshot['original_sha'],
        binding_sha=snapshot['binding_sha'],admission_sha=sha(directory/'admission.json'),
        owner_events_sha=sha(directory/'owner-events.json'),observations=observations,
        historical_confirmed={key:snapshot['refs'][key] for key in REQUESTS[7:]},
        sealed_at=sealed,elapsed_seconds=elapsed)

def validate_seal(directory,snapshot):
    directory=plain(directory)
    required={'admission.json','owner-events.json','seal.json','.seal-ready.json'}|{k+'.json' for k in REQUESTS[:7]}
    rc.require({p.name for p in directory.iterdir()}==required, 'RESOLUTION_PARTIAL_OR_EXTRA')
    rc.require(all(p.is_file() for p in directory.iterdir()), 'RESOLUTION_FILE_TYPE')
    a,observations,last,elapsed=validate_records(directory,snapshot)
    v=read_record(directory/'seal.json',directory.name,'SEAL')
    rc.require(read_record(directory/'.seal-ready.json',directory.name,'SEAL')==v
        and os.path.samefile(directory/'.seal-ready.json',directory/'seal.json'), 'RESOLUTION_PUBLICATION_REQUIRED')
    expected=dict(logical_obligation='RESOLVED',historical_closed=False,original_sha=snapshot['original_sha'],
        binding_sha=snapshot['binding_sha'],admission_sha=sha(directory/'admission.json'),
        owner_events_sha=sha(directory/'owner-events.json'),observations=observations,
        historical_confirmed={key:snapshot['refs'][key] for key in REQUESTS[7:]},
        sealed_at=v.get('sealed_at'),elapsed_seconds=v.get('elapsed_seconds'))
    rc.require(v==expected, 'RESOLUTION_SEAL_BINDING')
    end=timestamp(v['sealed_at'])
    rc.require(last<=end and 0<=(end-timestamp(a['started_at'])).total_seconds()<300
        and type(v['elapsed_seconds']) in (int,float) and elapsed<=v['elapsed_seconds']<300, 'RESOLUTION_SEAL_STALE')
    return v

def publish_seal(directory,snapshot,elapsed,deadline,before_commit):
    # One commit point. A fsync/readback/schema failure leaves only an invalid
    # staging file. The final name is an exclusive hard link to that SAME inode,
    # whose exact bytes were flushed and read back. No mutation after commit.
    directory=plain(directory)
    payload=seal_payload(directory,snapshot,elapsed)
    pending=directory/'.seal-ready.json'
    write_record(pending,directory.name,'SEAL',payload)
    rc.require(read_record(pending,directory.name,'SEAL')==payload, 'RESOLUTION_SEAL_READBACK')
    before_commit()
    rc.require(time.monotonic()<deadline, 'RESOLUTION_DEADLINE')
    os.link(pending,directory/'seal.json')  # atomic exclusive create; never replace
    return payload

def resolved(state_root,original_directory):
    snapshot=original(original_directory)  # always validate original first
    root=namespace(state_root)
    if not root.exists():
        return False
    generations=list(root.iterdir())
    rc.require(all(p.is_dir() and re.fullmatch('[0-9a-f]{32}',p.name) for p in generations), 'RESOLUTION_UNKNOWN_ARTIFACT')
    sealed=[p for p in generations if (p/'seal.json').exists()]
    if not sealed:
        return False
    rc.require(len(sealed)==1, 'RESOLUTION_AMBIGUOUS_SEALS')
    validate_seal(sealed[0],snapshot)
    return True
