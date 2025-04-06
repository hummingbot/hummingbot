
from __future__ import annotations

if False:  # MYPY
    from typing import Dict, Any  # NOQA

_package_data = dict(
    full_package_name='ruamel.yaml',
    version_info=(0, 18, 10),
    __version__='0.18.10',
    version_timestamp='2025-01-06 15:02:34',
    author='Anthon van der Neut',
    author_email='a.van.der.neut@ruamel.eu',
    description='ruamel.yaml is a YAML parser/emitter that supports roundtrip preservation of comments, seq/map flow style, and map key order',  # NOQA
    entry_points=None,
    since=2014,
    extras_require={
        ':platform_python_implementation=="CPython" and python_version<"3.13"': ['ruamel.yaml.clib>=0.2.7'],  # NOQA
        'jinja2': ['ruamel.yaml.jinja2>=0.2'],
        'docs': ['ryd', 'mercurial>5.7'],
    },
    classifiers=[
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Text Processing :: Markup',
        'Typing :: Typed',
    ],
    keywords='yaml 1.2 parser round-trip preserve quotes order config',
    url_doc='https://yaml.dev/doc/{full_package_name}',
    supported=[(3, 8)],  # minimum
    tox=dict(
        env='*',
        fl8excl='_test/lib,branch_default',
    ),
    # universal=True,
    python_requires='>=3.7',
)  # type: Dict[Any, Any]


version_info = _package_data['version_info']
__version__ = _package_data['__version__']

try:
    from .cyaml import *  # NOQA

    __with_libyaml__ = True
except (ImportError, ValueError):  # for Jython
    __with_libyaml__ = False

from ruamel.yaml.main import *  # NOQA
