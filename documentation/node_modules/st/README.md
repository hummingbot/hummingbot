# st

[![Travis Status](https://api.travis-ci.org/isaacs/st.svg?branch=master)](https://travis-ci.org/isaacs/st)

A module for serving static files.  Does etags, caching, etc.

## USAGE

Here are some very simple usage examples.

Just serve the files in the cwd at the root of the http server url:

```javascript
const st = require('st')
const http = require('http')

http.createServer(
  st(process.cwd())
).listen(1337)
```


Serve the files in static under the /static url.  Otherwise do a
different thing:

```javascript
const path = require('path')
const mount = st({ path: path.join(__dirname, '/static'), url: '/static' })

http.createServer((req, res) => {
  const stHandled = mount(req, res)
  if (stHandled)
    return
  else
    res.end('this is not a static file')
}).listen(1338)
```

The same sort of thing, but using an express middleware style:

```javascript
const path = require('path')
const mount = st({ path: path.join(__dirname, '/static'), url: '/static' })

http.createServer((req, res) => {
  mount(req, res, () => res.end('this is not a static file'))
}).listen(1339)
```


Serve the files in static under the / url, but only if not some doing
other thing:

```javascript
const path = require('path')
const mount = st({ path: path.join(__dirname, '/static'), url: '/' })

http.createServer((req, res) => {
  if (shouldDoThing(req)) {
    doTheThing(req, res)
  } else {
    mount(req, res)
  }
}).listen(1340)
```

Serve the files in static under the / url, but don't serve a 404 if
the file isn't found, so that the rest of the app can handle it:

```javascript
const path = require('path')
const mount = st({ path: path.join(__dirname, '/static'), url: '/', passthrough: true})

http.createServer((req, res) => {
  mount(req, res, () => res.end('this is not a static file'))
}).listen(1341)
```

Serve the files with
[CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Access_control_CORS)
enabled, to serve static files to any domain:

```javascript
http.createServer(
  st({
   path: process.cwd(),
   cors: true
  })
).listen(1337)
```


Pass some options to the `st` function, and it returns a handler
function.

That handler function will return `true` if it handles the static
request, or `false` if it doesn't.  (This is so that you can only
serve static files if they're in `/static` for example.)

Here are some options if you want to configure stuff.  All of these
are optional except `path` which tells it where to get stuff from.

If you pass a string instead of an object, then it'll use the string
as the path.

If you don't specify a `url`, then it'll mount on the `'/'` url, so
`st({ path: './static/' })` will try to serve `./static/foo.html` when
the user goes to `http://example.com/foo.html`.  (Note: This behavior
changed in st 0.2.0.)

Here are all the options described with their defaults values and a
few possible settings you might choose to use:

```javascript
const st = require('st')
const mount = st({
  path: 'resources/static/', // resolved against the process cwd
  url: 'static/', // defaults to '/'

  cache: { // specify cache:false to turn off caching entirely
    fd: {
      max: 1000, // number of fd's to hang on to
      maxAge: 1000*60*60, // amount of ms before fd's expire
    },

    stat: {
      max: 5000, // number of stat objects to hang on to
      maxAge: 1000 * 60, // number of ms that stats are good for
    },

    content: {
      max: 1024*1024*64, // how much memory to use on caching contents
      maxAge: 1000 * 60 * 10, // how long to cache contents for
                              // if `false` does not set cache control headers
      cacheControl: 'public, max-age=600' // to set an explicit cache-control
                                          // header value
    },

    index: { // irrelevant if not using index:true
      max: 1024 * 8, // how many bytes of autoindex html to cache
      maxAge: 1000 * 60 * 10, // how long to store it for
    },

    readdir: { // irrelevant if not using index:true
      max: 1000, // how many dir entries to cache
      maxAge: 1000 * 60 * 10, // how long to cache them for
    }
  },

  // indexing options
  index: true, // auto-index, the default
  index: 'index.html', // use 'index.html' file as the index
  index: false, // return 404's for directories

  dot: false, // default: return 403 for any url with a dot-file part
  dot: true, // allow dot-files to be fetched normally

  passthrough: true, // calls next/returns instead of returning a 404 error
  passthrough: false, // returns a 404 when a file or an index is not found

  gzip: true, // default: compresses the response with gzip compression
  gzip: false, // does not compress the response, even if client accepts gzip

  cors: false, // default: static assets not accessible from other domains
  cors: true, // static assets can be accessed from any domain
})

// with bare node.js
http.createServer((req, res) => {
  if (mount(req, res)) return // serving a static file
  myCustomLogic(req, res)
}).listen(PORT)

// with express
app.use(mount)
// or
app.route('/static/:fooblz', (req, res, next) => {
  mount(req, res, next) // will call next() if it doesn't do anything
})
```

On the command line:

```
$ st -h
st
Static file server in node

Options:

-h --help             Show this help

-p --port PORT        Listen on PORT (default=1337)

-H --host HOST        Bind address HOST (default=*)

-l --localhost        Same as "--host localhost"

-d --dir DIRECTORY    Serve the contents of DIRECTORY (default=cwd)

-u --url MOUNTURL     Serve the contents at MOUNTURL mount path (default=/)

-i --index [INDEX]    Use the specified INDEX filename as the result
                      when a directory is requested.  Set to "true"
                      to turn autoindexing on, or "false" to turn it
                      off.  If no INDEX is provided, then it will turn
                      autoindexing on.  (default=true)

-ni --no-index        Same as "--index false"

-. --dot [DOT]        Allow .files to be served.  Set to "false" to
                      disable.

-n. --no-dot          Same as "--dot false"

-co --cors            Enable CORS to serve files to any domain.

-nc --no-cache        Turn off all caching.

-a --age AGE          Max age (in ms) of cache entries.
```

## Range Requests

Range requests are not supported.

I'd love a patch to add support for them, but the spec is kind of
confusing, and it's not always a clear win if you're not serving very
large files, so it should come with some very comprehensive tests.

Thankfully, as far as I can tell, it's always safe to serve the entire
file to a request with a range header, so st does behave correctly, if
not ideally in those situations.  It'd be great to be able to do the
better thing if the contents are cached, but still serve the full file
if it's not in cache (so that it can be cached for subsequent
requests).

## Memory Caching

To make things go as fast as possible, it is a good idea to set the
cache limits as high as you can afford, given the amount of memory on
your server.  Serving buffers out of process memory will generally
always be faster than hitting the file system.

## Client Caching

An etag header and last-modified will be attached to every request.
If presented with an `if-none-match` or `if-modified-since`, then
it'll return a 304 in the appropriate conditions.

The etag is generated based on the dev, ino, and last modified date.
Stat results are cached.

## Compression

If the request header claims to enjoy gzip encoding, and the filename
does not end in '.gz' or '.tgz', then the response will be gzipped.

Gzipped bytes are not included in the calculation of cache sizes, so
this utility will use a bit more memory than the cache.content.max and
cache.index.max bytes would seem to allow.  This will be less than
double, and usually insignificant for normal web assets, but is
important to consider if memory is at a premium.

Gzip compression can be disabled by setting `gzip: false` on the options passed
into `st()`. This is useful if your application already handles gzipping
responses by other means.

## Filtering Output

If you want to do some fancy stuff to the file before sending it, you
can attach a `res.filter = myFilterStream` thing to the response
object before passing it to the mount function.

This is useful if you want to get the benefits of caching and gzipping
and such, but serve stylus files as css, for example.

## Security Status

Versions prior to 0.2.5 did not properly prevent folder traversal.
Literal dots in a path were resolved out, but url encoded dots were
not.  Thus, a request like
`/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/etc/passwd` would leak sensitive
data from the server.

As of version 0.2.5, any `'/../'` in the request path, urlencoded or
not, will be replaced with `'/'`.  If your application depends on url
traversal, then you are encouraged to please refactor so that you do
not depend on having `..` in url paths, as this tends to expose data
that you may be surprised to be exposing.

Consider using the `--localhost` setting if you don't want other
people on your local network to read the files served by the command
line server.  This may become the default in a future major version.
