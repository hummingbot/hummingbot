const mime = require('mime')
const path = require('path')
const url = require('url')
let fs
try {
  fs = require('graceful-fs')
} catch (e) {
  fs = require('fs')
}
const zlib = require('zlib')
const Neg = require('negotiator')
const http = require('http')
const AC = require('async-cache')
const FD = require('fd')
const bl = require('bl')

const defaultCacheOptions = {
  fd: {
    max: 1000,
    maxAge: 1000 * 60 * 60
  },
  stat: {
    max: 5000,
    maxAge: 1000 * 60
  },
  content: {
    max: 1024 * 1024 * 64,
    length: (n) => n.length,
    maxAge: 1000 * 60 * 10
  },
  index: {
    max: 1024 * 8,
    length: (n) => n.length,
    maxAge: 1000 * 60 * 10
  },
  readdir: {
    max: 1000,
    length: (n) => n.length,
    maxAge: 1000 * 60 * 10
  }
}

// lru-cache doesn't like when max=0, so we just pretend
// everything is really big.  kind of a kludge, but easiest way
// to get it done
const none = {
  max: 1,
  length: () => Infinity
}

const noCaching = {
  fd: none,
  stat: none,
  index: none,
  readdir: none,
  content: none
}

function st (opt) {
  let p, u
  if (typeof opt === 'string') {
    p = opt
    opt = arguments[1]
    if (typeof opt === 'string') {
      u = opt
      opt = arguments[2]
    }
  }

  if (!opt) {
    opt = {}
  } else {
    opt = Object.assign({}, opt)
  }

  if (!p) {
    p = opt.path
  }
  if (typeof p !== 'string') {
    throw new Error('no path specified')
  }
  p = path.resolve(p)
  if (!u) {
    u = opt.url
  }
  if (!u) {
    u = ''
  }
  if (u.charAt(0) !== '/') {
    u = '/' + u
  }

  opt.url = u
  opt.path = p

  const m = new Mount(opt)
  const fn = m.serve.bind(m)
  fn._this = m
  return fn
}

class Mount {
  constructor (opt) {
    if (!opt) {
      throw new Error('no options provided')
    }
    if (typeof opt !== 'object') {
      throw new Error('invalid options')
    }
    if (!(this instanceof Mount)) {
      return new Mount(opt)
    }

    this.opt = opt
    this.url = opt.url
    this.path = opt.path
    this._index = opt.index === false ? false
      : typeof opt.index === 'string' ? opt.index
        : true
    this.fdman = FD()

    // cache basically everything
    const c = this.getCacheOptions(opt)
    this.cache = {
      fd: AC(c.fd),
      stat: AC(c.stat),
      index: AC(c.index),
      readdir: AC(c.readdir),
      content: AC(c.content)
    }

    this._cacheControl =
      c.content.maxAge === false
        ? undefined
        : typeof c.content.cacheControl === 'string'
          ? c.content.cacheControl
          : opt.cache === false
            ? 'no-cache'
            : 'public, max-age=' + (c.content.maxAge / 1000)
  }

  getCacheOptions (opt) {
    let o = opt.cache
    const set = (key) => {
      return o[key] === false
        ? Object.assign({}, none)
        : Object.assign(Object.assign({}, d[key]), o[key])
    }

    if (o === false) {
      o = noCaching
    } else if (!o) {
      o = {}
    }

    const d = defaultCacheOptions

    // should really only ever set max and maxAge here.
    // load and fd disposal is important to control.
    const c = {
      fd: set('fd'),
      stat: set('stat'),
      index: set('index'),
      readdir: set('readdir'),
      content: set('content')
    }

    c.fd.dispose = this.fdman.close.bind(this.fdman)
    c.fd.load = this.fdman.open.bind(this.fdman)

    c.stat.load = this._loadStat.bind(this)
    c.index.load = this._loadIndex.bind(this)
    c.readdir.load = this._loadReaddir.bind(this)
    c.content.load = this._loadContent.bind(this)
    return c
  }

