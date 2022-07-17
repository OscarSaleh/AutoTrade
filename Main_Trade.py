# ==================================================================================================================
# Main_Trade.py
# ==================================================================================================================
# This program places orders automatically using TD Ameritrade interface.
# ==================================================================================================================
# Date      User         Remarks
# 20201028  Oscar Saleh  Original program.
#                        Use Single Buy and Sell Orders.
# 20201029  Oscar Saleh  Implemented Conditional Orders.
# 20201030  Oscar Saleh  Improved logic to get Prior Order Buy Price.
# 20201031  Oscar Saleh  Implemented place_order, update_order_status and reset_order methods in str_lineOrderStatus.
# 20201102  Oscar Saleh  Added Period and Type on Order Status to classify orders.
#                        Use new directory structure to segregate by account number.
# 20201105  Oscar Saleh  Improved Display routine.
# 20201107  Oscar Saleh  Modified RSI Calculation. Store historical stock prices to build repository.
# 20201221  Oscar Saleh  Corrected TokenCheck routine to keep latest values in memory.
# 20210111  Oscar Saleh  Updated api_GetTokenAuthorization routine to keep latest values in memory.
# 20210115  Oscar Saleh  Improved Error displays; include additional fields. Save OrderStatus before exit.
# 20210125  Oscar Saleh  Saved OrderStatus as contingency when placing/updating orders.
# 20210129  Oscar Saleh  Included Market Hours api.
# 20210130  Oscar Saleh  Filtered times to place orders: isOpen, preMarket, regularMarket and postMarket
# 20210131  Oscar Saleh  Created list to identify regularMarket stocks.
# 20210201  Oscar Saleh  Modified main loop to exit when time close to midnight
#                        (to force retrieving Market Hours again).
# 20210210  Oscar Saleh  Validated Prior Price search.
# 20210226  Oscar Saleh  Implement Buy-Sell Status.
# 20210304  Oscar Saleh  Implemented classes across processes.
# 20210330  Oscar Saleh  Emphasize key differences between Single and Conditional orders.
#                        Documented in more detail in Documentation (links below).
# 20210617  Oscar Saleh  Split time_delay between time_delay_process and time_delay_io to allow independent delays.
# 20211116  Oscar Saleh  Rename program and config files to integrate better with scheduler program and config files.
# 20211129  Oscar Saleh  Validated Post Market hours during holiday, Thanksgiving.
# 20220501  Oscar Saleh  Enable trades from multiple accounts.
# 20220518  Oscar Saleh  Use alias on account numbers to improve security.
#
# ==================================================================================================================
# Pending items:
# - Remove "evil" global variables.
# - Encapsulate repetitive steps when cleansing data.
# - Improve naming conventions and standards.
#
# ==================================================================================================================
# Objective:
# This program is used to place stock order automatically based on technical indicators.
#
# ==================================================================================================================
# Logic:
# - The program retrieve and store stock prices in a repository.
# - The Market Indicators (RSI) are calculated using prices at the exact time of the request.
# - Orders are placed and traced for each order request until full cycle (buy and sell).
# - Upon a full order cycle (buy and sell), the order is enabled again.
#
# ==================================================================================================================
# Documentation:
#  Manual: https://docs.google.com/document/d/172M_8yZioGCqQUkQoQqaoRXROKNZ13DzIemTIKMCAKw/edit
#
# ==================================================================================================================
# RSI Calculation Periods to retrieve data.
#
# RSI Calc - Basic
# Parms		        Weekly	Daily	4hr 	1hr	    30m	    15m
# periodType	    year	month	day	    day 	day	    day
# period		    1	    1	    10	    3	    1 	    1
# frequencyType	    weekly	daily	minute	minute	minute	minute
# frequency	        1	    1	    30	    30	    30	    15
# needExtHourData	true	true	true	true	true	true
#
# RSI Calc - Extended
# Parms		        Weekly	Daily	4hr	    1hr	    30m	    15m
# periodType	    year	month	day	    day	    day	    day
# period		    3	    3	    10	    10	    10	    5
# frequencyType	    weekly	daily	minute	minute	minute	minute
# frequency	        1	    1	    30	    30	    30	    15
# needExtHourData	true	true	true	true	true	true
# ================================================================================================================== 
# Timeframes to Place Orders.
#                           -------------------- Windows -------------------
#                           night/weekend  7-9:30    9:30-16       16-20
# Order Type submit/execute  MarketClose  PreMarte RegularMarket PostMarket
# Conditional                   No/No       No/No     Yes/Yes      No/No
# Single - most stocks          No/No      Yes/Yes    Yes/Yes     Yes/Yes
# Single - regularMarket only   No/No       No/No     Yes/Yes      No/No
#
# ==================================================================================================================

import configparser
import datetime
import json
import os
import requests
import sys
import time

# from configparser import SafeConfigParser
from datetime import datetime, timedelta
from operator import attrgetter
from shutil import copyfile


def api_GetHistoricalPrices(Symb, Range, PeriodType, FrequencyType, Frequency, StartDate, EndDate):
    global str_token_access, str_consumer_key

    int_cnt_retry = 0
    int_cntr = 0
    str_api_status = 'No OK'  # Default value. Loop until Historical Prices are retrieved.

    HistoricalPrices = []

    while (str_api_status == 'No OK'):

        func_check_token()

        url = r"https://api.tdameritrade.com/v1/marketdata/{}/pricehistory".format(Symb)
        params = {'apikey': str_consumer_key,
                  'periodType': PeriodType,
                  'frequencyType':  FrequencyType,
                  'frequency': Frequency,
                  'endDate': EndDate,
                  'startDate': StartDate,
                  'needExtendedHoursData': 'true'}
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + str_token_access}
        content = requests.get(url=url, headers=headers, params=params)  # make request

        if (content.status_code != 200):  # Display error if api not successful
            func_display_info(0, 'Both', ['-' * 128])
            int_cnt_retry = int_cnt_retry + 1
            func_display_info(0, 'Both', ['int_cnt_retry: ' + str(int_cnt_retry)])
            func_display_info(0, 'Both', [url])
            func_display_info(0, 'Both', [params])
            func_display_info(0, 'Both', [headers])
            func_display_info(0, 'Both', [content])
            func_display_info(0, 'Both', ['* * * ERROR * * * Unable to get History Prices from api_GetHistoricalPrices'])
            func_display_info(0, 'Both', ['-' * 128])
            if (int_cnt_retry > int_max_retries):
                func_display_info(0, 'Both', ['-' * 128])
                func_display_info(0, 'Both', ['* * * ERROR * * * Max number of retries exhausted in api_GetHistoricalPrices'])
                func_display_info(-1, 'Both', ['-' * 128])

        if (content.status_code == 200):  # Process values if api-call successful
            data = content.json()  # convert to python dictionary
            func_display_info(90, 'Both', ['data: ' + '>>>' + str(data) + '<<<'])

            if (data["empty"]):
                func_display_info(0, 'Both', ['-' * 128])
                int_cnt_retry = int_cnt_retry + 1
                func_display_info(0, 'Both', ['int_cnt_retry: ' + str(int_cnt_retry)])
                func_display_info(0, 'Both', [url])
                func_display_info(0, 'Both', [params])
                func_display_info(0, 'Both', [headers])
                func_display_info(0, 'Both', [content])
                func_display_info(0, 'Both', ['* * * ERROR * * * Empty History Prices from api_GetHistoricalPrices.'])
                func_display_info(0, 'Both', ['-' * 128])
                if (int_cnt_retry > int_max_retries):
                    func_display_info(0, 'Both', ['-' * 128])
                    func_display_info(0, 'Both', ['* * * ERROR * * * Max number of retries exhausted in api_GetHistoricalPrices'])
                    #func_display_info(-1, 'Both', ['-' * 128])  # commented out to include no records for recent IPO stock, e.g. COIN
                    func_display_info(0, 'Both', ['-' * 128])
                    return (HistoricalPrices)

            if (not data["empty"]):
                for p in data['candles']:
                    int_cntr = int_cntr + 1
                    if (Range == 1440): HistoricalPrices.append([p['datetime'] + (15 * 60 * 60 * 1000), p['close'], Range])  # Default is 0 hours; Close time is 3 PM New York Time; need to add 15 hours
                    if (Range ==   15): HistoricalPrices.append([p['datetime'] + (     14 * 60 * 1000), p['close'], Range])  # Default is begin-of-period; Close time is 14 min into the future; need to add 14 min
                    if (Range ==    1): HistoricalPrices.append([p['datetime'] + (          50 * 1000), p['close'], Range])  # Default is begin-of-period; Close time is 50 sec into the future; need to add 50 sec

                func_display_info(50, 'Both', ['Records retrieved from api_GetHistoricalPrices: ' + str(len(HistoricalPrices))])
                if (int_cntr > 10):
                    str_api_status = 'Ok'
                else:
                    func_display_info(0, 'Both', ['-' * 128])
                    int_cnt_retry = int_cnt_retry + 1
                    func_display_info(0, 'Both', ['int_cnt_retry: ' + str(int_cnt_retry)])
                    func_display_info(0, 'Both', [url])
                    func_display_info(0, 'Both', [params])
                    func_display_info(0, 'Both', [headers])
                    func_display_info(0, 'Both', [content])
                    func_display_info(0, 'Both', ['data: ' + '>>>' + str(data) + '<<<'])
                    func_display_info(0, 'Both', ['* * * ERROR * * * Less than 10 records received from api_GetHistoricalPrices.'])
                    func_display_info(0, 'Both', ['-' * 128])
                    if (int_cnt_retry > int_max_retries):
                        func_display_info(0, 'Both', ['-' * 128])
                        func_display_info(0, 'Both', ['* * * ERROR * * * Max number of retries exhausted in api_GetHistoricalPrices'])
                        func_display_info(-1, 'Both', ['-' * 128])

    return(HistoricalPrices)

def api_GetLastPrice(Symb):
    global str_token_access, str_consumer_key
    global int_max_retries

    LastPrice = -1.23456789  # Default value. Loop until real LastPrice is retrieved.
    int_cnt_retry = 0

    while (LastPrice ==  -1.23456789):

        func_check_token()

        url = r"https://api.tdameritrade.com/v1/marketdata/{}/quotes".format(Symb)
        params = {'apikey': str_consumer_key}
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + str_token_access}

        #content = requests.get(url=url, headers=headers, params=params)  # make request

        try:
            content = requests.get(url=url, headers=headers, params=params)  # make request

            if (content.status_code != 200):  # Display values if not successful
                func_display_info(0, 'Both', ['-' * 128])
                int_cnt_retry = int_cnt_retry + 1
                func_display_info(0, 'Both', ['int_cnt_retry: ' + str(int_cnt_retry)])
                func_display_info(0, 'Both', [url])
                func_display_info(0, 'Both', [params])
                func_display_info(0, 'Both', [headers])
                func_display_info(0, 'Both', [content])
                func_display_info(0, 'Both', ['* * * ERROR * * * Unable to get latest price in api_GetLastPrice'])
                func_display_info(0, 'Both', ['-' * 128])
                if (int_cnt_retry> int_max_retries):
                    func_display_info(0, 'Both', ['-' * 128])
                    func_display_info(0, 'Both', ['* * * ERROR * * * Max number of retries exhausted in api_GetLastPrice'])
                    func_display_info(-1, 'Both', ['-' * 128])

            if (content.status_code == 200):  # Process values if successful
                data = content.json()         # convert to python dictionary
                func_display_info(80, 'Both', ['data: ' + '>>>' + str(data) + '<<<'])

                for p in data.values(): LastPrice = float(p.get("lastPrice"))  # Get value from selected record

                func_display_info(80, 'Both', ['LastPrice: ' + '>>>' + str(LastPrice) + '<<<'])

        except requests.exceptions.ConnectionError:
            func_display_info(0, 'Both', ['-' * 128])
            int_cnt_retry = int_cnt_retry + 1
            func_display_info(0, 'Both', ['int_cnt_retry: ' + str(int_cnt_retry)])
            func_display_info(0, 'Both', [url])
            func_display_info(0, 'Both', [params])
            func_display_info(0, 'Both', [headers])
            #func_display_info(0, 'Both', [content])
            func_display_info(0, 'Both', ['* * * ERROR * * * Connection error to get latest price in api_GetLastPrice'])
            func_display_info(0, 'Both', ['-' * 128])
            if (int_cnt_retry> int_max_retries):
                func_display_info(0, 'Both', ['-' * 128])
                func_display_info(0, 'Both', ['* * * ERROR * * * Max number of retries exhausted in api_GetLastPrice'])
                func_display_info(-1, 'Both', ['-' * 128])

    return(LastPrice)

