import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import TimeFrame
from datetime import date, timedelta, datetime

api = tradeapi.REST('PKUEREPQKTC3C0U4B1JO', '5aG23GgQN99fEGhgLjAJh092Ql1PYnNzf41g031v', 'https://paper-api.alpaca.markets')
inverse_last_trade = api.get_last_trade('LABD')
print(inverse_last_trade)


import pytz
from datetime import datetime
tz = pytz.timezone('US/Eastern')
today = datetime.today() - timedelta(minutes=15)
earlier = today - timedelta(minutes=15)

loc_today = tz.localize(today).replace(microsecond=0).isoformat()
loc_earlier = tz.localize(earlier).replace(microsecond=0).isoformat()

print(loc_today)
print(loc_earlier)

inverse_stop = api.get_bars('SQQQ', TimeFrame.Minute, loc_earlier, loc_today, limit=1, adjustment='raw').df

print(inverse_stop)
