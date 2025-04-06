# encoding: UTF-8

# Copyright 2016-2017 Cedric Mesnil <cedric.mesnil@ubinity.com>, Ubinity SAS
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


""" Elliptic Curve and Point manipulation

.. moduleauthor:: Cédric Mesnil <cedric.mesnil@ubinity.com>

"""

#python 2 compatibility
from builtins import int,pow

import binascii
import random

from . import curve_defs




class Curve:
    """Elliptic Curve abstraction

    You should not directly create such Object.
    Use `get_curve` to get the predefined curve or create a well-know type
    of curve with your parameters

    Supported well know elliptic curve are:
       - Short Weierstrass form:  y²=x³+a*x+b
       - Twisted Edward           a*x²+y²=1+d*x²*y²
       - Montgomery:              b.y²=x³+a*x²+x.

    Attributes:
       name (str)       : curve name, the one given to get_curve or return by get_curve_names
       size (int)       : bit size of curve
       a (int)          : first curve parameter
       b d (int)        : second curve parameter
       field (int)      : curve field
       generator (Point): curve point generator
       order (int)      : order of generator

    """

    _curves_cache = {}


    @staticmethod
    def get_curve(name):
        """Return a Curve object  according to its name

       Args:
           name (str) : curve name to retrieve

       Returns:
           Curve:          Curve object, or None if curve is unknown
        """

        if name in Curve._curves_cache:
            return Curve._curves_cache[name]

        l = [c for c in curve_defs.curves if c['name']==name]
        if len(l) == 0:
            return None
        cp = l[0]
        if cp['type'] == curve_defs.WEIERSTRASS:
            cv = WeierstrassCurve(cp)
        elif cp['type'] == curve_defs.TWISTEDEDWARD:
            cv =  TwistedEdwardCurve(cp)
        elif cp['type'] == curve_defs.MONTGOMERY:
            cv = MontgomeryCurve(cp)
        else:
            cv = None

        if cv :
            Curve._curves_cache[name] = cv

        return cv

    @staticmethod
    def get_curve_names():
        """ Returns all known curve names

        Returns:
          tuple:  list of names as str
        """
        return [c['name'] for c in curve_defs.curves]


    def __init__(self, parameters):
        raise NotImplementedError('Abstract method __init__')

    def _set(self, params, keys):
        for k in keys :
            self._domain[k] = params[k]
        self._domain['name'] = str(self._domain['name'])
        x = self._domain['generator'][0]
        y = self._domain['generator'][1]
        self._domain['generator'] = Point(x,y,self)

        self._infinity_point = Point(0,0,self._domain['name'],False)
        self._infinity_point._at_infinity = True

    def __getattr__(self, name):
        if name in self._domain:
            return self._domain[name]
        raise AttributeError(name)

    def __str__(self):
        return str(self._domain).replace(',','\n')


    @property
    def infinity(self):
        return self._infinity_point

    def is_on_curve(self, P):
        """Check if P is on this curve

        This function ignores the default curve attach to P

        Args:
            P (Point): Point to check

        Returns:
            bool: True if P is on curve, False else

        """
        raise NotImplementedError('Abstract method is_on_curve')

    def add_point(self, P, Q):
        """ Returns the sum of P and Q

        Args:
            P (Point): first  point to add
            Q (Point): second point to add

        Returns:
            Point: A new Point R = P+Q

        Raises:
             ECPyException : with "Point not on curve", if Point R is not on \
             curve,  thus meaning either P or Q was not on.
        """
        return P+Q

    def sub_point(self, P, Q):
        """ Returns the difference of P and Q

        Args:
            P (Point): first  point to subtract with
            Q (Point): second point to subtract to

        Returns:
            Point: A new Point R = P-Q

        Raises:
             ECPyException : with "Point not on curve", if Point R is not on \
             curve,  thus meaning either P or Q was not on.
        """
        return P-Q

    def mul_point(self, k, P):
        """ Returns the scalar multiplication  P with k.

        This function ignores the default curve attach to P and Q,
        and assumes P and Q are on this curve.

        Args:
            P (Point): point to mul_point
            k (int)  : scalar to multiply

        Returns:
            Point: A new Point R = k*Q

        Raises:
            ECPyException : with "Point not on curve", if Point R is not
            on curve, thus meaning P was not on.
        """
        return k*P

    def neg_point(self, P):
        """ Returns R, R = -P.

        Args:
            P (Point): point to mul_point

        Returns:
            Point: A new Point R = -Q

        Raises:
            ECPyException : with "Point not on curve", if Point R is not
            on curve, thus meaning P was not on.

        """
        return -P

    def _add_point(self, P, Q):
        raise NotImplementedError('Abstract method add_point')

    def _mul_point(self, k, P):
        raise NotImplementedError('Abstract method mul_point')

    def _neg_point(self, P):
        raise NotImplementedError('Abstract method neg_point')


    def y_recover(self, x, sign=0):
        """ Recover the y coordinate according to x

        This method is currently only  supported for Weierstrass and Montgomery curve

        Args:
            x the coordinate
            sign the sign of y

        Returns:
           y coordinate

        """
        raise NotImplementedError('Abstract method y_recover')

    def x_recover(self, y, sign=0):
        """ Recover the x coordinate according to y

        This method is currently only supported for TwiestedEdward curve

        Args:
            y the coordinate
            sign the sign of x

        Returns:
           x coordinate
        """
        raise NotImplementedError('Abstract method x_recover')

    def encode_point(self, P):
        """ encode/compress a point according to its curve"""
        raise NotImplementedError('Abstract method encode_point')
        pass

    def decode_point(self, eP):
        """ decode/decompress a point according to its curve"""
        raise NotImplementedError('Abstract method _point decode_point')

        pass

    @staticmethod
    def _sqrt(n, p, sign=0):
        """ Generic Tonelli–Shanks algorithm """

        #check Euler criterion
        if pow(n,(p-1)//2,p) != 1:
            return None

        #compute square root
        p_1 = p-1
        s = 0
        q = p_1
        while q & 1 == 0:
            q = q>>1
            s  = s+1
        if s == 1:
            r = pow(n,(p+1)//4,p)
        else:
            z = 2
            while pow(z,(p-1)//2,p) == 1:
                z = z+1
            c = pow(z,q,p)
            r = pow(n,(q+1)//2,p)
            t = pow(n,q,p)
            m = s
            while True:
                if t == 1:
                    break
                else:
                    for i in range(1,m):
                        if pow(t,pow(2,i),p) == 1:
                            break
                    b = pow(c,pow(2,m-i-1),p)
                    r = (r*b)   %p
                    t = (t*b*b) %p
                    c = (b*b)   %p
                    m = i
        if sign:
            sign = 1
        if r&1 != sign:
            r = p-r
        return r


class WeierstrassCurve(Curve):
    """An elliptic curve defined by the equation: y²=x³+a*x+b.

        The given domain must be a dictionary providing the following keys/values:
              - name (str)         : curve unique name
              - size (int)         : bit size
              - a    (int)         : `a` equation coefficient
              - b    (int)         : `b` equation coefficient
              - field (inf)        : field value
              - generator (int[2]) : x,y coordinate of generator
              - order (int)        : order of generator
              - cofactor (int)     : cofactor

        *Note*: you should not use the constructor and only use :func:`Curve.get_curve`
        builder to ensure using supported curve.

        Args:
           domain (dict): a dictionary providing curve parameters

    """

    def __init__(self, domain):
        """ Built an new short Weierstrass curve with the provided parameters. """
        self._domain = {}
        self._set(domain, ('name','type', 'size',
                              'a','b','field','generator','order','cofactor'))


    def is_on_curve(self, P):
        """ See :func:`Curve.is_on_curve` """
        q     = self.field
        x     = P.x
        sq3x  = (x*x*x)%q
        y     = P.y
        sqy   = (y*y)%q
        left  = sqy
        right = (sq3x+self.a*x+self.b)%q
        return left == right


    def y_recover(self, x, sign=0):
        """ """
        p  = self.field
        y2 = (x*x*x + self.a*x + self.b)%p
        y  = self._sqrt(y2,p,sign)
        return y

    def encode_point(self, P, compressed=False):
        """ Encodes a point P according to *P1363-2000*.

        Args:
            P: point to encode

        Returns:
           bytes : encoded point [04 | x | y] or [02 | x | sign]
        """
        size = self.size+7 >> 3
        x = bytearray(P.x.to_bytes(size,'big'))
        y = bytearray(P.y.to_bytes(size,'big'))
        if compressed:
            enc = [2 | (P.y&1)]
            y = []
        else:
            enc = [4]
        enc.extend(x)
        enc.extend(y)
        return enc

    def decode_point(self, eP):
        """ Decodes a point P according to *P1363-2008*.

        Args:
            eP (bytes)    : encoded point
            curve (Curve) : curve on witch point is
        Returns:
           Point : decoded point
        """
        size = self.size+7 >> 3
        xy    =  bytearray(eP)
        if xy[0] == 2 or xy[0] == 3:
            x = xy[1:1+size]
            x = int.from_bytes(x,'big')
            y = self.y_recover(x,xy[0]&1)
        elif xy[0] == 4:
            x = xy[1:1+size]
            x = int.from_bytes(x,'big')
            y = xy[1+size:1+size+size]
            y = int.from_bytes(y,'big')
        else:
            raise ECPyException("Invalid encoded point")

        return Point(x,y,self,False)

    def _add_point(self, P, Q):
        """ See :func:`Curve.add_point` """
        q = self.field
        if (P == Q):
            Px,Py,Pz = self._aff2jac(P.x,P.y, q)
            x,y,z = self._dbl_jac(Px,Py,Pz, q,self.a)
        else:
            Px,Py,Pz = self._aff2jac(P.x,P.y, q)
            Qx,Qy,Qz = self._aff2jac(Q.x,Q.y, q)
            x,y,z = self._add_jac(Px,Py,Pz, Qx,Qy,Qz, q)

        if z:
            x,y = self._jac2aff(x,y,z, q)
            return  Point(x,y, self)
        else:
            return self.infinity

    def _mul_point(self, k, P):
        """ See :func:`Curve.mul_point` """
        q = self.field
        a = self.a
        x1,y1,z1 = self._aff2jac(P.x,P.y, q)
        k = bin(k)
        k = k[2:]
        sz = len(k)
        x2,y2,z2 = self._dbl_jac(x1,y1,z1, q,a)
        for i in range(1, sz):
            if k[i] == '1' :
                x1,y1,z1 = self._add_jac(x2,y2,z2, x1,y1,z1, q)
                x2,y2,z2 = self._dbl_jac(x2,y2,z2, q,a)
            else:
                x2,y2,z2 = self._add_jac(x1,y1,z1, x2,y2,z2, q)
                x1,y1,z1 = self._dbl_jac(x1,y1,z1, q,a)

        if z1:
            x,y = self._jac2aff(x1,y1,z1, q)
            return Point(x,y,self)
        else:
            return self.infinity

    def _neg_point(self, P):
        return Point(P.x,self.field-P.y,self)

    @staticmethod
    def _aff2jac(x,y, q):
        return(x,y,1)

    @staticmethod
    def _jac2aff(x,y,z, q):
        invz = pow(z,q-2,q)
        sqinvz = (invz*invz)%q
        x = (x*sqinvz)%q
        y = (y*sqinvz*invz)%q
        return (x,y)


    @staticmethod
    def _dbl_jac(X1,Y1,Z1, q, a):
        XX   = (X1*X1)%q
        YY   = (Y1*Y1)%q
        YYYY = (YY*YY)%q
        ZZ   = (Z1*Z1)%q
        S    = (2*((X1+YY)*(X1+YY)-XX-YYYY))%q
        M    = (3*XX+a*ZZ*ZZ)%q
        T    = (M*M-2*S)%q
        X3   = (T)%q
        Y3   = (M*(S-T)-8*YYYY)%q
        Z3   = ((Y1+Z1)*(Y1+Z1)-YY-ZZ)%q
        return X3,Y3,Z3

    @staticmethod
    def _add_jac(X1,Y1,Z1, X2,Y2,Z2, q):
        Z1Z1 = (Z1*Z1)%q
        Z2Z2 = (Z2*Z2)%q
        U1   = (X1*Z2Z2)%q
        U2   = (X2*Z1Z1)%q
        S1   = (Y1*Z2*Z2Z2)%q
        S2   = (Y2*Z1*Z1Z1)%q
        H    = (U2-U1)%q
        I    = ((2*H)*(2*H))%q
        J    = (H*I)%q
        r    = (2*(S2-S1))%q
        V    = (U1*I)%q
        X3   = (r*r-J-2*V)%q
        Y3   = (r*(V-X3)-2*S1*J)%q
        Z3   = (((Z1+Z2)*(Z1+Z2)-Z1Z1-Z2Z2)*H)%q
        return X3,Y3,Z3


class TwistedEdwardCurve(Curve):
    """An elliptic curve defined by the equation: a*x²+y²=1+d*x²*y²

        The given domain must be a dictionary providing the following keys/values:
              - name (str)         : curve unique name
              - size (int)         : bit size
              - a    (int)         : `a` equation coefficient
              - d    (int)         : `b` equation coefficient
              - field (inf)        : field value
              - generator (int[2]) : x,y coordinate of generator
              - order (int)        : order of generator

        *Note*: you should not use the constructor and only use :func:`Curve.get_curve`
        builder to ensure using supported curve.

        Args:
           domain (dict): a dictionary providing curve domain parameters
    """

    def __init__(self, domain):
        """ Built an new short twisted Edward curve with the provided parameters.  """
        self._domain = {}
        self._set(domain, ('name','type','size',
                              'a','d','field','generator','order'))

    def _coord_size(self):
        if self.name == 'Ed25519':
            size = 32
        elif self.name == 'Ed448':
            size = 57
        else:
            assert False, '%s not supported'%curve.name
        return size


    def is_on_curve(self, P):
        """ See :func:`Curve.is_on_curve` """
        q     = self.field
        x     = P.x
        sqx   = (x*x)%q
        y     = P.y
        sqy   = (y*y)%q
        left  = (self.a*sqx+sqy)%q
        right = (1+self.d*sqx*sqy)%q
        return left == right

    def x_recover(self, y, sign=0):
        """ Retrieves the x coordinate according to the y one, \
            such that point (x,y) is on curve.

        Args:
            y (int): y coordinate
            sign (int): sign of x

        Returns:
           int: the computed x coordinate
        """
        q = self.field
        a = self.a
        d = self.d
        if sign:
            sign = 1

        # #x2 = (y^2-1) * (d*y^2-a)^-1
        yy = (y*y)%q
        u = (1-yy)%q
        v = pow(a-d*yy,q-2,q)
        xx = (u*v)%q
        if self.name =='Ed25519':
            x = pow(xx,(q+3)//8,q)
            if (x*x - xx) % q != 0:
                I = pow(2,(q-1)//4,q)
                x = (x*I) % q
        elif self.name =='Ed448':
            x = pow(xx,(q+1)//4,q)
        else:
            assert False, '%s not supported'%curve.name

        if x &1 != sign:
            x = q-x

        assert (x*x)%q == xx


        # over F(q):
        #     a.xx +yy = 1+d.xx.yy
        # <=> xx(a-d.yy) = 1-yy
        # <=> xx = (1-yy)/(a-d.yy)
        # <=> x = +- sqrt((1-yy)/(a-d.yy))
        # yy   = (y*y)%q
        # u    = (1-yy)%q
        # v    = (a - d*yy)%q
        # v_1 = pow(v, q-2,q)
        # xx = (v_1*u)%q
        # x = self._sqrt(xx,q,sign) # Inherited generic Tonelli–Shanks from Curve
        return x

    def encode_point(self, P):
        """ Encodes a point P according to *draft_irtf-cfrg-eddsa-04*.

        Args:
            P: point to encode

        Returns:
           bytes : encoded point
        """
        size = self._coord_size()

        y = bytearray(P.y.to_bytes(size,'little'))
        if P.x&1:
            y[len(y)-1] |= 0x80
        return bytes(y)
    def decode_point(self, eP):
        """ Decodes a point P according to *draft_irtf-cfrg-eddsa-04*.

        Args:
            eP (bytes)    : encoded point
            curve (Curve) : curve on witch point is
        Returns:
           Point : decoded point
        """
        y    =  bytearray(eP)
        sign = y[len(y)-1] & 0x80
        y[len(y)-1] &= ~0x80
        y = int.from_bytes(y,'little')
        x = self.x_recover(y,sign)
        return Point(x,y,self,True)

    @staticmethod
    def decode_scalar_25519(k):
        """ decode scalar according to RF7748 and draft-irtf-cfrg-eddsa

        Args:
               k (bytes) : scalar to decode

        Returns:
              int: decoded scalar
        """
        k = bytearray(k)
        k[0]  &= 0xF8
        k[31] = (k[31] &0x7F) | 0x40
        k = bytes(k)
        k = int.from_bytes(k,'little')
        return k

    @staticmethod
    def encode_scalar_25519(k):
        """ encode scalar according to RF7748 and draft-irtf-cfrg-eddsa

        Args:
               k (int) : scalar to encode

        Returns:
              bytes: encoded scalar
        """
        k.to_bytes(32,'little')
        k = bytearray(k)
        k[0]  &= 0xF8
        k[31] = (k[31] &0x7F) | 0x40
        k = bytes(k)
        return k

    def _add_point(self, P, Q):
        """ See :func:`Curve.add_point` """
        q = self.field
        a = self.a
        if (P == Q):
            Px,Py,Pz,Pt = self._aff2ext(P.x,P.y, q)
            x,y,z,t     = self._dbl_ext(Px,Py,Pz,Pt, q,self.a)
        else:
            Px,Py,Pz,Pt = self._aff2ext(P.x,P.y, q)
            Qx,Qy,Qz,Qt = self._aff2ext(Q.x,Q.y, q)
            x,y,z,t     = self._add_ext(Px,Py,Pz,Pt, Qx,Qy,Qz,Qt, q,a)

        if z:
            x,y = self._ext2aff(x,y,z,t, q)
            return Point(x,y, self)
        else:
            return self.infinity

    def _mul_point(self, k, P):
        """ See :func:`Curve.add_point` """
        q = self.field
        a = self.a
        x1,y1,z1,t1 = self._aff2ext(P.x,P.y, q)
        k = bin(k)
        k = k[2:]
        sz = len(k)
        x2,y2,z2,t2 = self._dbl_ext(x1,y1,z1,t1, q,a)
        for i in range(1, sz):
            if k[i] == '1' :
                x1,y1,z1,t1 = self._add_ext(x2,y2,z2,t2, x1,y1,z1,t1, q,a)
                x2,y2,z2,t2 = self._dbl_ext(x2,y2,z2,t2, q,a)
            else:
                x2,y2,z2,t2 = self._add_ext(x1,y1,z1,t1, x2,y2,z2,t2, q,a)
                x1,y1,z1,t1 = self._dbl_ext(x1,y1,z1,t1, q,a)
        if z1:
            x,y = self._ext2aff(x1,y1,z1,t1, q)
            return Point(x,y,self)
        else:
            return self.infinity

    def _neg_point(self, P):
        return Point(self.field-P.x,P.y,self)

    @staticmethod
    def _aff2ext(x, y, q):
        z = 1
        t = (x*y*z) % q
        x = (x*z) % q
        y = (y*z) % q
        return (x,y,z,t)

    @staticmethod
    def _ext2aff(x,y,z,xy, q):
        invz = pow(z,q-2,q)
        x = (x*invz)%q
        y = (y*invz)%q
        return (x,y)

    @staticmethod
    def _dbl_ext(X1,Y1,Z1,XY1, q,a):
        A  = (X1*X1)%q
        B  = (Y1*Y1)%q
        C  = (2*Z1*Z1)%q
        D  = (a*A)%q
        E  = ((X1+Y1)*(X1+Y1)-A-B)%q
        G  = (D+B)%q
        F  = (G-C)%q
        H  = (D-B)%q
        X3  = (E*F)%q
        Y3  = (G*H)%q
        XY3 = (E*H)%q
        Z3  = (F*G)%q
        return (X3,Y3,Z3,XY3)

    @staticmethod
    def _add_ext(X1,Y1,Z1,XY1,  X2,Y2,Z2,XY2, q,a):
        A = (X1*X2)%q
        B = (Y1*Y2)%q
        C = (Z1*XY2)%q
        D = (XY1*Z2)%q
        E = (D+C)%q
        t0 = (X1-Y1)%q
        t1 = (X2+Y2)%q
        t2 = (t0*t1)%q
        t3 = (t2+B)%q
        F = (t3-A)%q
        t4 = (a*A)%q
        G = (B+t4)%q
        H = (D-C)%q
        X3 = (E*F)%q
        Y3 = (G*H)%q
        XY3 = (E*H)%q
        Z3 = (F*G)%q
        return (X3,Y3,Z3,XY3)


class MontgomeryCurve(Curve):
    """An elliptic curve defined by the equation: b.y²=x³+a*x²+x.

        The given domain must be a dictionary providing the following keys/values:
              - name (str)         : curve unique name
              - size (int)         : bit size
              - a    (int)         : `a` equation coefficient
              - b    (int)         : `b` equation coefficient
              - field (inf)        : field value
              - generator (int[2]) : x,y coordinate of generator
              - order (int)        : order of generator

        *Note*: you should not use the constructor and only use :func:`Curve.get_curve`
        builder to ensure using supported curve.

        Args:
           domain (dict): a dictionary providing curve domain parameters
    """

    def __init__(self, domain):
        """ Built an new short twisted Edward curve with the provided parameters.  """
        self._domain = {}
        self._set(domain, ('name','type','size',
                           'a','b','field','generator','order'))
        #inv4 = pow(4,p-2,p)
        #self.a24  = ((self.a+2)*inv4)%p
        self.a24  = (self.a+2)//4

    def is_on_curve(self, P):
        """ See :func:`Curve.is_on_curve` """
        p = self.field
        x = P.x
        right = (x*x*x + self.a*x*x + x)%p
        if P.has_y:
            y     = P.y
            left  = (self.b*y*y)%p
            return left == right
        else:
            #check equation has a solution according to Euler criterion
            return pow(right,(p-1)//2, p) == 1

    def y_recover(self, x, sign=0):
        """ """
        p  = self.field
        by2 = (x*x*x + self.a*x*x + x)%p
        binv = pow(self.b, p-2,p)
        assert((binv*self.b)%p == 1)
        y2 = (binv*by2)%p
        y  = self._sqrt(y2,p,sign)

        return y

    def encode_point(self, P):
        """ Encodes a point P according to *RFC7748*.

        Args:
            P: point to encode

        Returns:
           bytes : encoded point
        """
        size = self.size+7 >> 3
        x = bytearray(P.x.to_bytes(size,'little'))
        return bytes(x)

    def decode_point(self, eP):
        """ Decodes a point P according to *RFC7748*.

        Args:
            eP (bytes)    : encoded point
            curve (Curve) : curve on witch point is
        Returns:
           Point : decoded point
        """
        x    =  bytearray(eP)
        x[len(x)-1] &= ~0x80
        x = int.from_bytes(x,'little')
        return Point(x,None,self)

    def _add_point(self, P, Q):
        """ See :func:`Curve.add_point` """
        if Q.has_y and P == -Q:
            return self.infinity

        if P == Q:
            return self._mul_point(2,P)

        x1 = P.x
        y1 = P.y
        x2 = Q.x
        y2 = Q.y
        p = self.field
        assert(x2!=x1)

        invx2x1   = pow(((x2-x1))                %p, p-2, p)
        invx2x1_2 = pow(((x2-x1)*(x2-x1))        %p, p-2, p)
        invx2x1_3 = pow(((x2-x1)*(x2-x1)*(x2-x1))%p, p-2, p)

        #x3 =
        #      b*(y2-y1)²    /(x2-x1)²       -a-x1-x2
        x3 = ( self.b*pow(y2-y1,2)*invx2x1_2 -self.a-x1-x2 ) %p
        # y3 =
        #      (2*x1+x2+a)*(y2-y1)/(x2-x1)      - b*(y2-y1)³         /(x2-x1)³  -y1
        y3 = ( (2*x1+x2+self.a)*(y2-y1)*invx2x1 - self.b*pow(y2-y1,3)*invx2x1_3 -y1 ) %p

        return Point(x3,y3,self)

    def _mul_point(self, k, P):
        """  """
        k = bin(k)
        k = k[2:]
        sz = len(k)
        x1 = P.x
        x2 = 1
        z2 = 0
        x3 = P.x
        z3 = 1
        for i in range(0, sz):
            ki = int(k[i])
            if ki == 1:
                x3,z3, x2,z2 = self._ladder_step(x1, x3,z3, x2,z2)
            else:
                x2,z2, x3,z3 = self._ladder_step(x1, x2,z2, x3,z3)

        p = self.field
        if z2:
            y2 = None
            if (P.has_y):
                x2,y2,z2 = self._ladder_recover_y(P.x,P.y, x2,z2, x3,z3)
            zinv = pow(z2,(p - 2),p)
            kx = (x2*zinv)%p
            ky = None
            if y2:
                ky = (y2*zinv)%p
            return Point (kx, ky, self)
        else:
            return self.infinity

    def _neg_point(self, P):
        return Point(P.x,self.field-P.y,self)

    def _ladder_step(self, x_qp, x_p, z_p, x_q, z_q):
        p    = self.field

        t1   = (x_p + z_p)              %p
        t6   = (t1  * t1)               %p
        t2   = (x_p - z_p)              %p
        t7   = (t2  * t2)               %p
        t5   = (t6  - t7)               %p
        t3   = (x_q + z_q)              %p
        t4   = (x_q - z_q)              %p
        t8   = (t4  * t1)               %p
        t9   = (t3  * t2)               %p

        x_pq = ((t8+t9)*(t8+t9))        %p
        z_pq = (x_qp*(t8-t9)*(t8-t9))   %p
        x_2p = (t6*t7)%p                %p
        z_2p = (t5*(t7+self.a24*t5))    %p

        return (x_2p, z_2p, x_pq, z_pq)

    def _ladder_recover_y(self, xp,yp, xq,zq, xa, za):
        p    = self.field

        v1 = (xp*zq)         %p
        v2 = (xq+v1)         %p
        v3 = (xq-v1)         %p
        v3 = (v3*v3)         %p
        v3 = (v3*xa)         %p
        v1 = (2*self.a*zq)   %p

        v2 = (v2+v1)         %p
        v4 = (xp*xq)         %p
        v4 = (v4+zq)         %p
        v2 = (v2*v4)         %p
        v1 = (v1*zq)         %p
        v2 = (v2-v1)         %p
        v2 = (v2*za)         %p

        y  = (v2-v3)         %p
        v1 = (2*self.b*yp)   %p
        v1 = (v1*zq)         %p
        v1 = (v1*za)         %p
        x  = (v1*xq)         %p
        z  = (v1*zq)         %p

        return (x,y,z)

class Point:
    """Immutable Elliptic Curve Point.

    A Point support the following operator:

        - `-` : Point Subtraction.
        - `+` : Point Addition, with automatic doubling support.
        - `*` : Scalar multiplication, can write as k*P or P*k, with P :class:Point and  k :class:int.
        - `==`: Point comparison.
        - `-` : Point negation (unary operator).

    Attributes:
        x (int)       : Affine x coordinate
        y (int)       : Affine y coordinate
        curve (Curve) : Curve on which the point is define
        check(bool)   : Check or not if the built point is on curve

    Args:
        x (int) :     x coordinate
        y (int) :     y coordinate
        check (bool): if True enforce x,y is on curve

    Raises:
        ECPyException : if check=True and x,y is not on curve
    """

    __slots__ = '_x', '_y', '_curve', '_at_infinity'

    @staticmethod
    def infinity():
        """ Return the unique (singleton) point at infinity

        Returns:
                Point : infinity Point
        """
        return _infinity_point

    def __init__(self, x,y, curve, check=True):

        self._x = None
        self._y = None
        self._at_infinity = False
        self._curve = curve
        if x != None:
            self._x = int(x)
        if y != None:
            self._y = int(y)
        if check and not curve.is_on_curve(self):
            raise ECPyException("Point not on curve")

    @property
    def is_infinity(self):
        """ Tell is this pointn is the inifinity one

        Returns:
            bool: true if self is infinity
        """
        return self._at_infinity

    @property
    def x(self):
        """ X affine coordinate of this point

            Returns:
                x coordinate

            Raises:
                ECPyException: if point is infinity
                ECPyException: if point has no x coordinate
        """
        if self.is_infinity:
            raise ECPyException('Infinity')
        if self._x == None:
            raise ECPyException('x coordinate not set')
        return self._x

    @property
    def y(self):
        """ Y affine coordinate of this point

            Returns:
                x coordinate

            Raises:
                ECPyException: if point is infinity
                ECPyException: if point has no y coordinate
        """
        if self.is_infinity:
            raise ECPyException('Infinity')
        if self._y == None:
            raise ECPyException('y coordinate not set')
        return self._y

    @property
    def has_x(self):
        """ Tell if this point has y coordinate

            Returns:
                Trueu if x coordinate is set, False else
        """
        return self._x != None

    @property
    def has_y(self):
        """ Tell if this point has y coordinate

            Returns:
                Trueu if y coordinate is set, False else
        """
        return self._y != None

    @property
    def curve(self):
        """ Returned the curve on which this point is defined

            Returns:
                Curve: this point curve
        """
        return self._curve

    @property
    def is_on_curve(self):
        """" Tells if this point is on the curve

            Returns:
                bool: True if point on curve, False else
        """
        return self.curve.is_on_curve(self)

    def recover(self, sign = 0):
        """ Recvoer the missing corrdinate according to the know one and the provided sign of the missing one

            Args:
                sign (int): zero or one
        """

        if self.is_infinity:
            return
        if self._y == None:
            self._y = self.curve.y_recover(self._x, sign)
        if self._x == None:
            self._x = self.curve.x_recover(self._y, sign)

    def __add__(self, Q):
        if isinstance(Q,Point) :
            if self.is_infinity:
                return Q
            if Q.is_infinity:
                return self
            if self._curve.name != Q._curve.name:
                raise ECPyException('__add__: points on same curve')
            return self.curve._add_point(self,Q)
        raise ECPyException('__add__: type not supported: %s'%type(Q))

    def __sub__(self, Q):
        if isinstance(Q,Point) :
            if self.is_infinity:
                return -Q
            if Q.is_infinity:
                return self
            if self._curve.name != Q._curve.name:
                raise ECPyException('__sub__: points on same curve')
            return self.curve._add_point(self,-Q)
        raise ECPyException('__sub__: type not supported: %s'%type(Q))

    def __mul__(self, scal):
        if isinstance(scal,int):
            if self.is_infinity:
                return self
            scal = scal%self.curve.order
            if scal == 0:
                return Point.infinity()
            return self.curve._mul_point(scal,self)
        raise ECPyException('__mul__: type not supported: %s'%type(scal))

    def __rmul__(self,scal) :
        return self.__mul__(scal)

    def __neg__(self):
        if self.is_infinity:
            return self
        return self.curve._neg_point(self)

    def __eq__(self,Q):
        if isinstance(Q,Point) :
            if self.is_infinity and Q.is_infinity:
                return True
            if self.is_infinity or Q.is_infinity:
                return False
            return (self._curve.name == Q._curve.name  and
                    self._x == Q._x and
                    self._y == Q._y)
        raise NotImplementedError('eq: type not supported: %s'%(type(Q)))

    def __str__(self):
        if self.is_infinity:
            return "inf"
        s = ""
        if self.has_x and self.has_y:
            return "(0x%x , 0x%x)" % (self._x,self._y)
        elif self.has_x:
            return "(0x%x , .)" % (self._x)
        elif self.has_y:
            return "(. , 0x%x)" % (self._y)
        else:
            return "(. , .)"

    def add(self, Q):
        """ Return the addition of self and provided point.

            Args:
                Q(Point): Point to add

            Returns:
                Point: self+Q
        """
        return self.__add__(Q)

    def sub(self, Q):
        """ Return the subtraction of felf and provided point.

            Args:
                Q(Point): Point to subtract

            Returns:
                Point: self-Q
        """
        return self.__sub__(Q)

    def mul(self, k):
        """ Return the scalar multiplication of self by k

            Args:
                k(int): the scalar to multiply

            Returns:
                Point: k*self
        """
        return self.__mul__(k)

    def neg(self):
        """ Return the opposite self point bycallinf Curve.neg function

            Returns:
                Point: -self
        """
        return self.__neg__()

    def eq(self,Q):
        """ Tells is the provided Point and this point have the same coordinate.

            Args:
                Q(Point): Point to check the equality

            Returns:
                bool: True if P==Q, False else.
        """
        return self.__eq__(Q)

_infinity_point = Point(0,0,None,False)
_infinity_point._at_infinity = True


class ECPyException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return rept(self.value)







if __name__ == "__main__":
    try:
        ###############################
        ### Weierstrass quick check ###
        ###############################
        cv  = Curve.get_curve('secp256k1')

        #check generator
        Gx = 0x79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798
        Gy = 0x483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8
        G = Point(Gx, Gy, cv)
        assert(G == cv.generator)

        #define point
        W1 = Point(0x6fb13b7e8ab1c7d191d16197c1bf7f8dc7992412e1266155b3fb3ac8b30f3ed8,
                   0x2e1eb77bd89505113819600b395e0475d102c4788a3280a583d9d82625ed8533,
                   cv)
        W2 = Point(0x07cd9ee748a0b26773d9d29361f75594964106d13e1cad67cfe2df503ee3e90e,
                   0xd209f7c16cdb6d3559bea88c7d920f8ff077406c615da8adfecdeef604cb40a6,
                   cv)

        #check add
        sum_W1_W2 = Point(0xc4a20cbc2dc27c70fbc1335292c109a1ccd106981b5698feafe702bcb0fb2fca,
                          0x7e1ad514051b87b7ce815c7defcd4fcc01e88842b3135e10a342be49bf5cad09,
                          cv)
        dbl_W2 = Point(0xb4f211b11166e6b3a3561e5978f47855787943dbeccd2014706c941a5890c913,
                       0xe0122dc6f3ce097eb73865e66a1ced02a518afdec02596d7d152f121391e2d63,
                       cv)

        s = W1+W2
        assert(s == sum_W1_W2)
        d = W2+W2
        assert(d == dbl_W2)

        #check mul
        k = 0x2976F786AE6333E125C0DFFD6C16D37E8CED5ABEDB491BCCA21C75B307D0B318
        kW1 = Point(0x1de93c28f8c58db95f30be1704394f6f5d4602291c4933a1126cc61f9ed70b88,
                    0x6f66df7bb6b37609cacded3052e1d127b47684949dff366020f824d517d66f34,
                    cv)
        mulW1 = k*W1
        assert(kW1 == mulW1)

        #check encoding
        W2_enc = [ 0x04,
                   #x
                   0x07, 0xcd, 0x9e, 0xe7, 0x48, 0xa0, 0xb2, 0x67, 0x73, 0xd9, 0xd2, 0x93, 0x61, 0xf7, 0x55, 0x94,
                   0x96, 0x41, 0x06, 0xd1, 0x3e, 0x1c, 0xad, 0x67, 0xcf, 0xe2, 0xdf, 0x50, 0x3e, 0xe3, 0xe9, 0x0e,
                #y
                   0xd2, 0x09, 0xf7, 0xc1, 0x6c, 0xdb, 0x6d, 0x35, 0x59, 0xbe, 0xa8, 0x8c, 0x7d, 0x92, 0x0f, 0x8f,
                   0xf0, 0x77, 0x40, 0x6c, 0x61, 0x5d, 0xa8, 0xad, 0xfe, 0xcd, 0xee, 0xf6, 0x04, 0xcb, 0x40, 0xa6]
        dW2_enc = [ 0x04,
                    #x
                    0xb4, 0xf2, 0x11, 0xb1, 0x11, 0x66, 0xe6, 0xb3, 0xa3, 0x56, 0x1e, 0x59, 0x78, 0xf4, 0x78, 0x55,
                    0x78, 0x79, 0x43, 0xdb, 0xec, 0xcd, 0x20, 0x14, 0x70, 0x6c, 0x94, 0x1a, 0x58, 0x90, 0xc9, 0x13,
                    #y
                    0xe0, 0x12, 0x2d, 0xc6, 0xf3, 0xce, 0x09, 0x7e, 0xb7, 0x38, 0x65, 0xe6, 0x6a, 0x1c, 0xed, 0x02,
                0xa5, 0x18, 0xaf, 0xde, 0xc0, 0x25, 0x96, 0xd7, 0xd1, 0x52, 0xf1, 0x21, 0x39, 0x1e, 0x2d, 0x63]
        W2_enc_comp = [ 0x02,
                        #x
                        0x07, 0xcd, 0x9e, 0xe7, 0x48, 0xa0, 0xb2, 0x67, 0x73, 0xd9, 0xd2, 0x93, 0x61, 0xf7, 0x55, 0x94,
                        0x96, 0x41, 0x06, 0xd1, 0x3e, 0x1c, 0xad, 0x67, 0xcf, 0xe2, 0xdf, 0x50, 0x3e, 0xe3, 0xe9, 0x0e,
                        #y sign
                        #0
                        ]
        dW2_enc_comp = [ 0x03,
                        #x²
                         0xb4, 0xf2, 0x11, 0xb1, 0x11, 0x66, 0xe6, 0xb3, 0xa3, 0x56, 0x1e, 0x59, 0x78, 0xf4, 0x78, 0x55,
                         0x78, 0x79, 0x43, 0xdb, 0xec, 0xcd, 0x20, 0x14, 0x70, 0x6c, 0x94, 0x1a, 0x58, 0x90, 0xc9, 0x13,
                        #y
                        # 1
                        ]

        P = cv.encode_point(W2)
        assert(P == W2_enc)
        P = cv.decode_point(P)
        assert(P == W2)

        P = cv.encode_point(dbl_W2)
        assert(P == dW2_enc)
        P = cv.decode_point(P)
        assert(P == dbl_W2)

        P = cv.encode_point(W2,True)
        assert(P == W2_enc_comp)
        P = cv.decode_point(P)
        assert(P == W2)

        P = cv.encode_point(dbl_W2,True)
        assert(P == dW2_enc_comp)
        P = cv.decode_point(P)
        assert(P == dbl_W2)


        ##################################
        ### Twisted Edward quick check ###
        ##################################
        cv  = Curve.get_curve('Ed25519')

        W1 = Point(0x36ab384c9f5a046c3d043b7d1833e7ac080d8e4515d7a45f83c5a14e2843ce0e,
                   0x2260cdf3092329c21da25ee8c9a21f5697390f51643851560e5f46ae6af8a3c9,
                   cv)
        W2 = Point(0x67ae9c4a22928f491ff4ae743edac83a6343981981624886ac62485fd3f8e25c,
                   0x1267b1d177ee69aba126a18e60269ef79f16ec176724030402c3684878f5b4d4,
                   cv)

        #check generator
        Bx = 15112221349535400772501151409588531511454012693041857206046113283949847762202
        By = 46316835694926478169428394003475163141307993866256225615783033603165251855960
        B = Point(Bx, By, cv)
        assert(B == cv.generator)

        #check add
        sum_W1_W2 = Point(0x49fda73eade3587bfcef7cf7d12da5de5c2819f93e1be1a591409cc0322ef233,
                          0x5f4825b298feae6fe02c6e148992466631282eca89430b5d10d21f83d676c8ed,

                          cv)
        dbl_W1 = Point(0x203da8db56cff1468325d4b87a3520f91a739ec193ce1547493aa657c4c9f870,
                       0x47d0e827cb1595e1470eb88580d5716c4cf22832ea2f0ff0df38ab61ca32112f,
                       cv)

        s = W1+W2
        assert(s == sum_W1_W2)
        d = W1+W1
        assert(d == dbl_W1)

        #check mul
        A = Point(0x74ad28205b4f384bc0813e6585864e528085f91fb6a5096f244ae01e57de43ae,
                  0x0c66f42af155cdc08c96c42ecf2c989cbc7e1b4da70ab7925a8943e8c317403d,
                  cv)
        k  = 0x035ce307f6524510110b4ea1c8af0e81fb705118ebcf886912f8d2d87b5776b3
        kA = Point(0x0d968dd46de0ff98f4a6916e60f84c8068444dbc2d93f5d3b9cf06dade04a994,
                   0x3ba16a015e1dd42b3d088c7a68c344ec47aaba463f67f4e9099c634f64781e00,
                   cv)
        mul = k*A
        assert(mul == kA)


        ##################################
        ### Montgomery quick check ###
        ##################################

        cv     = Curve.get_curve('Curve25519')
        eP =  binascii.unhexlify("e3712d851a0e5d79b831c5e34ab22b41a198171de209b8b8faca23a11c624859")
        _P  = cv.decode_point(eP)
        assert(_P.x == 0x5948621ca123cafab8b809e21d1798a1412bb24ae3c531b8795d0e1a852d71e3)
        _eP = cv.encode_point(_P)
        assert(_eP == eP)

        eQ = binascii.unhexlify("b5bea823d9c9ff576091c54b7c596c0ae296884f0e150290e88455d7fba6126f")
        _Q  = cv.decode_point(eQ)
        assert(_Q.x == 0x6f12a6fbd75584e89002150e4f8896e20a6c597c4bc5916057ffc9d923a8beb5)
        _eQ = cv.encode_point(_Q)
        assert(_eQ == eQ)

        #0x449a44ba44226a50185afcc10a4c1462dd5e46824b15163b9d7c52f06be346a0
        k = binascii.unhexlify("a546e36bf0527c9d3b16154b82465edd62144c0ac1fc5a18506a2244ba449ac4")
        k = TwistedEdwardCurve.decode_scalar_25519(k)
        assert(k == 0x449a44ba44226a50185afcc10a4c1462dd5e46824b15163b9d7c52f06be346a0)

        eP =  binascii.unhexlify("e6db6867583030db3594c1a424b15f7c726624ec26b3353b10a903a6d0ab1c4c")
        P  = cv.decode_point(eP)
        assert(P.x == 34426434033919594451155107781188821651316167215306631574996226621102155684838)

        eQ = binascii.unhexlify("c3da55379de9c6908e94ea4df28d084f32eccf03491c71f754b4075577a28552")
        Q  = cv.decode_point(eQ)

        kP = k*P
        assert(kP.x == Q.x)
        ekP =  cv.encode_point(kP)
        assert(ekP == eQ)

        #------------

        eG =  binascii.unhexlify("09")
        G  = cv.decode_point(eG)

        #a8abababababababababababababababababababababababababababababab6b
        k1 = binascii.unhexlify("a8abababababababababababababababababababababababababababababab6b")
        k1 = TwistedEdwardCurve.decode_scalar_25519(k1)


        eQ1 = binascii.unhexlify("e3712d851a0e5d79b831c5e34ab22b41a198171de209b8b8faca23a11c624859")
        Q1  = cv.decode_point(eQ1)

        k1G = k1*G
        assert(k1G.x == Q1.x)
        ek1G =  cv.encode_point(k1G)
        assert(ek1G == eQ1)

        #c8cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd4d
        k2 = binascii.unhexlify("c8cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd4d")
        k2 = TwistedEdwardCurve.decode_scalar_25519(k2)

        eQ2 = binascii.unhexlify("b5bea823d9c9ff576091c54b7c596c0ae296884f0e150290e88455d7fba6126f")
        Q2  = cv.decode_point(eQ2)

        k2G = k2*G
        assert(k2G.x == Q2.x)
        ek2G =  cv.encode_point(k2G)
        assert(ek2G == eQ2)


        #Check xy multiplication
        G = Point(cv.generator.x, cv.generator.y, cv)
        k1G = k1*G
        assert(k1G.x == Q1.x)
        assert(k1G.has_y)

        G = Point(cv.generator.x, cv.generator.y, cv)
        k2G = k2*G
        assert(k2G.x == Q2.x)
        assert(k2G.has_y)

        #Check xy addition
        W1 = (k1+k2)*G
        W2 = k1G+k2G
        assert(W1.x == W2.x)
        assert(W1.y == W2.y)

        dblG = 2*G
        GG = G+G
        assert(GG == dblG)

        trpG = 3*G
        GGG = GG+G
        assert(GGG == trpG)

        ##OK!
        print("All internal assert OK!")
    finally:
        pass
