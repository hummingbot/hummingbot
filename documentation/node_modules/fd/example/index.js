// run `npm install` in the current directory to install
// the required dependencies for this example.
// also change `ROOT` if you want to serve a location other
// than the root of this repo

const fdman = require('../')()
    , http  = require('http')
    , fs    = require('fs')
    , path  = require('path')
    , AC    = require('async-cache')
    , mime  = require('mime')

    , ROOT  = path.join(__dirname, '..')

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
      var st = fs.createReadStream(p, { fd: fd, start: 0, end: stat.size })
        .on('end', checkin)
        .on('error', checkin)

      // override destroy so we don't close the fd
      st.destroy = function () {}

      st.pipe(res)

    })
  })
}).listen(8080)