def api_GetMarketHours(dt_trading_timestamp):
    global str_token_access, str_consumer_key
    global int_max_retries
    global bool_isOpen, dt_preMarket_start, dt_preMarket_end, dt_regularMarket_start, dt_regularMarket_end, dt_postMarket_start, dt_postMarket_end

    int_cnt_retry = 0
    str_api_status = 'No OK'  # Default value. Loop until Market Hours are retrieved.

    while (str_api_status ==  'No OK'):

        func_check_token()

        url = r"https://api.tdameritrade.com/v1/marketdata/{}/hours".format('EQUITY')
        params = {'apikey': str_consumer_key, 'date': dt_trading_timestamp}
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + str_token_access}
        content = requests.get(url=url, headers=headers, params=params)  # make request

        if (content.status_code != 200):  # Display error if api not successful
            func_display_info(0, 'Both', ['-' * 128])
            int_cnt_retry = int_cnt_retry + 1
            func_display_info(0, 'Both', ['int_cnt_retry: ' + str(int_cnt_retry)])
            func_display_info(0, 'Both', [url])
            func_display_info(0, 'Both', [params])
            func_display_info(0, 'Both', [headers])
            func_display_info(0, 'Both', [content])
            func_display_info(0, 'Both', ['* * * ERROR * * * Unable to get market hours in api_GetMarketHours'])
            func_display_info(0, 'Both', ['-' * 128])
            if (int_cnt_retry > int_max_retries):
                func_display_info(0, 'Both', ['-' * 128])
                func_display_info(0, 'Both', ['* * * ERROR * * * Max number of retries exhausted in api_GetMarketHours'])
                func_display_info(-1, 'Both', ['-' * 128])

        if (content.status_code == 200):  # Process values if api-call successful
            data = content.json()         # convert to python dictionary
            func_display_info(80, 'Both', ['data: ' + '>>>' + str(data) + '<<<'])

            if (len(set(list(data['equity'].keys())) & set(['equity'])) == 1):  # Market should be close
                bool_isOpen = data['equity']['equity']['isOpen']
                if (bool_isOpen == False):  # Market is close
                    str_isOpen = 'False'
                    func_display_info(0, 'Both', ['str_isOpen             : ' + str_isOpen])
                    str_api_status = 'Ok'
                if (bool_isOpen == True):  # Market should not be open
                    if (bool_isOpen):
                        func_display_info(0, 'Both', ['-' * 128])
                        int_cnt_retry = int_cnt_retry + 1
                        func_display_info(0, 'Both', ['int_cnt_retry: ' + str(int_cnt_retry)])
                        func_display_info(0, 'Both', [url])
                        func_display_info(0, 'Both', [params])
                        func_display_info(0, 'Both', [headers])
                        func_display_info(0, 'Both', [content])
                        func_display_info(0, 'Both', ['data: ' + '>>>' + str(data) + '<<<'])
                        func_display_info(0, 'Both', ['* * * ERROR * * * Market is open with no dates in api_GetMarketHours'])
                        func_display_info(0, 'Both', ['-' * 128])
                        if (int_cnt_retry > int_max_retries):
                            func_display_info(0, 'Both', ['-' * 128])
                            func_display_info(0, 'Both', ['* * * ERROR * * * Max number of retries exhausted in api_GetMarketHours'])
                            func_display_info(-1, 'Both', ['-' * 128])

            if (len(set(list(data['equity'].keys())) & set(['EQ'])) == 1):  # Market should be open

                if ((data['equity']['EQ']['marketType'] == 'EQUITY') and (data['equity']['EQ']['product'] == 'EQ')):  # Verify internal values
                    bool_isOpen = data['equity']['EQ']['isOpen']
                    if (bool_isOpen == True):  # Market is open
                        str_isOpen = 'True'
                        str_preMarket_start     = data['equity']['EQ']['sessionHours']['preMarket'][0]['start']
                        str_preMarket_end       = data['equity']['EQ']['sessionHours']['preMarket'][0]['end']
                        str_regularMarket_start = data['equity']['EQ']['sessionHours']['regularMarket'][0]['start']
                        str_regularMarket_end   = data['equity']['EQ']['sessionHours']['regularMarket'][0]['end']
                        if 'postMarket' in data['equity']['EQ']['sessionHours']:  # During Thanksgiving holiday, the postMarket is closed; use regularMarket_end hours.
                            str_postMarket_start = data['equity']['EQ']['sessionHours']['postMarket'][0]['start']
                            str_postMarket_end   = data['equity']['EQ']['sessionHours']['postMarket'][0]['end']
                        else:
                            str_postMarket_start = data['equity']['EQ']['sessionHours']['regularMarket'][0]['end']
                            str_postMarket_end   = data['equity']['EQ']['sessionHours']['regularMarket'][0]['end']
                        func_display_info(0, 'Both', ['str_isOpen             : ' + str_isOpen])
                        func_display_info(0, 'Both', ['str_preMarket_start    : ' + str_preMarket_start])
                        func_display_info(0, 'Both', ['str_preMarket_end      : ' + str_preMarket_end])
                        func_display_info(0, 'Both', ['str_regularMarket_start: ' + str_regularMarket_start])
                        func_display_info(0, 'Both', ['str_regularMarket_end  : ' + str_regularMarket_end])
                        func_display_info(0, 'Both', ['str_postMarket_start   : ' + str_postMarket_start])
                        func_display_info(0, 'Both', ['str_postMarket_end     : ' + str_postMarket_end])
                        dt_preMarket_start     = datetime.strptime(str_preMarket_start[0:19], '%Y-%m-%dT%H:%M:%S')
                        dt_preMarket_end       = datetime.strptime(str_preMarket_end[0:19], '%Y-%m-%dT%H:%M:%S')
                        dt_regularMarket_start = datetime.strptime(str_regularMarket_start[0:19], '%Y-%m-%dT%H:%M:%S')
                        dt_regularMarket_end   = datetime.strptime(str_regularMarket_end[0:19], '%Y-%m-%dT%H:%M:%S')
                        dt_postMarket_start    = datetime.strptime(str_postMarket_start[0:19], '%Y-%m-%dT%H:%M:%S')
                        dt_postMarket_end      = datetime.strptime(str_postMarket_end[0:19], '%Y-%m-%dT%H:%M:%S')
                        str_api_status = 'Ok'
                    else:
                        str_isOpen = 'False'
                        func_display_info(0, 'Both', ['str_isOpen             : ' + str_isOpen])
                        str_api_status = 'Ok'
                else:
                    func_display_info(0, 'Both', ['-' * 128])
                    int_cnt_retry = int_cnt_retry + 1
                    func_display_info(0, 'Both', ['int_cnt_retry: ' + str(int_cnt_retry)])
                    func_display_info(0, 'Both', [url])
                    func_display_info(0, 'Both', [params])
                    func_display_info(0, 'Both', [headers])
                    func_display_info(0, 'Both', [content])
                    func_display_info(0, 'Both', [data])
                    func_display_info(0, 'Both', ['data: ' + '>>>' + str(data) + '<<<'])
                    func_display_info(0, 'Both', ['* * * ERROR * * * Invalid values received from api_GetMarketHours'])
                    func_display_info(0, 'Both', ['-' * 128])
                    if (int_cnt_retry > int_max_retries):
                        func_display_info(0, 'Both', ['-' * 128])
                        func_display_info(0, 'Both', ['* * * ERROR * * * Max number of retries exhausted in api_GetMarketHours'])
                        func_display_info(-1, 'Both', ['-' * 128])

    return()

def api_GetOrderByPath(OrderType, BuySell, obj_LineOrderStatus):  # OrderType is 'Single' or 'Conditional'
    global str_token_access, obj_ListLineOrderStatus
    func_check_token()

    url = r"https://api.tdameritrade.com/v1/accounts/{}/orders".format(func_get_account(obj_LineOrderStatus.acct_desc))

    params = {'maxResults': 500,
              'fromEnteredTime': datetime.now().strftime("%Y-%m-%d"),
              'toEnteredTime': datetime.now().strftime("%Y-%m-%d"),
              'status': ''  # No value because it could be FILLED already
              }

    headers = {"HTTP_HOST": "http://localhost", "Authorization": "Bearer " + str_token_access}

    content = requests.get(url=url, params=params, headers=headers)  # make a request

    if (content.status_code != 200):
        func_display_info(0, 'Both', ['-' * 128])
        func_display_info(0, 'Both', ['OrderType = ' + OrderType])
        func_display_info(0, 'Both', ['BuySell = ' + BuySell])
        func_display_info(0, 'Both', [url])
        func_display_info(0, 'Both', [params])
        func_display_info(0, 'Both', [headers])
        func_display_info(0, 'Both', [content])
        func_display_info(0, 'Both', ['* * * ERROR * * * Unable to get list of orders in api_GetOrderByPath'])
        func_display_info(-1, 'Both', ['-' * 128])

    data = content.json()  # convert to python dictionary
    func_display_info(90, 'Both', [data])

    ListOrderSubmitted = []      # Use by Single Order
    ListOrderSubmittedBuy = []   # Use by Conditional Order
    ListOrderSubmittedSell = []  # Use by Conditional Order

    for obj_Order in data:
        if (int_debug > 100):
            print('------------------------------------------------------------------')
            print('session: ' + obj_Order['session'])
            print('duration: ' + obj_Order['duration'])
            print('orderType: ' + obj_Order['orderType'])
            print('quantity: ' + str(obj_Order['quantity']))
            print('filledQuantity: ' + str(obj_Order['filledQuantity']))
            print('remainingQuantity: ' + str(obj_Order['remainingQuantity']))
            if (obj_Order['orderType'] == 'MARKET'):
                print('price is NULL')
            else:
                print('price: ' + str(obj_Order['price']))
            for obj_orderLegCollection in obj_Order["orderLegCollection"]:
                print('orderLegCollection orderLegType: ' + obj_orderLegCollection['orderLegType'])
                print('orderLegCollection LegId: ' + str(obj_orderLegCollection['legId']))
                print('orderLegCollection instrument assetType: ' + obj_orderLegCollection['instrument']['assetType'])
                print('orderLegCollection instrument symbol: ' + obj_orderLegCollection['instrument']['symbol'])
                print('orderLegCollection instruction: ' + obj_orderLegCollection['instruction'])
                print('orderLegCollection positionEffect: ' + obj_orderLegCollection['positionEffect'])
                print('orderLegCollection quantity: ' + str(obj_orderLegCollection['quantity']))
            print('orderStrategyType: ' + obj_Order['orderStrategyType'])
            print('orderId: ' + str(obj_Order['orderId']))
            print('status: ' + obj_Order['status'])
            print(obj_Order['enteredTime'])
            print('accountId: ' + str(obj_Order['accountId']))
            if (obj_Order['orderStrategyType'] == 'TRIGGER'):
                for obj_childOrderStrategies in obj_Order["childOrderStrategies"]:
                    print('childOrderStrategies session: ' + obj_childOrderStrategies['session'])
                    print('childOrderStrategies duration: ' + obj_childOrderStrategies['duration'])
                    print('childOrderStrategies orderType: ' + obj_childOrderStrategies['orderType'])
                    print('childOrderStrategies quantity: ' + str(obj_childOrderStrategies['quantity']))
                    print('childOrderStrategies price: ' + str(obj_childOrderStrategies['price']))
                    for obj_orderLegCollection in obj_childOrderStrategies["orderLegCollection"]:
                        print('orderLegCollection orderLegType: ' + obj_orderLegCollection['orderLegType'])
                        print('orderLegCollection LegId: ' + str(obj_orderLegCollection['legId']))
                        print('orderLegCollection instrument assetType: ' + obj_orderLegCollection['instrument']['assetType'])
                        print('orderLegCollection instrument symbol: ' + obj_orderLegCollection['instrument']['symbol'])
                        print('orderLegCollection instruction: ' + obj_orderLegCollection['instruction'])
                        print('orderLegCollection quantity: ' + str(obj_orderLegCollection['quantity']))
                    print('childOrderStrategies orderId: ' + str(obj_childOrderStrategies['orderId']))
                    print('childOrderStrategies status: ' + obj_childOrderStrategies['status'])
                    print(obj_childOrderStrategies['enteredTime'])
                    print('childOrderStrategies accountId: ' + str(obj_childOrderStrategies['accountId']))
            print('------------------------------------------------------------------')
        if (OrderType == 'Single'):
            if (((obj_Order['status']) != 'CANCELED') and (obj_Order['orderType'] != 'MARKET')):
                if ((obj_Order['duration']  == 'GOOD_TILL_CANCEL') and
                    (obj_Order['orderType'] == 'LIMIT'           ) and
                    (obj_Order['quantity']  == obj_LineOrderStatus.order_buy_shares) and
                    ((BuySell == 'BUY' and (obj_Order['quantity'] == obj_LineOrderStatus.order_buy_shares)) or
                     (BuySell == 'SELL' and (obj_Order['quantity'] == obj_LineOrderStatus.order_sell_shares))) and
                    ((BuySell == 'BUY' and (obj_Order['price'] == obj_LineOrderStatus.order_buy_price)) or
                     (BuySell == 'SELL' and (obj_Order['price'] == obj_LineOrderStatus.order_sell_price))) and
                    (obj_Order['accountId'] == int(func_get_account(obj_LineOrderStatus.acct_desc))) and
                    (obj_Order['orderStrategyType'] == 'SINGLE')):
                    for obj_orderLegCollection in obj_Order["orderLegCollection"]:
                        if ((obj_orderLegCollection['orderLegType']         == 'EQUITY') and
                            (obj_orderLegCollection['instrument']['symbol'] == obj_LineOrderStatus.symbol) and
                            (obj_orderLegCollection['instruction']          ==  BuySell)):
                            ListOrderSubmitted.append(obj_Order['orderId'])
        if (OrderType == 'Conditional'):
            if (((obj_Order['status']) != 'CANCELED') and (obj_Order['orderType'] != 'MARKET')):
                if ((obj_Order['duration']  == 'GOOD_TILL_CANCEL') and
                    (obj_Order['orderType'] == 'LIMIT'           ) and
                    (obj_Order['quantity']  == obj_LineOrderStatus.order_buy_shares) and
                    (obj_Order['price']     == obj_LineOrderStatus.order_buy_price) and
                    (obj_Order['accountId'] == int(func_get_account(obj_LineOrderStatus.acct_desc))) and
                    (obj_Order['orderStrategyType'] == 'TRIGGER')):
                    bool_valid_buy_order = False
                    for obj_orderLegCollection in obj_Order["orderLegCollection"]:
                        if ((obj_orderLegCollection['orderLegType']         == 'EQUITY') and
                            (obj_orderLegCollection['instrument']['symbol'] == obj_LineOrderStatus.symbol) and
                            (obj_orderLegCollection['instruction']          ==  'BUY')):
                            bool_valid_buy_order = True
                            ListOrderSubmittedBuy.append(obj_Order['orderId'])
                    for obj_childOrderStrategies in obj_Order["childOrderStrategies"]:
                        if ((obj_childOrderStrategies['duration']  == 'GOOD_TILL_CANCEL') and
                            (obj_childOrderStrategies['orderType'] == 'LIMIT') and
                            (obj_childOrderStrategies['quantity']  == obj_LineOrderStatus.order_sell_shares) and
                            (obj_childOrderStrategies['price']     == obj_LineOrderStatus.order_sell_price)):
                            for obj_orderLegCollection in obj_childOrderStrategies["orderLegCollection"]:
                                if ((obj_orderLegCollection['instrument']['symbol'] == obj_LineOrderStatus.symbol) and
                                    (obj_orderLegCollection['instruction'] == 'SELL')):
                                    if (bool_valid_buy_order):
                                        ListOrderSubmittedSell.append(obj_childOrderStrategies['orderId'])

    if (int_debug > 100):
        print('Possible Orders found (Orders):')
        print(ListOrderSubmitted)
        print(ListOrderSubmittedBuy)
        print(ListOrderSubmittedSell)

    if (OrderType == 'Single'):

        # Eliminate orders already in use
        for obj_LineOrderStatusOrderSearch in obj_ListLineOrderStatus.List:
            if (BuySell == 'BUY'):
                if (obj_LineOrderStatusOrderSearch.order_buy_number in ListOrderSubmitted):
                    ListOrderSubmitted.remove(obj_LineOrderStatusOrderSearch.order_buy_number)
            if (BuySell == 'SELL'):
                if (obj_LineOrderStatusOrderSearch.order_sell_number in ListOrderSubmitted):
                    ListOrderSubmitted.remove(obj_LineOrderStatusOrderSearch.order_sell_number)

        func_display_info(40, 'Both', ['Possible Orders found not being used: ' + str(ListOrderSubmitted)])

        if (len(ListOrderSubmitted) > 0):
            return (ListOrderSubmitted[0])
        else:
            func_display_info(0, 'Both', ['-' * 128])
            func_display_info(0, 'Both', ['OrderType = ' + OrderType])
            func_display_info(0, 'Both', ['BuySell = ' + BuySell])
            func_display_info(0, 'Both', [url])
            func_display_info(0, 'Both', [params])
            func_display_info(0, 'Both', [headers])
            func_display_info(0, 'Both', [content])
            func_display_info(0, 'Both', ['* * * ERROR * * * No Single Order found in api_GetOrderByPath'])
            func_display_info(-1, 'Both', ['-' * 128])

    if (OrderType == 'Conditional'):

        # Eliminate orders already in use
        for obj_LineOrderStatusOrderSearch in obj_ListLineOrderStatus.List:
            if (obj_LineOrderStatusOrderSearch.order_buy_number in ListOrderSubmittedBuy):
                index = ListOrderSubmitted.index(obj_LineOrderStatusOrderSearch.order_buy_number)
                ListOrderSubmittedBuy.pop(index)
                ListOrderSubmittedSell.pop(index)
            if (obj_LineOrderStatusOrderSearch.order_sell_number in ListOrderSubmittedSell):
                index = ListOrderSubmitted.index(obj_LineOrderStatusOrderSearch.order_sell_number)
                ListOrderSubmittedBuy.pop(index)
                ListOrderSubmittedSell.pop(index)

        func_display_info(40, 'Both', ['Possible Orders not being used: Buy ' + str(ListOrderSubmittedBuy) + ' Sell '+ str(ListOrderSubmittedSell)])

        if (len(ListOrderSubmittedBuy) > 0):
            return (ListOrderSubmittedBuy[0],ListOrderSubmittedSell[0])
        else:
            func_display_info(0, 'Both', ['-' * 128])
            func_display_info(0, 'Both', ['OrderType = ' + OrderType])
            func_display_info(0, 'Both', ['BuySell = ' + BuySell])
            func_display_info(0, 'Both', [url])
            func_display_info(0, 'Both', [params])
            func_display_info(0, 'Both', [headers])
            func_display_info(0, 'Both', [content])
            func_display_info(0, 'Both', ['* * * ERROR * * * No Conditional Order found in api_GetOrderByPath'])
            func_display_info(-1, 'Both', ['-' * 128])

