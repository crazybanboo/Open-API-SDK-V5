import asyncio
import base64
import datetime
import hmac
import json
import time
import zlib

import requests
import websockets
import os


def get_timestamp():
    now = datetime.datetime.now()
    t = now.isoformat("T", "milliseconds")
    return t + "Z"


def get_server_time():
    url = "https://www.okex.com/api/v5/public/time"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()['data'][0]['ts']
    else:
        return ""


def get_local_timestamp():
    return int(time.time())


def login_params(timestamp, api_key, passphrase, secret_key):
    message = timestamp + 'GET' + '/users/self/verify'

    mac = hmac.new(bytes(secret_key, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
    d = mac.digest()
    sign = base64.b64encode(d)

    login_param = {"op": "login", "args": [{"apiKey": api_key,
                                            "passphrase": passphrase,
                                            "timestamp": timestamp,
                                            "sign": sign.decode("utf-8")}]}
    login_str = json.dumps(login_param)
    return login_str


def partial(res):
    data_obj = res['data'][0]
    bids = data_obj['bids']
    asks = data_obj['asks']
    instrument_id = res['arg']['instId']
    # print('全量数据bids为：' + str(bids))
    # print('档数为：' + str(len(bids)))
    # print('全量数据asks为：' + str(asks))
    # print('档数为：' + str(len(asks)))
    return bids, asks, instrument_id


def update_bids(res, bids_p):
    # 获取增量bids数据
    bids_u = res['data'][0]['bids']
    # print('增量数据bids为：' + str(bids_u))
    # print('档数为：' + str(len(bids_u)))
    # bids合并
    for i in bids_u:
        bid_price = i[0]
        for j in bids_p:
            if bid_price == j[0]:
                if i[1] == '0':
                    bids_p.remove(j)
                    break
                else:
                    del j[1]
                    j.insert(1, i[1])
                    break
        else:
            if i[1] != "0":
                bids_p.append(i)
    else:
        bids_p.sort(key=lambda price: sort_num(price[0]), reverse=True)
        # print('合并后的bids为：' + str(bids_p) + '，档数为：' + str(len(bids_p)))
    return bids_p


def update_asks(res, asks_p):
    # 获取增量asks数据
    asks_u = res['data'][0]['asks']
    # print('增量数据asks为：' + str(asks_u))
    # print('档数为：' + str(len(asks_u)))
    # asks合并
    for i in asks_u:
        ask_price = i[0]
        for j in asks_p:
            if ask_price == j[0]:
                if i[1] == '0':
                    asks_p.remove(j)
                    break
                else:
                    del j[1]
                    j.insert(1, i[1])
                    break
        else:
            if i[1] != "0":
                asks_p.append(i)
    else:
        asks_p.sort(key=lambda price: sort_num(price[0]))
        # print('合并后的asks为：' + str(asks_p) + '，档数为：' + str(len(asks_p)))
    return asks_p


def sort_num(n):
    if n.isdigit():
        return int(n)
    else:
        return float(n)


def check(bids, asks):
    # 获取bid档str
    bids_l = []
    bid_l = []
    count_bid = 1
    while count_bid <= 25:
        if count_bid > len(bids):
            break
        bids_l.append(bids[count_bid - 1])
        count_bid += 1
    for j in bids_l:
        str_bid = ':'.join(j[0: 2])
        bid_l.append(str_bid)
    # 获取ask档str
    asks_l = []
    ask_l = []
    count_ask = 1
    while count_ask <= 25:
        if count_ask > len(asks):
            break
        asks_l.append(asks[count_ask - 1])
        count_ask += 1
    for k in asks_l:
        str_ask = ':'.join(k[0: 2])
        ask_l.append(str_ask)
    # 拼接str
    num = ''
    if len(bid_l) == len(ask_l):
        for m in range(len(bid_l)):
            num += bid_l[m] + ':' + ask_l[m] + ':'
    elif len(bid_l) > len(ask_l):
        # bid档比ask档多
        for n in range(len(ask_l)):
            num += bid_l[n] + ':' + ask_l[n] + ':'
        for l in range(len(ask_l), len(bid_l)):
            num += bid_l[l] + ':'
    elif len(bid_l) < len(ask_l):
        # ask档比bid档多
        for n in range(len(bid_l)):
            num += bid_l[n] + ':' + ask_l[n] + ':'
        for l in range(len(bid_l), len(ask_l)):
            num += ask_l[l] + ':'

    new_num = num[:-1]
    int_checksum = zlib.crc32(new_num.encode())
    fina = change(int_checksum)
    return fina


def change(num_old):
    num = pow(2, 31) - 1
    if num_old > num:
        out = num_old - num * 2 - 2
    else:
        out = num_old
    return out

def file_size(file:str)->int:
    return os.stat(file).st_size

class file_manager():
    def __init__(self, channels:list) -> None:
        self.channels:list = channels
        self.base_dir:str = '../../database/market_crawling'
        self.count_dict:dict = {} #用于指示当前标的的存储文件从多少开始

        if not os.path.exists(self.base_dir):
            os.mkdir(self.base_dir)

        for root,dirs,files in os.walk(self.base_dir):
            for c in self.channels:
                inst_id = c['instId']
                if root.endswith(inst_id):
                    count = 0
                    for f in files:
                        l = list(filter(str.isdigit, f))
                        n = int(''.join(l)) #获取到文件的序列号
                        count = n if n > count else count
                    self.count_dict[inst_id] = count
            
    def save_json(self, dic:dict, save_string:str):
        for c in self.channels:
            channel:str = c['channel']
            inst_id:str = c['instId']
            if dic['data'][0]['instId'] == inst_id:
                inst_dir = os.path.join(self.base_dir, inst_id)
                if not os.path.exists(inst_dir): # 如果没有该标的的文件夹，则创建一个
                    os.mkdir(inst_dir)

                # 判断数据库里是否已经有该文件，如果有，就追加，没有就从0开始
                # ../../database/market_crawling/DOT-USDT-SWAP/DOT-USDT-SWAP-0.json
                file = ''
                if inst_id in self.count_dict:
                    file = f'{inst_dir}/{inst_id}-{self.count_dict[inst_id]}.json'
                    # print(f'file:{file}')
                    if file_size(file) > 50*1024*1024:
                        self.count_dict[inst_id] = self.count_dict[inst_id] + 1
                        file = f'{inst_dir}/{inst_id}-{self.count_dict[inst_id]}.json' # 更新文件名
                else:
                    self.count_dict[inst_id] = 0
                    file = f'{inst_dir}/{inst_id}-{self.count_dict[inst_id]}.json'
                    
                with open(file, 'a') as f:
                    f.write(save_string+'\n')
                break


# subscribe channels un_need login
async def subscribe_without_login(url, channels):
    l = []
    fm = file_manager(channels)
    while True:
        try:
            async with websockets.connect(url) as ws:
                sub_param = {"op": "subscribe", "args": channels}
                sub_str = json.dumps(sub_param)
                await ws.send(sub_str)
                print(f"send: {sub_str}")

                while True:
                    try:
                        res = await asyncio.wait_for(ws.recv(), timeout=25)
                    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed) as e:
                        try:
                            await ws.send('ping')
                            res = await ws.recv()
                            print(res)
                            continue
                        except Exception as e:
                            print("连接关闭，正在重连……")
                            break

                    res = eval(res)
                    if 'event' in res:
                        continue

                    for i in res['arg']:
                        if 'books' in res['arg'][i] and 'books5' not in res['arg'][i]:
                            # 订阅频道是深度频道
                            if res['action'] == 'snapshot':
                                for m in l:
                                    if res['arg']['instId'] == m['instrument_id']:
                                        l.remove(m)
                                # 获取首次全量深度数据
                                bids_p, asks_p, instrument_id = partial(res)
                                d = {}
                                d['instrument_id'] = instrument_id
                                d['bids_p'] = bids_p
                                d['asks_p'] = asks_p
                                l.append(d)

                                # 校验checksum
                                checksum = res['data'][0]['checksum']
                                # print('推送数据的checksum为：' + str(checksum))
                                check_num = check(bids_p, asks_p)
                                # print('校验后的checksum为：' + str(check_num))
                                if check_num == checksum:
                                    print("校验结果为：True")
                                else:
                                    print("校验结果为：False，正在重新订阅……")

                                    # 取消订阅
                                    await unsubscribe_without_login(url, channels)
                                    # 发送订阅
                                    async with websockets.connect(url) as ws:
                                        sub_param = {"op": "subscribe", "args": channels}
                                        sub_str = json.dumps(sub_param)
                                        await ws.send(sub_str)
                                        print(f"send: {sub_str}")

                            elif res['action'] == 'update':
                                for j in l:
                                    if res['arg']['instId'] == j['instrument_id']:
                                        # 获取全量数据
                                        bids_p = j['bids_p']
                                        asks_p = j['asks_p']
                                        # 获取合并后数据
                                        bids_p = update_bids(res, bids_p)
                                        asks_p = update_asks(res, asks_p)

                                        # 校验checksum
                                        checksum = res['data'][0]['checksum']
                                        # print('推送数据的checksum为：' + str(checksum))
                                        check_num = check(bids_p, asks_p)
                                        # print('校验后的checksum为：' + str(check_num))
                                        if check_num == checksum:
                                            print("校验结果为：True")
                                        else:
                                            print("校验结果为：False，正在重新订阅……")

                                            # 取消订阅
                                            await unsubscribe_without_login(url, channels)
                                            # 发送订阅
                                            async with websockets.connect(url) as ws:
                                                sub_param = {"op": "subscribe", "args": channels}
                                                sub_str = json.dumps(sub_param)
                                                await ws.send(sub_str)
                                                print(f"send: {sub_str}")

                    # 保存数据
                    try:
                        del res['arg'] #节省空间
                        fm.save_json(res, json.dumps(res))
                    except Exception as e:
                        print(f'e:{e}')
                    
        except Exception as e:
            print("连接断开，正在重连……")
            continue


# subscribe channels need login
async def subscribe(url, api_key, passphrase, secret_key, channels):
    while True:
        try:
            async with websockets.connect(url) as ws:
                # login
                timestamp = str(get_local_timestamp())
                login_str = login_params(timestamp, api_key, passphrase, secret_key)
                await ws.send(login_str)
                # print(f"send: {login_str}")
                res = await ws.recv()
                print(res)

                # subscribe
                sub_param = {"op": "subscribe", "args": channels}
                sub_str = json.dumps(sub_param)
                await ws.send(sub_str)
                print(f"send: {sub_str}")

                while True:
                    try:
                        res = await asyncio.wait_for(ws.recv(), timeout=25)
                    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed) as e:
                        try:
                            await ws.send('ping')
                            res = await ws.recv()
                            print(res)
                            continue
                        except Exception as e:
                            print("连接关闭，正在重连……")
                            break

                    print(get_timestamp() + res)

        except Exception as e:
            print("连接断开，正在重连……")
            continue


