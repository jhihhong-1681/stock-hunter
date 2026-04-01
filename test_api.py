import requests

def test_api():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*'
    }
    # Test cnyes API
    url_cnyes = "https://www.cnyes.com/api/v3/twstock/concept" 
    # Just guessing endpoints
    try:
        r = requests.get("https://ws.cnyes.com/webapi/v1/twstock/category", headers=headers, timeout=5)
        print("cnyes api status code:", r.status_code)
        if r.status_code == 200:
            print(r.json()[:100] if len(r.text) > 100 else r.json())
    except:
        pass
    
    # Test finguider API
    try:
        r = requests.get("https://finguider.cc/api/concepts", headers=headers, timeout=5)
        print("finguider api status code:", r.status_code)
    except:
        pass

if __name__ == '__main__':
    test_api()
