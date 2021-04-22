# TODO
# - Remove Stop from Sell Price calculation
# Need to make stop and stop_limit_price optional variable

from flask import Flask, request
import requests
import os
import alpaca_trade_api as tradeapi
from alpaca_trade_api.common import URL
from alpaca_trade_api.rest import TimeFrame
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
from datetime import date
from discord import Webhook, RequestsWebhookAdapter
import inspect

# Configure Logging for Docker container
log = logging.getLogger('app')
log.setLevel(logging.DEBUG)
#logFormatter = logging.Formatter("%(name)-12s %(asctime)s %(levelname)-8s %(filename)s:%(funcName)s %(message)s")
consoleHandler = logging.StreamHandler(stdout)
#consoleHandler.setFormatter(logFormatter)
log.addHandler(consoleHandler)

def marketIsOpen():
    now = datetime.now()
    market_open = now.replace(hour=13, minute=30, second=0, microsecond=0)
    market_closed = now.replace(hour=20, minute=0, second=0, microsecond=0)
    #market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    #market_closed = now.replace(hour=16, minute=0, second=0, microsecond=0)

    if now < market_open or now > market_closed:
        log.info(f"Market is Closed - {time.strftime('%l:%M %p')}")
        return False
    else:
        log.info(f"Market is Open - {time.strftime('%l:%M %p')}")
        return True
    return True

def sendDiscordMessage(message):
    url = "https://discord.com/api/webhooks/831890918796820510/OWR1HucrnJzHdTE-vASdf5EIbPC1axPikD4D5lh0VBn413nARUW4mla3xPjZHWCK9-9P"
    debug_url = "https://discord.com/api/webhooks/832603152330784819/yA1ZK7ymT3XBU0fJtg0cKZ9RNMPS0C9h0IDABmZZd_KIquToIODOSVOJ6k2aJQSrwC8I"
    webhook = Webhook.from_url(url, adapter=RequestsWebhookAdapter())

    if message is None:
        log.warning('Error: Discord Message is empty!')
    elif 'Error' in message:
        webhook = Webhook.from_url(debug_url, adapter=RequestsWebhookAdapter())
        msg = f'```diff\n-{message}\n```'
        webhook.send(msg)
    elif 'Failed' in message:
        msg = f'```diff\n-{message}\n```'
        webhook.send(msg)
    elif 'Success' in message:
        msg = f'```diff\n+{message}\n```'
        webhook.send(msg)
    else:
        webhook = Webhook.from_url(debug_url, adapter=RequestsWebhookAdapter())
        webhook.send(message)

def checkOpenOrders(api, user, qty, side, ticker, position):
    open_orders = api.list_orders()
    print(side)
    # Check if there are any open orders
    if not open_orders:
        log.info('No Open Orders found.')
    else:
        log.info(f'{len(open_orders)} Open Orders were found.')
            
    open_order_qty = 0
    open_order_ticker_count = 0
    for open_order in open_orders:
        if  open_order.symbol == ticker:
            open_order_qty += int(open_order.qty)
            open_order_ticker_count += 1

    log.info(f'There are {open_order_ticker_count} Open Orders for {ticker}')
    #log.info(position)
    #log.info(int(position.qty))
    #log.info(f'position qty is less than or equal to order qty: {int(position.qty) <= qty}')
    #log.info(f'position qty is greater than order qty: {int(position.qty) > qty}')
    #log.info(f'open order qty minus order qty is less than or equal to 0: {int(open_order_qty) - qty <= 0}')
    #log.info(f'open order qty minus order qty is greater than 0: {int(open_order_qty) - qty > 0}')
    for open_order in open_orders:
        if open_order.symbol == ticker:
            log.info(f'Canceling {open_order.order_type} Order ID: {open_order.id}')
            cancelled_order = api.cancel_order(order_id=open_order.id)
            time.sleep(3)
            log.info(cancelled_order)

    open_order_qty = 0
    open_order_ticker_count = 0
    open_orders = api.list_orders()
    for open_order in open_orders:
        if  open_order.symbol == ticker:
            open_order_qty += int(open_order.qty)
            open_order_ticker_count += 1

    print(position)
    if position is not None and int(position.qty) == open_order_qty and side == 'sell':
        log.error(f'Error: User: {user} - There are already {open_order_ticker_count} Open Orders totaling {open_order_qty} shares of {ticker}. You have nothing to sell.')
        sendDiscordMessage(f'Error: User: {user} - There are already {open_order_ticker_count} Open Orders totaling {open_order_qty} shares of {ticker}. You have nothing to sell.')
        return f'Error: There are already {open_order_ticker_count} Open Orders totaling {open_order_qty} shares of {ticker}. You have nothing to sell.', 400
    elif position is not None and int(position.qty) <= qty:
        if int(open_order_qty) - qty == 0 and side == 'sell':
            log.error(f'Error: User: {user} - There is already an Open order to sell {open_order_qty} of {ticker}')
            sendDiscordMessage(f'Error: User: {user} - There is already an Open order to sell {open_order_qty} of {ticker}')
            return f'Error: There is already an Open order to sell {open_order_qty} of {ticker}', 400

        elif int(open_order_qty) - qty > 0 and side == 'sell':
            log.warning(f'Warning: User: {user} - You are selling {open_order_qty} of {ticker}, which would leave {int(open_order_qty) - qty} leftover.')
    elif position is not None and int(position.qty) > qty:
        if int(open_order_qty) - qty == 0 and side == 'sell':
            log.error(f'Error: User: {user} - There is already an Open order to sell {open_order_qty} of {ticker}.')
            sendDiscordMessage(f'Error: User: {user} - There is already an Open order to sell {open_order_qty} of {ticker}.')
            return f'Error: There is already an Open order to sell {open_order_qty} of {ticker}.', 400
        elif int(open_order_qty) - qty > 0 and side == 'sell':
            log.warning(f'Warning: User: {user} - You are selling {open_order_qty} of {ticker}, which would leave {abs(int(open_order_qty) - qty)} leftover.')

    return None

