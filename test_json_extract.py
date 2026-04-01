import requests
from bs4 import BeautifulSoup
import json
import re

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

def extract_cnyes():
    url = "https://www.cnyes.com/twstock/stock_astock.aspx"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, 'html.parser')
    # Look for script tag with window.__INITIAL_STATE__ or __NEXT_DATA__
    for script in soup.find_all('script'):
        if script.string and '__INITIAL_STATE__' in script.string:
            print("Found __INITIAL_STATE__ in CnYes!")
            # try to parse
            match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', script.string, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                print("Extracted Data keys:", data.keys())
                break

def extract_finguider():
    url = "https://finguider.cc/concept-list?tab=%E6%A6%82%E5%BF%B5%E6%B8%85%E5%96%AE"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, 'html.parser')
    for script in soup.find_all('script'):
        if script.string and ('__NUXT__' in script.string or 'concept' in script.string):
            print("Found potential data in FinGuider script")

if __name__ == "__main__":
    extract_cnyes()
    extract_finguider()
