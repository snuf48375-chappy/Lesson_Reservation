"""Read-only predecessor admission for the new request-local namespace."""
from pathlib import Path
import hashlib
import retry_continuation as rc
from runtime_config import digest as binding_digest

def scan(root, binding, entries, execution='NEW'):
    # A fresh launcher admission is intentional NEW. An unfinished predecessor
    # still requires continuation regardless of the requested mode.
    rc.require(execution in ('NEW','CONTINUATION'), 'EXECUTION_MODE')
    root=Path(root)
    directories=sorted(root.iterdir()) if root.exists() else []
    # Only the latest session is the requested continuation source. Ancestor
    # supplemental resolutions remain verified, never reclassified CLOSED.
    continuation_source=None
    if execution=='CONTINUATION':
        heads=[]
        for d in directories:
            if d.name=='execution.lock':
                continue
            rc.require(d.is_dir() and len(d.name)==32 and all(c in '0123456789abcdef' for c in d.name), 'UNKNOWN_EXECUTION_ARTIFACT')
            ordinal=rc.read(d/'admission.json')['ordinal']
            rc.require(type(ordinal) is int and ordinal>0, 'CONTINUATION_FORK_OR_GAP')
            heads.append((ordinal,d.name))
        continuation_source=max(heads)[1] if heads else None
        rc.require(continuation_source!='ab7feed24d2440dcb37c4e054ecd473e', 'AB7_CONTINUATION_FORBIDDEN')
    records=[]
    for directory in directories:
        if directory.name=='execution.lock':
            continue
        rc.require(directory.is_dir() and len(directory.name)==32 and all(c in '0123456789abcdef' for c in directory.name), 'UNKNOWN_EXECUTION_ARTIFACT')
        history_mode='NEW' if execution=='CONTINUATION' and directory.name!=continuation_source else execution
        admission=rc.read(directory/'admission.json')
        previous_binding=admission['binding']
        rc.require(admission['schema']==rc.SCHEMA and admission['session']==directory.name, 'HISTORICAL_ADMISSION_BINDING')
        from admission_control import entries as bound_entries
        old_entries=bound_entries(previous_binding)
        rc.require(admission['entries']==old_entries, 'HISTORICAL_ADMISSION_BINDING')
        historical=[]
        for worker in ('A','B'):
            rows=[e for e in old_entries if e['worker']==worker]
            for e,key in zip(rows,previous_binding['request_keys'][worker]):
                rc.require(e['date']==key[0], 'HISTORICAL_ADMISSION_BINDING')
                if 'start_time' in e:
                    rc.require(len(key)==3 and e['start_time']==key[1], 'HISTORICAL_ADMISSION_BINDING')
                    historical.append(dict(e,canonical_lesson=key[2]))
                else:
                    rc.require(len(key)==2, 'HISTORICAL_ADMISSION_BINDING')
                    historical.append(dict(e,canonical_lesson=key[1]))
        rc.require(rc.read(directory/'consumed.json')==dict(session=directory.name,binding_sha=binding_digest(previous_binding)), 'INCOMPLETE_ADMISSION')
        rc.require({p.name for p in (directory/'request_attempts').iterdir()}=={'A','B'}, 'UNKNOWN_WORKER_JOURNAL')
        journals={}; summaries={}
        for worker in ('A','B'):
            journal=rc.Journal(directory/'request_attempts'/worker,worker,[e for e in historical if e['worker']==worker],previous_binding,directory.name)
            events=journal.events()
            rc.require(events and events[0]['event_type']=='REGISTER', 'REGISTRATION_INCOMPLETE')
            # Only the pinned incident may defer restart assessment until its
            # independent seal has been validated below. CONTINUATION never does.
            if not (directory.name in ('3851e654c248413cbaf8b2e1dec17099','1926b84080a7467b80866f14169cdeba','ab7feed24d2440dcb37c4e054ecd473e') and history_mode=='NEW'):
                rc.restart_assessment([journal])
            journals[worker]=events
            summaries[worker]=journal.summary()
        if any(e['event_type']=='ATTEMPT_BEGIN' for events in journals.values() for e in events):
            from admission_control import GO_SEMANTIC
            go=rc.read(directory/'human_go.json')
            rc.require(go.get('semantic')==GO_SEMANTIC and go.get('binding_sha')==binding_digest(previous_binding), 'HISTORICAL_GO_BINDING')
            for worker in ('A','B'):
                rc.require(rc.read(directory/f'claim-{worker}.json')==dict(session=directory.name,worker=worker), 'HISTORICAL_WORKER_CLAIM')
                rc.require(rc.read(directory/f'login-{worker}.json')==dict(code='OK',state='LOGINED'), 'HISTORICAL_WORKER_LOGIN')
        known={'admission.json','consumed.json','human_go.json','finished.json','results.json','operational_timing.json','request_attempts','native_logs'}
        known.update(f'{prefix}-{w}.json' for prefix in ('claim','login','worker') for w in ('A','B'))
        rc.require(all(p.name in known for p in directory.iterdir()),'UNKNOWN_EXECUTION_ARTIFACT')
        files={p.relative_to(directory).as_posix():hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in directory.rglob('*.json') if 'native_logs' not in p.parts}
        # finished.json is also written after failures: require independent
        # worker completion, zero exit codes and exact reconstructed results.
        closed=False
        if all((directory/name).is_file() for name in ('finished.json','results.json','worker-A.json','worker-B.json')):
            results=rc.read(directory/'results.json')
            expected=[dict(row,worker=w) for w in ('A','B') for row in summaries[w]['requests']]
            actual=results.get('results',[])
            closed=(rc.read(directory/'finished.json').get('lifecycle')=='CONSUMED_NO_RESTART'
                and all(rc.read(directory/f'worker-{w}.json')==dict(status='COMPLETED') and summaries[w]['runtime']=='COMPLETED' for w in ('A','B'))
                and results.get('worker_exit_codes')==[0,0]
                and sorted(actual,key=lambda r:(r['worker'],r['request']))==sorted(expected,key=lambda r:(r['worker'],r['request'])))
        logical_resolved=False
        if directory.name=='3851e654c248413cbaf8b2e1dec17099' and history_mode=='NEW':
            import resolution_evidence
            logical_resolved=resolution_evidence.resolved(root,directory)
            rc.require(logical_resolved, '3851_ACTIVE_UNRESOLVED_BLOCKER')
        if directory.name=='1926b84080a7467b80866f14169cdeba' and history_mode=='NEW':
            import manual_1926
            logical_resolved=manual_1926.resolved(root,directory)
            rc.require(logical_resolved, '1926_ACTIVE_UNRESOLVED_BLOCKER')
        if directory.name=='ab7feed24d2440dcb37c4e054ecd473e' and history_mode=='NEW':
            import manual_ab7feed
            logical_resolved=manual_ab7feed.resolved(root,directory)
            rc.require(logical_resolved, 'AB7_ACTIVE_UNRESOLVED_BLOCKER')
        records.append(dict(session=directory.name,ordinal=admission['ordinal'],previous=admission['previous_run'],events=journals,files=files,sha=rc.digest(files),binding=previous_binding,entries=historical,closed=closed,logical_resolved=logical_resolved))
    records.sort(key=lambda r:r['ordinal'])
    previous=None
    resolved={r['session'] for r in records if r['logical_resolved']}
    for n,row in enumerate(records,1):
        rc.require(type(row['ordinal']) is int and row['ordinal']==n, 'CONTINUATION_FORK_OR_GAP')
        if n>1 and row['previous'] is None:
            rc.require(records[n-2]['closed'] or records[n-2]['logical_resolved'], 'CONTINUATION_FORK_OR_GAP')
            rc.require(not any(e['event_type']=='CONTINUATION' for es in row['events'].values() for e in es), 'PREDECESSOR_CHANGED')
            _nonoverlap(row['entries'],records[:n-1],resolved)
        else:
            rc.require(row['previous']==previous, 'CONTINUATION_FORK_OR_GAP')
        if row['previous'] is not None:
            prior=records[n-2]
            rc.require(prior['session']!='ab7feed24d2440dcb37c4e054ecd473e', 'AB7_CONTINUATION_FORBIDDEN')
            rc.require(row['entries']==prior['entries'] and (prior['closed'] or row['binding']==prior['binding']), 'CONTINUATION_REQUEST_BINDING_CHANGED')
            for worker in ('A','B'):
                imports=[e for e in row['events'][worker] if e['event_type']=='CONTINUATION']
                rc.require(len(imports)==1 and imports[0]['payload']['source_session']==prior['session'] and imports[0]['payload']['source_sha']==prior['sha'] and imports[0]['payload']['events']==prior['events'][worker], 'PREDECESSOR_CHANGED')
                if 'execution_mode' in imports[0]['payload']:
                    payload=imports[0]['payload']
                    rc.require(prior['closed'] and payload['source_session']==prior['session'], 'FRESH_PREDECESSOR_NOT_CLOSED')
                    expected=_fresh_requests(prior,worker)
                    rc.require(expected and payload.get('fresh_requests')==expected, 'FRESH_REQUEST_SET')
            # A mixed worker pair must apply the same execution boundary rule.
            if any(e['event_type']=='CONTINUATION' and 'execution_mode' in e['payload'] for es in row['events'].values() for e in es):
                for worker in ('A','B'):
                    fresh=any(e['event_type']=='CONTINUATION' and 'execution_mode' in e['payload'] for e in row['events'][worker])
                    rc.require(fresh==bool(_fresh_requests(prior,worker)), 'FRESH_WORKER_BOUNDARY_MISMATCH')
        if row['closed']:
            # A verified terminal continuation completes the same obligation.
            # Keep each ancestor's historical closed flag and files unchanged.
            cursor=row
            while cursor['previous'] is not None:
                prior=records[cursor['ordinal']-2]
                if (cursor['binding']!=prior['binding'] or cursor['entries']!=prior['entries']
                    or any(e['event_type']=='CONTINUATION' and 'execution_mode' in e['payload']
                           for es in cursor['events'].values() for e in es)):
                    break  # Never cross an independent/fresh execution boundary.
                resolved.add(prior['session'])
                cursor=prior
        previous=row['session']
    latest=records[-1] if records else None
    if latest:
        same=latest['binding']==binding and latest['entries']==entries
        if execution=='CONTINUATION' or not (latest['closed'] or latest['logical_resolved']):
            rc.require(same, 'CONTINUATION_REQUEST_BINDING_CHANGED')
        else:
            # Intentional NEW after verified CLOSED history always evaluates
            # current Production state; historical results are evidence only.
            _nonoverlap(entries,records,resolved)
            previous=latest=None
    return dict(ordinal=len(records)+1,previous_run=previous,predecessor=latest)


