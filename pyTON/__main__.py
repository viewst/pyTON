from .client import TonlibClient
from .address_utils import detect_address as _detect_address
from .wallet_utils import wallets as known_wallets, sha256

from aiohttp import web
import base64, argparse, os

import importlib.resources
from tvm_valuetypes.cell import deserialize_cell_from_object
import warnings, traceback

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', '-p', default=8000, type=int)
    parser.add_argument('--getmethods', '-g', default=False, type=bool)
    args = parser.parse_args()
    port = args.port
    routes = web.RouteTableDef()
    default_config = {
        "liteservers": [
          {
            "@type": "liteserver.desc",
            "ip": 1137658550,
            "port": 4924,
            "id": {
              "@type": "pub.ed25519",
              "key": "peJTw/arlRfssgTuf9BMypJzqOi7SXEqSPSWiEw2U1M="
            }
          }
        ],
        "validator": {
          "@type": "validator.config.global",
          "zero_state": {
            "workchain": -1,
            "shard": -9223372036854775808,
            "seqno": 0,
            "root_hash": "F6OpKZKqvqeFp6CQmFomXNMfMj2EnaUSOXN+Mh+wVWk=",
            "file_hash": "XplPz01CXAps5qeSWUtxcyBfdAo5zVb1N979KLSKD24="
          }
        }
      }

    keystore= os.path.expanduser('ton_keystore')
    if not os.path.exists(keystore):
        os.makedirs(keystore)
    tonlib = TonlibClient(default_config, keystore=keystore)

    def detect_address(address):
        try:
            return _detect_address(address)
        except:
            raise web.HTTPRequestRangeNotSatisfiable()

    def wrap_result(func):
      async def wrapper(*args, **kwargs):
        try:
          return web.json_response( { "ok": True, "result": await func(*args, **kwargs) })
        except Exception as e:
          try:
            return web.json_response( { "ok": False, "code": e.status_code,"description": str(e) })
          except:
            warnings.warn("Unknown exception", SyntaxWarning)
            traceback.print_exc()
            return web.json_response( { "ok": False, "description": str(e) })
      return wrapper

    def address_state(account_info):
      if len(account_info.get("code","")) == 0:
        if len(account_info.get("frozen_hash","")) == 0:
          return "uninitialized"
        else:
          return "frozen"
      return "active"

    @routes.get('/')
    async def index(request):
        with importlib.resources.path('pyTON.webserver', 'index.html') as path:
          return web.FileResponse(path)

    @routes.get('/application.js')
    async def index_js(request):
        with importlib.resources.path('pyTON.webserver', 'application.js') as path:
          return web.FileResponse(path)

    @routes.get('/application.css')
    async def index_css(request):
        with importlib.resources.path('pyTON.webserver', 'application.css') as path:
          return web.FileResponse(path)


    @routes.get('/getAddressInformation')
    @wrap_result
    async def getAddressInformation(request):
      address = detect_address(request.query['address'])["bounceable"]["b64"]
      result = await tonlib.raw_get_account_state(address)
      result["state"] = address_state(result)
      if "balance" in result and int(result["balance"])<0:
        result["balance"] = 0
      return result

    @routes.get('/getExtendedAddressInformation')
    @wrap_result
    async def getExtendedAddressInformation(request):
      address = detect_address(request.query['address'])["bounceable"]["b64"]
      result = await tonlib.generic_get_account_state(address)
      return result

    @routes.get('/getWalletInformation')
    @wrap_result
    async def getWalletInformation(request):
      address = detect_address(request.query['address'])["bounceable"]["b64"]
      result = await tonlib.raw_get_account_state(address)
      res = {'wallet':False, 'balance': 0, 'account_state':None, 'wallet_type':None, 'seqno':None}
      res["account_state"] = address_state(result)
      res["balance"] = result["balance"] if (result["balance"] and int(result["balance"])>0) else 0
      if "last_transaction_id" in result:
        res["last_transaction_id"] = result["last_transaction_id"]
      ci = sha256(result["code"])
      if ci in known_wallets:
        res["wallet"] = True
        wallet_handler = known_wallets[ci]
        res["wallet_type"] = wallet_handler["type"]
        wallet_handler["data_extractor"](res, result)
      return res

    @routes.get('/getTransactions')
    @wrap_result
    async def getTransactions(request):
      address = detect_address(request.query['address'])["bounceable"]["b64"]
      limit = int(request.query.get('limit', 1000))
      lt = request.query.get('lt', None)
      lt = lt if not lt else int(lt)
      tx_hash = request.query.get('hash', None)
      to_lt = request.query.get('to_lt', 0)
      to_lt = to_lt if not to_lt else int(to_lt)
      return await tonlib.get_transactions(address, from_transaction_lt = lt, from_transaction_hash = tx_hash, to_transaction_lt = to_lt, limit = limit)

    @routes.get('/getAddressBalance')
    @wrap_result
    async def getAddressBalance(request):
      address = detect_address(request.query['address'])["bounceable"]["b64"]
      result = await tonlib.raw_get_account_state(address)
      if "balance" in result and int(result["balance"])<0:
        result["balance"] = 0
      return result["balance"]

    @routes.get('/getAddressState')
    @wrap_result
    async def getAddress(request):
      address = detect_address(request.query['address'])["bounceable"]["b64"]
      result = await tonlib.raw_get_account_state(address)
      return address_state(result)

    @routes.get('/packAddress')
    @wrap_result
    async def packAddress(request):
      return detect_address(request.query['address'])["bounceable"]["b64"]

    @routes.get('/unpackAddress')
    @wrap_result
    async def unpackAddress(request):
      return detect_address(request.query['address'])["raw_form"]

    @routes.get('/detectAddress')
    @wrap_result
    async def detectAddress(request):
      return detect_address(request.query['address'])

    @routes.post('/sendboc')
    @wrap_result
    async def sendboc(request):
      data = await request.json()
      boc = base64.b64decode(data['boc'])
      return await tonlib.raw_send_message(boc)

    @routes.post('/sendcell')
    @wrap_result
    async def sendcell(request):
      data = await request.json()
      try:
        cell = deserialize_cell_from_object(data['cell'])
        boc = cell.serialize_boc()
      except:
        raise web.HTTPBadRequest("Wrong cell object")
      return await tonlib.raw_send_message(boc)

    @routes.post('/sendquery')
    @wrap_result
    async def sendquery(request):
      data = await request.json()
      address = detect_address(request.query['address'])["bounceable"]["b64"]
      body = codecs.decode(codecs.encode(request.query['body'], "utf-8"), 'base64').replace("\n",'') 
      code = codecs.decode(codecs.encode(request.query.get('init_code', b''), "utf-8"), 'base64').replace("\n",'') 
      data = codecs.decode(codecs.encode(request.query.get('init_data', b''), "utf-8"), 'base64').replace("\n",'')
      return await tonlib.raw_create_and_send_query(address, body, init_code=code, init_data=data)

    @routes.post('/sendquerycell')
    @wrap_result
    async def sendquery(request):
      data = await request.json()
      address = detect_address(request.query['address'])["bounceable"]["b64"]
      try:
        body = serialize_boc(deserialize_cell_from_object(data['body']))
        code, data = b'', b''
        if 'init_code' in data:
          code = serialize_boc(deserialize_cell_from_object(data['init_code']))
        if 'init_data' in data:
          data = serialize_boc(deserialize_cell_from_object(data['init_data']))
      except:
        raise web.HTTPBadRequest("Can't serialize cell object")
      return await tonlib.raw_create_and_send_query(address, body, init_code=code, init_data=data)

    @routes.post('/estimateFee')
    @wrap_result
    async def sendquery(request):
      data = await request.json()
      address = detect_address(request.query['address'])["bounceable"]["b64"]
      body = codecs.decode(codecs.encode(request.query['body'], "utf-8"), 'base64').replace("\n",'') 
      code = codecs.decode(codecs.encode(request.query.get('init_code', b''), "utf-8"), 'base64').replace("\n",'') 
      data = codecs.decode(codecs.encode(request.query.get('init_data', b''), "utf-8"), 'base64').replace("\n",'')
      return await tonlib.raw_estimate_fees(address, body, init_code=code, init_data=data)

    @routes.post('/estimateFeeCell')
    @wrap_result
    async def sendquery(request):
      data = await request.json()
      address = detect_address(request.query['address'])["bounceable"]["b64"]
      try:
        body = serialize_boc(deserialize_cell_from_object(data['body']))
        code, data = b'', b''
        if 'init_code' in data:
          code = serialize_boc(deserialize_cell_from_object(data['init_code']))
        if 'init_data' in data:
          data = serialize_boc(deserialize_cell_from_object(data['init_data']))
      except:
        raise web.HTTPBadRequest("Can't serialize cell object")
      return await tonlib.raw_estimate_fees(address, body, init_code=code, init_data=data)

    if args.getmethods:
        @routes.post('/runGetMethod')
        @wrap_result
        async def getAddress(request):
          data = await request.json()
          address = detect_address(data['address'])["bounceable"]["b64"]
          method = data['method']
          stack = data['stack']
          return await tonlib.raw_run_method(address, method, stack)

    app = web.Application()
    app.add_routes(routes)
    web.run_app(app, port = port)


if __name__ == "__main__":
    main()
