"""Local-only capability probes. No browser, authorization or run creation."""
import ctypes
import os
import stat
import sys
import time
import uuid
from pathlib import Path
from runtime_config import require
from credentials import WindowsCredentials, binding_for
from frozen_inputs import FrozenInputs


def environment(module, verify_versions):
    verify_versions()
    require(os.name == 'nt' and not ctypes.windll.shell32.IsUserAnAdmin(),
            'STANDARD_WINDOWS_USER_REQUIRED')
    require(module.webdriver is not None and module.jaconv is not None,
            'NATIVE_DEPENDENCIES_REQUIRED')
    require(sys.stdin.isatty(), 'INTERACTIVE_OWNER_CONSOLE_REQUIRED')


def credentials(module):
    for alias, user in zip(('A', 'B'), module.users):
        binding = binding_for(module, alias, user)
        # Same native read/binding validation as Live; never return secret material.
        with WindowsCredentials().open(binding) as entry:
            secret = None
            try:
                secret = ctypes.string_at(entry.CredentialBlob, entry.CredentialBlobSize).decode('utf-16-le')
                require(bool(secret) and '\x00' not in secret, 'CREDENTIAL_MATERIAL_INVALID')
            except Exception:
                raise ValueError('LOCAL_CREDENTIAL_MATERIAL_INVALID') from None
            finally:
                secret = None


def executable_structure(path):
    """Read-only Windows image/access checks; never load or execute the image."""
    from ctypes import wintypes
    path = Path(path)
    require(path.is_file(), 'LOCAL_EXECUTABLE_NOT_REGULAR_FILE')
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                               ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    api.CreateFileW.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    api.GetBinaryTypeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    api.GetBinaryTypeW.restype = wintypes.BOOL
    # GENERIC_READ | GENERIC_EXECUTE, share read/write/delete, OPEN_EXISTING.
    # No exclusive lease, process, profile or persistent artifact is acquired.
    handle = api.CreateFileW(str(path), 0xA0000000, 7, None, 3, 0, None)
    require(handle != ctypes.c_void_p(-1).value, 'LOCAL_EXECUTABLE_ACCESS_DENIED')
    try:
        kind = wintypes.DWORD()
        require(bool(api.GetBinaryTypeW(str(path), ctypes.byref(kind))),
                'LOCAL_EXECUTABLE_INVALID_IMAGE')
        require(kind.value in (0, 6), 'LOCAL_EXECUTABLE_NOT_WIN32_OR_WIN64')
    finally:
        require(bool(api.CloseHandle(handle)), 'LOCAL_EXECUTABLE_HANDLE_CLOSE_FAILED')


def selenium_manager():
    # Live uses an explicit verified Service, so neither PATH nor
    # SE_CHROMEDRIVER is allowed to select its driver.
    require(not os.getenv('SE_MANAGER_PATH'), 'CLA1_SELENIUM_MANAGER_OVERRIDE')
    from selenium.webdriver.common.selenium_manager import SeleniumManager
    path = SeleniumManager._get_binary()
    executable_structure(path)
    return {'route': 'bundled SeleniumManager', 'executable': str(Path(path).absolute())}


def profile_structure(module):
    require(len(module.users) == len(module._FIXED_USER_SETTINGS) == 2,
            'LOCAL_PROFILE_IDENTITY_COUNT')
    paths = []
    for user, fixed in zip(module.users, module._FIXED_USER_SETTINGS):
        require(user['profile_path'] == fixed['profile_path'], 'LOCAL_PROFILE_IDENTITY_MISMATCH')
        path = Path(user['profile_path'])
        # Traverse lexical ancestors first: resolving first can hide file/.. conflicts.
        for ancestor in reversed((path, *path.parents)):
            try:
                ancestor.lstat()
            except FileNotFoundError:
                continue
            require(stat.S_ISDIR(ancestor.stat().st_mode), 'LOCAL_PROFILE_NOT_DIRECTORY')
        paths.append(path.resolve())
    require(os.path.normcase(str(paths[0])) != os.path.normcase(str(paths[1])),
            'LOCAL_PROFILE_NOT_DISTINCT')
    return dict(zip(('A', 'B'), map(str, paths)))


