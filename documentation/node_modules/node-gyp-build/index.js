var fs = require('fs')
var path = require('path')
var os = require('os')

// Workaround to fix webpack's build warnings: 'the request of a dependency is an expression'
var runtimeRequire = typeof __webpack_require__ === 'function' ? __non_webpack_require__ : require // eslint-disable-line

var abi = process.versions.modules // TODO: support old node where this is undef
var runtime = isElectron() ? 'electron' : 'node'
var arch = os.arch()
var platform = os.platform()

module.exports = load

function load (dir) {
  return runtimeRequire(load.path(dir))
}

load.path = function (dir) {
  dir = path.resolve(dir || '.')

  try {
    var name = runtimeRequire(path.join(dir, 'package.json')).name.toUpperCase().replace(/-/g, '_')
    if (process.env[name + '_PREBUILD']) dir = process.env[name + '_PREBUILD']
  } catch (err) {}

  var release = getFirst(path.join(dir, 'build/Release'), matchBuild)
  if (release) return release

  var debug = getFirst(path.join(dir, 'build/Debug'), matchBuild)
  if (debug) return debug

  var prebuild = getFirst(path.join(dir, 'prebuilds/' + platform + '-' + arch), matchPrebuild)
  if (prebuild) return prebuild

  var napiRuntime = getFirst(path.join(dir, 'prebuilds/' + platform + '-' + arch), matchNapiRuntime)
  if (napiRuntime) return napiRuntime

  var napi = getFirst(path.join(dir, 'prebuilds/' + platform + '-' + arch), matchNapi)
  if (napi) return napi

  throw new Error('No native build was found for runtime=' + runtime + ' abi=' + abi + ' platform=' + platform + ' arch=' + arch)
}

function getFirst (dir, filter) {
  try {
    var files = fs.readdirSync(dir).filter(filter)
    return files[0] && path.join(dir, files[0])
  } catch (err) {
    return null
  }
}

function matchNapiRuntime (name) {
  return name === runtime + '-napi.node'
}

function matchNapi (name) {
  return name === 'node-napi.node'
}

function matchPrebuild (name) {
  var parts = name.split('-')
  return parts[0] === runtime && parts[1] === abi + '.node'
}

function matchBuild (name) {
  return /\.node$/.test(name)
}

function isElectron () {
  if (process.versions && process.versions.electron) return true
  if (process.env.ELECTRON_RUN_AS_NODE) return true
  return typeof window !== 'undefined' && window.process && window.process.type === 'renderer'
}
