"""Explicit pre-GO Q closeout; never a Human GO or reservation entry."""
from __future__ import annotations
import argparse, ctypes, hashlib, json, os, re, secrets, sys, time
from ctypes import wintypes as wt
from datetime import datetime, timedelta, timezone
from pathlib import Path
import retry_continuation as rc
from admission_control import entries
from runtime_config import digest as binding_digest

SCHEMA = "CLA1_PRE_GO_NON_SUCCESS_V1"
QOUT = "SAFE_QUIT_PRE_GO_NO_SUBMIT"
AOUT = "ABORTED_PRE_GO_NO_SUBMIT"
class SafeQuitRequested(Exception):
    pass
def require(value, reason):
    if not value: raise ValueError(reason)
def stamp(): return datetime.now(timezone.utc).isoformat()
def canonical(v): return json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("ascii")
def digest(v): return hashlib.sha256(canonical(v)).hexdigest().upper()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()
def plain(p):
    p=Path(p).absolute()
    require(p.resolve()==p and not any(q.is_symlink() or hasattr(q,"is_junction") and q.is_junction() for q in (p,*p.parents)),"QUIT_PATH_REDIRECTED")
    return p
def inventory(root):
    root=plain(root)
    return {p.relative_to(root).as_posix():sha(plain(p)) for p in sorted(root.rglob("*")) if p.is_file()}
def publish(path,value):
    path=plain(path); payload=canonical(value)
    with path.open("xb") as f: f.write(payload); f.flush(); os.fsync(f.fileno())
def config(current=None):
    current=Path(current) if current else Path(__file__).resolve().parents[1]
    m=rc.read(current/"OPERATIONAL_MANIFEST.json"); c=m["safe_pre_go_quit"]
    require(c["schema"]==SCHEMA,"QUIT_CONTRACT_SCHEMA")
    require(m["runtime_files"]["app/safe_quit.py"]==sha(current/"app/safe_quit.py"),"QUIT_VALIDATOR_PIN")
    require(m["runtime_files"][c["authority_path"]]==c["authority_sha256"]==sha(current/c["authority_path"]),"QUIT_AUTHORITY_PIN")
    display=current.parent/"operational_launcher/Final-ResultSummary.ps1"
    require(sha(display)==c["result_display_sha256"],"QUIT_DISPLAY_PIN")
    recovery=c.get("q_failure_recovery")
    if recovery is not None:
        require(recovery["session"]=="5e1f515ac3264be691f976f68c21932b" and
                recovery["lock_sha256"]=="66E6E42A3B649EF73EFC0A5B0C0BA62FD3E7E55C7F4F505E101518A33F609BFC" and
                recovery["source_inventory_sha256"]=="0902F6B43C73E35ED277C0466864A58DD0AE21F55F033DBB5CA6C43D7A8BF158" and
                recovery["evidence_root"]==r"C:\Lesson_Reservation_GEN2\evidence\cla1-gen2-concurrent-20261031T165747-a8cfc00a" and
                recovery["result_sha256"]=="DCF6A6581D1809F2665C678DCD37C7432F4C238A72A3888369F99FF55D0F400A" and
                recovery["console_sha256"]=="6BED920A3F48490DE5744103DF5A8976DF87690D6364773D1D6F7D3324C0723A",
                "Q_FAILURE_RECOVERY_PIN")
    return c
