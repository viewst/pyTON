from hashlib import sha256 as hasher
import codecs

from tvm_valuetypes.cell import deserialize_boc

def seqno_extractor(result, data):
  data_cell = deserialize_boc(codecs.decode(codecs.encode(data["data"], 'utf-8'), 'base64'))
  seqno = int.from_bytes(data_cell.data.data[0:32].tobytes(), 'big')
  result['seqno'] = seqno

def v3_extractor(result, data):
  seqno_extractor(result, data)
  data_cell = deserialize_boc(codecs.decode(codecs.encode(data["data"], 'utf-8'), 'base64'))
  wallet_id = int.from_bytes(data_cell.data.data[32:64].tobytes(), 'big')
  result['wallet_id'] = wallet_id
  

def sha256(x):
  if not isinstance(x, bytes):
    x = codecs.encode(x, 'utf-8')
  h = hasher()
  h.update(x)
  return h.digest()

simple_wallet_code = "te6cckEBAQEARAAAhP8AIN2k8mCBAgDXGCDXCx/tRNDTH9P/0VESuvKhIvkBVBBE+RDyovgAAdMfMSDXSpbTB9QC+wDe0aTIyx/L/8ntVEH98Ik="
standard_wallet_code = "te6cckEBAQEAUwAAov8AIN0gggFMl7qXMO1E0NcLH+Ck8mCBAgDXGCDXCx/tRNDTH9P/0VESuvKhIvkBVBBE+RDyovgAAdMfMSDXSpbTB9QC+wDe0aTIyx/L/8ntVNDieG8="
wallet_v3_code = "te6cckEBAQEAYgAAwP8AIN0gggFMl7qXMO1E0NcLH+Ck8mCDCNcYINMf0x/TH/gjE7vyY+1E0NMf0x/T/9FRMrryoVFEuvKiBPkBVBBV+RDyo/gAkyDXSpbTB9QC+wDo0QGkyMsfyx/L/8ntVD++buA="

wallets = { sha256(simple_wallet_code): {'type': 'simple wallet', 'data_extractor':seqno_extractor},
	    sha256(standard_wallet_code): {'type': 'standart wallet', 'data_extractor':seqno_extractor},
	    sha256(wallet_v3_code): {'type': 'v3 wallet', 'data_extractor':v3_extractor}
}
