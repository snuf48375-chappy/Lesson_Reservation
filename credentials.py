"""Current-token Windows Credential Manager, exact per-worker reference only.

No enumeration, browser extraction, environment fallback, or source-password use.
Credential material is never included in repr, errors, or returned evidence.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
import logging
import contextlib
from contextlib import contextmanager
from dataclasses import dataclass
from runtime_config import require


@dataclass(frozen=True, repr=False)
class Binding:
    worker: str
    username: str
    member: str

    def __repr__(self):
        return 'CredentialBinding(<redacted>)'

    @property
    def target(self):
        require(self.worker in ('A', 'B') and bool(self.username)
                and len(self.member) == 12 and self.member.isascii()
                and self.member.isdigit(), 'CREDENTIAL_BINDING_INVALID')
        # Hash identifies the NONSECRET identity tuple; never hashes a password.
        identity = json.dumps([self.worker, self.username, self.member], ensure_ascii=True)
        return 'LessonReservation/StageC/' + self.worker + '/' + hashlib.sha256(identity.encode()).hexdigest()


def binding_for(module, alias, user):
    require(alias in ('A', 'B'), 'CREDENTIAL_WORKER_INVALID')
    fixed = module._FIXED_USER_SETTINGS[0 if alias == 'A' else 1]
    member = module._cla1_identity_bindings().get(fixed['username'])
    require(user['username'] == fixed['username'] and member
            and user.get('expected_member_identifier') == member, 'CREDENTIAL_CROSS_WORKER')
    return Binding(alias, fixed['username'], member)


class Credential(C.Structure):
    _fields_ = [('Flags', W.DWORD), ('Type', W.DWORD), ('TargetName', W.LPWSTR),
                ('Comment', W.LPWSTR), ('LastWritten', W.FILETIME),
                ('CredentialBlobSize', W.DWORD), ('CredentialBlob', C.POINTER(C.c_ubyte)),
                ('Persist', W.DWORD), ('AttributeCount', W.DWORD),
                ('Attributes', C.c_void_p), ('TargetAlias', W.LPWSTR), ('UserName', W.LPWSTR)]


class WindowsCredentials:
    def __init__(self):
        require(os.name == 'nt', 'WINDOWS_CREDENTIALS_REQUIRED')
        self.api = C.WinDLL('Advapi32.dll', use_last_error=True)
        self.api.CredReadW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, C.POINTER(C.POINTER(Credential))]
        self.api.CredReadW.restype = W.BOOL
        self.api.CredFree.argtypes = [C.c_void_p]
        self.api.CredFree.restype = None
        self.api.CredWriteW.argtypes = [C.POINTER(Credential), W.DWORD]
        self.api.CredWriteW.restype = W.BOOL

    @contextmanager
    def open(self, binding, reference=None):
        target = binding.target
        require(reference is None or reference == target, 'CREDENTIAL_REFERENCE_MISMATCH')
        pointer = C.POINTER(Credential)()
        require(self.api.CredReadW(target, 1, 0, C.byref(pointer)), 'CREDENTIAL_UNAVAILABLE')
        try:
            entry = pointer.contents
            require(entry.Type == 1 and entry.TargetName == target
                    and entry.UserName == binding.username and entry.Persist == 2
                    and entry.AttributeCount == 0, 'CREDENTIAL_ENTRY_BINDING')
            require(0 < entry.CredentialBlobSize <= 2560 and entry.CredentialBlobSize % 2 == 0,
                    'CREDENTIAL_MATERIAL_INVALID')
            # Native buffer stays owned here and is scrubbed even on failure.
            yield entry
        finally:
            entry = pointer.contents
            if entry.CredentialBlob and entry.CredentialBlobSize:
                C.memset(entry.CredentialBlob, 0, entry.CredentialBlobSize)
            self.api.CredFree(pointer)

    def validate(self, binding, reference=None):
        with self.open(binding, reference):
            return dict(present=True, binding='PASS', access_control='CURRENT_TOKEN_LOCAL_MACHINE')

    def fill(self, binding, username_field, password_field, reference=None):
        # Selenium/urllib3 debug logs can include send_keys command bodies.
        previous = logging.root.manager.disable
        try:
            logging.disable(logging.CRITICAL)
            with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                self._fill(binding, username_field, password_field, reference)
        except Exception as exc:
            observation = getattr(self, 'observation', None)
            if observation:
                if observation.active == 'CREDENTIAL_RUNTIME_RETRIEVAL':
                    observation.data['credential']['runtime_retrieval'] = 'FAILURE'
                observation.fail(exc)
            raise ValueError('CREDENTIAL_FILL_FAILED') from None
        finally:
            logging.disable(previous)

    def _fill(self, binding, username_field, password_field, reference=None):
        observation = getattr(self, 'observation', None)
        with self.open(binding, reference) as entry:
            secret = None
            try:
                secret = C.string_at(entry.CredentialBlob, entry.CredentialBlobSize).decode('utf-16-le')
                require(bool(secret) and '\x00' not in secret, 'CREDENTIAL_MATERIAL_INVALID')
                if observation:
                    observation.data['credential']['runtime_retrieval'] = 'SUCCESS'
                    observation.done('CREDENTIAL_RUNTIME_RETRIEVAL')
                    observation.start('USERNAME_INPUT_COMPLETE', 'USERNAME_INPUT_FAILED')
                username_field.clear()
                if observation: observation.start('PASSWORD_INPUT_COMPLETE', 'PASSWORD_INPUT_FAILED')
                password_field.clear()
                if observation: observation.start('USERNAME_INPUT_COMPLETE', 'USERNAME_INPUT_FAILED')
                username_field.send_keys(binding.username)
                if observation:
                    observation.data['username_input_complete'] = True
                    observation.done('USERNAME_INPUT_COMPLETE')
                    observation.start('PASSWORD_INPUT_COMPLETE', 'PASSWORD_INPUT_FAILED')
                password_field.send_keys(secret)
                if observation:
                    observation.data['password_input_complete'] = True
                    observation.done('PASSWORD_INPUT_COMPLETE')
            except Exception as exc:
                if observation: observation.fail(exc)
                raise ValueError('CREDENTIAL_FILL_FAILED') from None
            finally:
                secret = None  # Python/Selenium transient copies cannot be guaranteed zeroized.

    def enroll(self, binding, secret):
        """Owner-only interactive provisioning; refuses to overwrite an entry."""
        pointer = C.POINTER(Credential)()
        if self.api.CredReadW(binding.target, 1, 0, C.byref(pointer)):
            entry = pointer.contents
            if entry.CredentialBlob and entry.CredentialBlobSize:
                C.memset(entry.CredentialBlob, 0, entry.CredentialBlobSize)
            self.api.CredFree(pointer)
            raise ValueError('CREDENTIAL_ALREADY_PRESENT')
        require(C.get_last_error() == 1168, 'CREDENTIAL_STORE_UNAVAILABLE')
        require(isinstance(secret, str) and bool(secret) and '\x00' not in secret, 'CREDENTIAL_MATERIAL_INVALID')
        size = len(secret.encode('utf-16-le'))
        require(size <= 2560, 'CREDENTIAL_MATERIAL_INVALID')
        buffer = C.create_unicode_buffer(secret)
        entry = Credential()
        entry.Type, entry.TargetName, entry.UserName, entry.Persist = 1, binding.target, binding.username, 2
        entry.CredentialBlobSize = size
        entry.CredentialBlob = C.cast(buffer, C.POINTER(C.c_ubyte))
        try:
            require(self.api.CredWriteW(C.byref(entry), 0), 'CREDENTIAL_STORE_FAILED')
        finally:
            C.memset(buffer, 0, C.sizeof(buffer))