def api_GetOrderStatus(BuySell, obj_LineOrderStatus):
    global str_token_access, obj_ListLineOrderStatus
    global int_max_retries

    OrderStatus = 'No OK'  # Default value. Loop until Order Status is retrieved.

    int_cnt_retry = 0
    while (OrderStatus == 'No OK'):
        func_check_token()

        if (BuySell == 'BUY'):
            OrderNumber = obj_LineOrderStatus.order_buy_number
        if (BuySell == 'SELL'):
            OrderNumber = obj_LineOrderStatus.order_sell_number

        url = r"https://api.tdameritrade.com/v1/accounts/{}/orders/{}".format(func_get_account(obj_LineOrderStatus.acct_desc), OrderNumber)
        params = {}
        headers = {"HTTP_HOST": "http://localhost", "Authorization": "Bearer " + str_token_access}
        
        try:  # error received: port=443): requests.exceptions.ConnectionError: HTTPSConnectionPool(host='api.tdameritrade.com', port=443): Max retries exceeded with url: /v1/accounts/870491859/orders/2225244376 (Caused by NewConnectionError('<urllib3.connection.VerifiedHTTPSConnection object at 0x000000F9A324C370>: Failed to establish a new connection: [Errno 11001] getaddrinfo failed'))
            content = requests.get(url=url, params=params, headers=headers)  # make a request
        except requests.exceptions.ConnectionError as e:
            content = "No Response"

        if ((content.status_code != 200) or (content == "No Response")):
            func_display_info(0, 'Both', ['-' * 128])
            int_cnt_retry = int_cnt_retry + 1
            func_display_info(0, 'Both', ['int_cnt_retry: ' + str(int_cnt_retry)])
            func_display_info(0, 'Both', ['BuySell = ' + BuySell])
            func_display_info(0, 'Both', [url])
            func_display_info(0, 'Both', [params])
            func_display_info(0, 'Both', [headers])
            func_display_info(0, 'Both', [content])
            func_display_info(0, 'Both', ['* * * ERROR * * * Unable to get latest order in api_GetOrderStatus'])
            func_display_info(0, 'Both', ['-' * 128])
            if (int_cnt_retry > int_max_retries):
                func_display_info(0, 'Both', ['-' * 128])
                func_display_info(0, 'Both', ['* * * ERROR * * * Max number of retries exhausted in api_GetOrderStatus'])
                func_display_info(-1, 'Both', ['-' * 128])
        else:
            OrderStatus = 'OK'

    data = content.json()  # convert to python dictionary
    func_display_info(90, 'Both', [data])

    ListOrderSubmitted = []
    ListOrderSubmittedStatus = []

    if (int_debug > 100):
        print('------------------------------------------------------------------')
        print('session: ' + data['session'])
        print('duration: ' + data['duration'])
        print('orderType: ' + data['orderType'])
        print('quantity: ' + str(data['quantity']))
        print('filledQuantity: ' + str(data['filledQuantity']))
        print('remainingQuantity: ' + str(data['remainingQuantity']))
        print('price: ' + str(data['price']))
        for data_orderLegCollection in data["orderLegCollection"]:
            print('orderLegCollection orderLegType: ' + data_orderLegCollection['orderLegType'])
            print('orderLegCollection LegId: ' + str(data_orderLegCollection['legId']))
            print('orderLegCollection instrument assetType: ' + data_orderLegCollection['instrument']['assetType'])
            print('orderLegCollection instrument symbol: ' + data_orderLegCollection['instrument']['symbol'])
            print('orderLegCollection instruction: ' + data_orderLegCollection['instruction'])
            print('orderLegCollection positionEffect: ' + data_orderLegCollection['positionEffect'])
            print('orderLegCollection quantity: ' + str(data_orderLegCollection['quantity']))
        print('orderStrategyType: ' + data['orderStrategyType'])
        print('orderId: ' + str(data['orderId']))
        print('status: ' + data['status'])
        print(data['enteredTime'])
        print('accountId: ' + str(data['accountId']))
        print('------------------------------------------------------------------')

    if (BuySell == 'BUY'):
        if ((data['duration'] == 'GOOD_TILL_CANCEL') and
            (data['orderType'] == 'LIMIT') and
            (data['quantity'] == obj_LineOrderStatus.order_buy_shares) and
            ((data['price'] == obj_LineOrderStatus.order_buy_price) or    # price in original order
             (data['price'] <  obj_LineOrderStatus.order_buy_price)) and  # Change made to accomodate price update after paying dividends. Considering lower prices adjusted ONLY!.
            (data['accountId'] == int(func_get_account(obj_LineOrderStatus.acct_desc)))):
            for data_orderLegCollection in data["orderLegCollection"]:
                if ((data_orderLegCollection['orderLegType'] == 'EQUITY') and
                    (data_orderLegCollection['instrument']['symbol'] == obj_LineOrderStatus.symbol) and
                    (data_orderLegCollection['instruction'] == BuySell)):
                    ListOrderSubmitted.append(data['orderId'])
                    ListOrderSubmittedStatus.append(data['status'])
    if (BuySell == 'SELL'):
        if ((data['duration'] == 'GOOD_TILL_CANCEL') and
            (data['orderType'] == 'LIMIT') and
            (data['quantity'] == obj_LineOrderStatus.order_sell_shares) and
            (data['price'] == obj_LineOrderStatus.order_sell_price) and
            (data['accountId'] == int(func_get_account(obj_LineOrderStatus.acct_desc)))):
            for data_orderLegCollection in data["orderLegCollection"]:
                if ((data_orderLegCollection['orderLegType'] == 'EQUITY') and
                    (data_orderLegCollection['instrument']['symbol'] == obj_LineOrderStatus.symbol) and
                    (data_orderLegCollection['instruction'] == BuySell)):
                    ListOrderSubmitted.append(data['orderId'])
                    ListOrderSubmittedStatus.append(data['status'])

    if (ListOrderSubmittedStatus[0] == 'FILLED'):
        func_display_info(10, 'Both', ['Get Order Status. Order Number: ' + str(ListOrderSubmitted) + ' Status: ' + str(ListOrderSubmittedStatus)])

    if (len(ListOrderSubmitted) != 1):
        func_display_info(0, 'Both', ['-' * 128])
        func_display_info(0, 'Both', ['BuySell = ' + BuySell])
        func_display_info(0, 'Both', [url])
        func_display_info(0, 'Both', [params])
        func_display_info(0, 'Both', [headers])
        func_display_info(0, 'Both', [content])
        func_display_info(0, 'Both', [data])
        func_display_info(0, 'Both', ['* * * ERROR * * * Order not found in api_GetOrderStatus'])
        func_display_info(-1, 'Both', ['-' * 128])

    if (len(ListOrderSubmitted) == 1):
        return (ListOrderSubmittedStatus[0])
    else:
        return ("Not_Found")

def api_GetTokenAuthorization(TokenType):
    global str_token_access, str_token_refresh, str_consumer_key

    url = "https://api.tdameritrade.com/v1/oauth2/token"

    # define data
    dataTokenAccess =  {
                          'grant_type': 'refresh_token',
                          'refresh_token': str_token_refresh,
                          'client_id': str_consumer_key
                       }
    dataTokenRefresh = {
                          'grant_type': 'refresh_token',
                          'refresh_token': str_token_refresh,
                          'access_type': 'offline',
                          'client_id': str_consumer_key
                       }
    if (TokenType == 'TokenAccess' ): data = dataTokenAccess
    if (TokenType == 'TokenRefresh'): data = dataTokenRefresh

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    content = requests.post(url=url, headers=headers, data=data)  # make a request

    if (content.status_code != 200):
        func_display_info(0, 'Both', ['-' * 128])
        func_display_info(0, 'Both', ['TokenType = ' + TokenType])
        func_display_info(0, 'Both', [url])
        func_display_info(0, 'Both', [data])
        func_display_info(0, 'Both', [headers])
        func_display_info(0, 'Both', [content])
        func_display_info(0, 'Both', ['* * * ERROR * * * Unable to get token authorization for TokenType: ' + TokenType + ' in api_GetTokenAuthorization'])
        func_display_info(-1, 'Both', ['-' * 128])

    data = content.json()  # convert to python dictionary
    func_display_info(50, 'Both', [str(data)])

    if (TokenType == 'TokenAccess'):
        func_display_info(50, 'Both', ['Token Access: ' + data['access_token']])
    if (TokenType == 'TokenRefresh'):
        func_display_info(50, 'Both', ['Token Access: ' + data['access_token']])
        func_display_info(50, 'Both', ['Token Refresh: ' + data['refresh_token']])

    if (TokenType == 'TokenAccess'):
        #DisplayInfo(10, 'Both', ['TokenAccess:', data])
        str_token_access = data['access_token']
    if (TokenType == 'TokenRefresh'):
        #DisplayInfo(10, 'Both', ['TokenRefresh:', data])
        str_token_refresh = data['refresh_token']

def api_PlaceOrder(OrderType, BuySell, obj_LineOrderStatus):
    # OrderType is 'Single' or 'Conditional'
    global str_token_access
    global lst_stock_regularMarketOnly_OTC_list  # list of stocks with restrictions to place single orders
    func_check_token()

    if (obj_LineOrderStatus.symbol in lst_stock_regularMarketOnly_OTC_list):
        SessionValue = "NORMAL"     # place order only during regularMarket hours
    else:
        SessionValue = "SEAMLESS"   # place order anytime

    url = r"https://api.tdameritrade.com/v1/accounts/{}/orders".format(func_get_account(obj_LineOrderStatus.acct_desc))

    if (OrderType == 'Single'):
        if (BuySell == 'BUY'):
            json = {
                      "orderType": "LIMIT",
                      "session": SessionValue,
                      "price": obj_LineOrderStatus.order_buy_price,
                      "duration": "GOOD_TILL_CANCEL",
                      "orderStrategyType": "SINGLE",
                      "orderLegCollection":
                         [
                            {
                               "instruction": BuySell,
                               "quantity": obj_LineOrderStatus.order_buy_shares,
                               "instrument":
                                  {
                                     "symbol": obj_LineOrderStatus.symbol,
                                     "assetType": "EQUITY"
                                  }
                            }
                         ]
                   }
        if (BuySell == 'SELL'):
            json = {
                     "orderType": "LIMIT",
                     "session": SessionValue,
                     "price": obj_LineOrderStatus.order_sell_price,
                     "duration": "GOOD_TILL_CANCEL",
                     "orderStrategyType": "SINGLE",
                     "orderLegCollection":
                        [
                            {
                                "instruction": BuySell,
                                "quantity": obj_LineOrderStatus.order_sell_shares,
                                "instrument":
                                    {
                                        "symbol": obj_LineOrderStatus.symbol,
                                        "assetType": "EQUITY"
                                    }
                            }
                        ]
                   }
    if (OrderType == 'Conditional'):
        json = {
                  "orderType": "LIMIT",
                  "session": "NORMAL",  # "SEAMLESS",
                  "price": obj_LineOrderStatus.order_buy_price,
                  "duration": "GOOD_TILL_CANCEL",
                  "orderStrategyType": "TRIGGER",
                  "orderLegCollection":
                     [
                        {
                           "instruction": "BUY",
                           "quantity": obj_LineOrderStatus.order_buy_shares,
                           "instrument":
                              {
                                 "symbol": obj_LineOrderStatus.symbol,
                                 "assetType": "EQUITY"
                              }
                         }
                     ],
                  "childOrderStrategies":
                     [
                        {
                           "orderType": "LIMIT",
                           "session": "NORMAL",  # "SEAMLESS",
                           "price": obj_LineOrderStatus.order_sell_price,
                           "duration": "GOOD_TILL_CANCEL",
                           "orderStrategyType": "SINGLE",
                           "orderLegCollection":
                              [
                                 {
                                    "instruction": "SELL",
                                    "quantity": obj_LineOrderStatus.order_sell_shares,
                                    "instrument":
                                       {
                                          "symbol": obj_LineOrderStatus.symbol,
                                          "assetType": "EQUITY"
                                       }
                                 }
                              ]
                        }
                     ]
               }

    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + str_token_access}

    content = requests.post( url=url, headers=headers, json=json)  # make a request

    if (content.status_code != 201):
        func_display_info(0, 'Both', ['-' * 128])
        func_display_info(0, 'Both', ['OrderType = ' + OrderType])
        func_display_info(0, 'Both', ['BuySell = ' + BuySell])
        func_display_info(0, 'Both', [url])
        func_display_info(0, 'Both', [json])
        func_display_info(0, 'Both', [headers])
        func_display_info(0, 'Both', [content])
        func_display_info(0, 'Both', ['* * * ERROR * * * Unable to place order in api_PlaceOrder'])
        func_display_info(-1, 'Both', ['-' * 128])

    # data = content.json() # convert to python dictionary - there is no data returned, except status_code below

    func_display_info(10, 'Both', ['Placed Order. Order Info: ' + str(obj_LineOrderStatus.symbol) + ' ' + str(OrderType) + ' ' + str(BuySell)])

    return("Transition")

