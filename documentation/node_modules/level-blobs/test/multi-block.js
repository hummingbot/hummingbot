var tape = require('tape');
var levelup = require('levelup');
var memdown = require('memdown');

var blobs = function() {
	return require('../')(levelup('mem', {db:memdown}));
};

var allocer = function() {
	var i = 0;
	return function() {
		var buf = new Buffer(50000);
		buf.fill(i++);
		return buf;
	};
};

tape('write + read', function(t) {
	var bl = blobs();

	var output = [];
	var alloc = allocer();
	var ws = bl.createWriteStream('test');

	ws.on('finish', function() {
		var rs = bl.createReadStream('test');
		var input = [];

		rs.on('data', function(data) {
			input.push(data);
		});
		rs.on('end', function() {
			t.same(Buffer.concat(input), Buffer.concat(output));
			t.end();
		});
	});

	for (var i = 0; i < 25; i++) {
		var b = alloc();
		output.push(b);
		ws.write(b);
	}
	ws.end();
});

tape('random access', function(t) {
	var bl = blobs();

	var output = [];
	var alloc = allocer();
	var ws = bl.createWriteStream('test');

	ws.on('finish', function() {
		var rs = bl.createReadStream('test', {start:77777});
		var input = [];

		rs.on('data', function(data) {
			input.push(data);
		});
		rs.on('end', function() {
			t.same(Buffer.concat(input).length, Buffer.concat(output).slice(77777).length);
			t.same(Buffer.concat(input), Buffer.concat(output).slice(77777));
			t.end();
		});
	});

	for (var i = 0; i < 3; i++) {
		var b = alloc();
		output.push(b);
		ws.write(b);
	}
	ws.end();
});

tape('append', function(t) {
	var bl = blobs();

	var output = [];
	var alloc = allocer();
	var ws = bl.createWriteStream('test');

	ws.on('finish', function() {
		ws = bl.createWriteStream('test', {append:true});

		ws.on('finish', function() {
			var rs = bl.createReadStream('test');
			var input = [];

			rs.on('data', function(data) {
				input.push(data);
			});
			rs.on('end', function() {
				t.same(Buffer.concat(input).length, Buffer.concat(output).length);
				t.same(Buffer.concat(input).toString('hex'), Buffer.concat(output).toString('hex'));
				t.end();
			});
		});

		for (var i = 0; i < 3; i++) {
			var b = alloc();
			output.push(b);
			ws.write(b);
		}

		ws.end();
	});

	for (var i = 0; i < 3; i++) {
		var b = alloc();
		output.push(b);
		ws.write(b);
	}
	ws.end();
});