# trade
async def trade(url, api_key, passphrase, secret_key, trade_param):
    while True:
        try:
            async with websockets.connect(url) as ws:
                # login
                timestamp = str(get_local_timestamp())
                login_str = login_params(timestamp, api_key, passphrase, secret_key)
                await ws.send(login_str)
                # print(f"send: {login_str}")
                res = await ws.recv()
                print(res)

                # trade
                sub_str = json.dumps(trade_param)
                await ws.send(sub_str)
                print(f"send: {sub_str}")

                while True:
                    try:
                        res = await asyncio.wait_for(ws.recv(), timeout=25)
                    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed) as e:
                        try:
                            await ws.send('ping')
                            res = await ws.recv()
                            print(res)
                            continue
                        except Exception as e:
                            print("连接关闭，正在重连……")
                            break

                    print(get_timestamp() + res)

        except Exception as e:
            print("连接断开，正在重连……")
            continue


# unsubscribe channels
async def unsubscribe(url, api_key, passphrase, secret_key, channels):
    async with websockets.connect(url) as ws:
        # login
        timestamp = str(get_local_timestamp())
        login_str = login_params(timestamp, api_key, passphrase, secret_key)
        await ws.send(login_str)
        # print(f"send: {login_str}")

        res = await ws.recv()
        print(f"recv: {res}")

        # unsubscribe
        sub_param = {"op": "unsubscribe", "args": channels}
        sub_str = json.dumps(sub_param)
        await ws.send(sub_str)
        print(f"send: {sub_str}")

        res = await ws.recv()
        print(f"recv: {res}")


