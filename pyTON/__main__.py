from .client import TonlibClient
from .address_utils import detect_address as _detect_address


from aiohttp import web
import base64, argparse, os

import importlib.resources
from tvm_valuetypes.cell import deserialize_cell_from_object


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
          return web.json_response( { "ok": False, "code": e.status_code,"description": str(e) })
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
