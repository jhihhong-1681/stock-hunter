from yahooquery import Screener
s = Screener()
print(s.available_screeners)
res = s.get_screeners('ms_technology', count=5)
print(res)
