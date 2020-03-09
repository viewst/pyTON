# -*- coding: utf-8 -*-
import asyncio
import codecs
import struct
import socket
from concurrent.futures import ThreadPoolExecutor
import threading
from datetime import datetime, timezone

import json
from .tonlibjson import TonWrapper
from .address_utils import prepare_address
from tvm_valuetypes import serialize_tvm_stack, render_tvm_stack
import functools

def parallelize(f):
    @functools.wraps(f)
    def wrapper(self, *args, **kwds):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(self._executor, functools.partial(f, self, *args, **kwds))
    return wrapper


def b64str_str(b64str):
  b64bytes = codecs.encode(b64str, "utf8")
  _bytes = codecs.decode(b64bytes, "base64")
  return codecs.decode(_bytes, "utf8")
  
def b64str_hex(b64str):
  b64bytes = codecs.encode(b64str, "utf8")
  _bytes = codecs.decode(b64bytes, "base64")
  _hex = codecs.encode(_bytes, "hex")
  return codecs.decode(_hex, "utf8")

def h2b64(x):
 return codecs.encode(codecs.decode(x, 'hex'), 'base64').decode().replace("\n", "")


class TonlibClient:
    _t_local = threading.local()
    _style = 'Choose asyncio or concurrent.futures style'

    def __init__(
            self,
            config,
            keystore,
            threads=10
    ):
        self._executor = ThreadPoolExecutor(
            max_workers = threads,
            initializer = self.init_tonlib_thread,
            initargs = (config, keystore)
        )

    def reload_tonlib(self):
      self.init_tonlib_thread(self.config, self.keystore)

    def init_tonlib_thread(self, config, keystore):
        """
        TL Spec
            init options:options = options.Info;
            options config:config keystore_type:KeyStoreType = Options;

            keyStoreTypeDirectory directory:string = KeyStoreType;
            config config:string blockchain_name:string use_callbacks_for_network:Bool ignore_cache:Bool = Config;

        :param ip: IPv4 address in dotted notation or signed int32
        :param port: IPv4 TCP port
        :param key: base64 pub key of liteserver node
        :return: None
        """
        (self.config, self.keystore) = config, keystore
        self._t_local.loaded_contracts_num = 0
        self._t_local.tonlib_wrapper = TonWrapper()
        liteservers = config["liteservers"]
        fixed_ip_liteservers = []
        for ls in liteservers:
          ip = ls["ip"]
          if isinstance(ip, str):
            num_ip = struct.unpack('!I', socket.inet_aton(ip))[0]
            if num_ip> 2**31:
              num_ip -= 2**32
            ls["ip"] = num_ip
          fixed_ip_liteservers.append(ls)
        config["liteservers"] = fixed_ip_liteservers
        config_obj = config

        keystore_obj = {
                '@type': 'keyStoreTypeDirectory',
                'directory': keystore
            }
        

        data = {
            '@type': 'init',
            'options': {
                '@type': 'options',
                'config': {
                    '@type': 'config',
                    'config': json.dumps(config_obj),
                    'use_callbacks_for_network': False,
                    'blockchain_name':'',
                    'ignore_cache': False
                },
                'keystore_type': keystore_obj
            }
        }

        self._t_local.tonlib_wrapper.ton_exec(data)
        self.set_verbosity_level(0)

    def set_verbosity_level(self, level):
        data = {
            '@type': 'setLogVerbosityLevel',
            'new_verbosity_level': level
            }
        r = self._t_local.tonlib_wrapper.ton_exec(data)
        return r

    def _raw_get_transactions(self, account_address: str, from_transaction_lt: str, from_transaction_hash: str):
        """
        TL Spec:
            raw.getTransactions account_address:accountAddress from_transaction_id:internal.transactionId = raw.Transactions;
            accountAddress account_address:string = AccountAddress;
            internal.transactionId lt:int64 hash:bytes = internal.TransactionId;
        :param account_address: str with raw or user friendly address
        :param from_transaction_lt: from transaction lt
        :param from_transaction_hash: from transaction hash in HEX representation
        :return: dict as
            {
                '@type': 'raw.transactions',
                'transactions': list[dict as {
                    '@type': 'raw.transaction',
                    'utime': int,
                    'data': str,
                    'transaction_id': internal.transactionId,
                    'fee': str,
                    'in_msg': dict as {
                        '@type': 'raw.message',
                        'source': str,
                        'destination': str,
                        'value': str,
                        'message': str
                    },
                    'out_msgs': list[dict as raw.message]
                }],
                'previous_transaction_id': internal.transactionId
            }
        """
        account_address = prepare_address(account_address)
        from_transaction_hash = h2b64(from_transaction_hash)

        data = {
            '@type': 'raw.getTransactions',
            'account_address': {
              'account_address': account_address,
            },
            'from_transaction_id': {
                '@type': 'internal.transactionId',
                'lt': from_transaction_lt,
                'hash': from_transaction_hash
            }
        }
        r = self._t_local.tonlib_wrapper.ton_exec(data)
        return r

    @parallelize
    def raw_get_transactions(self, account_address: str, from_transaction_lt: str, from_transaction_hash: str):
      return self._raw_get_transactions(account_address, from_transaction_lt, from_transaction_hash)

    @parallelize
    def get_transactions(self, account_address, from_transaction_lt=None, from_transaction_hash=None,
                                                to_transaction_lt=0, limit = 1000):
      """
       Return all transactions between from_transaction_lt and to_transaction_lt
       if to_transaction_lt and to_transaction_hash are not defined returns all transactions
       if from_transaction_lt and from_transaction_hash are not defined checks last
      """
      if (from_transaction_lt==None) or (from_transaction_hash==None):
        addr = self._raw_get_account_state(account_address)
        try:
          from_transaction_lt, from_transaction_hash = int(addr["last_transaction_id"]["lt"]), b64str_hex(addr["last_transaction_id"]["hash"])
        except KeyError:
          return []
      reach_lt = False
      all_transactions = []
      current_lt, curret_hash = from_transaction_lt, from_transaction_hash
      while (not reach_lt) and (len(all_transactions)<limit):
        raw_transactions = self._raw_get_transactions(account_address, current_lt, curret_hash)
        if(raw_transactions['@type']) == 'error':
          break
          #TODO probably we should chenge get_transactions API
          #if 'message' in raw_transactions['message']:
          #  raise Exception(raw_transactions['message'])
          #else:
          #  raise Exception("Can't get transactions")
        transactions, next = raw_transactions['transactions'], raw_transactions.get("previous_transaction_id", None)
        for t in transactions:
          tlt = int(t['transaction_id']['lt'])
          if tlt <= to_transaction_lt:
            reach_lt = True
            break
          all_transactions.append(t)
        if next:
          current_lt, curret_hash = int(next["lt"]), b64str_hex(next["hash"])
        else:
          break
        if current_lt==0:
          break
      return all_transactions

    def _raw_get_account_state(self, address: str):
        """
        TL Spec:
            raw.getAccountState account_address:accountAddress = raw.AccountState;
            accountAddress account_address:string = AccountAddress;
        :param address: str with raw or user friendly address
        :return: dict as
            {
                '@type': 'raw.accountState',
                'balance': str,
                'code': str,
                'data': str,
                'last_transaction_id': internal.transactionId,
                'sync_utime': int
            }
        """
        account_address = prepare_address(address)

        data = {
            '@type': 'raw.getAccountState',
            'account_address': {
                'account_address': address
            }
        }

        r = self._t_local.tonlib_wrapper.ton_exec(data)
        return r

    @parallelize
    def raw_get_account_state(self, address: str):
      return self._raw_get_account_state(address)

    @parallelize
    def generic_get_account_state(self, address: str):
        account_address = prepare_address(address)
        data = {
            '@type': 'generic.getAccountState',
            'account_address': {
                'account_address': address
            }
        }
        r = self._t_local.tonlib_wrapper.ton_exec(data)
        return r

    def _load_contract(self, address):
        if(self._t_local.loaded_contracts_num > 300):
          self.reload_tonlib()
        account_address = prepare_address(address)
        data = {
              '@type': 'smc.load',
               'account_address': {
                  'account_address': address
              }
        }  
        r = self._t_local.tonlib_wrapper.ton_exec(data)
        self._t_local.loaded_contracts_num += 1
        return r["id"]    

    def _raw_run_method(self, address, method, stack_data, output_layout=None):
      """
        For numeric data only
        TL Spec:
          smc.runGetMethod id:int53 method:smc.MethodId stack:vector<tvm.StackEntry> = smc.RunResult;
          
        smc.methodIdNumber number:int32 = smc.MethodId;
        smc.methodIdName name:string = smc.MethodId;
        
        tvm.slice bytes:string = tvm.Slice;
        tvm.cell bytes:string = tvm.Cell;
        tvm.numberDecimal number:string = tvm.Number;
        tvm.tuple elements:vector<tvm.StackEntry> = tvm.Tuple;
        tvm.list elements:vector<tvm.StackEntry> = tvm.List;

        tvm.stackEntrySlice slice:tvm.slice = tvm.StackEntry;
        tvm.stackEntryCell cell:tvm.cell = tvm.StackEntry;
        tvm.stackEntryNumber number:tvm.Number = tvm.StackEntry;
        tvm.stackEntryTuple tuple:tvm.Tuple = tvm.StackEntry;
        tvm.stackEntryList list:tvm.List = tvm.StackEntry;
        tvm.stackEntryUnsupported = tvm.StackEntry;
        
        smc.runResult gas_used:int53 stack:vector<tvm.StackEntry> exit_code:int32 = smc.RunResult;
      """
      stack_data = render_tvm_stack(stack_data)
      if isinstance(method, int):
        method = { '@type': 'smc.methodIdNumber', 'number': method}
      else:
        method = { '@type': 'smc.methodIdName', 'name': str(method)}
      contract_id = self._load_contract(address);
      data = {
            '@type': 'smc.runGetMethod',
            'id': contract_id,
            'method' : method,
            'stack' : stack_data
      }      
      r = self._t_local.tonlib_wrapper.ton_exec(data)
      if 'stack' in r:
        r['stack'] = serialize_tvm_stack(r['stack'])
      if '@type' in r and r['@type'] == 'smc.runResult':
        r.pop('@type')
      return r
      
    @parallelize
    def raw_run_method(self, address, method, stack_data, output_layout=None):
      return self._raw_run_method(address, method, stack_data, output_layout)
      

    @parallelize
    def raw_send_message(self, serialized_boc):
      """
        raw.sendMessage body:bytes = Ok;

        :param serialized_boc: bytes, serialized bag of cell
      """
      serialized_boc = codecs.decode(codecs.encode(serialized_boc, "base64"), 'utf-8').replace("\n",'')
      data = {
        '@type': 'raw.sendMessage',
        'body': serialized_boc
      }
      r = self._t_local.tonlib_wrapper.ton_exec(data)
      return r
      
    def _raw_create_query(self, destination, body, init_code=b'', init_data=b''):
      """
        raw.createQuery destination:accountAddress init_code:bytes init_data:bytes body:bytes = query.Info;
        
        query.info id:int53 valid_until:int53 body_hash:bytes  = query.Info;

      """
      init_code = codecs.decode(codecs.encode(init_code, "base64"), 'utf-8').replace("\n",'')
      init_data = codecs.decode(codecs.encode(init_data, "base64"), 'utf-8').replace("\n",'')
      body = codecs.decode(codecs.encode(body, "base64"), 'utf-8').replace("\n",'')
      destination = prepare_address(destination)
      data = {
        '@type': 'raw.createQuery',
        'body': body,
        'init_code': init_code,
        'init_data': init_data,
        'destination': {
          'account_address': destination
        }
      }
      r = self._t_local.tonlib_wrapper.ton_exec(data)
      return r
    
    def _raw_send_query(self, query_info): 
      """
        query.send id:int53 = Ok;
      """
      data = {
        '@type': 'query.send',
        'id': query_info['id']
      }
      r = self._t_local.tonlib_wrapper.ton_exec(data)
      return r
      #return ('@type' in r) and (r['@type']=="Ok")
    
    @parallelize
    def raw_create_and_send_query(self, destination, body, init_code=b'', init_data=b''):
      query_info = self._raw_create_query(destination, body, init_code, init_data)
      return self._raw_send_query(query_info)
      
    @parallelize
    def raw_create_and_send_message(self, destination, body, initial_account_state=b''):
      # Very close to raw_create_and_send_query, but StateInit should be generated outside
      """
        raw.createAndSendMessage destination:accountAddress initial_account_state:bytes data:bytes = Ok;
        
      """
      initial_account_state = codecs.decode(codecs.encode(initial_account_state, "base64"), 'utf-8').replace("\n",'')
      body = codecs.decode(codecs.encode(body, "base64"), 'utf-8').replace("\n",'')
      destination = prepare_address(destination)
      data = {
        '@type': 'raw.createAndSendMessage',
        'destination': {
          'account_address': destination
        },
        'initial_account_state': initial_account_state,
        'data': body
      }
      r = self._t_local.tonlib_wrapper.ton_exec(data)
      return r
      #return ('@type' in r) and (r['@type']=="Ok")

    @parallelize
    def raw_estimate_fees(self, destination, body, init_code=b'', init_data=b'', ignore_chksig=True):
      query_info = self._raw_create_query(destination, body, init_code, init_data)
      data = {
        '@type': 'query.estimateFees',
        'id': query_info['id'],
        'ignore_chksig': ignore_chksig
      }
      r = self._t_local.tonlib_wrapper.ton_exec(data)
      return r
