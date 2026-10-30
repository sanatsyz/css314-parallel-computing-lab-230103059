"""Build transparent C hot loops; Python owns arrays, timing and verification."""
import ctypes
import hashlib
import os
from pathlib import Path
import platform
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "native" / "locality.c"
FLAGS = ["-O3", "-std=c11", "-fno-fast-math", "-ffp-contract=off", "-shared", "-fPIC"]


def load_library():
    compiler = shlex.split(os.environ.get("CC", "cc"))
    version = subprocess.run(compiler + ["--version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    key = hashlib.sha256(SOURCE.read_bytes() + repr((FLAGS, version, platform.machine())).encode()).hexdigest()[:16]
    cache = ROOT / ".native-cache"
    cache.mkdir(exist_ok=True)
    target = cache / ("locality-" + key + (".dylib" if platform.system() == "Darwin" else ".so"))
    if not target.exists():
        subprocess.run(compiler + FLAGS + [str(SOURCE), "-o", str(target)], check=True)
    lib = ctypes.CDLL(str(target))
    pointer = ctypes.POINTER(ctypes.c_double)
    lib.stride_sum.argtypes = [pointer, ctypes.c_size_t, ctypes.c_size_t]
    lib.stride_sum.restype = ctypes.c_double
    for name in ["matmul_ijk", "matmul_ikj"]:
        fn = getattr(lib, name)
        fn.argtypes = [pointer, pointer, pointer, ctypes.c_size_t]
        fn.restype = None
    return lib, {"compiler": version, "flags": FLAGS,
                 "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest()}


def pointer(array):
    return array.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
