var tap        = require('tap')
  , sinon      = require('sinon')
  , fs         = require('fs')
  , path       = require('path')
  , mkfiletree = require('mkfiletree')
  , FDManager  = require('./')

tap.test('open / close', function (t) {
  var fsMock = sinon.mock(fs)
    , fdman  = FDManager()

  fsMock.expects('open').once().withArgs('/foo/bar/baz.txt', 'r').callsArgWith(2, null, 101)
  fsMock.expects('close').once().withArgs(101)

  fdman.open('/foo/bar/baz.txt', function (err, fd) {
    t.notOk(err)
    t.equal(fd, 101)
    fdman.close('/foo/bar/baz.txt', 101)
    process.nextTick(function () {
      fsMock.verify()
      t.equal(0, FDManager._totalOpenFds)
      t.end()
    })
  })
})

tap.test('open / checkout / close', function (t) {
  var fsMock = sinon.mock(fs)
    , fdman  = FDManager()
    , closeSpy

  fsMock.expects('open').once().withArgs('/foo/bar/baz.txt', 'r').callsArgWith(2, null, 101)
  closeSpy = fsMock.expects('close').once().withArgs(101)

  // open a file
  fdman.open('/foo/bar/baz.txt', function (err, fd) {
    t.notOk(err)
    t.equal(fd, 101)

    // check it out
    fdman.checkout('/foo/bar/baz.txt', 101)

    // close it
    fdman.close('/foo/bar/baz.txt', fd)

    process.nextTick(function () {
      // file should NOT be closed
      t.equal(closeSpy.callCount, 0)

      // check it in
      fdman.checkin('/foo/bar/baz.txt', 101)
      process.nextTick(function () {
        // file should now be closed
        fsMock.verify()
        t.equal(0, FDManager._totalOpenFds)
        t.end()
      })
    })
  })
})

tap.test('open / checkout / close with checkinfn', function (t) {
  var fsMock = sinon.mock(fs)
    , fdman  = FDManager()
    , closeSpy

  fsMock.expects('open').once().withArgs('/foo/bar/baz.txt', 'r').callsArgWith(2, null, 101)
  closeSpy = fsMock.expects('close').once().withArgs(101)

  // open a file
  fdman.open('/foo/bar/baz.txt', function (err, fd) {
    t.notOk(err)
    t.equal(fd, 101)

    // check it out
    fdman.checkout('/foo/bar/baz.txt', 101)
    var checkin = fdman.checkinfn('/foo/bar/baz.txt', 101)

    // close it
    fdman.close('/foo/bar/baz.txt', fd)

    process.nextTick(function () {
      // file should NOT be closed
      t.equal(closeSpy.callCount, 0)

      // check it in
      checkin('/foo/bar/baz.txt', 101)
      process.nextTick(function () {
        // file should now be closed
        fsMock.verify()
        t.equal(0, FDManager._totalOpenFds)
        t.end()
      })
    })
  })
})

tap.test('many open files', function (t) {
  var filetree = {}
    , fdman    = FDManager()
    , i        = 200
    , maxopen  = 0
    , tasks    = 0
    , end      = function () {
        process.nextTick(function () {
          // after all that, we shouldn't have anything left open
          t.equal(0, FDManager._totalOpenFds)
          console.error('Max open fds: ' + maxopen)
          mkfiletree.cleanUp(t.end.bind(t))
        })
      }
      // a simple async tasks queue, once we start putting jobs into this
      // we watch them complete and when tasks in = tasks complete then
      // end()
    , async    = function (task) {
        tasks++
        process.nextTick(task.bind(null, function (err) {
          // watch the fd-open count
          if (FDManager._totalOpenFds > maxopen) maxopen = FDManager._totalOpenFds
          t.notOk(err)
          if (--tasks === 0)
            end()
        }))
      }

  // make a big directory full of guff
  while (i--)
    filetree['derp' + i] = 'DERPTASTIC! ' + i

  // HAHAHAHAHAHAHAHAHAHAHAHAH!
  // good luck figuring this out buddy
  // it made sense when it was coming out of my fingers at least
  mkfiletree.makeTemp('fd', filetree, function (err, dir) {

    // called for each of the 200 files
    function runner (i) {
      var f = path.join(dir, 'derp' + i)
      return function (callback) {
        setTimeout(function () { // stagger opens
          // open the file
          fdman.open(f, function (err, fd) {
            t.equal(err, null, 'no err')
            t.ok(fd > 0, 'fd > 0 [' + fd + ']: ' + f)
            // for each file, do this next stuff up to `i` times
            for (var j = 0; j < i; j++) {
              (function (j) {
                async(function (callback) {
                  setTimeout(function () {
                    // checkout the file, `j` ms later
                    fdman.checkout(f, fd)
                    if (j === i - 1) {
                      // on the last checkout, read from the fd to make sure it's
                      // what we expect
                      var buf = new Buffer(20)
                      fs.read(fd, buf, 0, 20, 0, function (err, len) {
                        t.notOk(err)
                        t.equal(buf.toString('utf8', 0, len), 'DERPTASTIC! ' + i)
                        // console.error('READ',i,buf.toString('utf8', 0, len))
                        callback()
                      })
                    } else
                      callback()
                  }, j)

                  async(function (callback) {
                    setTimeout(function () {
                      // a matching checkin for each checkout, delayed from the
                      // checkin by up to 10ms
                      // (this could be moved up into the checkout block to make sure
                      // the read doesn't cause problems)
                      fdman.checkin(f, fd)
                      callback()
                    }, j + (Math.random() * 10))
                  })
                })
              }(j))
            }

            async(function (callback) {
              setTimeout(function () {
                // close the file at some point after we've opened it, by this
                // time there will be checkouts in process so it shouldn't be
                // closeable
                fdman.close(f, fd)
                callback()
              }, Math.floor(10 + Math.random() * i))
            })
            callback()
          })
        }, i)
      }
    }

    console.error('DIR',dir)
    t.notOk(err, 'no err')

    for (i = 0; i < 200; i++)
      async(runner(i))
  })
})