def _nonoverlap(entries,records,resolved=()):
    from lesson_target import canonical_name
    key=lambda e:(e['worker'],e['date'],canonical_name(e['canonical_lesson'],lambda value:value))
    keys={key(e) for e in entries}
    rc.require(all(keys.isdisjoint(key(e) for e in row['entries']) for row in records if not row['closed'] and row['session'] not in resolved), 'HISTORICAL_REQUEST_OVERLAP')

def _fresh_requests(record,worker):
    rows,_,_=rc.reduce_events(record['events'][worker],[e for e in record['entries'] if e['worker']==worker])
    return rc.fresh_request_ids(rows)

def restore(journal, predecessor):
    if predecessor:
        rc.require(predecessor['session']!='ab7feed24d2440dcb37c4e054ecd473e', 'AB7_CONTINUATION_FORBIDDEN')
        payload=dict(source_session=predecessor['session'],source_sha=predecessor['sha'],events=predecessor['events'][journal.alias])
        fresh=[rid for rid in predecessor.get('fresh_requests',[]) if rid in {e['request_id'] for e in journal.entries}]
        if fresh:
            rc.require(predecessor['closed'] and fresh==_fresh_requests(predecessor,journal.alias), 'FRESH_SAFE_PROVENANCE_REQUIRED')
            payload.update(execution_mode='NEW',authority='SFF-NEW-20260924-01',fresh_requests=fresh)
        # Preserve the pre-GO registration envelope; NEW metadata changes only
        # request reconstruction, not Human GO/Barrier or reservation flow.
        journal.append('CONTINUATION',payload)
