"""Exact 1926 Owner-manual supplemental receipt reader. No production APIs."""
import hashlib,json,os,re
from datetime import datetime,timezone
from pathlib import Path
import retry_continuation as rc
from runtime_config import digest as binding_digest

SESSION='1926b84080a7467b80866f14169cdeba'
AUTHORITY='1926-MANUAL-SIMPLIFIED-1'
SCHEMA='1926_OWNER_MANUAL_V1'
APP=Path(__file__).resolve().parent
from package_authority import OPERATIONAL_ROOT
ROOT=OPERATIONAL_ROOT
REVIEW=ROOT/'reviews/session_1926_simplified_recovery_20260930_01'
STATE=ROOT/'runtime/reservation_journal/schema-v2/cla1-request-local-v1'
RECEIPT=ROOT/'runtime/supplemental_resolution_1926_owner'
TARGET=dict(date='20261011',lesson='サンデープログラム②')
REQUESTS=tuple(w+str(n) for w in 'AB' for n in (1,2,3))

def require(v,r):
    if not v:raise ValueError(r)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()
def read(p):return rc.read(p)
def digest(v):return rc.digest(v)
def utc():return datetime.now(timezone.utc).isoformat()
def timestamp(v):
    require(type(v) is str,'TIMESTAMP');d=datetime.fromisoformat(v)
    require(d.tzinfo is not None and d.utcoffset().total_seconds()==0,'TIMESTAMP');return d

def plain(p):
    p=Path(p).absolute();require(p.resolve()==p,'PATH_REDIRECTED')
    for part in (p,*p.parents):require(not part.is_symlink() and not (hasattr(part,'is_junction') and part.is_junction()),'PATH_REDIRECTED')
    return p

def inventory(p):
    p=plain(p);return {f.relative_to(p).as_posix():sha(plain(f)) for f in sorted(p.rglob('*')) if f.is_file()}

def contract():
    m=read(APP.parent/'OPERATIONAL_MANIFEST.json');ref=m['manual_1926_contract']
    require(ref['path']==str(REVIEW/'contract.json') and sha(plain(ref['path']))==ref['sha256'],'CONTRACT_IDENTITY')
    c=read(ref['path']);require(c['session']==SESSION and c['authority']==AUTHORITY and c['max_age_seconds']==300,'CONTRACT_SCOPE')
    require(sha(REVIEW/'LIMITED_AUTHORITY.md')==c['authority_sha'],'AUTHORITY_CHANGED')
    for name,expected in m['runtime_files'].items():require(sha(APP.parent/name)==expected,'SOURCE_CHANGED')
    require(sha(REVIEW/'issue_manual_resolution.py')==c['issuer_sha'],'ISSUER_CHANGED')
    return c

def original(directory=None):
    directory=plain(directory or STATE/SESSION);require(directory==STATE/SESSION,'SESSION_PATH')
    c=contract();files=inventory(directory);require(files==c['original_inventory'],'ORIGINAL_EVIDENCE_MISMATCH')
    a=read(directory/'admission.json');b=a['binding']
    from admission_control import entries
    require(a['session']==SESSION and a['entries']==entries(b),'SESSION_BINDING')
    require([e['request_id'] for e in a['entries']]==list(REQUESTS),'REQUEST_SET')
    refs=[]
    for w,logname in [('A','production.log.worker_15496.tmp'),('B','production.log.worker_4124.tmp')]:
        es=[dict(e,canonical_lesson=b['request_keys'][w][i][1]) for i,e in enumerate(e for e in a['entries'] if e['worker']==w)]
        require(all(e['user_binding']=='FIXED_USER_'+w for e in es),'USER_BINDING')
        require(es[0]['date']==TARGET['date'] and es[0]['lesson']==TARGET['lesson'],'TARGET_BINDING')
        journal=rc.Journal(directory/'request_attempts'/w,w,es,b,SESSION)
        model,seal,registered=journal.view();require(registered and seal==0 and len(journal.events())==7,'CHAIN_SHAPE')
        logs=[json.loads(x[len('[v1.6] '):]) for x in (directory/'native_logs'/logname).read_text(encoding='utf-8').splitlines() if x.startswith('[v1.6] ')]
        started=[x for x in logs if x['event']=='final_submit_native_click_started'];returned=[x for x in logs if x['event']=='final_submit_native_click_returned'];no=[x for x in logs if x.get('result',{}).get('state')=='FINAL_SUBMIT_NOT_ATTEMPTED']
        require(len(started)==len(returned)==len(no)==1 and returned[0]['submission_attempted'] is True and no[0]['submission_attempted'] is False,'SUBMIT_ACCOUNTING')
        for n in (1,2,3):
            rid=w+str(n);row=model[rid];attempts=row['attempts']
            if n==1:
                require(row['result']=='AWAITING_RECONCILIATION' and len(attempts)==1,'POSITIVE_COMPLETE_REQUIRED');last=attempts[0]
                require(last['state']=='SUBMIT_INTENT' and last['submission_attempted'] is True and last['complete_evidence']['positive'] is True and last['reconciliation_pending'] is True,'POSITIVE_COMPLETE_REQUIRED')
            elif n==2:
                require(row['result']=='ACTIVE' and len(attempts)==1,'NO_SUBMIT_SHAPE');last=attempts[0]
                require(last['state']=='ACTION_INTENT' and last['action_intent'] is True and all(last[k] is False for k in ('submission_attempted','submission_possible','submit_intent_durable')),'ZERO_SUBMIT_REQUIRED')
            else:require(row['result']=='NOT_STARTED' and attempts==[],'NOT_STARTED_REQUIRED')
            refs.append(dict(request_id=rid,user_binding='FIXED_USER_'+w,submit_count=1 if n==1 else 0,original_classification=row['result'],obligation='CURRENT_RESERVED_VERIFIED' if n==1 else 'ABANDONED_NO_FINAL_SUBMIT' if n==2 else 'NOT_STARTED_NO_OPERATION'))
    require(read(directory/'results.json')['results']==[],'ORIGINAL_RESULTS')
    return dict(target_session=SESSION,target_session_identity=binding_digest(b),original_evidence_digest=digest(files),request_resolution=refs)