def write_capability(state, publish):
    state = Path(state)
    require(state.is_dir(), 'LOCAL_RUNTIME_DIRECTORY_UNAVAILABLE')
    require(not any(state.glob('.local-preflight-probe-*')), 'LOCAL_PROBE_ARTIFACT_REMAINS')
    tag = '.local-preflight-probe-' + uuid.uuid4().hex
    direct, directory = state / (tag + '.tmp'), state / tag
    child = directory / 'capability.tmp'
    owned = []
    try:
        # Exclusive creation, identical to Live publish; no run or semantic data.
        with direct.open('x', encoding='utf-8') as stream:
            owned.append(direct)
            stream.write('local capability probe\n')
            stream.flush()
            os.fsync(stream.fileno())
        directory.mkdir()
        owned.append(directory)
        # Reserve ownership before publish so partial-write failures are cleaned.
        owned.append(child)
        publish(child, {'local_capability_probe': True})
    finally:
        failed = False
        for path in reversed(owned):
            try:
                if path == directory:
                    path.rmdir()
                else:
                    path.unlink(missing_ok=True)
            except OSError:
                failed = True
        require(not failed and not any(p.exists() for p in owned), 'LOCAL_PROBE_CLEANUP_FAILED')


def read_leases(rt, adapter, binding):
    lease = FrozenInputs()
    try:
        lease.add(rt.input_paths())
        lease.require_open()
        inventory = rt.journal_inventory()
        fresh = rt.context()
        require(adapter.exact(fresh[2], binding), 'CONFIGURATION_CHANGED_BEFORE_FREEZE')
        rt.history_preflight(fresh[1])
        require(rt.journal_inventory() == inventory, 'HISTORY_CHANGED_DURING_FREEZE')
    finally:
        # Check actual native close results; even if one fails, attempt every close.
        failed = False
        for handle in lease.handles.values():
            if not lease.api.CloseHandle(handle):
                failed = True
        lease.handles.clear()
        lease.closed = True
        require(not failed, 'LOCAL_LEASE_CLEANUP_FAILED')


def run(rt, adapter, module, binding, verify_versions):
    from driver_selection import prepare_driver
    timings = {}
    checks = (
        ('ENVIRONMENT', lambda: environment(module, verify_versions)),
        ('SELENIUM_MANAGER_STRUCTURE', selenium_manager),
        ('CHROME_DRIVER_PREPARATION', prepare_driver),
        ('PROFILE_A_B_STRUCTURE', lambda: profile_structure(module)),
        ('CREDENTIAL_A_B_BINDING', lambda: credentials(module)),
        ('WRITE_CAPABILITY', lambda: write_capability(rt.STATE, adapter.publish)),
        ('READ_LEASE', lambda: read_leases(rt, adapter, binding)),
    )
    for name, check in checks:
        started = time.perf_counter()
        try:
            detail = check()
        except Exception as exc:
            # Do not propagate provider exceptions or secret-bearing diagnostics.
            reason = str(exc) if name == 'CHROME_DRIVER_PREPARATION' and str(exc).startswith('CLA1_') else 'CHECK_FAILED'
            print(name + ' = BLOCK; reason=' + reason)
            raise ValueError('LOCAL_PREFLIGHT_' + name + '_BLOCK') from None
        timings[name] = round((time.perf_counter() - started) * 1000, 3)
        print(name + ' = PASS; duration_ms=' + str(timings[name]))
        if name in ('SELENIUM_MANAGER_STRUCTURE', 'PROFILE_A_B_STRUCTURE'):
            print(name + '_IDENTITY = ' + str(detail))
    print('A CREDENTIAL = AVAILABLE; B CREDENTIAL = AVAILABLE; BINDING = PASS')
    print('CHROME_DRIVER_PROFILE_STARTUP = NOT_VERIFIED; PROFILE_SEPARATION = PASS')
    return timings
