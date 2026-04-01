import requests
from bs4 import BeautifulSoup
import re

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

def test_cnyes():
    url = "https://www.cnyes.com/twstock/stock_astock.aspx"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, 'lxml' if 'lxml' else 'html.parser')
    concepts = []
    # cnyes concepts are usually in a specific table or div, but let's just find all a tags that have 'concept' in href
    for a in soup.find_all('a', href=re.compile(r'/twstock/concept/')):
        name = a.text.strip()
        href = a['href']
        if name:
            concepts.append((name, href))
    print(f"CnYes Concepts: {len(concepts)}")
    print(concepts[:10])

def test_finguider():
    url = "https://finguider.cc/concept-list?tab=%E6%A6%82%E5%BF%B5%E6%B8%85%E5%96%AE"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, 'lxml' if 'lxml' else 'html.parser')
    concepts = []
    # finGuider concepts
    for a in soup.find_all('a', href=re.compile(r'/Concept/')):
        name = a.text.strip()
        if name:
            concepts.append(name)
    print(f"FinGuider Concepts: {len(concepts)}")
    print(concepts[:10])

if __name__ == "__main__":
    test_cnyes()
    test_finguider()
