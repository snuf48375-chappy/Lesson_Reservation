"""Small GO boundary: pinned inputs, current admission/claims, no prior-history replay."""
from pathlib import Path
import runtime as rt
from runtime_config import require
from admission_control import GO_SEMANTIC


class FinalGuard:
    def __init__(self, store, binding, root, lease, inventory):
        self.store, self.root, self.lease = store, Path(root), lease
        self.inventory = inventory
        self.prepared = False

    def prepare(self):
        self.lease.require_open()
        self.lease.add(self.root / n for n in ('admission.json', 'consumed.json',
            'claim-A.json', 'claim-B.json', 'login-A.json', 'login-B.json'))
        self.store.validate_admission()
        if self.store.snapshot().get('schema') == 'CLA1_REQUEST_LOCAL_V1':
            for w in ('A', 'B'):
                rows, _, registered = self.store.retry_journal(w).view()
                events=self.store.retry_journal(w).events()
                require(registered and [e['event_type'] for e in events] in (['REGISTER'],['REGISTER','CONTINUATION']), 'REGISTRATION_REQUIRED')
            self.lease.add((self.root / 'request_attempts').rglob('*.json'))
        self.check_current()
        self.prepared = True

    def check_current(self):
        session = self.root.name
        require(rt.read(self.root.parent / 'execution.lock')['session'] == session, 'EXCLUSIVE_LOCK_LOST')
        require(rt.read(self.root / 'consumed.json') == dict(session=session,
            binding_sha=self.store.binding_sha), 'ADMISSION_CONSUMPTION_CHANGED')
        for w in ('A', 'B'):
            require(rt.read(self.root / ('claim-' + w + '.json')) == dict(session=session, worker=w), 'WORKER_CLAIM_CHANGED')
            require(rt.read(self.root / ('login-' + w + '.json')) == dict(code='OK', state='LOGINED'), 'WORKER_NOT_READY')
        require(not (self.root / 'human_go.json').exists() and not (self.root / 'finished.json').exists(), 'GO_ALREADY_USED')
        require(not list(self.root.glob('A-*.json')) and not list(self.root.glob('B-*.json')), 'PRE_GO_JOURNAL_ACTION')

    def check(self):
        require(self.prepared, 'BOTH_READY_REQUIRED')
        self.lease.require_open()
        self.check_current()
        require(rt.journal_inventory(exclude=self.root) == self.inventory, 'HISTORY_INVENTORY_CHANGED')

    def record(self, value):
        require(self.prepared and value.get('semantic') == GO_SEMANTIC, 'HUMAN_GO_SEMANTIC')
        # The only Owner authorization record is created by the interactive GO
        # callback, after final checks and before the second Barrier release.
        import json, os
        # Keep the historical semantic token for existing Journal readers.
        # Current GO attests List execution approval, never reservation absence.
        payload = dict(value, binding_sha=self.store.binding_sha,
                      approval_semantic='OWNER_CURRENT_LIST_EXECUTION_APPROVAL',
                      session=self.root.name,
                      approved_requests=[e['request_id'] for e in self.store.all_entries()])
        with (self.root / 'human_go.json').open('x', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, sort_keys=True)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        self.lease.add([self.root / 'human_go.json'])
