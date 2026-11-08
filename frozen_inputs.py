"""Windows read leases: prevent writes/deletes to validated inputs through run end."""
import ctypes
import os
from pathlib import Path
from runtime_config import require


class FrozenInputs:
    def __init__(self):
        require(os.name == 'nt', 'WINDOWS_READ_LEASE_REQUIRED')
        from ctypes import wintypes
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self.api.CreateFileW.restype = wintypes.HANDLE
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        self.handles = {}; self.closed = False

    def add(self, paths):
        require(not self.closed, 'INPUT_LEASE_CLOSED')
        try:
            for value in sorted(set(map(Path, paths))):
                path = value.absolute()
                require(path.resolve() == path and path.is_file(), 'INPUT_PATH_REDIRECTED_OR_MISSING')
                if str(path) in self.handles:
                    continue
                # GENERIC_READ, FILE_SHARE_READ only, OPEN_EXISTING. An existing
                # writer is also refused; a lease cannot silently overlap it.
                handle = self.api.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
                if handle == ctypes.c_void_p(-1).value:
                    raise ctypes.WinError(ctypes.get_last_error())
                self.handles[str(path)] = handle
        except BaseException:
            self.close()
            raise

    def require_open(self):
        require(not self.closed and bool(self.handles), 'INPUT_LEASE_NOT_ACTIVE')

    def close(self):
        if not self.closed:
            for handle in self.handles.values():
                self.api.CloseHandle(handle)
            self.handles.clear(); self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
