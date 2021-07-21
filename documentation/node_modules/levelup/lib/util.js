/* Copyright (c) 2012-2014 LevelUP contributors
 * See list at <https://github.com/rvagg/node-levelup#contributing>
 * MIT License
 * <https://github.com/rvagg/node-levelup/blob/master/LICENSE.md>
 */

var extend        = require('xtend')
  , LevelUPError  = require('./errors').LevelUPError

  , encodingNames = [
        'hex'
      , 'utf8'
      , 'utf-8'
      , 'ascii'
      , 'binary'
      , 'base64'
      , 'ucs2'
      , 'ucs-2'
      , 'utf16le'
      , 'utf-16le'
    ]

  , defaultOptions = {
        createIfMissing : true
      , errorIfExists   : false
      , keyEncoding     : 'utf8'
      , valueEncoding   : 'utf8'
      , compression     : true
    }

  , leveldown

  , encodings = (function () {
      function isBinary (data) {
        return data === undefined || data === null || Buffer.isBuffer(data)
      }

      var encodings = {}
      encodings.utf8 = encodings['utf-8'] = {
          encode : function (data) {
            return isBinary(data) ? data : String(data)
          }
        , decode : function (data) {
          return data
          }
        , buffer : false
        , type   : 'utf8'
      }
      encodings.json = {
          encode : JSON.stringify
        , decode : JSON.parse
        , buffer : false
        , type   : 'json'
      }
      encodingNames.forEach(function (type) {
        if (encodings[type])
          return
        encodings[type] = {
            encode : function (data) {
              return isBinary(data) ? data : new Buffer(data, type)
            }
          , decode : function (buffer) {
              return process.browser ? buffer.toString(type) : buffer;
            }
          , buffer : true
          , type   : type // useful for debugging purposes
        }
      })
      return encodings
    })()

  , encodingOpts = (function () {
      var eo = {}
      encodingNames.forEach(function (e) {
        eo[e] = { valueEncoding : e }
      })
      return eo
    }())

function copy (srcdb, dstdb, callback) {
  srcdb.readStream()
    .pipe(dstdb.writeStream())
    .on('close', callback ? callback : function () {})
    .on('error', callback ? callback : function (err) { throw err })
}

function getOptions (levelup, options) {
  var s = typeof options == 'string' // just an encoding
  if (!s && options && options.encoding && !options.valueEncoding)
    options.valueEncoding = options.encoding
  return extend(
      (levelup && levelup.options) || {}
    , s ? encodingOpts[options] || encodingOpts[defaultOptions.valueEncoding]
        : options
  )
}

function getLevelDOWN () {
  if (leveldown)
    return leveldown

  var requiredVersion       = require('../package.json').devDependencies.leveldown
    , missingLevelDOWNError = 'Could not locate LevelDOWN, try `npm install leveldown`'
    , leveldownVersion

  try {
    leveldownVersion = require('leveldown/package').version
  } catch (e) {
    throw new LevelUPError(missingLevelDOWNError)
  }

  if (!require('semver').satisfies(leveldownVersion, requiredVersion)) {
    throw new LevelUPError(
        'Installed version of LevelDOWN ('
      + leveldownVersion
      + ') does not match required version ('
      + requiredVersion
      + ')'
    )
  }

  try {
    return leveldown = require('leveldown')
  } catch (e) {
    throw new LevelUPError(missingLevelDOWNError)
  }
}

function dispatchError (levelup, error, callback) {
  return typeof callback == 'function'
    ? callback(error)
    : levelup.emit('error', error)
}

function getKeyEncoder (options, op) {
  var type = ((op && op.keyEncoding) || options.keyEncoding) || 'utf8'
  return encodings[type] || type
}

function getValueEncoder (options, op) {
  var type = (((op && (op.valueEncoding || op.encoding))
      || options.valueEncoding || options.encoding)) || 'utf8'
  return encodings[type] || type
}

function encodeKey (key, options, op) {
  return getKeyEncoder(options, op).encode(key)
}

function encodeValue (value, options, op) {
  return getValueEncoder(options, op).encode(value)
}

function decodeKey (key, options) {
  return getKeyEncoder(options).decode(key)
}

function decodeValue (value, options) {
  return getValueEncoder(options).decode(value)
}

function isValueAsBuffer (options, op) {
  return getValueEncoder(options, op).buffer
}

function isKeyAsBuffer (options, op) {
  return getKeyEncoder(options, op).buffer
}

module.exports = {
    defaultOptions  : defaultOptions
  , copy            : copy
  , getOptions      : getOptions
  , getLevelDOWN    : getLevelDOWN
  , dispatchError   : dispatchError
  , encodeKey       : encodeKey
  , encodeValue     : encodeValue
  , isValueAsBuffer : isValueAsBuffer
  , isKeyAsBuffer   : isKeyAsBuffer
  , decodeValue     : decodeValue
  , decodeKey       : decodeKey
}
