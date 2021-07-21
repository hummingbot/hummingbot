# fd [![Build Status](https://secure.travis-ci.org/rvagg/node-fd.png)](http://travis-ci.org/rvagg/node-fd)

File descriptor manager for Node.js. *Available in npm as <strong>fd</strong>*.

**fd** manages `fs.open()` and `fs.close()` calls safely for you where there may be timing issues related to multiple-use of the same descriptor.

**fd** provides `checkin()` and `checkout()` functions so your application can register its intent to use a file descriptor after it's been opened and then register that it has finished with the descriptor so that any pending `fs.close()` operations may be performed.

**fd** naturally couples with [async-cache](https://github.com/isaacs/async-cache) to provide a safe pool of file descriptors.

## Example

Lets make a static resource web server! This example can be found in the *example/* directory of this repository.

We use [async-cache](https://github.com/isaacs/async-cache) to cache both `fs.sync()` calls and `fd`s, but we hook it up to **fd** so we can safely manage opens and closes.

```js
const fdman = require('fd')()
    , http  = require('http')
    , fs    = require('fs')
    , path  = require('path')
    , AC    = require('async-cache')
    , mime  = require('mime')

    , ROOT  = path.join(__dirname, 'public')

      // an async cache for fs.stat calls, fresh for 10s
    , statCache = AC({
          max    : 100
        , maxAge : 10000
        , load   : function (path, callback) {
                     fs.stat(path, callback)
                   }
      })

      // an async cache for fds, fresh for 10s
    , fdCache = AC({
          max     : 100
        , maxAge  : 10000
          // use fdman to open & close
        , load    : fdman.open.bind(fdman)
        , dispose : fdman.close.bind(fdman)
      })

    , serveError = function (res) {
        res.statusCode = 404
        res.setHeader('content-type', 'text/plain')
        res.end(http.STATUS_CODES[res.statusCode] + '\n')
      }

http.createServer(function (req, res) {
  var p = path.join(ROOT, req.url)

  // get a fs.stat for this file
  statCache.get(p, function (err, stat) {
    if (err || !stat.isFile())
      return serveError(res)

    // get an fd for this file
    fdCache.get(p, function (err, fd) {
      var mimeType = mime.lookup(path.extname(p))
          // get a safe checkin function from fdman that
          // we could safely all multiple times for this single
          // checkout
        , checkin = fdman.checkinfn(p, fd)

      // check out the fd for use
      fdman.checkout(p, fd)

      res.setHeader(
          'content-type'
          // don't force download, just show it
        , mimeType != 'application/octet-stream' ? mimeType : 'text/plain'
      )

      // stream from the fd to the response
      var st = fs.createReadStream(p, { fd: fd, start: 0, end: stat.size })n
        .on('end', checkin)
        .on('error', checkin)

      // override destroy so we don't close the fd
      st.destroy = function () {}

      st.pipe(res)

    })
  })
}).listen(8080)
```

## API

### fd()
Create a new instance of **fd**. Typically called with `var fdman = require('fd')()`. You can have multiple, separate instances of **fd** operating at the same time, hence the need to instantiate.

### fdman.open(path, callback)
Equivalent to `fs.open(path, callback)`, you'll get back an `err` and `fd` parameters but the descriptor will go into the managed pool.

### fdman.close(path, fd)
Will call `fs.close(fd)` *only when the `fd` is no longer in use*. i.e. it will wait till all current uses have been checked in (see below).

### fdman.checkout(path, fd)
Called when your application may need to use the `fd`. This should be called as early as possible, even if your application may not end up using it.

It is important to perform a `checkout()` as soon as you have a reference to the file descriptor if you may be using it, otherwise an asynchronous call may interrupt and call `close()` before you use it. You *don't have to use the `fd`* to register your intent to use it, as long as you eventually call `checkin()`.

### fdman.checkin(path, fd)
Register with **fd** that you have finished using the descriptor and it can be safely closed if need be.

The descriptor may not need to be closed or there may be other uses of the descriptor currently checked out so a `checkin()` won't automatically lead to a `close()`.

### fdman.checkinfn(path, fd)
Returns a function that, when called, will safely perform a `checkin()` for you on the given path and descriptor. An important property of the function is that it will only perform a single `checkin()` regardless of how many times it is called.

This returned function is helpful for calling `checkin()` from multiple points in your application, such as in case of error, and you don't need to worry about whether it's been previously called for the current `checkout()`.

See the example above how this can be used.


## Licence

fd is Copyright (c) 2012 Rod Vagg [@rvagg](https://twitter.com/rvagg) and licenced under the MIT licence. All rights not explicitly granted in the MIT license are reserved. See the included LICENSE file for more details.