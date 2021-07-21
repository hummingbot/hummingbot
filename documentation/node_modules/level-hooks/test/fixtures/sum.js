
var levelup = require('levelup')
var rimraf  = require('rimraf')
var pad     = require('pad')

function genSum (path, cb) {
  rimraf(path, function () {
    levelup(path, {createIfMissing: true}, function (err, db) {

      //install plugin system
      require('../../use')(db)

      var l = 1e3, i = 0
      var stream = db.writeStream()
      while(l--)
        stream.write({key: pad(6, ''+ ++i, '0'), value: JSON.stringify(i)})
      stream.end()
      if(cb) stream.on('close', function () {
        cb(null, db)
      })
    })
  })
}

if(!module.parent) {
  genSum('/tmp/map-reduce-sum-test')
}

module.exports = genSum

