# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from collections.abc import Callable

from astroid.manager import AstroidManager
from astroid.nodes.scoped_nodes import Module


def register_module_extender(
    manager: AstroidManager, module_name: str, get_extension_mod: Callable[[], Module]
) -> None:
    def transform(node: Module) -> None:
        extension_module = get_extension_mod()
        for name, objs in extension_module.locals.items():
            node.locals[name] = objs
            for obj in objs:
                if obj.parent is extension_module:
                    obj.parent = node

    manager.register_transform(Module, transform, lambda n: n.name == module_name)


# pylint: disable-next=too-many-locals
def register_all_brains(manager: AstroidManager) -> None:
    from astroid.brain import (  # pylint: disable=import-outside-toplevel
        brain_argparse,
        brain_attrs,
        brain_boto3,
        brain_builtin_inference,
        brain_collections,
        brain_crypt,
        brain_ctypes,
        brain_curses,
        brain_dataclasses,
        brain_datetime,
        brain_dateutil,
        brain_functools,
        brain_gi,
        brain_hashlib,
        brain_http,
        brain_hypothesis,
        brain_io,
        brain_mechanize,
        brain_multiprocessing,
        brain_namedtuple_enum,
        brain_nose,
        brain_numpy_core_einsumfunc,
        brain_numpy_core_fromnumeric,
        brain_numpy_core_function_base,
        brain_numpy_core_multiarray,
        brain_numpy_core_numeric,
        brain_numpy_core_numerictypes,
        brain_numpy_core_umath,
        brain_numpy_ma,
        brain_numpy_ndarray,
        brain_numpy_random_mtrand,
        brain_pathlib,
        brain_pkg_resources,
        brain_pytest,
        brain_qt,
        brain_random,
        brain_re,
        brain_regex,
        brain_responses,
        brain_scipy_signal,
        brain_signal,
        brain_six,
        brain_sqlalchemy,
        brain_ssl,
        brain_subprocess,
        brain_threading,
        brain_type,
        brain_typing,
        brain_unittest,
        brain_uuid,
    )

    brain_argparse.register(manager)
    brain_attrs.register(manager)
    brain_boto3.register(manager)
    brain_builtin_inference.register(manager)
    brain_collections.register(manager)
    brain_crypt.register(manager)
    brain_ctypes.register(manager)
    brain_curses.register(manager)
    brain_dataclasses.register(manager)
    brain_datetime.register(manager)
    brain_dateutil.register(manager)
    brain_functools.register(manager)
    brain_gi.register(manager)
    brain_hashlib.register(manager)
    brain_http.register(manager)
    brain_hypothesis.register(manager)
    brain_io.register(manager)
    brain_mechanize.register(manager)
    brain_multiprocessing.register(manager)
    brain_namedtuple_enum.register(manager)
    brain_nose.register(manager)
    brain_numpy_core_einsumfunc.register(manager)
    brain_numpy_core_fromnumeric.register(manager)
    brain_numpy_core_function_base.register(manager)
    brain_numpy_core_multiarray.register(manager)
    brain_numpy_core_numerictypes.register(manager)
    brain_numpy_core_umath.register(manager)
    brain_numpy_random_mtrand.register(manager)
    brain_numpy_ma.register(manager)
    brain_numpy_ndarray.register(manager)
    brain_numpy_core_numeric.register(manager)
    brain_pathlib.register(manager)
    brain_pkg_resources.register(manager)
    brain_pytest.register(manager)
    brain_qt.register(manager)
    brain_random.register(manager)
    brain_re.register(manager)
    brain_regex.register(manager)
    brain_responses.register(manager)
    brain_scipy_signal.register(manager)
    brain_signal.register(manager)
    brain_six.register(manager)
    brain_sqlalchemy.register(manager)
    brain_ssl.register(manager)
    brain_subprocess.register(manager)
    brain_threading.register(manager)
    brain_type.register(manager)
    brain_typing.register(manager)
    brain_unittest.register(manager)
    brain_uuid.register(manager)
