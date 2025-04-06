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
from ecpy.formatters import decode_sig, encode_sig, list_formats
from ecpy            import ecrand
from ecpy.curves     import ECPyException

import hashlib
import binascii

class ECSchnorr:
    """ ECSchnorr signer implementation according to:

     - `BSI:TR03111 <https://www.bsi.bund.de/SharedDocs/Downloads/EN/BSI/Publications/TechGuidelines/TR03111/BSI-TR-03111_pdf.html>`_
     - `ISO/IEC:14888-3 <http://www.iso.org/iso/iso_catalogue/catalogue_ics/catalogue_detail_ics.htm?csnumber=43656>`_
     - `bitcoin-core:libsecp256k1 <https://github.com/bitcoin-core/secp256k1/blob/master/src/modules/schnorr/schnorr_impl.h>`_
     - `Z` : https://docs.zilliqa.com/whitepaper.pdf

    In order to select the specification to be conform to, choose
    the corresponding string option: "BSI", "ISO", "ISOx", "LIBSECP", "Z"

    *Signature*:

    - "BSI": compute r,s according to to BSI :
        1. k = RNG(1:n-1)
        2. Q = [k]G
        3. r = H(M ||Qx)
           If r = 0 mod n, goto 1.
        4. s = k - r.d mod n
           If s = 0 goto 1.
        5. Output (r, s)
    - "ISO": compute r,s according to ISO :
        1. k = RNG(1:n-1)
        2. Q = [k]G
           If r = 0 mod n, goto 1.
        3. r = H(Qx||Qy||M).
        4. s = (k + r.d) mod n
           If s = 0 goto 1.
        5. Output (r, s)
    - "ISOx": compute r,s according to optimized ISO variant:
        1. k = RNG(1:n-1)
        2. Q = [k]G
           If r = 0 mod n, goto 1.
        3. r = H(Qx||Qy||M).
        4. s = (k + r.d) mod n
           If s = 0 goto 1.
        5. Output (r, s)
    - "LIBSECP": compute r,s according to bitcoin lib:
        1. k = RNG(1:n-1)
        2. Q = [k]G
           if Qy is odd, negate k and goto 2
        3. r = Qx % n
        4. h = H(r || m).
           if h == 0 or h >= order goto 1
        5. s = k - h.d.
        6. Output (r, s)
    - "Z": compute r,s according to zilliqa lib:
        1. Generate a random k from [1, ..., order-1]
        2. Compute the commitment Q = kG, where  G is the base point
        3. Compute the challenge r = H(Q, kpub, m) [CME: mod n according to pdf/code, Q and kpub compressed "02|03 x" according to code)
        4. If r = 0 mod(order), goto 1
        5. Compute s = k - r*kpriv mod(order)
        6. If s = 0 goto 1.
        7. Output (r, s)

    *Verification*

    - "BSI": verify r,s according to to BSI :
        1. Verify that r in {0, . . . , 2**t - 1} and s in {1, 2, . . . , n - 1}.
           If the check fails, output False and terminate.
        2. Q = [s]G + [r]W
           If Q = 0, output Error and terminate.
        3. v = H(M||Qx)
        4. Output True if v = r, and False otherwise.
    - "ISO": verify r,s according to ISO :
        1. check...
        2. Q = [s]G - [r]W
           If Q = 0, output Error and terminate.
        3. v = H(Qx||Qy||M).
        4. Output True if v = r, and False otherwise.
    - "ISOx": verify r,s according to optimized ISO variant:
        1. check...
        2. Q = [s]G - [r]W
           If Q = 0, output Error and terminate.
        3. v = H(Qx||M).
        4. Output True if v = r, and False otherwise.
    - "LIBSECP":
        1. Signature is invalid if s >= order.
           Signature is invalid if r >= p.
        2. h = H(r || m).
           Signature is invalid if h == 0 or h >= order.
        3. R = [h]Q + [s]G.
           Signature is invalid if R is infinity or R's y coordinate is odd.
        4. Signature is valid if the serialization of R's x coordinate equals r.
    - "Z":
        1. Check if r,s is in [1, ..., order-1]
        2. Compute Q = sG + r*kpub
        3. If Q = O (the neutral point), return 0;
        4. r' = H(Q, kpub, m) [CME: mod n according to pdf/code, according to code), Q and kpub compressed "02|03 x"]
        5. return r' == r

    Default is "ISO"

    Args:
      hasher (hashlib): callable constructor returning an object with update(), digest() interface. Example: hashlib.sha256,  hashlib.sha512...
      option (str) : one of "BSI","ISO","ISOx","LIBSECP"
      fmt (str) : in/out signature format. See :mod:`ecpy.formatters`
    """

    def __init__(self, hasher, option="ISO", fmt="DER"):
        if not option in ("ISO","ISOx","BSI","LIBSECP","Z"):
            raise ECPyException('ECSchnorr option not supported: %s'%option)
        if not fmt in list_formats():
            raise ECPyException('ECSchnorr format not supported: %s'%fmt)

        self._hasher = hasher
        self.fmt = fmt
        self.maxtries = 100
        self.option = option

    def sign(self, msg, pv_key):
        """ Signs a message hash.

        Args:
            hash_msg (bytes)               : the message hash to sign
            pv_key (ecpy.keys.ECPrivateKey): key to use for signing
        """
        order = pv_key.curve.order
        for i in range(1,self.maxtries):
            k = ecrand.rnd(order)
            sig = self._do_sign(msg, pv_key,k)
            if sig:
                return sig
        return None

    def sign_k(self, msg, pv_key, k):
        """ Signs a message hash  with provided random

        Args:
            hash_msg (bytes)               : the message hash to sign
            pv_key (ecpy.keys.ECPrivateKey): key to use for signing
            k (ecpy.keys.ECPrivateKey)     : random to use for signing
        """
        return self._do_sign(msg, pv_key,k)

    def _do_sign(self, msg, pv_key, k):
        if (pv_key.curve == None):
            raise ECPyException('private key haz no curve')
        curve = pv_key.curve
        n     = curve.order
        G     = curve.generator
        size  = (curve.size+7)//8

        Q = G*k
        hasher = self._hasher()
        if self.option == "ISO":
            xQ = (Q.x).to_bytes(size,'big')
            yQ = (Q.y).to_bytes(size,'big')
            hasher.update(xQ+yQ+msg)
            r = hasher.digest()
            r = int.from_bytes(r,'big')
            if r % n == 0:
                return None
            s = (k+r*pv_key.d)%n
            if s==0:
                return None

        elif self.option == "ISOx":
            xQ = (Q.x).to_bytes(size,'big')
            hasher.update(xQ+msg)
            r = hasher.digest()
            r = int.from_bytes(r,'big')
            if r % n == 0:
                return None
            s = (k+r*pv_key.d)%n
            if s==0:
                return None

        elif self.option == "BSI":
            xQ = Q.x.to_bytes(size,'big')
            hasher.update(msg+xQ)
            r = hasher.digest()
            r = int.from_bytes(r,'big')
            if r%n == 0:
                return None
            s = (k-r*pv_key.d)%n
            if s==0:
                return None

        elif self.option == "LIBSECP":
            if Q.y & 1:
                k = n-k
                Q = G*k
            r = (Q.x%n).to_bytes(size,'big')
            hasher.update(r+msg)
            h = hasher.digest()
            h = int.from_bytes(h,'big')
            if h > n:
                return None
            r = Q.x % n
            s = (k - h*pv_key.d)%n

        elif self.option == "Z":
            if Q.y & 1:
                xQ = b'\x03'+Q.x.to_bytes(size,'big')
            else :
                xQ = b'\x02'+Q.x.to_bytes(size,'big')
            pu_key = pv_key.get_public_key()
            if pu_key.W.y & 1:
                xPub = b'\x03'+pu_key.W.x.to_bytes(size,'big')
            else :
                xPub = b'\x02'+pu_key.W.x.to_bytes(size,'big')
            hasher.update(xQ+xPub+msg)
            r = hasher.digest()
            r = int.from_bytes(r,'big') % n
            if r % n == 0:
                return None
            s = (k - r*pv_key.d) %n
            if s==0:
                return None

        return encode_sig(r, s, self.fmt)

    def verify(self,msg,sig,pu_key):
        """ Verifies a message signature.

        Args:
            msg (bytes)             : the message hash to verify the signature
            sig (bytes)             : signature to verify
            pu_key (ecpy.keys.ECPublicKey): key to use for verifying
        """
        curve = pu_key.curve
        n     = pu_key.curve.order
        G     = pu_key.curve.generator
        size  = (curve.size+7)//8

        r,s = decode_sig(sig, self.fmt)
        if (r == None or s == None or
            r == 0 or
            s == 0 or s >= n ):
            return False
        hasher = self._hasher()
        if self.option == "ISO":
            sG = s * G
            rW = r*pu_key.W
            Q = sG - rW
            xQ = Q.x.to_bytes(size,'big')
            yQ = Q.y.to_bytes(size,'big')
            hasher.update(xQ+yQ+msg)
            v = hasher.digest()
            v = int.from_bytes(v,'big')

        elif self.option == "ISOx":
            sG = s * G
            rW = r*pu_key.W
            Q = sG - rW
            xQ = Q.x.to_bytes(size,'big')
            hasher.update(xQ+msg)
            v = hasher.digest()
            v = int.from_bytes(v,'big')

        elif self.option == "BSI":
            sG = s * G
            rW = r*pu_key.W
            Q = sG + rW
            xQ = (Q.x).to_bytes(size,'big')
            hasher.update(msg+xQ)
            v = hasher.digest()
            v = int.from_bytes(v,'big')

        elif self.option == "LIBSECP":
            rb = r.to_bytes(size,'big')
            hasher.update(rb+msg)
            h = hasher.digest()
            h = int.from_bytes(h,'big')
            if h == 0 or h > n :
                return 0
            sG = s * G
            hW = h*pu_key.W
            R = sG + hW
            v = R.x % n

        elif self.option == "Z":
            sG = s * G
            rW = r*pu_key.W
            Q = sG + rW
            if Q.y & 1:
                xQ = b'\x03'+Q.x.to_bytes(size,'big')
            else :
                xQ = b'\x02'+Q.x.to_bytes(size,'big')
            if pu_key.W.y & 1:
                xPub = b'\x03'+pu_key.W.x.to_bytes(size,'big')
            else :
                xPub = b'\x02'+pu_key.W.x.to_bytes(size,'big')
            hasher.update(xQ+xPub+msg)
            v = hasher.digest()
            v = int.from_bytes(v,'big')
            v = v%n

        return v == r

