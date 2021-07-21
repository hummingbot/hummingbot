var fixRange = require('level-fix-range')
//get the first/last record in a range

exports = module.exports = peek
exports.first    = first
exports.last     = last

function once(emitter, events, listener) {
  var remove = []
  events.forEach(function (e) {
    function onEvent (arg) {
      if(listener(e, arg) === false) return
      remove.forEach(function (r) {
        r()
      })
    }
    emitter.on(e, onEvent)
    remove.push(function () {
      emitter.removeListener(e, onEvent)
    })
  })
  return emitter
}


function peek (db, opts, cb) {
  opts.limit = opts.reverse ? 2 : 1
  var stream = once(db.createReadStream(opts), 
    ['data', 'error', 'end'],
    function (event, data) {
      if(opts.reverse && data && opts.start 
        && (data.key.toString() > opts.start))
        return false
      if(event == 'error') cb(data)
      else if(event == 'end') cb(new Error('range not found'), null, null)
      else cb(null, data.key, data.value)
    })
}

function first (db, opts, cb) {
  if (!cb) {
    cb = opts;
    opts = {};
  }
  opts.reverse = false
  return peek(db, fixRange(opts), cb)  
}

//SO, this is pretty horrible,
//but it's works around an issue here
//https://github.com/rvagg/node-levelup/issues/110

function last (db, opts, cb) {
  if (!cb) {
    cb = opts;
    opts = {};
  }
  var start = opts.start
  opts.reverse = true
  return peek(db, fixRange(opts), function (err, key, value) {
    if(err) {
      var _start = opts.start
      opts.start = null
      peek (db, opts, function (_, key, value) {
        if(!key) return cb(err, null, null)
        var _key = key.toString()
        if(_key <= _start && (!opts.end || _key >= opts.end))
          cb(_, key, value)
        else cb(err, null, null)
      })
    }
    else cb(err, key, value)
  })
}

