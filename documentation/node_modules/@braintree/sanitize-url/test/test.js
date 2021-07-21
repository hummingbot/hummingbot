'use strict';

var expect = require('chai').expect;
var sanitizeUrl = require('../').sanitizeUrl;

describe('sanitizeUrl', function () {
  it('replaces javascript urls with about:blank', function () {
    expect(sanitizeUrl('javascript:alert(document.domain)')).to.equal('about:blank');
  });

  it('disregards capitalization for JavaScript urls', function () {
    expect(sanitizeUrl('jAvasCrIPT:alert(document.domain)')).to.equal('about:blank');
  });

  it('ignores ctrl characters in javascript urls', function () {
    expect(sanitizeUrl(decodeURIComponent('JaVaScRiP%0at:alert(document.domain)'))).to.equal('about:blank');
  });

  it('replaces javascript urls with about:blank when javascript url begins with %20', function () {
    expect(sanitizeUrl('%20%20%20%20javascript:alert(document.domain)')).to.equal('about:blank');
  });

  it('replaces javascript urls with about:blank when javascript url begins with \s', function () {
    expect(sanitizeUrl('    javascript:alert(document.domain)')).to.equal('about:blank');
  });

  it('does not replace javascript: if it is not in the scheme of the URL', function () {
    expect(sanitizeUrl('http://example.com#myjavascript:foo')).to.equal('http://example.com#myjavascript:foo');
  });

  it('replaces data urls with about:blank', function () {
    expect(sanitizeUrl('data:text/html;base64,PH%3Cscript%3Ealert(document.domain)%3C/script%3E')).to.equal('about:blank');
  });

  it('replaces data urls with about:blank when data url begins with %20', function () {
    expect(sanitizeUrl('%20%20%20%20data:text/html;base64,PH%3Cscript%3Ealert(document.domain)%3C/script%3E')).to.equal('about:blank');
  });

  it('replaces data urls with about:blank when data url begins with \s', function () {
    expect(sanitizeUrl('    data:text/html;base64,PH%3Cscript%3Ealert(document.domain)%3C/script%3E')).to.equal('about:blank');
  });

  it('disregards capitalization for data urls', function () {
    expect(sanitizeUrl('dAtA:text/html;base64,PH%3Cscript%3Ealert(document.domain)%3C/script%3E')).to.equal('about:blank');
  });

  it('ignores ctrl characters in data urls', function () {
    expect(sanitizeUrl(decodeURIComponent('dat%0aa:text/html;base64,PH%3Cscript%3Ealert(document.domain)%3C/script%3E'))).to.equal('about:blank');
  });

  it('does not alter http URLs', function () {
    expect(sanitizeUrl('http://example.com/path/to:something')).to.equal('http://example.com/path/to:something');
  });

  it('does not alter http URLs with ports', function () {
    expect(sanitizeUrl('http://example.com:4567/path/to:something')).to.equal('http://example.com:4567/path/to:something');
  });

  it('does not alter https URLs', function () {
    expect(sanitizeUrl('https://example.com')).to.equal('https://example.com');
  });

  it('does not alter https URLs with ports', function () {
    expect(sanitizeUrl('https://example.com:4567/path/to:something')).to.equal('https://example.com:4567/path/to:something');
  });

  it('does not alter relative-path reference URLs', function () {
    expect(sanitizeUrl('./path/to/my.json')).to.equal('./path/to/my.json');
  });

  it('does not alter absolute-path reference URLs', function () {
    expect(sanitizeUrl('/path/to/my.json')).to.equal('/path/to/my.json');
  });

  it('does not alter network-path relative URLs', function () {
    expect(sanitizeUrl('//google.com/robots.txt')).to.equal('//google.com/robots.txt');
  });

  it('does not alter deep-link urls', function () {
    expect(sanitizeUrl('com.braintreepayments.demo://example')).to.equal('com.braintreepayments.demo://example');
  });

  it('does not alter mailto urls', function () {
      expect(sanitizeUrl('mailto:test@example.com?subject=hello+world')).to.equal('mailto:test@example.com?subject=hello+world');
  });

  it('replaces blank urls with about:blank', function () {
    expect(sanitizeUrl('')).to.equal('about:blank');
  });

  it('replaces null values with about:blank', function () {
    expect(sanitizeUrl(null)).to.equal('about:blank');
  });

  it('removes whitespace from urls', function () {
    expect(sanitizeUrl('   http://example.com/path/to:something    ')).to.equal('http://example.com/path/to:something');
  });
});
