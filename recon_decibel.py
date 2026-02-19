import re
import requests
from urllib.parse import urljoin

TARGET_URL = "https://docs.decibel.trade/"

def scan_for_endpoints():
    print(f"🕵️ [RECON] Scanning {TARGET_URL} for API clues...")
    
    try:
        # 1. Get Index HTML
        response = requests.get(TARGET_URL)
        response.raise_for_status()
        html = response.text
        
        # 2. Extract JS files (script src)
        # Using multiline string to avoid quote hell
        pattern = r"""<script.*?src=["'](.*?)["']"""
        scripts = re.findall(pattern, html)
        print(f"   Found {len(scripts)} JS files.")
        
        found_urls = set()
        
        # 3. Analyze each script
        for script_path in scripts:
            full_url = urljoin(TARGET_URL, script_path)
            if not full_url.endswith('.js'): continue
            
            print(f"   Reading {full_url}...")
            try:
                js_content = requests.get(full_url).text
                
                # Regex for potential API endpoints
                urls = re.findall(r'(https?://[a-zA-Z0-9.-]+\.decibel\.trade[a-zA-Z0-9./_]*)', js_content)
                wss = re.findall(r'(wss://[a-zA-Z0-9.-]+\.decibel\.trade[a-zA-Z0-9./_]*)', js_content)
                
                found_urls.update(urls)
                found_urls.update(wss)
                
            except Exception as e:
                print(f"   ⚠️ Failed to read JS: {e}")

        # 4. Report
        print("\n🔍 [RESULTS] Potential Endpoints:")
        if not found_urls:
            print("   ❌ No direct API URLs found in JS chunks.")
        else:
            for url in found_urls:
                print(f"   ✅ {url}")

    except Exception as e:
        print(f"❌ RECON FAILED: {e}")

if __name__ == "__main__":
    scan_for_endpoints()
