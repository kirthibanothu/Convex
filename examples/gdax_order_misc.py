#!/usr/bin/env python3

from convex.order_adapter.gdax.order_adapter import AccountHandler, OrderHandler, ReportHandler

def accountRequest():
    accountHandler = AccountHandler()
    json_response = accountHandler.get_json()
    for account in json_response:
        if(account['currency'] == 'BTC' or account['currency'] == 'USD'):
            print("Balance: " + account['balance'] + " Curr: " + account['currency'])

    # Example Result:
    #     [{'hold': '0.0000000000000000',
    #       'id': 'c785bb6c-6fd4-4967-b423-8c7d82184bcb',
    #       'balance': '10000.0000000000000000', 'currency': 'USD',
    #       'profile_id': '4febd79a-23e2-4214-91e4-1a750beb8ad7',
    #       'available': '10000.0000000000000000'}
    #      ...
    #      ...
    #      ...]


def simpleBuyOrder():
    order = {
        'size': 1.0,
        'price': 1.0,
        'side': 'buy',
        'product_id': 'BTC-USD',
    }

    orderHandler = OrderHandler()
    print(orderHandler.order_json(order))

def simpleSellOrder():
    order = {
        'size': 1.0,
        'price': 1.0,
        'side': 'sell',
        'product_id': 'BTC-USD',
    }

    orderHandler = OrderHandler()
    print(orderHandler.order_json(order))

def reportRequest():
    reportHandler = ReportHandler()

    fill_report = {
        "type": "fills",
        "start_date": "2014-11-01T00:00:00.000Z",
        "end_date": "2014-11-30T23:59:59.000Z"
    }
    print(reportHandler.get_json(fill_report))

    account_report = {
        "type": "account",
        "start_date": "2014-11-01T00:00:00.000Z",
        "end_date": "2014-11-30T23:59:59.000Z"
    }
    print(reportHandler.get_json(account_report))

def main():
    accountRequest()
    simpleBuyOrder()
    accountRequest()
    simpleSellOrder()
    accountRequest()
    reportRequest()



if __name__ == '__main__':
    main()