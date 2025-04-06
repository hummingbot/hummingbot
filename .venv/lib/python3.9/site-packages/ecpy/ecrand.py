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
from builtins import int

from ecpy.curves     import Curve,Point
from ecpy.keys       import ECPublicKey, ECPrivateKey
from ecpy.formatters import decode_sig, encode_sig

import random
import hmac

def rnd(q):
    """ Returns a random number less than q, with the same bits length than q

    Args:
        q (int)         : field/modulo

    Returns:
        int : random
    """
    nbits = q.bit_length()
    while True:
        k = random.getrandbits(nbits)
        if k<q:
            return k



def rnd_rfc6979(hashmsg, secret, q, hasher, VK = None):
    """ Generates a deterministic `value` according  to RF6979.

    See https://tools.ietf.org/html/rfc6979#section-3.2

    if V == None, this is the first try, so compute the initial value for V.
    Else it means the previous value has been rejected by the caller, so
    generate the next one!

    Warning: the `hashmsg` parameter is the message hash, not the message
    itself. In other words, `hashmsg` is equal to `h1` in the  *rfc6979, section-3.2,
    step a*.

    Args:
       hasher (hashlib): hasher
       hashmsg (bytes) : message hash
       secret (int)    : secret
       q (int)         : field/modulo
       V               : previous value for continuation

    The function returns a couple `(k,V)` with `k` the expected value and `V` is the
    continuation value to pass to next cal if k is rejected.

    Returns:
      tuple: (k,V)

    """
    def bits2int(bs):
        """
        bs(bytes): binary value
        """
        i = int.from_bytes(bs,'big')
        blen = len(bs)*8


        qlen = q.bit_length()
        if blen > qlen:
            i = i >> (blen-qlen)
        return i

    def int2octets(i):
        rlen = ((q.bit_length()+7)&~7)//8
        o = i.to_bytes(rlen, 'big')
        return o

    def bits2octets(bs) :
        z1 = bits2int(bs)
        z2 = z1%q
        o = int2octets(z2)
        return o

    if (VK == None):
        #A.  Process m through the hash function H, yielding: h1 = H(m)
        #h1 = hasher(msg).digest()
        hsize = hasher().digest_size
        h1 = hashmsg
        #B. Set: V = 0x01 0x01 0x01 ... 0x01
        V = b'\x01'*hsize
        #C. Set: K = 0x00 0x00 0x00 ... 0x00
        K = b'\x00'*hsize
        #D. Set: K = HMAC_K(V || 0x00 || int2octets(x) || bits2octets(h1))
        K = hmac.new(K, V + b'\x00' + int2octets(secret) + bits2octets(h1), hasher).digest()
        #E. Set: V = HMAC_K(V)
        V = hmac.new(K,V,hasher).digest()
        #F. Set: K = HMAC_K(V || 0x01 || int2octets(x) || bits2octets(h1))
        K = hmac.new(K, V + b'\x01' + int2octets(secret) + bits2octets(h1), hasher).digest()
        #G. Set: V = HMAC_K(V)
        V = hmac.new(K,V,hasher).digest()
    else:
        V = VK[0]
        K = VK[1]
        K = hmac.new(K, V+b'\x00', hasher).digest()
        V = hmac.new(K, V, hasher).digest()

    #h.  Apply the following algorithm until a proper value is found for  k:
    while True:
        #
        #  1.  Set T to the empty sequence.  The length of T (in bits) is
        #      denoted tlen; thus, at that point, tlen = 0.
        T = b''
        #   2.  While tlen < qlen, do the following:
        #         V = HMAC_K(V)
        #         T = T || V
        qlen =  q.bit_length()
        _i = 0
        while len(T)*8 < qlen :
            V = hmac.new(K, V, hasher).digest()
            T = T + V
        #3.  Compute:
        k = bits2int(T)
        #      If that value of k is within the [1,q-1] range, and is
        #      suitable for DSA or ECDSA (i.e., it results in an r value
        #      that is not 0; see Section 3.4), then the generation of k is
        #      finished.  The obtained value of k is used in DSA or ECDSA.
        if 1 <= k and k <= (q-1):
            return k,(V,K)
        #      Otherwise, compute:
        #        K = HMAC_K(V || 0x00)
        #        V = HMAC_K(V)
        #        and loop (try to generate a new T, and so on).
        K = hmac.new(K, V+b'\x00', hasher).digest()
        V = hmac.new(K, V, hasher).digest()


if __name__ == "__main__":
    import hashlib
    h = 0xaf9ae10ca04f826d5ff4727f97fb568c79e9ffa9686b9d5deb4ea4db44d6f23d
    h = h.to_bytes(32,'big')
    secret = 0xe7244dd97b3558788fbf02f443d9a6ebd12a1ab01703a683aa12412354a43218
    q = 0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f

    hashlib.sha256
    r,V = rnd_rfc6979(h, secret, q, hashlib.sha256)
    assert(r == 0xbf13da837bcfa314f30fa68be3a9219ca244c1b36f0440624ba88406fcd7462d)
