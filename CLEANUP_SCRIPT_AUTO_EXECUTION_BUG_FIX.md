# Cleanup Script Auto-Execution Bug Fix

**Date**: November 2, 2025
**Session Duration**: ~2 hours
**Severity**: High - Prevented Hummingbot from starting normally
**Status**: ✅ RESOLVED

## Problem Summary

After running database cleanup operations, the `./start` command would execute cleanup scripts instead of starting Hummingbot's CLI. The cleanup scripts (`cleanup_all_unmatched.py` and `cleanup_unmatched_trades.py`) were being automatically executed during Hummingbot startup, even though they were never explicitly called.

### Symptoms

1. Running `./start` would display cleanup output instead of the password prompt
2. After entering password, cleanup scripts would run showing:
   - Database backup messages
   - Trade count analysis
   - Cleanup plan output
3. Hummingbot CLI never started
4. Both cleanup scripts needed to be disabled to start Hummingbot
5. **Additional symptom found**: When exiting Hummingbot, `debug_hype_missing.py` would execute showing:
   - Trade normalization output
   - FIFO matching results
   - PnL calculation
   - HYPE asset diagnosis

## Root Cause Analysis

### The Investigation Process

The debugging process was extensive and checked:

1. ✅ `./start` script - No modifications found
2. ✅ `bin/hummingbot_quickstart.py` - Correct and unmodified
3. ✅ Environment variables - No `CONFIG_FILE_NAME` or auto-start variables set
4. ✅ Conda activation scripts - No cleanup references
5. ✅ Git hooks - No pre-commit cleanup execution
6. ✅ Shell aliases - No `start` alias redirecting to cleanup
7. ✅ Python startup files - No `.pythonrc` or `sitecustomize.py`
8. ✅ Docker compose - CONFIG_FILE_NAME commented out
9. ✅ Import statements - No direct imports of cleanup scripts

### The Discovery

The root cause was found in `/home/todd/PycharmProjects/hummingbot/hummingbot/client/ui/completer.py:86-97`

```python
def get_strategies_v2_with_config(self):
    file_names = file_name_list(str(SCRIPT_STRATEGIES_PATH), "py")
    strategies_with_config = []

    for script_name in file_names:
        try:
            script_name = script_name.replace(".py", "")
            module = sys.modules.get(f"{settings.SCRIPT_STRATEGIES_MODULE}.{script_name}")
            if module is not None:
                script_module = importlib.reload(module)
            else:
                script_module = importlib.import_module(f".{script_name}",
                                                        package=settings.SCRIPT_STRATEGIES_MODULE)
            # ... checks for Strategy V2 config classes
```

**What was happening:**

1. **Hummingbot's autocompleter** loads during startup to provide tab-completion for strategy scripts
2. **It imports ALL `.py` files** in the `scripts/` directory using `importlib.import_module()`
3. **The cleanup scripts had module-level code** that ran immediately upon import (not protected by `if __name__ == "__main__":`)
4. **Both scripts executed** during the import process, showing their output and creating database backups

### Why This Was Difficult to Find

1. **Indirect execution**: Scripts weren't being called directly - they were imported
2. **Hidden in autocompleter**: The import happens in UI initialization, not in obvious startup code
3. **No obvious connection**: No grep for "cleanup" or "import cleanup" would find the issue
4. **Module-level code**: The problem was in the script structure, not in how they were being called
5. **Both scripts affected**: Required disabling both to isolate the issue

## The Solution

### Fix Applied

Wrapped all executable code in both cleanup scripts with proper Python main guards:

**Before (problematic):**
```python
#!/usr/bin/env python3
"""Script docstring"""
import sys
import argparse

# Parse arguments - THIS RUNS ON IMPORT!
parser = argparse.ArgumentParser(...)
args = parser.parse_args()

# Database operations - THIS RUNS ON IMPORT!
db_path = Path(data_path()) / "mqtt_webhook_strategy_w_cex.sqlite"
print(f"✅ Found database: {db_path}")
# ... rest of cleanup logic runs immediately
```

**After (fixed):**
```python
#!/usr/bin/env python3
"""Script docstring"""
import sys
import argparse

# Add hummingbot to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from hummingbot import data_path
from reporting.database.connection import DatabaseManager
# ... other imports


def main():
    """Main cleanup function"""
    # Parse arguments - ONLY runs when script is executed
    parser = argparse.ArgumentParser(...)
    args = parser.parse_args()

    # Database operations - ONLY runs when script is executed
    db_path = Path(data_path()) / "mqtt_webhook_strategy_w_cex.sqlite"
    print(f"✅ Found database: {db_path}")
    # ... rest of cleanup logic


if __name__ == "__main__":
    main()
```

### Files Modified

1. `scripts/cleanup_all_unmatched.py` - Wrapped in `main()` function
2. `scripts/cleanup_unmatched_trades.py` - Wrapped in `main()` function
3. `scripts/debug_hype_missing.py` - Wrapped in `main()` function (found during exit)

### Verification