# unsubscribe channels
async def unsubscribe_without_login(url, channels):
    async with websockets.connect(url) as ws:
        # unsubscribe
        sub_param = {"op": "unsubscribe", "args": channels}
        sub_str = json.dumps(sub_param)
        await ws.send(sub_str)
        print(f"send: {sub_str}")

        res = await ws.recv()
        print(f"recv: {res}")


api_key = ""
secret_key = ""
passphrase = ""

# WebSocket公共频道 public channels
# 实盘 real trading
url = "wss://ws.okex.com:8443/ws/v5/public"
# 模拟盘 demo trading
# url = "wss://ws.okex.com:8443/ws/v5/public?brokerId=9999"

# WebSocket私有频道 private channels
# 实盘 real trading
# url = "wss://ws.okex.com:8443/ws/v5/private"
# 模拟盘 demo trading
# url = "wss://ws.okex.com:8443/ws/v5/private?brokerId=9999"

'''
公共频道 public channel
:param channel: 频道名
:param instType: 产品类型
:param instId: 产品ID
:param uly: 合约标的指数

'''

# 产品频道  Instruments Channel
# channels = [{"channel": "instruments", "instType": "SWAP"}]
# 行情频道 tickers channel
# channels = [{"channel": "tickers", "instId": "BTC-USD-210326"}]
# channels = [{"channel": "tickers", "instId": "DOT-USDT-SWAP"}, 
#             {"channel": "tickers", "instId": "SLP-USDT-SWAP"}]
# 持仓总量频道 Open interest Channel
# channels = [{"channel": "open-interest", "instId": "BTC-USD-210326"}]
# K线频道 Candlesticks Channel
# channels = [{"channel": "candle1m", "instId": "BTC-USD-210326"}]
# 交易频道 Trades Channel
# channels = [{"channel": "trades", "instId": "BTC-USD-201225"}]
# 预估交割/行权价格频道 Estimated delivery/exercise Price Channel
# channels = [{"channel": "estimated-price", "instType": "FUTURES", "uly": "BTC-USD"}]
# 标记价格频道 Mark Price Channel
# channels = [{"channel": "mark-price", "instId": "BTC-USDT-210326"}]
# 标记价格K线频道 Mark Price Candlesticks Channel0
# channels = [{"channel": "mark-price-candle1D", "instId": "BTC-USD-201225"}]
# 限价频道 Price Limit Channel
# channels = [{"channel": "price-limit", "instId": "BTC-USD-201225"}]
# 深度频道 Order Book Channel
# channels = [{"channel": "books", "instId": "BTC-USD-SWAP"}]
# 期权定价频道 OPTION Summary Channel
# channels = [{"channel": "opt-summary", "uly": "BTC-USD"}]
# 资金费率频道 Funding Rate Channel
# channels = [{"channel": "funding-rate", "instId": "BTC-USD-SWAP"}]
# 指数K线频道 Index Candlesticks Channel
# channels = [{"channel": "index-candle1m", "instId": "BTC-USDT"}]
# 指数行情频道 Index Tickers Channel
# channels = [{"channel": "index-tickers", "instId": "BTC-USDT"}]
# status频道 Status Channel
# channels = [{"channel": "status"}]

