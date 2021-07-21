require('./setup');
var extend = require('util')._extend;
var out, input, str;

describe('Hicat the module', function() {
  it('is a function', function () {
    expect(hicat).be.a('function');
  });

  it('has colors', function () {
    expect(hicat.colors).be.a('object');
    expect(hicat.colors.string).be.a('string');
  });
});

describe('Explicitly setting the language', function() {
  beforeEach(function () {
    input = 'var x = 2 + "hi"; /*yo*/';
    out = hicat(input, { lang: 'javascript' });
  });

  it('produces .language', function () {
    expect(out.language).be.eql('javascript');
  });
});

describe('Json prettification', function () {
  var obj = {
    name: "Jake Rockwell",
    position: "Land Operations Specialist"
  };

  beforeEach(function () {
    input = JSON.stringify(obj);
    out = hicat(input, { lang: 'json' });
  });

  it('happens', function () {
    expect(out.raw).eql(JSON.stringify(obj, null, 2) + "\n");
  });
});

describe('Explicitly setting an invalid language', function() {
  beforeEach(function () {
    input = '{"a":2}';
    out = hicat(input, { lang: 'aoeu' });
  });

  it('auto-detects the language', function () {
    expect(out.language).be.eql('json');
  });
});

describe('A simple example', function() {
  var str, out, input;

  beforeEach(function () {
    input = 'var x = 2345 + "hi"; /*yo*/ window.document.x = function($){};';
    out = hicat(input);
    str = out.ansi;
  });

  it('produces .language', function () {
    expect(out.language).be.eql('javascript');
  });

  it('produces .ansi', function () {
    expect(out.ansi).be.a('string');
  });

  it('produces .raw', function () {
    expect(out.raw).eql(input);
  });

  it('produces ansi codes', function () {
    var code = str.replace(/\033[^m]+m/g, '');
    expect(code).eql(input);
  });

  it('highlights numbers', function () {
    var fragment = hicat.colorize('2345', hicat.color('number', 'javascript'));
    expect(str).include(str);
  });

  it('highlights comments', function () {
    var fragment = hicat.colorize('/*yo*/', hicat.color('comment', 'javascript'));
    expect(str).include(fragment);
  });
});

describe('Hicat.color', function () {
  var oldcolors;

  beforeEach(function () {
    oldcolors = extend({}, hicat.colors);
  });

  afterEach(function () {
    hicat.colors = oldcolors;
  });

  it('works for simple cases', function () {
    hicat.colors = { string: '80' };
    expect(hicat.color('string')).eql('80');
  });

  it('resolves references', function () {
    hicat.colors = { string: '70', str: 'string', s: 'str' };
    expect(hicat.color('s')).eql('70');
  });

  it('accounts for languages', function () {
    hicat.colors = { val: '20', 'json:val': '30' };
    expect(hicat.color('val')).eql('20');
    expect(hicat.color('json:val')).eql('30');
  });

});

describe('Hicat.colorize', function () {
  it('works', function () {
    var fragment = hicat.colorize('yo', '32');
    expect(fragment).eql('\033[32m' + 'yo' + '\033[0m');
  });
});
