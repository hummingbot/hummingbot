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

from ecpy.curves     import Curve,Point
from ecpy.keys       import ECPublicKey, ECPrivateKey
from ecpy.formatters import decode_sig, encode_sig
from ecpy            import ecrand

import hashlib

class ECDSA:
    """ECDSA signer.

    Args:
        fmt (str) : in/out signature format. See :mod:`ecpy.formatters`
    """
    def __init__(self, fmt="DER"):
        self.fmt=fmt
        self.maxtries=10
        pass

    def sign(self, msg, pv_key, canonical=False):
        """ Signs a message hash.

        Args:
            msg (bytes)                    : the message hash to sign
            pv_key (ecpy.keys.ECPrivateKey): key to use for signing
        """
        order = pv_key.curve.order
        for i in range(1,self.maxtries):
            k = ecrand.rnd(order)
            sig = self._do_sign(msg, pv_key,k, canonical)
            if sig:
                return sig
        return None

    def sign_rfc6979(self, msg, pv_key, hasher, canonical=False):
        """ Signs a message hash  according to  RFC6979

        Args:
            msg (bytes)                    : the message hash to sign
            pv_key (ecpy.keys.ECPrivateKey): key to use for signing
            hasher (hashlib)               : hasher conform to hashlib interface
        """
        order = pv_key.curve.order
        V = None
        for i in range(1,self.maxtries):
            k,V = ecrand.rnd_rfc6979(msg, pv_key.d, order, hasher,V)
            sig = self._do_sign(msg, pv_key, k, canonical)
            if sig:
                return sig

        return None

    def sign_k(self, msg, pv_key, k,canonical=False):
        """ Signs a message hash  with provided random

        Args:
            msg (bytes)                    : the hash of message to sign
            pv_key (ecpy.keys.ECPrivateKey): key to use for signing
            k (ecpy.keys.ECPrivateKey)     : random to use for signing
        """
        return self._do_sign(msg, pv_key, k, canonical)

    def _do_sign(self, msg, pv_key, k, canonical=False):
        if (pv_key.curve == None):
            raise ECPyException('private key haz no curve')
        curve = pv_key.curve
        n = curve.order
        G = curve.generator
        k = k%n

        # if "msg (hash) bit length" is greater that the "domain bit length",
        # we only consider the left most "domain bit length" of message.
        msg_len = len(msg)*8;
        msg = int.from_bytes(msg, 'big');
        if msg_len > curve.size:
            msg = msg >> (msg_len-curve.size)

        Q = G*k
        if Q.is_infinity:
            return None

        kinv = pow(k,n-2,n)
        r = Q.x % n
        if r == 0:
            return None

        s = (kinv*(msg+pv_key.d*r)) %n
        if s == 0:
            return None

        if canonical and (s > (n//2)):
            s = n-s

        sig = encode_sig(r,s,self.fmt)

        # r = r.to_bytes((r.bit_length()+7)//8, 'big')
        # s = s.to_bytes((s.bit_length()+7)//8, 'big')
        # if (r[0] & 0x80) == 0x80 :
        #     r = b'\0'+r
        # if (s[0] & 0x80) == 0x80 :
        #     s = b'\0'+s
        # sig = (b'\x30'+int((len(r)+len(s)+4)).to_bytes(1,'big') +
        #        b'\x02'+int(len(r)).to_bytes(1,'big') + r        +
        #        b'\x02'+int(len(s)).to_bytes(1,'big') + s      )
        return sig

    def verify(self,msg,sig,pu_key):
        """ Verifies a message signature.

        Args:
            msg (bytes)                   : the message hash to verify the signature
            sig (bytes)                   : signature to verify
            pu_key (ecpy.keys.ECPublicKey): key to use for verifying
        """
        curve = pu_key.curve
        n     = curve.order
        G     = curve.generator

        r,s = decode_sig(sig, self.fmt)
        if (r == None or s == None or
            r == 0 or r >= n or
            s == 0 or s >= n ) :
            return False

        # if "msg (hash) bit length" is greater that the "domain bit length",
        # we only consider the left most "domain bit length" of message.
        msg_len = len(msg)*8;
        h = int.from_bytes(msg, 'big')
        if msg_len > curve.size:
            h = h >> (msg_len-curve.size)

        c   = pow(s, n-2, n)
        u1  = (h*c)%n
        u2  = (r*c)%n
        u1G = u1*G
        u2Q = u2*pu_key.W
        GQ  =  u1G+u2Q
        if GQ.is_infinity:
            return False
        x   = GQ.x % n

        return x == r


if __name__ == "__main__":
    import binascii
    try:
        signer = ECDSA()

        ### ECDSA secp256k1
        cv     = Curve.get_curve('secp256k1')
        pu_key = ECPublicKey(Point(0x65d5b8bf9ab1801c9f168d4815994ad35f1dcb6ae6c7a1a303966b677b813b00,

                                   0xe6b865e529b8ecbf71cf966e900477d49ced5846d7662dd2dd11ccd55c0aff7f,
                                   cv))
        pv_key = ECPrivateKey(0xfb26a4e75eec75544c0f44e937dcf5ee6355c7176600b9688c667e5c283b43c5,
                              cv)

        #sha256("abc")
        #  c:  0xC03DDDA6174963AD10224BADDBCF7ED9EA5E3DAE91941CB428D2EC060B4F290A
        # u1:  0x113BE17918E856E4D6EC2EE04F5E9B3CB599B82AC879C8E32A0140C290D32659
        # u2:  0x2976F786AE6333E125C0DFFD6C16D37E8CED5ABEDB491BCCA21C75B307D0B318
        # u1G: 0x51e4e6ed6f4b1db33b0d21b8bd30fb732f1d999c4e27bb1800eba20813ad3e86
        #      0x93101a9fa0d5c7c680400b03d3becb9130dd8f9f4d9b034360a74829dc1201ab
        # u2Q: 0xeaca8440897333e259d0f99165611b085d6e10a9bfd371c451bc0aea1aeb99c3
        #      0x57c5c95ea9f491c0fd9029a4089a2e6df47313f915f3e39e9f12e03ab16521c2
        #  + : 0x0623b4159c7112125be51716d1e706d68e52f5b321da68d8b86b3c7c7019a9da
        #    : 0x1029094ccc466a534df3dbb7f588b283c9bef213633750aeff021c4c131b7ce5
        # SIG: 3045
        #      0220
        #       0623b4159c7112125be51716d1e706d68e52f5b321da68d8b86b3c7c7019a9da
        #      0221
        #       008dffe3c592a0c7e5168dcb3d4121a60ee727082be4fbf79eae564929156305fc

        msg = int(0xba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad)
        sig = int(0x304502200623b4159c7112125be51716d1e706d68e52f5b321da68d8b86b3c7c7019a9da0221008dffe3c592a0c7e5168dcb3d4121a60ee727082be4fbf79eae564929156305fc)
        msg  = msg.to_bytes(32,'big')
        sig  = sig.to_bytes(0x47,'big')

        assert(signer.verify(msg,sig,pu_key))

        #  k:     0xe5a8d1d529971c10ca2af378444fb544a211707892c8898f91dcb171584e3db9
        # kG:     0x4f123ed9de853836447782f0a436508d34e6609083cf97c9b9cd69673d8f04a5
        #         0x50b57473f987f2d7c4715827dbd7b23c3088645d5f898aa66e4ef2778591d643
        # kinv:    0x0F2DD0361F61F683957CF708FB54DBC0B6B97F9EDF28604983E6F492117C154C
        # kinv.d   0xFF68C89B97C63273EB5F787FBC0C33DA02BA4C883AB09E3D381197E9E3964E8C
        # kinv.d.x 0x5A20058782FB81C8F98C30D9D441B7196C22939B144918CF519FB155180664B1
        # kinv.h   0x112FA7E277E3AE8AE4911A05B56880F05B601CCC633A3D0084C4D5734F0C5BD1
        # SIG      3044
        #           0220,
        #            4f123ed9de853836447782f0a436508d34e6609083cf97c9b9cd69673d8f04a5
        #           0220,
        #            6b4fad69fadf3053de1d4adf89aa3809c782b067778355cfd66486c86712c082
        expected_sig = int(0x304402204f123ed9de853836447782f0a436508d34e6609083cf97c9b9cd69673d8f04a502206b4fad69fadf3053de1d4adf89aa3809c782b067778355cfd66486c86712c082)
        expected_sig = expected_sig.to_bytes(0x46,'big')
        k   = int(0xe5a8d1d529971c10ca2af378444fb544a211707892c8898f91dcb171584e3db9)
        sig = signer.sign_k(msg,pv_key,k)
        assert(sig == expected_sig)

        #Sign with k rand
        sig = signer.sign(msg,pv_key)
        assert(signer.verify(msg,sig,pu_key))

        #sign with krfc
        sig = signer.sign_rfc6979(msg,pv_key,hashlib.sha256)
        assert(sig == expected_sig)


        ### ECDSA secp256k1

        cv     = Curve.get_curve('secp256k1')
        pu_key = ECPublicKey(Point(0x65d5b8bf9ab1801c9f168d4815994ad35f1dcb6ae6c7a1a303966b677b813b00,

                                   0xe6b865e529b8ecbf71cf966e900477d49ced5846d7662dd2dd11ccd55c0aff7f,
                                   cv))
        pv_key = ECPrivateKey(0xfb26a4e75eec75544c0f44e937dcf5ee6355c7176600b9688c667e5c283b43c5,
                              cv)
        W = pv_key.d * cv.generator
        assert(W == pu_key.W)

        msg = int(0xba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015adabcd)
        msg  = msg.to_bytes(34,'big')
        sig = signer.sign(msg,pv_key)
        assert(signer.verify(msg,sig,pu_key))

        ### ECDSA secp521k1

        cv     = Curve.get_curve('secp521r1')
        pv_key = ECPrivateKey(0x018cd813ca254d350b6e4a4a0a0fe2a27eac701d8ccfb1564085d612f315d5aa6c055390cfb7bedf7fc8c02af2360423e8c8a2e3cb045f844f3ec0a6c75025f4a4fa,
                              cv)
        pu_key = ECPublicKey(Point(0x016d523c74262368b2f066859dfd36645cfd7aa7f7c782732c8bee450cd9d42384bb3b9b480df9b440374856a37061d023ff99861796d7b5d146c5c5c3f9a0e34872,
                                   0x002377c7bee60c8dd47ce351c6e3f05d47fd0a1d62c8e2d0a61413e2ee453a38debf67de2da37bcdbd7e80ea5082021ad3f32c829f12d72240bc9f997b483366035a,
                                   cv))
        W = pv_key.d * cv.generator
        assert(W == pu_key.W)

        msg = int(0xba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad)
        msg  = msg.to_bytes(32,'big')
        sig = signer.sign(msg,pv_key)
        assert(signer.verify(msg,sig,pu_key))

        ##OK!
        print("All internal assert OK!")
    finally:
        pass