'''
私有频道 private channel
:param channel: 频道名
:param ccy: 币种
:param instType: 产品类型
:param uly: 合约标的指数
:param instId: 产品ID

'''

# 账户频道 Account Channel
# channels = [{"channel": "account", "ccy": "BTC"}]
# 持仓频道 Positions Channel
# channels = [{"channel": "positions", "instType": "FUTURES", "uly": "BTC-USDT", "instId": "BTC-USDT-210326"}]
# 余额和持仓频道 Balance and Position Channel
# channels = [{"channel": "balance_and_position"}]
# 订单频道 Order Channel
# channels = [{"channel": "orders", "instType": "FUTURES", "uly": "BTC-USD", "instId": "BTC-USD-201225"}]
# 策略委托订单频道 Algo Orders Channel
# channels = [{"channel": "orders-algo", "instType": "FUTURES", "uly": "BTC-USD", "instId": "BTC-USD-201225"}]
#高级策略委托订单频道 Cancel Advance Algos
# channels = [{"channel": "algo-advance", "instType": "SPOT","instId": "BTC-USD-201225","algoId":"12345678"}]

'''
交易 trade
'''

# 下单 Place Order
# trade_param = {"id": "1512", "op": "order", "args": [{"side": "buy", "instId": "BTC-USDT", "tdMode": "isolated", "ordType": "limit", "px": "19777", "sz": "1"}]}
# 批量下单 Place Multiple Orders
# trade_param = {"id": "1512", "op": "batch-orders", "args": [
#         {"side": "buy", "instId": "BTC-USDT", "tdMode": "isolated", "ordType": "limit", "px": "19666", "sz": "1"},
#         {"side": "buy", "instId": "BTC-USDT", "tdMode": "isolated", "ordType": "limit", "px": "19633", "sz": "1"}
#     ]}
# 撤单 Cancel Order
# trade_param = {"id": "1512", "op": "cancel-order", "args": [{"instId": "BTC-USDT", "ordId": "259424589042823169"}]}
# 批量撤单 Cancel Multiple Orders
# trade_param = {"id": "1512", "op": "batch-cancel-orders", "args": [
#         {"instId": "BTC-USDT", "ordId": "259432098826694656"},
#         {"instId": "BTC-USDT", "ordId": "259432098826694658"}
#     ]}
# 改单 Amend Order
# trade_param = {"id": "1512", "op": "amend-order", "args": [{"instId": "BTC-USDT", "ordId": "259432767558135808", "newSz": "2"}]}
# 批量改单 Amend Multiple Orders
# trade_param = {"id": "1512", "op": "batch-amend-orders", "args": [
#         {"instId": "BTC-USDT", "ordId": "259435442492289024", "newSz": "2"},
#         {"instId": "BTC-USDT", "ordId": "259435442496483328", "newSz": "3"}
#     ]}