def base_evidence(root):
    root=plain(root); sid=root.name
    require(re.fullmatch("[0-9a-f]{32}",sid) is not None,"QUIT_SESSION")
    a=rc.read(root/"admission.json"); b=a["binding"]
    require(a["schema"]==rc.SCHEMA and a["session"]==sid and a["entries"]==entries(b),"QUIT_ADMISSION")
    require(rc.read(root/"consumed.json")==dict(session=sid,binding_sha=binding_digest(b)),"QUIT_CONSUMED")
    require({p.name for p in (root/"request_attempts").iterdir()}=={"A","B"},"QUIT_WORKERS")
    for w in "AB":
        require(rc.read(root/f"claim-{w}.json")==dict(session=sid,worker=w),"QUIT_CLAIM")
        require(rc.read(root/f"login-{w}.json")==dict(code="OK",state="LOGINED"),"QUIT_LOGIN")
        selected=[e for e in a["entries"] if e["worker"]==w]
        keys=b["request_keys"][w]
        require(len(selected)==len(keys),"QUIT_REQUEST_KEYS")
        rows=[]
        for e,key in zip(selected,keys):
            require(type(key) is list and len(key)==(3 if "start_time" in e else 2)
                    and e["date"]==key[0]
                    and ("start_time" not in e or e["start_time"]==key[1]),"QUIT_REQUEST_KEY")
            rows.append(dict(e,canonical_lesson=key[2] if len(key)==3 else key[1]))
        journal=rc.Journal(root/"request_attempts"/w,w,rows,b,sid)
        ev=journal.events(); model,_,registered=journal.view()
        require(registered and [e["event_type"] for e in ev]==["REGISTER"],"QUIT_NOT_REGISTER_ONLY")
        require(all(not x["attempts"] and x["result"]=="NOT_STARTED" for x in model.values()),"QUIT_ATTEMPT_OR_UNKNOWN")
    require(not any((root/n).exists() for n in ("human_go.json","results.json","finished.json")),"QUIT_GO_OR_NORMAL_TERMINAL")
    known={"admission.json","consumed.json","request_attempts","native_logs","safe_quit_request.json","safe_quit_result.json"}
    known.update(f"{p}-{w}.json" for p in ("claim","login","worker") for w in "AB")
    require(all(p.name in known for p in root.iterdir()),"QUIT_UNKNOWN_ARTIFACT")
    return a,b
def request(root,binding,choice,both_ready,check):
    require(choice in ("Q","q"),"QUIT_INPUT")
    check(); a,b=base_evidence(root)
    require(b==binding,"QUIT_BINDING")
    value=dict(schema=SCHEMA,session=Path(root).name,binding_sha=binding_digest(b),
        input="Q",nonce=secrets.token_hex(16),both_ready_at=both_ready,requested_at=stamp())
    publish(Path(root)/"safe_quit_request.json",value)
    return value
def verify_request(root,binding):
    a,b=base_evidence(root); q=rc.read(Path(root)/"safe_quit_request.json")
    require(set(q)=={"schema","session","binding_sha","input","nonce","both_ready_at","requested_at"},"QUIT_REQUEST_SCHEMA")
    require(q["schema"]==SCHEMA and q["session"]==Path(root).name and q["binding_sha"]==binding_digest(b)==binding_digest(binding) and q["input"]=="Q" and re.fullmatch("[0-9a-f]{32}",q["nonce"]),"QUIT_REQUEST_BINDING")
    for key in ("both_ready_at","requested_at"):
        require(datetime.fromisoformat(q[key]).tzinfo is not None,"QUIT_TIME")
    require(datetime.fromisoformat(q["requested_at"])>=datetime.fromisoformat(q["both_ready_at"]),"QUIT_TIME_ORDER")
    return q

class PE(ctypes.Structure):
    _fields_=[("dwSize",wt.DWORD),("cntUsage",wt.DWORD),("th32ProcessID",wt.DWORD),
      ("th32DefaultHeapID",ctypes.c_size_t),("th32ModuleID",wt.DWORD),("cntThreads",wt.DWORD),
      ("th32ParentProcessID",wt.DWORD),("pcPriClassBase",wt.LONG),("dwFlags",wt.DWORD),("szExeFile",wt.WCHAR*260)]
def _api():
    require(os.name=="nt","QUIT_WINDOWS_PROCESS_PROOF")
    k=ctypes.WinDLL("kernel32",use_last_error=True)
    k.CreateToolhelp32Snapshot.argtypes=[wt.DWORD,wt.DWORD];k.CreateToolhelp32Snapshot.restype=wt.HANDLE
    k.Process32FirstW.argtypes=[wt.HANDLE,ctypes.POINTER(PE)];k.Process32FirstW.restype=wt.BOOL
    k.Process32NextW.argtypes=[wt.HANDLE,ctypes.POINTER(PE)];k.Process32NextW.restype=wt.BOOL
    k.OpenProcess.argtypes=[wt.DWORD,wt.BOOL,wt.DWORD];k.OpenProcess.restype=wt.HANDLE
    k.WaitForSingleObject.argtypes=[wt.HANDLE,wt.DWORD];k.WaitForSingleObject.restype=wt.DWORD
    k.CloseHandle.argtypes=[wt.HANDLE];k.CloseHandle.restype=wt.BOOL
    return k