if __name__ == "__main__":
    import sys,random
    try:
        cv     = Curve.get_curve('NIST-P256')
        pu_key = ECPublicKey(Point(0x09b58b88323c52d1080aa525c89e8e12c6f40fcb014640fa88081ed9e9352de7,
                                   0x5ccbbd189538516238b0b0b28acb5f0b5e27217c3a9872421219de0aeebf1080,
                                   cv))
        pv_key = ECPrivateKey(0x5202a3d8acaf6909d12c9a774cd886f9fba61137ffd3e8e76aed363fb47ac492,
                              cv)

        msg = int(0x616263)
        msg  = msg.to_bytes(3,'big')

        k = int(0xde7e0e5e663f24183414b7c72f24546b81e9e5f410bebf26f3ca5fa82f5192c8)

        ## ISO
        R=0x5A79A0AA9B241E381A594B220554D096A5F09FA628AD9A33C3CE4393ADE1DEF7
        S=0x5C0EB78B67A513C3E53B2619F96855E291D5141C7CD0915E1D04B347457C9601

        signer = ECSchnorr(hashlib.sha256,"ISO","ITUPLE")
        sig = signer.sign_k(msg,pv_key,k)
        assert(R==sig[0])
        assert(S==sig[1])
        assert(signer.verify(msg,sig,pu_key))

        ##ISOx
        R = 0xd7fb8135d8ea45e8fb3c9059f146e2630ef4bd51c4006a92edb4c8b0849963fb
        S = 0xb46d1525379e02e232d97928265b7254ea2ed97813454388c1a08f62dccd70b3

        signer = ECSchnorr(hashlib.sha256,"ISOx","ITUPLE")
        sig = signer.sign_k(msg,pv_key,k)
        assert(R==sig[0])
        assert(S==sig[1])
        assert(signer.verify(msg,sig,pu_key))

        ##BSI
        signer = ECSchnorr(hashlib.sha256,"BSI","ITUPLE")
        sig = signer.sign_k(msg,pv_key,k)
        assert(signer.verify(msg,sig,pu_key))

        ##Z
        k = int(0xde7e0e5e663f24183414b7c72f24546b81e9e5f410bebf26f3ca5fa82f5192c8)
        cv     = Curve.get_curve('secp256r1')
        pv_key = ECPrivateKey(0x2eef7823f82ed254524fad3d11cc17e897e582a0cd52b93f07cc030370d170bd,
                              cv)
        pu_key = pv_key.get_public_key()
        msg = int(0xb46d1525379e02e232d97928265b7254ea2ed97813454388c1a08f62dccd70b3)
        msg  = msg.to_bytes(32,'big')
        signer = ECSchnorr(hashlib.sha256,"Z","ITUPLE")
        sig = signer.sign_k(msg,pv_key,k)
        assert(signer.verify(msg,sig,pu_key))


        ##LIBSECP
        cv     = Curve.get_curve('secp256k1')
        pu_key = ECPublicKey(Point(0x65d5b8bf9ab1801c9f168d4815994ad35f1dcb6ae6c7a1a303966b677b813b00,
                                   0xe6b865e529b8ecbf71cf966e900477d49ced5846d7662dd2dd11ccd55c0aff7f,
                                   cv))
        pv_key = ECPrivateKey(0xfb26a4e75eec75544c0f44e937dcf5ee6355c7176600b9688c667e5c283b43c5,
                              cv)

        msg = int(0x0101010101010101010101010101010101010101010101010101010101010101)
        msg  = msg.to_bytes(32,'big')
        k = int(0x4242424242424242424242424242424242424242424242424242424242424242)
        expect_r = 0x24653eac434488002cc06bbfb7f10fe18991e35f9fe4302dbea6d2353dc0ab1c
        expect_s = 0xacd417b277ab7e7d993cc4a601dd01a71696fd0dd2e93561d9de9b69dd4dc75c

        signer = ECSchnorr(hashlib.sha256,"LIBSECP","ITUPLE")
        sig = signer.sign_k(msg,pv_key,k)
        assert(expect_r == sig[0])
        assert(expect_s == sig[1])
        assert(signer.verify(msg,sig,pu_key))

        def _round8(v):
            v += 7
            return v-v%8

        CURVES = ["secp256k1", "secp256r1", "Brainpool-p256r1", "Brainpool-p256t1"]
        MODES = ["LIBSECP", "ISO", "ISOx", "BSI", "Z"]
        SUCCESS_LIMIT = 100
        hashname = "sha256"
        for curvename in CURVES:
            for modename in MODES:
                print(f"CURVE={curvename}, MODE={modename}, HASH={hashname}")
                i = 1
                while i < SUCCESS_LIMIT:
                    hasher = eval(f"hashlib.{hashname}")()
                    hasherclass = eval(f"hashlib.{hashname}")
                    curveobj = Curve.get_curve(curvename)
                    curvesize = _round8(curveobj.size)//8
                    signer = ECSchnorr(hasherclass, option=modename)
                    d = random.randint(0, curveobj.order)
                    priv_key = ECPrivateKey(d, curveobj)
                    pub_key = priv_key.get_public_key()
                    msg = random.randint(0, pow(2, 256))
                    msg = msg.to_bytes(32, 'big')
                    hasher.update(msg)
                    msg = hasher.digest()
                    sig_host = signer.sign(msg, priv_key)
                    try:
                        assert(signer.verify(msg, sig_host, pub_key))
                    except AssertionError:
                        print(f"failed at {i}th round")
                        break
                    else:
                        i += 1

        # ##OK!
        print("All internal assert OK!")
    finally:
        pass
