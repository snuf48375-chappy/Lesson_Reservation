"""Separately approved 3851 observation. No import-time I/O and no normal worker dispatch."""
import sys
import time
import uuid
from pathlib import Path
import retry_continuation as rc
import resolution_evidence as ev
import diagnostic as diagnostic

def _observe(name,*args,**kwargs):
    # Even an unavailable/broken probe cannot affect the transaction.
    try: getattr(diagnostic,name)(*args,**kwargs)
    except BaseException: pass

def _persisted(resolution_id,kind,payload,request_id=None):
    try:
        value=ev.envelope(resolution_id,kind,payload)
        _observe('fet_resolution_persisted',kind,request_id,value['evidence_hash'])
    except BaseException: pass

def execute(state_root,approval,source_paths,open_inquiry,lease_factory,check_source):
    _observe('fet_resolution_enter')
    try:
        return _execute(state_root,approval,source_paths,open_inquiry,lease_factory,check_source)
    except BaseException as exc:
        _observe('fet_resolution_capture','RUNTIME_ORIGINAL',exc)
        _observe('fet_resolution_capture','RESOLUTION_ABORT',exc)
        raise  # Retain interrupts and post-commit cleanup propagation verbatim.
    finally:
        _observe('fet_resolution_stop')

def _execute(state_root,approval,source_paths,open_inquiry,lease_factory,check_source):
    """Internal orchestration; production caller below supplies only the fixed A inquiry adapter."""
    started=time.monotonic(); deadline=started+300
    state_root=ev.plain(state_root)
    rid=uuid.uuid4().hex
    _observe('fet_resolution_start',state_root.parents[2]/'diagnostic_evidence',ev.SESSION,rid,
             ev.APP.parent/'OPERATIONAL_MANIFEST.json')
    lock=state_root/'execution.lock'
    lock_value=dict(session=rid,kind='3851_RESOLUTION_ONLY')
    directory=None; lease=None; inquiry=None; locked=False
    committed=False  # Diagnostic labeling only; never used to decide validity/outcome.
    try:
        check_source()
        snapshot=ev.original(state_root/ev.SESSION)
        _observe('fet_resolution_context','ORIGINAL_VERIFIED',binding_sha=snapshot['binding_sha'])
        admission=ev.admission_payload(snapshot,approval)
        rc.require(not ev.resolved(state_root,state_root/ev.SESSION), 'RESOLUTION_ALREADY_SEALED')
        # Exclusive creation: a stale or competing execution lock is never removed.
        rc.publish(lock,lock_value); locked=True
        initial=ev.inventory(state_root/ev.SESSION)
        evidence_root=ev.namespace(state_root)
        prior=ev.inventory(evidence_root) if evidence_root.exists() else {}
        lease=lease_factory()
        paths=set(source_paths)|set((state_root/ev.SESSION).rglob('*'))
        paths|=set(evidence_root.rglob('*')) if evidence_root.exists() else set()
        lease.add(p for p in paths if p.is_file())
        def check():
            lease.require_open(); check_source()
            rc.require(time.monotonic()<deadline, 'RESOLUTION_DEADLINE')
            rc.require(rc.read(lock)==lock_value, 'RESOLUTION_LOCK_CHANGED')
            rc.require(ev.inventory(state_root/ev.SESSION)==initial, 'RESOLUTION_ORIGINAL_CHANGED')
            current=ev.inventory(evidence_root) if evidence_root.exists() else {}
            outside={k:v for k,v in current.items() if not k.startswith(rid+'/')}
            rc.require(outside==prior, 'RESOLUTION_EVIDENCE_CHANGED')
        check()
        snapshot=ev.original(state_root/ev.SESSION)
        rc.require(not ev.resolved(state_root,state_root/ev.SESSION), 'RESOLUTION_ALREADY_SEALED')
        directory=evidence_root/rid
        directory.mkdir(parents=True,exist_ok=False)
        _observe('fet_resolution_context','ADMISSION_WRITE')
        ev.write_record(directory/'admission.json',rid,'ADMISSION',admission)
        _persisted(rid,'ADMISSION',admission)
        _observe('fet_resolution_context','OWNER_EVENTS_WRITE')
        ev.write_record(directory/'owner-events.json',rid,'OWNER_EVENTS',ev.OWNER_EVENTS)
        _persisted(rid,'OWNER_EVENTS',ev.OWNER_EVENTS)
        lease.add([directory/'admission.json',directory/'owner-events.json'])
        _observe('fet_resolution_context','INQUIRY_OPEN',worker='A')
        inquiry=open_inquiry(snapshot,deadline,check)  # only A; never instantiate B
        for request_id in ev.REQUESTS[:7]:
            _observe('fet_resolution_context','INQUIRY_OBSERVE',request_id,worker='A')
            check()
            entry=next(e for e in snapshot['entries'] if e['request_id']==request_id)
            request=dict(date=entry['date'],name=entry['lesson'])
            proof=inquiry.observe(request)
            check()
            value=ev.observation(snapshot,request_id,proof,time.monotonic()-started)
            path=directory/(request_id+'.json')
            _observe('fet_resolution_context','OBSERVATION_WRITE',request_id,worker='A')
            ev.write_record(path,rid,'OBSERVATION',value)
            _persisted(rid,'OBSERVATION',value,request_id)
            lease.add([path])
        _observe('fet_resolution_context','PRE_SEAL_BROWSER_CLOSE',worker='A')
        try: inquiry.close()
        except BaseException as exc:
            _observe('fet_resolution_capture','CLEANUP',exc)
            raise
        inquiry=None  # a browser cleanup failure must prevent sealing
        check()
        _observe('fet_resolution_context','SEAL_PUBLISH')
        seal=ev.publish_seal(directory,snapshot,time.monotonic()-started,deadline,check)
        committed=True
        _persisted(rid,'SEAL',seal)
        _observe('fet_resolution_context','SEAL_PUBLISHED')
        return dict(status='RESOLVED',resolution_id=rid)
    except Exception as exc:
        _observe('fet_resolution_capture','RUNTIME_ORIGINAL',exc)
        _observe('fet_resolution_capture','RESOLUTION_ABORT',exc)
        # Never persist raw error text/trace/credentials; partials remain in their own generation.
        return dict(status='INCOMPLETE',resolution_id=rid)
    finally:
        clean=True
        if inquiry is not None:
            _observe('fet_resolution_context','PRE_SEAL_BROWSER_FINALLY',worker='A')
            try:
                try: inquiry.close()
                except BaseException as exc:
                    _observe('fet_resolution_capture','CLEANUP',exc)
                    raise
            except Exception:
                clean=False
        if lease is not None:
            _observe('fet_resolution_context','POST_SEAL_LEASE_CLOSE' if committed else 'PRE_SEAL_LEASE_CLOSE')
            try: lease.close()
            except BaseException as exc:
                _observe('fet_resolution_capture','CLEANUP',exc)
                raise
        # Only our exact, no-longer-active lock can be released. Never a stale lock.
        if locked and clean:
            _observe('fet_resolution_context','POST_SEAL_LOCK_RELEASE' if committed else 'PRE_SEAL_LOCK_RELEASE')
            try:
                if rc.read(lock)==lock_value:
                    lock.unlink()
            except Exception as exc:
                _observe('fet_resolution_capture','CLEANUP',exc)
                # The publication commit point has already been decided. An
                # unreleased own lock remains an admission blocker, never erased.
                pass

