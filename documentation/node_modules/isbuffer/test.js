var test = require('tape');
var isBuffer = require('./index.js');
var Buffer = require('buffer').Buffer;

test('node.js buffer', function (t) {
  t.ok(isBuffer(new Buffer(3)));
  t.end();
});

test('Typed Arrays', function (t) {
  if (typeof Int8Array != 'undefined') t.ok(isBuffer(new Int8Array()));
  if (typeof Int16Array != 'undefined') t.ok(isBuffer(new Int16Array()));
  if (typeof Int32Array != 'undefined') t.ok(isBuffer(new Int32Array()));
  if (typeof Uint8Array != 'undefined') t.ok(isBuffer(new Uint8Array()));
  if (typeof Uint16Array != 'undefined') t.ok(isBuffer(new Uint16Array()));
  if (typeof Uint32Array != 'undefined') t.ok(isBuffer(new Uint32Array()));
  if (typeof Uint8ClampedArray != 'undefined') t.ok(isBuffer(new Uint8ClampedArray()));
  if (typeof Float32Array != 'undefined') t.ok(isBuffer(new Float32Array()));
  if (typeof Float64Array != 'undefined') t.ok(isBuffer(new Float64Array()));
  if (typeof ArrayBuffer != 'undefined') t.ok(isBuffer(new ArrayBuffer()));
  t.ok(true); // have at least one passing test
  t.end();
});

test('non buffers', function (t) {
  t.notOk(isBuffer(null));
  t.notOk(isBuffer(undefined));
  t.notOk(isBuffer(1));
  t.notOk(isBuffer(''));
  t.notOk(isBuffer([]));
  t.notOk(isBuffer({}));
  t.end();
});
