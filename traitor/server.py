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
from datetime import datetime, date, timezone, timedelta
from datetime import date
from discord import Webhook, RequestsWebhookAdapter
import inspect
import pytz
from dotenv import load_dotenv

load_dotenv()

# Configure Logging for Docker container
log = logging.getLogger()
log.setLevel(logging.DEBUG)
log.propagate = False
formatter = logging.Formatter('[%(asctime)s] %(pathname)s:%(lineno)d %(levelname)s - %(message)s','%m-%d %H:%M:%S')
consoleHandler = logging.StreamHandler(stdout)
consoleHandler.setFormatter(formatter)
log.addHandler(consoleHandler)

def marketIsOpen():
    now = datetime.now()
    tz_string = datetime.now(timezone.utc).astimezone().tzname()
    if tz_string == 'UTC':
        market_open = now.replace(hour=13, minute=30, second=0, microsecond=0)
        market_closed = now.replace(hour=20, minute=0, second=0, microsecond=0)
    elif tz_string == 'EDT' or tz_string == 'EST':
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_closed = now.replace(hour=16, minute=0, second=0, microsecond=0)

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

def checkOpenOrders(api, user, qty, side, ticker, position, inverse_mode):
    try:
        open_orders = api.list_orders()
    except Exception as e:
        log.error(e)
    else:
        if not open_orders:
            log.info('No Open Orders found.')
            return None
        else:
            log.info(f'{len(open_orders)} Open Orders were found.')
                
            open_order_qty = 0
            open_order_ticker_count = 0
            for open_order in open_orders:
                if  open_order.symbol == ticker:
                    open_order_qty += int(open_order.qty)
                    open_order_ticker_count += 1

            log.info(f'There are {open_order_ticker_count} Open Orders for {ticker}')

            for open_order in open_orders:
                if open_order.symbol == ticker:
                    log.info(f'Canceling {open_order.order_type} Order ID: {open_order.id}')
                    cancelled_order = api.cancel_order(order_id=open_order.id)
                    time.sleep(3)
                    log.info(cancelled_order)

            open_order_qty = 0
            open_order_ticker_count = 0

            for open_order in open_orders:
                if  open_order.symbol == ticker:
                    open_order_qty += int(open_order.qty)
                    open_order_ticker_count += 1

            log.info(f'Open Order Quantity is {open_order_qty}')

            if position is not None and int(position.qty) == open_order_qty and side == 'sell':
                log.error(f'Failed: User: {user} - There are already {open_order_ticker_count} Open Orders totaling {open_order_qty} shares of {ticker}. You have nothing to sell.')
                sendDiscordMessage(f'Failed: User: {user} - There are already {open_order_ticker_count} Open Orders totaling {open_order_qty} shares of {ticker}. You have nothing to sell.')
                return f'Failed: There are already {open_order_ticker_count} Open Orders totaling {open_order_qty} shares of {ticker}. You have nothing to sell.', 400
            
            elif position is not None and int(position.qty) <= qty:
                if int(open_order_qty) - qty == 0 and side == 'sell':
                    log.error(f'Failed: User: {user} - There is already an Open order to sell {open_order_qty} of {ticker}')
                    sendDiscordMessage(f'Failed: User: {user} - There is already an Open order to sell {open_order_qty} of {ticker}')
                    raise Exception (f'Failed: There is already an Open order to sell {open_order_qty} of {ticker}')

                elif int(open_order_qty) - qty > 0 and side == 'sell':
                    log.warning(f'Warning: User: {user} - You are selling {open_order_qty} of {ticker}, which would leave {int(open_order_qty) - qty} leftover.')
            
            elif position is not None and int(position.qty) > qty:
                if int(open_order_qty) - qty == 0 and side == 'sell':
                    if inverse_mode:
                        log.info(f'No Open Orders found for {ticker}. Using Position Quantity')
                    else:
                        log.error(f'Failed: User: {user} - There is already an Open order to sell {open_order_qty} of {ticker}.')
                        sendDiscordMessage(f'Failed: User: {user} - There is already an Open order to sell {open_order_qty} of {ticker}.')
                        raise Exception (f'Failed: There is already an Open order to sell {open_order_qty} of {ticker}')
                
                elif int(open_order_qty) - qty > 0 and side == 'sell':
                    log.warning(f'Warning: User: {user} - You are selling {open_order_qty} of {ticker}, which would leave {abs(int(open_order_qty) - qty)} leftover.')