def checkPositionExists(api, user, side, ticker, inverse_trade):
    # Get Positions
    portfolio = api.list_positions()

    if not portfolio:
        log.info('No Positions were found.')
    else:
        log.info(f'{len(portfolio)} Positions were found.')

    position = next((position for position in portfolio if position.symbol == ticker), None)

    # Check if there is already a Position for Ticker
    if position is not None and side == 'buy':
        log.info(f'User: {user} - You have a Position of {position.qty} shares in {ticker}')
        return position
    elif position is None and side == 'buy':
        log.info(f'No position for {ticker} found. Proceeding...')
    elif position is None and side == 'sell':
        if not inverse_trade:
            log.info(f'User {user} - You have no position in {ticker} to sell.')
            sendDiscordMessage(f'Error: User {user} - You have no position in {ticker} to sell.')
            return None
        elif inverse_trade:
            log.info(f'User {user} - Has no position in {ticker} to sell. Will buy Inverse Ticker.')
    elif position is not None and side == 'sell':
        log.info(f'User {user} - Has {position.qty} shares of {ticker} to sell')
        return position
    else:
        return None

def watchOrderFilledStatus(api, user, user_key, ticker, qty, side, order_type, time_in_force, limit_price, client_order_id, stop):
    log.info(f'Checking Status for Client Order ID: {client_order_id}')
    order = api.get_order_by_client_order_id(client_order_id)

    if order is not None:
        retry = 0
        order_id = order.id
        order_status = order.status
        log.info(f'Initial Order status is {order_status}')

        log.info(f'Original Buy Order ID: {order_id}')

        if not marketIsOpen():
            raise Exception(f"Error: Order to {side} {qty} shares of {ticker} was submitted but cannot be filled - Market is Closed")
        else:
            marketOpen = marketIsOpen()

        while order_status == 'accepted' or order_status == 'new' and order_status != 'partially_filled' and order_status != 'filled' and order_status != 'canceled' and order_status != 'done_for_day' and order_status != 'replaced' and order_status != 'pending_replace' and retry < 5 and marketOpen:
            time.sleep(15)
            log.info(f'Order Retry is {retry}')

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
                log.info(f'Buy Order status is {order_status}')

                if order_status == 'filled' or order_status == 'partially_filled' or order_status == 'canceled' or order_status == 'done_for_day' or order_status == 'replaced' or order_status == 'pending_replace':
                    log.info(f'Order Status is {order_status}. Breaking!')
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
                    log.info(f'Modified Buy Order ID: {order_id}')
                except tradeapi.rest.APIError as err:
                    log.error(f'Error modifying buy order: {err.response.content}')
                    return err

                log.info(f'Buy Limit Price was changed from {limit_price} to {new_limit_price}')
                limit_price = new_limit_price
                log.info(f'Buy Stop Loss Price was changed from {stop} to {new_stop}')
                stop = new_stop
                log.info(f'Buy Order status is: {order_status}')
            # Modify Sell Limit Price
            elif side == 'sell':
                new_limit_price = round(float(order.limit_price) * .9925, 2)
                order = api.get_order(order_id)
                order_id = order.id
                order_status = order.status
                log.info(f'Sell Order status is {order_status}')

                if order_status == 'filled' or order_status == 'partially_filled' or order_status == 'canceled' or order_status == 'done_for_day' or order_status == 'replaced' or order_status == 'pending_replace':
                    log.info(f'Order Status is {order_status}. Breaking!')
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
                    log.info(f'Modified Sell Order ID: {order_id}')
                except tradeapi.rest.APIError as err:
                    log.error(f'Error modifying sell order: {err.response.content}')
                    return err

                log.info(f'Sell Limit Price was changed from {limit_price} to {new_limit_price}')
                limit_price = new_limit_price
                log.info(f'Sell Order status is: {order_status}')
            else:
                log.info(f'Order is None!')

            marketOpen = marketIsOpen()
            time.sleep(10)
            retry += 1
    
        order = api.get_order(order_id)
        order_id = order.id
        order_status = order.status
        log.info(f'Last Order ID: {order_id}')
        log.info(f'Last Order status is: {order_status}')

    if retry >= 5:
        return f'Error: Retry limit reached to {side} {qty} of {ticker}. Aborting.'
    elif retry < 5 and order_status == 'filled' or order_status == 'partially_filled':
        return f'{order_status}'
    elif retry < 5 and order_status == 'canceled' or order_status == 'done_for_day' or order_status == 'replaced' or order_status == 'pending_replace':
        return f'Failed: {order_status}'
    else:
        log.info('Order was empty!')
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
                log.error(f'Error: {e} - Check your API Keys are correct')
                return f'Error: {e} - Check your API Keys correct', 500
            else:
                log.error(f'Error submitting Order: {e}')
                return f'Error submitting Order: {e}', 500
        return order
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
                log.error(f'Error: {e} - Check your API Keys are correct')
                return f'Error: {e} - Check your API Keys correct', 500
            else:
                log.error(f'Error submitting Order: {e}')
                return f'Error submitting Order: {e}', 500
        return order
    return None