class cls_LineBuySellStatus:
    def __init__(self, obj_LineOrderStatus):  # attributes
        self.symbol               = obj_LineOrderStatus.symbol
        self.period               = obj_LineOrderStatus.period
        self.trigger_buy_rsi_wk   = obj_LineOrderStatus.trigger_buy_rsi_wk
        self.trigger_buy_rsi_day  = obj_LineOrderStatus.trigger_buy_rsi_day
        self.trigger_buy_rsi_4hr  = obj_LineOrderStatus.trigger_buy_rsi_4hr
        self.trigger_buy_rsi_1hr  = obj_LineOrderStatus.trigger_buy_rsi_1hr
        self.trigger_buy_rsi_30m  = obj_LineOrderStatus.trigger_buy_rsi_30m
        self.trigger_buy_rsi_15m  = obj_LineOrderStatus.trigger_buy_rsi_15m
        self.trigger_sell_rsi_wk  = obj_LineOrderStatus.trigger_sell_rsi_wk
        self.trigger_sell_rsi_day = obj_LineOrderStatus.trigger_sell_rsi_day
        self.trigger_sell_rsi_4hr = obj_LineOrderStatus.trigger_sell_rsi_4hr
        self.trigger_sell_rsi_1hr = obj_LineOrderStatus.trigger_sell_rsi_1hr
        self.trigger_sell_rsi_30m = obj_LineOrderStatus.trigger_sell_rsi_30m
        self.trigger_sell_rsi_15m = obj_LineOrderStatus.trigger_sell_rsi_15m
        self.current_rsi_wk       = 0
        self.current_rsi_day      = 0
        self.current_rsi_4hr      = 0
        self.current_rsi_1hr      = 0
        self.current_rsi_30m      = 0
        self.current_rsi_15m      = 0
        self.buy_status           = '   '
        self.buy_percentage       = 0.0
        self.sell_status          = '   '
        self.sell_percentage      = 0.0
        self.repetitions          = 0
        self.repetitions_buy      = 0
        self.repetitions_sell     = 0

    def print(self): 
        str_line = str(self.symbol + "     ")[:5] + " "
        str_line = str_line + str(self.period + "               ")[:15] + " "
        str_line = str_line + ("   " + str(self.trigger_buy_rsi_wk ))[-3:] + " "
        str_line = str_line + ("   " + str(self.trigger_buy_rsi_day))[-3:] + " "
        str_line = str_line + ("   " + str(self.trigger_buy_rsi_4hr))[-3:] + " "
        str_line = str_line + ("   " + str(self.trigger_buy_rsi_1hr))[-3:] + " "
        str_line = str_line + ("   " + str(self.trigger_buy_rsi_30m))[-3:] + " "
        str_line = str_line + ("   " + str(self.trigger_buy_rsi_15m))[-3:] + " "
        str_line = str_line + ("   " + str(self.buy_status)) + " "
        self.buy_percentage = ((self.repetitions_buy * 100) / self.repetitions)
        str_line = str_line + ("       " + str("{:.2f}".format(self.buy_percentage)))[-7:] + " "
        str_line = str_line + ("   " + str(round(self.current_rsi_wk )))[-3:] + " "
        str_line = str_line + ("   " + str(round(self.current_rsi_day)))[-3:] + " "
        str_line = str_line + ("   " + str(round(self.current_rsi_4hr)))[-3:] + " "
        str_line = str_line + ("   " + str(round(self.current_rsi_1hr)))[-3:] + " "
        str_line = str_line + ("   " + str(round(self.current_rsi_30m)))[-3:] + " "
        str_line = str_line + ("   " + str(round(self.current_rsi_15m)))[-3:] + " "
        self.sell_percentage = ((self.repetitions_sell * 100) / self.repetitions)
        str_line = str_line + ("       " + str("{:.2f}".format(self.sell_percentage)))[-7:] + " "
        str_line = str_line + ("   " + str(self.sell_status)) + " "
        str_line = str_line + ("   " + str(self.trigger_sell_rsi_wk ))[-3:] + " "
        str_line = str_line + ("   " + str(self.trigger_sell_rsi_day))[-3:] + " "
        str_line = str_line + ("   " + str(self.trigger_sell_rsi_4hr))[-3:] + " "
        str_line = str_line + ("   " + str(self.trigger_sell_rsi_1hr))[-3:] + " "
        str_line = str_line + ("   " + str(self.trigger_sell_rsi_30m))[-3:] + " "
        str_line = str_line + ("   " + str(self.trigger_sell_rsi_15m))[-3:] + " "
        str_line = str_line + ("   " + str(self.repetitions)) + " "
        str_line = str_line + ("   " + str(self.repetitions_buy)) + " "
        str_line = str_line + ("   " + str(self.repetitions_sell))
        if ((self.buy_percentage != 0) or (self.sell_percentage != 0)):
           func_display_info(20, 'Both', [str_line])

    def update(self, obj_LineMarketIndicators):  
        self.current_rsi_wk  = obj_LineMarketIndicators.rsi_wk
        self.current_rsi_day = obj_LineMarketIndicators.rsi_day
        self.current_rsi_4hr = obj_LineMarketIndicators.rsi_4hr
        self.current_rsi_1hr = obj_LineMarketIndicators.rsi_1hr
        self.current_rsi_30m = obj_LineMarketIndicators.rsi_30m
        self.current_rsi_15m = obj_LineMarketIndicators.rsi_15m
        if ((self.trigger_buy_rsi_wk  > self.current_rsi_wk ) and
            (self.trigger_buy_rsi_day > self.current_rsi_day) and
            (self.trigger_buy_rsi_4hr > self.current_rsi_4hr) and
            (self.trigger_buy_rsi_1hr > self.current_rsi_1hr) and
            (self.trigger_buy_rsi_30m > self.current_rsi_30m) and
            (self.trigger_buy_rsi_15m > self.current_rsi_15m )):
            self.buy_status = 'Yes'
        else:
            self.buy_status = 'No '
        if ((self.trigger_sell_rsi_wk  < self.current_rsi_wk ) and
            (self.trigger_sell_rsi_day < self.current_rsi_day) and
            (self.trigger_sell_rsi_4hr < self.current_rsi_4hr) and
            (self.trigger_sell_rsi_1hr < self.current_rsi_1hr) and
            (self.trigger_sell_rsi_30m < self.current_rsi_30m) and
            (self.trigger_sell_rsi_15m < self.current_rsi_15m)):
            self.sell_status = 'Yes'
        else:
            self.sell_status = 'No '

