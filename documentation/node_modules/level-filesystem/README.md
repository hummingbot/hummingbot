# level-filesystem

Full implementation of the fs module on top of leveldb (except sync ops)

	npm install level-filesystem

[![build status](http://img.shields.io/travis/mafintosh/level-filesystem.svg?style=flat)](http://travis-ci.org/mafintosh/level-filesystem)
![dat](http://img.shields.io/badge/Development%20sponsored%20by-dat-green.svg?style=flat)


[![browser support](https://ci.testling.com/mafintosh/level-filesystem.png)
](https://ci.testling.com/mafintosh/level-filesystem)

## Current status

All async methods in the fs module are supported and well tested (including links!)

```
✓ fs.rmdir(path, callback)
✓ fs.mkdir(path, [mode], callback)
✓ fs.readdir(path, callback)
✓ fs.stat(path, callback)
✓ fs.exists(path, callback)
✓ fs.chmod(path, mode, callback)
✓ fs.chown(path, uid, gid, callback)
✓ fs.rename(oldPath, newPath, callback)
✓ fs.realpath(path, [cache], callback)
✓ fs.readFile(filename, [options], callback)
✓ fs.writeFile(filename, data, [options], callback)
✓ fs.appendFile(filename, data, [options], callback)
✓ fs.utimes(path, atime, mtime, callback)
✓ fs.unlink(path, callback)
✓ fs.createReadStream(path, [options])
✓ fs.createWriteStream(path, [options])
✓ fs.truncate(path, len, callback)
✓ fs.watchFile(filename, [options], listener)
✓ fs.unwatchFile(filename, [listener])
✓ fs.watch(filename, [options], [listener])
✓ fs.fsync(fd, callback)
✓ fs.write(fd, buffer, offset, length, position, callback)
✓ fs.read(fd, buffer, offset, length, position, callback)
✓ fs.close(fd, callback)
✓ fs.open(path, flags, [mode], callback)
✓ fs.futimes(fd, atime, mtime, callback)
✓ fs.fchown(fd, uid, gid, callback)
✓ fs.ftruncate(fd, len, callback)
✓ fs.fchmod(fd, mode, callback)
✓ fs.fstat(fd, callback)
✓ fs.lchown(path, uid, gid, callback)
✓ fs.lchmod(path, mode, callback)
✓ fs.symlink(srcpath, dstpath, [type], callback)
✓ fs.lstat(path, callback)
✓ fs.readlink(path, callback)
✓ fs.link(srcpath, dstpath, callback)
```

If any of the methods do not behave as you would expect please add a test case or open an issue.

## Usage

``` js
var filesystem = require('level-filesystem');
var fs = filesystem(db); // where db is a levelup instance

// use fs as you would node cores fs module

fs.mkdir('/hello', function(err) {
	if (err) throw err;
	fs.writeFile('/hello/world.txt', 'world', function(err) {
		if (err) throw err;
		fs.readFile('/hello/world.txt', 'utf-8', function(err, data) {
			console.log(data);
		});
	});
});
```

## Errors

When you get an error in a callback it is similar to what you get in Node core fs.

``` js
fs.mkdir('/hello', function() {
	fs.mkdir('/hello', function(err) {
		console.log(err); // err.code is EEXIST
	});
});

fs.mkdir('/hello', function() {
	fs.readFile('/hello', function(err) {
		console.log(err); // err.code is EISDIR
	});
});

...
```

## Relation to level-fs

The goal of this module is similar to [level-fs](https://github.com/juliangruber/level-fs) and is probably gonna end up as a PR to that module.
I decided to make this as a standalone module (for now) since adding proper directory support to [level-fs](https://github.com/juliangruber/level-fs)
turned out to be non-trivial (more or a less a complete rewrite).


## License

MIT
