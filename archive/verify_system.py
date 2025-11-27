#!/usr/bin/env python3
"""
System verification script
Checks all components are properly installed and configured
"""
import sys
import os
from pathlib import Path

def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def check_files():
    """Check required files exist"""
    print_header("Checking Project Files")

    required_files = [
        'main.py',
        'config.yaml',
        'requirements.txt',
        'README.md',
        'QUICKSTART.md',
        'src/__init__.py',
        'src/rpc_manager.py',
        'src/database.py',
        'src/monitor.py',
    ]

    all_ok = True
    for file in required_files:
        path = Path(file)
        if path.exists():
            size = path.stat().st_size
            print(f"  ✓ {file:<30} ({size:,} bytes)")
        else:
            print(f"  ✗ {file:<30} MISSING!")
            all_ok = False

    return all_ok

def check_directories():
    """Check required directories exist"""
    print_header("Checking Directories")

    required_dirs = ['src', 'data', 'logs']

    all_ok = True
    for dir_name in required_dirs:
        path = Path(dir_name)
        if path.exists() and path.is_dir():
            print(f"  ✓ {dir_name}/")
        else:
            print(f"  ✗ {dir_name}/ MISSING!")
            all_ok = False

    return all_ok

def check_dependencies():
    """Check Python dependencies"""
    print_header("Checking Python Dependencies")

    dependencies = [
        'web3',
        'yaml',
        'requests',
        'dotenv'
    ]

    all_ok = True
    for dep in dependencies:
        try:
            __import__(dep)
            print(f"  ✓ {dep}")
        except ImportError:
            print(f"  ✗ {dep} - NOT INSTALLED")
            all_ok = False

    return all_ok

def check_config():
    """Check configuration"""
    print_header("Checking Configuration")

    try:
        import yaml
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)

        # Check monitored addresses
        addresses = config.get('monitored_addresses', [])
        has_real_address = any(
            addr != "0x0000000000000000000000000000000000000000"
            for addr in addresses
        )

        if has_real_address:
            print(f"  ✓ Monitored addresses configured: {len(addresses)}")
        else:
            print(f"  ⚠ Monitored addresses not configured (using placeholders)")
            print(f"    → Edit config.yaml before running")

        # Check RPC endpoints
        rpc_count = len(config.get('rpc_endpoints', []))
        print(f"  ✓ RPC endpoints configured: {rpc_count}")

        # Check contract
        contract = config.get('polymarket_ctf_exchange', '')
        if contract:
            print(f"  ✓ Polymarket contract: {contract[:10]}...")

        return True

    except Exception as e:
        print(f"  ✗ Error reading config: {e}")
        return False

def check_permissions():
    """Check file permissions"""
    print_header("Checking Permissions")

    try:
        # Check write permission in data/
        test_file = Path('data/test_write.tmp')
        test_file.touch()
        test_file.unlink()
        print("  ✓ data/ directory writable")

        # Check write permission in logs/
        test_file = Path('logs/test_write.tmp')
        test_file.touch()
        test_file.unlink()
        print("  ✓ logs/ directory writable")

        return True

    except Exception as e:
        print(f"  ✗ Permission error: {e}")
        return False

def main():
    """Main verification"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     POLYMARKET COPY TRADING SYSTEM                        ║
║     System Verification                                   ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)

    results = {
        'Files': check_files(),
        'Directories': check_directories(),
        'Dependencies': check_dependencies(),
        'Configuration': check_config(),
        'Permissions': check_permissions()
    }

    print_header("Verification Summary")

    all_passed = True
    for check, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status:<10} {check}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)

    if all_passed:
        print("\n🎉 All checks passed! System is ready to run.")
        print("\nNext steps:")
        print("  1. Edit config.yaml to add your monitored addresses")
        print("  2. Run: python3 main.py")
        print("\n")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.")
        print("\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
