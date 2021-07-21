var fwd = require('./');
var tape = require('tape');
var PassThrough = require('readable-stream/passthrough');

tape('fwd.readable', function(t) {
	var rs = fwd.readable({objectMode:true}, function(cb) {
		process.nextTick(function() {
			var pt = new PassThrough({objectMode:true});

			pt.write('hello');
			pt.write('world');
			pt.end();

			cb(null, pt);
		});
	});

	var expects = ['hello', 'world'];

	rs.on('data', function(data) {
		t.same(data, expects.shift());
	});

	rs.on('end', function() {
		t.same(expects, []);
		t.end();
	});
});

tape('fwd.readable and close', function(t) {
	var rs = fwd.readable({objectMode:true}, function(cb) {
		process.nextTick(function() {
			var pt = new PassThrough({objectMode:true});

			process.nextTick(function() {
				pt.write('hello');
				pt.write('world');
				pt.end();
				pt.emit('close');
			});

			cb(null, pt);
		});
	});

	var expects = ['hello', 'world'];

	rs.on('data', function(data) {
		t.same(data, expects.shift());
	});

	rs.on('close', function() {
		t.ok(rs._readableState.ended);
		t.same(expects, []);
		t.end();
	});
});

tape('fwd.writable', function(t) {
	var expects = ['hello', 'world'];
	var ws = fwd.writable({objectMode:true}, function(cb) {
		process.nextTick(function() {
			var pt = new PassThrough({objectMode:true});

			pt.on('data', function(data) {
				t.same(data, expects.shift());
			});

			pt.on('end', function() {
				t.same(expects, []);
				t.end();
			});

			cb(null, pt);
		});
	});

	ws.write('hello');
	ws.write('world');
	ws.end();
});

tape('fwd.writable and just end', function(t) {
	var ws = fwd.writable({objectMode:true}, function(cb) {
		process.nextTick(function() {
			var pt = new PassThrough({objectMode:true});

			pt.on('finish', function() {
				t.ok(true);
				t.end();
			});

			cb(null, pt);
		});
	});

	ws.end();
});

tape('fwd.writable binary', function(t) {
	var ws = fwd.writable(function(cb) {
		process.nextTick(function() {
			var pt = new PassThrough({objectMode:true});
			var buf = [];

			pt.on('data', function(data) {
				buf.push(data);
			});

			pt.on('end', function() {
				t.same(Buffer.concat(buf), new Buffer('helloworld'));
				t.end();
			});

			cb(null, pt);
		});
	});

	ws.write('hello');
	ws.write('world');
	ws.end();
});

tape('fwd.duplex', function(t) {
	t.plan(6);

	var dupl = fwd.duplex({objectMode:true},
		function(cb) {
			var expects = ['hello', 'world'];

			process.nextTick(function() {
				var pt = new PassThrough({objectMode:true});

				pt.on('data', function(data) {
					t.same(data, expects.shift());
				});

				pt.on('end', function() {
					t.same(expects, []);
				});

				cb(null, pt);
			});
		},
		function(cb) {
			process.nextTick(function() {
				var pt = new PassThrough({objectMode:true});

				pt.write('guttentag');
				pt.write('welt');
				pt.end();

				cb(null, pt);
			});
		}
	);

	dupl.write('hello');
	dupl.write('world');
	dupl.end();

	var expects = ['guttentag', 'welt'];

	dupl.on('data', function(data) {
		t.same(data, expects.shift());
	});

	dupl.on('end', function() {
		t.same(expects, []);
	});
});
