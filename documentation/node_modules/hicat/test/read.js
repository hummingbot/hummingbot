/* jshint expr: true */
var expect = require('chai').expect;
var read = require('../lib/read');

describe('read.files', function () {
  var res;

  beforeEach(function (next) {
    read(['./test/read.js', './foo'], function (err, _res) {
      expect(err).falsy;
      res = _res;
      next();
    });
  });

  it('returns .files', function () {
    expect(res.files).array;
    expect(res.files).have.length(2);
  });

  it('concatenates res', function () {
    expect(res.data).eql(res.files[0].data);
  });

  it('gives res', function () {
    var file = res.files[0];
    expect(file.data).a('string');
    expect(file.data).match(/Hola mundo/);
    expect(file.name).eql('./test/read.js');
  });

  it('gives errors', function () {
    var file = res.files[1];
    expect(file.error).instanceOf(Error);
    expect(file.error.code).eql('ENOENT');
  });
});

/* Hola mundo */
