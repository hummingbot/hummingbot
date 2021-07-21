var test = require('./helpers/test');
var concat = require('concat-stream');

test('createWriteStream', function(fs, t) {
	var ws = fs.createWriteStream('/test.txt');

	ws.write('hello ');
	ws.write('hi ');
	ws.write('ho ');
	ws.write('hey ');
	ws.end('world');

	ws.on('finish', function() {
		fs.readFile('/test.txt', 'utf-8', function(err, buf) {
			t.ok(!err);
			t.same(buf, 'hello hi ho hey world');
			t.end();
		});
	});
});

test('createWriteStream big', function(fs, t) {
	var ws = fs.createWriteStream('/test.txt');
	var big = new Buffer(100 * 1024);

	ws.end(big);

	ws.on('finish', function() {
		fs.readFile('/test.txt', function(err, buf) {
			t.ok(!err);
			t.same(buf, big);
			t.end();
		});
	});
});

test('createWriteStream append', function(fs, t) {
	var ws = fs.createWriteStream('/test.txt');

	ws.write('hello ');
	ws.end('world');

	ws.on('finish', function() {
		var ws = fs.createWriteStream('/test.txt', {flags:'a'});

		ws.write(' hej ');
		ws.end('verden');

		ws.on('finish', function() {

			fs.readFile('/test.txt', 'utf-8', function(err, buf) {
				t.ok(!err);
				t.same(buf, 'hello world hej verden');
				t.end();
			});
		});
	});
});

test('createWriteStream not exists', function(fs, t) {
	var ws = fs.createWriteStream('/test.txt');

	ws.write('hello ');
	ws.end('world');

	ws.on('finish', function() {
		var ws = fs.createWriteStream('/test.txt', {flags:'wx'});

		ws.write(' hej ');
		ws.end('verden');

		ws.on('error', function(err) {
			t.ok(err);
			t.same(err.code, 'EEXIST');
			t.end();
		});
	});
});

test('createWriteStream is dir', function(fs, t) {
	var ws = fs.createWriteStream('/');

	ws.write('hello ');
	ws.end('world');

	ws.on('error', function(err) {
		t.ok(err);
		t.same(err.code, 'EISDIR');
		t.end();
	});
});