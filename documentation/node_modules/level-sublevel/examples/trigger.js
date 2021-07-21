
var db   = require('../')(require('levelup')('/tmp/whatever'))
var copy = require('../')(require('levelup')('/tmp/whatever2'))

var makeQueue = require('./queue')

makeQueue(db, 'jobs', function (key, done) {
  console.log("JOB KEY", key)
  db.get(key, function (err, value) {
    console.log(key, value, err)
    value && copy.put(key, value, done) || done()
  })
})

db.put('hello' + Date.now(), 'value_' + new Date(), function () {

  setTimeout(function () {

    copy
      .createReadStream()
      .on('data', console.log)

  }, 1000)

})