def orderFlow(api, user, user_key, ticker, position, buying_power, qty, side, order_type, time_in_force, limit_price, stop_limit_price, client_order_id, new_stop):
    # Order Flow
    if buying_power <= 0 and side == 'buy':
        log.error(f'Error: User: {user} - You have no Buying Power: ${buying_power}')
        sendDiscordMessage(f'Error: User: {user} - You have no Buying Power: ${buying_power}')
        return f'Error: You have no Buying Power: ${buying_power}', 400
    elif buying_power > 0 and side == 'buy':
        if qty > 0 and math.floor(buying_power // qty) > 0:
            # Submit Order with Stop Loss

            order = submitOrder(api, ticker, qty, side, order_type, time_in_force, limit_price, stop_limit_price, client_order_id, new_stop)
            
            #log.info(order)
            if order.status == 'accepted':
                log.info (f'Pending: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')

                # Check that order if filled
                try:
                    status = watchOrderFilledStatus(api, user, user_key, ticker, qty, side, order_type, time_in_force, limit_price, client_order_id, new_stop)
                except Exception as e:
                    sendDiscordMessage(str(e))
                    return str(e), 500
                #log.info(status)
                if 'filled' in status or 'partially_filled' in status:
                    log.info (f'User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {status}')
                    sendDiscordMessage(f'Success: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {status}.')
                    return f'Success: Order to {side} of {qty} shares of {ticker} at ${limit_price} was {status}.', 200
                else:
                    log.info(status)
                    sendDiscordMessage(status)
                    return f'{status}', 200
            else:
                log.error(f'Error: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')
                sendDiscordMessage(f'Error: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')
                return f'Error: Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}', 400
        else:
            log.error(f'Error: User: {user} - Not enough Buying Power (${buying_power}) to buy {qty} shares of {ticker} at limit price ${limit_price}.')
            sendDiscordMessage(f'Error: User: {user} - Not enough Buying Power (${buying_power}) to buy {qty} shares of {ticker} at limit price ${limit_price}.')
            return f'Error: Not enough Buying Power (${buying_power}) to buy {qty} shares of {ticker} at limit price ${limit_price}.', 400
    elif int(position.qty) > 0 and side == 'sell':
        if int(qty) <= int(position.qty):
            order_type = 'limit'
            new_stop = None
            stop_limit_price = None
            order = submitOrder(api, ticker, qty, side, order_type, time_in_force, limit_price, stop_limit_price, client_order_id, new_stop)
            log.info(order)
            
            if order.status == 'accepted':
                log.info (f'Pending: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')

                # Check that order if filled
                try:
                    status = watchOrderFilledStatus(api, user, user_key, ticker, qty, side, order_type, time_in_force, limit_price, client_order_id, new_stop)
                except Exception as e:
                    sendDiscordMessage(str(e))
                    return str(e), 500
                #log.info(status)
                
                if 'filled' in status or 'partially_filled' in status:
                    log.info (f'User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {status}')
                    sendDiscordMessage(f'Success: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {status}.')
                    return f'Success: Order to {side} of {qty} shares of {ticker} at ${limit_price} was {status}.', 200
                elif 'Failed' in status:
                    log.warning(status)
                    sendDiscordMessage(status)
                    return f'{status}', 200
                elif 'Error' in status:
                    log.error(status)
                    sendDiscordMessage(status)
                    return f'{status}', 500
                else:
                    log.error(status)
                    sendDiscordMessage(status)
                    return f'{status}', 500
            else:
                log.error(f'Error: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')
                sendDiscordMessage(f'Error: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')
                return f'Error: Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.', 400
        else:
            log.error(f'Error: User: {user} - You cannot sell {qty} when you only have {position.qty}.')
            sendDiscordMessage(f'Error: User: {user} - You cannot sell {qty} when you only have {position.qty}.')
            return f'Error: You cannot sell {qty} when you only have {position.qty}', 400
    else:
        log.error(f'Error: User {user} - Data Payload was empty!')
        sendDiscordMessage(f'Error: User {user} - Data Payload was empty!')
        return f'Error: Data Payload was empty!', 400 

app = Flask(__name__)

app.debug = True

@app.route('/', methods=["POST"])

def alpaca():
#    if request.args.get('token') is None:
#        return 'Unauthorized', 401#

#    if request.args.get('token') != "XcYrXRtFXaNjTFXTFtQDMbsrmnmwygvuTa":
#        return 'Unauthorized', 401
    
    #if not marketIsOpen():
    #    return f"Market is Closed - {time.strftime('%l:%M %p')}", 400

    base_limit_price_mulitplier = 1

    base_stop_price_multiplier = .9925

    base_stop_limit_price_multiplier = .99935

    base_stop_price_minimum_multiplier = .9999

    if request.args.get('APCA_API_KEY_ID') is None:
        log.error(f'Error: APCA_API_KEY_ID is not set!')
        sendDiscordMessage(f'Error: APCA_API_KEY_ID is not set!')
        return 'APCA_API_KEY_ID is not set!', 400
    if request.args.get('APCA_API_SECRET_KEY') is None:
        log.error(f'Error: APCA_API_SECRET_KEY is not set!')
        sendDiscordMessage(f'Error: APCA_API_SECRET_KEY is not set!')
        return 'APCA_API_SECRET_KEY is not set!', 400

    user = request.args.get('APCA_API_KEY_ID')
    user_key = request.args.get('APCA_API_SECRET_KEY')

    log.info(f'\n\nOrder received for User: {user}')

    data = request.get_data()

    if(request.data):
        try:
            json_data = json.loads(data)
        except json.decoder.JSONDecodeError as e:
            log.error(f'Error parsing JSON body for User {user}: {e}')
            sendDiscordMessage(f'Error parsing JSON body for User {user}: {e}')
            return f'Error parsing JSON: {e}', 400

        if json_data['ticker'] is None:
            log.error(f'Error: User: {user} - Ticker parameter is not set!')
            sendDiscordMessage(f'Error: User: {user} - Ticker parameter is not set!')
            return 'Error: Ticker parameter is not set!', 400

        if 'inverse_ticker' not in json_data:
            log.info(f'Info: User: {user} - Inverse Ticker parameter is not set! Using Normal Trading Mode')
            inverse_mode = False
            inverse_ticker = None
        elif json_data['inverse_ticker'] is not None:
            log.info(f'Info: User: {user} - Inverse Ticker parameter is set! Using Inverse Trading Mode')
            inverse_mode = True
            inverse_ticker = json_data['inverse_ticker']

        if json_data['price'] is None:
            log.error(f'Error: User: {user} - Price parameter is not set!')
            sendDiscordMessage(f'Error: User: {user} - Price parameter is not set!')
            return 'Error: Price parameter is not set!', 400
        if json_data['side'] is None:
            log.error(f'Error: User: {user} - Side parameter is not set!')
            sendDiscordMessage(f'Error: User: {user} - Side parameter is not set!')
            return 'Error: Side parameter is not set!', 400
        
        ticker = json_data['ticker']
        price = json_data['price']
        side = json_data['side']

        if side.strip() != 'buy' and side.strip() != 'sell':
            log.error(f'Error: User: {user} - Side is {side}. Can only be Buy or Sell!')
            sendDiscordMessage(f'Error: User: {user} - Side is {side}. Can only be Buy or Sell!')
            return f'Side is {side}. Can only be buy or sell!', 400

        # Check if Live or Paper Trading
        if user[0:2] == 'PK':
            api = tradeapi.REST(user, user_key, 'https://paper-api.alpaca.markets')
            log.info('Using Paper Trading API')
        elif user[0:2] == 'AK':
            api = tradeapi.REST(user, user_key, 'https://api.alpaca.markets')
            log.info('Using Live Trading API')
        else:
            log.error(f'Error: API Key {user} is malformed.')
            sendDiscordMessage(f'Error: API Key {user} is malformed.')
            return 'Error: API Key {user} is malformed.', 400

        # Get Account information
        account = api.get_account()

        # Get available Buying Power
        buying_power = float(account.buying_power)       
        log.info(f'Buying Power is ${buying_power}')

        # Get Time-In-Force
        time_in_force_condition = 'time_in_force' not in json_data
        if time_in_force_condition:
            time_in_force = 'gtc'
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


        # Print Variables
        log.info(f'Ticker is {ticker}')
        log.info(f'Inverse Ticker is {inverse_ticker}')
        log.info(f'Using Inverse Trading Mode? {inverse_mode}')
        log.info(f'Original Price is ${price}')
        log.info(f'Side is {side}')
        log.info(f'Time-In-Force is {time_in_force}')
        log.info(f'Order Type is {order_type}')
        log.info(f'Quantity is {qty}')

        # Get Stop Loss
        if 'stop' not in json_data and side == 'buy':
            log.error(f'Error: User: {user} - No Stop Loss was given for Buy. Stop Loss is required.')
            sendDiscordMessage(f'Error: User: {user} - No Stop Loss was given for Buy. Stop Loss is required.')
            return f'Error: No Stop Loss was given for Buy. Stop Loss is required.', 400
        elif 'stop' in json_data:
            stop = int(json_data['stop'])

        if side == 'buy':
             # Set Buy Limit Price higher to ensure it gets filled
            #limit_price = round(float(price) * 1.005, 2)
            #log.info(f'Updated Limit Price is ${limit_price}')
            limit_price = price * base_limit_price_mulitplier
            diff = round(abs(limit_price - price),2)

            log.info(f'Buying Limit Price is: ${price} + ${diff} = ${limit_price}')

            log.info(f'Original Stop Price is ${stop}')
            new_stop = round(stop * base_stop_price_multiplier, 2)

            # Make sure Limit Price is greater than Stop Price
            if limit_price - new_stop < 0:
                new_stop = round(new_stop * base_stop_price_minimum_multiplier, 2)

            log.info(f'Updated Stop Price is ${new_stop}')

            stop_limit_price = round(new_stop * base_stop_limit_price_multiplier, 2)

            log.info(f'Stop Limit Price is ${stop_limit_price}')

            if new_stop - stop_limit_price < 0:
                stop_limit_price = round(stop_limit_price * .999, 2)
                log.info(f'Modifiying Stop Limit Price to ${stop_limit_price}')

        elif side == 'sell':
            # Set Sell Limit Price lower to ensure it gets filled
            #limit_price = round(abs(float(price) * .995), 2)
            #log.info(f'Updated Limit Price is ${limit_price}')
            limit_price = price

            new_stop = None

            #log.info(f'Updated Stop Price is ${new_stop}')

            stop_limit_price = None
            #log.info(f'Updated Stop Limit Price is ${stop_limit_price}')

            diff = round(abs(limit_price - price),2)

            log.info(f'Selling Limit Price is: ${price} - ${diff} = ${limit_price}')

        # Check if Account is Blocked
        if account.trading_blocked:
            sendDiscordMessage(f'Error: User: {user} - Account is currently restricted from trading.')
            return 'Account is currently restricted from trading.', 400

        if inverse_mode:
            # Generate Order ID
            inverse_client_order_id = str(uuid.uuid4())

            if side == 'buy':
                inverse_side = 'sell'

                inverse_position = checkPositionExists(api, user, inverse_side, inverse_ticker, True)

                # Check that inverse_position is not empty and is a tuple
                if inverse_position is not None and type(inverse_position) == 'tuple':
                    return f'{inverse_position}', 500
                print(inverse_position)
                try:
                    inverse_last_trade = api.get_last_trade(inverse_ticker)
                except requests.exceptions.HTTPError as e:
                    log.error(e)
                    return f'{e}', 500

                inverse_limit_price = inverse_last_trade.price

                log.info(f'Last Price for {inverse_ticker} was {inverse_limit_price}')

                inverse_open_orders = checkOpenOrders(api, user, qty, inverse_side, inverse_ticker, inverse_position)
                
                if inverse_position is not None:

                    inverser_order_results = orderFlow(api, user, user_key, inverse_ticker, inverse_position, buying_power, qty, 'sell', order_type, time_in_force, inverse_limit_price, 'None', inverse_client_order_id, 'None')
                else:
                    log.info(f'No Positions or Orders for {inverse_ticker}. Skipping Sell Order Flow')
                    inverser_order_results = None

                if inverser_order_results is not None:
                    print(inverser_order_results)
            
                # Generate Order ID
                client_order_id = str(uuid.uuid4())
                ticker_position = checkPositionExists(api, user, side, ticker, False)
                
                open_orders = checkOpenOrders(api, user, qty, side, ticker, ticker_position)
                
                order_results = orderFlow(api, user, user_key, ticker, ticker_position, buying_power, qty, side, order_type, time_in_force, limit_price, stop_limit_price, client_order_id, new_stop)
                return order_results
            elif side == 'sell':
                inverse_side = 'buy'

                # Generate Order ID
                client_order_id = str(uuid.uuid4())
                ticker_position = checkPositionExists(api, user, side, ticker, False)
                
                open_orders = checkOpenOrders(api, user, qty, side, ticker, ticker_position)
                
                if ticker_position is not None:
                    order_results = orderFlow(api, user, user_key, ticker, ticker_position, buying_power, qty, side, order_type, time_in_force, limit_price, stop_limit_price, client_order_id, new_stop)

                    if order_results is not None:
                        print(order_results)

                inverse_position = checkPositionExists(api, user, inverse_side, inverse_ticker, True)

                # Check that inverse_position is not empty and is a tuple
                if inverse_position is not None and type(inverse_position) == 'tuple':
                    return f'{inverse_position}', 500
                print(inverse_position)

                try:
                    inverse_last_trade = api.get_last_trade(inverse_ticker)
                except requests.exceptions.HTTPError as e:
                    log.error(e)
                    return f'{e}', 500

                inverse_limit_price = inverse_last_trade.price

                log.info(f'Last Price for {inverse_ticker} was {inverse_limit_price}')

                inverse_open_orders = checkOpenOrders(api, user, qty, inverse_side, inverse_ticker, inverse_position)
                
                inverse_stop = api.get_bars(inverse_position, TimeFrame.Hour, date.today(), date.today(), limit=10, adjustment='raw').df
                print(inverse_stop)
                inverser_order_results = orderFlow(api, user, user_key, inverse_ticker, inverse_position, buying_power, qty, inverse_side, order_type, time_in_force, inverse_limit_price, 'None', inverse_client_order_id, 'None')

                if inverser_order_results is not None:
                    print(inverser_order_results)

                return inverser_order_results
        else:
            client_order_id = str(uuid.uuid4())
            ticker_position = checkPositionExists(api, user, side, ticker, False)
            
            open_orders = checkOpenOrders(api, user, qty, side, ticker, ticker_position)
            
            order_results = orderFlow(api, user, user_key, ticker, ticker_position, buying_power, qty, side, order_type, time_in_force, limit_price, stop_limit_price, client_order_id, new_stop)
            return order_results
        #return 'foo', 500
    return 'bar', 500

if __name__ == '__main__':
    serve(app, host="0.0.0.0", port=8080)
