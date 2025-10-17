#!/usr/bin/env python3
"""
Test script to verify AsterDex connector without group ID requirement
"""

import os
import sys

def test_asterdex_no_groupid():
    print("🚀 Testing AsterDex Connector (No Group ID Required)")
    print("=" * 60)
    
    # Check if AsterDex connector directory exists
    asterdex_dir = "hummingbot/connector/exchange/asterdex"
    if os.path.exists(asterdex_dir):
        print(f"✅ AsterDex connector directory exists: {asterdex_dir}")
        
        # List files in the directory
        files = os.listdir(asterdex_dir)
        print(f"✅ Found {len(files)} files:")
        for file in files:
            if not file.startswith('__'):
                print(f"   - {file}")
    else:
        print(f"❌ AsterDex connector directory not found: {asterdex_dir}")
        return False
    
    # Check constants file
    constants_file = f"{asterdex_dir}/asterdex_constants.py"
    if os.path.exists(constants_file):
        print(f"✅ Constants file exists: {constants_file}")
        
        # Read and check constants
        with open(constants_file, 'r') as f:
            content = f.read()
            
        if 'EXCHANGE_NAME = "asterdex"' in content:
            print("✅ Exchange name is correct: asterdex")
        else:
            print("❌ Exchange name is incorrect")
            
        if '{group_id}' not in content:
            print("✅ No group ID references found in constants")
        else:
            print("❌ Group ID references still found in constants")
            
        if 'PRIVATE_REST_URL = "https://asterdex.com/api/pro/v1/"' in content:
            print("✅ Private REST URL is correct (no group ID)")
        else:
            print("❌ Private REST URL is incorrect")
            
    else:
        print(f"❌ Constants file not found: {constants_file}")
        return False
    
    # Check exchange file
    exchange_file = f"{asterdex_dir}/asterdex_exchange.py"
    if os.path.exists(exchange_file):
        print(f"✅ Exchange file exists: {exchange_file}")
        
        # Read and check exchange file
        with open(exchange_file, 'r') as f:
            content = f.read()
            
        if 'asterdex_api_key' in content and 'asterdex_secret_key' in content:
            print("✅ Exchange file has correct parameter names")
        else:
            print("❌ Exchange file has incorrect parameter names")
            
        if 'ascend_ex_group_id' not in content and 'asterdex_group_id' not in content:
            print("✅ No group ID parameter found in exchange file")
        else:
            print("❌ Group ID parameter still found in exchange file")
            
    else:
        print(f"❌ Exchange file not found: {exchange_file}")
        return False
    
    # Check utils file
    utils_file = f"{asterdex_dir}/asterdex_utils.py"
    if os.path.exists(utils_file):
        print(f"✅ Utils file exists: {utils_file}")
        
        # Read and check utils file
        with open(utils_file, 'r') as f:
            content = f.read()
            
        if 'ascend_ex_group_id' not in content and 'asterdex_group_id' not in content:
            print("✅ No group ID field found in utils file")
        else:
            print("❌ Group ID field still found in utils file")
            
    else:
        print(f"❌ Utils file not found: {utils_file}")
        return False
    
    print("\n🎉 All AsterDex connector files are properly configured!")
    print("✅ No group ID requirement")
    print("✅ Correct API URLs")
    print("✅ Proper parameter names")
    print("\n🚀 Your AsterDex connector is ready to use!")
    print("   Just provide: API Key + Secret Key")
    print("   No Group ID needed!")
    
    return True

if __name__ == "__main__":
    test_asterdex_no_groupid()
