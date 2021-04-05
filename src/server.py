from flask import Flask, request
import requests
import alpaca_trade_api as tradeapi
import json
from decimal import Decimal
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

app = Flask(__name__)

app.debug = True

@app.route('/', methods=["POST"])


def alpaca():
    data = request.data

    json_data = json.loads(data)
    #print(json_data)
    #print(request.args)

    if request.args.get('APCA_API_KEY_ID') is None:
        return 'APCA_API_KEY_ID is not set!', 400
    if request.args.get('APCA_API_SECRET_KEY') is None:
        return 'APCA_API_SECRET_KEY is not set!', 400
    if json_data['ticker'] is None:
        return 'ticker is not set!', 400
    if json_data['price'] is None:
        return 'price is not set!', 400
    if json_data['side'] is None:
        return 'side is not set!', 400

    time_in_force_condition = 'time_in_force' not in json_data
    print(time_in_force_condition)
    if time_in_force_condition:
        time_in_force = 'day'
    else:
        time_in_force = json_data['time_in_force']

    order_type_condition = 'type' not in json_data
    print(order_type_condition)
    if order_type_condition:
        order_type = 'limit'
    else:
        order_type = json_data['order_type']

    APCA_API_KEY_ID = request.args.get('APCA_API_KEY_ID')
    APCA_API_SECRET_KEY = request.args.get('APCA_API_SECRET_KEY')
    ticker = json_data['ticker']
    price = json_data['price']
    side = json_data['side']

    print(f'ticker is {ticker}')
    print(f'price is {price}')
    print(f'side is {side}')
    print(f'time_in_force is {time_in_force}')
    print(f'order_type is {order_type}')

    api = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, 'https://paper-api.alpaca.markets')

    account = api.get_account()

    if account.trading_blocked:
        return 'Account is currently restricted from trading.', 400
    open_orders = api.list_orders()
    if not open_orders:
        print('Not Open Orders found')
        print(f'{len(open_orders)} Open Orders found!')
    else:
        print(open_orders)

    #portfolio = api.list_positions()
    portfolio = {
      "asset_id": "904837e3-3b76-47ec-b432-046db621571b",
      "symbol": "AAPL",
      "exchange": "NASDAQ",
      "asset_class": "us_equity",
      "avg_entry_price": "100.0",
      "qty": "5",
      "side": "long",
      "market_value": "600.0",
      "cost_basis": "500.0",
      "unrealized_pl": "100.0",
      "unrealized_plpc": "0.20",
      "unrealized_intraday_pl": "10.0",
      "unrealized_intraday_plpc": "0.0084",
      "current_price": "120.0",
      "lastday_price": "119.0",
      "change_today": "0.0084"
    }

    sqqq_position = json.loads('{"asset_id": "904837e3-3b76-47ec-b432-046db621571b","symbol": "SQQQ","exchange": "NASDAQ","asset_class": "us_equity","avg_entry_price": "100.0","qty": "5","side": "long","market_value": "600.0","cost_basis": "500.0","unrealized_pl": "100.0","unrealized_plpc": "0.20","unrealized_intraday_pl": "10.0","unrealized_intraday_plpc": "0.0084","current_price": "120.0","lastday_price": "119.0","change_today": "0.0084"}')

    tqqq_position = json.loads('{"asset_id": "904837e3-3b76-47ec-b432-046db621571a","symbol": "TQQQ","exchange": "NASDAQ","asset_class": "us_equity","avg_entry_price": "100.0","qty": "5","side": "long","market_value": "600.0","cost_basis": "500.0","unrealized_pl": "100.0","unrealized_plpc": "0.20","unrealized_intraday_pl": "10.0","unrealized_intraday_plpc": "0.0084","current_price": "120.0","lastday_price": "119.0","change_today": "0.0084"}')
    print(portfolio)

    # Recieved a Buy TQQQ alert
    if side == 'buy':
        if not portfolio:
            print('No Open positions found!')
        else:
            # Check if there is an open SQQQ position
            #try:   
            #    sqqq_position = api.get_position('SQQQ')
            #except tradeapi.rest.APIError as exception:
            #    print(exception)
            
            # Sell SQQQ positions at Market
            try:
                order = api.submit_order(
                    symbol='SQQQ',
                    qty=sqqq_position['qty'],
                    side='sell',
                    type='market',
                    time_in_force=time_in_force,
                )
            except tradeapi.rest.APIError as exception:
                print(exception)

            if order.status == 'accepted':
                tqqq_filled_qty = tqqq_position['filled_qty']
                result = f'Success: Sale of {tqqq_position['tqqq_filled_qty']} of TQQQ was {order.status}'

                message = Mail(
                    from_email='alerts@trading.battista.dev',
                    to_emails='jonbattista@gmail.com',
                    subject=f'{result}')
                try:
                    sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
                    response = sg.send(message)
                    print(response.status_code)
                    print(response.body)
                    print(response.headers)
                except Exception as e:
                    print(e.message)

                return result
            else:
                result = f'Error: Sale of TQQQ was {order.status}'
                message = Mail(
                    from_email='alerts@trading.battista.dev',
                    to_emails='jonbattista@gmail.com',
                    subject=f'{result}')
                try:
                    sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
                    response = sg.send(message)
                    print(response.status_code)
                    print(response.body)
                    print(response.headers)
                except Exception as e:
                    print(e.message)
                return result

    # Recieved a Sell TQQQ alert
    elif side == 'sell':
        if not portfolio:
            print('No Open positions found!')
        else:
            # Check if there is an open TQQQ position
            #try:
            #    tqqq_position = api.get_position('TQQQ')
            #except tradeapi.rest.APIError as exception:
            #    print(exception)

            # Sell TQQQ positions at Market price
            try:
                order = api.submit_order(
                    symbol='TQQQ',
                    qty=tqqq_position['qty'],
                    side='sell',
                    type='market',
                    time_in_force=time_in_force,
                )
            except tradeapi.rest.APIError as exception:
                print(exception)

            if order.status == 'accepted':
                return f'Success: Sale of {tqqq_position.filled_qty} of TQQQ was {order.status}'
            else:
                return f'Error: Sale of {tqqq_position.filled_qty} of TQQQ was {order.status}'

            # Wait for TQQQ Sell Order to be filled
            tqqq_order_id = order.asset_id

            tqqq_order_filled = False

            while not tqqq_order_filled:
                tqqq_order_status = get_order_by_client_order_id(tqqq_order_id)
                if tqqq_order_status == 'filled':
                    tqqq_order_filled = True

            # Check if there is an TQQQ position is closed
            try:
                tqqq_position = api.get_position('TQQQ')
            except tradeapi.rest.APIError as exception:
                print(exception)

            buying_power = Decimal(account.buying_power)
            
            print(f'Buying Power is {buying_power}')
            
            limit_price = Decimal(price) * Decimal('.0.5')

            if buying_power != 0:
                number_of_shares = round(buying_power // price)
                if number_of_shares > 0:
                    order = api.submit_order(
                        symbol=ticker,
                        qty=number_of_shares - 1,
                        side=side,
                        type=order_type,
                        time_in_force=time_in_force,
                        limit_price=limit_price
                    )
                    print(order)
                    if order.status == 'accepted':
                        return f'Success: Purchase of {number_of_shares} at ${price} was {order.status}'
                    else:
                        return f'Error: Purchase of {number_of_shares} at ${price} was {order.status}'
                else:
                    return f'Not enough Buying Power: ${buying_power}', 200
            
            return f'You have no Buying Power: ${buying_power}', 200
    return 'hello', 200

if __name__ == '__main__':
  app.run(host='0.0.0.0', port=8080)
