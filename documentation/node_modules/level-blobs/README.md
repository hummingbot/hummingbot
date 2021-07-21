# level-blobs

Save binary blobs in level and stream then back.
Similar to [level-store](https://github.com/juliangruber/level-store) but streams2 and with support for random access writes and reads

	npm install level-blobs

[![build status](http://img.shields.io/travis/mafintosh/level-filesystem.svg?style=flat)](http://travis-ci.org/mafintosh/level-blobs)
![dat](http://img.shields.io/badge/Development%20sponsored%20by-dat-green.svg?style=flat)

[![browser support](https://ci.testling.com/mafintosh/level-blobs.png)](https://ci.testling.com/mafintosh/level-blobs)

## Usage

``` js
var blobs = require('level-blobs');
var level = require('level');

var db = level('/tmp/my-blobs-db');
var bl = blobs(db);

// create a write stream
var ws = blobs.createWriteStream('my-file.txt');

ws.on('finish', function() {
	// lets read the blob and pipe it to stdout
	var rs = blobs.createReadStream('my-file.txt');
	rs.pipe(process.stdout);
});

ws.write('hello ');
ws.write('world');
ws.end();
```

## API

#### `blobs(db, opts)`

Create a new blobs instance. Options default to

``` js
{
	blockSize: 65536, // byte size for each block of data stored
	batch: 100        // batch at max 100 blocks when writing
}
```

#### `bl.createReadStream(name, opts)`

Create a read stream for `name`. Options default to

``` js
{
	start: 0       // start reading from this byte offset
	end: Infinity  // end at end-of-file or this offset (inclusive)
}
```

#### `bl.createWriteStream(name, opts)`

Create a write stream to `name`. Options default to

``` js
{
	start: 0       // start writing at this offset
	               // if append === true start defaults to end-of-file
	append: false  // set to true if you want to append to the file
	               // if not true the file will be truncated before writing
}
```

#### `bl.read(name, opts, cb)`

Create a read stream and buffer the stream into a single buffer that is passed to the callback.
Options are passed to `createReadStream`.

#### `bl.write(name, data, opts, cb)`

Write `data` to `name` and call the callback when done.
Options are passed to `createWriteStream`.

#### `bl.remove(name, cb)`

Remove `name` from the blob store

## License

MIT
