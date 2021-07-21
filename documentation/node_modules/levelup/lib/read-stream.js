/* Copyright (c) 2012-2014 LevelUP contributors
 * See list at <https://github.com/rvagg/node-levelup#contributing>
 * MIT License <https://github.com/rvagg/node-levelup/blob/master/LICENSE.md>
 */

// NOTE: we are fixed to readable-stream@1.0.x for now
// for pure Streams2 across Node versions
var Readable      = require('readable-stream').Readable
  , inherits      = require('util').inherits
  , extend        = require('xtend')
  , EncodingError = require('./errors').EncodingError
  , util          = require('./util')

  , defaultOptions = { keys: true, values: true }

  , makeKeyValueData = function (key, value) {
      return {
          key: util.decodeKey(key, this._options)
        , value: util.decodeValue(value, this._options)
      }
    }
  , makeKeyData = function (key) {
      return util.decodeKey(key, this._options)
    }
  , makeValueData = function (_, value) {
      return util.decodeValue(value, this._options)
    }
  , makeNoData = function () { return null }

function ReadStream (options, db, iteratorFactory) {
  if (!(this instanceof ReadStream))
    return new ReadStream(options, db, iteratorFactory)

  Readable.call(this, { objectMode: true, highWaterMark: options.highWaterMark })

  // purely to keep `db` around until we're done so it's not GCed if the user doesn't keep a ref
  this._db = db

  options = this._options = extend(defaultOptions, options)

  this._keyEncoding   = options.keyEncoding   || options.encoding
  this._valueEncoding = options.valueEncoding || options.encoding

  if (typeof this._options.start != 'undefined')
    this._options.start = util.encodeKey(this._options.start, this._options)
  if (typeof this._options.end != 'undefined')
    this._options.end = util.encodeKey(this._options.end, this._options)
  if (typeof this._options.limit != 'number')
    this._options.limit = -1

  this._options.keyAsBuffer   = util.isKeyAsBuffer(this._options)

  this._options.valueAsBuffer = util.isValueAsBuffer(this._options)

  this._makeData = this._options.keys && this._options.values
    ? makeKeyValueData : this._options.keys
      ? makeKeyData : this._options.values
        ? makeValueData : makeNoData

  var self = this
  if (!this._db.isOpen()) {
    this._db.once('ready', function () {
      if (!self._destroyed) {
        self._iterator = iteratorFactory(self._options)
      }
    })
  } else
    this._iterator = iteratorFactory(this._options)
}

inherits(ReadStream, Readable)

ReadStream.prototype._read = function read () {
  var self = this
  if (!self._db.isOpen()) {
    return self._db.once('ready', function () { read.call(self) })
  }
  if (self._destroyed)
    return
 
  self._iterator.next(function(err, key, value) {
    if (err || (key === undefined && value === undefined)) {
      if (!err && !self._destroyed)
        self.push(null)
      return self._cleanup(err)
    }

    try {
      value = self._makeData(key, value)
    } catch (e) {
      return self._cleanup(new EncodingError(e))
    }
    if (!self._destroyed)
      self.push(value)
  })
}

ReadStream.prototype._cleanup = function (err) {
  if (this._destroyed)
    return

  this._destroyed = true

  var self = this
  if (err)
    self.emit('error', err)

  if (self._iterator) {
    self._iterator.end(function () {
      self._iterator = null
      self.emit('close')
    })
  } else {
    self.emit('close')
  }
}

ReadStream.prototype.destroy = function () {
  this._cleanup()
}

ReadStream.prototype.toString = function () {
  return 'LevelUP.ReadStream'
}

module.exports = ReadStream
