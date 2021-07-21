var tape = require('tape');
var levelup = require('levelup');
var memdown = require('memdown');

var blobs = function() {
	return require('../')(levelup('mem', {db:memdown}));
};

tape('write + read', function(t) {
	var bl = blobs();

	bl.write('test', 'hello world', function(err) {
		t.ok(!err);
		bl.read('test', function(err, buf) {
			t.ok(!err);
			t.same(buf.toString(), 'hello world');
			t.end();
		});
	});
});

tape('streams', function(t) {
	var bl = blobs();
	var ws = bl.createWriteStream('test');

	ws.on('finish', function() {
		var rs = bl.createReadStream('test');
		var buffer = [];

		rs.on('data', function(data) {
			buffer.push(data);
		});
		rs.on('end', function() {
			t.same(Buffer.concat(buffer).toString(), 'hello world');
			t.end();
		});
	});

	ws.write('hello ');
	ws.end('world');
});

tape('random access', function(t) {
	var bl = blobs();

	bl.write('test', 'hello world', function() {
		bl.read('test', {start:6}, function(err, buf) {
			t.ok(!err);
			t.same(buf.toString(), 'world');
			t.end();
		});
	});
});

tape('append', function(t) {
	var bl = blobs();

	bl.write('test', 'hello ', function() {
		bl.write('test', 'world', {append:true}, function() {
			bl.read('test', {start:6}, function(err, buf) {
				t.ok(!err);
				t.same(buf.toString(), 'world');
				t.end();
			});
		});
	});
});

tape('write read write read', function(t) {
	var bl = blobs();

	bl.write('test', 'hello', function() {
		bl.read('test', function(err, buf) {
			t.same(buf.toString(), 'hello');
			bl.write('test', 'world', function() {
				bl.read('test', function(err, buf) {
					t.same(buf.toString(), 'world');
					t.end();
				});
			});
		});
	});
});

tape('write + size', function(t) {
	var bl = blobs();

	bl.size('bar', function(err, size) {
		t.same(size, 0);
		bl.write('bar', 'world', function() {
			bl.size('bar', function(err, size) {
				t.same(size, 5);
				bl.size('foo', function(err, size) {
					t.same(size, 0);
					bl.write('baz', 'hi', function() {
						bl.size('baz', function(err, size) {
							t.same(size, 2);
							bl.size('bar', function(err, size) {
								t.same(size, 5);
								t.end();
							});
						});
					});
				});
			});
		});
	});
});