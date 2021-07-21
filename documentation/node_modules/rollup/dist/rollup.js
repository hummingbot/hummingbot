/*
  @license
	Rollup.js v1.23.1
	Sat, 05 Oct 2019 06:08:56 GMT - commit 53266e6b971fff985b273800d808b17084d5c41b


	https://github.com/rollup/rollup

	Released under the MIT License.
*/
'use strict';

Object.defineProperty(exports, '__esModule', { value: true });

var index = require('./shared/index.js');
var util = require('util');
var path = require('path');
var fs = require('fs');
var acorn = require('acorn');
var events = require('events');
require('module');

/*! *****************************************************************************
Copyright (c) Microsoft Corporation. All rights reserved.
Licensed under the Apache License, Version 2.0 (the "License"); you may not use
this file except in compliance with the License. You may obtain a copy of the
License at http://www.apache.org/licenses/LICENSE-2.0

THIS CODE IS PROVIDED ON AN *AS IS* BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, EITHER EXPRESS OR IMPLIED, INCLUDING WITHOUT LIMITATION ANY IMPLIED
WARRANTIES OR CONDITIONS OF TITLE, FITNESS FOR A PARTICULAR PURPOSE,
MERCHANTABLITY OR NON-INFRINGEMENT.

See the Apache Version 2.0 License for specific language governing permissions
and limitations under the License.
***************************************************************************** */
function __awaiter(thisArg, _arguments, P, generator) {
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try {
            step(generator.next(value));
        }
        catch (e) {
            reject(e);
        } }
        function rejected(value) { try {
            step(generator["throw"](value));
        }
        catch (e) {
            reject(e);
        } }
        function step(result) { result.done ? resolve(result.value) : new P(function (resolve) { resolve(result.value); }).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
}

var minimalisticAssert = assert;
function assert(val, msg) {
    if (!val)
        throw new Error(msg || 'Assertion failed');
}
assert.equal = function assertEqual(l, r, msg) {
    if (l != r)
        throw new Error(msg || ('Assertion failed: ' + l + ' != ' + r));
};

var inherits_browser = index.createCommonjsModule(function (module) {
    if (typeof Object.create === 'function') {
        // implementation from standard node.js 'util' module
        module.exports = function inherits(ctor, superCtor) {
            ctor.super_ = superCtor;
            ctor.prototype = Object.create(superCtor.prototype, {
                constructor: {
                    value: ctor,
                    enumerable: false,
                    writable: true,
                    configurable: true
                }
            });
        };
    }
    else {
        // old school shim for old browsers
        module.exports = function inherits(ctor, superCtor) {
            ctor.super_ = superCtor;
            var TempCtor = function () { };
            TempCtor.prototype = superCtor.prototype;
            ctor.prototype = new TempCtor();
            ctor.prototype.constructor = ctor;
        };
    }
});

var inherits = index.createCommonjsModule(function (module) {
    try {
        var util$1 = util;
        if (typeof util$1.inherits !== 'function')
            throw '';
        module.exports = util$1.inherits;
    }
    catch (e) {
        module.exports = inherits_browser;
    }
});

var inherits_1 = inherits;
function isSurrogatePair(msg, i) {
    if ((msg.charCodeAt(i) & 0xFC00) !== 0xD800) {
        return false;
    }
    if (i < 0 || i + 1 >= msg.length) {
        return false;
    }
    return (msg.charCodeAt(i + 1) & 0xFC00) === 0xDC00;
}
function toArray(msg, enc) {
    if (Array.isArray(msg))
        return msg.slice();
    if (!msg)
        return [];
    var res = [];
    if (typeof msg === 'string') {
        if (!enc) {
            // Inspired by stringToUtf8ByteArray() in closure-library by Google
            // https://github.com/google/closure-library/blob/8598d87242af59aac233270742c8984e2b2bdbe0/closure/goog/crypt/crypt.js#L117-L143
            // Apache License 2.0
            // https://github.com/google/closure-library/blob/master/LICENSE
            var p = 0;
            for (var i = 0; i < msg.length; i++) {
                var c = msg.charCodeAt(i);
                if (c < 128) {
                    res[p++] = c;
                }
                else if (c < 2048) {
                    res[p++] = (c >> 6) | 192;
                    res[p++] = (c & 63) | 128;
                }
                else if (isSurrogatePair(msg, i)) {
                    c = 0x10000 + ((c & 0x03FF) << 10) + (msg.charCodeAt(++i) & 0x03FF);
                    res[p++] = (c >> 18) | 240;
                    res[p++] = ((c >> 12) & 63) | 128;
                    res[p++] = ((c >> 6) & 63) | 128;
                    res[p++] = (c & 63) | 128;
                }
                else {
                    res[p++] = (c >> 12) | 224;
                    res[p++] = ((c >> 6) & 63) | 128;
                    res[p++] = (c & 63) | 128;
                }
            }
        }
        else if (enc === 'hex') {
            msg = msg.replace(/[^a-z0-9]+/ig, '');
            if (msg.length % 2 !== 0)
                msg = '0' + msg;
            for (i = 0; i < msg.length; i += 2)
                res.push(parseInt(msg[i] + msg[i + 1], 16));
        }
    }
    else {
        for (i = 0; i < msg.length; i++)
            res[i] = msg[i] | 0;
    }
    return res;
}
var toArray_1 = toArray;
function toHex(msg) {
    var res = '';
    for (var i = 0; i < msg.length; i++)
        res += zero2(msg[i].toString(16));
    return res;
}
var toHex_1 = toHex;
function htonl(w) {
    var res = (w >>> 24) |
        ((w >>> 8) & 0xff00) |
        ((w << 8) & 0xff0000) |
        ((w & 0xff) << 24);
    return res >>> 0;
}
var htonl_1 = htonl;
function toHex32(msg, endian) {
    var res = '';
    for (var i = 0; i < msg.length; i++) {
        var w = msg[i];
        if (endian === 'little')
            w = htonl(w);
        res += zero8(w.toString(16));
    }
    return res;
}
var toHex32_1 = toHex32;
function zero2(word) {
    if (word.length === 1)
        return '0' + word;
    else
        return word;
}
var zero2_1 = zero2;
function zero8(word) {
    if (word.length === 7)
        return '0' + word;
    else if (word.length === 6)
        return '00' + word;
    else if (word.length === 5)
        return '000' + word;
    else if (word.length === 4)
        return '0000' + word;
    else if (word.length === 3)
        return '00000' + word;
    else if (word.length === 2)
        return '000000' + word;
    else if (word.length === 1)
        return '0000000' + word;
    else
        return word;
}
var zero8_1 = zero8;
function join32(msg, start, end, endian) {
    var len = end - start;
    minimalisticAssert(len % 4 === 0);
    var res = new Array(len / 4);
    for (var i = 0, k = start; i < res.length; i++, k += 4) {
        var w;
        if (endian === 'big')
            w = (msg[k] << 24) | (msg[k + 1] << 16) | (msg[k + 2] << 8) | msg[k + 3];
        else
            w = (msg[k + 3] << 24) | (msg[k + 2] << 16) | (msg[k + 1] << 8) | msg[k];
        res[i] = w >>> 0;
    }
    return res;
}
var join32_1 = join32;
function split32(msg, endian) {
    var res = new Array(msg.length * 4);
    for (var i = 0, k = 0; i < msg.length; i++, k += 4) {
        var m = msg[i];
        if (endian === 'big') {
            res[k] = m >>> 24;
            res[k + 1] = (m >>> 16) & 0xff;
            res[k + 2] = (m >>> 8) & 0xff;
            res[k + 3] = m & 0xff;
        }
        else {
            res[k + 3] = m >>> 24;
            res[k + 2] = (m >>> 16) & 0xff;
            res[k + 1] = (m >>> 8) & 0xff;
            res[k] = m & 0xff;
        }
    }
    return res;
}
var split32_1 = split32;
function rotr32(w, b) {
    return (w >>> b) | (w << (32 - b));
}
var rotr32_1 = rotr32;
function rotl32(w, b) {
    return (w << b) | (w >>> (32 - b));
}
var rotl32_1 = rotl32;
function sum32(a, b) {
    return (a + b) >>> 0;
}
var sum32_1 = sum32;
function sum32_3(a, b, c) {
    return (a + b + c) >>> 0;
}
var sum32_3_1 = sum32_3;
function sum32_4(a, b, c, d) {
    return (a + b + c + d) >>> 0;
}
var sum32_4_1 = sum32_4;
function sum32_5(a, b, c, d, e) {
    return (a + b + c + d + e) >>> 0;
}
var sum32_5_1 = sum32_5;
function sum64(buf, pos, ah, al) {
    var bh = buf[pos];
    var bl = buf[pos + 1];
    var lo = (al + bl) >>> 0;
    var hi = (lo < al ? 1 : 0) + ah + bh;
    buf[pos] = hi >>> 0;
    buf[pos + 1] = lo;
}
var sum64_1 = sum64;
function sum64_hi(ah, al, bh, bl) {
    var lo = (al + bl) >>> 0;
    var hi = (lo < al ? 1 : 0) + ah + bh;
    return hi >>> 0;
}
var sum64_hi_1 = sum64_hi;
function sum64_lo(ah, al, bh, bl) {
    var lo = al + bl;
    return lo >>> 0;
}
var sum64_lo_1 = sum64_lo;
function sum64_4_hi(ah, al, bh, bl, ch, cl, dh, dl) {
    var carry = 0;
    var lo = al;
    lo = (lo + bl) >>> 0;
    carry += lo < al ? 1 : 0;
    lo = (lo + cl) >>> 0;
    carry += lo < cl ? 1 : 0;
    lo = (lo + dl) >>> 0;
    carry += lo < dl ? 1 : 0;
    var hi = ah + bh + ch + dh + carry;
    return hi >>> 0;
}
var sum64_4_hi_1 = sum64_4_hi;
function sum64_4_lo(ah, al, bh, bl, ch, cl, dh, dl) {
    var lo = al + bl + cl + dl;
    return lo >>> 0;
}
var sum64_4_lo_1 = sum64_4_lo;
function sum64_5_hi(ah, al, bh, bl, ch, cl, dh, dl, eh, el) {
    var carry = 0;
    var lo = al;
    lo = (lo + bl) >>> 0;
    carry += lo < al ? 1 : 0;
    lo = (lo + cl) >>> 0;
    carry += lo < cl ? 1 : 0;
    lo = (lo + dl) >>> 0;
    carry += lo < dl ? 1 : 0;
    lo = (lo + el) >>> 0;
    carry += lo < el ? 1 : 0;
    var hi = ah + bh + ch + dh + eh + carry;
    return hi >>> 0;
}
var sum64_5_hi_1 = sum64_5_hi;
function sum64_5_lo(ah, al, bh, bl, ch, cl, dh, dl, eh, el) {
    var lo = al + bl + cl + dl + el;
    return lo >>> 0;
}
var sum64_5_lo_1 = sum64_5_lo;
function rotr64_hi(ah, al, num) {
    var r = (al << (32 - num)) | (ah >>> num);
    return r >>> 0;
}
var rotr64_hi_1 = rotr64_hi;
function rotr64_lo(ah, al, num) {
    var r = (ah << (32 - num)) | (al >>> num);
    return r >>> 0;
}
var rotr64_lo_1 = rotr64_lo;
function shr64_hi(ah, al, num) {
    return ah >>> num;
}
var shr64_hi_1 = shr64_hi;
function shr64_lo(ah, al, num) {
    var r = (ah << (32 - num)) | (al >>> num);
    return r >>> 0;
}
var shr64_lo_1 = shr64_lo;
var utils = {
    inherits: inherits_1,
    toArray: toArray_1,
    toHex: toHex_1,
    htonl: htonl_1,
    toHex32: toHex32_1,
    zero2: zero2_1,
    zero8: zero8_1,
    join32: join32_1,
    split32: split32_1,
    rotr32: rotr32_1,
    rotl32: rotl32_1,
    sum32: sum32_1,
    sum32_3: sum32_3_1,
    sum32_4: sum32_4_1,
    sum32_5: sum32_5_1,
    sum64: sum64_1,
    sum64_hi: sum64_hi_1,
    sum64_lo: sum64_lo_1,
    sum64_4_hi: sum64_4_hi_1,
    sum64_4_lo: sum64_4_lo_1,
    sum64_5_hi: sum64_5_hi_1,
    sum64_5_lo: sum64_5_lo_1,
    rotr64_hi: rotr64_hi_1,
    rotr64_lo: rotr64_lo_1,
    shr64_hi: shr64_hi_1,
    shr64_lo: shr64_lo_1
};

function BlockHash() {
    this.pending = null;
    this.pendingTotal = 0;
    this.blockSize = this.constructor.blockSize;
    this.outSize = this.constructor.outSize;
    this.hmacStrength = this.constructor.hmacStrength;
    this.padLength = this.constructor.padLength / 8;
    this.endian = 'big';
    this._delta8 = this.blockSize / 8;
    this._delta32 = this.blockSize / 32;
}
var BlockHash_1 = BlockHash;
BlockHash.prototype.update = function update(msg, enc) {
    // Convert message to array, pad it, and join into 32bit blocks
    msg = utils.toArray(msg, enc);
    if (!this.pending)
        this.pending = msg;
    else
        this.pending = this.pending.concat(msg);
    this.pendingTotal += msg.length;
    // Enough data, try updating
    if (this.pending.length >= this._delta8) {
        msg = this.pending;
        // Process pending data in blocks
        var r = msg.length % this._delta8;
        this.pending = msg.slice(msg.length - r, msg.length);
        if (this.pending.length === 0)
            this.pending = null;
        msg = utils.join32(msg, 0, msg.length - r, this.endian);
        for (var i = 0; i < msg.length; i += this._delta32)
            this._update(msg, i, i + this._delta32);
    }
    return this;
};
BlockHash.prototype.digest = function digest(enc) {
    this.update(this._pad());
    minimalisticAssert(this.pending === null);
    return this._digest(enc);
};
BlockHash.prototype._pad = function pad() {
    var len = this.pendingTotal;
    var bytes = this._delta8;
    var k = bytes - ((len + this.padLength) % bytes);
    var res = new Array(k + this.padLength);
    res[0] = 0x80;
    for (var i = 1; i < k; i++)
        res[i] = 0;
    // Append length
    len <<= 3;
    if (this.endian === 'big') {
        for (var t = 8; t < this.padLength; t++)
            res[i++] = 0;
        res[i++] = 0;
        res[i++] = 0;
        res[i++] = 0;
        res[i++] = 0;
        res[i++] = (len >>> 24) & 0xff;
        res[i++] = (len >>> 16) & 0xff;
        res[i++] = (len >>> 8) & 0xff;
        res[i++] = len & 0xff;
    }
    else {
        res[i++] = len & 0xff;
        res[i++] = (len >>> 8) & 0xff;
        res[i++] = (len >>> 16) & 0xff;
        res[i++] = (len >>> 24) & 0xff;
        res[i++] = 0;
        res[i++] = 0;
        res[i++] = 0;
        res[i++] = 0;
        for (t = 8; t < this.padLength; t++)
            res[i++] = 0;
    }
    return res;
};
var common = {
    BlockHash: BlockHash_1
};

var rotr32$1 = utils.rotr32;
function ft_1(s, x, y, z) {
    if (s === 0)
        return ch32(x, y, z);
    if (s === 1 || s === 3)
        return p32(x, y, z);
    if (s === 2)
        return maj32(x, y, z);
}
var ft_1_1 = ft_1;
function ch32(x, y, z) {
    return (x & y) ^ ((~x) & z);
}
var ch32_1 = ch32;
function maj32(x, y, z) {
    return (x & y) ^ (x & z) ^ (y & z);
}
var maj32_1 = maj32;
function p32(x, y, z) {
    return x ^ y ^ z;
}
var p32_1 = p32;
function s0_256(x) {
    return rotr32$1(x, 2) ^ rotr32$1(x, 13) ^ rotr32$1(x, 22);
}
var s0_256_1 = s0_256;
function s1_256(x) {
    return rotr32$1(x, 6) ^ rotr32$1(x, 11) ^ rotr32$1(x, 25);
}
var s1_256_1 = s1_256;
function g0_256(x) {
    return rotr32$1(x, 7) ^ rotr32$1(x, 18) ^ (x >>> 3);
}
var g0_256_1 = g0_256;
function g1_256(x) {
    return rotr32$1(x, 17) ^ rotr32$1(x, 19) ^ (x >>> 10);
}
var g1_256_1 = g1_256;
var common$1 = {
    ft_1: ft_1_1,
    ch32: ch32_1,
    maj32: maj32_1,
    p32: p32_1,
    s0_256: s0_256_1,
    s1_256: s1_256_1,
    g0_256: g0_256_1,
    g1_256: g1_256_1
};

var sum32$1 = utils.sum32;
var sum32_4$1 = utils.sum32_4;
var sum32_5$1 = utils.sum32_5;
var ch32$1 = common$1.ch32;
var maj32$1 = common$1.maj32;
var s0_256$1 = common$1.s0_256;
var s1_256$1 = common$1.s1_256;
var g0_256$1 = common$1.g0_256;
var g1_256$1 = common$1.g1_256;
var BlockHash$1 = common.BlockHash;
var sha256_K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
    0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
    0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
    0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
];
function SHA256() {
    if (!(this instanceof SHA256))
        return new SHA256();
    BlockHash$1.call(this);
    this.h = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    ];
    this.k = sha256_K;
    this.W = new Array(64);
}
utils.inherits(SHA256, BlockHash$1);
var _256 = SHA256;
SHA256.blockSize = 512;
SHA256.outSize = 256;
SHA256.hmacStrength = 192;
SHA256.padLength = 64;
SHA256.prototype._update = function _update(msg, start) {
    var W = this.W;
    for (var i = 0; i < 16; i++)
        W[i] = msg[start + i];
    for (; i < W.length; i++)
        W[i] = sum32_4$1(g1_256$1(W[i - 2]), W[i - 7], g0_256$1(W[i - 15]), W[i - 16]);
    var a = this.h[0];
    var b = this.h[1];
    var c = this.h[2];
    var d = this.h[3];
    var e = this.h[4];
    var f = this.h[5];
    var g = this.h[6];
    var h = this.h[7];
    minimalisticAssert(this.k.length === W.length);
    for (i = 0; i < W.length; i++) {
        var T1 = sum32_5$1(h, s1_256$1(e), ch32$1(e, f, g), this.k[i], W[i]);
        var T2 = sum32$1(s0_256$1(a), maj32$1(a, b, c));
        h = g;
        g = f;
        f = e;
        e = sum32$1(d, T1);
        d = c;
        c = b;
        b = a;
        a = sum32$1(T1, T2);
    }
    this.h[0] = sum32$1(this.h[0], a);
    this.h[1] = sum32$1(this.h[1], b);
    this.h[2] = sum32$1(this.h[2], c);
    this.h[3] = sum32$1(this.h[3], d);
    this.h[4] = sum32$1(this.h[4], e);
    this.h[5] = sum32$1(this.h[5], f);
    this.h[6] = sum32$1(this.h[6], g);
    this.h[7] = sum32$1(this.h[7], h);
};
SHA256.prototype._digest = function digest(enc) {
    if (enc === 'hex')
        return utils.toHex32(this.h, 'big');
    else
        return utils.split32(this.h, 'big');
};

var charToInteger = {};
var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';
for (var i = 0; i < chars.length; i++) {
    charToInteger[chars.charCodeAt(i)] = i;
}
function decode(mappings) {
    var generatedCodeColumn = 0; // first field
    var sourceFileIndex = 0; // second field
    var sourceCodeLine = 0; // third field
    var sourceCodeColumn = 0; // fourth field
    var nameIndex = 0; // fifth field
    var decoded = [];
    var line = [];
    var segment = [];
    for (var i = 0, j = 0, shift = 0, value = 0, len = mappings.length; i < len; i++) {
        var c = mappings.charCodeAt(i);
        if (c === 44) { // ","
            if (segment.length)
                line.push(segment);
            segment = [];
            j = 0;
        }
        else if (c === 59) { // ";"
            if (segment.length)
                line.push(segment);
            segment = [];
            j = 0;
            decoded.push(line);
            line = [];
            generatedCodeColumn = 0;
        }
        else {
            var integer = charToInteger[c];
            if (integer === undefined) {
                throw new Error('Invalid character (' + String.fromCharCode(c) + ')');
            }
            var hasContinuationBit = integer & 32;
            integer &= 31;
            value += integer << shift;
            if (hasContinuationBit) {
                shift += 5;
            }
            else {
                var shouldNegate = value & 1;
                value >>>= 1;
                if (shouldNegate) {
                    value = -value;
                    if (value === 0)
                        value = -0x80000000;
                }
                if (j == 0) {
                    generatedCodeColumn += value;
                    segment.push(generatedCodeColumn);
                }
                else if (j === 1) {
                    sourceFileIndex += value;
                    segment.push(sourceFileIndex);
                }
                else if (j === 2) {
                    sourceCodeLine += value;
                    segment.push(sourceCodeLine);
                }
                else if (j === 3) {
                    sourceCodeColumn += value;
                    segment.push(sourceCodeColumn);
                }
                else if (j === 4) {
                    nameIndex += value;
                    segment.push(nameIndex);
                }
                j++;
                value = shift = 0; // reset
            }
        }
    }
    if (segment.length)
        line.push(segment);
    decoded.push(line);
    return decoded;
}
function encode(decoded) {
    var sourceFileIndex = 0; // second field
    var sourceCodeLine = 0; // third field
    var sourceCodeColumn = 0; // fourth field
    var nameIndex = 0; // fifth field
    var mappings = '';
    for (var i = 0; i < decoded.length; i++) {
        var line = decoded[i];
        if (i > 0)
            mappings += ';';
        if (line.length === 0)
            continue;
        var generatedCodeColumn = 0; // first field
        var lineMappings = [];
        for (var _i = 0, line_1 = line; _i < line_1.length; _i++) {
            var segment = line_1[_i];
            var segmentMappings = encodeInteger(segment[0] - generatedCodeColumn);
            generatedCodeColumn = segment[0];
            if (segment.length > 1) {
                segmentMappings +=
                    encodeInteger(segment[1] - sourceFileIndex) +
                        encodeInteger(segment[2] - sourceCodeLine) +
                        encodeInteger(segment[3] - sourceCodeColumn);
                sourceFileIndex = segment[1];
                sourceCodeLine = segment[2];
                sourceCodeColumn = segment[3];
            }
            if (segment.length === 5) {
                segmentMappings += encodeInteger(segment[4] - nameIndex);
                nameIndex = segment[4];
            }
            lineMappings.push(segmentMappings);
        }
        mappings += lineMappings.join(',');
    }
    return mappings;
}
function encodeInteger(num) {
    var result = '';
    num = num < 0 ? (-num << 1) | 1 : num << 1;
    do {
        var clamped = num & 31;
        num >>>= 5;
        if (num > 0) {
            clamped |= 32;
        }
        result += chars[clamped];
    } while (num > 0);
    return result;
}

var Chunk = function Chunk(start, end, content) {
    this.start = start;
    this.end = end;
    this.original = content;
    this.intro = '';
    this.outro = '';
    this.content = content;
    this.storeName = false;
    this.edited = false;
    // we make these non-enumerable, for sanity while debugging
    Object.defineProperties(this, {
        previous: { writable: true, value: null },
        next: { writable: true, value: null }
    });
};
Chunk.prototype.appendLeft = function appendLeft(content) {
    this.outro += content;
};
Chunk.prototype.appendRight = function appendRight(content) {
    this.intro = this.intro + content;
};
Chunk.prototype.clone = function clone() {
    var chunk = new Chunk(this.start, this.end, this.original);
    chunk.intro = this.intro;
    chunk.outro = this.outro;
    chunk.content = this.content;
    chunk.storeName = this.storeName;
    chunk.edited = this.edited;
    return chunk;
};
Chunk.prototype.contains = function contains(index) {
    return this.start < index && index < this.end;
};
Chunk.prototype.eachNext = function eachNext(fn) {
    var chunk = this;
    while (chunk) {
        fn(chunk);
        chunk = chunk.next;
    }
};
Chunk.prototype.eachPrevious = function eachPrevious(fn) {
    var chunk = this;
    while (chunk) {
        fn(chunk);
        chunk = chunk.previous;
    }
};
Chunk.prototype.edit = function edit(content, storeName, contentOnly) {
    this.content = content;
    if (!contentOnly) {
        this.intro = '';
        this.outro = '';
    }
    this.storeName = storeName;
    this.edited = true;
    return this;
};
Chunk.prototype.prependLeft = function prependLeft(content) {
    this.outro = content + this.outro;
};
Chunk.prototype.prependRight = function prependRight(content) {
    this.intro = content + this.intro;
};
Chunk.prototype.split = function split(index) {
    var sliceIndex = index - this.start;
    var originalBefore = this.original.slice(0, sliceIndex);
    var originalAfter = this.original.slice(sliceIndex);
    this.original = originalBefore;
    var newChunk = new Chunk(index, this.end, originalAfter);
    newChunk.outro = this.outro;
    this.outro = '';
    this.end = index;
    if (this.edited) {
        // TODO is this block necessary?...
        newChunk.edit('', false);
        this.content = '';
    }
    else {
        this.content = originalBefore;
    }
    newChunk.next = this.next;
    if (newChunk.next) {
        newChunk.next.previous = newChunk;
    }
    newChunk.previous = this;
    this.next = newChunk;
    return newChunk;
};
Chunk.prototype.toString = function toString() {
    return this.intro + this.content + this.outro;
};
Chunk.prototype.trimEnd = function trimEnd(rx) {
    this.outro = this.outro.replace(rx, '');
    if (this.outro.length) {
        return true;
    }
    var trimmed = this.content.replace(rx, '');
    if (trimmed.length) {
        if (trimmed !== this.content) {
            this.split(this.start + trimmed.length).edit('', undefined, true);
        }
        return true;
    }
    else {
        this.edit('', undefined, true);
        this.intro = this.intro.replace(rx, '');
        if (this.intro.length) {
            return true;
        }
    }
};
Chunk.prototype.trimStart = function trimStart(rx) {
    this.intro = this.intro.replace(rx, '');
    if (this.intro.length) {
        return true;
    }
    var trimmed = this.content.replace(rx, '');
    if (trimmed.length) {
        if (trimmed !== this.content) {
            this.split(this.end - trimmed.length);
            this.edit('', undefined, true);
        }
        return true;
    }
    else {
        this.edit('', undefined, true);
        this.outro = this.outro.replace(rx, '');
        if (this.outro.length) {
            return true;
        }
    }
};
var btoa = function () {
    throw new Error('Unsupported environment: `window.btoa` or `Buffer` should be supported.');
};
if (typeof window !== 'undefined' && typeof window.btoa === 'function') {
    btoa = function (str) { return window.btoa(unescape(encodeURIComponent(str))); };
}
else if (typeof Buffer === 'function') {
    btoa = function (str) { return Buffer.from(str, 'utf-8').toString('base64'); };
}
var SourceMap = function SourceMap(properties) {
    this.version = 3;
    this.file = properties.file;
    this.sources = properties.sources;
    this.sourcesContent = properties.sourcesContent;
    this.names = properties.names;
    this.mappings = encode(properties.mappings);
};
SourceMap.prototype.toString = function toString() {
    return JSON.stringify(this);
};
SourceMap.prototype.toUrl = function toUrl() {
    return 'data:application/json;charset=utf-8;base64,' + btoa(this.toString());
};
function guessIndent(code) {
    var lines = code.split('\n');
    var tabbed = lines.filter(function (line) { return /^\t+/.test(line); });
    var spaced = lines.filter(function (line) { return /^ {2,}/.test(line); });
    if (tabbed.length === 0 && spaced.length === 0) {
        return null;
    }
    // More lines tabbed than spaced? Assume tabs, and
    // default to tabs in the case of a tie (or nothing
    // to go on)
    if (tabbed.length >= spaced.length) {
        return '\t';
    }
    // Otherwise, we need to guess the multiple
    var min = spaced.reduce(function (previous, current) {
        var numSpaces = /^ +/.exec(current)[0].length;
        return Math.min(numSpaces, previous);
    }, Infinity);
    return new Array(min + 1).join(' ');
}
function getRelativePath(from, to) {
    var fromParts = from.split(/[/\\]/);
    var toParts = to.split(/[/\\]/);
    fromParts.pop(); // get dirname
    while (fromParts[0] === toParts[0]) {
        fromParts.shift();
        toParts.shift();
    }
    if (fromParts.length) {
        var i = fromParts.length;
        while (i--) {
            fromParts[i] = '..';
        }
    }
    return fromParts.concat(toParts).join('/');
}
var toString = Object.prototype.toString;
function isObject(thing) {
    return toString.call(thing) === '[object Object]';
}
function getLocator(source) {
    var originalLines = source.split('\n');
    var lineOffsets = [];
    for (var i = 0, pos = 0; i < originalLines.length; i++) {
        lineOffsets.push(pos);
        pos += originalLines[i].length + 1;
    }
    return function locate(index) {
        var i = 0;
        var j = lineOffsets.length;
        while (i < j) {
            var m = (i + j) >> 1;
            if (index < lineOffsets[m]) {
                j = m;
            }
            else {
                i = m + 1;
            }
        }
        var line = i - 1;
        var column = index - lineOffsets[line];
        return { line: line, column: column };
    };
}
var Mappings = function Mappings(hires) {
    this.hires = hires;
    this.generatedCodeLine = 0;
    this.generatedCodeColumn = 0;
    this.raw = [];
    this.rawSegments = this.raw[this.generatedCodeLine] = [];
    this.pending = null;
};
Mappings.prototype.addEdit = function addEdit(sourceIndex, content, loc, nameIndex) {
    if (content.length) {
        var segment = [this.generatedCodeColumn, sourceIndex, loc.line, loc.column];
        if (nameIndex >= 0) {
            segment.push(nameIndex);
        }
        this.rawSegments.push(segment);
    }
    else if (this.pending) {
        this.rawSegments.push(this.pending);
    }
    this.advance(content);
    this.pending = null;
};
Mappings.prototype.addUneditedChunk = function addUneditedChunk(sourceIndex, chunk, original, loc, sourcemapLocations) {
    var this$1 = this;
    var originalCharIndex = chunk.start;
    var first = true;
    while (originalCharIndex < chunk.end) {
        if (this$1.hires || first || sourcemapLocations[originalCharIndex]) {
            this$1.rawSegments.push([this$1.generatedCodeColumn, sourceIndex, loc.line, loc.column]);
        }
        if (original[originalCharIndex] === '\n') {
            loc.line += 1;
            loc.column = 0;
            this$1.generatedCodeLine += 1;
            this$1.raw[this$1.generatedCodeLine] = this$1.rawSegments = [];
            this$1.generatedCodeColumn = 0;
        }
        else {
            loc.column += 1;
            this$1.generatedCodeColumn += 1;
        }
        originalCharIndex += 1;
        first = false;
    }
    this.pending = [this.generatedCodeColumn, sourceIndex, loc.line, loc.column];
};
Mappings.prototype.advance = function advance(str) {
    var this$1 = this;
    if (!str) {
        return;
    }
    var lines = str.split('\n');
    if (lines.length > 1) {
        for (var i = 0; i < lines.length - 1; i++) {
            this$1.generatedCodeLine++;
            this$1.raw[this$1.generatedCodeLine] = this$1.rawSegments = [];
        }
        this.generatedCodeColumn = 0;
    }
    this.generatedCodeColumn += lines[lines.length - 1].length;
};
var n = '\n';
var warned = {
    insertLeft: false,
    insertRight: false,
    storeName: false
};
var MagicString = function MagicString(string, options) {
    if (options === void 0)
        options = {};
    var chunk = new Chunk(0, string.length, string);
    Object.defineProperties(this, {
        original: { writable: true, value: string },
        outro: { writable: true, value: '' },
        intro: { writable: true, value: '' },
        firstChunk: { writable: true, value: chunk },
        lastChunk: { writable: true, value: chunk },
        lastSearchedChunk: { writable: true, value: chunk },
        byStart: { writable: true, value: {} },
        byEnd: { writable: true, value: {} },
        filename: { writable: true, value: options.filename },
        indentExclusionRanges: { writable: true, value: options.indentExclusionRanges },
        sourcemapLocations: { writable: true, value: {} },
        storedNames: { writable: true, value: {} },
        indentStr: { writable: true, value: guessIndent(string) }
    });
    this.byStart[0] = chunk;
    this.byEnd[string.length] = chunk;
};
MagicString.prototype.addSourcemapLocation = function addSourcemapLocation(char) {
    this.sourcemapLocations[char] = true;
};
MagicString.prototype.append = function append(content) {
    if (typeof content !== 'string') {
        throw new TypeError('outro content must be a string');
    }
    this.outro += content;
    return this;
};
MagicString.prototype.appendLeft = function appendLeft(index, content) {
    if (typeof content !== 'string') {
        throw new TypeError('inserted content must be a string');
    }
    this._split(index);
    var chunk = this.byEnd[index];
    if (chunk) {
        chunk.appendLeft(content);
    }
    else {
        this.intro += content;
    }
    return this;
};
MagicString.prototype.appendRight = function appendRight(index, content) {
    if (typeof content !== 'string') {
        throw new TypeError('inserted content must be a string');
    }
    this._split(index);
    var chunk = this.byStart[index];
    if (chunk) {
        chunk.appendRight(content);
    }
    else {
        this.outro += content;
    }
    return this;
};
MagicString.prototype.clone = function clone() {
    var cloned = new MagicString(this.original, { filename: this.filename });
    var originalChunk = this.firstChunk;
    var clonedChunk = (cloned.firstChunk = cloned.lastSearchedChunk = originalChunk.clone());
    while (originalChunk) {
        cloned.byStart[clonedChunk.start] = clonedChunk;
        cloned.byEnd[clonedChunk.end] = clonedChunk;
        var nextOriginalChunk = originalChunk.next;
        var nextClonedChunk = nextOriginalChunk && nextOriginalChunk.clone();
        if (nextClonedChunk) {
            clonedChunk.next = nextClonedChunk;
            nextClonedChunk.previous = clonedChunk;
            clonedChunk = nextClonedChunk;
        }
        originalChunk = nextOriginalChunk;
    }
    cloned.lastChunk = clonedChunk;
    if (this.indentExclusionRanges) {
        cloned.indentExclusionRanges = this.indentExclusionRanges.slice();
    }
    Object.keys(this.sourcemapLocations).forEach(function (loc) {
        cloned.sourcemapLocations[loc] = true;
    });
    cloned.intro = this.intro;
    cloned.outro = this.outro;
    return cloned;
};
MagicString.prototype.generateDecodedMap = function generateDecodedMap(options) {
    var this$1 = this;
    options = options || {};
    var sourceIndex = 0;
    var names = Object.keys(this.storedNames);
    var mappings = new Mappings(options.hires);
    var locate = getLocator(this.original);
    if (this.intro) {
        mappings.advance(this.intro);
    }
    this.firstChunk.eachNext(function (chunk) {
        var loc = locate(chunk.start);
        if (chunk.intro.length) {
            mappings.advance(chunk.intro);
        }
        if (chunk.edited) {
            mappings.addEdit(sourceIndex, chunk.content, loc, chunk.storeName ? names.indexOf(chunk.original) : -1);
        }
        else {
            mappings.addUneditedChunk(sourceIndex, chunk, this$1.original, loc, this$1.sourcemapLocations);
        }
        if (chunk.outro.length) {
            mappings.advance(chunk.outro);
        }
    });
    return {
        file: options.file ? options.file.split(/[/\\]/).pop() : null,
        sources: [options.source ? getRelativePath(options.file || '', options.source) : null],
        sourcesContent: options.includeContent ? [this.original] : [null],
        names: names,
        mappings: mappings.raw
    };
};
MagicString.prototype.generateMap = function generateMap(options) {
    return new SourceMap(this.generateDecodedMap(options));
};
MagicString.prototype.getIndentString = function getIndentString() {
    return this.indentStr === null ? '\t' : this.indentStr;
};
MagicString.prototype.indent = function indent(indentStr, options) {
    var this$1 = this;
    var pattern = /^[^\r\n]/gm;
    if (isObject(indentStr)) {
        options = indentStr;
        indentStr = undefined;
    }
    indentStr = indentStr !== undefined ? indentStr : this.indentStr || '\t';
    if (indentStr === '') {
        return this;
    } // noop
    options = options || {};
    // Process exclusion ranges
    var isExcluded = {};
    if (options.exclude) {
        var exclusions = typeof options.exclude[0] === 'number' ? [options.exclude] : options.exclude;
        exclusions.forEach(function (exclusion) {
            for (var i = exclusion[0]; i < exclusion[1]; i += 1) {
                isExcluded[i] = true;
            }
        });
    }
    var shouldIndentNextCharacter = options.indentStart !== false;
    var replacer = function (match) {
        if (shouldIndentNextCharacter) {
            return ("" + indentStr + match);
        }
        shouldIndentNextCharacter = true;
        return match;
    };
    this.intro = this.intro.replace(pattern, replacer);
    var charIndex = 0;
    var chunk = this.firstChunk;
    while (chunk) {
        var end = chunk.end;
        if (chunk.edited) {
            if (!isExcluded[charIndex]) {
                chunk.content = chunk.content.replace(pattern, replacer);
                if (chunk.content.length) {
                    shouldIndentNextCharacter = chunk.content[chunk.content.length - 1] === '\n';
                }
            }
        }
        else {
            charIndex = chunk.start;
            while (charIndex < end) {
                if (!isExcluded[charIndex]) {
                    var char = this$1.original[charIndex];
                    if (char === '\n') {
                        shouldIndentNextCharacter = true;
                    }
                    else if (char !== '\r' && shouldIndentNextCharacter) {
                        shouldIndentNextCharacter = false;
                        if (charIndex === chunk.start) {
                            chunk.prependRight(indentStr);
                        }
                        else {
                            this$1._splitChunk(chunk, charIndex);
                            chunk = chunk.next;
                            chunk.prependRight(indentStr);
                        }
                    }
                }
                charIndex += 1;
            }
        }
        charIndex = chunk.end;
        chunk = chunk.next;
    }
    this.outro = this.outro.replace(pattern, replacer);
    return this;
};
MagicString.prototype.insert = function insert() {
    throw new Error('magicString.insert(...) is deprecated. Use prependRight(...) or appendLeft(...)');
};
MagicString.prototype.insertLeft = function insertLeft(index, content) {
    if (!warned.insertLeft) {
        console.warn('magicString.insertLeft(...) is deprecated. Use magicString.appendLeft(...) instead'); // eslint-disable-line no-console
        warned.insertLeft = true;
    }
    return this.appendLeft(index, content);
};
MagicString.prototype.insertRight = function insertRight(index, content) {
    if (!warned.insertRight) {
        console.warn('magicString.insertRight(...) is deprecated. Use magicString.prependRight(...) instead'); // eslint-disable-line no-console
        warned.insertRight = true;
    }
    return this.prependRight(index, content);
};
MagicString.prototype.move = function move(start, end, index) {
    if (index >= start && index <= end) {
        throw new Error('Cannot move a selection inside itself');
    }
    this._split(start);
    this._split(end);
    this._split(index);
    var first = this.byStart[start];
    var last = this.byEnd[end];
    var oldLeft = first.previous;
    var oldRight = last.next;
    var newRight = this.byStart[index];
    if (!newRight && last === this.lastChunk) {
        return this;
    }
    var newLeft = newRight ? newRight.previous : this.lastChunk;
    if (oldLeft) {
        oldLeft.next = oldRight;
    }
    if (oldRight) {
        oldRight.previous = oldLeft;
    }
    if (newLeft) {
        newLeft.next = first;
    }
    if (newRight) {
        newRight.previous = last;
    }
    if (!first.previous) {
        this.firstChunk = last.next;
    }
    if (!last.next) {
        this.lastChunk = first.previous;
        this.lastChunk.next = null;
    }
    first.previous = newLeft;
    last.next = newRight || null;
    if (!newLeft) {
        this.firstChunk = first;
    }
    if (!newRight) {
        this.lastChunk = last;
    }
    return this;
};
MagicString.prototype.overwrite = function overwrite(start, end, content, options) {
    var this$1 = this;
    if (typeof content !== 'string') {
        throw new TypeError('replacement content must be a string');
    }
    while (start < 0) {
        start += this$1.original.length;
    }
    while (end < 0) {
        end += this$1.original.length;
    }
    if (end > this.original.length) {
        throw new Error('end is out of bounds');
    }
    if (start === end) {
        throw new Error('Cannot overwrite a zero-length range – use appendLeft or prependRight instead');
    }
    this._split(start);
    this._split(end);
    if (options === true) {
        if (!warned.storeName) {
            console.warn('The final argument to magicString.overwrite(...) should be an options object. See https://github.com/rich-harris/magic-string'); // eslint-disable-line no-console
            warned.storeName = true;
        }
        options = { storeName: true };
    }
    var storeName = options !== undefined ? options.storeName : false;
    var contentOnly = options !== undefined ? options.contentOnly : false;
    if (storeName) {
        var original = this.original.slice(start, end);
        this.storedNames[original] = true;
    }
    var first = this.byStart[start];
    var last = this.byEnd[end];
    if (first) {
        if (end > first.end && first.next !== this.byStart[first.end]) {
            throw new Error('Cannot overwrite across a split point');
        }
        first.edit(content, storeName, contentOnly);
        if (first !== last) {
            var chunk = first.next;
            while (chunk !== last) {
                chunk.edit('', false);
                chunk = chunk.next;
            }
            chunk.edit('', false);
        }
    }
    else {
        // must be inserting at the end
        var newChunk = new Chunk(start, end, '').edit(content, storeName);
        // TODO last chunk in the array may not be the last chunk, if it's moved...
        last.next = newChunk;
        newChunk.previous = last;
    }
    return this;
};
MagicString.prototype.prepend = function prepend(content) {
    if (typeof content !== 'string') {
        throw new TypeError('outro content must be a string');
    }
    this.intro = content + this.intro;
    return this;
};
MagicString.prototype.prependLeft = function prependLeft(index, content) {
    if (typeof content !== 'string') {
        throw new TypeError('inserted content must be a string');
    }
    this._split(index);
    var chunk = this.byEnd[index];
    if (chunk) {
        chunk.prependLeft(content);
    }
    else {
        this.intro = content + this.intro;
    }
    return this;
};
MagicString.prototype.prependRight = function prependRight(index, content) {
    if (typeof content !== 'string') {
        throw new TypeError('inserted content must be a string');
    }
    this._split(index);
    var chunk = this.byStart[index];
    if (chunk) {
        chunk.prependRight(content);
    }
    else {
        this.outro = content + this.outro;
    }
    return this;
};
MagicString.prototype.remove = function remove(start, end) {
    var this$1 = this;
    while (start < 0) {
        start += this$1.original.length;
    }
    while (end < 0) {
        end += this$1.original.length;
    }
    if (start === end) {
        return this;
    }
    if (start < 0 || end > this.original.length) {
        throw new Error('Character is out of bounds');
    }
    if (start > end) {
        throw new Error('end must be greater than start');
    }
    this._split(start);
    this._split(end);
    var chunk = this.byStart[start];
    while (chunk) {
        chunk.intro = '';
        chunk.outro = '';
        chunk.edit('');
        chunk = end > chunk.end ? this$1.byStart[chunk.end] : null;
    }
    return this;
};
MagicString.prototype.lastChar = function lastChar() {
    if (this.outro.length) {
        return this.outro[this.outro.length - 1];
    }
    var chunk = this.lastChunk;
    do {
        if (chunk.outro.length) {
            return chunk.outro[chunk.outro.length - 1];
        }
        if (chunk.content.length) {
            return chunk.content[chunk.content.length - 1];
        }
        if (chunk.intro.length) {
            return chunk.intro[chunk.intro.length - 1];
        }
    } while (chunk = chunk.previous);
    if (this.intro.length) {
        return this.intro[this.intro.length - 1];
    }
    return '';
};
MagicString.prototype.lastLine = function lastLine() {
    var lineIndex = this.outro.lastIndexOf(n);
    if (lineIndex !== -1) {
        return this.outro.substr(lineIndex + 1);
    }
    var lineStr = this.outro;
    var chunk = this.lastChunk;
    do {
        if (chunk.outro.length > 0) {
            lineIndex = chunk.outro.lastIndexOf(n);
            if (lineIndex !== -1) {
                return chunk.outro.substr(lineIndex + 1) + lineStr;
            }
            lineStr = chunk.outro + lineStr;
        }
        if (chunk.content.length > 0) {
            lineIndex = chunk.content.lastIndexOf(n);
            if (lineIndex !== -1) {
                return chunk.content.substr(lineIndex + 1) + lineStr;
            }
            lineStr = chunk.content + lineStr;
        }
        if (chunk.intro.length > 0) {
            lineIndex = chunk.intro.lastIndexOf(n);
            if (lineIndex !== -1) {
                return chunk.intro.substr(lineIndex + 1) + lineStr;
            }
            lineStr = chunk.intro + lineStr;
        }
    } while (chunk = chunk.previous);
    lineIndex = this.intro.lastIndexOf(n);
    if (lineIndex !== -1) {
        return this.intro.substr(lineIndex + 1) + lineStr;
    }
    return this.intro + lineStr;
};
MagicString.prototype.slice = function slice(start, end) {
    var this$1 = this;
    if (start === void 0)
        start = 0;
    if (end === void 0)
        end = this.original.length;
    while (start < 0) {
        start += this$1.original.length;
    }
    while (end < 0) {
        end += this$1.original.length;
    }
    var result = '';
    // find start chunk
    var chunk = this.firstChunk;
    while (chunk && (chunk.start > start || chunk.end <= start)) {
        // found end chunk before start
        if (chunk.start < end && chunk.end >= end) {
            return result;
        }
        chunk = chunk.next;
    }
    if (chunk && chunk.edited && chunk.start !== start) {
        throw new Error(("Cannot use replaced character " + start + " as slice start anchor."));
    }
    var startChunk = chunk;
    while (chunk) {
        if (chunk.intro && (startChunk !== chunk || chunk.start === start)) {
            result += chunk.intro;
        }
        var containsEnd = chunk.start < end && chunk.end >= end;
        if (containsEnd && chunk.edited && chunk.end !== end) {
            throw new Error(("Cannot use replaced character " + end + " as slice end anchor."));
        }
        var sliceStart = startChunk === chunk ? start - chunk.start : 0;
        var sliceEnd = containsEnd ? chunk.content.length + end - chunk.end : chunk.content.length;
        result += chunk.content.slice(sliceStart, sliceEnd);
        if (chunk.outro && (!containsEnd || chunk.end === end)) {
            result += chunk.outro;
        }
        if (containsEnd) {
            break;
        }
        chunk = chunk.next;
    }
    return result;
};
// TODO deprecate this? not really very useful
MagicString.prototype.snip = function snip(start, end) {
    var clone = this.clone();
    clone.remove(0, start);
    clone.remove(end, clone.original.length);
    return clone;
};
MagicString.prototype._split = function _split(index) {
    var this$1 = this;
    if (this.byStart[index] || this.byEnd[index]) {
        return;
    }
    var chunk = this.lastSearchedChunk;
    var searchForward = index > chunk.end;
    while (chunk) {
        if (chunk.contains(index)) {
            return this$1._splitChunk(chunk, index);
        }
        chunk = searchForward ? this$1.byStart[chunk.end] : this$1.byEnd[chunk.start];
    }
};
MagicString.prototype._splitChunk = function _splitChunk(chunk, index) {
    if (chunk.edited && chunk.content.length) {
        // zero-length edited chunks are a special case (overlapping replacements)
        var loc = getLocator(this.original)(index);
        throw new Error(("Cannot split a chunk that has already been edited (" + (loc.line) + ":" + (loc.column) + " – \"" + (chunk.original) + "\")"));
    }
    var newChunk = chunk.split(index);
    this.byEnd[index] = chunk;
    this.byStart[index] = newChunk;
    this.byEnd[newChunk.end] = newChunk;
    if (chunk === this.lastChunk) {
        this.lastChunk = newChunk;
    }
    this.lastSearchedChunk = chunk;
    return true;
};
MagicString.prototype.toString = function toString() {
    var str = this.intro;
    var chunk = this.firstChunk;
    while (chunk) {
        str += chunk.toString();
        chunk = chunk.next;
    }
    return str + this.outro;
};
MagicString.prototype.isEmpty = function isEmpty() {
    var chunk = this.firstChunk;
    do {
        if (chunk.intro.length && chunk.intro.trim() ||
            chunk.content.length && chunk.content.trim() ||
            chunk.outro.length && chunk.outro.trim()) {
            return false;
        }
    } while (chunk = chunk.next);
    return true;
};
MagicString.prototype.length = function length() {
    var chunk = this.firstChunk;
    var length = 0;
    do {
        length += chunk.intro.length + chunk.content.length + chunk.outro.length;
    } while (chunk = chunk.next);
    return length;
};
MagicString.prototype.trimLines = function trimLines() {
    return this.trim('[\\r\\n]');
};
MagicString.prototype.trim = function trim(charType) {
    return this.trimStart(charType).trimEnd(charType);
};
MagicString.prototype.trimEndAborted = function trimEndAborted(charType) {
    var this$1 = this;
    var rx = new RegExp((charType || '\\s') + '+$');
    this.outro = this.outro.replace(rx, '');
    if (this.outro.length) {
        return true;
    }
    var chunk = this.lastChunk;
    do {
        var end = chunk.end;
        var aborted = chunk.trimEnd(rx);
        // if chunk was trimmed, we have a new lastChunk
        if (chunk.end !== end) {
            if (this$1.lastChunk === chunk) {
                this$1.lastChunk = chunk.next;
            }
            this$1.byEnd[chunk.end] = chunk;
            this$1.byStart[chunk.next.start] = chunk.next;
            this$1.byEnd[chunk.next.end] = chunk.next;
        }
        if (aborted) {
            return true;
        }
        chunk = chunk.previous;
    } while (chunk);
    return false;
};
MagicString.prototype.trimEnd = function trimEnd(charType) {
    this.trimEndAborted(charType);
    return this;
};
MagicString.prototype.trimStartAborted = function trimStartAborted(charType) {
    var this$1 = this;
    var rx = new RegExp('^' + (charType || '\\s') + '+');
    this.intro = this.intro.replace(rx, '');
    if (this.intro.length) {
        return true;
    }
    var chunk = this.firstChunk;
    do {
        var end = chunk.end;
        var aborted = chunk.trimStart(rx);
        if (chunk.end !== end) {
            // special case...
            if (chunk === this$1.lastChunk) {
                this$1.lastChunk = chunk.next;
            }
            this$1.byEnd[chunk.end] = chunk;
            this$1.byStart[chunk.next.start] = chunk.next;
            this$1.byEnd[chunk.next.end] = chunk.next;
        }
        if (aborted) {
            return true;
        }
        chunk = chunk.next;
    } while (chunk);
    return false;
};
MagicString.prototype.trimStart = function trimStart(charType) {
    this.trimStartAborted(charType);
    return this;
};
var hasOwnProp = Object.prototype.hasOwnProperty;
var Bundle = function Bundle(options) {
    if (options === void 0)
        options = {};
    this.intro = options.intro || '';
    this.separator = options.separator !== undefined ? options.separator : '\n';
    this.sources = [];
    this.uniqueSources = [];
    this.uniqueSourceIndexByFilename = {};
};
Bundle.prototype.addSource = function addSource(source) {
    if (source instanceof MagicString) {
        return this.addSource({
            content: source,
            filename: source.filename,
            separator: this.separator
        });
    }
    if (!isObject(source) || !source.content) {
        throw new Error('bundle.addSource() takes an object with a `content` property, which should be an instance of MagicString, and an optional `filename`');
    }
    ['filename', 'indentExclusionRanges', 'separator'].forEach(function (option) {
        if (!hasOwnProp.call(source, option)) {
            source[option] = source.content[option];
        }
    });
    if (source.separator === undefined) {
        // TODO there's a bunch of this sort of thing, needs cleaning up
        source.separator = this.separator;
    }
    if (source.filename) {
        if (!hasOwnProp.call(this.uniqueSourceIndexByFilename, source.filename)) {
            this.uniqueSourceIndexByFilename[source.filename] = this.uniqueSources.length;
            this.uniqueSources.push({ filename: source.filename, content: source.content.original });
        }
        else {
            var uniqueSource = this.uniqueSources[this.uniqueSourceIndexByFilename[source.filename]];
            if (source.content.original !== uniqueSource.content) {
                throw new Error(("Illegal source: same filename (" + (source.filename) + "), different contents"));
            }
        }
    }
    this.sources.push(source);
    return this;
};
Bundle.prototype.append = function append(str, options) {
    this.addSource({
        content: new MagicString(str),
        separator: (options && options.separator) || ''
    });
    return this;
};
Bundle.prototype.clone = function clone() {
    var bundle = new Bundle({
        intro: this.intro,
        separator: this.separator
    });
    this.sources.forEach(function (source) {
        bundle.addSource({
            filename: source.filename,
            content: source.content.clone(),
            separator: source.separator
        });
    });
    return bundle;
};
Bundle.prototype.generateDecodedMap = function generateDecodedMap(options) {
    var this$1 = this;
    if (options === void 0)
        options = {};
    var names = [];
    this.sources.forEach(function (source) {
        Object.keys(source.content.storedNames).forEach(function (name) {
            if (!~names.indexOf(name)) {
                names.push(name);
            }
        });
    });
    var mappings = new Mappings(options.hires);
    if (this.intro) {
        mappings.advance(this.intro);
    }
    this.sources.forEach(function (source, i) {
        if (i > 0) {
            mappings.advance(this$1.separator);
        }
        var sourceIndex = source.filename ? this$1.uniqueSourceIndexByFilename[source.filename] : -1;
        var magicString = source.content;
        var locate = getLocator(magicString.original);
        if (magicString.intro) {
            mappings.advance(magicString.intro);
        }
        magicString.firstChunk.eachNext(function (chunk) {
            var loc = locate(chunk.start);
            if (chunk.intro.length) {
                mappings.advance(chunk.intro);
            }
            if (source.filename) {
                if (chunk.edited) {
                    mappings.addEdit(sourceIndex, chunk.content, loc, chunk.storeName ? names.indexOf(chunk.original) : -1);
                }
                else {
                    mappings.addUneditedChunk(sourceIndex, chunk, magicString.original, loc, magicString.sourcemapLocations);
                }
            }
            else {
                mappings.advance(chunk.content);
            }
            if (chunk.outro.length) {
                mappings.advance(chunk.outro);
            }
        });
        if (magicString.outro) {
            mappings.advance(magicString.outro);
        }
    });
    return {
        file: options.file ? options.file.split(/[/\\]/).pop() : null,
        sources: this.uniqueSources.map(function (source) {
            return options.file ? getRelativePath(options.file, source.filename) : source.filename;
        }),
        sourcesContent: this.uniqueSources.map(function (source) {
            return options.includeContent ? source.content : null;
        }),
        names: names,
        mappings: mappings.raw
    };
};
Bundle.prototype.generateMap = function generateMap(options) {
    return new SourceMap(this.generateDecodedMap(options));
};
Bundle.prototype.getIndentString = function getIndentString() {
    var indentStringCounts = {};
    this.sources.forEach(function (source) {
        var indentStr = source.content.indentStr;
        if (indentStr === null) {
            return;
        }
        if (!indentStringCounts[indentStr]) {
            indentStringCounts[indentStr] = 0;
        }
        indentStringCounts[indentStr] += 1;
    });
    return (Object.keys(indentStringCounts).sort(function (a, b) {
        return indentStringCounts[a] - indentStringCounts[b];
    })[0] || '\t');
};
Bundle.prototype.indent = function indent(indentStr) {
    var this$1 = this;
    if (!arguments.length) {
        indentStr = this.getIndentString();
    }
    if (indentStr === '') {
        return this;
    } // noop
    var trailingNewline = !this.intro || this.intro.slice(-1) === '\n';
    this.sources.forEach(function (source, i) {
        var separator = source.separator !== undefined ? source.separator : this$1.separator;
        var indentStart = trailingNewline || (i > 0 && /\r?\n$/.test(separator));
        source.content.indent(indentStr, {
            exclude: source.indentExclusionRanges,
            indentStart: indentStart //: trailingNewline || /\r?\n$/.test( separator )  //true///\r?\n/.test( separator )
        });
        trailingNewline = source.content.lastChar() === '\n';
    });
    if (this.intro) {
        this.intro =
            indentStr +
                this.intro.replace(/^[^\n]/gm, function (match, index) {
                    return index > 0 ? indentStr + match : match;
                });
    }
    return this;
};
Bundle.prototype.prepend = function prepend(str) {
    this.intro = str + this.intro;
    return this;
};
Bundle.prototype.toString = function toString() {
    var this$1 = this;
    var body = this.sources
        .map(function (source, i) {
        var separator = source.separator !== undefined ? source.separator : this$1.separator;
        var str = (i > 0 ? separator : '') + source.content.toString();
        return str;
    })
        .join('');
    return this.intro + body;
};
Bundle.prototype.isEmpty = function isEmpty() {
    if (this.intro.length && this.intro.trim()) {
        return false;
    }
    if (this.sources.some(function (source) { return !source.content.isEmpty(); })) {
        return false;
    }
    return true;
};
Bundle.prototype.length = function length() {
    return this.sources.reduce(function (length, source) { return length + source.content.length(); }, this.intro.length);
};
Bundle.prototype.trimLines = function trimLines() {
    return this.trim('[\\r\\n]');
};
Bundle.prototype.trim = function trim(charType) {
    return this.trimStart(charType).trimEnd(charType);
};
Bundle.prototype.trimStart = function trimStart(charType) {
    var this$1 = this;
    var rx = new RegExp('^' + (charType || '\\s') + '+');
    this.intro = this.intro.replace(rx, '');
    if (!this.intro) {
        var source;
        var i = 0;
        do {
            source = this$1.sources[i++];
            if (!source) {
                break;
            }
        } while (!source.content.trimStartAborted(charType));
    }
    return this;
};
Bundle.prototype.trimEnd = function trimEnd(charType) {
    var this$1 = this;
    var rx = new RegExp((charType || '\\s') + '+$');
    var source;
    var i = this.sources.length - 1;
    do {
        source = this$1.sources[i--];
        if (!source) {
            this$1.intro = this$1.intro.replace(rx, '');
            break;
        }
    } while (!source.content.trimEndAborted(charType));
    return this;
};

function relative(from, to) {
    const fromParts = from.split(/[/\\]/).filter(Boolean);
    const toParts = to.split(/[/\\]/).filter(Boolean);
    if (fromParts[0] === '.')
        fromParts.shift();
    if (toParts[0] === '.')
        toParts.shift();
    while (fromParts[0] && toParts[0] && fromParts[0] === toParts[0]) {
        fromParts.shift();
        toParts.shift();
    }
    while (toParts[0] === '..' && fromParts.length > 0) {
        toParts.shift();
        fromParts.pop();
    }
    while (fromParts.pop()) {
        toParts.unshift('..');
    }
    return toParts.join('/');
}

const BLANK = Object.create(null);

const BlockStatement = 'BlockStatement';
const CallExpression = 'CallExpression';
const ExportAllDeclaration = 'ExportAllDeclaration';
const ExpressionStatement = 'ExpressionStatement';
const FunctionExpression = 'FunctionExpression';
const Identifier = 'Identifier';
const ImportDefaultSpecifier = 'ImportDefaultSpecifier';
const ImportNamespaceSpecifier = 'ImportNamespaceSpecifier';
const Program = 'Program';
const Property = 'Property';
const ReturnStatement = 'ReturnStatement';
const VariableDeclaration = 'VariableDeclaration';

function treeshakeNode(node, code, start, end) {
    code.remove(start, end);
    if (node.annotations) {
        for (const annotation of node.annotations) {
            if (annotation.start < start) {
                code.remove(annotation.start, annotation.end);
            }
            else {
                return;
            }
        }
    }
}
function removeAnnotations(node, code) {
    if (!node.annotations && node.parent.type === ExpressionStatement) {
        node = node.parent;
    }
    if (node.annotations) {
        for (const annotation of node.annotations) {
            code.remove(annotation.start, annotation.end);
        }
    }
}

const NO_SEMICOLON = { isNoStatement: true };
// This assumes there are only white-space and comments between start and the string we are looking for
function findFirstOccurrenceOutsideComment(code, searchString, start = 0) {
    let searchPos, charCodeAfterSlash;
    searchPos = code.indexOf(searchString, start);
    while (true) {
        start = code.indexOf('/', start);
        if (start === -1 || start > searchPos)
            return searchPos;
        charCodeAfterSlash = code.charCodeAt(++start);
        ++start;
        // With our assumption, '/' always starts a comment. Determine comment type:
        start =
            charCodeAfterSlash === 47 /*"/"*/
                ? code.indexOf('\n', start) + 1
                : code.indexOf('*/', start) + 2;
        if (start > searchPos) {
            searchPos = code.indexOf(searchString, start);
        }
    }
}
// This assumes "code" only contains white-space and comments
function findFirstLineBreakOutsideComment(code) {
    let lineBreakPos, charCodeAfterSlash, start = 0;
    lineBreakPos = code.indexOf('\n', start);
    while (true) {
        start = code.indexOf('/', start);
        if (start === -1 || start > lineBreakPos)
            return lineBreakPos;
        // With our assumption, '/' always starts a comment. Determine comment type:
        charCodeAfterSlash = code.charCodeAt(++start);
        if (charCodeAfterSlash === 47 /*"/"*/)
            return lineBreakPos;
        start = code.indexOf('*/', start + 2) + 2;
        if (start > lineBreakPos) {
            lineBreakPos = code.indexOf('\n', start);
        }
    }
}
function renderStatementList(statements, code, start, end, options) {
    let currentNode, currentNodeStart, currentNodeNeedsBoundaries, nextNodeStart;
    let nextNode = statements[0];
    let nextNodeNeedsBoundaries = !nextNode.included || nextNode.needsBoundaries;
    if (nextNodeNeedsBoundaries) {
        nextNodeStart =
            start + findFirstLineBreakOutsideComment(code.original.slice(start, nextNode.start)) + 1;
    }
    for (let nextIndex = 1; nextIndex <= statements.length; nextIndex++) {
        currentNode = nextNode;
        currentNodeStart = nextNodeStart;
        currentNodeNeedsBoundaries = nextNodeNeedsBoundaries;
        nextNode = statements[nextIndex];
        nextNodeNeedsBoundaries =
            nextNode === undefined ? false : !nextNode.included || nextNode.needsBoundaries;
        if (currentNodeNeedsBoundaries || nextNodeNeedsBoundaries) {
            nextNodeStart =
                currentNode.end +
                    findFirstLineBreakOutsideComment(code.original.slice(currentNode.end, nextNode === undefined ? end : nextNode.start)) +
                    1;
            if (currentNode.included) {
                currentNodeNeedsBoundaries
                    ? currentNode.render(code, options, {
                        end: nextNodeStart,
                        start: currentNodeStart
                    })
                    : currentNode.render(code, options);
            }
            else {
                treeshakeNode(currentNode, code, currentNodeStart, nextNodeStart);
            }
        }
        else {
            currentNode.render(code, options);
        }
    }
}
// This assumes that the first character is not part of the first node
function getCommaSeparatedNodesWithBoundaries(nodes, code, start, end) {
    const splitUpNodes = [];
    let node, nextNode, nextNodeStart, contentEnd, char;
    let separator = start - 1;
    for (let nextIndex = 0; nextIndex < nodes.length; nextIndex++) {
        nextNode = nodes[nextIndex];
        if (node !== undefined) {
            separator =
                node.end +
                    findFirstOccurrenceOutsideComment(code.original.slice(node.end, nextNode.start), ',');
        }
        nextNodeStart = contentEnd =
            separator +
                2 +
                findFirstLineBreakOutsideComment(code.original.slice(separator + 1, nextNode.start));
        while (((char = code.original.charCodeAt(nextNodeStart)),
            char === 32 /*" "*/ || char === 9 /*"\t"*/ || char === 10 /*"\n"*/ || char === 13) /*"\r"*/)
            nextNodeStart++;
        if (node !== undefined) {
            splitUpNodes.push({
                contentEnd,
                end: nextNodeStart,
                node,
                separator,
                start
            });
        }
        node = nextNode;
        start = nextNodeStart;
    }
    splitUpNodes.push({
        contentEnd: end,
        end,
        node: node,
        separator: null,
        start
    });
    return splitUpNodes;
}
// This assumes there are only white-space and comments between start and end
function removeLineBreaks(code, start, end) {
    while (true) {
        const lineBreakPos = findFirstLineBreakOutsideComment(code.original.slice(start, end));
        if (lineBreakPos === -1) {
            break;
        }
        start = start + lineBreakPos + 1;
        code.remove(start - 1, start);
    }
}

const chars$1 = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_$';
const base = 64;
function toBase64(num) {
    let outStr = '';
    do {
        const curDigit = num % base;
        num = Math.floor(num / base);
        outStr = chars$1[curDigit] + outStr;
    } while (num !== 0);
    return outStr;
}

// Verified on IE 6/7 that these keywords can't be used for object properties without escaping:
//   break case catch class const continue debugger default delete do
//   else enum export extends false finally for function if import
//   in instanceof new null return super switch this throw true
//   try typeof var void while with
const RESERVED_NAMES = Object.assign(Object.create(null), {
    await: true,
    break: true,
    case: true,
    catch: true,
    class: true,
    const: true,
    continue: true,
    debugger: true,
    default: true,
    delete: true,
    do: true,
    else: true,
    enum: true,
    eval: true,
    export: true,
    extends: true,
    false: true,
    finally: true,
    for: true,
    function: true,
    if: true,
    implements: true,
    import: true,
    in: true,
    instanceof: true,
    interface: true,
    let: true,
    new: true,
    null: true,
    package: true,
    private: true,
    protected: true,
    public: true,
    return: true,
    static: true,
    super: true,
    switch: true,
    this: true,
    throw: true,
    true: true,
    try: true,
    typeof: true,
    undefined: true,
    var: true,
    void: true,
    while: true,
    with: true,
    yield: true
});

function getSafeName(baseName, usedNames) {
    let safeName = baseName;
    let count = 1;
    while (usedNames.has(safeName) || RESERVED_NAMES[safeName]) {
        safeName = `${baseName}$${toBase64(count++)}`;
    }
    usedNames.add(safeName);
    return safeName;
}

class CallOptions {
    constructor({ withNew = false, args = [], callIdentifier = undefined } = {}) {
        this.withNew = withNew;
        this.args = args;
        this.callIdentifier = callIdentifier;
    }
    static create(callOptions) {
        return new this(callOptions);
    }
    equals(callOptions) {
        return callOptions && this.callIdentifier === callOptions.callIdentifier;
    }
}

const UNKNOWN_KEY = { UNKNOWN_KEY: true };
const EMPTY_PATH = [];
const UNKNOWN_PATH = [UNKNOWN_KEY];
function assembleMemberDescriptions(memberDescriptions, inheritedDescriptions = null) {
    return Object.create(inheritedDescriptions, memberDescriptions);
}
const UNKNOWN_VALUE = { UNKNOWN_VALUE: true };
const UNKNOWN_EXPRESSION = {
    deoptimizePath: () => { },
    getLiteralValueAtPath: () => UNKNOWN_VALUE,
    getReturnExpressionWhenCalledAtPath: () => UNKNOWN_EXPRESSION,
    hasEffectsWhenAccessedAtPath: path => path.length > 0,
    hasEffectsWhenAssignedAtPath: path => path.length > 0,
    hasEffectsWhenCalledAtPath: () => true,
    include: () => { },
    includeCallArguments(args) {
        for (const arg of args) {
            arg.include(false);
        }
    },
    included: true,
    toString: () => '[[UNKNOWN]]'
};
const UNDEFINED_EXPRESSION = {
    deoptimizePath: () => { },
    getLiteralValueAtPath: () => undefined,
    getReturnExpressionWhenCalledAtPath: () => UNKNOWN_EXPRESSION,
    hasEffectsWhenAccessedAtPath: path => path.length > 0,
    hasEffectsWhenAssignedAtPath: path => path.length > 0,
    hasEffectsWhenCalledAtPath: () => true,
    include: () => { },
    includeCallArguments() { },
    included: true,
    toString: () => 'undefined'
};
const returnsUnknown = {
    value: {
        callsArgs: null,
        mutatesSelf: false,
        returns: null,
        returnsPrimitive: UNKNOWN_EXPRESSION
    }
};
const mutatesSelfReturnsUnknown = {
    value: { returns: null, returnsPrimitive: UNKNOWN_EXPRESSION, callsArgs: null, mutatesSelf: true }
};
const callsArgReturnsUnknown = {
    value: { returns: null, returnsPrimitive: UNKNOWN_EXPRESSION, callsArgs: [0], mutatesSelf: false }
};
class UnknownArrayExpression {
    constructor() {
        this.included = false;
    }
    deoptimizePath() { }
    getLiteralValueAtPath() {
        return UNKNOWN_VALUE;
    }
    getReturnExpressionWhenCalledAtPath(path) {
        if (path.length === 1) {
            return getMemberReturnExpressionWhenCalled(arrayMembers, path[0]);
        }
        return UNKNOWN_EXPRESSION;
    }
    hasEffectsWhenAccessedAtPath(path) {
        return path.length > 1;
    }
    hasEffectsWhenAssignedAtPath(path) {
        return path.length > 1;
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        if (path.length === 1) {
            return hasMemberEffectWhenCalled(arrayMembers, path[0], this.included, callOptions, options);
        }
        return true;
    }
    include() {
        this.included = true;
    }
    includeCallArguments(args) {
        for (const arg of args) {
            arg.include(false);
        }
    }
    toString() {
        return '[[UNKNOWN ARRAY]]';
    }
}
const returnsArray = {
    value: {
        callsArgs: null,
        mutatesSelf: false,
        returns: UnknownArrayExpression,
        returnsPrimitive: null
    }
};
const mutatesSelfReturnsArray = {
    value: {
        callsArgs: null,
        mutatesSelf: true,
        returns: UnknownArrayExpression,
        returnsPrimitive: null
    }
};
const callsArgReturnsArray = {
    value: {
        callsArgs: [0],
        mutatesSelf: false,
        returns: UnknownArrayExpression,
        returnsPrimitive: null
    }
};
const callsArgMutatesSelfReturnsArray = {
    value: {
        callsArgs: [0],
        mutatesSelf: true,
        returns: UnknownArrayExpression,
        returnsPrimitive: null
    }
};
const UNKNOWN_LITERAL_BOOLEAN = {
    deoptimizePath: () => { },
    getLiteralValueAtPath: () => UNKNOWN_VALUE,
    getReturnExpressionWhenCalledAtPath: path => {
        if (path.length === 1) {
            return getMemberReturnExpressionWhenCalled(literalBooleanMembers, path[0]);
        }
        return UNKNOWN_EXPRESSION;
    },
    hasEffectsWhenAccessedAtPath: path => path.length > 1,
    hasEffectsWhenAssignedAtPath: path => path.length > 0,
    hasEffectsWhenCalledAtPath: path => {
        if (path.length === 1) {
            const subPath = path[0];
            return typeof subPath !== 'string' || !literalBooleanMembers[subPath];
        }
        return true;
    },
    include: () => { },
    includeCallArguments(args) {
        for (const arg of args) {
            arg.include(false);
        }
    },
    included: true,
    toString: () => '[[UNKNOWN BOOLEAN]]'
};
const returnsBoolean = {
    value: {
        callsArgs: null,
        mutatesSelf: false,
        returns: null,
        returnsPrimitive: UNKNOWN_LITERAL_BOOLEAN
    }
};
const callsArgReturnsBoolean = {
    value: {
        callsArgs: [0],
        mutatesSelf: false,
        returns: null,
        returnsPrimitive: UNKNOWN_LITERAL_BOOLEAN
    }
};
const UNKNOWN_LITERAL_NUMBER = {
    deoptimizePath: () => { },
    getLiteralValueAtPath: () => UNKNOWN_VALUE,
    getReturnExpressionWhenCalledAtPath: path => {
        if (path.length === 1) {
            return getMemberReturnExpressionWhenCalled(literalNumberMembers, path[0]);
        }
        return UNKNOWN_EXPRESSION;
    },
    hasEffectsWhenAccessedAtPath: path => path.length > 1,
    hasEffectsWhenAssignedAtPath: path => path.length > 0,
    hasEffectsWhenCalledAtPath: path => {
        if (path.length === 1) {
            const subPath = path[0];
            return typeof subPath !== 'string' || !literalNumberMembers[subPath];
        }
        return true;
    },
    include: () => { },
    includeCallArguments(args) {
        for (const arg of args) {
            arg.include(false);
        }
    },
    included: true,
    toString: () => '[[UNKNOWN NUMBER]]'
};
const returnsNumber = {
    value: {
        callsArgs: null,
        mutatesSelf: false,
        returns: null,
        returnsPrimitive: UNKNOWN_LITERAL_NUMBER
    }
};
const mutatesSelfReturnsNumber = {
    value: {
        callsArgs: null,
        mutatesSelf: true,
        returns: null,
        returnsPrimitive: UNKNOWN_LITERAL_NUMBER
    }
};
const callsArgReturnsNumber = {
    value: {
        callsArgs: [0],
        mutatesSelf: false,
        returns: null,
        returnsPrimitive: UNKNOWN_LITERAL_NUMBER
    }
};
const UNKNOWN_LITERAL_STRING = {
    deoptimizePath: () => { },
    getLiteralValueAtPath: () => UNKNOWN_VALUE,
    getReturnExpressionWhenCalledAtPath: path => {
        if (path.length === 1) {
            return getMemberReturnExpressionWhenCalled(literalStringMembers, path[0]);
        }
        return UNKNOWN_EXPRESSION;
    },
    hasEffectsWhenAccessedAtPath: path => path.length > 1,
    hasEffectsWhenAssignedAtPath: path => path.length > 0,
    hasEffectsWhenCalledAtPath: (path, callOptions, options) => {
        if (path.length === 1) {
            return hasMemberEffectWhenCalled(literalStringMembers, path[0], true, callOptions, options);
        }
        return true;
    },
    include: () => { },
    includeCallArguments(args) {
        for (const arg of args) {
            arg.include(false);
        }
    },
    included: true,
    toString: () => '[[UNKNOWN STRING]]'
};
const returnsString = {
    value: {
        callsArgs: null,
        mutatesSelf: false,
        returns: null,
        returnsPrimitive: UNKNOWN_LITERAL_STRING
    }
};
class UnknownObjectExpression {
    constructor() {
        this.included = false;
    }
    deoptimizePath() { }
    getLiteralValueAtPath() {
        return UNKNOWN_VALUE;
    }
    getReturnExpressionWhenCalledAtPath(path) {
        if (path.length === 1) {
            return getMemberReturnExpressionWhenCalled(objectMembers, path[0]);
        }
        return UNKNOWN_EXPRESSION;
    }
    hasEffectsWhenAccessedAtPath(path) {
        return path.length > 1;
    }
    hasEffectsWhenAssignedAtPath(path) {
        return path.length > 1;
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        if (path.length === 1) {
            return hasMemberEffectWhenCalled(objectMembers, path[0], this.included, callOptions, options);
        }
        return true;
    }
    include() {
        this.included = true;
    }
    includeCallArguments(args) {
        for (const arg of args) {
            arg.include(false);
        }
    }
    toString() {
        return '[[UNKNOWN OBJECT]]';
    }
}
const objectMembers = assembleMemberDescriptions({
    hasOwnProperty: returnsBoolean,
    isPrototypeOf: returnsBoolean,
    propertyIsEnumerable: returnsBoolean,
    toLocaleString: returnsString,
    toString: returnsString,
    valueOf: returnsUnknown
});
const arrayMembers = assembleMemberDescriptions({
    concat: returnsArray,
    copyWithin: mutatesSelfReturnsArray,
    every: callsArgReturnsBoolean,
    fill: mutatesSelfReturnsArray,
    filter: callsArgReturnsArray,
    find: callsArgReturnsUnknown,
    findIndex: callsArgReturnsNumber,
    forEach: callsArgReturnsUnknown,
    includes: returnsBoolean,
    indexOf: returnsNumber,
    join: returnsString,
    lastIndexOf: returnsNumber,
    map: callsArgReturnsArray,
    pop: mutatesSelfReturnsUnknown,
    push: mutatesSelfReturnsNumber,
    reduce: callsArgReturnsUnknown,
    reduceRight: callsArgReturnsUnknown,
    reverse: mutatesSelfReturnsArray,
    shift: mutatesSelfReturnsUnknown,
    slice: returnsArray,
    some: callsArgReturnsBoolean,
    sort: callsArgMutatesSelfReturnsArray,
    splice: mutatesSelfReturnsArray,
    unshift: mutatesSelfReturnsNumber
}, objectMembers);
const literalBooleanMembers = assembleMemberDescriptions({
    valueOf: returnsBoolean
}, objectMembers);
const literalNumberMembers = assembleMemberDescriptions({
    toExponential: returnsString,
    toFixed: returnsString,
    toLocaleString: returnsString,
    toPrecision: returnsString,
    valueOf: returnsNumber
}, objectMembers);
const literalStringMembers = assembleMemberDescriptions({
    charAt: returnsString,
    charCodeAt: returnsNumber,
    codePointAt: returnsNumber,
    concat: returnsString,
    endsWith: returnsBoolean,
    includes: returnsBoolean,
    indexOf: returnsNumber,
    lastIndexOf: returnsNumber,
    localeCompare: returnsNumber,
    match: returnsBoolean,
    normalize: returnsString,
    padEnd: returnsString,
    padStart: returnsString,
    repeat: returnsString,
    replace: {
        value: {
            callsArgs: [1],
            mutatesSelf: false,
            returns: null,
            returnsPrimitive: UNKNOWN_LITERAL_STRING
        }
    },
    search: returnsNumber,
    slice: returnsString,
    split: returnsArray,
    startsWith: returnsBoolean,
    substr: returnsString,
    substring: returnsString,
    toLocaleLowerCase: returnsString,
    toLocaleUpperCase: returnsString,
    toLowerCase: returnsString,
    toUpperCase: returnsString,
    trim: returnsString,
    valueOf: returnsString
}, objectMembers);
function getLiteralMembersForValue(value) {
    switch (typeof value) {
        case 'boolean':
            return literalBooleanMembers;
        case 'number':
            return literalNumberMembers;
        case 'string':
            return literalStringMembers;
        default:
            return Object.create(null);
    }
}
function hasMemberEffectWhenCalled(members, memberName, parentIncluded, callOptions, options) {
    if (typeof memberName !== 'string' || !members[memberName])
        return true;
    if (members[memberName].mutatesSelf && parentIncluded)
        return true;
    if (!members[memberName].callsArgs)
        return false;
    for (const argIndex of members[memberName].callsArgs) {
        if (callOptions.args[argIndex] &&
            callOptions.args[argIndex].hasEffectsWhenCalledAtPath(EMPTY_PATH, CallOptions.create({
                args: [],
                callIdentifier: {},
                withNew: false
            }), options.getHasEffectsWhenCalledOptions()))
            return true;
    }
    return false;
}
function getMemberReturnExpressionWhenCalled(members, memberName) {
    if (typeof memberName !== 'string' || !members[memberName])
        return UNKNOWN_EXPRESSION;
    return members[memberName].returnsPrimitive !== null
        ? members[memberName].returnsPrimitive
        : new members[memberName].returns();
}

class Variable {
    constructor(name) {
        this.alwaysRendered = false;
        this.exportName = null;
        this.included = false;
        this.isId = false;
        this.isReassigned = false;
        this.renderBaseName = null;
        this.renderName = null;
        this.safeExportName = null;
        this.name = name;
    }
    /**
     * Binds identifiers that reference this variable to this variable.
     * Necessary to be able to change variable names.
     */
    addReference(_identifier) { }
    deoptimizePath(_path) { }
    getBaseVariableName() {
        return this.renderBaseName || this.renderName || this.name;
    }
    getLiteralValueAtPath(_path, _recursionTracker, _origin) {
        return UNKNOWN_VALUE;
    }
    getName() {
        const name = this.renderName || this.name;
        return this.renderBaseName ? `${this.renderBaseName}.${name}` : name;
    }
    getReturnExpressionWhenCalledAtPath(_path, _recursionTracker, _origin) {
        return UNKNOWN_EXPRESSION;
    }
    hasEffectsWhenAccessedAtPath(path, _options) {
        return path.length > 0;
    }
    hasEffectsWhenAssignedAtPath(_path, _options) {
        return true;
    }
    hasEffectsWhenCalledAtPath(_path, _callOptions, _options) {
        return true;
    }
    /**
     * Marks this variable as being part of the bundle, which is usually the case when one of
     * its identifiers becomes part of the bundle. Returns true if it has not been included
     * previously.
     * Once a variable is included, it should take care all its declarations are included.
     */
    include() {
        this.included = true;
    }
    includeCallArguments(args) {
        for (const arg of args) {
            arg.include(false);
        }
    }
    markCalledFromTryStatement() { }
    setRenderNames(baseName, name) {
        this.renderBaseName = baseName;
        this.renderName = name;
    }
    setSafeName(name) {
        this.renderName = name;
    }
    toString() {
        return this.name;
    }
}

class ExternalVariable extends Variable {
    constructor(module, name) {
        super(name);
        this.module = module;
        this.isNamespace = name === '*';
        this.referenced = false;
    }
    addReference(identifier) {
        this.referenced = true;
        if (this.name === 'default' || this.name === '*') {
            this.module.suggestName(identifier.name);
        }
    }
    include() {
        if (!this.included) {
            this.included = true;
            this.module.used = true;
        }
    }
}

const reservedWords = 'break case class catch const continue debugger default delete do else export extends finally for function if import in instanceof let new return super switch this throw try typeof var void while with yield enum await implements package protected static interface private public'.split(' ');
const builtins = 'Infinity NaN undefined null true false eval uneval isFinite isNaN parseFloat parseInt decodeURI decodeURIComponent encodeURI encodeURIComponent escape unescape Object Function Boolean Symbol Error EvalError InternalError RangeError ReferenceError SyntaxError TypeError URIError Number Math Date String RegExp Array Int8Array Uint8Array Uint8ClampedArray Int16Array Uint16Array Int32Array Uint32Array Float32Array Float64Array Map Set WeakMap WeakSet SIMD ArrayBuffer DataView JSON Promise Generator GeneratorFunction Reflect Proxy Intl'.split(' ');
const blacklisted = Object.create(null);
reservedWords.concat(builtins).forEach(word => (blacklisted[word] = true));
const illegalCharacters = /[^$_a-zA-Z0-9]/g;
const startsWithDigit = (str) => /\d/.test(str[0]);
function isLegal(str) {
    if (startsWithDigit(str) || blacklisted[str]) {
        return false;
    }
    return !illegalCharacters.test(str);
}
function makeLegal(str) {
    str = str.replace(/-(\w)/g, (_, letter) => letter.toUpperCase()).replace(illegalCharacters, '_');
    if (startsWithDigit(str) || blacklisted[str])
        str = `_${str}`;
    return str || '_';
}

class ExternalModule {
    constructor(graph, id, moduleSideEffects) {
        this.exportsNames = false;
        this.exportsNamespace = false;
        this.mostCommonSuggestion = 0;
        this.reexported = false;
        this.renderPath = undefined;
        this.renormalizeRenderPath = false;
        this.used = false;
        this.graph = graph;
        this.id = id;
        this.execIndex = Infinity;
        this.moduleSideEffects = moduleSideEffects;
        const parts = id.split(/[\\/]/);
        this.variableName = makeLegal(parts.pop());
        this.nameSuggestions = Object.create(null);
        this.declarations = Object.create(null);
        this.exportedVariables = new Map();
    }
    getVariableForExportName(name, _isExportAllSearch) {
        if (name === '*') {
            this.exportsNamespace = true;
        }
        else if (name !== 'default') {
            this.exportsNames = true;
        }
        let declaration = this.declarations[name];
        if (declaration)
            return declaration;
        this.declarations[name] = declaration = new ExternalVariable(this, name);
        this.exportedVariables.set(declaration, name);
        return declaration;
    }
    setRenderPath(options, inputBase) {
        this.renderPath = '';
        if (options.paths) {
            this.renderPath =
                typeof options.paths === 'function' ? options.paths(this.id) : options.paths[this.id];
        }
        if (!this.renderPath) {
            if (!index.isAbsolute(this.id)) {
                this.renderPath = this.id;
            }
            else {
                this.renderPath = index.normalize(path.relative(inputBase, this.id));
                this.renormalizeRenderPath = true;
            }
        }
        return this.renderPath;
    }
    suggestName(name) {
        if (!this.nameSuggestions[name])
            this.nameSuggestions[name] = 0;
        this.nameSuggestions[name] += 1;
        if (this.nameSuggestions[name] > this.mostCommonSuggestion) {
            this.mostCommonSuggestion = this.nameSuggestions[name];
            this.variableName = name;
        }
    }
    warnUnusedImports() {
        const unused = Object.keys(this.declarations).filter(name => {
            if (name === '*')
                return false;
            const declaration = this.declarations[name];
            return !declaration.included && !this.reexported && !declaration.referenced;
        });
        if (unused.length === 0)
            return;
        const names = unused.length === 1
            ? `'${unused[0]}' is`
            : `${unused
                .slice(0, -1)
                .map(name => `'${name}'`)
                .join(', ')} and '${unused.slice(-1)}' are`;
        this.graph.warn({
            code: 'UNUSED_EXTERNAL_IMPORT',
            message: `${names} imported from external module '${this.id}' but never used`,
            names: unused,
            source: this.id
        });
    }
}

function markModuleAndImpureDependenciesAsExecuted(baseModule) {
    baseModule.isExecuted = true;
    const modules = [baseModule];
    const visitedModules = new Set();
    for (const module of modules) {
        for (const dependency of module.dependencies) {
            if (!(dependency instanceof ExternalModule) &&
                !dependency.isExecuted &&
                dependency.moduleSideEffects &&
                !visitedModules.has(dependency.id)) {
                dependency.isExecuted = true;
                visitedModules.add(dependency.id);
                modules.push(dependency);
            }
        }
    }
}

// To avoid infinite recursions
const MAX_PATH_DEPTH = 7;
class LocalVariable extends Variable {
    constructor(name, declarator, init, context) {
        super(name);
        this.additionalInitializers = null;
        this.calledFromTryStatement = false;
        this.expressionsToBeDeoptimized = [];
        this.declarations = declarator ? [declarator] : [];
        this.init = init;
        this.deoptimizationTracker = context.deoptimizationTracker;
        this.module = context.module;
    }
    addDeclaration(identifier, init) {
        this.declarations.push(identifier);
        if (this.additionalInitializers === null) {
            this.additionalInitializers = this.init === null ? [] : [this.init];
            this.init = UNKNOWN_EXPRESSION;
            this.isReassigned = true;
        }
        if (init !== null) {
            this.additionalInitializers.push(init);
        }
    }
    consolidateInitializers() {
        if (this.additionalInitializers !== null) {
            for (const initializer of this.additionalInitializers) {
                initializer.deoptimizePath(UNKNOWN_PATH);
            }
            this.additionalInitializers = null;
        }
    }
    deoptimizePath(path) {
        if (path.length > MAX_PATH_DEPTH)
            return;
        if (!(this.isReassigned || this.deoptimizationTracker.track(this, path))) {
            if (path.length === 0) {
                if (!this.isReassigned) {
                    this.isReassigned = true;
                    for (const expression of this.expressionsToBeDeoptimized) {
                        expression.deoptimizeCache();
                    }
                    if (this.init) {
                        this.init.deoptimizePath(UNKNOWN_PATH);
                    }
                }
            }
            else if (this.init) {
                this.init.deoptimizePath(path);
            }
        }
    }
    getLiteralValueAtPath(path, recursionTracker, origin) {
        if (this.isReassigned ||
            !this.init ||
            path.length > MAX_PATH_DEPTH ||
            recursionTracker.isTracked(this.init, path)) {
            return UNKNOWN_VALUE;
        }
        this.expressionsToBeDeoptimized.push(origin);
        return this.init.getLiteralValueAtPath(path, recursionTracker.track(this.init, path), origin);
    }
    getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin) {
        if (this.isReassigned ||
            !this.init ||
            path.length > MAX_PATH_DEPTH ||
            recursionTracker.isTracked(this.init, path)) {
            return UNKNOWN_EXPRESSION;
        }
        this.expressionsToBeDeoptimized.push(origin);
        return this.init.getReturnExpressionWhenCalledAtPath(path, recursionTracker.track(this.init, path), origin);
    }
    hasEffectsWhenAccessedAtPath(path, options) {
        if (path.length === 0)
            return false;
        return (this.isReassigned ||
            path.length > MAX_PATH_DEPTH ||
            (this.init &&
                !options.hasNodeBeenAccessedAtPath(path, this.init) &&
                this.init.hasEffectsWhenAccessedAtPath(path, options.addAccessedNodeAtPath(path, this.init))));
    }
    hasEffectsWhenAssignedAtPath(path, options) {
        if (this.included || path.length > MAX_PATH_DEPTH)
            return true;
        if (path.length === 0)
            return false;
        return (this.isReassigned ||
            (this.init &&
                !options.hasNodeBeenAssignedAtPath(path, this.init) &&
                this.init.hasEffectsWhenAssignedAtPath(path, options.addAssignedNodeAtPath(path, this.init))));
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        if (path.length > MAX_PATH_DEPTH)
            return true;
        return (this.isReassigned ||
            (this.init &&
                !options.hasNodeBeenCalledAtPathWithOptions(path, this.init, callOptions) &&
                this.init.hasEffectsWhenCalledAtPath(path, callOptions, options.addCalledNodeAtPathWithOptions(path, this.init, callOptions))));
    }
    include() {
        if (!this.included) {
            this.included = true;
            if (!this.module.isExecuted) {
                markModuleAndImpureDependenciesAsExecuted(this.module);
            }
            for (const declaration of this.declarations) {
                // If node is a default export, it can save a tree-shaking run to include the full declaration now
                if (!declaration.included)
                    declaration.include(false);
                let node = declaration.parent;
                while (!node.included) {
                    // We do not want to properly include parents in case they are part of a dead branch
                    // in which case .include() might pull in more dead code
                    node.included = true;
                    if (node.type === Program)
                        break;
                    node = node.parent;
                }
            }
        }
    }
    includeCallArguments(args) {
        if (this.isReassigned) {
            for (const arg of args) {
                arg.include(false);
            }
        }
        else if (this.init) {
            this.init.includeCallArguments(args);
        }
    }
    markCalledFromTryStatement() {
        this.calledFromTryStatement = true;
    }
}

class Scope {
    constructor() {
        this.children = [];
        this.variables = new Map();
    }
    addDeclaration(identifier, context, init = null, _isHoisted) {
        const name = identifier.name;
        let variable = this.variables.get(name);
        if (variable) {
            variable.addDeclaration(identifier, init);
        }
        else {
            variable = new LocalVariable(identifier.name, identifier, init || UNDEFINED_EXPRESSION, context);
            this.variables.set(name, variable);
        }
        return variable;
    }
    contains(name) {
        return this.variables.has(name);
    }
    findVariable(_name) {
        throw new Error('Internal Error: findVariable needs to be implemented by a subclass');
    }
}

class ChildScope extends Scope {
    constructor(parent) {
        super();
        this.accessedOutsideVariables = new Map();
        this.parent = parent;
        parent.children.push(this);
    }
    addAccessedGlobalsByFormat(globalsByFormat) {
        let accessedGlobalVariablesByFormat = this.accessedGlobalVariablesByFormat;
        if (!accessedGlobalVariablesByFormat) {
            accessedGlobalVariablesByFormat = this.accessedGlobalVariablesByFormat = new Map();
        }
        for (const format of Object.keys(globalsByFormat)) {
            let accessedGlobalVariables = accessedGlobalVariablesByFormat.get(format);
            if (!accessedGlobalVariables) {
                accessedGlobalVariables = new Set();
                accessedGlobalVariablesByFormat.set(format, accessedGlobalVariables);
            }
            for (const name of globalsByFormat[format]) {
                accessedGlobalVariables.add(name);
            }
        }
        if (this.parent instanceof ChildScope) {
            this.parent.addAccessedGlobalsByFormat(globalsByFormat);
        }
    }
    addNamespaceMemberAccess(name, variable) {
        this.accessedOutsideVariables.set(name, variable);
        if (this.parent instanceof ChildScope) {
            this.parent.addNamespaceMemberAccess(name, variable);
        }
    }
    addReturnExpression(expression) {
        this.parent instanceof ChildScope && this.parent.addReturnExpression(expression);
    }
    contains(name) {
        return this.variables.has(name) || this.parent.contains(name);
    }
    deconflict(format) {
        const usedNames = new Set();
        for (const variable of this.accessedOutsideVariables.values()) {
            if (variable.included) {
                usedNames.add(variable.getBaseVariableName());
                if (variable.exportName && format === 'system') {
                    usedNames.add('exports');
                }
            }
        }
        const accessedGlobalVariables = this.accessedGlobalVariablesByFormat && this.accessedGlobalVariablesByFormat.get(format);
        if (accessedGlobalVariables) {
            for (const name of accessedGlobalVariables) {
                usedNames.add(name);
            }
        }
        for (const [name, variable] of this.variables) {
            if (variable.included || variable.alwaysRendered) {
                variable.setSafeName(getSafeName(name, usedNames));
            }
        }
        for (const scope of this.children) {
            scope.deconflict(format);
        }
    }
    findLexicalBoundary() {
        return this.parent instanceof ChildScope ? this.parent.findLexicalBoundary() : this;
    }
    findVariable(name) {
        const knownVariable = this.variables.get(name) || this.accessedOutsideVariables.get(name);
        if (knownVariable) {
            return knownVariable;
        }
        const variable = this.parent.findVariable(name);
        this.accessedOutsideVariables.set(name, variable);
        return variable;
    }
}

function getLocator$1(source, options) {
    if (options === void 0) {
        options = {};
    }
    var offsetLine = options.offsetLine || 0;
    var offsetColumn = options.offsetColumn || 0;
    var originalLines = source.split('\n');
    var start = 0;
    var lineRanges = originalLines.map(function (line, i) {
        var end = start + line.length + 1;
        var range = { start: start, end: end, line: i };
        start = end;
        return range;
    });
    var i = 0;
    function rangeContains(range, index) {
        return range.start <= index && index < range.end;
    }
    function getLocation(range, index) {
        return { line: offsetLine + range.line, column: offsetColumn + index - range.start, character: index };
    }
    function locate(search, startIndex) {
        if (typeof search === 'string') {
            search = source.indexOf(search, startIndex || 0);
        }
        var range = lineRanges[i];
        var d = search >= range.end ? 1 : -1;
        while (range) {
            if (rangeContains(range, search))
                return getLocation(range, search);
            i += d;
            range = lineRanges[i];
        }
    }
    return locate;
}
function locate(source, search, options) {
    if (typeof options === 'number') {
        throw new Error('locate takes a { startIndex, offsetLine, offsetColumn } object as the third argument');
    }
    return getLocator$1(source, options)(search, options && options.startIndex);
}

/**
 * Copyright (c) 2014-present, Facebook, Inc.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
// Used for setting prototype methods that IE8 chokes on.
var DELETE = 'delete';
// Constants describing the size of trie nodes.
var SHIFT = 5; // Resulted in best performance after ______?
var SIZE = 1 << SHIFT;
var MASK = SIZE - 1;
// A consistent shared value representing "not set" which equals nothing other
// than itself, and nothing that could be provided externally.
var NOT_SET = {};
// Boolean references, Rough equivalent of `bool &`.
function MakeRef() {
    return { value: false };
}
function SetRef(ref) {
    if (ref) {
        ref.value = true;
    }
}
// A function which returns a value representing an "owner" for transient writes
// to tries. The return value will only ever equal itself, and will not equal
// the return of any subsequent call of this function.
function OwnerID() { }
function ensureSize(iter) {
    if (iter.size === undefined) {
        iter.size = iter.__iterate(returnTrue);
    }
    return iter.size;
}
function wrapIndex(iter, index) {
    // This implements "is array index" which the ECMAString spec defines as:
    //
    //     A String property name P is an array index if and only if
    //     ToString(ToUint32(P)) is equal to P and ToUint32(P) is not equal
    //     to 2^32−1.
    //
    // http://www.ecma-international.org/ecma-262/6.0/#sec-array-exotic-objects
    if (typeof index !== 'number') {
        var uint32Index = index >>> 0; // N >>> 0 is shorthand for ToUint32
        if ('' + uint32Index !== index || uint32Index === 4294967295) {
            return NaN;
        }
        index = uint32Index;
    }
    return index < 0 ? ensureSize(iter) + index : index;
}
function returnTrue() {
    return true;
}
function wholeSlice(begin, end, size) {
    return (((begin === 0 && !isNeg(begin)) ||
        (size !== undefined && begin <= -size)) &&
        (end === undefined || (size !== undefined && end >= size)));
}
function resolveBegin(begin, size) {
    return resolveIndex(begin, size, 0);
}
function resolveEnd(end, size) {
    return resolveIndex(end, size, size);
}
function resolveIndex(index, size, defaultIndex) {
    // Sanitize indices using this shorthand for ToInt32(argument)
    // http://www.ecma-international.org/ecma-262/6.0/#sec-toint32
    return index === undefined
        ? defaultIndex
        : isNeg(index)
            ? size === Infinity
                ? size
                : Math.max(0, size + index) | 0
            : size === undefined || size === index
                ? index
                : Math.min(size, index) | 0;
}
function isNeg(value) {
    // Account for -0 which is negative, but not less than 0.
    return value < 0 || (value === 0 && 1 / value === -Infinity);
}
// Note: value is unchanged to not break immutable-devtools.
var IS_COLLECTION_SYMBOL = '@@__IMMUTABLE_ITERABLE__@@';
function isCollection(maybeCollection) {
    return Boolean(maybeCollection && maybeCollection[IS_COLLECTION_SYMBOL]);
}
var IS_KEYED_SYMBOL = '@@__IMMUTABLE_KEYED__@@';
function isKeyed(maybeKeyed) {
    return Boolean(maybeKeyed && maybeKeyed[IS_KEYED_SYMBOL]);
}
var IS_INDEXED_SYMBOL = '@@__IMMUTABLE_INDEXED__@@';
function isIndexed(maybeIndexed) {
    return Boolean(maybeIndexed && maybeIndexed[IS_INDEXED_SYMBOL]);
}
function isAssociative(maybeAssociative) {
    return isKeyed(maybeAssociative) || isIndexed(maybeAssociative);
}
var Collection = function Collection(value) {
    return isCollection(value) ? value : Seq(value);
};
var KeyedCollection = /*@__PURE__*/ (function (Collection) {
    function KeyedCollection(value) {
        return isKeyed(value) ? value : KeyedSeq(value);
    }
    if (Collection)
        KeyedCollection.__proto__ = Collection;
    KeyedCollection.prototype = Object.create(Collection && Collection.prototype);
    KeyedCollection.prototype.constructor = KeyedCollection;
    return KeyedCollection;
}(Collection));
var IndexedCollection = /*@__PURE__*/ (function (Collection) {
    function IndexedCollection(value) {
        return isIndexed(value) ? value : IndexedSeq(value);
    }
    if (Collection)
        IndexedCollection.__proto__ = Collection;
    IndexedCollection.prototype = Object.create(Collection && Collection.prototype);
    IndexedCollection.prototype.constructor = IndexedCollection;
    return IndexedCollection;
}(Collection));
var SetCollection = /*@__PURE__*/ (function (Collection) {
    function SetCollection(value) {
        return isCollection(value) && !isAssociative(value) ? value : SetSeq(value);
    }
    if (Collection)
        SetCollection.__proto__ = Collection;
    SetCollection.prototype = Object.create(Collection && Collection.prototype);
    SetCollection.prototype.constructor = SetCollection;
    return SetCollection;
}(Collection));
Collection.Keyed = KeyedCollection;
Collection.Indexed = IndexedCollection;
Collection.Set = SetCollection;
var IS_SEQ_SYMBOL = '@@__IMMUTABLE_SEQ__@@';
function isSeq(maybeSeq) {
    return Boolean(maybeSeq && maybeSeq[IS_SEQ_SYMBOL]);
}
var IS_RECORD_SYMBOL = '@@__IMMUTABLE_RECORD__@@';
function isRecord(maybeRecord) {
    return Boolean(maybeRecord && maybeRecord[IS_RECORD_SYMBOL]);
}
function isImmutable(maybeImmutable) {
    return isCollection(maybeImmutable) || isRecord(maybeImmutable);
}
var IS_ORDERED_SYMBOL = '@@__IMMUTABLE_ORDERED__@@';
function isOrdered(maybeOrdered) {
    return Boolean(maybeOrdered && maybeOrdered[IS_ORDERED_SYMBOL]);
}
var ITERATE_KEYS = 0;
var ITERATE_VALUES = 1;
var ITERATE_ENTRIES = 2;
var REAL_ITERATOR_SYMBOL = typeof Symbol === 'function' && Symbol.iterator;
var FAUX_ITERATOR_SYMBOL = '@@iterator';
var ITERATOR_SYMBOL = REAL_ITERATOR_SYMBOL || FAUX_ITERATOR_SYMBOL;
var Iterator = function Iterator(next) {
    this.next = next;
};
Iterator.prototype.toString = function toString() {
    return '[Iterator]';
};
Iterator.KEYS = ITERATE_KEYS;
Iterator.VALUES = ITERATE_VALUES;
Iterator.ENTRIES = ITERATE_ENTRIES;
Iterator.prototype.inspect = Iterator.prototype.toSource = function () {
    return this.toString();
};
Iterator.prototype[ITERATOR_SYMBOL] = function () {
    return this;
};
function iteratorValue(type, k, v, iteratorResult) {
    var value = type === 0 ? k : type === 1 ? v : [k, v];
    iteratorResult
        ? (iteratorResult.value = value)
        : (iteratorResult = {
            value: value,
            done: false,
        });
    return iteratorResult;
}
function iteratorDone() {
    return { value: undefined, done: true };
}
function hasIterator(maybeIterable) {
    return !!getIteratorFn(maybeIterable);
}
function isIterator(maybeIterator) {
    return maybeIterator && typeof maybeIterator.next === 'function';
}
function getIterator(iterable) {
    var iteratorFn = getIteratorFn(iterable);
    return iteratorFn && iteratorFn.call(iterable);
}
function getIteratorFn(iterable) {
    var iteratorFn = iterable &&
        ((REAL_ITERATOR_SYMBOL && iterable[REAL_ITERATOR_SYMBOL]) ||
            iterable[FAUX_ITERATOR_SYMBOL]);
    if (typeof iteratorFn === 'function') {
        return iteratorFn;
    }
}
var hasOwnProperty = Object.prototype.hasOwnProperty;
function isArrayLike(value) {
    if (Array.isArray(value) || typeof value === 'string') {
        return true;
    }
    return (value &&
        typeof value === 'object' &&
        Number.isInteger(value.length) &&
        value.length >= 0 &&
        (value.length === 0
            ? // Only {length: 0} is considered Array-like.
                Object.keys(value).length === 1
            : // An object is only Array-like if it has a property where the last value
                // in the array-like may be found (which could be undefined).
                value.hasOwnProperty(value.length - 1)));
}
var Seq = /*@__PURE__*/ (function (Collection$$1) {
    function Seq(value) {
        return value === null || value === undefined
            ? emptySequence()
            : isImmutable(value)
                ? value.toSeq()
                : seqFromValue(value);
    }
    if (Collection$$1)
        Seq.__proto__ = Collection$$1;
    Seq.prototype = Object.create(Collection$$1 && Collection$$1.prototype);
    Seq.prototype.constructor = Seq;
    Seq.prototype.toSeq = function toSeq() {
        return this;
    };
    Seq.prototype.toString = function toString() {
        return this.__toString('Seq {', '}');
    };
    Seq.prototype.cacheResult = function cacheResult() {
        if (!this._cache && this.__iterateUncached) {
            this._cache = this.entrySeq().toArray();
            this.size = this._cache.length;
        }
        return this;
    };
    // abstract __iterateUncached(fn, reverse)
    Seq.prototype.__iterate = function __iterate(fn, reverse) {
        var cache = this._cache;
        if (cache) {
            var size = cache.length;
            var i = 0;
            while (i !== size) {
                var entry = cache[reverse ? size - ++i : i++];
                if (fn(entry[1], entry[0], this) === false) {
                    break;
                }
            }
            return i;
        }
        return this.__iterateUncached(fn, reverse);
    };
    // abstract __iteratorUncached(type, reverse)
    Seq.prototype.__iterator = function __iterator(type, reverse) {
        var cache = this._cache;
        if (cache) {
            var size = cache.length;
            var i = 0;
            return new Iterator(function () {
                if (i === size) {
                    return iteratorDone();
                }
                var entry = cache[reverse ? size - ++i : i++];
                return iteratorValue(type, entry[0], entry[1]);
            });
        }
        return this.__iteratorUncached(type, reverse);
    };
    return Seq;
}(Collection));
var KeyedSeq = /*@__PURE__*/ (function (Seq) {
    function KeyedSeq(value) {
        return value === null || value === undefined
            ? emptySequence().toKeyedSeq()
            : isCollection(value)
                ? isKeyed(value)
                    ? value.toSeq()
                    : value.fromEntrySeq()
                : isRecord(value)
                    ? value.toSeq()
                    : keyedSeqFromValue(value);
    }
    if (Seq)
        KeyedSeq.__proto__ = Seq;
    KeyedSeq.prototype = Object.create(Seq && Seq.prototype);
    KeyedSeq.prototype.constructor = KeyedSeq;
    KeyedSeq.prototype.toKeyedSeq = function toKeyedSeq() {
        return this;
    };
    return KeyedSeq;
}(Seq));
var IndexedSeq = /*@__PURE__*/ (function (Seq) {
    function IndexedSeq(value) {
        return value === null || value === undefined
            ? emptySequence()
            : isCollection(value)
                ? isKeyed(value)
                    ? value.entrySeq()
                    : value.toIndexedSeq()
                : isRecord(value)
                    ? value.toSeq().entrySeq()
                    : indexedSeqFromValue(value);
    }
    if (Seq)
        IndexedSeq.__proto__ = Seq;
    IndexedSeq.prototype = Object.create(Seq && Seq.prototype);
    IndexedSeq.prototype.constructor = IndexedSeq;
    IndexedSeq.of = function of( /*...values*/) {
        return IndexedSeq(arguments);
    };
    IndexedSeq.prototype.toIndexedSeq = function toIndexedSeq() {
        return this;
    };
    IndexedSeq.prototype.toString = function toString() {
        return this.__toString('Seq [', ']');
    };
    return IndexedSeq;
}(Seq));
var SetSeq = /*@__PURE__*/ (function (Seq) {
    function SetSeq(value) {
        return (isCollection(value) && !isAssociative(value)
            ? value
            : IndexedSeq(value)).toSetSeq();
    }
    if (Seq)
        SetSeq.__proto__ = Seq;
    SetSeq.prototype = Object.create(Seq && Seq.prototype);
    SetSeq.prototype.constructor = SetSeq;
    SetSeq.of = function of( /*...values*/) {
        return SetSeq(arguments);
    };
    SetSeq.prototype.toSetSeq = function toSetSeq() {
        return this;
    };
    return SetSeq;
}(Seq));
Seq.isSeq = isSeq;
Seq.Keyed = KeyedSeq;
Seq.Set = SetSeq;
Seq.Indexed = IndexedSeq;
Seq.prototype[IS_SEQ_SYMBOL] = true;
// #pragma Root Sequences
var ArraySeq = /*@__PURE__*/ (function (IndexedSeq) {
    function ArraySeq(array) {
        this._array = array;
        this.size = array.length;
    }
    if (IndexedSeq)
        ArraySeq.__proto__ = IndexedSeq;
    ArraySeq.prototype = Object.create(IndexedSeq && IndexedSeq.prototype);
    ArraySeq.prototype.constructor = ArraySeq;
    ArraySeq.prototype.get = function get(index, notSetValue) {
        return this.has(index) ? this._array[wrapIndex(this, index)] : notSetValue;
    };
    ArraySeq.prototype.__iterate = function __iterate(fn, reverse) {
        var array = this._array;
        var size = array.length;
        var i = 0;
        while (i !== size) {
            var ii = reverse ? size - ++i : i++;
            if (fn(array[ii], ii, this) === false) {
                break;
            }
        }
        return i;
    };
    ArraySeq.prototype.__iterator = function __iterator(type, reverse) {
        var array = this._array;
        var size = array.length;
        var i = 0;
        return new Iterator(function () {
            if (i === size) {
                return iteratorDone();
            }
            var ii = reverse ? size - ++i : i++;
            return iteratorValue(type, ii, array[ii]);
        });
    };
    return ArraySeq;
}(IndexedSeq));
var ObjectSeq = /*@__PURE__*/ (function (KeyedSeq) {
    function ObjectSeq(object) {
        var keys = Object.keys(object);
        this._object = object;
        this._keys = keys;
        this.size = keys.length;
    }
    if (KeyedSeq)
        ObjectSeq.__proto__ = KeyedSeq;
    ObjectSeq.prototype = Object.create(KeyedSeq && KeyedSeq.prototype);
    ObjectSeq.prototype.constructor = ObjectSeq;
    ObjectSeq.prototype.get = function get(key, notSetValue) {
        if (notSetValue !== undefined && !this.has(key)) {
            return notSetValue;
        }
        return this._object[key];
    };
    ObjectSeq.prototype.has = function has(key) {
        return hasOwnProperty.call(this._object, key);
    };
    ObjectSeq.prototype.__iterate = function __iterate(fn, reverse) {
        var object = this._object;
        var keys = this._keys;
        var size = keys.length;
        var i = 0;
        while (i !== size) {
            var key = keys[reverse ? size - ++i : i++];
            if (fn(object[key], key, this) === false) {
                break;
            }
        }
        return i;
    };
    ObjectSeq.prototype.__iterator = function __iterator(type, reverse) {
        var object = this._object;
        var keys = this._keys;
        var size = keys.length;
        var i = 0;
        return new Iterator(function () {
            if (i === size) {
                return iteratorDone();
            }
            var key = keys[reverse ? size - ++i : i++];
            return iteratorValue(type, key, object[key]);
        });
    };
    return ObjectSeq;
}(KeyedSeq));
ObjectSeq.prototype[IS_ORDERED_SYMBOL] = true;
var CollectionSeq = /*@__PURE__*/ (function (IndexedSeq) {
    function CollectionSeq(collection) {
        this._collection = collection;
        this.size = collection.length || collection.size;
    }
    if (IndexedSeq)
        CollectionSeq.__proto__ = IndexedSeq;
    CollectionSeq.prototype = Object.create(IndexedSeq && IndexedSeq.prototype);
    CollectionSeq.prototype.constructor = CollectionSeq;
    CollectionSeq.prototype.__iterateUncached = function __iterateUncached(fn, reverse) {
        if (reverse) {
            return this.cacheResult().__iterate(fn, reverse);
        }
        var collection = this._collection;
        var iterator = getIterator(collection);
        var iterations = 0;
        if (isIterator(iterator)) {
            var step;
            while (!(step = iterator.next()).done) {
                if (fn(step.value, iterations++, this) === false) {
                    break;
                }
            }
        }
        return iterations;
    };
    CollectionSeq.prototype.__iteratorUncached = function __iteratorUncached(type, reverse) {
        if (reverse) {
            return this.cacheResult().__iterator(type, reverse);
        }
        var collection = this._collection;
        var iterator = getIterator(collection);
        if (!isIterator(iterator)) {
            return new Iterator(iteratorDone);
        }
        var iterations = 0;
        return new Iterator(function () {
            var step = iterator.next();
            return step.done ? step : iteratorValue(type, iterations++, step.value);
        });
    };
    return CollectionSeq;
}(IndexedSeq));
// # pragma Helper functions
var EMPTY_SEQ;
function emptySequence() {
    return EMPTY_SEQ || (EMPTY_SEQ = new ArraySeq([]));
}
function keyedSeqFromValue(value) {
    var seq = Array.isArray(value)
        ? new ArraySeq(value)
        : hasIterator(value)
            ? new CollectionSeq(value)
            : undefined;
    if (seq) {
        return seq.fromEntrySeq();
    }
    if (typeof value === 'object') {
        return new ObjectSeq(value);
    }
    throw new TypeError('Expected Array or collection object of [k, v] entries, or keyed object: ' +
        value);
}
function indexedSeqFromValue(value) {
    var seq = maybeIndexedSeqFromValue(value);
    if (seq) {
        return seq;
    }
    throw new TypeError('Expected Array or collection object of values: ' + value);
}
function seqFromValue(value) {
    var seq = maybeIndexedSeqFromValue(value);
    if (seq) {
        return seq;
    }
    if (typeof value === 'object') {
        return new ObjectSeq(value);
    }
    throw new TypeError('Expected Array or collection object of values, or keyed object: ' + value);
}
function maybeIndexedSeqFromValue(value) {
    return isArrayLike(value)
        ? new ArraySeq(value)
        : hasIterator(value)
            ? new CollectionSeq(value)
            : undefined;
}
var IS_MAP_SYMBOL = '@@__IMMUTABLE_MAP__@@';
function isMap(maybeMap) {
    return Boolean(maybeMap && maybeMap[IS_MAP_SYMBOL]);
}
function isOrderedMap(maybeOrderedMap) {
    return isMap(maybeOrderedMap) && isOrdered(maybeOrderedMap);
}
function isValueObject(maybeValue) {
    return Boolean(maybeValue &&
        typeof maybeValue.equals === 'function' &&
        typeof maybeValue.hashCode === 'function');
}
/**
 * An extension of the "same-value" algorithm as [described for use by ES6 Map
 * and Set](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Map#Key_equality)
 *
 * NaN is considered the same as NaN, however -0 and 0 are considered the same
 * value, which is different from the algorithm described by
 * [`Object.is`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/is).
 *
 * This is extended further to allow Objects to describe the values they
 * represent, by way of `valueOf` or `equals` (and `hashCode`).
 *
 * Note: because of this extension, the key equality of Immutable.Map and the
 * value equality of Immutable.Set will differ from ES6 Map and Set.
 *
 * ### Defining custom values
 *
 * The easiest way to describe the value an object represents is by implementing
 * `valueOf`. For example, `Date` represents a value by returning a unix
 * timestamp for `valueOf`:
 *
 *     var date1 = new Date(1234567890000); // Fri Feb 13 2009 ...
 *     var date2 = new Date(1234567890000);
 *     date1.valueOf(); // 1234567890000
 *     assert( date1 !== date2 );
 *     assert( Immutable.is( date1, date2 ) );
 *
 * Note: overriding `valueOf` may have other implications if you use this object
 * where JavaScript expects a primitive, such as implicit string coercion.
 *
 * For more complex types, especially collections, implementing `valueOf` may
 * not be performant. An alternative is to implement `equals` and `hashCode`.
 *
 * `equals` takes another object, presumably of similar type, and returns true
 * if it is equal. Equality is symmetrical, so the same result should be
 * returned if this and the argument are flipped.
 *
 *     assert( a.equals(b) === b.equals(a) );
 *
 * `hashCode` returns a 32bit integer number representing the object which will
 * be used to determine how to store the value object in a Map or Set. You must
 * provide both or neither methods, one must not exist without the other.
 *
 * Also, an important relationship between these methods must be upheld: if two
 * values are equal, they *must* return the same hashCode. If the values are not
 * equal, they might have the same hashCode; this is called a hash collision,
 * and while undesirable for performance reasons, it is acceptable.
 *
 *     if (a.equals(b)) {
 *       assert( a.hashCode() === b.hashCode() );
 *     }
 *
 * All Immutable collections are Value Objects: they implement `equals()`
 * and `hashCode()`.
 */
function is(valueA, valueB) {
    if (valueA === valueB || (valueA !== valueA && valueB !== valueB)) {
        return true;
    }
    if (!valueA || !valueB) {
        return false;
    }
    if (typeof valueA.valueOf === 'function' &&
        typeof valueB.valueOf === 'function') {
        valueA = valueA.valueOf();
        valueB = valueB.valueOf();
        if (valueA === valueB || (valueA !== valueA && valueB !== valueB)) {
            return true;
        }
        if (!valueA || !valueB) {
            return false;
        }
    }
    return !!(isValueObject(valueA) &&
        isValueObject(valueB) &&
        valueA.equals(valueB));
}
var imul = typeof Math.imul === 'function' && Math.imul(0xffffffff, 2) === -2
    ? Math.imul
    : function imul(a, b) {
        a |= 0; // int
        b |= 0; // int
        var c = a & 0xffff;
        var d = b & 0xffff;
        // Shift by 0 fixes the sign on the high part.
        return (c * d + ((((a >>> 16) * d + c * (b >>> 16)) << 16) >>> 0)) | 0; // int
    };
// v8 has an optimization for storing 31-bit signed numbers.
// Values which have either 00 or 11 as the high order bits qualify.
// This function drops the highest order bit in a signed number, maintaining
// the sign bit.
function smi(i32) {
    return ((i32 >>> 1) & 0x40000000) | (i32 & 0xbfffffff);
}
var defaultValueOf = Object.prototype.valueOf;
function hash(o) {
    switch (typeof o) {
        case 'boolean':
            // The hash values for built-in constants are a 1 value for each 5-byte
            // shift region expect for the first, which encodes the value. This
            // reduces the odds of a hash collision for these common values.
            return o ? 0x42108421 : 0x42108420;
        case 'number':
            return hashNumber(o);
        case 'string':
            return o.length > STRING_HASH_CACHE_MIN_STRLEN
                ? cachedHashString(o)
                : hashString(o);
        case 'object':
        case 'function':
            if (o === null) {
                return 0x42108422;
            }
            if (typeof o.hashCode === 'function') {
                // Drop any high bits from accidentally long hash codes.
                return smi(o.hashCode(o));
            }
            if (o.valueOf !== defaultValueOf && typeof o.valueOf === 'function') {
                o = o.valueOf(o);
            }
            return hashJSObj(o);
        case 'undefined':
            return 0x42108423;
        default:
            if (typeof o.toString === 'function') {
                return hashString(o.toString());
            }
            throw new Error('Value type ' + typeof o + ' cannot be hashed.');
    }
}
// Compress arbitrarily large numbers into smi hashes.
function hashNumber(n) {
    if (n !== n || n === Infinity) {
        return 0;
    }
    var hash = n | 0;
    if (hash !== n) {
        hash ^= n * 0xffffffff;
    }
    while (n > 0xffffffff) {
        n /= 0xffffffff;
        hash ^= n;
    }
    return smi(hash);
}
function cachedHashString(string) {
    var hashed = stringHashCache[string];
    if (hashed === undefined) {
        hashed = hashString(string);
        if (STRING_HASH_CACHE_SIZE === STRING_HASH_CACHE_MAX_SIZE) {
            STRING_HASH_CACHE_SIZE = 0;
            stringHashCache = {};
        }
        STRING_HASH_CACHE_SIZE++;
        stringHashCache[string] = hashed;
    }
    return hashed;
}
// http://jsperf.com/hashing-strings
function hashString(string) {
    // This is the hash from JVM
    // The hash code for a string is computed as
    // s[0] * 31 ^ (n - 1) + s[1] * 31 ^ (n - 2) + ... + s[n - 1],
    // where s[i] is the ith character of the string and n is the length of
    // the string. We "mod" the result to make it between 0 (inclusive) and 2^31
    // (exclusive) by dropping high bits.
    var hashed = 0;
    for (var ii = 0; ii < string.length; ii++) {
        hashed = (31 * hashed + string.charCodeAt(ii)) | 0;
    }
    return smi(hashed);
}
function hashJSObj(obj) {
    var hashed;
    if (usingWeakMap) {
        hashed = weakMap.get(obj);
        if (hashed !== undefined) {
            return hashed;
        }
    }
    hashed = obj[UID_HASH_KEY];
    if (hashed !== undefined) {
        return hashed;
    }
    if (!canDefineProperty) {
        hashed = obj.propertyIsEnumerable && obj.propertyIsEnumerable[UID_HASH_KEY];
        if (hashed !== undefined) {
            return hashed;
        }
        hashed = getIENodeHash(obj);
        if (hashed !== undefined) {
            return hashed;
        }
    }
    hashed = ++objHashUID;
    if (objHashUID & 0x40000000) {
        objHashUID = 0;
    }
    if (usingWeakMap) {
        weakMap.set(obj, hashed);
    }
    else if (isExtensible !== undefined && isExtensible(obj) === false) {
        throw new Error('Non-extensible objects are not allowed as keys.');
    }
    else if (canDefineProperty) {
        Object.defineProperty(obj, UID_HASH_KEY, {
            enumerable: false,
            configurable: false,
            writable: false,
            value: hashed,
        });
    }
    else if (obj.propertyIsEnumerable !== undefined &&
        obj.propertyIsEnumerable === obj.constructor.prototype.propertyIsEnumerable) {
        // Since we can't define a non-enumerable property on the object
        // we'll hijack one of the less-used non-enumerable properties to
        // save our hash on it. Since this is a function it will not show up in
        // `JSON.stringify` which is what we want.
        obj.propertyIsEnumerable = function () {
            return this.constructor.prototype.propertyIsEnumerable.apply(this, arguments);
        };
        obj.propertyIsEnumerable[UID_HASH_KEY] = hashed;
    }
    else if (obj.nodeType !== undefined) {
        // At this point we couldn't get the IE `uniqueID` to use as a hash
        // and we couldn't use a non-enumerable property to exploit the
        // dontEnum bug so we simply add the `UID_HASH_KEY` on the node
        // itself.
        obj[UID_HASH_KEY] = hashed;
    }
    else {
        throw new Error('Unable to set a non-enumerable property on object.');
    }
    return hashed;
}
// Get references to ES5 object methods.
var isExtensible = Object.isExtensible;
// True if Object.defineProperty works as expected. IE8 fails this test.
var canDefineProperty = (function () {
    try {
        Object.defineProperty({}, '@', {});
        return true;
    }
    catch (e) {
        return false;
    }
})();
// IE has a `uniqueID` property on DOM nodes. We can construct the hash from it
// and avoid memory leaks from the IE cloneNode bug.
function getIENodeHash(node) {
    if (node && node.nodeType > 0) {
        switch (node.nodeType) {
            case 1: // Element
                return node.uniqueID;
            case 9: // Document
                return node.documentElement && node.documentElement.uniqueID;
        }
    }
}
// If possible, use a WeakMap.
var usingWeakMap = typeof WeakMap === 'function';
var weakMap;
if (usingWeakMap) {
    weakMap = new WeakMap();
}
var objHashUID = 0;
var UID_HASH_KEY = '__immutablehash__';
if (typeof Symbol === 'function') {
    UID_HASH_KEY = Symbol(UID_HASH_KEY);
}
var STRING_HASH_CACHE_MIN_STRLEN = 16;
var STRING_HASH_CACHE_MAX_SIZE = 255;
var STRING_HASH_CACHE_SIZE = 0;
var stringHashCache = {};
var ToKeyedSequence = /*@__PURE__*/ (function (KeyedSeq$$1) {
    function ToKeyedSequence(indexed, useKeys) {
        this._iter = indexed;
        this._useKeys = useKeys;
        this.size = indexed.size;
    }
    if (KeyedSeq$$1)
        ToKeyedSequence.__proto__ = KeyedSeq$$1;
    ToKeyedSequence.prototype = Object.create(KeyedSeq$$1 && KeyedSeq$$1.prototype);
    ToKeyedSequence.prototype.constructor = ToKeyedSequence;
    ToKeyedSequence.prototype.get = function get(key, notSetValue) {
        return this._iter.get(key, notSetValue);
    };
    ToKeyedSequence.prototype.has = function has(key) {
        return this._iter.has(key);
    };
    ToKeyedSequence.prototype.valueSeq = function valueSeq() {
        return this._iter.valueSeq();
    };
    ToKeyedSequence.prototype.reverse = function reverse() {
        var this$1 = this;
        var reversedSequence = reverseFactory(this, true);
        if (!this._useKeys) {
            reversedSequence.valueSeq = function () { return this$1._iter.toSeq().reverse(); };
        }
        return reversedSequence;
    };
    ToKeyedSequence.prototype.map = function map(mapper, context) {
        var this$1 = this;
        var mappedSequence = mapFactory(this, mapper, context);
        if (!this._useKeys) {
            mappedSequence.valueSeq = function () { return this$1._iter.toSeq().map(mapper, context); };
        }
        return mappedSequence;
    };
    ToKeyedSequence.prototype.__iterate = function __iterate(fn, reverse) {
        var this$1 = this;
        return this._iter.__iterate(function (v, k) { return fn(v, k, this$1); }, reverse);
    };
    ToKeyedSequence.prototype.__iterator = function __iterator(type, reverse) {
        return this._iter.__iterator(type, reverse);
    };
    return ToKeyedSequence;
}(KeyedSeq));
ToKeyedSequence.prototype[IS_ORDERED_SYMBOL] = true;
var ToIndexedSequence = /*@__PURE__*/ (function (IndexedSeq$$1) {
    function ToIndexedSequence(iter) {
        this._iter = iter;
        this.size = iter.size;
    }
    if (IndexedSeq$$1)
        ToIndexedSequence.__proto__ = IndexedSeq$$1;
    ToIndexedSequence.prototype = Object.create(IndexedSeq$$1 && IndexedSeq$$1.prototype);
    ToIndexedSequence.prototype.constructor = ToIndexedSequence;
    ToIndexedSequence.prototype.includes = function includes(value) {
        return this._iter.includes(value);
    };
    ToIndexedSequence.prototype.__iterate = function __iterate(fn, reverse) {
        var this$1 = this;
        var i = 0;
        reverse && ensureSize(this);
        return this._iter.__iterate(function (v) { return fn(v, reverse ? this$1.size - ++i : i++, this$1); }, reverse);
    };
    ToIndexedSequence.prototype.__iterator = function __iterator(type, reverse) {
        var this$1 = this;
        var iterator = this._iter.__iterator(ITERATE_VALUES, reverse);
        var i = 0;
        reverse && ensureSize(this);
        return new Iterator(function () {
            var step = iterator.next();
            return step.done
                ? step
                : iteratorValue(type, reverse ? this$1.size - ++i : i++, step.value, step);
        });
    };
    return ToIndexedSequence;
}(IndexedSeq));
var ToSetSequence = /*@__PURE__*/ (function (SetSeq$$1) {
    function ToSetSequence(iter) {
        this._iter = iter;
        this.size = iter.size;
    }
    if (SetSeq$$1)
        ToSetSequence.__proto__ = SetSeq$$1;
    ToSetSequence.prototype = Object.create(SetSeq$$1 && SetSeq$$1.prototype);
    ToSetSequence.prototype.constructor = ToSetSequence;
    ToSetSequence.prototype.has = function has(key) {
        return this._iter.includes(key);
    };
    ToSetSequence.prototype.__iterate = function __iterate(fn, reverse) {
        var this$1 = this;
        return this._iter.__iterate(function (v) { return fn(v, v, this$1); }, reverse);
    };
    ToSetSequence.prototype.__iterator = function __iterator(type, reverse) {
        var iterator = this._iter.__iterator(ITERATE_VALUES, reverse);
        return new Iterator(function () {
            var step = iterator.next();
            return step.done
                ? step
                : iteratorValue(type, step.value, step.value, step);
        });
    };
    return ToSetSequence;
}(SetSeq));
var FromEntriesSequence = /*@__PURE__*/ (function (KeyedSeq$$1) {
    function FromEntriesSequence(entries) {
        this._iter = entries;
        this.size = entries.size;
    }
    if (KeyedSeq$$1)
        FromEntriesSequence.__proto__ = KeyedSeq$$1;
    FromEntriesSequence.prototype = Object.create(KeyedSeq$$1 && KeyedSeq$$1.prototype);
    FromEntriesSequence.prototype.constructor = FromEntriesSequence;
    FromEntriesSequence.prototype.entrySeq = function entrySeq() {
        return this._iter.toSeq();
    };
    FromEntriesSequence.prototype.__iterate = function __iterate(fn, reverse) {
        var this$1 = this;
        return this._iter.__iterate(function (entry) {
            // Check if entry exists first so array access doesn't throw for holes
            // in the parent iteration.
            if (entry) {
                validateEntry(entry);
                var indexedCollection = isCollection(entry);
                return fn(indexedCollection ? entry.get(1) : entry[1], indexedCollection ? entry.get(0) : entry[0], this$1);
            }
        }, reverse);
    };
    FromEntriesSequence.prototype.__iterator = function __iterator(type, reverse) {
        var iterator = this._iter.__iterator(ITERATE_VALUES, reverse);
        return new Iterator(function () {
            while (true) {
                var step = iterator.next();
                if (step.done) {
                    return step;
                }
                var entry = step.value;
                // Check if entry exists first so array access doesn't throw for holes
                // in the parent iteration.
                if (entry) {
                    validateEntry(entry);
                    var indexedCollection = isCollection(entry);
                    return iteratorValue(type, indexedCollection ? entry.get(0) : entry[0], indexedCollection ? entry.get(1) : entry[1], step);
                }
            }
        });
    };
    return FromEntriesSequence;
}(KeyedSeq));
ToIndexedSequence.prototype.cacheResult = ToKeyedSequence.prototype.cacheResult = ToSetSequence.prototype.cacheResult = FromEntriesSequence.prototype.cacheResult = cacheResultThrough;
function flipFactory(collection) {
    var flipSequence = makeSequence(collection);
    flipSequence._iter = collection;
    flipSequence.size = collection.size;
    flipSequence.flip = function () { return collection; };
    flipSequence.reverse = function () {
        var reversedSequence = collection.reverse.apply(this); // super.reverse()
        reversedSequence.flip = function () { return collection.reverse(); };
        return reversedSequence;
    };
    flipSequence.has = function (key) { return collection.includes(key); };
    flipSequence.includes = function (key) { return collection.has(key); };
    flipSequence.cacheResult = cacheResultThrough;
    flipSequence.__iterateUncached = function (fn, reverse) {
        var this$1 = this;
        return collection.__iterate(function (v, k) { return fn(k, v, this$1) !== false; }, reverse);
    };
    flipSequence.__iteratorUncached = function (type, reverse) {
        if (type === ITERATE_ENTRIES) {
            var iterator = collection.__iterator(type, reverse);
            return new Iterator(function () {
                var step = iterator.next();
                if (!step.done) {
                    var k = step.value[0];
                    step.value[0] = step.value[1];
                    step.value[1] = k;
                }
                return step;
            });
        }
        return collection.__iterator(type === ITERATE_VALUES ? ITERATE_KEYS : ITERATE_VALUES, reverse);
    };
    return flipSequence;
}
function mapFactory(collection, mapper, context) {
    var mappedSequence = makeSequence(collection);
    mappedSequence.size = collection.size;
    mappedSequence.has = function (key) { return collection.has(key); };
    mappedSequence.get = function (key, notSetValue) {
        var v = collection.get(key, NOT_SET);
        return v === NOT_SET
            ? notSetValue
            : mapper.call(context, v, key, collection);
    };
    mappedSequence.__iterateUncached = function (fn, reverse) {
        var this$1 = this;
        return collection.__iterate(function (v, k, c) { return fn(mapper.call(context, v, k, c), k, this$1) !== false; }, reverse);
    };
    mappedSequence.__iteratorUncached = function (type, reverse) {
        var iterator = collection.__iterator(ITERATE_ENTRIES, reverse);
        return new Iterator(function () {
            var step = iterator.next();
            if (step.done) {
                return step;
            }
            var entry = step.value;
            var key = entry[0];
            return iteratorValue(type, key, mapper.call(context, entry[1], key, collection), step);
        });
    };
    return mappedSequence;
}
function reverseFactory(collection, useKeys) {
    var this$1 = this;
    var reversedSequence = makeSequence(collection);
    reversedSequence._iter = collection;
    reversedSequence.size = collection.size;
    reversedSequence.reverse = function () { return collection; };
    if (collection.flip) {
        reversedSequence.flip = function () {
            var flipSequence = flipFactory(collection);
            flipSequence.reverse = function () { return collection.flip(); };
            return flipSequence;
        };
    }
    reversedSequence.get = function (key, notSetValue) { return collection.get(useKeys ? key : -1 - key, notSetValue); };
    reversedSequence.has = function (key) { return collection.has(useKeys ? key : -1 - key); };
    reversedSequence.includes = function (value) { return collection.includes(value); };
    reversedSequence.cacheResult = cacheResultThrough;
    reversedSequence.__iterate = function (fn, reverse) {
        var this$1 = this;
        var i = 0;
        reverse && ensureSize(collection);
        return collection.__iterate(function (v, k) { return fn(v, useKeys ? k : reverse ? this$1.size - ++i : i++, this$1); }, !reverse);
    };
    reversedSequence.__iterator = function (type, reverse) {
        var i = 0;
        reverse && ensureSize(collection);
        var iterator = collection.__iterator(ITERATE_ENTRIES, !reverse);
        return new Iterator(function () {
            var step = iterator.next();
            if (step.done) {
                return step;
            }
            var entry = step.value;
            return iteratorValue(type, useKeys ? entry[0] : reverse ? this$1.size - ++i : i++, entry[1], step);
        });
    };
    return reversedSequence;
}
function filterFactory(collection, predicate, context, useKeys) {
    var filterSequence = makeSequence(collection);
    if (useKeys) {
        filterSequence.has = function (key) {
            var v = collection.get(key, NOT_SET);
            return v !== NOT_SET && !!predicate.call(context, v, key, collection);
        };
        filterSequence.get = function (key, notSetValue) {
            var v = collection.get(key, NOT_SET);
            return v !== NOT_SET && predicate.call(context, v, key, collection)
                ? v
                : notSetValue;
        };
    }
    filterSequence.__iterateUncached = function (fn, reverse) {
        var this$1 = this;
        var iterations = 0;
        collection.__iterate(function (v, k, c) {
            if (predicate.call(context, v, k, c)) {
                iterations++;
                return fn(v, useKeys ? k : iterations - 1, this$1);
            }
        }, reverse);
        return iterations;
    };
    filterSequence.__iteratorUncached = function (type, reverse) {
        var iterator = collection.__iterator(ITERATE_ENTRIES, reverse);
        var iterations = 0;
        return new Iterator(function () {
            while (true) {
                var step = iterator.next();
                if (step.done) {
                    return step;
                }
                var entry = step.value;
                var key = entry[0];
                var value = entry[1];
                if (predicate.call(context, value, key, collection)) {
                    return iteratorValue(type, useKeys ? key : iterations++, value, step);
                }
            }
        });
    };
    return filterSequence;
}
function countByFactory(collection, grouper, context) {
    var groups = Map$1().asMutable();
    collection.__iterate(function (v, k) {
        groups.update(grouper.call(context, v, k, collection), 0, function (a) { return a + 1; });
    });
    return groups.asImmutable();
}
function groupByFactory(collection, grouper, context) {
    var isKeyedIter = isKeyed(collection);
    var groups = (isOrdered(collection) ? OrderedMap() : Map$1()).asMutable();
    collection.__iterate(function (v, k) {
        groups.update(grouper.call(context, v, k, collection), function (a) { return ((a = a || []), a.push(isKeyedIter ? [k, v] : v), a); });
    });
    var coerce = collectionClass(collection);
    return groups.map(function (arr) { return reify(collection, coerce(arr)); }).asImmutable();
}
function sliceFactory(collection, begin, end, useKeys) {
    var originalSize = collection.size;
    if (wholeSlice(begin, end, originalSize)) {
        return collection;
    }
    var resolvedBegin = resolveBegin(begin, originalSize);
    var resolvedEnd = resolveEnd(end, originalSize);
    // begin or end will be NaN if they were provided as negative numbers and
    // this collection's size is unknown. In that case, cache first so there is
    // a known size and these do not resolve to NaN.
    if (resolvedBegin !== resolvedBegin || resolvedEnd !== resolvedEnd) {
        return sliceFactory(collection.toSeq().cacheResult(), begin, end, useKeys);
    }
    // Note: resolvedEnd is undefined when the original sequence's length is
    // unknown and this slice did not supply an end and should contain all
    // elements after resolvedBegin.
    // In that case, resolvedSize will be NaN and sliceSize will remain undefined.
    var resolvedSize = resolvedEnd - resolvedBegin;
    var sliceSize;
    if (resolvedSize === resolvedSize) {
        sliceSize = resolvedSize < 0 ? 0 : resolvedSize;
    }
    var sliceSeq = makeSequence(collection);
    // If collection.size is undefined, the size of the realized sliceSeq is
    // unknown at this point unless the number of items to slice is 0
    sliceSeq.size =
        sliceSize === 0 ? sliceSize : (collection.size && sliceSize) || undefined;
    if (!useKeys && isSeq(collection) && sliceSize >= 0) {
        sliceSeq.get = function (index, notSetValue) {
            index = wrapIndex(this, index);
            return index >= 0 && index < sliceSize
                ? collection.get(index + resolvedBegin, notSetValue)
                : notSetValue;
        };
    }
    sliceSeq.__iterateUncached = function (fn, reverse) {
        var this$1 = this;
        if (sliceSize === 0) {
            return 0;
        }
        if (reverse) {
            return this.cacheResult().__iterate(fn, reverse);
        }
        var skipped = 0;
        var isSkipping = true;
        var iterations = 0;
        collection.__iterate(function (v, k) {
            if (!(isSkipping && (isSkipping = skipped++ < resolvedBegin))) {
                iterations++;
                return (fn(v, useKeys ? k : iterations - 1, this$1) !== false &&
                    iterations !== sliceSize);
            }
        });
        return iterations;
    };
    sliceSeq.__iteratorUncached = function (type, reverse) {
        if (sliceSize !== 0 && reverse) {
            return this.cacheResult().__iterator(type, reverse);
        }
        // Don't bother instantiating parent iterator if taking 0.
        if (sliceSize === 0) {
            return new Iterator(iteratorDone);
        }
        var iterator = collection.__iterator(type, reverse);
        var skipped = 0;
        var iterations = 0;
        return new Iterator(function () {
            while (skipped++ < resolvedBegin) {
                iterator.next();
            }
            if (++iterations > sliceSize) {
                return iteratorDone();
            }
            var step = iterator.next();
            if (useKeys || type === ITERATE_VALUES || step.done) {
                return step;
            }
            if (type === ITERATE_KEYS) {
                return iteratorValue(type, iterations - 1, undefined, step);
            }
            return iteratorValue(type, iterations - 1, step.value[1], step);
        });
    };
    return sliceSeq;
}
function takeWhileFactory(collection, predicate, context) {
    var takeSequence = makeSequence(collection);
    takeSequence.__iterateUncached = function (fn, reverse) {
        var this$1 = this;
        if (reverse) {
            return this.cacheResult().__iterate(fn, reverse);
        }
        var iterations = 0;
        collection.__iterate(function (v, k, c) { return predicate.call(context, v, k, c) && ++iterations && fn(v, k, this$1); });
        return iterations;
    };
    takeSequence.__iteratorUncached = function (type, reverse) {
        var this$1 = this;
        if (reverse) {
            return this.cacheResult().__iterator(type, reverse);
        }
        var iterator = collection.__iterator(ITERATE_ENTRIES, reverse);
        var iterating = true;
        return new Iterator(function () {
            if (!iterating) {
                return iteratorDone();
            }
            var step = iterator.next();
            if (step.done) {
                return step;
            }
            var entry = step.value;
            var k = entry[0];
            var v = entry[1];
            if (!predicate.call(context, v, k, this$1)) {
                iterating = false;
                return iteratorDone();
            }
            return type === ITERATE_ENTRIES ? step : iteratorValue(type, k, v, step);
        });
    };
    return takeSequence;
}
function skipWhileFactory(collection, predicate, context, useKeys) {
    var skipSequence = makeSequence(collection);
    skipSequence.__iterateUncached = function (fn, reverse) {
        var this$1 = this;
        if (reverse) {
            return this.cacheResult().__iterate(fn, reverse);
        }
        var isSkipping = true;
        var iterations = 0;
        collection.__iterate(function (v, k, c) {
            if (!(isSkipping && (isSkipping = predicate.call(context, v, k, c)))) {
                iterations++;
                return fn(v, useKeys ? k : iterations - 1, this$1);
            }
        });
        return iterations;
    };
    skipSequence.__iteratorUncached = function (type, reverse) {
        var this$1 = this;
        if (reverse) {
            return this.cacheResult().__iterator(type, reverse);
        }
        var iterator = collection.__iterator(ITERATE_ENTRIES, reverse);
        var skipping = true;
        var iterations = 0;
        return new Iterator(function () {
            var step;
            var k;
            var v;
            do {
                step = iterator.next();
                if (step.done) {
                    if (useKeys || type === ITERATE_VALUES) {
                        return step;
                    }
                    if (type === ITERATE_KEYS) {
                        return iteratorValue(type, iterations++, undefined, step);
                    }
                    return iteratorValue(type, iterations++, step.value[1], step);
                }
                var entry = step.value;
                k = entry[0];
                v = entry[1];
                skipping && (skipping = predicate.call(context, v, k, this$1));
            } while (skipping);
            return type === ITERATE_ENTRIES ? step : iteratorValue(type, k, v, step);
        });
    };
    return skipSequence;
}
function concatFactory(collection, values) {
    var isKeyedCollection = isKeyed(collection);
    var iters = [collection]
        .concat(values)
        .map(function (v) {
        if (!isCollection(v)) {
            v = isKeyedCollection
                ? keyedSeqFromValue(v)
                : indexedSeqFromValue(Array.isArray(v) ? v : [v]);
        }
        else if (isKeyedCollection) {
            v = KeyedCollection(v);
        }
        return v;
    })
        .filter(function (v) { return v.size !== 0; });
    if (iters.length === 0) {
        return collection;
    }
    if (iters.length === 1) {
        var singleton = iters[0];
        if (singleton === collection ||
            (isKeyedCollection && isKeyed(singleton)) ||
            (isIndexed(collection) && isIndexed(singleton))) {
            return singleton;
        }
    }
    var concatSeq = new ArraySeq(iters);
    if (isKeyedCollection) {
        concatSeq = concatSeq.toKeyedSeq();
    }
    else if (!isIndexed(collection)) {
        concatSeq = concatSeq.toSetSeq();
    }
    concatSeq = concatSeq.flatten(true);
    concatSeq.size = iters.reduce(function (sum, seq) {
        if (sum !== undefined) {
            var size = seq.size;
            if (size !== undefined) {
                return sum + size;
            }
        }
    }, 0);
    return concatSeq;
}
function flattenFactory(collection, depth, useKeys) {
    var flatSequence = makeSequence(collection);
    flatSequence.__iterateUncached = function (fn, reverse) {
        if (reverse) {
            return this.cacheResult().__iterate(fn, reverse);
        }
        var iterations = 0;
        var stopped = false;
        function flatDeep(iter, currentDepth) {
            iter.__iterate(function (v, k) {
                if ((!depth || currentDepth < depth) && isCollection(v)) {
                    flatDeep(v, currentDepth + 1);
                }
                else {
                    iterations++;
                    if (fn(v, useKeys ? k : iterations - 1, flatSequence) === false) {
                        stopped = true;
                    }
                }
                return !stopped;
            }, reverse);
        }
        flatDeep(collection, 0);
        return iterations;
    };
    flatSequence.__iteratorUncached = function (type, reverse) {
        if (reverse) {
            return this.cacheResult().__iterator(type, reverse);
        }
        var iterator = collection.__iterator(type, reverse);
        var stack = [];
        var iterations = 0;
        return new Iterator(function () {
            while (iterator) {
                var step = iterator.next();
                if (step.done !== false) {
                    iterator = stack.pop();
                    continue;
                }
                var v = step.value;
                if (type === ITERATE_ENTRIES) {
                    v = v[1];
                }
                if ((!depth || stack.length < depth) && isCollection(v)) {
                    stack.push(iterator);
                    iterator = v.__iterator(type, reverse);
                }
                else {
                    return useKeys ? step : iteratorValue(type, iterations++, v, step);
                }
            }
            return iteratorDone();
        });
    };
    return flatSequence;
}
function flatMapFactory(collection, mapper, context) {
    var coerce = collectionClass(collection);
    return collection
        .toSeq()
        .map(function (v, k) { return coerce(mapper.call(context, v, k, collection)); })
        .flatten(true);
}
function interposeFactory(collection, separator) {
    var interposedSequence = makeSequence(collection);
    interposedSequence.size = collection.size && collection.size * 2 - 1;
    interposedSequence.__iterateUncached = function (fn, reverse) {
        var this$1 = this;
        var iterations = 0;
        collection.__iterate(function (v) {
            return (!iterations || fn(separator, iterations++, this$1) !== false) &&
                fn(v, iterations++, this$1) !== false;
        }, reverse);
        return iterations;
    };
    interposedSequence.__iteratorUncached = function (type, reverse) {
        var iterator = collection.__iterator(ITERATE_VALUES, reverse);
        var iterations = 0;
        var step;
        return new Iterator(function () {
            if (!step || iterations % 2) {
                step = iterator.next();
                if (step.done) {
                    return step;
                }
            }
            return iterations % 2
                ? iteratorValue(type, iterations++, separator)
                : iteratorValue(type, iterations++, step.value, step);
        });
    };
    return interposedSequence;
}
function sortFactory(collection, comparator, mapper) {
    if (!comparator) {
        comparator = defaultComparator;
    }
    var isKeyedCollection = isKeyed(collection);
    var index = 0;
    var entries = collection
        .toSeq()
        .map(function (v, k) { return [k, v, index++, mapper ? mapper(v, k, collection) : v]; })
        .valueSeq()
        .toArray();
    entries.sort(function (a, b) { return comparator(a[3], b[3]) || a[2] - b[2]; }).forEach(isKeyedCollection
        ? function (v, i) {
            entries[i].length = 2;
        }
        : function (v, i) {
            entries[i] = v[1];
        });
    return isKeyedCollection
        ? KeyedSeq(entries)
        : isIndexed(collection)
            ? IndexedSeq(entries)
            : SetSeq(entries);
}
function maxFactory(collection, comparator, mapper) {
    if (!comparator) {
        comparator = defaultComparator;
    }
    if (mapper) {
        var entry = collection
            .toSeq()
            .map(function (v, k) { return [v, mapper(v, k, collection)]; })
            .reduce(function (a, b) { return (maxCompare(comparator, a[1], b[1]) ? b : a); });
        return entry && entry[0];
    }
    return collection.reduce(function (a, b) { return (maxCompare(comparator, a, b) ? b : a); });
}
function maxCompare(comparator, a, b) {
    var comp = comparator(b, a);
    // b is considered the new max if the comparator declares them equal, but
    // they are not equal and b is in fact a nullish value.
    return ((comp === 0 && b !== a && (b === undefined || b === null || b !== b)) ||
        comp > 0);
}
function zipWithFactory(keyIter, zipper, iters, zipAll) {
    var zipSequence = makeSequence(keyIter);
    var sizes = new ArraySeq(iters).map(function (i) { return i.size; });
    zipSequence.size = zipAll ? sizes.max() : sizes.min();
    // Note: this a generic base implementation of __iterate in terms of
    // __iterator which may be more generically useful in the future.
    zipSequence.__iterate = function (fn, reverse) {
        /* generic:
        var iterator = this.__iterator(ITERATE_ENTRIES, reverse);
        var step;
        var iterations = 0;
        while (!(step = iterator.next()).done) {
          iterations++;
          if (fn(step.value[1], step.value[0], this) === false) {
            break;
          }
        }
        return iterations;
        */
        // indexed:
        var iterator = this.__iterator(ITERATE_VALUES, reverse);
        var step;
        var iterations = 0;
        while (!(step = iterator.next()).done) {
            if (fn(step.value, iterations++, this) === false) {
                break;
            }
        }
        return iterations;
    };
    zipSequence.__iteratorUncached = function (type, reverse) {
        var iterators = iters.map(function (i) { return ((i = Collection(i)), getIterator(reverse ? i.reverse() : i)); });
        var iterations = 0;
        var isDone = false;
        return new Iterator(function () {
            var steps;
            if (!isDone) {
                steps = iterators.map(function (i) { return i.next(); });
                isDone = zipAll ? steps.every(function (s) { return s.done; }) : steps.some(function (s) { return s.done; });
            }
            if (isDone) {
                return iteratorDone();
            }
            return iteratorValue(type, iterations++, zipper.apply(null, steps.map(function (s) { return s.value; })));
        });
    };
    return zipSequence;
}
// #pragma Helper Functions
function reify(iter, seq) {
    return iter === seq ? iter : isSeq(iter) ? seq : iter.constructor(seq);
}
function validateEntry(entry) {
    if (entry !== Object(entry)) {
        throw new TypeError('Expected [K, V] tuple: ' + entry);
    }
}
function collectionClass(collection) {
    return isKeyed(collection)
        ? KeyedCollection
        : isIndexed(collection)
            ? IndexedCollection
            : SetCollection;
}
function makeSequence(collection) {
    return Object.create((isKeyed(collection)
        ? KeyedSeq
        : isIndexed(collection)
            ? IndexedSeq
            : SetSeq).prototype);
}
function cacheResultThrough() {
    if (this._iter.cacheResult) {
        this._iter.cacheResult();
        this.size = this._iter.size;
        return this;
    }
    return Seq.prototype.cacheResult.call(this);
}
function defaultComparator(a, b) {
    if (a === undefined && b === undefined) {
        return 0;
    }
    if (a === undefined) {
        return 1;
    }
    if (b === undefined) {
        return -1;
    }
    return a > b ? 1 : a < b ? -1 : 0;
}
// http://jsperf.com/copy-array-inline
function arrCopy(arr, offset) {
    offset = offset || 0;
    var len = Math.max(0, arr.length - offset);
    var newArr = new Array(len);
    for (var ii = 0; ii < len; ii++) {
        newArr[ii] = arr[ii + offset];
    }
    return newArr;
}
function invariant(condition, error) {
    if (!condition) {
        throw new Error(error);
    }
}
function assertNotInfinite(size) {
    invariant(size !== Infinity, 'Cannot perform this action with an infinite size.');
}
function coerceKeyPath(keyPath) {
    if (isArrayLike(keyPath) && typeof keyPath !== 'string') {
        return keyPath;
    }
    if (isOrdered(keyPath)) {
        return keyPath.toArray();
    }
    throw new TypeError('Invalid keyPath: expected Ordered Collection or Array: ' + keyPath);
}
function isPlainObj(value) {
    return (value &&
        (typeof value.constructor !== 'function' ||
            value.constructor.name === 'Object'));
}
/**
 * Returns true if the value is a potentially-persistent data structure, either
 * provided by Immutable.js or a plain Array or Object.
 */
function isDataStructure(value) {
    return (typeof value === 'object' &&
        (isImmutable(value) || Array.isArray(value) || isPlainObj(value)));
}
/**
 * Converts a value to a string, adding quotes if a string was provided.
 */
function quoteString(value) {
    try {
        return typeof value === 'string' ? JSON.stringify(value) : String(value);
    }
    catch (_ignoreError) {
        return JSON.stringify(value);
    }
}
function has(collection, key) {
    return isImmutable(collection)
        ? collection.has(key)
        : isDataStructure(collection) && hasOwnProperty.call(collection, key);
}
function get(collection, key, notSetValue) {
    return isImmutable(collection)
        ? collection.get(key, notSetValue)
        : !has(collection, key)
            ? notSetValue
            : typeof collection.get === 'function'
                ? collection.get(key)
                : collection[key];
}
function shallowCopy(from) {
    if (Array.isArray(from)) {
        return arrCopy(from);
    }
    var to = {};
    for (var key in from) {
        if (hasOwnProperty.call(from, key)) {
            to[key] = from[key];
        }
    }
    return to;
}
function remove(collection, key) {
    if (!isDataStructure(collection)) {
        throw new TypeError('Cannot update non-data-structure value: ' + collection);
    }
    if (isImmutable(collection)) {
        if (!collection.remove) {
            throw new TypeError('Cannot update immutable value without .remove() method: ' + collection);
        }
        return collection.remove(key);
    }
    if (!hasOwnProperty.call(collection, key)) {
        return collection;
    }
    var collectionCopy = shallowCopy(collection);
    if (Array.isArray(collectionCopy)) {
        collectionCopy.splice(key, 1);
    }
    else {
        delete collectionCopy[key];
    }
    return collectionCopy;
}
function set(collection, key, value) {
    if (!isDataStructure(collection)) {
        throw new TypeError('Cannot update non-data-structure value: ' + collection);
    }
    if (isImmutable(collection)) {
        if (!collection.set) {
            throw new TypeError('Cannot update immutable value without .set() method: ' + collection);
        }
        return collection.set(key, value);
    }
    if (hasOwnProperty.call(collection, key) && value === collection[key]) {
        return collection;
    }
    var collectionCopy = shallowCopy(collection);
    collectionCopy[key] = value;
    return collectionCopy;
}
function updateIn(collection, keyPath, notSetValue, updater) {
    if (!updater) {
        updater = notSetValue;
        notSetValue = undefined;
    }
    var updatedValue = updateInDeeply(isImmutable(collection), collection, coerceKeyPath(keyPath), 0, notSetValue, updater);
    return updatedValue === NOT_SET ? notSetValue : updatedValue;
}
function updateInDeeply(inImmutable, existing, keyPath, i, notSetValue, updater) {
    var wasNotSet = existing === NOT_SET;
    if (i === keyPath.length) {
        var existingValue = wasNotSet ? notSetValue : existing;
        var newValue = updater(existingValue);
        return newValue === existingValue ? existing : newValue;
    }
    if (!wasNotSet && !isDataStructure(existing)) {
        throw new TypeError('Cannot update within non-data-structure value in path [' +
            keyPath.slice(0, i).map(quoteString) +
            ']: ' +
            existing);
    }
    var key = keyPath[i];
    var nextExisting = wasNotSet ? NOT_SET : get(existing, key, NOT_SET);
    var nextUpdated = updateInDeeply(nextExisting === NOT_SET ? inImmutable : isImmutable(nextExisting), nextExisting, keyPath, i + 1, notSetValue, updater);
    return nextUpdated === nextExisting
        ? existing
        : nextUpdated === NOT_SET
            ? remove(existing, key)
            : set(wasNotSet ? (inImmutable ? emptyMap() : {}) : existing, key, nextUpdated);
}
function setIn(collection, keyPath, value) {
    return updateIn(collection, keyPath, NOT_SET, function () { return value; });
}
function setIn$1(keyPath, v) {
    return setIn(this, keyPath, v);
}
function removeIn(collection, keyPath) {
    return updateIn(collection, keyPath, function () { return NOT_SET; });
}
function deleteIn(keyPath) {
    return removeIn(this, keyPath);
}
function update(collection, key, notSetValue, updater) {
    return updateIn(collection, [key], notSetValue, updater);
}
function update$1(key, notSetValue, updater) {
    return arguments.length === 1
        ? key(this)
        : update(this, key, notSetValue, updater);
}
function updateIn$1(keyPath, notSetValue, updater) {
    return updateIn(this, keyPath, notSetValue, updater);
}
function merge() {
    var iters = [], len = arguments.length;
    while (len--)
        iters[len] = arguments[len];
    return mergeIntoKeyedWith(this, iters);
}
function mergeWith(merger) {
    var iters = [], len = arguments.length - 1;
    while (len-- > 0)
        iters[len] = arguments[len + 1];
    if (typeof merger !== 'function') {
        throw new TypeError('Invalid merger function: ' + merger);
    }
    return mergeIntoKeyedWith(this, iters, merger);
}
function mergeIntoKeyedWith(collection, collections, merger) {
    var iters = [];
    for (var ii = 0; ii < collections.length; ii++) {
        var collection$1 = KeyedCollection(collections[ii]);
        if (collection$1.size !== 0) {
            iters.push(collection$1);
        }
    }
    if (iters.length === 0) {
        return collection;
    }
    if (collection.toSeq().size === 0 &&
        !collection.__ownerID &&
        iters.length === 1) {
        return collection.constructor(iters[0]);
    }
    return collection.withMutations(function (collection) {
        var mergeIntoCollection = merger
            ? function (value, key) {
                update(collection, key, NOT_SET, function (oldVal) { return (oldVal === NOT_SET ? value : merger(oldVal, value, key)); });
            }
            : function (value, key) {
                collection.set(key, value);
            };
        for (var ii = 0; ii < iters.length; ii++) {
            iters[ii].forEach(mergeIntoCollection);
        }
    });
}
function merge$1(collection) {
    var sources = [], len = arguments.length - 1;
    while (len-- > 0)
        sources[len] = arguments[len + 1];
    return mergeWithSources(collection, sources);
}
function mergeWith$1(merger, collection) {
    var sources = [], len = arguments.length - 2;
    while (len-- > 0)
        sources[len] = arguments[len + 2];
    return mergeWithSources(collection, sources, merger);
}
function mergeDeep(collection) {
    var sources = [], len = arguments.length - 1;
    while (len-- > 0)
        sources[len] = arguments[len + 1];
    return mergeDeepWithSources(collection, sources);
}
function mergeDeepWith(merger, collection) {
    var sources = [], len = arguments.length - 2;
    while (len-- > 0)
        sources[len] = arguments[len + 2];
    return mergeDeepWithSources(collection, sources, merger);
}
function mergeDeepWithSources(collection, sources, merger) {
    return mergeWithSources(collection, sources, deepMergerWith(merger));
}
function mergeWithSources(collection, sources, merger) {
    if (!isDataStructure(collection)) {
        throw new TypeError('Cannot merge into non-data-structure value: ' + collection);
    }
    if (isImmutable(collection)) {
        return typeof merger === 'function' && collection.mergeWith
            ? collection.mergeWith.apply(collection, [merger].concat(sources))
            : collection.merge
                ? collection.merge.apply(collection, sources)
                : collection.concat.apply(collection, sources);
    }
    var isArray = Array.isArray(collection);
    var merged = collection;
    var Collection$$1 = isArray ? IndexedCollection : KeyedCollection;
    var mergeItem = isArray
        ? function (value) {
            // Copy on write
            if (merged === collection) {
                merged = shallowCopy(merged);
            }
            merged.push(value);
        }
        : function (value, key) {
            var hasVal = hasOwnProperty.call(merged, key);
            var nextVal = hasVal && merger ? merger(merged[key], value, key) : value;
            if (!hasVal || nextVal !== merged[key]) {
                // Copy on write
                if (merged === collection) {
                    merged = shallowCopy(merged);
                }
                merged[key] = nextVal;
            }
        };
    for (var i = 0; i < sources.length; i++) {
        Collection$$1(sources[i]).forEach(mergeItem);
    }
    return merged;
}
function deepMergerWith(merger) {
    function deepMerger(oldValue, newValue, key) {
        return isDataStructure(oldValue) && isDataStructure(newValue)
            ? mergeWithSources(oldValue, [newValue], deepMerger)
            : merger
                ? merger(oldValue, newValue, key)
                : newValue;
    }
    return deepMerger;
}
function mergeDeep$1() {
    var iters = [], len = arguments.length;
    while (len--)
        iters[len] = arguments[len];
    return mergeDeepWithSources(this, iters);
}
function mergeDeepWith$1(merger) {
    var iters = [], len = arguments.length - 1;
    while (len-- > 0)
        iters[len] = arguments[len + 1];
    return mergeDeepWithSources(this, iters, merger);
}
function mergeIn(keyPath) {
    var iters = [], len = arguments.length - 1;
    while (len-- > 0)
        iters[len] = arguments[len + 1];
    return updateIn(this, keyPath, emptyMap(), function (m) { return mergeWithSources(m, iters); });
}
function mergeDeepIn(keyPath) {
    var iters = [], len = arguments.length - 1;
    while (len-- > 0)
        iters[len] = arguments[len + 1];
    return updateIn(this, keyPath, emptyMap(), function (m) { return mergeDeepWithSources(m, iters); });
}
function withMutations(fn) {
    var mutable = this.asMutable();
    fn(mutable);
    return mutable.wasAltered() ? mutable.__ensureOwner(this.__ownerID) : this;
}
function asMutable() {
    return this.__ownerID ? this : this.__ensureOwner(new OwnerID());
}
function asImmutable() {
    return this.__ensureOwner();
}
function wasAltered() {
    return this.__altered;
}
var Map$1 = /*@__PURE__*/ (function (KeyedCollection$$1) {
    function Map(value) {
        return value === null || value === undefined
            ? emptyMap()
            : isMap(value) && !isOrdered(value)
                ? value
                : emptyMap().withMutations(function (map) {
                    var iter = KeyedCollection$$1(value);
                    assertNotInfinite(iter.size);
                    iter.forEach(function (v, k) { return map.set(k, v); });
                });
    }
    if (KeyedCollection$$1)
        Map.__proto__ = KeyedCollection$$1;
    Map.prototype = Object.create(KeyedCollection$$1 && KeyedCollection$$1.prototype);
    Map.prototype.constructor = Map;
    Map.of = function of() {
        var keyValues = [], len = arguments.length;
        while (len--)
            keyValues[len] = arguments[len];
        return emptyMap().withMutations(function (map) {
            for (var i = 0; i < keyValues.length; i += 2) {
                if (i + 1 >= keyValues.length) {
                    throw new Error('Missing value for key: ' + keyValues[i]);
                }
                map.set(keyValues[i], keyValues[i + 1]);
            }
        });
    };
    Map.prototype.toString = function toString() {
        return this.__toString('Map {', '}');
    };
    // @pragma Access
    Map.prototype.get = function get(k, notSetValue) {
        return this._root
            ? this._root.get(0, undefined, k, notSetValue)
            : notSetValue;
    };
    // @pragma Modification
    Map.prototype.set = function set(k, v) {
        return updateMap(this, k, v);
    };
    Map.prototype.remove = function remove(k) {
        return updateMap(this, k, NOT_SET);
    };
    Map.prototype.deleteAll = function deleteAll(keys) {
        var collection = Collection(keys);
        if (collection.size === 0) {
            return this;
        }
        return this.withMutations(function (map) {
            collection.forEach(function (key) { return map.remove(key); });
        });
    };
    Map.prototype.clear = function clear() {
        if (this.size === 0) {
            return this;
        }
        if (this.__ownerID) {
            this.size = 0;
            this._root = null;
            this.__hash = undefined;
            this.__altered = true;
            return this;
        }
        return emptyMap();
    };
    // @pragma Composition
    Map.prototype.sort = function sort(comparator) {
        // Late binding
        return OrderedMap(sortFactory(this, comparator));
    };
    Map.prototype.sortBy = function sortBy(mapper, comparator) {
        // Late binding
        return OrderedMap(sortFactory(this, comparator, mapper));
    };
    Map.prototype.map = function map(mapper, context) {
        return this.withMutations(function (map) {
            map.forEach(function (value, key) {
                map.set(key, mapper.call(context, value, key, map));
            });
        });
    };
    // @pragma Mutability
    Map.prototype.__iterator = function __iterator(type, reverse) {
        return new MapIterator(this, type, reverse);
    };
    Map.prototype.__iterate = function __iterate(fn, reverse) {
        var this$1 = this;
        var iterations = 0;
        this._root &&
            this._root.iterate(function (entry) {
                iterations++;
                return fn(entry[1], entry[0], this$1);
            }, reverse);
        return iterations;
    };
    Map.prototype.__ensureOwner = function __ensureOwner(ownerID) {
        if (ownerID === this.__ownerID) {
            return this;
        }
        if (!ownerID) {
            if (this.size === 0) {
                return emptyMap();
            }
            this.__ownerID = ownerID;
            this.__altered = false;
            return this;
        }
        return makeMap(this.size, this._root, ownerID, this.__hash);
    };
    return Map;
}(KeyedCollection));
Map$1.isMap = isMap;
var MapPrototype = Map$1.prototype;
MapPrototype[IS_MAP_SYMBOL] = true;
MapPrototype[DELETE] = MapPrototype.remove;
MapPrototype.removeAll = MapPrototype.deleteAll;
MapPrototype.setIn = setIn$1;
MapPrototype.removeIn = MapPrototype.deleteIn = deleteIn;
MapPrototype.update = update$1;
MapPrototype.updateIn = updateIn$1;
MapPrototype.merge = MapPrototype.concat = merge;
MapPrototype.mergeWith = mergeWith;
MapPrototype.mergeDeep = mergeDeep$1;
MapPrototype.mergeDeepWith = mergeDeepWith$1;
MapPrototype.mergeIn = mergeIn;
MapPrototype.mergeDeepIn = mergeDeepIn;
MapPrototype.withMutations = withMutations;
MapPrototype.wasAltered = wasAltered;
MapPrototype.asImmutable = asImmutable;
MapPrototype['@@transducer/init'] = MapPrototype.asMutable = asMutable;
MapPrototype['@@transducer/step'] = function (result, arr) {
    return result.set(arr[0], arr[1]);
};
MapPrototype['@@transducer/result'] = function (obj) {
    return obj.asImmutable();
};
// #pragma Trie Nodes
var ArrayMapNode = function ArrayMapNode(ownerID, entries) {
    this.ownerID = ownerID;
    this.entries = entries;
};
ArrayMapNode.prototype.get = function get(shift, keyHash, key, notSetValue) {
    var entries = this.entries;
    for (var ii = 0, len = entries.length; ii < len; ii++) {
        if (is(key, entries[ii][0])) {
            return entries[ii][1];
        }
    }
    return notSetValue;
};
ArrayMapNode.prototype.update = function update(ownerID, shift, keyHash, key, value, didChangeSize, didAlter) {
    var removed = value === NOT_SET;
    var entries = this.entries;
    var idx = 0;
    var len = entries.length;
    for (; idx < len; idx++) {
        if (is(key, entries[idx][0])) {
            break;
        }
    }
    var exists = idx < len;
    if (exists ? entries[idx][1] === value : removed) {
        return this;
    }
    SetRef(didAlter);
    (removed || !exists) && SetRef(didChangeSize);
    if (removed && entries.length === 1) {
        return; // undefined
    }
    if (!exists && !removed && entries.length >= MAX_ARRAY_MAP_SIZE) {
        return createNodes(ownerID, entries, key, value);
    }
    var isEditable = ownerID && ownerID === this.ownerID;
    var newEntries = isEditable ? entries : arrCopy(entries);
    if (exists) {
        if (removed) {
            idx === len - 1
                ? newEntries.pop()
                : (newEntries[idx] = newEntries.pop());
        }
        else {
            newEntries[idx] = [key, value];
        }
    }
    else {
        newEntries.push([key, value]);
    }
    if (isEditable) {
        this.entries = newEntries;
        return this;
    }
    return new ArrayMapNode(ownerID, newEntries);
};
var BitmapIndexedNode = function BitmapIndexedNode(ownerID, bitmap, nodes) {
    this.ownerID = ownerID;
    this.bitmap = bitmap;
    this.nodes = nodes;
};
BitmapIndexedNode.prototype.get = function get(shift, keyHash, key, notSetValue) {
    if (keyHash === undefined) {
        keyHash = hash(key);
    }
    var bit = 1 << ((shift === 0 ? keyHash : keyHash >>> shift) & MASK);
    var bitmap = this.bitmap;
    return (bitmap & bit) === 0
        ? notSetValue
        : this.nodes[popCount(bitmap & (bit - 1))].get(shift + SHIFT, keyHash, key, notSetValue);
};
BitmapIndexedNode.prototype.update = function update(ownerID, shift, keyHash, key, value, didChangeSize, didAlter) {
    if (keyHash === undefined) {
        keyHash = hash(key);
    }
    var keyHashFrag = (shift === 0 ? keyHash : keyHash >>> shift) & MASK;
    var bit = 1 << keyHashFrag;
    var bitmap = this.bitmap;
    var exists = (bitmap & bit) !== 0;
    if (!exists && value === NOT_SET) {
        return this;
    }
    var idx = popCount(bitmap & (bit - 1));
    var nodes = this.nodes;
    var node = exists ? nodes[idx] : undefined;
    var newNode = updateNode(node, ownerID, shift + SHIFT, keyHash, key, value, didChangeSize, didAlter);
    if (newNode === node) {
        return this;
    }
    if (!exists && newNode && nodes.length >= MAX_BITMAP_INDEXED_SIZE) {
        return expandNodes(ownerID, nodes, bitmap, keyHashFrag, newNode);
    }
    if (exists &&
        !newNode &&
        nodes.length === 2 &&
        isLeafNode(nodes[idx ^ 1])) {
        return nodes[idx ^ 1];
    }
    if (exists && newNode && nodes.length === 1 && isLeafNode(newNode)) {
        return newNode;
    }
    var isEditable = ownerID && ownerID === this.ownerID;
    var newBitmap = exists ? (newNode ? bitmap : bitmap ^ bit) : bitmap | bit;
    var newNodes = exists
        ? newNode
            ? setAt(nodes, idx, newNode, isEditable)
            : spliceOut(nodes, idx, isEditable)
        : spliceIn(nodes, idx, newNode, isEditable);
    if (isEditable) {
        this.bitmap = newBitmap;
        this.nodes = newNodes;
        return this;
    }
    return new BitmapIndexedNode(ownerID, newBitmap, newNodes);
};
var HashArrayMapNode = function HashArrayMapNode(ownerID, count, nodes) {
    this.ownerID = ownerID;
    this.count = count;
    this.nodes = nodes;
};
HashArrayMapNode.prototype.get = function get(shift, keyHash, key, notSetValue) {
    if (keyHash === undefined) {
        keyHash = hash(key);
    }
    var idx = (shift === 0 ? keyHash : keyHash >>> shift) & MASK;
    var node = this.nodes[idx];
    return node
        ? node.get(shift + SHIFT, keyHash, key, notSetValue)
        : notSetValue;
};
HashArrayMapNode.prototype.update = function update(ownerID, shift, keyHash, key, value, didChangeSize, didAlter) {
    if (keyHash === undefined) {
        keyHash = hash(key);
    }
    var idx = (shift === 0 ? keyHash : keyHash >>> shift) & MASK;
    var removed = value === NOT_SET;
    var nodes = this.nodes;
    var node = nodes[idx];
    if (removed && !node) {
        return this;
    }
    var newNode = updateNode(node, ownerID, shift + SHIFT, keyHash, key, value, didChangeSize, didAlter);
    if (newNode === node) {
        return this;
    }
    var newCount = this.count;
    if (!node) {
        newCount++;
    }
    else if (!newNode) {
        newCount--;
        if (newCount < MIN_HASH_ARRAY_MAP_SIZE) {
            return packNodes(ownerID, nodes, newCount, idx);
        }
    }
    var isEditable = ownerID && ownerID === this.ownerID;
    var newNodes = setAt(nodes, idx, newNode, isEditable);
    if (isEditable) {
        this.count = newCount;
        this.nodes = newNodes;
        return this;
    }
    return new HashArrayMapNode(ownerID, newCount, newNodes);
};
var HashCollisionNode = function HashCollisionNode(ownerID, keyHash, entries) {
    this.ownerID = ownerID;
    this.keyHash = keyHash;
    this.entries = entries;
};
HashCollisionNode.prototype.get = function get(shift, keyHash, key, notSetValue) {
    var entries = this.entries;
    for (var ii = 0, len = entries.length; ii < len; ii++) {
        if (is(key, entries[ii][0])) {
            return entries[ii][1];
        }
    }
    return notSetValue;
};
HashCollisionNode.prototype.update = function update(ownerID, shift, keyHash, key, value, didChangeSize, didAlter) {
    if (keyHash === undefined) {
        keyHash = hash(key);
    }
    var removed = value === NOT_SET;
    if (keyHash !== this.keyHash) {
        if (removed) {
            return this;
        }
        SetRef(didAlter);
        SetRef(didChangeSize);
        return mergeIntoNode(this, ownerID, shift, keyHash, [key, value]);
    }
    var entries = this.entries;
    var idx = 0;
    var len = entries.length;
    for (; idx < len; idx++) {
        if (is(key, entries[idx][0])) {
            break;
        }
    }
    var exists = idx < len;
    if (exists ? entries[idx][1] === value : removed) {
        return this;
    }
    SetRef(didAlter);
    (removed || !exists) && SetRef(didChangeSize);
    if (removed && len === 2) {
        return new ValueNode(ownerID, this.keyHash, entries[idx ^ 1]);
    }
    var isEditable = ownerID && ownerID === this.ownerID;
    var newEntries = isEditable ? entries : arrCopy(entries);
    if (exists) {
        if (removed) {
            idx === len - 1
                ? newEntries.pop()
                : (newEntries[idx] = newEntries.pop());
        }
        else {
            newEntries[idx] = [key, value];
        }
    }
    else {
        newEntries.push([key, value]);
    }
    if (isEditable) {
        this.entries = newEntries;
        return this;
    }
    return new HashCollisionNode(ownerID, this.keyHash, newEntries);
};
var ValueNode = function ValueNode(ownerID, keyHash, entry) {
    this.ownerID = ownerID;
    this.keyHash = keyHash;
    this.entry = entry;
};
ValueNode.prototype.get = function get(shift, keyHash, key, notSetValue) {
    return is(key, this.entry[0]) ? this.entry[1] : notSetValue;
};
ValueNode.prototype.update = function update(ownerID, shift, keyHash, key, value, didChangeSize, didAlter) {
    var removed = value === NOT_SET;
    var keyMatch = is(key, this.entry[0]);
    if (keyMatch ? value === this.entry[1] : removed) {
        return this;
    }
    SetRef(didAlter);
    if (removed) {
        SetRef(didChangeSize);
        return; // undefined
    }
    if (keyMatch) {
        if (ownerID && ownerID === this.ownerID) {
            this.entry[1] = value;
            return this;
        }
        return new ValueNode(ownerID, this.keyHash, [key, value]);
    }
    SetRef(didChangeSize);
    return mergeIntoNode(this, ownerID, shift, hash(key), [key, value]);
};
// #pragma Iterators
ArrayMapNode.prototype.iterate = HashCollisionNode.prototype.iterate = function (fn, reverse) {
    var entries = this.entries;
    for (var ii = 0, maxIndex = entries.length - 1; ii <= maxIndex; ii++) {
        if (fn(entries[reverse ? maxIndex - ii : ii]) === false) {
            return false;
        }
    }
};
BitmapIndexedNode.prototype.iterate = HashArrayMapNode.prototype.iterate = function (fn, reverse) {
    var nodes = this.nodes;
    for (var ii = 0, maxIndex = nodes.length - 1; ii <= maxIndex; ii++) {
        var node = nodes[reverse ? maxIndex - ii : ii];
        if (node && node.iterate(fn, reverse) === false) {
            return false;
        }
    }
};
// eslint-disable-next-line no-unused-vars
ValueNode.prototype.iterate = function (fn, reverse) {
    return fn(this.entry);
};
var MapIterator = /*@__PURE__*/ (function (Iterator$$1) {
    function MapIterator(map, type, reverse) {
        this._type = type;
        this._reverse = reverse;
        this._stack = map._root && mapIteratorFrame(map._root);
    }
    if (Iterator$$1)
        MapIterator.__proto__ = Iterator$$1;
    MapIterator.prototype = Object.create(Iterator$$1 && Iterator$$1.prototype);
    MapIterator.prototype.constructor = MapIterator;
    MapIterator.prototype.next = function next() {
        var type = this._type;
        var stack = this._stack;
        while (stack) {
            var node = stack.node;
            var index = stack.index++;
            var maxIndex = (void 0);
            if (node.entry) {
                if (index === 0) {
                    return mapIteratorValue(type, node.entry);
                }
            }
            else if (node.entries) {
                maxIndex = node.entries.length - 1;
                if (index <= maxIndex) {
                    return mapIteratorValue(type, node.entries[this._reverse ? maxIndex - index : index]);
                }
            }
            else {
                maxIndex = node.nodes.length - 1;
                if (index <= maxIndex) {
                    var subNode = node.nodes[this._reverse ? maxIndex - index : index];
                    if (subNode) {
                        if (subNode.entry) {
                            return mapIteratorValue(type, subNode.entry);
                        }
                        stack = this._stack = mapIteratorFrame(subNode, stack);
                    }
                    continue;
                }
            }
            stack = this._stack = this._stack.__prev;
        }
        return iteratorDone();
    };
    return MapIterator;
}(Iterator));
function mapIteratorValue(type, entry) {
    return iteratorValue(type, entry[0], entry[1]);
}
function mapIteratorFrame(node, prev) {
    return {
        node: node,
        index: 0,
        __prev: prev,
    };
}
function makeMap(size, root, ownerID, hash$$1) {
    var map = Object.create(MapPrototype);
    map.size = size;
    map._root = root;
    map.__ownerID = ownerID;
    map.__hash = hash$$1;
    map.__altered = false;
    return map;
}
var EMPTY_MAP;
function emptyMap() {
    return EMPTY_MAP || (EMPTY_MAP = makeMap(0));
}
function updateMap(map, k, v) {
    var newRoot;
    var newSize;
    if (!map._root) {
        if (v === NOT_SET) {
            return map;
        }
        newSize = 1;
        newRoot = new ArrayMapNode(map.__ownerID, [[k, v]]);
    }
    else {
        var didChangeSize = MakeRef();
        var didAlter = MakeRef();
        newRoot = updateNode(map._root, map.__ownerID, 0, undefined, k, v, didChangeSize, didAlter);
        if (!didAlter.value) {
            return map;
        }
        newSize = map.size + (didChangeSize.value ? (v === NOT_SET ? -1 : 1) : 0);
    }
    if (map.__ownerID) {
        map.size = newSize;
        map._root = newRoot;
        map.__hash = undefined;
        map.__altered = true;
        return map;
    }
    return newRoot ? makeMap(newSize, newRoot) : emptyMap();
}
function updateNode(node, ownerID, shift, keyHash, key, value, didChangeSize, didAlter) {
    if (!node) {
        if (value === NOT_SET) {
            return node;
        }
        SetRef(didAlter);
        SetRef(didChangeSize);
        return new ValueNode(ownerID, keyHash, [key, value]);
    }
    return node.update(ownerID, shift, keyHash, key, value, didChangeSize, didAlter);
}
function isLeafNode(node) {
    return (node.constructor === ValueNode || node.constructor === HashCollisionNode);
}
function mergeIntoNode(node, ownerID, shift, keyHash, entry) {
    if (node.keyHash === keyHash) {
        return new HashCollisionNode(ownerID, keyHash, [node.entry, entry]);
    }
    var idx1 = (shift === 0 ? node.keyHash : node.keyHash >>> shift) & MASK;
    var idx2 = (shift === 0 ? keyHash : keyHash >>> shift) & MASK;
    var newNode;
    var nodes = idx1 === idx2
        ? [mergeIntoNode(node, ownerID, shift + SHIFT, keyHash, entry)]
        : ((newNode = new ValueNode(ownerID, keyHash, entry)),
            idx1 < idx2 ? [node, newNode] : [newNode, node]);
    return new BitmapIndexedNode(ownerID, (1 << idx1) | (1 << idx2), nodes);
}
function createNodes(ownerID, entries, key, value) {
    if (!ownerID) {
        ownerID = new OwnerID();
    }
    var node = new ValueNode(ownerID, hash(key), [key, value]);
    for (var ii = 0; ii < entries.length; ii++) {
        var entry = entries[ii];
        node = node.update(ownerID, 0, undefined, entry[0], entry[1]);
    }
    return node;
}
function packNodes(ownerID, nodes, count, excluding) {
    var bitmap = 0;
    var packedII = 0;
    var packedNodes = new Array(count);
    for (var ii = 0, bit = 1, len = nodes.length; ii < len; ii++, bit <<= 1) {
        var node = nodes[ii];
        if (node !== undefined && ii !== excluding) {
            bitmap |= bit;
            packedNodes[packedII++] = node;
        }
    }
    return new BitmapIndexedNode(ownerID, bitmap, packedNodes);
}
function expandNodes(ownerID, nodes, bitmap, including, node) {
    var count = 0;
    var expandedNodes = new Array(SIZE);
    for (var ii = 0; bitmap !== 0; ii++, bitmap >>>= 1) {
        expandedNodes[ii] = bitmap & 1 ? nodes[count++] : undefined;
    }
    expandedNodes[including] = node;
    return new HashArrayMapNode(ownerID, count + 1, expandedNodes);
}
function popCount(x) {
    x -= (x >> 1) & 0x55555555;
    x = (x & 0x33333333) + ((x >> 2) & 0x33333333);
    x = (x + (x >> 4)) & 0x0f0f0f0f;
    x += x >> 8;
    x += x >> 16;
    return x & 0x7f;
}
function setAt(array, idx, val, canEdit) {
    var newArray = canEdit ? array : arrCopy(array);
    newArray[idx] = val;
    return newArray;
}
function spliceIn(array, idx, val, canEdit) {
    var newLen = array.length + 1;
    if (canEdit && idx + 1 === newLen) {
        array[idx] = val;
        return array;
    }
    var newArray = new Array(newLen);
    var after = 0;
    for (var ii = 0; ii < newLen; ii++) {
        if (ii === idx) {
            newArray[ii] = val;
            after = -1;
        }
        else {
            newArray[ii] = array[ii + after];
        }
    }
    return newArray;
}
function spliceOut(array, idx, canEdit) {
    var newLen = array.length - 1;
    if (canEdit && idx === newLen) {
        array.pop();
        return array;
    }
    var newArray = new Array(newLen);
    var after = 0;
    for (var ii = 0; ii < newLen; ii++) {
        if (ii === idx) {
            after = 1;
        }
        newArray[ii] = array[ii + after];
    }
    return newArray;
}
var MAX_ARRAY_MAP_SIZE = SIZE / 4;
var MAX_BITMAP_INDEXED_SIZE = SIZE / 2;
var MIN_HASH_ARRAY_MAP_SIZE = SIZE / 4;
var IS_LIST_SYMBOL = '@@__IMMUTABLE_LIST__@@';
function isList(maybeList) {
    return Boolean(maybeList && maybeList[IS_LIST_SYMBOL]);
}
var List = /*@__PURE__*/ (function (IndexedCollection$$1) {
    function List(value) {
        var empty = emptyList();
        if (value === null || value === undefined) {
            return empty;
        }
        if (isList(value)) {
            return value;
        }
        var iter = IndexedCollection$$1(value);
        var size = iter.size;
        if (size === 0) {
            return empty;
        }
        assertNotInfinite(size);
        if (size > 0 && size < SIZE) {
            return makeList(0, size, SHIFT, null, new VNode(iter.toArray()));
        }
        return empty.withMutations(function (list) {
            list.setSize(size);
            iter.forEach(function (v, i) { return list.set(i, v); });
        });
    }
    if (IndexedCollection$$1)
        List.__proto__ = IndexedCollection$$1;
    List.prototype = Object.create(IndexedCollection$$1 && IndexedCollection$$1.prototype);
    List.prototype.constructor = List;
    List.of = function of( /*...values*/) {
        return this(arguments);
    };
    List.prototype.toString = function toString() {
        return this.__toString('List [', ']');
    };
    // @pragma Access
    List.prototype.get = function get(index, notSetValue) {
        index = wrapIndex(this, index);
        if (index >= 0 && index < this.size) {
            index += this._origin;
            var node = listNodeFor(this, index);
            return node && node.array[index & MASK];
        }
        return notSetValue;
    };
    // @pragma Modification
    List.prototype.set = function set(index, value) {
        return updateList(this, index, value);
    };
    List.prototype.remove = function remove(index) {
        return !this.has(index)
            ? this
            : index === 0
                ? this.shift()
                : index === this.size - 1
                    ? this.pop()
                    : this.splice(index, 1);
    };
    List.prototype.insert = function insert(index, value) {
        return this.splice(index, 0, value);
    };
    List.prototype.clear = function clear() {
        if (this.size === 0) {
            return this;
        }
        if (this.__ownerID) {
            this.size = this._origin = this._capacity = 0;
            this._level = SHIFT;
            this._root = this._tail = null;
            this.__hash = undefined;
            this.__altered = true;
            return this;
        }
        return emptyList();
    };
    List.prototype.push = function push( /*...values*/) {
        var values = arguments;
        var oldSize = this.size;
        return this.withMutations(function (list) {
            setListBounds(list, 0, oldSize + values.length);
            for (var ii = 0; ii < values.length; ii++) {
                list.set(oldSize + ii, values[ii]);
            }
        });
    };
    List.prototype.pop = function pop() {
        return setListBounds(this, 0, -1);
    };
    List.prototype.unshift = function unshift( /*...values*/) {
        var values = arguments;
        return this.withMutations(function (list) {
            setListBounds(list, -values.length);
            for (var ii = 0; ii < values.length; ii++) {
                list.set(ii, values[ii]);
            }
        });
    };
    List.prototype.shift = function shift() {
        return setListBounds(this, 1);
    };
    // @pragma Composition
    List.prototype.concat = function concat( /*...collections*/) {
        var arguments$1 = arguments;
        var seqs = [];
        for (var i = 0; i < arguments.length; i++) {
            var argument = arguments$1[i];
            var seq = IndexedCollection$$1(typeof argument !== 'string' && hasIterator(argument)
                ? argument
                : [argument]);
            if (seq.size !== 0) {
                seqs.push(seq);
            }
        }
        if (seqs.length === 0) {
            return this;
        }
        if (this.size === 0 && !this.__ownerID && seqs.length === 1) {
            return this.constructor(seqs[0]);
        }
        return this.withMutations(function (list) {
            seqs.forEach(function (seq) { return seq.forEach(function (value) { return list.push(value); }); });
        });
    };
    List.prototype.setSize = function setSize(size) {
        return setListBounds(this, 0, size);
    };
    List.prototype.map = function map(mapper, context) {
        var this$1 = this;
        return this.withMutations(function (list) {
            for (var i = 0; i < this$1.size; i++) {
                list.set(i, mapper.call(context, list.get(i), i, list));
            }
        });
    };
    // @pragma Iteration
    List.prototype.slice = function slice(begin, end) {
        var size = this.size;
        if (wholeSlice(begin, end, size)) {
            return this;
        }
        return setListBounds(this, resolveBegin(begin, size), resolveEnd(end, size));
    };
    List.prototype.__iterator = function __iterator(type, reverse) {
        var index = reverse ? this.size : 0;
        var values = iterateList(this, reverse);
        return new Iterator(function () {
            var value = values();
            return value === DONE
                ? iteratorDone()
                : iteratorValue(type, reverse ? --index : index++, value);
        });
    };
    List.prototype.__iterate = function __iterate(fn, reverse) {
        var index = reverse ? this.size : 0;
        var values = iterateList(this, reverse);
        var value;
        while ((value = values()) !== DONE) {
            if (fn(value, reverse ? --index : index++, this) === false) {
                break;
            }
        }
        return index;
    };
    List.prototype.__ensureOwner = function __ensureOwner(ownerID) {
        if (ownerID === this.__ownerID) {
            return this;
        }
        if (!ownerID) {
            if (this.size === 0) {
                return emptyList();
            }
            this.__ownerID = ownerID;
            this.__altered = false;
            return this;
        }
        return makeList(this._origin, this._capacity, this._level, this._root, this._tail, ownerID, this.__hash);
    };
    return List;
}(IndexedCollection));
List.isList = isList;
var ListPrototype = List.prototype;
ListPrototype[IS_LIST_SYMBOL] = true;
ListPrototype[DELETE] = ListPrototype.remove;
ListPrototype.merge = ListPrototype.concat;
ListPrototype.setIn = setIn$1;
ListPrototype.deleteIn = ListPrototype.removeIn = deleteIn;
ListPrototype.update = update$1;
ListPrototype.updateIn = updateIn$1;
ListPrototype.mergeIn = mergeIn;
ListPrototype.mergeDeepIn = mergeDeepIn;
ListPrototype.withMutations = withMutations;
ListPrototype.wasAltered = wasAltered;
ListPrototype.asImmutable = asImmutable;
ListPrototype['@@transducer/init'] = ListPrototype.asMutable = asMutable;
ListPrototype['@@transducer/step'] = function (result, arr) {
    return result.push(arr);
};
ListPrototype['@@transducer/result'] = function (obj) {
    return obj.asImmutable();
};
var VNode = function VNode(array, ownerID) {
    this.array = array;
    this.ownerID = ownerID;
};
// TODO: seems like these methods are very similar
VNode.prototype.removeBefore = function removeBefore(ownerID, level, index) {
    if (index === level ? 1 << level : this.array.length === 0) {
        return this;
    }
    var originIndex = (index >>> level) & MASK;
    if (originIndex >= this.array.length) {
        return new VNode([], ownerID);
    }
    var removingFirst = originIndex === 0;
    var newChild;
    if (level > 0) {
        var oldChild = this.array[originIndex];
        newChild =
            oldChild && oldChild.removeBefore(ownerID, level - SHIFT, index);
        if (newChild === oldChild && removingFirst) {
            return this;
        }
    }
    if (removingFirst && !newChild) {
        return this;
    }
    var editable = editableVNode(this, ownerID);
    if (!removingFirst) {
        for (var ii = 0; ii < originIndex; ii++) {
            editable.array[ii] = undefined;
        }
    }
    if (newChild) {
        editable.array[originIndex] = newChild;
    }
    return editable;
};
VNode.prototype.removeAfter = function removeAfter(ownerID, level, index) {
    if (index === (level ? 1 << level : 0) || this.array.length === 0) {
        return this;
    }
    var sizeIndex = ((index - 1) >>> level) & MASK;
    if (sizeIndex >= this.array.length) {
        return this;
    }
    var newChild;
    if (level > 0) {
        var oldChild = this.array[sizeIndex];
        newChild =
            oldChild && oldChild.removeAfter(ownerID, level - SHIFT, index);
        if (newChild === oldChild && sizeIndex === this.array.length - 1) {
            return this;
        }
    }
    var editable = editableVNode(this, ownerID);
    editable.array.splice(sizeIndex + 1);
    if (newChild) {
        editable.array[sizeIndex] = newChild;
    }
    return editable;
};
var DONE = {};
function iterateList(list, reverse) {
    var left = list._origin;
    var right = list._capacity;
    var tailPos = getTailOffset(right);
    var tail = list._tail;
    return iterateNodeOrLeaf(list._root, list._level, 0);
    function iterateNodeOrLeaf(node, level, offset) {
        return level === 0
            ? iterateLeaf(node, offset)
            : iterateNode(node, level, offset);
    }
    function iterateLeaf(node, offset) {
        var array = offset === tailPos ? tail && tail.array : node && node.array;
        var from = offset > left ? 0 : left - offset;
        var to = right - offset;
        if (to > SIZE) {
            to = SIZE;
        }
        return function () {
            if (from === to) {
                return DONE;
            }
            var idx = reverse ? --to : from++;
            return array && array[idx];
        };
    }
    function iterateNode(node, level, offset) {
        var values;
        var array = node && node.array;
        var from = offset > left ? 0 : (left - offset) >> level;
        var to = ((right - offset) >> level) + 1;
        if (to > SIZE) {
            to = SIZE;
        }
        return function () {
            while (true) {
                if (values) {
                    var value = values();
                    if (value !== DONE) {
                        return value;
                    }
                    values = null;
                }
                if (from === to) {
                    return DONE;
                }
                var idx = reverse ? --to : from++;
                values = iterateNodeOrLeaf(array && array[idx], level - SHIFT, offset + (idx << level));
            }
        };
    }
}
function makeList(origin, capacity, level, root, tail, ownerID, hash) {
    var list = Object.create(ListPrototype);
    list.size = capacity - origin;
    list._origin = origin;
    list._capacity = capacity;
    list._level = level;
    list._root = root;
    list._tail = tail;
    list.__ownerID = ownerID;
    list.__hash = hash;
    list.__altered = false;
    return list;
}
var EMPTY_LIST;
function emptyList() {
    return EMPTY_LIST || (EMPTY_LIST = makeList(0, 0, SHIFT));
}
function updateList(list, index, value) {
    index = wrapIndex(list, index);
    if (index !== index) {
        return list;
    }
    if (index >= list.size || index < 0) {
        return list.withMutations(function (list) {
            index < 0
                ? setListBounds(list, index).set(0, value)
                : setListBounds(list, 0, index + 1).set(index, value);
        });
    }
    index += list._origin;
    var newTail = list._tail;
    var newRoot = list._root;
    var didAlter = MakeRef();
    if (index >= getTailOffset(list._capacity)) {
        newTail = updateVNode(newTail, list.__ownerID, 0, index, value, didAlter);
    }
    else {
        newRoot = updateVNode(newRoot, list.__ownerID, list._level, index, value, didAlter);
    }
    if (!didAlter.value) {
        return list;
    }
    if (list.__ownerID) {
        list._root = newRoot;
        list._tail = newTail;
        list.__hash = undefined;
        list.__altered = true;
        return list;
    }
    return makeList(list._origin, list._capacity, list._level, newRoot, newTail);
}
function updateVNode(node, ownerID, level, index, value, didAlter) {
    var idx = (index >>> level) & MASK;
    var nodeHas = node && idx < node.array.length;
    if (!nodeHas && value === undefined) {
        return node;
    }
    var newNode;
    if (level > 0) {
        var lowerNode = node && node.array[idx];
        var newLowerNode = updateVNode(lowerNode, ownerID, level - SHIFT, index, value, didAlter);
        if (newLowerNode === lowerNode) {
            return node;
        }
        newNode = editableVNode(node, ownerID);
        newNode.array[idx] = newLowerNode;
        return newNode;
    }
    if (nodeHas && node.array[idx] === value) {
        return node;
    }
    if (didAlter) {
        SetRef(didAlter);
    }
    newNode = editableVNode(node, ownerID);
    if (value === undefined && idx === newNode.array.length - 1) {
        newNode.array.pop();
    }
    else {
        newNode.array[idx] = value;
    }
    return newNode;
}
function editableVNode(node, ownerID) {
    if (ownerID && node && ownerID === node.ownerID) {
        return node;
    }
    return new VNode(node ? node.array.slice() : [], ownerID);
}
function listNodeFor(list, rawIndex) {
    if (rawIndex >= getTailOffset(list._capacity)) {
        return list._tail;
    }
    if (rawIndex < 1 << (list._level + SHIFT)) {
        var node = list._root;
        var level = list._level;
        while (node && level > 0) {
            node = node.array[(rawIndex >>> level) & MASK];
            level -= SHIFT;
        }
        return node;
    }
}
function setListBounds(list, begin, end) {
    // Sanitize begin & end using this shorthand for ToInt32(argument)
    // http://www.ecma-international.org/ecma-262/6.0/#sec-toint32
    if (begin !== undefined) {
        begin |= 0;
    }
    if (end !== undefined) {
        end |= 0;
    }
    var owner = list.__ownerID || new OwnerID();
    var oldOrigin = list._origin;
    var oldCapacity = list._capacity;
    var newOrigin = oldOrigin + begin;
    var newCapacity = end === undefined
        ? oldCapacity
        : end < 0
            ? oldCapacity + end
            : oldOrigin + end;
    if (newOrigin === oldOrigin && newCapacity === oldCapacity) {
        return list;
    }
    // If it's going to end after it starts, it's empty.
    if (newOrigin >= newCapacity) {
        return list.clear();
    }
    var newLevel = list._level;
    var newRoot = list._root;
    // New origin might need creating a higher root.
    var offsetShift = 0;
    while (newOrigin + offsetShift < 0) {
        newRoot = new VNode(newRoot && newRoot.array.length ? [undefined, newRoot] : [], owner);
        newLevel += SHIFT;
        offsetShift += 1 << newLevel;
    }
    if (offsetShift) {
        newOrigin += offsetShift;
        oldOrigin += offsetShift;
        newCapacity += offsetShift;
        oldCapacity += offsetShift;
    }
    var oldTailOffset = getTailOffset(oldCapacity);
    var newTailOffset = getTailOffset(newCapacity);
    // New size might need creating a higher root.
    while (newTailOffset >= 1 << (newLevel + SHIFT)) {
        newRoot = new VNode(newRoot && newRoot.array.length ? [newRoot] : [], owner);
        newLevel += SHIFT;
    }
    // Locate or create the new tail.
    var oldTail = list._tail;
    var newTail = newTailOffset < oldTailOffset
        ? listNodeFor(list, newCapacity - 1)
        : newTailOffset > oldTailOffset
            ? new VNode([], owner)
            : oldTail;
    // Merge Tail into tree.
    if (oldTail &&
        newTailOffset > oldTailOffset &&
        newOrigin < oldCapacity &&
        oldTail.array.length) {
        newRoot = editableVNode(newRoot, owner);
        var node = newRoot;
        for (var level = newLevel; level > SHIFT; level -= SHIFT) {
            var idx = (oldTailOffset >>> level) & MASK;
            node = node.array[idx] = editableVNode(node.array[idx], owner);
        }
        node.array[(oldTailOffset >>> SHIFT) & MASK] = oldTail;
    }
    // If the size has been reduced, there's a chance the tail needs to be trimmed.
    if (newCapacity < oldCapacity) {
        newTail = newTail && newTail.removeAfter(owner, 0, newCapacity);
    }
    // If the new origin is within the tail, then we do not need a root.
    if (newOrigin >= newTailOffset) {
        newOrigin -= newTailOffset;
        newCapacity -= newTailOffset;
        newLevel = SHIFT;
        newRoot = null;
        newTail = newTail && newTail.removeBefore(owner, 0, newOrigin);
        // Otherwise, if the root has been trimmed, garbage collect.
    }
    else if (newOrigin > oldOrigin || newTailOffset < oldTailOffset) {
        offsetShift = 0;
        // Identify the new top root node of the subtree of the old root.
        while (newRoot) {
            var beginIndex = (newOrigin >>> newLevel) & MASK;
            if ((beginIndex !== newTailOffset >>> newLevel) & MASK) {
                break;
            }
            if (beginIndex) {
                offsetShift += (1 << newLevel) * beginIndex;
            }
            newLevel -= SHIFT;
            newRoot = newRoot.array[beginIndex];
        }
        // Trim the new sides of the new root.
        if (newRoot && newOrigin > oldOrigin) {
            newRoot = newRoot.removeBefore(owner, newLevel, newOrigin - offsetShift);
        }
        if (newRoot && newTailOffset < oldTailOffset) {
            newRoot = newRoot.removeAfter(owner, newLevel, newTailOffset - offsetShift);
        }
        if (offsetShift) {
            newOrigin -= offsetShift;
            newCapacity -= offsetShift;
        }
    }
    if (list.__ownerID) {
        list.size = newCapacity - newOrigin;
        list._origin = newOrigin;
        list._capacity = newCapacity;
        list._level = newLevel;
        list._root = newRoot;
        list._tail = newTail;
        list.__hash = undefined;
        list.__altered = true;
        return list;
    }
    return makeList(newOrigin, newCapacity, newLevel, newRoot, newTail);
}
function getTailOffset(size) {
    return size < SIZE ? 0 : ((size - 1) >>> SHIFT) << SHIFT;
}
var OrderedMap = /*@__PURE__*/ (function (Map$$1) {
    function OrderedMap(value) {
        return value === null || value === undefined
            ? emptyOrderedMap()
            : isOrderedMap(value)
                ? value
                : emptyOrderedMap().withMutations(function (map) {
                    var iter = KeyedCollection(value);
                    assertNotInfinite(iter.size);
                    iter.forEach(function (v, k) { return map.set(k, v); });
                });
    }
    if (Map$$1)
        OrderedMap.__proto__ = Map$$1;
    OrderedMap.prototype = Object.create(Map$$1 && Map$$1.prototype);
    OrderedMap.prototype.constructor = OrderedMap;
    OrderedMap.of = function of( /*...values*/) {
        return this(arguments);
    };
    OrderedMap.prototype.toString = function toString() {
        return this.__toString('OrderedMap {', '}');
    };
    // @pragma Access
    OrderedMap.prototype.get = function get(k, notSetValue) {
        var index = this._map.get(k);
        return index !== undefined ? this._list.get(index)[1] : notSetValue;
    };
    // @pragma Modification
    OrderedMap.prototype.clear = function clear() {
        if (this.size === 0) {
            return this;
        }
        if (this.__ownerID) {
            this.size = 0;
            this._map.clear();
            this._list.clear();
            return this;
        }
        return emptyOrderedMap();
    };
    OrderedMap.prototype.set = function set(k, v) {
        return updateOrderedMap(this, k, v);
    };
    OrderedMap.prototype.remove = function remove(k) {
        return updateOrderedMap(this, k, NOT_SET);
    };
    OrderedMap.prototype.wasAltered = function wasAltered() {
        return this._map.wasAltered() || this._list.wasAltered();
    };
    OrderedMap.prototype.__iterate = function __iterate(fn, reverse) {
        var this$1 = this;
        return this._list.__iterate(function (entry) { return entry && fn(entry[1], entry[0], this$1); }, reverse);
    };
    OrderedMap.prototype.__iterator = function __iterator(type, reverse) {
        return this._list.fromEntrySeq().__iterator(type, reverse);
    };
    OrderedMap.prototype.__ensureOwner = function __ensureOwner(ownerID) {
        if (ownerID === this.__ownerID) {
            return this;
        }
        var newMap = this._map.__ensureOwner(ownerID);
        var newList = this._list.__ensureOwner(ownerID);
        if (!ownerID) {
            if (this.size === 0) {
                return emptyOrderedMap();
            }
            this.__ownerID = ownerID;
            this._map = newMap;
            this._list = newList;
            return this;
        }
        return makeOrderedMap(newMap, newList, ownerID, this.__hash);
    };
    return OrderedMap;
}(Map$1));
OrderedMap.isOrderedMap = isOrderedMap;
OrderedMap.prototype[IS_ORDERED_SYMBOL] = true;
OrderedMap.prototype[DELETE] = OrderedMap.prototype.remove;
function makeOrderedMap(map, list, ownerID, hash) {
    var omap = Object.create(OrderedMap.prototype);
    omap.size = map ? map.size : 0;
    omap._map = map;
    omap._list = list;
    omap.__ownerID = ownerID;
    omap.__hash = hash;
    return omap;
}
var EMPTY_ORDERED_MAP;
function emptyOrderedMap() {
    return (EMPTY_ORDERED_MAP ||
        (EMPTY_ORDERED_MAP = makeOrderedMap(emptyMap(), emptyList())));
}
function updateOrderedMap(omap, k, v) {
    var map = omap._map;
    var list = omap._list;
    var i = map.get(k);
    var has = i !== undefined;
    var newMap;
    var newList;
    if (v === NOT_SET) {
        // removed
        if (!has) {
            return omap;
        }
        if (list.size >= SIZE && list.size >= map.size * 2) {
            newList = list.filter(function (entry, idx) { return entry !== undefined && i !== idx; });
            newMap = newList
                .toKeyedSeq()
                .map(function (entry) { return entry[0]; })
                .flip()
                .toMap();
            if (omap.__ownerID) {
                newMap.__ownerID = newList.__ownerID = omap.__ownerID;
            }
        }
        else {
            newMap = map.remove(k);
            newList = i === list.size - 1 ? list.pop() : list.set(i, undefined);
        }
    }
    else if (has) {
        if (v === list.get(i)[1]) {
            return omap;
        }
        newMap = map;
        newList = list.set(i, [k, v]);
    }
    else {
        newMap = map.set(k, list.size);
        newList = list.set(list.size, [k, v]);
    }
    if (omap.__ownerID) {
        omap.size = newMap.size;
        omap._map = newMap;
        omap._list = newList;
        omap.__hash = undefined;
        return omap;
    }
    return makeOrderedMap(newMap, newList);
}
var IS_STACK_SYMBOL = '@@__IMMUTABLE_STACK__@@';
function isStack(maybeStack) {
    return Boolean(maybeStack && maybeStack[IS_STACK_SYMBOL]);
}
var Stack = /*@__PURE__*/ (function (IndexedCollection$$1) {
    function Stack(value) {
        return value === null || value === undefined
            ? emptyStack()
            : isStack(value)
                ? value
                : emptyStack().pushAll(value);
    }
    if (IndexedCollection$$1)
        Stack.__proto__ = IndexedCollection$$1;
    Stack.prototype = Object.create(IndexedCollection$$1 && IndexedCollection$$1.prototype);
    Stack.prototype.constructor = Stack;
    Stack.of = function of( /*...values*/) {
        return this(arguments);
    };
    Stack.prototype.toString = function toString() {
        return this.__toString('Stack [', ']');
    };
    // @pragma Access
    Stack.prototype.get = function get(index, notSetValue) {
        var head = this._head;
        index = wrapIndex(this, index);
        while (head && index--) {
            head = head.next;
        }
        return head ? head.value : notSetValue;
    };
    Stack.prototype.peek = function peek() {
        return this._head && this._head.value;
    };
    // @pragma Modification
    Stack.prototype.push = function push( /*...values*/) {
        var arguments$1 = arguments;
        if (arguments.length === 0) {
            return this;
        }
        var newSize = this.size + arguments.length;
        var head = this._head;
        for (var ii = arguments.length - 1; ii >= 0; ii--) {
            head = {
                value: arguments$1[ii],
                next: head,
            };
        }
        if (this.__ownerID) {
            this.size = newSize;
            this._head = head;
            this.__hash = undefined;
            this.__altered = true;
            return this;
        }
        return makeStack(newSize, head);
    };
    Stack.prototype.pushAll = function pushAll(iter) {
        iter = IndexedCollection$$1(iter);
        if (iter.size === 0) {
            return this;
        }
        if (this.size === 0 && isStack(iter)) {
            return iter;
        }
        assertNotInfinite(iter.size);
        var newSize = this.size;
        var head = this._head;
        iter.__iterate(function (value) {
            newSize++;
            head = {
                value: value,
                next: head,
            };
        }, /* reverse */ true);
        if (this.__ownerID) {
            this.size = newSize;
            this._head = head;
            this.__hash = undefined;
            this.__altered = true;
            return this;
        }
        return makeStack(newSize, head);
    };
    Stack.prototype.pop = function pop() {
        return this.slice(1);
    };
    Stack.prototype.clear = function clear() {
        if (this.size === 0) {
            return this;
        }
        if (this.__ownerID) {
            this.size = 0;
            this._head = undefined;
            this.__hash = undefined;
            this.__altered = true;
            return this;
        }
        return emptyStack();
    };
    Stack.prototype.slice = function slice(begin, end) {
        if (wholeSlice(begin, end, this.size)) {
            return this;
        }
        var resolvedBegin = resolveBegin(begin, this.size);
        var resolvedEnd = resolveEnd(end, this.size);
        if (resolvedEnd !== this.size) {
            // super.slice(begin, end);
            return IndexedCollection$$1.prototype.slice.call(this, begin, end);
        }
        var newSize = this.size - resolvedBegin;
        var head = this._head;
        while (resolvedBegin--) {
            head = head.next;
        }
        if (this.__ownerID) {
            this.size = newSize;
            this._head = head;
            this.__hash = undefined;
            this.__altered = true;
            return this;
        }
        return makeStack(newSize, head);
    };
    // @pragma Mutability
    Stack.prototype.__ensureOwner = function __ensureOwner(ownerID) {
        if (ownerID === this.__ownerID) {
            return this;
        }
        if (!ownerID) {
            if (this.size === 0) {
                return emptyStack();
            }
            this.__ownerID = ownerID;
            this.__altered = false;
            return this;
        }
        return makeStack(this.size, this._head, ownerID, this.__hash);
    };
    // @pragma Iteration
    Stack.prototype.__iterate = function __iterate(fn, reverse) {
        var this$1 = this;
        if (reverse) {
            return new ArraySeq(this.toArray()).__iterate(function (v, k) { return fn(v, k, this$1); }, reverse);
        }
        var iterations = 0;
        var node = this._head;
        while (node) {
            if (fn(node.value, iterations++, this) === false) {
                break;
            }
            node = node.next;
        }
        return iterations;
    };
    Stack.prototype.__iterator = function __iterator(type, reverse) {
        if (reverse) {
            return new ArraySeq(this.toArray()).__iterator(type, reverse);
        }
        var iterations = 0;
        var node = this._head;
        return new Iterator(function () {
            if (node) {
                var value = node.value;
                node = node.next;
                return iteratorValue(type, iterations++, value);
            }
            return iteratorDone();
        });
    };
    return Stack;
}(IndexedCollection));
Stack.isStack = isStack;
var StackPrototype = Stack.prototype;
StackPrototype[IS_STACK_SYMBOL] = true;
StackPrototype.shift = StackPrototype.pop;
StackPrototype.unshift = StackPrototype.push;
StackPrototype.unshiftAll = StackPrototype.pushAll;
StackPrototype.withMutations = withMutations;
StackPrototype.wasAltered = wasAltered;
StackPrototype.asImmutable = asImmutable;
StackPrototype['@@transducer/init'] = StackPrototype.asMutable = asMutable;
StackPrototype['@@transducer/step'] = function (result, arr) {
    return result.unshift(arr);
};
StackPrototype['@@transducer/result'] = function (obj) {
    return obj.asImmutable();
};
function makeStack(size, head, ownerID, hash) {
    var map = Object.create(StackPrototype);
    map.size = size;
    map._head = head;
    map.__ownerID = ownerID;
    map.__hash = hash;
    map.__altered = false;
    return map;
}
var EMPTY_STACK;
function emptyStack() {
    return EMPTY_STACK || (EMPTY_STACK = makeStack(0));
}
var IS_SET_SYMBOL = '@@__IMMUTABLE_SET__@@';
function isSet(maybeSet) {
    return Boolean(maybeSet && maybeSet[IS_SET_SYMBOL]);
}
function isOrderedSet(maybeOrderedSet) {
    return isSet(maybeOrderedSet) && isOrdered(maybeOrderedSet);
}
function deepEqual(a, b) {
    if (a === b) {
        return true;
    }
    if (!isCollection(b) ||
        (a.size !== undefined && b.size !== undefined && a.size !== b.size) ||
        (a.__hash !== undefined &&
            b.__hash !== undefined &&
            a.__hash !== b.__hash) ||
        isKeyed(a) !== isKeyed(b) ||
        isIndexed(a) !== isIndexed(b) ||
        isOrdered(a) !== isOrdered(b)) {
        return false;
    }
    if (a.size === 0 && b.size === 0) {
        return true;
    }
    var notAssociative = !isAssociative(a);
    if (isOrdered(a)) {
        var entries = a.entries();
        return (b.every(function (v, k) {
            var entry = entries.next().value;
            return entry && is(entry[1], v) && (notAssociative || is(entry[0], k));
        }) && entries.next().done);
    }
    var flipped = false;
    if (a.size === undefined) {
        if (b.size === undefined) {
            if (typeof a.cacheResult === 'function') {
                a.cacheResult();
            }
        }
        else {
            flipped = true;
            var _ = a;
            a = b;
            b = _;
        }
    }
    var allEqual = true;
    var bSize = b.__iterate(function (v, k) {
        if (notAssociative
            ? !a.has(v)
            : flipped
                ? !is(v, a.get(k, NOT_SET))
                : !is(a.get(k, NOT_SET), v)) {
            allEqual = false;
            return false;
        }
    });
    return allEqual && a.size === bSize;
}
/**
 * Contributes additional methods to a constructor
 */
function mixin(ctor, methods) {
    var keyCopier = function (key) {
        ctor.prototype[key] = methods[key];
    };
    Object.keys(methods).forEach(keyCopier);
    Object.getOwnPropertySymbols &&
        Object.getOwnPropertySymbols(methods).forEach(keyCopier);
    return ctor;
}
function toJS(value) {
    if (!value || typeof value !== 'object') {
        return value;
    }
    if (!isCollection(value)) {
        if (!isDataStructure(value)) {
            return value;
        }
        value = Seq(value);
    }
    if (isKeyed(value)) {
        var result$1 = {};
        value.__iterate(function (v, k) {
            result$1[k] = toJS(v);
        });
        return result$1;
    }
    var result = [];
    value.__iterate(function (v) {
        result.push(toJS(v));
    });
    return result;
}
var Set$1 = /*@__PURE__*/ (function (SetCollection$$1) {
    function Set(value) {
        return value === null || value === undefined
            ? emptySet()
            : isSet(value) && !isOrdered(value)
                ? value
                : emptySet().withMutations(function (set) {
                    var iter = SetCollection$$1(value);
                    assertNotInfinite(iter.size);
                    iter.forEach(function (v) { return set.add(v); });
                });
    }
    if (SetCollection$$1)
        Set.__proto__ = SetCollection$$1;
    Set.prototype = Object.create(SetCollection$$1 && SetCollection$$1.prototype);
    Set.prototype.constructor = Set;
    Set.of = function of( /*...values*/) {
        return this(arguments);
    };
    Set.fromKeys = function fromKeys(value) {
        return this(KeyedCollection(value).keySeq());
    };
    Set.intersect = function intersect(sets) {
        sets = Collection(sets).toArray();
        return sets.length
            ? SetPrototype.intersect.apply(Set(sets.pop()), sets)
            : emptySet();
    };
    Set.union = function union(sets) {
        sets = Collection(sets).toArray();
        return sets.length
            ? SetPrototype.union.apply(Set(sets.pop()), sets)
            : emptySet();
    };
    Set.prototype.toString = function toString() {
        return this.__toString('Set {', '}');
    };
    // @pragma Access
    Set.prototype.has = function has(value) {
        return this._map.has(value);
    };
    // @pragma Modification
    Set.prototype.add = function add(value) {
        return updateSet(this, this._map.set(value, value));
    };
    Set.prototype.remove = function remove(value) {
        return updateSet(this, this._map.remove(value));
    };
    Set.prototype.clear = function clear() {
        return updateSet(this, this._map.clear());
    };
    // @pragma Composition
    Set.prototype.map = function map(mapper, context) {
        var this$1 = this;
        var removes = [];
        var adds = [];
        this.forEach(function (value) {
            var mapped = mapper.call(context, value, value, this$1);
            if (mapped !== value) {
                removes.push(value);
                adds.push(mapped);
            }
        });
        return this.withMutations(function (set) {
            removes.forEach(function (value) { return set.remove(value); });
            adds.forEach(function (value) { return set.add(value); });
        });
    };
    Set.prototype.union = function union() {
        var iters = [], len = arguments.length;
        while (len--)
            iters[len] = arguments[len];
        iters = iters.filter(function (x) { return x.size !== 0; });
        if (iters.length === 0) {
            return this;
        }
        if (this.size === 0 && !this.__ownerID && iters.length === 1) {
            return this.constructor(iters[0]);
        }
        return this.withMutations(function (set) {
            for (var ii = 0; ii < iters.length; ii++) {
                SetCollection$$1(iters[ii]).forEach(function (value) { return set.add(value); });
            }
        });
    };
    Set.prototype.intersect = function intersect() {
        var iters = [], len = arguments.length;
        while (len--)
            iters[len] = arguments[len];
        if (iters.length === 0) {
            return this;
        }
        iters = iters.map(function (iter) { return SetCollection$$1(iter); });
        var toRemove = [];
        this.forEach(function (value) {
            if (!iters.every(function (iter) { return iter.includes(value); })) {
                toRemove.push(value);
            }
        });
        return this.withMutations(function (set) {
            toRemove.forEach(function (value) {
                set.remove(value);
            });
        });
    };
    Set.prototype.subtract = function subtract() {
        var iters = [], len = arguments.length;
        while (len--)
            iters[len] = arguments[len];
        if (iters.length === 0) {
            return this;
        }
        iters = iters.map(function (iter) { return SetCollection$$1(iter); });
        var toRemove = [];
        this.forEach(function (value) {
            if (iters.some(function (iter) { return iter.includes(value); })) {
                toRemove.push(value);
            }
        });
        return this.withMutations(function (set) {
            toRemove.forEach(function (value) {
                set.remove(value);
            });
        });
    };
    Set.prototype.sort = function sort(comparator) {
        // Late binding
        return OrderedSet(sortFactory(this, comparator));
    };
    Set.prototype.sortBy = function sortBy(mapper, comparator) {
        // Late binding
        return OrderedSet(sortFactory(this, comparator, mapper));
    };
    Set.prototype.wasAltered = function wasAltered() {
        return this._map.wasAltered();
    };
    Set.prototype.__iterate = function __iterate(fn, reverse) {
        var this$1 = this;
        return this._map.__iterate(function (k) { return fn(k, k, this$1); }, reverse);
    };
    Set.prototype.__iterator = function __iterator(type, reverse) {
        return this._map.__iterator(type, reverse);
    };
    Set.prototype.__ensureOwner = function __ensureOwner(ownerID) {
        if (ownerID === this.__ownerID) {
            return this;
        }
        var newMap = this._map.__ensureOwner(ownerID);
        if (!ownerID) {
            if (this.size === 0) {
                return this.__empty();
            }
            this.__ownerID = ownerID;
            this._map = newMap;
            return this;
        }
        return this.__make(newMap, ownerID);
    };
    return Set;
}(SetCollection));
Set$1.isSet = isSet;
var SetPrototype = Set$1.prototype;
SetPrototype[IS_SET_SYMBOL] = true;
SetPrototype[DELETE] = SetPrototype.remove;
SetPrototype.merge = SetPrototype.concat = SetPrototype.union;
SetPrototype.withMutations = withMutations;
SetPrototype.asImmutable = asImmutable;
SetPrototype['@@transducer/init'] = SetPrototype.asMutable = asMutable;
SetPrototype['@@transducer/step'] = function (result, arr) {
    return result.add(arr);
};
SetPrototype['@@transducer/result'] = function (obj) {
    return obj.asImmutable();
};
SetPrototype.__empty = emptySet;
SetPrototype.__make = makeSet;
function updateSet(set, newMap) {
    if (set.__ownerID) {
        set.size = newMap.size;
        set._map = newMap;
        return set;
    }
    return newMap === set._map
        ? set
        : newMap.size === 0
            ? set.__empty()
            : set.__make(newMap);
}
function makeSet(map, ownerID) {
    var set = Object.create(SetPrototype);
    set.size = map ? map.size : 0;
    set._map = map;
    set.__ownerID = ownerID;
    return set;
}
var EMPTY_SET;
function emptySet() {
    return EMPTY_SET || (EMPTY_SET = makeSet(emptyMap()));
}
/**
 * Returns a lazy seq of nums from start (inclusive) to end
 * (exclusive), by step, where start defaults to 0, step to 1, and end to
 * infinity. When start is equal to end, returns empty list.
 */
var Range = /*@__PURE__*/ (function (IndexedSeq$$1) {
    function Range(start, end, step) {
        if (!(this instanceof Range)) {
            return new Range(start, end, step);
        }
        invariant(step !== 0, 'Cannot step a Range by 0');
        start = start || 0;
        if (end === undefined) {
            end = Infinity;
        }
        step = step === undefined ? 1 : Math.abs(step);
        if (end < start) {
            step = -step;
        }
        this._start = start;
        this._end = end;
        this._step = step;
        this.size = Math.max(0, Math.ceil((end - start) / step - 1) + 1);
        if (this.size === 0) {
            if (EMPTY_RANGE) {
                return EMPTY_RANGE;
            }
            EMPTY_RANGE = this;
        }
    }
    if (IndexedSeq$$1)
        Range.__proto__ = IndexedSeq$$1;
    Range.prototype = Object.create(IndexedSeq$$1 && IndexedSeq$$1.prototype);
    Range.prototype.constructor = Range;
    Range.prototype.toString = function toString() {
        if (this.size === 0) {
            return 'Range []';
        }
        return ('Range [ ' +
            this._start +
            '...' +
            this._end +
            (this._step !== 1 ? ' by ' + this._step : '') +
            ' ]');
    };
    Range.prototype.get = function get(index, notSetValue) {
        return this.has(index)
            ? this._start + wrapIndex(this, index) * this._step
            : notSetValue;
    };
    Range.prototype.includes = function includes(searchValue) {
        var possibleIndex = (searchValue - this._start) / this._step;
        return (possibleIndex >= 0 &&
            possibleIndex < this.size &&
            possibleIndex === Math.floor(possibleIndex));
    };
    Range.prototype.slice = function slice(begin, end) {
        if (wholeSlice(begin, end, this.size)) {
            return this;
        }
        begin = resolveBegin(begin, this.size);
        end = resolveEnd(end, this.size);
        if (end <= begin) {
            return new Range(0, 0);
        }
        return new Range(this.get(begin, this._end), this.get(end, this._end), this._step);
    };
    Range.prototype.indexOf = function indexOf(searchValue) {
        var offsetValue = searchValue - this._start;
        if (offsetValue % this._step === 0) {
            var index = offsetValue / this._step;
            if (index >= 0 && index < this.size) {
                return index;
            }
        }
        return -1;
    };
    Range.prototype.lastIndexOf = function lastIndexOf(searchValue) {
        return this.indexOf(searchValue);
    };
    Range.prototype.__iterate = function __iterate(fn, reverse) {
        var size = this.size;
        var step = this._step;
        var value = reverse ? this._start + (size - 1) * step : this._start;
        var i = 0;
        while (i !== size) {
            if (fn(value, reverse ? size - ++i : i++, this) === false) {
                break;
            }
            value += reverse ? -step : step;
        }
        return i;
    };
    Range.prototype.__iterator = function __iterator(type, reverse) {
        var size = this.size;
        var step = this._step;
        var value = reverse ? this._start + (size - 1) * step : this._start;
        var i = 0;
        return new Iterator(function () {
            if (i === size) {
                return iteratorDone();
            }
            var v = value;
            value += reverse ? -step : step;
            return iteratorValue(type, reverse ? size - ++i : i++, v);
        });
    };
    Range.prototype.equals = function equals(other) {
        return other instanceof Range
            ? this._start === other._start &&
                this._end === other._end &&
                this._step === other._step
            : deepEqual(this, other);
    };
    return Range;
}(IndexedSeq));
var EMPTY_RANGE;
function getIn(collection, searchKeyPath, notSetValue) {
    var keyPath = coerceKeyPath(searchKeyPath);
    var i = 0;
    while (i !== keyPath.length) {
        collection = get(collection, keyPath[i++], NOT_SET);
        if (collection === NOT_SET) {
            return notSetValue;
        }
    }
    return collection;
}
function getIn$1(searchKeyPath, notSetValue) {
    return getIn(this, searchKeyPath, notSetValue);
}
function hasIn(collection, keyPath) {
    return getIn(collection, keyPath, NOT_SET) !== NOT_SET;
}
function hasIn$1(searchKeyPath) {
    return hasIn(this, searchKeyPath);
}
function toObject() {
    assertNotInfinite(this.size);
    var object = {};
    this.__iterate(function (v, k) {
        object[k] = v;
    });
    return object;
}
// Note: all of these methods are deprecated.
Collection.isIterable = isCollection;
Collection.isKeyed = isKeyed;
Collection.isIndexed = isIndexed;
Collection.isAssociative = isAssociative;
Collection.isOrdered = isOrdered;
Collection.Iterator = Iterator;
mixin(Collection, {
    // ### Conversion to other types
    toArray: function toArray() {
        assertNotInfinite(this.size);
        var array = new Array(this.size || 0);
        var useTuples = isKeyed(this);
        var i = 0;
        this.__iterate(function (v, k) {
            // Keyed collections produce an array of tuples.
            array[i++] = useTuples ? [k, v] : v;
        });
        return array;
    },
    toIndexedSeq: function toIndexedSeq() {
        return new ToIndexedSequence(this);
    },
    toJS: function toJS$1() {
        return toJS(this);
    },
    toKeyedSeq: function toKeyedSeq() {
        return new ToKeyedSequence(this, true);
    },
    toMap: function toMap() {
        // Use Late Binding here to solve the circular dependency.
        return Map$1(this.toKeyedSeq());
    },
    toObject: toObject,
    toOrderedMap: function toOrderedMap() {
        // Use Late Binding here to solve the circular dependency.
        return OrderedMap(this.toKeyedSeq());
    },
    toOrderedSet: function toOrderedSet() {
        // Use Late Binding here to solve the circular dependency.
        return OrderedSet(isKeyed(this) ? this.valueSeq() : this);
    },
    toSet: function toSet() {
        // Use Late Binding here to solve the circular dependency.
        return Set$1(isKeyed(this) ? this.valueSeq() : this);
    },
    toSetSeq: function toSetSeq() {
        return new ToSetSequence(this);
    },
    toSeq: function toSeq() {
        return isIndexed(this)
            ? this.toIndexedSeq()
            : isKeyed(this)
                ? this.toKeyedSeq()
                : this.toSetSeq();
    },
    toStack: function toStack() {
        // Use Late Binding here to solve the circular dependency.
        return Stack(isKeyed(this) ? this.valueSeq() : this);
    },
    toList: function toList() {
        // Use Late Binding here to solve the circular dependency.
        return List(isKeyed(this) ? this.valueSeq() : this);
    },
    // ### Common JavaScript methods and properties
    toString: function toString() {
        return '[Collection]';
    },
    __toString: function __toString(head, tail) {
        if (this.size === 0) {
            return head + tail;
        }
        return (head +
            ' ' +
            this.toSeq()
                .map(this.__toStringMapper)
                .join(', ') +
            ' ' +
            tail);
    },
    // ### ES6 Collection methods (ES6 Array and Map)
    concat: function concat() {
        var values = [], len = arguments.length;
        while (len--)
            values[len] = arguments[len];
        return reify(this, concatFactory(this, values));
    },
    includes: function includes(searchValue) {
        return this.some(function (value) { return is(value, searchValue); });
    },
    entries: function entries() {
        return this.__iterator(ITERATE_ENTRIES);
    },
    every: function every(predicate, context) {
        assertNotInfinite(this.size);
        var returnValue = true;
        this.__iterate(function (v, k, c) {
            if (!predicate.call(context, v, k, c)) {
                returnValue = false;
                return false;
            }
        });
        return returnValue;
    },
    filter: function filter(predicate, context) {
        return reify(this, filterFactory(this, predicate, context, true));
    },
    find: function find(predicate, context, notSetValue) {
        var entry = this.findEntry(predicate, context);
        return entry ? entry[1] : notSetValue;
    },
    forEach: function forEach(sideEffect, context) {
        assertNotInfinite(this.size);
        return this.__iterate(context ? sideEffect.bind(context) : sideEffect);
    },
    join: function join(separator) {
        assertNotInfinite(this.size);
        separator = separator !== undefined ? '' + separator : ',';
        var joined = '';
        var isFirst = true;
        this.__iterate(function (v) {
            isFirst ? (isFirst = false) : (joined += separator);
            joined += v !== null && v !== undefined ? v.toString() : '';
        });
        return joined;
    },
    keys: function keys() {
        return this.__iterator(ITERATE_KEYS);
    },
    map: function map(mapper, context) {
        return reify(this, mapFactory(this, mapper, context));
    },
    reduce: function reduce$1(reducer, initialReduction, context) {
        return reduce(this, reducer, initialReduction, context, arguments.length < 2, false);
    },
    reduceRight: function reduceRight(reducer, initialReduction, context) {
        return reduce(this, reducer, initialReduction, context, arguments.length < 2, true);
    },
    reverse: function reverse() {
        return reify(this, reverseFactory(this, true));
    },
    slice: function slice(begin, end) {
        return reify(this, sliceFactory(this, begin, end, true));
    },
    some: function some(predicate, context) {
        return !this.every(not(predicate), context);
    },
    sort: function sort(comparator) {
        return reify(this, sortFactory(this, comparator));
    },
    values: function values() {
        return this.__iterator(ITERATE_VALUES);
    },
    // ### More sequential methods
    butLast: function butLast() {
        return this.slice(0, -1);
    },
    isEmpty: function isEmpty() {
        return this.size !== undefined ? this.size === 0 : !this.some(function () { return true; });
    },
    count: function count(predicate, context) {
        return ensureSize(predicate ? this.toSeq().filter(predicate, context) : this);
    },
    countBy: function countBy(grouper, context) {
        return countByFactory(this, grouper, context);
    },
    equals: function equals(other) {
        return deepEqual(this, other);
    },
    entrySeq: function entrySeq() {
        var collection = this;
        if (collection._cache) {
            // We cache as an entries array, so we can just return the cache!
            return new ArraySeq(collection._cache);
        }
        var entriesSequence = collection
            .toSeq()
            .map(entryMapper)
            .toIndexedSeq();
        entriesSequence.fromEntrySeq = function () { return collection.toSeq(); };
        return entriesSequence;
    },
    filterNot: function filterNot(predicate, context) {
        return this.filter(not(predicate), context);
    },
    findEntry: function findEntry(predicate, context, notSetValue) {
        var found = notSetValue;
        this.__iterate(function (v, k, c) {
            if (predicate.call(context, v, k, c)) {
                found = [k, v];
                return false;
            }
        });
        return found;
    },
    findKey: function findKey(predicate, context) {
        var entry = this.findEntry(predicate, context);
        return entry && entry[0];
    },
    findLast: function findLast(predicate, context, notSetValue) {
        return this.toKeyedSeq()
            .reverse()
            .find(predicate, context, notSetValue);
    },
    findLastEntry: function findLastEntry(predicate, context, notSetValue) {
        return this.toKeyedSeq()
            .reverse()
            .findEntry(predicate, context, notSetValue);
    },
    findLastKey: function findLastKey(predicate, context) {
        return this.toKeyedSeq()
            .reverse()
            .findKey(predicate, context);
    },
    first: function first(notSetValue) {
        return this.find(returnTrue, null, notSetValue);
    },
    flatMap: function flatMap(mapper, context) {
        return reify(this, flatMapFactory(this, mapper, context));
    },
    flatten: function flatten(depth) {
        return reify(this, flattenFactory(this, depth, true));
    },
    fromEntrySeq: function fromEntrySeq() {
        return new FromEntriesSequence(this);
    },
    get: function get(searchKey, notSetValue) {
        return this.find(function (_, key) { return is(key, searchKey); }, undefined, notSetValue);
    },
    getIn: getIn$1,
    groupBy: function groupBy(grouper, context) {
        return groupByFactory(this, grouper, context);
    },
    has: function has(searchKey) {
        return this.get(searchKey, NOT_SET) !== NOT_SET;
    },
    hasIn: hasIn$1,
    isSubset: function isSubset(iter) {
        iter = typeof iter.includes === 'function' ? iter : Collection(iter);
        return this.every(function (value) { return iter.includes(value); });
    },
    isSuperset: function isSuperset(iter) {
        iter = typeof iter.isSubset === 'function' ? iter : Collection(iter);
        return iter.isSubset(this);
    },
    keyOf: function keyOf(searchValue) {
        return this.findKey(function (value) { return is(value, searchValue); });
    },
    keySeq: function keySeq() {
        return this.toSeq()
            .map(keyMapper)
            .toIndexedSeq();
    },
    last: function last(notSetValue) {
        return this.toSeq()
            .reverse()
            .first(notSetValue);
    },
    lastKeyOf: function lastKeyOf(searchValue) {
        return this.toKeyedSeq()
            .reverse()
            .keyOf(searchValue);
    },
    max: function max(comparator) {
        return maxFactory(this, comparator);
    },
    maxBy: function maxBy(mapper, comparator) {
        return maxFactory(this, comparator, mapper);
    },
    min: function min(comparator) {
        return maxFactory(this, comparator ? neg(comparator) : defaultNegComparator);
    },
    minBy: function minBy(mapper, comparator) {
        return maxFactory(this, comparator ? neg(comparator) : defaultNegComparator, mapper);
    },
    rest: function rest() {
        return this.slice(1);
    },
    skip: function skip(amount) {
        return amount === 0 ? this : this.slice(Math.max(0, amount));
    },
    skipLast: function skipLast(amount) {
        return amount === 0 ? this : this.slice(0, -Math.max(0, amount));
    },
    skipWhile: function skipWhile(predicate, context) {
        return reify(this, skipWhileFactory(this, predicate, context, true));
    },
    skipUntil: function skipUntil(predicate, context) {
        return this.skipWhile(not(predicate), context);
    },
    sortBy: function sortBy(mapper, comparator) {
        return reify(this, sortFactory(this, comparator, mapper));
    },
    take: function take(amount) {
        return this.slice(0, Math.max(0, amount));
    },
    takeLast: function takeLast(amount) {
        return this.slice(-Math.max(0, amount));
    },
    takeWhile: function takeWhile(predicate, context) {
        return reify(this, takeWhileFactory(this, predicate, context));
    },
    takeUntil: function takeUntil(predicate, context) {
        return this.takeWhile(not(predicate), context);
    },
    update: function update(fn) {
        return fn(this);
    },
    valueSeq: function valueSeq() {
        return this.toIndexedSeq();
    },
    // ### Hashable Object
    hashCode: function hashCode() {
        return this.__hash || (this.__hash = hashCollection(this));
    },
});
var CollectionPrototype = Collection.prototype;
CollectionPrototype[IS_COLLECTION_SYMBOL] = true;
CollectionPrototype[ITERATOR_SYMBOL] = CollectionPrototype.values;
CollectionPrototype.toJSON = CollectionPrototype.toArray;
CollectionPrototype.__toStringMapper = quoteString;
CollectionPrototype.inspect = CollectionPrototype.toSource = function () {
    return this.toString();
};
CollectionPrototype.chain = CollectionPrototype.flatMap;
CollectionPrototype.contains = CollectionPrototype.includes;
mixin(KeyedCollection, {
    // ### More sequential methods
    flip: function flip() {
        return reify(this, flipFactory(this));
    },
    mapEntries: function mapEntries(mapper, context) {
        var this$1 = this;
        var iterations = 0;
        return reify(this, this.toSeq()
            .map(function (v, k) { return mapper.call(context, [k, v], iterations++, this$1); })
            .fromEntrySeq());
    },
    mapKeys: function mapKeys(mapper, context) {
        var this$1 = this;
        return reify(this, this.toSeq()
            .flip()
            .map(function (k, v) { return mapper.call(context, k, v, this$1); })
            .flip());
    },
});
var KeyedCollectionPrototype = KeyedCollection.prototype;
KeyedCollectionPrototype[IS_KEYED_SYMBOL] = true;
KeyedCollectionPrototype[ITERATOR_SYMBOL] = CollectionPrototype.entries;
KeyedCollectionPrototype.toJSON = toObject;
KeyedCollectionPrototype.__toStringMapper = function (v, k) { return quoteString(k) + ': ' + quoteString(v); };
mixin(IndexedCollection, {
    // ### Conversion to other types
    toKeyedSeq: function toKeyedSeq() {
        return new ToKeyedSequence(this, false);
    },
    // ### ES6 Collection methods (ES6 Array and Map)
    filter: function filter(predicate, context) {
        return reify(this, filterFactory(this, predicate, context, false));
    },
    findIndex: function findIndex(predicate, context) {
        var entry = this.findEntry(predicate, context);
        return entry ? entry[0] : -1;
    },
    indexOf: function indexOf(searchValue) {
        var key = this.keyOf(searchValue);
        return key === undefined ? -1 : key;
    },
    lastIndexOf: function lastIndexOf(searchValue) {
        var key = this.lastKeyOf(searchValue);
        return key === undefined ? -1 : key;
    },
    reverse: function reverse() {
        return reify(this, reverseFactory(this, false));
    },
    slice: function slice(begin, end) {
        return reify(this, sliceFactory(this, begin, end, false));
    },
    splice: function splice(index, removeNum /*, ...values*/) {
        var numArgs = arguments.length;
        removeNum = Math.max(removeNum || 0, 0);
        if (numArgs === 0 || (numArgs === 2 && !removeNum)) {
            return this;
        }
        // If index is negative, it should resolve relative to the size of the
        // collection. However size may be expensive to compute if not cached, so
        // only call count() if the number is in fact negative.
        index = resolveBegin(index, index < 0 ? this.count() : this.size);
        var spliced = this.slice(0, index);
        return reify(this, numArgs === 1
            ? spliced
            : spliced.concat(arrCopy(arguments, 2), this.slice(index + removeNum)));
    },
    // ### More collection methods
    findLastIndex: function findLastIndex(predicate, context) {
        var entry = this.findLastEntry(predicate, context);
        return entry ? entry[0] : -1;
    },
    first: function first(notSetValue) {
        return this.get(0, notSetValue);
    },
    flatten: function flatten(depth) {
        return reify(this, flattenFactory(this, depth, false));
    },
    get: function get(index, notSetValue) {
        index = wrapIndex(this, index);
        return index < 0 ||
            (this.size === Infinity || (this.size !== undefined && index > this.size))
            ? notSetValue
            : this.find(function (_, key) { return key === index; }, undefined, notSetValue);
    },
    has: function has(index) {
        index = wrapIndex(this, index);
        return (index >= 0 &&
            (this.size !== undefined
                ? this.size === Infinity || index < this.size
                : this.indexOf(index) !== -1));
    },
    interpose: function interpose(separator) {
        return reify(this, interposeFactory(this, separator));
    },
    interleave: function interleave( /*...collections*/) {
        var collections = [this].concat(arrCopy(arguments));
        var zipped = zipWithFactory(this.toSeq(), IndexedSeq.of, collections);
        var interleaved = zipped.flatten(true);
        if (zipped.size) {
            interleaved.size = zipped.size * collections.length;
        }
        return reify(this, interleaved);
    },
    keySeq: function keySeq() {
        return Range(0, this.size);
    },
    last: function last(notSetValue) {
        return this.get(-1, notSetValue);
    },
    skipWhile: function skipWhile(predicate, context) {
        return reify(this, skipWhileFactory(this, predicate, context, false));
    },
    zip: function zip( /*, ...collections */) {
        var collections = [this].concat(arrCopy(arguments));
        return reify(this, zipWithFactory(this, defaultZipper, collections));
    },
    zipAll: function zipAll( /*, ...collections */) {
        var collections = [this].concat(arrCopy(arguments));
        return reify(this, zipWithFactory(this, defaultZipper, collections, true));
    },
    zipWith: function zipWith(zipper /*, ...collections */) {
        var collections = arrCopy(arguments);
        collections[0] = this;
        return reify(this, zipWithFactory(this, zipper, collections));
    },
});
var IndexedCollectionPrototype = IndexedCollection.prototype;
IndexedCollectionPrototype[IS_INDEXED_SYMBOL] = true;
IndexedCollectionPrototype[IS_ORDERED_SYMBOL] = true;
mixin(SetCollection, {
    // ### ES6 Collection methods (ES6 Array and Map)
    get: function get(value, notSetValue) {
        return this.has(value) ? value : notSetValue;
    },
    includes: function includes(value) {
        return this.has(value);
    },
    // ### More sequential methods
    keySeq: function keySeq() {
        return this.valueSeq();
    },
});
SetCollection.prototype.has = CollectionPrototype.includes;
SetCollection.prototype.contains = SetCollection.prototype.includes;
// Mixin subclasses
mixin(KeyedSeq, KeyedCollection.prototype);
mixin(IndexedSeq, IndexedCollection.prototype);
mixin(SetSeq, SetCollection.prototype);
// #pragma Helper functions
function reduce(collection, reducer, reduction, context, useFirst, reverse) {
    assertNotInfinite(collection.size);
    collection.__iterate(function (v, k, c) {
        if (useFirst) {
            useFirst = false;
            reduction = v;
        }
        else {
            reduction = reducer.call(context, reduction, v, k, c);
        }
    }, reverse);
    return reduction;
}
function keyMapper(v, k) {
    return k;
}
function entryMapper(v, k) {
    return [k, v];
}
function not(predicate) {
    return function () {
        return !predicate.apply(this, arguments);
    };
}
function neg(predicate) {
    return function () {
        return -predicate.apply(this, arguments);
    };
}
function defaultZipper() {
    return arrCopy(arguments);
}
function defaultNegComparator(a, b) {
    return a < b ? 1 : a > b ? -1 : 0;
}
function hashCollection(collection) {
    if (collection.size === Infinity) {
        return 0;
    }
    var ordered = isOrdered(collection);
    var keyed = isKeyed(collection);
    var h = ordered ? 1 : 0;
    var size = collection.__iterate(keyed
        ? ordered
            ? function (v, k) {
                h = (31 * h + hashMerge(hash(v), hash(k))) | 0;
            }
            : function (v, k) {
                h = (h + hashMerge(hash(v), hash(k))) | 0;
            }
        : ordered
            ? function (v) {
                h = (31 * h + hash(v)) | 0;
            }
            : function (v) {
                h = (h + hash(v)) | 0;
            });
    return murmurHashOfSize(size, h);
}
function murmurHashOfSize(size, h) {
    h = imul(h, 0xcc9e2d51);
    h = imul((h << 15) | (h >>> -15), 0x1b873593);
    h = imul((h << 13) | (h >>> -13), 5);
    h = ((h + 0xe6546b64) | 0) ^ size;
    h = imul(h ^ (h >>> 16), 0x85ebca6b);
    h = imul(h ^ (h >>> 13), 0xc2b2ae35);
    h = smi(h ^ (h >>> 16));
    return h;
}
function hashMerge(a, b) {
    return (a ^ (b + 0x9e3779b9 + (a << 6) + (a >> 2))) | 0; // int
}
var OrderedSet = /*@__PURE__*/ (function (Set$$1) {
    function OrderedSet(value) {
        return value === null || value === undefined
            ? emptyOrderedSet()
            : isOrderedSet(value)
                ? value
                : emptyOrderedSet().withMutations(function (set) {
                    var iter = SetCollection(value);
                    assertNotInfinite(iter.size);
                    iter.forEach(function (v) { return set.add(v); });
                });
    }
    if (Set$$1)
        OrderedSet.__proto__ = Set$$1;
    OrderedSet.prototype = Object.create(Set$$1 && Set$$1.prototype);
    OrderedSet.prototype.constructor = OrderedSet;
    OrderedSet.of = function of( /*...values*/) {
        return this(arguments);
    };
    OrderedSet.fromKeys = function fromKeys(value) {
        return this(KeyedCollection(value).keySeq());
    };
    OrderedSet.prototype.toString = function toString() {
        return this.__toString('OrderedSet {', '}');
    };
    return OrderedSet;
}(Set$1));
OrderedSet.isOrderedSet = isOrderedSet;
var OrderedSetPrototype = OrderedSet.prototype;
OrderedSetPrototype[IS_ORDERED_SYMBOL] = true;
OrderedSetPrototype.zip = IndexedCollectionPrototype.zip;
OrderedSetPrototype.zipWith = IndexedCollectionPrototype.zipWith;
OrderedSetPrototype.__empty = emptyOrderedSet;
OrderedSetPrototype.__make = makeOrderedSet;
function makeOrderedSet(map, ownerID) {
    var set = Object.create(OrderedSetPrototype);
    set.size = map ? map.size : 0;
    set._map = map;
    set.__ownerID = ownerID;
    return set;
}
var EMPTY_ORDERED_SET;
function emptyOrderedSet() {
    return (EMPTY_ORDERED_SET || (EMPTY_ORDERED_SET = makeOrderedSet(emptyOrderedMap())));
}
var Record = function Record(defaultValues, name) {
    var hasInitialized;
    var RecordType = function Record(values) {
        var this$1 = this;
        if (values instanceof RecordType) {
            return values;
        }
        if (!(this instanceof RecordType)) {
            return new RecordType(values);
        }
        if (!hasInitialized) {
            hasInitialized = true;
            var keys = Object.keys(defaultValues);
            var indices = (RecordTypePrototype._indices = {});
            // Deprecated: left to attempt not to break any external code which
            // relies on a ._name property existing on record instances.
            // Use Record.getDescriptiveName() instead
            RecordTypePrototype._name = name;
            RecordTypePrototype._keys = keys;
            RecordTypePrototype._defaultValues = defaultValues;
            for (var i = 0; i < keys.length; i++) {
                var propName = keys[i];
                indices[propName] = i;
                if (RecordTypePrototype[propName]) {
                    /* eslint-disable no-console */
                    typeof console === 'object' &&
                        console.warn &&
                        console.warn('Cannot define ' +
                            recordName(this) +
                            ' with property "' +
                            propName +
                            '" since that property name is part of the Record API.');
                    /* eslint-enable no-console */
                }
                else {
                    setProp(RecordTypePrototype, propName);
                }
            }
        }
        this.__ownerID = undefined;
        this._values = List().withMutations(function (l) {
            l.setSize(this$1._keys.length);
            KeyedCollection(values).forEach(function (v, k) {
                l.set(this$1._indices[k], v === this$1._defaultValues[k] ? undefined : v);
            });
        });
    };
    var RecordTypePrototype = (RecordType.prototype = Object.create(RecordPrototype));
    RecordTypePrototype.constructor = RecordType;
    if (name) {
        RecordType.displayName = name;
    }
    return RecordType;
};
Record.prototype.toString = function toString() {
    var str = recordName(this) + ' { ';
    var keys = this._keys;
    var k;
    for (var i = 0, l = keys.length; i !== l; i++) {
        k = keys[i];
        str += (i ? ', ' : '') + k + ': ' + quoteString(this.get(k));
    }
    return str + ' }';
};
Record.prototype.equals = function equals(other) {
    return (this === other ||
        (other &&
            this._keys === other._keys &&
            recordSeq(this).equals(recordSeq(other))));
};
Record.prototype.hashCode = function hashCode() {
    return recordSeq(this).hashCode();
};
// @pragma Access
Record.prototype.has = function has(k) {
    return this._indices.hasOwnProperty(k);
};
Record.prototype.get = function get(k, notSetValue) {
    if (!this.has(k)) {
        return notSetValue;
    }
    var index = this._indices[k];
    var value = this._values.get(index);
    return value === undefined ? this._defaultValues[k] : value;
};
// @pragma Modification
Record.prototype.set = function set(k, v) {
    if (this.has(k)) {
        var newValues = this._values.set(this._indices[k], v === this._defaultValues[k] ? undefined : v);
        if (newValues !== this._values && !this.__ownerID) {
            return makeRecord(this, newValues);
        }
    }
    return this;
};
Record.prototype.remove = function remove(k) {
    return this.set(k);
};
Record.prototype.clear = function clear() {
    var newValues = this._values.clear().setSize(this._keys.length);
    return this.__ownerID ? this : makeRecord(this, newValues);
};
Record.prototype.wasAltered = function wasAltered() {
    return this._values.wasAltered();
};
Record.prototype.toSeq = function toSeq() {
    return recordSeq(this);
};
Record.prototype.toJS = function toJS$1() {
    return toJS(this);
};
Record.prototype.entries = function entries() {
    return this.__iterator(ITERATE_ENTRIES);
};
Record.prototype.__iterator = function __iterator(type, reverse) {
    return recordSeq(this).__iterator(type, reverse);
};
Record.prototype.__iterate = function __iterate(fn, reverse) {
    return recordSeq(this).__iterate(fn, reverse);
};
Record.prototype.__ensureOwner = function __ensureOwner(ownerID) {
    if (ownerID === this.__ownerID) {
        return this;
    }
    var newValues = this._values.__ensureOwner(ownerID);
    if (!ownerID) {
        this.__ownerID = ownerID;
        this._values = newValues;
        return this;
    }
    return makeRecord(this, newValues, ownerID);
};
Record.isRecord = isRecord;
Record.getDescriptiveName = recordName;
var RecordPrototype = Record.prototype;
RecordPrototype[IS_RECORD_SYMBOL] = true;
RecordPrototype[DELETE] = RecordPrototype.remove;
RecordPrototype.deleteIn = RecordPrototype.removeIn = deleteIn;
RecordPrototype.getIn = getIn$1;
RecordPrototype.hasIn = CollectionPrototype.hasIn;
RecordPrototype.merge = merge;
RecordPrototype.mergeWith = mergeWith;
RecordPrototype.mergeIn = mergeIn;
RecordPrototype.mergeDeep = mergeDeep$1;
RecordPrototype.mergeDeepWith = mergeDeepWith$1;
RecordPrototype.mergeDeepIn = mergeDeepIn;
RecordPrototype.setIn = setIn$1;
RecordPrototype.update = update$1;
RecordPrototype.updateIn = updateIn$1;
RecordPrototype.withMutations = withMutations;
RecordPrototype.asMutable = asMutable;
RecordPrototype.asImmutable = asImmutable;
RecordPrototype[ITERATOR_SYMBOL] = RecordPrototype.entries;
RecordPrototype.toJSON = RecordPrototype.toObject =
    CollectionPrototype.toObject;
RecordPrototype.inspect = RecordPrototype.toSource = function () {
    return this.toString();
};
function makeRecord(likeRecord, values, ownerID) {
    var record = Object.create(Object.getPrototypeOf(likeRecord));
    record._values = values;
    record.__ownerID = ownerID;
    return record;
}
function recordName(record) {
    return record.constructor.displayName || record.constructor.name || 'Record';
}
function recordSeq(record) {
    return keyedSeqFromValue(record._keys.map(function (k) { return [k, record.get(k)]; }));
}
function setProp(prototype, name) {
    try {
        Object.defineProperty(prototype, name, {
            get: function () {
                return this.get(name);
            },
            set: function (value) {
                invariant(this.__ownerID, 'Cannot set on an immutable record.');
                this.set(name, value);
            },
        });
    }
    catch (error) {
        // Object.defineProperty failed. Probably IE8.
    }
}
/**
 * Returns a lazy Seq of `value` repeated `times` times. When `times` is
 * undefined, returns an infinite sequence of `value`.
 */
var Repeat = /*@__PURE__*/ (function (IndexedSeq$$1) {
    function Repeat(value, times) {
        if (!(this instanceof Repeat)) {
            return new Repeat(value, times);
        }
        this._value = value;
        this.size = times === undefined ? Infinity : Math.max(0, times);
        if (this.size === 0) {
            if (EMPTY_REPEAT) {
                return EMPTY_REPEAT;
            }
            EMPTY_REPEAT = this;
        }
    }
    if (IndexedSeq$$1)
        Repeat.__proto__ = IndexedSeq$$1;
    Repeat.prototype = Object.create(IndexedSeq$$1 && IndexedSeq$$1.prototype);
    Repeat.prototype.constructor = Repeat;
    Repeat.prototype.toString = function toString() {
        if (this.size === 0) {
            return 'Repeat []';
        }
        return 'Repeat [ ' + this._value + ' ' + this.size + ' times ]';
    };
    Repeat.prototype.get = function get(index, notSetValue) {
        return this.has(index) ? this._value : notSetValue;
    };
    Repeat.prototype.includes = function includes(searchValue) {
        return is(this._value, searchValue);
    };
    Repeat.prototype.slice = function slice(begin, end) {
        var size = this.size;
        return wholeSlice(begin, end, size)
            ? this
            : new Repeat(this._value, resolveEnd(end, size) - resolveBegin(begin, size));
    };
    Repeat.prototype.reverse = function reverse() {
        return this;
    };
    Repeat.prototype.indexOf = function indexOf(searchValue) {
        if (is(this._value, searchValue)) {
            return 0;
        }
        return -1;
    };
    Repeat.prototype.lastIndexOf = function lastIndexOf(searchValue) {
        if (is(this._value, searchValue)) {
            return this.size;
        }
        return -1;
    };
    Repeat.prototype.__iterate = function __iterate(fn, reverse) {
        var size = this.size;
        var i = 0;
        while (i !== size) {
            if (fn(this._value, reverse ? size - ++i : i++, this) === false) {
                break;
            }
        }
        return i;
    };
    Repeat.prototype.__iterator = function __iterator(type, reverse) {
        var this$1 = this;
        var size = this.size;
        var i = 0;
        return new Iterator(function () {
            return i === size
                ? iteratorDone()
                : iteratorValue(type, reverse ? size - ++i : i++, this$1._value);
        });
    };
    Repeat.prototype.equals = function equals(other) {
        return other instanceof Repeat
            ? is(this._value, other._value)
            : deepEqual(other);
    };
    return Repeat;
}(IndexedSeq));
var EMPTY_REPEAT;
function fromJS(value, converter) {
    return fromJSWith([], converter || defaultConverter, value, '', converter && converter.length > 2 ? [] : undefined, { '': value });
}
function fromJSWith(stack, converter, value, key, keyPath, parentValue) {
    var toSeq = Array.isArray(value)
        ? IndexedSeq
        : isPlainObj(value)
            ? KeyedSeq
            : null;
    if (toSeq) {
        if (~stack.indexOf(value)) {
            throw new TypeError('Cannot convert circular structure to Immutable');
        }
        stack.push(value);
        keyPath && key !== '' && keyPath.push(key);
        var converted = converter.call(parentValue, key, toSeq(value).map(function (v, k) { return fromJSWith(stack, converter, v, k, keyPath, value); }), keyPath && keyPath.slice());
        stack.pop();
        keyPath && keyPath.pop();
        return converted;
    }
    return value;
}
function defaultConverter(k, v) {
    return isKeyed(v) ? v.toMap() : v.toList();
}
var version = "4.0.0-rc.11";
var Immutable = {
    version: version,
    Collection: Collection,
    // Note: Iterable is deprecated
    Iterable: Collection,
    Seq: Seq,
    Map: Map$1,
    OrderedMap: OrderedMap,
    List: List,
    Stack: Stack,
    Set: Set$1,
    OrderedSet: OrderedSet,
    Record: Record,
    Range: Range,
    Repeat: Repeat,
    is: is,
    fromJS: fromJS,
    hash: hash,
    isImmutable: isImmutable,
    isCollection: isCollection,
    isKeyed: isKeyed,
    isIndexed: isIndexed,
    isAssociative: isAssociative,
    isOrdered: isOrdered,
    isValueObject: isValueObject,
    isSeq: isSeq,
    isList: isList,
    isMap: isMap,
    isOrderedMap: isOrderedMap,
    isStack: isStack,
    isSet: isSet,
    isOrderedSet: isOrderedSet,
    isRecord: isRecord,
    get: get,
    getIn: getIn,
    has: has,
    hasIn: hasIn,
    merge: merge$1,
    mergeDeep: mergeDeep,
    mergeWith: mergeWith$1,
    mergeDeepWith: mergeDeepWith,
    remove: remove,
    removeIn: removeIn,
    set: set,
    setIn: setIn,
    update: update,
    updateIn: updateIn,
};

var OptionTypes;
(function (OptionTypes) {
    OptionTypes[OptionTypes["IGNORED_LABELS"] = 0] = "IGNORED_LABELS";
    OptionTypes[OptionTypes["ACCESSED_NODES"] = 1] = "ACCESSED_NODES";
    OptionTypes[OptionTypes["ASSIGNED_NODES"] = 2] = "ASSIGNED_NODES";
    OptionTypes[OptionTypes["IGNORE_BREAK_STATEMENTS"] = 3] = "IGNORE_BREAK_STATEMENTS";
    OptionTypes[OptionTypes["IGNORE_RETURN_AWAIT_YIELD"] = 4] = "IGNORE_RETURN_AWAIT_YIELD";
    OptionTypes[OptionTypes["NODES_CALLED_AT_PATH_WITH_OPTIONS"] = 5] = "NODES_CALLED_AT_PATH_WITH_OPTIONS";
    OptionTypes[OptionTypes["REPLACED_VARIABLE_INITS"] = 6] = "REPLACED_VARIABLE_INITS";
    OptionTypes[OptionTypes["RETURN_EXPRESSIONS_ACCESSED_AT_PATH"] = 7] = "RETURN_EXPRESSIONS_ACCESSED_AT_PATH";
    OptionTypes[OptionTypes["RETURN_EXPRESSIONS_ASSIGNED_AT_PATH"] = 8] = "RETURN_EXPRESSIONS_ASSIGNED_AT_PATH";
    OptionTypes[OptionTypes["RETURN_EXPRESSIONS_CALLED_AT_PATH"] = 9] = "RETURN_EXPRESSIONS_CALLED_AT_PATH";
})(OptionTypes || (OptionTypes = {}));
const RESULT_KEY = {};
class ExecutionPathOptions {
    constructor(optionValues) {
        this.optionValues = optionValues;
    }
    static create() {
        return new this(Immutable.Map());
    }
    addAccessedNodeAtPath(path, node) {
        return this.setIn([OptionTypes.ACCESSED_NODES, node, ...path, RESULT_KEY], true);
    }
    addAccessedReturnExpressionAtPath(path, callExpression) {
        return this.setIn([OptionTypes.RETURN_EXPRESSIONS_ACCESSED_AT_PATH, callExpression, ...path, RESULT_KEY], true);
    }
    addAssignedNodeAtPath(path, node) {
        return this.setIn([OptionTypes.ASSIGNED_NODES, node, ...path, RESULT_KEY], true);
    }
    addAssignedReturnExpressionAtPath(path, callExpression) {
        return this.setIn([OptionTypes.RETURN_EXPRESSIONS_ASSIGNED_AT_PATH, callExpression, ...path, RESULT_KEY], true);
    }
    addCalledNodeAtPathWithOptions(path, node, callOptions) {
        return this.setIn([OptionTypes.NODES_CALLED_AT_PATH_WITH_OPTIONS, node, ...path, RESULT_KEY, callOptions], true);
    }
    addCalledReturnExpressionAtPath(path, callExpression) {
        return this.setIn([OptionTypes.RETURN_EXPRESSIONS_CALLED_AT_PATH, callExpression, ...path, RESULT_KEY], true);
    }
    getHasEffectsWhenCalledOptions() {
        return this.setIgnoreReturnAwaitYield()
            .setIgnoreBreakStatements(false)
            .setIgnoreNoLabels();
    }
    getReplacedVariableInit(variable) {
        return this.optionValues.getIn([OptionTypes.REPLACED_VARIABLE_INITS, variable]);
    }
    hasNodeBeenAccessedAtPath(path, node) {
        return this.optionValues.getIn([OptionTypes.ACCESSED_NODES, node, ...path, RESULT_KEY]);
    }
    hasNodeBeenAssignedAtPath(path, node) {
        return this.optionValues.getIn([OptionTypes.ASSIGNED_NODES, node, ...path, RESULT_KEY]);
    }
    hasNodeBeenCalledAtPathWithOptions(path, node, callOptions) {
        const previousCallOptions = this.optionValues.getIn([
            OptionTypes.NODES_CALLED_AT_PATH_WITH_OPTIONS,
            node,
            ...path,
            RESULT_KEY
        ]);
        return (previousCallOptions &&
            previousCallOptions.find((_, otherCallOptions) => otherCallOptions.equals(callOptions)));
    }
    hasReturnExpressionBeenAccessedAtPath(path, callExpression) {
        return this.optionValues.getIn([
            OptionTypes.RETURN_EXPRESSIONS_ACCESSED_AT_PATH,
            callExpression,
            ...path,
            RESULT_KEY
        ]);
    }
    hasReturnExpressionBeenAssignedAtPath(path, callExpression) {
        return this.optionValues.getIn([
            OptionTypes.RETURN_EXPRESSIONS_ASSIGNED_AT_PATH,
            callExpression,
            ...path,
            RESULT_KEY
        ]);
    }
    hasReturnExpressionBeenCalledAtPath(path, callExpression) {
        return this.optionValues.getIn([
            OptionTypes.RETURN_EXPRESSIONS_CALLED_AT_PATH,
            callExpression,
            ...path,
            RESULT_KEY
        ]);
    }
    ignoreBreakStatements() {
        return this.get(OptionTypes.IGNORE_BREAK_STATEMENTS);
    }
    ignoreLabel(labelName) {
        return this.optionValues.getIn([OptionTypes.IGNORED_LABELS, labelName]);
    }
    ignoreReturnAwaitYield() {
        return this.get(OptionTypes.IGNORE_RETURN_AWAIT_YIELD);
    }
    replaceVariableInit(variable, init) {
        return this.setIn([OptionTypes.REPLACED_VARIABLE_INITS, variable], init);
    }
    setIgnoreBreakStatements(value = true) {
        return this.set(OptionTypes.IGNORE_BREAK_STATEMENTS, value);
    }
    setIgnoreLabel(labelName) {
        return this.setIn([OptionTypes.IGNORED_LABELS, labelName], true);
    }
    setIgnoreNoLabels() {
        return this.remove(OptionTypes.IGNORED_LABELS);
    }
    setIgnoreReturnAwaitYield(value = true) {
        return this.set(OptionTypes.IGNORE_RETURN_AWAIT_YIELD, value);
    }
    get(option) {
        return this.optionValues.get(option);
    }
    remove(option) {
        return new ExecutionPathOptions(this.optionValues.remove(option));
    }
    set(option, value) {
        return new ExecutionPathOptions(this.optionValues.set(option, value));
    }
    setIn(optionPath, value) {
        return new ExecutionPathOptions(this.optionValues.setIn(optionPath, value));
    }
}

const keys = {
    Literal: [],
    Program: ['body']
};
function getAndCreateKeys(esTreeNode) {
    keys[esTreeNode.type] = Object.keys(esTreeNode).filter(key => typeof esTreeNode[key] === 'object');
    return keys[esTreeNode.type];
}

const INCLUDE_PARAMETERS = 'variables';
const NEW_EXECUTION_PATH = ExecutionPathOptions.create();
class NodeBase {
    constructor(esTreeNode, parent, parentScope) {
        this.included = false;
        this.keys = keys[esTreeNode.type] || getAndCreateKeys(esTreeNode);
        this.parent = parent;
        this.context = parent.context;
        this.createScope(parentScope);
        this.parseNode(esTreeNode);
        this.initialise();
        this.context.magicString.addSourcemapLocation(this.start);
        this.context.magicString.addSourcemapLocation(this.end);
    }
    /**
     * Override this to bind assignments to variables and do any initialisations that
     * require the scopes to be populated with variables.
     */
    bind() {
        for (const key of this.keys) {
            const value = this[key];
            if (value === null || key === 'annotations')
                continue;
            if (Array.isArray(value)) {
                for (const child of value) {
                    if (child !== null)
                        child.bind();
                }
            }
            else {
                value.bind();
            }
        }
    }
    /**
     * Override if this node should receive a different scope than the parent scope.
     */
    createScope(parentScope) {
        this.scope = parentScope;
    }
    declare(_kind, _init) {
        return [];
    }
    deoptimizePath(_path) { }
    getLiteralValueAtPath(_path, _recursionTracker, _origin) {
        return UNKNOWN_VALUE;
    }
    getReturnExpressionWhenCalledAtPath(_path, _recursionTracker, _origin) {
        return UNKNOWN_EXPRESSION;
    }
    hasEffects(options) {
        for (const key of this.keys) {
            const value = this[key];
            if (value === null || key === 'annotations')
                continue;
            if (Array.isArray(value)) {
                for (const child of value) {
                    if (child !== null && child.hasEffects(options))
                        return true;
                }
            }
            else if (value.hasEffects(options))
                return true;
        }
        return false;
    }
    hasEffectsWhenAccessedAtPath(path, _options) {
        return path.length > 0;
    }
    hasEffectsWhenAssignedAtPath(_path, _options) {
        return true;
    }
    hasEffectsWhenCalledAtPath(_path, _callOptions, _options) {
        return true;
    }
    include(includeChildrenRecursively) {
        this.included = true;
        for (const key of this.keys) {
            const value = this[key];
            if (value === null || key === 'annotations')
                continue;
            if (Array.isArray(value)) {
                for (const child of value) {
                    if (child !== null)
                        child.include(includeChildrenRecursively);
                }
            }
            else {
                value.include(includeChildrenRecursively);
            }
        }
    }
    includeCallArguments(args) {
        for (const arg of args) {
            arg.include(false);
        }
    }
    includeWithAllDeclaredVariables(includeChildrenRecursively) {
        this.include(includeChildrenRecursively);
    }
    /**
     * Override to perform special initialisation steps after the scope is initialised
     */
    initialise() { }
    insertSemicolon(code) {
        if (code.original[this.end - 1] !== ';') {
            code.appendLeft(this.end, ';');
        }
    }
    locate() {
        // useful for debugging
        const location = locate(this.context.code, this.start, { offsetLine: 1 });
        location.file = this.context.fileName;
        location.toString = () => JSON.stringify(location);
        return location;
    }
    parseNode(esTreeNode) {
        for (const key of Object.keys(esTreeNode)) {
            // That way, we can override this function to add custom initialisation and then call super.parseNode
            if (this.hasOwnProperty(key))
                continue;
            const value = esTreeNode[key];
            if (typeof value !== 'object' || value === null || key === 'annotations') {
                this[key] = value;
            }
            else if (Array.isArray(value)) {
                this[key] = [];
                for (const child of value) {
                    this[key].push(child === null
                        ? null
                        : new (this.context.nodeConstructors[child.type] ||
                            this.context.nodeConstructors.UnknownNode)(child, this, this.scope));
                }
            }
            else {
                this[key] = new (this.context.nodeConstructors[value.type] ||
                    this.context.nodeConstructors.UnknownNode)(value, this, this.scope);
            }
        }
    }
    render(code, options) {
        for (const key of this.keys) {
            const value = this[key];
            if (value === null || key === 'annotations')
                continue;
            if (Array.isArray(value)) {
                for (const child of value) {
                    if (child !== null)
                        child.render(code, options);
                }
            }
            else {
                value.render(code, options);
            }
        }
    }
    shouldBeIncluded() {
        return this.included || this.hasEffects(NEW_EXECUTION_PATH);
    }
    toString() {
        return this.context.code.slice(this.start, this.end);
    }
}

class ClassNode extends NodeBase {
    createScope(parentScope) {
        this.scope = new ChildScope(parentScope);
    }
    hasEffectsWhenAccessedAtPath(path, _options) {
        return path.length > 1;
    }
    hasEffectsWhenAssignedAtPath(path, _options) {
        return path.length > 1;
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        return (this.body.hasEffectsWhenCalledAtPath(path, callOptions, options) ||
            (this.superClass !== null &&
                this.superClass.hasEffectsWhenCalledAtPath(path, callOptions, options)));
    }
    initialise() {
        if (this.id !== null) {
            this.id.declare('class', this);
        }
    }
}

class ClassDeclaration extends ClassNode {
    initialise() {
        super.initialise();
        if (this.id !== null) {
            this.id.variable.isId = true;
        }
    }
    parseNode(esTreeNode) {
        if (esTreeNode.id !== null) {
            this.id = new this.context.nodeConstructors.Identifier(esTreeNode.id, this, this.scope
                .parent);
        }
        super.parseNode(esTreeNode);
    }
    render(code, options) {
        if (options.format === 'system' && this.id && this.id.variable.exportName) {
            code.appendLeft(this.end, ` exports('${this.id.variable.exportName}', ${this.id.variable.getName()});`);
        }
        super.render(code, options);
    }
}

class ArgumentsVariable extends LocalVariable {
    constructor(context) {
        super('arguments', null, UNKNOWN_EXPRESSION, context);
    }
    hasEffectsWhenAccessedAtPath(path) {
        return path.length > 1;
    }
    hasEffectsWhenAssignedAtPath() {
        return true;
    }
    hasEffectsWhenCalledAtPath() {
        return true;
    }
}

class ThisVariable extends LocalVariable {
    constructor(context) {
        super('this', null, null, context);
    }
    _getInit(options) {
        return options.getReplacedVariableInit(this) || UNKNOWN_EXPRESSION;
    }
    getLiteralValueAtPath() {
        return UNKNOWN_VALUE;
    }
    hasEffectsWhenAccessedAtPath(path, options) {
        return (this._getInit(options).hasEffectsWhenAccessedAtPath(path, options) ||
            super.hasEffectsWhenAccessedAtPath(path, options));
    }
    hasEffectsWhenAssignedAtPath(path, options) {
        return (this._getInit(options).hasEffectsWhenAssignedAtPath(path, options) ||
            super.hasEffectsWhenAssignedAtPath(path, options));
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        return (this._getInit(options).hasEffectsWhenCalledAtPath(path, callOptions, options) ||
            super.hasEffectsWhenCalledAtPath(path, callOptions, options));
    }
}

class ParameterScope extends ChildScope {
    constructor(parent, context) {
        super(parent);
        this.parameters = [];
        this.hasRest = false;
        this.context = context;
        this.hoistedBodyVarScope = new ChildScope(this);
    }
    /**
     * Adds a parameter to this scope. Parameters must be added in the correct
     * order, e.g. from left to right.
     */
    addParameterDeclaration(identifier) {
        const name = identifier.name;
        let variable = this.hoistedBodyVarScope.variables.get(name);
        if (variable) {
            variable.addDeclaration(identifier, null);
        }
        else {
            variable = new LocalVariable(name, identifier, UNKNOWN_EXPRESSION, this.context);
        }
        this.variables.set(name, variable);
        return variable;
    }
    addParameterVariables(parameters, hasRest) {
        this.parameters = parameters;
        for (const parameterList of parameters) {
            for (const parameter of parameterList) {
                parameter.alwaysRendered = true;
            }
        }
        this.hasRest = hasRest;
    }
    includeCallArguments(args) {
        let calledFromTryStatement = false;
        let argIncluded = false;
        const restParam = this.hasRest && this.parameters[this.parameters.length - 1];
        for (let index = args.length - 1; index >= 0; index--) {
            const paramVars = this.parameters[index] || restParam;
            const arg = args[index];
            if (paramVars) {
                calledFromTryStatement = false;
                for (const variable of paramVars) {
                    if (variable.included) {
                        argIncluded = true;
                    }
                    if (variable.calledFromTryStatement) {
                        calledFromTryStatement = true;
                    }
                }
            }
            if (!argIncluded && arg.shouldBeIncluded()) {
                argIncluded = true;
            }
            if (argIncluded) {
                arg.include(calledFromTryStatement);
            }
        }
    }
}

class ReturnValueScope extends ParameterScope {
    constructor() {
        super(...arguments);
        this.returnExpression = null;
        this.returnExpressions = [];
    }
    addReturnExpression(expression) {
        this.returnExpressions.push(expression);
    }
    getReturnExpression() {
        if (this.returnExpression === null)
            this.updateReturnExpression();
        return this.returnExpression;
    }
    updateReturnExpression() {
        if (this.returnExpressions.length === 1) {
            this.returnExpression = this.returnExpressions[0];
        }
        else {
            this.returnExpression = UNKNOWN_EXPRESSION;
            for (const expression of this.returnExpressions) {
                expression.deoptimizePath(UNKNOWN_PATH);
            }
        }
    }
}

class FunctionScope extends ReturnValueScope {
    constructor(parent, context) {
        super(parent, context);
        this.variables.set('arguments', (this.argumentsVariable = new ArgumentsVariable(context)));
        this.variables.set('this', (this.thisVariable = new ThisVariable(context)));
    }
    findLexicalBoundary() {
        return this;
    }
    getOptionsWhenCalledWith({ withNew }, options) {
        return options.replaceVariableInit(this.thisVariable, withNew ? new UnknownObjectExpression() : UNKNOWN_EXPRESSION);
    }
    includeCallArguments(args) {
        super.includeCallArguments(args);
        if (this.argumentsVariable.included) {
            for (const arg of args) {
                if (!arg.included) {
                    arg.include(false);
                }
            }
        }
    }
}

function isReference(node, parent) {
    if (node.type === 'MemberExpression') {
        return !node.computed && isReference(node.object, node);
    }
    if (node.type === 'Identifier') {
        if (!parent)
            return true;
        switch (parent.type) {
            // disregard `bar` in `foo.bar`
            case 'MemberExpression': return parent.computed || node === parent.object;
            // disregard the `foo` in `class {foo(){}}` but keep it in `class {[foo](){}}`
            case 'MethodDefinition': return parent.computed;
            // disregard the `bar` in `{ bar: foo }`, but keep it in `{ [bar]: foo }`
            case 'Property': return parent.computed || node === parent.value;
            // disregard the `bar` in `export { foo as bar }` or
            // the foo in `import { foo as bar }`
            case 'ExportSpecifier':
            case 'ImportSpecifier': return node === parent.local;
            // disregard the `foo` in `foo: while (...) { ... break foo; ... continue foo;}`
            case 'LabeledStatement':
            case 'BreakStatement':
            case 'ContinueStatement': return false;
            default: return true;
        }
    }
    return false;
}

const ValueProperties = Symbol('Value Properties');
const PURE = { pure: true };
const IMPURE = { pure: false };
// We use shortened variables to reduce file size here
/* OBJECT */
const O = {
    // @ts-ignore
    __proto__: null,
    [ValueProperties]: IMPURE
};
/* PURE FUNCTION */
const PF = {
    // @ts-ignore
    __proto__: null,
    [ValueProperties]: PURE
};
/* CONSTRUCTOR */
const C = {
    // @ts-ignore
    __proto__: null,
    [ValueProperties]: IMPURE,
    prototype: O
};
/* PURE CONSTRUCTOR */
const PC = {
    // @ts-ignore
    __proto__: null,
    [ValueProperties]: PURE,
    prototype: O
};
const ARRAY_TYPE = {
    // @ts-ignore
    __proto__: null,
    [ValueProperties]: PURE,
    from: PF,
    of: PF,
    prototype: O
};
const INTL_MEMBER = {
    // @ts-ignore
    __proto__: null,
    [ValueProperties]: PURE,
    supportedLocalesOf: PC
};
const knownGlobals = {
    // Placeholders for global objects to avoid shape mutations
    global: O,
    globalThis: O,
    self: O,
    window: O,
    // Common globals
    // @ts-ignore
    __proto__: null,
    [ValueProperties]: IMPURE,
    Array: {
        // @ts-ignore
        __proto__: null,
        [ValueProperties]: IMPURE,
        from: PF,
        isArray: PF,
        of: PF,
        prototype: O
    },
    ArrayBuffer: {
        // @ts-ignore
        __proto__: null,
        [ValueProperties]: PURE,
        isView: PF,
        prototype: O
    },
    Atomics: O,
    BigInt: C,
    BigInt64Array: C,
    BigUint64Array: C,
    Boolean: PC,
    // @ts-ignore
    constructor: C,
    DataView: PC,
    Date: {
        // @ts-ignore
        __proto__: null,
        [ValueProperties]: PURE,
        now: PF,
        parse: PF,
        prototype: O,
        UTC: PF
    },
    decodeURI: PF,
    decodeURIComponent: PF,
    encodeURI: PF,
    encodeURIComponent: PF,
    Error: PC,
    escape: PF,
    eval: O,
    EvalError: PC,
    Float32Array: ARRAY_TYPE,
    Float64Array: ARRAY_TYPE,
    Function: C,
    // @ts-ignore
    hasOwnProperty: O,
    Infinity: O,
    Int16Array: ARRAY_TYPE,
    Int32Array: ARRAY_TYPE,
    Int8Array: ARRAY_TYPE,
    isFinite: PF,
    isNaN: PF,
    // @ts-ignore
    isPrototypeOf: O,
    JSON: O,
    Map: PC,
    Math: {
        // @ts-ignore
        __proto__: null,
        [ValueProperties]: IMPURE,
        abs: PF,
        acos: PF,
        acosh: PF,
        asin: PF,
        asinh: PF,
        atan: PF,
        atan2: PF,
        atanh: PF,
        cbrt: PF,
        ceil: PF,
        clz32: PF,
        cos: PF,
        cosh: PF,
        exp: PF,
        expm1: PF,
        floor: PF,
        fround: PF,
        hypot: PF,
        imul: PF,
        log: PF,
        log10: PF,
        log1p: PF,
        log2: PF,
        max: PF,
        min: PF,
        pow: PF,
        random: PF,
        round: PF,
        sign: PF,
        sin: PF,
        sinh: PF,
        sqrt: PF,
        tan: PF,
        tanh: PF,
        trunc: PF
    },
    NaN: O,
    Number: {
        // @ts-ignore
        __proto__: null,
        [ValueProperties]: PURE,
        isFinite: PF,
        isInteger: PF,
        isNaN: PF,
        isSafeInteger: PF,
        parseFloat: PF,
        parseInt: PF,
        prototype: O
    },
    Object: {
        // @ts-ignore
        __proto__: null,
        [ValueProperties]: PURE,
        create: PF,
        getNotifier: PF,
        getOwn: PF,
        getOwnPropertyDescriptor: PF,
        getOwnPropertyNames: PF,
        getOwnPropertySymbols: PF,
        getPrototypeOf: PF,
        is: PF,
        isExtensible: PF,
        isFrozen: PF,
        isSealed: PF,
        keys: PF,
        prototype: O
    },
    parseFloat: PF,
    parseInt: PF,
    Promise: {
        // @ts-ignore
        __proto__: null,
        [ValueProperties]: IMPURE,
        all: PF,
        prototype: O,
        race: PF,
        resolve: PF
    },
    // @ts-ignore
    propertyIsEnumerable: O,
    Proxy: O,
    RangeError: PC,
    ReferenceError: PC,
    Reflect: O,
    RegExp: PC,
    Set: PC,
    SharedArrayBuffer: C,
    String: {
        // @ts-ignore
        __proto__: null,
        [ValueProperties]: PURE,
        fromCharCode: PF,
        fromCodePoint: PF,
        prototype: O,
        raw: PF
    },
    Symbol: {
        // @ts-ignore
        __proto__: null,
        [ValueProperties]: PURE,
        for: PF,
        keyFor: PF,
        prototype: O
    },
    SyntaxError: PC,
    // @ts-ignore
    toLocaleString: O,
    // @ts-ignore
    toString: O,
    TypeError: PC,
    Uint16Array: ARRAY_TYPE,
    Uint32Array: ARRAY_TYPE,
    Uint8Array: ARRAY_TYPE,
    Uint8ClampedArray: ARRAY_TYPE,
    // Technically, this is a global, but it needs special handling
    // undefined: ?,
    unescape: PF,
    URIError: PC,
    // @ts-ignore
    valueOf: O,
    WeakMap: PC,
    WeakSet: PC,
    // Additional globals shared by Node and Browser that are not strictly part of the language
    clearInterval: C,
    clearTimeout: C,
    console: O,
    Intl: {
        // @ts-ignore
        __proto__: null,
        [ValueProperties]: IMPURE,
        Collator: INTL_MEMBER,
        DateTimeFormat: INTL_MEMBER,
        ListFormat: INTL_MEMBER,
        NumberFormat: INTL_MEMBER,
        PluralRules: INTL_MEMBER,
        RelativeTimeFormat: INTL_MEMBER
    },
    setInterval: C,
    setTimeout: C,
    TextDecoder: C,
    TextEncoder: C,
    URL: C,
    URLSearchParams: C,
    // Browser specific globals
    AbortController: C,
    AbortSignal: C,
    addEventListener: O,
    alert: O,
    AnalyserNode: C,
    Animation: C,
    AnimationEvent: C,
    applicationCache: O,
    ApplicationCache: C,
    ApplicationCacheErrorEvent: C,
    atob: O,
    Attr: C,
    Audio: C,
    AudioBuffer: C,
    AudioBufferSourceNode: C,
    AudioContext: C,
    AudioDestinationNode: C,
    AudioListener: C,
    AudioNode: C,
    AudioParam: C,
    AudioProcessingEvent: C,
    AudioScheduledSourceNode: C,
    AudioWorkletNode: C,
    BarProp: C,
    BaseAudioContext: C,
    BatteryManager: C,
    BeforeUnloadEvent: C,
    BiquadFilterNode: C,
    Blob: C,
    BlobEvent: C,
    blur: O,
    BroadcastChannel: C,
    btoa: O,
    ByteLengthQueuingStrategy: C,
    Cache: C,
    caches: O,
    CacheStorage: C,
    cancelAnimationFrame: O,
    cancelIdleCallback: O,
    CanvasCaptureMediaStreamTrack: C,
    CanvasGradient: C,
    CanvasPattern: C,
    CanvasRenderingContext2D: C,
    ChannelMergerNode: C,
    ChannelSplitterNode: C,
    CharacterData: C,
    clientInformation: O,
    ClipboardEvent: C,
    close: O,
    closed: O,
    CloseEvent: C,
    Comment: C,
    CompositionEvent: C,
    confirm: O,
    ConstantSourceNode: C,
    ConvolverNode: C,
    CountQueuingStrategy: C,
    createImageBitmap: O,
    Credential: C,
    CredentialsContainer: C,
    crypto: O,
    Crypto: C,
    CryptoKey: C,
    CSS: C,
    CSSConditionRule: C,
    CSSFontFaceRule: C,
    CSSGroupingRule: C,
    CSSImportRule: C,
    CSSKeyframeRule: C,
    CSSKeyframesRule: C,
    CSSMediaRule: C,
    CSSNamespaceRule: C,
    CSSPageRule: C,
    CSSRule: C,
    CSSRuleList: C,
    CSSStyleDeclaration: C,
    CSSStyleRule: C,
    CSSStyleSheet: C,
    CSSSupportsRule: C,
    CustomElementRegistry: C,
    customElements: O,
    CustomEvent: C,
    DataTransfer: C,
    DataTransferItem: C,
    DataTransferItemList: C,
    defaultstatus: O,
    defaultStatus: O,
    DelayNode: C,
    DeviceMotionEvent: C,
    DeviceOrientationEvent: C,
    devicePixelRatio: O,
    dispatchEvent: O,
    document: O,
    Document: C,
    DocumentFragment: C,
    DocumentType: C,
    DOMError: C,
    DOMException: C,
    DOMImplementation: C,
    DOMMatrix: C,
    DOMMatrixReadOnly: C,
    DOMParser: C,
    DOMPoint: C,
    DOMPointReadOnly: C,
    DOMQuad: C,
    DOMRect: C,
    DOMRectReadOnly: C,
    DOMStringList: C,
    DOMStringMap: C,
    DOMTokenList: C,
    DragEvent: C,
    DynamicsCompressorNode: C,
    Element: C,
    ErrorEvent: C,
    Event: C,
    EventSource: C,
    EventTarget: C,
    external: O,
    fetch: O,
    File: C,
    FileList: C,
    FileReader: C,
    find: O,
    focus: O,
    FocusEvent: C,
    FontFace: C,
    FontFaceSetLoadEvent: C,
    FormData: C,
    frames: O,
    GainNode: C,
    Gamepad: C,
    GamepadButton: C,
    GamepadEvent: C,
    getComputedStyle: O,
    getSelection: O,
    HashChangeEvent: C,
    Headers: C,
    history: O,
    History: C,
    HTMLAllCollection: C,
    HTMLAnchorElement: C,
    HTMLAreaElement: C,
    HTMLAudioElement: C,
    HTMLBaseElement: C,
    HTMLBodyElement: C,
    HTMLBRElement: C,
    HTMLButtonElement: C,
    HTMLCanvasElement: C,
    HTMLCollection: C,
    HTMLContentElement: C,
    HTMLDataElement: C,
    HTMLDataListElement: C,
    HTMLDetailsElement: C,
    HTMLDialogElement: C,
    HTMLDirectoryElement: C,
    HTMLDivElement: C,
    HTMLDListElement: C,
    HTMLDocument: C,
    HTMLElement: C,
    HTMLEmbedElement: C,
    HTMLFieldSetElement: C,
    HTMLFontElement: C,
    HTMLFormControlsCollection: C,
    HTMLFormElement: C,
    HTMLFrameElement: C,
    HTMLFrameSetElement: C,
    HTMLHeadElement: C,
    HTMLHeadingElement: C,
    HTMLHRElement: C,
    HTMLHtmlElement: C,
    HTMLIFrameElement: C,
    HTMLImageElement: C,
    HTMLInputElement: C,
    HTMLLabelElement: C,
    HTMLLegendElement: C,
    HTMLLIElement: C,
    HTMLLinkElement: C,
    HTMLMapElement: C,
    HTMLMarqueeElement: C,
    HTMLMediaElement: C,
    HTMLMenuElement: C,
    HTMLMetaElement: C,
    HTMLMeterElement: C,
    HTMLModElement: C,
    HTMLObjectElement: C,
    HTMLOListElement: C,
    HTMLOptGroupElement: C,
    HTMLOptionElement: C,
    HTMLOptionsCollection: C,
    HTMLOutputElement: C,
    HTMLParagraphElement: C,
    HTMLParamElement: C,
    HTMLPictureElement: C,
    HTMLPreElement: C,
    HTMLProgressElement: C,
    HTMLQuoteElement: C,
    HTMLScriptElement: C,
    HTMLSelectElement: C,
    HTMLShadowElement: C,
    HTMLSlotElement: C,
    HTMLSourceElement: C,
    HTMLSpanElement: C,
    HTMLStyleElement: C,
    HTMLTableCaptionElement: C,
    HTMLTableCellElement: C,
    HTMLTableColElement: C,
    HTMLTableElement: C,
    HTMLTableRowElement: C,
    HTMLTableSectionElement: C,
    HTMLTemplateElement: C,
    HTMLTextAreaElement: C,
    HTMLTimeElement: C,
    HTMLTitleElement: C,
    HTMLTrackElement: C,
    HTMLUListElement: C,
    HTMLUnknownElement: C,
    HTMLVideoElement: C,
    IDBCursor: C,
    IDBCursorWithValue: C,
    IDBDatabase: C,
    IDBFactory: C,
    IDBIndex: C,
    IDBKeyRange: C,
    IDBObjectStore: C,
    IDBOpenDBRequest: C,
    IDBRequest: C,
    IDBTransaction: C,
    IDBVersionChangeEvent: C,
    IdleDeadline: C,
    IIRFilterNode: C,
    Image: C,
    ImageBitmap: C,
    ImageBitmapRenderingContext: C,
    ImageCapture: C,
    ImageData: C,
    indexedDB: O,
    innerHeight: O,
    innerWidth: O,
    InputEvent: C,
    IntersectionObserver: C,
    IntersectionObserverEntry: C,
    isSecureContext: O,
    KeyboardEvent: C,
    KeyframeEffect: C,
    length: O,
    localStorage: O,
    location: O,
    Location: C,
    locationbar: O,
    matchMedia: O,
    MediaDeviceInfo: C,
    MediaDevices: C,
    MediaElementAudioSourceNode: C,
    MediaEncryptedEvent: C,
    MediaError: C,
    MediaKeyMessageEvent: C,
    MediaKeySession: C,
    MediaKeyStatusMap: C,
    MediaKeySystemAccess: C,
    MediaList: C,
    MediaQueryList: C,
    MediaQueryListEvent: C,
    MediaRecorder: C,
    MediaSettingsRange: C,
    MediaSource: C,
    MediaStream: C,
    MediaStreamAudioDestinationNode: C,
    MediaStreamAudioSourceNode: C,
    MediaStreamEvent: C,
    MediaStreamTrack: C,
    MediaStreamTrackEvent: C,
    menubar: O,
    MessageChannel: C,
    MessageEvent: C,
    MessagePort: C,
    MIDIAccess: C,
    MIDIConnectionEvent: C,
    MIDIInput: C,
    MIDIInputMap: C,
    MIDIMessageEvent: C,
    MIDIOutput: C,
    MIDIOutputMap: C,
    MIDIPort: C,
    MimeType: C,
    MimeTypeArray: C,
    MouseEvent: C,
    moveBy: O,
    moveTo: O,
    MutationEvent: C,
    MutationObserver: C,
    MutationRecord: C,
    name: O,
    NamedNodeMap: C,
    NavigationPreloadManager: C,
    navigator: O,
    Navigator: C,
    NetworkInformation: C,
    Node: C,
    NodeFilter: O,
    NodeIterator: C,
    NodeList: C,
    Notification: C,
    OfflineAudioCompletionEvent: C,
    OfflineAudioContext: C,
    offscreenBuffering: O,
    OffscreenCanvas: C,
    open: O,
    openDatabase: O,
    Option: C,
    origin: O,
    OscillatorNode: C,
    outerHeight: O,
    outerWidth: O,
    PageTransitionEvent: C,
    pageXOffset: O,
    pageYOffset: O,
    PannerNode: C,
    parent: O,
    Path2D: C,
    PaymentAddress: C,
    PaymentRequest: C,
    PaymentRequestUpdateEvent: C,
    PaymentResponse: C,
    performance: O,
    Performance: C,
    PerformanceEntry: C,
    PerformanceLongTaskTiming: C,
    PerformanceMark: C,
    PerformanceMeasure: C,
    PerformanceNavigation: C,
    PerformanceNavigationTiming: C,
    PerformanceObserver: C,
    PerformanceObserverEntryList: C,
    PerformancePaintTiming: C,
    PerformanceResourceTiming: C,
    PerformanceTiming: C,
    PeriodicWave: C,
    Permissions: C,
    PermissionStatus: C,
    personalbar: O,
    PhotoCapabilities: C,
    Plugin: C,
    PluginArray: C,
    PointerEvent: C,
    PopStateEvent: C,
    postMessage: O,
    Presentation: C,
    PresentationAvailability: C,
    PresentationConnection: C,
    PresentationConnectionAvailableEvent: C,
    PresentationConnectionCloseEvent: C,
    PresentationConnectionList: C,
    PresentationReceiver: C,
    PresentationRequest: C,
    print: O,
    ProcessingInstruction: C,
    ProgressEvent: C,
    PromiseRejectionEvent: C,
    prompt: O,
    PushManager: C,
    PushSubscription: C,
    PushSubscriptionOptions: C,
    queueMicrotask: O,
    RadioNodeList: C,
    Range: C,
    ReadableStream: C,
    RemotePlayback: C,
    removeEventListener: O,
    Request: C,
    requestAnimationFrame: O,
    requestIdleCallback: O,
    resizeBy: O,
    ResizeObserver: C,
    ResizeObserverEntry: C,
    resizeTo: O,
    Response: C,
    RTCCertificate: C,
    RTCDataChannel: C,
    RTCDataChannelEvent: C,
    RTCDtlsTransport: C,
    RTCIceCandidate: C,
    RTCIceTransport: C,
    RTCPeerConnection: C,
    RTCPeerConnectionIceEvent: C,
    RTCRtpReceiver: C,
    RTCRtpSender: C,
    RTCSctpTransport: C,
    RTCSessionDescription: C,
    RTCStatsReport: C,
    RTCTrackEvent: C,
    screen: O,
    Screen: C,
    screenLeft: O,
    ScreenOrientation: C,
    screenTop: O,
    screenX: O,
    screenY: O,
    ScriptProcessorNode: C,
    scroll: O,
    scrollbars: O,
    scrollBy: O,
    scrollTo: O,
    scrollX: O,
    scrollY: O,
    SecurityPolicyViolationEvent: C,
    Selection: C,
    ServiceWorker: C,
    ServiceWorkerContainer: C,
    ServiceWorkerRegistration: C,
    sessionStorage: O,
    ShadowRoot: C,
    SharedWorker: C,
    SourceBuffer: C,
    SourceBufferList: C,
    speechSynthesis: O,
    SpeechSynthesisEvent: C,
    SpeechSynthesisUtterance: C,
    StaticRange: C,
    status: O,
    statusbar: O,
    StereoPannerNode: C,
    stop: O,
    Storage: C,
    StorageEvent: C,
    StorageManager: C,
    styleMedia: O,
    StyleSheet: C,
    StyleSheetList: C,
    SubtleCrypto: C,
    SVGAElement: C,
    SVGAngle: C,
    SVGAnimatedAngle: C,
    SVGAnimatedBoolean: C,
    SVGAnimatedEnumeration: C,
    SVGAnimatedInteger: C,
    SVGAnimatedLength: C,
    SVGAnimatedLengthList: C,
    SVGAnimatedNumber: C,
    SVGAnimatedNumberList: C,
    SVGAnimatedPreserveAspectRatio: C,
    SVGAnimatedRect: C,
    SVGAnimatedString: C,
    SVGAnimatedTransformList: C,
    SVGAnimateElement: C,
    SVGAnimateMotionElement: C,
    SVGAnimateTransformElement: C,
    SVGAnimationElement: C,
    SVGCircleElement: C,
    SVGClipPathElement: C,
    SVGComponentTransferFunctionElement: C,
    SVGDefsElement: C,
    SVGDescElement: C,
    SVGDiscardElement: C,
    SVGElement: C,
    SVGEllipseElement: C,
    SVGFEBlendElement: C,
    SVGFEColorMatrixElement: C,
    SVGFEComponentTransferElement: C,
    SVGFECompositeElement: C,
    SVGFEConvolveMatrixElement: C,
    SVGFEDiffuseLightingElement: C,
    SVGFEDisplacementMapElement: C,
    SVGFEDistantLightElement: C,
    SVGFEDropShadowElement: C,
    SVGFEFloodElement: C,
    SVGFEFuncAElement: C,
    SVGFEFuncBElement: C,
    SVGFEFuncGElement: C,
    SVGFEFuncRElement: C,
    SVGFEGaussianBlurElement: C,
    SVGFEImageElement: C,
    SVGFEMergeElement: C,
    SVGFEMergeNodeElement: C,
    SVGFEMorphologyElement: C,
    SVGFEOffsetElement: C,
    SVGFEPointLightElement: C,
    SVGFESpecularLightingElement: C,
    SVGFESpotLightElement: C,
    SVGFETileElement: C,
    SVGFETurbulenceElement: C,
    SVGFilterElement: C,
    SVGForeignObjectElement: C,
    SVGGElement: C,
    SVGGeometryElement: C,
    SVGGradientElement: C,
    SVGGraphicsElement: C,
    SVGImageElement: C,
    SVGLength: C,
    SVGLengthList: C,
    SVGLinearGradientElement: C,
    SVGLineElement: C,
    SVGMarkerElement: C,
    SVGMaskElement: C,
    SVGMatrix: C,
    SVGMetadataElement: C,
    SVGMPathElement: C,
    SVGNumber: C,
    SVGNumberList: C,
    SVGPathElement: C,
    SVGPatternElement: C,
    SVGPoint: C,
    SVGPointList: C,
    SVGPolygonElement: C,
    SVGPolylineElement: C,
    SVGPreserveAspectRatio: C,
    SVGRadialGradientElement: C,
    SVGRect: C,
    SVGRectElement: C,
    SVGScriptElement: C,
    SVGSetElement: C,
    SVGStopElement: C,
    SVGStringList: C,
    SVGStyleElement: C,
    SVGSVGElement: C,
    SVGSwitchElement: C,
    SVGSymbolElement: C,
    SVGTextContentElement: C,
    SVGTextElement: C,
    SVGTextPathElement: C,
    SVGTextPositioningElement: C,
    SVGTitleElement: C,
    SVGTransform: C,
    SVGTransformList: C,
    SVGTSpanElement: C,
    SVGUnitTypes: C,
    SVGUseElement: C,
    SVGViewElement: C,
    TaskAttributionTiming: C,
    Text: C,
    TextEvent: C,
    TextMetrics: C,
    TextTrack: C,
    TextTrackCue: C,
    TextTrackCueList: C,
    TextTrackList: C,
    TimeRanges: C,
    toolbar: O,
    top: O,
    Touch: C,
    TouchEvent: C,
    TouchList: C,
    TrackEvent: C,
    TransitionEvent: C,
    TreeWalker: C,
    UIEvent: C,
    ValidityState: C,
    visualViewport: O,
    VisualViewport: C,
    VTTCue: C,
    WaveShaperNode: C,
    WebAssembly: O,
    WebGL2RenderingContext: C,
    WebGLActiveInfo: C,
    WebGLBuffer: C,
    WebGLContextEvent: C,
    WebGLFramebuffer: C,
    WebGLProgram: C,
    WebGLQuery: C,
    WebGLRenderbuffer: C,
    WebGLRenderingContext: C,
    WebGLSampler: C,
    WebGLShader: C,
    WebGLShaderPrecisionFormat: C,
    WebGLSync: C,
    WebGLTexture: C,
    WebGLTransformFeedback: C,
    WebGLUniformLocation: C,
    WebGLVertexArrayObject: C,
    WebSocket: C,
    WheelEvent: C,
    Window: C,
    Worker: C,
    WritableStream: C,
    XMLDocument: C,
    XMLHttpRequest: C,
    XMLHttpRequestEventTarget: C,
    XMLHttpRequestUpload: C,
    XMLSerializer: C,
    XPathEvaluator: C,
    XPathExpression: C,
    XPathResult: C,
    XSLTProcessor: C
};
for (const global of ['window', 'global', 'self', 'globalThis']) {
    knownGlobals[global] = knownGlobals;
}
function getGlobalAtPath(path) {
    let currentGlobal = knownGlobals;
    for (const pathSegment of path) {
        if (typeof pathSegment !== 'string') {
            return null;
        }
        currentGlobal = currentGlobal[pathSegment];
        if (!currentGlobal) {
            return null;
        }
    }
    return currentGlobal[ValueProperties];
}
function isPureGlobal(path) {
    const globalAtPath = getGlobalAtPath(path);
    return globalAtPath !== null && globalAtPath.pure;
}
function isGlobalMember(path) {
    if (path.length === 1) {
        return path[0] === 'undefined' || getGlobalAtPath(path) !== null;
    }
    return getGlobalAtPath(path.slice(0, -1)) !== null;
}

class GlobalVariable extends Variable {
    hasEffectsWhenAccessedAtPath(path) {
        return !isGlobalMember([this.name, ...path]);
    }
    hasEffectsWhenCalledAtPath(path) {
        return !isPureGlobal([this.name, ...path]);
    }
}

class Identifier$1 extends NodeBase {
    constructor() {
        super(...arguments);
        this.variable = null;
        this.bound = false;
    }
    addExportedVariables(variables) {
        if (this.variable !== null && this.variable.exportName) {
            variables.push(this.variable);
        }
    }
    bind() {
        if (this.bound)
            return;
        this.bound = true;
        if (this.variable === null && isReference(this, this.parent)) {
            this.variable = this.scope.findVariable(this.name);
            this.variable.addReference(this);
        }
        if (this.variable !== null &&
            this.variable instanceof LocalVariable &&
            this.variable.additionalInitializers !== null) {
            this.variable.consolidateInitializers();
        }
    }
    declare(kind, init) {
        let variable;
        switch (kind) {
            case 'var':
            case 'function':
                variable = this.scope.addDeclaration(this, this.context, init, true);
                break;
            case 'let':
            case 'const':
            case 'class':
                variable = this.scope.addDeclaration(this, this.context, init, false);
                break;
            case 'parameter':
                variable = this.scope.addParameterDeclaration(this);
                break;
            /* istanbul ignore next */
            default:
                /* istanbul ignore next */
                throw new Error(`Internal Error: Unexpected identifier kind ${kind}.`);
        }
        return [(this.variable = variable)];
    }
    deoptimizePath(path) {
        if (!this.bound)
            this.bind();
        if (path.length === 0 && !this.scope.contains(this.name)) {
            this.disallowImportReassignment();
        }
        this.variable.deoptimizePath(path);
    }
    getLiteralValueAtPath(path, recursionTracker, origin) {
        if (!this.bound)
            this.bind();
        return this.variable.getLiteralValueAtPath(path, recursionTracker, origin);
    }
    getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin) {
        if (!this.bound)
            this.bind();
        return this.variable.getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin);
    }
    hasEffects() {
        return (this.context.unknownGlobalSideEffects &&
            this.variable instanceof GlobalVariable &&
            this.variable.hasEffectsWhenAccessedAtPath(EMPTY_PATH));
    }
    hasEffectsWhenAccessedAtPath(path, options) {
        return this.variable !== null && this.variable.hasEffectsWhenAccessedAtPath(path, options);
    }
    hasEffectsWhenAssignedAtPath(path, options) {
        return !this.variable || this.variable.hasEffectsWhenAssignedAtPath(path, options);
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        return !this.variable || this.variable.hasEffectsWhenCalledAtPath(path, callOptions, options);
    }
    include() {
        if (!this.included) {
            this.included = true;
            if (this.variable !== null) {
                this.context.includeVariable(this.variable);
            }
        }
    }
    includeCallArguments(args) {
        this.variable.includeCallArguments(args);
    }
    render(code, _options, { renderedParentType, isCalleeOfRenderedParent, isShorthandProperty } = BLANK) {
        if (this.variable) {
            const name = this.variable.getName();
            if (name !== this.name) {
                code.overwrite(this.start, this.end, name, {
                    contentOnly: true,
                    storeName: true
                });
                if (isShorthandProperty) {
                    code.prependRight(this.start, `${this.name}: `);
                }
            }
            // In strict mode, any variable named "eval" must be the actual "eval" function
            if (name === 'eval' &&
                renderedParentType === CallExpression &&
                isCalleeOfRenderedParent) {
                code.appendRight(this.start, '0, ');
            }
        }
    }
    disallowImportReassignment() {
        this.context.error({
            code: 'ILLEGAL_REASSIGNMENT',
            message: `Illegal reassignment to import '${this.name}'`
        }, this.start);
    }
}

class RestElement extends NodeBase {
    constructor() {
        super(...arguments);
        this.declarationInit = null;
    }
    addExportedVariables(variables) {
        this.argument.addExportedVariables(variables);
    }
    bind() {
        super.bind();
        if (this.declarationInit !== null) {
            this.declarationInit.deoptimizePath([UNKNOWN_KEY, UNKNOWN_KEY]);
        }
    }
    declare(kind, init) {
        this.declarationInit = init;
        return this.argument.declare(kind, UNKNOWN_EXPRESSION);
    }
    deoptimizePath(path) {
        path.length === 0 && this.argument.deoptimizePath(EMPTY_PATH);
    }
    hasEffectsWhenAssignedAtPath(path, options) {
        return path.length > 0 || this.argument.hasEffectsWhenAssignedAtPath(EMPTY_PATH, options);
    }
}

class FunctionNode extends NodeBase {
    constructor() {
        super(...arguments);
        this.isPrototypeDeoptimized = false;
    }
    createScope(parentScope) {
        this.scope = new FunctionScope(parentScope, this.context);
    }
    deoptimizePath(path) {
        if (path.length === 1) {
            if (path[0] === 'prototype') {
                this.isPrototypeDeoptimized = true;
            }
            else if (path[0] === UNKNOWN_KEY) {
                this.isPrototypeDeoptimized = true;
                // A reassignment of UNKNOWN_PATH is considered equivalent to having lost track
                // which means the return expression needs to be reassigned as well
                this.scope.getReturnExpression().deoptimizePath(UNKNOWN_PATH);
            }
        }
    }
    getReturnExpressionWhenCalledAtPath(path) {
        return path.length === 0 ? this.scope.getReturnExpression() : UNKNOWN_EXPRESSION;
    }
    hasEffects() {
        return this.id !== null && this.id.hasEffects();
    }
    hasEffectsWhenAccessedAtPath(path) {
        if (path.length <= 1) {
            return false;
        }
        return path.length > 2 || path[0] !== 'prototype' || this.isPrototypeDeoptimized;
    }
    hasEffectsWhenAssignedAtPath(path) {
        if (path.length <= 1) {
            return false;
        }
        return path.length > 2 || path[0] !== 'prototype' || this.isPrototypeDeoptimized;
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        if (path.length > 0) {
            return true;
        }
        const innerOptions = this.scope.getOptionsWhenCalledWith(callOptions, options);
        for (const param of this.params) {
            if (param.hasEffects(innerOptions))
                return true;
        }
        return this.body.hasEffects(innerOptions);
    }
    include(includeChildrenRecursively) {
        this.included = true;
        this.body.include(includeChildrenRecursively);
        if (this.id) {
            this.id.include();
        }
        const hasArguments = this.scope.argumentsVariable.included;
        for (const param of this.params) {
            if (!(param instanceof Identifier$1) || hasArguments) {
                param.include(includeChildrenRecursively);
            }
        }
    }
    includeCallArguments(args) {
        this.scope.includeCallArguments(args);
    }
    initialise() {
        if (this.id !== null) {
            this.id.declare('function', this);
        }
        this.scope.addParameterVariables(this.params.map(param => param.declare('parameter', UNKNOWN_EXPRESSION)), this.params[this.params.length - 1] instanceof RestElement);
        this.body.addImplicitReturnExpressionToScope();
    }
    parseNode(esTreeNode) {
        this.body = new this.context.nodeConstructors.BlockStatement(esTreeNode.body, this, this.scope.hoistedBodyVarScope);
        super.parseNode(esTreeNode);
    }
}
FunctionNode.prototype.preventChildBlockScope = true;

class FunctionDeclaration extends FunctionNode {
    initialise() {
        super.initialise();
        if (this.id !== null) {
            this.id.variable.isId = true;
        }
    }
    parseNode(esTreeNode) {
        if (esTreeNode.id !== null) {
            this.id = new this.context.nodeConstructors.Identifier(esTreeNode.id, this, this.scope
                .parent);
        }
        super.parseNode(esTreeNode);
    }
}

const WHITESPACE = /\s/;
// The header ends at the first non-white-space after "default"
function getDeclarationStart(code, start = 0) {
    start = findFirstOccurrenceOutsideComment(code, 'default', start) + 7;
    while (WHITESPACE.test(code[start]))
        start++;
    return start;
}
function getIdInsertPosition(code, declarationKeyword, start = 0) {
    const declarationEnd = findFirstOccurrenceOutsideComment(code, declarationKeyword, start) + declarationKeyword.length;
    code = code.slice(declarationEnd, findFirstOccurrenceOutsideComment(code, '{', declarationEnd));
    const generatorStarPos = findFirstOccurrenceOutsideComment(code, '*');
    if (generatorStarPos === -1) {
        return declarationEnd;
    }
    return declarationEnd + generatorStarPos + 1;
}
class ExportDefaultDeclaration extends NodeBase {
    include(includeChildrenRecursively) {
        super.include(includeChildrenRecursively);
        if (includeChildrenRecursively) {
            this.context.includeVariable(this.variable);
        }
    }
    initialise() {
        const declaration = this.declaration;
        this.declarationName =
            (declaration.id && declaration.id.name) || this.declaration.name;
        this.variable = this.scope.addExportDefaultDeclaration(this.declarationName || this.context.getModuleName(), this, this.context);
        this.context.addExport(this);
    }
    render(code, options, { start, end } = BLANK) {
        const declarationStart = getDeclarationStart(code.original, this.start);
        if (this.declaration instanceof FunctionDeclaration) {
            this.renderNamedDeclaration(code, declarationStart, 'function', this.declaration.id === null, options);
        }
        else if (this.declaration instanceof ClassDeclaration) {
            this.renderNamedDeclaration(code, declarationStart, 'class', this.declaration.id === null, options);
        }
        else if (this.variable.getOriginalVariable() !== this.variable) {
            // Remove altogether to prevent re-declaring the same variable
            if (options.format === 'system' && this.variable.exportName) {
                code.overwrite(start, end, `exports('${this.variable.exportName}', ${this.variable.getName()});`);
            }
            else {
                treeshakeNode(this, code, start, end);
            }
            return;
        }
        else if (this.variable.included) {
            this.renderVariableDeclaration(code, declarationStart, options);
        }
        else {
            code.remove(this.start, declarationStart);
            this.declaration.render(code, options, {
                isCalleeOfRenderedParent: false,
                renderedParentType: ExpressionStatement
            });
            if (code.original[this.end - 1] !== ';') {
                code.appendLeft(this.end, ';');
            }
            return;
        }
        this.declaration.render(code, options);
    }
    renderNamedDeclaration(code, declarationStart, declarationKeyword, needsId, options) {
        const name = this.variable.getName();
        // Remove `export default`
        code.remove(this.start, declarationStart);
        if (needsId) {
            code.appendLeft(getIdInsertPosition(code.original, declarationKeyword, declarationStart), ` ${name}`);
        }
        if (options.format === 'system' &&
            this.declaration instanceof ClassDeclaration &&
            this.variable.exportName) {
            code.appendLeft(this.end, ` exports('${this.variable.exportName}', ${name});`);
        }
    }
    renderVariableDeclaration(code, declarationStart, options) {
        const systemBinding = options.format === 'system' && this.variable.exportName
            ? `exports('${this.variable.exportName}', `
            : '';
        code.overwrite(this.start, declarationStart, `${options.varOrConst} ${this.variable.getName()} = ${systemBinding}`);
        const hasTrailingSemicolon = code.original.charCodeAt(this.end - 1) === 59; /*";"*/
        if (systemBinding) {
            code.appendRight(hasTrailingSemicolon ? this.end - 1 : this.end, ')' + (hasTrailingSemicolon ? '' : ';'));
        }
        else if (!hasTrailingSemicolon) {
            code.appendLeft(this.end, ';');
        }
    }
}
ExportDefaultDeclaration.prototype.needsBoundaries = true;

class ExportDefaultVariable extends LocalVariable {
    constructor(name, exportDefaultDeclaration, context) {
        super(name, exportDefaultDeclaration, exportDefaultDeclaration.declaration, context);
        this.hasId = false;
        // Not initialised during construction
        this.originalId = null;
        this.originalVariable = null;
        const declaration = exportDefaultDeclaration.declaration;
        if ((declaration instanceof FunctionDeclaration || declaration instanceof ClassDeclaration) &&
            declaration.id) {
            this.hasId = true;
            this.originalId = declaration.id;
        }
        else if (declaration instanceof Identifier$1) {
            this.originalId = declaration;
        }
    }
    addReference(identifier) {
        if (!this.hasId) {
            this.name = identifier.name;
        }
    }
    getAssignedVariableName() {
        return (this.originalId && this.originalId.name) || null;
    }
    getBaseVariableName() {
        const original = this.getOriginalVariable();
        if (original === this) {
            return super.getBaseVariableName();
        }
        else {
            return original.getBaseVariableName();
        }
    }
    getName() {
        const original = this.getOriginalVariable();
        if (original === this) {
            return super.getName();
        }
        else {
            return original.getName();
        }
    }
    getOriginalVariable() {
        if (this.originalVariable === null) {
            if (!this.originalId || (!this.hasId && this.originalId.variable.isReassigned)) {
                this.originalVariable = this;
            }
            else {
                const assignedOriginal = this.originalId.variable;
                this.originalVariable =
                    assignedOriginal instanceof ExportDefaultVariable
                        ? assignedOriginal.getOriginalVariable()
                        : assignedOriginal;
            }
        }
        return this.originalVariable;
    }
    setRenderNames(baseName, name) {
        const original = this.getOriginalVariable();
        if (original === this) {
            super.setRenderNames(baseName, name);
        }
        else {
            original.setRenderNames(baseName, name);
        }
    }
    setSafeName(name) {
        const original = this.getOriginalVariable();
        if (original === this) {
            super.setSafeName(name);
        }
        else {
            original.setSafeName(name);
        }
    }
}

const MISSING_EXPORT_SHIM_VARIABLE = '_missingExportShim';
const INTEROP_DEFAULT_VARIABLE = '_interopDefault';
const INTEROP_NAMESPACE_VARIABLE = '_interopNamespace';

class ExportShimVariable extends Variable {
    constructor(module) {
        super(MISSING_EXPORT_SHIM_VARIABLE);
        this.module = module;
    }
}

class NamespaceVariable extends Variable {
    constructor(context) {
        super(context.getModuleName());
        this.memberVariables = Object.create(null);
        this.containsExternalNamespace = false;
        this.referencedEarly = false;
        this.references = [];
        this.context = context;
        this.module = context.module;
    }
    addReference(identifier) {
        this.references.push(identifier);
        this.name = identifier.name;
    }
    // This is only called if "UNKNOWN_PATH" is reassigned as in all other situations, either the
    // build fails due to an illegal namespace reassignment or MemberExpression already forwards
    // the reassignment to the right variable. This means we lost track of this variable and thus
    // need to reassign all exports.
    deoptimizePath() {
        for (const key in this.memberVariables) {
            this.memberVariables[key].deoptimizePath(UNKNOWN_PATH);
        }
    }
    include() {
        if (!this.included) {
            if (this.containsExternalNamespace) {
                this.context.error({
                    code: 'NAMESPACE_CANNOT_CONTAIN_EXTERNAL',
                    id: this.module.id,
                    message: `Cannot create an explicit namespace object for module "${this.context.getModuleName()}" because it contains a reexported external namespace`
                }, undefined);
            }
            this.included = true;
            for (const identifier of this.references) {
                if (identifier.context.getModuleExecIndex() <= this.context.getModuleExecIndex()) {
                    this.referencedEarly = true;
                    break;
                }
            }
            if (this.context.preserveModules) {
                for (const memberName of Object.keys(this.memberVariables))
                    this.memberVariables[memberName].include();
            }
            else {
                for (const memberName of Object.keys(this.memberVariables))
                    this.context.includeVariable(this.memberVariables[memberName]);
            }
        }
    }
    initialise() {
        for (const name of this.context.getExports().concat(this.context.getReexports())) {
            if (name[0] === '*' && name.length > 1)
                this.containsExternalNamespace = true;
            this.memberVariables[name] = this.context.traceExport(name);
        }
    }
    renderBlock(options) {
        const _ = options.compact ? '' : ' ';
        const n = options.compact ? '' : '\n';
        const t = options.indent;
        const members = Object.keys(this.memberVariables).map(name => {
            const original = this.memberVariables[name];
            if (this.referencedEarly || original.isReassigned) {
                return `${t}get ${name}${_}()${_}{${_}return ${original.getName()}${options.compact ? '' : ';'}${_}}`;
            }
            const safeName = RESERVED_NAMES[name] ? `'${name}'` : name;
            return `${t}${safeName}: ${original.getName()}`;
        });
        members.unshift(`${t}__proto__:${_}null`);
        if (options.namespaceToStringTag) {
            members.unshift(`${t}[Symbol.toStringTag]:${_}'Module'`);
        }
        const name = this.getName();
        const callee = options.freeze ? `/*#__PURE__*/Object.freeze` : '';
        const membersStr = members.join(`,${n}`);
        let output = `${options.varOrConst} ${name}${_}=${_}${callee}({${n}${membersStr}${n}});`;
        if (options.format === 'system' && this.exportName) {
            output += `${n}exports('${this.exportName}',${_}${name});`;
        }
        return output;
    }
    renderFirst() {
        return this.referencedEarly;
    }
}
NamespaceVariable.prototype.isNamespace = true;

const esModuleExport = `Object.defineProperty(exports, '__esModule', { value: true });`;
const compactEsModuleExport = `Object.defineProperty(exports,'__esModule',{value:true});`;

function getExportBlock(exports, dependencies, namedExportsMode, interop, compact, t, mechanism = 'return ') {
    const _ = compact ? '' : ' ';
    const n = compact ? '' : '\n';
    if (!namedExportsMode) {
        let local;
        if (exports.length > 0) {
            local = exports[0].local;
        }
        else {
            for (const dep of dependencies) {
                if (dep.reexports) {
                    const expt = dep.reexports[0];
                    local =
                        dep.namedExportsMode && expt.imported !== '*' && expt.imported !== 'default'
                            ? `${dep.name}.${expt.imported}`
                            : dep.name;
                }
            }
        }
        return `${mechanism}${local};`;
    }
    let exportBlock = '';
    // star exports must always output first for precedence
    dependencies.forEach(({ name, reexports }) => {
        if (reexports && namedExportsMode) {
            reexports.forEach(specifier => {
                if (specifier.reexported === '*') {
                    if (exportBlock)
                        exportBlock += n;
                    if (specifier.needsLiveBinding) {
                        exportBlock +=
                            `Object.keys(${name}).forEach(function${_}(k)${_}{${n}` +
                                `${t}if${_}(k${_}!==${_}'default')${_}Object.defineProperty(exports,${_}k,${_}{${n}` +
                                `${t}${t}enumerable:${_}true,${n}` +
                                `${t}${t}get:${_}function${_}()${_}{${n}` +
                                `${t}${t}${t}return ${name}[k];${n}` +
                                `${t}${t}}${n}${t}});${n}});`;
                    }
                    else {
                        exportBlock +=
                            `Object.keys(${name}).forEach(function${_}(k)${_}{${n}` +
                                `${t}if${_}(k${_}!==${_}'default')${_}exports[k]${_}=${_}${name}[k];${n}});`;
                    }
                }
            });
        }
    });
    for (const { name, imports, reexports, isChunk, namedExportsMode: depNamedExportsMode, exportsNames } of dependencies) {
        if (reexports && namedExportsMode) {
            for (const specifier of reexports) {
                if (specifier.imported === 'default' && !isChunk) {
                    if (exportBlock)
                        exportBlock += n;
                    if (exportsNames &&
                        (reexports.some(specifier => specifier.imported === 'default'
                            ? specifier.reexported === 'default'
                            : specifier.imported !== '*') ||
                            (imports && imports.some(specifier => specifier.imported !== 'default')))) {
                        exportBlock += `exports.${specifier.reexported}${_}=${_}${name}${interop !== false ? '__default' : '.default'};`;
                    }
                    else {
                        exportBlock += `exports.${specifier.reexported}${_}=${_}${name};`;
                    }
                }
                else if (specifier.imported !== '*') {
                    if (exportBlock)
                        exportBlock += n;
                    const importName = specifier.imported === 'default' && !depNamedExportsMode
                        ? name
                        : `${name}.${specifier.imported}`;
                    exportBlock += specifier.needsLiveBinding
                        ? `Object.defineProperty(exports,${_}'${specifier.reexported}',${_}{${n}` +
                            `${t}enumerable:${_}true,${n}` +
                            `${t}get:${_}function${_}()${_}{${n}` +
                            `${t}${t}return ${importName};${n}${t}}${n}});`
                        : `exports.${specifier.reexported}${_}=${_}${importName};`;
                }
                else if (specifier.reexported !== '*') {
                    if (exportBlock)
                        exportBlock += n;
                    exportBlock += `exports.${specifier.reexported}${_}=${_}${name};`;
                }
            }
        }
    }
    for (const expt of exports) {
        const lhs = `exports.${expt.exported}`;
        const rhs = expt.local;
        if (lhs !== rhs) {
            if (exportBlock)
                exportBlock += n;
            exportBlock += `${lhs}${_}=${_}${rhs};`;
        }
    }
    return exportBlock;
}

function getInteropBlock(dependencies, options, varOrConst) {
    const _ = options.compact ? '' : ' ';
    return dependencies
        .map(({ name, exportsNames, exportsDefault, namedExportsMode }) => {
        if (!namedExportsMode || !exportsDefault || options.interop === false)
            return null;
        if (exportsNames) {
            return (`${varOrConst} ${name}__default${_}=${_}'default'${_}in ${name}${_}?` +
                `${_}${name}['default']${_}:${_}${name};`);
        }
        return (`${name}${_}=${_}${name}${_}&&${_}${name}.hasOwnProperty('default')${_}?` +
            `${_}${name}['default']${_}:${_}${name};`);
    })
        .filter(Boolean)
        .join(options.compact ? '' : '\n');
}

function copyPropertyLiveBinding(_, n, t, i) {
    return (`${i}var d${_}=${_}Object.getOwnPropertyDescriptor(e,${_}k);${n}` +
        `${i}Object.defineProperty(n,${_}k,${_}d.get${_}?${_}d${_}:${_}{${n}` +
        `${i}${t}enumerable:${_}true,${n}` +
        `${i}${t}get:${_}function${_}()${_}{${n}` +
        `${i}${t}${t}return e[k];${n}` +
        `${i}${t}}${n}` +
        `${i}});${n}`);
}
function copyPropertyStatic(_, n, _t, i) {
    return `${i}n[k]${_}=e${_}[k];${n}`;
}
function getInteropNamespace(_, n, t, liveBindings) {
    return (`function ${INTEROP_NAMESPACE_VARIABLE}(e)${_}{${n}` +
        `${t}if${_}(e${_}&&${_}e.__esModule)${_}{${_}return e;${_}}${_}else${_}{${n}` +
        `${t}${t}var n${_}=${_}{};${n}` +
        `${t}${t}if${_}(e)${_}{${n}` +
        `${t}${t}${t}Object.keys(e).forEach(function${_}(k)${_}{${n}` +
        (liveBindings ? copyPropertyLiveBinding : copyPropertyStatic)(_, n, t, t + t + t + t) +
        `${t}${t}${t}});${n}` +
        `${t}${t}}${n}` +
        `${t}${t}n['default']${_}=${_}e;${n}` +
        `${t}${t}return n;${n}` +
        `${t}}${n}` +
        `}${n}${n}`);
}

const builtins$1 = {
    assert: true,
    buffer: true,
    console: true,
    constants: true,
    domain: true,
    events: true,
    http: true,
    https: true,
    os: true,
    path: true,
    process: true,
    punycode: true,
    querystring: true,
    stream: true,
    string_decoder: true,
    timers: true,
    tty: true,
    url: true,
    util: true,
    vm: true,
    zlib: true
};
// Creating a browser chunk that depends on Node.js built-in modules ('util'). You might need to include https://www.npmjs.com/package/rollup-plugin-node-builtins
function warnOnBuiltins(warn, dependencies) {
    const externalBuiltins = dependencies.map(({ id }) => id).filter(id => id in builtins$1);
    if (!externalBuiltins.length)
        return;
    const detail = externalBuiltins.length === 1
        ? `module ('${externalBuiltins[0]}')`
        : `modules (${externalBuiltins
            .slice(0, -1)
            .map(name => `'${name}'`)
            .join(', ')} and '${externalBuiltins.slice(-1)}')`;
    warn({
        code: 'MISSING_NODE_BUILTINS',
        message: `Creating a browser bundle that depends on Node.js built-in ${detail}. You might need to include https://www.npmjs.com/package/rollup-plugin-node-builtins`,
        modules: externalBuiltins
    });
}

// AMD resolution will only respect the AMD baseUrl if the .js extension is omitted.
// The assumption is that this makes sense for all relative ids:
// https://requirejs.org/docs/api.html#jsfiles
function removeExtensionFromRelativeAmdId(id) {
    if (id[0] === '.' && id.endsWith('.js')) {
        return id.slice(0, -3);
    }
    return id;
}
function amd(magicString, { accessedGlobals, dependencies, exports, hasExports, indentString: t, intro, isEntryModuleFacade, namedExportsMode, outro, varOrConst, warn }, options) {
    warnOnBuiltins(warn, dependencies);
    const deps = dependencies.map(m => `'${removeExtensionFromRelativeAmdId(m.id)}'`);
    const args = dependencies.map(m => m.name);
    const n = options.compact ? '' : '\n';
    const _ = options.compact ? '' : ' ';
    if (namedExportsMode && hasExports) {
        args.unshift(`exports`);
        deps.unshift(`'exports'`);
    }
    if (accessedGlobals.has('require')) {
        args.unshift('require');
        deps.unshift(`'require'`);
    }
    if (accessedGlobals.has('module')) {
        args.unshift('module');
        deps.unshift(`'module'`);
    }
    const amdOptions = options.amd || {};
    const params = (amdOptions.id ? `'${amdOptions.id}',${_}` : ``) +
        (deps.length ? `[${deps.join(`,${_}`)}],${_}` : ``);
    const useStrict = options.strict !== false ? `${_}'use strict';` : ``;
    const define = amdOptions.define || 'define';
    const wrapperStart = `${define}(${params}function${_}(${args.join(`,${_}`)})${_}{${useStrict}${n}${n}`;
    // var foo__default = 'default' in foo ? foo['default'] : foo;
    const interopBlock = getInteropBlock(dependencies, options, varOrConst);
    if (interopBlock) {
        magicString.prepend(interopBlock + n + n);
    }
    if (accessedGlobals.has(INTEROP_NAMESPACE_VARIABLE)) {
        magicString.prepend(getInteropNamespace(_, n, t, options.externalLiveBindings !== false));
    }
    if (intro)
        magicString.prepend(intro);
    const exportBlock = getExportBlock(exports, dependencies, namedExportsMode, options.interop, options.compact, t);
    if (exportBlock)
        magicString.append(n + n + exportBlock);
    if (namedExportsMode && hasExports && isEntryModuleFacade && options.esModule)
        magicString.append(`${n}${n}${options.compact ? compactEsModuleExport : esModuleExport}`);
    if (outro)
        magicString.append(outro);
    return magicString
        .indent(t)
        .append(n + n + '});')
        .prepend(wrapperStart);
}

function cjs(magicString, { accessedGlobals, dependencies, exports, hasExports, indentString: t, intro, isEntryModuleFacade, namedExportsMode, outro, varOrConst }, options) {
    const n = options.compact ? '' : '\n';
    const _ = options.compact ? '' : ' ';
    intro =
        (options.strict === false ? intro : `'use strict';${n}${n}${intro}`) +
            (namedExportsMode && hasExports && isEntryModuleFacade && options.esModule
                ? `${options.compact ? compactEsModuleExport : esModuleExport}${n}${n}`
                : '');
    let needsInterop = false;
    const interop = options.interop !== false;
    let importBlock;
    let definingVariable = false;
    importBlock = '';
    for (const { id, namedExportsMode, isChunk, name, reexports, imports, exportsNames, exportsDefault } of dependencies) {
        if (!reexports && !imports) {
            if (importBlock) {
                importBlock += !options.compact || definingVariable ? `;${n}` : ',';
            }
            definingVariable = false;
            importBlock += `require('${id}')`;
        }
        else {
            importBlock +=
                options.compact && definingVariable ? ',' : `${importBlock ? `;${n}` : ''}${varOrConst} `;
            definingVariable = true;
            if (!interop || isChunk || !exportsDefault || !namedExportsMode) {
                importBlock += `${name}${_}=${_}require('${id}')`;
            }
            else {
                needsInterop = true;
                if (exportsNames)
                    importBlock += `${name}${_}=${_}require('${id}')${options.compact ? ',' : `;\n${varOrConst} `}${name}__default${_}=${_}${INTEROP_DEFAULT_VARIABLE}(${name})`;
                else
                    importBlock += `${name}${_}=${_}${INTEROP_DEFAULT_VARIABLE}(require('${id}'))`;
            }
        }
    }
    if (importBlock)
        importBlock += ';';
    if (needsInterop) {
        const ex = options.compact ? 'e' : 'ex';
        intro +=
            `function ${INTEROP_DEFAULT_VARIABLE}${_}(${ex})${_}{${_}return${_}` +
                `(${ex}${_}&&${_}(typeof ${ex}${_}===${_}'object')${_}&&${_}'default'${_}in ${ex})${_}` +
                `?${_}${ex}['default']${_}:${_}${ex}${options.compact ? '' : '; '}}${n}${n}`;
    }
    if (accessedGlobals.has(INTEROP_NAMESPACE_VARIABLE)) {
        intro += getInteropNamespace(_, n, t, options.externalLiveBindings !== false);
    }
    if (importBlock)
        intro += importBlock + n + n;
    const exportBlock = getExportBlock(exports, dependencies, namedExportsMode, options.interop, options.compact, t, `module.exports${_}=${_}`);
    magicString.prepend(intro);
    if (exportBlock)
        magicString.append(n + n + exportBlock);
    if (outro)
        magicString.append(outro);
    return magicString;
}

function esm(magicString, { intro, outro, dependencies, exports }, options) {
    const _ = options.compact ? '' : ' ';
    const n = options.compact ? '' : '\n';
    const importBlock = dependencies
        .map(({ id, reexports, imports, name }) => {
        if (!reexports && !imports) {
            return `import${_}'${id}';`;
        }
        let output = '';
        if (imports) {
            const defaultImport = imports.find(specifier => specifier.imported === 'default');
            const starImport = imports.find(specifier => specifier.imported === '*');
            if (starImport) {
                output += `import${_}*${_}as ${starImport.local} from${_}'${id}';`;
                if (imports.length > 1)
                    output += n;
            }
            if (defaultImport && imports.length === 1) {
                output += `import ${defaultImport.local} from${_}'${id}';`;
            }
            else if (!starImport || imports.length > 1) {
                output += `import ${defaultImport ? `${defaultImport.local},${_}` : ''}{${_}${imports
                    .filter(specifier => specifier !== defaultImport && specifier !== starImport)
                    .map(specifier => {
                    if (specifier.imported === specifier.local) {
                        return specifier.imported;
                    }
                    else {
                        return `${specifier.imported} as ${specifier.local}`;
                    }
                })
                    .join(`,${_}`)}${_}}${_}from${_}'${id}';`;
            }
        }
        if (reexports) {
            if (imports)
                output += n;
            const starExport = reexports.find(specifier => specifier.reexported === '*');
            const namespaceReexport = reexports.find(specifier => specifier.imported === '*' && specifier.reexported !== '*');
            if (starExport) {
                output += `export${_}*${_}from${_}'${id}';`;
                if (reexports.length === 1) {
                    return output;
                }
                output += n;
            }
            if (namespaceReexport) {
                if (!imports ||
                    !imports.some(specifier => specifier.imported === '*' && specifier.local === name))
                    output += `import${_}*${_}as ${name} from${_}'${id}';${n}`;
                output += `export${_}{${_}${name === namespaceReexport.reexported
                    ? name
                    : `${name} as ${namespaceReexport.reexported}`} };`;
                if (reexports.length === (starExport ? 2 : 1)) {
                    return output;
                }
                output += n;
            }
            output += `export${_}{${_}${reexports
                .filter(specifier => specifier !== starExport && specifier !== namespaceReexport)
                .map(specifier => {
                if (specifier.imported === specifier.reexported) {
                    return specifier.imported;
                }
                else {
                    return `${specifier.imported} as ${specifier.reexported}`;
                }
            })
                .join(`,${_}`)}${_}}${_}from${_}'${id}';`;
        }
        return output;
    })
        .join(n);
    if (importBlock)
        intro += importBlock + n + n;
    if (intro)
        magicString.prepend(intro);
    const exportBlock = [];
    const exportDeclaration = [];
    exports.forEach(specifier => {
        if (specifier.exported === 'default') {
            exportBlock.push(`export default ${specifier.local};`);
        }
        else {
            exportDeclaration.push(specifier.exported === specifier.local
                ? specifier.local
                : `${specifier.local} as ${specifier.exported}`);
        }
    });
    if (exportDeclaration.length) {
        exportBlock.push(`export${_}{${_}${exportDeclaration.join(`,${_}`)}${_}};`);
    }
    if (exportBlock.length)
        magicString.append(n + n + exportBlock.join(n).trim());
    if (outro)
        magicString.append(outro);
    return magicString.trim();
}

function spaces(i) {
    let result = '';
    while (i--)
        result += ' ';
    return result;
}
function tabsToSpaces(str) {
    return str.replace(/^\t+/, match => match.split('\t').join('  '));
}
function getCodeFrame(source, line, column) {
    let lines = source.split('\n');
    const frameStart = Math.max(0, line - 3);
    let frameEnd = Math.min(line + 2, lines.length);
    lines = lines.slice(frameStart, frameEnd);
    while (!/\S/.test(lines[lines.length - 1])) {
        lines.pop();
        frameEnd -= 1;
    }
    const digits = String(frameEnd).length;
    return lines
        .map((str, i) => {
        const isErrorLine = frameStart + i + 1 === line;
        let lineNum = String(i + frameStart + 1);
        while (lineNum.length < digits)
            lineNum = ` ${lineNum}`;
        if (isErrorLine) {
            const indicator = spaces(digits + 2 + tabsToSpaces(str.slice(0, column)).length) + '^';
            return `${lineNum}: ${tabsToSpaces(str)}\n${indicator}`;
        }
        return `${lineNum}: ${tabsToSpaces(str)}`;
    })
        .join('\n');
}

function error(base, props) {
    if (!(base instanceof Error))
        base = Object.assign(new Error(base.message), base);
    if (props)
        Object.assign(base, props);
    throw base;
}
function augmentCodeLocation(object, pos, source, id) {
    if (typeof pos === 'object') {
        const { line, column } = pos;
        object.loc = { file: id, line, column };
    }
    else {
        object.pos = pos;
        const { line, column } = locate(source, pos, { offsetLine: 1 });
        object.loc = { file: id, line, column };
    }
    if (object.frame === undefined) {
        const { line, column } = object.loc;
        object.frame = getCodeFrame(source, line, column);
    }
}
var Errors;
(function (Errors) {
    Errors["ASSET_NOT_FINALISED"] = "ASSET_NOT_FINALISED";
    Errors["ASSET_NOT_FOUND"] = "ASSET_NOT_FOUND";
    Errors["ASSET_SOURCE_ALREADY_SET"] = "ASSET_SOURCE_ALREADY_SET";
    Errors["ASSET_SOURCE_MISSING"] = "ASSET_SOURCE_MISSING";
    Errors["BAD_LOADER"] = "BAD_LOADER";
    Errors["CANNOT_EMIT_FROM_OPTIONS_HOOK"] = "CANNOT_EMIT_FROM_OPTIONS_HOOK";
    Errors["CHUNK_NOT_GENERATED"] = "CHUNK_NOT_GENERATED";
    Errors["DEPRECATED_FEATURE"] = "DEPRECATED_FEATURE";
    Errors["FILE_NOT_FOUND"] = "FILE_NOT_FOUND";
    Errors["FILE_NAME_CONFLICT"] = "FILE_NAME_CONFLICT";
    Errors["INVALID_CHUNK"] = "INVALID_CHUNK";
    Errors["INVALID_EXTERNAL_ID"] = "INVALID_EXTERNAL_ID";
    Errors["INVALID_OPTION"] = "INVALID_OPTION";
    Errors["INVALID_PLUGIN_HOOK"] = "INVALID_PLUGIN_HOOK";
    Errors["INVALID_ROLLUP_PHASE"] = "INVALID_ROLLUP_PHASE";
    Errors["NAMESPACE_CONFLICT"] = "NAMESPACE_CONFLICT";
    Errors["PLUGIN_ERROR"] = "PLUGIN_ERROR";
    Errors["UNRESOLVED_ENTRY"] = "UNRESOLVED_ENTRY";
    Errors["UNRESOLVED_IMPORT"] = "UNRESOLVED_IMPORT";
    Errors["VALIDATION_ERROR"] = "VALIDATION_ERROR";
})(Errors || (Errors = {}));
function errAssetNotFinalisedForFileName(name) {
    return {
        code: Errors.ASSET_NOT_FINALISED,
        message: `Plugin error - Unable to get file name for asset "${name}". Ensure that the source is set and that generate is called first.`
    };
}
function errCannotEmitFromOptionsHook() {
    return {
        code: Errors.CANNOT_EMIT_FROM_OPTIONS_HOOK,
        message: `Cannot emit files or set asset sources in the "outputOptions" hook, use the "renderStart" hook instead.`
    };
}
function errChunkNotGeneratedForFileName(name) {
    return {
        code: Errors.CHUNK_NOT_GENERATED,
        message: `Plugin error - Unable to get file name for chunk "${name}". Ensure that generate is called first.`
    };
}
function errAssetReferenceIdNotFoundForSetSource(assetReferenceId) {
    return {
        code: Errors.ASSET_NOT_FOUND,
        message: `Plugin error - Unable to set the source for unknown asset "${assetReferenceId}".`
    };
}
function errAssetSourceAlreadySet(name) {
    return {
        code: Errors.ASSET_SOURCE_ALREADY_SET,
        message: `Unable to set the source for asset "${name}", source already set.`
    };
}
function errNoAssetSourceSet(assetName) {
    return {
        code: Errors.ASSET_SOURCE_MISSING,
        message: `Plugin error creating asset "${assetName}" - no asset source set.`
    };
}
function errBadLoader(id) {
    return {
        code: Errors.BAD_LOADER,
        message: `Error loading ${index.relativeId(id)}: plugin load hook should return a string, a { code, map } object, or nothing/null`
    };
}
function errDeprecation(deprecation) {
    return Object.assign({ code: Errors.DEPRECATED_FEATURE }, (typeof deprecation === 'string' ? { message: deprecation } : deprecation));
}
function errFileReferenceIdNotFoundForFilename(assetReferenceId) {
    return {
        code: Errors.FILE_NOT_FOUND,
        message: `Plugin error - Unable to get file name for unknown file "${assetReferenceId}".`
    };
}
function errFileNameConflict(fileName) {
    return {
        code: Errors.FILE_NAME_CONFLICT,
        message: `Could not emit file "${fileName}" as it conflicts with an already emitted file.`
    };
}
function errCannotAssignModuleToChunk(moduleId, assignToAlias, currentAlias) {
    return {
        code: Errors.INVALID_CHUNK,
        message: `Cannot assign ${index.relativeId(moduleId)} to the "${assignToAlias}" chunk as it is already in the "${currentAlias}" chunk.`
    };
}
function errInternalIdCannotBeExternal(source, importer) {
    return {
        code: Errors.INVALID_EXTERNAL_ID,
        message: `'${source}' is imported as an external by ${index.relativeId(importer)}, but is already an existing non-external module id.`
    };
}
function errInvalidOption(option, explanation) {
    return {
        code: Errors.INVALID_OPTION,
        message: `Invalid value for option "${option}" - ${explanation}.`
    };
}
function errInvalidRollupPhaseForAddWatchFile() {
    return {
        code: Errors.INVALID_ROLLUP_PHASE,
        message: `Cannot call addWatchFile after the build has finished.`
    };
}
function errInvalidRollupPhaseForChunkEmission() {
    return {
        code: Errors.INVALID_ROLLUP_PHASE,
        message: `Cannot emit chunks after module loading has finished.`
    };
}
function errNamespaceConflict(name, reexportingModule, additionalExportAllModule) {
    return {
        code: Errors.NAMESPACE_CONFLICT,
        message: `Conflicting namespaces: ${index.relativeId(reexportingModule.id)} re-exports '${name}' from both ${index.relativeId(reexportingModule.exportsAll[name])} and ${index.relativeId(additionalExportAllModule.exportsAll[name])} (will be ignored)`,
        name,
        reexporter: reexportingModule.id,
        sources: [reexportingModule.exportsAll[name], additionalExportAllModule.exportsAll[name]]
    };
}
function errEntryCannotBeExternal(unresolvedId) {
    return {
        code: Errors.UNRESOLVED_ENTRY,
        message: `Entry module cannot be external (${index.relativeId(unresolvedId)}).`
    };
}
function errUnresolvedEntry(unresolvedId) {
    return {
        code: Errors.UNRESOLVED_ENTRY,
        message: `Could not resolve entry module (${index.relativeId(unresolvedId)}).`
    };
}
function errUnresolvedImport(source, importer) {
    return {
        code: Errors.UNRESOLVED_IMPORT,
        message: `Could not resolve '${source}' from ${index.relativeId(importer)}`
    };
}
function errUnresolvedImportTreatedAsExternal(source, importer) {
    return {
        code: Errors.UNRESOLVED_IMPORT,
        importer: index.relativeId(importer),
        message: `'${source}' is imported by ${index.relativeId(importer)}, but could not be resolved – treating it as an external dependency`,
        source,
        url: 'https://rollupjs.org/guide/en/#warning-treating-module-as-external-dependency'
    };
}
function errFailedValidation(message) {
    return {
        code: Errors.VALIDATION_ERROR,
        message
    };
}

// Generate strings which dereference dotted properties, but use array notation `['prop-deref']`
// if the property name isn't trivial
const shouldUseDot = /^[a-zA-Z$_][a-zA-Z0-9$_]*$/;
function property(prop) {
    return shouldUseDot.test(prop) ? `.${prop}` : `['${prop}']`;
}
function keypath(keypath) {
    return keypath
        .split('.')
        .map(property)
        .join('');
}

function setupNamespace(name, root, globals, compact) {
    const parts = name.split('.');
    if (globals) {
        parts[0] = (typeof globals === 'function' ? globals(parts[0]) : globals[parts[0]]) || parts[0];
    }
    const _ = compact ? '' : ' ';
    parts.pop();
    let acc = root;
    return (parts
        .map(part => ((acc += property(part)), `${acc}${_}=${_}${acc}${_}||${_}{}${compact ? '' : ';'}`))
        .join(compact ? ',' : '\n') + (compact && parts.length ? ';' : '\n'));
}
function assignToDeepVariable(deepName, root, globals, compact, assignment) {
    const _ = compact ? '' : ' ';
    const parts = deepName.split('.');
    if (globals) {
        parts[0] = (typeof globals === 'function' ? globals(parts[0]) : globals[parts[0]]) || parts[0];
    }
    const last = parts.pop();
    let acc = root;
    let deepAssignment = parts
        .map(part => ((acc += property(part)), `${acc}${_}=${_}${acc}${_}||${_}{}`))
        .concat(`${acc}${property(last)}`)
        .join(`,${_}`)
        .concat(`${_}=${_}${assignment}`);
    if (parts.length > 0) {
        deepAssignment = `(${deepAssignment})`;
    }
    return deepAssignment;
}

function trimEmptyImports(dependencies) {
    let i = dependencies.length;
    while (i--) {
        const dependency = dependencies[i];
        if (dependency.exportsDefault || dependency.exportsNames) {
            return dependencies.slice(0, i + 1);
        }
    }
    return [];
}

const thisProp = (name) => `this${keypath(name)}`;
function iife(magicString, { dependencies, exports, hasExports, indentString: t, intro, namedExportsMode, outro, varOrConst, warn }, options) {
    const _ = options.compact ? '' : ' ';
    const n = options.compact ? '' : '\n';
    const { extend, name } = options;
    const isNamespaced = name && name.indexOf('.') !== -1;
    const useVariableAssignment = !extend && !isNamespaced;
    if (name && useVariableAssignment && !isLegal(name)) {
        error({
            code: 'ILLEGAL_IDENTIFIER_AS_NAME',
            message: `Given name (${name}) is not legal JS identifier. If you need this you can try --extend option`
        });
    }
    warnOnBuiltins(warn, dependencies);
    const external = trimEmptyImports(dependencies);
    const deps = external.map(dep => dep.globalName || 'null');
    const args = external.map(m => m.name);
    if (hasExports && !name) {
        error({
            code: 'INVALID_OPTION',
            message: `You must supply "output.name" for IIFE bundles.`
        });
    }
    if (namedExportsMode && hasExports) {
        if (extend) {
            deps.unshift(`${thisProp(name)}${_}=${_}${thisProp(name)}${_}||${_}{}`);
            args.unshift('exports');
        }
        else {
            deps.unshift('{}');
            args.unshift('exports');
        }
    }
    const useStrict = options.strict !== false ? `${t}'use strict';${n}${n}` : ``;
    let wrapperIntro = `(function${_}(${args.join(`,${_}`)})${_}{${n}${useStrict}`;
    if (hasExports && (!extend || !namedExportsMode)) {
        wrapperIntro =
            (useVariableAssignment ? `${varOrConst} ${name}` : thisProp(name)) +
                `${_}=${_}${wrapperIntro}`;
    }
    if (isNamespaced && hasExports) {
        wrapperIntro =
            setupNamespace(name, 'this', options.globals, options.compact) + wrapperIntro;
    }
    let wrapperOutro = `${n}${n}}(${deps.join(`,${_}`)}));`;
    if (!extend && namedExportsMode && hasExports) {
        wrapperOutro = `${n}${n}${t}return exports;${wrapperOutro}`;
    }
    // var foo__default = 'default' in foo ? foo['default'] : foo;
    const interopBlock = getInteropBlock(dependencies, options, varOrConst);
    if (interopBlock)
        magicString.prepend(interopBlock + n + n);
    if (intro)
        magicString.prepend(intro);
    const exportBlock = getExportBlock(exports, dependencies, namedExportsMode, options.interop, options.compact, t);
    if (exportBlock)
        magicString.append(n + n + exportBlock);
    if (outro)
        magicString.append(outro);
    return magicString
        .indent(t)
        .prepend(wrapperIntro)
        .append(wrapperOutro);
}

function getStarExcludes({ dependencies, exports }) {
    const starExcludes = new Set(exports.map(expt => expt.exported));
    if (!starExcludes.has('default'))
        starExcludes.add('default');
    // also include reexport names
    dependencies.forEach(({ reexports }) => {
        if (reexports)
            reexports.forEach(reexport => {
                if (reexport.imported !== '*' && !starExcludes.has(reexport.reexported))
                    starExcludes.add(reexport.reexported);
            });
    });
    return starExcludes;
}
const getStarExcludesBlock = (starExcludes, varOrConst, _, t, n) => starExcludes
    ? `${n}${t}${varOrConst} _starExcludes${_}=${_}{${_}${Array.from(starExcludes).join(`:${_}1,${_}`)}${starExcludes.size ? `:${_}1` : ''}${_}};`
    : '';
const getImportBindingsBlock = (importBindings, _, t, n) => (importBindings.length ? `${n}${t}var ${importBindings.join(`,${_}`)};` : '');
function getExportsBlock(exports, _, t, n) {
    if (exports.length === 0) {
        return '';
    }
    if (exports.length === 1) {
        return `${t}${t}${t}exports('${exports[0].name}',${_}${exports[0].value});${n}${n}`;
    }
    return (`${t}${t}${t}exports({${n}` +
        exports.map(({ name, value }) => `${t}${t}${t}${t}${name}:${_}${value}`).join(`,${n}`) +
        `${n}${t}${t}${t}});${n}${n}`);
}
const getHoistedExportsBlock = (exports, _, t, n) => getExportsBlock(exports
    .filter(expt => expt.hoisted || expt.uninitialized)
    .map(expt => ({ name: expt.exported, value: expt.uninitialized ? 'void 0' : expt.local })), _, t, n);
const getMissingExportsBlock = (exports, _, t, n) => getExportsBlock(exports
    .filter(expt => expt.local === MISSING_EXPORT_SHIM_VARIABLE)
    .map(expt => ({ name: expt.exported, value: MISSING_EXPORT_SHIM_VARIABLE })), _, t, n);
function system(magicString, { accessedGlobals, dependencies, exports, hasExports, indentString: t, intro, outro, usesTopLevelAwait, varOrConst }, options) {
    const n = options.compact ? '' : '\n';
    const _ = options.compact ? '' : ' ';
    const dependencyIds = dependencies.map(m => `'${m.id}'`);
    const importBindings = [];
    let starExcludes;
    const setters = [];
    dependencies.forEach(({ imports, reexports }) => {
        const setter = [];
        if (imports) {
            imports.forEach(specifier => {
                importBindings.push(specifier.local);
                if (specifier.imported === '*') {
                    setter.push(`${specifier.local}${_}=${_}module;`);
                }
                else {
                    setter.push(`${specifier.local}${_}=${_}module.${specifier.imported};`);
                }
            });
        }
        if (reexports) {
            let createdSetter = false;
            // bulk-reexport form
            if (reexports.length > 1 ||
                (reexports.length === 1 &&
                    (reexports[0].reexported === '*' || reexports[0].imported === '*'))) {
                // star reexports
                reexports.forEach(specifier => {
                    if (specifier.reexported !== '*')
                        return;
                    // need own exports list for deduping in star export case
                    if (!starExcludes) {
                        starExcludes = getStarExcludes({ dependencies, exports });
                    }
                    if (!createdSetter) {
                        setter.push(`${varOrConst} _setter${_}=${_}{};`);
                        createdSetter = true;
                    }
                    setter.push(`for${_}(var _$p${_}in${_}module)${_}{`);
                    setter.push(`${t}if${_}(!_starExcludes[_$p])${_}_setter[_$p]${_}=${_}module[_$p];`);
                    setter.push('}');
                });
                // star import reexport
                reexports.forEach(specifier => {
                    if (specifier.imported !== '*' || specifier.reexported === '*')
                        return;
                    setter.push(`exports('${specifier.reexported}',${_}module);`);
                });
                // reexports
                reexports.forEach(specifier => {
                    if (specifier.reexported === '*' || specifier.imported === '*')
                        return;
                    if (!createdSetter) {
                        setter.push(`${varOrConst} _setter${_}=${_}{};`);
                        createdSetter = true;
                    }
                    setter.push(`_setter.${specifier.reexported}${_}=${_}module.${specifier.imported};`);
                });
                if (createdSetter) {
                    setter.push('exports(_setter);');
                }
            }
            else {
                // single reexport
                reexports.forEach(specifier => {
                    setter.push(`exports('${specifier.reexported}',${_}module.${specifier.imported});`);
                });
            }
        }
        setters.push(setter.join(`${n}${t}${t}${t}`));
    });
    const registeredName = options.name ? `'${options.name}',${_}` : '';
    const wrapperParams = accessedGlobals.has('module')
        ? `exports,${_}module`
        : hasExports
            ? 'exports'
            : '';
    let wrapperStart = `System.register(${registeredName}[` +
        dependencyIds.join(`,${_}`) +
        `],${_}function${_}(${wrapperParams})${_}{${n}${t}${options.strict ? "'use strict';" : ''}` +
        getStarExcludesBlock(starExcludes, varOrConst, _, t, n) +
        getImportBindingsBlock(importBindings, _, t, n) +
        `${n}${t}return${_}{${setters.length
            ? `${n}${t}${t}setters:${_}[${setters
                .map(s => s
                ? `function${_}(module)${_}{${n}${t}${t}${t}${s}${n}${t}${t}}`
                : `function${_}()${_}{}`)
                .join(`,${_}`)}],`
            : ''}${n}`;
    wrapperStart +=
        `${t}${t}execute:${_}${usesTopLevelAwait ? `async${_}` : ''}function${_}()${_}{${n}${n}` +
            getHoistedExportsBlock(exports, _, t, n);
    const wrapperEnd = `${n}${n}` +
        getMissingExportsBlock(exports, _, t, n) +
        `${t}${t}}${n}${t}}${options.compact ? '' : ';'}${n}});`;
    if (intro)
        magicString.prepend(intro);
    if (outro)
        magicString.append(outro);
    return magicString
        .indent(`${t}${t}${t}`)
        .append(wrapperEnd)
        .prepend(wrapperStart);
}

function globalProp(name, globalVar) {
    if (!name)
        return 'null';
    return `${globalVar}${keypath(name)}`;
}
function safeAccess(name, globalVar, _) {
    const parts = name.split('.');
    let acc = globalVar;
    return parts.map(part => ((acc += property(part)), acc)).join(`${_}&&${_}`);
}
function umd(magicString, { dependencies, exports, hasExports, indentString: t, intro, namedExportsMode, outro, varOrConst, warn }, options) {
    const _ = options.compact ? '' : ' ';
    const n = options.compact ? '' : '\n';
    const factoryVar = options.compact ? 'f' : 'factory';
    const globalVar = options.compact ? 'g' : 'global';
    if (hasExports && !options.name) {
        error({
            code: 'INVALID_OPTION',
            message: 'You must supply "output.name" for UMD bundles.'
        });
    }
    warnOnBuiltins(warn, dependencies);
    const amdDeps = dependencies.map(m => `'${m.id}'`);
    const cjsDeps = dependencies.map(m => `require('${m.id}')`);
    const trimmedImports = trimEmptyImports(dependencies);
    const globalDeps = trimmedImports.map(module => globalProp(module.globalName, globalVar));
    const factoryArgs = trimmedImports.map(m => m.name);
    if (namedExportsMode && (hasExports || options.noConflict === true)) {
        amdDeps.unshift(`'exports'`);
        cjsDeps.unshift(`exports`);
        globalDeps.unshift(assignToDeepVariable(options.name, globalVar, options.globals, options.compact, `${options.extend ? `${globalProp(options.name, globalVar)}${_}||${_}` : ''}{}`));
        factoryArgs.unshift('exports');
    }
    const amdOptions = options.amd || {};
    const amdParams = (amdOptions.id ? `'${amdOptions.id}',${_}` : ``) +
        (amdDeps.length ? `[${amdDeps.join(`,${_}`)}],${_}` : ``);
    const define = amdOptions.define || 'define';
    const cjsExport = !namedExportsMode && hasExports ? `module.exports${_}=${_}` : ``;
    const useStrict = options.strict !== false ? `${_}'use strict';${n}` : ``;
    let iifeExport;
    if (options.noConflict === true) {
        const noConflictExportsVar = options.compact ? 'e' : 'exports';
        let factory;
        if (!namedExportsMode && hasExports) {
            factory = `var ${noConflictExportsVar}${_}=${_}${assignToDeepVariable(options.name, globalVar, options.globals, options.compact, `${factoryVar}(${globalDeps.join(`,${_}`)})`)};`;
        }
        else if (namedExportsMode) {
            const module = globalDeps.shift();
            factory =
                `var ${noConflictExportsVar}${_}=${_}${module};${n}` +
                    `${t}${t}${factoryVar}(${[noConflictExportsVar].concat(globalDeps).join(`,${_}`)});`;
        }
        iifeExport =
            `(function${_}()${_}{${n}` +
                `${t}${t}var current${_}=${_}${safeAccess(options.name, globalVar, _)};${n}` +
                `${t}${t}${factory}${n}` +
                `${t}${t}${noConflictExportsVar}.noConflict${_}=${_}function${_}()${_}{${_}` +
                `${globalProp(options.name, globalVar)}${_}=${_}current;${_}return ${noConflictExportsVar}${options.compact ? '' : '; '}};${n}` +
                `${t}}())`;
    }
    else {
        iifeExport = `${factoryVar}(${globalDeps.join(`,${_}`)})`;
        if (!namedExportsMode && hasExports) {
            iifeExport = assignToDeepVariable(options.name, globalVar, options.globals, options.compact, iifeExport);
        }
    }
    const iifeNeedsGlobal = hasExports || (options.noConflict === true && namedExportsMode) || globalDeps.length > 0;
    const globalParam = iifeNeedsGlobal ? `${globalVar},${_}` : '';
    const globalArg = iifeNeedsGlobal ? `this,${_}` : '';
    const iifeStart = iifeNeedsGlobal ? `(${globalVar}${_}=${_}${globalVar}${_}||${_}self,${_}` : '';
    const iifeEnd = iifeNeedsGlobal ? ')' : '';
    const cjsIntro = iifeNeedsGlobal
        ? `${t}typeof exports${_}===${_}'object'${_}&&${_}typeof module${_}!==${_}'undefined'${_}?` +
            `${_}${cjsExport}${factoryVar}(${cjsDeps.join(`,${_}`)})${_}:${n}`
        : '';
    const wrapperIntro = `(function${_}(${globalParam}${factoryVar})${_}{${n}` +
        cjsIntro +
        `${t}typeof ${define}${_}===${_}'function'${_}&&${_}${define}.amd${_}?${_}${define}(${amdParams}${factoryVar})${_}:${n}` +
        `${t}${iifeStart}${iifeExport}${iifeEnd};${n}` +
        `}(${globalArg}function${_}(${factoryArgs.join(', ')})${_}{${useStrict}${n}`;
    const wrapperOutro = n + n + '}));';
    // var foo__default = 'default' in foo ? foo['default'] : foo;
    const interopBlock = getInteropBlock(dependencies, options, varOrConst);
    if (interopBlock)
        magicString.prepend(interopBlock + n + n);
    if (intro)
        magicString.prepend(intro);
    const exportBlock = getExportBlock(exports, dependencies, namedExportsMode, options.interop, options.compact, t);
    if (exportBlock)
        magicString.append(n + n + exportBlock);
    if (namedExportsMode && hasExports && options.esModule)
        magicString.append(n + n + (options.compact ? compactEsModuleExport : esModuleExport));
    if (outro)
        magicString.append(outro);
    return magicString
        .trim()
        .indent(t)
        .append(wrapperOutro)
        .prepend(wrapperIntro);
}

var finalisers = { system, amd, cjs, es: esm, iife, umd };

const extractors = {
    ArrayPattern(names, param) {
        for (const element of param.elements) {
            if (element)
                extractors[element.type](names, element);
        }
    },
    AssignmentPattern(names, param) {
        extractors[param.left.type](names, param.left);
    },
    Identifier(names, param) {
        names.push(param.name);
    },
    MemberExpression() { },
    ObjectPattern(names, param) {
        for (const prop of param.properties) {
            if (prop.type === 'RestElement') {
                extractors.RestElement(names, prop);
            }
            else {
                extractors[prop.value.type](names, prop.value);
            }
        }
    },
    RestElement(names, param) {
        extractors[param.argument.type](names, param.argument);
    }
};
const extractAssignedNames = function extractAssignedNames(param) {
    const names = [];
    extractors[param.type](names, param);
    return names;
};

class ArrayExpression extends NodeBase {
    bind() {
        super.bind();
        for (const element of this.elements) {
            if (element !== null)
                element.deoptimizePath(UNKNOWN_PATH);
        }
    }
    getReturnExpressionWhenCalledAtPath(path) {
        if (path.length !== 1)
            return UNKNOWN_EXPRESSION;
        return getMemberReturnExpressionWhenCalled(arrayMembers, path[0]);
    }
    hasEffectsWhenAccessedAtPath(path) {
        return path.length > 1;
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        if (path.length === 1) {
            return hasMemberEffectWhenCalled(arrayMembers, path[0], this.included, callOptions, options);
        }
        return true;
    }
}

class ArrayPattern extends NodeBase {
    addExportedVariables(variables) {
        for (const element of this.elements) {
            if (element !== null) {
                element.addExportedVariables(variables);
            }
        }
    }
    declare(kind, _init) {
        const variables = [];
        for (const element of this.elements) {
            if (element !== null) {
                variables.push(...element.declare(kind, UNKNOWN_EXPRESSION));
            }
        }
        return variables;
    }
    deoptimizePath(path) {
        if (path.length === 0) {
            for (const element of this.elements) {
                if (element !== null) {
                    element.deoptimizePath(path);
                }
            }
        }
    }
    hasEffectsWhenAssignedAtPath(path, options) {
        if (path.length > 0)
            return true;
        for (const element of this.elements) {
            if (element !== null && element.hasEffectsWhenAssignedAtPath(EMPTY_PATH, options))
                return true;
        }
        return false;
    }
}

class BlockScope extends ChildScope {
    addDeclaration(identifier, context, init = null, isHoisted = false) {
        if (isHoisted) {
            return this.parent.addDeclaration(identifier, context, UNKNOWN_EXPRESSION, true);
        }
        else {
            return super.addDeclaration(identifier, context, init, false);
        }
    }
}

class BlockStatement$1 extends NodeBase {
    addImplicitReturnExpressionToScope() {
        const lastStatement = this.body[this.body.length - 1];
        if (!lastStatement || lastStatement.type !== ReturnStatement) {
            this.scope.addReturnExpression(UNKNOWN_EXPRESSION);
        }
    }
    createScope(parentScope) {
        this.scope = this.parent.preventChildBlockScope
            ? parentScope
            : new BlockScope(parentScope);
    }
    hasEffects(options) {
        for (const node of this.body) {
            if (node.hasEffects(options))
                return true;
        }
        return false;
    }
    include(includeChildrenRecursively) {
        this.included = true;
        for (const node of this.body) {
            if (includeChildrenRecursively || node.shouldBeIncluded())
                node.include(includeChildrenRecursively);
        }
    }
    render(code, options) {
        if (this.body.length) {
            renderStatementList(this.body, code, this.start + 1, this.end - 1, options);
        }
        else {
            super.render(code, options);
        }
    }
}

class ArrowFunctionExpression extends NodeBase {
    createScope(parentScope) {
        this.scope = new ReturnValueScope(parentScope, this.context);
    }
    deoptimizePath(path) {
        // A reassignment of UNKNOWN_PATH is considered equivalent to having lost track
        // which means the return expression needs to be reassigned
        if (path.length === 1 && path[0] === UNKNOWN_KEY) {
            this.scope.getReturnExpression().deoptimizePath(UNKNOWN_PATH);
        }
    }
    getReturnExpressionWhenCalledAtPath(path) {
        return path.length === 0 ? this.scope.getReturnExpression() : UNKNOWN_EXPRESSION;
    }
    hasEffects(_options) {
        return false;
    }
    hasEffectsWhenAccessedAtPath(path, _options) {
        return path.length > 1;
    }
    hasEffectsWhenAssignedAtPath(path, _options) {
        return path.length > 1;
    }
    hasEffectsWhenCalledAtPath(path, _callOptions, options) {
        if (path.length > 0) {
            return true;
        }
        for (const param of this.params) {
            if (param.hasEffects(options))
                return true;
        }
        return this.body.hasEffects(options);
    }
    include(includeChildrenRecursively) {
        this.included = true;
        this.body.include(includeChildrenRecursively);
        for (const param of this.params) {
            if (!(param instanceof Identifier$1)) {
                param.include(includeChildrenRecursively);
            }
        }
    }
    includeCallArguments(args) {
        this.scope.includeCallArguments(args);
    }
    initialise() {
        this.scope.addParameterVariables(this.params.map(param => param.declare('parameter', UNKNOWN_EXPRESSION)), this.params[this.params.length - 1] instanceof RestElement);
        if (this.body instanceof BlockStatement$1) {
            this.body.addImplicitReturnExpressionToScope();
        }
        else {
            this.scope.addReturnExpression(this.body);
        }
    }
    parseNode(esTreeNode) {
        if (esTreeNode.body.type === BlockStatement) {
            this.body = new this.context.nodeConstructors.BlockStatement(esTreeNode.body, this, this.scope.hoistedBodyVarScope);
        }
        super.parseNode(esTreeNode);
    }
}
ArrowFunctionExpression.prototype.preventChildBlockScope = true;

function getSystemExportStatement(exportedVariables) {
    if (exportedVariables.length === 1) {
        return `exports('${exportedVariables[0].safeExportName ||
            exportedVariables[0].exportName}', ${exportedVariables[0].getName()});`;
    }
    else {
        return `exports({${exportedVariables
            .map(variable => `${variable.safeExportName || variable.exportName}: ${variable.getName()}`)
            .join(', ')}});`;
    }
}

class AssignmentExpression extends NodeBase {
    bind() {
        super.bind();
        this.left.deoptimizePath(EMPTY_PATH);
        // We cannot propagate mutations of the new binding to the old binding with certainty
        this.right.deoptimizePath(UNKNOWN_PATH);
    }
    hasEffects(options) {
        return (this.right.hasEffects(options) ||
            this.left.hasEffects(options) ||
            this.left.hasEffectsWhenAssignedAtPath(EMPTY_PATH, options));
    }
    hasEffectsWhenAccessedAtPath(path, options) {
        return path.length > 0 && this.right.hasEffectsWhenAccessedAtPath(path, options);
    }
    render(code, options) {
        this.left.render(code, options);
        this.right.render(code, options);
        if (options.format === 'system') {
            if (this.left.variable && this.left.variable.exportName) {
                code.prependLeft(code.original.indexOf('=', this.left.end) + 1, ` exports('${this.left.variable.exportName}',`);
                code.appendLeft(this.right.end, `)`);
            }
            else if ('addExportedVariables' in this.left) {
                const systemPatternExports = [];
                this.left.addExportedVariables(systemPatternExports);
                if (systemPatternExports.length > 0) {
                    code.prependRight(this.start, `function (v) {${getSystemExportStatement(systemPatternExports)} return v;} (`);
                    code.appendLeft(this.end, ')');
                }
            }
        }
    }
}

class AssignmentPattern extends NodeBase {
    addExportedVariables(variables) {
        this.left.addExportedVariables(variables);
    }
    bind() {
        super.bind();
        this.left.deoptimizePath(EMPTY_PATH);
        this.right.deoptimizePath(UNKNOWN_PATH);
    }
    declare(kind, init) {
        return this.left.declare(kind, init);
    }
    deoptimizePath(path) {
        path.length === 0 && this.left.deoptimizePath(path);
    }
    hasEffectsWhenAssignedAtPath(path, options) {
        return path.length > 0 || this.left.hasEffectsWhenAssignedAtPath(EMPTY_PATH, options);
    }
    render(code, options, { isShorthandProperty } = BLANK) {
        this.left.render(code, options, { isShorthandProperty });
        this.right.render(code, options);
    }
}

class AwaitExpression extends NodeBase {
    hasEffects(options) {
        return super.hasEffects(options) || !options.ignoreReturnAwaitYield();
    }
    include(includeChildrenRecursively) {
        checkTopLevelAwait: if (!this.included && !this.context.usesTopLevelAwait) {
            let parent = this.parent;
            do {
                if (parent instanceof FunctionNode || parent instanceof ArrowFunctionExpression)
                    break checkTopLevelAwait;
            } while ((parent = parent.parent));
            this.context.usesTopLevelAwait = true;
        }
        super.include(includeChildrenRecursively);
    }
    render(code, options) {
        super.render(code, options);
    }
}

const RESULT_KEY$1 = {};
class ImmutableEntityPathTracker {
    constructor(existingEntityPaths = Immutable.Map()) {
        this.entityPaths = existingEntityPaths;
    }
    isTracked(entity, path) {
        return this.entityPaths.getIn([entity, ...path, RESULT_KEY$1]);
    }
    track(entity, path) {
        return new ImmutableEntityPathTracker(this.entityPaths.setIn([entity, ...path, RESULT_KEY$1], true));
    }
}
const EMPTY_IMMUTABLE_TRACKER = new ImmutableEntityPathTracker();

class ExpressionStatement$1 extends NodeBase {
    initialise() {
        if (this.directive &&
            this.directive !== 'use strict' &&
            this.parent.type === Program) {
            this.context.warn(
            // This is necessary, because either way (deleting or not) can lead to errors.
            {
                code: 'MODULE_LEVEL_DIRECTIVE',
                message: `Module level directives cause errors when bundled, '${this.directive}' was ignored.`
            }, this.start);
        }
    }
    render(code, options) {
        super.render(code, options);
        if (this.included)
            this.insertSemicolon(code);
    }
    shouldBeIncluded() {
        if (this.directive && this.directive !== 'use strict')
            return this.parent.type !== Program;
        return super.shouldBeIncluded();
    }
}

const binaryOperators = {
    '!=': (left, right) => left != right,
    '!==': (left, right) => left !== right,
    '%': (left, right) => left % right,
    '&': (left, right) => left & right,
    '*': (left, right) => left * right,
    // At the moment, "**" will be transpiled to Math.pow
    '**': (left, right) => Math.pow(left, right),
    '+': (left, right) => left + right,
    '-': (left, right) => left - right,
    '/': (left, right) => left / right,
    '<': (left, right) => left < right,
    '<<': (left, right) => left << right,
    '<=': (left, right) => left <= right,
    '==': (left, right) => left == right,
    '===': (left, right) => left === right,
    '>': (left, right) => left > right,
    '>=': (left, right) => left >= right,
    '>>': (left, right) => left >> right,
    '>>>': (left, right) => left >>> right,
    '^': (left, right) => left ^ right,
    in: () => UNKNOWN_VALUE,
    instanceof: () => UNKNOWN_VALUE,
    '|': (left, right) => left | right
};
class BinaryExpression extends NodeBase {
    deoptimizeCache() { }
    getLiteralValueAtPath(path, recursionTracker, origin) {
        if (path.length > 0)
            return UNKNOWN_VALUE;
        const leftValue = this.left.getLiteralValueAtPath(EMPTY_PATH, recursionTracker, origin);
        if (leftValue === UNKNOWN_VALUE)
            return UNKNOWN_VALUE;
        const rightValue = this.right.getLiteralValueAtPath(EMPTY_PATH, recursionTracker, origin);
        if (rightValue === UNKNOWN_VALUE)
            return UNKNOWN_VALUE;
        const operatorFn = binaryOperators[this.operator];
        if (!operatorFn)
            return UNKNOWN_VALUE;
        return operatorFn(leftValue, rightValue);
    }
    hasEffects(options) {
        // support some implicit type coercion runtime errors
        if (this.operator === '+' &&
            this.parent instanceof ExpressionStatement$1 &&
            this.left.getLiteralValueAtPath(EMPTY_PATH, EMPTY_IMMUTABLE_TRACKER, this) === '') {
            return true;
        }
        return super.hasEffects(options);
    }
    hasEffectsWhenAccessedAtPath(path, _options) {
        return path.length > 1;
    }
}

class BreakStatement extends NodeBase {
    hasEffects(options) {
        return (super.hasEffects(options) ||
            !options.ignoreBreakStatements() ||
            (this.label !== null && !options.ignoreLabel(this.label.name)));
    }
}

class CallExpression$1 extends NodeBase {
    constructor() {
        super(...arguments);
        // We collect deoptimization information if returnExpression !== UNKNOWN_EXPRESSION
        this.expressionsToBeDeoptimized = [];
        this.returnExpression = null;
    }
    bind() {
        super.bind();
        if (this.callee instanceof Identifier$1) {
            const variable = this.scope.findVariable(this.callee.name);
            if (variable.isNamespace) {
                this.context.error({
                    code: 'CANNOT_CALL_NAMESPACE',
                    message: `Cannot call a namespace ('${this.callee.name}')`
                }, this.start);
            }
            if (this.callee.name === 'eval') {
                this.context.warn({
                    code: 'EVAL',
                    message: `Use of eval is strongly discouraged, as it poses security risks and may cause issues with minification`,
                    url: 'https://rollupjs.org/guide/en/#avoiding-eval'
                }, this.start);
            }
        }
        if (this.returnExpression === null) {
            this.returnExpression = this.callee.getReturnExpressionWhenCalledAtPath(EMPTY_PATH, EMPTY_IMMUTABLE_TRACKER, this);
        }
        for (const argument of this.arguments) {
            // This will make sure all properties of parameters behave as "unknown"
            argument.deoptimizePath(UNKNOWN_PATH);
        }
    }
    deoptimizeCache() {
        if (this.returnExpression !== UNKNOWN_EXPRESSION) {
            this.returnExpression = UNKNOWN_EXPRESSION;
            for (const expression of this.expressionsToBeDeoptimized) {
                expression.deoptimizeCache();
            }
        }
    }
    deoptimizePath(path) {
        if (path.length > 0 && !this.context.deoptimizationTracker.track(this, path)) {
            if (this.returnExpression === null) {
                this.returnExpression = this.callee.getReturnExpressionWhenCalledAtPath(EMPTY_PATH, EMPTY_IMMUTABLE_TRACKER, this);
            }
            this.returnExpression.deoptimizePath(path);
        }
    }
    getLiteralValueAtPath(path, recursionTracker, origin) {
        if (this.returnExpression === null) {
            this.returnExpression = this.callee.getReturnExpressionWhenCalledAtPath(EMPTY_PATH, recursionTracker, this);
        }
        if (this.returnExpression === UNKNOWN_EXPRESSION ||
            recursionTracker.isTracked(this.returnExpression, path)) {
            return UNKNOWN_VALUE;
        }
        this.expressionsToBeDeoptimized.push(origin);
        return this.returnExpression.getLiteralValueAtPath(path, recursionTracker.track(this.returnExpression, path), origin);
    }
    getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin) {
        if (this.returnExpression === null) {
            this.returnExpression = this.callee.getReturnExpressionWhenCalledAtPath(EMPTY_PATH, recursionTracker, this);
        }
        if (this.returnExpression === UNKNOWN_EXPRESSION ||
            recursionTracker.isTracked(this.returnExpression, path)) {
            return UNKNOWN_EXPRESSION;
        }
        this.expressionsToBeDeoptimized.push(origin);
        return this.returnExpression.getReturnExpressionWhenCalledAtPath(path, recursionTracker.track(this.returnExpression, path), origin);
    }
    hasEffects(options) {
        for (const argument of this.arguments) {
            if (argument.hasEffects(options))
                return true;
        }
        if (this.context.annotations && this.annotatedPure)
            return false;
        return (this.callee.hasEffects(options) ||
            this.callee.hasEffectsWhenCalledAtPath(EMPTY_PATH, this.callOptions, options.getHasEffectsWhenCalledOptions()));
    }
    hasEffectsWhenAccessedAtPath(path, options) {
        return (path.length > 0 &&
            !options.hasReturnExpressionBeenAccessedAtPath(path, this) &&
            this.returnExpression.hasEffectsWhenAccessedAtPath(path, options.addAccessedReturnExpressionAtPath(path, this)));
    }
    hasEffectsWhenAssignedAtPath(path, options) {
        return (path.length === 0 ||
            (!options.hasReturnExpressionBeenAssignedAtPath(path, this) &&
                this.returnExpression.hasEffectsWhenAssignedAtPath(path, options.addAssignedReturnExpressionAtPath(path, this))));
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        if (options.hasReturnExpressionBeenCalledAtPath(path, this))
            return false;
        return this.returnExpression.hasEffectsWhenCalledAtPath(path, callOptions, options.addCalledReturnExpressionAtPath(path, this));
    }
    include(includeChildrenRecursively) {
        if (includeChildrenRecursively) {
            super.include(includeChildrenRecursively);
            if (includeChildrenRecursively === INCLUDE_PARAMETERS &&
                this.callee instanceof Identifier$1 &&
                this.callee.variable) {
                this.callee.variable.markCalledFromTryStatement();
            }
        }
        else {
            this.included = true;
            this.callee.include(false);
        }
        this.callee.includeCallArguments(this.arguments);
        if (!this.returnExpression.included) {
            this.returnExpression.include(false);
        }
    }
    initialise() {
        this.callOptions = CallOptions.create({
            args: this.arguments,
            callIdentifier: this,
            withNew: false
        });
    }
    render(code, options, { renderedParentType } = BLANK) {
        this.callee.render(code, options);
        if (this.arguments.length > 0) {
            if (this.arguments[this.arguments.length - 1].included) {
                for (const arg of this.arguments) {
                    arg.render(code, options);
                }
            }
            else {
                let lastIncludedIndex = this.arguments.length - 2;
                while (lastIncludedIndex >= 0 && !this.arguments[lastIncludedIndex].included) {
                    lastIncludedIndex--;
                }
                if (lastIncludedIndex >= 0) {
                    for (let index = 0; index <= lastIncludedIndex; index++) {
                        this.arguments[index].render(code, options);
                    }
                    code.remove(findFirstOccurrenceOutsideComment(code.original, ',', this.arguments[lastIncludedIndex].end), this.end - 1);
                }
                else {
                    code.remove(findFirstOccurrenceOutsideComment(code.original, '(', this.callee.end) + 1, this.end - 1);
                }
            }
        }
        if (renderedParentType === ExpressionStatement &&
            this.callee.type === FunctionExpression) {
            code.appendRight(this.start, '(');
            code.prependLeft(this.end, ')');
        }
    }
}

class CatchScope extends ParameterScope {
    addDeclaration(identifier, context, init = null, isHoisted = false) {
        if (isHoisted) {
            return this.parent.addDeclaration(identifier, context, init, true);
        }
        else {
            return super.addDeclaration(identifier, context, init, false);
        }
    }
}

class CatchClause extends NodeBase {
    createScope(parentScope) {
        this.scope = new CatchScope(parentScope, this.context);
    }
    initialise() {
        if (this.param) {
            this.param.declare('parameter', UNKNOWN_EXPRESSION);
        }
    }
    parseNode(esTreeNode) {
        this.body = new this.context.nodeConstructors.BlockStatement(esTreeNode.body, this, this.scope);
        super.parseNode(esTreeNode);
    }
}
CatchClause.prototype.preventChildBlockScope = true;

class ClassBody extends NodeBase {
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        if (path.length > 0) {
            return true;
        }
        return (this.classConstructor !== null &&
            this.classConstructor.hasEffectsWhenCalledAtPath(EMPTY_PATH, callOptions, options));
    }
    initialise() {
        for (const method of this.body) {
            if (method.kind === 'constructor') {
                this.classConstructor = method;
                return;
            }
        }
        this.classConstructor = null;
    }
}

class ClassExpression extends ClassNode {
}

class MultiExpression {
    constructor(expressions) {
        this.included = false;
        this.expressions = expressions;
    }
    deoptimizePath(path) {
        for (const expression of this.expressions) {
            expression.deoptimizePath(path);
        }
    }
    getLiteralValueAtPath() {
        return UNKNOWN_VALUE;
    }
    getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin) {
        return new MultiExpression(this.expressions.map(expression => expression.getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin)));
    }
    hasEffectsWhenAccessedAtPath(path, options) {
        for (const expression of this.expressions) {
            if (expression.hasEffectsWhenAccessedAtPath(path, options))
                return true;
        }
        return false;
    }
    hasEffectsWhenAssignedAtPath(path, options) {
        for (const expression of this.expressions) {
            if (expression.hasEffectsWhenAssignedAtPath(path, options))
                return true;
        }
        return false;
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        for (const expression of this.expressions) {
            if (expression.hasEffectsWhenCalledAtPath(path, callOptions, options))
                return true;
        }
        return false;
    }
    include() { }
    includeCallArguments(args) {
        for (const expression of this.expressions) {
            expression.includeCallArguments(args);
        }
    }
}

class ConditionalExpression extends NodeBase {
    constructor() {
        super(...arguments);
        // We collect deoptimization information if usedBranch !== null
        this.expressionsToBeDeoptimized = [];
        this.isBranchResolutionAnalysed = false;
        this.unusedBranch = null;
        this.usedBranch = null;
    }
    bind() {
        super.bind();
        if (!this.isBranchResolutionAnalysed)
            this.analyseBranchResolution();
    }
    deoptimizeCache() {
        if (this.usedBranch !== null) {
            // We did not track if there were reassignments to the previous branch.
            // Also, the return value might need to be reassigned.
            this.usedBranch = null;
            this.unusedBranch.deoptimizePath(UNKNOWN_PATH);
            for (const expression of this.expressionsToBeDeoptimized) {
                expression.deoptimizeCache();
            }
        }
    }
    deoptimizePath(path) {
        if (path.length > 0) {
            if (!this.isBranchResolutionAnalysed)
                this.analyseBranchResolution();
            if (this.usedBranch === null) {
                this.consequent.deoptimizePath(path);
                this.alternate.deoptimizePath(path);
            }
            else {
                this.usedBranch.deoptimizePath(path);
            }
        }
    }
    getLiteralValueAtPath(path, recursionTracker, origin) {
        if (!this.isBranchResolutionAnalysed)
            this.analyseBranchResolution();
        if (this.usedBranch === null)
            return UNKNOWN_VALUE;
        this.expressionsToBeDeoptimized.push(origin);
        return this.usedBranch.getLiteralValueAtPath(path, recursionTracker, origin);
    }
    getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin) {
        if (!this.isBranchResolutionAnalysed)
            this.analyseBranchResolution();
        if (this.usedBranch === null)
            return new MultiExpression([
                this.consequent.getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin),
                this.alternate.getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin)
            ]);
        this.expressionsToBeDeoptimized.push(origin);
        return this.usedBranch.getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin);
    }
    hasEffects(options) {
        if (this.test.hasEffects(options))
            return true;
        if (this.usedBranch === null) {
            return this.consequent.hasEffects(options) || this.alternate.hasEffects(options);
        }
        return this.usedBranch.hasEffects(options);
    }
    hasEffectsWhenAccessedAtPath(path, options) {
        if (path.length === 0)
            return false;
        if (this.usedBranch === null) {
            return (this.consequent.hasEffectsWhenAccessedAtPath(path, options) ||
                this.alternate.hasEffectsWhenAccessedAtPath(path, options));
        }
        return this.usedBranch.hasEffectsWhenAccessedAtPath(path, options);
    }
    hasEffectsWhenAssignedAtPath(path, options) {
        if (path.length === 0)
            return true;
        if (this.usedBranch === null) {
            return (this.consequent.hasEffectsWhenAssignedAtPath(path, options) ||
                this.alternate.hasEffectsWhenAssignedAtPath(path, options));
        }
        return this.usedBranch.hasEffectsWhenAssignedAtPath(path, options);
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        if (this.usedBranch === null) {
            return (this.consequent.hasEffectsWhenCalledAtPath(path, callOptions, options) ||
                this.alternate.hasEffectsWhenCalledAtPath(path, callOptions, options));
        }
        return this.usedBranch.hasEffectsWhenCalledAtPath(path, callOptions, options);
    }
    include(includeChildrenRecursively) {
        this.included = true;
        if (includeChildrenRecursively || this.usedBranch === null || this.test.shouldBeIncluded()) {
            this.test.include(includeChildrenRecursively);
            this.consequent.include(includeChildrenRecursively);
            this.alternate.include(includeChildrenRecursively);
        }
        else {
            this.usedBranch.include(includeChildrenRecursively);
        }
    }
    render(code, options, { renderedParentType, isCalleeOfRenderedParent, preventASI } = BLANK) {
        if (!this.test.included) {
            const colonPos = findFirstOccurrenceOutsideComment(code.original, ':', this.consequent.end);
            const inclusionStart = (this.consequent.included
                ? findFirstOccurrenceOutsideComment(code.original, '?', this.test.end)
                : colonPos) + 1;
            if (preventASI) {
                removeLineBreaks(code, inclusionStart, this.usedBranch.start);
            }
            code.remove(this.start, inclusionStart);
            if (this.consequent.included) {
                code.remove(colonPos, this.end);
            }
            removeAnnotations(this, code);
            this.usedBranch.render(code, options, {
                isCalleeOfRenderedParent: renderedParentType
                    ? isCalleeOfRenderedParent
                    : this.parent.callee === this,
                renderedParentType: renderedParentType || this.parent.type
            });
        }
        else {
            super.render(code, options);
        }
    }
    analyseBranchResolution() {
        this.isBranchResolutionAnalysed = true;
        const testValue = this.test.getLiteralValueAtPath(EMPTY_PATH, EMPTY_IMMUTABLE_TRACKER, this);
        if (testValue !== UNKNOWN_VALUE) {
            if (testValue) {
                this.usedBranch = this.consequent;
                this.unusedBranch = this.alternate;
            }
            else {
                this.usedBranch = this.alternate;
                this.unusedBranch = this.consequent;
            }
        }
    }
}

class DoWhileStatement extends NodeBase {
    hasEffects(options) {
        return (this.test.hasEffects(options) || this.body.hasEffects(options.setIgnoreBreakStatements()));
    }
}

class EmptyStatement extends NodeBase {
    hasEffects() {
        return false;
    }
}

class ExportAllDeclaration$1 extends NodeBase {
    hasEffects() {
        return false;
    }
    initialise() {
        this.context.addExport(this);
    }
    render(code, _options, { start, end } = BLANK) {
        code.remove(start, end);
    }
}
ExportAllDeclaration$1.prototype.needsBoundaries = true;

class ExportNamedDeclaration extends NodeBase {
    bind() {
        // Do not bind specifiers
        if (this.declaration !== null)
            this.declaration.bind();
    }
    hasEffects(options) {
        return this.declaration !== null && this.declaration.hasEffects(options);
    }
    initialise() {
        this.context.addExport(this);
    }
    render(code, options, { start, end } = BLANK) {
        if (this.declaration === null) {
            code.remove(start, end);
        }
        else {
            code.remove(this.start, this.declaration.start);
            this.declaration.render(code, options, { start, end });
        }
    }
}
ExportNamedDeclaration.prototype.needsBoundaries = true;

class ForInStatement extends NodeBase {
    bind() {
        this.left.bind();
        this.left.deoptimizePath(EMPTY_PATH);
        this.right.bind();
        this.body.bind();
    }
    createScope(parentScope) {
        this.scope = new BlockScope(parentScope);
    }
    hasEffects(options) {
        return ((this.left &&
            (this.left.hasEffects(options) ||
                this.left.hasEffectsWhenAssignedAtPath(EMPTY_PATH, options))) ||
            (this.right && this.right.hasEffects(options)) ||
            this.body.hasEffects(options.setIgnoreBreakStatements()));
    }
    include(includeChildrenRecursively) {
        this.included = true;
        this.left.includeWithAllDeclaredVariables(includeChildrenRecursively);
        this.left.deoptimizePath(EMPTY_PATH);
        this.right.include(includeChildrenRecursively);
        this.body.include(includeChildrenRecursively);
    }
    render(code, options) {
        this.left.render(code, options, NO_SEMICOLON);
        this.right.render(code, options, NO_SEMICOLON);
        this.body.render(code, options);
    }
}

class ForOfStatement extends NodeBase {
    bind() {
        this.left.bind();
        this.left.deoptimizePath(EMPTY_PATH);
        this.right.bind();
        this.body.bind();
    }
    createScope(parentScope) {
        this.scope = new BlockScope(parentScope);
    }
    hasEffects() {
        // Placeholder until proper Symbol.Iterator support
        return true;
    }
    include(includeChildrenRecursively) {
        this.included = true;
        this.left.includeWithAllDeclaredVariables(includeChildrenRecursively);
        this.left.deoptimizePath(EMPTY_PATH);
        this.right.include(includeChildrenRecursively);
        this.body.include(includeChildrenRecursively);
    }
    render(code, options) {
        this.left.render(code, options, NO_SEMICOLON);
        this.right.render(code, options, NO_SEMICOLON);
        this.body.render(code, options);
    }
}

class ForStatement extends NodeBase {
    createScope(parentScope) {
        this.scope = new BlockScope(parentScope);
    }
    hasEffects(options) {
        return ((this.init && this.init.hasEffects(options)) ||
            (this.test && this.test.hasEffects(options)) ||
            (this.update && this.update.hasEffects(options)) ||
            this.body.hasEffects(options.setIgnoreBreakStatements()));
    }
    render(code, options) {
        if (this.init)
            this.init.render(code, options, NO_SEMICOLON);
        if (this.test)
            this.test.render(code, options, NO_SEMICOLON);
        if (this.update)
            this.update.render(code, options, NO_SEMICOLON);
        this.body.render(code, options);
    }
}

class FunctionExpression$1 extends FunctionNode {
}

class IfStatement extends NodeBase {
    constructor() {
        super(...arguments);
        this.isTestValueAnalysed = false;
    }
    bind() {
        super.bind();
        if (!this.isTestValueAnalysed) {
            this.testValue = UNKNOWN_VALUE;
            this.isTestValueAnalysed = true;
            this.testValue = this.test.getLiteralValueAtPath(EMPTY_PATH, EMPTY_IMMUTABLE_TRACKER, this);
        }
    }
    deoptimizeCache() {
        this.testValue = UNKNOWN_VALUE;
    }
    hasEffects(options) {
        if (this.test.hasEffects(options))
            return true;
        if (this.testValue === UNKNOWN_VALUE) {
            return (this.consequent.hasEffects(options) ||
                (this.alternate !== null && this.alternate.hasEffects(options)));
        }
        return this.testValue
            ? this.consequent.hasEffects(options)
            : this.alternate !== null && this.alternate.hasEffects(options);
    }
    include(includeChildrenRecursively) {
        this.included = true;
        if (includeChildrenRecursively) {
            this.test.include(includeChildrenRecursively);
            this.consequent.include(includeChildrenRecursively);
            if (this.alternate !== null) {
                this.alternate.include(includeChildrenRecursively);
            }
            return;
        }
        const hasUnknownTest = this.testValue === UNKNOWN_VALUE;
        if (hasUnknownTest || this.test.shouldBeIncluded()) {
            this.test.include(false);
        }
        if ((hasUnknownTest || this.testValue) && this.consequent.shouldBeIncluded()) {
            this.consequent.include(false);
        }
        if (this.alternate !== null &&
            ((hasUnknownTest || !this.testValue) && this.alternate.shouldBeIncluded())) {
            this.alternate.include(false);
        }
    }
    render(code, options) {
        // Note that unknown test values are always included
        if (!this.test.included &&
            (this.testValue
                ? this.alternate === null || !this.alternate.included
                : !this.consequent.included)) {
            const singleRetainedBranch = (this.testValue
                ? this.consequent
                : this.alternate);
            code.remove(this.start, singleRetainedBranch.start);
            code.remove(singleRetainedBranch.end, this.end);
            removeAnnotations(this, code);
            singleRetainedBranch.render(code, options);
        }
        else {
            if (this.test.included) {
                this.test.render(code, options);
            }
            else {
                code.overwrite(this.test.start, this.test.end, this.testValue ? 'true' : 'false');
            }
            if (this.consequent.included) {
                this.consequent.render(code, options);
            }
            else {
                code.overwrite(this.consequent.start, this.consequent.end, ';');
            }
            if (this.alternate !== null) {
                if (this.alternate.included) {
                    this.alternate.render(code, options);
                }
                else {
                    code.remove(this.consequent.end, this.alternate.end);
                }
            }
        }
    }
}

class ImportDeclaration extends NodeBase {
    bind() { }
    hasEffects() {
        return false;
    }
    initialise() {
        this.context.addImport(this);
    }
    render(code, _options, { start, end } = BLANK) {
        code.remove(start, end);
    }
}
ImportDeclaration.prototype.needsBoundaries = true;

class Import extends NodeBase {
    constructor() {
        super(...arguments);
        this.exportMode = 'auto';
    }
    hasEffects() {
        return true;
    }
    include(includeChildrenRecursively) {
        if (!this.included) {
            this.included = true;
            this.context.includeDynamicImport(this);
        }
        this.source.include(includeChildrenRecursively);
    }
    initialise() {
        this.context.addDynamicImport(this);
    }
    render(code, options) {
        if (this.inlineNamespace) {
            const _ = options.compact ? '' : ' ';
            const s = options.compact ? '' : ';';
            code.overwrite(this.start, this.end, `Promise.resolve().then(function${_}()${_}{${_}return ${this.inlineNamespace.getName()}${s}${_}})`);
            return;
        }
        const importMechanism = this.getDynamicImportMechanism(options);
        if (importMechanism) {
            code.overwrite(this.start, findFirstOccurrenceOutsideComment(code.original, '(', this.start + 6) + 1, importMechanism.left);
            code.overwrite(this.end - 1, this.end, importMechanism.right);
        }
        this.source.render(code, options);
    }
    renderFinalResolution(code, resolution, format) {
        if (this.included) {
            if (format === 'amd' && resolution.startsWith("'.") && resolution.endsWith(".js'")) {
                resolution = resolution.slice(0, -4) + "'";
            }
            code.overwrite(this.source.start, this.source.end, resolution);
        }
    }
    setResolution(exportMode, inlineNamespace) {
        this.exportMode = exportMode;
        if (inlineNamespace) {
            this.inlineNamespace = inlineNamespace;
        }
        else {
            this.scope.addAccessedGlobalsByFormat({
                amd: ['require'],
                cjs: ['require'],
                system: ['module']
            });
            if (exportMode === 'auto') {
                this.scope.addAccessedGlobalsByFormat({
                    amd: [INTEROP_NAMESPACE_VARIABLE],
                    cjs: [INTEROP_NAMESPACE_VARIABLE]
                });
            }
        }
    }
    getDynamicImportMechanism(options) {
        switch (options.format) {
            case 'cjs': {
                const _ = options.compact ? '' : ' ';
                const resolve = options.compact ? 'c' : 'resolve';
                switch (this.exportMode) {
                    case 'default':
                        return {
                            left: `new Promise(function${_}(${resolve})${_}{${_}${resolve}({${_}'default':${_}require(`,
                            right: `)${_}});${_}})`
                        };
                    case 'auto':
                        return {
                            left: `new Promise(function${_}(${resolve})${_}{${_}${resolve}(${INTEROP_NAMESPACE_VARIABLE}(require(`,
                            right: `)));${_}})`
                        };
                    default:
                        return {
                            left: `new Promise(function${_}(${resolve})${_}{${_}${resolve}(require(`,
                            right: `));${_}})`
                        };
                }
            }
            case 'amd': {
                const _ = options.compact ? '' : ' ';
                const resolve = options.compact ? 'c' : 'resolve';
                const reject = options.compact ? 'e' : 'reject';
                const resolveNamespace = this.exportMode === 'default'
                    ? `function${_}(m)${_}{${_}${resolve}({${_}'default':${_}m${_}});${_}}`
                    : this.exportMode === 'auto'
                        ? `function${_}(m)${_}{${_}${resolve}(${INTEROP_NAMESPACE_VARIABLE}(m));${_}}`
                        : resolve;
                return {
                    left: `new Promise(function${_}(${resolve},${_}${reject})${_}{${_}require([`,
                    right: `],${_}${resolveNamespace},${_}${reject})${_}})`
                };
            }
            case 'system':
                return {
                    left: 'module.import(',
                    right: ')'
                };
            case 'es':
                if (options.dynamicImportFunction) {
                    return {
                        left: `${options.dynamicImportFunction}(`,
                        right: ')'
                    };
                }
        }
        return null;
    }
}

class LabeledStatement extends NodeBase {
    hasEffects(options) {
        return this.body.hasEffects(options.setIgnoreLabel(this.label.name).setIgnoreBreakStatements());
    }
}

class Literal extends NodeBase {
    getLiteralValueAtPath(path) {
        if (path.length > 0 ||
            // unknown literals can also be null but do not start with an "n"
            (this.value === null && this.context.code.charCodeAt(this.start) !== 110) ||
            typeof this.value === 'bigint' ||
            // to support shims for regular expressions
            this.context.code.charCodeAt(this.start) === 47) {
            return UNKNOWN_VALUE;
        }
        return this.value;
    }
    getReturnExpressionWhenCalledAtPath(path) {
        if (path.length !== 1)
            return UNKNOWN_EXPRESSION;
        return getMemberReturnExpressionWhenCalled(this.members, path[0]);
    }
    hasEffectsWhenAccessedAtPath(path) {
        if (this.value === null) {
            return path.length > 0;
        }
        return path.length > 1;
    }
    hasEffectsWhenAssignedAtPath(path) {
        return path.length > 0;
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        if (path.length === 1) {
            return hasMemberEffectWhenCalled(this.members, path[0], this.included, callOptions, options);
        }
        return true;
    }
    initialise() {
        this.members = getLiteralMembersForValue(this.value);
    }
    render(code, _options) {
        if (typeof this.value === 'string') {
            code.indentExclusionRanges.push([this.start + 1, this.end - 1]);
        }
    }
}

class LogicalExpression extends NodeBase {
    constructor() {
        super(...arguments);
        // We collect deoptimization information if usedBranch !== null
        this.expressionsToBeDeoptimized = [];
        this.isBranchResolutionAnalysed = false;
        this.unusedBranch = null;
        this.usedBranch = null;
    }
    bind() {
        super.bind();
        if (!this.isBranchResolutionAnalysed)
            this.analyseBranchResolution();
    }
    deoptimizeCache() {
        if (this.usedBranch !== null) {
            // We did not track if there were reassignments to any of the branches.
            // Also, the return values might need reassignment.
            this.usedBranch = null;
            this.unusedBranch.deoptimizePath(UNKNOWN_PATH);
            for (const expression of this.expressionsToBeDeoptimized) {
                expression.deoptimizeCache();
            }
        }
    }
    deoptimizePath(path) {
        if (path.length > 0) {
            if (!this.isBranchResolutionAnalysed)
                this.analyseBranchResolution();
            if (this.usedBranch === null) {
                this.left.deoptimizePath(path);
                this.right.deoptimizePath(path);
            }
            else {
                this.usedBranch.deoptimizePath(path);
            }
        }
    }
    getLiteralValueAtPath(path, recursionTracker, origin) {
        if (!this.isBranchResolutionAnalysed)
            this.analyseBranchResolution();
        if (this.usedBranch === null)
            return UNKNOWN_VALUE;
        this.expressionsToBeDeoptimized.push(origin);
        return this.usedBranch.getLiteralValueAtPath(path, recursionTracker, origin);
    }
    getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin) {
        if (!this.isBranchResolutionAnalysed)
            this.analyseBranchResolution();
        if (this.usedBranch === null)
            return new MultiExpression([
                this.left.getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin),
                this.right.getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin)
            ]);
        this.expressionsToBeDeoptimized.push(origin);
        return this.usedBranch.getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin);
    }
    hasEffects(options) {
        if (this.usedBranch === null) {
            return this.left.hasEffects(options) || this.right.hasEffects(options);
        }
        return this.usedBranch.hasEffects(options);
    }
    hasEffectsWhenAccessedAtPath(path, options) {
        if (path.length === 0)
            return false;
        if (this.usedBranch === null) {
            return (this.left.hasEffectsWhenAccessedAtPath(path, options) ||
                this.right.hasEffectsWhenAccessedAtPath(path, options));
        }
        return this.usedBranch.hasEffectsWhenAccessedAtPath(path, options);
    }
    hasEffectsWhenAssignedAtPath(path, options) {
        if (path.length === 0)
            return true;
        if (this.usedBranch === null) {
            return (this.left.hasEffectsWhenAssignedAtPath(path, options) ||
                this.right.hasEffectsWhenAssignedAtPath(path, options));
        }
        return this.usedBranch.hasEffectsWhenAssignedAtPath(path, options);
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        if (this.usedBranch === null) {
            return (this.left.hasEffectsWhenCalledAtPath(path, callOptions, options) ||
                this.right.hasEffectsWhenCalledAtPath(path, callOptions, options));
        }
        return this.usedBranch.hasEffectsWhenCalledAtPath(path, callOptions, options);
    }
    include(includeChildrenRecursively) {
        this.included = true;
        if (includeChildrenRecursively ||
            this.usedBranch === null ||
            this.unusedBranch.shouldBeIncluded()) {
            this.left.include(includeChildrenRecursively);
            this.right.include(includeChildrenRecursively);
        }
        else {
            this.usedBranch.include(includeChildrenRecursively);
        }
    }
    render(code, options, { renderedParentType, isCalleeOfRenderedParent, preventASI } = BLANK) {
        if (!this.left.included || !this.right.included) {
            const operatorPos = findFirstOccurrenceOutsideComment(code.original, this.operator, this.left.end);
            if (this.right.included) {
                code.remove(this.start, operatorPos + 2);
                if (preventASI) {
                    removeLineBreaks(code, operatorPos + 2, this.right.start);
                }
            }
            else {
                code.remove(operatorPos, this.end);
            }
            removeAnnotations(this, code);
            this.usedBranch.render(code, options, {
                isCalleeOfRenderedParent: renderedParentType
                    ? isCalleeOfRenderedParent
                    : this.parent.callee === this,
                renderedParentType: renderedParentType || this.parent.type
            });
        }
        else {
            super.render(code, options);
        }
    }
    analyseBranchResolution() {
        this.isBranchResolutionAnalysed = true;
        const leftValue = this.left.getLiteralValueAtPath(EMPTY_PATH, EMPTY_IMMUTABLE_TRACKER, this);
        if (leftValue !== UNKNOWN_VALUE) {
            if (this.operator === '||' ? leftValue : !leftValue) {
                this.usedBranch = this.left;
                this.unusedBranch = this.right;
            }
            else {
                this.usedBranch = this.right;
                this.unusedBranch = this.left;
            }
        }
    }
}

function getResolvablePropertyKey(memberExpression) {
    return memberExpression.computed
        ? getResolvableComputedPropertyKey(memberExpression.property)
        : memberExpression.property.name;
}
function getResolvableComputedPropertyKey(propertyKey) {
    if (propertyKey instanceof Literal) {
        return String(propertyKey.value);
    }
    return null;
}
function getPathIfNotComputed(memberExpression) {
    const nextPathKey = memberExpression.propertyKey;
    const object = memberExpression.object;
    if (typeof nextPathKey === 'string') {
        if (object instanceof Identifier$1) {
            return [
                { key: object.name, pos: object.start },
                { key: nextPathKey, pos: memberExpression.property.start }
            ];
        }
        if (object instanceof MemberExpression) {
            const parentPath = getPathIfNotComputed(object);
            return (parentPath && [...parentPath, { key: nextPathKey, pos: memberExpression.property.start }]);
        }
    }
    return null;
}
function getStringFromPath(path) {
    let pathString = path[0].key;
    for (let index = 1; index < path.length; index++) {
        pathString += '.' + path[index].key;
    }
    return pathString;
}
class MemberExpression extends NodeBase {
    constructor() {
        super(...arguments);
        this.variable = null;
        this.bound = false;
        this.expressionsToBeDeoptimized = [];
        this.replacement = null;
    }
    addExportedVariables() { }
    bind() {
        if (this.bound)
            return;
        this.bound = true;
        const path = getPathIfNotComputed(this);
        const baseVariable = path && this.scope.findVariable(path[0].key);
        if (baseVariable && baseVariable.isNamespace) {
            const resolvedVariable = this.resolveNamespaceVariables(baseVariable, path.slice(1));
            if (!resolvedVariable) {
                super.bind();
            }
            else if (typeof resolvedVariable === 'string') {
                this.replacement = resolvedVariable;
            }
            else {
                if (resolvedVariable instanceof ExternalVariable && resolvedVariable.module) {
                    resolvedVariable.module.suggestName(path[0].key);
                }
                this.variable = resolvedVariable;
                this.scope.addNamespaceMemberAccess(getStringFromPath(path), resolvedVariable);
            }
        }
        else {
            super.bind();
            if (this.propertyKey === null)
                this.analysePropertyKey();
        }
    }
    deoptimizeCache() {
        for (const expression of this.expressionsToBeDeoptimized) {
            expression.deoptimizeCache();
        }
    }
    deoptimizePath(path) {
        if (!this.bound)
            this.bind();
        if (path.length === 0)
            this.disallowNamespaceReassignment();
        if (this.variable) {
            this.variable.deoptimizePath(path);
        }
        else {
            if (this.propertyKey === null)
                this.analysePropertyKey();
            this.object.deoptimizePath([this.propertyKey, ...path]);
        }
    }
    getLiteralValueAtPath(path, recursionTracker, origin) {
        if (!this.bound)
            this.bind();
        if (this.variable !== null) {
            return this.variable.getLiteralValueAtPath(path, recursionTracker, origin);
        }
        if (this.propertyKey === null)
            this.analysePropertyKey();
        this.expressionsToBeDeoptimized.push(origin);
        return this.object.getLiteralValueAtPath([this.propertyKey, ...path], recursionTracker, origin);
    }
    getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin) {
        if (!this.bound)
            this.bind();
        if (this.variable !== null) {
            return this.variable.getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin);
        }
        if (this.propertyKey === null)
            this.analysePropertyKey();
        this.expressionsToBeDeoptimized.push(origin);
        return this.object.getReturnExpressionWhenCalledAtPath([this.propertyKey, ...path], recursionTracker, origin);
    }
    hasEffects(options) {
        return (this.property.hasEffects(options) ||
            this.object.hasEffects(options) ||
            (this.context.propertyReadSideEffects &&
                this.object.hasEffectsWhenAccessedAtPath([this.propertyKey], options)));
    }
    hasEffectsWhenAccessedAtPath(path, options) {
        if (path.length === 0) {
            return false;
        }
        if (this.variable !== null) {
            return this.variable.hasEffectsWhenAccessedAtPath(path, options);
        }
        return this.object.hasEffectsWhenAccessedAtPath([this.propertyKey, ...path], options);
    }
    hasEffectsWhenAssignedAtPath(path, options) {
        if (this.variable !== null) {
            return this.variable.hasEffectsWhenAssignedAtPath(path, options);
        }
        return this.object.hasEffectsWhenAssignedAtPath([this.propertyKey, ...path], options);
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        if (this.variable !== null) {
            return this.variable.hasEffectsWhenCalledAtPath(path, callOptions, options);
        }
        return this.object.hasEffectsWhenCalledAtPath([this.propertyKey, ...path], callOptions, options);
    }
    include(includeChildrenRecursively) {
        if (!this.included) {
            this.included = true;
            if (this.variable !== null) {
                this.context.includeVariable(this.variable);
            }
        }
        this.object.include(includeChildrenRecursively);
        this.property.include(includeChildrenRecursively);
    }
    includeCallArguments(args) {
        if (this.variable) {
            this.variable.includeCallArguments(args);
        }
        else {
            super.includeCallArguments(args);
        }
    }
    initialise() {
        this.propertyKey = getResolvablePropertyKey(this);
    }
    render(code, options, { renderedParentType, isCalleeOfRenderedParent } = BLANK) {
        const isCalleeOfDifferentParent = renderedParentType === CallExpression && isCalleeOfRenderedParent;
        if (this.variable || this.replacement) {
            let replacement = this.variable ? this.variable.getName() : this.replacement;
            if (isCalleeOfDifferentParent)
                replacement = '0, ' + replacement;
            code.overwrite(this.start, this.end, replacement, {
                contentOnly: true,
                storeName: true
            });
        }
        else {
            if (isCalleeOfDifferentParent) {
                code.appendRight(this.start, '0, ');
            }
            super.render(code, options);
        }
    }
    analysePropertyKey() {
        this.propertyKey = UNKNOWN_KEY;
        const value = this.property.getLiteralValueAtPath(EMPTY_PATH, EMPTY_IMMUTABLE_TRACKER, this);
        this.propertyKey = value === UNKNOWN_VALUE ? UNKNOWN_KEY : String(value);
    }
    disallowNamespaceReassignment() {
        if (this.object instanceof Identifier$1 &&
            this.scope.findVariable(this.object.name).isNamespace) {
            this.context.error({
                code: 'ILLEGAL_NAMESPACE_REASSIGNMENT',
                message: `Illegal reassignment to import '${this.object.name}'`
            }, this.start);
        }
    }
    resolveNamespaceVariables(baseVariable, path) {
        if (path.length === 0)
            return baseVariable;
        if (!baseVariable.isNamespace)
            return null;
        const exportName = path[0].key;
        const variable = baseVariable instanceof ExternalVariable
            ? baseVariable.module.getVariableForExportName(exportName)
            : baseVariable.context.traceExport(exportName);
        if (!variable) {
            const fileName = baseVariable instanceof ExternalVariable
                ? baseVariable.module.id
                : baseVariable.context.fileName;
            this.context.warn({
                code: 'MISSING_EXPORT',
                exporter: index.relativeId(fileName),
                importer: index.relativeId(this.context.fileName),
                message: `'${exportName}' is not exported by '${index.relativeId(fileName)}'`,
                missing: exportName,
                url: `https://rollupjs.org/guide/en/#error-name-is-not-exported-by-module`
            }, path[0].pos);
            return 'undefined';
        }
        return this.resolveNamespaceVariables(variable, path.slice(1));
    }
}

const readFile = (file) => new Promise((fulfil, reject) => fs.readFile(file, 'utf-8', (err, contents) => (err ? reject(err) : fulfil(contents))));
function mkdirpath(path$1) {
    const dir = path.dirname(path$1);
    try {
        fs.readdirSync(dir);
    }
    catch (err) {
        mkdirpath(dir);
        try {
            fs.mkdirSync(dir);
        }
        catch (err2) {
            if (err2.code !== 'EEXIST') {
                throw err2;
            }
        }
    }
}
function writeFile(dest, data) {
    return new Promise((fulfil, reject) => {
        mkdirpath(dest);
        fs.writeFile(dest, data, err => {
            if (err) {
                reject(err);
            }
            else {
                fulfil();
            }
        });
    });
}

function getRollupDefaultPlugin(preserveSymlinks) {
    return {
        name: 'Rollup Core',
        resolveId: createResolveId(preserveSymlinks),
        load(id) {
            return readFile(id);
        },
        resolveFileUrl({ relativePath, format }) {
            return relativeUrlMechanisms[format](relativePath);
        },
        resolveImportMeta(prop, { chunkId, format }) {
            const mechanism = importMetaMechanisms[format] && importMetaMechanisms[format](prop, chunkId);
            if (mechanism) {
                return mechanism;
            }
        }
    };
}
function findFile(file, preserveSymlinks) {
    try {
        const stats = fs.lstatSync(file);
        if (!preserveSymlinks && stats.isSymbolicLink())
            return findFile(fs.realpathSync(file), preserveSymlinks);
        if ((preserveSymlinks && stats.isSymbolicLink()) || stats.isFile()) {
            // check case
            const name = path.basename(file);
            const files = fs.readdirSync(path.dirname(file));
            if (files.indexOf(name) !== -1)
                return file;
        }
    }
    catch (err) {
        // suppress
    }
}
function addJsExtensionIfNecessary(file, preserveSymlinks) {
    let found = findFile(file, preserveSymlinks);
    if (found)
        return found;
    found = findFile(file + '.mjs', preserveSymlinks);
    if (found)
        return found;
    found = findFile(file + '.js', preserveSymlinks);
    return found;
}
function createResolveId(preserveSymlinks) {
    return function (source, importer) {
        if (typeof process === 'undefined') {
            error({
                code: 'MISSING_PROCESS',
                message: `It looks like you're using Rollup in a non-Node.js environment. This means you must supply a plugin with custom resolveId and load functions`,
                url: 'https://rollupjs.org/guide/en/#a-simple-example'
            });
        }
        // external modules (non-entry modules that start with neither '.' or '/')
        // are skipped at this stage.
        if (importer !== undefined && !index.isAbsolute(source) && source[0] !== '.')
            return null;
        // `resolve` processes paths from right to left, prepending them until an
        // absolute path is created. Absolute importees therefore shortcircuit the
        // resolve call and require no special handing on our part.
        // See https://nodejs.org/api/path.html#path_path_resolve_paths
        return addJsExtensionIfNecessary(path.resolve(importer ? path.dirname(importer) : path.resolve(), source), preserveSymlinks);
    };
}
const getResolveUrl = (path, URL = 'URL') => `new ${URL}(${path}).href`;
const getUrlFromDocument = (chunkId) => `(document.currentScript && document.currentScript.src || new URL('${chunkId}', document.baseURI).href)`;
const getGenericImportMetaMechanism = (getUrl) => (prop, chunkId) => {
    const urlMechanism = getUrl(chunkId);
    return prop === null ? `({ url: ${urlMechanism} })` : prop === 'url' ? urlMechanism : 'undefined';
};
const importMetaMechanisms = {
    amd: getGenericImportMetaMechanism(() => getResolveUrl(`module.uri, document.baseURI`)),
    cjs: getGenericImportMetaMechanism(chunkId => `(typeof document === 'undefined' ? ${getResolveUrl(`'file:' + __filename`, `(require('u' + 'rl').URL)`)} : ${getUrlFromDocument(chunkId)})`),
    iife: getGenericImportMetaMechanism(chunkId => getUrlFromDocument(chunkId)),
    system: prop => (prop === null ? `module.meta` : `module.meta.${prop}`),
    umd: getGenericImportMetaMechanism(chunkId => `(typeof document === 'undefined' ? ${getResolveUrl(`'file:' + __filename`, `(require('u' + 'rl').URL)`)} : ${getUrlFromDocument(chunkId)})`)
};
const getRelativeUrlFromDocument = (relativePath) => getResolveUrl(`'${relativePath}', document.currentScript && document.currentScript.src || document.baseURI`);
const relativeUrlMechanisms = {
    amd: relativePath => {
        if (relativePath[0] !== '.')
            relativePath = './' + relativePath;
        return getResolveUrl(`require.toUrl('${relativePath}'), document.baseURI`);
    },
    cjs: relativePath => `(typeof document === 'undefined' ? ${getResolveUrl(`'file:' + __dirname + '/${relativePath}'`, `(require('u' + 'rl').URL)`)} : ${getRelativeUrlFromDocument(relativePath)})`,
    es: relativePath => getResolveUrl(`'${relativePath}', import.meta.url`),
    iife: relativePath => getRelativeUrlFromDocument(relativePath),
    system: relativePath => getResolveUrl(`'${relativePath}', module.meta.url`),
    umd: relativePath => `(typeof document === 'undefined' ? ${getResolveUrl(`'file:' + __dirname + '/${relativePath}'`, `(require('u' + 'rl').URL)`)} : ${getRelativeUrlFromDocument(relativePath)})`
};
const accessedMetaUrlGlobals = {
    amd: ['document', 'module', 'URL'],
    cjs: ['document', 'require', 'URL'],
    iife: ['document', 'URL'],
    system: ['module'],
    umd: ['document', 'require', 'URL']
};
const accessedFileUrlGlobals = {
    amd: ['document', 'require', 'URL'],
    cjs: ['document', 'require', 'URL'],
    iife: ['document', 'URL'],
    system: ['module', 'URL'],
    umd: ['document', 'require', 'URL']
};

const ASSET_PREFIX = 'ROLLUP_ASSET_URL_';
const CHUNK_PREFIX = 'ROLLUP_CHUNK_URL_';
const FILE_PREFIX = 'ROLLUP_FILE_URL_';
class MetaProperty extends NodeBase {
    hasEffects() {
        return false;
    }
    hasEffectsWhenAccessedAtPath(path) {
        return path.length > 1;
    }
    include() {
        if (!this.included) {
            this.included = true;
            const parent = this.parent;
            const metaProperty = (this.metaProperty =
                parent instanceof MemberExpression && typeof parent.propertyKey === 'string'
                    ? parent.propertyKey
                    : null);
            if (metaProperty) {
                if (metaProperty === 'url') {
                    this.scope.addAccessedGlobalsByFormat(accessedMetaUrlGlobals);
                }
                else if (metaProperty.startsWith(FILE_PREFIX) ||
                    metaProperty.startsWith(ASSET_PREFIX) ||
                    metaProperty.startsWith(CHUNK_PREFIX)) {
                    this.scope.addAccessedGlobalsByFormat(accessedFileUrlGlobals);
                }
            }
        }
    }
    initialise() {
        if (this.meta.name === 'import') {
            this.context.addImportMeta(this);
        }
    }
    renderFinalMechanism(code, chunkId, format, pluginDriver) {
        if (!this.included)
            return;
        const parent = this.parent;
        const metaProperty = this.metaProperty;
        if (metaProperty &&
            (metaProperty.startsWith(FILE_PREFIX) ||
                metaProperty.startsWith(ASSET_PREFIX) ||
                metaProperty.startsWith(CHUNK_PREFIX))) {
            let referenceId = null;
            let assetReferenceId = null;
            let chunkReferenceId = null;
            let fileName;
            if (metaProperty.startsWith(FILE_PREFIX)) {
                referenceId = metaProperty.substr(FILE_PREFIX.length);
                fileName = this.context.getFileName(referenceId);
            }
            else if (metaProperty.startsWith(ASSET_PREFIX)) {
                this.context.warnDeprecation(`Using the "${ASSET_PREFIX}" prefix to reference files is deprecated. Use the "${FILE_PREFIX}" prefix instead.`, false);
                assetReferenceId = metaProperty.substr(ASSET_PREFIX.length);
                fileName = this.context.getFileName(assetReferenceId);
            }
            else {
                this.context.warnDeprecation(`Using the "${CHUNK_PREFIX}" prefix to reference files is deprecated. Use the "${FILE_PREFIX}" prefix instead.`, false);
                chunkReferenceId = metaProperty.substr(CHUNK_PREFIX.length);
                fileName = this.context.getFileName(chunkReferenceId);
            }
            const relativePath = index.normalize(path.relative(path.dirname(chunkId), fileName));
            let replacement;
            if (assetReferenceId !== null) {
                replacement = pluginDriver.hookFirstSync('resolveAssetUrl', [
                    {
                        assetFileName: fileName,
                        chunkId,
                        format,
                        moduleId: this.context.module.id,
                        relativeAssetPath: relativePath
                    }
                ]);
            }
            if (!replacement) {
                replacement = pluginDriver.hookFirstSync('resolveFileUrl', [
                    {
                        assetReferenceId,
                        chunkId,
                        chunkReferenceId,
                        fileName,
                        format,
                        moduleId: this.context.module.id,
                        referenceId: referenceId || assetReferenceId || chunkReferenceId,
                        relativePath
                    }
                ]);
            }
            code.overwrite(parent.start, parent.end, replacement, { contentOnly: true });
            return;
        }
        const replacement = pluginDriver.hookFirstSync('resolveImportMeta', [
            metaProperty,
            {
                chunkId,
                format,
                moduleId: this.context.module.id
            }
        ]);
        if (typeof replacement === 'string') {
            if (parent instanceof MemberExpression) {
                code.overwrite(parent.start, parent.end, replacement, { contentOnly: true });
            }
            else {
                code.overwrite(this.start, this.end, replacement, { contentOnly: true });
            }
        }
    }
}

class MethodDefinition extends NodeBase {
    hasEffects(options) {
        return this.key.hasEffects(options);
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        return (path.length > 0 || this.value.hasEffectsWhenCalledAtPath(EMPTY_PATH, callOptions, options));
    }
}

class NewExpression extends NodeBase {
    bind() {
        super.bind();
        for (const argument of this.arguments) {
            // This will make sure all properties of parameters behave as "unknown"
            argument.deoptimizePath(UNKNOWN_PATH);
        }
    }
    hasEffects(options) {
        for (const argument of this.arguments) {
            if (argument.hasEffects(options))
                return true;
        }
        if (this.annotatedPure)
            return false;
        return this.callee.hasEffectsWhenCalledAtPath(EMPTY_PATH, this.callOptions, options.getHasEffectsWhenCalledOptions());
    }
    hasEffectsWhenAccessedAtPath(path, _options) {
        return path.length > 1;
    }
    initialise() {
        this.callOptions = CallOptions.create({
            args: this.arguments,
            callIdentifier: this,
            withNew: true
        });
    }
}

class SpreadElement extends NodeBase {
    bind() {
        super.bind();
        // Only properties of properties of the argument could become subject to reassignment
        // This will also reassign the return values of iterators
        this.argument.deoptimizePath([UNKNOWN_KEY, UNKNOWN_KEY]);
    }
}

class ObjectExpression extends NodeBase {
    constructor() {
        super(...arguments);
        this.deoptimizedPaths = new Set();
        // We collect deoptimization information if we can resolve a computed property access
        this.expressionsToBeDeoptimized = new Map();
        this.hasUnknownDeoptimizedProperty = false;
        this.propertyMap = null;
        this.unmatchablePropertiesRead = [];
        this.unmatchablePropertiesWrite = [];
    }
    bind() {
        super.bind();
        if (this.propertyMap === null)
            this.buildPropertyMap();
    }
    // We could also track this per-property but this would quickly become much more complex
    deoptimizeCache() {
        if (!this.hasUnknownDeoptimizedProperty)
            this.deoptimizeAllProperties();
    }
    deoptimizePath(path) {
        if (this.hasUnknownDeoptimizedProperty)
            return;
        if (this.propertyMap === null)
            this.buildPropertyMap();
        if (path.length === 0) {
            this.deoptimizeAllProperties();
            return;
        }
        const key = path[0];
        if (path.length === 1) {
            if (typeof key !== 'string') {
                this.deoptimizeAllProperties();
                return;
            }
            if (!this.deoptimizedPaths.has(key)) {
                this.deoptimizedPaths.add(key);
                // we only deoptimizeCache exact matches as in all other cases,
                // we do not return a literal value or return expression
                const expressionsToBeDeoptimized = this.expressionsToBeDeoptimized.get(key);
                if (expressionsToBeDeoptimized) {
                    for (const expression of expressionsToBeDeoptimized) {
                        expression.deoptimizeCache();
                    }
                }
            }
        }
        const subPath = path.length === 1 ? UNKNOWN_PATH : path.slice(1);
        for (const property of typeof key === 'string'
            ? this.propertyMap[key]
                ? this.propertyMap[key].propertiesRead
                : []
            : this.properties) {
            property.deoptimizePath(subPath);
        }
    }
    getLiteralValueAtPath(path, recursionTracker, origin) {
        if (this.propertyMap === null)
            this.buildPropertyMap();
        const key = path[0];
        if (path.length === 0 ||
            this.hasUnknownDeoptimizedProperty ||
            typeof key !== 'string' ||
            this.deoptimizedPaths.has(key))
            return UNKNOWN_VALUE;
        if (path.length === 1 &&
            !this.propertyMap[key] &&
            !objectMembers[key] &&
            (this.unmatchablePropertiesRead).length === 0) {
            const expressionsToBeDeoptimized = this.expressionsToBeDeoptimized.get(key);
            if (expressionsToBeDeoptimized) {
                expressionsToBeDeoptimized.push(origin);
            }
            else {
                this.expressionsToBeDeoptimized.set(key, [origin]);
            }
            return undefined;
        }
        if (!this.propertyMap[key] ||
            this.propertyMap[key].exactMatchRead === null ||
            this.propertyMap[key].propertiesRead.length > 1) {
            return UNKNOWN_VALUE;
        }
        const expressionsToBeDeoptimized = this.expressionsToBeDeoptimized.get(key);
        if (expressionsToBeDeoptimized) {
            expressionsToBeDeoptimized.push(origin);
        }
        else {
            this.expressionsToBeDeoptimized.set(key, [origin]);
        }
        return this.propertyMap[key]
            .exactMatchRead.getLiteralValueAtPath(path.slice(1), recursionTracker, origin);
    }
    getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin) {
        if (this.propertyMap === null)
            this.buildPropertyMap();
        const key = path[0];
        if (path.length === 0 ||
            this.hasUnknownDeoptimizedProperty ||
            typeof key !== 'string' ||
            this.deoptimizedPaths.has(key))
            return UNKNOWN_EXPRESSION;
        if (path.length === 1 &&
            objectMembers[key] &&
            this.unmatchablePropertiesRead.length === 0 &&
            (!this.propertyMap[key] ||
                this.propertyMap[key].exactMatchRead === null))
            return getMemberReturnExpressionWhenCalled(objectMembers, key);
        if (!this.propertyMap[key] ||
            this.propertyMap[key].exactMatchRead === null ||
            this.propertyMap[key].propertiesRead.length > 1)
            return UNKNOWN_EXPRESSION;
        const expressionsToBeDeoptimized = this.expressionsToBeDeoptimized.get(key);
        if (expressionsToBeDeoptimized) {
            expressionsToBeDeoptimized.push(origin);
        }
        else {
            this.expressionsToBeDeoptimized.set(key, [origin]);
        }
        return this.propertyMap[key]
            .exactMatchRead.getReturnExpressionWhenCalledAtPath(path.slice(1), recursionTracker, origin);
    }
    hasEffectsWhenAccessedAtPath(path, options) {
        if (path.length === 0)
            return false;
        const key = path[0];
        if (path.length > 1 &&
            (this.hasUnknownDeoptimizedProperty ||
                typeof key !== 'string' ||
                this.deoptimizedPaths.has(key) ||
                !this.propertyMap[key] ||
                this.propertyMap[key].exactMatchRead === null))
            return true;
        const subPath = path.slice(1);
        for (const property of typeof key !== 'string'
            ? this.properties
            : this.propertyMap[key]
                ? this.propertyMap[key].propertiesRead
                : []) {
            if (property.hasEffectsWhenAccessedAtPath(subPath, options))
                return true;
        }
        return false;
    }
    hasEffectsWhenAssignedAtPath(path, options) {
        if (path.length === 0)
            return false;
        const key = path[0];
        if (path.length > 1 &&
            (this.hasUnknownDeoptimizedProperty ||
                typeof key !== 'string' ||
                this.deoptimizedPaths.has(key) ||
                !this.propertyMap[key] ||
                this.propertyMap[key].exactMatchRead === null))
            return true;
        const subPath = path.slice(1);
        for (const property of typeof key !== 'string'
            ? this.properties
            : path.length > 1
                ? this.propertyMap[key].propertiesRead
                : this.propertyMap[key]
                    ? this.propertyMap[key].propertiesSet
                    : []) {
            if (property.hasEffectsWhenAssignedAtPath(subPath, options))
                return true;
        }
        return false;
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        const key = path[0];
        if (path.length === 0 ||
            this.hasUnknownDeoptimizedProperty ||
            typeof key !== 'string' ||
            this.deoptimizedPaths.has(key) ||
            (this.propertyMap[key]
                ? !this.propertyMap[key].exactMatchRead
                : path.length > 1 || !objectMembers[key]))
            return true;
        const subPath = path.slice(1);
        for (const property of this.propertyMap[key]
            ? this.propertyMap[key].propertiesRead
            : []) {
            if (property.hasEffectsWhenCalledAtPath(subPath, callOptions, options))
                return true;
        }
        if (path.length === 1 && objectMembers[key])
            return hasMemberEffectWhenCalled(objectMembers, key, this.included, callOptions, options);
        return false;
    }
    render(code, options, { renderedParentType } = BLANK) {
        super.render(code, options);
        if (renderedParentType === ExpressionStatement) {
            code.appendRight(this.start, '(');
            code.prependLeft(this.end, ')');
        }
    }
    buildPropertyMap() {
        this.propertyMap = Object.create(null);
        for (let index = this.properties.length - 1; index >= 0; index--) {
            const property = this.properties[index];
            if (property instanceof SpreadElement) {
                this.unmatchablePropertiesRead.push(property);
                continue;
            }
            const isWrite = property.kind !== 'get';
            const isRead = property.kind !== 'set';
            let key;
            if (property.computed) {
                const keyValue = property.key.getLiteralValueAtPath(EMPTY_PATH, EMPTY_IMMUTABLE_TRACKER, this);
                if (keyValue === UNKNOWN_VALUE) {
                    if (isRead) {
                        this.unmatchablePropertiesRead.push(property);
                    }
                    else {
                        this.unmatchablePropertiesWrite.push(property);
                    }
                    continue;
                }
                key = String(keyValue);
            }
            else if (property.key instanceof Identifier$1) {
                key = property.key.name;
            }
            else {
                key = String(property.key.value);
            }
            const propertyMapProperty = this.propertyMap[key];
            if (!propertyMapProperty) {
                this.propertyMap[key] = {
                    exactMatchRead: isRead ? property : null,
                    exactMatchWrite: isWrite ? property : null,
                    propertiesRead: isRead ? [property, ...this.unmatchablePropertiesRead] : [],
                    propertiesSet: isWrite && !isRead ? [property, ...this.unmatchablePropertiesWrite] : []
                };
                continue;
            }
            if (isRead && propertyMapProperty.exactMatchRead === null) {
                propertyMapProperty.exactMatchRead = property;
                propertyMapProperty.propertiesRead.push(property, ...this.unmatchablePropertiesRead);
            }
            if (isWrite && !isRead && propertyMapProperty.exactMatchWrite === null) {
                propertyMapProperty.exactMatchWrite = property;
                propertyMapProperty.propertiesSet.push(property, ...this.unmatchablePropertiesWrite);
            }
        }
    }
    deoptimizeAllProperties() {
        this.hasUnknownDeoptimizedProperty = true;
        for (const property of this.properties) {
            property.deoptimizePath(UNKNOWN_PATH);
        }
        for (const expressionsToBeDeoptimized of this.expressionsToBeDeoptimized.values()) {
            for (const expression of expressionsToBeDeoptimized) {
                expression.deoptimizeCache();
            }
        }
    }
}

class ObjectPattern extends NodeBase {
    addExportedVariables(variables) {
        for (const property of this.properties) {
            if (property.type === Property) {
                property.value.addExportedVariables(variables);
            }
            else {
                property.argument.addExportedVariables(variables);
            }
        }
    }
    declare(kind, init) {
        const variables = [];
        for (const property of this.properties) {
            variables.push(...property.declare(kind, init));
        }
        return variables;
    }
    deoptimizePath(path) {
        if (path.length === 0) {
            for (const property of this.properties) {
                property.deoptimizePath(path);
            }
        }
    }
    hasEffectsWhenAssignedAtPath(path, options) {
        if (path.length > 0)
            return true;
        for (const property of this.properties) {
            if (property.hasEffectsWhenAssignedAtPath(EMPTY_PATH, options))
                return true;
        }
        return false;
    }
}

class Program$1 extends NodeBase {
    hasEffects(options) {
        for (const node of this.body) {
            if (node.hasEffects(options))
                return true;
        }
        return false;
    }
    include(includeChildrenRecursively) {
        this.included = true;
        for (const node of this.body) {
            if (includeChildrenRecursively || node.shouldBeIncluded()) {
                node.include(includeChildrenRecursively);
            }
        }
    }
    render(code, options) {
        if (this.body.length) {
            renderStatementList(this.body, code, this.start, this.end, options);
        }
        else {
            super.render(code, options);
        }
    }
}

class Property$1 extends NodeBase {
    constructor() {
        super(...arguments);
        this.declarationInit = null;
        this.returnExpression = null;
    }
    bind() {
        super.bind();
        if (this.kind === 'get' && this.returnExpression === null)
            this.updateReturnExpression();
        if (this.declarationInit !== null) {
            this.declarationInit.deoptimizePath([UNKNOWN_KEY, UNKNOWN_KEY]);
        }
    }
    declare(kind, init) {
        this.declarationInit = init;
        return this.value.declare(kind, UNKNOWN_EXPRESSION);
    }
    deoptimizeCache() {
        // As getter properties directly receive their values from function expressions that always
        // have a fixed return value, there is no known situation where a getter is deoptimized.
        throw new Error('Unexpected deoptimization');
    }
    deoptimizePath(path) {
        if (this.kind === 'get') {
            if (path.length > 0) {
                if (this.returnExpression === null)
                    this.updateReturnExpression();
                this.returnExpression.deoptimizePath(path);
            }
        }
        else if (this.kind !== 'set') {
            this.value.deoptimizePath(path);
        }
    }
    getLiteralValueAtPath(path, recursionTracker, origin) {
        if (this.kind === 'set') {
            return UNKNOWN_VALUE;
        }
        if (this.kind === 'get') {
            if (this.returnExpression === null)
                this.updateReturnExpression();
            return this.returnExpression.getLiteralValueAtPath(path, recursionTracker, origin);
        }
        return this.value.getLiteralValueAtPath(path, recursionTracker, origin);
    }
    getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin) {
        if (this.kind === 'set') {
            return UNKNOWN_EXPRESSION;
        }
        if (this.kind === 'get') {
            if (this.returnExpression === null)
                this.updateReturnExpression();
            return this.returnExpression.getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin);
        }
        return this.value.getReturnExpressionWhenCalledAtPath(path, recursionTracker, origin);
    }
    hasEffects(options) {
        return this.key.hasEffects(options) || this.value.hasEffects(options);
    }
    hasEffectsWhenAccessedAtPath(path, options) {
        if (this.kind === 'get') {
            return (this.value.hasEffectsWhenCalledAtPath(EMPTY_PATH, this.accessorCallOptions, options.getHasEffectsWhenCalledOptions()) ||
                (path.length > 0 &&
                    this.returnExpression.hasEffectsWhenAccessedAtPath(path, options)));
        }
        return this.value.hasEffectsWhenAccessedAtPath(path, options);
    }
    hasEffectsWhenAssignedAtPath(path, options) {
        if (this.kind === 'get') {
            return (path.length === 0 ||
                this.returnExpression.hasEffectsWhenAssignedAtPath(path, options));
        }
        if (this.kind === 'set') {
            return (path.length > 0 ||
                this.value.hasEffectsWhenCalledAtPath(EMPTY_PATH, this.accessorCallOptions, options.getHasEffectsWhenCalledOptions()));
        }
        return this.value.hasEffectsWhenAssignedAtPath(path, options);
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        if (this.kind === 'get') {
            return this.returnExpression.hasEffectsWhenCalledAtPath(path, callOptions, options);
        }
        return this.value.hasEffectsWhenCalledAtPath(path, callOptions, options);
    }
    initialise() {
        this.accessorCallOptions = CallOptions.create({
            callIdentifier: this,
            withNew: false
        });
    }
    render(code, options) {
        if (!this.shorthand) {
            this.key.render(code, options);
        }
        this.value.render(code, options, { isShorthandProperty: this.shorthand });
    }
    updateReturnExpression() {
        this.returnExpression = UNKNOWN_EXPRESSION;
        this.returnExpression = this.value.getReturnExpressionWhenCalledAtPath(EMPTY_PATH, EMPTY_IMMUTABLE_TRACKER, this);
    }
}

class ReturnStatement$1 extends NodeBase {
    hasEffects(options) {
        return (!options.ignoreReturnAwaitYield() ||
            (this.argument !== null && this.argument.hasEffects(options)));
    }
    initialise() {
        this.scope.addReturnExpression(this.argument || UNKNOWN_EXPRESSION);
    }
    render(code, options) {
        if (this.argument) {
            this.argument.render(code, options, { preventASI: true });
            if (this.argument.start === this.start + 6 /* 'return'.length */) {
                code.prependLeft(this.start + 6, ' ');
            }
        }
    }
}

class SequenceExpression extends NodeBase {
    deoptimizePath(path) {
        if (path.length > 0)
            this.expressions[this.expressions.length - 1].deoptimizePath(path);
    }
    getLiteralValueAtPath(path, recursionTracker, origin) {
        return this.expressions[this.expressions.length - 1].getLiteralValueAtPath(path, recursionTracker, origin);
    }
    hasEffects(options) {
        for (const expression of this.expressions) {
            if (expression.hasEffects(options))
                return true;
        }
        return false;
    }
    hasEffectsWhenAccessedAtPath(path, options) {
        return (path.length > 0 &&
            this.expressions[this.expressions.length - 1].hasEffectsWhenAccessedAtPath(path, options));
    }
    hasEffectsWhenAssignedAtPath(path, options) {
        return (path.length === 0 ||
            this.expressions[this.expressions.length - 1].hasEffectsWhenAssignedAtPath(path, options));
    }
    hasEffectsWhenCalledAtPath(path, callOptions, options) {
        return this.expressions[this.expressions.length - 1].hasEffectsWhenCalledAtPath(path, callOptions, options);
    }
    include(includeChildrenRecursively) {
        this.included = true;
        for (let i = 0; i < this.expressions.length - 1; i++) {
            const node = this.expressions[i];
            if (includeChildrenRecursively || node.shouldBeIncluded())
                node.include(includeChildrenRecursively);
        }
        this.expressions[this.expressions.length - 1].include(includeChildrenRecursively);
    }
    render(code, options, { renderedParentType, isCalleeOfRenderedParent, preventASI } = BLANK) {
        let includedNodes = 0;
        for (const { node, start, end } of getCommaSeparatedNodesWithBoundaries(this.expressions, code, this.start, this.end)) {
            if (!node.included) {
                treeshakeNode(node, code, start, end);
                continue;
            }
            includedNodes++;
            if (includedNodes === 1 && preventASI) {
                removeLineBreaks(code, start, node.start);
            }
            if (node === this.expressions[this.expressions.length - 1] && includedNodes === 1) {
                node.render(code, options, {
                    isCalleeOfRenderedParent: renderedParentType
                        ? isCalleeOfRenderedParent
                        : this.parent.callee === this,
                    renderedParentType: renderedParentType || this.parent.type
                });
            }
            else {
                node.render(code, options);
            }
        }
    }
}

class SwitchCase extends NodeBase {
    include(includeChildrenRecursively) {
        this.included = true;
        if (this.test)
            this.test.include(includeChildrenRecursively);
        for (const node of this.consequent) {
            if (includeChildrenRecursively || node.shouldBeIncluded())
                node.include(includeChildrenRecursively);
        }
    }
    render(code, options) {
        if (this.consequent.length) {
            this.test && this.test.render(code, options);
            const testEnd = this.test
                ? this.test.end
                : findFirstOccurrenceOutsideComment(code.original, 'default', this.start) + 7;
            const consequentStart = findFirstOccurrenceOutsideComment(code.original, ':', testEnd) + 1;
            renderStatementList(this.consequent, code, consequentStart, this.end, options);
        }
        else {
            super.render(code, options);
        }
    }
}

class SwitchStatement extends NodeBase {
    createScope(parentScope) {
        this.scope = new BlockScope(parentScope);
    }
    hasEffects(options) {
        return super.hasEffects(options.setIgnoreBreakStatements());
    }
}

class TaggedTemplateExpression extends NodeBase {
    bind() {
        super.bind();
        if (this.tag.type === Identifier) {
            const variable = this.scope.findVariable(this.tag.name);
            if (variable.isNamespace) {
                this.context.error({
                    code: 'CANNOT_CALL_NAMESPACE',
                    message: `Cannot call a namespace ('${this.tag.name}')`
                }, this.start);
            }
            if (this.tag.name === 'eval') {
                this.context.warn({
                    code: 'EVAL',
                    message: `Use of eval is strongly discouraged, as it poses security risks and may cause issues with minification`,
                    url: 'https://rollupjs.org/guide/en/#avoiding-eval'
                }, this.start);
            }
        }
    }
    hasEffects(options) {
        return (super.hasEffects(options) ||
            this.tag.hasEffectsWhenCalledAtPath(EMPTY_PATH, this.callOptions, options.getHasEffectsWhenCalledOptions()));
    }
    initialise() {
        this.callOptions = CallOptions.create({
            callIdentifier: this,
            withNew: false
        });
    }
}

class TemplateElement extends NodeBase {
    hasEffects(_options) {
        return false;
    }
}

class TemplateLiteral extends NodeBase {
    getLiteralValueAtPath(path) {
        if (path.length > 0 || this.quasis.length !== 1) {
            return UNKNOWN_VALUE;
        }
        return this.quasis[0].value.cooked;
    }
    render(code, options) {
        code.indentExclusionRanges.push([this.start, this.end]);
        super.render(code, options);
    }
}

class ModuleScope extends ChildScope {
    constructor(parent, context) {
        super(parent);
        this.context = context;
        this.variables.set('this', new LocalVariable('this', null, UNDEFINED_EXPRESSION, context));
    }
    addExportDefaultDeclaration(name, exportDefaultDeclaration, context) {
        const variable = new ExportDefaultVariable(name, exportDefaultDeclaration, context);
        this.variables.set('default', variable);
        return variable;
    }
    addNamespaceMemberAccess(_name, variable) {
        if (variable instanceof GlobalVariable) {
            this.accessedOutsideVariables.set(variable.name, variable);
        }
    }
    deconflict(format) {
        // all module level variables are already deconflicted when deconflicting the chunk
        for (const scope of this.children)
            scope.deconflict(format);
    }
    findLexicalBoundary() {
        return this;
    }
    findVariable(name) {
        const knownVariable = this.variables.get(name) || this.accessedOutsideVariables.get(name);
        if (knownVariable) {
            return knownVariable;
        }
        const variable = this.context.traceVariable(name) || this.parent.findVariable(name);
        if (variable instanceof GlobalVariable) {
            this.accessedOutsideVariables.set(name, variable);
        }
        return variable;
    }
}

class ThisExpression extends NodeBase {
    bind() {
        super.bind();
        this.variable = this.scope.findVariable('this');
    }
    hasEffectsWhenAccessedAtPath(path, options) {
        return path.length > 0 && this.variable.hasEffectsWhenAccessedAtPath(path, options);
    }
    hasEffectsWhenAssignedAtPath(path, options) {
        return this.variable.hasEffectsWhenAssignedAtPath(path, options);
    }
    initialise() {
        this.alias =
            this.scope.findLexicalBoundary() instanceof ModuleScope ? this.context.moduleContext : null;
        if (this.alias === 'undefined') {
            this.context.warn({
                code: 'THIS_IS_UNDEFINED',
                message: `The 'this' keyword is equivalent to 'undefined' at the top level of an ES module, and has been rewritten`,
                url: `https://rollupjs.org/guide/en/#error-this-is-undefined`
            }, this.start);
        }
    }
    render(code, _options) {
        if (this.alias !== null) {
            code.overwrite(this.start, this.end, this.alias, {
                contentOnly: false,
                storeName: true
            });
        }
    }
}

class ThrowStatement extends NodeBase {
    hasEffects(_options) {
        return true;
    }
    render(code, options) {
        this.argument.render(code, options, { preventASI: true });
    }
}

class TryStatement extends NodeBase {
    constructor() {
        super(...arguments);
        this.directlyIncluded = false;
    }
    hasEffects(options) {
        return (this.block.body.length > 0 ||
            (this.handler !== null && this.handler.hasEffects(options)) ||
            (this.finalizer !== null && this.finalizer.hasEffects(options)));
    }
    include(includeChildrenRecursively) {
        if (!this.directlyIncluded || !this.context.tryCatchDeoptimization) {
            this.included = true;
            this.directlyIncluded = true;
            this.block.include(this.context.tryCatchDeoptimization ? INCLUDE_PARAMETERS : includeChildrenRecursively);
        }
        if (this.handler !== null) {
            this.handler.include(includeChildrenRecursively);
        }
        if (this.finalizer !== null) {
            this.finalizer.include(includeChildrenRecursively);
        }
    }
}

const unaryOperators = {
    '!': value => !value,
    '+': value => +value,
    '-': value => -value,
    delete: () => UNKNOWN_VALUE,
    typeof: value => typeof value,
    void: () => undefined,
    '~': value => ~value
};
class UnaryExpression extends NodeBase {
    bind() {
        super.bind();
        if (this.operator === 'delete') {
            this.argument.deoptimizePath(EMPTY_PATH);
        }
    }
    getLiteralValueAtPath(path, recursionTracker, origin) {
        if (path.length > 0)
            return UNKNOWN_VALUE;
        const argumentValue = this.argument.getLiteralValueAtPath(EMPTY_PATH, recursionTracker, origin);
        if (argumentValue === UNKNOWN_VALUE)
            return UNKNOWN_VALUE;
        return unaryOperators[this.operator](argumentValue);
    }
    hasEffects(options) {
        if (this.operator === 'typeof' && this.argument instanceof Identifier$1)
            return false;
        return (this.argument.hasEffects(options) ||
            (this.operator === 'delete' &&
                this.argument.hasEffectsWhenAssignedAtPath(EMPTY_PATH, options)));
    }
    hasEffectsWhenAccessedAtPath(path, _options) {
        if (this.operator === 'void') {
            return path.length > 0;
        }
        return path.length > 1;
    }
}

class UnknownNode extends NodeBase {
    hasEffects(_options) {
        return true;
    }
    include() {
        super.include(true);
    }
}

class UpdateExpression extends NodeBase {
    bind() {
        super.bind();
        this.argument.deoptimizePath(EMPTY_PATH);
        if (this.argument instanceof Identifier$1) {
            const variable = this.scope.findVariable(this.argument.name);
            variable.isReassigned = true;
        }
    }
    hasEffects(options) {
        return (this.argument.hasEffects(options) ||
            this.argument.hasEffectsWhenAssignedAtPath(EMPTY_PATH, options));
    }
    hasEffectsWhenAccessedAtPath(path, _options) {
        return path.length > 1;
    }
    render(code, options) {
        this.argument.render(code, options);
        const variable = this.argument.variable;
        if (options.format === 'system' && variable && variable.exportName) {
            const name = variable.getName();
            if (this.prefix) {
                code.overwrite(this.start, this.end, `exports('${variable.exportName}', ${this.operator}${name})`);
            }
            else {
                let op;
                switch (this.operator) {
                    case '++':
                        op = `${name} + 1`;
                        break;
                    case '--':
                        op = `${name} - 1`;
                        break;
                }
                code.overwrite(this.start, this.end, `(exports('${variable.exportName}', ${op}), ${name}${this.operator})`);
            }
        }
    }
}

function isReassignedExportsMember(variable) {
    return variable.renderBaseName !== null && variable.exportName !== null && variable.isReassigned;
}
function areAllDeclarationsIncludedAndNotExported(declarations) {
    for (const declarator of declarations) {
        if (!declarator.included) {
            return false;
        }
        if (declarator.id.type === Identifier) {
            if (declarator.id.variable.exportName)
                return false;
        }
        else {
            const exportedVariables = [];
            declarator.id.addExportedVariables(exportedVariables);
            if (exportedVariables.length > 0)
                return false;
        }
    }
    return true;
}
class VariableDeclaration$1 extends NodeBase {
    deoptimizePath(_path) {
        for (const declarator of this.declarations) {
            declarator.deoptimizePath(EMPTY_PATH);
        }
    }
    hasEffectsWhenAssignedAtPath(_path, _options) {
        return false;
    }
    include(includeChildrenRecursively) {
        this.included = true;
        for (const declarator of this.declarations) {
            if (includeChildrenRecursively || declarator.shouldBeIncluded())
                declarator.include(includeChildrenRecursively);
        }
    }
    includeWithAllDeclaredVariables(includeChildrenRecursively) {
        this.included = true;
        for (const declarator of this.declarations) {
            declarator.include(includeChildrenRecursively);
        }
    }
    initialise() {
        for (const declarator of this.declarations) {
            declarator.declareDeclarator(this.kind);
        }
    }
    render(code, options, nodeRenderOptions = BLANK) {
        if (areAllDeclarationsIncludedAndNotExported(this.declarations)) {
            for (const declarator of this.declarations) {
                declarator.render(code, options);
            }
            if (!nodeRenderOptions.isNoStatement &&
                code.original.charCodeAt(this.end - 1) !== 59 /*";"*/) {
                code.appendLeft(this.end, ';');
            }
        }
        else {
            this.renderReplacedDeclarations(code, options, nodeRenderOptions);
        }
    }
    renderDeclarationEnd(code, separatorString, lastSeparatorPos, actualContentEnd, renderedContentEnd, addSemicolon, systemPatternExports) {
        if (code.original.charCodeAt(this.end - 1) === 59 /*";"*/) {
            code.remove(this.end - 1, this.end);
        }
        if (addSemicolon) {
            separatorString += ';';
        }
        if (lastSeparatorPos !== null) {
            if (code.original.charCodeAt(actualContentEnd - 1) === 10 /*"\n"*/ &&
                (code.original.charCodeAt(this.end) === 10 /*"\n"*/ ||
                    code.original.charCodeAt(this.end) === 13) /*"\r"*/) {
                actualContentEnd--;
                if (code.original.charCodeAt(actualContentEnd) === 13 /*"\r"*/) {
                    actualContentEnd--;
                }
            }
            if (actualContentEnd === lastSeparatorPos + 1) {
                code.overwrite(lastSeparatorPos, renderedContentEnd, separatorString);
            }
            else {
                code.overwrite(lastSeparatorPos, lastSeparatorPos + 1, separatorString);
                code.remove(actualContentEnd, renderedContentEnd);
            }
        }
        else {
            code.appendLeft(renderedContentEnd, separatorString);
        }
        if (systemPatternExports.length > 0) {
            code.appendLeft(renderedContentEnd, ' ' + getSystemExportStatement(systemPatternExports));
        }
    }
    renderReplacedDeclarations(code, options, { start = this.start, end = this.end, isNoStatement }) {
        const separatedNodes = getCommaSeparatedNodesWithBoundaries(this.declarations, code, this.start + this.kind.length, this.end - (code.original.charCodeAt(this.end - 1) === 59 /*";"*/ ? 1 : 0));
        let actualContentEnd, renderedContentEnd;
        if (/\n\s*$/.test(code.slice(this.start, separatedNodes[0].start))) {
            renderedContentEnd = this.start + this.kind.length;
        }
        else {
            renderedContentEnd = separatedNodes[0].start;
        }
        let lastSeparatorPos = renderedContentEnd - 1;
        code.remove(this.start, lastSeparatorPos);
        let isInDeclaration = false;
        let hasRenderedContent = false;
        let separatorString = '', leadingString, nextSeparatorString;
        const systemPatternExports = [];
        for (const { node, start, separator, contentEnd, end } of separatedNodes) {
            if (!node.included ||
                (node.id instanceof Identifier$1 &&
                    isReassignedExportsMember(node.id.variable) &&
                    node.init === null)) {
                code.remove(start, end);
                continue;
            }
            leadingString = '';
            nextSeparatorString = '';
            if (node.id instanceof Identifier$1 &&
                isReassignedExportsMember(node.id.variable)) {
                if (hasRenderedContent) {
                    separatorString += ';';
                }
                isInDeclaration = false;
            }
            else {
                if (options.format === 'system' && node.init !== null) {
                    if (node.id.type !== Identifier) {
                        node.id.addExportedVariables(systemPatternExports);
                    }
                    else if (node.id.variable.exportName) {
                        code.prependLeft(code.original.indexOf('=', node.id.end) + 1, ` exports('${node.id.variable.safeExportName ||
                            node.id.variable.exportName}',`);
                        nextSeparatorString += ')';
                    }
                }
                if (isInDeclaration) {
                    separatorString += ',';
                }
                else {
                    if (hasRenderedContent) {
                        separatorString += ';';
                    }
                    leadingString += `${this.kind} `;
                    isInDeclaration = true;
                }
            }
            if (renderedContentEnd === lastSeparatorPos + 1) {
                code.overwrite(lastSeparatorPos, renderedContentEnd, separatorString + leadingString);
            }
            else {
                code.overwrite(lastSeparatorPos, lastSeparatorPos + 1, separatorString);
                code.appendLeft(renderedContentEnd, leadingString);
            }
            node.render(code, options);
            actualContentEnd = contentEnd;
            renderedContentEnd = end;
            hasRenderedContent = true;
            lastSeparatorPos = separator;
            separatorString = nextSeparatorString;
        }
        if (hasRenderedContent) {
            this.renderDeclarationEnd(code, separatorString, lastSeparatorPos, actualContentEnd, renderedContentEnd, !isNoStatement, systemPatternExports);
        }
        else {
            code.remove(start, end);
        }
    }
}

class VariableDeclarator extends NodeBase {
    declareDeclarator(kind) {
        this.id.declare(kind, this.init || UNDEFINED_EXPRESSION);
    }
    deoptimizePath(path) {
        this.id.deoptimizePath(path);
    }
    render(code, options) {
        // This can happen for hoisted variables in dead branches
        if (this.init !== null && !this.init.included) {
            code.remove(this.id.end, this.end);
            this.id.render(code, options);
        }
        else {
            super.render(code, options);
        }
    }
}

class WhileStatement extends NodeBase {
    hasEffects(options) {
        return (this.test.hasEffects(options) || this.body.hasEffects(options.setIgnoreBreakStatements()));
    }
}

class YieldExpression extends NodeBase {
    bind() {
        super.bind();
        if (this.argument !== null) {
            this.argument.deoptimizePath(UNKNOWN_PATH);
        }
    }
    hasEffects(options) {
        return (!options.ignoreReturnAwaitYield() ||
            (this.argument !== null && this.argument.hasEffects(options)));
    }
    render(code, options) {
        if (this.argument) {
            this.argument.render(code, options);
            if (this.argument.start === this.start + 5 /* 'yield'.length */) {
                code.prependLeft(this.start + 5, ' ');
            }
        }
    }
}

const nodeConstructors = {
    ArrayExpression,
    ArrayPattern,
    ArrowFunctionExpression,
    AssignmentExpression,
    AssignmentPattern,
    AwaitExpression,
    BinaryExpression,
    BlockStatement: BlockStatement$1,
    BreakStatement,
    CallExpression: CallExpression$1,
    CatchClause,
    ClassBody,
    ClassDeclaration,
    ClassExpression,
    ConditionalExpression,
    DoWhileStatement,
    EmptyStatement,
    ExportAllDeclaration: ExportAllDeclaration$1,
    ExportDefaultDeclaration,
    ExportNamedDeclaration,
    ExpressionStatement: ExpressionStatement$1,
    ForInStatement,
    ForOfStatement,
    ForStatement,
    FunctionDeclaration,
    FunctionExpression: FunctionExpression$1,
    Identifier: Identifier$1,
    IfStatement,
    ImportDeclaration,
    ImportExpression: Import,
    LabeledStatement,
    Literal,
    LogicalExpression,
    MemberExpression,
    MetaProperty,
    MethodDefinition,
    NewExpression,
    ObjectExpression,
    ObjectPattern,
    Program: Program$1,
    Property: Property$1,
    RestElement,
    ReturnStatement: ReturnStatement$1,
    SequenceExpression,
    SpreadElement,
    SwitchCase,
    SwitchStatement,
    TaggedTemplateExpression,
    TemplateElement,
    TemplateLiteral,
    ThisExpression,
    ThrowStatement,
    TryStatement,
    UnaryExpression,
    UnknownNode,
    UpdateExpression,
    VariableDeclaration: VariableDeclaration$1,
    VariableDeclarator,
    WhileStatement,
    YieldExpression
};

function getOriginalLocation(sourcemapChain, location) {
    // This cast is guaranteed. If it were a missing Map, it wouldn't have a mappings.
    const filteredSourcemapChain = sourcemapChain.filter(sourcemap => sourcemap.mappings);
    while (filteredSourcemapChain.length > 0) {
        const sourcemap = filteredSourcemapChain.pop();
        const line = sourcemap.mappings[location.line - 1];
        let locationFound = false;
        if (line !== undefined) {
            for (const segment of line) {
                if (segment[0] >= location.column) {
                    if (segment.length === 1)
                        break;
                    location = {
                        column: segment[3],
                        line: segment[2] + 1,
                        name: segment.length === 5 ? sourcemap.names[segment[4]] : undefined,
                        source: sourcemap.sources[segment[1]]
                    };
                    locationFound = true;
                    break;
                }
            }
        }
        if (!locationFound) {
            throw new Error("Can't resolve original location of error.");
        }
    }
    return location;
}

// AST walker module for Mozilla Parser API compatible trees

function skipThrough(node, st, c) { c(node, st); }
function ignore(_node, _st, _c) {}

// Node walkers.

var base$1 = {};

base$1.Program = base$1.BlockStatement = function (node, st, c) {
  for (var i = 0, list = node.body; i < list.length; i += 1)
    {
    var stmt = list[i];

    c(stmt, st, "Statement");
  }
};
base$1.Statement = skipThrough;
base$1.EmptyStatement = ignore;
base$1.ExpressionStatement = base$1.ParenthesizedExpression =
  function (node, st, c) { return c(node.expression, st, "Expression"); };
base$1.IfStatement = function (node, st, c) {
  c(node.test, st, "Expression");
  c(node.consequent, st, "Statement");
  if (node.alternate) { c(node.alternate, st, "Statement"); }
};
base$1.LabeledStatement = function (node, st, c) { return c(node.body, st, "Statement"); };
base$1.BreakStatement = base$1.ContinueStatement = ignore;
base$1.WithStatement = function (node, st, c) {
  c(node.object, st, "Expression");
  c(node.body, st, "Statement");
};
base$1.SwitchStatement = function (node, st, c) {
  c(node.discriminant, st, "Expression");
  for (var i$1 = 0, list$1 = node.cases; i$1 < list$1.length; i$1 += 1) {
    var cs = list$1[i$1];

    if (cs.test) { c(cs.test, st, "Expression"); }
    for (var i = 0, list = cs.consequent; i < list.length; i += 1)
      {
      var cons = list[i];

      c(cons, st, "Statement");
    }
  }
};
base$1.SwitchCase = function (node, st, c) {
  if (node.test) { c(node.test, st, "Expression"); }
  for (var i = 0, list = node.consequent; i < list.length; i += 1)
    {
    var cons = list[i];

    c(cons, st, "Statement");
  }
};
base$1.ReturnStatement = base$1.YieldExpression = base$1.AwaitExpression = function (node, st, c) {
  if (node.argument) { c(node.argument, st, "Expression"); }
};
base$1.ThrowStatement = base$1.SpreadElement =
  function (node, st, c) { return c(node.argument, st, "Expression"); };
base$1.TryStatement = function (node, st, c) {
  c(node.block, st, "Statement");
  if (node.handler) { c(node.handler, st); }
  if (node.finalizer) { c(node.finalizer, st, "Statement"); }
};
base$1.CatchClause = function (node, st, c) {
  if (node.param) { c(node.param, st, "Pattern"); }
  c(node.body, st, "Statement");
};
base$1.WhileStatement = base$1.DoWhileStatement = function (node, st, c) {
  c(node.test, st, "Expression");
  c(node.body, st, "Statement");
};
base$1.ForStatement = function (node, st, c) {
  if (node.init) { c(node.init, st, "ForInit"); }
  if (node.test) { c(node.test, st, "Expression"); }
  if (node.update) { c(node.update, st, "Expression"); }
  c(node.body, st, "Statement");
};
base$1.ForInStatement = base$1.ForOfStatement = function (node, st, c) {
  c(node.left, st, "ForInit");
  c(node.right, st, "Expression");
  c(node.body, st, "Statement");
};
base$1.ForInit = function (node, st, c) {
  if (node.type === "VariableDeclaration") { c(node, st); }
  else { c(node, st, "Expression"); }
};
base$1.DebuggerStatement = ignore;

base$1.FunctionDeclaration = function (node, st, c) { return c(node, st, "Function"); };
base$1.VariableDeclaration = function (node, st, c) {
  for (var i = 0, list = node.declarations; i < list.length; i += 1)
    {
    var decl = list[i];

    c(decl, st);
  }
};
base$1.VariableDeclarator = function (node, st, c) {
  c(node.id, st, "Pattern");
  if (node.init) { c(node.init, st, "Expression"); }
};

base$1.Function = function (node, st, c) {
  if (node.id) { c(node.id, st, "Pattern"); }
  for (var i = 0, list = node.params; i < list.length; i += 1)
    {
    var param = list[i];

    c(param, st, "Pattern");
  }
  c(node.body, st, node.expression ? "Expression" : "Statement");
};

base$1.Pattern = function (node, st, c) {
  if (node.type === "Identifier")
    { c(node, st, "VariablePattern"); }
  else if (node.type === "MemberExpression")
    { c(node, st, "MemberPattern"); }
  else
    { c(node, st); }
};
base$1.VariablePattern = ignore;
base$1.MemberPattern = skipThrough;
base$1.RestElement = function (node, st, c) { return c(node.argument, st, "Pattern"); };
base$1.ArrayPattern = function (node, st, c) {
  for (var i = 0, list = node.elements; i < list.length; i += 1) {
    var elt = list[i];

    if (elt) { c(elt, st, "Pattern"); }
  }
};
base$1.ObjectPattern = function (node, st, c) {
  for (var i = 0, list = node.properties; i < list.length; i += 1) {
    var prop = list[i];

    if (prop.type === "Property") {
      if (prop.computed) { c(prop.key, st, "Expression"); }
      c(prop.value, st, "Pattern");
    } else if (prop.type === "RestElement") {
      c(prop.argument, st, "Pattern");
    }
  }
};

base$1.Expression = skipThrough;
base$1.ThisExpression = base$1.Super = base$1.MetaProperty = ignore;
base$1.ArrayExpression = function (node, st, c) {
  for (var i = 0, list = node.elements; i < list.length; i += 1) {
    var elt = list[i];

    if (elt) { c(elt, st, "Expression"); }
  }
};
base$1.ObjectExpression = function (node, st, c) {
  for (var i = 0, list = node.properties; i < list.length; i += 1)
    {
    var prop = list[i];

    c(prop, st);
  }
};
base$1.FunctionExpression = base$1.ArrowFunctionExpression = base$1.FunctionDeclaration;
base$1.SequenceExpression = function (node, st, c) {
  for (var i = 0, list = node.expressions; i < list.length; i += 1)
    {
    var expr = list[i];

    c(expr, st, "Expression");
  }
};
base$1.TemplateLiteral = function (node, st, c) {
  for (var i = 0, list = node.quasis; i < list.length; i += 1)
    {
    var quasi = list[i];

    c(quasi, st);
  }

  for (var i$1 = 0, list$1 = node.expressions; i$1 < list$1.length; i$1 += 1)
    {
    var expr = list$1[i$1];

    c(expr, st, "Expression");
  }
};
base$1.TemplateElement = ignore;
base$1.UnaryExpression = base$1.UpdateExpression = function (node, st, c) {
  c(node.argument, st, "Expression");
};
base$1.BinaryExpression = base$1.LogicalExpression = function (node, st, c) {
  c(node.left, st, "Expression");
  c(node.right, st, "Expression");
};
base$1.AssignmentExpression = base$1.AssignmentPattern = function (node, st, c) {
  c(node.left, st, "Pattern");
  c(node.right, st, "Expression");
};
base$1.ConditionalExpression = function (node, st, c) {
  c(node.test, st, "Expression");
  c(node.consequent, st, "Expression");
  c(node.alternate, st, "Expression");
};
base$1.NewExpression = base$1.CallExpression = function (node, st, c) {
  c(node.callee, st, "Expression");
  if (node.arguments)
    { for (var i = 0, list = node.arguments; i < list.length; i += 1)
      {
        var arg = list[i];

        c(arg, st, "Expression");
      } }
};
base$1.MemberExpression = function (node, st, c) {
  c(node.object, st, "Expression");
  if (node.computed) { c(node.property, st, "Expression"); }
};
base$1.ExportNamedDeclaration = base$1.ExportDefaultDeclaration = function (node, st, c) {
  if (node.declaration)
    { c(node.declaration, st, node.type === "ExportNamedDeclaration" || node.declaration.id ? "Statement" : "Expression"); }
  if (node.source) { c(node.source, st, "Expression"); }
};
base$1.ExportAllDeclaration = function (node, st, c) {
  c(node.source, st, "Expression");
};
base$1.ImportDeclaration = function (node, st, c) {
  for (var i = 0, list = node.specifiers; i < list.length; i += 1)
    {
    var spec = list[i];

    c(spec, st);
  }
  c(node.source, st, "Expression");
};
base$1.ImportExpression = function (node, st, c) {
  c(node.source, st, "Expression");
};
base$1.ImportSpecifier = base$1.ImportDefaultSpecifier = base$1.ImportNamespaceSpecifier = base$1.Identifier = base$1.Literal = ignore;

base$1.TaggedTemplateExpression = function (node, st, c) {
  c(node.tag, st, "Expression");
  c(node.quasi, st, "Expression");
};
base$1.ClassDeclaration = base$1.ClassExpression = function (node, st, c) { return c(node, st, "Class"); };
base$1.Class = function (node, st, c) {
  if (node.id) { c(node.id, st, "Pattern"); }
  if (node.superClass) { c(node.superClass, st, "Expression"); }
  c(node.body, st);
};
base$1.ClassBody = function (node, st, c) {
  for (var i = 0, list = node.body; i < list.length; i += 1)
    {
    var elt = list[i];

    c(elt, st);
  }
};
base$1.MethodDefinition = base$1.Property = function (node, st, c) {
  if (node.computed) { c(node.key, st, "Expression"); }
  c(node.value, st, "Expression");
};

// @ts-ignore
function handlePureAnnotationsOfNode(node, state, type = node.type) {
    let commentNode = state.commentNodes[state.commentIndex];
    while (commentNode && node.start >= commentNode.end) {
        markPureNode(node, commentNode);
        commentNode = state.commentNodes[++state.commentIndex];
    }
    if (commentNode && commentNode.end <= node.end) {
        base$1[type](node, state, handlePureAnnotationsOfNode);
    }
}
function markPureNode(node, comment) {
    if (node.annotations) {
        node.annotations.push(comment);
    }
    else {
        node.annotations = [comment];
    }
    if (node.type === 'ExpressionStatement') {
        node = node.expression;
    }
    if (node.type === 'CallExpression' || node.type === 'NewExpression') {
        node.annotatedPure = true;
    }
}
const pureCommentRegex = /[@#]__PURE__/;
const isPureComment = (comment) => pureCommentRegex.test(comment.text);
function markPureCallExpressions(comments, esTreeAst) {
    handlePureAnnotationsOfNode(esTreeAst, {
        commentIndex: 0,
        commentNodes: comments.filter(isPureComment)
    });
}

// this looks ridiculous, but it prevents sourcemap tooling from mistaking
// this for an actual sourceMappingURL
let SOURCEMAPPING_URL = 'sourceMa';
SOURCEMAPPING_URL += 'ppingURL';
const SOURCEMAPPING_URL_RE = new RegExp(`^#\\s+${SOURCEMAPPING_URL}=.+\\n?`);

const NOOP = () => { };
let getStartTime = () => [0, 0];
let getElapsedTime = () => 0;
let getMemory = () => 0;
let timers = {};
const normalizeHrTime = (time) => time[0] * 1e3 + time[1] / 1e6;
function setTimeHelpers() {
    if (typeof process !== 'undefined' && typeof process.hrtime === 'function') {
        getStartTime = process.hrtime.bind(process);
        getElapsedTime = previous => normalizeHrTime(process.hrtime(previous));
    }
    else if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
        getStartTime = () => [performance.now(), 0];
        getElapsedTime = previous => performance.now() - previous[0];
    }
    if (typeof process !== 'undefined' && typeof process.memoryUsage === 'function') {
        getMemory = () => process.memoryUsage().heapUsed;
    }
}
function getPersistedLabel(label, level) {
    switch (level) {
        case 1:
            return `# ${label}`;
        case 2:
            return `## ${label}`;
        case 3:
            return label;
        default:
            return `${'  '.repeat(level - 4)}- ${label}`;
    }
}
function timeStartImpl(label, level = 3) {
    label = getPersistedLabel(label, level);
    if (!timers.hasOwnProperty(label)) {
        timers[label] = {
            memory: 0,
            startMemory: undefined,
            startTime: undefined,
            time: 0,
            totalMemory: 0
        };
    }
    const currentMemory = getMemory();
    timers[label].startTime = getStartTime();
    timers[label].startMemory = currentMemory;
}
function timeEndImpl(label, level = 3) {
    label = getPersistedLabel(label, level);
    if (timers.hasOwnProperty(label)) {
        const currentMemory = getMemory();
        timers[label].time += getElapsedTime(timers[label].startTime);
        timers[label].totalMemory = Math.max(timers[label].totalMemory, currentMemory);
        timers[label].memory += currentMemory - timers[label].startMemory;
    }
}
function getTimings() {
    const newTimings = {};
    Object.keys(timers).forEach(label => {
        newTimings[label] = [timers[label].time, timers[label].memory, timers[label].totalMemory];
    });
    return newTimings;
}
let timeStart = NOOP, timeEnd = NOOP;
const TIMED_PLUGIN_HOOKS = {
    load: true,
    ongenerate: true,
    onwrite: true,
    resolveDynamicImport: true,
    resolveId: true,
    transform: true,
    transformBundle: true
};
function getPluginWithTimers(plugin, index) {
    const timedPlugin = {};
    for (const hook of Object.keys(plugin)) {
        if (TIMED_PLUGIN_HOOKS[hook] === true) {
            let timerLabel = `plugin ${index}`;
            if (plugin.name) {
                timerLabel += ` (${plugin.name})`;
            }
            timerLabel += ` - ${hook}`;
            timedPlugin[hook] = function () {
                timeStart(timerLabel, 4);
                const result = plugin[hook].apply(this === timedPlugin ? plugin : this, arguments);
                timeEnd(timerLabel, 4);
                if (result && typeof result.then === 'function') {
                    timeStart(`${timerLabel} (async)`, 4);
                    result.then(() => timeEnd(`${timerLabel} (async)`, 4));
                }
                return result;
            };
        }
        else {
            timedPlugin[hook] = plugin[hook];
        }
    }
    return timedPlugin;
}
function initialiseTimers(inputOptions) {
    if (inputOptions.perf) {
        timers = {};
        setTimeHelpers();
        timeStart = timeStartImpl;
        timeEnd = timeEndImpl;
        inputOptions.plugins = inputOptions.plugins.map(getPluginWithTimers);
    }
    else {
        timeStart = NOOP;
        timeEnd = NOOP;
    }
}

const defaultAcornOptions = {
    ecmaVersion: 2020,
    preserveParens: false,
    sourceType: 'module'
};
function tryParse(module, Parser, acornOptions) {
    try {
        return Parser.parse(module.code, Object.assign(Object.assign(Object.assign({}, defaultAcornOptions), acornOptions), { onComment: (block, text, start, end) => module.comments.push({ block, text, start, end }) }));
    }
    catch (err) {
        let message = err.message.replace(/ \(\d+:\d+\)$/, '');
        if (module.id.endsWith('.json')) {
            message += ' (Note that you need rollup-plugin-json to import JSON files)';
        }
        else if (!module.id.endsWith('.js')) {
            message += ' (Note that you need plugins to import files that are not JavaScript)';
        }
        module.error({
            code: 'PARSE_ERROR',
            message
        }, err.pos);
    }
}
function handleMissingExport(exportName, importingModule, importedModule, importerStart) {
    importingModule.error({
        code: 'MISSING_EXPORT',
        message: `'${exportName}' is not exported by ${index.relativeId(importedModule)}`,
        url: `https://rollupjs.org/guide/en/#error-name-is-not-exported-by-module`
    }, importerStart);
}
const MISSING_EXPORT_SHIM_DESCRIPTION = {
    identifier: null,
    localName: MISSING_EXPORT_SHIM_VARIABLE
};
class Module {
    constructor(graph, id, moduleSideEffects, isEntry) {
        this.chunkFileNames = new Set();
        this.chunkName = null;
        this.comments = [];
        this.dependencies = [];
        this.dynamicallyImportedBy = [];
        this.dynamicDependencies = [];
        this.dynamicImports = [];
        this.entryPointsHash = new Uint8Array(10);
        this.execIndex = Infinity;
        this.exportAllModules = null;
        this.exportAllSources = [];
        this.exports = Object.create(null);
        this.exportsAll = Object.create(null);
        this.exportShimVariable = new ExportShimVariable(this);
        this.facadeChunk = null;
        this.importDescriptions = Object.create(null);
        this.importMetas = [];
        this.imports = new Set();
        this.isExecuted = false;
        this.isUserDefinedEntryPoint = false;
        this.manualChunkAlias = null;
        this.reexports = Object.create(null);
        this.sources = [];
        this.userChunkNames = new Set();
        this.usesTopLevelAwait = false;
        this.namespaceVariable = undefined;
        this.transformDependencies = [];
        this.id = id;
        this.graph = graph;
        this.excludeFromSourcemap = /\0/.test(id);
        this.context = graph.getModuleContext(id);
        this.moduleSideEffects = moduleSideEffects;
        this.isEntryPoint = isEntry;
    }
    basename() {
        const base = path.basename(this.id);
        const ext = path.extname(this.id);
        return makeLegal(ext ? base.slice(0, -ext.length) : base);
    }
    bindReferences() {
        this.ast.bind();
    }
    error(props, pos) {
        if (pos !== undefined) {
            props.pos = pos;
            let location = locate(this.code, pos, { offsetLine: 1 });
            try {
                location = getOriginalLocation(this.sourcemapChain, location);
            }
            catch (e) {
                this.warn({
                    code: 'SOURCEMAP_ERROR',
                    loc: {
                        column: location.column,
                        file: this.id,
                        line: location.line
                    },
                    message: `Error when using sourcemap for reporting an error: ${e.message}`,
                    pos
                }, undefined);
            }
            props.loc = {
                column: location.column,
                file: this.id,
                line: location.line
            };
            props.frame = getCodeFrame(this.originalCode, location.line, location.column);
        }
        props.watchFiles = Object.keys(this.graph.watchFiles);
        error(props);
    }
    getAllExportNames() {
        if (this.allExportNames) {
            return this.allExportNames;
        }
        const allExportNames = (this.allExportNames = new Set());
        for (const name of Object.keys(this.exports)) {
            allExportNames.add(name);
        }
        for (const name of Object.keys(this.reexports)) {
            allExportNames.add(name);
        }
        for (const module of this.exportAllModules) {
            if (module instanceof ExternalModule) {
                allExportNames.add(`*${module.id}`);
                continue;
            }
            for (const name of module.getAllExportNames()) {
                if (name !== 'default')
                    allExportNames.add(name);
            }
        }
        return allExportNames;
    }
    getDynamicImportExpressions() {
        return this.dynamicImports.map(({ node }) => {
            const importArgument = node.source;
            if (importArgument instanceof TemplateLiteral &&
                importArgument.quasis.length === 1 &&
                importArgument.quasis[0].value.cooked) {
                return importArgument.quasis[0].value.cooked;
            }
            if (importArgument instanceof Literal && typeof importArgument.value === 'string') {
                return importArgument.value;
            }
            return importArgument;
        });
    }
    getExportNamesByVariable() {
        const exportNamesByVariable = new Map();
        for (const exportName of this.getAllExportNames()) {
            const tracedVariable = this.getVariableForExportName(exportName);
            if (!tracedVariable ||
                !(tracedVariable.included || tracedVariable instanceof ExternalVariable)) {
                continue;
            }
            const existingExportNames = exportNamesByVariable.get(tracedVariable);
            if (existingExportNames) {
                existingExportNames.push(exportName);
            }
            else {
                exportNamesByVariable.set(tracedVariable, [exportName]);
            }
        }
        return exportNamesByVariable;
    }
    getExports() {
        return Object.keys(this.exports);
    }
    getOrCreateNamespace() {
        if (!this.namespaceVariable) {
            this.namespaceVariable = new NamespaceVariable(this.astContext);
            this.namespaceVariable.initialise();
        }
        return this.namespaceVariable;
    }
    getReexports() {
        if (this.transitiveReexports) {
            return this.transitiveReexports;
        }
        // to avoid infinite recursion when using circular `export * from X`
        this.transitiveReexports = [];
        const reexports = new Set();
        for (const name in this.reexports) {
            reexports.add(name);
        }
        for (const module of this.exportAllModules) {
            if (module instanceof ExternalModule) {
                reexports.add(`*${module.id}`);
            }
            else {
                for (const name of module.getExports().concat(module.getReexports())) {
                    if (name !== 'default')
                        reexports.add(name);
                }
            }
        }
        return (this.transitiveReexports = Array.from(reexports));
    }
    getRenderedExports() {
        // only direct exports are counted here, not reexports at all
        const renderedExports = [];
        const removedExports = [];
        for (const exportName in this.exports) {
            const variable = this.getVariableForExportName(exportName);
            (variable && variable.included ? renderedExports : removedExports).push(exportName);
        }
        return { renderedExports, removedExports };
    }
    getTransitiveDependencies() {
        return this.dependencies.concat(this.getReexports().map(exportName => this.getVariableForExportName(exportName).module));
    }
    getVariableForExportName(name, isExportAllSearch) {
        if (name[0] === '*') {
            if (name.length === 1) {
                return this.getOrCreateNamespace();
            }
            else {
                // export * from 'external'
                const module = this.graph.moduleById.get(name.slice(1));
                return module.getVariableForExportName('*');
            }
        }
        // export { foo } from './other'
        const reexportDeclaration = this.reexports[name];
        if (reexportDeclaration) {
            const declaration = reexportDeclaration.module.getVariableForExportName(reexportDeclaration.localName);
            if (!declaration) {
                handleMissingExport(reexportDeclaration.localName, this, reexportDeclaration.module.id, reexportDeclaration.start);
            }
            return declaration;
        }
        const exportDeclaration = this.exports[name];
        if (exportDeclaration) {
            if (exportDeclaration === MISSING_EXPORT_SHIM_DESCRIPTION) {
                return this.exportShimVariable;
            }
            const name = exportDeclaration.localName;
            return this.traceVariable(name) || this.graph.scope.findVariable(name);
        }
        if (name !== 'default') {
            for (const module of this.exportAllModules) {
                const declaration = module.getVariableForExportName(name, true);
                if (declaration)
                    return declaration;
            }
        }
        // we don't want to create shims when we are just
        // probing export * modules for exports
        if (this.graph.shimMissingExports && !isExportAllSearch) {
            this.shimMissingExport(name);
            return this.exportShimVariable;
        }
        return undefined;
    }
    include() {
        if (this.ast.shouldBeIncluded())
            this.ast.include(false);
    }
    includeAllExports() {
        if (!this.isExecuted) {
            this.graph.needsTreeshakingPass = true;
            markModuleAndImpureDependenciesAsExecuted(this);
        }
        for (const exportName of this.getExports()) {
            const variable = this.getVariableForExportName(exportName);
            variable.deoptimizePath(UNKNOWN_PATH);
            if (!variable.included) {
                variable.include();
                this.graph.needsTreeshakingPass = true;
            }
        }
        for (const name of this.getReexports()) {
            const variable = this.getVariableForExportName(name);
            variable.deoptimizePath(UNKNOWN_PATH);
            if (!variable.included) {
                variable.include();
                this.graph.needsTreeshakingPass = true;
            }
            if (variable instanceof ExternalVariable) {
                variable.module.reexported = true;
            }
        }
    }
    includeAllInBundle() {
        this.ast.include(true);
    }
    isIncluded() {
        return this.ast.included || (this.namespaceVariable && this.namespaceVariable.included);
    }
    linkDependencies() {
        for (const source of this.sources) {
            const id = this.resolvedIds[source].id;
            if (id) {
                const module = this.graph.moduleById.get(id);
                this.dependencies.push(module);
            }
        }
        for (const { resolution } of this.dynamicImports) {
            if (resolution instanceof Module || resolution instanceof ExternalModule) {
                this.dynamicDependencies.push(resolution);
            }
        }
        this.addModulesToSpecifiers(this.importDescriptions);
        this.addModulesToSpecifiers(this.reexports);
        this.exportAllModules = this.exportAllSources
            .map(source => {
            const id = this.resolvedIds[source].id;
            return this.graph.moduleById.get(id);
        })
            .sort((moduleA, moduleB) => {
            const aExternal = moduleA instanceof ExternalModule;
            const bExternal = moduleB instanceof ExternalModule;
            return aExternal === bExternal ? 0 : aExternal ? 1 : -1;
        });
    }
    render(options) {
        const magicString = this.magicString.clone();
        this.ast.render(magicString, options);
        this.usesTopLevelAwait = this.astContext.usesTopLevelAwait;
        return magicString;
    }
    setSource({ ast, code, customTransformCache, moduleSideEffects, originalCode, originalSourcemap, resolvedIds, sourcemapChain, transformDependencies, transformFiles }) {
        this.code = code;
        this.originalCode = originalCode;
        this.originalSourcemap = originalSourcemap;
        this.sourcemapChain = sourcemapChain;
        if (transformFiles) {
            this.transformFiles = transformFiles;
        }
        this.transformDependencies = transformDependencies;
        this.customTransformCache = customTransformCache;
        if (typeof moduleSideEffects === 'boolean') {
            this.moduleSideEffects = moduleSideEffects;
        }
        timeStart('generate ast', 3);
        this.esTreeAst = ast || tryParse(this, this.graph.acornParser, this.graph.acornOptions);
        markPureCallExpressions(this.comments, this.esTreeAst);
        timeEnd('generate ast', 3);
        this.resolvedIds = resolvedIds || Object.create(null);
        // By default, `id` is the file name. Custom resolvers and loaders
        // can change that, but it makes sense to use it for the source file name
        const fileName = this.id;
        this.magicString = new MagicString(code, {
            filename: (this.excludeFromSourcemap ? null : fileName),
            indentExclusionRanges: []
        });
        this.removeExistingSourceMap();
        timeStart('analyse ast', 3);
        this.astContext = {
            addDynamicImport: this.addDynamicImport.bind(this),
            addExport: this.addExport.bind(this),
            addImport: this.addImport.bind(this),
            addImportMeta: this.addImportMeta.bind(this),
            annotations: (this.graph.treeshakingOptions &&
                this.graph.treeshakingOptions.annotations),
            code,
            deoptimizationTracker: this.graph.deoptimizationTracker,
            error: this.error.bind(this),
            fileName,
            getExports: this.getExports.bind(this),
            getFileName: this.graph.pluginDriver.getFileName,
            getModuleExecIndex: () => this.execIndex,
            getModuleName: this.basename.bind(this),
            getReexports: this.getReexports.bind(this),
            importDescriptions: this.importDescriptions,
            includeDynamicImport: this.includeDynamicImport.bind(this),
            includeVariable: this.includeVariable.bind(this),
            isCrossChunkImport: importDescription => importDescription.module.chunk !== this.chunk,
            magicString: this.magicString,
            module: this,
            moduleContext: this.context,
            nodeConstructors,
            preserveModules: this.graph.preserveModules,
            propertyReadSideEffects: (!this.graph.treeshakingOptions ||
                this.graph.treeshakingOptions.propertyReadSideEffects),
            traceExport: this.getVariableForExportName.bind(this),
            traceVariable: this.traceVariable.bind(this),
            treeshake: !!this.graph.treeshakingOptions,
            tryCatchDeoptimization: (!this.graph.treeshakingOptions ||
                this.graph.treeshakingOptions.tryCatchDeoptimization),
            unknownGlobalSideEffects: (!this.graph.treeshakingOptions ||
                this.graph.treeshakingOptions.unknownGlobalSideEffects),
            usesTopLevelAwait: false,
            warn: this.warn.bind(this),
            warnDeprecation: this.graph.warnDeprecation.bind(this.graph)
        };
        this.scope = new ModuleScope(this.graph.scope, this.astContext);
        this.ast = new Program$1(this.esTreeAst, { type: 'Module', context: this.astContext }, this.scope);
        timeEnd('analyse ast', 3);
    }
    toJSON() {
        return {
            ast: this.esTreeAst,
            code: this.code,
            customTransformCache: this.customTransformCache,
            dependencies: this.dependencies.map(module => module.id),
            id: this.id,
            moduleSideEffects: this.moduleSideEffects,
            originalCode: this.originalCode,
            originalSourcemap: this.originalSourcemap,
            resolvedIds: this.resolvedIds,
            sourcemapChain: this.sourcemapChain,
            transformDependencies: this.transformDependencies,
            transformFiles: this.transformFiles
        };
    }
    traceVariable(name) {
        const localVariable = this.scope.variables.get(name);
        if (localVariable) {
            return localVariable;
        }
        if (name in this.importDescriptions) {
            const importDeclaration = this.importDescriptions[name];
            const otherModule = importDeclaration.module;
            if (otherModule instanceof Module && importDeclaration.name === '*') {
                return otherModule.getOrCreateNamespace();
            }
            const declaration = otherModule.getVariableForExportName(importDeclaration.name);
            if (!declaration) {
                handleMissingExport(importDeclaration.name, this, otherModule.id, importDeclaration.start);
            }
            return declaration;
        }
        return null;
    }
    warn(warning, pos) {
        if (pos !== undefined) {
            warning.pos = pos;
            const { line, column } = locate(this.code, pos, { offsetLine: 1 }); // TODO trace sourcemaps, cf. error()
            warning.loc = { file: this.id, line, column };
            warning.frame = getCodeFrame(this.code, line, column);
        }
        warning.id = this.id;
        this.graph.warn(warning);
    }
    addDynamicImport(node) {
        this.dynamicImports.push({ node, resolution: null });
    }
    addExport(node) {
        const source = node.source && node.source.value;
        // export { name } from './other'
        if (source) {
            if (this.sources.indexOf(source) === -1)
                this.sources.push(source);
            if (node.type === ExportAllDeclaration) {
                // Store `export * from '...'` statements in an array of delegates.
                // When an unknown import is encountered, we see if one of them can satisfy it.
                this.exportAllSources.push(source);
            }
            else {
                for (const specifier of node.specifiers) {
                    const name = specifier.exported.name;
                    if (this.exports[name] || this.reexports[name]) {
                        this.error({
                            code: 'DUPLICATE_EXPORT',
                            message: `A module cannot have multiple exports with the same name ('${name}')`
                        }, specifier.start);
                    }
                    this.reexports[name] = {
                        localName: specifier.local.name,
                        module: null,
                        source,
                        start: specifier.start
                    };
                }
            }
        }
        else if (node instanceof ExportDefaultDeclaration) {
            // export default function foo () {}
            // export default foo;
            // export default 42;
            if (this.exports.default) {
                this.error({
                    code: 'DUPLICATE_EXPORT',
                    message: `A module can only have one default export`
                }, node.start);
            }
            this.exports.default = {
                identifier: node.variable.getAssignedVariableName(),
                localName: 'default'
            };
        }
        else if (node.declaration) {
            // export var { foo, bar } = ...
            // export var foo = 42;
            // export var a = 1, b = 2, c = 3;
            // export function foo () {}
            const declaration = node.declaration;
            if (declaration.type === VariableDeclaration) {
                for (const decl of declaration.declarations) {
                    for (const localName of extractAssignedNames(decl.id)) {
                        this.exports[localName] = { identifier: null, localName };
                    }
                }
            }
            else {
                // export function foo () {}
                const localName = declaration.id.name;
                this.exports[localName] = { identifier: null, localName };
            }
        }
        else {
            // export { foo, bar, baz }
            for (const specifier of node.specifiers) {
                const localName = specifier.local.name;
                const exportedName = specifier.exported.name;
                if (this.exports[exportedName] || this.reexports[exportedName]) {
                    this.error({
                        code: 'DUPLICATE_EXPORT',
                        message: `A module cannot have multiple exports with the same name ('${exportedName}')`
                    }, specifier.start);
                }
                this.exports[exportedName] = { identifier: null, localName };
            }
        }
    }
    addImport(node) {
        const source = node.source.value;
        if (this.sources.indexOf(source) === -1)
            this.sources.push(source);
        for (const specifier of node.specifiers) {
            const localName = specifier.local.name;
            if (this.importDescriptions[localName]) {
                this.error({
                    code: 'DUPLICATE_IMPORT',
                    message: `Duplicated import '${localName}'`
                }, specifier.start);
            }
            const isDefault = specifier.type === ImportDefaultSpecifier;
            const isNamespace = specifier.type === ImportNamespaceSpecifier;
            const name = isDefault
                ? 'default'
                : isNamespace
                    ? '*'
                    : specifier.imported.name;
            this.importDescriptions[localName] = { source, start: specifier.start, name, module: null };
        }
    }
    addImportMeta(node) {
        this.importMetas.push(node);
    }
    addModulesToSpecifiers(specifiers) {
        for (const name of Object.keys(specifiers)) {
            const specifier = specifiers[name];
            const id = this.resolvedIds[specifier.source].id;
            specifier.module = this.graph.moduleById.get(id);
        }
    }
    includeDynamicImport(node) {
        const resolution = this.dynamicImports.find(dynamicImport => dynamicImport.node === node).resolution;
        if (resolution instanceof Module) {
            resolution.dynamicallyImportedBy.push(this);
            resolution.includeAllExports();
        }
    }
    includeVariable(variable) {
        const variableModule = variable.module;
        if (!variable.included) {
            variable.include();
            this.graph.needsTreeshakingPass = true;
        }
        if (variableModule && variableModule !== this) {
            this.imports.add(variable);
        }
    }
    removeExistingSourceMap() {
        for (const comment of this.comments) {
            if (!comment.block && SOURCEMAPPING_URL_RE.test(comment.text)) {
                this.magicString.remove(comment.start, comment.end);
            }
        }
    }
    shimMissingExport(name) {
        if (!this.exports[name]) {
            this.graph.warn({
                code: 'SHIMMED_EXPORT',
                exporter: index.relativeId(this.id),
                exportName: name,
                message: `Missing export "${name}" has been shimmed in module ${index.relativeId(this.id)}.`
            });
            this.exports[name] = MISSING_EXPORT_SHIM_DESCRIPTION;
        }
    }
}

class Source {
    constructor(filename, content) {
        this.isOriginal = true;
        this.filename = filename;
        this.content = content;
    }
    traceSegment(line, column, name) {
        return { line, column, name, source: this };
    }
}
class Link {
    constructor(map, sources) {
        this.sources = sources;
        this.names = map.names;
        this.mappings = map.mappings;
    }
    traceMappings() {
        const sources = [];
        const sourcesContent = [];
        const names = [];
        const mappings = [];
        for (const line of this.mappings) {
            const tracedLine = [];
            for (const segment of line) {
                if (segment.length == 1)
                    continue;
                const source = this.sources[segment[1]];
                if (!source)
                    continue;
                const traced = source.traceSegment(segment[2], segment[3], segment.length === 5 ? this.names[segment[4]] : '');
                if (traced) {
                    // newer sources are more likely to be used, so search backwards.
                    let sourceIndex = sources.lastIndexOf(traced.source.filename);
                    if (sourceIndex === -1) {
                        sourceIndex = sources.length;
                        sources.push(traced.source.filename);
                        sourcesContent[sourceIndex] = traced.source.content;
                    }
                    else if (sourcesContent[sourceIndex] == null) {
                        sourcesContent[sourceIndex] = traced.source.content;
                    }
                    else if (traced.source.content != null &&
                        sourcesContent[sourceIndex] !== traced.source.content) {
                        error({
                            message: `Multiple conflicting contents for sourcemap source ${traced.source.filename}`
                        });
                    }
                    const tracedSegment = [
                        segment[0],
                        sourceIndex,
                        traced.line,
                        traced.column
                    ];
                    if (traced.name) {
                        let nameIndex = names.indexOf(traced.name);
                        if (nameIndex === -1) {
                            nameIndex = names.length;
                            names.push(traced.name);
                        }
                        tracedSegment[4] = nameIndex;
                    }
                    tracedLine.push(tracedSegment);
                }
            }
            mappings.push(tracedLine);
        }
        return { sources, sourcesContent, names, mappings };
    }
    traceSegment(line, column, name) {
        const segments = this.mappings[line];
        if (!segments)
            return null;
        // binary search through segments for the given column
        let i = 0;
        let j = segments.length - 1;
        while (i <= j) {
            const m = (i + j) >> 1;
            const segment = segments[m];
            if (segment[0] === column) {
                if (segment.length == 1)
                    return null;
                const source = this.sources[segment[1]];
                if (!source)
                    return null;
                return source.traceSegment(segment[2], segment[3], segment.length === 5 ? this.names[segment[4]] : name);
            }
            if (segment[0] > column) {
                j = m - 1;
            }
            else {
                i = m + 1;
            }
        }
        return null;
    }
}
function getLinkMap(graph) {
    return function linkMap(source, map) {
        if (map.mappings) {
            return new Link(map, [source]);
        }
        graph.warn({
            code: 'SOURCEMAP_BROKEN',
            message: `Sourcemap is likely to be incorrect: a plugin${map.plugin ? ` ('${map.plugin}')` : ``} was used to transform files, but didn't generate a sourcemap for the transformation. Consult the plugin documentation for help`,
            plugin: map.plugin,
            url: `https://rollupjs.org/guide/en/#warning-sourcemap-is-likely-to-be-incorrect`
        });
        return new Link({
            mappings: [],
            names: []
        }, [source]);
    };
}
function getCollapsedSourcemap(id, originalCode, originalSourcemap, sourcemapChain, linkMap) {
    let source;
    if (!originalSourcemap) {
        source = new Source(id, originalCode);
    }
    else {
        const sources = originalSourcemap.sources;
        const sourcesContent = originalSourcemap.sourcesContent || [];
        // TODO indiscriminately treating IDs and sources as normal paths is probably bad.
        const directory = path.dirname(id) || '.';
        const sourceRoot = originalSourcemap.sourceRoot || '.';
        const baseSources = sources.map((source, i) => new Source(path.resolve(directory, sourceRoot, source), sourcesContent[i]));
        source = new Link(originalSourcemap, baseSources);
    }
    return sourcemapChain.reduce(linkMap, source);
}
function collapseSourcemaps(bundle, file, map, modules, bundleSourcemapChain, excludeContent) {
    const linkMap = getLinkMap(bundle.graph);
    const moduleSources = modules
        .filter(module => !module.excludeFromSourcemap)
        .map(module => getCollapsedSourcemap(module.id, module.originalCode, module.originalSourcemap, module.sourcemapChain, linkMap));
    // DecodedSourceMap (from magic-string) uses a number[] instead of the more
    // correct SourceMapSegment tuples. Cast it here to gain type safety.
    let source = new Link(map, moduleSources);
    source = bundleSourcemapChain.reduce(linkMap, source);
    let { sources, sourcesContent, names, mappings } = source.traceMappings();
    if (file) {
        const directory = path.dirname(file);
        sources = sources.map((source) => path.relative(directory, source));
        file = path.basename(file);
    }
    sourcesContent = (excludeContent ? null : sourcesContent);
    return new SourceMap({ file, sources, sourcesContent, names, mappings });
}
function collapseSourcemap(graph, id, originalCode, originalSourcemap, sourcemapChain) {
    if (!sourcemapChain.length) {
        return originalSourcemap;
    }
    const source = getCollapsedSourcemap(id, originalCode, originalSourcemap, sourcemapChain, getLinkMap(graph));
    const map = source.traceMappings();
    return Object.assign({ version: 3 }, map);
}

const DECONFLICT_IMPORTED_VARIABLES_BY_FORMAT = {
    amd: deconflictImportsOther,
    cjs: deconflictImportsOther,
    es: deconflictImportsEsm,
    iife: deconflictImportsOther,
    system: deconflictImportsEsm,
    umd: deconflictImportsOther
};
function deconflictChunk(modules, dependencies, imports, usedNames, format, interop, preserveModules) {
    addUsedGlobalNames(usedNames, modules, format);
    deconflictTopLevelVariables(usedNames, modules);
    DECONFLICT_IMPORTED_VARIABLES_BY_FORMAT[format](usedNames, imports, dependencies, interop, preserveModules);
    for (const module of modules) {
        module.scope.deconflict(format);
    }
}
function addUsedGlobalNames(usedNames, modules, format) {
    for (const module of modules) {
        const moduleScope = module.scope;
        for (const [name, variable] of moduleScope.accessedOutsideVariables) {
            if (variable.included) {
                usedNames.add(name);
            }
        }
        const accessedGlobalVariables = moduleScope.accessedGlobalVariablesByFormat &&
            moduleScope.accessedGlobalVariablesByFormat.get(format);
        if (accessedGlobalVariables) {
            for (const name of accessedGlobalVariables) {
                usedNames.add(name);
            }
        }
    }
}
function deconflictImportsEsm(usedNames, imports, _dependencies, interop) {
    for (const variable of imports) {
        const module = variable.module;
        const name = variable.name;
        let proposedName;
        if (module instanceof ExternalModule && (name === '*' || name === 'default')) {
            if (name === 'default' && interop && module.exportsNamespace) {
                proposedName = module.variableName + '__default';
            }
            else {
                proposedName = module.variableName;
            }
        }
        else {
            proposedName = name;
        }
        variable.setRenderNames(null, getSafeName(proposedName, usedNames));
    }
}
function deconflictImportsOther(usedNames, imports, dependencies, interop, preserveModules) {
    for (const chunkOrExternalModule of dependencies) {
        chunkOrExternalModule.variableName = getSafeName(chunkOrExternalModule.variableName, usedNames);
    }
    for (const variable of imports) {
        const module = variable.module;
        if (module instanceof ExternalModule) {
            const name = variable.name;
            if (name === 'default' && interop && (module.exportsNamespace || module.exportsNames)) {
                variable.setRenderNames(null, module.variableName + '__default');
            }
            else if (name === '*' || name === 'default') {
                variable.setRenderNames(null, module.variableName);
            }
            else {
                variable.setRenderNames(module.variableName, null);
            }
        }
        else {
            const chunk = module.chunk;
            if (chunk.exportMode === 'default' || (preserveModules && variable.isNamespace)) {
                variable.setRenderNames(null, chunk.variableName);
            }
            else {
                variable.setRenderNames(chunk.variableName, chunk.getVariableExportName(variable));
            }
        }
    }
}
function deconflictTopLevelVariables(usedNames, modules) {
    for (const module of modules) {
        for (const variable of module.scope.variables.values()) {
            if (variable.included &&
                // this will only happen for exports in some formats
                !(variable.renderBaseName ||
                    (variable instanceof ExportDefaultVariable && variable.getOriginalVariable() !== variable))) {
                variable.setRenderNames(null, getSafeName(variable.name, usedNames));
            }
        }
        const namespace = module.getOrCreateNamespace();
        if (namespace.included) {
            namespace.setRenderNames(null, getSafeName(namespace.name, usedNames));
        }
    }
}

const compareExecIndex = (unitA, unitB) => unitA.execIndex > unitB.execIndex ? 1 : -1;
function sortByExecutionOrder(units) {
    units.sort(compareExecIndex);
}
function analyseModuleExecution(entryModules) {
    let nextExecIndex = 0;
    const cyclePaths = [];
    const analysedModules = {};
    const orderedModules = [];
    const dynamicImports = [];
    const parents = {};
    const analyseModule = (module) => {
        if (analysedModules[module.id])
            return;
        if (module instanceof ExternalModule) {
            module.execIndex = nextExecIndex++;
            analysedModules[module.id] = true;
            return;
        }
        for (const dependency of module.dependencies) {
            if (dependency.id in parents) {
                if (!analysedModules[dependency.id]) {
                    cyclePaths.push(getCyclePath(dependency.id, module.id, parents));
                }
                continue;
            }
            parents[dependency.id] = module.id;
            analyseModule(dependency);
        }
        for (const { resolution } of module.dynamicImports) {
            if (resolution instanceof Module && dynamicImports.indexOf(resolution) === -1) {
                dynamicImports.push(resolution);
            }
        }
        module.execIndex = nextExecIndex++;
        analysedModules[module.id] = true;
        orderedModules.push(module);
    };
    for (const curEntry of entryModules) {
        if (!parents[curEntry.id]) {
            parents[curEntry.id] = null;
            analyseModule(curEntry);
        }
    }
    for (const curEntry of dynamicImports) {
        if (!parents[curEntry.id]) {
            parents[curEntry.id] = null;
            analyseModule(curEntry);
        }
    }
    return { orderedModules, cyclePaths };
}
function getCyclePath(id, parentId, parents) {
    const path = [index.relativeId(id)];
    let curId = parentId;
    while (curId !== id) {
        path.push(index.relativeId(curId));
        curId = parents[curId];
        if (!curId)
            break;
    }
    path.push(path[0]);
    path.reverse();
    return path;
}

function guessIndentString(code) {
    const lines = code.split('\n');
    const tabbed = lines.filter(line => /^\t+/.test(line));
    const spaced = lines.filter(line => /^ {2,}/.test(line));
    if (tabbed.length === 0 && spaced.length === 0) {
        return null;
    }
    // More lines tabbed than spaced? Assume tabs, and
    // default to tabs in the case of a tie (or nothing
    // to go on)
    if (tabbed.length >= spaced.length) {
        return '\t';
    }
    // Otherwise, we need to guess the multiple
    const min = spaced.reduce((previous, current) => {
        const numSpaces = /^ +/.exec(current)[0].length;
        return Math.min(numSpaces, previous);
    }, Infinity);
    return new Array(min + 1).join(' ');
}
function getIndentString(modules, options) {
    if (options.indent !== true)
        return options.indent || '';
    for (let i = 0; i < modules.length; i++) {
        const indent = guessIndentString(modules[i].originalCode);
        if (indent !== null)
            return indent;
    }
    return '\t';
}

function decodedSourcemap(map) {
    if (!map)
        return null;
    if (typeof map === 'string') {
        map = JSON.parse(map);
    }
    if (map.mappings === '') {
        return {
            mappings: [],
            names: [],
            sources: [],
            version: 3
        };
    }
    let mappings;
    if (typeof map.mappings === 'string') {
        mappings = decode(map.mappings);
    }
    else {
        mappings = map.mappings;
    }
    return Object.assign(Object.assign({}, map), { mappings });
}

function renderChunk({ graph, chunk, renderChunk, code, sourcemapChain, options }) {
    const renderChunkReducer = (code, result, plugin) => {
        if (result == null)
            return code;
        if (typeof result === 'string')
            result = {
                code: result,
                map: undefined
            };
        // strict null check allows 'null' maps to not be pushed to the chain, while 'undefined' gets the missing map warning
        if (result.map !== null) {
            const map = decodedSourcemap(result.map);
            sourcemapChain.push(map || { missing: true, plugin: plugin.name });
        }
        return result.code;
    };
    let inTransformBundle = false;
    let inRenderChunk = true;
    return graph.pluginDriver
        .hookReduceArg0('renderChunk', [code, renderChunk, options], renderChunkReducer)
        .then(code => {
        inRenderChunk = false;
        return graph.pluginDriver.hookReduceArg0('transformChunk', [code, options, chunk], renderChunkReducer);
    })
        .then(code => {
        inTransformBundle = true;
        return graph.pluginDriver.hookReduceArg0('transformBundle', [code, options, chunk], renderChunkReducer);
    })
        .catch(err => {
        if (inRenderChunk)
            throw err;
        return error(err, {
            code: inTransformBundle ? 'BAD_BUNDLE_TRANSFORMER' : 'BAD_CHUNK_TRANSFORMER',
            message: `Error transforming ${(inTransformBundle ? 'bundle' : 'chunk') +
                (err.plugin ? ` with '${err.plugin}' plugin` : '')}: ${err.message}`,
            plugin: err.plugin
        });
    });
}

function renderNamePattern(pattern, patternName, replacements) {
    if (!index.isPlainPathFragment(pattern))
        return error(errFailedValidation(`Invalid pattern "${pattern}" for "${patternName}", patterns can be neither absolute nor relative paths and must not contain invalid characters.`));
    return pattern.replace(/\[(\w+)\]/g, (_match, type) => {
        if (!replacements.hasOwnProperty(type)) {
            return error(errFailedValidation(`"[${type}]" is not a valid placeholder in "${patternName}" pattern.`));
        }
        const replacement = replacements[type]();
        if (!index.isPlainPathFragment(replacement))
            return error(errFailedValidation(`Invalid substitution "${replacement}" for placeholder "[${type}]" in "${patternName}" pattern, can be neither absolute nor relative path.`));
        return replacement;
    });
}
function makeUnique(name, existingNames) {
    if (name in existingNames === false)
        return name;
    const ext = path.extname(name);
    name = name.substr(0, name.length - ext.length);
    let uniqueName, uniqueIndex = 1;
    while (existingNames[(uniqueName = name + ++uniqueIndex + ext)])
        ;
    return uniqueName;
}

const NON_ASSET_EXTENSIONS = ['.js', '.jsx', '.ts', '.tsx'];
function getGlobalName(module, globals, graph, hasExports) {
    let globalName;
    if (typeof globals === 'function') {
        globalName = globals(module.id);
    }
    else if (globals) {
        globalName = globals[module.id];
    }
    if (globalName) {
        return globalName;
    }
    if (hasExports) {
        graph.warn({
            code: 'MISSING_GLOBAL_NAME',
            guess: module.variableName,
            message: `No name was provided for external module '${module.id}' in output.globals – guessing '${module.variableName}'`,
            source: module.id
        });
        return module.variableName;
    }
}
function isChunkRendered(chunk) {
    return !chunk.isEmpty || chunk.entryModules.length > 0 || chunk.manualChunkAlias !== null;
}
class Chunk$1 {
    constructor(graph, orderedModules) {
        this.entryModules = [];
        this.exportMode = 'named';
        this.facadeModule = null;
        this.id = null;
        this.indentString = undefined;
        this.manualChunkAlias = null;
        this.usedModules = undefined;
        this.variableName = 'chunk';
        this.dependencies = undefined;
        this.dynamicDependencies = undefined;
        this.exportNames = Object.create(null);
        this.exports = new Set();
        this.fileName = null;
        this.imports = new Set();
        this.name = null;
        this.needsExportsShim = false;
        this.renderedDeclarations = undefined;
        this.renderedHash = undefined;
        this.renderedModuleSources = new Map();
        this.renderedSource = null;
        this.renderedSourceLength = undefined;
        this.sortedExportNames = null;
        this.graph = graph;
        this.orderedModules = orderedModules;
        this.execIndex = orderedModules.length > 0 ? orderedModules[0].execIndex : Infinity;
        this.isEmpty = true;
        for (const module of orderedModules) {
            if (this.isEmpty && module.isIncluded()) {
                this.isEmpty = false;
            }
            if (module.manualChunkAlias) {
                this.manualChunkAlias = module.manualChunkAlias;
            }
            module.chunk = this;
            if (module.isEntryPoint ||
                module.dynamicallyImportedBy.some(module => orderedModules.indexOf(module) === -1)) {
                this.entryModules.push(module);
            }
        }
        const moduleForNaming = this.entryModules[0] || this.orderedModules[this.orderedModules.length - 1];
        if (moduleForNaming) {
            this.variableName = makeLegal(path.basename(moduleForNaming.chunkName ||
                moduleForNaming.manualChunkAlias ||
                index.getAliasName(moduleForNaming.id)));
        }
    }
    static generateFacade(graph, facadedModule, facadeName) {
        const chunk = new Chunk$1(graph, []);
        chunk.assignFacadeName(facadeName, facadedModule);
        if (!facadedModule.facadeChunk) {
            facadedModule.facadeChunk = chunk;
        }
        chunk.dependencies = [facadedModule.chunk];
        chunk.dynamicDependencies = [];
        chunk.facadeModule = facadedModule;
        for (const exportName of facadedModule.getAllExportNames()) {
            const tracedVariable = facadedModule.getVariableForExportName(exportName);
            chunk.exports.add(tracedVariable);
            chunk.exportNames[exportName] = tracedVariable;
        }
        return chunk;
    }
    canModuleBeFacade(moduleExportNamesByVariable) {
        for (const exposedVariable of this.exports) {
            if (!moduleExportNamesByVariable.has(exposedVariable)) {
                return false;
            }
        }
        return true;
    }
    generateFacades() {
        const facades = [];
        for (const module of this.entryModules) {
            const requiredFacades = Array.from(module.userChunkNames).map(name => ({
                name
            }));
            if (requiredFacades.length === 0 && module.isUserDefinedEntryPoint) {
                requiredFacades.push({});
            }
            requiredFacades.push(...Array.from(module.chunkFileNames).map(fileName => ({ fileName })));
            if (requiredFacades.length === 0) {
                requiredFacades.push({});
            }
            if (!this.facadeModule) {
                const exportNamesByVariable = module.getExportNamesByVariable();
                if (this.graph.preserveModules || this.canModuleBeFacade(exportNamesByVariable)) {
                    this.facadeModule = module;
                    module.facadeChunk = this;
                    for (const [variable, exportNames] of exportNamesByVariable) {
                        for (const exportName of exportNames) {
                            this.exportNames[exportName] = variable;
                        }
                    }
                    this.assignFacadeName(requiredFacades.shift(), module);
                }
            }
            for (const facadeName of requiredFacades) {
                facades.push(Chunk$1.generateFacade(this.graph, module, facadeName));
            }
        }
        return facades;
    }
    generateId(addons, options, existingNames, includeHash) {
        if (this.fileName !== null) {
            return this.fileName;
        }
        const [pattern, patternName] = this.facadeModule && this.facadeModule.isUserDefinedEntryPoint
            ? [options.entryFileNames || '[name].js', 'output.entryFileNames']
            : [options.chunkFileNames || '[name]-[hash].js', 'output.chunkFileNames'];
        return makeUnique(renderNamePattern(pattern, patternName, {
            format: () => (options.format === 'es' ? 'esm' : options.format),
            hash: () => includeHash
                ? this.computeContentHashWithDependencies(addons, options, existingNames)
                : '[hash]',
            name: () => this.getChunkName()
        }), existingNames);
    }
    generateIdPreserveModules(preserveModulesRelativeDir, options, existingNames) {
        const id = this.orderedModules[0].id;
        const sanitizedId = index.sanitizeFileName(id);
        let path$1;
        if (index.isAbsolute(id)) {
            const extension = path.extname(id);
            const name = renderNamePattern(options.entryFileNames ||
                (NON_ASSET_EXTENSIONS.includes(extension) ? '[name].js' : '[name][extname].js'), 'output.entryFileNames', {
                ext: () => extension.substr(1),
                extname: () => extension,
                format: () => (options.format === 'es' ? 'esm' : options.format),
                name: () => this.getChunkName()
            });
            path$1 = relative(preserveModulesRelativeDir, `${path.dirname(sanitizedId)}/${name}`);
        }
        else {
            path$1 = `_virtual/${path.basename(sanitizedId)}`;
        }
        return makeUnique(index.normalize(path$1), existingNames);
    }
    generateInternalExports(options) {
        if (this.facadeModule !== null)
            return;
        const mangle = options.format === 'system' || options.format === 'es' || options.compact;
        let i = 0, safeExportName;
        this.exportNames = Object.create(null);
        this.sortedExportNames = null;
        if (mangle) {
            for (const variable of this.exports) {
                const suggestedName = variable.name[0];
                if (!this.exportNames[suggestedName]) {
                    this.exportNames[suggestedName] = variable;
                }
                else {
                    do {
                        safeExportName = toBase64(++i);
                        // skip past leading number identifiers
                        if (safeExportName.charCodeAt(0) === 49 /* '1' */) {
                            i += 9 * Math.pow(64, (safeExportName.length - 1));
                            safeExportName = toBase64(i);
                        }
                    } while (RESERVED_NAMES[safeExportName] || this.exportNames[safeExportName]);
                    this.exportNames[safeExportName] = variable;
                }
            }
        }
        else {
            for (const variable of this.exports) {
                i = 0;
                safeExportName = variable.name;
                while (this.exportNames[safeExportName]) {
                    safeExportName = variable.name + '$' + ++i;
                }
                this.exportNames[safeExportName] = variable;
            }
        }
    }
    getChunkName() {
        return this.name || (this.name = index.sanitizeFileName(this.getFallbackChunkName()));
    }
    getDynamicImportIds() {
        return this.dynamicDependencies.map(chunk => chunk.id).filter(Boolean);
    }
    getExportNames() {
        return (this.sortedExportNames || (this.sortedExportNames = Object.keys(this.exportNames).sort()));
    }
    getImportIds() {
        return this.dependencies.map(chunk => chunk.id).filter(Boolean);
    }
    getRenderedHash() {
        if (this.renderedHash)
            return this.renderedHash;
        if (!this.renderedSource)
            return '';
        const hash = _256();
        const hashAugmentation = this.calculateHashAugmentation();
        hash.update(hashAugmentation);
        hash.update(this.renderedSource.toString());
        hash.update(this.getExportNames()
            .map(exportName => {
            const variable = this.exportNames[exportName];
            return `${index.relativeId(variable.module.id).replace(/\\/g, '/')}:${variable.name}:${exportName}`;
        })
            .join(','));
        return (this.renderedHash = hash.digest('hex'));
    }
    getRenderedSourceLength() {
        if (this.renderedSourceLength !== undefined)
            return this.renderedSourceLength;
        return (this.renderedSourceLength = this.renderedSource.length());
    }
    getVariableExportName(variable) {
        if (this.graph.preserveModules && variable instanceof NamespaceVariable) {
            return '*';
        }
        for (const exportName of Object.keys(this.exportNames)) {
            if (this.exportNames[exportName] === variable)
                return exportName;
        }
        throw new Error(`Internal Error: Could not find export name for variable ${variable.name}.`);
    }
    link() {
        const dependencies = new Set();
        const dynamicDependencies = new Set();
        for (const module of this.orderedModules) {
            this.addDependenciesToChunk(module.getTransitiveDependencies(), dependencies);
            this.addDependenciesToChunk(module.dynamicDependencies, dynamicDependencies);
            this.setUpChunkImportsAndExportsForModule(module);
        }
        this.dependencies = Array.from(dependencies);
        this.dynamicDependencies = Array.from(dynamicDependencies);
    }
    /*
     * Performs a full merge of another chunk into this chunk
     * chunkList allows updating references in other chunks for the merged chunk to this chunk
     * A new facade will be added to chunkList if tainting exports of either as an entry point
     */
    merge(chunk, chunkList, options, inputBase) {
        if (this.facadeModule !== null || chunk.facadeModule !== null)
            throw new Error('Internal error: Code splitting chunk merges not supported for facades');
        for (const module of chunk.orderedModules) {
            module.chunk = this;
            this.orderedModules.push(module);
        }
        for (const variable of chunk.imports) {
            if (!this.imports.has(variable) && variable.module.chunk !== this) {
                this.imports.add(variable);
            }
        }
        // NB detect when exported variables are orphaned by the merge itself
        // (involves reverse tracing dependents)
        for (const variable of chunk.exports) {
            if (!this.exports.has(variable)) {
                this.exports.add(variable);
            }
        }
        const thisOldExportNames = this.exportNames;
        // regenerate internal names
        this.generateInternalExports(options);
        const updateRenderedDeclaration = (dep, oldExportNames) => {
            if (dep.imports) {
                for (const impt of dep.imports) {
                    impt.imported = this.getVariableExportName(oldExportNames[impt.imported]);
                }
            }
            if (dep.reexports) {
                for (const reexport of dep.reexports) {
                    reexport.imported = this.getVariableExportName(oldExportNames[reexport.imported]);
                }
            }
        };
        const mergeRenderedDeclaration = (into, from) => {
            if (from.imports) {
                if (!into.imports) {
                    into.imports = from.imports;
                }
                else {
                    into.imports = into.imports.concat(from.imports);
                }
            }
            if (from.reexports) {
                if (!into.reexports) {
                    into.reexports = from.reexports;
                }
                else {
                    into.reexports = into.reexports.concat(from.reexports);
                }
            }
            if (!into.exportsNames && from.exportsNames) {
                into.exportsNames = true;
            }
            if (!into.exportsDefault && from.exportsDefault) {
                into.exportsDefault = true;
            }
            into.name = this.variableName;
        };
        // go through the other chunks and update their dependencies
        // also update their import and reexport names in the process
        for (const c of chunkList) {
            let includedDeclaration = undefined;
            for (let i = 0; i < c.dependencies.length; i++) {
                const dep = c.dependencies[i];
                if ((dep === chunk || dep === this) && includedDeclaration) {
                    const duplicateDeclaration = c.renderedDeclarations.dependencies[i];
                    updateRenderedDeclaration(duplicateDeclaration, dep === chunk ? chunk.exportNames : thisOldExportNames);
                    mergeRenderedDeclaration(includedDeclaration, duplicateDeclaration);
                    c.renderedDeclarations.dependencies.splice(i, 1);
                    c.dependencies.splice(i--, 1);
                }
                else if (dep === chunk) {
                    c.dependencies[i] = this;
                    includedDeclaration = c.renderedDeclarations.dependencies[i];
                    updateRenderedDeclaration(includedDeclaration, chunk.exportNames);
                }
                else if (dep === this) {
                    includedDeclaration = c.renderedDeclarations.dependencies[i];
                    updateRenderedDeclaration(includedDeclaration, thisOldExportNames);
                }
            }
        }
        // re-render the merged chunk
        this.preRender(options, inputBase);
    }
    // prerender allows chunk hashes and names to be generated before finalizing
    preRender(options, inputBase) {
        timeStart('render modules', 3);
        const magicString = new Bundle({ separator: options.compact ? '' : '\n\n' });
        this.usedModules = [];
        this.indentString = options.compact ? '' : getIndentString(this.orderedModules, options);
        const n = options.compact ? '' : '\n';
        const _ = options.compact ? '' : ' ';
        const renderOptions = {
            compact: options.compact,
            dynamicImportFunction: options.dynamicImportFunction,
            format: options.format,
            freeze: options.freeze !== false,
            indent: this.indentString,
            namespaceToStringTag: options.namespaceToStringTag === true,
            varOrConst: options.preferConst ? 'const' : 'var'
        };
        // Make sure the direct dependencies of a chunk are present to maintain execution order
        for (const { module } of this.imports) {
            const chunkOrExternal = (module instanceof Module ? module.chunk : module);
            if (this.dependencies.indexOf(chunkOrExternal) === -1) {
                this.dependencies.push(chunkOrExternal);
            }
        }
        // for static and dynamic entry points, inline the execution list to avoid loading latency
        if (!this.graph.preserveModules && this.facadeModule !== null) {
            for (const dep of this.dependencies) {
                if (dep instanceof Chunk$1)
                    this.inlineChunkDependencies(dep, true);
            }
        }
        // prune empty dependency chunks, inlining their side-effect dependencies
        for (let i = 0; i < this.dependencies.length; i++) {
            const dep = this.dependencies[i];
            if (dep instanceof Chunk$1 && dep.isEmpty) {
                this.dependencies.splice(i--, 1);
                this.inlineChunkDependencies(dep, false);
            }
        }
        sortByExecutionOrder(this.dependencies);
        this.prepareDynamicImports();
        this.setIdentifierRenderResolutions(options);
        let hoistedSource = '';
        const renderedModules = (this.renderedModules = Object.create(null));
        for (const module of this.orderedModules) {
            let renderedLength = 0;
            if (module.isIncluded()) {
                const source = module.render(renderOptions).trim();
                if (options.compact && source.lastLine().indexOf('//') !== -1)
                    source.append('\n');
                const namespace = module.getOrCreateNamespace();
                if (namespace.included || source.length() > 0) {
                    renderedLength = source.length();
                    this.renderedModuleSources.set(module, source);
                    magicString.addSource(source);
                    this.usedModules.push(module);
                    if (namespace.included && !this.graph.preserveModules) {
                        const rendered = namespace.renderBlock(renderOptions);
                        if (namespace.renderFirst())
                            hoistedSource += n + rendered;
                        else
                            magicString.addSource(new MagicString(rendered));
                    }
                }
            }
            const { renderedExports, removedExports } = module.getRenderedExports();
            renderedModules[module.id] = {
                originalLength: module.originalCode.length,
                removedExports,
                renderedExports,
                renderedLength
            };
        }
        if (hoistedSource)
            magicString.prepend(hoistedSource + n + n);
        if (this.needsExportsShim) {
            magicString.prepend(`${n}${renderOptions.varOrConst} ${MISSING_EXPORT_SHIM_VARIABLE}${_}=${_}void 0;${n}${n}`);
        }
        if (options.compact) {
            this.renderedSource = magicString;
        }
        else {
            this.renderedSource = magicString.trim();
        }
        this.renderedSourceLength = undefined;
        this.renderedHash = undefined;
        if (this.getExportNames().length === 0 && this.getImportIds().length === 0 && this.isEmpty) {
            this.graph.warn({
                code: 'EMPTY_BUNDLE',
                message: 'Generated an empty bundle'
            });
        }
        this.setExternalRenderPaths(options, inputBase);
        this.renderedDeclarations = {
            dependencies: this.getChunkDependencyDeclarations(options),
            exports: this.exportMode === 'none' ? [] : this.getChunkExportDeclarations()
        };
        timeEnd('render modules', 3);
    }
    render(options, addons, outputChunk) {
        timeStart('render format', 3);
        if (!this.renderedSource)
            throw new Error('Internal error: Chunk render called before preRender');
        const format = options.format;
        const finalise = finalisers[format];
        if (!finalise) {
            error({
                code: 'INVALID_OPTION',
                message: `Invalid format: ${format} - valid options are ${Object.keys(finalisers).join(', ')}.`
            });
        }
        if (options.dynamicImportFunction && format !== 'es') {
            this.graph.warn({
                code: 'INVALID_OPTION',
                message: '"output.dynamicImportFunction" is ignored for formats other than "esm".'
            });
        }
        // populate ids in the rendered declarations only here
        // as chunk ids known only after prerender
        for (let i = 0; i < this.dependencies.length; i++) {
            const dep = this.dependencies[i];
            if (dep instanceof ExternalModule && !dep.renormalizeRenderPath)
                continue;
            const renderedDependency = this.renderedDeclarations.dependencies[i];
            const depId = dep instanceof ExternalModule ? renderedDependency.id : dep.id;
            if (dep instanceof Chunk$1)
                renderedDependency.namedExportsMode = dep.exportMode !== 'default';
            renderedDependency.id = this.getRelativePath(depId);
        }
        this.finaliseDynamicImports(format);
        this.finaliseImportMetas(format);
        const hasExports = this.renderedDeclarations.exports.length !== 0 ||
            this.renderedDeclarations.dependencies.some(dep => (dep.reexports && dep.reexports.length !== 0));
        let usesTopLevelAwait = false;
        const accessedGlobals = new Set();
        for (const module of this.orderedModules) {
            if (module.usesTopLevelAwait) {
                usesTopLevelAwait = true;
            }
            const accessedGlobalVariablesByFormat = module.scope.accessedGlobalVariablesByFormat;
            const accessedGlobalVariables = accessedGlobalVariablesByFormat && accessedGlobalVariablesByFormat.get(format);
            if (accessedGlobalVariables) {
                for (const name of accessedGlobalVariables) {
                    accessedGlobals.add(name);
                }
            }
        }
        if (usesTopLevelAwait && format !== 'es' && format !== 'system') {
            error({
                code: 'INVALID_TLA_FORMAT',
                message: `Module format ${format} does not support top-level await. Use the "es" or "system" output formats rather.`
            });
        }
        const magicString = finalise(this.renderedSource, {
            accessedGlobals,
            dependencies: this.renderedDeclarations.dependencies,
            exports: this.renderedDeclarations.exports,
            hasExports,
            indentString: this.indentString,
            intro: addons.intro,
            isEntryModuleFacade: this.facadeModule !== null && this.facadeModule.isEntryPoint,
            namedExportsMode: this.exportMode !== 'default',
            outro: addons.outro,
            usesTopLevelAwait,
            varOrConst: options.preferConst ? 'const' : 'var',
            warn: this.graph.warn.bind(this.graph)
        }, options);
        if (addons.banner)
            magicString.prepend(addons.banner);
        if (addons.footer)
            magicString.append(addons.footer);
        const prevCode = magicString.toString();
        timeEnd('render format', 3);
        let map = null;
        const chunkSourcemapChain = [];
        return renderChunk({
            chunk: this,
            code: prevCode,
            graph: this.graph,
            options,
            renderChunk: outputChunk,
            sourcemapChain: chunkSourcemapChain
        }).then((code) => {
            if (options.sourcemap) {
                timeStart('sourcemap', 3);
                let file;
                if (options.file)
                    file = path.resolve(options.sourcemapFile || options.file);
                else if (options.dir)
                    file = path.resolve(options.dir, this.id);
                else
                    file = path.resolve(this.id);
                const decodedMap = magicString.generateDecodedMap({});
                map = collapseSourcemaps(this, file, decodedMap, this.usedModules, chunkSourcemapChain, options.sourcemapExcludeSources);
                map.sources = map.sources.map(sourcePath => index.normalize(options.sourcemapPathTransform ? options.sourcemapPathTransform(sourcePath) : sourcePath));
                timeEnd('sourcemap', 3);
            }
            if (options.compact !== true && code[code.length - 1] !== '\n')
                code += '\n';
            return { code, map };
        });
    }
    visitDependencies(handleDependency) {
        const toBeVisited = [this];
        const visited = new Set();
        for (const current of toBeVisited) {
            handleDependency(current);
            if (current instanceof ExternalModule)
                continue;
            for (const dependency of current.dependencies.concat(current.dynamicDependencies)) {
                if (!visited.has(dependency)) {
                    visited.add(dependency);
                    toBeVisited.push(dependency);
                }
            }
        }
    }
    visitStaticDependenciesUntilCondition(isConditionSatisfied) {
        const seen = new Set();
        function visitDep(dep) {
            if (seen.has(dep))
                return undefined;
            seen.add(dep);
            if (dep instanceof Chunk$1) {
                for (const subDep of dep.dependencies) {
                    if (visitDep(subDep))
                        return true;
                }
            }
            return isConditionSatisfied(dep) === true;
        }
        return visitDep(this);
    }
    addDependenciesToChunk(moduleDependencies, chunkDependencies) {
        for (const depModule of moduleDependencies) {
            if (depModule.chunk === this) {
                continue;
            }
            let dependency;
            if (depModule instanceof Module) {
                dependency = depModule.chunk;
            }
            else {
                if (!(depModule.used || depModule.moduleSideEffects)) {
                    continue;
                }
                dependency = depModule;
            }
            chunkDependencies.add(dependency);
        }
    }
    assignFacadeName({ fileName, name }, facadedModule) {
        if (fileName) {
            this.fileName = fileName;
        }
        else {
            this.name = index.sanitizeFileName(name || facadedModule.chunkName || index.getAliasName(facadedModule.id));
        }
    }
    calculateHashAugmentation() {
        const facadeModule = this.facadeModule;
        const getChunkName = this.getChunkName.bind(this);
        const preRenderedChunk = {
            dynamicImports: this.getDynamicImportIds(),
            exports: this.getExportNames(),
            facadeModuleId: facadeModule && facadeModule.id,
            imports: this.getImportIds(),
            isDynamicEntry: facadeModule !== null && facadeModule.dynamicallyImportedBy.length > 0,
            isEntry: facadeModule !== null && facadeModule.isEntryPoint,
            modules: this.renderedModules,
            get name() {
                return getChunkName();
            }
        };
        const hashAugmentation = this.graph.pluginDriver.hookReduceValueSync('augmentChunkHash', '', [preRenderedChunk], (hashAugmentation, pluginHash) => {
            if (pluginHash) {
                hashAugmentation += pluginHash;
            }
            return hashAugmentation;
        });
        return hashAugmentation;
    }
    computeContentHashWithDependencies(addons, options, existingNames) {
        const hash = _256();
        hash.update([addons.intro, addons.outro, addons.banner, addons.footer].map(addon => addon || '').join(':'));
        hash.update(options.format);
        this.visitDependencies(dep => {
            if (dep instanceof ExternalModule) {
                hash.update(':' + dep.renderPath);
            }
            else {
                hash.update(dep.getRenderedHash());
                hash.update(dep.generateId(addons, options, existingNames, false));
            }
        });
        return hash.digest('hex').substr(0, 8);
    }
    finaliseDynamicImports(format) {
        for (const [module, code] of this.renderedModuleSources) {
            for (const { node, resolution } of module.dynamicImports) {
                if (!resolution)
                    continue;
                if (resolution instanceof Module) {
                    if (resolution.chunk !== this && isChunkRendered(resolution.chunk)) {
                        const resolutionChunk = resolution.facadeChunk || resolution.chunk;
                        node.renderFinalResolution(code, `'${this.getRelativePath(resolutionChunk.id)}'`, format);
                    }
                }
                else {
                    node.renderFinalResolution(code, resolution instanceof ExternalModule
                        ? `'${resolution.renormalizeRenderPath
                            ? this.getRelativePath(resolution.renderPath)
                            : resolution.id}'`
                        : resolution, format);
                }
            }
        }
    }
    finaliseImportMetas(format) {
        for (const [module, code] of this.renderedModuleSources) {
            for (const importMeta of module.importMetas) {
                importMeta.renderFinalMechanism(code, this.id, format, this.graph.pluginDriver);
            }
        }
    }
    getChunkDependencyDeclarations(options) {
        const reexportDeclarations = new Map();
        for (let exportName of this.getExportNames()) {
            let exportChunk;
            let importName;
            let needsLiveBinding = false;
            if (exportName[0] === '*') {
                needsLiveBinding = options.externalLiveBindings !== false;
                exportChunk = this.graph.moduleById.get(exportName.substr(1));
                importName = exportName = '*';
            }
            else {
                const variable = this.exportNames[exportName];
                const module = variable.module;
                // skip local exports
                if (!module || module.chunk === this)
                    continue;
                if (module instanceof Module) {
                    exportChunk = module.chunk;
                    importName = exportChunk.getVariableExportName(variable);
                    needsLiveBinding = variable.isReassigned;
                }
                else {
                    exportChunk = module;
                    importName = variable.name;
                    needsLiveBinding = options.externalLiveBindings !== false;
                }
            }
            let reexportDeclaration = reexportDeclarations.get(exportChunk);
            if (!reexportDeclaration)
                reexportDeclarations.set(exportChunk, (reexportDeclaration = []));
            reexportDeclaration.push({ imported: importName, reexported: exportName, needsLiveBinding });
        }
        const renderedImports = new Set();
        const dependencies = [];
        for (const dep of this.dependencies) {
            const imports = [];
            for (const variable of this.imports) {
                const renderedVariable = variable instanceof ExportDefaultVariable ? variable.getOriginalVariable() : variable;
                if ((variable.module instanceof Module
                    ? variable.module.chunk === dep
                    : variable.module === dep) &&
                    !renderedImports.has(renderedVariable)) {
                    renderedImports.add(renderedVariable);
                    imports.push({
                        imported: variable.module instanceof ExternalModule
                            ? variable.name
                            : variable.module.chunk.getVariableExportName(variable),
                        local: variable.getName()
                    });
                }
            }
            const reexports = reexportDeclarations.get(dep);
            let exportsNames, exportsDefault;
            let namedExportsMode = true;
            if (dep instanceof ExternalModule) {
                exportsNames = dep.exportsNames || dep.exportsNamespace;
                exportsDefault = 'default' in dep.declarations;
            }
            else {
                exportsNames = true;
                // we don't want any interop patterns to trigger
                exportsDefault = false;
                namedExportsMode = dep.exportMode !== 'default';
            }
            let id = undefined;
            let globalName = undefined;
            if (dep instanceof ExternalModule) {
                id = dep.renderPath;
                if (options.format === 'umd' || options.format === 'iife') {
                    globalName = getGlobalName(dep, options.globals, this.graph, exportsNames || exportsDefault);
                }
            }
            dependencies.push({
                exportsDefault,
                exportsNames,
                globalName,
                id,
                imports: imports.length > 0 ? imports : null,
                isChunk: dep instanceof Chunk$1,
                name: dep.variableName,
                namedExportsMode,
                reexports
            });
        }
        return dependencies;
    }
    getChunkExportDeclarations() {
        const exports = [];
        for (const exportName of this.getExportNames()) {
            if (exportName[0] === '*')
                continue;
            const variable = this.exportNames[exportName];
            const module = variable.module;
            if (module && module.chunk !== this)
                continue;
            let hoisted = false;
            let uninitialized = false;
            if (variable instanceof LocalVariable) {
                if (variable.init === UNDEFINED_EXPRESSION) {
                    uninitialized = true;
                }
                for (const declaration of variable.declarations) {
                    if (declaration.parent instanceof FunctionDeclaration ||
                        (declaration instanceof ExportDefaultDeclaration &&
                            declaration.declaration instanceof FunctionDeclaration)) {
                        hoisted = true;
                        break;
                    }
                }
            }
            else if (variable instanceof GlobalVariable) {
                hoisted = true;
            }
            const localName = variable.getName();
            exports.push({
                exported: exportName === '*' ? localName : exportName,
                hoisted,
                local: localName,
                uninitialized
            });
        }
        return exports;
    }
    getFallbackChunkName() {
        if (this.manualChunkAlias) {
            return this.manualChunkAlias;
        }
        if (this.fileName) {
            return index.getAliasName(this.fileName);
        }
        return index.getAliasName(this.orderedModules[this.orderedModules.length - 1].id);
    }
    getRelativePath(targetPath) {
        const relativePath = index.normalize(relative(path.dirname(this.id), targetPath));
        return relativePath.startsWith('../') ? relativePath : './' + relativePath;
    }
    inlineChunkDependencies(chunk, deep) {
        for (const dep of chunk.dependencies) {
            if (dep instanceof ExternalModule) {
                if (this.dependencies.indexOf(dep) === -1)
                    this.dependencies.push(dep);
            }
            else {
                if (dep === this || this.dependencies.indexOf(dep) !== -1)
                    continue;
                if (!dep.isEmpty)
                    this.dependencies.push(dep);
                if (deep)
                    this.inlineChunkDependencies(dep, true);
            }
        }
    }
    prepareDynamicImports() {
        for (const module of this.orderedModules) {
            for (const { node, resolution } of module.dynamicImports) {
                if (!node.included)
                    continue;
                if (resolution instanceof Module) {
                    if (resolution.chunk === this) {
                        const namespace = resolution.getOrCreateNamespace();
                        node.setResolution('named', namespace);
                    }
                    else {
                        node.setResolution(resolution.chunk.exportMode);
                    }
                }
                else {
                    node.setResolution('auto');
                }
            }
        }
    }
    setExternalRenderPaths(options, inputBase) {
        for (const dependency of this.dependencies.concat(this.dynamicDependencies)) {
            if (dependency instanceof ExternalModule) {
                dependency.setRenderPath(options, inputBase);
            }
        }
    }
    setIdentifierRenderResolutions(options) {
        for (const exportName of this.getExportNames()) {
            const exportVariable = this.exportNames[exportName];
            if (exportVariable) {
                if (exportVariable instanceof ExportShimVariable) {
                    this.needsExportsShim = true;
                }
                exportVariable.exportName = exportName;
                if (options.format !== 'es' &&
                    options.format !== 'system' &&
                    exportVariable.isReassigned &&
                    !exportVariable.isId &&
                    !(exportVariable instanceof ExportDefaultVariable && exportVariable.hasId)) {
                    exportVariable.setRenderNames('exports', exportName);
                }
                else {
                    exportVariable.setRenderNames(null, null);
                }
            }
        }
        const usedNames = new Set();
        if (this.needsExportsShim) {
            usedNames.add(MISSING_EXPORT_SHIM_VARIABLE);
        }
        if (options.format !== 'es') {
            usedNames.add('exports');
            if (options.format === 'cjs') {
                usedNames
                    .add(INTEROP_DEFAULT_VARIABLE)
                    .add('require')
                    .add('module')
                    .add('__filename')
                    .add('__dirname');
            }
        }
        deconflictChunk(this.orderedModules, this.dependencies, this.imports, usedNames, options.format, options.interop !== false, this.graph.preserveModules);
    }
    setUpChunkImportsAndExportsForModule(module) {
        for (const variable of module.imports) {
            if (variable.module.chunk !== this) {
                this.imports.add(variable);
                if (variable.module instanceof Module) {
                    variable.module.chunk.exports.add(variable);
                }
            }
        }
        if (module.isEntryPoint ||
            module.dynamicallyImportedBy.some(importer => importer.chunk !== this)) {
            const map = module.getExportNamesByVariable();
            for (const exportedVariable of map.keys()) {
                this.exports.add(exportedVariable);
                const exportingModule = exportedVariable.module;
                if (exportingModule && exportingModule.chunk && exportingModule.chunk !== this) {
                    exportingModule.chunk.exports.add(exportedVariable);
                }
            }
        }
        if (module.getOrCreateNamespace().included) {
            for (const reexportName of Object.keys(module.reexports)) {
                const reexport = module.reexports[reexportName];
                const variable = reexport.module.getVariableForExportName(reexport.localName);
                if (variable.module.chunk !== this) {
                    this.imports.add(variable);
                    if (variable.module instanceof Module) {
                        variable.module.chunk.exports.add(variable);
                    }
                }
            }
        }
        for (const { node, resolution } of module.dynamicImports) {
            if (node.included && resolution instanceof Module && resolution.chunk === this)
                resolution.getOrCreateNamespace().include();
        }
    }
}

/*
 * Given a chunk list, perform optimizations on that chunk list
 * to reduce the mumber of chunks. Mutates the chunks array.
 *
 * Manual chunks (with chunk.chunkAlias already set) are preserved
 * Entry points are carefully preserved as well
 *
 */
function optimizeChunks(chunks, options, CHUNK_GROUPING_SIZE, inputBase) {
    for (let chunkIndex = 0; chunkIndex < chunks.length; chunkIndex++) {
        const mainChunk = chunks[chunkIndex];
        const execGroup = [];
        mainChunk.visitStaticDependenciesUntilCondition(dep => {
            if (dep instanceof Chunk$1) {
                execGroup.push(dep);
            }
        });
        if (execGroup.length < 2) {
            continue;
        }
        let execGroupIndex = 1;
        let seekingFirstMergeCandidate = true;
        let lastChunk = undefined, chunk = execGroup[0], nextChunk = execGroup[1];
        const isMergeCandidate = (chunk) => {
            if (chunk.facadeModule !== null || chunk.manualChunkAlias !== null) {
                return false;
            }
            if (!nextChunk || nextChunk.facadeModule !== null) {
                return false;
            }
            if (chunk.getRenderedSourceLength() > CHUNK_GROUPING_SIZE) {
                return false;
            }
            // if (!chunk.isPure()) continue;
            return true;
        };
        do {
            if (seekingFirstMergeCandidate) {
                if (isMergeCandidate(chunk)) {
                    seekingFirstMergeCandidate = false;
                }
                continue;
            }
            let remainingSize = CHUNK_GROUPING_SIZE - lastChunk.getRenderedSourceLength() - chunk.getRenderedSourceLength();
            if (remainingSize <= 0) {
                if (!isMergeCandidate(chunk)) {
                    seekingFirstMergeCandidate = true;
                }
                continue;
            }
            // if (!chunk.isPure()) continue;
            const chunkDependencies = new Set();
            chunk.visitStaticDependenciesUntilCondition(dep => chunkDependencies.add(dep));
            const ignoreSizeChunks = new Set([chunk, lastChunk]);
            if (lastChunk.visitStaticDependenciesUntilCondition(dep => {
                if (dep === chunk || dep === lastChunk) {
                    return false;
                }
                if (chunkDependencies.has(dep)) {
                    return false;
                }
                if (dep instanceof ExternalModule) {
                    return true;
                }
                remainingSize -= dep.getRenderedSourceLength();
                if (remainingSize <= 0) {
                    return true;
                }
                ignoreSizeChunks.add(dep);
            })) {
                if (!isMergeCandidate(chunk)) {
                    seekingFirstMergeCandidate = true;
                }
                continue;
            }
            if (chunk.visitStaticDependenciesUntilCondition(dep => {
                if (ignoreSizeChunks.has(dep)) {
                    return false;
                }
                if (dep instanceof ExternalModule) {
                    return true;
                }
                remainingSize -= dep.getRenderedSourceLength();
                if (remainingSize <= 0) {
                    return true;
                }
            })) {
                if (!isMergeCandidate(chunk)) {
                    seekingFirstMergeCandidate = true;
                }
                continue;
            }
            // within the size limit -> merge!
            const optimizedChunkIndex = chunks.indexOf(chunk);
            if (optimizedChunkIndex <= chunkIndex)
                chunkIndex--;
            chunks.splice(optimizedChunkIndex, 1);
            lastChunk.merge(chunk, chunks, options, inputBase);
            execGroup.splice(--execGroupIndex, 1);
            chunk = lastChunk;
            // keep going to see if we can merge this with the next again
            if (nextChunk && !isMergeCandidate(nextChunk)) {
                seekingFirstMergeCandidate = true;
            }
        } while (((lastChunk = chunk), (chunk = nextChunk), (nextChunk = execGroup[++execGroupIndex]), chunk));
    }
    return chunks;
}

const tt = acorn.tokTypes;
const skipWhiteSpace = /(?:\s|\/\/.*|\/\*[^]*?\*\/)*/g;
const nextTokenIsDot = parser => {
    skipWhiteSpace.lastIndex = parser.pos;
    let skip = skipWhiteSpace.exec(parser.input);
    let next = parser.pos + skip[0].length;
    return parser.input.slice(next, next + 1) === ".";
};
var acornImportMeta = function (Parser) {
    return class extends Parser {
        parseExprAtom(refDestructuringErrors) {
            if (this.type !== tt._import || !nextTokenIsDot(this))
                return super.parseExprAtom(refDestructuringErrors);
            if (!this.options.allowImportExportEverywhere && !this.inModule) {
                this.raise(this.start, "'import' and 'export' may appear only with 'sourceType: module'");
            }
            let node = this.startNode();
            node.meta = this.parseIdent(true);
            this.expect(tt.dot);
            node.property = this.parseIdent(true);
            if (node.property.name !== "meta") {
                this.raiseRecoverable(node.property.start, "The only valid meta property for import is import.meta");
            }
            if (this.containsEsc) {
                this.raiseRecoverable(node.property.start, "\"meta\" in import.meta must not contain escape sequences");
            }
            return this.finishNode(node, "MetaProperty");
        }
        parseStatement(context, topLevel, exports) {
            if (this.type !== tt._import || !nextTokenIsDot(this)) {
                return super.parseStatement(context, topLevel, exports);
            }
            let node = this.startNode();
            let expr = this.parseExpression();
            return this.parseExpressionStatement(node, expr);
        }
    };
};

class UndefinedVariable extends Variable {
    constructor() {
        super('undefined');
    }
    getLiteralValueAtPath() {
        return undefined;
    }
}

class GlobalScope extends Scope {
    constructor() {
        super();
        this.variables.set('undefined', new UndefinedVariable());
    }
    findVariable(name) {
        let variable = this.variables.get(name);
        if (!variable) {
            variable = new GlobalVariable(name);
            this.variables.set(name, variable);
        }
        return variable;
    }
}

const getNewTrackedPaths = () => ({
    paths: Object.create(null),
    tracked: false,
    unknownPath: null
});
class EntityPathTracker {
    constructor() {
        this.entityPaths = new Map();
    }
    track(entity, path) {
        let trackedPaths = this.entityPaths.get(entity);
        if (!trackedPaths) {
            trackedPaths = getNewTrackedPaths();
            this.entityPaths.set(entity, trackedPaths);
        }
        let pathIndex = 0, trackedSubPaths;
        while (pathIndex < path.length) {
            const key = path[pathIndex];
            if (typeof key === 'string') {
                trackedSubPaths = trackedPaths.paths[key];
                if (!trackedSubPaths) {
                    trackedSubPaths = getNewTrackedPaths();
                    trackedPaths.paths[key] = trackedSubPaths;
                }
            }
            else {
                trackedSubPaths = trackedPaths.unknownPath;
                if (!trackedSubPaths) {
                    trackedSubPaths = getNewTrackedPaths();
                    trackedPaths.unknownPath = trackedSubPaths;
                }
            }
            trackedPaths = trackedSubPaths;
            pathIndex++;
        }
        const found = trackedPaths.tracked;
        trackedPaths.tracked = true;
        return found;
    }
}

var BuildPhase;
(function (BuildPhase) {
    BuildPhase[BuildPhase["LOAD_AND_PARSE"] = 0] = "LOAD_AND_PARSE";
    BuildPhase[BuildPhase["ANALYSE"] = 1] = "ANALYSE";
    BuildPhase[BuildPhase["GENERATE"] = 2] = "GENERATE";
})(BuildPhase || (BuildPhase = {}));

function generateAssetFileName(name, source, output) {
    const emittedName = name || 'asset';
    return makeUnique(renderNamePattern(output.assetFileNames, 'output.assetFileNames', {
        hash() {
            const hash = _256();
            hash.update(emittedName);
            hash.update(':');
            hash.update(source);
            return hash.digest('hex').substr(0, 8);
        },
        ext: () => path.extname(emittedName).substr(1),
        extname: () => path.extname(emittedName),
        name: () => emittedName.substr(0, emittedName.length - path.extname(emittedName).length)
    }), output.bundle);
}
function reserveFileNameInBundle(fileName, bundle) {
    if (fileName in bundle) {
        return error(errFileNameConflict(fileName));
    }
    bundle[fileName] = FILE_PLACEHOLDER;
}
const FILE_PLACEHOLDER = {
    type: 'placeholder'
};
function hasValidType(emittedFile) {
    return (emittedFile &&
        (emittedFile.type === 'asset' ||
            emittedFile.type === 'chunk'));
}
function hasValidName(emittedFile) {
    const validatedName = emittedFile.fileName || emittedFile.name;
    return (!validatedName || (typeof validatedName === 'string' && index.isPlainPathFragment(validatedName)));
}
function getValidSource(source, emittedFile, fileReferenceId) {
    if (typeof source !== 'string' && !Buffer.isBuffer(source)) {
        const assetName = emittedFile.fileName || emittedFile.name || fileReferenceId;
        return error(errFailedValidation(`Could not set source for ${typeof assetName === 'string' ? `asset "${assetName}"` : 'unnamed asset'}, asset source needs to be a string of Buffer.`));
    }
    return source;
}
function getAssetFileName(file, referenceId) {
    if (typeof file.fileName !== 'string') {
        return error(errAssetNotFinalisedForFileName(file.name || referenceId));
    }
    return file.fileName;
}
function getChunkFileName(file) {
    const fileName = file.fileName || (file.module && file.module.facadeChunk.id);
    if (!fileName)
        return error(errChunkNotGeneratedForFileName(file.fileName || file.name));
    return fileName;
}
class FileEmitter {
    constructor(graph) {
        this.filesByReferenceId = new Map();
        // tslint:disable member-ordering
        this.buildFilesByReferenceId = this.filesByReferenceId;
        this.output = null;
        this.emitFile = (emittedFile) => {
            if (!hasValidType(emittedFile)) {
                return error(errFailedValidation(`Emitted files must be of type "asset" or "chunk", received "${emittedFile &&
                    emittedFile.type}".`));
            }
            if (!hasValidName(emittedFile)) {
                return error(errFailedValidation(`The "fileName" or "name" properties of emitted files must be strings that are neither absolute nor relative paths and do not contain invalid characters, received "${emittedFile.fileName ||
                    emittedFile.name}".`));
            }
            if (emittedFile.type === 'chunk') {
                return this.emitChunk(emittedFile);
            }
            else {
                return this.emitAsset(emittedFile);
            }
        };
        this.getFileName = (fileReferenceId) => {
            const emittedFile = this.filesByReferenceId.get(fileReferenceId);
            if (!emittedFile)
                return error(errFileReferenceIdNotFoundForFilename(fileReferenceId));
            if (emittedFile.type === 'chunk') {
                return getChunkFileName(emittedFile);
            }
            else {
                return getAssetFileName(emittedFile, fileReferenceId);
            }
        };
        this.setAssetSource = (referenceId, requestedSource) => {
            const consumedFile = this.filesByReferenceId.get(referenceId);
            if (!consumedFile)
                return error(errAssetReferenceIdNotFoundForSetSource(referenceId));
            if (consumedFile.type !== 'asset') {
                return error(errFailedValidation(`Asset sources can only be set for emitted assets but "${referenceId}" is an emitted chunk.`));
            }
            if (consumedFile.source !== undefined) {
                return error(errAssetSourceAlreadySet(consumedFile.name || referenceId));
            }
            const source = getValidSource(requestedSource, consumedFile, referenceId);
            if (this.output) {
                this.finalizeAsset(consumedFile, source, referenceId, this.output);
            }
            else {
                consumedFile.source = source;
            }
        };
        this.graph = graph;
    }
    startOutput(outputBundle, assetFileNames) {
        this.filesByReferenceId = new Map(this.buildFilesByReferenceId);
        this.output = {
            assetFileNames,
            bundle: outputBundle
        };
        for (const emittedFile of this.filesByReferenceId.values()) {
            if (emittedFile.fileName) {
                reserveFileNameInBundle(emittedFile.fileName, this.output.bundle);
            }
        }
        for (const [referenceId, consumedFile] of this.filesByReferenceId.entries()) {
            if (consumedFile.type === 'asset' && consumedFile.source !== undefined) {
                this.finalizeAsset(consumedFile, consumedFile.source, referenceId, this.output);
            }
        }
    }
    assertAssetsFinalized() {
        for (const [referenceId, emittedFile] of this.filesByReferenceId.entries()) {
            if (emittedFile.type === 'asset' && typeof emittedFile.fileName !== 'string')
                error(errNoAssetSourceSet(emittedFile.name || referenceId));
        }
    }
    emitAsset(emittedAsset) {
        const source = typeof emittedAsset.source !== 'undefined'
            ? getValidSource(emittedAsset.source, emittedAsset, null)
            : undefined;
        const consumedAsset = {
            fileName: emittedAsset.fileName,
            name: emittedAsset.name,
            source,
            type: 'asset'
        };
        const referenceId = this.assignReferenceId(consumedAsset, emittedAsset.fileName || emittedAsset.name || emittedAsset.type);
        if (this.output) {
            if (emittedAsset.fileName) {
                reserveFileNameInBundle(emittedAsset.fileName, this.output.bundle);
            }
            if (source !== undefined) {
                this.finalizeAsset(consumedAsset, source, referenceId, this.output);
            }
        }
        return referenceId;
    }
    emitChunk(emittedChunk) {
        if (this.graph.phase > BuildPhase.LOAD_AND_PARSE) {
            error(errInvalidRollupPhaseForChunkEmission());
        }
        if (typeof emittedChunk.id !== 'string') {
            return error(errFailedValidation(`Emitted chunks need to have a valid string id, received "${emittedChunk.id}"`));
        }
        const consumedChunk = {
            fileName: emittedChunk.fileName,
            module: null,
            name: emittedChunk.name || emittedChunk.id,
            type: 'chunk'
        };
        this.graph.moduleLoader
            .addEntryModules([
            {
                fileName: emittedChunk.fileName || null,
                id: emittedChunk.id,
                name: emittedChunk.name || null
            }
        ], false)
            .then(({ newEntryModules: [module] }) => {
            consumedChunk.module = module;
        })
            .catch(() => {
            // Avoid unhandled Promise rejection as the error will be thrown later
            // once module loading has finished
        });
        return this.assignReferenceId(consumedChunk, emittedChunk.id);
    }
    assignReferenceId(file, idBase) {
        let referenceId;
        do {
            const hash = _256();
            if (referenceId) {
                hash.update(referenceId);
            }
            else {
                hash.update(idBase);
            }
            referenceId = hash.digest('hex').substr(0, 8);
        } while (this.filesByReferenceId.has(referenceId));
        this.filesByReferenceId.set(referenceId, file);
        return referenceId;
    }
    finalizeAsset(consumedFile, source, referenceId, output) {
        const fileName = consumedFile.fileName ||
            this.findExistingAssetFileNameWithSource(output.bundle, source) ||
            generateAssetFileName(consumedFile.name, source, output);
        // We must not modify the original assets to avoid interaction between outputs
        const assetWithFileName = Object.assign(Object.assign({}, consumedFile), { source, fileName });
        this.filesByReferenceId.set(referenceId, assetWithFileName);
        const graph = this.graph;
        output.bundle[fileName] = {
            fileName,
            get isAsset() {
                graph.warnDeprecation('Accessing "isAsset" on files in the bundle is deprecated, please use "type === \'asset\'" instead', false);
                return true;
            },
            source,
            type: 'asset'
        };
    }
    findExistingAssetFileNameWithSource(bundle, source) {
        for (const fileName of Object.keys(bundle)) {
            const outputFile = bundle[fileName];
            if (outputFile.type === 'asset' &&
                (Buffer.isBuffer(source) && Buffer.isBuffer(outputFile.source)
                    ? source.equals(outputFile.source)
                    : source === outputFile.source))
                return fileName;
        }
        return null;
    }
}

const ANONYMOUS_PLUGIN_PREFIX = 'at position ';
const deprecatedHooks = [
    { active: true, deprecated: 'ongenerate', replacement: 'generateBundle' },
    { active: true, deprecated: 'onwrite', replacement: 'generateBundle/writeBundle' },
    { active: true, deprecated: 'transformBundle', replacement: 'renderChunk' },
    { active: true, deprecated: 'transformChunk', replacement: 'renderChunk' },
    { active: false, deprecated: 'resolveAssetUrl', replacement: 'resolveFileUrl' }
];
function warnDeprecatedHooks(plugins, graph) {
    for (const { active, deprecated, replacement } of deprecatedHooks) {
        for (const plugin of plugins) {
            if (deprecated in plugin) {
                graph.warnDeprecation({
                    message: `The "${deprecated}" hook used by plugin ${plugin.name} is deprecated. The "${replacement}" hook should be used instead.`,
                    plugin: plugin.name
                }, active);
            }
        }
    }
}
function throwPluginError(err, plugin, { hook, id } = {}) {
    if (typeof err === 'string')
        err = { message: err };
    if (err.code && err.code !== Errors.PLUGIN_ERROR) {
        err.pluginCode = err.code;
    }
    err.code = Errors.PLUGIN_ERROR;
    err.plugin = plugin;
    if (hook) {
        err.hook = hook;
    }
    if (id) {
        err.id = id;
    }
    return error(err);
}
function createPluginDriver(graph, options, pluginCache, watcher) {
    warnDeprecatedHooks(options.plugins, graph);
    function getDeprecatedHookHandler(handler, handlerName, newHandlerName, pluginName, acitveDeprecation) {
        let deprecationWarningShown = false;
        return ((...args) => {
            if (!deprecationWarningShown) {
                deprecationWarningShown = true;
                graph.warnDeprecation({
                    message: `The "this.${handlerName}" plugin context function used by plugin ${pluginName} is deprecated. The "this.${newHandlerName}" plugin context function should be used instead.`,
                    plugin: pluginName
                }, acitveDeprecation);
            }
            return handler(...args);
        });
    }
    const plugins = [
        ...options.plugins,
        getRollupDefaultPlugin(options.preserveSymlinks)
    ];
    const fileEmitter = new FileEmitter(graph);
    const existingPluginKeys = new Set();
    const pluginContexts = plugins.map((plugin, pidx) => {
        let cacheable = true;
        if (typeof plugin.cacheKey !== 'string') {
            if (plugin.name.startsWith(ANONYMOUS_PLUGIN_PREFIX) || existingPluginKeys.has(plugin.name)) {
                cacheable = false;
            }
            else {
                existingPluginKeys.add(plugin.name);
            }
        }
        let cacheInstance;
        if (!pluginCache) {
            cacheInstance = noCache;
        }
        else if (cacheable) {
            const cacheKey = plugin.cacheKey || plugin.name;
            cacheInstance = createPluginCache(pluginCache[cacheKey] || (pluginCache[cacheKey] = Object.create(null)));
        }
        else {
            cacheInstance = uncacheablePlugin(plugin.name);
        }
        const context = {
            addWatchFile(id) {
                if (graph.phase >= BuildPhase.GENERATE)
                    this.error(errInvalidRollupPhaseForAddWatchFile());
                graph.watchFiles[id] = true;
            },
            cache: cacheInstance,
            emitAsset: getDeprecatedHookHandler((name, source) => fileEmitter.emitFile({ type: 'asset', name, source }), 'emitAsset', 'emitFile', plugin.name, false),
            emitChunk: getDeprecatedHookHandler((id, options) => fileEmitter.emitFile({ type: 'chunk', id, name: options && options.name }), 'emitChunk', 'emitFile', plugin.name, false),
            emitFile: fileEmitter.emitFile,
            error(err) {
                return throwPluginError(err, plugin.name);
            },
            getAssetFileName: getDeprecatedHookHandler(fileEmitter.getFileName, 'getAssetFileName', 'getFileName', plugin.name, false),
            getChunkFileName: getDeprecatedHookHandler(fileEmitter.getFileName, 'getChunkFileName', 'getFileName', plugin.name, false),
            getFileName: fileEmitter.getFileName,
            getModuleInfo(moduleId) {
                const foundModule = graph.moduleById.get(moduleId);
                if (foundModule == null) {
                    throw new Error(`Unable to find module ${moduleId}`);
                }
                return {
                    hasModuleSideEffects: foundModule.moduleSideEffects,
                    id: foundModule.id,
                    importedIds: foundModule instanceof ExternalModule
                        ? []
                        : foundModule.sources.map(id => foundModule.resolvedIds[id].id),
                    isEntry: foundModule instanceof Module && foundModule.isEntryPoint,
                    isExternal: foundModule instanceof ExternalModule
                };
            },
            isExternal: getDeprecatedHookHandler((id, parentId, isResolved = false) => graph.moduleLoader.isExternal(id, parentId, isResolved), 'isExternal', 'resolve', plugin.name, false),
            meta: {
                rollupVersion: index.version
            },
            get moduleIds() {
                return graph.moduleById.keys();
            },
            parse: graph.contextParse,
            resolve(source, importer, options) {
                return graph.moduleLoader.resolveId(source, importer, options && options.skipSelf ? pidx : null);
            },
            resolveId: getDeprecatedHookHandler((source, importer) => graph.moduleLoader
                .resolveId(source, importer)
                .then(resolveId => resolveId && resolveId.id), 'resolveId', 'resolve', plugin.name, false),
            setAssetSource: fileEmitter.setAssetSource,
            warn(warning) {
                if (typeof warning === 'string')
                    warning = { message: warning };
                if (warning.code)
                    warning.pluginCode = warning.code;
                warning.code = 'PLUGIN_WARNING';
                warning.plugin = plugin.name;
                graph.warn(warning);
            },
            watcher: watcher
                ? (() => {
                    let deprecationWarningShown = false;
                    function deprecatedWatchListener(event, handler) {
                        if (!deprecationWarningShown) {
                            context.warn({
                                code: 'PLUGIN_WATCHER_DEPRECATED',
                                message: `this.watcher usage is deprecated in plugins. Use the watchChange plugin hook and this.addWatchFile() instead.`
                            });
                            deprecationWarningShown = true;
                        }
                        return watcher.on(event, handler);
                    }
                    return Object.assign(Object.assign({}, watcher), { addListener: deprecatedWatchListener, on: deprecatedWatchListener });
                })()
                : undefined
        };
        return context;
    });
    function runHookSync(hookName, args, pluginIndex, permitValues = false, hookContext) {
        const plugin = plugins[pluginIndex];
        let context = pluginContexts[pluginIndex];
        const hook = plugin[hookName];
        if (!hook)
            return undefined;
        if (hookContext) {
            context = hookContext(context, plugin);
            if (!context || context === pluginContexts[pluginIndex])
                throw new Error('Internal Rollup error: hookContext must return a new context object.');
        }
        try {
            // permit values allows values to be returned instead of a functional hook
            if (typeof hook !== 'function') {
                if (permitValues)
                    return hook;
                error({
                    code: 'INVALID_PLUGIN_HOOK',
                    message: `Error running plugin hook ${hookName} for ${plugin.name}, expected a function hook.`
                });
            }
            return hook.apply(context, args);
        }
        catch (err) {
            return throwPluginError(err, plugin.name, { hook: hookName });
        }
    }
    function runHook(hookName, args, pluginIndex, permitValues = false, hookContext) {
        const plugin = plugins[pluginIndex];
        let context = pluginContexts[pluginIndex];
        const hook = plugin[hookName];
        if (!hook)
            return undefined;
        if (hookContext) {
            context = hookContext(context, plugin);
            if (!context || context === pluginContexts[pluginIndex])
                throw new Error('Internal Rollup error: hookContext must return a new context object.');
        }
        return Promise.resolve()
            .then(() => {
            // permit values allows values to be returned instead of a functional hook
            if (typeof hook !== 'function') {
                if (permitValues)
                    return hook;
                error({
                    code: 'INVALID_PLUGIN_HOOK',
                    message: `Error running plugin hook ${hookName} for ${plugin.name}, expected a function hook.`
                });
            }
            return hook.apply(context, args);
        })
            .catch(err => throwPluginError(err, plugin.name, { hook: hookName }));
    }
    const pluginDriver = {
        emitFile: fileEmitter.emitFile,
        finaliseAssets() {
            fileEmitter.assertAssetsFinalized();
        },
        getFileName: fileEmitter.getFileName,
        // chains, ignores returns
        hookSeq(name, args, hookContext) {
            let promise = Promise.resolve();
            for (let i = 0; i < plugins.length; i++)
                promise = promise.then(() => runHook(name, args, i, false, hookContext));
            return promise;
        },
        // chains, ignores returns
        hookSeqSync(name, args, hookContext) {
            for (let i = 0; i < plugins.length; i++)
                runHookSync(name, args, i, false, hookContext);
        },
        // chains, first non-null result stops and returns
        hookFirst(name, args, hookContext, skip) {
            let promise = Promise.resolve();
            for (let i = 0; i < plugins.length; i++) {
                if (skip === i)
                    continue;
                promise = promise.then((result) => {
                    if (result != null)
                        return result;
                    return runHook(name, args, i, false, hookContext);
                });
            }
            return promise;
        },
        // chains synchronously, first non-null result stops and returns
        hookFirstSync(name, args, hookContext) {
            for (let i = 0; i < plugins.length; i++) {
                const result = runHookSync(name, args, i, false, hookContext);
                if (result != null)
                    return result;
            }
            return null;
        },
        // parallel, ignores returns
        hookParallel(name, args, hookContext) {
            const promises = [];
            for (let i = 0; i < plugins.length; i++) {
                const hookPromise = runHook(name, args, i, false, hookContext);
                if (!hookPromise)
                    continue;
                promises.push(hookPromise);
            }
            return Promise.all(promises).then(() => { });
        },
        // chains, reduces returns of type R, to type T, handling the reduced value as the first hook argument
        hookReduceArg0(name, [arg0, ...args], reduce, hookContext) {
            let promise = Promise.resolve(arg0);
            for (let i = 0; i < plugins.length; i++) {
                promise = promise.then(arg0 => {
                    const hookPromise = runHook(name, [arg0, ...args], i, false, hookContext);
                    if (!hookPromise)
                        return arg0;
                    return hookPromise.then((result) => reduce.call(pluginContexts[i], arg0, result, plugins[i]));
                });
            }
            return promise;
        },
        // chains synchronously, reduces returns of type R, to type T, handling the reduced value as the first hook argument
        hookReduceArg0Sync(name, [arg0, ...args], reduce, hookContext) {
            for (let i = 0; i < plugins.length; i++) {
                const result = runHookSync(name, [arg0, ...args], i, false, hookContext);
                arg0 = reduce.call(pluginContexts[i], arg0, result, plugins[i]);
            }
            return arg0;
        },
        // chains, reduces returns of type R, to type T, handling the reduced value separately. permits hooks as values.
        hookReduceValue(name, initial, args, reduce, hookContext) {
            let promise = Promise.resolve(initial);
            for (let i = 0; i < plugins.length; i++) {
                promise = promise.then(value => {
                    const hookPromise = runHook(name, args, i, true, hookContext);
                    if (!hookPromise)
                        return value;
                    return hookPromise.then((result) => reduce.call(pluginContexts[i], value, result, plugins[i]));
                });
            }
            return promise;
        },
        // chains, reduces returns of type R, to type T, handling the reduced value separately. permits hooks as values.
        hookReduceValueSync(name, initial, args, reduce, hookContext) {
            let acc = initial;
            for (let i = 0; i < plugins.length; i++) {
                const result = runHookSync(name, args, i, true, hookContext);
                acc = reduce.call(pluginContexts[i], acc, result, plugins[i]);
            }
            return acc;
        },
        startOutput(outputBundle, assetFileNames) {
            fileEmitter.startOutput(outputBundle, assetFileNames);
        }
    };
    return pluginDriver;
}
function createPluginCache(cache) {
    return {
        has(id) {
            const item = cache[id];
            if (!item)
                return false;
            item[0] = 0;
            return true;
        },
        get(id) {
            const item = cache[id];
            if (!item)
                return undefined;
            item[0] = 0;
            return item[1];
        },
        set(id, value) {
            cache[id] = [0, value];
        },
        delete(id) {
            return delete cache[id];
        }
    };
}
function trackPluginCache(pluginCache) {
    const result = { used: false, cache: undefined };
    result.cache = {
        has(id) {
            result.used = true;
            return pluginCache.has(id);
        },
        get(id) {
            result.used = true;
            return pluginCache.get(id);
        },
        set(id, value) {
            result.used = true;
            return pluginCache.set(id, value);
        },
        delete(id) {
            result.used = true;
            return pluginCache.delete(id);
        }
    };
    return result;
}
const noCache = {
    has() {
        return false;
    },
    get() {
        return undefined;
    },
    set() { },
    delete() {
        return false;
    }
};
function uncacheablePluginError(pluginName) {
    if (pluginName.startsWith(ANONYMOUS_PLUGIN_PREFIX))
        error({
            code: 'ANONYMOUS_PLUGIN_CACHE',
            message: 'A plugin is trying to use the Rollup cache but is not declaring a plugin name or cacheKey.'
        });
    else
        error({
            code: 'DUPLICATE_PLUGIN_NAME',
            message: `The plugin name ${pluginName} is being used twice in the same build. Plugin names must be distinct or provide a cacheKey (please post an issue to the plugin if you are a plugin user).`
        });
}
const uncacheablePlugin = pluginName => ({
    has() {
        uncacheablePluginError(pluginName);
        return false;
    },
    get() {
        uncacheablePluginError(pluginName);
        return undefined;
    },
    set() {
        uncacheablePluginError(pluginName);
    },
    delete() {
        uncacheablePluginError(pluginName);
        return false;
    }
});

function transform(graph, source, module) {
    const id = module.id;
    const sourcemapChain = [];
    let originalSourcemap = source.map === null ? null : decodedSourcemap(source.map);
    const originalCode = source.code;
    let ast = source.ast;
    const transformDependencies = [];
    const emittedFiles = [];
    let customTransformCache = false;
    let moduleSideEffects = null;
    let trackedPluginCache;
    let curPlugin;
    const curSource = source.code;
    function transformReducer(code, result, plugin) {
        // track which plugins use the custom this.cache to opt-out of transform caching
        if (!customTransformCache && trackedPluginCache.used)
            customTransformCache = true;
        if (customTransformCache) {
            if (result && typeof result === 'object' && Array.isArray(result.dependencies)) {
                for (const dep of result.dependencies) {
                    graph.watchFiles[path.resolve(path.dirname(id), dep)] = true;
                }
            }
        }
        else {
            // files emitted by a transform hook need to be emitted again if the hook is skipped
            if (emittedFiles.length)
                module.transformFiles = emittedFiles;
            if (result && typeof result === 'object' && Array.isArray(result.dependencies)) {
                // not great, but a useful way to track this without assuming WeakMap
                if (!curPlugin.warnedTransformDependencies)
                    graph.warnDeprecation(`Returning "dependencies" from the "transform" hook as done by plugin ${plugin.name} is deprecated. The "this.addWatchFile" plugin context function should be used instead.`, true);
                curPlugin.warnedTransformDependencies = true;
                for (const dep of result.dependencies)
                    transformDependencies.push(path.resolve(path.dirname(id), dep));
            }
        }
        if (typeof result === 'string') {
            result = {
                ast: undefined,
                code: result,
                map: undefined
            };
        }
        else if (result && typeof result === 'object') {
            if (typeof result.map === 'string') {
                result.map = JSON.parse(result.map);
            }
            if (typeof result.moduleSideEffects === 'boolean') {
                moduleSideEffects = result.moduleSideEffects;
            }
        }
        else {
            return code;
        }
        // strict null check allows 'null' maps to not be pushed to the chain, while 'undefined' gets the missing map warning
        if (result.map !== null) {
            const map = decodedSourcemap(result.map);
            sourcemapChain.push(map || { missing: true, plugin: plugin.name });
        }
        ast = result.ast;
        return result.code;
    }
    let setAssetSourceErr;
    return graph.pluginDriver
        .hookReduceArg0('transform', [curSource, id], transformReducer, (pluginContext, plugin) => {
        curPlugin = plugin;
        if (curPlugin.cacheKey)
            customTransformCache = true;
        else
            trackedPluginCache = trackPluginCache(pluginContext.cache);
        return Object.assign(Object.assign({}, pluginContext), { cache: trackedPluginCache ? trackedPluginCache.cache : pluginContext.cache, warn(warning, pos) {
                if (typeof warning === 'string')
                    warning = { message: warning };
                if (pos)
                    augmentCodeLocation(warning, pos, curSource, id);
                warning.id = id;
                warning.hook = 'transform';
                pluginContext.warn(warning);
            },
            error(err, pos) {
                if (typeof err === 'string')
                    err = { message: err };
                if (pos)
                    augmentCodeLocation(err, pos, curSource, id);
                err.id = id;
                err.hook = 'transform';
                return pluginContext.error(err);
            },
            emitAsset(name, source) {
                const emittedFile = { type: 'asset', name, source };
                emittedFiles.push(Object.assign({}, emittedFile));
                return graph.pluginDriver.emitFile(emittedFile);
            },
            emitChunk(id, options) {
                const emittedFile = { type: 'chunk', id, name: options && options.name };
                emittedFiles.push(Object.assign({}, emittedFile));
                return graph.pluginDriver.emitFile(emittedFile);
            },
            emitFile(emittedFile) {
                emittedFiles.push(emittedFile);
                return graph.pluginDriver.emitFile(emittedFile);
            },
            addWatchFile(id) {
                transformDependencies.push(id);
                pluginContext.addWatchFile(id);
            },
            setAssetSource(assetReferenceId, source) {
                pluginContext.setAssetSource(assetReferenceId, source);
                if (!customTransformCache && !setAssetSourceErr) {
                    try {
                        this.error({
                            code: 'INVALID_SETASSETSOURCE',
                            message: `setAssetSource cannot be called in transform for caching reasons. Use emitFile with a source, or call setAssetSource in another hook.`
                        });
                    }
                    catch (err) {
                        setAssetSourceErr = err;
                    }
                }
            },
            getCombinedSourcemap() {
                const combinedMap = collapseSourcemap(graph, id, originalCode, originalSourcemap, sourcemapChain);
                if (!combinedMap) {
                    const magicString = new MagicString(originalCode);
                    return magicString.generateMap({ includeContent: true, hires: true, source: id });
                }
                if (originalSourcemap !== combinedMap) {
                    originalSourcemap = combinedMap;
                    sourcemapChain.length = 0;
                }
                return new SourceMap(Object.assign(Object.assign({}, combinedMap), { file: null, sourcesContent: combinedMap.sourcesContent }));
            } });
    })
        .catch(err => throwPluginError(err, curPlugin.name, { hook: 'transform', id }))
        .then(code => {
        if (!customTransformCache && setAssetSourceErr)
            throw setAssetSourceErr;
        return {
            ast: ast,
            code,
            customTransformCache,
            moduleSideEffects,
            originalCode,
            originalSourcemap,
            sourcemapChain,
            transformDependencies
        };
    });
}

function normalizeRelativeExternalId(importer, source) {
    return index.isRelative(source) ? path.resolve(importer, '..', source) : source;
}
function getIdMatcher(option) {
    if (option === true) {
        return () => true;
    }
    if (typeof option === 'function') {
        return (id, ...args) => (!id.startsWith('\0') && option(id, ...args)) || false;
    }
    if (option) {
        const ids = new Set(Array.isArray(option) ? option : option ? [option] : []);
        return (id => ids.has(id));
    }
    return () => false;
}
function getHasModuleSideEffects(moduleSideEffectsOption, pureExternalModules, graph) {
    if (typeof moduleSideEffectsOption === 'boolean') {
        return () => moduleSideEffectsOption;
    }
    if (moduleSideEffectsOption === 'no-external') {
        return (_id, external) => !external;
    }
    if (typeof moduleSideEffectsOption === 'function') {
        return (id, external) => !id.startsWith('\0') ? moduleSideEffectsOption(id, external) !== false : true;
    }
    if (Array.isArray(moduleSideEffectsOption)) {
        const ids = new Set(moduleSideEffectsOption);
        return id => ids.has(id);
    }
    if (moduleSideEffectsOption) {
        graph.warn(errInvalidOption('treeshake.moduleSideEffects', 'please use one of false, "no-external", a function or an array'));
    }
    const isPureExternalModule = getIdMatcher(pureExternalModules);
    return (id, external) => !(external && isPureExternalModule(id));
}
class ModuleLoader {
    constructor(graph, modulesById, pluginDriver, external, getManualChunk, moduleSideEffects, pureExternalModules) {
        this.indexedEntryModules = [];
        this.latestLoadModulesPromise = Promise.resolve();
        this.manualChunkModules = {};
        this.nextEntryModuleIndex = 0;
        this.loadEntryModule = (unresolvedId, isEntry) => this.pluginDriver.hookFirst('resolveId', [unresolvedId, undefined]).then(resolveIdResult => {
            if (resolveIdResult === false ||
                (resolveIdResult && typeof resolveIdResult === 'object' && resolveIdResult.external)) {
                return error(errEntryCannotBeExternal(unresolvedId));
            }
            const id = resolveIdResult && typeof resolveIdResult === 'object'
                ? resolveIdResult.id
                : resolveIdResult;
            if (typeof id === 'string') {
                return this.fetchModule(id, undefined, true, isEntry);
            }
            return error(errUnresolvedEntry(unresolvedId));
        });
        this.graph = graph;
        this.modulesById = modulesById;
        this.pluginDriver = pluginDriver;
        this.isExternal = getIdMatcher(external);
        this.hasModuleSideEffects = getHasModuleSideEffects(moduleSideEffects, pureExternalModules, graph);
        this.getManualChunk = typeof getManualChunk === 'function' ? getManualChunk : () => null;
    }
    addEntryModules(unresolvedEntryModules, isUserDefined) {
        const firstEntryModuleIndex = this.nextEntryModuleIndex;
        this.nextEntryModuleIndex += unresolvedEntryModules.length;
        const loadNewEntryModulesPromise = Promise.all(unresolvedEntryModules.map(({ fileName, id, name }) => this.loadEntryModule(id, true).then(module => {
            if (fileName !== null) {
                module.chunkFileNames.add(fileName);
            }
            else if (name !== null) {
                if (module.chunkName === null) {
                    module.chunkName = name;
                }
                if (isUserDefined) {
                    module.userChunkNames.add(name);
                }
            }
            return module;
        }))).then(entryModules => {
            let moduleIndex = firstEntryModuleIndex;
            for (const entryModule of entryModules) {
                entryModule.isUserDefinedEntryPoint = entryModule.isUserDefinedEntryPoint || isUserDefined;
                const existingIndexModule = this.indexedEntryModules.find(indexedModule => indexedModule.module.id === entryModule.id);
                if (!existingIndexModule) {
                    this.indexedEntryModules.push({ module: entryModule, index: moduleIndex });
                }
                else {
                    existingIndexModule.index = Math.min(existingIndexModule.index, moduleIndex);
                }
                moduleIndex++;
            }
            this.indexedEntryModules.sort(({ index: indexA }, { index: indexB }) => indexA > indexB ? 1 : -1);
            return entryModules;
        });
        return this.awaitLoadModulesPromise(loadNewEntryModulesPromise).then(newEntryModules => ({
            entryModules: this.indexedEntryModules.map(({ module }) => module),
            manualChunkModulesByAlias: this.manualChunkModules,
            newEntryModules
        }));
    }
    addManualChunks(manualChunks) {
        const unresolvedManualChunks = [];
        for (const alias of Object.keys(manualChunks)) {
            const manualChunkIds = manualChunks[alias];
            for (const id of manualChunkIds) {
                unresolvedManualChunks.push({ id, alias });
            }
        }
        const loadNewManualChunkModulesPromise = Promise.all(unresolvedManualChunks.map(({ id }) => this.loadEntryModule(id, false))).then(manualChunkModules => {
            for (let index = 0; index < manualChunkModules.length; index++) {
                this.addModuleToManualChunk(unresolvedManualChunks[index].alias, manualChunkModules[index]);
            }
        });
        return this.awaitLoadModulesPromise(loadNewManualChunkModulesPromise);
    }
    resolveId(source, importer, skip) {
        return __awaiter(this, void 0, void 0, function* () {
            return this.normalizeResolveIdResult(this.isExternal(source, importer, false)
                ? false
                : yield this.pluginDriver.hookFirst('resolveId', [source, importer], null, skip), importer, source);
        });
    }
    addModuleToManualChunk(alias, module) {
        if (module.manualChunkAlias !== null && module.manualChunkAlias !== alias) {
            error(errCannotAssignModuleToChunk(module.id, alias, module.manualChunkAlias));
        }
        module.manualChunkAlias = alias;
        if (!this.manualChunkModules[alias]) {
            this.manualChunkModules[alias] = [];
        }
        this.manualChunkModules[alias].push(module);
    }
    awaitLoadModulesPromise(loadNewModulesPromise) {
        this.latestLoadModulesPromise = Promise.all([
            loadNewModulesPromise,
            this.latestLoadModulesPromise
        ]);
        const getCombinedPromise = () => {
            const startingPromise = this.latestLoadModulesPromise;
            return startingPromise.then(() => {
                if (this.latestLoadModulesPromise !== startingPromise) {
                    return getCombinedPromise();
                }
            });
        };
        return getCombinedPromise().then(() => loadNewModulesPromise);
    }
    fetchAllDependencies(module) {
        const fetchDynamicImportsPromise = Promise.all(module.getDynamicImportExpressions().map((specifier, index$1) => this.resolveDynamicImport(module, specifier, module.id).then(resolvedId => {
            if (resolvedId === null)
                return;
            const dynamicImport = module.dynamicImports[index$1];
            if (typeof resolvedId === 'string') {
                dynamicImport.resolution = resolvedId;
                return;
            }
            return this.fetchResolvedDependency(index.relativeId(resolvedId.id), module.id, resolvedId).then(module => {
                dynamicImport.resolution = module;
            });
        })));
        fetchDynamicImportsPromise.catch(() => { });
        return Promise.all(module.sources.map(source => this.resolveAndFetchDependency(module, source))).then(() => fetchDynamicImportsPromise);
    }
    fetchModule(id, importer, moduleSideEffects, isEntry) {
        const existingModule = this.modulesById.get(id);
        if (existingModule) {
            if (existingModule instanceof ExternalModule)
                throw new Error(`Cannot fetch external module ${id}`);
            existingModule.isEntryPoint = existingModule.isEntryPoint || isEntry;
            return Promise.resolve(existingModule);
        }
        const module = new Module(this.graph, id, moduleSideEffects, isEntry);
        this.modulesById.set(id, module);
        this.graph.watchFiles[id] = true;
        const manualChunkAlias = this.getManualChunk(id);
        if (typeof manualChunkAlias === 'string') {
            this.addModuleToManualChunk(manualChunkAlias, module);
        }
        timeStart('load modules', 3);
        return Promise.resolve(this.pluginDriver.hookFirst('load', [id]))
            .catch((err) => {
            timeEnd('load modules', 3);
            let msg = `Could not load ${id}`;
            if (importer)
                msg += ` (imported by ${importer})`;
            msg += `: ${err.message}`;
            err.message = msg;
            throw err;
        })
            .then(source => {
            timeEnd('load modules', 3);
            if (typeof source === 'string')
                return { code: source };
            if (source && typeof source === 'object' && typeof source.code === 'string')
                return source;
            return error(errBadLoader(id));
        })
            .then(sourceDescription => {
            const cachedModule = this.graph.cachedModules.get(id);
            if (cachedModule &&
                !cachedModule.customTransformCache &&
                cachedModule.originalCode === sourceDescription.code) {
                if (cachedModule.transformFiles) {
                    for (const emittedFile of cachedModule.transformFiles)
                        this.pluginDriver.emitFile(emittedFile);
                }
                return cachedModule;
            }
            if (typeof sourceDescription.moduleSideEffects === 'boolean') {
                module.moduleSideEffects = sourceDescription.moduleSideEffects;
            }
            return transform(this.graph, sourceDescription, module);
        })
            .then((source) => {
            module.setSource(source);
            this.modulesById.set(id, module);
            return this.fetchAllDependencies(module).then(() => {
                for (const name in module.exports) {
                    if (name !== 'default') {
                        module.exportsAll[name] = module.id;
                    }
                }
                module.exportAllSources.forEach(source => {
                    const id = module.resolvedIds[source].id;
                    const exportAllModule = this.modulesById.get(id);
                    if (exportAllModule instanceof ExternalModule)
                        return;
                    for (const name in exportAllModule.exportsAll) {
                        if (name in module.exportsAll) {
                            this.graph.warn(errNamespaceConflict(name, module, exportAllModule));
                        }
                        else {
                            module.exportsAll[name] = exportAllModule.exportsAll[name];
                        }
                    }
                });
                return module;
            });
        });
    }
    fetchResolvedDependency(source, importer, resolvedId) {
        if (resolvedId.external) {
            if (!this.modulesById.has(resolvedId.id)) {
                this.modulesById.set(resolvedId.id, new ExternalModule(this.graph, resolvedId.id, resolvedId.moduleSideEffects));
            }
            const externalModule = this.modulesById.get(resolvedId.id);
            if (!(externalModule instanceof ExternalModule)) {
                return error(errInternalIdCannotBeExternal(source, importer));
            }
            return Promise.resolve(externalModule);
        }
        else {
            return this.fetchModule(resolvedId.id, importer, resolvedId.moduleSideEffects, false);
        }
    }
    handleMissingImports(resolvedId, source, importer) {
        if (resolvedId === null) {
            if (index.isRelative(source)) {
                error(errUnresolvedImport(source, importer));
            }
            this.graph.warn(errUnresolvedImportTreatedAsExternal(source, importer));
            return {
                external: true,
                id: source,
                moduleSideEffects: this.hasModuleSideEffects(source, true)
            };
        }
        return resolvedId;
    }
    normalizeResolveIdResult(resolveIdResult, importer, source) {
        let id = '';
        let external = false;
        let moduleSideEffects = null;
        if (resolveIdResult) {
            if (typeof resolveIdResult === 'object') {
                id = resolveIdResult.id;
                if (resolveIdResult.external) {
                    external = true;
                }
                if (typeof resolveIdResult.moduleSideEffects === 'boolean') {
                    moduleSideEffects = resolveIdResult.moduleSideEffects;
                }
            }
            else {
                if (this.isExternal(resolveIdResult, importer, true)) {
                    external = true;
                }
                id = external ? normalizeRelativeExternalId(importer, resolveIdResult) : resolveIdResult;
            }
        }
        else {
            id = normalizeRelativeExternalId(importer, source);
            if (resolveIdResult !== false && !this.isExternal(id, importer, true)) {
                return null;
            }
            external = true;
        }
        return {
            external,
            id,
            moduleSideEffects: typeof moduleSideEffects === 'boolean'
                ? moduleSideEffects
                : this.hasModuleSideEffects(id, external)
        };
    }
    resolveAndFetchDependency(module, source) {
        return __awaiter(this, void 0, void 0, function* () {
            return this.fetchResolvedDependency(source, module.id, (module.resolvedIds[source] =
                module.resolvedIds[source] ||
                    this.handleMissingImports(yield this.resolveId(source, module.id), source, module.id)));
        });
    }
    resolveDynamicImport(module, specifier, importer) {
        return __awaiter(this, void 0, void 0, function* () {
            // TODO we only should expose the acorn AST here
            const resolution = yield this.pluginDriver.hookFirst('resolveDynamicImport', [
                specifier,
                importer
            ]);
            if (typeof specifier !== 'string') {
                if (typeof resolution === 'string') {
                    return resolution;
                }
                if (!resolution) {
                    return null;
                }
                return Object.assign({ external: false, moduleSideEffects: true }, resolution);
            }
            if (resolution == null) {
                return (module.resolvedIds[specifier] =
                    module.resolvedIds[specifier] ||
                        this.handleMissingImports(yield this.resolveId(specifier, module.id), specifier, module.id));
            }
            return this.handleMissingImports(this.normalizeResolveIdResult(resolution, importer, specifier), specifier, importer);
        });
    }
}

const CHAR_CODE_A = 97;
const CHAR_CODE_0 = 48;
function intToHex(num) {
    if (num < 10)
        return String.fromCharCode(CHAR_CODE_0 + num);
    else
        return String.fromCharCode(CHAR_CODE_A + (num - 10));
}
function Uint8ArrayToHexString(buffer) {
    let str = '';
    // hex conversion - 2 chars per 8 bit component
    for (let i = 0; i < buffer.length; i++) {
        const num = buffer[i];
        // big endian conversion, but whatever
        str += intToHex(num >> 4);
        str += intToHex(num & 0xf);
    }
    return str;
}
function Uint8ArrayXor(to, from) {
    for (let i = 0; i < to.length; i++)
        to[i] = to[i] ^ from[i];
    return to;
}
function randomUint8Array(len) {
    const buffer = new Uint8Array(len);
    for (let i = 0; i < buffer.length; i++)
        buffer[i] = Math.random() * (2 << 8);
    return buffer;
}

function assignChunkColouringHashes(entryModules, manualChunkModules) {
    let currentEntry, currentEntryHash;
    let modulesVisitedForCurrentEntry;
    const handledEntryPoints = new Set();
    const dynamicImports = [];
    const addCurrentEntryColourToModule = (module) => {
        if (currentEntry.manualChunkAlias) {
            module.manualChunkAlias = currentEntry.manualChunkAlias;
            module.entryPointsHash = currentEntryHash;
        }
        else {
            Uint8ArrayXor(module.entryPointsHash, currentEntryHash);
        }
        for (const dependency of module.dependencies) {
            if (dependency instanceof ExternalModule ||
                modulesVisitedForCurrentEntry.has(dependency.id)) {
                continue;
            }
            modulesVisitedForCurrentEntry.add(dependency.id);
            if (!handledEntryPoints.has(dependency.id) && !dependency.manualChunkAlias) {
                addCurrentEntryColourToModule(dependency);
            }
        }
        for (const { resolution } of module.dynamicImports) {
            if (resolution instanceof Module &&
                resolution.dynamicallyImportedBy.length > 0 &&
                !resolution.manualChunkAlias) {
                dynamicImports.push(resolution);
            }
        }
    };
    if (manualChunkModules) {
        for (const chunkName of Object.keys(manualChunkModules)) {
            currentEntryHash = randomUint8Array(10);
            for (currentEntry of manualChunkModules[chunkName]) {
                modulesVisitedForCurrentEntry = new Set(currentEntry.id);
                addCurrentEntryColourToModule(currentEntry);
            }
        }
    }
    for (currentEntry of entryModules) {
        handledEntryPoints.add(currentEntry.id);
        currentEntryHash = randomUint8Array(10);
        modulesVisitedForCurrentEntry = new Set(currentEntry.id);
        if (!currentEntry.manualChunkAlias) {
            addCurrentEntryColourToModule(currentEntry);
        }
    }
    for (currentEntry of dynamicImports) {
        if (handledEntryPoints.has(currentEntry.id)) {
            continue;
        }
        handledEntryPoints.add(currentEntry.id);
        currentEntryHash = randomUint8Array(10);
        modulesVisitedForCurrentEntry = new Set(currentEntry.id);
        addCurrentEntryColourToModule(currentEntry);
    }
}

function makeOnwarn() {
    const warned = Object.create(null);
    return (warning) => {
        const str = warning.toString();
        if (str in warned)
            return;
        console.error(str);
        warned[str] = true;
    };
}
function normalizeEntryModules(entryModules) {
    if (typeof entryModules === 'string') {
        return [{ fileName: null, name: null, id: entryModules }];
    }
    if (Array.isArray(entryModules)) {
        return entryModules.map(id => ({ fileName: null, name: null, id }));
    }
    return Object.keys(entryModules).map(name => ({
        fileName: null,
        id: entryModules[name],
        name
    }));
}
class Graph {
    constructor(options, watcher) {
        this.moduleById = new Map();
        this.needsTreeshakingPass = false;
        this.phase = BuildPhase.LOAD_AND_PARSE;
        this.watchFiles = Object.create(null);
        this.externalModules = [];
        this.modules = [];
        this.onwarn = options.onwarn || makeOnwarn();
        this.deoptimizationTracker = new EntityPathTracker();
        this.cachedModules = new Map();
        if (options.cache) {
            if (options.cache.modules)
                for (const module of options.cache.modules)
                    this.cachedModules.set(module.id, module);
        }
        if (options.cache !== false) {
            this.pluginCache = (options.cache && options.cache.plugins) || Object.create(null);
            // increment access counter
            for (const name in this.pluginCache) {
                const cache = this.pluginCache[name];
                for (const key of Object.keys(cache))
                    cache[key][0]++;
            }
        }
        this.preserveModules = options.preserveModules;
        this.strictDeprecations = options.strictDeprecations;
        this.cacheExpiry = options.experimentalCacheExpiry;
        if (options.treeshake !== false) {
            this.treeshakingOptions = options.treeshake
                ? {
                    annotations: options.treeshake.annotations !== false,
                    moduleSideEffects: options.treeshake.moduleSideEffects,
                    propertyReadSideEffects: options.treeshake.propertyReadSideEffects !== false,
                    pureExternalModules: options.treeshake.pureExternalModules,
                    tryCatchDeoptimization: options.treeshake.tryCatchDeoptimization !== false,
                    unknownGlobalSideEffects: options.treeshake.unknownGlobalSideEffects !== false
                }
                : {
                    annotations: true,
                    moduleSideEffects: true,
                    propertyReadSideEffects: true,
                    tryCatchDeoptimization: true,
                    unknownGlobalSideEffects: true
                };
            if (typeof this.treeshakingOptions.pureExternalModules !== 'undefined') {
                this.warnDeprecation(`The "treeshake.pureExternalModules" option is deprecated. The "treeshake.moduleSideEffects" option should be used instead. "treeshake.pureExternalModules: true" is equivalent to "treeshake.moduleSideEffects: 'no-external'"`, false);
            }
        }
        this.contextParse = (code, options = {}) => this.acornParser.parse(code, Object.assign(Object.assign(Object.assign({}, defaultAcornOptions), options), this.acornOptions));
        this.pluginDriver = createPluginDriver(this, options, this.pluginCache, watcher);
        if (watcher) {
            const handleChange = (id) => this.pluginDriver.hookSeqSync('watchChange', [id]);
            watcher.on('change', handleChange);
            watcher.once('restart', () => {
                watcher.removeListener('change', handleChange);
            });
        }
        this.shimMissingExports = options.shimMissingExports;
        this.scope = new GlobalScope();
        this.context = String(options.context);
        const optionsModuleContext = options.moduleContext;
        if (typeof optionsModuleContext === 'function') {
            this.getModuleContext = id => optionsModuleContext(id) || this.context;
        }
        else if (typeof optionsModuleContext === 'object') {
            const moduleContext = new Map();
            for (const key in optionsModuleContext) {
                moduleContext.set(path.resolve(key), optionsModuleContext[key]);
            }
            this.getModuleContext = id => moduleContext.get(id) || this.context;
        }
        else {
            this.getModuleContext = () => this.context;
        }
        this.acornOptions = options.acorn ? Object.assign({}, options.acorn) : {};
        const acornPluginsToInject = [];
        acornPluginsToInject.push(acornImportMeta);
        if (options.experimentalTopLevelAwait) {
            this.acornOptions.allowAwaitOutsideFunction = true;
        }
        const acornInjectPlugins = options.acornInjectPlugins;
        acornPluginsToInject.push(...(Array.isArray(acornInjectPlugins)
            ? acornInjectPlugins
            : acornInjectPlugins
                ? [acornInjectPlugins]
                : []));
        this.acornParser = acorn.Parser.extend(...acornPluginsToInject);
        this.moduleLoader = new ModuleLoader(this, this.moduleById, this.pluginDriver, options.external, (typeof options.manualChunks === 'function' && options.manualChunks), (this.treeshakingOptions
            ? this.treeshakingOptions.moduleSideEffects
            : null), (this.treeshakingOptions
            ? this.treeshakingOptions.pureExternalModules
            : false));
    }
    build(entryModules, manualChunks, inlineDynamicImports) {
        // Phase 1 – discovery. We load the entry module and find which
        // modules it imports, and import those, until we have all
        // of the entry module's dependencies
        timeStart('parse modules', 2);
        return Promise.all([
            this.moduleLoader.addEntryModules(normalizeEntryModules(entryModules), true),
            (manualChunks &&
                typeof manualChunks === 'object' &&
                this.moduleLoader.addManualChunks(manualChunks))
        ]).then(([{ entryModules, manualChunkModulesByAlias }]) => {
            if (entryModules.length === 0) {
                throw new Error('You must supply options.input to rollup');
            }
            for (const module of this.moduleById.values()) {
                if (module instanceof Module) {
                    this.modules.push(module);
                }
                else {
                    this.externalModules.push(module);
                }
            }
            timeEnd('parse modules', 2);
            this.phase = BuildPhase.ANALYSE;
            // Phase 2 - linking. We populate the module dependency links and
            // determine the topological execution order for the bundle
            timeStart('analyse dependency graph', 2);
            this.link(entryModules);
            timeEnd('analyse dependency graph', 2);
            // Phase 3 – marking. We include all statements that should be included
            timeStart('mark included statements', 2);
            if (inlineDynamicImports) {
                if (entryModules.length > 1) {
                    throw new Error('Internal Error: can only inline dynamic imports for single-file builds.');
                }
            }
            for (const module of entryModules) {
                module.includeAllExports();
            }
            this.includeMarked(this.modules);
            // check for unused external imports
            for (const externalModule of this.externalModules)
                externalModule.warnUnusedImports();
            timeEnd('mark included statements', 2);
            // Phase 4 – we construct the chunks, working out the optimal chunking using
            // entry point graph colouring, before generating the import and export facades
            timeStart('generate chunks', 2);
            if (!this.preserveModules && !inlineDynamicImports) {
                assignChunkColouringHashes(entryModules, manualChunkModulesByAlias);
            }
            // TODO: there is one special edge case unhandled here and that is that any module
            //       exposed as an unresolvable export * (to a graph external export *,
            //       either as a namespace import reexported or top-level export *)
            //       should be made to be its own entry point module before chunking
            let chunks = [];
            if (this.preserveModules) {
                for (const module of this.modules) {
                    const chunk = new Chunk$1(this, [module]);
                    if (module.isEntryPoint || !chunk.isEmpty) {
                        chunk.entryModules = [module];
                    }
                    chunks.push(chunk);
                }
            }
            else {
                const chunkModules = {};
                for (const module of this.modules) {
                    const entryPointsHashStr = Uint8ArrayToHexString(module.entryPointsHash);
                    const curChunk = chunkModules[entryPointsHashStr];
                    if (curChunk) {
                        curChunk.push(module);
                    }
                    else {
                        chunkModules[entryPointsHashStr] = [module];
                    }
                }
                for (const entryHashSum in chunkModules) {
                    const chunkModulesOrdered = chunkModules[entryHashSum];
                    sortByExecutionOrder(chunkModulesOrdered);
                    const chunk = new Chunk$1(this, chunkModulesOrdered);
                    chunks.push(chunk);
                }
            }
            for (const chunk of chunks) {
                chunk.link();
            }
            chunks = chunks.filter(isChunkRendered);
            const facades = [];
            for (const chunk of chunks) {
                facades.push(...chunk.generateFacades());
            }
            timeEnd('generate chunks', 2);
            this.phase = BuildPhase.GENERATE;
            return chunks.concat(facades);
        });
    }
    getCache() {
        // handle plugin cache eviction
        for (const name in this.pluginCache) {
            const cache = this.pluginCache[name];
            let allDeleted = true;
            for (const key of Object.keys(cache)) {
                if (cache[key][0] >= this.cacheExpiry)
                    delete cache[key];
                else
                    allDeleted = false;
            }
            if (allDeleted)
                delete this.pluginCache[name];
        }
        return {
            modules: this.modules.map(module => module.toJSON()),
            plugins: this.pluginCache
        };
    }
    includeMarked(modules) {
        if (this.treeshakingOptions) {
            let treeshakingPass = 1;
            do {
                timeStart(`treeshaking pass ${treeshakingPass}`, 3);
                this.needsTreeshakingPass = false;
                for (const module of modules) {
                    if (module.isExecuted)
                        module.include();
                }
                timeEnd(`treeshaking pass ${treeshakingPass++}`, 3);
            } while (this.needsTreeshakingPass);
        }
        else {
            // Necessary to properly replace namespace imports
            for (const module of modules)
                module.includeAllInBundle();
        }
    }
    warn(warning) {
        warning.toString = () => {
            let str = '';
            if (warning.plugin)
                str += `(${warning.plugin} plugin) `;
            if (warning.loc)
                str += `${index.relativeId(warning.loc.file)} (${warning.loc.line}:${warning.loc.column}) `;
            str += warning.message;
            return str;
        };
        this.onwarn(warning);
    }
    warnDeprecation(deprecation, activeDeprecation) {
        if (activeDeprecation || this.strictDeprecations) {
            const warning = errDeprecation(deprecation);
            if (this.strictDeprecations) {
                return error(warning);
            }
            this.warn(warning);
        }
    }
    link(entryModules) {
        for (const module of this.modules) {
            module.linkDependencies();
        }
        const { orderedModules, cyclePaths } = analyseModuleExecution(entryModules);
        for (const cyclePath of cyclePaths) {
            this.warn({
                code: 'CIRCULAR_DEPENDENCY',
                importer: cyclePath[0],
                message: `Circular dependency: ${cyclePath.join(' -> ')}`
            });
        }
        this.modules = orderedModules;
        for (const module of this.modules) {
            module.bindReferences();
        }
        this.warnForMissingExports();
    }
    warnForMissingExports() {
        for (const module of this.modules) {
            for (const importName of Object.keys(module.importDescriptions)) {
                const importDescription = module.importDescriptions[importName];
                if (importDescription.name !== '*' &&
                    !importDescription.module.getVariableForExportName(importDescription.name)) {
                    module.warn({
                        code: 'NON_EXISTENT_EXPORT',
                        message: `Non-existent export '${importDescription.name}' is imported from ${index.relativeId(importDescription.module.id)}`,
                        name: importDescription.name,
                        source: importDescription.module.id
                    }, importDescription.start);
                }
            }
        }
    }
}

function evalIfFn(strOrFn) {
    switch (typeof strOrFn) {
        case 'function':
            return strOrFn();
        case 'string':
            return strOrFn;
        default:
            return '';
    }
}
const concatSep = (out, next) => (next ? `${out}\n${next}` : out);
const concatDblSep = (out, next) => (next ? `${out}\n\n${next}` : out);
function createAddons(graph, options) {
    const pluginDriver = graph.pluginDriver;
    return Promise.all([
        pluginDriver.hookReduceValue('banner', evalIfFn(options.banner), [], concatSep),
        pluginDriver.hookReduceValue('footer', evalIfFn(options.footer), [], concatSep),
        pluginDriver.hookReduceValue('intro', evalIfFn(options.intro), [], concatDblSep),
        pluginDriver.hookReduceValue('outro', evalIfFn(options.outro), [], concatDblSep)
    ])
        .then(([banner, footer, intro, outro]) => {
        if (intro)
            intro += '\n\n';
        if (outro)
            outro = `\n\n${outro}`;
        if (banner.length)
            banner += '\n';
        if (footer.length)
            footer = '\n' + footer;
        return { intro, outro, banner, footer };
    })
        .catch((err) => {
        error({
            code: 'ADDON_ERROR',
            message: `Could not retrieve ${err.hook}. Check configuration of plugin ${err.plugin}.
\tError Message: ${err.message}`
        });
    });
}

function assignChunkIds(chunks, inputOptions, outputOptions, inputBase, addons, bundle) {
    const entryChunks = [];
    const otherChunks = [];
    for (const chunk of chunks) {
        (chunk.facadeModule && chunk.facadeModule.isUserDefinedEntryPoint
            ? entryChunks
            : otherChunks).push(chunk);
    }
    // make sure entry chunk names take precedence with regard to deconflicting
    const chunksForNaming = entryChunks.concat(otherChunks);
    for (const chunk of chunksForNaming) {
        if (outputOptions.file) {
            chunk.id = path.basename(outputOptions.file);
        }
        else if (inputOptions.preserveModules) {
            chunk.id = chunk.generateIdPreserveModules(inputBase, outputOptions, bundle);
        }
        else {
            chunk.id = chunk.generateId(addons, outputOptions, bundle, true);
        }
        bundle[chunk.id] = FILE_PLACEHOLDER;
    }
}

// ported from https://github.com/substack/node-commondir
function commondir(files) {
    if (files.length === 0)
        return '/';
    if (files.length === 1)
        return path.dirname(files[0]);
    const commonSegments = files.slice(1).reduce((commonSegments, file) => {
        const pathSegements = file.split(/\/+|\\+/);
        let i;
        for (i = 0; commonSegments[i] === pathSegements[i] &&
            i < Math.min(commonSegments.length, pathSegements.length); i++)
            ;
        return commonSegments.slice(0, i);
    }, files[0].split(/\/+|\\+/));
    // Windows correctly handles paths with forward-slashes
    return commonSegments.length > 1 ? commonSegments.join('/') : '/';
}

function badExports(option, keys) {
    error({
        code: 'INVALID_EXPORT_OPTION',
        message: `'${option}' was specified for output.exports, but entry module has following exports: ${keys.join(', ')}`
    });
}
function getExportMode(chunk, { exports: exportMode, name, format }) {
    const exportKeys = chunk.getExportNames();
    if (exportMode === 'default') {
        if (exportKeys.length !== 1 || exportKeys[0] !== 'default') {
            badExports('default', exportKeys);
        }
    }
    else if (exportMode === 'none' && exportKeys.length) {
        badExports('none', exportKeys);
    }
    if (!exportMode || exportMode === 'auto') {
        if (exportKeys.length === 0) {
            exportMode = 'none';
        }
        else if (exportKeys.length === 1 && exportKeys[0] === 'default') {
            exportMode = 'default';
        }
        else {
            if (chunk.facadeModule !== null &&
                chunk.facadeModule.isEntryPoint &&
                format !== 'es' &&
                exportKeys.indexOf('default') !== -1) {
                chunk.graph.warn({
                    code: 'MIXED_EXPORTS',
                    message: `Using named and default exports together. Consumers of your bundle will have to use ${name ||
                        'bundle'}['default'] to access the default export, which may not be what you want. Use \`output.exports: 'named'\` to disable this warning`,
                    url: `https://rollupjs.org/guide/en/#output-exports`
                });
            }
            exportMode = 'named';
        }
    }
    if (!/(?:default|named|none)/.test(exportMode)) {
        error({
            code: 'INVALID_EXPORT_OPTION',
            message: `output.exports must be 'default', 'named', 'none', 'auto', or left unspecified (defaults to 'auto')`,
            url: `https://rollupjs.org/guide/en/#output-exports`
        });
    }
    return exportMode;
}

function checkOutputOptions(options) {
    if (options.format === 'es6') {
        error(errDeprecation({
            message: 'The "es6" output format is deprecated – use "esm" instead',
            url: `https://rollupjs.org/guide/en/#output-format`
        }));
    }
    if (['amd', 'cjs', 'system', 'es', 'iife', 'umd'].indexOf(options.format) < 0) {
        error({
            message: `You must specify "output.format", which can be one of "amd", "cjs", "system", "esm", "iife" or "umd".`,
            url: `https://rollupjs.org/guide/en/#output-format`
        });
    }
}
function getAbsoluteEntryModulePaths(chunks) {
    const absoluteEntryModulePaths = [];
    for (const chunk of chunks) {
        for (const entryModule of chunk.entryModules) {
            if (index.isAbsolute(entryModule.id)) {
                absoluteEntryModulePaths.push(entryModule.id);
            }
        }
    }
    return absoluteEntryModulePaths;
}
const throwAsyncGenerateError = {
    get() {
        throw new Error(`bundle.generate(...) now returns a Promise instead of a { code, map } object`);
    }
};
function applyOptionHook(inputOptions, plugin) {
    if (plugin.options)
        return plugin.options.call({ meta: { rollupVersion: index.version } }, inputOptions) || inputOptions;
    return inputOptions;
}
function ensureArray(items) {
    if (Array.isArray(items)) {
        return items.filter(Boolean);
    }
    if (items) {
        return [items];
    }
    return [];
}
function getInputOptions(rawInputOptions) {
    if (!rawInputOptions) {
        throw new Error('You must supply an options object to rollup');
    }
    let { inputOptions, optionError } = index.mergeOptions({
        config: rawInputOptions
    });
    if (optionError)
        inputOptions.onwarn({ message: optionError, code: 'UNKNOWN_OPTION' });
    inputOptions = ensureArray(inputOptions.plugins).reduce(applyOptionHook, inputOptions);
    inputOptions.plugins = ensureArray(inputOptions.plugins);
    for (let pluginIndex = 0; pluginIndex < inputOptions.plugins.length; pluginIndex++) {
        const plugin = inputOptions.plugins[pluginIndex];
        if (!plugin.name) {
            plugin.name = `${ANONYMOUS_PLUGIN_PREFIX}${pluginIndex + 1}`;
        }
    }
    if (inputOptions.inlineDynamicImports) {
        if (inputOptions.preserveModules)
            error({
                code: 'INVALID_OPTION',
                message: `"preserveModules" does not support the "inlineDynamicImports" option.`
            });
        if (inputOptions.manualChunks)
            error({
                code: 'INVALID_OPTION',
                message: '"manualChunks" option is not supported for "inlineDynamicImports".'
            });
        if (inputOptions.experimentalOptimizeChunks)
            error({
                code: 'INVALID_OPTION',
                message: '"experimentalOptimizeChunks" option is not supported for "inlineDynamicImports".'
            });
        if ((inputOptions.input instanceof Array && inputOptions.input.length > 1) ||
            (typeof inputOptions.input === 'object' && Object.keys(inputOptions.input).length > 1))
            error({
                code: 'INVALID_OPTION',
                message: 'Multiple inputs are not supported for "inlineDynamicImports".'
            });
    }
    else if (inputOptions.preserveModules) {
        if (inputOptions.manualChunks)
            error({
                code: 'INVALID_OPTION',
                message: '"preserveModules" does not support the "manualChunks" option.'
            });
        if (inputOptions.experimentalOptimizeChunks)
            error({
                code: 'INVALID_OPTION',
                message: '"preserveModules" does not support the "experimentalOptimizeChunks" option.'
            });
    }
    return inputOptions;
}
let curWatcher;
function setWatcher(watcher) {
    curWatcher = watcher;
}
function assignChunksToBundle(chunks, outputBundle) {
    for (let i = 0; i < chunks.length; i++) {
        const chunk = chunks[i];
        const facadeModule = chunk.facadeModule;
        outputBundle[chunk.id] = {
            code: undefined,
            dynamicImports: chunk.getDynamicImportIds(),
            exports: chunk.getExportNames(),
            facadeModuleId: facadeModule && facadeModule.id,
            fileName: chunk.id,
            imports: chunk.getImportIds(),
            isDynamicEntry: facadeModule !== null && facadeModule.dynamicallyImportedBy.length > 0,
            isEntry: facadeModule !== null && facadeModule.isEntryPoint,
            map: undefined,
            modules: chunk.renderedModules,
            get name() {
                return chunk.getChunkName();
            },
            type: 'chunk'
        };
    }
    return outputBundle;
}
function rollup(rawInputOptions) {
    return __awaiter(this, void 0, void 0, function* () {
        const inputOptions = getInputOptions(rawInputOptions);
        initialiseTimers(inputOptions);
        const graph = new Graph(inputOptions, curWatcher);
        curWatcher = undefined;
        // remove the cache option from the memory after graph creation (cache is not used anymore)
        const useCache = rawInputOptions.cache !== false;
        delete inputOptions.cache;
        delete rawInputOptions.cache;
        timeStart('BUILD', 1);
        let chunks;
        try {
            yield graph.pluginDriver.hookParallel('buildStart', [inputOptions]);
            chunks = yield graph.build(inputOptions.input, inputOptions.manualChunks, inputOptions.inlineDynamicImports);
        }
        catch (err) {
            yield graph.pluginDriver.hookParallel('buildEnd', [err]);
            throw err;
        }
        yield graph.pluginDriver.hookParallel('buildEnd', []);
        timeEnd('BUILD', 1);
        // ensure we only do one optimization pass per build
        let optimized = false;
        function getOutputOptions(rawOutputOptions) {
            return normalizeOutputOptions(inputOptions, rawOutputOptions, chunks.length > 1, graph.pluginDriver);
        }
        function generate(outputOptions, isWrite) {
            return __awaiter(this, void 0, void 0, function* () {
                timeStart('GENERATE', 1);
                const assetFileNames = outputOptions.assetFileNames || 'assets/[name]-[hash][extname]';
                const outputBundleWithPlaceholders = Object.create(null);
                let outputBundle;
                const inputBase = commondir(getAbsoluteEntryModulePaths(chunks));
                graph.pluginDriver.startOutput(outputBundleWithPlaceholders, assetFileNames);
                try {
                    yield graph.pluginDriver.hookParallel('renderStart', []);
                    const addons = yield createAddons(graph, outputOptions);
                    for (const chunk of chunks) {
                        if (!inputOptions.preserveModules)
                            chunk.generateInternalExports(outputOptions);
                        if (chunk.facadeModule && chunk.facadeModule.isEntryPoint)
                            chunk.exportMode = getExportMode(chunk, outputOptions);
                    }
                    for (const chunk of chunks) {
                        chunk.preRender(outputOptions, inputBase);
                    }
                    if (!optimized && inputOptions.experimentalOptimizeChunks) {
                        optimizeChunks(chunks, outputOptions, inputOptions.chunkGroupingSize, inputBase);
                        optimized = true;
                    }
                    assignChunkIds(chunks, inputOptions, outputOptions, inputBase, addons, outputBundleWithPlaceholders);
                    outputBundle = assignChunksToBundle(chunks, outputBundleWithPlaceholders);
                    yield Promise.all(chunks.map(chunk => {
                        const outputChunk = outputBundleWithPlaceholders[chunk.id];
                        return chunk.render(outputOptions, addons, outputChunk).then(rendered => {
                            outputChunk.code = rendered.code;
                            outputChunk.map = rendered.map;
                            return graph.pluginDriver.hookParallel('ongenerate', [
                                Object.assign({ bundle: outputChunk }, outputOptions),
                                outputChunk
                            ]);
                        });
                    }));
                }
                catch (error) {
                    yield graph.pluginDriver.hookParallel('renderError', [error]);
                    throw error;
                }
                yield graph.pluginDriver.hookSeq('generateBundle', [outputOptions, outputBundle, isWrite]);
                for (const key of Object.keys(outputBundle)) {
                    const file = outputBundle[key];
                    if (!file.type) {
                        graph.warnDeprecation('A plugin is directly adding properties to the bundle object in the "generateBundle" hook. This is deprecated and will be removed in a future Rollup version, please use "this.emitFile" instead.', false);
                        file.type = 'asset';
                    }
                }
                graph.pluginDriver.finaliseAssets();
                timeEnd('GENERATE', 1);
                return outputBundle;
            });
        }
        const cache = useCache ? graph.getCache() : undefined;
        const result = {
            cache: cache,
            generate: ((rawOutputOptions) => {
                const promise = generate(getOutputOptions(rawOutputOptions), false).then(result => createOutput(result));
                Object.defineProperty(promise, 'code', throwAsyncGenerateError);
                Object.defineProperty(promise, 'map', throwAsyncGenerateError);
                return promise;
            }),
            watchFiles: Object.keys(graph.watchFiles),
            write: ((rawOutputOptions) => {
                const outputOptions = getOutputOptions(rawOutputOptions);
                if (!outputOptions.dir && !outputOptions.file) {
                    error({
                        code: 'MISSING_OPTION',
                        message: 'You must specify "output.file" or "output.dir" for the build.'
                    });
                }
                return generate(outputOptions, true).then((bundle) => __awaiter(this, void 0, void 0, function* () {
                    let chunkCnt = 0;
                    for (const fileName of Object.keys(bundle)) {
                        const file = bundle[fileName];
                        if (file.type === 'asset')
                            continue;
                        chunkCnt++;
                        if (chunkCnt > 1)
                            break;
                    }
                    if (chunkCnt > 1) {
                        if (outputOptions.sourcemapFile)
                            error({
                                code: 'INVALID_OPTION',
                                message: '"output.sourcemapFile" is only supported for single-file builds.'
                            });
                        if (typeof outputOptions.file === 'string')
                            error({
                                code: 'INVALID_OPTION',
                                message: 'When building multiple chunks, the "output.dir" option must be used, not "output.file".' +
                                    (typeof inputOptions.input !== 'string' ||
                                        inputOptions.inlineDynamicImports === true
                                        ? ''
                                        : ' To inline dynamic imports, set the "inlineDynamicImports" option.')
                            });
                    }
                    yield Promise.all(Object.keys(bundle).map(chunkId => writeOutputFile(graph, result, bundle[chunkId], outputOptions)));
                    yield graph.pluginDriver.hookParallel('writeBundle', [bundle]);
                    return createOutput(bundle);
                }));
            })
        };
        if (inputOptions.perf === true)
            result.getTimings = getTimings;
        return result;
    });
}
var SortingFileType;
(function (SortingFileType) {
    SortingFileType[SortingFileType["ENTRY_CHUNK"] = 0] = "ENTRY_CHUNK";
    SortingFileType[SortingFileType["SECONDARY_CHUNK"] = 1] = "SECONDARY_CHUNK";
    SortingFileType[SortingFileType["ASSET"] = 2] = "ASSET";
})(SortingFileType || (SortingFileType = {}));
function getSortingFileType(file) {
    if (file.type === 'asset') {
        return SortingFileType.ASSET;
    }
    if (file.isEntry) {
        return SortingFileType.ENTRY_CHUNK;
    }
    return SortingFileType.SECONDARY_CHUNK;
}
function createOutput(outputBundle) {
    return {
        output: Object.keys(outputBundle)
            .map(fileName => outputBundle[fileName])
            .filter(outputFile => Object.keys(outputFile).length > 0).sort((outputFileA, outputFileB) => {
            const fileTypeA = getSortingFileType(outputFileA);
            const fileTypeB = getSortingFileType(outputFileB);
            if (fileTypeA === fileTypeB)
                return 0;
            return fileTypeA < fileTypeB ? -1 : 1;
        })
    };
}
function writeOutputFile(graph, build, outputFile, outputOptions) {
    const fileName = path.resolve(outputOptions.dir || path.dirname(outputOptions.file), outputFile.fileName);
    let writeSourceMapPromise;
    let source;
    if (outputFile.type === 'asset') {
        source = outputFile.source;
    }
    else {
        source = outputFile.code;
        if (outputOptions.sourcemap && outputFile.map) {
            let url;
            if (outputOptions.sourcemap === 'inline') {
                url = outputFile.map.toUrl();
            }
            else {
                url = `${path.basename(outputFile.fileName)}.map`;
                writeSourceMapPromise = writeFile(`${fileName}.map`, outputFile.map.toString());
            }
            if (outputOptions.sourcemap !== 'hidden') {
                source += `//# ${SOURCEMAPPING_URL}=${url}\n`;
            }
        }
    }
    return writeFile(fileName, source)
        .then(() => writeSourceMapPromise)
        .then(() => outputFile.type === 'chunk' &&
        graph.pluginDriver.hookSeq('onwrite', [
            Object.assign({ bundle: build }, outputOptions),
            outputFile
        ]))
        .then(() => { });
}
function normalizeOutputOptions(inputOptions, rawOutputOptions, hasMultipleChunks, pluginDriver) {
    if (!rawOutputOptions) {
        throw new Error('You must supply an options object');
    }
    const mergedOptions = index.mergeOptions({
        config: {
            output: Object.assign(Object.assign(Object.assign({}, rawOutputOptions), rawOutputOptions.output), inputOptions.output)
        }
    });
    if (mergedOptions.optionError)
        throw new Error(mergedOptions.optionError);
    // now outputOptions is an array, but rollup.rollup API doesn't support arrays
    const mergedOutputOptions = mergedOptions.outputOptions[0];
    const outputOptionsReducer = (outputOptions, result) => result || outputOptions;
    const outputOptions = pluginDriver.hookReduceArg0Sync('outputOptions', [mergedOutputOptions], outputOptionsReducer, pluginContext => {
        const emitError = () => pluginContext.error(errCannotEmitFromOptionsHook());
        return Object.assign(Object.assign({}, pluginContext), { emitFile: emitError, setAssetSource: emitError });
    });
    checkOutputOptions(outputOptions);
    if (typeof outputOptions.file === 'string') {
        if (typeof outputOptions.dir === 'string')
            error({
                code: 'INVALID_OPTION',
                message: 'You must set either "output.file" for a single-file build or "output.dir" when generating multiple chunks.'
            });
        if (inputOptions.preserveModules) {
            error({
                code: 'INVALID_OPTION',
                message: 'You must set "output.dir" instead of "output.file" when using the "preserveModules" option.'
            });
        }
        if (typeof inputOptions.input === 'object' && !Array.isArray(inputOptions.input))
            error({
                code: 'INVALID_OPTION',
                message: 'You must set "output.dir" instead of "output.file" when providing named inputs.'
            });
    }
    if (hasMultipleChunks) {
        if (outputOptions.format === 'umd' || outputOptions.format === 'iife')
            error({
                code: 'INVALID_OPTION',
                message: 'UMD and IIFE output formats are not supported for code-splitting builds.'
            });
        if (typeof outputOptions.file === 'string')
            error({
                code: 'INVALID_OPTION',
                message: 'You must set "output.dir" instead of "output.file" when generating multiple chunks.'
            });
    }
    return outputOptions;
}

var utils$1 = index.createCommonjsModule(function (module, exports) {
    exports.isInteger = num => {
        if (typeof num === 'number') {
            return Number.isInteger(num);
        }
        if (typeof num === 'string' && num.trim() !== '') {
            return Number.isInteger(Number(num));
        }
        return false;
    };
    /**
     * Find a node of the given type
     */
    exports.find = (node, type) => node.nodes.find(node => node.type === type);
    /**
     * Find a node of the given type
     */
    exports.exceedsLimit = (min, max, step = 1, limit) => {
        if (limit === false)
            return false;
        if (!exports.isInteger(min) || !exports.isInteger(max))
            return false;
        return ((Number(max) - Number(min)) / Number(step)) >= limit;
    };
    /**
     * Escape the given node with '\\' before node.value
     */
    exports.escapeNode = (block, n = 0, type) => {
        let node = block.nodes[n];
        if (!node)
            return;
        if ((type && node.type === type) || node.type === 'open' || node.type === 'close') {
            if (node.escaped !== true) {
                node.value = '\\' + node.value;
                node.escaped = true;
            }
        }
    };
    /**
     * Returns true if the given brace node should be enclosed in literal braces
     */
    exports.encloseBrace = node => {
        if (node.type !== 'brace')
            return false;
        if ((node.commas >> 0 + node.ranges >> 0) === 0) {
            node.invalid = true;
            return true;
        }
        return false;
    };
    /**
     * Returns true if a brace node is invalid.
     */
    exports.isInvalidBrace = block => {
        if (block.type !== 'brace')
            return false;
        if (block.invalid === true || block.dollar)
            return true;
        if ((block.commas >> 0 + block.ranges >> 0) === 0) {
            block.invalid = true;
            return true;
        }
        if (block.open !== true || block.close !== true) {
            block.invalid = true;
            return true;
        }
        return false;
    };
    /**
     * Returns true if a node is an open or close node
     */
    exports.isOpenOrClose = node => {
        if (node.type === 'open' || node.type === 'close') {
            return true;
        }
        return node.open === true || node.close === true;
    };
    /**
     * Reduce an array of text nodes.
     */
    exports.reduce = nodes => nodes.reduce((acc, node) => {
        if (node.type === 'text')
            acc.push(node.value);
        if (node.type === 'range')
            node.type = 'text';
        return acc;
    }, []);
    /**
     * Flatten an array
     */
    exports.flatten = (...args) => {
        const result = [];
        const flat = arr => {
            for (let i = 0; i < arr.length; i++) {
                let ele = arr[i];
                Array.isArray(ele) ? flat(ele) : ele !== void 0 && result.push(ele);
            }
            return result;
        };
        flat(args);
        return result;
    };
});

var stringify = (ast, options = {}) => {
    let stringify = (node, parent = {}) => {
        let invalidBlock = options.escapeInvalid && utils$1.isInvalidBrace(parent);
        let invalidNode = node.invalid === true && options.escapeInvalid === true;
        let output = '';
        if (node.value) {
            if ((invalidBlock || invalidNode) && utils$1.isOpenOrClose(node)) {
                return '\\' + node.value;
            }
            return node.value;
        }
        if (node.value) {
            return node.value;
        }
        if (node.nodes) {
            for (let child of node.nodes) {
                output += stringify(child);
            }
        }
        return output;
    };
    return stringify(ast);
};

/*!
 * is-number <https://github.com/jonschlinkert/is-number>
 *
 * Copyright (c) 2014-present, Jon Schlinkert.
 * Released under the MIT License.
 */
var isNumber = function (num) {
    if (typeof num === 'number') {
        return num - num === 0;
    }
    if (typeof num === 'string' && num.trim() !== '') {
        return Number.isFinite ? Number.isFinite(+num) : isFinite(+num);
    }
    return false;
};

const toRegexRange = (min, max, options) => {
    if (isNumber(min) === false) {
        throw new TypeError('toRegexRange: expected the first argument to be a number');
    }
    if (max === void 0 || min === max) {
        return String(min);
    }
    if (isNumber(max) === false) {
        throw new TypeError('toRegexRange: expected the second argument to be a number.');
    }
    let opts = Object.assign({ relaxZeros: true }, options);
    if (typeof opts.strictZeros === 'boolean') {
        opts.relaxZeros = opts.strictZeros === false;
    }
    let relax = String(opts.relaxZeros);
    let shorthand = String(opts.shorthand);
    let capture = String(opts.capture);
    let wrap = String(opts.wrap);
    let cacheKey = min + ':' + max + '=' + relax + shorthand + capture + wrap;
    if (toRegexRange.cache.hasOwnProperty(cacheKey)) {
        return toRegexRange.cache[cacheKey].result;
    }
    let a = Math.min(min, max);
    let b = Math.max(min, max);
    if (Math.abs(a - b) === 1) {
        let result = min + '|' + max;
        if (opts.capture) {
            return `(${result})`;
        }
        if (opts.wrap === false) {
            return result;
        }
        return `(?:${result})`;
    }
    let isPadded = hasPadding(min) || hasPadding(max);
    let state = { min, max, a, b };
    let positives = [];
    let negatives = [];
    if (isPadded) {
        state.isPadded = isPadded;
        state.maxLen = String(state.max).length;
    }
    if (a < 0) {
        let newMin = b < 0 ? Math.abs(b) : 1;
        negatives = splitToPatterns(newMin, Math.abs(a), state, opts);
        a = state.a = 0;
    }
    if (b >= 0) {
        positives = splitToPatterns(a, b, state, opts);
    }
    state.negatives = negatives;
    state.positives = positives;
    state.result = collatePatterns(negatives, positives);
    if (opts.capture === true) {
        state.result = `(${state.result})`;
    }
    else if (opts.wrap !== false && (positives.length + negatives.length) > 1) {
        state.result = `(?:${state.result})`;
    }
    toRegexRange.cache[cacheKey] = state;
    return state.result;
};
function collatePatterns(neg, pos, options) {
    let onlyNegative = filterPatterns(neg, pos, '-', false) || [];
    let onlyPositive = filterPatterns(pos, neg, '', false) || [];
    let intersected = filterPatterns(neg, pos, '-?', true) || [];
    let subpatterns = onlyNegative.concat(intersected).concat(onlyPositive);
    return subpatterns.join('|');
}
function splitToRanges(min, max) {
    let nines = 1;
    let zeros = 1;
    let stop = countNines(min, nines);
    let stops = new Set([max]);
    while (min <= stop && stop <= max) {
        stops.add(stop);
        nines += 1;
        stop = countNines(min, nines);
    }
    stop = countZeros(max + 1, zeros) - 1;
    while (min < stop && stop <= max) {
        stops.add(stop);
        zeros += 1;
        stop = countZeros(max + 1, zeros) - 1;
    }
    stops = [...stops];
    stops.sort(compare);
    return stops;
}
/**
 * Convert a range to a regex pattern
 * @param {Number} `start`
 * @param {Number} `stop`
 * @return {String}
 */
function rangeToPattern(start, stop, options) {
    if (start === stop) {
        return { pattern: start, count: [], digits: 0 };
    }
    let zipped = zip(start, stop);
    let digits = zipped.length;
    let pattern = '';
    let count = 0;
    for (let i = 0; i < digits; i++) {
        let [startDigit, stopDigit] = zipped[i];
        if (startDigit === stopDigit) {
            pattern += startDigit;
        }
        else if (startDigit !== '0' || stopDigit !== '9') {
            pattern += toCharacterClass(startDigit, stopDigit);
        }
        else {
            count++;
        }
    }
    if (count) {
        pattern += options.shorthand === true ? '\\d' : '[0-9]';
    }
    return { pattern, count: [count], digits };
}
function splitToPatterns(min, max, tok, options) {
    let ranges = splitToRanges(min, max);
    let tokens = [];
    let start = min;
    let prev;
    for (let i = 0; i < ranges.length; i++) {
        let max = ranges[i];
        let obj = rangeToPattern(String(start), String(max), options);
        let zeros = '';
        if (!tok.isPadded && prev && prev.pattern === obj.pattern) {
            if (prev.count.length > 1) {
                prev.count.pop();
            }
            prev.count.push(obj.count[0]);
            prev.string = prev.pattern + toQuantifier(prev.count);
            start = max + 1;
            continue;
        }
        if (tok.isPadded) {
            zeros = padZeros(max, tok, options);
        }
        obj.string = zeros + obj.pattern + toQuantifier(obj.count);
        tokens.push(obj);
        start = max + 1;
        prev = obj;
    }
    return tokens;
}
function filterPatterns(arr, comparison, prefix, intersection, options) {
    let result = [];
    for (let ele of arr) {
        let { string } = ele;
        // only push if _both_ are negative...
        if (!intersection && !contains(comparison, 'string', string)) {
            result.push(prefix + string);
        }
        // or _both_ are positive
        if (intersection && contains(comparison, 'string', string)) {
            result.push(prefix + string);
        }
    }
    return result;
}
/**
 * Zip strings
 */
function zip(a, b) {
    let arr = [];
    for (let i = 0; i < a.length; i++)
        arr.push([a[i], b[i]]);
    return arr;
}
function compare(a, b) {
    return a > b ? 1 : b > a ? -1 : 0;
}
function contains(arr, key, val) {
    return arr.some(ele => ele[key] === val);
}
function countNines(min, len) {
    return Number(String(min).slice(0, -len) + '9'.repeat(len));
}
function countZeros(integer, zeros) {
    return integer - (integer % Math.pow(10, zeros));
}
function toQuantifier(digits) {
    let [start = 0, stop = ''] = digits;
    if (stop || start > 1) {
        return `{${start + (stop ? ',' + stop : '')}}`;
    }
    return '';
}
function toCharacterClass(a, b, options) {
    return `[${a}${(b - a === 1) ? '' : '-'}${b}]`;
}
function hasPadding(str) {
    return /^-?(0+)\d/.test(str);
}
function padZeros(value, tok, options) {
    if (!tok.isPadded) {
        return value;
    }
    let diff = Math.abs(tok.maxLen - String(value).length);
    let relax = options.relaxZeros !== false;
    switch (diff) {
        case 0:
            return '';
        case 1:
            return relax ? '0?' : '0';
        case 2:
            return relax ? '0{0,2}' : '00';
        default: {
            return relax ? `0{0,${diff}}` : `0{${diff}}`;
        }
    }
}
/**
 * Cache
 */
toRegexRange.cache = {};
toRegexRange.clearCache = () => (toRegexRange.cache = {});
/**
 * Expose `toRegexRange`
 */
var toRegexRange_1 = toRegexRange;

const isObject$1 = val => val !== null && typeof val === 'object' && !Array.isArray(val);
const transform$1 = toNumber => {
    return value => toNumber === true ? Number(value) : String(value);
};
const isValidValue = value => {
    return typeof value === 'number' || (typeof value === 'string' && value !== '');
};
const isNumber$1 = num => Number.isInteger(+num);
const zeros = input => {
    let value = `${input}`;
    let index = -1;
    if (value[0] === '-')
        value = value.slice(1);
    if (value === '0')
        return false;
    while (value[++index] === '0')
        ;
    return index > 0;
};
const stringify$1 = (start, end, options) => {
    if (typeof start === 'string' || typeof end === 'string') {
        return true;
    }
    return options.stringify === true;
};
const pad = (input, maxLength, toNumber) => {
    if (maxLength > 0) {
        let dash = input[0] === '-' ? '-' : '';
        if (dash)
            input = input.slice(1);
        input = (dash + input.padStart(dash ? maxLength - 1 : maxLength, '0'));
    }
    if (toNumber === false) {
        return String(input);
    }
    return input;
};
const toMaxLen = (input, maxLength) => {
    let negative = input[0] === '-' ? '-' : '';
    if (negative) {
        input = input.slice(1);
        maxLength--;
    }
    while (input.length < maxLength)
        input = '0' + input;
    return negative ? ('-' + input) : input;
};
const toSequence = (parts, options) => {
    parts.negatives.sort((a, b) => a < b ? -1 : a > b ? 1 : 0);
    parts.positives.sort((a, b) => a < b ? -1 : a > b ? 1 : 0);
    let prefix = options.capture ? '' : '?:';
    let positives = '';
    let negatives = '';
    let result;
    if (parts.positives.length) {
        positives = parts.positives.join('|');
    }
    if (parts.negatives.length) {
        negatives = `-(${prefix}${parts.negatives.join('|')})`;
    }
    if (positives && negatives) {
        result = `${positives}|${negatives}`;
    }
    else {
        result = positives || negatives;
    }
    if (options.wrap) {
        return `(${prefix}${result})`;
    }
    return result;
};
const toRange = (a, b, isNumbers, options) => {
    if (isNumbers) {
        return toRegexRange_1(a, b, Object.assign({ wrap: false }, options));
    }
    let start = String.fromCharCode(a);
    if (a === b)
        return start;
    let stop = String.fromCharCode(b);
    return `[${start}-${stop}]`;
};
const toRegex = (start, end, options) => {
    if (Array.isArray(start)) {
        let wrap = options.wrap === true;
        let prefix = options.capture ? '' : '?:';
        return wrap ? `(${prefix}${start.join('|')})` : start.join('|');
    }
    return toRegexRange_1(start, end, options);
};
const rangeError = (...args) => {
    return new RangeError('Invalid range arguments: ' + util.inspect(...args));
};
const invalidRange = (start, end, options) => {
    if (options.strictRanges === true)
        throw rangeError([start, end]);
    return [];
};
const invalidStep = (step, options) => {
    if (options.strictRanges === true) {
        throw new TypeError(`Expected step "${step}" to be a number`);
    }
    return [];
};
const fillNumbers = (start, end, step = 1, options = {}) => {
    let a = Number(start);
    let b = Number(end);
    if (!Number.isInteger(a) || !Number.isInteger(b)) {
        if (options.strictRanges === true)
            throw rangeError([start, end]);
        return [];
    }
    // fix negative zero
    if (a === 0)
        a = 0;
    if (b === 0)
        b = 0;
    let descending = a > b;
    let startString = String(start);
    let endString = String(end);
    let stepString = String(step);
    step = Math.max(Math.abs(step), 1);
    let padded = zeros(startString) || zeros(endString) || zeros(stepString);
    let maxLen = padded ? Math.max(startString.length, endString.length, stepString.length) : 0;
    let toNumber = padded === false && stringify$1(start, end, options) === false;
    let format = options.transform || transform$1(toNumber);
    if (options.toRegex && step === 1) {
        return toRange(toMaxLen(start, maxLen), toMaxLen(end, maxLen), true, options);
    }
    let parts = { negatives: [], positives: [] };
    let push = num => parts[num < 0 ? 'negatives' : 'positives'].push(Math.abs(num));
    let range = [];
    let index = 0;
    while (descending ? a >= b : a <= b) {
        if (options.toRegex === true && step > 1) {
            push(a);
        }
        else {
            range.push(pad(format(a, index), maxLen, toNumber));
        }
        a = descending ? a - step : a + step;
        index++;
    }
    if (options.toRegex === true) {
        return step > 1
            ? toSequence(parts, options)
            : toRegex(range, null, Object.assign({ wrap: false }, options));
    }
    return range;
};
const fillLetters = (start, end, step = 1, options = {}) => {
    if ((!isNumber$1(start) && start.length > 1) || (!isNumber$1(end) && end.length > 1)) {
        return invalidRange(start, end, options);
    }
    let format = options.transform || (val => String.fromCharCode(val));
    let a = `${start}`.charCodeAt(0);
    let b = `${end}`.charCodeAt(0);
    let descending = a > b;
    let min = Math.min(a, b);
    let max = Math.max(a, b);
    if (options.toRegex && step === 1) {
        return toRange(min, max, false, options);
    }
    let range = [];
    let index = 0;
    while (descending ? a >= b : a <= b) {
        range.push(format(a, index));
        a = descending ? a - step : a + step;
        index++;
    }
    if (options.toRegex === true) {
        return toRegex(range, null, { wrap: false, options });
    }
    return range;
};
const fill = (start, end, step, options = {}) => {
    if (end == null && isValidValue(start)) {
        return [start];
    }
    if (!isValidValue(start) || !isValidValue(end)) {
        return invalidRange(start, end, options);
    }
    if (typeof step === 'function') {
        return fill(start, end, 1, { transform: step });
    }
    if (isObject$1(step)) {
        return fill(start, end, 0, step);
    }
    let opts = Object.assign({}, options);
    if (opts.capture === true)
        opts.wrap = true;
    step = step || opts.step || 1;
    if (!isNumber$1(step)) {
        if (step != null && !isObject$1(step))
            return invalidStep(step, opts);
        return fill(start, end, 1, step);
    }
    if (isNumber$1(start) && isNumber$1(end)) {
        return fillNumbers(start, end, step, opts);
    }
    return fillLetters(start, end, Math.max(Math.abs(step), 1), opts);
};
var fillRange = fill;

const compile = (ast, options = {}) => {
    let walk = (node, parent = {}) => {
        let invalidBlock = utils$1.isInvalidBrace(parent);
        let invalidNode = node.invalid === true && options.escapeInvalid === true;
        let invalid = invalidBlock === true || invalidNode === true;
        let prefix = options.escapeInvalid === true ? '\\' : '';
        let output = '';
        if (node.isOpen === true) {
            return prefix + node.value;
        }
        if (node.isClose === true) {
            return prefix + node.value;
        }
        if (node.type === 'open') {
            return invalid ? (prefix + node.value) : '(';
        }
        if (node.type === 'close') {
            return invalid ? (prefix + node.value) : ')';
        }
        if (node.type === 'comma') {
            return node.prev.type === 'comma' ? '' : (invalid ? node.value : '|');
        }
        if (node.value) {
            return node.value;
        }
        if (node.nodes && node.ranges > 0) {
            let args = utils$1.reduce(node.nodes);
            let range = fillRange(...args, Object.assign(Object.assign({}, options), { wrap: false, toRegex: true }));
            if (range.length !== 0) {
                return args.length > 1 && range.length > 1 ? `(${range})` : range;
            }
        }
        if (node.nodes) {
            for (let child of node.nodes) {
                output += walk(child, node);
            }
        }
        return output;
    };
    return walk(ast);
};
var compile_1 = compile;

const append = (queue = '', stash = '', enclose = false) => {
    let result = [];
    queue = [].concat(queue);
    stash = [].concat(stash);
    if (!stash.length)
        return queue;
    if (!queue.length) {
        return enclose ? utils$1.flatten(stash).map(ele => `{${ele}}`) : stash;
    }
    for (let item of queue) {
        if (Array.isArray(item)) {
            for (let value of item) {
                result.push(append(value, stash, enclose));
            }
        }
        else {
            for (let ele of stash) {
                if (enclose === true && typeof ele === 'string')
                    ele = `{${ele}}`;
                result.push(Array.isArray(ele) ? append(item, ele, enclose) : (item + ele));
            }
        }
    }
    return utils$1.flatten(result);
};
const expand = (ast, options = {}) => {
    let rangeLimit = options.rangeLimit === void 0 ? 1000 : options.rangeLimit;
    let walk = (node, parent = {}) => {
        node.queue = [];
        let p = parent;
        let q = parent.queue;
        while (p.type !== 'brace' && p.type !== 'root' && p.parent) {
            p = p.parent;
            q = p.queue;
        }
        if (node.invalid || node.dollar) {
            q.push(append(q.pop(), stringify(node, options)));
            return;
        }
        if (node.type === 'brace' && node.invalid !== true && node.nodes.length === 2) {
            q.push(append(q.pop(), ['{}']));
            return;
        }
        if (node.nodes && node.ranges > 0) {
            let args = utils$1.reduce(node.nodes);
            if (utils$1.exceedsLimit(...args, options.step, rangeLimit)) {
                throw new RangeError('expanded array length exceeds range limit. Use options.rangeLimit to increase or disable the limit.');
            }
            let range = fillRange(...args, options);
            if (range.length === 0) {
                range = stringify(node, options);
            }
            q.push(append(q.pop(), range));
            node.nodes = [];
            return;
        }
        let enclose = utils$1.encloseBrace(node);
        let queue = node.queue;
        let block = node;
        while (block.type !== 'brace' && block.type !== 'root' && block.parent) {
            block = block.parent;
            queue = block.queue;
        }
        for (let i = 0; i < node.nodes.length; i++) {
            let child = node.nodes[i];
            if (child.type === 'comma' && node.type === 'brace') {
                if (i === 1)
                    queue.push('');
                queue.push('');
                continue;
            }
            if (child.type === 'close') {
                q.push(append(q.pop(), queue, enclose));
                continue;
            }
            if (child.value && child.type !== 'open') {
                queue.push(append(queue.pop(), child.value));
                continue;
            }
            if (child.nodes) {
                walk(child, node);
            }
        }
        return queue;
    };
    return utils$1.flatten(walk(ast));
};
var expand_1 = expand;

var constants = {
    MAX_LENGTH: 1024 * 64,
    // Digits
    CHAR_0: '0',
    CHAR_9: '9',
    // Alphabet chars.
    CHAR_UPPERCASE_A: 'A',
    CHAR_LOWERCASE_A: 'a',
    CHAR_UPPERCASE_Z: 'Z',
    CHAR_LOWERCASE_Z: 'z',
    CHAR_LEFT_PARENTHESES: '(',
    CHAR_RIGHT_PARENTHESES: ')',
    CHAR_ASTERISK: '*',
    // Non-alphabetic chars.
    CHAR_AMPERSAND: '&',
    CHAR_AT: '@',
    CHAR_BACKSLASH: '\\',
    CHAR_BACKTICK: '`',
    CHAR_CARRIAGE_RETURN: '\r',
    CHAR_CIRCUMFLEX_ACCENT: '^',
    CHAR_COLON: ':',
    CHAR_COMMA: ',',
    CHAR_DOLLAR: '$',
    CHAR_DOT: '.',
    CHAR_DOUBLE_QUOTE: '"',
    CHAR_EQUAL: '=',
    CHAR_EXCLAMATION_MARK: '!',
    CHAR_FORM_FEED: '\f',
    CHAR_FORWARD_SLASH: '/',
    CHAR_HASH: '#',
    CHAR_HYPHEN_MINUS: '-',
    CHAR_LEFT_ANGLE_BRACKET: '<',
    CHAR_LEFT_CURLY_BRACE: '{',
    CHAR_LEFT_SQUARE_BRACKET: '[',
    CHAR_LINE_FEED: '\n',
    CHAR_NO_BREAK_SPACE: '\u00A0',
    CHAR_PERCENT: '%',
    CHAR_PLUS: '+',
    CHAR_QUESTION_MARK: '?',
    CHAR_RIGHT_ANGLE_BRACKET: '>',
    CHAR_RIGHT_CURLY_BRACE: '}',
    CHAR_RIGHT_SQUARE_BRACKET: ']',
    CHAR_SEMICOLON: ';',
    CHAR_SINGLE_QUOTE: '\'',
    CHAR_SPACE: ' ',
    CHAR_TAB: '\t',
    CHAR_UNDERSCORE: '_',
    CHAR_VERTICAL_LINE: '|',
    CHAR_ZERO_WIDTH_NOBREAK_SPACE: '\uFEFF' /* \uFEFF */
};

/**
 * Constants
 */
const { MAX_LENGTH, CHAR_BACKSLASH, /* \ */ CHAR_BACKTICK, /* ` */ CHAR_COMMA, /* , */ CHAR_DOT, /* . */ CHAR_LEFT_PARENTHESES, /* ( */ CHAR_RIGHT_PARENTHESES, /* ) */ CHAR_LEFT_CURLY_BRACE, /* { */ CHAR_RIGHT_CURLY_BRACE, /* } */ CHAR_LEFT_SQUARE_BRACKET, /* [ */ CHAR_RIGHT_SQUARE_BRACKET, /* ] */ CHAR_DOUBLE_QUOTE, /* " */ CHAR_SINGLE_QUOTE, /* ' */ CHAR_NO_BREAK_SPACE, CHAR_ZERO_WIDTH_NOBREAK_SPACE } = constants;
/**
 * parse
 */
const parse = (input, options = {}) => {
    if (typeof input !== 'string') {
        throw new TypeError('Expected a string');
    }
    let opts = options || {};
    let max = typeof opts.maxLength === 'number' ? Math.min(MAX_LENGTH, opts.maxLength) : MAX_LENGTH;
    if (input.length > max) {
        throw new SyntaxError(`Input length (${input.length}), exceeds max characters (${max})`);
    }
    let ast = { type: 'root', input, nodes: [] };
    let stack = [ast];
    let block = ast;
    let prev = ast;
    let brackets = 0;
    let length = input.length;
    let index = 0;
    let depth = 0;
    let value;
    /**
     * Helpers
     */
    const advance = () => input[index++];
    const push = node => {
        if (node.type === 'text' && prev.type === 'dot') {
            prev.type = 'text';
        }
        if (prev && prev.type === 'text' && node.type === 'text') {
            prev.value += node.value;
            return;
        }
        block.nodes.push(node);
        node.parent = block;
        node.prev = prev;
        prev = node;
        return node;
    };
    push({ type: 'bos' });
    while (index < length) {
        block = stack[stack.length - 1];
        value = advance();
        /**
         * Invalid chars
         */
        if (value === CHAR_ZERO_WIDTH_NOBREAK_SPACE || value === CHAR_NO_BREAK_SPACE) {
            continue;
        }
        /**
         * Escaped chars
         */
        if (value === CHAR_BACKSLASH) {
            push({ type: 'text', value: (options.keepEscaping ? value : '') + advance() });
            continue;
        }
        /**
         * Right square bracket (literal): ']'
         */
        if (value === CHAR_RIGHT_SQUARE_BRACKET) {
            push({ type: 'text', value: '\\' + value });
            continue;
        }
        /**
         * Left square bracket: '['
         */
        if (value === CHAR_LEFT_SQUARE_BRACKET) {
            brackets++;
            let next;
            while (index < length && (next = advance())) {
                value += next;
                if (next === CHAR_LEFT_SQUARE_BRACKET) {
                    brackets++;
                    continue;
                }
                if (next === CHAR_BACKSLASH) {
                    value += advance();
                    continue;
                }
                if (next === CHAR_RIGHT_SQUARE_BRACKET) {
                    brackets--;
                    if (brackets === 0) {
                        break;
                    }
                }
            }
            push({ type: 'text', value });
            continue;
        }
        /**
         * Parentheses
         */
        if (value === CHAR_LEFT_PARENTHESES) {
            block = push({ type: 'paren', nodes: [] });
            stack.push(block);
            push({ type: 'text', value });
            continue;
        }
        if (value === CHAR_RIGHT_PARENTHESES) {
            if (block.type !== 'paren') {
                push({ type: 'text', value });
                continue;
            }
            block = stack.pop();
            push({ type: 'text', value });
            block = stack[stack.length - 1];
            continue;
        }
        /**
         * Quotes: '|"|`
         */
        if (value === CHAR_DOUBLE_QUOTE || value === CHAR_SINGLE_QUOTE || value === CHAR_BACKTICK) {
            let open = value;
            let next;
            if (options.keepQuotes !== true) {
                value = '';
            }
            while (index < length && (next = advance())) {
                if (next === CHAR_BACKSLASH) {
                    value += next + advance();
                    continue;
                }
                if (next === open) {
                    if (options.keepQuotes === true)
                        value += next;
                    break;
                }
                value += next;
            }
            push({ type: 'text', value });
            continue;
        }
        /**
         * Left curly brace: '{'
         */
        if (value === CHAR_LEFT_CURLY_BRACE) {
            depth++;
            let dollar = prev.value && prev.value.slice(-1) === '$' || block.dollar === true;
            let brace = {
                type: 'brace',
                open: true,
                close: false,
                dollar,
                depth,
                commas: 0,
                ranges: 0,
                nodes: []
            };
            block = push(brace);
            stack.push(block);
            push({ type: 'open', value });
            continue;
        }
        /**
         * Right curly brace: '}'
         */
        if (value === CHAR_RIGHT_CURLY_BRACE) {
            if (block.type !== 'brace') {
                push({ type: 'text', value });
                continue;
            }
            let type = 'close';
            block = stack.pop();
            block.close = true;
            push({ type, value });
            depth--;
            block = stack[stack.length - 1];
            continue;
        }
        /**
         * Comma: ','
         */
        if (value === CHAR_COMMA && depth > 0) {
            if (block.ranges > 0) {
                block.ranges = 0;
                let open = block.nodes.shift();
                block.nodes = [open, { type: 'text', value: stringify(block) }];
            }
            push({ type: 'comma', value });
            block.commas++;
            continue;
        }
        /**
         * Dot: '.'
         */
        if (value === CHAR_DOT && depth > 0 && block.commas === 0) {
            let siblings = block.nodes;
            if (depth === 0 || siblings.length === 0) {
                push({ type: 'text', value });
                continue;
            }
            if (prev.type === 'dot') {
                block.range = [];
                prev.value += value;
                prev.type = 'range';
                if (block.nodes.length !== 3 && block.nodes.length !== 5) {
                    block.invalid = true;
                    block.ranges = 0;
                    prev.type = 'text';
                    continue;
                }
                block.ranges++;
                block.args = [];
                continue;
            }
            if (prev.type === 'range') {
                siblings.pop();
                let before = siblings[siblings.length - 1];
                before.value += prev.value + value;
                prev = before;
                block.ranges--;
                continue;
            }
            push({ type: 'dot', value });
            continue;
        }
        /**
         * Text
         */
        push({ type: 'text', value });
    }
    // Mark imbalanced braces and brackets as invalid
    do {
        block = stack.pop();
        if (block.type !== 'root') {
            block.nodes.forEach(node => {
                if (!node.nodes) {
                    if (node.type === 'open')
                        node.isOpen = true;
                    if (node.type === 'close')
                        node.isClose = true;
                    if (!node.nodes)
                        node.type = 'text';
                    node.invalid = true;
                }
            });
            // get the location of the block on parent.nodes (block's siblings)
            let parent = stack[stack.length - 1];
            let index = parent.nodes.indexOf(block);
            // replace the (invalid) block with it's nodes
            parent.nodes.splice(index, 1, ...block.nodes);
        }
    } while (stack.length > 0);
    push({ type: 'eos' });
    return ast;
};
var parse_1 = parse;

/**
 * Expand the given pattern or create a regex-compatible string.
 *
 * ```js
 * const braces = require('braces');
 * console.log(braces('{a,b,c}', { compile: true })); //=> ['(a|b|c)']
 * console.log(braces('{a,b,c}')); //=> ['a', 'b', 'c']
 * ```
 * @param {String} `str`
 * @param {Object} `options`
 * @return {String}
 * @api public
 */
const braces = (input, options = {}) => {
    let output = [];
    if (Array.isArray(input)) {
        for (let pattern of input) {
            let result = braces.create(pattern, options);
            if (Array.isArray(result)) {
                output.push(...result);
            }
            else {
                output.push(result);
            }
        }
    }
    else {
        output = [].concat(braces.create(input, options));
    }
    if (options && options.expand === true && options.nodupes === true) {
        output = [...new Set(output)];
    }
    return output;
};
/**
 * Parse the given `str` with the given `options`.
 *
 * ```js
 * // braces.parse(pattern, [, options]);
 * const ast = braces.parse('a/{b,c}/d');
 * console.log(ast);
 * ```
 * @param {String} pattern Brace pattern to parse
 * @param {Object} options
 * @return {Object} Returns an AST
 * @api public
 */
braces.parse = (input, options = {}) => parse_1(input, options);
/**
 * Creates a braces string from an AST, or an AST node.
 *
 * ```js
 * const braces = require('braces');
 * let ast = braces.parse('foo/{a,b}/bar');
 * console.log(stringify(ast.nodes[2])); //=> '{a,b}'
 * ```
 * @param {String} `input` Brace pattern or AST.
 * @param {Object} `options`
 * @return {Array} Returns an array of expanded values.
 * @api public
 */
braces.stringify = (input, options = {}) => {
    if (typeof input === 'string') {
        return stringify(braces.parse(input, options), options);
    }
    return stringify(input, options);
};
/**
 * Compiles a brace pattern into a regex-compatible, optimized string.
 * This method is called by the main [braces](#braces) function by default.
 *
 * ```js
 * const braces = require('braces');
 * console.log(braces.compile('a/{b,c}/d'));
 * //=> ['a/(b|c)/d']
 * ```
 * @param {String} `input` Brace pattern or AST.
 * @param {Object} `options`
 * @return {Array} Returns an array of expanded values.
 * @api public
 */
braces.compile = (input, options = {}) => {
    if (typeof input === 'string') {
        input = braces.parse(input, options);
    }
    return compile_1(input, options);
};
/**
 * Expands a brace pattern into an array. This method is called by the
 * main [braces](#braces) function when `options.expand` is true. Before
 * using this method it's recommended that you read the [performance notes](#performance))
 * and advantages of using [.compile](#compile) instead.
 *
 * ```js
 * const braces = require('braces');
 * console.log(braces.expand('a/{b,c}/d'));
 * //=> ['a/b/d', 'a/c/d'];
 * ```
 * @param {String} `pattern` Brace pattern
 * @param {Object} `options`
 * @return {Array} Returns an array of expanded values.
 * @api public
 */
braces.expand = (input, options = {}) => {
    if (typeof input === 'string') {
        input = braces.parse(input, options);
    }
    let result = expand_1(input, options);
    // filter out empty strings if specified
    if (options.noempty === true) {
        result = result.filter(Boolean);
    }
    // filter out duplicates if specified
    if (options.nodupes === true) {
        result = [...new Set(result)];
    }
    return result;
};
/**
 * Processes a brace pattern and returns either an expanded array
 * (if `options.expand` is true), a highly optimized regex-compatible string.
 * This method is called by the main [braces](#braces) function.
 *
 * ```js
 * const braces = require('braces');
 * console.log(braces.create('user-{200..300}/project-{a,b,c}-{1..10}'))
 * //=> 'user-(20[0-9]|2[1-9][0-9]|300)/project-(a|b|c)-([1-9]|10)'
 * ```
 * @param {String} `pattern` Brace pattern
 * @param {Object} `options`
 * @return {Array} Returns an array of expanded values.
 * @api public
 */
braces.create = (input, options = {}) => {
    if (input === '' || input.length < 3) {
        return [input];
    }
    return options.expand !== true
        ? braces.compile(input, options)
        : braces.expand(input, options);
};
/**
 * Expose "braces"
 */
var braces_1 = braces;

const WIN_SLASH = '\\\\/';
const WIN_NO_SLASH = `[^${WIN_SLASH}]`;
/**
 * Posix glob regex
 */
const DOT_LITERAL = '\\.';
const PLUS_LITERAL = '\\+';
const QMARK_LITERAL = '\\?';
const SLASH_LITERAL = '\\/';
const ONE_CHAR = '(?=.)';
const QMARK = '[^/]';
const END_ANCHOR = `(?:${SLASH_LITERAL}|$)`;
const START_ANCHOR = `(?:^|${SLASH_LITERAL})`;
const DOTS_SLASH = `${DOT_LITERAL}{1,2}${END_ANCHOR}`;
const NO_DOT = `(?!${DOT_LITERAL})`;
const NO_DOTS = `(?!${START_ANCHOR}${DOTS_SLASH})`;
const NO_DOT_SLASH = `(?!${DOT_LITERAL}{0,1}${END_ANCHOR})`;
const NO_DOTS_SLASH = `(?!${DOTS_SLASH})`;
const QMARK_NO_DOT = `[^.${SLASH_LITERAL}]`;
const STAR = `${QMARK}*?`;
const POSIX_CHARS = {
    DOT_LITERAL,
    PLUS_LITERAL,
    QMARK_LITERAL,
    SLASH_LITERAL,
    ONE_CHAR,
    QMARK,
    END_ANCHOR,
    DOTS_SLASH,
    NO_DOT,
    NO_DOTS,
    NO_DOT_SLASH,
    NO_DOTS_SLASH,
    QMARK_NO_DOT,
    STAR,
    START_ANCHOR
};
/**
 * Windows glob regex
 */
const WINDOWS_CHARS = Object.assign(Object.assign({}, POSIX_CHARS), { SLASH_LITERAL: `[${WIN_SLASH}]`, QMARK: WIN_NO_SLASH, STAR: `${WIN_NO_SLASH}*?`, DOTS_SLASH: `${DOT_LITERAL}{1,2}(?:[${WIN_SLASH}]|$)`, NO_DOT: `(?!${DOT_LITERAL})`, NO_DOTS: `(?!(?:^|[${WIN_SLASH}])${DOT_LITERAL}{1,2}(?:[${WIN_SLASH}]|$))`, NO_DOT_SLASH: `(?!${DOT_LITERAL}{0,1}(?:[${WIN_SLASH}]|$))`, NO_DOTS_SLASH: `(?!${DOT_LITERAL}{1,2}(?:[${WIN_SLASH}]|$))`, QMARK_NO_DOT: `[^.${WIN_SLASH}]`, START_ANCHOR: `(?:^|[${WIN_SLASH}])`, END_ANCHOR: `(?:[${WIN_SLASH}]|$)` });
/**
 * POSIX Bracket Regex
 */
const POSIX_REGEX_SOURCE = {
    alnum: 'a-zA-Z0-9',
    alpha: 'a-zA-Z',
    ascii: '\\x00-\\x7F',
    blank: ' \\t',
    cntrl: '\\x00-\\x1F\\x7F',
    digit: '0-9',
    graph: '\\x21-\\x7E',
    lower: 'a-z',
    print: '\\x20-\\x7E ',
    punct: '\\-!"#$%&\'()\\*+,./:;<=>?@[\\]^_`{|}~',
    space: ' \\t\\r\\n\\v\\f',
    upper: 'A-Z',
    word: 'A-Za-z0-9_',
    xdigit: 'A-Fa-f0-9'
};
var constants$1 = {
    MAX_LENGTH: 1024 * 64,
    POSIX_REGEX_SOURCE,
    // regular expressions
    REGEX_BACKSLASH: /\\(?![*+?^${}(|)[\]])/g,
    REGEX_NON_SPECIAL_CHAR: /^[^@![\].,$*+?^{}()|\\/]+/,
    REGEX_SPECIAL_CHARS: /[-*+?.^${}(|)[\]]/,
    REGEX_SPECIAL_CHARS_BACKREF: /(\\?)((\W)(\3*))/g,
    REGEX_SPECIAL_CHARS_GLOBAL: /([-*+?.^${}(|)[\]])/g,
    REGEX_REMOVE_BACKSLASH: /(?:\[.*?[^\\]\]|\\(?=.))/g,
    // Replace globs with equivalent patterns to reduce parsing time.
    REPLACEMENTS: {
        '***': '*',
        '**/**': '**',
        '**/**/**': '**'
    },
    // Digits
    CHAR_0: 48,
    CHAR_9: 57,
    // Alphabet chars.
    CHAR_UPPERCASE_A: 65,
    CHAR_LOWERCASE_A: 97,
    CHAR_UPPERCASE_Z: 90,
    CHAR_LOWERCASE_Z: 122,
    CHAR_LEFT_PARENTHESES: 40,
    CHAR_RIGHT_PARENTHESES: 41,
    CHAR_ASTERISK: 42,
    // Non-alphabetic chars.
    CHAR_AMPERSAND: 38,
    CHAR_AT: 64,
    CHAR_BACKWARD_SLASH: 92,
    CHAR_CARRIAGE_RETURN: 13,
    CHAR_CIRCUMFLEX_ACCENT: 94,
    CHAR_COLON: 58,
    CHAR_COMMA: 44,
    CHAR_DOT: 46,
    CHAR_DOUBLE_QUOTE: 34,
    CHAR_EQUAL: 61,
    CHAR_EXCLAMATION_MARK: 33,
    CHAR_FORM_FEED: 12,
    CHAR_FORWARD_SLASH: 47,
    CHAR_GRAVE_ACCENT: 96,
    CHAR_HASH: 35,
    CHAR_HYPHEN_MINUS: 45,
    CHAR_LEFT_ANGLE_BRACKET: 60,
    CHAR_LEFT_CURLY_BRACE: 123,
    CHAR_LEFT_SQUARE_BRACKET: 91,
    CHAR_LINE_FEED: 10,
    CHAR_NO_BREAK_SPACE: 160,
    CHAR_PERCENT: 37,
    CHAR_PLUS: 43,
    CHAR_QUESTION_MARK: 63,
    CHAR_RIGHT_ANGLE_BRACKET: 62,
    CHAR_RIGHT_CURLY_BRACE: 125,
    CHAR_RIGHT_SQUARE_BRACKET: 93,
    CHAR_SEMICOLON: 59,
    CHAR_SINGLE_QUOTE: 39,
    CHAR_SPACE: 32,
    CHAR_TAB: 9,
    CHAR_UNDERSCORE: 95,
    CHAR_VERTICAL_LINE: 124,
    CHAR_ZERO_WIDTH_NOBREAK_SPACE: 65279,
    SEP: path.sep,
    /**
     * Create EXTGLOB_CHARS
     */
    extglobChars(chars) {
        return {
            '!': { type: 'negate', open: '(?:(?!(?:', close: `))${chars.STAR})` },
            '?': { type: 'qmark', open: '(?:', close: ')?' },
            '+': { type: 'plus', open: '(?:', close: ')+' },
            '*': { type: 'star', open: '(?:', close: ')*' },
            '@': { type: 'at', open: '(?:', close: ')' }
        };
    },
    /**
     * Create GLOB_CHARS
     */
    globChars(win32) {
        return win32 === true ? WINDOWS_CHARS : POSIX_CHARS;
    }
};

var utils$2 = index.createCommonjsModule(function (module, exports) {
    const win32 = process.platform === 'win32';
    const { REGEX_SPECIAL_CHARS, REGEX_SPECIAL_CHARS_GLOBAL, REGEX_REMOVE_BACKSLASH } = constants$1;
    exports.isObject = val => val !== null && typeof val === 'object' && !Array.isArray(val);
    exports.hasRegexChars = str => REGEX_SPECIAL_CHARS.test(str);
    exports.isRegexChar = str => str.length === 1 && exports.hasRegexChars(str);
    exports.escapeRegex = str => str.replace(REGEX_SPECIAL_CHARS_GLOBAL, '\\$1');
    exports.toPosixSlashes = str => str.replace(/\\/g, '/');
    exports.removeBackslashes = str => {
        return str.replace(REGEX_REMOVE_BACKSLASH, match => {
            return match === '\\' ? '' : match;
        });
    };
    exports.supportsLookbehinds = () => {
        let segs = process.version.slice(1).split('.');
        if (segs.length === 3 && +segs[0] >= 9 || (+segs[0] === 8 && +segs[1] >= 10)) {
            return true;
        }
        return false;
    };
    exports.isWindows = options => {
        if (options && typeof options.windows === 'boolean') {
            return options.windows;
        }
        return win32 === true || path.sep === '\\';
    };
    exports.escapeLast = (input, char, lastIdx) => {
        let idx = input.lastIndexOf(char, lastIdx);
        if (idx === -1)
            return input;
        if (input[idx - 1] === '\\')
            return exports.escapeLast(input, char, idx - 1);
        return input.slice(0, idx) + '\\' + input.slice(idx);
    };
});

const { CHAR_ASTERISK, /* * */ CHAR_AT, /* @ */ CHAR_BACKWARD_SLASH, /* \ */ CHAR_COMMA: CHAR_COMMA$1, /* , */ CHAR_DOT: CHAR_DOT$1, /* . */ CHAR_EXCLAMATION_MARK, /* ! */ CHAR_FORWARD_SLASH, /* / */ CHAR_LEFT_CURLY_BRACE: CHAR_LEFT_CURLY_BRACE$1, /* { */ CHAR_LEFT_PARENTHESES: CHAR_LEFT_PARENTHESES$1, /* ( */ CHAR_LEFT_SQUARE_BRACKET: CHAR_LEFT_SQUARE_BRACKET$1, /* [ */ CHAR_PLUS, /* + */ CHAR_QUESTION_MARK, /* ? */ CHAR_RIGHT_CURLY_BRACE: CHAR_RIGHT_CURLY_BRACE$1, /* } */ CHAR_RIGHT_PARENTHESES: CHAR_RIGHT_PARENTHESES$1, /* ) */ CHAR_RIGHT_SQUARE_BRACKET: CHAR_RIGHT_SQUARE_BRACKET$1 /* ] */ } = constants$1;
const isPathSeparator = code => {
    return code === CHAR_FORWARD_SLASH || code === CHAR_BACKWARD_SLASH;
};
/**
 * Quickly scans a glob pattern and returns an object with a handful of
 * useful properties, like `isGlob`, `path` (the leading non-glob, if it exists),
 * `glob` (the actual pattern), and `negated` (true if the path starts with `!`).
 *
 * ```js
 * const pm = require('picomatch');
 * console.log(pm.scan('foo/bar/*.js'));
 * { isGlob: true, input: 'foo/bar/*.js', base: 'foo/bar', glob: '*.js' }
 * ```
 * @param {String} `str`
 * @param {Object} `options`
 * @return {Object} Returns an object with tokens and regex source string.
 * @api public
 */
var scan = (input, options) => {
    let opts = options || {};
    let length = input.length - 1;
    let index = -1;
    let start = 0;
    let lastIndex = 0;
    let isGlob = false;
    let backslashes = false;
    let negated = false;
    let braces = 0;
    let prev;
    let code;
    let braceEscaped = false;
    let eos = () => index >= length;
    let advance = () => {
        prev = code;
        return input.charCodeAt(++index);
    };
    while (index < length) {
        code = advance();
        let next;
        if (code === CHAR_BACKWARD_SLASH) {
            backslashes = true;
            next = advance();
            if (next === CHAR_LEFT_CURLY_BRACE$1) {
                braceEscaped = true;
            }
            continue;
        }
        if (braceEscaped === true || code === CHAR_LEFT_CURLY_BRACE$1) {
            braces++;
            while (!eos() && (next = advance())) {
                if (next === CHAR_BACKWARD_SLASH) {
                    backslashes = true;
                    next = advance();
                    continue;
                }
                if (next === CHAR_LEFT_CURLY_BRACE$1) {
                    braces++;
                    continue;
                }
                if (!braceEscaped && next === CHAR_DOT$1 && (next = advance()) === CHAR_DOT$1) {
                    isGlob = true;
                    break;
                }
                if (!braceEscaped && next === CHAR_COMMA$1) {
                    isGlob = true;
                    break;
                }
                if (next === CHAR_RIGHT_CURLY_BRACE$1) {
                    braces--;
                    if (braces === 0) {
                        braceEscaped = false;
                        break;
                    }
                }
            }
        }
        if (code === CHAR_FORWARD_SLASH) {
            if (prev === CHAR_DOT$1 && index === (start + 1)) {
                start += 2;
                continue;
            }
            lastIndex = index + 1;
            continue;
        }
        if (code === CHAR_ASTERISK) {
            isGlob = true;
            break;
        }
        if (code === CHAR_ASTERISK || code === CHAR_QUESTION_MARK) {
            isGlob = true;
            break;
        }
        if (code === CHAR_LEFT_SQUARE_BRACKET$1) {
            while (!eos() && (next = advance())) {
                if (next === CHAR_BACKWARD_SLASH) {
                    backslashes = true;
                    next = advance();
                    continue;
                }
                if (next === CHAR_RIGHT_SQUARE_BRACKET$1) {
                    isGlob = true;
                    break;
                }
            }
        }
        let isExtglobChar = code === CHAR_PLUS
            || code === CHAR_AT
            || code === CHAR_EXCLAMATION_MARK;
        if (isExtglobChar && input.charCodeAt(index + 1) === CHAR_LEFT_PARENTHESES$1) {
            isGlob = true;
            break;
        }
        if (code === CHAR_EXCLAMATION_MARK && index === start) {
            negated = true;
            start++;
            continue;
        }
        if (code === CHAR_LEFT_PARENTHESES$1) {
            while (!eos() && (next = advance())) {
                if (next === CHAR_BACKWARD_SLASH) {
                    backslashes = true;
                    next = advance();
                    continue;
                }
                if (next === CHAR_RIGHT_PARENTHESES$1) {
                    isGlob = true;
                    break;
                }
            }
        }
        if (isGlob) {
            break;
        }
    }
    let prefix = '';
    let orig = input;
    let base = input;
    let glob = '';
    if (start > 0) {
        prefix = input.slice(0, start);
        input = input.slice(start);
        lastIndex -= start;
    }
    if (base && isGlob === true && lastIndex > 0) {
        base = input.slice(0, lastIndex);
        glob = input.slice(lastIndex);
    }
    else if (isGlob === true) {
        base = '';
        glob = input;
    }
    else {
        base = input;
    }
    if (base && base !== '' && base !== '/' && base !== input) {
        if (isPathSeparator(base.charCodeAt(base.length - 1))) {
            base = base.slice(0, -1);
        }
    }
    if (opts.unescape === true) {
        if (glob)
            glob = utils$2.removeBackslashes(glob);
        if (base && backslashes === true) {
            base = utils$2.removeBackslashes(base);
        }
    }
    return { prefix, input: orig, base, glob, negated, isGlob };
};

/**
 * Constants
 */
const { MAX_LENGTH: MAX_LENGTH$1, POSIX_REGEX_SOURCE: POSIX_REGEX_SOURCE$1, REGEX_NON_SPECIAL_CHAR, REGEX_SPECIAL_CHARS_BACKREF, REPLACEMENTS } = constants$1;
/**
 * Helpers
 */
const expandRange = (args, options) => {
    if (typeof options.expandRange === 'function') {
        return options.expandRange(...args, options);
    }
    args.sort();
    let value = `[${args.join('-')}]`;
    try {
    }
    catch (ex) {
        return args.map(v => utils$2.escapeRegex(v)).join('..');
    }
    return value;
};
const negate = state => {
    let count = 1;
    while (state.peek() === '!' && (state.peek(2) !== '(' || state.peek(3) === '?')) {
        state.advance();
        state.start++;
        count++;
    }
    if (count % 2 === 0) {
        return false;
    }
    state.negated = true;
    state.start++;
    return true;
};
/**
 * Create the message for a syntax error
 */
const syntaxError = (type, char) => {
    return `Missing ${type}: "${char}" - use "\\\\${char}" to match literal characters`;
};
/**
 * Parse the given input string.
 * @param {String} input
 * @param {Object} options
 * @return {Object}
 */
const parse$1 = (input, options) => {
    if (typeof input !== 'string') {
        throw new TypeError('Expected a string');
    }
    input = REPLACEMENTS[input] || input;
    let opts = Object.assign({}, options);
    let max = typeof opts.maxLength === 'number' ? Math.min(MAX_LENGTH$1, opts.maxLength) : MAX_LENGTH$1;
    let len = input.length;
    if (len > max) {
        throw new SyntaxError(`Input length: ${len}, exceeds maximum allowed length: ${max}`);
    }
    let bos = { type: 'bos', value: '', output: opts.prepend || '' };
    let tokens = [bos];
    let capture = opts.capture ? '' : '?:';
    let win32 = utils$2.isWindows(options);
    // create constants based on platform, for windows or posix
    const PLATFORM_CHARS = constants$1.globChars(win32);
    const EXTGLOB_CHARS = constants$1.extglobChars(PLATFORM_CHARS);
    const { DOT_LITERAL, PLUS_LITERAL, SLASH_LITERAL, ONE_CHAR, DOTS_SLASH, NO_DOT, NO_DOT_SLASH, NO_DOTS_SLASH, QMARK, QMARK_NO_DOT, STAR, START_ANCHOR } = PLATFORM_CHARS;
    const globstar = (opts) => {
        return `(${capture}(?:(?!${START_ANCHOR}${opts.dot ? DOTS_SLASH : DOT_LITERAL}).)*?)`;
    };
    let nodot = opts.dot ? '' : NO_DOT;
    let star = opts.bash === true ? globstar(opts) : STAR;
    let qmarkNoDot = opts.dot ? QMARK : QMARK_NO_DOT;
    if (opts.capture) {
        star = `(${star})`;
    }
    // minimatch options support
    if (typeof opts.noext === 'boolean') {
        opts.noextglob = opts.noext;
    }
    let state = {
        index: -1,
        start: 0,
        consumed: '',
        output: '',
        backtrack: false,
        brackets: 0,
        braces: 0,
        parens: 0,
        quotes: 0,
        tokens
    };
    let extglobs = [];
    let stack = [];
    let prev = bos;
    let value;
    /**
     * Tokenizing helpers
     */
    const eos = () => state.index === len - 1;
    const peek = state.peek = (n = 1) => input[state.index + n];
    const advance = state.advance = () => input[++state.index];
    const append = token => {
        state.output += token.output != null ? token.output : token.value;
        state.consumed += token.value || '';
    };
    const increment = type => {
        state[type]++;
        stack.push(type);
    };
    const decrement = type => {
        state[type]--;
        stack.pop();
    };
    /**
     * Push tokens onto the tokens array. This helper speeds up
     * tokenizing by 1) helping us avoid backtracking as much as possible,
     * and 2) helping us avoid creating extra tokens when consecutive
     * characters are plain text. This improves performance and simplifies
     * lookbehinds.
     */
    const push = tok => {
        if (prev.type === 'globstar') {
            let isBrace = state.braces > 0 && (tok.type === 'comma' || tok.type === 'brace');
            let isExtglob = extglobs.length && (tok.type === 'pipe' || tok.type === 'paren');
            if (tok.type !== 'slash' && tok.type !== 'paren' && !isBrace && !isExtglob) {
                state.output = state.output.slice(0, -prev.output.length);
                prev.type = 'star';
                prev.value = '*';
                prev.output = star;
                state.output += prev.output;
            }
        }
        if (extglobs.length && tok.type !== 'paren' && !EXTGLOB_CHARS[tok.value]) {
            extglobs[extglobs.length - 1].inner += tok.value;
        }
        if (tok.value || tok.output)
            append(tok);
        if (prev && prev.type === 'text' && tok.type === 'text') {
            prev.value += tok.value;
            return;
        }
        tok.prev = prev;
        tokens.push(tok);
        prev = tok;
    };
    const extglobOpen = (type, value) => {
        let token = Object.assign(Object.assign({}, EXTGLOB_CHARS[value]), { conditions: 1, inner: '' });
        token.prev = prev;
        token.parens = state.parens;
        token.output = state.output;
        let output = (opts.capture ? '(' : '') + token.open;
        push({ type, value, output: state.output ? '' : ONE_CHAR });
        push({ type: 'paren', extglob: true, value: advance(), output });
        increment('parens');
        extglobs.push(token);
    };
    const extglobClose = token => {
        let output = token.close + (opts.capture ? ')' : '');
        if (token.type === 'negate') {
            let extglobStar = star;
            if (token.inner && token.inner.length > 1 && token.inner.includes('/')) {
                extglobStar = globstar(opts);
            }
            if (extglobStar !== star || eos() || /^\)+$/.test(input.slice(state.index + 1))) {
                output = token.close = ')$))' + extglobStar;
            }
            if (token.prev.type === 'bos' && eos()) {
                state.negatedExtglob = true;
            }
        }
        push({ type: 'paren', extglob: true, value, output });
        decrement('parens');
    };
    if (opts.fastpaths !== false && !/(^[*!]|[/{[()\]}"])/.test(input)) {
        let backslashes = false;
        let output = input.replace(REGEX_SPECIAL_CHARS_BACKREF, (m, esc, chars, first, rest, index) => {
            if (first === '\\') {
                backslashes = true;
                return m;
            }
            if (first === '?') {
                if (esc) {
                    return esc + first + (rest ? QMARK.repeat(rest.length) : '');
                }
                if (index === 0) {
                    return qmarkNoDot + (rest ? QMARK.repeat(rest.length) : '');
                }
                return QMARK.repeat(chars.length);
            }
            if (first === '.') {
                return DOT_LITERAL.repeat(chars.length);
            }
            if (first === '*') {
                if (esc) {
                    return esc + first + (rest ? star : '');
                }
                return star;
            }
            return esc ? m : '\\' + m;
        });
        if (backslashes === true) {
            if (opts.unescape === true) {
                output = output.replace(/\\/g, '');
            }
            else {
                output = output.replace(/\\+/g, m => {
                    return m.length % 2 === 0 ? '\\\\' : (m ? '\\' : '');
                });
            }
        }
        state.output = output;
        return state;
    }
    /**
     * Tokenize input until we reach end-of-string
     */
    while (!eos()) {
        value = advance();
        if (value === '\u0000') {
            continue;
        }
        /**
         * Escaped characters
         */
        if (value === '\\') {
            let next = peek();
            if (next === '/' && opts.bash !== true) {
                continue;
            }
            if (next === '.' || next === ';') {
                continue;
            }
            if (!next) {
                value += '\\';
                push({ type: 'text', value });
                continue;
            }
            // collapse slashes to reduce potential for exploits
            let match = /^\\+/.exec(input.slice(state.index + 1));
            let slashes = 0;
            if (match && match[0].length > 2) {
                slashes = match[0].length;
                state.index += slashes;
                if (slashes % 2 !== 0) {
                    value += '\\';
                }
            }
            if (opts.unescape === true) {
                value = advance() || '';
            }
            else {
                value += advance() || '';
            }
            if (state.brackets === 0) {
                push({ type: 'text', value });
                continue;
            }
        }
        /**
         * If we're inside a regex character class, continue
         * until we reach the closing bracket.
         */
        if (state.brackets > 0 && (value !== ']' || prev.value === '[' || prev.value === '[^')) {
            if (opts.posix !== false && value === ':') {
                let inner = prev.value.slice(1);
                if (inner.includes('[')) {
                    prev.posix = true;
                    if (inner.includes(':')) {
                        let idx = prev.value.lastIndexOf('[');
                        let pre = prev.value.slice(0, idx);
                        let rest = prev.value.slice(idx + 2);
                        let posix = POSIX_REGEX_SOURCE$1[rest];
                        if (posix) {
                            prev.value = pre + posix;
                            state.backtrack = true;
                            advance();
                            if (!bos.output && tokens.indexOf(prev) === 1) {
                                bos.output = ONE_CHAR;
                            }
                            continue;
                        }
                    }
                }
            }
            if ((value === '[' && peek() !== ':') || (value === '-' && peek() === ']')) {
                value = '\\' + value;
            }
            if (value === ']' && (prev.value === '[' || prev.value === '[^')) {
                value = '\\' + value;
            }
            if (opts.posix === true && value === '!' && prev.value === '[') {
                value = '^';
            }
            prev.value += value;
            append({ value });
            continue;
        }
        /**
         * If we're inside a quoted string, continue
         * until we reach the closing double quote.
         */
        if (state.quotes === 1 && value !== '"') {
            value = utils$2.escapeRegex(value);
            prev.value += value;
            append({ value });
            continue;
        }
        /**
         * Double quotes
         */
        if (value === '"') {
            state.quotes = state.quotes === 1 ? 0 : 1;
            if (opts.keepQuotes === true) {
                push({ type: 'text', value });
            }
            continue;
        }
        /**
         * Parentheses
         */
        if (value === '(') {
            push({ type: 'paren', value });
            increment('parens');
            continue;
        }
        if (value === ')') {
            if (state.parens === 0 && opts.strictBrackets === true) {
                throw new SyntaxError(syntaxError('opening', '('));
            }
            let extglob = extglobs[extglobs.length - 1];
            if (extglob && state.parens === extglob.parens + 1) {
                extglobClose(extglobs.pop());
                continue;
            }
            push({ type: 'paren', value, output: state.parens ? ')' : '\\)' });
            decrement('parens');
            continue;
        }
        /**
         * Brackets
         */
        if (value === '[') {
            if (opts.nobracket === true || !input.slice(state.index + 1).includes(']')) {
                if (opts.nobracket !== true && opts.strictBrackets === true) {
                    throw new SyntaxError(syntaxError('closing', ']'));
                }
                value = '\\' + value;
            }
            else {
                increment('brackets');
            }
            push({ type: 'bracket', value });
            continue;
        }
        if (value === ']') {
            if (opts.nobracket === true || (prev && prev.type === 'bracket' && prev.value.length === 1)) {
                push({ type: 'text', value, output: '\\' + value });
                continue;
            }
            if (state.brackets === 0) {
                if (opts.strictBrackets === true) {
                    throw new SyntaxError(syntaxError('opening', '['));
                }
                push({ type: 'text', value, output: '\\' + value });
                continue;
            }
            decrement('brackets');
            let prevValue = prev.value.slice(1);
            if (prev.posix !== true && prevValue[0] === '^' && !prevValue.includes('/')) {
                value = '/' + value;
            }
            prev.value += value;
            append({ value });
            // when literal brackets are explicitly disabled
            // assume we should match with a regex character class
            if (opts.literalBrackets === false || utils$2.hasRegexChars(prevValue)) {
                continue;
            }
            let escaped = utils$2.escapeRegex(prev.value);
            state.output = state.output.slice(0, -prev.value.length);
            // when literal brackets are explicitly enabled
            // assume we should escape the brackets to match literal characters
            if (opts.literalBrackets === true) {
                state.output += escaped;
                prev.value = escaped;
                continue;
            }
            // when the user specifies nothing, try to match both
            prev.value = `(${capture}${escaped}|${prev.value})`;
            state.output += prev.value;
            continue;
        }
        /**
         * Braces
         */
        if (value === '{' && opts.nobrace !== true) {
            push({ type: 'brace', value, output: '(' });
            increment('braces');
            continue;
        }
        if (value === '}') {
            if (opts.nobrace === true || state.braces === 0) {
                push({ type: 'text', value, output: '\\' + value });
                continue;
            }
            let output = ')';
            if (state.dots === true) {
                let arr = tokens.slice();
                let range = [];
                for (let i = arr.length - 1; i >= 0; i--) {
                    tokens.pop();
                    if (arr[i].type === 'brace') {
                        break;
                    }
                    if (arr[i].type !== 'dots') {
                        range.unshift(arr[i].value);
                    }
                }
                output = expandRange(range, opts);
                state.backtrack = true;
            }
            push({ type: 'brace', value, output });
            decrement('braces');
            continue;
        }
        /**
         * Pipes
         */
        if (value === '|') {
            if (extglobs.length > 0) {
                extglobs[extglobs.length - 1].conditions++;
            }
            push({ type: 'text', value });
            continue;
        }
        /**
         * Commas
         */
        if (value === ',') {
            let output = value;
            if (state.braces > 0 && stack[stack.length - 1] === 'braces') {
                output = '|';
            }
            push({ type: 'comma', value, output });
            continue;
        }
        /**
         * Slashes
         */
        if (value === '/') {
            // if the beginning of the glob is "./", advance the start
            // to the current index, and don't add the "./" characters
            // to the state. This greatly simplifies lookbehinds when
            // checking for BOS characters like "!" and "." (not "./")
            if (prev.type === 'dot' && state.index === 1) {
                state.start = state.index + 1;
                state.consumed = '';
                state.output = '';
                tokens.pop();
                prev = bos; // reset "prev" to the first token
                continue;
            }
            push({ type: 'slash', value, output: SLASH_LITERAL });
            continue;
        }
        /**
         * Dots
         */
        if (value === '.') {
            if (state.braces > 0 && prev.type === 'dot') {
                if (prev.value === '.')
                    prev.output = DOT_LITERAL;
                prev.type = 'dots';
                prev.output += value;
                prev.value += value;
                state.dots = true;
                continue;
            }
            push({ type: 'dot', value, output: DOT_LITERAL });
            continue;
        }
        /**
         * Question marks
         */
        if (value === '?') {
            if (prev && prev.type === 'paren') {
                let next = peek();
                let output = value;
                if (next === '<' && !utils$2.supportsLookbehinds()) {
                    throw new Error('Node.js v10 or higher is required for regex lookbehinds');
                }
                if (prev.value === '(' && !/[!=<:]/.test(next) || (next === '<' && !/[!=]/.test(peek(2)))) {
                    output = '\\' + value;
                }
                push({ type: 'text', value, output });
                continue;
            }
            if (opts.noextglob !== true && peek() === '(' && peek(2) !== '?') {
                extglobOpen('qmark', value);
                continue;
            }
            if (opts.dot !== true && (prev.type === 'slash' || prev.type === 'bos')) {
                push({ type: 'qmark', value, output: QMARK_NO_DOT });
                continue;
            }
            push({ type: 'qmark', value, output: QMARK });
            continue;
        }
        /**
         * Exclamation
         */
        if (value === '!') {
            if (opts.noextglob !== true && peek() === '(') {
                if (peek(2) !== '?' || !/[!=<:]/.test(peek(3))) {
                    extglobOpen('negate', value);
                    continue;
                }
            }
            if (opts.nonegate !== true && state.index === 0) {
                negate(state);
                continue;
            }
        }
        /**
         * Plus
         */
        if (value === '+') {
            if (opts.noextglob !== true && peek() === '(' && peek(2) !== '?') {
                extglobOpen('plus', value);
                continue;
            }
            if (prev && (prev.type === 'bracket' || prev.type === 'paren' || prev.type === 'brace')) {
                let output = prev.extglob === true ? '\\' + value : value;
                push({ type: 'plus', value, output });
                continue;
            }
            // use regex behavior inside parens
            if (state.parens > 0 && opts.regex !== false) {
                push({ type: 'plus', value });
                continue;
            }
            push({ type: 'plus', value: PLUS_LITERAL });
            continue;
        }
        /**
         * Plain text
         */
        if (value === '@') {
            if (opts.noextglob !== true && peek() === '(' && peek(2) !== '?') {
                push({ type: 'at', value, output: '' });
                continue;
            }
            push({ type: 'text', value });
            continue;
        }
        /**
         * Plain text
         */
        if (value !== '*') {
            if (value === '$' || value === '^') {
                value = '\\' + value;
            }
            let match = REGEX_NON_SPECIAL_CHAR.exec(input.slice(state.index + 1));
            if (match) {
                value += match[0];
                state.index += match[0].length;
            }
            push({ type: 'text', value });
            continue;
        }
        /**
         * Stars
         */
        if (prev && (prev.type === 'globstar' || prev.star === true)) {
            prev.type = 'star';
            prev.star = true;
            prev.value += value;
            prev.output = star;
            state.backtrack = true;
            state.consumed += value;
            continue;
        }
        if (opts.noextglob !== true && peek() === '(' && peek(2) !== '?') {
            extglobOpen('star', value);
            continue;
        }
        if (prev.type === 'star') {
            if (opts.noglobstar === true) {
                state.consumed += value;
                continue;
            }
            let prior = prev.prev;
            let before = prior.prev;
            let isStart = prior.type === 'slash' || prior.type === 'bos';
            let afterStar = before && (before.type === 'star' || before.type === 'globstar');
            if (opts.bash === true && (!isStart || (!eos() && peek() !== '/'))) {
                push({ type: 'star', value, output: '' });
                continue;
            }
            let isBrace = state.braces > 0 && (prior.type === 'comma' || prior.type === 'brace');
            let isExtglob = extglobs.length && (prior.type === 'pipe' || prior.type === 'paren');
            if (!isStart && prior.type !== 'paren' && !isBrace && !isExtglob) {
                push({ type: 'star', value, output: '' });
                continue;
            }
            // strip consecutive `/**/`
            while (input.slice(state.index + 1, state.index + 4) === '/**') {
                let after = input[state.index + 4];
                if (after && after !== '/') {
                    break;
                }
                state.consumed += '/**';
                state.index += 3;
            }
            if (prior.type === 'bos' && eos()) {
                prev.type = 'globstar';
                prev.value += value;
                prev.output = globstar(opts);
                state.output = prev.output;
                state.consumed += value;
                continue;
            }
            if (prior.type === 'slash' && prior.prev.type !== 'bos' && !afterStar && eos()) {
                state.output = state.output.slice(0, -(prior.output + prev.output).length);
                prior.output = '(?:' + prior.output;
                prev.type = 'globstar';
                prev.output = globstar(opts) + '|$)';
                prev.value += value;
                state.output += prior.output + prev.output;
                state.consumed += value;
                continue;
            }
            let next = peek();
            if (prior.type === 'slash' && prior.prev.type !== 'bos' && next === '/') {
                let end = peek(2) !== void 0 ? '|$' : '';
                state.output = state.output.slice(0, -(prior.output + prev.output).length);
                prior.output = '(?:' + prior.output;
                prev.type = 'globstar';
                prev.output = `${globstar(opts)}${SLASH_LITERAL}|${SLASH_LITERAL}${end})`;
                prev.value += value;
                state.output += prior.output + prev.output;
                state.consumed += value + advance();
                push({ type: 'slash', value, output: '' });
                continue;
            }
            if (prior.type === 'bos' && next === '/') {
                prev.type = 'globstar';
                prev.value += value;
                prev.output = `(?:^|${SLASH_LITERAL}|${globstar(opts)}${SLASH_LITERAL})`;
                state.output = prev.output;
                state.consumed += value + advance();
                push({ type: 'slash', value, output: '' });
                continue;
            }
            // remove single star from output
            state.output = state.output.slice(0, -prev.output.length);
            // reset previous token to globstar
            prev.type = 'globstar';
            prev.output = globstar(opts);
            prev.value += value;
            // reset output with globstar
            state.output += prev.output;
            state.consumed += value;
            continue;
        }
        let token = { type: 'star', value, output: star };
        if (opts.bash === true) {
            token.output = '.*?';
            if (prev.type === 'bos' || prev.type === 'slash') {
                token.output = nodot + token.output;
            }
            push(token);
            continue;
        }
        if (prev && (prev.type === 'bracket' || prev.type === 'paren') && opts.regex === true) {
            token.output = value;
            push(token);
            continue;
        }
        if (state.index === state.start || prev.type === 'slash' || prev.type === 'dot') {
            if (prev.type === 'dot') {
                state.output += NO_DOT_SLASH;
                prev.output += NO_DOT_SLASH;
            }
            else if (opts.dot === true) {
                state.output += NO_DOTS_SLASH;
                prev.output += NO_DOTS_SLASH;
            }
            else {
                state.output += nodot;
                prev.output += nodot;
            }
            if (peek() !== '*') {
                state.output += ONE_CHAR;
                prev.output += ONE_CHAR;
            }
        }
        push(token);
    }
    while (state.brackets > 0) {
        if (opts.strictBrackets === true)
            throw new SyntaxError(syntaxError('closing', ']'));
        state.output = utils$2.escapeLast(state.output, '[');
        decrement('brackets');
    }
    while (state.parens > 0) {
        if (opts.strictBrackets === true)
            throw new SyntaxError(syntaxError('closing', ')'));
        state.output = utils$2.escapeLast(state.output, '(');
        decrement('parens');
    }
    while (state.braces > 0) {
        if (opts.strictBrackets === true)
            throw new SyntaxError(syntaxError('closing', '}'));
        state.output = utils$2.escapeLast(state.output, '{');
        decrement('braces');
    }
    if (opts.strictSlashes !== true && (prev.type === 'star' || prev.type === 'bracket')) {
        push({ type: 'maybe_slash', value: '', output: `${SLASH_LITERAL}?` });
    }
    // rebuild the output if we had to backtrack at any point
    if (state.backtrack === true) {
        state.output = '';
        for (let token of state.tokens) {
            state.output += token.output != null ? token.output : token.value;
            if (token.suffix) {
                state.output += token.suffix;
            }
        }
    }
    return state;
};
/**
 * Fast paths for creating regular expressions for common glob patterns.
 * This can significantly speed up processing and has very little downside
 * impact when none of the fast paths match.
 */
parse$1.fastpaths = (input, options) => {
    let opts = Object.assign({}, options);
    let max = typeof opts.maxLength === 'number' ? Math.min(MAX_LENGTH$1, opts.maxLength) : MAX_LENGTH$1;
    let len = input.length;
    if (len > max) {
        throw new SyntaxError(`Input length: ${len}, exceeds maximum allowed length: ${max}`);
    }
    input = REPLACEMENTS[input] || input;
    let win32 = utils$2.isWindows(options);
    // create constants based on platform, for windows or posix
    const { DOT_LITERAL, SLASH_LITERAL, ONE_CHAR, DOTS_SLASH, NO_DOT, NO_DOTS, NO_DOTS_SLASH, STAR, START_ANCHOR } = constants$1.globChars(win32);
    let capture = opts.capture ? '' : '?:';
    let star = opts.bash === true ? '.*?' : STAR;
    let nodot = opts.dot ? NO_DOTS : NO_DOT;
    let slashDot = opts.dot ? NO_DOTS_SLASH : NO_DOT;
    if (opts.capture) {
        star = `(${star})`;
    }
    const globstar = (opts) => {
        return `(${capture}(?:(?!${START_ANCHOR}${opts.dot ? DOTS_SLASH : DOT_LITERAL}).)*?)`;
    };
    const create = str => {
        switch (str) {
            case '*':
                return `${nodot}${ONE_CHAR}${star}`;
            case '.*':
                return `${DOT_LITERAL}${ONE_CHAR}${star}`;
            case '*.*':
                return `${nodot}${star}${DOT_LITERAL}${ONE_CHAR}${star}`;
            case '*/*':
                return `${nodot}${star}${SLASH_LITERAL}${ONE_CHAR}${slashDot}${star}`;
            case '**':
                return nodot + globstar(opts);
            case '**/*':
                return `(?:${nodot}${globstar(opts)}${SLASH_LITERAL})?${slashDot}${ONE_CHAR}${star}`;
            case '**/*.*':
                return `(?:${nodot}${globstar(opts)}${SLASH_LITERAL})?${slashDot}${star}${DOT_LITERAL}${ONE_CHAR}${star}`;
            case '**/.*':
                return `(?:${nodot}${globstar(opts)}${SLASH_LITERAL})?${DOT_LITERAL}${ONE_CHAR}${star}`;
            default: {
                let match = /^(.*?)\.(\w+)$/.exec(str);
                if (!match)
                    return;
                let source = create(match[1]);
                if (!source)
                    return;
                return source + DOT_LITERAL + match[2];
            }
        }
    };
    let output = create(input);
    if (output && opts.strictSlashes !== true) {
        output += `${SLASH_LITERAL}?`;
    }
    return output;
};
var parse_1$1 = parse$1;

/**
 * Creates a matcher function from one or more glob patterns. The
 * returned function takes a string to match as its first argument,
 * and returns true if the string is a match. The returned matcher
 * function also takes a boolean as the second argument that, when true,
 * returns an object with additional information.
 *
 * ```js
 * const picomatch = require('picomatch');
 * // picomatch(glob[, options]);
 *
 * const isMatch = picomatch('*.!(*a)');
 * console.log(isMatch('a.a')); //=> false
 * console.log(isMatch('a.b')); //=> true
 * ```
 * @name picomatch
 * @param {String|Array} `globs` One or more glob patterns.
 * @param {Object=} `options`
 * @return {Function=} Returns a matcher function.
 * @api public
 */
const picomatch = (glob, options, returnState = false) => {
    if (Array.isArray(glob)) {
        let fns = glob.map(input => picomatch(input, options, returnState));
        return str => {
            for (let isMatch of fns) {
                let state = isMatch(str);
                if (state)
                    return state;
            }
            return false;
        };
    }
    if (typeof glob !== 'string' || glob === '') {
        throw new TypeError('Expected pattern to be a non-empty string');
    }
    let opts = options || {};
    let posix = utils$2.isWindows(options);
    let regex = picomatch.makeRe(glob, options, false, true);
    let state = regex.state;
    delete regex.state;
    let isIgnored = () => false;
    if (opts.ignore) {
        let ignoreOpts = Object.assign(Object.assign({}, options), { ignore: null, onMatch: null, onResult: null });
        isIgnored = picomatch(opts.ignore, ignoreOpts, returnState);
    }
    const matcher = (input, returnObject = false) => {
        let { isMatch, match, output } = picomatch.test(input, regex, options, { glob, posix });
        let result = { glob, state, regex, posix, input, output, match, isMatch };
        if (typeof opts.onResult === 'function') {
            opts.onResult(result);
        }
        if (isMatch === false) {
            result.isMatch = false;
            return returnObject ? result : false;
        }
        if (isIgnored(input)) {
            if (typeof opts.onIgnore === 'function') {
                opts.onIgnore(result);
            }
            result.isMatch = false;
            return returnObject ? result : false;
        }
        if (typeof opts.onMatch === 'function') {
            opts.onMatch(result);
        }
        return returnObject ? result : true;
    };
    if (returnState) {
        matcher.state = state;
    }
    return matcher;
};
/**
 * Test `input` with the given `regex`. This is used by the main
 * `picomatch()` function to test the input string.
 *
 * ```js
 * const picomatch = require('picomatch');
 * // picomatch.test(input, regex[, options]);
 *
 * console.log(picomatch.test('foo/bar', /^(?:([^/]*?)\/([^/]*?))$/));
 * // { isMatch: true, match: [ 'foo/', 'foo', 'bar' ], output: 'foo/bar' }
 * ```
 * @param {String} `input` String to test.
 * @param {RegExp} `regex`
 * @return {Object} Returns an object with matching info.
 * @api public
 */
picomatch.test = (input, regex, options, { glob, posix } = {}) => {
    if (typeof input !== 'string') {
        throw new TypeError('Expected input to be a string');
    }
    if (input === '') {
        return { isMatch: false, output: '' };
    }
    let opts = options || {};
    let format = opts.format || (posix ? utils$2.toPosixSlashes : null);
    let match = input === glob;
    let output = (match && format) ? format(input) : input;
    if (match === false) {
        output = format ? format(input) : input;
        match = output === glob;
    }
    if (match === false || opts.capture === true) {
        if (opts.matchBase === true || opts.basename === true) {
            match = picomatch.matchBase(input, regex, options, posix);
        }
        else {
            match = regex.exec(output);
        }
    }
    return { isMatch: !!match, match, output };
};
/**
 * Match the basename of a filepath.
 *
 * ```js
 * const picomatch = require('picomatch');
 * // picomatch.matchBase(input, glob[, options]);
 * console.log(picomatch.matchBase('foo/bar.js', '*.js'); // true
 * ```
 * @param {String} `input` String to test.
 * @param {RegExp|String} `glob` Glob pattern or regex created by [.makeRe](#makeRe).
 * @return {Boolean}
 * @api public
 */
picomatch.matchBase = (input, glob, options, posix = utils$2.isWindows(options)) => {
    let regex = glob instanceof RegExp ? glob : picomatch.makeRe(glob, options);
    return regex.test(path.basename(input));
};
/**
 * Returns true if **any** of the given glob `patterns` match the specified `string`.
 *
 * ```js
 * const picomatch = require('picomatch');
 * // picomatch.isMatch(string, patterns[, options]);
 *
 * console.log(picomatch.isMatch('a.a', ['b.*', '*.a'])); //=> true
 * console.log(picomatch.isMatch('a.a', 'b.*')); //=> false
 * ```
 * @param {String|Array} str The string to test.
 * @param {String|Array} patterns One or more glob patterns to use for matching.
 * @param {Object} [options] See available [options](#options).
 * @return {Boolean} Returns true if any patterns match `str`
 * @api public
 */
picomatch.isMatch = (str, patterns, options) => picomatch(patterns, options)(str);
/**
 * Parse a glob pattern to create the source string for a regular
 * expression.
 *
 * ```js
 * const picomatch = require('picomatch');
 * const result = picomatch.parse(glob[, options]);
 * ```
 * @param {String} `glob`
 * @param {Object} `options`
 * @return {Object} Returns an object with useful properties and output to be used as a regex source string.
 * @api public
 */
picomatch.parse = (glob, options) => parse_1$1(glob, options);
/**
 * Scan a glob pattern to separate the pattern into segments.
 *
 * ```js
 * const picomatch = require('picomatch');
 * // picomatch.scan(input[, options]);
 *
 * const result = picomatch.scan('!./foo/*.js');
 * console.log(result);
 * // { prefix: '!./',
 * //   input: '!./foo/*.js',
 * //   base: 'foo',
 * //   glob: '*.js',
 * //   negated: true,
 * //   isGlob: true }
 * ```
 * @param {String} `input` Glob pattern to scan.
 * @param {Object} `options`
 * @return {Object} Returns an object with
 * @api public
 */
picomatch.scan = (input, options) => scan(input, options);
/**
 * Create a regular expression from a glob pattern.
 *
 * ```js
 * const picomatch = require('picomatch');
 * // picomatch.makeRe(input[, options]);
 *
 * console.log(picomatch.makeRe('*.js'));
 * //=> /^(?:(?!\.)(?=.)[^/]*?\.js)$/
 * ```
 * @param {String} `input` A glob pattern to convert to regex.
 * @param {Object} `options`
 * @return {RegExp} Returns a regex created from the given pattern.
 * @api public
 */
picomatch.makeRe = (input, options, returnOutput = false, returnState = false) => {
    if (!input || typeof input !== 'string') {
        throw new TypeError('Expected a non-empty string');
    }
    let opts = options || {};
    let prepend = opts.contains ? '' : '^';
    let append = opts.contains ? '' : '$';
    let state = { negated: false, fastpaths: true };
    let prefix = '';
    let output;
    if (input.startsWith('./')) {
        input = input.slice(2);
        prefix = state.prefix = './';
    }
    if (opts.fastpaths !== false && (input[0] === '.' || input[0] === '*')) {
        output = parse_1$1.fastpaths(input, options);
    }
    if (output === void 0) {
        state = picomatch.parse(input, options);
        state.prefix = prefix + (state.prefix || '');
        output = state.output;
    }
    if (returnOutput === true) {
        return output;
    }
    let source = `${prepend}(?:${output})${append}`;
    if (state && state.negated === true) {
        source = `^(?!${source}).*$`;
    }
    let regex = picomatch.toRegex(source, options);
    if (returnState === true) {
        regex.state = state;
    }
    return regex;
};
/**
 * Create a regular expression from the given regex source string.
 *
 * ```js
 * const picomatch = require('picomatch');
 * // picomatch.toRegex(source[, options]);
 *
 * const { output } = picomatch.parse('*.js');
 * console.log(picomatch.toRegex(output));
 * //=> /^(?:(?!\.)(?=.)[^/]*?\.js)$/
 * ```
 * @param {String} `source` Regular expression source string.
 * @param {Object} `options`
 * @return {RegExp}
 * @api public
 */
picomatch.toRegex = (source, options) => {
    try {
        let opts = options || {};
        return new RegExp(source, opts.flags || (opts.nocase ? 'i' : ''));
    }
    catch (err) {
        if (options && options.debug === true)
            throw err;
        return /$^/;
    }
};
/**
 * Picomatch constants.
 * @return {Object}
 */
picomatch.constants = constants$1;
/**
 * Expose "picomatch"
 */
var picomatch_1 = picomatch;

var picomatch$1 = picomatch_1;

const isEmptyString = val => typeof val === 'string' && (val === '' || val === './');
/**
 * Returns an array of strings that match one or more glob patterns.
 *
 * ```js
 * const mm = require('micromatch');
 * // mm(list, patterns[, options]);
 *
 * console.log(mm(['a.js', 'a.txt'], ['*.js']));
 * //=> [ 'a.js' ]
 * ```
 * @param {String|Array<string>} list List of strings to match.
 * @param {String|Array<string>} patterns One or more glob patterns to use for matching.
 * @param {Object} options See available [options](#options)
 * @return {Array} Returns an array of matches
 * @summary false
 * @api public
 */
const micromatch = (list, patterns, options) => {
    patterns = [].concat(patterns);
    list = [].concat(list);
    let omit = new Set();
    let keep = new Set();
    let items = new Set();
    let negatives = 0;
    let onResult = state => {
        items.add(state.output);
        if (options && options.onResult) {
            options.onResult(state);
        }
    };
    for (let i = 0; i < patterns.length; i++) {
        let isMatch = picomatch$1(String(patterns[i]), Object.assign(Object.assign({}, options), { onResult }), true);
        let negated = isMatch.state.negated || isMatch.state.negatedExtglob;
        if (negated)
            negatives++;
        for (let item of list) {
            let matched = isMatch(item, true);
            let match = negated ? !matched.isMatch : matched.isMatch;
            if (!match)
                continue;
            if (negated) {
                omit.add(matched.output);
            }
            else {
                omit.delete(matched.output);
                keep.add(matched.output);
            }
        }
    }
    let result = negatives === patterns.length ? [...items] : [...keep];
    let matches = result.filter(item => !omit.has(item));
    if (options && matches.length === 0) {
        if (options.failglob === true) {
            throw new Error(`No matches found for "${patterns.join(', ')}"`);
        }
        if (options.nonull === true || options.nullglob === true) {
            return options.unescape ? patterns.map(p => p.replace(/\\/g, '')) : patterns;
        }
    }
    return matches;
};
/**
 * Backwards compatibility
 */
micromatch.match = micromatch;
/**
 * Returns a matcher function from the given glob `pattern` and `options`.
 * The returned function takes a string to match as its only argument and returns
 * true if the string is a match.
 *
 * ```js
 * const mm = require('micromatch');
 * // mm.matcher(pattern[, options]);
 *
 * const isMatch = mm.matcher('*.!(*a)');
 * console.log(isMatch('a.a')); //=> false
 * console.log(isMatch('a.b')); //=> true
 * ```
 * @param {String} `pattern` Glob pattern
 * @param {Object} `options`
 * @return {Function} Returns a matcher function.
 * @api public
 */
micromatch.matcher = (pattern, options) => picomatch$1(pattern, options);
/**
 * Returns true if **any** of the given glob `patterns` match the specified `string`.
 *
 * ```js
 * const mm = require('micromatch');
 * // mm.isMatch(string, patterns[, options]);
 *
 * console.log(mm.isMatch('a.a', ['b.*', '*.a'])); //=> true
 * console.log(mm.isMatch('a.a', 'b.*')); //=> false
 * ```
 * @param {String} str The string to test.
 * @param {String|Array} patterns One or more glob patterns to use for matching.
 * @param {Object} [options] See available [options](#options).
 * @return {Boolean} Returns true if any patterns match `str`
 * @api public
 */
micromatch.isMatch = (str, patterns, options) => picomatch$1(patterns, options)(str);
/**
 * Backwards compatibility
 */
micromatch.any = micromatch.isMatch;
/**
 * Returns a list of strings that _**do not match any**_ of the given `patterns`.
 *
 * ```js
 * const mm = require('micromatch');
 * // mm.not(list, patterns[, options]);
 *
 * console.log(mm.not(['a.a', 'b.b', 'c.c'], '*.a'));
 * //=> ['b.b', 'c.c']
 * ```
 * @param {Array} `list` Array of strings to match.
 * @param {String|Array} `patterns` One or more glob pattern to use for matching.
 * @param {Object} `options` See available [options](#options) for changing how matches are performed
 * @return {Array} Returns an array of strings that **do not match** the given patterns.
 * @api public
 */
micromatch.not = (list, patterns, options = {}) => {
    patterns = [].concat(patterns).map(String);
    let result = new Set();
    let items = [];
    let onResult = state => {
        if (options.onResult)
            options.onResult(state);
        items.push(state.output);
    };
    let matches = micromatch(list, patterns, Object.assign(Object.assign({}, options), { onResult }));
    for (let item of items) {
        if (!matches.includes(item)) {
            result.add(item);
        }
    }
    return [...result];
};
/**
 * Returns true if the given `string` contains the given pattern. Similar
 * to [.isMatch](#isMatch) but the pattern can match any part of the string.
 *
 * ```js
 * var mm = require('micromatch');
 * // mm.contains(string, pattern[, options]);
 *
 * console.log(mm.contains('aa/bb/cc', '*b'));
 * //=> true
 * console.log(mm.contains('aa/bb/cc', '*d'));
 * //=> false
 * ```
 * @param {String} `str` The string to match.
 * @param {String|Array} `patterns` Glob pattern to use for matching.
 * @param {Object} `options` See available [options](#options) for changing how matches are performed
 * @return {Boolean} Returns true if the patter matches any part of `str`.
 * @api public
 */
micromatch.contains = (str, pattern, options) => {
    if (typeof str !== 'string') {
        throw new TypeError(`Expected a string: "${util.inspect(str)}"`);
    }
    if (Array.isArray(pattern)) {
        return pattern.some(p => micromatch.contains(str, p, options));
    }
    if (typeof pattern === 'string') {
        if (isEmptyString(str) || isEmptyString(pattern)) {
            return false;
        }
        if (str.includes(pattern) || (str.startsWith('./') && str.slice(2).includes(pattern))) {
            return true;
        }
    }
    return micromatch.isMatch(str, pattern, Object.assign(Object.assign({}, options), { contains: true }));
};
/**
 * Filter the keys of the given object with the given `glob` pattern
 * and `options`. Does not attempt to match nested keys. If you need this feature,
 * use [glob-object][] instead.
 *
 * ```js
 * const mm = require('micromatch');
 * // mm.matchKeys(object, patterns[, options]);
 *
 * const obj = { aa: 'a', ab: 'b', ac: 'c' };
 * console.log(mm.matchKeys(obj, '*b'));
 * //=> { ab: 'b' }
 * ```
 * @param {Object} `object` The object with keys to filter.
 * @param {String|Array} `patterns` One or more glob patterns to use for matching.
 * @param {Object} `options` See available [options](#options) for changing how matches are performed
 * @return {Object} Returns an object with only keys that match the given patterns.
 * @api public
 */
micromatch.matchKeys = (obj, patterns, options) => {
    if (!utils$2.isObject(obj)) {
        throw new TypeError('Expected the first argument to be an object');
    }
    let keys = micromatch(Object.keys(obj), patterns, options);
    let res = {};
    for (let key of keys)
        res[key] = obj[key];
    return res;
};
/**
 * Returns true if some of the strings in the given `list` match any of the given glob `patterns`.
 *
 * ```js
 * const mm = require('micromatch');
 * // mm.some(list, patterns[, options]);
 *
 * console.log(mm.some(['foo.js', 'bar.js'], ['*.js', '!foo.js']));
 * // true
 * console.log(mm.some(['foo.js'], ['*.js', '!foo.js']));
 * // false
 * ```
 * @param {String|Array} `list` The string or array of strings to test. Returns as soon as the first match is found.
 * @param {String|Array} `patterns` One or more glob patterns to use for matching.
 * @param {Object} `options` See available [options](#options) for changing how matches are performed
 * @return {Boolean} Returns true if any patterns match `str`
 * @api public
 */
micromatch.some = (list, patterns, options) => {
    let items = [].concat(list);
    for (let pattern of [].concat(patterns)) {
        let isMatch = picomatch$1(String(pattern), options);
        if (items.some(item => isMatch(item))) {
            return true;
        }
    }
    return false;
};
/**
 * Returns true if every string in the given `list` matches
 * any of the given glob `patterns`.
 *
 * ```js
 * const mm = require('micromatch');
 * // mm.every(list, patterns[, options]);
 *
 * console.log(mm.every('foo.js', ['foo.js']));
 * // true
 * console.log(mm.every(['foo.js', 'bar.js'], ['*.js']));
 * // true
 * console.log(mm.every(['foo.js', 'bar.js'], ['*.js', '!foo.js']));
 * // false
 * console.log(mm.every(['foo.js'], ['*.js', '!foo.js']));
 * // false
 * ```
 * @param {String|Array} `list` The string or array of strings to test.
 * @param {String|Array} `patterns` One or more glob patterns to use for matching.
 * @param {Object} `options` See available [options](#options) for changing how matches are performed
 * @return {Boolean} Returns true if any patterns match `str`
 * @api public
 */
micromatch.every = (list, patterns, options) => {
    let items = [].concat(list);
    for (let pattern of [].concat(patterns)) {
        let isMatch = picomatch$1(String(pattern), options);
        if (!items.every(item => isMatch(item))) {
            return false;
        }
    }
    return true;
};
/**
 * Returns true if **all** of the given `patterns` match
 * the specified string.
 *
 * ```js
 * const mm = require('micromatch');
 * // mm.all(string, patterns[, options]);
 *
 * console.log(mm.all('foo.js', ['foo.js']));
 * // true
 *
 * console.log(mm.all('foo.js', ['*.js', '!foo.js']));
 * // false
 *
 * console.log(mm.all('foo.js', ['*.js', 'foo.js']));
 * // true
 *
 * console.log(mm.all('foo.js', ['*.js', 'f*', '*o*', '*o.js']));
 * // true
 * ```
 * @param {String|Array} `str` The string to test.
 * @param {String|Array} `patterns` One or more glob patterns to use for matching.
 * @param {Object} `options` See available [options](#options) for changing how matches are performed
 * @return {Boolean} Returns true if any patterns match `str`
 * @api public
 */
micromatch.all = (str, patterns, options) => {
    if (typeof str !== 'string') {
        throw new TypeError(`Expected a string: "${util.inspect(str)}"`);
    }
    return [].concat(patterns).every(p => picomatch$1(p, options)(str));
};
/**
 * Returns an array of matches captured by `pattern` in `string, or `null` if the pattern did not match.
 *
 * ```js
 * const mm = require('micromatch');
 * // mm.capture(pattern, string[, options]);
 *
 * console.log(mm.capture('test/*.js', 'test/foo.js'));
 * //=> ['foo']
 * console.log(mm.capture('test/*.js', 'foo/bar.css'));
 * //=> null
 * ```
 * @param {String} `glob` Glob pattern to use for matching.
 * @param {String} `input` String to match
 * @param {Object} `options` See available [options](#options) for changing how matches are performed
 * @return {Boolean} Returns an array of captures if the input matches the glob pattern, otherwise `null`.
 * @api public
 */
micromatch.capture = (glob, input, options) => {
    let posix = utils$2.isWindows(options);
    let regex = picomatch$1.makeRe(String(glob), Object.assign(Object.assign({}, options), { capture: true }));
    let match = regex.exec(posix ? utils$2.toPosixSlashes(input) : input);
    if (match) {
        return match.slice(1).map(v => v === void 0 ? '' : v);
    }
};
/**
 * Create a regular expression from the given glob `pattern`.
 *
 * ```js
 * const mm = require('micromatch');
 * // mm.makeRe(pattern[, options]);
 *
 * console.log(mm.makeRe('*.js'));
 * //=> /^(?:(\.[\\\/])?(?!\.)(?=.)[^\/]*?\.js)$/
 * ```
 * @param {String} `pattern` A glob pattern to convert to regex.
 * @param {Object} `options`
 * @return {RegExp} Returns a regex created from the given pattern.
 * @api public
 */
micromatch.makeRe = (...args) => picomatch$1.makeRe(...args);
/**
 * Scan a glob pattern to separate the pattern into segments. Used
 * by the [split](#split) method.
 *
 * ```js
 * const mm = require('micromatch');
 * const state = mm.scan(pattern[, options]);
 * ```
 * @param {String} `pattern`
 * @param {Object} `options`
 * @return {Object} Returns an object with
 * @api public
 */
micromatch.scan = (...args) => picomatch$1.scan(...args);
/**
 * Parse a glob pattern to create the source string for a regular
 * expression.
 *
 * ```js
 * const mm = require('micromatch');
 * const state = mm(pattern[, options]);
 * ```
 * @param {String} `glob`
 * @param {Object} `options`
 * @return {Object} Returns an object with useful properties and output to be used as regex source string.
 * @api public
 */
micromatch.parse = (patterns, options) => {
    let res = [];
    for (let pattern of [].concat(patterns || [])) {
        for (let str of braces_1(String(pattern), options)) {
            res.push(picomatch$1.parse(str, options));
        }
    }
    return res;
};
/**
 * Process the given brace `pattern`.
 *
 * ```js
 * const { braces } = require('micromatch');
 * console.log(braces('foo/{a,b,c}/bar'));
 * //=> [ 'foo/(a|b|c)/bar' ]
 *
 * console.log(braces('foo/{a,b,c}/bar', { expand: true }));
 * //=> [ 'foo/a/bar', 'foo/b/bar', 'foo/c/bar' ]
 * ```
 * @param {String} `pattern` String with brace pattern to process.
 * @param {Object} `options` Any [options](#options) to change how expansion is performed. See the [braces][] library for all available options.
 * @return {Array}
 * @api public
 */
micromatch.braces = (pattern, options) => {
    if (typeof pattern !== 'string')
        throw new TypeError('Expected a string');
    if ((options && options.nobrace === true) || !/\{.*\}/.test(pattern)) {
        return [pattern];
    }
    return braces_1(pattern, options);
};
/**
 * Expand braces
 */
micromatch.braceExpand = (pattern, options) => {
    if (typeof pattern !== 'string')
        throw new TypeError('Expected a string');
    return micromatch.braces(pattern, Object.assign(Object.assign({}, options), { expand: true }));
};
/**
 * Expose micromatch
 */
var micromatch_1 = micromatch;

function ensureArray$1(thing) {
    if (Array.isArray(thing))
        return thing;
    if (thing == undefined)
        return [];
    return [thing];
}

function getMatcherString(id, resolutionBase) {
    if (resolutionBase === false) {
        return id;
    }
    return path.resolve(...(typeof resolutionBase === 'string' ? [resolutionBase, id] : [id]));
}
const createFilter = function createFilter(include, exclude, options) {
    const resolutionBase = options && options.resolve;
    const getMatcher = (id) => {
        return id instanceof RegExp
            ? id
            : {
                test: micromatch_1.matcher(getMatcherString(id, resolutionBase)
                    .split(path.sep)
                    .join('/'), { dot: true })
            };
    };
    const includeMatchers = ensureArray$1(include).map(getMatcher);
    const excludeMatchers = ensureArray$1(exclude).map(getMatcher);
    return function (id) {
        if (typeof id !== 'string')
            return false;
        if (/\0/.test(id))
            return false;
        id = id.split(path.sep).join('/');
        for (let i = 0; i < excludeMatchers.length; ++i) {
            const matcher = excludeMatchers[i];
            if (matcher.test(id))
                return false;
        }
        for (let i = 0; i < includeMatchers.length; ++i) {
            const matcher = includeMatchers[i];
            if (matcher.test(id))
                return true;
        }
        return !includeMatchers.length;
    };
};

let chokidar;
try {
    chokidar = index.relative('chokidar', process.cwd());
}
catch (err) {
    chokidar = null;
}
var chokidar$1 = chokidar;

const opts = { encoding: 'utf-8', persistent: true };
const watchers = new Map();
function addTask(id, task, chokidarOptions, chokidarOptionsHash, isTransformDependency) {
    if (!watchers.has(chokidarOptionsHash))
        watchers.set(chokidarOptionsHash, new Map());
    const group = watchers.get(chokidarOptionsHash);
    const watcher = group.get(id) || new FileWatcher(id, chokidarOptions, group);
    if (!watcher.fsWatcher) {
        if (isTransformDependency)
            throw new Error(`Transform dependency ${id} does not exist.`);
    }
    else {
        watcher.addTask(task, isTransformDependency);
    }
}
function deleteTask(id, target, chokidarOptionsHash) {
    const group = watchers.get(chokidarOptionsHash);
    const watcher = group.get(id);
    if (watcher)
        watcher.deleteTask(target, group);
}
class FileWatcher {
    constructor(id, chokidarOptions, group) {
        this.id = id;
        this.tasks = new Set();
        this.transformDependencyTasks = new Set();
        let modifiedTime;
        try {
            const stats = fs.statSync(id);
            modifiedTime = +stats.mtime;
        }
        catch (err) {
            if (err.code === 'ENOENT') {
                // can't watch files that don't exist (e.g. injected
                // by plugins somehow)
                return;
            }
            throw err;
        }
        const handleWatchEvent = (event) => {
            if (event === 'rename' || event === 'unlink') {
                this.close();
                group.delete(id);
                this.trigger(id);
                return;
            }
            else {
                let stats;
                try {
                    stats = fs.statSync(id);
                }
                catch (err) {
                    if (err.code === 'ENOENT') {
                        modifiedTime = -1;
                        this.trigger(id);
                        return;
                    }
                    throw err;
                }
                // debounce
                if (+stats.mtime - modifiedTime > 15)
                    this.trigger(id);
            }
        };
        this.fsWatcher = chokidarOptions
            ? chokidar$1.watch(id, chokidarOptions).on('all', handleWatchEvent)
            : fs.watch(id, opts, handleWatchEvent);
        group.set(id, this);
    }
    addTask(task, isTransformDependency) {
        if (isTransformDependency)
            this.transformDependencyTasks.add(task);
        else
            this.tasks.add(task);
    }
    close() {
        if (this.fsWatcher)
            this.fsWatcher.close();
    }
    deleteTask(task, group) {
        let deleted = this.tasks.delete(task);
        deleted = this.transformDependencyTasks.delete(task) || deleted;
        if (deleted && this.tasks.size === 0 && this.transformDependencyTasks.size === 0) {
            group.delete(this.id);
            this.close();
        }
    }
    trigger(id) {
        this.tasks.forEach(task => {
            task.invalidate(id, false);
        });
        this.transformDependencyTasks.forEach(task => {
            task.invalidate(id, true);
        });
    }
}

const DELAY = 200;
class Watcher {
    constructor(configs) {
        this.buildTimeout = null;
        this.invalidatedIds = new Set();
        this.rerun = false;
        this.emitter = new (class extends events.EventEmitter {
            constructor(close) {
                super();
                this.close = close;
                // Allows more than 10 bundles to be watched without
                // showing the `MaxListenersExceededWarning` to the user.
                this.setMaxListeners(Infinity);
            }
        })(this.close.bind(this));
        this.tasks = (Array.isArray(configs) ? configs : configs ? [configs] : []).map(config => new Task(this, config));
        this.running = true;
        process.nextTick(() => this.run());
    }
    close() {
        if (this.buildTimeout)
            clearTimeout(this.buildTimeout);
        for (const task of this.tasks) {
            task.close();
        }
        this.emitter.removeAllListeners();
    }
    emit(event, value) {
        this.emitter.emit(event, value);
    }
    invalidate(id) {
        if (id) {
            this.invalidatedIds.add(id);
        }
        if (this.running) {
            this.rerun = true;
            return;
        }
        if (this.buildTimeout)
            clearTimeout(this.buildTimeout);
        this.buildTimeout = setTimeout(() => {
            this.buildTimeout = null;
            for (const id of this.invalidatedIds) {
                this.emit('change', id);
            }
            this.invalidatedIds.clear();
            this.emit('restart');
            this.run();
        }, DELAY);
    }
    run() {
        this.running = true;
        this.emit('event', {
            code: 'START'
        });
        let taskPromise = Promise.resolve();
        for (const task of this.tasks)
            taskPromise = taskPromise.then(() => task.run());
        return taskPromise
            .then(() => {
            this.running = false;
            this.emit('event', {
                code: 'END'
            });
        })
            .catch(error => {
            this.running = false;
            this.emit('event', {
                code: 'ERROR',
                error
            });
        })
            .then(() => {
            if (this.rerun) {
                this.rerun = false;
                this.invalidate();
            }
        });
    }
}
class Task {
    constructor(watcher, config) {
        this.cache = { modules: [] };
        this.watchFiles = [];
        this.invalidated = true;
        this.watcher = watcher;
        this.closed = false;
        this.watched = new Set();
        const { inputOptions, outputOptions } = index.mergeOptions({
            config
        });
        this.inputOptions = inputOptions;
        this.outputs = outputOptions;
        this.outputFiles = this.outputs.map(output => {
            if (output.file || output.dir)
                return path.resolve(output.file || output.dir);
            return undefined;
        });
        const watchOptions = inputOptions.watch || {};
        if ('useChokidar' in watchOptions)
            watchOptions.chokidar = watchOptions.useChokidar;
        let chokidarOptions = 'chokidar' in watchOptions ? watchOptions.chokidar : !!chokidar$1;
        if (chokidarOptions) {
            chokidarOptions = Object.assign(Object.assign({}, (chokidarOptions === true ? {} : chokidarOptions)), { disableGlobbing: true, ignoreInitial: true });
        }
        if (chokidarOptions && !chokidar$1) {
            throw new Error(`watch.chokidar was provided, but chokidar could not be found. Have you installed it?`);
        }
        this.chokidarOptions = chokidarOptions;
        this.chokidarOptionsHash = JSON.stringify(chokidarOptions);
        this.filter = createFilter(watchOptions.include, watchOptions.exclude);
    }
    close() {
        this.closed = true;
        for (const id of this.watched) {
            deleteTask(id, this, this.chokidarOptionsHash);
        }
    }
    invalidate(id, isTransformDependency) {
        this.invalidated = true;
        if (isTransformDependency) {
            for (const module of this.cache.modules) {
                if (module.transformDependencies.indexOf(id) === -1)
                    continue;
                // effective invalidation
                module.originalCode = null;
            }
        }
        this.watcher.invalidate(id);
    }
    run() {
        if (!this.invalidated)
            return;
        this.invalidated = false;
        const options = Object.assign(Object.assign({}, this.inputOptions), { cache: this.cache });
        const start = Date.now();
        this.watcher.emit('event', {
            code: 'BUNDLE_START',
            input: this.inputOptions.input,
            output: this.outputFiles
        });
        setWatcher(this.watcher.emitter);
        return rollup(options)
            .then(result => {
            if (this.closed)
                return undefined;
            this.updateWatchedFiles(result);
            return Promise.all(this.outputs.map(output => result.write(output))).then(() => result);
        })
            .then((result) => {
            this.watcher.emit('event', {
                code: 'BUNDLE_END',
                duration: Date.now() - start,
                input: this.inputOptions.input,
                output: this.outputFiles,
                result
            });
        })
            .catch((error) => {
            if (this.closed)
                return;
            if (Array.isArray(error.watchFiles)) {
                for (const id of error.watchFiles) {
                    this.watchFile(id);
                }
            }
            throw error;
        });
    }
    updateWatchedFiles(result) {
        const previouslyWatched = this.watched;
        this.watched = new Set();
        this.watchFiles = result.watchFiles;
        this.cache = result.cache;
        for (const id of this.watchFiles) {
            this.watchFile(id);
        }
        for (const module of this.cache.modules) {
            for (const depId of module.transformDependencies) {
                this.watchFile(depId, true);
            }
        }
        for (const id of previouslyWatched) {
            if (!this.watched.has(id))
                deleteTask(id, this, this.chokidarOptionsHash);
        }
    }
    watchFile(id, isTransformDependency = false) {
        if (!this.filter(id))
            return;
        this.watched.add(id);
        if (this.outputFiles.some(file => file === id)) {
            throw new Error('Cannot import the generated bundle');
        }
        // this is necessary to ensure that any 'renamed' files
        // continue to be watched following an error
        addTask(id, this, this.chokidarOptions, this.chokidarOptionsHash, isTransformDependency);
    }
}
function watch(configs) {
    return new Watcher(configs).emitter;
}

exports.VERSION = index.version;
exports.rollup = rollup;
exports.watch = watch;
//# sourceMappingURL=rollup.js.map