def open_a(snapshot,deadline,check):
    import runtime as rt
    from resolution_inquiry import Inquiry
    from login_control import automatic_login
    from credentials import WindowsCredentials
    module,user=rt.resolution_context(snapshot)
    check()
    options=module.webdriver.ChromeOptions()
    options.add_argument('--user-data-dir='+user['profile_path'])
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--log-level=3')
    options.add_experimental_option('excludeSwitches',['enable-logging'])
    from driver_selection import CHROME, chrome_service
    options.binary_location=str(CHROME)
    driver=module.webdriver.Chrome(service=chrome_service(), options=options)
    try:
        check()
        automatic_login(module,driver,user,'A',WindowsCredentials(),check,lambda name:None)
        check()
        return Inquiry(module,driver,user,deadline,check)
    except BaseException as exc:
        _observe('fet_resolution_capture','RUNTIME_ORIGINAL',exc)
        _observe('fet_resolution_context','OPEN_BROWSER_CLEANUP',worker='A')
        try: driver.quit()
        except BaseException as cleanup:
            _observe('fet_resolution_capture','CLEANUP',cleanup)
            raise
        raise

def main():
    # No --live, BAT, normal GO, launch.worker(), retry_worker.run(), or fallback.
    import runtime as rt
    from frozen_inputs import FrozenInputs
    rc.require(sys.stdin.isatty(), 'RESOLUTION_INTERACTIVE_OWNER_REQUIRED')
    rt.verify_package()  # independent offline copies intentionally remain unadopted
    snapshot=ev.original(rt.STATE/ev.SESSION)
    print('3851 A1-A7 Inquiry only; B historical evidence only. No manual changes during observation.')
    print('This approval grants no reservation, continuation, Freeze or Adoption authority.')
    required=ev.APPROVAL+':'+snapshot['binding_sha']
    rc.require(input('Enter the exact resolution-only approval: '+required+'\n')==required, 'RESOLUTION_OWNER_APPROVAL')
    approval=dict(semantic=ev.APPROVAL,session=ev.SESSION,binding_sha=snapshot['binding_sha'])
    c=ev.contract()
    paths={ev.APP.parent/name for name in rc.read(rt.MANIFEST)['runtime_files']}
    paths.update((rt.MANIFEST,rt.IDENTITY,Path(c['authority_path'])))
    result=execute(rt.STATE,approval,paths,open_a,FrozenInputs,rt.verify_package)
    print('RESOLUTION='+result['status'])
    return 0 if result['status']=='RESOLVED' else 1

if __name__=='__main__':
    raise SystemExit(main())
