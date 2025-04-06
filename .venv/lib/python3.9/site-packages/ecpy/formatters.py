# Copyright 2016 Cedric Mesnil <cedric.mesnil@ubinity.com>, Ubinity SAS
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#python 2 compatibility
from builtins import int,pow

def list_formats():
    return ("DER","BTUPLE","ITUPLE","RAW","EDDSA")

def encode_sig(r,s,fmt="DER",size=0) :
    """ encore signature according format

    Args:
        r (int):   r value
        s (int):   s value
        fmt (str): 'DER'|'BTUPLE'|'ITUPLE'|'RAW'|'EDDSA

    Returns:
         bytes:  TLV   for DER encoding
    Returns:
         bytes:  (r,s) for BTUPLE encoding
    Returns:
         ints:   (r,s) for ITUPLE encoding
    Returns:
         bytes:  r|s   for RAW encoding
    """

    def _int2bin(x, size=None):
        if not size:
            size = (x.bit_length()+7)//8
        return x.to_bytes(size, 'big')

    if fmt=="DER":

        def _strip_leading_zero(x):
            while x[0] == 0:
                x = x[1:]
            if x[0] &0x80:
                x = b'\0'+x
            return x

        def _tlv(t,v):
            """
            t(bin),v(bin) ->  tlv(bin)
            """
            l = _int2bin(len(v))
            if len(v) > 0x80:
                l = bytes([0x80 + len(l)])+l
            return t+l+v

        r = _tlv(b'\x02', _strip_leading_zero(_int2bin(r)))
        s = _tlv(b'\x02', _strip_leading_zero(_int2bin(s)))
        sig = _tlv(b'\x30',r+s)
        return sig

    if fmt=="BTUPLE":
        r = _int2bin(r)
        s = _int2bin(s)
        return (r,s)

    if fmt=="ITUPLE":
        return (r,s)

    if fmt=="RAW":
        if size == 0:
            raise ECPyException("size must be specified when encoding in RAW")
        r = _int2bin(r, size)
        s = _int2bin(s, size)
        return r+s

    if fmt=="EDDSA":
        if size == 0:
            raise ECPyException("size must be specified when encoding in EDDSA")
        r = r.to_bytes(size, 'little')
        s = s.to_bytes(size, 'little')
        return r+s


def decode_sig(sig,fmt="DER") :
    """ encore signature according format

    Args:
        rs (bytes,ints,tuple) : r,s value
        fmt (str): 'DER'|'BTUPLE'|'ITUPLES'|'RAW'|'EDDSA'

    Returns:
       ints:   (r,s)
    """

    def _untlv(tlv):
        t = tlv[0]
        l = tlv[1]
        tlv = tlv[2:]
        if l & 0x80 :
            l = l&0x7F
            if l == 1:
                l = tlv[0]
                tlv = tlv[1:]
            elif l ==2:
                l = tlv[0]<<8 | tlv[1]
                tlv = tlv[2:]
            elif l ==3:
                l = tlv[0]<<16 | tlv[1]<<8 | tlv[2]
                tlv = tlv[3:]
            elif l ==4:
                l = tlv[0]<<24 | tlv[1]<<16 | tlv[2]<<8 | tlv[3]
                tlv = tlv[4:]
            else :
                return None,None,None,None

            if len(tlv)<l:
                return None,None,None,None

        v = tlv[0:l]
        return t,l,v, tlv[l:]


    if fmt=="DER":

        t,l,v, tail = _untlv(sig)

        if t != 0x30 or len(tail) != 0:
            return None,None

        tr,lr,vr , tail = _untlv(v)
        ts,ls,vs , tail = _untlv(tail)

        if ts != 0x02 or tr != 0x02 or len(tail) != 0:
           return None,None

        r = int.from_bytes(vr, 'big')
        s = int.from_bytes(vs, 'big')
        return r,s

    if fmt=="ITUPLE":
        return sig[0], sig[1]

    if fmt=="BTUPLE":
        r = int.from_bytes(sig[0], 'big')
        s = int.from_bytes(sig[1], 'big')
        return r,s

    if fmt=="RAW":
        l = len(sig)
        if l & 1:
            return None,None
        l = l>>1
        r = int.from_bytes(sig[0:l], 'big')
        s = int.from_bytes(sig[l:],  'big')
        return r,s

    if fmt=="EDDSA":
        l = len(sig)
        if l & 1:
            return None,None
        l = l>>1
        r = int.from_bytes(sig[0:l], 'little')
        s = int.from_bytes(sig[l:],  'little')
        return r,s