class cls_LineMarketIndicators:
    def __init__(self, symbol):  # attributes

        self.symbol      = symbol
        self.last_update = 0            # Seconds since last update
        self.need_load_from_file = 'Yes'     # Set to load prices from file
        self.list_prices =  [
                                # {
                                #     'date':  0,    Epoch date
                                #     'price': 0,    Stock price
                                #     'frequency': 0 0 - last price,
                                #                    1 1min,
                                #                    5 5min,
                                #                   15 15min,
                                #                   30 30min
                                #                   60 60min
                                #       24 * 60 = 1440 1day
                                #  7 * 24 * 60 = 10087 1wk
                                # }
                            ]
        self.rsi_wk     = 0.0
        self.rsi_day    = 0.0
        self.rsi_4hr    = 0.0
        self.rsi_1hr    = 0.0
        self.rsi_30m    = 0.0
        self.rsi_15m    = 0.0
        self.last_price = 0.0

    def load_from_file(self, DateTimeNow_UnixEpoch_TDAFormat):
        if (self.need_load_from_file == 'Yes'):
            self.need_load_from_file = 'No'
            if (os.path.isfile('Stock_' + self.symbol.strip() + '.txt')):                                # History already exists
                func_display_info(20, 'Both', ['Load from file Historical Prices ' + self.symbol.strip()])
                self.last_update = int(os.path.getctime('Stock_' + self.symbol.strip() + '.txt') * 1000)
                with open('Stock_' + self.symbol.strip() + '.txt') as file:
                    for str_line in file:
                        str_line = str_line.strip()
                        #print(line + ' ' + str(len(self.list_prices)))
                        self.list_prices.append([int(str_line[0:15].strip()), float(str_line[16:31].strip()), int(str_line[32:42].strip())])
                if (len(self.list_prices) < 100):  # If no records - or little records on file -, load prices from Online
                    self.last_update = DateTimeNow_UnixEpoch_TDAFormat - (3 * 365 * 24 * 60 * 60 * 1000)
            else:                                                                                       # History does not exist; set Last Update to 3 years
                self.last_update = DateTimeNow_UnixEpoch_TDAFormat - (3 * 365 * 24 * 60 * 60 * 1000)
        func_display_info(60, 'Both', ['Historical records loaded from file: ' + str(len(self.list_prices))])

    def load_from_online(self, DateTimeNow_UnixEpoch_TDAFormat):
        global bool_isOpen, bool_preMarket, bool_regularMarket, bool_postMarket
        global lst_stock_regularMarketOnly_OTCOnly_OTC  # list of stocks with restrictions to place single orders

        func_display_info(50, 'Both', ['Last Update: ' + str(self.last_update)])
        if (self.last_update < (DateTimeNow_UnixEpoch_TDAFormat - (365 * 24 * 60 * 60 * 1000))):    # If Last Update older than 1 year, get Daily Prices for the last 3 years
            StartDate = DateTimeNow_UnixEpoch_TDAFormat - (3 * 365 * 24 * 60 * 60 * 1000)           # Start Date is 3 years ago
            while (StartDate < (DateTimeNow_UnixEpoch_TDAFormat - (3 * 30 * 24 * 60 * 60 * 1000))): # Process until 3 months earlier from now
                EndDate = StartDate + (3 * 30 * 24 * 60 * 60 * 1000)                                # Process 3 months
                self.list_prices.extend(api_GetHistoricalPrices(self.symbol, 1440, 'month', 'daily', 1, StartDate, EndDate))
                StartDate = EndDate
        if (self.last_update < (DateTimeNow_UnixEpoch_TDAFormat - (3 * 30 * 24 * 60 * 60 * 1000))):  # If Last Update older than 3 months, get 15 min Prices for the last 3 months
            StartDate = DateTimeNow_UnixEpoch_TDAFormat - (3 * 30 * 24 * 60 * 60 * 1000)             # Start Date is 3 months ago

            if ((datetime.fromtimestamp(StartDate / 1000).strftime("%A")) == 'Saturday'):
                StartDate = StartDate - (1 * 24 * 60 * 60 * 1000)  # Subtract 1 day to move to Friday
            if ((datetime.fromtimestamp(StartDate / 1000).strftime("%A")) == 'Sunday'):
                StartDate = StartDate - (2 * 24 * 60 * 60 * 1000)  # Subtract 2 days to move to Friday

            while (StartDate < (DateTimeNow_UnixEpoch_TDAFormat - (5 * 24 * 60 * 60 * 1000))):      # Process until 5 days earlier from now
                EndDate = StartDate + (5 * 24 * 60 * 60 * 1000)                                     # Process 5 days

                if ((datetime.fromtimestamp(EndDate / 1000).strftime("%A")) == 'Saturday'):
                    EndDate = EndDate - (1 * 24 * 60 * 60 * 1000)  # Subtract 1 day to move to Friday
                if ((datetime.fromtimestamp(EndDate / 1000).strftime("%A")) == 'Sunday'):
                    EndDate = EndDate - (2 * 24 * 60 * 60 * 1000)  # Subtract 2 days to move to Friday

                self.list_prices.extend(api_GetHistoricalPrices(self.symbol, 15, 'day', 'minute', 15, StartDate, EndDate))
                StartDate = EndDate
        if ((self.last_update < (DateTimeNow_UnixEpoch_TDAFormat - (5 * 24 * 60 * 60 * 1000))) or     # If Last Update older than 5 days, get 1 min Prices for the last 5 days
            (self.last_update < (DateTimeNow_UnixEpoch_TDAFormat - (          5 * 60 * 1000))) or     # or if Last Update older than 5 minutes
            (self.last_update < (DateTimeNow_UnixEpoch_TDAFormat - (          1 * 60 * 1000))) or     # or if Last Update older than 1 minutes
            ( 1 != 1)):                                                                               # or always (maybe) - if delay in processing orders too long.
            func_display_info(80, 'Both', ['Getting historical prices because last update is greater than 5 minutes mark'])
            StartDate = DateTimeNow_UnixEpoch_TDAFormat - (5 * 24 * 60 * 60 * 1000)                   # Start Date is 5 days ago
            EndDate = DateTimeNow_UnixEpoch_TDAFormat                                                 # Process till today
            self.list_prices.extend(api_GetHistoricalPrices(self.symbol, 1, 'day', 'minute', 1, StartDate, EndDate))

        # Load Last Price
        func_check_market_hours()

        DateTimeNow_UnixEpoch_TDAFormat = int(round(time.time() * 1000, 0))  # current EPOCH time in TDA format
        if (self.symbol in lst_stock_regularMarketOnly_OTC_list):
            if (bool_regularMarket):  # Check if current NY time is regularMarket
                self.list_prices.append([DateTimeNow_UnixEpoch_TDAFormat, api_GetLastPrice(self.symbol), 0])  # Get Latest price
                func_display_info(80, 'Both', ['DateTimeNow_UnixEpoch_TDAFormat: ' + str(DateTimeNow_UnixEpoch_TDAFormat)])
        else:
            if (bool_preMarket or bool_regularMarket or bool_postMarket):  # Check if current NY time is preMarket, regularMarket or postMarket
               self.list_prices.append([DateTimeNow_UnixEpoch_TDAFormat, api_GetLastPrice(self.symbol), 0])  # Get Latest price
               func_display_info(80, 'Both', ['DateTimeNow_UnixEpoch_TDAFormat: ' + str(DateTimeNow_UnixEpoch_TDAFormat)])
        self.last_update = DateTimeNow_UnixEpoch_TDAFormat  # Prices updated
        func_display_info(80, 'Both', ['Total of Prices loaded from online: ' + str(len(self.list_prices))])

        # Delete records with price 0
        for objPrice in self.list_prices:
            if (objPrice[1] == 0):    # if price is zero, remove
                self.list_prices.remove(objPrice)
        func_display_info(80, 'Both', ['Total of Prices after deleting price zero: ' + str(len(self.list_prices))])

        # Sort records; oldest records first
        self.list_prices = sorted(self.list_prices, reverse = True)
        func_display_info(80, 'Both', ['Total of Records after sorting: ' + str(len(self.list_prices))])

        #for objPrice in self.list_prices:
        #    print('Date: ' + str(objPrice[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPrice[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPrice[1], 2)) + ' Range: ' + str(objPrice[2]))

        # Remove duplicate records; change to Tuples
        self.list_prices = set(tuple(x) for x in self.list_prices)  # convert inner lists to tuples so they are hashable
        self.list_prices = [list(x) for x in self.list_prices]      # convert tuples back into lists

        func_display_info(80, 'Both', ['Total of Records after deleting duplicates: ' + str(len(self.list_prices))])

        #for objPrice in self.list_prices:
        #    print('Date: ' + str(objPrice[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPrice[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPrice[1], 2)) + ' Range: ' + str(objPrice[2]))

        # Sort records; oldest records first
        self.list_prices = sorted(self.list_prices, reverse = True)
        func_display_info(80, 'Both', ['Total of Records after sorting: ' + str(len(self.list_prices))])

        # Delete mixed Range records, first pass
        int_cntr = 0
        for objPrice in self.list_prices:

            func_display_info(80, 'Both', ['Symb: ' + self.symbol + ' Date: ' + str(objPrice[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPrice[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPrice[1], 2)) + ' Range: ' + str(objPrice[2]) + ' ---(value)'])

            int_cntr = int_cntr + 1
            if (int_cntr == 1):
                objPricePPPP = objPrice
                objPricePPP  = objPrice
                objPricePP   = objPrice
                objPriceP    = objPrice
            # PriorPriorPriorPrior PPPP ==   1    1   1
            # PriorPriorPrior      PPP  !=  15    1   1
            # PriorPrior           PP   !=  15   15   1
            # Prior                P    !=  15   15  15  <-- delete when different
            # Current                        1    1   1
            if (objPricePPPP[2] == objPrice[2]):
                if ((objPricePPP[2] != objPrice[2]) and (objPricePP[2] != objPrice[2]) and  (objPriceP[2] != objPrice[2])):  # 3 out of sequence
                    if (objPriceP[2] > 1):
                        self.list_prices.remove(objPriceP)  # skip for Ranges 0 or 1 only
                        func_display_info(80, 'Both', ['Symb: ' + self.symbol + ' Date: ' + str(objPriceP[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPriceP[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPriceP[1], 2)) + ' Range: ' + str(objPriceP[2]) + ' -- (remove P)'])
                        objPriceP = objPrice
                    if (objPricePP[2] > 1):
                        self.list_prices.remove(objPricePP)
                        func_display_info(80, 'Both', ['Symb: ' + self.symbol + ' Date: ' + str(objPricePP[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPricePP[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPricePP[1], 2)) + ' Range: ' + str(objPricePP[2]) + ' -- (remove PP)'])
                        objPricePP = objPrice
                    if (objPricePPP[2] > 1):
                        self.list_prices.remove(objPricePPP)
                        func_display_info(80, 'Both', ['Symb: ' + self.symbol + ' Date: ' + str(objPricePPP[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPricePPP[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPricePPP[1], 2)) + ' Range: ' + str(objPricePPP[2]) + ' -- (remove PPP)'])
                        objPricePPP = objPrice
            if (objPricePPP[2] == objPrice[2]):
                if ((objPricePP[2] != objPrice[2]) and (objPriceP[2] != objPrice[2])):  # 2 out of sequence
                    if (objPriceP[2] > 1):
                        self.list_prices.remove(objPriceP)
                        func_display_info(80, 'Both', ['Symb: ' + self.symbol + ' Date: ' + str(objPriceP[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPriceP[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPriceP[1], 2)) + ' Range: ' + str(objPriceP[2]) + ' -- (remove P'])
                        objPriceP = objPrice
                    if (objPricePP[2] > 1):
                        self.list_prices.remove(objPricePP)
                        func_display_info(80, 'Both', ['Symb: ' + self.symbol + ' Date: ' + str(objPricePP[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPricePP[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPricePP[1], 2)) + ' Range: ' + str(objPricePP[2]) + ' -- (remove PP)'])
                        objPricePP = objPrice
            if (objPricePP[2] == objPrice[2]):
                if (objPriceP[2] != objPrice[2]):  # 1 out of sequence
                    if (objPriceP[2] > 1):
                        self.list_prices.remove(objPriceP)
                        func_display_info(80, 'Both', ['Symb: ' + self.symbol + ' Date: ' + str(objPriceP[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPriceP[0] / 1000, 0)))   + ' Price: ' + '{:.8f}'.format(round(objPriceP[1], 2))   + ' Range: ' + str(objPriceP[2]) + ' -- (remove P)'])
                        objPriceP = objPrice

            objPricePPPP = objPricePPP
            objPricePPP = objPricePP
            objPricePP = objPriceP
            objPriceP = objPrice

        #DisplayInfo(80, 'Both', ['Selected - Symb: ' + self.symbol + ' Date: ' + str(objPricePrior[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPricePrior[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPricePrior[1], 2)) + ' Range: ' + str(objPricePrior[2]) + ' ---(remove)'])

        func_display_info(80, 'Both', ['Total of Records after deleting records with mix ranges, first pass: ' + str(len(self.list_prices))])

        # Sort records again; oldest records first
        self.list_prices = sorted(self.list_prices, reverse = True)
        func_display_info(80, 'Both', ['Total of Records after sorting: ' + str(len(self.list_prices))])

        # Delete mixed Range records, second pass
        int_cntr = 0
        for objPrice in self.list_prices:

            func_display_info(80, 'Both', ['Symb: ' + self.symbol + ' Date: ' + str(objPrice[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPrice[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPrice[1], 2)) + ' Range: ' + str(objPrice[2]) + ' ---(value)'])

            int_cntr = int_cntr + 1
            if (int_cntr == 1):
                objPricePPPP = objPrice
                objPricePPP  = objPrice
                objPricePP   = objPrice
                objPriceP    = objPrice
            # PriorPriorPriorPrior PPPP ==   1    1   1
            # PriorPriorPrior      PPP  !=  15    1   1
            # PriorPrior           PP   !=  15   15   1
            # Prior                P    !=  15   15  15  <-- delete when different
            # Current                        1    1   1
            if (objPricePPPP[2] == objPrice[2]):
                if ((objPricePPP[2] != objPrice[2]) and (objPricePP[2] != objPrice[2]) and  (objPriceP[2] != objPrice[2])):  # 3 out of sequence
                    if (objPriceP[2] > 1):
                        self.list_prices.remove(objPriceP)  # skip for Ranges 0 or 1 only
                        func_display_info(80, 'Both', ['Symb: ' + self.symbol + ' Date: ' + str(objPriceP[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPriceP[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPriceP[1], 2)) + ' Range: ' + str(objPriceP[2]) + ' -- (remove P)'])
                        objPriceP = objPrice
                    if (objPricePP[2] > 1):
                        self.list_prices.remove(objPricePP)
                        func_display_info(80, 'Both', ['Symb: ' + self.symbol + ' Date: ' + str(objPricePP[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPricePP[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPricePP[1], 2)) + ' Range: ' + str(objPricePP[2]) + ' -- (remove PP)'])
                        objPricePP = objPrice
                    if (objPricePPP[2] > 1):
                        self.list_prices.remove(objPricePPP)
                        func_display_info(80, 'Both', ['Symb: ' + self.symbol + ' Date: ' + str(objPricePPP[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPricePPP[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPricePPP[1], 2)) + ' Range: ' + str(objPricePPP[2]) + ' -- (remove PPP)'])
                        objPricePPP = objPrice
            if (objPricePPP[2] == objPrice[2]):
                if ((objPricePP[2] != objPrice[2]) and (objPriceP[2] != objPrice[2])):  # 2 out of sequence
                    if (objPriceP[2] > 1):
                        self.list_prices.remove(objPriceP)
                        func_display_info(80, 'Both', ['Symb: ' + self.symbol + ' Date: ' + str(objPriceP[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPriceP[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPriceP[1], 2)) + ' Range: ' + str(objPriceP[2]) + ' -- (remove P'])
                        objPriceP = objPrice
                    if (objPricePP[2] > 1):
                        self.list_prices.remove(objPricePP)
                        func_display_info(80, 'Both', ['Symb: ' + self.symbol + ' Date: ' + str(objPricePP[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPricePP[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPricePP[1], 2)) + ' Range: ' + str(objPricePP[2]) + ' -- (remove PP)'])
                        objPricePP = objPrice
            if (objPricePP[2] == objPrice[2]):
                if (objPriceP[2] != objPrice[2]):  # 1 out of sequence
                    if (objPriceP[2] > 1):
                        self.list_prices.remove(objPriceP)
                        func_display_info(80, 'Both', ['Symb: ' + self.symbol + ' Date: ' + str(objPriceP[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPriceP[0] / 1000, 0)))   + ' Price: ' + '{:.8f}'.format(round(objPriceP[1], 2))   + ' Range: ' + str(objPriceP[2]) + ' -- (remove P)'])
                        objPriceP = objPrice

            objPricePPPP = objPricePPP
            objPricePPP = objPricePP
            objPricePP = objPriceP
            objPriceP = objPrice

        #DisplayInfo(80, 'Both', ['Selected - Symb: ' + self.symbol + ' Date: ' + str(objPricePrior[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPricePrior[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPricePrior[1], 2)) + ' Range: ' + str(objPricePrior[2]) + ' ---(remove)'])

        func_display_info(80, 'Both', ['Total of Records after deleting records with mix ranges, second pass: ' + str(len(self.list_prices))])

        # Sort records again; oldest records first
        self.list_prices = sorted(self.list_prices, reverse = True)
        func_display_info(80, 'Both', ['Total of Records after sorting: ' + str(len(self.list_prices))])

        func_display_info(50, 'Both', ['Total of Records after sorting: ' + str(self.symbol) + ' ' + str(len(self.list_prices))])

    def calc_last_price(self, LastPrice):
        self.last_price = LastPrice

    def calc_rsi(self, Period, DateMark):
        if (Period == 'week'):
            TimeDelta = (7 * 24 * 60 * 60 * 1000)
        if (Period == 'day'):
            TimeDelta = (24 * 60 * 60 * 1000)
        if (Period == '4hr'):
            TimeDelta = (4 * 60 * 60 * 1000)
        if (Period == '1hr'):
            TimeDelta = (1 * 60 * 60 * 1000)
        if (Period == '30min'):
            TimeDelta = (30 * 60 * 1000)
        if (Period == '15min'):
            TimeDelta = (15 * 60 * 1000)
        func_display_info(70, 'Both', ['Period: ' + Period])
        ListValues = []
        for objPrice in self.list_prices:  # ListPrices sorted already; oldest first

            if ((Period == 'week') or (Period == 'day')):
                if ((objPrice[0] <= DateMark) and (len(ListValues) > -1)):
                    ListValues.append(objPrice[1])

                    #print('Selected - Date: ' + str(objPrice[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPrice[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPrice[1], 2)) + ' Range: ' + str(objPrice[2]))

                    # DateMark = DateMark - TimeDelta
                    DateMark = objPrice[0] - TimeDelta
                    # Week - Move DateMark to prior stock price reading to skip holidays; over 24 hours period
                    # Day  - Move DateMark to prior stock price reading to skip weekends and holidays; 24 hour period

            if ((Period == '4hr') or (Period == '1hr') or (Period == '30min') or (Period == '15min')):
                if ((objPrice[0] <= DateMark) and (len(ListValues) > -1)):
                    ListValues.append(objPrice[1])

                    if ((Period == '15min') and (len(ListValues) < 40)):
                       func_display_info(80, 'Both', ['Selected - Symb: ' + self.symbol + ' Period: ' + Period + ' Date: ' + str(objPrice[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPrice[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPrice[1], 2)) + ' Range: ' + str(objPrice[2])])

                    MovingDate = objPrice[0]  # it could be DateMark or objPrice[0]. Keeping objPrice[0] to compensate with non-tradeing after hours
                    func_display_info(82, 'Both', ['MovingDate: ' + str(MovingDate)])

                    # Calcualte 6 AM Date, current day
                    DateAt6AM_Basic = datetime(datetime.fromtimestamp(MovingDate / 1000).year,
                                               datetime.fromtimestamp(MovingDate / 1000).month,
                                               datetime.fromtimestamp(MovingDate / 1000).day, 6, 0)
                    func_display_info(82, 'Both', ['DateAt6AM_Basic: ' + str(DateAt6AM_Basic)])

                    DateAt6AM_UnixEpoch = time.mktime(DateAt6AM_Basic.timetuple())
                    func_display_info(82, 'Both', ['DateAt6AM_UnixEpoch: ' + str(DateAt6AM_UnixEpoch)])

                    DateAt6AM_UnixEpoch_TDAFormat = DateAt6AM_UnixEpoch * 1000
                    func_display_info(82, 'Both', ['DateAt6AM_UnixEpoch_TDAFormat: ' + str(DateAt6AM_UnixEpoch_TDAFormat)])

                    # Calcualte 7 PM Date, prior day
                    DateAt7PM_UnixEpoch_TDAFormat = DateAt6AM_UnixEpoch_TDAFormat - (11 * 60 * 60 * 1000)  # 6AM -> 7PM, 11 hours
                    func_display_info(82, 'Both', ['DateAt7PM_UnixEpoch_TDAFormat: ' + str(DateAt7PM_UnixEpoch_TDAFormat)])

                    if ((MovingDate - DateAt6AM_UnixEpoch_TDAFormat) < TimeDelta):  # No space for delta; need to compensate for dead zone
                        AdjustTime_TDAFormat = TimeDelta - (MovingDate - DateAt6AM_UnixEpoch_TDAFormat)
                        MovingDate = DateAt7PM_UnixEpoch_TDAFormat - AdjustTime_TDAFormat
                        func_display_info(82, 'Both', ['AdjustTime_TDAFormat: ' + str(AdjustTime_TDAFormat)])
                    else:                                                            # There is space for delta
                         MovingDate = MovingDate - TimeDelta
                    func_display_info(82, 'Both', ['MovingDate: ' + str(MovingDate)])

                    if ((datetime.fromtimestamp(MovingDate / 1000).strftime("%A")) == 'Sunday'):
                        MovingDate = MovingDate - (2 * 24 * 60 * 60 * 1000)  # if Sunday, subtract 2 day

                    if ((datetime.fromtimestamp(MovingDate / 1000).strftime("%A")) == 'Saturday'):
                        MovingDate = MovingDate - (1 * 24 * 60 * 60 * 1000)  # if Saturday, subtract 1 day
                    func_display_info(82, 'Both', ['MovingDate: ' + str(MovingDate)])

                    DateMark = MovingDate

                else:
                    if ((Period == '15min') and (len(ListValues) < 40)):
                       func_display_info(80, 'Both', ['Selected - Symb: ' + self.symbol + ' Period: ' + Period + ' Date: ' + str(objPrice[0]) + ' Format: ' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(round(objPrice[0] / 1000, 0))) + ' Price: ' + '{:.8f}'.format(round(objPrice[1], 2)) + ' Range: ' + str(objPrice[2]) + ' ---(skip)'])

        func_display_info(70, 'Both', ['len(ListValues): ' + str(len(ListValues))])
        ListValues.reverse()  # Oldest prices first

        if (Period == 'week'):
            self.rsi_wk = func_calc_rsi(ListValues)
        if (Period == 'day'):
            self.rsi_day = func_calc_rsi(ListValues)
        if (Period == '4hr'):
            self.rsi_4hr = func_calc_rsi(ListValues)
        if (Period == '1hr'):
            self.rsi_1hr = func_calc_rsi(ListValues)
        if (Period == '30min'):
            self.rsi_30m = func_calc_rsi(ListValues)
        if (Period == '15min'):
            self.rsi_15m = func_calc_rsi(ListValues)

    def print(self):
        str_line = str(self.symbol + "      ")[0:6]
        str_line = str_line + str("{:.2f}".format(round(self.rsi_wk  ,2))) + " "
        str_line = str_line + str("{:.2f}".format(round(self.rsi_day ,2))) + " "
        str_line = str_line + str("{:.2f}".format(round(self.rsi_4hr ,2))) + " "
        str_line = str_line + str("{:.2f}".format(round(self.rsi_1hr ,2))) + " "
        str_line = str_line + str("{:.2f}".format(round(self.rsi_30m ,2))) + " "
        str_line = str_line + str("{:.2f}".format(round(self.rsi_15m ,2))) + " "
        str_line = str_line + str("{:7.2f}".format(round(self.last_price ,2))) + " "
        return(str_line)

    def save(self):
        func_display_info(20, 'Both', ['Delete and rewrite file with Historical Prices ' + self.symbol.strip()])
        if os.path.exists(str_path_dir_Data + '\Stock_' + self.symbol.strip() + '.txt'):
            os.remove(str_path_dir_Data +'\Stock_' + self.symbol.strip() + '.txt')
            time.sleep(float_time_delay_io)  # Delay given to remove/delete file
        outF = open(str_path_dir_Data + '\Stock_' + self.symbol.strip() + '.txt', "a")
        for objPrice in self.list_prices:
            str_line =            ("               " + str(objPrice[0]))[-15:]                  + " "
            str_line = str_line + ("               " + str("{:.6f}".format(objPrice[1])))[-15:] + " "
            str_line = str_line + ("          "      + str(objPrice[2]))[-10:]
            outF.write(str_line)
            outF.write("\n")
        time.sleep(float_time_delay_io)  # Delay given to write file
        outF.close()

class cls_LineOrderStatus:
    def __init__(self, str_from_file, str_line):   # attributes
        if str_from_file == "FromFile":
            self.symbol                 = str_line[0:5].strip()
            self.period                 = str_line[6:21].strip()
            self.type                   = str_line[22:33].strip()
            self.acct_desc              = str_line[34:64].strip()
            self.seq                    = int(str_line[65:68].strip())
            self.trigger_buy_gap        = float(str_line[69:74].strip())
            self.trigger_buy_rsi_wk     = int(str_line[75:78].strip())
            self.trigger_buy_rsi_day    = int(str_line[79:82].strip())
            self.trigger_buy_rsi_4hr    = int(str_line[83:86].strip())
            self.trigger_buy_rsi_1hr    = int(str_line[87:90].strip())
            self.trigger_buy_rsi_30m    = int(str_line[91:94].strip())
            self.trigger_buy_rsi_15m    = int(str_line[95:98].strip())
            self.trigger_buy_adj_price  = float(str_line[99:104].strip())
            self.trigger_sell_rsi_wk    = int(str_line[105:108].strip())
            self.trigger_sell_rsi_day   = int(str_line[109:112].strip())
            self.trigger_sell_rsi_4hr   = int(str_line[113:116].strip())
            self.trigger_sell_rsi_1hr   = int(str_line[117:120].strip())
            self.trigger_sell_rsi_30m   = int(str_line[121:124].strip())
            self.trigger_sell_rsi_15m   = int(str_line[125:128].strip())
            self.trigger_sell_adj_price = float(str_line[129:134].strip())
            self.trigger_buy_shares_amt = float(str_line[135:141].strip())

            self.order_buy_status       = str_line[196:206].strip()
            if (self.order_buy_status != ""):
                self.order_buy_rsi_wk   = int(str_line[142:145].strip())
                self.order_buy_rsi_day  = int(str_line[146:149].strip())
                self.order_buy_rsi_4hr  = int(str_line[150:153].strip())
                self.order_buy_rsi_1hr  = int(str_line[154:157].strip())
                self.order_buy_rsi_30m  = int(str_line[158:161].strip())
                self.order_buy_rsi_15m  = int(str_line[162:165].strip())
                self.order_buy_number   = int(str_line[166:178].strip())
                self.order_buy_shares   = int(str_line[179:185].strip())
                self.order_buy_price    = float(str_line[186:195].strip())
                self.order_buy_status   = str_line[196:206].strip()
            else:
                self.order_buy_rsi_wk   = 0
                self.order_buy_rsi_day  = 0
                self.order_buy_rsi_4hr  = 0
                self.order_buy_rsi_1hr  = 0
                self.order_buy_rsi_30m  = 0
                self.order_buy_rsi_15m  = 0
                self.order_buy_number   = 0
                self.order_buy_shares   = 0
                self.order_buy_price    = 0.0
                self.order_buy_status   = ""

            self.order_sell_status      = str_line[262:271].strip()
            if (self.order_sell_status != ""):
                self.order_sell_rsi_wk  = int(str_line[207:210].strip())
                self.order_sell_rsi_day = int(str_line[211:214].strip())
                self.order_sell_rsi_4hr = int(str_line[215:218].strip())
                self.order_sell_rsi_1hr = int(str_line[219:222].strip())
                self.order_sell_rsi_30m = int(str_line[223:226].strip())
                self.order_sell_rsi_15m = int(str_line[227:230].strip())
                self.order_sell_number  = int(str_line[231:242].strip())
                self.order_sell_shares  = int(str_line[243:250].strip())
                self.order_sell_price   = float(str_line[251:260].strip())
                self.order_sell_status  = str_line[262:271].strip()
            else:
                self.order_sell_rsi_wk  = 0
                self.order_sell_rsi_day = 0
                self.order_sell_rsi_4hr = 0
                self.order_sell_rsi_1hr = 0
                self.order_sell_rsi_30m = 0
                self.order_sell_rsi_15m = 0
                self.order_sell_number  = 0
                self.order_sell_shares  = 0
                self.order_sell_price   = 0.0
                self.order_sell_status  = ""

    def place_order(self, float_prior_order_buy_price, obj_LineMarketIndicators):
        global bool_preMarket, bool_regularMarket, bool_postMarket
        global lst_stock_regularMarketOnly_OTC_list
        func_check_market_hours()
        if (self.order_buy_status.strip() == '' ):  # Check if Buy Order was placed already
            if (os.path.isfile("PlaceBuyOrders.txt")):  # Check if file PlaceBuyOrders exits
                if (((self.symbol     in lst_stock_regularMarketOnly_OTC_list) and ((self.type == 'Single') and (bool_regularMarket))) or                                       # Check if stock     in regularMarket and single order during regularMarket
                    ((self.symbol not in lst_stock_regularMarketOnly_OTC_list) and ((self.type == 'Single') and (bool_preMarket or bool_regularMarket or bool_postMarket))) or  # Check if stock not in regularMarket and single order during preMarket, regularMarket and postMarket
                    ((self.type == 'Conditional') and (bool_regularMarket))):                                                                                              # Check if conditional order during regularMarket
                    if ((self.trigger_buy_rsi_wk  > obj_LineMarketIndicators.rsi_wk ) and  # Check for triggers to place Buy Order
                        (self.trigger_buy_rsi_day > obj_LineMarketIndicators.rsi_day) and
                        (self.trigger_buy_rsi_4hr > obj_LineMarketIndicators.rsi_4hr) and
                        (self.trigger_buy_rsi_1hr > obj_LineMarketIndicators.rsi_1hr) and
                        (self.trigger_buy_rsi_30m > obj_LineMarketIndicators.rsi_30m) and
                        (self.trigger_buy_rsi_15m > obj_LineMarketIndicators.rsi_15m) and
                        (((float_prior_order_buy_price > 0.0) and (((1 - (self.trigger_buy_gap / 1000)) * (float_prior_order_buy_price)) > obj_LineMarketIndicators.last_price)) or (float_prior_order_buy_price == 0))):  # Prior order buy price adjustment condition
                        # Place New Buy Order
                        self.order_buy_rsi_wk  = round(obj_LineMarketIndicators.rsi_wk )  # Save Buy Order RSI Indicators
                        self.order_buy_rsi_day = round(obj_LineMarketIndicators.rsi_day)
                        self.order_buy_rsi_4hr = round(obj_LineMarketIndicators.rsi_4hr)
                        self.order_buy_rsi_1hr = round(obj_LineMarketIndicators.rsi_1hr)
                        self.order_buy_rsi_30m = round(obj_LineMarketIndicators.rsi_30m)
                        self.order_buy_rsi_15m = round(obj_LineMarketIndicators.rsi_15m)
                        self.order_buy_number = 0                                         # Save Buy Order Number (Temp)
                        self.order_buy_status = 'New_Order'                               # Save Buy Order Status (Temp)
                        self.order_buy_shares = round(self.trigger_buy_shares_amt / obj_LineMarketIndicators.last_price)  # Save Buy Order Number of Shares
                        if (self.order_buy_shares == 0): self.order_buy_shares = 1                                        # Verify Number of Shares is at least 1
                        self.order_sell_shares = self.order_buy_shares                                                    # Save Sell Order Number of Shares
                        self.order_buy_price = (self.trigger_buy_adj_price * obj_LineMarketIndicators.last_price)         # Save Buy Order Price
                        self.order_buy_price = float(f"{self.order_buy_price:.2f}")                                       # Truncate Buy Order Price
                        if (self.type == 'Single'):       # If Single Order
                            self.order_buy_status = api_PlaceOrder('Single', 'BUY', func_get_account(self.acct_desc), self)                    # default status Transition
                            self.order_buy_number = api_GetOrderByPath('Single', 'BUY', func_get_account(self.acct_desc), self)                # Buy Order Number received
                            self.order_buy_status = api_GetOrderStatus('BUY', func_get_account(self.acct_desc), self)                          # actual status
                            obj_ListLineOrderStatus.save()                                                                # Save Order Status file as contingency
                        if (self.type == 'Conditional'):  # If Conditional Order
                            self.order_sell_number = 0                                   # Save Sell Order Number (Temp)
                            self.order_sell_status = 'New_Order'                         # Save Sell Order Status (Temp)
                            self.order_sell_shares = self.order_buy_shares               # Number of shares
                            self.order_sell_price = round((self.order_buy_price * self.trigger_sell_adj_price), 2)  # Save Sell Order Price
                            self.order_buy_status = api_PlaceOrder('Conditional', 'BUY', func_get_account(self.acct_desc), self)         # default status Transition
                            OrderNumbers = api_GetOrderByPath('Conditional', 'BUY', func_get_account(self.acct_desc), self)              # Buy and Sell Order Numbers received
                            self.order_buy_number = OrderNumbers[0]
                            self.order_sell_number = OrderNumbers[1]
                            self.order_buy_status = api_GetOrderStatus('BUY', func_get_account(self.acct_desc), self)   #ofsofs I do not need this parm                 # actual status
                            obj_ListLineOrderStatus.save()                                                          # Save Order Status file as contingency

        if ((self.order_buy_status.strip() == 'FILLED') and (self.order_sell_status.strip() == '')):        # Check if Sell Order is already in place; Conditional Order not apply
            if ((self.type == 'Single') and (bool_preMarket or bool_regularMarket or bool_postMarket)):     # Check if single order during preMarket, regularMarket and postMarket
                if ((self.trigger_sell_rsi_wk  < obj_LineMarketIndicators.rsi_wk ) and                      # Check for triggers to place Sell Order
                    (self.trigger_sell_rsi_day < obj_LineMarketIndicators.rsi_day) and
                    (self.trigger_sell_rsi_4hr < obj_LineMarketIndicators.rsi_4hr) and
                    (self.trigger_sell_rsi_1hr < obj_LineMarketIndicators.rsi_1hr) and
                    (self.trigger_sell_rsi_30m < obj_LineMarketIndicators.rsi_30m) and
                    (self.trigger_sell_rsi_15m < obj_LineMarketIndicators.rsi_15m) and
                    ((self.order_buy_price * 1.01) < obj_LineMarketIndicators.last_price) and                       # Minimum 1% profit
                    ((self.order_buy_price * self.trigger_sell_adj_price) < obj_LineMarketIndicators.last_price)):  # Minimun sell adjustment price
                    # Place New Sell Order
                    self.order_sell_rsi_wk  = round(obj_LineMarketIndicators.rsi_wk )                               # Save Buy Order RSI Indicators
                    self.order_sell_rsi_day = round(obj_LineMarketIndicators.rsi_day)
                    self.order_sell_rsi_4hr = round(obj_LineMarketIndicators.rsi_4hr)
                    self.order_sell_rsi_1hr = round(obj_LineMarketIndicators.rsi_1hr)
                    self.order_sell_rsi_30m = round(obj_LineMarketIndicators.rsi_30m)
                    self.order_sell_rsi_15m = round(obj_LineMarketIndicators.rsi_15m)
                    self.order_sell_number = 0                                                                     # Save Buy Order Number (Temp)
                    self.order_sell_status = 'New_Order'                                                           # Save Buy Order Status (Temp)
                    self.order_sell_shares = self.order_buy_shares                                                 # Save Sell Order Number of Shares
                    self.order_sell_price = round((1.001 * obj_LineMarketIndicators.last_price), 2)                # Save Sell Order Price; Round Sell Order Price
                    self.order_sell_status = api_PlaceOrder('Single', 'SELL', self)                                # default status Transition
                    self.order_sell_number = api_GetOrderByPath('Single', 'SELL', self)
                    self.order_sell_status = api_GetOrderStatus('SELL', self)                                      # actual status
                    obj_ListLineOrderStatus.save()                                                                 # Save Order Status file as contingency

    def print(self):
        str_line =                        str(self.symbol  + "     "                       )[:5]  + " "
        str_line = str_line +             str(self.period  + "               "             )[:15] + " "
        str_line = str_line +             str(self.type    + "           "                 )[:11] + " "
        str_line = str_line +             str(self.acct_desc + "                          ")[:30] + " "
        str_line = str_line + ("   "    + str(self.seq                                    ))[-3:] + " "
        str_line = str_line + ("     "  + str("{:.3f}".format(self.trigger_buy_gap)       ))[-5:] + " "
        str_line = str_line + ("   "    + str(self.trigger_buy_rsi_wk                     ))[-3:] + " "
        str_line = str_line + ("   "    + str(self.trigger_buy_rsi_day                    ))[-3:] + " "
        str_line = str_line + ("   "    + str(self.trigger_buy_rsi_4hr                    ))[-3:] + " "
        str_line = str_line + ("   "    + str(self.trigger_buy_rsi_1hr                    ))[-3:] + " "
        str_line = str_line + ("   "    + str(self.trigger_buy_rsi_30m                    ))[-3:] + " "
        str_line = str_line + ("   "    + str(self.trigger_buy_rsi_15m                    ))[-3:] + " "
        str_line = str_line + ("     "  + str("{:.3f}".format(self.trigger_buy_adj_price) ))[-5:] + " "
        str_line = str_line + ("   "    + str(self.trigger_sell_rsi_wk                    ))[-3:] + " "
        str_line = str_line + ("   "    + str(self.trigger_sell_rsi_day                   ))[-3:] + " "
        str_line = str_line + ("   "    + str(self.trigger_sell_rsi_4hr                   ))[-3:] + " "
        str_line = str_line + ("   "    + str(self.trigger_sell_rsi_1hr                   ))[-3:] + " "
        str_line = str_line + ("   "    + str(self.trigger_sell_rsi_30m                   ))[-3:] + " "
        str_line = str_line + ("   "    + str(self.trigger_sell_rsi_15m                   ))[-3:] + " "
        str_line = str_line + ("     "  + str("{:.3f}".format(self.trigger_sell_adj_price)))[-5:] + " "
        str_line = str_line + ("      " + str("{:.0f}".format(self.trigger_buy_shares_amt)))[-6:] + " "
        if (self.order_buy_status != ""):
            str_line = str_line + ("   " + str(self.order_buy_rsi_wk) )[-3:] + " "
            str_line = str_line + ("   " + str(self.order_buy_rsi_day))[-3:] + " "
            str_line = str_line + ("   " + str(self.order_buy_rsi_4hr))[-3:] + " "
            str_line = str_line + ("   " + str(self.order_buy_rsi_1hr))[-3:] + " "
            str_line = str_line + ("   " + str(self.order_buy_rsi_30m))[-3:] + " "
            str_line = str_line + ("   " + str(self.order_buy_rsi_15m))[-3:] + " "
            str_line = str_line + ("          " + str(self.order_buy_number))[-10:]                + " "
            str_line = str_line + ("      "     + str(self.order_buy_shares))[-6:]                 + " "
            str_line = str_line + ("         "  + str("{:.2f}".format(self.order_buy_price)))[-9:] + " "
            str_line = str_line + str(self.order_buy_status + "          ")[:10] + " "
            if (self.order_sell_status != ""):
                str_line = str_line + ("   " + str(self.order_sell_rsi_wk) )[-3:] + " "
                str_line = str_line + ("   " + str(self.order_sell_rsi_day))[-3:] + " "
                str_line = str_line + ("   " + str(self.order_sell_rsi_4hr))[-3:] + " "
                str_line = str_line + ("   " + str(self.order_sell_rsi_1hr))[-3:] + " "
                str_line = str_line + ("   " + str(self.order_sell_rsi_30m))[-3:] + " "
                str_line = str_line + ("   " + str(self.order_sell_rsi_15m))[-3:] + " "
                str_line = str_line + ("          " + str(self.order_sell_number))[-10:]                + " "
                str_line = str_line + ("      "     + str(self.order_sell_shares))[-6:]                 + " "
                str_line = str_line + ("         "  + str("{:.2f}".format(self.order_sell_price)))[-9:] + " "
                str_line = str_line + str(self.order_sell_status + "          ")[:10] + " "
        return(str_line)

    def reset_order(self):
        if ((self.order_buy_status == 'FILLED') and (self.order_sell_status == 'FILLED')):                      # Initialize order cycle.
            func_display_info(30, 'Both', [ 'Reset: ' + str(self.print())])
            obj_LineOrderStatus.order_buy_rsi_wk = 0
            obj_LineOrderStatus.order_buy_rsi_day = 0
            obj_LineOrderStatus.order_buy_rsi_4hr = 0
            obj_LineOrderStatus.order_buy_rsi_1hr = 0
            obj_LineOrderStatus.order_buy_rsi_30m = 0
            obj_LineOrderStatus.order_buy_rsi_15m = 0
            obj_LineOrderStatus.order_buy_number = 0
            obj_LineOrderStatus.order_buy_shares = 0.0
            obj_LineOrderStatus.order_buy_price = 0
            obj_LineOrderStatus.order_buy_status = ''
            obj_LineOrderStatus.order_sell_rsi_wk = 0
            obj_LineOrderStatus.order_sell_rsi_day = 0
            obj_LineOrderStatus.order_sell_rsi_4hr = 0
            obj_LineOrderStatus.order_sell_rsi_1hr = 0
            obj_LineOrderStatus.order_sell_rsi_30m = 0
            obj_LineOrderStatus.order_sell_rsi_15m = 0
            obj_LineOrderStatus.order_sell_number = 0
            obj_LineOrderStatus.order_sell_shares = 0
            obj_LineOrderStatus.order_sell_price = 0.0
            obj_LineOrderStatus.order_sell_status = ''
            obj_ListLineOrderStatus.save()                                                                               # Save Order Status file as contingency

    def update_order_status(self):
        if ((self.order_buy_status.strip() != '') and (self.order_buy_status != 'FILLED')):                     # Buy Order in Transition
            self.order_buy_status = api_GetOrderStatus('BUY', func_get_account(obj_LineOrderStatus.acct_desc), self)
        if ((self.order_buy_status == 'FILLED') and (self.order_sell_status.strip() != '') and (self.order_sell_status != 'FILLED')):    # Sell Order in Transition
            self.order_sell_status = api_GetOrderStatus('SELL', func_get_account(obj_LineOrderStatus.acct_desc), self)

class cls_ListLineBuySellStatus:
    def __init__(self):  # attributes
        self.List = []

    def initial_load(self, obj_ListLineOrderStatus):
        # add new records
        for obj_LineOrderStatus in obj_ListLineOrderStatus.List:
            if (obj_LineOrderStatus.type.strip() == 'Single'):
                bool_symbol_found = False
                for obj_LineBuySellStatus in self.List:
                    if ((obj_LineOrderStatus.symbol == obj_LineBuySellStatus.symbol) and
                        (obj_LineOrderStatus.period == obj_LineBuySellStatus.period)):
                        bool_symbol_found = True
                if (bool_symbol_found == False):
                    self.List.append(cls_LineBuySellStatus(obj_LineOrderStatus))
        # count repetitions
        for obj_LineBuySellStatus in self.List:
            str_symbol = ''
            for obj_LineBuySellStatus_Nested in self.List:
                if (str_symbol == ''):
                    if (obj_LineBuySellStatus_Nested.repetitions == 0):
                        str_symbol = obj_LineBuySellStatus_Nested.symbol.strip()
                        int_cntr_repetitions = 0
                if (obj_LineBuySellStatus_Nested.symbol.strip() == str_symbol):
                    int_cntr_repetitions = int_cntr_repetitions + 1
            for obj_LineBuySellStatus_Nested in self.List:
                if (obj_LineBuySellStatus_Nested.symbol == str_symbol):
                    obj_LineBuySellStatus_Nested.repetitions = int_cntr_repetitions
        func_display_info(80, 'Both', ['BuySell monitored: '])
        for obj_LineBuySellStatus in self.List:
            func_display_info(80, 'Both', [str(obj_LineBuySellStatus.symbol) + ' ' + str(obj_LineBuySellStatus.period) + ' ' + str(obj_LineBuySellStatus.repetitions)])

    def print(self):
        func_display_info(20, 'Both', ['Symb  Period           Wk Day 4hr 1hr 30m 15m  Status   Buy%  Wk Day 4hr 1hr 30m 15m   Sell%  Status Wk Day 4hr 1hr 30m 15m Rep.T. R.Buy R.Sell'])
        for obj_LineBuySellStatus in self.List:
            obj_LineBuySellStatus.print()

    def update_market_indicators(self, obj_ListLineMarketIndicators):
        for obj_LineMarketIndicators in obj_ListLineMarketIndicators.List:
            for obj_LineBuySellStatus in self.List:
                if (obj_LineMarketIndicators.symbol == obj_LineBuySellStatus.symbol):
                    obj_LineBuySellStatus.update(obj_LineMarketIndicators)

    def update_repetitions(self):
        str_symbol = ''
        for obj_LineBuySellStatus in self.List:
            if (str_symbol == ''):  # Select symbol
                str_symbol = obj_LineBuySellStatus.symbol
            else:
                if (obj_LineBuySellStatus.symbol != str_symbol):
                    str_symbol = obj_LineBuySellStatus.symbol
                else:
                    continue
            int_cntr_buys = 0
            int_cntr_sells = 0
            for obj_LineBuySellStatus_Nested in self.List:
                if (obj_LineBuySellStatus_Nested.symbol == str_symbol):
                    if (obj_LineBuySellStatus_Nested.buy_status.strip() == 'Yes'):
                        int_cntr_buys = int_cntr_buys + 1
                    if (obj_LineBuySellStatus_Nested.sell_status.strip() == 'Yes'):
                        int_cntr_sells = int_cntr_sells + 1
            for obj_LineBuySellStatus_Nested in self.List:
                if (obj_LineBuySellStatus_Nested.symbol == str_symbol):
                    obj_LineBuySellStatus_Nested.repetitions_buy = int_cntr_buys
                    obj_LineBuySellStatus_Nested.repetitions_sell = int_cntr_sells

class cls_ListLineMarketIndicators:
    def __init__(self):  # attributes
        self.List = []

    def initial_load(self, obj_ListLineOrderStatus):  # load symbols
        for obj_LineOrderStatus in obj_ListLineOrderStatus.List:
            bool_symbol_found = False
            for obj_LineMarketIndicators in obj_ListLineMarketIndicators.List:
                if (obj_LineOrderStatus.symbol == obj_LineMarketIndicators.symbol):
                    bool_symbol_found = True
            if (bool_symbol_found == False):
                obj_ListLineMarketIndicators.List.append(cls_LineMarketIndicators(obj_LineOrderStatus.symbol))
        func_display_info(80, 'Both', ['Stocks monitored: '])
        for obj_LineMarketIndicators in obj_ListLineMarketIndicators.List:
            func_display_info(80, 'Both', [str(obj_LineMarketIndicators.symbol)])

    def load(self):
        DateTimeNow_UnixEpoch_TDAFormat = int(round(time.time() * 1000, 0))
        func_display_info(80, 'Both', ['DateTimeNow_UnixEpoch_TDAFormat: ' + str(DateTimeNow_UnixEpoch_TDAFormat)])

        for obj_LineMarketIndicators in self.List:
            obj_LineMarketIndicators.load_from_file(DateTimeNow_UnixEpoch_TDAFormat)
            obj_LineMarketIndicators.load_from_online(DateTimeNow_UnixEpoch_TDAFormat)
            obj_LineMarketIndicators.calc_rsi('week', DateTimeNow_UnixEpoch_TDAFormat)
            obj_LineMarketIndicators.calc_rsi('day', DateTimeNow_UnixEpoch_TDAFormat)
            obj_LineMarketIndicators.calc_rsi('4hr', DateTimeNow_UnixEpoch_TDAFormat)
            obj_LineMarketIndicators.calc_rsi('1hr', DateTimeNow_UnixEpoch_TDAFormat)
            obj_LineMarketIndicators.calc_rsi('30min', DateTimeNow_UnixEpoch_TDAFormat)
            obj_LineMarketIndicators.calc_rsi('15min', DateTimeNow_UnixEpoch_TDAFormat)
            obj_LineMarketIndicators.calc_last_price(api_GetLastPrice(obj_LineMarketIndicators.symbol))

    def print(self):
        func_display_info(20, 'Both', ['Symb     Wk   Day   4hr   1hr   30m   15m    Last'])
        for obj_LineMarketIndicators in self.List:
            func_display_info(20, 'Both', [obj_LineMarketIndicators.print()])

    def save(self):
        for obj_LineMarketIndicators in obj_ListLineMarketIndicators.List:  # Save Stock Prices file before exit
            if (len(obj_LineMarketIndicators.list_prices) > 0):
                obj_LineMarketIndicators.save()

class cls_ListLineOrderStatus:
    def __init__(self):  # attributes
        self.List = []

    def load(self):
        with open(str_path_dir_Config + "\OrderStatus.txt", "r") as fileOrderStatus:
            for int_cntr, str_line in enumerate(fileOrderStatus):
                if int_cntr > 6:  # first seven str_lines are the heather
                    self.List.append(cls_LineOrderStatus('FromFile', str_line))

        func_display_info(50, "Both", ["List of Order Status Loaded:"])
        for obj_LineOrderStatus in self.List:
            func_display_info(50, "Both", [obj_LineOrderStatus.print()])

        self.List = sorted(self.List, key=attrgetter("symbol", "period", "type", "seq"), reverse=False)

        func_display_info(50, "Both", ["List of Order Status Sorted:"])
        for obj_LineOrderStatus in self.List:
            func_display_info(50, "Both", [obj_LineOrderStatus.print()])

        func_display_info(50, "Both", ["Validate Duplicate Records in List of Order Status"])

        lst_seen = []
        lst_dupes = []
        for obj_LineOrderStatus in self.List:
            str_value_check = obj_LineOrderStatus.symbol + " " + obj_LineOrderStatus.period + " " + obj_LineOrderStatus.type + " " + str(obj_LineOrderStatus.seq)
            # print(str_value_check)
            if (str_value_check) not in lst_seen:
                lst_seen.append(str_value_check)
            else:
                lst_dupes.append(str_value_check)
        if (len(lst_dupes) > 0):
            func_display_info(0, "Both", ["-" * 128])
            for obj in lst_dupes:
                func_display_info(0, "Both", [obj])
            func_display_info(0, "Both", ["* * * ERROR * * * Duplicate Records in List of Order Status at LoadOrderStatus"])
            func_display_info(-1, "Both", ["-" * 128])

        func_display_info(50, "Both", ["Validate Skipped-Sequence Records in List of Order Status"])

        str_prior_symb = ""
        str_prior_period = ""
        str_prior_type = ""
        int_prior_seq = 0
        lst_out_of_seq = []
        for obj_LineOrderStatus in self.List:
            if (obj_LineOrderStatus.seq == 1):
                str_prior_symb = obj_LineOrderStatus.symbol
                str_prior_period = obj_LineOrderStatus.period
                str_prior_type = obj_LineOrderStatus.type
                int_prior_seq = obj_LineOrderStatus.seq
            else:
                if ((obj_LineOrderStatus.symbol == str_prior_symb) and (obj_LineOrderStatus.period == str_prior_period) and (obj_LineOrderStatus.type == str_prior_type) and (obj_LineOrderStatus.seq == (int_prior_seq + 1))):
                    int_prior_seq = obj_LineOrderStatus.seq
                else:
                    lst_out_of_seq.append(obj_LineOrderStatus.symbol + " " + obj_LineOrderStatus.period + " " + obj_LineOrderStatus.type + " " + str(obj_LineOrderStatus.seq))
        if (len(lst_out_of_seq) > 0):
            func_display_info(0, "Both", ["-" * 128])
            func_display_info(0, "Both", [str(lst_out_of_seq[0])])
            func_display_info(0, "Both", ["* * * ERROR * * * Out of Sequence Records in List of Order Status at LoadOrderStatus"])
            func_display_info(-1, "Both", ["-" * 128])

    def save(self):
        copyfile(str_path_dir_Config + "\OrderStatusHeader.txt", str_path_dir_Config + "\OrderStatus.txt")
        time.sleep(float_time_delay_io)
        outF = open(str_path_dir_Config + "\OrderStatus.txt", "a")
        for obj_LineOrderStatus in self.List:
            outF.write(obj_LineOrderStatus.print())
            outF.write("\n")
        time.sleep(float_time_delay_io)

def func_calc_rsi(ListValues):
    # ListValues has Oldest record first, len(ListValues) is the number of records to process
    ListGain = []
    ListLoss = []
    ListAvgGain = []
    ListAvgLoss = []
    ListRS = []
    ListRSI = []
    SumGain = 0.0
    SumLoss = 0.0

#   if (len(ListValues) < 15):  #  modified interation limit to allow new stock IPOs, e.g. COIN
    if (len(ListValues) < 15):
        func_display_info(0, 'Both', ['-' * 128])
        func_display_info(0, 'Both', ['* * * ERROR * * * missing historical records to calculate RSI in func_calc_rsi.'])
        func_display_info(-1, 'Both', ['-' * 128])

    # Record Zero is set to 0
    ListGain.append(0.0)
    ListLoss.append(0.0)
    ListAvgGain.append(0.0)
    ListAvgLoss.append(0.0)
    ListRS.append(0.0)
    ListRSI.append(0.0)

    # Calculate Gain and Loss for all records; pointer; record + 1
    for cntr in range(1, len(ListValues)):  # Process from 1 to (len(ListValues) - 1)
        Change = (ListValues[cntr] - ListValues[cntr - 1])
        if (Change > 0):
            ListGain.append(Change)
            ListLoss.append(0.0)
        else:
            ListGain.append(0.0)
            ListLoss.append((Change * (-1)))

    if ((len(ListGain) != len(ListValues)) or (len(ListLoss) != len(ListValues))):
        func_display_info(0, 'Both', ['-' * 128])
        func_display_info(0, 'Both', ['* * * ERROR * * * Number of records use in calculation do NOT match (mark1) in func_calc_rsi: ' + str(len(ListGain)) + ' and ' + str(len(ListLoss)) + ' vs. ' + str(len(ListValues))])
        func_display_info(-1, 'Both', ['-' * 128])

    # Processing records from 1 to 14. Record 0 has initial value of 0. Minimum records required are 15.
    for cntr in range(1, 15):
        SumGain = SumGain + ListGain[cntr]
        SumLoss = SumLoss + ListLoss[cntr]

    # Initialize 13 records [0 to 13].  Pending to fill record 14.
    for cntr in range(1, 14):
        ListAvgGain.append(0.0)
        ListAvgLoss.append(0.0)
        ListRS.append(0.0)
        ListRSI.append(0.0)

    if (len(ListRSI) != 14):
        func_display_info(0, 'Both', ['-' * 128])
        func_display_info(0, 'Both', ['* * * ERROR * * * number of records use in calculation do NOT match (mark2) in func_calc_rsi: ' + str(len(ListGain)) + ' ' + str(len(ListValues))])
        func_display_info(-1, 'Both', ['-' * 128])

    # Filing record 14 [0 to 14].
    ListAvgGain.append(SumGain / 14)
    ListAvgLoss.append(SumLoss / 14)
    # print(str(ListAvgGain) + " " + str(ListAvgLoss))
    # print(str(ListAvgGain[14]) + " " + str(ListAvgLoss[14]))
    if (SumLoss == 0):
        ListRS.append(999999999)
    else:
        ListRS.append(ListAvgGain[14] / ListAvgLoss[14])
    ListRSI.append(100.0 - (100.0 / (1 + ListRS[14])))

    # print('ListRSI[14]: ' + str(ListRSI[14]))

    # Record 14 completed. Processing additional records.
    if (len(ListValues) > 15):
        for cntr in range(15, len(ListValues)):
            # print('cntr: ' + str(cntr))
            ListAvgGain.append(((ListAvgGain[cntr - 1] * 13) + ListGain[cntr]) / 14)
            ListAvgLoss.append(((ListAvgLoss[cntr - 1] * 13) + ListLoss[cntr]) / 14)
            if (ListAvgLoss[cntr] == 0):
                ListRS.append(999999999)
            else:
                ListRS.append(ListAvgGain[cntr] / ListAvgLoss[cntr])
            ListRSI.append(100.0000000000 - (100.0000000000 / (1 + ListRS[cntr])))

    if (len(ListRSI) != len(ListValues)):
        func_display_info(0, 'Both', ['-' * 128])
        func_display_info(0, 'Both', ['* * * ERROR * * * number of records use in calculation do NOT match (mark3) in func_calc_rsi: ' + str(len(ListGain)) + ' ' + str(len(ListValues))])
        func_display_info(-1, 'Both', ['-' * 128])

    # print('ListRSI[max]: ' + str(ListRSI[len(ListValues)-1]))
    func_display_info(50, 'Both', ['Total Records: ' + str(len(ListValues))])

    # print('Chart Values - Begin')
    # for cntr in range(14, TotalRecords):
    #    print(str(ListRSI[cntr]))
    # print('Chart Values - End')

    func_display_info(90, 'Both', [
        '          ListValues             ListGain             ListLoss          ListAvgGain          ListAvgLoss               ListRS              ListRSI'])
    for cntr in range(0, len(ListValues)):
        func_display_info(90, 'Both', [str("{:20.14f}".format(ListValues[cntr])) + ' ' +
                                       str("{:20.14f}".format(ListGain[cntr])) + ' ' +
                                       str("{:20.14f}".format(ListLoss[cntr])) + ' ' +
                                       str("{:20.14f}".format(ListAvgGain[cntr])) + ' ' +
                                       str("{:20.14f}".format(ListAvgLoss[cntr])) + ' ' +
                                       str("{:20.14f}".format(ListRS[cntr])) + ' ' +
                                       str("{:20.14f}".format(ListRSI[cntr]))])
    func_display_info(80, 'Both', ['RSI: ' + str(ListRSI[len(ListValues) - 1])])

    return (ListRSI[len(ListValues) - 1])

def func_check_market_hours():
    global bool_isOpen, dt_preMarket_start, dt_preMarket_end, dt_regularMarket_start, dt_regularMarket_end, dt_postMarket_start, dt_postMarket_end
    global dt_trading_timestamp, bool_preMarket, bool_regularMarket, bool_postMarket

    if (bool_isOpen):  # Market open
        dt_trading_timestamp = datetime.today() + timedelta(minutes=60)  # current NY time
        if ((dt_trading_timestamp >= dt_preMarket_start) and (
                dt_trading_timestamp <= dt_preMarket_end)):  # Check if current NY time is in preMarket
            bool_preMarket = True
        else:
            bool_preMarket = False
        if ((dt_trading_timestamp >= dt_regularMarket_start) and (
                dt_trading_timestamp <= dt_regularMarket_end)):  # Check if current NY time is in regularMarket
            bool_regularMarket = True
        else:
            bool_regularMarket = False
        if ((dt_trading_timestamp >= dt_postMarket_start) and (
                dt_trading_timestamp <= dt_postMarket_end)):  # Check if current NY time is in postMarket
            bool_postMarket = True
        else:
            bool_postMarket = False
    else:  # Market close
        bool_preMarket = False
        bool_regularMarket = False
        bool_postMarket = False
    return ()

def func_check_token():
    global int_token_access_time_limit, int_token_refresh_time_limit, str_token_access, str_token_refresh

    time.sleep(float_time_delay_process)  # Delay given to each API Request call

    str_token_access_datetime_request = io_read_file_Config.get("Access", "str_token_access_datetime_request")
    dt_token_access_datetime_request = datetime.strptime(str_token_access_datetime_request, "%Y%m%d %H:%M:%S")
    func_display_info(50, 'Both', ['str_token_access_datetime_request >>>' + str_token_access_datetime_request + '<<<'])

    str_token_refresh_datetime_request = io_read_file_Config.get("Access", "str_token_refresh_datetime_request")
    dt_token_refresh_datetime_request = datetime.strptime(str_token_refresh_datetime_request, "%Y%m%d %H:%M:%S")
    func_display_info(50, 'Both', ['str_token_refresh_datetime_request >>>' + str_token_refresh_datetime_request + '<<<'])

    str_token_access = io_read_file_Config.get("Access", "str_token_access")
    func_display_info(50, 'Both', ['str_token_access >>>' + str_token_access + '<<<'])

    str_token_refresh = io_read_file_Config.get("Access", "str_token_refresh")
    func_display_info(50, 'Both', ['str_token_refresh >>>' + str_token_refresh + '<<<'])

    # Request str_token_access, if expired; it is good for 30 minutes; 2 minutes is time margin
    if ((dt_token_access_datetime_request + timedelta(minutes=int_token_access_time_limit)) < (datetime.now() + timedelta(minutes=2))):
        api_GetTokenAuthorization('TokenAccess')
        func_display_info(50, 'Both', ['New str_token_access >>>' + str_token_access + '<<<'])

        # Save Token Access information in Trade_Config.ini file
        dt_token_access_datetime_request = datetime.now()
        str_token_access_datetime_request = dt_token_access_datetime_request.strftime("%Y%m%d %H:%M:%S")
        io_read_file_Config.set("Access", "str_token_access_datetime_request", str_token_access_datetime_request)
        io_read_file_Config.set("Access", "str_token_access", str_token_access)
        with open(str_path_dir_Config + "\Trade_Config.ini", 'w') as configfile:
            io_read_file_Config.write(configfile)
        time.sleep(float_time_delay_io)  # Delay given to write file

    # Request str_token_refresh, if expired; it is good for 90 days; 10 days is time margin
    if ((dt_token_refresh_datetime_request + timedelta(minutes=int_token_refresh_time_limit)) < (datetime.now() + timedelta(days=10))):
        api_GetTokenAuthorization('TokenRefresh')
        func_display_info(50, 'Both', ['New str_token_refresh >>>' + str_token_refresh + '<<<'])

        # Save Token Refresh information in Trade_Config.ini file
        dt_token_refresh_datetime_request = datetime.now()
        str_token_refresh_datetime_request = dt_token_refresh_datetime_request.strftime("%Y%m%d %H:%M:%S")
        io_read_file_Config.set("Access", "str_token_refresh_datetime_request", str_token_refresh_datetime_request)
        io_read_file_Config.set("Access", "str_token_refresh", str_token_refresh)
        with open(str_path_dir_Config + "\Trade_Config.ini", 'w') as configfile:
            io_read_file_Config.write(configfile)
        time.sleep(float_time_delay_io * 2)  # Delay given to write file

def func_display_info(int_debug_value, strPrintLocation, ListLine):
    global int_debug, str_valid_ListLineOrderStatus

    if (int_debug >= int_debug_value):  # Print info
        if ((strPrintLocation == 'Screen') or (strPrintLocation == 'Both')):
            for objLine in ListLine:
                print(str(objLine))
        if ((strPrintLocation == 'Log') or (strPrintLocation == 'Both')):
            for objLine in ListLine:
                io_write_file_Log.write(str(objLine))
                io_write_file_Log.write("\n")
        if (int_debug_value == -1):  # 0 Display message; -1 Last message prior to Exit
            if (str_valid_ListLineOrderStatus == 'YesValid'):
                obj_ListLineOrderStatus.save()
            obj_ListLineMarketIndicators.save()
            func_display_info(0, 'Both', ['Ended With Error!'])
            sys.exit(-1)  # Error message

def func_get_account(str_account_desc):
    for tup_account in tup_accounts:
        if tup_account[1] == str_account_desc:
           return(tup_account[0])

if __name__ == "__main__":
    # sys.exit()  # Exit

    # global variables
    #global obj_ListLineOrderStatus, obj_ListLineMarketIndicators, obj_ListLineBuySellStatus, str_valid_ListLineOrderStatus
    obj_ListLineOrderStatus       = cls_ListLineOrderStatus()
    obj_ListLineMarketIndicators  = cls_ListLineMarketIndicators()
    obj_ListLineBuySellStatus     = cls_ListLineBuySellStatus()
    str_valid_ListLineOrderStatus = "NoValid"

    # set path of working directories and files
    str_path_dir_Config = os.getcwd() + "\Config"
    str_path_dir_Data = os.getcwd() + "\Data"

    # setup Log output
    if not (os.path.isfile(str_path_dir_Config + "\Trade_Log.txt")):
        io_write_file_Log = open(str_path_dir_Config + "\Trade_Log.txt", "w")
        io_write_file_Log.write(str_path_dir_Config + "\Trade_Log.txt" + " created on " + str(datetime.today()))
        io_write_file_Log.write("\n")
        io_write_file_Log.close()
    io_write_file_Log = open(str_path_dir_Config + "\Trade_Log.txt", "a")

    # read Trade_Config.ini file to get parameters
    io_read_file_Config = configparser.ConfigParser()
    io_read_file_Config.read(str_path_dir_Config + "\Trade_Config.ini")

    #global int_debug  # 0 no events, 1 high level events, 50 medium level events, 100 small events (all)
    str_debug = io_read_file_Config.get("App Config", "str_debug")
    int_debug = int(str_debug)
    func_display_info(50, "Both", ["str_debug >>>" + str_debug + "<<<"])

    #global float_time_delay_io
    str_time_delay_io = io_read_file_Config.get("App Config", "str_time_delay_io")
    float_time_delay_io = float(str_time_delay_io)
    func_display_info(50, "Both", ["str_time_delay_io >>>" + str_time_delay_io + "<<<"])

    #global float_time_delay_process
    str_time_delay_process = io_read_file_Config.get("App Config", "str_time_delay_process")
    float_time_delay_process = float(str_time_delay_process)
    func_display_info(50, "Both", ["str_time_delay_process >>>" + str_time_delay_process + "<<<"])

    #global int_max_retries
    str_max_retries = io_read_file_Config.get("App Config", "str_max_retries")
    int_max_retries = int(str_max_retries)
    func_display_info(50, "Both", ["str_max_retries >>>" + str_max_retries + "<<<"])

    #global int_token_access_time_limit, str_token_access
    str_token_access_time_limit = io_read_file_Config.get("App Config", "str_token_access_time_limit")
    int_token_access_time_limit = int(str_token_access_time_limit)
    func_display_info(50, "Both", ["str_token_access_time_limit >>>" + str_token_access_time_limit + "<<<"])

    #global int_token_refresh_time_limit, str_token_refresh
    str_token_refresh_time_limit = io_read_file_Config.get("App Config", "str_token_refresh_time_limit")
    int_token_refresh_time_limit = int(str_token_refresh_time_limit)
    func_display_info(50, "Both", ["str_token_refresh_time_limit >>>" + str_token_refresh_time_limit + "<<<"])

    #global str_consumer_key
    str_consumer_key = io_read_file_Config.get("App Config", "str_consumer_key")
    func_display_info(50, "Both", ["str_consumer_key >>>" + str_consumer_key + "<<<"])

    tup_accounts = io_read_file_Config.items("Account Alias")
    del tup_accounts[0]  # delete format field
    func_display_info(50, "Both", tup_accounts)

    str_user_id = io_read_file_Config.get("TD Ameritrade", "str_user_id")
    func_display_info(50, "Both", ["str_user_id >>>" + str_user_id + "<<<"])

    func_display_info(50, "Both", ["Verify Necessary Files Exist. . ."])
    if not (os.path.isfile(str_path_dir_Config + "\Trade_Config.ini")):
        func_display_info(0, "Both", ["-" * 128])
        func_display_info(0, "Both", ["* * * ERROR * * * Missing file Trade_Config.ini!"])
        func_display_info(-1, "Both", ["-" * 128])
    if not (os.path.isfile(str_path_dir_Config + "\OrderStatus.txt")):
        func_display_info(0, "Both", ["-" * 128])
        func_display_info(0, "Both", ["* * * ERROR * * * Missing file OrderStatus.txt!"])
        func_display_info(-1, "Both", ["-" * 128])
    if not (os.path.isfile(str_path_dir_Config + "\OrderStatusHeader.txt")):
        func_display_info(0, "Both", ["-" * 128])
        func_display_info(0, "Both", ["* * * ERROR * * * Missing file OrderStatusHeader.txt!"])
        func_display_info(-1, "Both", ["-" * 128])
    func_display_info(50, 'Both', ['. . . Verify Necessary Files Exist'])

    #global lst_stock_regularMarketOnly_OTC_list  # list of stocks with restrictions to place single limit orders (only allowed during regularMarket)
    lst_stock_regularMarketOnly_OTC = io_read_file_Config.get("TD Ameritrade", "lst_stock_regularMarketOnly_OTC")
    func_display_info(50, "Both", ["lst_stock_regularMarketOnly_OTC >>>" + lst_stock_regularMarketOnly_OTC + "<<<"])
    lst_stock_regularMarketOnly_OTC_list = json.loads(lst_stock_regularMarketOnly_OTC)
    for lst_cntr in lst_stock_regularMarketOnly_OTC_list:
        func_display_info(50, "Both", ["lst_stock_regularMarketOnly_OTC_list >>>" + lst_cntr + "<<<"])

    obj_ListLineOrderStatus.load()
    obj_ListLineMarketIndicators.initial_load(obj_ListLineOrderStatus)
    obj_ListLineBuySellStatus.initial_load(obj_ListLineOrderStatus)
    str_valid_ListLineOrderStatus = 'YesValid'

    #global bool_isOpen, dt_preMarket_start, dt_preMarket_end, dt_regularMarket_start, dt_regularMarket_end, dt_postMarket_start, dt_postMarket_end
    #global dt_trading_timestamp, bool_preMarket, bool_regularMarket, bool_postMarket
    dt_trading_timestamp = datetime.today() + timedelta(minutes=60)
    api_GetMarketHours(dt_trading_timestamp)

    while not (os.path.isfile(str_path_dir_Config + '\Trade_Exit.txt') or (dt_trading_timestamp > dt_trading_timestamp.replace(hour=23, minute=45, second=0, microsecond=0))):  # Main loop * * * Begin of Loop * * *  # If file Exit exists or near to midnight, then Exit loop.

        dt_trading_timestamp = datetime.today() + timedelta(minutes=60)
        func_display_info(20, 'Both', ['dt_trading_timestamp: ' + str(dt_trading_timestamp) + ' str_user_id: ' + str_user_id + ' str_time_delay_process: ' + str_time_delay_process])

        obj_ListLineMarketIndicators.load()
        obj_ListLineMarketIndicators.print()
        obj_ListLineBuySellStatus.update_market_indicators(obj_ListLineMarketIndicators)
        obj_ListLineBuySellStatus.update_repetitions()
        obj_ListLineBuySellStatus.print()

        for obj_LineOrderStatus in obj_ListLineOrderStatus.List:
            func_display_info(40, 'Both', ['Processing Order for: ' + obj_LineOrderStatus.symbol + ' ' + obj_LineOrderStatus.type + ' ' + obj_LineOrderStatus.period + ' ' + str(obj_LineOrderStatus.seq)])
            for obj_LineMarketIndicators in obj_ListLineMarketIndicators.List:
                if  (obj_LineOrderStatus.symbol == obj_LineMarketIndicators.symbol):
                    if (obj_LineOrderStatus.seq == 1):
                        float_prior_order_buy_price = 0.0
                    else:
                        float_prior_order_buy_price = 0.0                                                             # Find Prior Order - with same Order Type - to get Buy Price
                        Trackfloat_prior_order_buy_price = False
                        for obj_LineOrderStatus_float_prior_order_buy_price in reversed(obj_ListLineOrderStatus.List):
                            if ((Trackfloat_prior_order_buy_price) and (float_prior_order_buy_price == 0.0)):
                               if ((obj_LineOrderStatus.symbol   == obj_LineOrderStatus_float_prior_order_buy_price.symbol  ) and  # Orders with same Symbol
                                   (obj_LineOrderStatus.period == obj_LineOrderStatus_float_prior_order_buy_price.period) and  # Orders with same Period
                                   (obj_LineOrderStatus.type   == obj_LineOrderStatus_float_prior_order_buy_price.type   )):   # Order with same Type
                                   if (obj_LineOrderStatus_float_prior_order_buy_price.order_buy_status.strip() != ''):          # Prior Order is active
                                       float_prior_order_buy_price = obj_LineOrderStatus_float_prior_order_buy_price.order_buy_price
                            if (obj_LineOrderStatus_float_prior_order_buy_price == obj_LineOrderStatus):                # Found current Order; start tracking
                               Trackfloat_prior_order_buy_price = True
                    #DisplayInfo(50, 'Both', ['Symbol - Prior Order Buy Price: ' + obj_LineOrderStatus.symbol + ' ' + str(float_prior_order_buy_price)])
                    func_display_info(50, 'Both', ['Symbol - Prior Order Buy Price: ' + obj_LineOrderStatus.symbol + ' ' + obj_LineOrderStatus.period + ' ' + obj_LineOrderStatus.type + ' ' + str(obj_LineOrderStatus.seq) + ' ' + str(float_prior_order_buy_price)])
                    obj_LineOrderStatus.place_order(float_prior_order_buy_price, obj_LineMarketIndicators)
                    obj_LineOrderStatus.update_order_status()
                    obj_LineOrderStatus.reset_order()

    obj_ListLineOrderStatus.save()  # Save Order Status file before exit
    obj_ListLineMarketIndicators.save()
    if (os.path.isfile(str_path_dir_Config + "\Trade_Exit.txt")):
        os.rename(str_path_dir_Config + "\Trade_Exit.txt", str_path_dir_Config + "\Trade_ExitNO.txt")  # Ready to start the process again
    func_display_info(0, 'Both', ['The End'])
    sys.exit()   # Final exit
# "__main__"
# Main_Trade.py
# The End
