# Python Code Quality Guide for Hummingbot

**Purpose**: Ensure all Python code passes pre-commit hooks (flake8, autopep8, isort) before committing.

## Quick Reference: Common Pre-commit Issues

### 1. Import Order (E402 - module level import not at top of file)

**Problem**: Imports after executable code
```python
# ❌ BAD
import sys
sys.path.insert(0, "some/path")  # Executable code
from hummingbot import data_path  # Import after code = E402 error
```

**Solution**: Use `# noqa: E402` for imports that MUST come after path manipulation
```python
# ✅ GOOD
import sys

# Add to path (necessary for imports to work)
sys.path.insert(0, str(Path(__file__).parent.parent))

from hummingbot import data_path  # noqa: E402
from reporting.database import DatabaseManager  # noqa: E402
```

**When to use noqa: E402:**
- Scripts in `scripts/` that need to add hummingbot to sys.path
- Test files that need path setup
- Utility scripts that modify import paths

### 2. Unused F-strings (F541 - f-string is missing placeholders)

**Problem**: F-string without any `{variables}`
```python
# ❌ BAD
print(f"✅ Backup created\n")  # No variables = unnecessary f-string
print(f"Total: {count}")       # This is correct - has variable
```

**Solution**: Remove `f` prefix if no variables are used
```python
# ✅ GOOD
print("✅ Backup created\n")   # No f needed
print(f"Total: {count}")        # Keep f - has variable
```

### 3. Line Length (E501 - line too long)

**Problem**: Lines longer than 120 characters
```python
# ❌ BAD
very_long_function_call_with_many_parameters(param1, param2, param3, param4, param5, param6, param7, param8, param9, param10)
```

**Solution**: Break into multiple lines
```python
# ✅ GOOD
very_long_function_call_with_many_parameters(
    param1, param2, param3,
    param4, param5, param6,
    param7, param8, param9,
    param10
)

# Or for strings
long_message = (
    "This is a very long message that would "
    "exceed the line length limit if written "
    "on a single line"
)
```

### 4. Whitespace Around Operators (E226 - missing whitespace around arithmetic operator)

**Problem**: Missing spaces around operators
```python
# ❌ BAD
result = timestamp/1000  # Missing spaces around /
```

**Solution**: Add spaces
```python
# ✅ GOOD
result = timestamp / 1000  # Spaces around /
```

### 5. Trailing Whitespace (W291, W293)

**Problem**: Spaces at end of lines
```python
# ❌ BAD (invisible spaces after code)
def my_function():
    return True
```

**Solution**: Configure your editor to remove trailing whitespace automatically
- VS Code: `"files.trimTrailingWhitespace": true`
- Most editors have this option

### 6. Import Sorting (isort)

**Problem**: Imports not properly sorted
```python
# ❌ BAD
from pathlib import Path
import sys
from datetime import datetime
import argparse
from hummingbot import data_path
```

**Solution**: Group and sort imports (isort does this automatically)
```python
# ✅ GOOD
import argparse
import sys
from datetime import datetime
from pathlib import Path

from hummingbot import data_path  # noqa: E402 (if after path setup)
```

**Import order:**
1. Standard library imports (sys, os, pathlib, etc.)
2. Third-party imports (requests, pandas, etc.)
3. Local application imports (hummingbot, reporting, etc.)

## Pre-commit Hooks Reference

Hummingbot runs these checks automatically on commit:

1. **trailing-whitespace**: Removes trailing spaces
2. **end-of-file-fixer**: Ensures files end with newline
3. **flake8**: Python linting (style, errors, complexity)
4. **autopep8**: Auto-formats code to PEP 8
5. **isort**: Sorts and organizes imports
6. **detect-private-key**: Security check for API keys
7. **detect-wallet-private-key**: Security check for wallet keys

## Running Checks Manually

### Before committing, run checks manually:

```bash
# Run flake8 on specific files
conda run -n hummingbot flake8 path/to/file.py

# Run flake8 on all changed files
conda run -n hummingbot flake8 $(git diff --name-only --diff-filter=AM | grep '\.py$')

# Run all pre-commit hooks without committing
pre-commit run --all-files

# Run specific hook
pre-commit run flake8 --all-files
pre-commit run isort --all-files
```

### Auto-fix many issues:

```bash
# Auto-fix with autopep8
autopep8 --in-place --max-line-length 120 path/to/file.py

# Auto-fix imports with isort
isort path/to/file.py
```

## Flake8 Configuration

Hummingbot's flake8 config (in `setup.cfg`):
```ini
[flake8]
max-line-length = 120
exclude =
    build/
    dist/
    *.egg-info/
    __pycache__/
    .git/
    venv/
ignore = E501,W503,E203,E731
per-file-ignores =
    __init__.py:F401
```

**What this means:**
- Max line length: 120 characters
- Ignores some specific rules globally
- Allows unused imports in `__init__.py`

## Best Practices for New Code

### 1. Use Proper Script Structure

For utility scripts in `scripts/`:

