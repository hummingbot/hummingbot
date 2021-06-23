# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.building.build_main import (
    Analysis,
    PYZ,
    EXE,
    COLLECT,
)
import os
import platform
import re
from typing import (
    List,
    Iterable,
    Tuple
)
import sys
sys.setrecursionlimit(5000)

global SPEC


def project_path() -> str:
    return os.path.realpath(f"{SPEC}/../../")


def enumerate_modules(path: str) -> Iterable[str]:
    source_re = re.compile(r"\.(py|pyx)$")
    actual_path: str = os.path.realpath(path)
    prefix_length: int = len(actual_path.split(os.sep)) - 1

    for dirpath, dirnames, filenames in os.walk(actual_path):
        pkg_components: List[str] = dirpath.split(os.sep)[prefix_length:]
        for filename in filenames:
            if filename == "__init__.py":
                yield ".".join(pkg_components)
            elif source_re.search(filename):
                module_name: str = source_re.sub("", filename)
                yield ".".join(pkg_components) + f".{module_name}"


def enumerate_data_files(path: str, pattern: str) -> Iterable[Tuple[str, str]]:
    actual_path: str = os.path.realpath(path)
    prefix_length: int = len(actual_path.split(os.sep)) - 1
    pattern_re = re.compile(pattern)

    for dirpath, dirnames, filenames in os.walk(actual_path):
        dst_path_components: List[str] = dirpath.split(os.sep)[prefix_length:]
        dst_dir: str = "/".join(dst_path_components)
        for filename in filenames:
            src_path: str = os.path.join(dirpath, filename)
            if pattern_re.search(src_path) is not None:
                yield src_path, dst_dir



if "SPEC" in globals():
    system_type: str = platform.system()
    block_cipher = None

    hidden_imports: List[str] = list(enumerate_modules(os.path.join(project_path(), "hummingbot")))
    hidden_imports.extend([
        "aiokafka",
        "pkg_resources.py2_warn",
    ])

    import _strptime

    datas: List[Tuple[str, str]] = list(enumerate_data_files(
        os.path.join(project_path(), "hummingbot"),
        r"(.+\.json|(?:\/|\\)VERSION|templates(?:\/|\\).+\.yml)$"
    ))
    datas.extend([(_strptime.__file__, ".")])
    datas.extend([(os.path.join(project_path(), "bin/path_util.py"), ".")])

    binaries: List[Tuple[str, str]] = []
    if system_type == "Windows":
       import coincurve
       binaries.extend([(os.path.realpath(os.path.join(coincurve.__file__, "../libsecp256k1.dll")), "coincurve")])
       datas.extend([(os.path.realpath(os.path.join(project_path(), "redist/VC_redist.x64.exe")), "redist")])


    a = Analysis([os.path.join(project_path(), "bin/bot")],
                 pathex=[project_path()],
                 binaries=binaries,
                 datas=datas,
                 hiddenimports=hidden_imports,
                 hookspath=[],
                 runtime_hooks=[],
                 excludes=[],
                 win_no_prefer_redirects=False,
                 win_private_assemblies=False,
                 cipher=block_cipher,
                 noarchive=False)

    pyz = PYZ(a.pure, a.zipped_data,
              cipher=block_cipher)
    exe = EXE(pyz,
              a.scripts,
              [],
	      exclude_binaries=True,
              name='bot',
              icon="hummingbot.ico",
              debug=False,
              bootloader_ignore_signals=False,
              strip=False,
              upx=True,
              console=True)
    coll = COLLECT(exe,
                    a.binaries,
                    a.zipfiles,
                    a.datas,
                    strip=False,
                    upx=True,
                    upx_exclude=[],
                    name='bot')
