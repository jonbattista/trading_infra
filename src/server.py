from flask import Flask, request
import requests
import alpaca_trade_api as tradeapi
import json

app = Flask(__name__)

app.debug = True

@app.route('/', methods=["POST"])


def alpaca():
    data = request.data

    print(data)
    json_data = json.loads(data)
    print(json_data)
    print(request.args)

    if request.args.get('APCA_API_KEY_ID') is None:
        return 'APCA_API_KEY_ID is not set!', 400
    if request.args.get('APCA_API_SECRET_KEY') is None:
        return 'APCA_API_SECRET_KEY is not set!', 400
    if json_data['ticker'] is None:
        return 'ticker is not set!', 400
    if json_data['price'] is None:
        return 'price is not set!', 400
    if json_data['order'] is None:
        return 'order is not set!', 400

    time_in_force_condition = 'time_in_force' not in json_data
    print(time_in_force_condition)
    if time_in_force_condition:
        time_in_force = 'day'
    else:
        time_in_force = json_data['time_in_force']

    order_type_condition = 'order_type' not in json_data
    print(order_type_condition)
    if order_type_condition:
        order_type = 'limit'
    else:
        order_type = json_data['order_type']

    APCA_API_KEY_ID = request.args.get('APCA_API_KEY_ID')
    APCA_API_SECRET_KEY = request.args.get('APCA_API_SECRET_KEY')
    ticker = json_data['ticker']
    price = json_data['price']
    order = json_data['order']

    print(f'ticker is {ticker}')
    print(f'price is {price}')
    print(f'order is {order}')
    print(f'time_in_force is {time_in_force}')
    print(f'order_type is {order_type}')

    api = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, 'https://paper-api.alpaca.markets')

    account = api.get_account()

    if account.trading_blocked:
        return 'Account is currently restricted from trading.', 400
    open_orders = api.list_orders()
    print(open_orders)

    portfolio = api.list_positions()
    print(portfolio)

    if not portfolio:
        print('No Open positions found!')
    else:
        try:   
            sqqq_position = api.get_position('SQQQ')
        except requests.HTTPError as exception:
            print(exception)
        
            #print(sqqq_position)

    #tqqq_position = api.get_position('TQQQ')

    #print(tqqq_position)

    buying_power = int(account.buying_power)
    
    print(buying_power)
    
    if buying_power != 0:
        number_of_shares = price // buying_power
        print(number_of_shares)
        if number_of_shares > 0:
            print(number_of_shares)
            print(round(number_of_shares))

            order = api.submit_order(ticker, number_of_shares, order, order_type, time_in_force)

    #print(order)
    #return f'Order was {order.status}'
    return 'got it', 200

if __name__ == '__main__':
  app.run(host='0.0.0.0', port=8080)
