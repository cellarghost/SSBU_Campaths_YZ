import ctypes
from ctypes import wintypes
import pymem.ressources.kernel32 as k32
from capstone import *

# windows constants
PAGE_READWRITE = 0x04
PAGE_EXECUTE_READWRITE = 0x40
MEM_COMMIT = 0x1000
MEM_MAPPED = 0x40000
MEM_PRIVATE = 0x20000

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


def aob_scan(pm, pattern: bytes):
    process_handle = pm.process_handle
    address = 0
    mbi = MEMORY_BASIC_INFORMATION()
    print("Scanning for AOBs...")
    while ctypes.windll.kernel32.VirtualQueryEx(
        process_handle,
        ctypes.c_void_p(address),
        ctypes.byref(mbi),
        ctypes.sizeof(mbi)
    ):
        if mbi.State == MEM_COMMIT and mbi.Protect in [PAGE_READWRITE, PAGE_EXECUTE_READWRITE]:
            try:
                buffer = pm.read_bytes(mbi.BaseAddress, mbi.RegionSize)
                offset = buffer.find(pattern)
                if offset != -1:
                    return mbi.BaseAddress + offset
            except:
                pass  # ignore unreadable regions

        address += mbi.RegionSize
    return None