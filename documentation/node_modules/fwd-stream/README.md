# fwd-stream

Forward a readable stream to another readable stream or a writable stream to another writable stream.
Featuring streams2 support and async instantiating.

	npm install fwd-stream

[![build status](https://secure.travis-ci.org/mafintosh/fwd-stream.png)](http://travis-ci.org/mafintosh/fwd-stream)

## When should I use this?

This module makes it easy to return a stream synchroniously that wraps another stream from an async context.
Say for example you wanted to create a folder before writing a write you could do

``` js
var fs = require('fs');
var fwd = require('fwd-stream');

var ws = fwd.writable(function(cb) {
	fs.mkdir('my-folder', function() {
		cb(null, fs.createWriteStream('my-folder/my-file.txt'));
	});
});

ws.write('content of my-file.txt');
```

## Usage

Forward readable streams

``` js
var fwd = require('fwd-stream');

// rs will be a stream that forwards someReadableStream's data and events
// backpressure etc will still be respected

var rs = fwd.readable(someReadableStream);

// or using async instantiating

var rs = fwd.readable(function(cb) {
	setTimeout(function() {
		cb(null, someReadableStream);
	}, 1000);
});

// or using objectMode

var rs = fwd.readable({objectMode:true}, someReadableObjectStream);
```

Forward writable streams

``` js
var ws = fwd.writable(someWritableStream);

// or using async instantiating

var ws = fwd.writable(function(cb) {
	setTimeout(function() {
		cb(null, ws);
	}, 1000);
});

// or using objectMode

var ws = fwd.writable({objectMode:true}, someWritableObjectStream);
```

Forward duplex streams

``` js
var dupl = fwd.duplex(someWritableStream, someReadableStream);

// or using async instantiating

var dupl = fwd.duplex(
	function(cb) {
		setTimeout(function() {
			cb(null, someWritableStream);
		}, 1000);
	},
	function(cb) {
		setTimeout(function() {
			cb(null, someReadableStream);
		}, 1000);
	}
);

// or using objectMode

var dupl = fwd.duplex({objectMode:true}, someReadableObjStream, someWritableObjStream);
```

## License

MIT