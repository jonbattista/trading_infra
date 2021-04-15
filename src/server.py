# TODO
# - Remove Stop from Sell Price calculation
# Need to make stop and stop_limit_price optional variable

from flask import Flask, request
import requests
import os
import alpaca_trade_api as tradeapi
from alpaca_trade_api.common import URL
import json
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from waitress import serve
import uuid
import logging
from sys import stdout
import math
import time
from datetime import datetime
from discord import Webhook, RequestsWebhookAdapter

# Configure Logging for Docker container
logger = logging.getLogger('mylogger')
logger.setLevel(logging.DEBUG)
logFormatter = logging.Formatter("%(name)-12s %(asctime)s %(levelname)-8s %(filename)s:%(funcName)s %(message)s")
consoleHandler = logging.StreamHandler(stdout)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

def marketIsOpen():
    now = datetime.now()
    market_open = now.replace(hour=13, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=20, minute=0, second=0, microsecond=0)

    if now < market_open or now > market_closed:
        print(f"Market is Closed - {time.strftime('%l:%M %p')}")
        return False
    else:
        print(f"Market is Open - {time.strftime('%l:%M %p')}")
        return True

def sendDiscordMessage(message):
    url = "https://discord.com/api/webhooks/831890918796820510/OWR1HucrnJzHdTE-vASdf5EIbPC1axPikD4D5lh0VBn413nARUW4mla3xPjZHWCK9-9P"
    webhook = Webhook.from_url(url, adapter=RequestsWebhookAdapter())

    if message is None:
        print('Error: Discord Message is empty!')
    elif 'Error' in message:
        msg = f'```diff\n-{message}\n```'
        webhook.send(msg)
    elif 'Success' in message:
        msg = f'```diff\n+{message}\n```'
        webhook.send(msg)
    else:
        webhook.send(message)

def watchOrderFilledStatus(api, APCA_API_KEY_ID, APCA_API_SECRET_KEY, ticker, qty, side, order_type, time_in_force, limit_price, client_order_id, stop):
    print(f'Checking Status for Client Order ID: {client_order_id}')
    order = api.get_order_by_client_order_id(client_order_id)

    if order is not None:
        count = 0
        order_id = order.id
        order_status = order.status
        print(f'Initial Order status is {order_status}')

        print(f'Original Buy Order ID: {order_id}')

        if not marketIsOpen():
            return f"Market is Closed"

        while order_status == 'accepted' or order_status == 'new' and order_status != 'partially_filled' and order_status != 'filled' and order_status != 'canceled' and order_status != 'done_for_day' and order_status != 'replaced' and order_status != 'pending_replace' and count < 5 and marketIsOpen():
            time.sleep(15)
            print(f'Order Check Count is {count}')

            # Modify Buy Limit Price
            if side == 'buy':
                new_limit_price = round(float(order.limit_price) * 1.005, 2)
                if order is not None and order.legs is not None: 
                    stop_limit_price = round(float(order.legs[0].stop_price) * .9925, 2)
                    new_stop = round(float(order.legs[0].stop_price) * .9945, 2)
                else:
                    stop_limit_price = round(float(stop) * .9925, 2)
                    new_stop = round(float(stop) * .9945, 2)

                order = api.get_order(order_id)
                order_id = order.id
                order_status = order.status
                print(f'Order status is {order_status}')
                if order_status == 'filled' or order_status != 'partially_filled' or order_status != 'filled' or order_status != 'canceled' or order_status != 'done_for_day' or order_status != 'replaced' or order_status != 'pending_replace':
                    break

                try:
                    order = api.replace_order(
                        order_id=order.id,
                        qty=qty,
                        time_in_force=time_in_force,
                        limit_price=new_limit_price
                    )
                    order_id = order.id
                    order_status = order.status
                    # Modify the stop loss
                    #order = api.replace_order(
                        #order_id=order.id,
                        #qty=qty,
                        #time_in_force=time_in_force,
                        #limit_price=new_limit_price
                    #)
                    print(f'Modified Buy Order ID: {order_id}')
                except tradeapi.rest.APIError as err:
                    print(f'Error modifying buy order: {err.response.content}')
                    return err

                print(f'Buy Limit Price was changed from {limit_price} to {new_limit_price}')
                limit_price = new_limit_price
                print(f'Buy Stop Loss Price was changed from {stop} to {new_stop}')
                stop = new_stop
                print(f'Order status is now: {order_status}')
            # Modify Sell Limit Price
            elif side == 'sell':
                new_limit_price = round(float(order.limit_price) * .9925, 2)
                order = api.get_order(order_id)
                order_id = order.id
                order_status = order.status
                print(f'Order status is {order_status}')
                if order_status == 'filled' or order_status != 'partially_filled' or order_status != 'filled' or order_status != 'canceled' or order_status != 'done_for_day' or order_status != 'replaced' or order_status != 'pending_replace':
                    break

                try:
                    order = api.replace_order(
                        order_id=order.id,
                        qty=qty,
                        time_in_force=time_in_force,
                        limit_price=new_limit_price
                    )
                    order_id = order.id
                    order_status = order.status
                    print(f'Modified Sell Order ID: {order_id}')
                except tradeapi.rest.APIError as err:
                    print(f'Error modifying sell order: {err.response.content}')
                    return err

                print(f'Sell Limit Price was changed from {limit_price} to {new_limit_price}')
                limit_price = new_limit_price
                print(f'Order status is now: {order_status}')
            else:
                print(f'Order is None!')

            time.sleep(10)
            count += 1
    
        print(f'Last Order ID: {order_id}')
    
        order = api.get_order(order_id)
        order_id = order.id
        order_status = order.status
        print(f'Order status is now: {order_status}')

        return order_status
    else:
        print('Order was empty!')
        return None

