# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/pylint-dev/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import contextlib
import platform
import sys
import traceback
from collections.abc import Iterator, Sequence
from datetime import datetime
from pathlib import Path

from pylint.constants import PYLINT_HOME, full_version


def prepare_crash_report(ex: Exception, filepath: str, crash_file_path: str) -> Path:
    issue_template_path = (
        Path(PYLINT_HOME) / datetime.now().strftime(str(crash_file_path))
    ).resolve()
    with open(filepath, encoding="utf8") as f:
        file_content = f.read()
    template = ""
    if not issue_template_path.exists():
        template = """\
First, please verify that the bug is not already filled:
https://github.com/pylint-dev/pylint/issues/

Then create a new issue:
https://github.com/pylint-dev/pylint/issues/new?labels=Crash 💥%2CNeeds triage 📥


"""
    template += f"""
Issue title:
Crash ``{ex}`` (if possible, be more specific about what made pylint crash)

### Bug description

When parsing the following ``a.py``:

<!--
 If sharing the code is not an option, please state so,
 but providing only the stacktrace would still be helpful.
 -->

```python
{file_content}
```

### Command used

```shell
pylint a.py
```

### Pylint output

<details open>
    <summary>
        pylint crashed with a ``{ex.__class__.__name__}`` and with the following stacktrace:
    </summary>

```python
"""
    template += traceback.format_exc()
    template += f"""
```


</details>

### Expected behavior

No crash.

### Pylint version

```shell
{full_version}
```

### OS / Environment

{sys.platform} ({platform.system()})

### Additional dependencies

<!--
Please remove this part if you're not using any of
your dependencies in the example.
 -->
"""
    try:
        with open(issue_template_path, "a", encoding="utf8") as f:
            f.write(template)
    except Exception as exc:  # pylint: disable=broad-except
        print(
            f"Can't write the issue template for the crash in {issue_template_path} "
            f"because of: '{exc}'\nHere's the content anyway:\n{template}.",
            file=sys.stderr,
        )
    return issue_template_path


def get_fatal_error_message(filepath: str, issue_template_path: Path) -> str:
    return (
        f"Fatal error while checking '{filepath}'. "
        f"Please open an issue in our bug tracker so we address this. "
        f"There is a pre-filled template that you can use in '{issue_template_path}'."
    )


def _augment_sys_path(additional_paths: Sequence[str]) -> list[str]:
    original = list(sys.path)
    changes = []
    seen = set()
    for additional_path in additional_paths:
        if additional_path not in seen:
            changes.append(additional_path)
            seen.add(additional_path)

    sys.path[:] = changes + sys.path
    return original


@contextlib.contextmanager
def augmented_sys_path(additional_paths: Sequence[str]) -> Iterator[None]:
    """Augment 'sys.path' by adding non-existent entries from additional_paths."""
    original = _augment_sys_path(additional_paths)
    try:
        yield
    finally:
        sys.path[:] = original