```python
#!/usr/bin/env python3
"""
Script description.

Usage:
    python script_name.py [options]
"""
import argparse  # Standard library first
import sys
from datetime import datetime
from pathlib import Path

# Add hummingbot to path BEFORE hummingbot imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Now import hummingbot modules with noqa
from hummingbot import data_path  # noqa: E402
from reporting.database import DatabaseManager  # noqa: E402


def main():
    """Main function - all executable code goes here."""
    parser = argparse.ArgumentParser(description='Script description')
    parser.add_argument('--option', help='Option help')
    args = parser.parse_args()

    # Your code here
    print("Running script...")


if __name__ == "__main__":
    main()
```

### 2. Check Code Before Committing

Create a pre-commit checklist:

```bash
#!/bin/bash
# save as: scripts/check_code.sh

echo "🔍 Running code quality checks..."

echo "1. Running flake8..."
conda run -n hummingbot flake8 $(git diff --cached --name-only --diff-filter=AM | grep '\.py$')
if [ $? -ne 0 ]; then
    echo "❌ Flake8 failed"
    exit 1
fi

echo "2. Running isort check..."
isort --check-only $(git diff --cached --name-only --diff-filter=AM | grep '\.py$')
if [ $? -ne 0 ]; then
    echo "❌ isort failed - run: isort <file>"
    exit 1
fi

echo "✅ All checks passed!"
```

### 3. Configure Your Editor

#### VS Code / Cursor Settings

Add to `.vscode/settings.json`:

```json
{
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.linting.flake8Args": [
        "--max-line-length=120"
    ],
    "python.formatting.provider": "autopep8",
    "python.formatting.autopep8Args": [
        "--max-line-length=120"
    ],
    "[python]": {
        "editor.rulers": [120],
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.organizeImports": true
        }
    },
    "files.trimTrailingWhitespace": true,
    "files.insertFinalNewline": true,
    "isort.args": ["--profile", "black"]
}
```

This will:
- Show flake8 errors in real-time
- Auto-format on save
- Auto-organize imports on save
- Remove trailing whitespace
- Add final newline

### 4. Common Patterns

#### Pattern 1: Scripts that need path setup
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from hummingbot import data_path  # noqa: E402
```

#### Pattern 2: Long conditionals
```python
# ❌ BAD
if some_long_condition and another_long_condition and yet_another_condition:
    do_something()

# ✅ GOOD
if (some_long_condition
        and another_long_condition
        and yet_another_condition):
    do_something()
```

#### Pattern 3: Long strings
```python
# ❌ BAD
message = f"This is a very long message that describes {something} and explains {something_else} in detail"

# ✅ GOOD
message = (
    f"This is a very long message that describes {something} "
    f"and explains {something_else} in detail"
)
```

#### Pattern 4: Print statements without variables
```python
# ❌ BAD
print(f"Starting process...")
print(f"Result: {result}")

# ✅ GOOD
print("Starting process...")  # No f needed
print(f"Result: {result}")     # f needed for variable
```

## Quick Fix Commands

```bash
# Fix all flake8 issues automatically (where possible)
autopep8 --in-place --aggressive --aggressive path/to/file.py

# Fix import order
isort path/to/file.py

# Check a file before committing
flake8 path/to/file.py && echo "✅ Flake8 passed"
isort --check path/to/file.py && echo "✅ isort passed"

# Fix common issues in bulk
find scripts/ -name "*.py" -exec autopep8 --in-place --max-line-length 120 {} \;
find scripts/ -name "*.py" -exec isort {} \;
```

## When Pre-commit Fails

If pre-commit hooks fail:

1. **Read the error message** - it tells you exactly what's wrong
2. **Check the line number** - errors reference specific lines
3. **Fix the issue** - use the patterns above
4. **Stage the fixes**: `git add <file>`
5. **Commit again** - hooks will re-run automatically

**Example workflow:**
```bash
git commit -m "My changes"
# Hook fails with: scripts/my_script.py:42:1: E402

# Fix the issue in the file
# Then:
git add scripts/my_script.py
git commit -m "My changes"  # Hooks pass this time
```

## Summary Checklist

Before writing code:
- [ ] Configure editor for auto-formatting
- [ ] Set max line length to 120
- [ ] Enable flake8 linting in editor

While writing code:
- [ ] Use `main()` function for utility scripts
- [ ] Add `# noqa: E402` for imports after path setup
- [ ] Remove `f` prefix from strings without variables
- [ ] Keep lines under 120 characters
- [ ] Add spaces around operators

Before committing:
- [ ] Run `flake8` on changed files
- [ ] Run `isort --check` on changed files
- [ ] Review the diff for obvious issues
- [ ] Let pre-commit hooks auto-fix what they can

If commit fails:
- [ ] Read the error message
- [ ] Fix the specific line mentioned
- [ ] Stage the fix
- [ ] Commit again

## Additional Resources

- **Flake8 Docs**: https://flake8.pycqa.org/
- **PEP 8 Style Guide**: https://pep8.org/
- **isort Docs**: https://pycqa.github.io/isort/
- **Pre-commit Docs**: https://pre-commit.com/

## Common noqa Comments

Use these to suppress specific warnings (use sparingly):

```python
import module  # noqa: E402  - Import not at top
long_line = "..."  # noqa: E501  - Line too long
lambda x: x  # noqa: E731  - Don't assign lambda
unused_var  # noqa: F841  - Variable assigned but never used
from module import *  # noqa: F401  - Import unused (in __init__.py)
```

**Best practice**: Fix the issue rather than using `noqa`, unless it's unavoidable (like E402 for path setup).
