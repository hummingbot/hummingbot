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

import hashlib
import random
import binascii

from ecpy.curves     import Curve,Point
from ecpy.keys       import ECPublicKey, ECPrivateKey
from ecpy.formatters import decode_sig, encode_sig, list_formats
from ecpy            import ecrand
from ecpy.curves     import ECPyException

def _h(b):
    return binascii.hexlify(b)

def _point_to_bytes(point, compressed = True):
    """ Point serialisation.
    
    Serialization is the standard one:
    
    - O2 x    for even x in compressed form
    - 03 x    for odd x in compressed form
    - 04 x y  for uncompressed form
    
    
    """
    if compressed:
        b = point.x.to_bytes(32,'big')
        if point.y & 1:
            b = b"\x03"+b
        else:
            b = b"\x02"+b
    else:
        b = b"\x04"+point.x.to_bytes(32,'big')+point.y.to_bytes(32,'big')
    return b

def _borromean_hash(m,e,i,j, H):
    """
    All params are bytes.
    
    m: bytes     message
    e: bytes     point
    i: int       ring index
    j: int       secret index
    """
    i = int(i).to_bytes(4,'big')
    j = int(j).to_bytes(4,'big')              
    sha256 = H()
    sha256.update(e)
    sha256.update(m)
    sha256.update(i)
    sha256.update(j)
    d = sha256.digest()
    return d

class Borromean:
    """ Borromean Ring signer implementation according to:
      
    https://github.com/Blockstream/borromean_paper/blob/master/borromean_draft_0.01_9ade1e49.pdf

    https://github.com/ElementsProject/secp256k1-zkp/blob/secp256k1-zkp/src/modules/rangeproof/borromean_impl.h

    ElementsProject implementation has some tweaks compared to PDF. This implementation is ElementsProject compliant.

    For now, only secp256k1+sha256 is supported. This constraint will be release soon.

    Args:
        fmt (str) : in/out signature format. See :mod:`ecpy.formatters`. IGNORED.
    """


    def __init__(self,  fmt="BTUPLE") :
        self.fmt = fmt
        self._curve = Curve.get_curve('secp256k1')
        self._hash = hashlib.sha256
        
    def sign(self, msg, rings, pv_keys, pv_keys_index):
        """ Signs a message hash.

        The public `rings` argument is a tuple of public key array. In other 
        words each element of the ring tuple is an array containing the  public
        keys list of that ring

        A Private key must be given for each provided ring. For each private key,
        the corresponding public key is specified by its index in the ring.
      
        Exemple:
            let r1 be the first ring with 2 keys:    pu11, pu12
            let 21 be the second ring with 3 keys:   pu21,pu22,pu23
            let say we want to produce a signature with sec12 and sec21 
            `sign` should be called as::

                borromean.sign(m, 
                              ([pu11,pu12],[pu21,pu22,pu23]), 
                              [sec12, sec21], [1,0])

        The return value is a tuple (e0, [s0,s1....]). Each value is encoded
        as binary (bytes).
        
        Args:
            msg (bytes)                              : the message hash to sign
            rings (tuple of (ecpy.keys.ECPublicKey[]): public key rings
            pv_keys (ecpy.keys.ECPrivateKey[])       : key to use for signing
            pv_keys_index (int[])                    :

        Returns:
            (e0, [s0,s1....]) : signature
        """
        #shorcuts
        G     = self._curve.generator
        order = self._curve.order

        #set up locals
        ring_count = len(rings)
        privkeys = pv_keys
        pubkeys = []
        rsizes = []
        for r in rings:
            pubkeys = pubkeys+r
            rsizes.append(len(r))
        e0 = None
        s  = [None]*len(pubkeys)
        k  = [None]*len(rings)
            
        #step2-3
        r0 = 0
        sha256_e0 = self._hash()
        for i in range (0,ring_count):
            k[i] = random.randint(1,order)
            kiG = k[i]*G
            j0 = pv_keys_index[i]
            e_ij = _point_to_bytes(kiG)               
            for j in range(j0+1, rsizes[i]):
                s[r0+j] = random.randint(1,order)
                e_ij = _borromean_hash(m,e_ij,i,j, self._hash) 
                e_ij = int.from_bytes(e_ij,'big')
                sG_eP = s[r0+j]*G + e_ij*pubkeys[r0+j].W
                e_ij = _point_to_bytes(sG_eP)
            sha256_e0.update(e_ij)
            r0 += rsizes[i]
        sha256_e0.update(m)
        e0 =  sha256_e0.digest()    
        #step 4
        r0 = 0
        for i in range (0, ring_count):
            j0 = pv_keys_index[i]
            e_ij = _borromean_hash(m,e0,i,0, self._hash)
            e_ij = int.from_bytes(e_ij,'big')
            for j in range(0, j0):
                s[r0+j] = random.randint(1,order)           
                sG_eP = s[r0+j]*G + e_ij*pubkeys[r0+j].W
                e_ij = _borromean_hash(m,_point_to_bytes(sG_eP),i,j+1, self._hash)
                e_ij = int.from_bytes(e_ij,'big')
            s[r0+j0] = (k[i]-privkeys[i].d*e_ij)%order
            r0 += rsizes[i]
        s = [int(sij).to_bytes(32,'big')  for sij in s]
        return (e0,s)

    def verify(self, msg, sig, rings):
        """ Verifies a message signature.                

        Args:
            msg (bytes)             : the message hash to verify the signature
            sig (bytes)             : signature to verify
            rings (key.ECPublicKey): key to use for verifying

        Returns:
            boolean : True if signature is verified, False else
        """
         #shortcuts
        G     = self._curve.generator
        #set up locals
        ring_count = len(rings)
        pubkeys = []
        rsizes = []
        for r in rings:
            pubkeys = pubkeys+r
            rsizes.append(len(r))
        #verify
        e0 = sig[0]
        s = sig[1]
        sha256_e0 = self._hash()
        r0 = 0
        for i in range (0,ring_count):
            e_ij = _borromean_hash(m,e0,i,0, self._hash) 
            for j in range(0,rsizes[i]):
                e_ij = int.from_bytes(e_ij,'big')
                s_ij = int.from_bytes(s[r0+j],'big')
                sG_eP = s_ij*G + e_ij*pubkeys[r0+j].W
                e_ij = _point_to_bytes(sG_eP)
                if j != rsizes[i]-1:
                    e_ij = _borromean_hash(m,e_ij,i,j+1, self._hash) 
                else:
                    sha256_e0.update(e_ij)
            r0 += rsizes[i]
        sha256_e0.update(m)
        e0x = sha256_e0.digest()
        return e0 == e0x


