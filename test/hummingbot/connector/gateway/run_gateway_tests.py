#!/usr/bin/env python
"""
Run Gateway connector tests.
Runs only the active test files, skipping legacy tests.
"""
import subprocess
import sys


def run_tests():
    """Run Gateway tests."""
    # Test files to run
    test_files = [
        "test_gateway_client.py",
        "test_gateway_monitor.py",
        "test_gateway_command_simple.py",
        "test_gateway_wallet_mock.py",
    ]

    # Run each test file
    for test_file in test_files:
        print(f"\n{'=' * 60}")
        print(f"Running {test_file}")
        print(f"{'=' * 60}\n")

        cmd = [
            sys.executable, "-m", "pytest",
            f"test/hummingbot/connector/gateway/{test_file}",
            "-xvs"
        ]

        result = subprocess.run(cmd)

        if result.returncode != 0:
            print(f"\n❌ {test_file} failed!")
            return 1

    print("\n✅ All Gateway tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(run_tests())
