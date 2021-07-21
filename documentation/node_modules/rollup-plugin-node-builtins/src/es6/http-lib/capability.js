export var hasFetch = isFunction(global.fetch) && isFunction(global.ReadableStream)

var _blobConstructor;
export function blobConstructor() {
  if (typeof _blobConstructor !== 'undefined') {
    return _blobConstructor;
  }
  try {
    new global.Blob([new ArrayBuffer(1)])
    _blobConstructor = true
  } catch (e) {
    _blobConstructor = false
  }
  return _blobConstructor
}
var xhr;

function checkTypeSupport(type) {
  if (!xhr) {
    xhr = new global.XMLHttpRequest()
    // If location.host is empty, e.g. if this page/worker was loaded
    // from a Blob, then use example.com to avoid an error
    xhr.open('GET', global.location.host ? '/' : 'https://example.com')
  }
  try {
    xhr.responseType = type
    return xhr.responseType === type
  } catch (e) {
    return false
  }

}

// For some strange reason, Safari 7.0 reports typeof global.ArrayBuffer === 'object'.
// Safari 7.1 appears to have fixed this bug.
var haveArrayBuffer = typeof global.ArrayBuffer !== 'undefined'
var haveSlice = haveArrayBuffer && isFunction(global.ArrayBuffer.prototype.slice)

export var arraybuffer = haveArrayBuffer && checkTypeSupport('arraybuffer')
  // These next two tests unavoidably show warnings in Chrome. Since fetch will always
  // be used if it's available, just return false for these to avoid the warnings.
export var msstream = !hasFetch && haveSlice && checkTypeSupport('ms-stream')
export var mozchunkedarraybuffer = !hasFetch && haveArrayBuffer &&
  checkTypeSupport('moz-chunked-arraybuffer')
export var overrideMimeType = isFunction(xhr.overrideMimeType)
export var vbArray = isFunction(global.VBArray)

function isFunction(value) {
  return typeof value === 'function'
}

xhr = null // Help gc
