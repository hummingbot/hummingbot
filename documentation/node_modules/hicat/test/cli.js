require('./setup');

var run = require('./cli_helpers').run,
    pipe = require('./cli_helpers').pipe;
    success = require('./cli_helpers').success;

describe('pipe', function () {

  var input = 'var x = 2';
  pipe(input);
  success();

  it('has no stderr', function () {
    expect(result.stderr).eql('');
  });

  it('has results', function () {
    expect(result.out).eql(hicat(input).ansi);
  });
});

describe('--help', function () {
  run('--help');
  success();

  it('shows --help', function () {
    expect(result.out).include('-h, --help');
    expect(result.out).include('print usage information');
  });
});

describe('--version', function () {
  run('--version');
  success();

  it('shows version info', function () {
    expect(result.out).include(require('../package.json').version);
  });
});

describe('-v', function () {
  run('-v');
  success();

  it('shows version info', function () {
    expect(result.out).include(require('../package.json').version);
  });
});

describe('--languages', function () {
  run('--languages');
  success();

  it('has color constants', function () {
    var out = hicat.listLanguages().sort().join('\n');
    expect(result.out.trim()).eql(out);
  });
});

describe('--list-colors', function () {
  run('--list-colors');
  success();

  it('has color constants', function () {
    expect(result.out).match(/RED=[0-9;]+/);
    expect(result.out).match(/GREEN=[0-9;]+/);
    expect(result.out).match(/BLUE=[0-9;]+/);
    expect(result.out).match(/CYAN=[0-9;]+/);
    expect(result.out).match(/YELLOW=[0-9;]+/);
  });

  it('has "value"', function () {
    expect(result.out).match(/value=.*/);
  });
});

describe('a ruby example', function () {
  run('samples/ruby.rb --no-pager');
  success();

  it('highlights', function () {
    expect(result.out).match(/method/);
    expect(result.out).match(/string/);
  });
});

describe('coercing via --lang', function () {
  run('samples/ruby.rb --no-pager --lang markdown --debug');
  success();

  it('works', function () {
    expect(result.out).match(/language: markdown/);
  });
});

describe('--numbers', function () {
  run('samples/ruby.rb --numbers');
  success();

  it('prefixes with numbers', function () {
    expect(result.stripped).match(/  1 class MyClass/);
    expect(result.stripped).match(/  2   NUMBER = 200/);
    expect(result.stripped).match(/  4   def method/);
  });

  it('colors the numbers', function () {
    expect(result.out).include(hicat.colorize('  3 ', hicat.color('line_number')));
  });
});

describe('coercing via -l', function () {
  run('samples/ruby.rb --no-pager -l markdown --debug');
  success();

  it('works', function () {
    expect(result.out).match(/language: markdown/);
  });
});

describe('a ruby example with --debug', function () {
  run('samples/ruby.rb --debug');
  success();

  it('highlights tags', function () {
    expect(result.out).match(/\[string\].*\[\/string\]/);
  });

  it('tells the language', function () {
    var strip = result.out.replace(/\033[^m]*m/g, '');
    expect(strip).include('hicat language: rb');
  });
});

describe('not found', function () {
  run('xxx yyy zzz --no-pager');

  it('fails', function () {
    expect(result.code).eql(8);
  });

  it('does no output', function () {
    expect(result.out).eql('');
  });

  it('reports errors', function () {
    expect(result.stderr).match(/xxx/);
    expect(result.stderr).match(/yyy/);
    expect(result.stderr).match(/zzz/);
    expect(result.stderr).match(/no such file or directory/);
  });
});