def checkPositionExists(api, user, side, ticker, inverse_trade):
    try:
        portfolio = api.list_positions()
    except Exception as e:
        log.error(e)
    else:
        if not portfolio:
            log.info('No Positions were found.')
        else:
            log.info(f'{len(portfolio)} Positions were found.')

            position = next((position for position in portfolio if position.symbol == ticker), None)

            if position is not None and side == 'buy':
                log.info(f'User: {user} - You have a Position of {position.qty} shares in {ticker}')
                return position
            elif position is None and side == 'buy':
                log.info(f'No position for {ticker} found. Proceeding...')
            elif position is None and side == 'sell':
                if not inverse_trade:
                    log.info(f'Failed: User {user} - You have no position in {ticker} to sell.')
                    return None
                elif inverse_trade:
                    log.info(f'User {user} - Has no position in {ticker} to sell. Will buy Inverse Ticker.')
            elif position is not None and side == 'sell':
                log.info(f'User {user} - Has {position.qty} shares of {ticker} to sell')
                return position
            else:
                return None

def watchOrderFilledStatus(api, user, user_key, ticker, qty, side, order_type, time_in_force, limit_price, order_id, stop):
    new_buy_limit_price_mulitplier = 1.005

    new_buy_stop_price_multiplier = .9945

    new_buy_stop_limit_price_multiplier = .9925

    base_stop_price_minimum_multiplier = .9999

    new_sell_stop_limit_price_multiplier = .9925

    log.info(f'Checking Status for Original Order ID: {order_id}')
    try:
        order = api.get_order(order_id)
    except Exception as e:
        log.error(e)
    else:
        if order is not None:
            retry = 0
            order_id = order.id
            order_status = order.status
            log.info(f'Initial Order status is {order_status}')

            if not marketIsOpen():
                raise Exception(f"Failed: Order to {side} {qty} shares of {ticker} was submitted but cannot be filled - Market is Closed")
            else:
                marketOpen = marketIsOpen()

            while order_status == 'accepted' or order_status == 'new' and order_status != 'partially_filled' and order_status != 'filled' and order_status != 'canceled' and order_status != 'done_for_day' and order_status != 'replaced' and order_status != 'pending_replace' and retry < 5 and marketOpen:
                time.sleep(15)
                log.info(f'Order Retry is {retry}/5')

                if side == 'buy':
                    new_limit_price = round(float(order.limit_price) * new_buy_limit_price_mulitplier, 2)
                    if order is not None and order.legs is not None: 
                        stop_limit_price = round(float(order.legs[0].stop_price) * new_buy_stop_limit_price_multiplier, 2)
                        new_stop = round(float(order.legs[0].stop_price) * new_buy_stop_price_multiplier, 2)
                    else:
                        stop_limit_price = round(float(stop) * new_buy_stop_limit_price_multiplier, 2)
                        new_stop = round(float(stop) * new_buy_stop_price_multiplier, 2)

                    order = api.get_order(order_id)
                    order_id = order.id
                    order_status = order.status
                    log.info(f'Buy Order status is {order_status}')
                    if order_status == 'filled' or order_status == 'partially_filled' or order_status == 'canceled' or order_status == 'done_for_day' or order_status == 'replaced' or order_status == 'pending_replace':
                        log.info(f'Order Status is {order_status}. Breaking!')
                        break
#                    log.info(f'Modified Buy Order ID: {order_id}')
#                except tradeapi.rest.APIError as err:
#                    log.error(f'Error modifying buy order: {err.response.content}')
#                    raise#

#                log.info(f'Buy Limit Price was changed from {limit_price} to {new_limit_price}')
#                limit_price = new_limit_price
#                log.info(f'Buy Stop Loss Price was changed from {stop} to {new_stop}')
#                stop = new_stop
#                log.info(f'Buy Order status is: {order_status}')#