def declaration(worker,when,mode):
    require(worker in 'AB' and len(worker)==1,'USER_BINDING')
    return dict(declaration_id=worker+'1',target_session=SESSION,owner='たかし' if mode=='ACTUAL' else 'FIXTURE_OWNER',
        worker=worker,user_binding='FIXED_USER_'+worker,request_id=worker+'1',target=dict(TARGET),
        result='VERIFIED_RESERVED',observation_timestamp=when,observation_surface='CURRENT_ACTIVE_RESERVATION_LIST',
        owner_confirmation=True,user_verified=True,target_unambiguous=True,current_reserved_visible=True,
        no_changes_since_observation=True,position='UNKNOWN',origin='OWNER_MANUAL_CURRENT_STATE' if mode=='ACTUAL' else 'OFFLINE_FIXTURE')

def assemble(snapshot,declarations,authorization,mode,ended,resolution_id):
    c=contract();require(mode in ('ACTUAL','OFFLINE_FIXTURE'),'MODE')
    require(digest(snapshot)==digest(original()),'ORIGINAL_EVIDENCE_MISMATCH')
    require(type(resolution_id) is str and re.fullmatch('[0-9a-f]{32}',resolution_id),'RESOLUTION_ID')
    require(type(declarations) is dict and set(declarations)=={'A1','B1'},'TWO_DECLARATIONS_REQUIRED')
    require(digest(authorization)==digest(dict(owner='たかし' if mode=='ACTUAL' else 'FIXTURE_OWNER',target_session=SESSION,
        original_evidence_digest=snapshot['original_evidence_digest'],authorize_resolution=True,abandon_remaining_execution=True,mode=mode)),'OWNER_AUTHORIZATION_REQUIRED')
    end=timestamp(ended);require(end<=datetime.now(timezone.utc),'FUTURE_RESOLUTION')
    for w in 'AB':
        d=declarations[w+'1'];require(type(d) is dict,'DECLARATION_SCHEMA')
        expected=declaration(w,d.get('observation_timestamp'),mode)
        require(digest(d)==digest(expected),'RESERVED_EXACT_OWNER_DECLARATION_REQUIRED')
        require(0<=(end-timestamp(d['observation_timestamp'])).total_seconds()<=c['max_age_seconds'],'STALE_OR_FUTURE_DECLARATION')
    return dict(snapshot,schema=SCHEMA,mode=mode,authority=AUTHORITY,authority_sha=c['authority_sha'],
        source_identity=sha(APP.parent/'OPERATIONAL_MANIFEST.json'),resolution_id=resolution_id,
        declarations=declarations,owner_authorization=authorization,resolution_timestamp=ended,
        logical_obligation='RESOLVED',historical_closed=False,production_operations_by_codex=0)

def envelope(payload):return dict(payload=payload,digest=digest(payload))

def validate(value,snapshot,mode='ACTUAL'):
    require(type(value) is dict and set(value)=={'payload','digest'},'RECEIPT_SCHEMA')
    p=value['payload'];require(type(p) is dict and value['digest']==digest(p),'RECEIPT_DIGEST')
    expected=assemble(snapshot,p['declarations'],p['owner_authorization'],mode,p['resolution_timestamp'],p['resolution_id'])
    # Historical ACTUAL receipts bind to the authorized issuance generation.
    if mode=='ACTUAL':
        issuer=read(APP.parent/'OPERATIONAL_MANIFEST.json')['manual_1926_contract'].get('issuer_manifest_sha')
        require(issuer=='7320D40C9580ABB139E704AEB679C68F8C645409229C3655D3D28E5AAED6DBCB','ISSUER_GENERATION')
        require(sha(plain(ROOT/'reviews/runtime_exit_code_closeout_20261005_01/previous_package/OPERATIONAL_MANIFEST.json'))==issuer,'ISSUER_PROVENANCE')
        expected['source_identity']=issuer
    require(digest(p)==digest(expected),'RECEIPT_CONTENT')
    return p

def receipt_valid(directory,snapshot,mode='ACTUAL'):
    directory=plain(directory)
    if not directory.exists():return False
    require({p.name for p in directory.iterdir()}=={'pending.json','seal.json'},'PARTIAL_OR_CONFLICTING_RECEIPT')
    require(os.path.samefile(directory/'pending.json',directory/'seal.json'),'PUBLICATION_IDENTITY')
    require(read(directory/'pending.json')==read(directory/'seal.json'),'ALTERED_RECEIPT')
    validate(read(directory/'seal.json'),snapshot,mode);return True

def resolved(root,directory):
    require(plain(root)==STATE and plain(directory)==STATE/SESSION,'SESSION_BINDING')
    snapshot=original(directory)
    return receipt_valid(RECEIPT,snapshot,'ACTUAL')
