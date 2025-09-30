#!/usr/bin/env python3
"""
Vest Markets Connector Environment Setup
Ensures all dependencies are available for the ./start script
"""

import importlib
import subprocess
import sys


def check_dependency(package_name, import_name=None):
    """Check if a dependency can be imported"""
    if import_name is None:
        import_name = package_name

    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False


def install_with_system_pip(packages):
    """Install packages using system pip"""
    try:
        cmd = [sys.executable, "-m", "pip", "install"] + packages
        subprocess.check_call(cmd)
        return True
    except subprocess.CalledProcessError:
        return False


def main():
    print("🚀 Vest Markets Connector Environment Setup")
    print("=" * 50)

    # Required dependencies for Vest connector
    dependencies = [
        ("pandas", "pandas"),
        ("bidict", "bidict"),
        ("eth-account", "eth_account"),
        ("pydantic", "pydantic")
    ]

    missing_deps = []

    print("🔍 Checking dependencies...")
    for package, import_name in dependencies:
        if check_dependency(import_name):
            print(f"  ✅ {package}")
        else:
            print(f"  ❌ {package} (missing)")
            missing_deps.append(package)

    if missing_deps:
        print(f"\n📦 Installing missing dependencies: {', '.join(missing_deps)}")
        if install_with_system_pip(missing_deps):
            print("✅ Dependencies installed successfully!")
        else:
            print("❌ Failed to install some dependencies")
            print("Manual installation required:")
            print(f"pip install {' '.join(missing_deps)}")
            return False

    print("\n🧪 Testing Vest connector imports...")

    # Add current directory to path for imports
    sys.path.insert(0, '.')

    test_imports = [
        ("hummingbot.connector.exchange.vest.vest_constants", "Vest constants"),
        ("hummingbot.connector.exchange.vest.vest_utils", "Vest utilities"),
        ("hummingbot.connector.exchange.vest.vest_auth", "Vest authentication"),
        ("hummingbot.connector.exchange.vest.vest_exchange", "Vest exchange class")
    ]

    all_good = True
    for module, description in test_imports:
        try:
            importlib.import_module(module)
            print(f"  ✅ {description}")
        except Exception as e:
            print(f"  ❌ {description}: {e}")
            all_good = False

    print("\n" + "=" * 50)

    if all_good:
        print("🎉 SUCCESS! Vest connector is ready!")
        print("\nNext steps:")
        print("1. Run: ./start")
        print("2. In Hummingbot, configure: config vest")
        print("\nRequired Vest API credentials:")
        print("- API Key")
        print("- Primary Address (wallet holding funds)")
        print("- Signing Address (delegate key)")
        print("- Private Key (for signing)")
        print("- Environment (prod/dev)")
    else:
        print("⚠️  Some issues detected.")
        print("Please check the errors above and resolve them.")

    return all_good


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