#            elif side == 'sell':
#                new_limit_price = round(float(order.limit_price) * new_sell_stop_limit_price_multiplier, 2)
#                order = api.get_order(order_id)
#                order_id = order.id
#                order_status = order.status
#                log.info(f'Sell Order status is {order_status}')

                    try:
                        order = api.replace_order(
                            order_id=order.id,
                            qty=qty,
                            time_in_force=time_in_force,
                            limit_price=new_limit_price
                        )
                        order_id = order.id
                        order_status = order.status

                        log.info(f'Modified Buy Order ID: {order_id}')
                    except tradeapi.rest.APIError as err:
                        log.error(f'Error modifying buy order: {err.response.content}')
                        raise
                    else:
                        log.info(f'Buy Limit Price was changed from {limit_price} to {new_limit_price}')
                        limit_price = new_limit_price
                        log.info(f'Buy Stop Loss Price was changed from {stop} to {new_stop}')
                        stop = new_stop
                        log.info(f'Buy Order status is: {order_status}')

                elif side == 'sell':
                    new_limit_price = round(float(order.limit_price) * new_sell_stop_limit_price_multiplier, 2)
                    order = api.get_order(order_id)
                    order_id = order.id
                    order_status = order.status
                    log.info(f'Sell Order status is {order_status}')

#                    log.info(f'Modified Sell Order ID: {order_id}')
#                except tradeapi.rest.APIError as err:
#                    log.error(f'Error modifying sell order: {err.response.content}')
#                    raise

#                log.info(f'Sell Limit Price was changed from {limit_price} to {new_limit_price}')
#                limit_price = new_limit_price
#                log.info(f'Sell Order status is: {order_status}')
#            else:
#                log.info(f'Order is None!')

                    if order_status == 'filled' or order_status == 'partially_filled' or order_status == 'canceled' or order_status == 'done_for_day' or order_status == 'replaced' or order_status == 'pending_replace':
                        log.info(f'Order Status is {order_status}. Breaking!')
                        sendDiscordMessage
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
                        raise

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
                return f'Failed: Retry limit reached to {side} {qty} of {ticker}. Aborting.'
            elif retry < 5 and order_status == 'filled' or order_status == 'partially_filled':
                return f'{order_status}'
            elif retry < 5 and order_status == 'canceled' or order_status == 'done_for_day' or order_status == 'replaced' or order_status == 'pending_replace':
                return f'Failed: {order_status}'
        else:
            log.warning('Order was empty!')
            return None

def submitOrder(api, ticker, qty, side, order_type, time_in_force, limit_price, stop_limit_price, stop):    
    if stop is None and stop_limit_price is None and side == 'sell':
        try:
            order = api.submit_order(
                symbol=ticker,
                qty=qty,
                side=side,
                type='limit',
                limit_price=limit_price,
                time_in_force=time_in_force,
            )
        except tradeapi.rest.APIError as e:
            if e == 'account is not authorized to trade':
                log.error(f'Failed: {e} - User: {user} - Check your API Keys are correct')
                return f'Failed: {e} - User: {user} - Check your API Keys correct', 500
            else:
                log.error(f'Error submitting Order: {e}')
                raise
        else:
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
                order_class='oto',
                stop_loss=dict(
                    stop_price=stop,
                    limit_price=stop_limit_price
                )
            )
        except tradeapi.rest.APIError as e:
            if e == 'account is not authorized to trade':
                log.error(f'Failed: {e} - User: {user} - Check your API Keys are correct')
                return f'Failed: {e} - User: {user} - Check your API Keys correct', 500
            else:
                log.error(f'Error submitting Order: {e}')
                raise
        else:
            return order
    return None