def submitOrder(api, ticker, qty, side, order_type, time_in_force, limit_price, stop_limit_price, client_order_id, stop):
    # Submit Order with Stop Loss
    
    if stop is None and stop_limit_price is None and side == 'sell':
        try:
            order = api.submit_order(
                symbol=ticker,
                qty=qty,
                side=side,
                type='limit',
                limit_price=limit_price,
                time_in_force=time_in_force,
                client_order_id=client_order_id,
            )
        except tradeapi.rest.APIError as e:
            if e == 'account is not authorized to trade':
                print(f'Error: {e} - Check your API Keys are correct')
                return f'Error: {e} - Check your API Keys correct', 500
            else:
                print(f'Error submitting Order: {e}')
                return f'Error submitting Order: {e}', 500
    else:
        try:
            order = api.submit_order(
                symbol=ticker,
                qty=qty,
                side=side,
                type='limit',
                limit_price=limit_price,
                time_in_force=time_in_force,
                client_order_id=client_order_id,
                order_class='oto',
                stop_loss=dict(
                    stop_price=stop,
                    limit_price=stop_limit_price
                )
            )
        except tradeapi.rest.APIError as e:
            if e == 'account is not authorized to trade':
                print(f'Error: {e} - Check your API Keys are correct')
                return f'Error: {e} - Check your API Keys correct', 500
            else:
                print(f'Error submitting Order: {e}')
                return f'Error submitting Order: {e}', 500
    #print(order)
    return order

app = Flask(__name__)

app.debug = True

@app.route('/', methods=["POST"])

def alpaca():
#    if request.args.get('token') is None:
#        return 'Unauthorized', 401#

