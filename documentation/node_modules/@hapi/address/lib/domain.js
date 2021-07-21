'use strict';

const Url = require('url');


const internals = {
    minDomainSegments: 2,
    nonAsciiRx: /[^\x00-\x7f]/,
    domainControlRx: /[\x00-\x20@\:\/]/,                                                // Control + space + separators
    tldSegmentRx: /^[a-zA-Z](?:[a-zA-Z0-9\-]*[a-zA-Z0-9])?$/,
    domainSegmentRx: /^[a-zA-Z0-9](?:[a-zA-Z0-9\-]*[a-zA-Z0-9])?$/,
    URL: Url.URL || URL                                                                 // $lab:coverage:ignore$
};


exports.analyze = function (domain, options = {}) {

    if (typeof domain !== 'string') {
        throw new Error('Invalid input: domain must be a string');
    }

    if (!domain) {
        return { error: 'Domain must be a non-empty string' };
    }

    if (domain.length > 256) {
        return { error: 'Domain too long' };
    }

    const ascii = !internals.nonAsciiRx.test(domain);
    if (!ascii) {
        if (options.allowUnicode === false) {                                           // Defaults to true
            return { error: 'Domain contains forbidden Unicode characters' };
        }

        domain = domain.normalize('NFC');
    }

    if (internals.domainControlRx.test(domain)) {
        return { error: 'Domain contains invalid character' };
    }

    domain = internals.punycode(domain);

    // https://tools.ietf.org/html/rfc1035 section 2.3.1

    const minDomainSegments = options.minDomainSegments || internals.minDomainSegments;

    const segments = domain.split('.');
    if (segments.length < minDomainSegments) {
        return { error: 'Domain lacks the minimum required number of segments' };
    }

    const tlds = options.tlds;
    if (tlds) {
        const tld = segments[segments.length - 1].toLowerCase();
        if (tlds.deny && tlds.deny.has(tld) ||
            tlds.allow && !tlds.allow.has(tld)) {

            return { error: 'Domain uses forbidden TLD' };
        }
    }

    for (let i = 0; i < segments.length; ++i) {
        const segment = segments[i];

        if (!segment.length) {
            return { error: 'Domain contains empty dot-separated segment' };
        }

        if (segment.length > 63) {
            return { error: 'Domain contains dot-separated segment that is too long' };
        }

        if (i < segments.length - 1) {
            if (!internals.domainSegmentRx.test(segment)) {
                return { error: 'Domain contains invalid character' };
            }
        }
        else {
            if (!internals.tldSegmentRx.test(segment)) {
                return { error: 'Domain contains invalid tld character' };
            }
        }
    }
};


exports.isValid = function (domain, options) {

    return !exports.analyze(domain, options);
};


internals.punycode = function (domain) {

    try {
        return new internals.URL(`http://${domain}`).host;
    }
    catch (err) {
        return domain;
    }
};