def orderFlow(api, user, user_key, ticker, position, buying_power, qty, side, order_type, time_in_force, limit_price, stop_limit_price, new_stop):
    if buying_power <= 0 and side == 'buy':
        log.info(f'Failed: User: {user} - You have no Buying Power: ${buying_power}')
        sendDiscordMessage(f'Failed: User: {user} - You have no Buying Power: ${buying_power}')
        return f'Failed: You have no Buying Power: ${buying_power}', 400
    elif buying_power > 0 and side == 'buy':
        if qty > 0:
            if math.floor(buying_power // qty) > 0:
                try:
                    order = submitOrder(api, ticker, qty, side, order_type, time_in_force, limit_price, stop_limit_price, new_stop)
                except Exception as e:
                    raise
                if order.status == 'accepted':
                    log.info (f'Pending: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')

                    try:
                        status = watchOrderFilledStatus(api, user, user_key, ticker, qty, side, order_type, time_in_force, limit_price, order.id, new_stop)
                    except Exception as e:
                        sendDiscordMessage(str(e))
                        return str(e), 500
                    if 'filled' in status or 'partially_filled' in status:
                        return f'Success: Order to {side} of {qty} shares of {ticker} at ${limit_price} was {status}.', 200
                    else:
                        log.info(status)
                        sendDiscordMessage(status)
                        return f'{status}', 200
                else:
                    log.info(f'Failed: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')
                    sendDiscordMessage(f'Failed: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')
                    return f'Failed: Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}', 400
            else:
                log.info(f'Failed: User: {user} - Not enough Buying Power (${buying_power}) to buy {qty} shares of {ticker} at limit price ${limit_price}.')
                sendDiscordMessage(f'Failed: User: {user} - Not enough Buying Power (${buying_power}) to buy {qty} shares of {ticker} at limit price ${limit_price}.')
                return f'Failed: Not enough Buying Power (${buying_power}) to buy {qty} shares of {ticker} at limit price ${limit_price}.', 400
        else:
            log.warning('Warning: Not buying 0 shares.')
    elif position is not None and int(position.qty) > 0 and side == 'sell':
        if int(qty) <= int(position.qty):
            order_type = 'limit'
            new_stop = None
            stop_limit_price = None

            try:
                order = submitOrder(api, ticker, qty, side, order_type, time_in_force, limit_price, stop_limit_price, new_stop)
            except:
                 raise

            if order.status == 'accepted':
                log.info (f'Pending: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')

                try:
                    status = watchOrderFilledStatus(api, user, user_key, ticker, qty, side, order_type, time_in_force, limit_price, order.id, new_stop)
                except Exception as e:
                    sendDiscordMessage(str(e))
                    return str(e), 500
                
                if 'filled' in status or 'partially_filled' in status:
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
                log.info(f'Failed: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')
                sendDiscordMessage(f'Failed: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.')
                return f'Failed: Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}.', 400
        else:
            log.info(f'Failed: User: {user} - You cannot sell {qty} when you only have {position.qty}.')
            sendDiscordMessage(f'Failed: User: {user} - You cannot sell {qty} when you only have {position.qty}.')
            return f'Failed: You cannot sell {qty} when you only have {position.qty}', 400
    else:
        log.info(f'Failed: User {user} - Data Payload was empty!')
        sendDiscordMessage(f'Failed: User {user} - Data Payload was empty!')
        return f'Failed: Data Payload was empty!', 400 

def getQuantity(api, user, ticker, inverse_mode, limit_price,buying_power, side):
    log.info(buying_power)
    log.info(inverse_mode)
    log.info(side)
    if side == 'buy':
        if buying_power - limit_price >= limit_price:
            temp_qty = math.floor(buying_power - limit_price)
            qty = math.floor(temp_qty // limit_price)
            log.info(f'{buying_power} - {limit_price} / {limit_price} = {qty}')
            return qty
        elif inverse_mode:
            log.info(f'Failed: User {user} - You dont have enough buying power to buy 1 share of {ticker}. Selling Inverse Ticker!')
            return 0
        else:
            log.info(f'Failed: User {user} - You dont have enough buying power to buy 1 share of {ticker}.')
            sendDiscordMessage(f'Failed: User {user} -You dont have enough buying power to buy 1 share of {ticker}.')
            return f'Failed: User {user} - You dont have enough buying power to buy 1 share of {ticker}.', 500
    elif side == 'sell':
        position = checkPositionExists(api, user, side, ticker, False)
        if position is not None:
            qty = int(position.qty)
            return qty
        elif inverse_mode:
            log.info(f'Failed: User {user} - You have no position in {ticker} to sell. Buying Inverse Ticker! ')
            return 0
        else:
            log.info(f'Failed: User {user} - You have no position in {ticker} to sell.')
            sendDiscordMessage(f'Failed: User {user} - Failed: User {user} - You have no position in {ticker} to sell.')
            return f'Failed: User {user} - Failed: User {user} - You have no position in {ticker} to sell.', 500

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
        log.info(f'Failed: APCA_API_KEY_ID is not set!')
        sendDiscordMessage(f'Failed: APCA_API_KEY_ID is not set!')
        return 'APCA_API_KEY_ID is not set!', 400
    if request.args.get('APCA_API_SECRET_KEY') is None:
        log.info(f'Failed: APCA_API_SECRET_KEY is not set!')
        sendDiscordMessage(f'Failed: APCA_API_SECRET_KEY is not set!')
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

        # Get Quantity
        if 'qty' not in json_data:
            qty = getQuantity(api, user, ticker, inverse_mode, limit_price,buying_power, side)        
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

        # Check if Account is Blocked
        if account.trading_blocked:
            sendDiscordMessage(f'Failed: User: {user} - Account is currently restricted from trading.')
            return 'Account is currently restricted from trading.', 400

        if inverse_mode:

            if side == 'buy':
                inverse_side = 'sell'

                inverse_position = checkPositionExists(api, user, inverse_side, inverse_ticker, True)
                print(inverse_position)
                # Check that inverse_position is not empty and is a tuple
                if inverse_position is not None and type(inverse_position) == 'tuple':
                    return f'{inverse_position}', 500
                
                if inverse_position is not None:
                    try:
                        inverse_last_trade = requests.get(f"https://api.twelvedata.com/price?symbol={inverse_ticker}&apikey={API_KEY}").json()
                        log.info(inverse_last_trade)
                    except requests.exceptions.HTTPError as e:
                        log.error(e)
                        return f'{e}', 500

                    if 'price' in inverse_last_trade:
                        inverse_limit_price = round(float(inverse_last_trade['price']), 2)
                    else:
                        log.error(inverse_last_trade)
                        raise

                    log.info(f'Last Price for {inverse_ticker} was {inverse_limit_price}')

                    inverse_open_orders = checkOpenOrders(api, user, qty, inverse_side, inverse_ticker, inverse_position, inverse_mode)
                    log.info(f'Open Orders is {inverse_open_orders}')
                    try:
                        inverser_order_results = orderFlow(api, user, user_key, inverse_ticker, inverse_position, buying_power, int(inverse_position.qty), 'sell', order_type, time_in_force, inverse_limit_price, 'None', 'None')
                    except Exception as e:
                        log.info(str(e))
                        sendDiscordMessage(str(e))

                    log.info(inverser_order_results[0])
                    sendDiscordMessage(inverser_order_results[0])
                else:
                    log.info(f'No Positions or Orders for {inverse_ticker}. Skipping Sell Order Flow')
                    inverser_order_results = None

                if inverser_order_results is not None:
                    log.info(f' {inverser_order_results[0]}')
                    sendDiscordMessage(f'{inverser_order_results[0]}')
            
                ticker_position = checkPositionExists(api, user, side, ticker, False)
                
                open_orders = checkOpenOrders(api, user, qty, side, ticker, ticker_position, inverse_mode)
                try:
                    order_results = orderFlow(api, user, user_key, ticker, ticker_position, buying_power, qty, side, order_type, time_in_force, limit_price, stop_limit_price, new_stop)
                except Exception as e:
                    log.info(str(e))
                    sendDiscordMessage(str(e))
                    return str(e), 500
                log.info(order_results[0])
                sendDiscordMessage(order_results[0])
                return order_results[0]
            elif side == 'sell':
                inverse_side = 'buy'

                ticker_position = checkPositionExists(api, user, side, ticker, False)
                open_orders = checkOpenOrders(api, user, qty, side, ticker, ticker_position, inverse_mode)
                
                if ticker_position is not None:
                    try:
                        order_results = orderFlow(api, user, user_key, ticker, ticker_position, buying_power, qty, side, order_type, time_in_force, limit_price, stop_limit_price, new_stop)
                    except Exception as e:
                        return str(e), 500

                    if order_results is not None:
                        log.info(order_results[0])

                inverse_position = checkPositionExists(api, user, inverse_side, inverse_ticker, True)

                # Check if you already have inverse_position
                if inverse_position is not None and type(inverse_position) == 'tuple':
                    return f'{inverse_position}', 500
                print(inverse_position)

                # Otherwies buy the Inverse Ticker
                try:
                    inverse_last_trade = requests.get(f"https://api.twelvedata.com/price?symbol={inverse_ticker}&apikey={API_KEY}").json()
                except requests.exceptions.HTTPError as e:
                    status_code = e.response.status_code
                    while status_code == '403':
                        try:
                            inverse_last_trade = requests.get(f"https://api.twelvedata.com/price?symbol={inverse_ticker}&apikey={API_KEY}").json()
                            status_code = e.response.status_code
                        except requests.exceptions.HTTPError as e:
                            log.error(e)
                            return str(e), 500
                    log.error(e)
                    return f'{e}', 500

                if 'price' in inverse_last_trade:
                    inverse_limit_price = round(float(inverse_last_trade['price']), 2)
                else:
                    log.error(inverse_last_trade)
                    raise

                log.info(f'Last Price for {inverse_ticker} was {inverse_limit_price}')

                inverse_open_orders = checkOpenOrders(api, user, qty, inverse_side, inverse_ticker, inverse_position, inverse_mode)
                
                tz = pytz.timezone('US/Eastern')
                today = datetime.today() - timedelta(minutes=15)
                earlier = today - timedelta(minutes=30)

                loc_today = tz.localize(today).replace(microsecond=0).isoformat()
                loc_earlier = tz.localize(earlier).replace(microsecond=0).isoformat()
                log.info(loc_today)
                log.info(loc_earlier)

                try:
                    res = requests.get(f'https://api.twelvedata.com/time_series?symbol={inverse_ticker}&interval=1min&apikey={API_KEY}').json()
                    last_inverse_trade = res['values'][0]
                except Exception as e:
                    log.info(str(e))
                    sendDiscordMessage(str(e))
                    return str(e), 500
                log.info(f'Limit Price is {inverse_limit_price}')

                inverse_stop = round(float(last_inverse_trade['close']) * base_stop_price_multiplier, 2)
                inverse_stop_limit = round(float(last_inverse_trade['close']) * base_stop_limit_price_multiplier, 2)
                while inverse_stop_limit >= inverse_stop:
                    inverse_stop_limit = round(inverse_stop_limit * .99, 2)
                    log.info(f'Inverse Stop Price is {inverse_stop}')
                    log.info(f'Inverse Stop Limit Price is {inverse_stop_limit}')

                inverse_qty = getQuantity(api, user, inverse_ticker, inverse_mode, limit_price, buying_power, inverse_side)
                log.info(f'Inverse Quantity is {inverse_qty}')
                try:
                    inverser_order_results = orderFlow(api, user, user_key, inverse_ticker, inverse_position, buying_power, inverse_qty, inverse_side, order_type, time_in_force, inverse_limit_price, inverse_stop_limit, inverse_stop)
                except Exception as e:
                    return str(e), 500

                if inverser_order_results is not None:
                    print(inverser_order_results[0])
                    sendDiscordMessage(inverser_order_results[0])
                    return inverser_order_results[0]
                else:
                    log.info(f'Inverse Position Result was {inverser_order_results}')
                    sendDiscordMessage(f'Inverse Position Result was {inverser_order_results}')
                    return f'Inverse Position Result was {inverser_order_results}', 200
        else:
            ticker_position = checkPositionExists(api, user, side, ticker, False)
            
            open_orders = checkOpenOrders(api, user, qty, side, ticker, ticker_position, inverse_mode)
            
            try:
                order_results = orderFlow(api, user, user_key, ticker, ticker_position, buying_power, qty, side, order_type, time_in_force, limit_price, stop_limit_price, new_stop)
            except Exception as e:
                return str(e), 500

            log.info(order_results[0])
            sendDiscordMessage(order_results[0])
            return order_results[0]
        #return 'foo', 500
    return 'bar', 500

if __name__ == '__main__':
    serve(app, host="0.0.0.0", port=8080)
