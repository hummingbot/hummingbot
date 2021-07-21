/*** Levelup tests 
  (the actual test suite isnt runnable in browser, and these arent complete)
***/
var levelup = require('levelup')
var leveljs = require('../')

window.db = levelup('foo', { db: leveljs })

db.put('name', 'LevelUP string', function (err) {
  if (err) return console.log('Ooops!', err) // some kind of I/O error
  db.get('name', function (err, value) {
    if (err) return console.log('Ooops!', err) // likely the key was not found
    console.log('name=' + value)
  })
})

var ary = new Uint8Array(1)
ary[0] = 1
db.put('binary', ary, function (err) {
  if (err) return console.log('Ooops!', err) // some kind of I/O error
  db.get('binary', function (err, value) {
    if (err) return console.log('Ooops!', err) // likely the key was not found
    console.log('binary', value)
  })
})

var writeStream = db.createWriteStream()
writeStream.on('error', function (err) {
  console.log('Oh my!', err)
})
writeStream.on('close', function () {
  console.log('Stream closed')
  db.createKeyStream()
    .on('data', function (data) {
      console.log('KEYSTREAM', data)
    })
    .on('error', function (err) {
      console.log('Oh my!', err)
    })
  db.createReadStream()
    .on('data', function (data) {
      console.log('READSTREAM', data.key, '=', data.value)
    })
    .on('error', function (err) {
      console.log('Oh my!', err)
    })
  db.createValueStream()
    .on('data', function (data) {
      console.log('VALUESTREAM', data)
    })
    .on('error', function (err) {
      console.log('Oh my!', err)
    })
})
writeStream.write({ key: 'name', value: 'Yuri Irsenovich Kim' })
writeStream.write({ key: 'dob', value: '16 February 1941' })
writeStream.write({ key: 'spouse', value: 'Kim Young-sook' })
writeStream.write({ key: 'occupation', value: 'Clown' })
writeStream.end()