#    if request.args.get('token') != "XcYrXRtFXaNjTFXTFtQDMbsrmnmwygvuTa":
#        return 'Unauthorized', 401

    
    if not marketIsOpen():
        return f"Market is Closed - {time.strftime('%l:%M %p')}", 400

    base_limit_price_mulitplier = 1

    base_stop_price_multiplier = .9925

    base_stop_limit_price_multiplier = .99935

    base_stop_price_minimum_multiplier = .9999

    if request.args.get('APCA_API_KEY_ID') is None:
        print(f'Error: APCA_API_KEY_ID is not set!')
        sendDiscordMessage(f'Error: APCA_API_KEY_ID is not set!')
        return 'APCA_API_KEY_ID is not set!', 400
    if request.args.get('APCA_API_SECRET_KEY') is None:
        print(f'Error: APCA_API_SECRET_KEY is not set!')
        sendDiscordMessage(f'Error: APCA_API_SECRET_KEY is not set!')
        return 'APCA_API_SECRET_KEY is not set!', 400

    APCA_API_KEY_ID = request.args.get('APCA_API_KEY_ID')
    APCA_API_SECRET_KEY = request.args.get('APCA_API_SECRET_KEY')
    user = APCA_API_KEY_ID

    print(f'\n\nOrder received for User: {user}')

    data = request.get_data()

    #print(f'Data: {data}')

    if(request.data):
        try:
            json_data = json.loads(data)
        except json.decoder.JSONDecodeError as e:
            print(f'Error parsing JSON body for User {user}: {e}')
            sendDiscordMessage(f'Error parsing JSON body for User {user}: {e}')
            return f'Error parsing JSON: {e}', 400

        if json_data['ticker'] is None:
            print(f'Error: User: {user} - Ticker parameter is not set!')
            sendDiscordMessage(f'Error: User: {user} - Ticker parameter is not set!')
            return 'Error: Ticker parameter is not set!', 400
        if json_data['price'] is None:
            print(f'Error: User: {user} - Price parameter is not set!')
            sendDiscordMessage(f'Error: User: {user} - Price parameter is not set!')
            return 'Error: Price parameter is not set!', 400
        if json_data['side'] is None:
            print(f'Error: User: {user} - Side parameter is not set!')
            sendDiscordMessage(f'Error: User: {user} - Side parameter is not set!')
            return 'Error: Side parameter is not set!', 400

        ticker = json_data['ticker']
        price = json_data['price']
        side = json_data['side']

        if side.strip() != 'buy' and side.strip() != 'sell':
            print(f'Error: User: {user} - Side is {side}. Can only be Buy or Sell!')
            sendDiscordMessage(f'Error: User: {user} - Side is {side}. Can only be Buy or Sell!')
            return f'Side is {side}. Can only be buy or sell!', 400

        # Check if Live or Paper Trading
        if APCA_API_KEY_ID[0:2] == 'PK':
            api = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, 'https://paper-api.alpaca.markets')
            print('Using Paper Trading API')
        elif APCA_API_KEY_ID[0:2] == 'AK':
            api = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, 'https://api.alpaca.markets')
            print('Using Live Trading API')
        else:
            print(f'Error: API Key {APCA_API_KEY_ID} is malformed.')
            sendDiscordMessage(f'Error: API Key {APCA_API_KEY_ID} is malformed.')
            return 'Error: API Key {APCA_API_KEY_ID} is malformed.', 400

        # Get Account information
        account = api.get_account()

        # Get available Buying Power
        buying_power = float(account.buying_power)       
        print(f'Buying Power is ${buying_power}')

        # Get Time-In-Force
        time_in_force_condition = 'time_in_force' not in json_data
        if time_in_force_condition:
            time_in_force = 'day'
        else:
            time_in_force = json_data['time_in_force']

        # Get Order Type
        order_type_condition = 'type' not in json_data
        if order_type_condition:
            order_type = 'bracket'
        else:
            order_type = json_data['order_type']

        # Get Quantity
        if 'qty' not in json_data:
            qty = math.floor(buying_power // limit_price)
        else:
            qty = json_data['qty']


        # Prin Variables
        print(f'Ticker is {ticker}')
        print(f'Original Price is ${price}')
        print(f'Side is {side}')
        print(f'Time-In-Force is {time_in_force}')
        print(f'Order Type is {order_type}')
        print(f'Quantity is {qty}')

        # Get Stop Loss
        if 'stop' not in json_data and side == 'buy':
            print(f'Error: User: {user} - No Stop Loss was given for Buy. Stop Loss is required.')
            sendDiscordMessage(f'Error: User: {user} - No Stop Loss was given for Buy. Stop Loss is required.')
            return f'Error: No Stop Loss was given for Buy. Stop Loss is required.', 400
        elif 'stop' in json_data:
            stop = int(json_data['stop'])

        if side == 'buy':
             # Set Buy Limit Price higher to ensure it gets filled
            #limit_price = round(float(price) * 1.005, 2)
            #print(f'Updated Limit Price is ${limit_price}')
            limit_price = price * base_limit_price_mulitplier
            diff = round(abs(limit_price - price),2)

            print(f'Buying Limit Price is: ${price} + ${diff} = ${limit_price}')

            print(f'Original Stop Price is ${stop}')
            new_stop = round(stop * base_stop_price_multiplier, 2)

            # Make sure Limit Price is greater than Stop Price
            if limit_price - new_stop < 0:
                new_stop = round(new_stop * base_stop_price_minimum_multiplier, 2)

            print(f'Updated Stop Price is ${new_stop}')

            stop_limit_price = round(new_stop * base_stop_limit_price_multiplier, 2)

            print(f'Stop Limit Price is ${stop_limit_price}')

            if new_stop - stop_limit_price < 0:
                stop_limit_price = round(stop_limit_price * .999, 2)
                print(f'Modifiying Stop Limit Price to ${stop_limit_price}')

        elif side == 'sell':
            # Set Sell Limit Price lower to ensure it gets filled
            #limit_price = round(abs(float(price) * .995), 2)
            #print(f'Updated Limit Price is ${limit_price}')
            limit_price = price

            new_stop = None

            #print(f'Updated Stop Price is ${new_stop}')

            stop_limit_price = None
            #print(f'Updated Stop Limit Price is ${stop_limit_price}')

            diff = round(abs(limit_price - price),2)

            print(f'Selling Limit Price is: ${price} - ${diff} = ${limit_price}')

        # Check if Account is Blocked
        if account.trading_blocked:
            sendDiscordMessage(f'Error: User: {user} - Account is currently restricted from trading.')
            return 'Account is currently restricted from trading.', 400
        
        open_orders = api.list_orders()

        # Check if there are any open orders
        if not open_orders:
            print('No Open Orders found.')
        else:
            print(f'{len(open_orders)} Open Orders were found.')

        # Generate Order ID
        client_order_id = str(uuid.uuid4())

        # Get Positions
        portfolio = api.list_positions()
        if not portfolio:
            print('No Positions were found.')
        else:
            print(f'{len(portfolio)} Positions were found.')
            #print(portfolio)

        position = next((position for position in portfolio if position.symbol == ticker), None)

        # Check if there is already a Position for Ticker
        if position is not None and side == 'buy':
            print(f'Error: User: {user} - You already have a Position of {position.qty} shares in {ticker}')
            sendDiscordMessage(f'Error: User: {user} - You already have a Position of {position.qty} shares in {ticker}')
            return f'Error: You already have a Position of {position.qty} in {ticker} shares', 400
        elif position is None and side == 'buy':
            print(f'No position for {ticker} found. Proceeding...')
        # Check if you are trying to sell something you dont have
        elif position is None and side == 'sell':
            print(f'Error: User {user} - You have no position in {ticker} to sell.')
            sendDiscordMessage(f'Error: User {user} - You have no position in {ticker} to sell.')
            return f'Error: You have no position in {ticker} to sell.', 400
        elif position is not None and side == 'sell':
            print(f'User {user} - Has {position.qty} shares of {ticker} to sell')

        open_order_qty = 0
        open_order_ticker_count = 0
        for open_order in open_orders:
            if  open_order.symbol == ticker:
                open_order_qty += int(open_order.qty)
                open_order_ticker_count += 1

        print(f'There are {open_order_ticker_count} Open Orders for {ticker}')
        #print(position)
        #print(int(position.qty))
        #print(f'position qty is less than or equal to order qty: {int(position.qty) <= qty}')
        #print(f'position qty is greater than order qty: {int(position.qty) > qty}')
        #print(f'open order qty minus order qty is less than or equal to 0: {int(open_order_qty) - qty <= 0}')
        #print(f'open order qty minus order qty is greater than 0: {int(open_order_qty) - qty > 0}')

        if side == 'sell':
            for open_order in open_orders:
                if open_order.symbol == ticker and open_order.side == 'sell':
                    print(f'Canceling Sell {open_order.order_type} Order ID: {open_order.id}')
                    cancelled_order = api.cancel_order(order_id=open_order.id)
                    time.sleep(3)
                    print(cancelled_order)
            open_order_qty = 0
            open_order_ticker_count = 0
            open_orders = api.list_orders()
            for open_order in open_orders:
                if  open_order.symbol == ticker:
                    open_order_qty += int(open_order.qty)
                    open_order_ticker_count += 1

        if position is not None and int(position.qty) == open_order_qty and side == 'sell':
            print(f'Error: User: {user} - There are already {open_order_ticker_count} Open Orders totaling {open_order_qty} shares of {ticker}. You have nothing to sell.')
            sendDiscordMessage(f'Error: User: {user} - There are already {open_order_ticker_count} Open Orders totaling {open_order_qty} shares of {ticker}. You have nothing to sell.')
            return f'Error: There are already {open_order_ticker_count} Open Orders totaling {open_order_qty} shares of {ticker}. You have nothing to sell.', 400
        elif position is not None and int(position.qty) <= qty:
            if int(open_order_qty) - qty == 0 and side == 'sell':
                print(f'Error: User: {user} - There is already an Open order to sell {open_order_qty} of {ticker}')
                sendDiscordMessage(f'Error: User: {user} - There is already an Open order to sell {open_order_qty} of {ticker}')
                return f'Error: There is already an Open order to sell {open_order_qty} of {ticker}', 400
    
            elif int(open_order_qty) - qty > 0 and side == 'sell':
                print(f'Warning: User: {user} - You are selling {open_order_qty} of {ticker}, which would leave {int(open_order_qty) - qty} leftover.')
        elif position is not None and int(position.qty) > qty:
            if int(open_order_qty) - qty == 0 and side == 'sell':
                print(f'Error: User: {user} - There is already an Open order to sell {open_order_qty} of {ticker}.')
                sendDiscordMessage(f'Error: User: {user} - There is already an Open order to sell {open_order_qty} of {ticker}.')
                return f'Error: There is already an Open order to sell {open_order_qty} of {ticker}.', 400
            elif int(open_order_qty) - qty > 0 and side == 'sell':
                print(f'Warning: User: {user} - You are selling {open_order_qty} of {ticker}, which would leave {abs(int(open_order_qty) - qty)} leftover.')
        
        # Order Flow
        if buying_power <= 0 and side == 'buy':
            print(f'Error: User: {user} - You have no Buying Power: ${buying_power}')
            sendDiscordMessage(f'Error: User: {user} - You have no Buying Power: ${buying_power}')
            return f'Error: You have no Buying Power: ${buying_power}', 400
        elif buying_power > 0 and side == 'buy':
            if qty > 0 and math.floor(buying_power // qty) > 0:
                # Submit Order with Stop Loss

                order = submitOrder(api, ticker, qty, side, order_type, time_in_force, limit_price, stop_limit_price, client_order_id, new_stop)
                #print(order)
                if order.status == 'accepted':
                    print (f'Pending: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')

                    # Check that order if filled
                    status = watchOrderFilledStatus(api, APCA_API_KEY_ID, APCA_API_SECRET_KEY, ticker, qty, side, order_type, time_in_force, limit_price, client_order_id, new_stop)
                    
                    if status == 'filled' or status == 'partially_filled':
                        print (f'User: {APCA_API_KEY_ID} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {status}')
                        sendDiscordMessage(f'Success: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {status}.')
                        return f'Success: Order to {side} of {qty} shares of {ticker} at ${limit_price} was {status}.', 200
                    else:
                        print(f'Error: {status}')
                        sendDiscordMessage(f'Error: {status}.')
                        return f'Error: {status}.', 200
                else:
                    print(f'Error: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')
                    sendDiscordMessage(f'Error: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')
                    return f'Error: Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}', 400
            else:
                print(f'Error: User: {user} - Not enough Buying Power (${buying_power}) to buy {qty} shares of {ticker} at limit price ${limit_price}.')
                sendDiscordMessage(f'Error: User: {user} - Not enough Buying Power (${buying_power}) to buy {qty} shares of {ticker} at limit price ${limit_price}.')
                return f'Error: Not enough Buying Power (${buying_power}) to buy {qty} shares of {ticker} at limit price ${limit_price}.', 400
        elif int(position.qty) > 0 and side == 'sell':
            if int(qty) <= int(position.qty):
                order_type = 'limit'
                new_stop = None
                order = submitOrder(api, ticker, qty, side, order_type, time_in_force, limit_price, stop_limit_price, client_order_id, new_stop)
                #print(order)
                if order.status == 'accepted':
                    print (f'Pending: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')

                    # Check that order if filled
                    status = watchOrderFilledStatus(api, APCA_API_KEY_ID, APCA_API_SECRET_KEY, ticker, qty, side, order_type, time_in_force, limit_price, client_order_id, new_stop)
                    if status == 'filled' or status == 'partially_filled':
                        print (f'User: {APCA_API_KEY_ID} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {status}')
                        sendDiscordMessage(f'Success: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {status}.')
                        return f'Success: Order to {side} of {qty} shares of {ticker} at ${limit_price} was {status}.', 200
                    else:
                        print(f'Error: {status}')
                        sendDiscordMessage(f'Error: {status}.')
                        return f'Error: {status}.', 200
                else:
                    print(f'Error: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')
                    sendDiscordMessage(f'Error: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')
                    return f'Error: Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.', 400
            else:
                print(f'Error: User: {user} - You cannot sell {qty} when you only have {position.qty}.')
                sendDiscordMessage(f'Error: User: {user} - You cannot sell {qty} when you only have {position.qty}.')
                return f'Error: You cannot sell {qty} when you only have {position.qty}', 400
    else:
        print(f'Error: User {user} - Data Payload was empty!')
        sendDiscordMessage(f'Error: User {user} - Data Payload was empty!')
        return f'Error: Data Payload was empty!', 400 

if __name__ == '__main__':
    serve(app, host="0.0.0.0", port=8080)