loop = asyncio.get_event_loop()

channels = [
    {"channel": "tickers", "instId": "ETC-USDT-SWAP"},
    {"channel": "tickers", "instId": "CRV-USDT-SWAP"},
    {"channel": "tickers", "instId": "SUSHI-USDT-SWAP"},
    {"channel": "tickers", "instId": "XLM-USDT-SWAP"},
    {"channel": "tickers", "instId": "DASH-USDT-SWAP"},
    {"channel": "tickers", "instId": "MATIC-USDT-SWAP"},
    {"channel": "tickers", "instId": "THETA-USDT-SWAP"},
    {"channel": "tickers", "instId": "CRO-USDT-SWAP"},
    {"channel": "tickers", "instId": "UNI-USDT-SWAP"},
    {"channel": "tickers", "instId": "LTC-USDT-SWAP"},
    {"channel": "tickers", "instId": "WAVES-USDT-SWAP"},
    {"channel": "tickers", "instId": "STORJ-USDT-SWAP"},
    {"channel": "tickers", "instId": "ENJ-USDT-SWAP"},
    {"channel": "tickers", "instId": "IOST-USDT-SWAP"},
    {"channel": "tickers", "instId": "BTC-USDT-SWAP"},
    {"channel": "tickers", "instId": "LON-USDT-SWAP"},
    {"channel": "tickers", "instId": "NEO-USDT-SWAP"},
    {"channel": "tickers", "instId": "SNX-USDT-SWAP"},
    {"channel": "tickers", "instId": "AVAX-USDT-SWAP"},
    {"channel": "tickers", "instId": "LPT-USDT-SWAP"},
    {"channel": "tickers", "instId": "BZZ-USDT-SWAP"},
    {"channel": "tickers", "instId": "SC-USDT-SWAP"},
    {"channel": "tickers", "instId": "RSR-USDT-SWAP"},
    {"channel": "tickers", "instId": "KNC-USDT-SWAP"},
    {"channel": "tickers", "instId": "LINK-USDT-SWAP"},
    {"channel": "tickers", "instId": "DOGE-USDT-SWAP"},
    {"channel": "tickers", "instId": "DORA-USDT-SWAP"},
    {"channel": "tickers", "instId": "COMP-USDT-SWAP"},
    {"channel": "tickers", "instId": "WNXM-USDT-SWAP"},
    {"channel": "tickers", "instId": "PERP-USDT-SWAP"},
    {"channel": "tickers", "instId": "MKR-USDT-SWAP"},
    {"channel": "tickers", "instId": "BADGER-USDT-SWAP"},
    {"channel": "tickers", "instId": "GRT-USDT-SWAP"},
    {"channel": "tickers", "instId": "FIL-USDT-SWAP"},
    {"channel": "tickers", "instId": "LAT-USDT-SWAP"},
    {"channel": "tickers", "instId": "ETH-USDT-SWAP"},
    {"channel": "tickers", "instId": "SHIB-USDT-SWAP"},
    {"channel": "tickers", "instId": "FLM-USDT-SWAP"},
    {"channel": "tickers", "instId": "EFI-USDT-SWAP"},
    {"channel": "tickers", "instId": "MINA-USDT-SWAP"},
    {"channel": "tickers", "instId": "BTT-USDT-SWAP"},
    {"channel": "tickers", "instId": "BSV-USDT-SWAP"},
    {"channel": "tickers", "instId": "XTZ-USDT-SWAP"},
    {"channel": "tickers", "instId": "EOS-USDT-SWAP"},
    {"channel": "tickers", "instId": "CVC-USDT-SWAP"},
    {"channel": "tickers", "instId": "LRC-USDT-SWAP"},
    {"channel": "tickers", "instId": "DYDX-USDT-SWAP"},
    {"channel": "tickers", "instId": "MIR-USDT-SWAP"},
    {"channel": "tickers", "instId": "SLP-USDT-SWAP"},
    {"channel": "tickers", "instId": "TORN-USDT-SWAP"},
    {"channel": "tickers", "instId": "CHZ-USDT-SWAP"},
    {"channel": "tickers", "instId": "JST-USDT-SWAP"},
    {"channel": "tickers", "instId": "BCH-USDT-SWAP"},
    {"channel": "tickers", "instId": "WNCG-USDT-SWAP"},
    {"channel": "tickers", "instId": "ATOM-USDT-SWAP"},
    {"channel": "tickers", "instId": "YGG-USDT-SWAP"},
    {"channel": "tickers", "instId": "AAVE-USDT-SWAP"},
    {"channel": "tickers", "instId": "SWRV-USDT-SWAP"},
    {"channel": "tickers", "instId": "EGLD-USDT-SWAP"},
    {"channel": "tickers", "instId": "AGLD-USDT-SWAP"},
    {"channel": "tickers", "instId": "ONT-USDT-SWAP"},
    {"channel": "tickers", "instId": "ALGO-USDT-SWAP"},
    {"channel": "tickers", "instId": "ADA-USDT-SWAP"},
    {"channel": "tickers", "instId": "GALA-USDT-SWAP"},
    {"channel": "tickers", "instId": "LUNA-USDT-SWAP"},
    {"channel": "tickers", "instId": "SAND-USDT-SWAP"},
    {"channel": "tickers", "instId": "TRX-USDT-SWAP"},
    {"channel": "tickers", "instId": "CELO-USDT-SWAP"},
    {"channel": "tickers", "instId": "OMG-USDT-SWAP"},
    {"channel": "tickers", "instId": "MANA-USDT-SWAP"},
    {"channel": "tickers", "instId": "CQT-USDT-SWAP"},
    {"channel": "tickers", "instId": "ICP-USDT-SWAP"},
    {"channel": "tickers", "instId": "BAND-USDT-SWAP"},
    {"channel": "tickers", "instId": "ZEC-USDT-SWAP"},
    {"channel": "tickers", "instId": "ZRX-USDT-SWAP"},
    {"channel": "tickers", "instId": "QTUM-USDT-SWAP"},
    {"channel": "tickers", "instId": "CSPR-USDT-SWAP"},
    {"channel": "tickers", "instId": "YFI-USDT-SWAP"},
    {"channel": "tickers", "instId": "XEM-USDT-SWAP"},
    {"channel": "tickers", "instId": "SOL-USDT-SWAP"},
    {"channel": "tickers", "instId": "DOT-USDT-SWAP"},
    {"channel": "tickers", "instId": "ALPHA-USDT-SWAP"},
    {"channel": "tickers", "instId": "BAT-USDT-SWAP"},
    {"channel": "tickers", "instId": "CONV-USDT-SWAP"},
    {"channel": "tickers", "instId": "REN-USDT-SWAP"},
    {"channel": "tickers", "instId": "IOTA-USDT-SWAP"},
    {"channel": "tickers", "instId": "TRB-USDT-SWAP"},
    {"channel": "tickers", "instId": "RVN-USDT-SWAP"},
    {"channel": "tickers", "instId": "XCH-USDT-SWAP"},
    {"channel": "tickers", "instId": "BTM-USDT-SWAP"},
    {"channel": "tickers", "instId": "ZIL-USDT-SWAP"},
    {"channel": "tickers", "instId": "KSM-USDT-SWAP"},
    {"channel": "tickers", "instId": "YFII-USDT-SWAP"},
    {"channel": "tickers", "instId": "CFX-USDT-SWAP"},
    {"channel": "tickers", "instId": "MASK-USDT-SWAP"},
    {"channel": "tickers", "instId": "UMA-USDT-SWAP"},
    {"channel": "tickers", "instId": "ZEN-USDT-SWAP"},
    {"channel": "tickers", "instId": "NEAR-USDT-SWAP"},
    {"channel": "tickers", "instId": "FTM-USDT-SWAP"},
    {"channel": "tickers", "instId": "XRP-USDT-SWAP"},
    {"channel": "tickers", "instId": "BNT-USDT-SWAP"},
    {"channel": "tickers", "instId": "ANC-USDT-SWAP"},
    {"channel": "tickers", "instId": "BAL-USDT-SWAP"},
    {"channel": "tickers", "instId": "SRM-USDT-SWAP"},
    {"channel": "tickers", "instId": "ANT-USDT-SWAP"},
    {"channel": "tickers", "instId": "AXS-USDT-SWAP"},
    {"channel": "tickers", "instId": "XMR-USDT-SWAP"}
]

# 公共频道 不需要登录（行情，持仓总量，K线，标记价格，深度，资金费率等）subscribe public channel
loop.run_until_complete(subscribe_without_login(url, channels))

# 私有频道 需要登录（账户，持仓，订单等）subscribe private channel
# loop.run_until_complete(subscribe(url, api_key, passphrase, secret_key, channels))

# 交易（下单，撤单，改单等）trade
# loop.run_until_complete(trade(url, api_key, passphrase, secret_key, trade_param))

loop.close()
