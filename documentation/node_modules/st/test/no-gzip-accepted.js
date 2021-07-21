global.options = {
}

const fs = require('fs')
const path = require('path')
const crypto = require('crypto')
const rimraf = require('rimraf')
const { test } = require('tap')
const { req } = require('./common.js')
const testFileName = 'no-gzip-accepted.testfile'
const testFile = path.join(__dirname, '../', testFileName)

const rndData = crypto.randomBytes(1024 * 128).toString('hex') // significantly larger than highWaterMark

test('does not gzip the response', (t) => {
  t.on('end', () => {
    rimraf(testFile, () => {})
  })

  fs.writeFile(testFile, rndData, (err) => {
    t.error(err)

    req('/test/' + testFileName, { 'accept-encoding': 'none' }, (er, res, body) => {
      t.error(er)
      t.equal(res.statusCode, 200)
      t.notOk(res.headers['content-encoding'])
      t.equal(body.toString(), rndData)
      t.end()
    })
  })
})