  // get the path component from a URI
  getUriPath (u) {
    let p = url.parse(u).pathname // eslint-disable-line

    // Encoded dots are dots
    p = p.replace(/%2e/ig, '.')

    // encoded slashes are /
    p = p.replace(/%2f|%5c/ig, '/')

    // back slashes are slashes
    p = p.replace(/[/\\]/g, '/')

    // Make sure it starts with a slash
    p = p.replace(/^\//, '/')
    if ((/[/\\]\.\.([/\\]|$)/).test(p)) {
      // traversal urls not ever even slightly allowed. clearly shenanigans
      // send a 403 on that noise, do not pass go, do not collect $200
      return 403
    }

    u = path.normalize(p).replace(/\\/g, '/')
    if (u.indexOf(this.url) !== 0) {
      return false
    }

    try {
      u = decodeURIComponent(u)
    } catch (e) {
      // if decodeURIComponent failed, we weren't given a valid URL to begin with.
      return false
    }

    // /a/b/c mounted on /path/to/z/d/x
    // /a/b/c/d --> /path/to/z/d/x/d
    u = u.substr(this.url.length)
    if (u.charAt(0) !== '/') {
      u = '/' + u
    }

    return u
  }

  // get a path from a url
  getPath (u) {
    return path.join(this.path, u)
  }

  // get a url from a path
  getUrl (p) {
    p = path.resolve(p)
    if (p.indexOf(this.path) !== 0) {
      return false
    }
    p = path.join('/', p.substr(this.path.length))
    const u = path.join(this.url, p).replace(/\\/g, '/')
    return u
  }

  serve (req, res, next) {
    if (req.method !== 'HEAD' && req.method !== 'GET') {
      if (typeof next === 'function') {
        next()
      }
      return false
    }

    // querystrings are of no concern to us
    if (!req.sturl) {
      req.sturl = this.getUriPath(req.url)
    }

    // don't allow dot-urls by default, unless explicitly allowed.
    // If we got a 403, then it's explicitly forbidden.
    if (req.sturl === 403 || (!this.opt.dot && (/(^|\/)\./).test(req.sturl))) {
      res.statusCode = 403
      res.end('Forbidden')
      return true
    }

    // Falsey here means we got some kind of invalid path.
    // Probably urlencoding we couldn't understand, or some
    // other "not compatible with st, but maybe ok" thing.
    if (typeof req.sturl !== 'string' || req.sturl === '') {
      if (typeof next === 'function') {
        next()
      }
      return false
    }

    const p = this.getPath(req.sturl)

    // now we have a path.  check for the fd.
    this.cache.fd.get(p, (er, fd) => {
      // inability to open is some kind of error, probably 404
      // if we're in passthrough, AND got a next function, we can
      // fall through to that.  otherwise, we already returned true,
      // send an error.
      if (er) {
        if (this.opt.passthrough === true && er.code === 'ENOENT' && next) {
          return next()
        }
        return this.error(er, res)
      }

      // we may be about to use this, so don't let it be closed by cache purge
      this.fdman.checkout(p, fd)
      // a safe end() function that can be called multiple times but
      // only perform a single checkin
      const end = this.fdman.checkinfn(p, fd)

      this.cache.stat.get(fd + ':' + p, (er, stat) => {
        if (er) {
          if (next && this.opt.passthrough === true && this._index === false) {
            return next()
          }
          end()
          return this.error(er, res)
        }

        const isDirectory = stat.isDirectory()

        if (isDirectory) {
          end() // we won't need this fd for a directory in any case
          if (next && this.opt.passthrough === true && this._index === false) {
            // this is done before if-modified-since and if-non-match checks so
            // cached modified and etag values won't return 304's if we've since
            // switched to !index. See Issue #51.
            return next()
          }
        }

        let ims = req.headers['if-modified-since']
        if (ims) {
          ims = new Date(ims).getTime()
        }
        if (ims && ims >= stat.mtime.getTime()) {
          res.statusCode = 304
          res.end()
          return end()
        }

        const etag = getEtag(stat)
        if (req.headers['if-none-match'] === etag) {
          res.statusCode = 304
          res.end()
          return end()
        }

        // only set headers once we're sure we'll be serving this request
        if (!res.getHeader('cache-control') && this._cacheControl) {
          res.setHeader('cache-control', this._cacheControl)
        }
        res.setHeader('last-modified', stat.mtime.toUTCString())
        res.setHeader('etag', etag)

        if (this.opt.cors) {
          res.setHeader('Access-Control-Allow-Origin', '*')
          res.setHeader('Access-Control-Allow-Headers',
            'Origin, X-Requested-With, Content-Type, Accept, Range')
        }

        return isDirectory
          ? this.index(p, req, res)
          : this.file(p, fd, stat, etag, req, res, end)
      })
    })

    return true
  }

  error (er, res) {
    res.statusCode = typeof er === 'number' ? er
      : er.code === 'ENOENT' || er.code === 'EISDIR' ? 404
        : er.code === 'EPERM' || er.code === 'EACCES' ? 403
          : 500

    if (typeof res.error === 'function') {
      // pattern of express and ErrorPage
      return res.error(res.statusCode, er)
    }

    res.setHeader('content-type', 'text/plain')
    res.end(http.STATUS_CODES[res.statusCode] + '\n')
  }

  index (p, req, res) {
    if (this._index === true) {
      return this.autoindex(p, req, res)
    }
    if (typeof this._index === 'string') {
      if (!/\/$/.test(req.sturl)) {
        req.sturl += '/'
      }
      req.sturl += this._index
      return this.serve(req, res)
    }
    return this.error(404, res)
  }

  autoindex (p, req, res) {
    if (!/\/$/.exec(req.sturl)) {
      res.statusCode = 301
      res.setHeader('location', req.sturl + '/')
      res.end('Moved: ' + req.sturl + '/')
      return
    }

    this.cache.index.get(p, (er, html) => {
      if (er) {
        return this.error(er, res)
      }

      res.statusCode = 200
      res.setHeader('content-type', 'text/html')
      res.setHeader('content-length', html.length)
      res.end(html)
    })
  }

  file (p, fd, stat, etag, req, res, end) {
    const key = stat.size + ':' + etag

    const mt = mime.getType(path.extname(p))
    if (mt !== 'application/octet-stream') {
      res.setHeader('content-type', mt)
    }

    // only use the content cache if it will actually fit there.
    if (this.cache.content.has(key)) {
      end()
      this.cachedFile(p, stat, etag, req, res)
    } else {
      this.streamFile(p, fd, stat, etag, req, res, end)
    }
  }

  cachedFile (p, stat, etag, req, res) {
    const key = stat.size + ':' + etag
    const gz = this.opt.gzip !== false && getGz(p, req)

    this.cache.content.get(key, (er, content) => {
      if (er) {
        return this.error(er, res)
      }
      res.statusCode = 200
      if (this.opt.cachedHeader) {
        res.setHeader('x-from-cache', 'true')
      }
      if (gz && content.gz) {
        res.setHeader('content-encoding', 'gzip')
        res.setHeader('content-length', content.gz.length)
        res.end(content.gz)
      } else {
        res.setHeader('content-length', content.length)
        res.end(content)
      }
    })
  }

  streamFile (p, fd, stat, etag, req, res, end) {
    const streamOpt = { fd: fd, start: 0, end: stat.size }
    let stream = fs.createReadStream(p, streamOpt)
    stream.destroy = () => {}

    // gzip only if not explicitly turned off or client doesn't accept it
    const gzOpt = this.opt.gzip !== false
    const gz = gzOpt && getGz(p, req)
    const cachable = this.cache.content._cache.max > stat.size
    let gzstr

    // need a gzipped version for the cache, so do it regardless of what the client wants
    if (gz || (gzOpt && cachable)) {
      gzstr = zlib.Gzip()
    }

    // too late to effectively handle any errors.
    // just kill the connection if that happens.
    stream.on('error', (e) => {
      console.error('Error serving %s fd=%d\n%s', p, fd, e.stack || e.message)
      res.socket.destroy()
      end()
    })

    if (res.filter) {
      stream = stream.pipe(res.filter)
    }

    res.statusCode = 200

    if (gz) {
      // we don't know how long it'll be, since it will be compressed.
      res.setHeader('content-encoding', 'gzip')
      stream.pipe(gzstr).pipe(res)
    } else {
      if (!res.filter) {
        res.setHeader('content-length', stat.size)
      }
      stream.pipe(res)
      if (gzstr) {
        stream.pipe(gzstr)
      } // for cache
    }

    stream.on('end', () => process.nextTick(end))

    if (cachable) {
      // collect it, and put it in the cache

      let calls = 0

      // called by bl() for both the raw stream and gzipped stream if we're
      // caching gzipped data
      const collectEnd = () => {
        if (++calls === (gzOpt ? 2 : 1)) {
          const content = bufs.slice()
          content.gz = gzbufs && gzbufs.slice()
          this.cache.content.set(key, content)
        }
      }

      const key = stat.size + ':' + etag
      const bufs = bl(collectEnd)
      let gzbufs

      stream.pipe(bufs)

      if (gzstr) {
        gzbufs = bl(collectEnd)
        gzstr.pipe(gzbufs)
      }
    }
  }

  // cache-fillers

  _loadIndex (p, cb) {
    // truncate off the first bits
    const url = p.substr(this.path.length).replace(/\\/g, '/')
    const t = url
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/'/g, '&#39;')

    let str =
      '<!doctype html>' +
      '<html>' +
      '<head><title>Index of ' + t + '</title></head>' +
      '<body>' +
      '<h1>Index of ' + t + '</h1>' +
      '<hr><pre><a href="../">../</a>\n'

    this.cache.readdir.get(p, (er, data) => {
      if (er) {
        return cb(er)
      }

      let nameLen = 0
      let sizeLen = 0

      Object.keys(data).map((f) => {
        const d = data[f]

        let name = f
          .replace(/"/g, '&quot;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/'/g, '&#39;')

        if (d.size === '-') {
          name += '/'
        }
        const showName = name.replace(/^(.{40}).{3,}$/, '$1..>')
        const linkName = encodeURIComponent(name)
          .replace(/%2e/ig, '.') // Encoded dots are dots
          .replace(/%2f|%5c/ig, '/') // encoded slashes are /
          .replace(/[/\\]/g, '/') // back slashes are slashes

        nameLen = Math.max(nameLen, showName.length)
        sizeLen = Math.max(sizeLen, ('' + d.size).length)
        return ['<a href="' + linkName + '">' + showName + '</a>',
          d.mtime, d.size, showName]
      }).sort((a, b) => {
        return a[2] === '-' && b[2] !== '-' ? -1 // dirs first
          : a[2] !== '-' && b[2] === '-' ? 1
            : a[0].toLowerCase() < b[0].toLowerCase() ? -1 // then alpha
              : a[0].toLowerCase() > b[0].toLowerCase() ? 1
                : 0
      }).forEach((line) => {
        const namePad = new Array(8 + nameLen - line[3].length).join(' ')
        const sizePad = new Array(8 + sizeLen - ('' + line[2]).length).join(' ')
        str += line[0] + namePad +
              line[1].toISOString() +
              sizePad + line[2] + '\n'
      })

      str += '</pre><hr></body></html>'
      cb(null, Buffer.from(str))
    })
  }

  _loadReaddir (p, cb) {
    let len
    let data
    fs.readdir(p, (er, files) => {
      if (er) {
        return cb(er)
      }
      files = files.filter((f) => {
        if (!this.opt.dot) {
          return !/^\./.test(f)
        } else {
          return f !== '.' && f !== '..'
        }
      })
      len = files.length
      data = {}
      files.forEach((file) => {
        const pf = path.join(p, file)
        this.cache.stat.get(pf, (er, stat) => {
          if (er) {
            return cb(er)
          }
          if (stat.isDirectory()) {
            stat.size = '-'
          }
          data[file] = stat
          next()
        })
      })
    })

    const next = () => {
      if (--len === 0) {
        cb(null, data)
      }
    }
  }

  _loadStat (key, cb) {
    // key is either fd:path or just a path
    const fdp = key.match(/^(\d+):(.*)/)
    if (fdp) {
      const fd = +fdp[1]
      const p = fdp[2]
      fs.fstat(fd, (er, stat) => {
        if (er) {
          return cb(er)
        }
        this.cache.stat.set(p, stat)
        cb(null, stat)
      })
    } else {
      fs.stat(key, cb)
    }
  }

  _loadContent () {
    // this function should never be called.
    // we check if the thing is in the cache, and if not, stream it in
    // manually.  this.cache.content.get() should not ever happen.
    throw new Error('This should not ever happen')
  }
}

function getEtag (s) {
  return '"' + s.dev + '-' + s.ino + '-' + s.mtime.getTime() + '"'
}

function getGz (p, req) {
  let gz = false
  if (!/\.t?gz$/.exec(p)) {
    const neg = req.negotiator || new Neg(req)
    gz = neg.preferredEncoding(['gzip', 'identity']) === 'gzip'
  }
  return gz
}

module.exports = st
module.exports.Mount = Mount