def _process_snapshot():
    k=_api(); snap=k.CreateToolhelp32Snapshot(2,0)
    require(snap not in (None,ctypes.c_void_p(-1).value),"QUIT_PROCESS_SNAPSHOT")
    rows={}
    try:
        e=PE();e.dwSize=ctypes.sizeof(e)
        ok=k.Process32FirstW(snap,ctypes.byref(e))
        require(bool(ok),"QUIT_PROCESS_ENUMERATION")
        while ok:
            rows[int(e.th32ProcessID)]=(int(e.th32ParentProcessID),e.szExeFile)
            ok=k.Process32NextW(snap,ctypes.byref(e))
        require(ctypes.get_last_error()==18,"QUIT_PROCESS_ENUMERATION_INCOMPLETE")
    finally:k.CloseHandle(snap)
    return rows
class FT(ctypes.Structure):
    _fields_=[("dwLowDateTime",wt.DWORD),("dwHighDateTime",wt.DWORD)]
def _process_created_at(pid):
    k=_api();handle=k.OpenProcess(0x1000,False,pid)
    require(bool(handle),"Q_FAILURE_PROCESS_TIME_UNKNOWN")
    try:
        k.GetProcessTimes.argtypes=[wt.HANDLE,ctypes.POINTER(FT),ctypes.POINTER(FT),ctypes.POINTER(FT),ctypes.POINTER(FT)]
        k.GetProcessTimes.restype=wt.BOOL
        created=FT();exited=FT();kernel=FT();user=FT()
        require(bool(k.GetProcessTimes(handle,ctypes.byref(created),ctypes.byref(exited),
                                       ctypes.byref(kernel),ctypes.byref(user))),
                "Q_FAILURE_PROCESS_TIME_UNKNOWN")
        ticks=(created.dwHighDateTime<<32)|created.dwLowDateTime
        return datetime(1601,1,1,tzinfo=timezone.utc)+timedelta(microseconds=ticks//10)
    finally:k.CloseHandle(handle)
def _process_handles(pid):
    k=_api(); rows=_process_snapshot()
    require(pid in rows,"QUIT_SERVICE_PROCESS_MISSING")
    selected={pid}; changed=True
    while changed:
        added={p for p,(parent,_) in rows.items() if parent in selected}-selected
        changed=bool(added);selected.update(added)
    owned=[]
    try:
        for p in sorted(selected):
            handle=k.OpenProcess(0x100000,False,p)
            if not handle:
                require(ctypes.get_last_error()==87 and p!=pid,"QUIT_PROCESS_HANDLE_UNKNOWN")
                continue
            owned.append(dict(pid=p,exe=rows[p][1],handle=handle))
        require(any(x["pid"]==pid for x in owned),"QUIT_SERVICE_HANDLE")
        return owned
    except BaseException:
        close_handles(owned);raise
def close_handles(owned):
    if owned:
        k=_api()
        for p in owned:
            if p.get("handle"):k.CloseHandle(p["handle"]);p["handle"]=None
def capture_owned_processes(driver):
    service=getattr(driver,"service",None); proc=getattr(service,"process",None)
    require(proc is not None and proc.poll() is None and type(proc.pid) is int,"QUIT_SERVICE_IDENTITY")
    owned=_process_handles(proc.pid)
    if not any(p["exe"].lower()=="chrome.exe" for p in owned):
        close_handles(owned);raise ValueError("QUIT_BROWSER_OWNERSHIP_UNKNOWN")
    return owned
def exited_processes(owned,timeout=20):
    require(bool(owned),"QUIT_OWNED_PROCESSES_REQUIRED")
    k=_api(); deadline=time.monotonic()+timeout
    for p in owned:
        ms=max(0,int((deadline-time.monotonic())*1000))
        require(k.WaitForSingleObject(p["handle"],ms)==0,"QUIT_OWNED_PROCESS_STILL_ALIVE")
    return [dict(pid=p["pid"],exe=p["exe"]) for p in owned]
def worker_complete(root,alias,binding,owned):
    q=verify_request(root,binding)
    try: proof=exited_processes(owned)
    finally:close_handles(owned)
    require(alias in "AB","QUIT_WORKER_ALIAS")
    value=dict(status="SAFE_QUIT_PRE_GO",session=Path(root).name,worker=alias,
        worker_pid=os.getpid(),request_sha256=sha(Path(root)/"safe_quit_request.json"),
        driver_quit_returned=True,driver_service_stopped=True,owned_processes_exited=True,
        owned_processes=proof,completed_at=stamp())
    publish(Path(root)/f"worker-{alias}.json",value)
    return value
def _q_evidence(root):
    a,b=base_evidence(root);verify_request(root,b)
    require(not list((Path(root)/"native_logs").glob("exception-*.json")),"QUIT_EXCEPTION_OR_CLEANUP_FAILURE")
    qsha=sha(Path(root)/"safe_quit_request.json")
    workers={}
    for w in "AB":
        r=rc.read(Path(root)/f"worker-{w}.json")
        require(set(r)=={"status","session","worker","worker_pid","request_sha256","driver_quit_returned","driver_service_stopped","owned_processes_exited","owned_processes","completed_at"},"QUIT_WORKER_SCHEMA")
        require(r["status"]=="SAFE_QUIT_PRE_GO" and r["session"]==Path(root).name and r["worker"]==w and r["request_sha256"]==qsha,"QUIT_WORKER_BINDING")
        require(all(r[k] is True for k in ("driver_quit_returned","driver_service_stopped","owned_processes_exited")),"QUIT_CLEANUP_INCOMPLETE")
        require(type(r["worker_pid"]) is int and r["worker_pid"]>0 and r["owned_processes"] and any(x["exe"].lower()=="chrome.exe" for x in r["owned_processes"]),"QUIT_PROCESS_PROOF")
        workers[w]=r
    require(workers["A"]["worker_pid"]!=workers["B"]["worker_pid"],"QUIT_WORKER_PID_COLLISION")
    return a,b,workers
def post_cleanup_check(workers):
    # Fresh coordinator check after BOTH workers exit; includes late children.
    require(set(workers)=={"A","B"},"QUIT_WORKER_OWNERSHIP_UNKNOWN")
    anchors=set()
    for worker in workers.values():
        owned=worker.get("owned_processes")
        require(type(worker.get("worker_pid")) is int and worker["worker_pid"]>0 and
            type(owned) is list and owned,"QUIT_WORKER_OWNERSHIP_UNKNOWN")
        images={p.get("exe","").lower() for p in owned if type(p) is dict}
        require({"chromedriver.exe","chrome.exe"}<=images,"QUIT_BROWSER_OWNERSHIP_UNKNOWN")
        pids=[worker["worker_pid"]]+[p.get("pid") for p in owned]
        require(all(type(pid) is int and pid>0 for pid in pids) and
            len(pids)==len(set(pids)) and not anchors.intersection(pids),
            "QUIT_WORKER_OWNERSHIP_UNKNOWN")
        anchors.update(pids)
    rows=_process_snapshot()
    related=set(anchors); changed=True
    while changed:
        added={pid for pid,(parent,_) in rows.items() if parent in related}-related
        changed=bool(added);related.update(added)
    require(not any(pid in related for pid in rows),"QUIT_RESIDUAL_RELATED_PROCESS")
    # The captured service/descendant handles and ancestry define this CLA-1
    # run's ownership. Other Chrome/Driver processes are not this run's proof.
    return dict(status="PASS",observed_at=stamp(),residual_related=[],
                unattributed_browser_or_driver=[])
def _receipt(root,outcome,c,owner):
    original=inventory(root)
    return dict(schema=SCHEMA,session=Path(root).name,outcome=outcome,
        authority_sha256=c["authority_sha256"],owner_intent=owner,
        original_inventory=original,original_inventory_sha256=digest(original))

def _q_failure_source(root,recovery):
    root=plain(root)
    require(root.name==recovery["session"],"Q_FAILURE_SESSION")
    original=inventory(root)
    require(len(original)==16 and digest(original)==recovery["source_inventory_sha256"],"Q_FAILURE_INVENTORY")
    a,b=base_evidence(root)
    require(len(a["entries"])==4 and all(len(b["request_keys"][w])==2 for w in "AB"),"Q_FAILURE_IDENTITY")
    require(not any((root/n).exists() for n in ("safe_quit_request.json","safe_quit_result.json","human_go.json","results.json","finished.json")),"Q_FAILURE_ACTION_ARTIFACT")
    for w in "AB":
        require(rc.read(root/f"worker-{w}.json")==dict(status="ABORT",exception_type="ValueError"),"Q_FAILURE_WORKER")
        for seq,channel in ((1,"RUNTIME_ORIGINAL"),(2,"WORKER_ABORT")):
            e=rc.read(root/"native_logs"/f"exception-{w}-{seq:06d}.json")
            frames={(frame.get("file"),frame.get("function")) for frame in e.get("frames",[]) if type(frame) is dict}
            require(e.get("session")==root.name and e.get("worker")==w and e.get("event_seq")==seq
                    and e.get("channel")==channel and e.get("exception_type")=="ValueError"
                    and e.get("truncated") is False
                    and ("app/safe_quit.py","verify_request") in frames
                    and ("app/retry_continuation.py","reduce_events") in frames,
                    "Q_FAILURE_EXCEPTION")
    traces=sorted((root/"native_logs").glob("production.log.worker_*.tmp"))
    require({p.name for p in traces}=={"production.log.worker_22136.tmp","production.log.worker_26140.tmp"},"Q_FAILURE_TRACE_SET")
    for trace in traces:
        lines=trace.read_text(encoding="utf-8").splitlines()
        require(all(line.startswith("[v1.6] ") for line in lines),"Q_FAILURE_TRACE")
        events=[json.loads(line[7:]) for line in lines]
        require([e.get("event") for e in events]==["browser_started","login_verification","worker_result"]
                and events[1].get("result",{}).get("state")=="LOGINED"
                and events[2].get("result",{}).get("state")=="WORKER_ABORTED", "Q_FAILURE_TRACE")
    evidence=plain(Path(recovery["evidence_root"]))
    result_path=evidence/"result.json"; console_path=evidence/"cla-console-output.txt"
    require(sha(result_path)==recovery["result_sha256"] and sha(console_path)==recovery["console_sha256"],"Q_FAILURE_EVIDENCE_PIN")
    result=rc.read(result_path);console=console_path.read_text(encoding="utf-8")
    require(result.get("session")==root.name and result.get("cla_exit")==1 and result.get("verdict")=="HOLD"
            and result.get("hold_reason")=="CLA_EXIT" and result.get("gen2",{}).get("exit")==4
            and "HOLD_CONCURRENT_GATE" in result.get("gen2",{}).get("output","")
            and "JOB_ACTIVE=0 STOP_CONFIRMED=True" in result.get("gen2",{}).get("output","")
            and "Worker A: READY" in console and "Worker B: READY" in console
            and "Q または q + Enter" in console and "REGISTRATION_INVALID" in console,
            "Q_FAILURE_RUN_EVIDENCE")
    events=[e.get("event") for e in result.get("events",[])]
    require(events==["CLA_STARTED","CLA_READY_Q_WAIT","BOTH_CHROME_DRIVER_WORKERS_RUNNING"],"Q_FAILURE_RUN_SEQUENCE")
    cla=result["pids"]["simultaneous_cla"];gen2=result["pids"]["simultaneous_gen2"]
    bypid={p["pid"]:p for p in cla}
    anchors=set(bypid)
    require(len(cla)==len(anchors)==23 and result["pids"]["cla_launcher"] in anchors
            and {22136,26140,5552,27352}<=anchors
            and all(p["parent"] in anchors for p in cla if p["pid"]!=result["pids"]["cla_launcher"])
            and sum(p["exe"]=="chromedriver.exe" for p in cla)==2
            and sum(p["exe"]=="chrome.exe" for p in cla)>=2
            and all(p["exe"]=="python.exe" for p in cla if p["pid"] in (22136,26140))
            and not anchors.intersection(p["pid"] for p in gen2)
            and result["pids"]["gen2_worker"] in {p["pid"] for p in gen2},
            "Q_FAILURE_PID_OWNERSHIP")
    return sorted(anchors)

def q_failure_process_check(root,recovery):
    anchors=_q_failure_source(root,recovery)
    rows=_process_snapshot()
    related=set(anchors);changed=True
    while changed:
        added={pid for pid,(parent,_) in rows.items() if parent in related}-related
        changed=bool(added);related.update(added)
    result_path=Path(recovery["evidence_root"])/"result.json"
    require(sha(result_path)==recovery["result_sha256"],"Q_FAILURE_EVIDENCE_PIN")
    result=rc.read(result_path)
    end=datetime.fromisoformat(result["ended_at_utc"])
    require(end.tzinfo is not None,"Q_FAILURE_RUN_TIME")
    reused=[];possibly_owned=[]
    for pid in sorted(related.intersection(rows)):
        created=_process_created_at(pid)
        require(created.tzinfo is not None,"Q_FAILURE_PROCESS_TIME_UNKNOWN")
        if created<=end:
            possibly_owned.append(pid)
        else:
            parent,exe=rows[pid]
            reused.append(dict(pid=pid,parent=parent,exe=exe,created_at=created.isoformat()))
    require(not possibly_owned,"Q_FAILURE_OWNED_PROCESS_REMAINS")
    return dict(schema="CLA1_Q_FAILURE_PROCESS_CHECK_V1",observed_at=stamp(),
                anchors_sha256=digest(anchors),residual_related=[],excluded_reused_pids=reused)

def _validate_q_failure_receipt(value,root,recovery):
    anchors=_q_failure_source(root,recovery)
    intent=value["owner_intent"]
    require(type(intent) is dict and set(intent)=={"kind","lock_sha256","process_check"}
            and intent["kind"]=="OWNER_DIRECT_Q_FAILURE_RECOVERY"
            and intent["lock_sha256"]==recovery["lock_sha256"],"Q_FAILURE_INTENT")
    proof=intent["process_check"]
    require(type(proof) is dict and set(proof)=={"schema","observed_at","anchors_sha256","residual_related","excluded_reused_pids"}
            and proof["schema"]=="CLA1_Q_FAILURE_PROCESS_CHECK_V1"
            and proof["anchors_sha256"]==digest(anchors) and proof["residual_related"]==[]
            and type(proof["excluded_reused_pids"]) is list,"Q_FAILURE_PROCESS_PROOF")
    require(datetime.fromisoformat(proof["observed_at"]).tzinfo is not None,"Q_FAILURE_PROCESS_TIME")
    result_path=Path(recovery["evidence_root"])/"result.json"
    require(sha(result_path)==recovery["result_sha256"],"Q_FAILURE_EVIDENCE_PIN")
    end=datetime.fromisoformat(rc.read(result_path)["ended_at_utc"])
    require(end.tzinfo is not None and all(
        type(row) is dict and set(row)=={"pid","parent","exe","created_at"}
        and type(row["pid"]) is int and type(row["parent"]) is int and type(row["exe"]) is str
        and datetime.fromisoformat(row["created_at"]).tzinfo is not None
        and datetime.fromisoformat(row["created_at"])>end
        for row in proof["excluded_reused_pids"]),"Q_FAILURE_REUSED_PID_PROOF")

def validate_receipt(value,root,c,commit=None):
    require(set(value)=={"schema","session","outcome","authority_sha256","owner_intent","original_inventory","original_inventory_sha256"},"QUIT_RECEIPT_SCHEMA")
    recovery=c.get("q_failure_recovery")
    require(value["schema"]==SCHEMA and value["session"]==Path(root).name and value["authority_sha256"]==c["authority_sha256"],"QUIT_RECEIPT_BINDING")
    original=inventory(root)
    require(value["original_inventory"]==original and value["original_inventory_sha256"]==digest(original),"QUIT_ORIGINAL_CHANGED")
    if value["outcome"]==AOUT:
        legacy=c["existing_abort_recovery"]
        if Path(root).name==legacy["session"]:
            require(digest(original)==legacy["source_inventory_sha256"],"LEGACY_ABORT_SCOPE")
            a,b=base_evidence(root)
            require(not any((Path(root)/n).exists() for n in ("safe_quit_request.json","safe_quit_result.json")),"LEGACY_NOT_Q")
            for w in "AB":
                require(rc.read(Path(root)/f"worker-{w}.json")==dict(status="ABORT",exception_type="KeyboardInterrupt"),"LEGACY_ABORT_RECORD")
                e=rc.read(Path(root)/"native_logs"/f"exception-{w}-000001.json")
                require(e["session"]==Path(root).name and e["worker"]==w and e["channel"]=="RUNTIME_ORIGINAL" and e["exception_type"]=="KeyboardInterrupt" and e["truncated"] is False,"LEGACY_INTERRUPT")
            require(value["owner_intent"]==dict(kind="EXACT_OWNER_RECOVERY_CLAUSE",raw_sha256=legacy["owner_clause_sha256"]),"LEGACY_APPROVAL")
        elif recovery is not None and Path(root).name==recovery["session"]:
            _validate_q_failure_receipt(value,root,recovery)
        else:
            raise ValueError("LEGACY_ABORT_SCOPE")
    elif value["outcome"]==QOUT:
        a,b,workers=_q_evidence(root);result=rc.read(Path(root)/"safe_quit_result.json")
        expected_rows=[dict(worker=e["worker"],request=e["request_id"],lesson=e["lesson"],final_result="NOT_STARTED",attempts=0,attempt_records=[]) for e in a["entries"]]
        require(set(result)=={"schema","session","outcome","binding_sha","request_sha256","worker_exit_codes","worker_pids","process_cleanup","results","created_at"},"QUIT_RESULT_SCHEMA")
        require(result["schema"]==SCHEMA and result["session"]==Path(root).name and result["outcome"]==QOUT and result["binding_sha"]==binding_digest(b) and result["request_sha256"]==sha(Path(root)/"safe_quit_request.json"),"QUIT_RESULT_BINDING")
        require(result["worker_exit_codes"]==[0,0] and all(type(x) is int for x in result["worker_exit_codes"]) and result["worker_pids"]==[workers[w]["worker_pid"] for w in "AB"] and result["results"]==expected_rows,"QUIT_RESULT_OR_EXIT")
        cleanup=result["process_cleanup"]
        require(isinstance(cleanup,dict) and set(cleanup)=={"status","observed_at","residual_related","unattributed_browser_or_driver"} and cleanup["status"]=="PASS" and cleanup["residual_related"]==[] and cleanup["unattributed_browser_or_driver"]==[],"QUIT_FINAL_PROCESS_PROOF")
        require(datetime.fromisoformat(cleanup["observed_at"]).tzinfo is not None,"QUIT_FINAL_PROCESS_TIME")
        require(value["owner_intent"]==dict(kind="DURABLE_OWNER_Q",request_sha256=sha(Path(root)/"safe_quit_request.json")),"QUIT_INTENT")
        if commit is not False:
            require(isinstance(commit,dict) and set(commit)=={"schema","session","outcome","receipt_sha256","committed_at"},"QUIT_COMMIT_REQUIRED")
            require(commit["schema"]==SCHEMA and commit["session"]==Path(root).name and commit["outcome"]==QOUT and commit["receipt_sha256"]==digest(value),"QUIT_COMMIT_BINDING")
    else:raise ValueError("QUIT_OUTCOME")
    return dict(session=Path(root).name,outcome=value["outcome"],normal_closed=False,continuation_allowed=False)
def verified_closeout_for(state,root,c=None):
    state,root=plain(state),plain(root)
    require(root.parent==state,"QUIT_STATE_SCOPE")
    path=state/"non_success_closeouts"/(root.name+".json")
    if not path.exists():return None
    c=c or config();v=rc.read(path)
    commit_path=path.with_name(root.name+".commit.json")
    commit=rc.read(commit_path) if commit_path.exists() else None
    return validate_receipt(v,root,c,commit)
def append_existing_abort(state,root,received_clause,c=None):
    c=c or config(); legacy=c["existing_abort_recovery"]
    require(received_clause==legacy["owner_clause_raw"] and hashlib.sha256(received_clause.encode("utf-8")).hexdigest().upper()==legacy["owner_clause_sha256"],"LEGACY_EXACT_APPROVAL_REQUIRED")
    value=_receipt(root,AOUT,c,dict(kind="EXACT_OWNER_RECOVERY_CLAUSE",raw_sha256=legacy["owner_clause_sha256"]))
    validate_receipt(value,root,c)
    path=Path(state)/"non_success_closeouts"/(Path(root).name+".json")
    if path.exists():
        require(path.read_bytes()==canonical(value),"QUIT_CONFLICTING_RECEIPT")
        return value
    publish(path,value)
    require(path.read_bytes()==canonical(value),"QUIT_RECEIPT_BYTES_CHANGED")
    return value

def append_q_failure_abort(state,root,c=None):
    c=c or config();recovery=c["q_failure_recovery"]
    state,root=plain(state),plain(root)
    require(root.parent==state and root.name==recovery["session"],"Q_FAILURE_SESSION")
    lock=state/"execution.lock"
    require(sha(lock)==recovery["lock_sha256"] and rc.read(lock)["session"]==root.name,"Q_FAILURE_LOCK")
    proof=q_failure_process_check(root,recovery)
    value=_receipt(root,AOUT,c,dict(kind="OWNER_DIRECT_Q_FAILURE_RECOVERY",
                                    lock_sha256=recovery["lock_sha256"],process_check=proof))
    validate_receipt(value,root,c)
    path=state/"non_success_closeouts"/(root.name+".json")
    require(not path.exists(),"Q_FAILURE_RECEIPT_CONFLICT")
    publish(path,value)
    require(path.read_bytes()==canonical(value),"QUIT_RECEIPT_BYTES_CHANGED")
    verified_closeout_for(state,root,c)
    return value
def complete_quit(root,binding,processes,lock,owner_lock_bytes,close_lease,c=None):
    root,lock=plain(root),plain(lock);c=c or config()
    require(len(processes)==2,"QUIT_PROCESS_COUNT")
    require(all(p.pid and not p.is_alive() and p.exitcode==0 for p in processes),"QUIT_WORKER_EXIT")
    a,b,workers=_q_evidence(root);require(b==binding,"QUIT_FINAL_BINDING")
    require([p.pid for p in processes]==[workers[w]["worker_pid"] for w in "AB"],"QUIT_PROCESS_BINDING")
    final_process_proof=post_cleanup_check(workers)
    result=dict(schema=SCHEMA,session=root.name,outcome=QOUT,binding_sha=binding_digest(b),
      request_sha256=sha(root/"safe_quit_request.json"),worker_exit_codes=[p.exitcode for p in processes],
      worker_pids=[p.pid for p in processes],process_cleanup=final_process_proof,
      results=[dict(worker=e["worker"],request=e["request_id"],lesson=e["lesson"],final_result="NOT_STARTED",attempts=0,attempt_records=[]) for e in a["entries"]],created_at=stamp())
    publish(root/"safe_quit_result.json",result)
    value=_receipt(root,QOUT,c,dict(kind="DURABLE_OWNER_Q",request_sha256=sha(root/"safe_quit_request.json")))
    validate_receipt(value,root,c,False)
    receipt_path=root.parent/"non_success_closeouts"/(root.name+".json")
    require(receipt_path.parent.is_dir(),"QUIT_RECEIPT_DIRECTORY")
    publish(receipt_path,value)
    require(receipt_path.read_bytes()==canonical(value),"QUIT_RECEIPT_BYTES_CHANGED")
    validate_receipt(rc.read(receipt_path),root,c,False)
    require(lock.read_bytes()==owner_lock_bytes and rc.read(lock)["session"]==root.name,"QUIT_LOCK_OWNERSHIP")
    close_lease()
    require(lock.read_bytes()==owner_lock_bytes and rc.read(lock)["session"]==root.name,"QUIT_LOCK_CHANGED")
    lock.unlink()
    commit=dict(schema=SCHEMA,session=root.name,outcome=QOUT,receipt_sha256=digest(value),committed_at=stamp())
    publish(receipt_path.with_name(root.name+".commit.json"),commit)
    verified_closeout_for(root.parent,root,c)
    return result
def display_summary(root,c=None):
    root=plain(root);verified=verified_closeout_for(root.parent,root,c)
    require(verified and verified["outcome"]==QOUT,"QUIT_SUMMARY_TERMINAL_REQUIRED")
    a,b=base_evidence(root);result=rc.read(root/"safe_quit_result.json")
    rows=[dict(Worker=r["worker"],Request=r["request"],Lesson=r["lesson"],Result="NOT_STARTED / SAFE QUIT",
       Position="-",Attempts=0,Submit=0,Review=False) for r in result["results"]]
    return dict(Month=b["configuration"]["month"],Total=len(rows),Rows=rows,
       Counts=dict(CONFIRMED=0,ALREADY_RESERVED=0,FAILED_FINAL=0,Review=0,Submit=0),
       Safety="N/A",Result="SAFE QUIT / NO HUMAN GO / NO SUBMIT",EvidencePath=str(root))
def cli():
    p=argparse.ArgumentParser();p.add_argument("--summary",required=True);a=p.parse_args()
    current=Path(__file__).resolve().parents[1]
    require(current==Path(r"C:\Users\Takashi\OneDrive\Desktop\Lesson_Reservation\current"),"QUIT_SUMMARY_FIXED_CURRENT")
    state=current.parent/"runtime/reservation_journal/schema-v2/cla1-request-local-v1"
    root=plain(a.summary);require(root.parent==state,"QUIT_SUMMARY_FIXED_STATE")
    print(json.dumps(display_summary(root),ensure_ascii=True))
if __name__=="__main__":cli()
