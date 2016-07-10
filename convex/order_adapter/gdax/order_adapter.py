#!/usr/bin/env python3

# For API Keys
from .config import *

import asyncio
import websockets

# For GDAX Authentication
import time, hmac, hashlib, base64, requests
from requests.auth import AuthBase

class GdaxAuthentication(AuthBase):
    def __init__(self, api_key, secret_key, passphrase):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase

    def __call__(self, request):
        timestamp = str(time.time())
        message = timestamp + request.method + request.path_url + (request.body or '')
        message = message.encode('utf-8')
        hmac_key = base64.b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message, hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest())

        request.headers.update({
            'CB-ACCESS-SIGN': signature_b64,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'CB-ACCESS-KEY': self.api_key,
            'CB-ACCESS-PASSPHRASE': self.passphrase,
        })
        return request

class AccountHandler():
    URL_PATH = 'accounts'
    FULL_PATH = API_URL + URL_PATH
    def __init__(self):
       self.auth = GdaxAuthentication(API_KEY, API_SECRET, API_PASS)

    def get(self):
        return requests.get(self.FULL_PATH, auth=self.auth)

    def get_json(self):
        return self.get().json()

class OrderHandler():
    URL_PATH = 'orders'
    FULL_PATH = API_URL + URL_PATH
    def __init__(self):
        self.auth = GdaxAuthentication(API_KEY, API_SECRET, API_PASS)

    def order(self, order):
        # ToDo: Add risk checks to verify order here
        return requests.post(self.FULL_PATH, json=order, auth=self.auth)

    def order_json(self, order):
        return self.order(order).json()

class ReportHandler():
    URL_PATH = 'reports'
    FULL_PATH = API_URL + URL_PATH
    def __init__(self):
        self.auth = GdaxAuthentication(API_KEY, API_SECRET, API_PASS)

    def get(self, report):
        # ToDo: Add risk checks to verify order here
        return requests.post(self.FULL_PATH, json=report, auth=self.auth)

    def get_json(self, report):
        return self.get(report).json()