if __name__ == "__main__":
    import sys
 
    def strsig(sigma):
        print("e0: %s"%h(sigma[0]))
        i=0
        for s in sigma[1]:
            print("s%d: %s"%(i,h(s)))
            i += 1
    try:

        #
        # layout: 
        # nrings = 2
        #   ring 1 has 2 keys
        #   ring 2 has 3 keys
        #
        # pubs=[ring1-key1, ring1-key2,   
        #       ring2-key1, ring2-key2, ring2-key3]
        # 
        # k = [ring1-rand, ring2-rand]
        # sec = [ring1-sec2, ring2-sec1]
        # rsizes = [2,3]
        # secidx = [1,0]
        # 
        #

        cv     = Curve.get_curve('secp256k1')
        
        seckey0  = ECPrivateKey(0xf026a4e75eec75544c0f44e937dcf5ee6355c7176600b9688c667e5c283b43c5, cv)
        seckey1  = ECPrivateKey(0xf126a4e75eec75544c0f44e937dcf5ee6355c7176600b9688c667e5c283b43c5, cv)
        seckey2  = ECPrivateKey(0xf226a4e75eec75544c0f44e937dcf5ee6355c7176600b9688c667e5c283b43c5, cv)
        seckey3  = ECPrivateKey(0xf326a4e75eec75544c0f44e937dcf5ee6355c7176600b9688c667e5c283b43c5, cv)
        seckey4  = ECPrivateKey(0xf426a4e75eec75544c0f44e937dcf5ee6355c7176600b9688c667e5c283b43c5, cv)
        seckey5  = ECPrivateKey(0xf526a4e75eec75544c0f44e937dcf5ee6355c7176600b9688c667e5c283b43c5, cv)
        seckey6  = ECPrivateKey(0xf626a4e75eec75544c0f44e937dcf5ee6355c7176600b9688c667e5c283b43c5, cv)
        seckey7  = ECPrivateKey(0xf726a4e75eec75544c0f44e937dcf5ee6355c7176600b9688c667e5c283b43c5, cv)
        seckey8  = ECPrivateKey(0xf826a4e75eec75544c0f44e937dcf5ee6355c7176600b9688c667e5c283b43c5, cv)
        
        pubkey0 = seckey0.get_public_key()
        pubkey1 = seckey1.get_public_key()
        pubkey2 = seckey2.get_public_key()
        pubkey3 = seckey3.get_public_key()
        pubkey4 = seckey4.get_public_key()
        pubkey5 = seckey5.get_public_key()
        pubkey6 = seckey6.get_public_key()
        pubkey7 = seckey7.get_public_key()
        pubkey8 = seckey8.get_public_key()
        
        allpubs = [pubkey0, pubkey1, pubkey2, pubkey3, pubkey4, pubkey5,pubkey6, pubkey7]
        allsecs = [seckey0, seckey1, seckey2, seckey3, seckey4, seckey5,seckey6, seckey7]

        m = int(0x800102030405060708090a0b0c0d0e0f800102030405060708090a0b0c0d0e0f)
        m = m.to_bytes(32,'big')

        borromean = Borromean()
        

        for l in range(2,len(allpubs)):
            pubs = allpubs[:l]
            secs = allsecs[:l]
            print("pool has %d key"%len(pubs))
            for i in range(1,len(pubs)):
                pubring1 = pubs[0:i]
                pubring2 = pubs[i:]
                secring1 = secs[0:i]
                secring2 = secs[i:]
        
                print("ring1 has %d keys"%len(pubring1))
                print("ring2 has %d keys"%len(pubring2))
                for s1 in range(0,len(pubring1)):
                    for s2 in range(0,len(pubring2)):
                        print("testing %d %d"%(s1,s2))
                        pubset = (pubring1 , pubring2)
                        secset = [secring1[s1] , secring2[s2]]
                        secidx = [s1,s2]
                        sigma = borromean.sign(m, pubset, secset, secidx )
                        assert(borromean.verify( m, sigma, pubset, )) 
                        
                        e0 = sigma[0]
                        e0 = e0[1:]+e0[:1]
                        sigma = (e0,sigma[1])
                        assert(not borromean.verify(m, sigma,  pubset))
                        

        

            # ##OK!
        print("All internal assert OK!")
    finally:
        pass
