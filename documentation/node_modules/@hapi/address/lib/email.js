'use strict';

const Util = require('util');

const Domain = require('./domain');


const internals = {
    nonAsciiRx: /[^\x00-\x7f]/,
    encoder: new (Util.TextEncoder || TextEncoder)()                                            // $lab:coverage:ignore$
};


exports.analyze = function (email, options) {

    return internals.email(email, options);
};


exports.isValid = function (email, options) {

    return !internals.email(email, options);
};


internals.email = function (email, options = {}) {

    if (typeof email !== 'string') {
        throw new Error('Invalid input: email must be a string');
    }

    if (!email) {
        return { error: 'Address must be a non-empty string' };
    }

    // Unicode

    const ascii = !internals.nonAsciiRx.test(email);
    if (!ascii) {
        if (options.allowUnicode === false) {                                                   // Defaults to true
            return { error: 'Address contains forbidden Unicode characters' };
        }

        email = email.normalize('NFC');
    }

    // Basic structure

    const parts = email.split('@');
    if (parts.length !== 2) {
        return { error: parts.length > 2 ? 'Address cannot contain more than one @ character' : 'Address must contain one @ character' };
    }

    const [local, domain] = parts;

    if (!local) {
        return { error: 'Address local part cannot be empty' };
    }

    if (!options.ignoreLength) {
        if (email.length > 254) {                                           // http://tools.ietf.org/html/rfc5321#section-4.5.3.1.3
            return { error: 'Address too long' };
        }

        if (internals.encoder.encode(local).length > 64) {                  // http://tools.ietf.org/html/rfc5321#section-4.5.3.1.1
            return { error: 'Address local part too long' };
        }
    }

    // Validate parts

    return internals.local(local, ascii) || Domain.analyze(domain, options);
};


internals.local = function (local, ascii) {

    const segments = local.split('.');
    for (const segment of segments) {
        if (!segment.length) {
            return { error: 'Address local part contains empty dot-separated segment' };
        }

        if (ascii) {
            if (!internals.atextRx.test(segment)) {
                return { error: 'Address local part contains invalid character' };
            }

            continue;
        }

        for (const char of segment) {
            if (internals.atextRx.test(char)) {
                continue;
            }

            const binary = internals.binary(char);
            if (!internals.atomRx.test(binary)) {
                return { error: 'Address local part contains invalid character' };
            }
        }
    }
};


internals.binary = function (char) {

    return Array.from(internals.encoder.encode(char)).map((v) => String.fromCharCode(v)).join('');
};


/*
    From RFC 5321:

        Mailbox         =   Local-part "@" ( Domain / address-literal )

        Local-part      =   Dot-string / Quoted-string
        Dot-string      =   Atom *("."  Atom)
        Atom            =   1*atext
        atext           =   ALPHA / DIGIT / "!" / "#" / "$" / "%" / "&" / "'" / "*" / "+" / "-" / "/" / "=" / "?" / "^" / "_" / "`" / "{" / "|" / "}" / "~"

        Domain          =   sub-domain *("." sub-domain)
        sub-domain      =   Let-dig [Ldh-str]
        Let-dig         =   ALPHA / DIGIT
        Ldh-str         =   *( ALPHA / DIGIT / "-" ) Let-dig

        ALPHA           =   %x41-5A / %x61-7A        ; a-z, A-Z
        DIGIT           =   %x30-39                  ; 0-9

    From RFC 6531:

        sub-domain      =/  U-label
        atext           =/  UTF8-non-ascii

        UTF8-non-ascii  =   UTF8-2 / UTF8-3 / UTF8-4

        UTF8-2          =   %xC2-DF UTF8-tail
        UTF8-3          =   %xE0 %xA0-BF UTF8-tail /
                            %xE1-EC 2( UTF8-tail ) /
                            %xED %x80-9F UTF8-tail /
                            %xEE-EF 2( UTF8-tail )
        UTF8-4          =   %xF0 %x90-BF 2( UTF8-tail ) /
                            %xF1-F3 3( UTF8-tail ) /
                            %xF4 %x80-8F 2( UTF8-tail )

        UTF8-tail       =   %x80-BF

    Note: The following are not supported:

        RFC 5321: address-literal, Quoted-string
        RFC 5322: obs-*, CFWS
*/


internals.atextRx = /^[\w!#\$%&'\*\+\-/=\?\^`\{\|\}~]+$/;               // _ included in \w


internals.atomRx = new RegExp([

    //  %xC2-DF UTF8-tail
    '(?:[\\xc2-\\xdf][\\x80-\\xbf])',

    //  %xE0 %xA0-BF UTF8-tail              %xE1-EC 2( UTF8-tail )            %xED %x80-9F UTF8-tail              %xEE-EF 2( UTF8-tail )
    '(?:\\xe0[\\xa0-\\xbf][\\x80-\\xbf])|(?:[\\xe1-\\xec][\\x80-\\xbf]{2})|(?:\\xed[\\x80-\\x9f][\\x80-\\xbf])|(?:[\\xee-\\xef][\\x80-\\xbf]{2})',

    //  %xF0 %x90-BF 2( UTF8-tail )            %xF1-F3 3( UTF8-tail )            %xF4 %x80-8F 2( UTF8-tail )
    '(?:\\xf0[\\x90-\\xbf][\\x80-\\xbf]{2})|(?:[\\xf1-\\xf3][\\x80-\\xbf]{3})|(?:\\xf4[\\x80-\\x8f][\\x80-\\xbf]{2})'

].join('|'));
