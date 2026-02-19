import httpx
import json

TRADING_HTTP_URL = "https://api.testnet.aptoslabs.com/decibel"

def test_connection():
    print(f"📡 [TEST] Probing Decibel API at {TRADING_HTTP_URL}...")
    
    try:
        # 1. Fetch Markets
        url = f"{TRADING_HTTP_URL}/api/v1/markets"
        r = httpx.get(url)
        print(f"   Status: {r.status_code}")
        
        if r.status_code == 200:
            markets = r.json()
            print(f"✅ Success! Found {len(markets)} markets.")
            if len(markets) > 0:
                print(f"   First Market: {json.dumps(markets[0], indent=2)}")
        else:
            print(f"❌ Failed to fetch markets. Body: {r.text[:200]}")

    except Exception as e:
        print(f"💥 Connection Error: {e}")

if __name__ == "__main__":
    test_connection()
