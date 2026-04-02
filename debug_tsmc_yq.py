from yahooquery import Ticker
import pprint

t = Ticker("2330.TW", asynchronous=True)
res = t.price
print("Price fields for 2330:")
pprint.pprint(res)