✅ `./start` now works correctly
✅ Cleanup scripts still work when run directly: `python scripts/cleanup_all_unmatched.py`
✅ No auto-execution during Hummingbot startup
✅ Autocompleter still functions properly for legitimate strategy scripts

## Lessons Learned

### Critical Best Practices for Hummingbot `scripts/` Directory

1. **ALWAYS use `if __name__ == "__main__":` guards**
   - All Python files in `scripts/` are imported by the autocompleter
   - Module-level code WILL execute during Hummingbot startup
   - Only put imports and function/class definitions at module level

2. **Structure utility scripts properly:**
   ```python
   # ✅ GOOD: Imports and definitions only at module level
   import sys
   from pathlib import Path

   def main():
       """All executable code goes here"""
       # ... your script logic

   if __name__ == "__main__":
       main()
   ```

   ```python
   # ❌ BAD: Executable code at module level
   import sys
   import argparse

   parser = argparse.ArgumentParser()  # Runs on import!
   args = parser.parse_args()  # Runs on import!

   db = connect_to_db()  # Runs on import!
   # ... more code that runs on import
   ```

3. **Test script imports:**
   ```bash
   # Test if your script can be safely imported
   python -c "import sys; sys.path.insert(0, '.'); from scripts import your_script"
   # Should complete without output or side effects
   ```

4. **Distinguish between strategies and utilities:**
   - **Strategy scripts**: Inherit from `ScriptStrategyBase`, can be imported safely
   - **Utility scripts**: Database tools, analysis scripts, cleanup tools
   - **Utility scripts MUST use main guards** to prevent auto-execution

5. **Debugging import-related issues:**
   - Check `hummingbot/client/ui/completer.py` for script loading logic
   - Clear Python cache: `find . -type d -name "__pycache__" -exec rm -rf {} +`
   - Look for module-level code in `scripts/*.py` files

### Why Hummingbot Imports All Scripts

The autocompleter scans all scripts to:
- Provide tab-completion for available strategy scripts
- Detect Strategy V2 scripts with config classes
- Enable the `start --script <name>` command autocomplete

This is intentional behavior, so all scripts must be import-safe.

## Prevention for Future Scripts

### Checklist for New Scripts in `scripts/`

- [ ] All executable code wrapped in `main()` function
- [ ] `if __name__ == "__main__":` guard at the end
- [ ] Only imports and definitions at module level
- [ ] Test import: `python -c "from scripts import your_script"`
- [ ] No `argparse.parse_args()` at module level
- [ ] No `sys.exit()` at module level
- [ ] No database operations at module level
- [ ] No print statements at module level (except in functions)

### Template for Utility Scripts

```python
#!/usr/bin/env python3
"""
Script description here.

Usage:
    python script_name.py [options]
"""
import sys
from pathlib import Path

# Add hummingbot to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Imports only - no executable code
from hummingbot import data_path
from reporting.database.connection import DatabaseManager


def main():
    """Main function - all executable code goes here"""
    import argparse

    # Argument parsing
    parser = argparse.ArgumentParser(description='Script description')
    parser.add_argument('--option', help='Option description')
    args = parser.parse_args()

    # Script logic
    print("Script running...")
    # ... your code here


if __name__ == "__main__":
    main()
```

## Impact Assessment

### Before Fix
- ❌ Hummingbot could not start normally
- ❌ Database backups created on every start attempt
- ❌ Confusing output during startup
- ❌ Unable to run trading bot

### After Fix
- ✅ Hummingbot starts normally
- ✅ Cleanup scripts still work when needed
- ✅ Clean startup output
- ✅ No unexpected side effects
- ✅ Autocompleter still functions

## Related Documentation

- Hummingbot CLAUDE.md: Best practices for script development
- Python documentation: [`__main__` — Top-level code environment](https://docs.python.org/3/library/__main__.html)
- Issue was not related to any external configuration or environment variables

## Debugging Timeline

1. **Initial investigation** (20 min): Checked obvious causes (start script, environment vars)
2. **Deep dive** (40 min): Investigated git hooks, conda env, aliases, config files
3. **Cache clearing** (10 min): Removed Python cache to eliminate stale imports
4. **Workaround** (5 min): Renamed scripts to `.disabled` - confirmed issue
5. **Root cause discovery** (30 min): Found autocompleter import logic
6. **Fix implementation** (15 min): Wrapped both scripts in `main()` functions
7. **Verification** (10 min): Tested startup and script functionality

**Total debugging time**: ~2 hours

## Conclusion

This was a subtle but critical bug caused by the interaction between:
1. Hummingbot's autocompleter importing all scripts
2. Cleanup scripts lacking proper main guards
3. Module-level code executing on import

The fix is straightforward once understood, but the root cause was difficult to identify because:
- The execution was indirect (via import, not direct call)
- The import happened in UI initialization code
- No obvious connection between autocompleter and cleanup scripts

**Key Takeaway**: All Python files in Hummingbot's `scripts/` directory must use proper `if __name__ == "__main__":` guards to prevent auto-execution during imports.
