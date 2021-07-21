"use strict";function _createForOfIteratorHelper(o,allowArrayLike){var it;if(typeof Symbol==="undefined"||o[Symbol.iterator]==null){if(Array.isArray(o)||(it=_unsupportedIterableToArray2(o))||allowArrayLike&&o&&typeof o.length==="number"){if(it)o=it;var i=0;var F=function F(){};return{s:F,n:function n(){if(i>=o.length)return{done:true};return{done:false,value:o[i++]};},e:function e(_e){throw _e;},f:F};}throw new TypeError("Invalid attempt to iterate non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");}var normalCompletion=true,didErr=false,err;return{s:function s(){it=o[Symbol.iterator]();},n:function n(){var step=it.next();normalCompletion=step.done;return step;},e:function e(_e2){didErr=true;err=_e2;},f:function f(){try{if(!normalCompletion&&it["return"]!=null)it["return"]();}finally{if(didErr)throw err;}}};}function _unsupportedIterableToArray2(o,minLen){if(!o)return;if(typeof o==="string")return _arrayLikeToArray2(o,minLen);var n=Object.prototype.toString.call(o).slice(8,-1);if(n==="Object"&&o.constructor)n=o.constructor.name;if(n==="Map"||n==="Set")return Array.from(o);if(n==="Arguments"||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n))return _arrayLikeToArray2(o,minLen);}function _arrayLikeToArray2(arr,len){if(len==null||len>arr.length)len=arr.length;for(var i=0,arr2=new Array(len);i<len;i++){arr2[i]=arr[i];}return arr2;}function _typeof(obj){"@babel/helpers - typeof";if(typeof Symbol==="function"&&typeof Symbol.iterator==="symbol"){_typeof=function _typeof(obj){return typeof obj;};}else{_typeof=function _typeof(obj){return obj&&typeof Symbol==="function"&&obj.constructor===Symbol&&obj!==Symbol.prototype?"symbol":typeof obj;};}return _typeof(obj);}(function(f){if((typeof exports==="undefined"?"undefined":_typeof(exports))==="object"&&typeof module!=="undefined"){module.exports=f();}else if(typeof define==="function"&&define.amd){define([],f);}else{var g;if(typeof window!=="undefined"){g=window;}else if(typeof global!=="undefined"){g=global;}else if(typeof self!=="undefined"){g=self;}else{g=this;}g.sanitizeHtml=f();}})(function(){var define,module,exports;return function(){function r(e,n,t){function o(i,f){if(!n[i]){if(!e[i]){var c="function"==typeof require&&require;if(!f&&c)return c(i,!0);if(u)return u(i,!0);var a=new Error("Cannot find module '"+i+"'");throw a.code="MODULE_NOT_FOUND",a;}var p=n[i]={exports:{}};e[i][0].call(p.exports,function(r){var n=e[i][1][r];return o(n||r);},p,p.exports,r,e,n,t);}return n[i].exports;}for(var u="function"==typeof require&&require,i=0;i<t.length;i++){o(t[i]);}return o;}return r;}()({1:[function(require,module,exports){'use strict';exports.byteLength=byteLength;exports.toByteArray=toByteArray;exports.fromByteArray=fromByteArray;var lookup=[];var revLookup=[];var Arr=typeof Uint8Array!=='undefined'?Uint8Array:Array;var code='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';for(var i=0,len=code.length;i<len;++i){lookup[i]=code[i];revLookup[code.charCodeAt(i)]=i;}// Support decoding URL-safe base64 strings, as Node.js does.
// See: https://en.wikipedia.org/wiki/Base64#URL_applications
revLookup['-'.charCodeAt(0)]=62;revLookup['_'.charCodeAt(0)]=63;function getLens(b64){var len=b64.length;if(len%4>0){throw new Error('Invalid string. Length must be a multiple of 4');}// Trim off extra bytes after placeholder bytes are found
// See: https://github.com/beatgammit/base64-js/issues/42
var validLen=b64.indexOf('=');if(validLen===-1)validLen=len;var placeHoldersLen=validLen===len?0:4-validLen%4;return[validLen,placeHoldersLen];}// base64 is 4/3 + up to two characters of the original data
function byteLength(b64){var lens=getLens(b64);var validLen=lens[0];var placeHoldersLen=lens[1];return(validLen+placeHoldersLen)*3/4-placeHoldersLen;}function _byteLength(b64,validLen,placeHoldersLen){return(validLen+placeHoldersLen)*3/4-placeHoldersLen;}function toByteArray(b64){var tmp;var lens=getLens(b64);var validLen=lens[0];var placeHoldersLen=lens[1];var arr=new Arr(_byteLength(b64,validLen,placeHoldersLen));var curByte=0;// if there are placeholders, only get up to the last complete 4 chars
var len=placeHoldersLen>0?validLen-4:validLen;var i;for(i=0;i<len;i+=4){tmp=revLookup[b64.charCodeAt(i)]<<18|revLookup[b64.charCodeAt(i+1)]<<12|revLookup[b64.charCodeAt(i+2)]<<6|revLookup[b64.charCodeAt(i+3)];arr[curByte++]=tmp>>16&0xFF;arr[curByte++]=tmp>>8&0xFF;arr[curByte++]=tmp&0xFF;}if(placeHoldersLen===2){tmp=revLookup[b64.charCodeAt(i)]<<2|revLookup[b64.charCodeAt(i+1)]>>4;arr[curByte++]=tmp&0xFF;}if(placeHoldersLen===1){tmp=revLookup[b64.charCodeAt(i)]<<10|revLookup[b64.charCodeAt(i+1)]<<4|revLookup[b64.charCodeAt(i+2)]>>2;arr[curByte++]=tmp>>8&0xFF;arr[curByte++]=tmp&0xFF;}return arr;}function tripletToBase64(num){return lookup[num>>18&0x3F]+lookup[num>>12&0x3F]+lookup[num>>6&0x3F]+lookup[num&0x3F];}function encodeChunk(uint8,start,end){var tmp;var output=[];for(var i=start;i<end;i+=3){tmp=(uint8[i]<<16&0xFF0000)+(uint8[i+1]<<8&0xFF00)+(uint8[i+2]&0xFF);output.push(tripletToBase64(tmp));}return output.join('');}function fromByteArray(uint8){var tmp;var len=uint8.length;var extraBytes=len%3;// if we have 1 byte left, pad 2 bytes
var parts=[];var maxChunkLength=16383;// must be multiple of 3
// go through the array every three bytes, we'll deal with trailing stuff later
for(var i=0,len2=len-extraBytes;i<len2;i+=maxChunkLength){parts.push(encodeChunk(uint8,i,i+maxChunkLength>len2?len2:i+maxChunkLength));}// pad the end with zeros, but make sure to not forget the extra bytes
if(extraBytes===1){tmp=uint8[len-1];parts.push(lookup[tmp>>2]+lookup[tmp<<4&0x3F]+'==');}else if(extraBytes===2){tmp=(uint8[len-2]<<8)+uint8[len-1];parts.push(lookup[tmp>>10]+lookup[tmp>>4&0x3F]+lookup[tmp<<2&0x3F]+'=');}return parts.join('');}},{}],2:[function(require,module,exports){},{}],3:[function(require,module,exports){(function(Buffer){/*!
 * The buffer module from node.js, for the browser.
 *
 * @author   Feross Aboukhadijeh <https://feross.org>
 * @license  MIT
 */ /* eslint-disable no-proto */'use strict';var base64=require('base64-js');var ieee754=require('ieee754');exports.Buffer=Buffer;exports.SlowBuffer=SlowBuffer;exports.INSPECT_MAX_BYTES=50;var K_MAX_LENGTH=0x7fffffff;exports.kMaxLength=K_MAX_LENGTH;/**
 * If `Buffer.TYPED_ARRAY_SUPPORT`:
 *   === true    Use Uint8Array implementation (fastest)
 *   === false   Print warning and recommend using `buffer` v4.x which has an Object
 *               implementation (most compatible, even IE6)
 *
 * Browsers that support typed arrays are IE 10+, Firefox 4+, Chrome 7+, Safari 5.1+,
 * Opera 11.6+, iOS 4.2+.
 *
 * We report that the browser does not support typed arrays if the are not subclassable
 * using __proto__. Firefox 4-29 lacks support for adding new properties to `Uint8Array`
 * (See: https://bugzilla.mozilla.org/show_bug.cgi?id=695438). IE 10 lacks support
 * for __proto__ and has a buggy typed array implementation.
 */Buffer.TYPED_ARRAY_SUPPORT=typedArraySupport();if(!Buffer.TYPED_ARRAY_SUPPORT&&typeof console!=='undefined'&&typeof console.error==='function'){console.error('This browser lacks typed array (Uint8Array) support which is required by '+'`buffer` v5.x. Use `buffer` v4.x if you require old browser support.');}function typedArraySupport(){// Can typed array instances can be augmented?
try{var arr=new Uint8Array(1);arr.__proto__={__proto__:Uint8Array.prototype,foo:function foo(){return 42;}};return arr.foo()===42;}catch(e){return false;}}Object.defineProperty(Buffer.prototype,'parent',{enumerable:true,get:function get(){if(!Buffer.isBuffer(this))return undefined;return this.buffer;}});Object.defineProperty(Buffer.prototype,'offset',{enumerable:true,get:function get(){if(!Buffer.isBuffer(this))return undefined;return this.byteOffset;}});function createBuffer(length){if(length>K_MAX_LENGTH){throw new RangeError('The value "'+length+'" is invalid for option "size"');}// Return an augmented `Uint8Array` instance
var buf=new Uint8Array(length);buf.__proto__=Buffer.prototype;return buf;}/**
 * The Buffer constructor returns instances of `Uint8Array` that have their
 * prototype changed to `Buffer.prototype`. Furthermore, `Buffer` is a subclass of
 * `Uint8Array`, so the returned instances will have all the node `Buffer` methods
 * and the `Uint8Array` methods. Square bracket notation works as expected -- it
 * returns a single octet.
 *
 * The `Uint8Array` prototype remains unmodified.
 */function Buffer(arg,encodingOrOffset,length){// Common case.
if(typeof arg==='number'){if(typeof encodingOrOffset==='string'){throw new TypeError('The "string" argument must be of type string. Received type number');}return allocUnsafe(arg);}return from(arg,encodingOrOffset,length);}// Fix subarray() in ES2016. See: https://github.com/feross/buffer/pull/97
if(typeof Symbol!=='undefined'&&Symbol.species!=null&&Buffer[Symbol.species]===Buffer){Object.defineProperty(Buffer,Symbol.species,{value:null,configurable:true,enumerable:false,writable:false});}Buffer.poolSize=8192;// not used by this implementation
function from(value,encodingOrOffset,length){if(typeof value==='string'){return fromString(value,encodingOrOffset);}if(ArrayBuffer.isView(value)){return fromArrayLike(value);}if(value==null){throw TypeError('The first argument must be one of type string, Buffer, ArrayBuffer, Array, '+'or Array-like Object. Received type '+_typeof(value));}if(isInstance(value,ArrayBuffer)||value&&isInstance(value.buffer,ArrayBuffer)){return fromArrayBuffer(value,encodingOrOffset,length);}if(typeof value==='number'){throw new TypeError('The "value" argument must not be of type number. Received type number');}var valueOf=value.valueOf&&value.valueOf();if(valueOf!=null&&valueOf!==value){return Buffer.from(valueOf,encodingOrOffset,length);}var b=fromObject(value);if(b)return b;if(typeof Symbol!=='undefined'&&Symbol.toPrimitive!=null&&typeof value[Symbol.toPrimitive]==='function'){return Buffer.from(value[Symbol.toPrimitive]('string'),encodingOrOffset,length);}throw new TypeError('The first argument must be one of type string, Buffer, ArrayBuffer, Array, '+'or Array-like Object. Received type '+_typeof(value));}/**
 * Functionally equivalent to Buffer(arg, encoding) but throws a TypeError
 * if value is a number.
 * Buffer.from(str[, encoding])
 * Buffer.from(array)
 * Buffer.from(buffer)
 * Buffer.from(arrayBuffer[, byteOffset[, length]])
 **/Buffer.from=function(value,encodingOrOffset,length){return from(value,encodingOrOffset,length);};// Note: Change prototype *after* Buffer.from is defined to workaround Chrome bug:
// https://github.com/feross/buffer/pull/148
Buffer.prototype.__proto__=Uint8Array.prototype;Buffer.__proto__=Uint8Array;function assertSize(size){if(typeof size!=='number'){throw new TypeError('"size" argument must be of type number');}else if(size<0){throw new RangeError('The value "'+size+'" is invalid for option "size"');}}function alloc(size,fill,encoding){assertSize(size);if(size<=0){return createBuffer(size);}if(fill!==undefined){// Only pay attention to encoding if it's a string. This
// prevents accidentally sending in a number that would
// be interpretted as a start offset.
return typeof encoding==='string'?createBuffer(size).fill(fill,encoding):createBuffer(size).fill(fill);}return createBuffer(size);}/**
 * Creates a new filled Buffer instance.
 * alloc(size[, fill[, encoding]])
 **/Buffer.alloc=function(size,fill,encoding){return alloc(size,fill,encoding);};function allocUnsafe(size){assertSize(size);return createBuffer(size<0?0:checked(size)|0);}/**
 * Equivalent to Buffer(num), by default creates a non-zero-filled Buffer instance.
 * */Buffer.allocUnsafe=function(size){return allocUnsafe(size);};/**
 * Equivalent to SlowBuffer(num), by default creates a non-zero-filled Buffer instance.
 */Buffer.allocUnsafeSlow=function(size){return allocUnsafe(size);};function fromString(string,encoding){if(typeof encoding!=='string'||encoding===''){encoding='utf8';}if(!Buffer.isEncoding(encoding)){throw new TypeError('Unknown encoding: '+encoding);}var length=byteLength(string,encoding)|0;var buf=createBuffer(length);var actual=buf.write(string,encoding);if(actual!==length){// Writing a hex string, for example, that contains invalid characters will
// cause everything after the first invalid character to be ignored. (e.g.
// 'abxxcd' will be treated as 'ab')
buf=buf.slice(0,actual);}return buf;}function fromArrayLike(array){var length=array.length<0?0:checked(array.length)|0;var buf=createBuffer(length);for(var i=0;i<length;i+=1){buf[i]=array[i]&255;}return buf;}function fromArrayBuffer(array,byteOffset,length){if(byteOffset<0||array.byteLength<byteOffset){throw new RangeError('"offset" is outside of buffer bounds');}if(array.byteLength<byteOffset+(length||0)){throw new RangeError('"length" is outside of buffer bounds');}var buf;if(byteOffset===undefined&&length===undefined){buf=new Uint8Array(array);}else if(length===undefined){buf=new Uint8Array(array,byteOffset);}else{buf=new Uint8Array(array,byteOffset,length);}// Return an augmented `Uint8Array` instance
buf.__proto__=Buffer.prototype;return buf;}function fromObject(obj){if(Buffer.isBuffer(obj)){var len=checked(obj.length)|0;var buf=createBuffer(len);if(buf.length===0){return buf;}obj.copy(buf,0,0,len);return buf;}if(obj.length!==undefined){if(typeof obj.length!=='number'||numberIsNaN(obj.length)){return createBuffer(0);}return fromArrayLike(obj);}if(obj.type==='Buffer'&&Array.isArray(obj.data)){return fromArrayLike(obj.data);}}function checked(length){// Note: cannot use `length < K_MAX_LENGTH` here because that fails when
// length is NaN (which is otherwise coerced to zero.)
if(length>=K_MAX_LENGTH){throw new RangeError('Attempt to allocate Buffer larger than maximum '+'size: 0x'+K_MAX_LENGTH.toString(16)+' bytes');}return length|0;}function SlowBuffer(length){if(+length!=length){// eslint-disable-line eqeqeq
length=0;}return Buffer.alloc(+length);}Buffer.isBuffer=function isBuffer(b){return b!=null&&b._isBuffer===true&&b!==Buffer.prototype;// so Buffer.isBuffer(Buffer.prototype) will be false
};Buffer.compare=function compare(a,b){if(isInstance(a,Uint8Array))a=Buffer.from(a,a.offset,a.byteLength);if(isInstance(b,Uint8Array))b=Buffer.from(b,b.offset,b.byteLength);if(!Buffer.isBuffer(a)||!Buffer.isBuffer(b)){throw new TypeError('The "buf1", "buf2" arguments must be one of type Buffer or Uint8Array');}if(a===b)return 0;var x=a.length;var y=b.length;for(var i=0,len=Math.min(x,y);i<len;++i){if(a[i]!==b[i]){x=a[i];y=b[i];break;}}if(x<y)return-1;if(y<x)return 1;return 0;};Buffer.isEncoding=function isEncoding(encoding){switch(String(encoding).toLowerCase()){case'hex':case'utf8':case'utf-8':case'ascii':case'latin1':case'binary':case'base64':case'ucs2':case'ucs-2':case'utf16le':case'utf-16le':return true;default:return false;}};Buffer.concat=function concat(list,length){if(!Array.isArray(list)){throw new TypeError('"list" argument must be an Array of Buffers');}if(list.length===0){return Buffer.alloc(0);}var i;if(length===undefined){length=0;for(i=0;i<list.length;++i){length+=list[i].length;}}var buffer=Buffer.allocUnsafe(length);var pos=0;for(i=0;i<list.length;++i){var buf=list[i];if(isInstance(buf,Uint8Array)){buf=Buffer.from(buf);}if(!Buffer.isBuffer(buf)){throw new TypeError('"list" argument must be an Array of Buffers');}buf.copy(buffer,pos);pos+=buf.length;}return buffer;};function byteLength(string,encoding){if(Buffer.isBuffer(string)){return string.length;}if(ArrayBuffer.isView(string)||isInstance(string,ArrayBuffer)){return string.byteLength;}if(typeof string!=='string'){throw new TypeError('The "string" argument must be one of type string, Buffer, or ArrayBuffer. '+'Received type '+_typeof(string));}var len=string.length;var mustMatch=arguments.length>2&&arguments[2]===true;if(!mustMatch&&len===0)return 0;// Use a for loop to avoid recursion
var loweredCase=false;for(;;){switch(encoding){case'ascii':case'latin1':case'binary':return len;case'utf8':case'utf-8':return utf8ToBytes(string).length;case'ucs2':case'ucs-2':case'utf16le':case'utf-16le':return len*2;case'hex':return len>>>1;case'base64':return base64ToBytes(string).length;default:if(loweredCase){return mustMatch?-1:utf8ToBytes(string).length;// assume utf8
}encoding=(''+encoding).toLowerCase();loweredCase=true;}}}Buffer.byteLength=byteLength;function slowToString(encoding,start,end){var loweredCase=false;// No need to verify that "this.length <= MAX_UINT32" since it's a read-only
// property of a typed array.
// This behaves neither like String nor Uint8Array in that we set start/end
// to their upper/lower bounds if the value passed is out of range.
// undefined is handled specially as per ECMA-262 6th Edition,
// Section 13.3.3.7 Runtime Semantics: KeyedBindingInitialization.
if(start===undefined||start<0){start=0;}// Return early if start > this.length. Done here to prevent potential uint32
// coercion fail below.
if(start>this.length){return'';}if(end===undefined||end>this.length){end=this.length;}if(end<=0){return'';}// Force coersion to uint32. This will also coerce falsey/NaN values to 0.
end>>>=0;start>>>=0;if(end<=start){return'';}if(!encoding)encoding='utf8';while(true){switch(encoding){case'hex':return hexSlice(this,start,end);case'utf8':case'utf-8':return utf8Slice(this,start,end);case'ascii':return asciiSlice(this,start,end);case'latin1':case'binary':return latin1Slice(this,start,end);case'base64':return base64Slice(this,start,end);case'ucs2':case'ucs-2':case'utf16le':case'utf-16le':return utf16leSlice(this,start,end);default:if(loweredCase)throw new TypeError('Unknown encoding: '+encoding);encoding=(encoding+'').toLowerCase();loweredCase=true;}}}// This property is used by `Buffer.isBuffer` (and the `is-buffer` npm package)
// to detect a Buffer instance. It's not possible to use `instanceof Buffer`
// reliably in a browserify context because there could be multiple different
// copies of the 'buffer' package in use. This method works even for Buffer
// instances that were created from another copy of the `buffer` package.
// See: https://github.com/feross/buffer/issues/154
Buffer.prototype._isBuffer=true;function swap(b,n,m){var i=b[n];b[n]=b[m];b[m]=i;}Buffer.prototype.swap16=function swap16(){var len=this.length;if(len%2!==0){throw new RangeError('Buffer size must be a multiple of 16-bits');}for(var i=0;i<len;i+=2){swap(this,i,i+1);}return this;};Buffer.prototype.swap32=function swap32(){var len=this.length;if(len%4!==0){throw new RangeError('Buffer size must be a multiple of 32-bits');}for(var i=0;i<len;i+=4){swap(this,i,i+3);swap(this,i+1,i+2);}return this;};Buffer.prototype.swap64=function swap64(){var len=this.length;if(len%8!==0){throw new RangeError('Buffer size must be a multiple of 64-bits');}for(var i=0;i<len;i+=8){swap(this,i,i+7);swap(this,i+1,i+6);swap(this,i+2,i+5);swap(this,i+3,i+4);}return this;};Buffer.prototype.toString=function toString(){var length=this.length;if(length===0)return'';if(arguments.length===0)return utf8Slice(this,0,length);return slowToString.apply(this,arguments);};Buffer.prototype.toLocaleString=Buffer.prototype.toString;Buffer.prototype.equals=function equals(b){if(!Buffer.isBuffer(b))throw new TypeError('Argument must be a Buffer');if(this===b)return true;return Buffer.compare(this,b)===0;};Buffer.prototype.inspect=function inspect(){var str='';var max=exports.INSPECT_MAX_BYTES;str=this.toString('hex',0,max).replace(/(.{2})/g,'$1 ').trim();if(this.length>max)str+=' ... ';return'<Buffer '+str+'>';};Buffer.prototype.compare=function compare(target,start,end,thisStart,thisEnd){if(isInstance(target,Uint8Array)){target=Buffer.from(target,target.offset,target.byteLength);}if(!Buffer.isBuffer(target)){throw new TypeError('The "target" argument must be one of type Buffer or Uint8Array. '+'Received type '+_typeof(target));}if(start===undefined){start=0;}if(end===undefined){end=target?target.length:0;}if(thisStart===undefined){thisStart=0;}if(thisEnd===undefined){thisEnd=this.length;}if(start<0||end>target.length||thisStart<0||thisEnd>this.length){throw new RangeError('out of range index');}if(thisStart>=thisEnd&&start>=end){return 0;}if(thisStart>=thisEnd){return-1;}if(start>=end){return 1;}start>>>=0;end>>>=0;thisStart>>>=0;thisEnd>>>=0;if(this===target)return 0;var x=thisEnd-thisStart;var y=end-start;var len=Math.min(x,y);var thisCopy=this.slice(thisStart,thisEnd);var targetCopy=target.slice(start,end);for(var i=0;i<len;++i){if(thisCopy[i]!==targetCopy[i]){x=thisCopy[i];y=targetCopy[i];break;}}if(x<y)return-1;if(y<x)return 1;return 0;};// Finds either the first index of `val` in `buffer` at offset >= `byteOffset`,
// OR the last index of `val` in `buffer` at offset <= `byteOffset`.
//
// Arguments:
// - buffer - a Buffer to search
// - val - a string, Buffer, or number
// - byteOffset - an index into `buffer`; will be clamped to an int32
// - encoding - an optional encoding, relevant is val is a string
// - dir - true for indexOf, false for lastIndexOf
function bidirectionalIndexOf(buffer,val,byteOffset,encoding,dir){// Empty buffer means no match
if(buffer.length===0)return-1;// Normalize byteOffset
if(typeof byteOffset==='string'){encoding=byteOffset;byteOffset=0;}else if(byteOffset>0x7fffffff){byteOffset=0x7fffffff;}else if(byteOffset<-0x80000000){byteOffset=-0x80000000;}byteOffset=+byteOffset;// Coerce to Number.
if(numberIsNaN(byteOffset)){// byteOffset: it it's undefined, null, NaN, "foo", etc, search whole buffer
byteOffset=dir?0:buffer.length-1;}// Normalize byteOffset: negative offsets start from the end of the buffer
if(byteOffset<0)byteOffset=buffer.length+byteOffset;if(byteOffset>=buffer.length){if(dir)return-1;else byteOffset=buffer.length-1;}else if(byteOffset<0){if(dir)byteOffset=0;else return-1;}// Normalize val
if(typeof val==='string'){val=Buffer.from(val,encoding);}// Finally, search either indexOf (if dir is true) or lastIndexOf
if(Buffer.isBuffer(val)){// Special case: looking for empty string/buffer always fails
if(val.length===0){return-1;}return arrayIndexOf(buffer,val,byteOffset,encoding,dir);}else if(typeof val==='number'){val=val&0xFF;// Search for a byte value [0-255]
if(typeof Uint8Array.prototype.indexOf==='function'){if(dir){return Uint8Array.prototype.indexOf.call(buffer,val,byteOffset);}else{return Uint8Array.prototype.lastIndexOf.call(buffer,val,byteOffset);}}return arrayIndexOf(buffer,[val],byteOffset,encoding,dir);}throw new TypeError('val must be string, number or Buffer');}function arrayIndexOf(arr,val,byteOffset,encoding,dir){var indexSize=1;var arrLength=arr.length;var valLength=val.length;if(encoding!==undefined){encoding=String(encoding).toLowerCase();if(encoding==='ucs2'||encoding==='ucs-2'||encoding==='utf16le'||encoding==='utf-16le'){if(arr.length<2||val.length<2){return-1;}indexSize=2;arrLength/=2;valLength/=2;byteOffset/=2;}}function read(buf,i){if(indexSize===1){return buf[i];}else{return buf.readUInt16BE(i*indexSize);}}var i;if(dir){var foundIndex=-1;for(i=byteOffset;i<arrLength;i++){if(read(arr,i)===read(val,foundIndex===-1?0:i-foundIndex)){if(foundIndex===-1)foundIndex=i;if(i-foundIndex+1===valLength)return foundIndex*indexSize;}else{if(foundIndex!==-1)i-=i-foundIndex;foundIndex=-1;}}}else{if(byteOffset+valLength>arrLength)byteOffset=arrLength-valLength;for(i=byteOffset;i>=0;i--){var found=true;for(var j=0;j<valLength;j++){if(read(arr,i+j)!==read(val,j)){found=false;break;}}if(found)return i;}}return-1;}Buffer.prototype.includes=function includes(val,byteOffset,encoding){return this.indexOf(val,byteOffset,encoding)!==-1;};Buffer.prototype.indexOf=function indexOf(val,byteOffset,encoding){return bidirectionalIndexOf(this,val,byteOffset,encoding,true);};Buffer.prototype.lastIndexOf=function lastIndexOf(val,byteOffset,encoding){return bidirectionalIndexOf(this,val,byteOffset,encoding,false);};function hexWrite(buf,string,offset,length){offset=Number(offset)||0;var remaining=buf.length-offset;if(!length){length=remaining;}else{length=Number(length);if(length>remaining){length=remaining;}}var strLen=string.length;if(length>strLen/2){length=strLen/2;}for(var i=0;i<length;++i){var parsed=parseInt(string.substr(i*2,2),16);if(numberIsNaN(parsed))return i;buf[offset+i]=parsed;}return i;}function utf8Write(buf,string,offset,length){return blitBuffer(utf8ToBytes(string,buf.length-offset),buf,offset,length);}function asciiWrite(buf,string,offset,length){return blitBuffer(asciiToBytes(string),buf,offset,length);}function latin1Write(buf,string,offset,length){return asciiWrite(buf,string,offset,length);}function base64Write(buf,string,offset,length){return blitBuffer(base64ToBytes(string),buf,offset,length);}function ucs2Write(buf,string,offset,length){return blitBuffer(utf16leToBytes(string,buf.length-offset),buf,offset,length);}Buffer.prototype.write=function write(string,offset,length,encoding){// Buffer#write(string)
if(offset===undefined){encoding='utf8';length=this.length;offset=0;// Buffer#write(string, encoding)
}else if(length===undefined&&typeof offset==='string'){encoding=offset;length=this.length;offset=0;// Buffer#write(string, offset[, length][, encoding])
}else if(isFinite(offset)){offset=offset>>>0;if(isFinite(length)){length=length>>>0;if(encoding===undefined)encoding='utf8';}else{encoding=length;length=undefined;}}else{throw new Error('Buffer.write(string, encoding, offset[, length]) is no longer supported');}var remaining=this.length-offset;if(length===undefined||length>remaining)length=remaining;if(string.length>0&&(length<0||offset<0)||offset>this.length){throw new RangeError('Attempt to write outside buffer bounds');}if(!encoding)encoding='utf8';var loweredCase=false;for(;;){switch(encoding){case'hex':return hexWrite(this,string,offset,length);case'utf8':case'utf-8':return utf8Write(this,string,offset,length);case'ascii':return asciiWrite(this,string,offset,length);case'latin1':case'binary':return latin1Write(this,string,offset,length);case'base64':// Warning: maxLength not taken into account in base64Write
return base64Write(this,string,offset,length);case'ucs2':case'ucs-2':case'utf16le':case'utf-16le':return ucs2Write(this,string,offset,length);default:if(loweredCase)throw new TypeError('Unknown encoding: '+encoding);encoding=(''+encoding).toLowerCase();loweredCase=true;}}};Buffer.prototype.toJSON=function toJSON(){return{type:'Buffer',data:Array.prototype.slice.call(this._arr||this,0)};};function base64Slice(buf,start,end){if(start===0&&end===buf.length){return base64.fromByteArray(buf);}else{return base64.fromByteArray(buf.slice(start,end));}}function utf8Slice(buf,start,end){end=Math.min(buf.length,end);var res=[];var i=start;while(i<end){var firstByte=buf[i];var codePoint=null;var bytesPerSequence=firstByte>0xEF?4:firstByte>0xDF?3:firstByte>0xBF?2:1;if(i+bytesPerSequence<=end){var secondByte,thirdByte,fourthByte,tempCodePoint;switch(bytesPerSequence){case 1:if(firstByte<0x80){codePoint=firstByte;}break;case 2:secondByte=buf[i+1];if((secondByte&0xC0)===0x80){tempCodePoint=(firstByte&0x1F)<<0x6|secondByte&0x3F;if(tempCodePoint>0x7F){codePoint=tempCodePoint;}}break;case 3:secondByte=buf[i+1];thirdByte=buf[i+2];if((secondByte&0xC0)===0x80&&(thirdByte&0xC0)===0x80){tempCodePoint=(firstByte&0xF)<<0xC|(secondByte&0x3F)<<0x6|thirdByte&0x3F;if(tempCodePoint>0x7FF&&(tempCodePoint<0xD800||tempCodePoint>0xDFFF)){codePoint=tempCodePoint;}}break;case 4:secondByte=buf[i+1];thirdByte=buf[i+2];fourthByte=buf[i+3];if((secondByte&0xC0)===0x80&&(thirdByte&0xC0)===0x80&&(fourthByte&0xC0)===0x80){tempCodePoint=(firstByte&0xF)<<0x12|(secondByte&0x3F)<<0xC|(thirdByte&0x3F)<<0x6|fourthByte&0x3F;if(tempCodePoint>0xFFFF&&tempCodePoint<0x110000){codePoint=tempCodePoint;}}}}if(codePoint===null){// we did not generate a valid codePoint so insert a
// replacement char (U+FFFD) and advance only 1 byte
codePoint=0xFFFD;bytesPerSequence=1;}else if(codePoint>0xFFFF){// encode to utf16 (surrogate pair dance)
codePoint-=0x10000;res.push(codePoint>>>10&0x3FF|0xD800);codePoint=0xDC00|codePoint&0x3FF;}res.push(codePoint);i+=bytesPerSequence;}return decodeCodePointsArray(res);}// Based on http://stackoverflow.com/a/22747272/680742, the browser with
// the lowest limit is Chrome, with 0x10000 args.
// We go 1 magnitude less, for safety
var MAX_ARGUMENTS_LENGTH=0x1000;function decodeCodePointsArray(codePoints){var len=codePoints.length;if(len<=MAX_ARGUMENTS_LENGTH){return String.fromCharCode.apply(String,codePoints);// avoid extra slice()
}// Decode in chunks to avoid "call stack size exceeded".
var res='';var i=0;while(i<len){res+=String.fromCharCode.apply(String,codePoints.slice(i,i+=MAX_ARGUMENTS_LENGTH));}return res;}function asciiSlice(buf,start,end){var ret='';end=Math.min(buf.length,end);for(var i=start;i<end;++i){ret+=String.fromCharCode(buf[i]&0x7F);}return ret;}function latin1Slice(buf,start,end){var ret='';end=Math.min(buf.length,end);for(var i=start;i<end;++i){ret+=String.fromCharCode(buf[i]);}return ret;}function hexSlice(buf,start,end){var len=buf.length;if(!start||start<0)start=0;if(!end||end<0||end>len)end=len;var out='';for(var i=start;i<end;++i){out+=toHex(buf[i]);}return out;}function utf16leSlice(buf,start,end){var bytes=buf.slice(start,end);var res='';for(var i=0;i<bytes.length;i+=2){res+=String.fromCharCode(bytes[i]+bytes[i+1]*256);}return res;}Buffer.prototype.slice=function slice(start,end){var len=this.length;start=~~start;end=end===undefined?len:~~end;if(start<0){start+=len;if(start<0)start=0;}else if(start>len){start=len;}if(end<0){end+=len;if(end<0)end=0;}else if(end>len){end=len;}if(end<start)end=start;var newBuf=this.subarray(start,end);// Return an augmented `Uint8Array` instance
newBuf.__proto__=Buffer.prototype;return newBuf;};/*
 * Need to make sure that buffer isn't trying to write out of bounds.
 */function checkOffset(offset,ext,length){if(offset%1!==0||offset<0)throw new RangeError('offset is not uint');if(offset+ext>length)throw new RangeError('Trying to access beyond buffer length');}Buffer.prototype.readUIntLE=function readUIntLE(offset,byteLength,noAssert){offset=offset>>>0;byteLength=byteLength>>>0;if(!noAssert)checkOffset(offset,byteLength,this.length);var val=this[offset];var mul=1;var i=0;while(++i<byteLength&&(mul*=0x100)){val+=this[offset+i]*mul;}return val;};Buffer.prototype.readUIntBE=function readUIntBE(offset,byteLength,noAssert){offset=offset>>>0;byteLength=byteLength>>>0;if(!noAssert){checkOffset(offset,byteLength,this.length);}var val=this[offset+--byteLength];var mul=1;while(byteLength>0&&(mul*=0x100)){val+=this[offset+--byteLength]*mul;}return val;};Buffer.prototype.readUInt8=function readUInt8(offset,noAssert){offset=offset>>>0;if(!noAssert)checkOffset(offset,1,this.length);return this[offset];};Buffer.prototype.readUInt16LE=function readUInt16LE(offset,noAssert){offset=offset>>>0;if(!noAssert)checkOffset(offset,2,this.length);return this[offset]|this[offset+1]<<8;};Buffer.prototype.readUInt16BE=function readUInt16BE(offset,noAssert){offset=offset>>>0;if(!noAssert)checkOffset(offset,2,this.length);return this[offset]<<8|this[offset+1];};Buffer.prototype.readUInt32LE=function readUInt32LE(offset,noAssert){offset=offset>>>0;if(!noAssert)checkOffset(offset,4,this.length);return(this[offset]|this[offset+1]<<8|this[offset+2]<<16)+this[offset+3]*0x1000000;};Buffer.prototype.readUInt32BE=function readUInt32BE(offset,noAssert){offset=offset>>>0;if(!noAssert)checkOffset(offset,4,this.length);return this[offset]*0x1000000+(this[offset+1]<<16|this[offset+2]<<8|this[offset+3]);};Buffer.prototype.readIntLE=function readIntLE(offset,byteLength,noAssert){offset=offset>>>0;byteLength=byteLength>>>0;if(!noAssert)checkOffset(offset,byteLength,this.length);var val=this[offset];var mul=1;var i=0;while(++i<byteLength&&(mul*=0x100)){val+=this[offset+i]*mul;}mul*=0x80;if(val>=mul)val-=Math.pow(2,8*byteLength);return val;};Buffer.prototype.readIntBE=function readIntBE(offset,byteLength,noAssert){offset=offset>>>0;byteLength=byteLength>>>0;if(!noAssert)checkOffset(offset,byteLength,this.length);var i=byteLength;var mul=1;var val=this[offset+--i];while(i>0&&(mul*=0x100)){val+=this[offset+--i]*mul;}mul*=0x80;if(val>=mul)val-=Math.pow(2,8*byteLength);return val;};Buffer.prototype.readInt8=function readInt8(offset,noAssert){offset=offset>>>0;if(!noAssert)checkOffset(offset,1,this.length);if(!(this[offset]&0x80))return this[offset];return(0xff-this[offset]+1)*-1;};Buffer.prototype.readInt16LE=function readInt16LE(offset,noAssert){offset=offset>>>0;if(!noAssert)checkOffset(offset,2,this.length);var val=this[offset]|this[offset+1]<<8;return val&0x8000?val|0xFFFF0000:val;};Buffer.prototype.readInt16BE=function readInt16BE(offset,noAssert){offset=offset>>>0;if(!noAssert)checkOffset(offset,2,this.length);var val=this[offset+1]|this[offset]<<8;return val&0x8000?val|0xFFFF0000:val;};Buffer.prototype.readInt32LE=function readInt32LE(offset,noAssert){offset=offset>>>0;if(!noAssert)checkOffset(offset,4,this.length);return this[offset]|this[offset+1]<<8|this[offset+2]<<16|this[offset+3]<<24;};Buffer.prototype.readInt32BE=function readInt32BE(offset,noAssert){offset=offset>>>0;if(!noAssert)checkOffset(offset,4,this.length);return this[offset]<<24|this[offset+1]<<16|this[offset+2]<<8|this[offset+3];};Buffer.prototype.readFloatLE=function readFloatLE(offset,noAssert){offset=offset>>>0;if(!noAssert)checkOffset(offset,4,this.length);return ieee754.read(this,offset,true,23,4);};Buffer.prototype.readFloatBE=function readFloatBE(offset,noAssert){offset=offset>>>0;if(!noAssert)checkOffset(offset,4,this.length);return ieee754.read(this,offset,false,23,4);};Buffer.prototype.readDoubleLE=function readDoubleLE(offset,noAssert){offset=offset>>>0;if(!noAssert)checkOffset(offset,8,this.length);return ieee754.read(this,offset,true,52,8);};Buffer.prototype.readDoubleBE=function readDoubleBE(offset,noAssert){offset=offset>>>0;if(!noAssert)checkOffset(offset,8,this.length);return ieee754.read(this,offset,false,52,8);};function checkInt(buf,value,offset,ext,max,min){if(!Buffer.isBuffer(buf))throw new TypeError('"buffer" argument must be a Buffer instance');if(value>max||value<min)throw new RangeError('"value" argument is out of bounds');if(offset+ext>buf.length)throw new RangeError('Index out of range');}Buffer.prototype.writeUIntLE=function writeUIntLE(value,offset,byteLength,noAssert){value=+value;offset=offset>>>0;byteLength=byteLength>>>0;if(!noAssert){var maxBytes=Math.pow(2,8*byteLength)-1;checkInt(this,value,offset,byteLength,maxBytes,0);}var mul=1;var i=0;this[offset]=value&0xFF;while(++i<byteLength&&(mul*=0x100)){this[offset+i]=value/mul&0xFF;}return offset+byteLength;};Buffer.prototype.writeUIntBE=function writeUIntBE(value,offset,byteLength,noAssert){value=+value;offset=offset>>>0;byteLength=byteLength>>>0;if(!noAssert){var maxBytes=Math.pow(2,8*byteLength)-1;checkInt(this,value,offset,byteLength,maxBytes,0);}var i=byteLength-1;var mul=1;this[offset+i]=value&0xFF;while(--i>=0&&(mul*=0x100)){this[offset+i]=value/mul&0xFF;}return offset+byteLength;};Buffer.prototype.writeUInt8=function writeUInt8(value,offset,noAssert){value=+value;offset=offset>>>0;if(!noAssert)checkInt(this,value,offset,1,0xff,0);this[offset]=value&0xff;return offset+1;};Buffer.prototype.writeUInt16LE=function writeUInt16LE(value,offset,noAssert){value=+value;offset=offset>>>0;if(!noAssert)checkInt(this,value,offset,2,0xffff,0);this[offset]=value&0xff;this[offset+1]=value>>>8;return offset+2;};Buffer.prototype.writeUInt16BE=function writeUInt16BE(value,offset,noAssert){value=+value;offset=offset>>>0;if(!noAssert)checkInt(this,value,offset,2,0xffff,0);this[offset]=value>>>8;this[offset+1]=value&0xff;return offset+2;};Buffer.prototype.writeUInt32LE=function writeUInt32LE(value,offset,noAssert){value=+value;offset=offset>>>0;if(!noAssert)checkInt(this,value,offset,4,0xffffffff,0);this[offset+3]=value>>>24;this[offset+2]=value>>>16;this[offset+1]=value>>>8;this[offset]=value&0xff;return offset+4;};Buffer.prototype.writeUInt32BE=function writeUInt32BE(value,offset,noAssert){value=+value;offset=offset>>>0;if(!noAssert)checkInt(this,value,offset,4,0xffffffff,0);this[offset]=value>>>24;this[offset+1]=value>>>16;this[offset+2]=value>>>8;this[offset+3]=value&0xff;return offset+4;};Buffer.prototype.writeIntLE=function writeIntLE(value,offset,byteLength,noAssert){value=+value;offset=offset>>>0;if(!noAssert){var limit=Math.pow(2,8*byteLength-1);checkInt(this,value,offset,byteLength,limit-1,-limit);}var i=0;var mul=1;var sub=0;this[offset]=value&0xFF;while(++i<byteLength&&(mul*=0x100)){if(value<0&&sub===0&&this[offset+i-1]!==0){sub=1;}this[offset+i]=(value/mul>>0)-sub&0xFF;}return offset+byteLength;};Buffer.prototype.writeIntBE=function writeIntBE(value,offset,byteLength,noAssert){value=+value;offset=offset>>>0;if(!noAssert){var limit=Math.pow(2,8*byteLength-1);checkInt(this,value,offset,byteLength,limit-1,-limit);}var i=byteLength-1;var mul=1;var sub=0;this[offset+i]=value&0xFF;while(--i>=0&&(mul*=0x100)){if(value<0&&sub===0&&this[offset+i+1]!==0){sub=1;}this[offset+i]=(value/mul>>0)-sub&0xFF;}return offset+byteLength;};Buffer.prototype.writeInt8=function writeInt8(value,offset,noAssert){value=+value;offset=offset>>>0;if(!noAssert)checkInt(this,value,offset,1,0x7f,-0x80);if(value<0)value=0xff+value+1;this[offset]=value&0xff;return offset+1;};Buffer.prototype.writeInt16LE=function writeInt16LE(value,offset,noAssert){value=+value;offset=offset>>>0;if(!noAssert)checkInt(this,value,offset,2,0x7fff,-0x8000);this[offset]=value&0xff;this[offset+1]=value>>>8;return offset+2;};Buffer.prototype.writeInt16BE=function writeInt16BE(value,offset,noAssert){value=+value;offset=offset>>>0;if(!noAssert)checkInt(this,value,offset,2,0x7fff,-0x8000);this[offset]=value>>>8;this[offset+1]=value&0xff;return offset+2;};Buffer.prototype.writeInt32LE=function writeInt32LE(value,offset,noAssert){value=+value;offset=offset>>>0;if(!noAssert)checkInt(this,value,offset,4,0x7fffffff,-0x80000000);this[offset]=value&0xff;this[offset+1]=value>>>8;this[offset+2]=value>>>16;this[offset+3]=value>>>24;return offset+4;};Buffer.prototype.writeInt32BE=function writeInt32BE(value,offset,noAssert){value=+value;offset=offset>>>0;if(!noAssert)checkInt(this,value,offset,4,0x7fffffff,-0x80000000);if(value<0)value=0xffffffff+value+1;this[offset]=value>>>24;this[offset+1]=value>>>16;this[offset+2]=value>>>8;this[offset+3]=value&0xff;return offset+4;};function checkIEEE754(buf,value,offset,ext,max,min){if(offset+ext>buf.length)throw new RangeError('Index out of range');if(offset<0)throw new RangeError('Index out of range');}function writeFloat(buf,value,offset,littleEndian,noAssert){value=+value;offset=offset>>>0;if(!noAssert){checkIEEE754(buf,value,offset,4,3.4028234663852886e+38,-3.4028234663852886e+38);}ieee754.write(buf,value,offset,littleEndian,23,4);return offset+4;}Buffer.prototype.writeFloatLE=function writeFloatLE(value,offset,noAssert){return writeFloat(this,value,offset,true,noAssert);};Buffer.prototype.writeFloatBE=function writeFloatBE(value,offset,noAssert){return writeFloat(this,value,offset,false,noAssert);};function writeDouble(buf,value,offset,littleEndian,noAssert){value=+value;offset=offset>>>0;if(!noAssert){checkIEEE754(buf,value,offset,8,1.7976931348623157E+308,-1.7976931348623157E+308);}ieee754.write(buf,value,offset,littleEndian,52,8);return offset+8;}Buffer.prototype.writeDoubleLE=function writeDoubleLE(value,offset,noAssert){return writeDouble(this,value,offset,true,noAssert);};Buffer.prototype.writeDoubleBE=function writeDoubleBE(value,offset,noAssert){return writeDouble(this,value,offset,false,noAssert);};// copy(targetBuffer, targetStart=0, sourceStart=0, sourceEnd=buffer.length)
Buffer.prototype.copy=function copy(target,targetStart,start,end){if(!Buffer.isBuffer(target))throw new TypeError('argument should be a Buffer');if(!start)start=0;if(!end&&end!==0)end=this.length;if(targetStart>=target.length)targetStart=target.length;if(!targetStart)targetStart=0;if(end>0&&end<start)end=start;// Copy 0 bytes; we're done
if(end===start)return 0;if(target.length===0||this.length===0)return 0;// Fatal error conditions
if(targetStart<0){throw new RangeError('targetStart out of bounds');}if(start<0||start>=this.length)throw new RangeError('Index out of range');if(end<0)throw new RangeError('sourceEnd out of bounds');// Are we oob?
if(end>this.length)end=this.length;if(target.length-targetStart<end-start){end=target.length-targetStart+start;}var len=end-start;if(this===target&&typeof Uint8Array.prototype.copyWithin==='function'){// Use built-in when available, missing from IE11
this.copyWithin(targetStart,start,end);}else if(this===target&&start<targetStart&&targetStart<end){// descending copy from end
for(var i=len-1;i>=0;--i){target[i+targetStart]=this[i+start];}}else{Uint8Array.prototype.set.call(target,this.subarray(start,end),targetStart);}return len;};// Usage:
//    buffer.fill(number[, offset[, end]])
//    buffer.fill(buffer[, offset[, end]])
//    buffer.fill(string[, offset[, end]][, encoding])
Buffer.prototype.fill=function fill(val,start,end,encoding){// Handle string cases:
if(typeof val==='string'){if(typeof start==='string'){encoding=start;start=0;end=this.length;}else if(typeof end==='string'){encoding=end;end=this.length;}if(encoding!==undefined&&typeof encoding!=='string'){throw new TypeError('encoding must be a string');}if(typeof encoding==='string'&&!Buffer.isEncoding(encoding)){throw new TypeError('Unknown encoding: '+encoding);}if(val.length===1){var code=val.charCodeAt(0);if(encoding==='utf8'&&code<128||encoding==='latin1'){// Fast path: If `val` fits into a single byte, use that numeric value.
val=code;}}}else if(typeof val==='number'){val=val&255;}// Invalid ranges are not set to a default, so can range check early.
if(start<0||this.length<start||this.length<end){throw new RangeError('Out of range index');}if(end<=start){return this;}start=start>>>0;end=end===undefined?this.length:end>>>0;if(!val)val=0;var i;if(typeof val==='number'){for(i=start;i<end;++i){this[i]=val;}}else{var bytes=Buffer.isBuffer(val)?val:Buffer.from(val,encoding);var len=bytes.length;if(len===0){throw new TypeError('The value "'+val+'" is invalid for argument "value"');}for(i=0;i<end-start;++i){this[i+start]=bytes[i%len];}}return this;};// HELPER FUNCTIONS
// ================
var INVALID_BASE64_RE=/[^+/0-9A-Za-z-_]/g;function base64clean(str){// Node takes equal signs as end of the Base64 encoding
str=str.split('=')[0];// Node strips out invalid characters like \n and \t from the string, base64-js does not
str=str.trim().replace(INVALID_BASE64_RE,'');// Node converts strings with length < 2 to ''
if(str.length<2)return'';// Node allows for non-padded base64 strings (missing trailing ===), base64-js does not
while(str.length%4!==0){str=str+'=';}return str;}function toHex(n){if(n<16)return'0'+n.toString(16);return n.toString(16);}function utf8ToBytes(string,units){units=units||Infinity;var codePoint;var length=string.length;var leadSurrogate=null;var bytes=[];for(var i=0;i<length;++i){codePoint=string.charCodeAt(i);// is surrogate component
if(codePoint>0xD7FF&&codePoint<0xE000){// last char was a lead
if(!leadSurrogate){// no lead yet
if(codePoint>0xDBFF){// unexpected trail
if((units-=3)>-1)bytes.push(0xEF,0xBF,0xBD);continue;}else if(i+1===length){// unpaired lead
if((units-=3)>-1)bytes.push(0xEF,0xBF,0xBD);continue;}// valid lead
leadSurrogate=codePoint;continue;}// 2 leads in a row
if(codePoint<0xDC00){if((units-=3)>-1)bytes.push(0xEF,0xBF,0xBD);leadSurrogate=codePoint;continue;}// valid surrogate pair
codePoint=(leadSurrogate-0xD800<<10|codePoint-0xDC00)+0x10000;}else if(leadSurrogate){// valid bmp char, but last char was a lead
if((units-=3)>-1)bytes.push(0xEF,0xBF,0xBD);}leadSurrogate=null;// encode utf8
if(codePoint<0x80){if((units-=1)<0)break;bytes.push(codePoint);}else if(codePoint<0x800){if((units-=2)<0)break;bytes.push(codePoint>>0x6|0xC0,codePoint&0x3F|0x80);}else if(codePoint<0x10000){if((units-=3)<0)break;bytes.push(codePoint>>0xC|0xE0,codePoint>>0x6&0x3F|0x80,codePoint&0x3F|0x80);}else if(codePoint<0x110000){if((units-=4)<0)break;bytes.push(codePoint>>0x12|0xF0,codePoint>>0xC&0x3F|0x80,codePoint>>0x6&0x3F|0x80,codePoint&0x3F|0x80);}else{throw new Error('Invalid code point');}}return bytes;}function asciiToBytes(str){var byteArray=[];for(var i=0;i<str.length;++i){// Node's code seems to be doing this and not & 0x7F..
byteArray.push(str.charCodeAt(i)&0xFF);}return byteArray;}function utf16leToBytes(str,units){var c,hi,lo;var byteArray=[];for(var i=0;i<str.length;++i){if((units-=2)<0)break;c=str.charCodeAt(i);hi=c>>8;lo=c%256;byteArray.push(lo);byteArray.push(hi);}return byteArray;}function base64ToBytes(str){return base64.toByteArray(base64clean(str));}function blitBuffer(src,dst,offset,length){for(var i=0;i<length;++i){if(i+offset>=dst.length||i>=src.length)break;dst[i+offset]=src[i];}return i;}// ArrayBuffer or Uint8Array objects from other contexts (i.e. iframes) do not pass
// the `instanceof` check but they should be treated as of that type.
// See: https://github.com/feross/buffer/issues/166
function isInstance(obj,type){return obj instanceof type||obj!=null&&obj.constructor!=null&&obj.constructor.name!=null&&obj.constructor.name===type.name;}function numberIsNaN(obj){// For IE11 support
return obj!==obj;// eslint-disable-line no-self-compare
}}).call(this,require("buffer").Buffer);},{"base64-js":1,"buffer":3,"ieee754":32}],4:[function(require,module,exports){"use strict";Object.defineProperty(exports,"__esModule",{value:true});exports.attributeNames=exports.elementNames=void 0;exports.elementNames=new Map([["altglyph","altGlyph"],["altglyphdef","altGlyphDef"],["altglyphitem","altGlyphItem"],["animatecolor","animateColor"],["animatemotion","animateMotion"],["animatetransform","animateTransform"],["clippath","clipPath"],["feblend","feBlend"],["fecolormatrix","feColorMatrix"],["fecomponenttransfer","feComponentTransfer"],["fecomposite","feComposite"],["feconvolvematrix","feConvolveMatrix"],["fediffuselighting","feDiffuseLighting"],["fedisplacementmap","feDisplacementMap"],["fedistantlight","feDistantLight"],["fedropshadow","feDropShadow"],["feflood","feFlood"],["fefunca","feFuncA"],["fefuncb","feFuncB"],["fefuncg","feFuncG"],["fefuncr","feFuncR"],["fegaussianblur","feGaussianBlur"],["feimage","feImage"],["femerge","feMerge"],["femergenode","feMergeNode"],["femorphology","feMorphology"],["feoffset","feOffset"],["fepointlight","fePointLight"],["fespecularlighting","feSpecularLighting"],["fespotlight","feSpotLight"],["fetile","feTile"],["feturbulence","feTurbulence"],["foreignobject","foreignObject"],["glyphref","glyphRef"],["lineargradient","linearGradient"],["radialgradient","radialGradient"],["textpath","textPath"]]);exports.attributeNames=new Map([["definitionurl","definitionURL"],["attributename","attributeName"],["attributetype","attributeType"],["basefrequency","baseFrequency"],["baseprofile","baseProfile"],["calcmode","calcMode"],["clippathunits","clipPathUnits"],["diffuseconstant","diffuseConstant"],["edgemode","edgeMode"],["filterunits","filterUnits"],["glyphref","glyphRef"],["gradienttransform","gradientTransform"],["gradientunits","gradientUnits"],["kernelmatrix","kernelMatrix"],["kernelunitlength","kernelUnitLength"],["keypoints","keyPoints"],["keysplines","keySplines"],["keytimes","keyTimes"],["lengthadjust","lengthAdjust"],["limitingconeangle","limitingConeAngle"],["markerheight","markerHeight"],["markerunits","markerUnits"],["markerwidth","markerWidth"],["maskcontentunits","maskContentUnits"],["maskunits","maskUnits"],["numoctaves","numOctaves"],["pathlength","pathLength"],["patterncontentunits","patternContentUnits"],["patterntransform","patternTransform"],["patternunits","patternUnits"],["pointsatx","pointsAtX"],["pointsaty","pointsAtY"],["pointsatz","pointsAtZ"],["preservealpha","preserveAlpha"],["preserveaspectratio","preserveAspectRatio"],["primitiveunits","primitiveUnits"],["refx","refX"],["refy","refY"],["repeatcount","repeatCount"],["repeatdur","repeatDur"],["requiredextensions","requiredExtensions"],["requiredfeatures","requiredFeatures"],["specularconstant","specularConstant"],["specularexponent","specularExponent"],["spreadmethod","spreadMethod"],["startoffset","startOffset"],["stddeviation","stdDeviation"],["stitchtiles","stitchTiles"],["surfacescale","surfaceScale"],["systemlanguage","systemLanguage"],["tablevalues","tableValues"],["targetx","targetX"],["targety","targetY"],["textlength","textLength"],["viewbox","viewBox"],["viewtarget","viewTarget"],["xchannelselector","xChannelSelector"],["ychannelselector","yChannelSelector"],["zoomandpan","zoomAndPan"]]);},{}],5:[function(require,module,exports){"use strict";var __assign=this&&this.__assign||function(){__assign=Object.assign||function(t){for(var s,i=1,n=arguments.length;i<n;i++){s=arguments[i];for(var p in s){if(Object.prototype.hasOwnProperty.call(s,p))t[p]=s[p];}}return t;};return __assign.apply(this,arguments);};var __createBinding=this&&this.__createBinding||(Object.create?function(o,m,k,k2){if(k2===undefined)k2=k;Object.defineProperty(o,k2,{enumerable:true,get:function get(){return m[k];}});}:function(o,m,k,k2){if(k2===undefined)k2=k;o[k2]=m[k];});var __setModuleDefault=this&&this.__setModuleDefault||(Object.create?function(o,v){Object.defineProperty(o,"default",{enumerable:true,value:v});}:function(o,v){o["default"]=v;});var __importStar=this&&this.__importStar||function(mod){if(mod&&mod.__esModule)return mod;var result={};if(mod!=null)for(var k in mod){if(k!=="default"&&Object.prototype.hasOwnProperty.call(mod,k))__createBinding(result,mod,k);}__setModuleDefault(result,mod);return result;};Object.defineProperty(exports,"__esModule",{value:true});/*
 * Module dependencies
 */var ElementType=__importStar(require("domelementtype"));var entities_1=require("entities");/*
 * Mixed-case SVG and MathML tags & attributes
 * recognized by the HTML parser, see
 * https://html.spec.whatwg.org/multipage/parsing.html#parsing-main-inforeign
 */var foreignNames_1=require("./foreignNames");var unencodedElements=new Set(["style","script","xmp","iframe","noembed","noframes","plaintext","noscript"]);/**
 * Format attributes
 */function formatAttributes(attributes,opts){if(!attributes)return;return Object.keys(attributes).map(function(key){var _a,_b;var value=(_a=attributes[key])!==null&&_a!==void 0?_a:"";if(opts.xmlMode==="foreign"){/* Fix up mixed-case attribute names */key=(_b=foreignNames_1.attributeNames.get(key))!==null&&_b!==void 0?_b:key;}if(!opts.emptyAttrs&&!opts.xmlMode&&value===""){return key;}return key+"=\""+(opts.decodeEntities?entities_1.encodeXML(value):value.replace(/"/g,"&quot;"))+"\"";}).join(" ");}/**
 * Self-enclosing tags
 */var singleTag=new Set(["area","base","basefont","br","col","command","embed","frame","hr","img","input","isindex","keygen","link","meta","param","source","track","wbr"]);/**
 * Renders a DOM node or an array of DOM nodes to a string.
 *
 * Can be thought of as the equivalent of the `outerHTML` of the passed node(s).
 *
 * @param node Node to be rendered.
 * @param options Changes serialization behavior
 */function render(node,options){if(options===void 0){options={};}// TODO: This is a bit hacky.
var nodes=Array.isArray(node)||node.cheerio?node:[node];var output="";for(var i=0;i<nodes.length;i++){output+=renderNode(nodes[i],options);}return output;}exports["default"]=render;function renderNode(node,options){switch(node.type){case"root":return render(node.children,options);case ElementType.Directive:return renderDirective(node);case ElementType.Comment:return renderComment(node);case ElementType.CDATA:return renderCdata(node);default:return ElementType.isTag(node)?renderTag(node,options):renderText(node,options);}}var foreignModeIntegrationPoints=new Set(["mi","mo","mn","ms","mtext","annotation-xml","foreignObject","desc","title"]);var foreignElements=new Set(["svg","math"]);function renderTag(elem,opts){var _a;// Handle SVG / MathML in HTML
if(opts.xmlMode==="foreign"){/* Fix up mixed-case element names */elem.name=(_a=foreignNames_1.elementNames.get(elem.name))!==null&&_a!==void 0?_a:elem.name;/* Exit foreign mode at integration points */if(elem.parent&&foreignModeIntegrationPoints.has(elem.parent.name)){opts=__assign(__assign({},opts),{xmlMode:false});}}if(!opts.xmlMode&&foreignElements.has(elem.name)){opts=__assign(__assign({},opts),{xmlMode:"foreign"});}var tag="<"+elem.name;var attribs=formatAttributes(elem.attribs,opts);if(attribs){tag+=" "+attribs;}if(elem.children.length===0&&(opts.xmlMode?// In XML mode or foreign mode, and user hasn't explicitly turned off self-closing tags
opts.selfClosingTags!==false:// User explicitly asked for self-closing tags, even in HTML mode
opts.selfClosingTags&&singleTag.has(elem.name))){if(!opts.xmlMode)tag+=" ";tag+="/>";}else{tag+=">";if(elem.children.length>0){tag+=render(elem.children,opts);}if(opts.xmlMode||!singleTag.has(elem.name)){tag+="</"+elem.name+">";}}return tag;}function renderDirective(elem){return"<"+elem.data+">";}function renderText(elem,opts){var data=elem.data||"";// If entities weren't decoded, no need to encode them back
if(opts.decodeEntities&&!(elem.parent&&unencodedElements.has(elem.parent.name))){data=entities_1.encodeXML(data);}return data;}function renderCdata(elem){return"<![CDATA["+elem.children[0].data+"]]>";}function renderComment(elem){return"<!--"+elem.data+"-->";}},{"./foreignNames":4,"domelementtype":6,"entities":20}],6:[function(require,module,exports){"use strict";Object.defineProperty(exports,"__esModule",{value:true});exports.Doctype=exports.CDATA=exports.Tag=exports.Style=exports.Script=exports.Comment=exports.Directive=exports.Text=exports.isTag=void 0;/**
 * Tests whether an element is a tag or not.
 *
 * @param elem Element to test
 */function isTag(elem){return elem.type==="tag"/* Tag */||elem.type==="script"/* Script */||elem.type==="style"/* Style */;}exports.isTag=isTag;// Exports for backwards compatibility
/** Type for Text */exports.Text="text"/* Text */;/** Type for <? ... ?> */exports.Directive="directive"/* Directive */;/** Type for <!-- ... --> */exports.Comment="comment"/* Comment */;/** Type for <script> tags */exports.Script="script"/* Script */;/** Type for <style> tags */exports.Style="style"/* Style */;/** Type for Any tag */exports.Tag="tag"/* Tag */;/** Type for <![CDATA[ ... ]]> */exports.CDATA="cdata"/* CDATA */;/** Type for <!doctype ...> */exports.Doctype="doctype"/* Doctype */;},{}],7:[function(require,module,exports){"use strict";Object.defineProperty(exports,"__esModule",{value:true});var node_1=require("./node");exports.Node=node_1.Node;exports.Element=node_1.Element;exports.DataNode=node_1.DataNode;exports.NodeWithChildren=node_1.NodeWithChildren;var reWhitespace=/\s+/g;// Default options
var defaultOpts={normalizeWhitespace:false,withStartIndices:false,withEndIndices:false};var DomHandler=/** @class */function(){/**
     * Initiate a new DomHandler.
     *
     * @param callback Called once parsing has completed.
     * @param options Settings for the handler.
     * @param elementCB Callback whenever a tag is closed.
     */function DomHandler(callback,options,elementCB){/** The constructed DOM */this.dom=[];/** Indicated whether parsing has been completed. */this._done=false;/** Stack of open tags. */this._tagStack=[];/** A data node that is still being written to. */this._lastNode=null;/** Reference to the parser instance. Used for location information. */this._parser=null;// Make it possible to skip arguments, for backwards-compatibility
if(typeof options==="function"){elementCB=options;options=defaultOpts;}if(_typeof(callback)==="object"){options=callback;callback=undefined;}this._callback=callback||null;this._options=options||defaultOpts;this._elementCB=elementCB||null;}DomHandler.prototype.onparserinit=function(parser){this._parser=parser;};// Resets the handler back to starting state
DomHandler.prototype.onreset=function(){this.dom=[];this._done=false;this._tagStack=[];this._lastNode=null;this._parser=this._parser||null;};// Signals the handler that parsing is done
DomHandler.prototype.onend=function(){if(this._done)return;this._done=true;this._parser=null;this.handleCallback(null);};DomHandler.prototype.onerror=function(error){this.handleCallback(error);};DomHandler.prototype.onclosetag=function(){this._lastNode=null;// If(this._tagStack.pop().name !== name) this.handleCallback(Error("Tagname didn't match!"));
var elem=this._tagStack.pop();if(!elem||!this._parser){return;}if(this._options.withEndIndices){elem.endIndex=this._parser.endIndex;}if(this._elementCB)this._elementCB(elem);};DomHandler.prototype.onopentag=function(name,attribs){var element=new node_1.Element(name,attribs);this.addNode(element);this._tagStack.push(element);};DomHandler.prototype.ontext=function(data){var normalize=this._options.normalizeWhitespace;var _lastNode=this._lastNode;if(_lastNode&&_lastNode.type==="text"/* Text */){if(normalize){_lastNode.data=(_lastNode.data+data).replace(reWhitespace," ");}else{_lastNode.data+=data;}}else{if(normalize){data=data.replace(reWhitespace," ");}var node=new node_1.DataNode("text"/* Text */,data);this.addNode(node);this._lastNode=node;}};DomHandler.prototype.oncomment=function(data){if(this._lastNode&&this._lastNode.type==="comment"/* Comment */){this._lastNode.data+=data;return;}var node=new node_1.DataNode("comment"/* Comment */,data);this.addNode(node);this._lastNode=node;};DomHandler.prototype.oncommentend=function(){this._lastNode=null;};DomHandler.prototype.oncdatastart=function(){var text=new node_1.DataNode("text"/* Text */,"");var node=new node_1.NodeWithChildren("cdata"/* CDATA */,[text]);this.addNode(node);text.parent=node;this._lastNode=text;};DomHandler.prototype.oncdataend=function(){this._lastNode=null;};DomHandler.prototype.onprocessinginstruction=function(name,data){var node=new node_1.ProcessingInstruction(name,data);this.addNode(node);};DomHandler.prototype.handleCallback=function(error){if(typeof this._callback==="function"){this._callback(error,this.dom);}else if(error){throw error;}};DomHandler.prototype.addNode=function(node){var parent=this._tagStack[this._tagStack.length-1];var siblings=parent?parent.children:this.dom;var previousSibling=siblings[siblings.length-1];if(this._parser){if(this._options.withStartIndices){node.startIndex=this._parser.startIndex;}if(this._options.withEndIndices){node.endIndex=this._parser.endIndex;}}siblings.push(node);if(previousSibling){node.prev=previousSibling;previousSibling.next=node;}if(parent){node.parent=parent;}this._lastNode=null;};DomHandler.prototype.addDataNode=function(node){this.addNode(node);this._lastNode=node;};return DomHandler;}();exports.DomHandler=DomHandler;exports["default"]=DomHandler;},{"./node":8}],8:[function(require,module,exports){"use strict";var __extends=this&&this.__extends||function(){var _extendStatics=function extendStatics(d,b){_extendStatics=Object.setPrototypeOf||{__proto__:[]}instanceof Array&&function(d,b){d.__proto__=b;}||function(d,b){for(var p in b){if(b.hasOwnProperty(p))d[p]=b[p];}};return _extendStatics(d,b);};return function(d,b){_extendStatics(d,b);function __(){this.constructor=d;}d.prototype=b===null?Object.create(b):(__.prototype=b.prototype,new __());};}();Object.defineProperty(exports,"__esModule",{value:true});var nodeTypes=new Map([["tag"/* Tag */,1],["script"/* Script */,1],["style"/* Style */,1],["directive"/* Directive */,1],["text"/* Text */,3],["cdata"/* CDATA */,4],["comment"/* Comment */,8]]);// This object will be used as the prototype for Nodes when creating a
// DOM-Level-1-compliant structure.
var Node=/** @class */function(){/**
     *
     * @param type The type of the node.
     */function Node(type){this.type=type;/** Parent of the node */this.parent=null;/** Previous sibling */this.prev=null;/** Next sibling */this.next=null;/** The start index of the node. Requires `withStartIndices` on the handler to be `true. */this.startIndex=null;/** The end index of the node. Requires `withEndIndices` on the handler to be `true. */this.endIndex=null;}Object.defineProperty(Node.prototype,"nodeType",{// Read-only aliases
get:function get(){return nodeTypes.get(this.type)||1;},enumerable:true,configurable:true});Object.defineProperty(Node.prototype,"parentNode",{// Read-write aliases for properties
get:function get(){return this.parent||null;},set:function set(parent){this.parent=parent;},enumerable:true,configurable:true});Object.defineProperty(Node.prototype,"previousSibling",{get:function get(){return this.prev||null;},set:function set(prev){this.prev=prev;},enumerable:true,configurable:true});Object.defineProperty(Node.prototype,"nextSibling",{get:function get(){return this.next||null;},set:function set(next){this.next=next;},enumerable:true,configurable:true});return Node;}();exports.Node=Node;var DataNode=/** @class */function(_super){__extends(DataNode,_super);/**
     *
     * @param type The type of the node
     * @param data The content of the data node
     */function DataNode(type,data){var _this=_super.call(this,type)||this;_this.data=data;return _this;}Object.defineProperty(DataNode.prototype,"nodeValue",{get:function get(){return this.data;},set:function set(data){this.data=data;},enumerable:true,configurable:true});return DataNode;}(Node);exports.DataNode=DataNode;var ProcessingInstruction=/** @class */function(_super){__extends(ProcessingInstruction,_super);function ProcessingInstruction(name,data){var _this=_super.call(this,"directive"/* Directive */,data)||this;_this.name=name;return _this;}return ProcessingInstruction;}(DataNode);exports.ProcessingInstruction=ProcessingInstruction;var NodeWithChildren=/** @class */function(_super){__extends(NodeWithChildren,_super);/**
     *
     * @param type Type of the node.
     * @param children Children of the node. Only certain node types can have children.
     */function NodeWithChildren(type,children){var _this=_super.call(this,type)||this;_this.children=children;return _this;}Object.defineProperty(NodeWithChildren.prototype,"firstChild",{// Aliases
get:function get(){return this.children[0]||null;},enumerable:true,configurable:true});Object.defineProperty(NodeWithChildren.prototype,"lastChild",{get:function get(){return this.children[this.children.length-1]||null;},enumerable:true,configurable:true});Object.defineProperty(NodeWithChildren.prototype,"childNodes",{get:function get(){return this.children;},set:function set(children){this.children=children;},enumerable:true,configurable:true});return NodeWithChildren;}(Node);exports.NodeWithChildren=NodeWithChildren;var Element=/** @class */function(_super){__extends(Element,_super);/**
     *
     * @param name Name of the tag, eg. `div`, `span`
     * @param attribs Object mapping attribute names to attribute values
     */function Element(name,attribs){var _this=_super.call(this,name==="script"?"script"/* Script */:name==="style"?"style"/* Style */:"tag"/* Tag */,[])||this;_this.name=name;_this.attribs=attribs;_this.attribs=attribs;return _this;}Object.defineProperty(Element.prototype,"tagName",{// DOM Level 1 aliases
get:function get(){return this.name;},set:function set(name){this.name=name;},enumerable:true,configurable:true});return Element;}(NodeWithChildren);exports.Element=Element;},{}],9:[function(require,module,exports){"use strict";Object.defineProperty(exports,"__esModule",{value:true});exports.uniqueSort=exports.compareDocumentPosition=exports.removeSubsets=void 0;var tagtypes_1=require("./tagtypes");/**
 * Given an array of nodes, remove any member that is contained by another.
 *
 * @param nodes Nodes to filter.
 */function removeSubsets(nodes){var idx=nodes.length;/*
     * Check if each node (or one of its ancestors) is already contained in the
     * array.
     */while(--idx>=0){var node=nodes[idx];/*
         * Remove the node if it is not unique.
         * We are going through the array from the end, so we only
         * have to check nodes that preceed the node under consideration in the array.
         */if(idx>0&&nodes.lastIndexOf(node,idx-1)>=0){nodes.splice(idx,1);continue;}for(var ancestor=node.parent;ancestor;ancestor=ancestor.parent){if(nodes.includes(ancestor)){nodes.splice(idx,1);break;}}}return nodes;}exports.removeSubsets=removeSubsets;/**
 * Compare the position of one node against another node in any other document.
 * The return value is a bitmask with the following values:
 *
 * document order:
 * > There is an ordering, document order, defined on all the nodes in the
 * > document corresponding to the order in which the first character of the
 * > XML representation of each node occurs in the XML representation of the
 * > document after expansion of general entities. Thus, the document element
 * > node will be the first node. Element nodes occur before their children.
 * > Thus, document order orders element nodes in order of the occurrence of
 * > their start-tag in the XML (after expansion of entities). The attribute
 * > nodes of an element occur after the element and before its children. The
 * > relative order of attribute nodes is implementation-dependent./
 *
 * Source:
 * http://www.w3.org/TR/DOM-Level-3-Core/glossary.html#dt-document-order
 * @param nodaA The first node to use in the comparison
 * @param nodeB The second node to use in the comparison
 *
 * @return A bitmask describing the input nodes' relative position.
 *
 *        See http://dom.spec.whatwg.org/#dom-node-comparedocumentposition for
 *        a description of these values.
 */function compareDocumentPosition(nodeA,nodeB){var aParents=[];var bParents=[];if(nodeA===nodeB){return 0;}var current=tagtypes_1.hasChildren(nodeA)?nodeA:nodeA.parent;while(current){aParents.unshift(current);current=current.parent;}current=tagtypes_1.hasChildren(nodeB)?nodeB:nodeB.parent;while(current){bParents.unshift(current);current=current.parent;}var maxIdx=Math.min(aParents.length,bParents.length);var idx=0;while(idx<maxIdx&&aParents[idx]===bParents[idx]){idx++;}if(idx===0){return 1/* DISCONNECTED */;}var sharedParent=aParents[idx-1];var siblings=sharedParent.children;var aSibling=aParents[idx];var bSibling=bParents[idx];if(siblings.indexOf(aSibling)>siblings.indexOf(bSibling)){if(sharedParent===nodeB){return 4/* FOLLOWING */|16/* CONTAINED_BY */;}return 4/* FOLLOWING */;}if(sharedParent===nodeA){return 2/* PRECEDING */|8/* CONTAINS */;}return 2/* PRECEDING */;}exports.compareDocumentPosition=compareDocumentPosition;/**
 * Sort an array of nodes based on their relative position in the document and
 * remove any duplicate nodes. If the array contains nodes that do not belong
 * to the same document, sort order is unspecified.
 *
 * @param nodes Array of DOM nodes
 * @returns collection of unique nodes, sorted in document order
 */function uniqueSort(nodes){nodes=nodes.filter(function(node,i,arr){return!arr.includes(node,i+1);});nodes.sort(function(a,b){var relative=compareDocumentPosition(a,b);if(relative&2/* PRECEDING */){return-1;}else if(relative&4/* FOLLOWING */){return 1;}return 0;});return nodes;}exports.uniqueSort=uniqueSort;},{"./tagtypes":15}],10:[function(require,module,exports){"use strict";var __createBinding=this&&this.__createBinding||(Object.create?function(o,m,k,k2){if(k2===undefined)k2=k;Object.defineProperty(o,k2,{enumerable:true,get:function get(){return m[k];}});}:function(o,m,k,k2){if(k2===undefined)k2=k;o[k2]=m[k];});var __exportStar=this&&this.__exportStar||function(m,exports){for(var p in m){if(p!=="default"&&!Object.prototype.hasOwnProperty.call(exports,p))__createBinding(exports,m,p);}};Object.defineProperty(exports,"__esModule",{value:true});__exportStar(require("./stringify"),exports);__exportStar(require("./traversal"),exports);__exportStar(require("./manipulation"),exports);__exportStar(require("./querying"),exports);__exportStar(require("./legacy"),exports);__exportStar(require("./helpers"),exports);__exportStar(require("./tagtypes"),exports);},{"./helpers":9,"./legacy":11,"./manipulation":12,"./querying":13,"./stringify":14,"./tagtypes":15,"./traversal":16}],11:[function(require,module,exports){"use strict";Object.defineProperty(exports,"__esModule",{value:true});exports.getElementsByTagType=exports.getElementsByTagName=exports.getElementById=exports.getElements=exports.testElement=void 0;var querying_1=require("./querying");var tagtypes_1=require("./tagtypes");function isTextNode(node){return node.type==="text"/* Text */;}var Checks={tag_name:function tag_name(name){if(typeof name==="function"){return function(elem){return tagtypes_1.isTag(elem)&&name(elem.name);};}else if(name==="*"){return tagtypes_1.isTag;}return function(elem){return tagtypes_1.isTag(elem)&&elem.name===name;};},tag_type:function tag_type(type){if(typeof type==="function"){return function(elem){return type(elem.type);};}return function(elem){return elem.type===type;};},tag_contains:function tag_contains(data){if(typeof data==="function"){return function(elem){return isTextNode(elem)&&data(elem.data);};}return function(elem){return isTextNode(elem)&&elem.data===data;};}};function getAttribCheck(attrib,value){if(typeof value==="function"){return function(elem){return tagtypes_1.isTag(elem)&&value(elem.attribs[attrib]);};}return function(elem){return tagtypes_1.isTag(elem)&&elem.attribs[attrib]===value;};}function combineFuncs(a,b){return function(elem){return a(elem)||b(elem);};}function compileTest(options){var funcs=Object.keys(options).map(function(key){var value=options[key];return key in Checks?Checks[key](value):getAttribCheck(key,value);});return funcs.length===0?null:funcs.reduce(combineFuncs);}function testElement(options,element){var test=compileTest(options);return test?test(element):true;}exports.testElement=testElement;function getElements(options,element,recurse,limit){if(limit===void 0){limit=Infinity;}var test=compileTest(options);return test?querying_1.filter(test,element,recurse,limit):[];}exports.getElements=getElements;function getElementById(id,element,recurse){if(recurse===void 0){recurse=true;}if(!Array.isArray(element))element=[element];return querying_1.findOne(getAttribCheck("id",id),element,recurse);}exports.getElementById=getElementById;function getElementsByTagName(name,element,recurse,limit){if(limit===void 0){limit=Infinity;}return querying_1.filter(Checks.tag_name(name),element,recurse,limit);}exports.getElementsByTagName=getElementsByTagName;function getElementsByTagType(type,element,recurse,limit){if(recurse===void 0){recurse=true;}if(limit===void 0){limit=Infinity;}return querying_1.filter(Checks.tag_type(type),element,recurse,limit);}exports.getElementsByTagType=getElementsByTagType;},{"./querying":13,"./tagtypes":15}],12:[function(require,module,exports){"use strict";Object.defineProperty(exports,"__esModule",{value:true});exports.prepend=exports.append=exports.appendChild=exports.replaceElement=exports.removeElement=void 0;/**
 * Remove an element from the dom
 *
 * @param elem The element to be removed
 */function removeElement(elem){if(elem.prev)elem.prev.next=elem.next;if(elem.next)elem.next.prev=elem.prev;if(elem.parent){var childs=elem.parent.children;childs.splice(childs.lastIndexOf(elem),1);}}exports.removeElement=removeElement;/**
 * Replace an element in the dom
 *
 * @param elem The element to be replaced
 * @param replacement The element to be added
 */function replaceElement(elem,replacement){var prev=replacement.prev=elem.prev;if(prev){prev.next=replacement;}var next=replacement.next=elem.next;if(next){next.prev=replacement;}var parent=replacement.parent=elem.parent;if(parent){var childs=parent.children;childs[childs.lastIndexOf(elem)]=replacement;}}exports.replaceElement=replaceElement;/**
 * Append a child to an element
 *
 * @param elem The element to append to
 * @param child The element to be added as a child
 */function appendChild(elem,child){removeElement(child);child.parent=elem;if(elem.children.push(child)!==1){var sibling=elem.children[elem.children.length-2];sibling.next=child;child.prev=sibling;child.next=null;}}exports.appendChild=appendChild;/**
 * Append an element after another
 *
 * @param elem The element to append to
 * @param next The element be added
 */function append(elem,next){removeElement(next);var parent=elem.parent;var currNext=elem.next;next.next=currNext;next.prev=elem;elem.next=next;next.parent=parent;if(currNext){currNext.prev=next;if(parent){var childs=parent.children;childs.splice(childs.lastIndexOf(currNext),0,next);}}else if(parent){parent.children.push(next);}}exports.append=append;/**
 * Prepend an element before another
 *
 * @param elem The element to append to
 * @param prev The element be added
 */function prepend(elem,prev){var parent=elem.parent;if(parent){var childs=parent.children;childs.splice(childs.lastIndexOf(elem),0,prev);}if(elem.prev){elem.prev.next=prev;}prev.parent=parent;prev.prev=elem.prev;prev.next=elem;elem.prev=prev;}exports.prepend=prepend;},{}],13:[function(require,module,exports){"use strict";Object.defineProperty(exports,"__esModule",{value:true});exports.findAll=exports.existsOne=exports.findOne=exports.findOneChild=exports.find=exports.filter=void 0;var tagtypes_1=require("./tagtypes");/**
 * Search a node and its children for nodes passing a test function.
 *
 * @param test Function to test nodes on.
 * @param element Element to search. Will be included in the result set if it matches.
 * @param recurse Also consider child nodes.
 * @param limit Maximum number of nodes to return.
 */function filter(test,node,recurse,limit){if(recurse===void 0){recurse=true;}if(limit===void 0){limit=Infinity;}if(!Array.isArray(node))node=[node];return find(test,node,recurse,limit);}exports.filter=filter;/**
 * Like `filter`, but only works on an array of nodes.
 *
 * @param test Function to test nodes on.
 * @param nodes Array of nodes to search.
 * @param recurse Also consider child nodes.
 * @param limit Maximum number of nodes to return.
 */function find(test,nodes,recurse,limit){var result=[];for(var _i=0,nodes_1=nodes;_i<nodes_1.length;_i++){var elem=nodes_1[_i];if(test(elem)){result.push(elem);if(--limit<=0)break;}if(recurse&&tagtypes_1.hasChildren(elem)&&elem.children.length>0){var children=find(test,elem.children,recurse,limit);result.push.apply(result,children);limit-=children.length;if(limit<=0)break;}}return result;}exports.find=find;/**
 * Finds the first element inside of an array that matches a test function.
 *
 * @param test Function to test nodes on.
 * @param nodes Array of nodes to search.
 */function findOneChild(test,nodes){return nodes.find(test);}exports.findOneChild=findOneChild;/**
 * Finds one element in a tree that passes a test.
 *
 * @param test Function to test nodes on.
 * @param nodes Array of nodes to search.
 * @param recurse Also consider child nodes.
 */function findOne(test,nodes,recurse){if(recurse===void 0){recurse=true;}var elem=null;for(var i=0;i<nodes.length&&!elem;i++){var checked=nodes[i];if(!tagtypes_1.isTag(checked)){continue;}else if(test(checked)){elem=checked;}else if(recurse&&checked.children.length>0){elem=findOne(test,checked.children);}}return elem;}exports.findOne=findOne;/**
 * Returns whether a tree of nodes contains at least one node passing a test.
 *
 * @param test Function to test nodes on.
 * @param nodes Array of nodes to search.
 */function existsOne(test,nodes){return nodes.some(function(checked){return tagtypes_1.isTag(checked)&&(test(checked)||checked.children.length>0&&existsOne(test,checked.children));});}exports.existsOne=existsOne;/**
 * Search and array of nodes and its children for nodes passing a test function.
 *
 * Same as `find`, only with less options, leading to reduced complexity.
 *
 * @param test Function to test nodes on.
 * @param nodes Array of nodes to search.
 */function findAll(test,nodes){var _a;var result=[];var stack=nodes.filter(tagtypes_1.isTag);var elem;while(elem=stack.shift()){var children=(_a=elem.children)===null||_a===void 0?void 0:_a.filter(tagtypes_1.isTag);if(children&&children.length>0){stack.unshift.apply(stack,children);}if(test(elem))result.push(elem);}return result;}exports.findAll=findAll;},{"./tagtypes":15}],14:[function(require,module,exports){"use strict";var __importDefault=this&&this.__importDefault||function(mod){return mod&&mod.__esModule?mod:{"default":mod};};Object.defineProperty(exports,"__esModule",{value:true});exports.getText=exports.getInnerHTML=exports.getOuterHTML=void 0;var tagtypes_1=require("./tagtypes");var dom_serializer_1=__importDefault(require("dom-serializer"));function getOuterHTML(node,options){return dom_serializer_1["default"](node,options);}exports.getOuterHTML=getOuterHTML;function getInnerHTML(node,options){return tagtypes_1.hasChildren(node)?node.children.map(function(node){return getOuterHTML(node,options);}).join(""):"";}exports.getInnerHTML=getInnerHTML;function getText(node){if(Array.isArray(node))return node.map(getText).join("");if(tagtypes_1.isTag(node))return node.name==="br"?"\n":getText(node.children);if(tagtypes_1.isCDATA(node))return getText(node.children);if(tagtypes_1.isText(node))return node.data;return"";}exports.getText=getText;},{"./tagtypes":15,"dom-serializer":5}],15:[function(require,module,exports){"use strict";Object.defineProperty(exports,"__esModule",{value:true});exports.hasChildren=exports.isComment=exports.isText=exports.isCDATA=exports.isTag=void 0;var domelementtype_1=require("domelementtype");function isTag(node){return domelementtype_1.isTag(node);}exports.isTag=isTag;function isCDATA(node){return node.type==="cdata"/* CDATA */;}exports.isCDATA=isCDATA;function isText(node){return node.type==="text"/* Text */;}exports.isText=isText;function isComment(node){return node.type==="comment"/* Comment */;}exports.isComment=isComment;function hasChildren(node){return Object.prototype.hasOwnProperty.call(node,"children");}exports.hasChildren=hasChildren;},{"domelementtype":6}],16:[function(require,module,exports){"use strict";Object.defineProperty(exports,"__esModule",{value:true});exports.nextElementSibling=exports.getName=exports.hasAttrib=exports.getAttributeValue=exports.getSiblings=exports.getParent=exports.getChildren=void 0;function getChildren(elem){return elem.children||null;}exports.getChildren=getChildren;function getParent(elem){return elem.parent||null;}exports.getParent=getParent;function getSiblings(elem){var parent=getParent(elem);return parent?getChildren(parent):[elem];}exports.getSiblings=getSiblings;function getAttributeValue(elem,name){var _a;return(_a=elem.attribs)===null||_a===void 0?void 0:_a[name];}exports.getAttributeValue=getAttributeValue;function hasAttrib(elem,name){return!!elem.attribs&&Object.prototype.hasOwnProperty.call(elem.attribs,name)&&elem.attribs[name]!=null;}exports.hasAttrib=hasAttrib;/**
 * Returns the name property of an element
 *
 * @param elem The element to get the name for
 */function getName(elem){return elem.name;}exports.getName=getName;function nextElementSibling(elem){var node=elem.next;while(node!==null&&node.type!=="tag"){node=node.next;}return node;}exports.nextElementSibling=nextElementSibling;},{}],17:[function(require,module,exports){"use strict";var __importDefault=this&&this.__importDefault||function(mod){return mod&&mod.__esModule?mod:{"default":mod};};Object.defineProperty(exports,"__esModule",{value:true});exports.decodeHTML=exports.decodeHTMLStrict=exports.decodeXML=void 0;var entities_json_1=__importDefault(require("./maps/entities.json"));var legacy_json_1=__importDefault(require("./maps/legacy.json"));var xml_json_1=__importDefault(require("./maps/xml.json"));var decode_codepoint_1=__importDefault(require("./decode_codepoint"));exports.decodeXML=getStrictDecoder(xml_json_1["default"]);exports.decodeHTMLStrict=getStrictDecoder(entities_json_1["default"]);function getStrictDecoder(map){var keys=Object.keys(map).join("|");var replace=getReplacer(map);keys+="|#[xX][\\da-fA-F]+|#\\d+";var re=new RegExp("&(?:"+keys+");","g");return function(str){return String(str).replace(re,replace);};}var sorter=function sorter(a,b){return a<b?1:-1;};exports.decodeHTML=function(){var legacy=Object.keys(legacy_json_1["default"]).sort(sorter);var keys=Object.keys(entities_json_1["default"]).sort(sorter);for(var i=0,j=0;i<keys.length;i++){if(legacy[j]===keys[i]){keys[i]+=";?";j++;}else{keys[i]+=";";}}var re=new RegExp("&(?:"+keys.join("|")+"|#[xX][\\da-fA-F]+;?|#\\d+;?)","g");var replace=getReplacer(entities_json_1["default"]);function replacer(str){if(str.substr(-1)!==";")str+=";";return replace(str);}//TODO consider creating a merged map
return function(str){return String(str).replace(re,replacer);};}();function getReplacer(map){return function replace(str){if(str.charAt(1)==="#"){var secondChar=str.charAt(2);if(secondChar==="X"||secondChar==="x"){return decode_codepoint_1["default"](parseInt(str.substr(3),16));}return decode_codepoint_1["default"](parseInt(str.substr(2),10));}return map[str.slice(1,-1)];};}},{"./decode_codepoint":18,"./maps/entities.json":22,"./maps/legacy.json":23,"./maps/xml.json":24}],18:[function(require,module,exports){"use strict";var __importDefault=this&&this.__importDefault||function(mod){return mod&&mod.__esModule?mod:{"default":mod};};Object.defineProperty(exports,"__esModule",{value:true});var decode_json_1=__importDefault(require("./maps/decode.json"));// modified version of https://github.com/mathiasbynens/he/blob/master/src/he.js#L94-L119
function decodeCodePoint(codePoint){if(codePoint>=0xd800&&codePoint<=0xdfff||codePoint>0x10ffff){return"\uFFFD";}if(codePoint in decode_json_1["default"]){codePoint=decode_json_1["default"][codePoint];}var output="";if(codePoint>0xffff){codePoint-=0x10000;output+=String.fromCharCode(codePoint>>>10&0x3ff|0xd800);codePoint=0xdc00|codePoint&0x3ff;}output+=String.fromCharCode(codePoint);return output;}exports["default"]=decodeCodePoint;},{"./maps/decode.json":21}],19:[function(require,module,exports){"use strict";var __importDefault=this&&this.__importDefault||function(mod){return mod&&mod.__esModule?mod:{"default":mod};};Object.defineProperty(exports,"__esModule",{value:true});exports.escape=exports.encodeHTML=exports.encodeXML=void 0;var xml_json_1=__importDefault(require("./maps/xml.json"));var inverseXML=getInverseObj(xml_json_1["default"]);var xmlReplacer=getInverseReplacer(inverseXML);exports.encodeXML=getInverse(inverseXML,xmlReplacer);var entities_json_1=__importDefault(require("./maps/entities.json"));var inverseHTML=getInverseObj(entities_json_1["default"]);var htmlReplacer=getInverseReplacer(inverseHTML);exports.encodeHTML=getInverse(inverseHTML,htmlReplacer);function getInverseObj(obj){return Object.keys(obj).sort().reduce(function(inverse,name){inverse[obj[name]]="&"+name+";";return inverse;},{});}function getInverseReplacer(inverse){var single=[];var multiple=[];for(var _i=0,_a=Object.keys(inverse);_i<_a.length;_i++){var k=_a[_i];if(k.length===1){// Add value to single array
single.push("\\"+k);}else{// Add value to multiple array
multiple.push(k);}}// Add ranges to single characters.
single.sort();for(var start=0;start<single.length-1;start++){// Find the end of a run of characters
var end=start;while(end<single.length-1&&single[end].charCodeAt(1)+1===single[end+1].charCodeAt(1)){end+=1;}var count=1+end-start;// We want to replace at least three characters
if(count<3)continue;single.splice(start,count,single[start]+"-"+single[end]);}multiple.unshift("["+single.join("")+"]");return new RegExp(multiple.join("|"),"g");}var reNonASCII=/(?:[\x80-\uD7FF\uE000-\uFFFF]|[\uD800-\uDBFF][\uDC00-\uDFFF]|[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?:[^\uD800-\uDBFF]|^)[\uDC00-\uDFFF])/g;function singleCharReplacer(c){// eslint-disable-next-line @typescript-eslint/no-non-null-assertion
return"&#x"+c.codePointAt(0).toString(16).toUpperCase()+";";}function getInverse(inverse,re){return function(data){return data.replace(re,function(name){return inverse[name];}).replace(reNonASCII,singleCharReplacer);};}var reXmlChars=getInverseReplacer(inverseXML);function escape(data){return data.replace(reXmlChars,singleCharReplacer).replace(reNonASCII,singleCharReplacer);}exports.escape=escape;},{"./maps/entities.json":22,"./maps/xml.json":24}],20:[function(require,module,exports){"use strict";Object.defineProperty(exports,"__esModule",{value:true});exports.encode=exports.decodeStrict=exports.decode=void 0;var decode_1=require("./decode");var encode_1=require("./encode");/**
 * Decodes a string with entities.
 *
 * @param data String to decode.
 * @param level Optional level to decode at. 0 = XML, 1 = HTML. Default is 0.
 */function decode(data,level){return(!level||level<=0?decode_1.decodeXML:decode_1.decodeHTML)(data);}exports.decode=decode;/**
 * Decodes a string with entities. Does not allow missing trailing semicolons for entities.
 *
 * @param data String to decode.
 * @param level Optional level to decode at. 0 = XML, 1 = HTML. Default is 0.
 */function decodeStrict(data,level){return(!level||level<=0?decode_1.decodeXML:decode_1.decodeHTMLStrict)(data);}exports.decodeStrict=decodeStrict;/**
 * Encodes a string with entities.
 *
 * @param data String to encode.
 * @param level Optional level to encode at. 0 = XML, 1 = HTML. Default is 0.
 */function encode(data,level){return(!level||level<=0?encode_1.encodeXML:encode_1.encodeHTML)(data);}exports.encode=encode;var encode_2=require("./encode");Object.defineProperty(exports,"encodeXML",{enumerable:true,get:function get(){return encode_2.encodeXML;}});Object.defineProperty(exports,"encodeHTML",{enumerable:true,get:function get(){return encode_2.encodeHTML;}});Object.defineProperty(exports,"escape",{enumerable:true,get:function get(){return encode_2.escape;}});// Legacy aliases
Object.defineProperty(exports,"encodeHTML4",{enumerable:true,get:function get(){return encode_2.encodeHTML;}});Object.defineProperty(exports,"encodeHTML5",{enumerable:true,get:function get(){return encode_2.encodeHTML;}});var decode_2=require("./decode");Object.defineProperty(exports,"decodeXML",{enumerable:true,get:function get(){return decode_2.decodeXML;}});Object.defineProperty(exports,"decodeHTML",{enumerable:true,get:function get(){return decode_2.decodeHTML;}});Object.defineProperty(exports,"decodeHTMLStrict",{enumerable:true,get:function get(){return decode_2.decodeHTMLStrict;}});// Legacy aliases
Object.defineProperty(exports,"decodeHTML4",{enumerable:true,get:function get(){return decode_2.decodeHTML;}});Object.defineProperty(exports,"decodeHTML5",{enumerable:true,get:function get(){return decode_2.decodeHTML;}});Object.defineProperty(exports,"decodeHTML4Strict",{enumerable:true,get:function get(){return decode_2.decodeHTMLStrict;}});Object.defineProperty(exports,"decodeHTML5Strict",{enumerable:true,get:function get(){return decode_2.decodeHTMLStrict;}});Object.defineProperty(exports,"decodeXMLStrict",{enumerable:true,get:function get(){return decode_2.decodeXML;}});},{"./decode":17,"./encode":19}],21:[function(require,module,exports){module.exports={"0":65533,"128":8364,"130":8218,"131":402,"132":8222,"133":8230,"134":8224,"135":8225,"136":710,"137":8240,"138":352,"139":8249,"140":338,"142":381,"145":8216,"146":8217,"147":8220,"148":8221,"149":8226,"150":8211,"151":8212,"152":732,"153":8482,"154":353,"155":8250,"156":339,"158":382,"159":376};},{}],22:[function(require,module,exports){module.exports={"Aacute":"\xC1","aacute":"\xE1","Abreve":"\u0102","abreve":"\u0103","ac":"\u223E","acd":"\u223F","acE":"\u223E\u0333","Acirc":"\xC2","acirc":"\xE2","acute":"\xB4","Acy":"\u0410","acy":"\u0430","AElig":"\xC6","aelig":"\xE6","af":"\u2061","Afr":"\uD835\uDD04","afr":"\uD835\uDD1E","Agrave":"\xC0","agrave":"\xE0","alefsym":"\u2135","aleph":"\u2135","Alpha":"\u0391","alpha":"\u03B1","Amacr":"\u0100","amacr":"\u0101","amalg":"\u2A3F","amp":"&","AMP":"&","andand":"\u2A55","And":"\u2A53","and":"\u2227","andd":"\u2A5C","andslope":"\u2A58","andv":"\u2A5A","ang":"\u2220","ange":"\u29A4","angle":"\u2220","angmsdaa":"\u29A8","angmsdab":"\u29A9","angmsdac":"\u29AA","angmsdad":"\u29AB","angmsdae":"\u29AC","angmsdaf":"\u29AD","angmsdag":"\u29AE","angmsdah":"\u29AF","angmsd":"\u2221","angrt":"\u221F","angrtvb":"\u22BE","angrtvbd":"\u299D","angsph":"\u2222","angst":"\xC5","angzarr":"\u237C","Aogon":"\u0104","aogon":"\u0105","Aopf":"\uD835\uDD38","aopf":"\uD835\uDD52","apacir":"\u2A6F","ap":"\u2248","apE":"\u2A70","ape":"\u224A","apid":"\u224B","apos":"'","ApplyFunction":"\u2061","approx":"\u2248","approxeq":"\u224A","Aring":"\xC5","aring":"\xE5","Ascr":"\uD835\uDC9C","ascr":"\uD835\uDCB6","Assign":"\u2254","ast":"*","asymp":"\u2248","asympeq":"\u224D","Atilde":"\xC3","atilde":"\xE3","Auml":"\xC4","auml":"\xE4","awconint":"\u2233","awint":"\u2A11","backcong":"\u224C","backepsilon":"\u03F6","backprime":"\u2035","backsim":"\u223D","backsimeq":"\u22CD","Backslash":"\u2216","Barv":"\u2AE7","barvee":"\u22BD","barwed":"\u2305","Barwed":"\u2306","barwedge":"\u2305","bbrk":"\u23B5","bbrktbrk":"\u23B6","bcong":"\u224C","Bcy":"\u0411","bcy":"\u0431","bdquo":"\u201E","becaus":"\u2235","because":"\u2235","Because":"\u2235","bemptyv":"\u29B0","bepsi":"\u03F6","bernou":"\u212C","Bernoullis":"\u212C","Beta":"\u0392","beta":"\u03B2","beth":"\u2136","between":"\u226C","Bfr":"\uD835\uDD05","bfr":"\uD835\uDD1F","bigcap":"\u22C2","bigcirc":"\u25EF","bigcup":"\u22C3","bigodot":"\u2A00","bigoplus":"\u2A01","bigotimes":"\u2A02","bigsqcup":"\u2A06","bigstar":"\u2605","bigtriangledown":"\u25BD","bigtriangleup":"\u25B3","biguplus":"\u2A04","bigvee":"\u22C1","bigwedge":"\u22C0","bkarow":"\u290D","blacklozenge":"\u29EB","blacksquare":"\u25AA","blacktriangle":"\u25B4","blacktriangledown":"\u25BE","blacktriangleleft":"\u25C2","blacktriangleright":"\u25B8","blank":"\u2423","blk12":"\u2592","blk14":"\u2591","blk34":"\u2593","block":"\u2588","bne":"=\u20E5","bnequiv":"\u2261\u20E5","bNot":"\u2AED","bnot":"\u2310","Bopf":"\uD835\uDD39","bopf":"\uD835\uDD53","bot":"\u22A5","bottom":"\u22A5","bowtie":"\u22C8","boxbox":"\u29C9","boxdl":"\u2510","boxdL":"\u2555","boxDl":"\u2556","boxDL":"\u2557","boxdr":"\u250C","boxdR":"\u2552","boxDr":"\u2553","boxDR":"\u2554","boxh":"\u2500","boxH":"\u2550","boxhd":"\u252C","boxHd":"\u2564","boxhD":"\u2565","boxHD":"\u2566","boxhu":"\u2534","boxHu":"\u2567","boxhU":"\u2568","boxHU":"\u2569","boxminus":"\u229F","boxplus":"\u229E","boxtimes":"\u22A0","boxul":"\u2518","boxuL":"\u255B","boxUl":"\u255C","boxUL":"\u255D","boxur":"\u2514","boxuR":"\u2558","boxUr":"\u2559","boxUR":"\u255A","boxv":"\u2502","boxV":"\u2551","boxvh":"\u253C","boxvH":"\u256A","boxVh":"\u256B","boxVH":"\u256C","boxvl":"\u2524","boxvL":"\u2561","boxVl":"\u2562","boxVL":"\u2563","boxvr":"\u251C","boxvR":"\u255E","boxVr":"\u255F","boxVR":"\u2560","bprime":"\u2035","breve":"\u02D8","Breve":"\u02D8","brvbar":"\xA6","bscr":"\uD835\uDCB7","Bscr":"\u212C","bsemi":"\u204F","bsim":"\u223D","bsime":"\u22CD","bsolb":"\u29C5","bsol":"\\","bsolhsub":"\u27C8","bull":"\u2022","bullet":"\u2022","bump":"\u224E","bumpE":"\u2AAE","bumpe":"\u224F","Bumpeq":"\u224E","bumpeq":"\u224F","Cacute":"\u0106","cacute":"\u0107","capand":"\u2A44","capbrcup":"\u2A49","capcap":"\u2A4B","cap":"\u2229","Cap":"\u22D2","capcup":"\u2A47","capdot":"\u2A40","CapitalDifferentialD":"\u2145","caps":"\u2229\uFE00","caret":"\u2041","caron":"\u02C7","Cayleys":"\u212D","ccaps":"\u2A4D","Ccaron":"\u010C","ccaron":"\u010D","Ccedil":"\xC7","ccedil":"\xE7","Ccirc":"\u0108","ccirc":"\u0109","Cconint":"\u2230","ccups":"\u2A4C","ccupssm":"\u2A50","Cdot":"\u010A","cdot":"\u010B","cedil":"\xB8","Cedilla":"\xB8","cemptyv":"\u29B2","cent":"\xA2","centerdot":"\xB7","CenterDot":"\xB7","cfr":"\uD835\uDD20","Cfr":"\u212D","CHcy":"\u0427","chcy":"\u0447","check":"\u2713","checkmark":"\u2713","Chi":"\u03A7","chi":"\u03C7","circ":"\u02C6","circeq":"\u2257","circlearrowleft":"\u21BA","circlearrowright":"\u21BB","circledast":"\u229B","circledcirc":"\u229A","circleddash":"\u229D","CircleDot":"\u2299","circledR":"\xAE","circledS":"\u24C8","CircleMinus":"\u2296","CirclePlus":"\u2295","CircleTimes":"\u2297","cir":"\u25CB","cirE":"\u29C3","cire":"\u2257","cirfnint":"\u2A10","cirmid":"\u2AEF","cirscir":"\u29C2","ClockwiseContourIntegral":"\u2232","CloseCurlyDoubleQuote":"\u201D","CloseCurlyQuote":"\u2019","clubs":"\u2663","clubsuit":"\u2663","colon":":","Colon":"\u2237","Colone":"\u2A74","colone":"\u2254","coloneq":"\u2254","comma":",","commat":"@","comp":"\u2201","compfn":"\u2218","complement":"\u2201","complexes":"\u2102","cong":"\u2245","congdot":"\u2A6D","Congruent":"\u2261","conint":"\u222E","Conint":"\u222F","ContourIntegral":"\u222E","copf":"\uD835\uDD54","Copf":"\u2102","coprod":"\u2210","Coproduct":"\u2210","copy":"\xA9","COPY":"\xA9","copysr":"\u2117","CounterClockwiseContourIntegral":"\u2233","crarr":"\u21B5","cross":"\u2717","Cross":"\u2A2F","Cscr":"\uD835\uDC9E","cscr":"\uD835\uDCB8","csub":"\u2ACF","csube":"\u2AD1","csup":"\u2AD0","csupe":"\u2AD2","ctdot":"\u22EF","cudarrl":"\u2938","cudarrr":"\u2935","cuepr":"\u22DE","cuesc":"\u22DF","cularr":"\u21B6","cularrp":"\u293D","cupbrcap":"\u2A48","cupcap":"\u2A46","CupCap":"\u224D","cup":"\u222A","Cup":"\u22D3","cupcup":"\u2A4A","cupdot":"\u228D","cupor":"\u2A45","cups":"\u222A\uFE00","curarr":"\u21B7","curarrm":"\u293C","curlyeqprec":"\u22DE","curlyeqsucc":"\u22DF","curlyvee":"\u22CE","curlywedge":"\u22CF","curren":"\xA4","curvearrowleft":"\u21B6","curvearrowright":"\u21B7","cuvee":"\u22CE","cuwed":"\u22CF","cwconint":"\u2232","cwint":"\u2231","cylcty":"\u232D","dagger":"\u2020","Dagger":"\u2021","daleth":"\u2138","darr":"\u2193","Darr":"\u21A1","dArr":"\u21D3","dash":"\u2010","Dashv":"\u2AE4","dashv":"\u22A3","dbkarow":"\u290F","dblac":"\u02DD","Dcaron":"\u010E","dcaron":"\u010F","Dcy":"\u0414","dcy":"\u0434","ddagger":"\u2021","ddarr":"\u21CA","DD":"\u2145","dd":"\u2146","DDotrahd":"\u2911","ddotseq":"\u2A77","deg":"\xB0","Del":"\u2207","Delta":"\u0394","delta":"\u03B4","demptyv":"\u29B1","dfisht":"\u297F","Dfr":"\uD835\uDD07","dfr":"\uD835\uDD21","dHar":"\u2965","dharl":"\u21C3","dharr":"\u21C2","DiacriticalAcute":"\xB4","DiacriticalDot":"\u02D9","DiacriticalDoubleAcute":"\u02DD","DiacriticalGrave":"`","DiacriticalTilde":"\u02DC","diam":"\u22C4","diamond":"\u22C4","Diamond":"\u22C4","diamondsuit":"\u2666","diams":"\u2666","die":"\xA8","DifferentialD":"\u2146","digamma":"\u03DD","disin":"\u22F2","div":"\xF7","divide":"\xF7","divideontimes":"\u22C7","divonx":"\u22C7","DJcy":"\u0402","djcy":"\u0452","dlcorn":"\u231E","dlcrop":"\u230D","dollar":"$","Dopf":"\uD835\uDD3B","dopf":"\uD835\uDD55","Dot":"\xA8","dot":"\u02D9","DotDot":"\u20DC","doteq":"\u2250","doteqdot":"\u2251","DotEqual":"\u2250","dotminus":"\u2238","dotplus":"\u2214","dotsquare":"\u22A1","doublebarwedge":"\u2306","DoubleContourIntegral":"\u222F","DoubleDot":"\xA8","DoubleDownArrow":"\u21D3","DoubleLeftArrow":"\u21D0","DoubleLeftRightArrow":"\u21D4","DoubleLeftTee":"\u2AE4","DoubleLongLeftArrow":"\u27F8","DoubleLongLeftRightArrow":"\u27FA","DoubleLongRightArrow":"\u27F9","DoubleRightArrow":"\u21D2","DoubleRightTee":"\u22A8","DoubleUpArrow":"\u21D1","DoubleUpDownArrow":"\u21D5","DoubleVerticalBar":"\u2225","DownArrowBar":"\u2913","downarrow":"\u2193","DownArrow":"\u2193","Downarrow":"\u21D3","DownArrowUpArrow":"\u21F5","DownBreve":"\u0311","downdownarrows":"\u21CA","downharpoonleft":"\u21C3","downharpoonright":"\u21C2","DownLeftRightVector":"\u2950","DownLeftTeeVector":"\u295E","DownLeftVectorBar":"\u2956","DownLeftVector":"\u21BD","DownRightTeeVector":"\u295F","DownRightVectorBar":"\u2957","DownRightVector":"\u21C1","DownTeeArrow":"\u21A7","DownTee":"\u22A4","drbkarow":"\u2910","drcorn":"\u231F","drcrop":"\u230C","Dscr":"\uD835\uDC9F","dscr":"\uD835\uDCB9","DScy":"\u0405","dscy":"\u0455","dsol":"\u29F6","Dstrok":"\u0110","dstrok":"\u0111","dtdot":"\u22F1","dtri":"\u25BF","dtrif":"\u25BE","duarr":"\u21F5","duhar":"\u296F","dwangle":"\u29A6","DZcy":"\u040F","dzcy":"\u045F","dzigrarr":"\u27FF","Eacute":"\xC9","eacute":"\xE9","easter":"\u2A6E","Ecaron":"\u011A","ecaron":"\u011B","Ecirc":"\xCA","ecirc":"\xEA","ecir":"\u2256","ecolon":"\u2255","Ecy":"\u042D","ecy":"\u044D","eDDot":"\u2A77","Edot":"\u0116","edot":"\u0117","eDot":"\u2251","ee":"\u2147","efDot":"\u2252","Efr":"\uD835\uDD08","efr":"\uD835\uDD22","eg":"\u2A9A","Egrave":"\xC8","egrave":"\xE8","egs":"\u2A96","egsdot":"\u2A98","el":"\u2A99","Element":"\u2208","elinters":"\u23E7","ell":"\u2113","els":"\u2A95","elsdot":"\u2A97","Emacr":"\u0112","emacr":"\u0113","empty":"\u2205","emptyset":"\u2205","EmptySmallSquare":"\u25FB","emptyv":"\u2205","EmptyVerySmallSquare":"\u25AB","emsp13":"\u2004","emsp14":"\u2005","emsp":"\u2003","ENG":"\u014A","eng":"\u014B","ensp":"\u2002","Eogon":"\u0118","eogon":"\u0119","Eopf":"\uD835\uDD3C","eopf":"\uD835\uDD56","epar":"\u22D5","eparsl":"\u29E3","eplus":"\u2A71","epsi":"\u03B5","Epsilon":"\u0395","epsilon":"\u03B5","epsiv":"\u03F5","eqcirc":"\u2256","eqcolon":"\u2255","eqsim":"\u2242","eqslantgtr":"\u2A96","eqslantless":"\u2A95","Equal":"\u2A75","equals":"=","EqualTilde":"\u2242","equest":"\u225F","Equilibrium":"\u21CC","equiv":"\u2261","equivDD":"\u2A78","eqvparsl":"\u29E5","erarr":"\u2971","erDot":"\u2253","escr":"\u212F","Escr":"\u2130","esdot":"\u2250","Esim":"\u2A73","esim":"\u2242","Eta":"\u0397","eta":"\u03B7","ETH":"\xD0","eth":"\xF0","Euml":"\xCB","euml":"\xEB","euro":"\u20AC","excl":"!","exist":"\u2203","Exists":"\u2203","expectation":"\u2130","exponentiale":"\u2147","ExponentialE":"\u2147","fallingdotseq":"\u2252","Fcy":"\u0424","fcy":"\u0444","female":"\u2640","ffilig":"\uFB03","fflig":"\uFB00","ffllig":"\uFB04","Ffr":"\uD835\uDD09","ffr":"\uD835\uDD23","filig":"\uFB01","FilledSmallSquare":"\u25FC","FilledVerySmallSquare":"\u25AA","fjlig":"fj","flat":"\u266D","fllig":"\uFB02","fltns":"\u25B1","fnof":"\u0192","Fopf":"\uD835\uDD3D","fopf":"\uD835\uDD57","forall":"\u2200","ForAll":"\u2200","fork":"\u22D4","forkv":"\u2AD9","Fouriertrf":"\u2131","fpartint":"\u2A0D","frac12":"\xBD","frac13":"\u2153","frac14":"\xBC","frac15":"\u2155","frac16":"\u2159","frac18":"\u215B","frac23":"\u2154","frac25":"\u2156","frac34":"\xBE","frac35":"\u2157","frac38":"\u215C","frac45":"\u2158","frac56":"\u215A","frac58":"\u215D","frac78":"\u215E","frasl":"\u2044","frown":"\u2322","fscr":"\uD835\uDCBB","Fscr":"\u2131","gacute":"\u01F5","Gamma":"\u0393","gamma":"\u03B3","Gammad":"\u03DC","gammad":"\u03DD","gap":"\u2A86","Gbreve":"\u011E","gbreve":"\u011F","Gcedil":"\u0122","Gcirc":"\u011C","gcirc":"\u011D","Gcy":"\u0413","gcy":"\u0433","Gdot":"\u0120","gdot":"\u0121","ge":"\u2265","gE":"\u2267","gEl":"\u2A8C","gel":"\u22DB","geq":"\u2265","geqq":"\u2267","geqslant":"\u2A7E","gescc":"\u2AA9","ges":"\u2A7E","gesdot":"\u2A80","gesdoto":"\u2A82","gesdotol":"\u2A84","gesl":"\u22DB\uFE00","gesles":"\u2A94","Gfr":"\uD835\uDD0A","gfr":"\uD835\uDD24","gg":"\u226B","Gg":"\u22D9","ggg":"\u22D9","gimel":"\u2137","GJcy":"\u0403","gjcy":"\u0453","gla":"\u2AA5","gl":"\u2277","glE":"\u2A92","glj":"\u2AA4","gnap":"\u2A8A","gnapprox":"\u2A8A","gne":"\u2A88","gnE":"\u2269","gneq":"\u2A88","gneqq":"\u2269","gnsim":"\u22E7","Gopf":"\uD835\uDD3E","gopf":"\uD835\uDD58","grave":"`","GreaterEqual":"\u2265","GreaterEqualLess":"\u22DB","GreaterFullEqual":"\u2267","GreaterGreater":"\u2AA2","GreaterLess":"\u2277","GreaterSlantEqual":"\u2A7E","GreaterTilde":"\u2273","Gscr":"\uD835\uDCA2","gscr":"\u210A","gsim":"\u2273","gsime":"\u2A8E","gsiml":"\u2A90","gtcc":"\u2AA7","gtcir":"\u2A7A","gt":">","GT":">","Gt":"\u226B","gtdot":"\u22D7","gtlPar":"\u2995","gtquest":"\u2A7C","gtrapprox":"\u2A86","gtrarr":"\u2978","gtrdot":"\u22D7","gtreqless":"\u22DB","gtreqqless":"\u2A8C","gtrless":"\u2277","gtrsim":"\u2273","gvertneqq":"\u2269\uFE00","gvnE":"\u2269\uFE00","Hacek":"\u02C7","hairsp":"\u200A","half":"\xBD","hamilt":"\u210B","HARDcy":"\u042A","hardcy":"\u044A","harrcir":"\u2948","harr":"\u2194","hArr":"\u21D4","harrw":"\u21AD","Hat":"^","hbar":"\u210F","Hcirc":"\u0124","hcirc":"\u0125","hearts":"\u2665","heartsuit":"\u2665","hellip":"\u2026","hercon":"\u22B9","hfr":"\uD835\uDD25","Hfr":"\u210C","HilbertSpace":"\u210B","hksearow":"\u2925","hkswarow":"\u2926","hoarr":"\u21FF","homtht":"\u223B","hookleftarrow":"\u21A9","hookrightarrow":"\u21AA","hopf":"\uD835\uDD59","Hopf":"\u210D","horbar":"\u2015","HorizontalLine":"\u2500","hscr":"\uD835\uDCBD","Hscr":"\u210B","hslash":"\u210F","Hstrok":"\u0126","hstrok":"\u0127","HumpDownHump":"\u224E","HumpEqual":"\u224F","hybull":"\u2043","hyphen":"\u2010","Iacute":"\xCD","iacute":"\xED","ic":"\u2063","Icirc":"\xCE","icirc":"\xEE","Icy":"\u0418","icy":"\u0438","Idot":"\u0130","IEcy":"\u0415","iecy":"\u0435","iexcl":"\xA1","iff":"\u21D4","ifr":"\uD835\uDD26","Ifr":"\u2111","Igrave":"\xCC","igrave":"\xEC","ii":"\u2148","iiiint":"\u2A0C","iiint":"\u222D","iinfin":"\u29DC","iiota":"\u2129","IJlig":"\u0132","ijlig":"\u0133","Imacr":"\u012A","imacr":"\u012B","image":"\u2111","ImaginaryI":"\u2148","imagline":"\u2110","imagpart":"\u2111","imath":"\u0131","Im":"\u2111","imof":"\u22B7","imped":"\u01B5","Implies":"\u21D2","incare":"\u2105","in":"\u2208","infin":"\u221E","infintie":"\u29DD","inodot":"\u0131","intcal":"\u22BA","int":"\u222B","Int":"\u222C","integers":"\u2124","Integral":"\u222B","intercal":"\u22BA","Intersection":"\u22C2","intlarhk":"\u2A17","intprod":"\u2A3C","InvisibleComma":"\u2063","InvisibleTimes":"\u2062","IOcy":"\u0401","iocy":"\u0451","Iogon":"\u012E","iogon":"\u012F","Iopf":"\uD835\uDD40","iopf":"\uD835\uDD5A","Iota":"\u0399","iota":"\u03B9","iprod":"\u2A3C","iquest":"\xBF","iscr":"\uD835\uDCBE","Iscr":"\u2110","isin":"\u2208","isindot":"\u22F5","isinE":"\u22F9","isins":"\u22F4","isinsv":"\u22F3","isinv":"\u2208","it":"\u2062","Itilde":"\u0128","itilde":"\u0129","Iukcy":"\u0406","iukcy":"\u0456","Iuml":"\xCF","iuml":"\xEF","Jcirc":"\u0134","jcirc":"\u0135","Jcy":"\u0419","jcy":"\u0439","Jfr":"\uD835\uDD0D","jfr":"\uD835\uDD27","jmath":"\u0237","Jopf":"\uD835\uDD41","jopf":"\uD835\uDD5B","Jscr":"\uD835\uDCA5","jscr":"\uD835\uDCBF","Jsercy":"\u0408","jsercy":"\u0458","Jukcy":"\u0404","jukcy":"\u0454","Kappa":"\u039A","kappa":"\u03BA","kappav":"\u03F0","Kcedil":"\u0136","kcedil":"\u0137","Kcy":"\u041A","kcy":"\u043A","Kfr":"\uD835\uDD0E","kfr":"\uD835\uDD28","kgreen":"\u0138","KHcy":"\u0425","khcy":"\u0445","KJcy":"\u040C","kjcy":"\u045C","Kopf":"\uD835\uDD42","kopf":"\uD835\uDD5C","Kscr":"\uD835\uDCA6","kscr":"\uD835\uDCC0","lAarr":"\u21DA","Lacute":"\u0139","lacute":"\u013A","laemptyv":"\u29B4","lagran":"\u2112","Lambda":"\u039B","lambda":"\u03BB","lang":"\u27E8","Lang":"\u27EA","langd":"\u2991","langle":"\u27E8","lap":"\u2A85","Laplacetrf":"\u2112","laquo":"\xAB","larrb":"\u21E4","larrbfs":"\u291F","larr":"\u2190","Larr":"\u219E","lArr":"\u21D0","larrfs":"\u291D","larrhk":"\u21A9","larrlp":"\u21AB","larrpl":"\u2939","larrsim":"\u2973","larrtl":"\u21A2","latail":"\u2919","lAtail":"\u291B","lat":"\u2AAB","late":"\u2AAD","lates":"\u2AAD\uFE00","lbarr":"\u290C","lBarr":"\u290E","lbbrk":"\u2772","lbrace":"{","lbrack":"[","lbrke":"\u298B","lbrksld":"\u298F","lbrkslu":"\u298D","Lcaron":"\u013D","lcaron":"\u013E","Lcedil":"\u013B","lcedil":"\u013C","lceil":"\u2308","lcub":"{","Lcy":"\u041B","lcy":"\u043B","ldca":"\u2936","ldquo":"\u201C","ldquor":"\u201E","ldrdhar":"\u2967","ldrushar":"\u294B","ldsh":"\u21B2","le":"\u2264","lE":"\u2266","LeftAngleBracket":"\u27E8","LeftArrowBar":"\u21E4","leftarrow":"\u2190","LeftArrow":"\u2190","Leftarrow":"\u21D0","LeftArrowRightArrow":"\u21C6","leftarrowtail":"\u21A2","LeftCeiling":"\u2308","LeftDoubleBracket":"\u27E6","LeftDownTeeVector":"\u2961","LeftDownVectorBar":"\u2959","LeftDownVector":"\u21C3","LeftFloor":"\u230A","leftharpoondown":"\u21BD","leftharpoonup":"\u21BC","leftleftarrows":"\u21C7","leftrightarrow":"\u2194","LeftRightArrow":"\u2194","Leftrightarrow":"\u21D4","leftrightarrows":"\u21C6","leftrightharpoons":"\u21CB","leftrightsquigarrow":"\u21AD","LeftRightVector":"\u294E","LeftTeeArrow":"\u21A4","LeftTee":"\u22A3","LeftTeeVector":"\u295A","leftthreetimes":"\u22CB","LeftTriangleBar":"\u29CF","LeftTriangle":"\u22B2","LeftTriangleEqual":"\u22B4","LeftUpDownVector":"\u2951","LeftUpTeeVector":"\u2960","LeftUpVectorBar":"\u2958","LeftUpVector":"\u21BF","LeftVectorBar":"\u2952","LeftVector":"\u21BC","lEg":"\u2A8B","leg":"\u22DA","leq":"\u2264","leqq":"\u2266","leqslant":"\u2A7D","lescc":"\u2AA8","les":"\u2A7D","lesdot":"\u2A7F","lesdoto":"\u2A81","lesdotor":"\u2A83","lesg":"\u22DA\uFE00","lesges":"\u2A93","lessapprox":"\u2A85","lessdot":"\u22D6","lesseqgtr":"\u22DA","lesseqqgtr":"\u2A8B","LessEqualGreater":"\u22DA","LessFullEqual":"\u2266","LessGreater":"\u2276","lessgtr":"\u2276","LessLess":"\u2AA1","lesssim":"\u2272","LessSlantEqual":"\u2A7D","LessTilde":"\u2272","lfisht":"\u297C","lfloor":"\u230A","Lfr":"\uD835\uDD0F","lfr":"\uD835\uDD29","lg":"\u2276","lgE":"\u2A91","lHar":"\u2962","lhard":"\u21BD","lharu":"\u21BC","lharul":"\u296A","lhblk":"\u2584","LJcy":"\u0409","ljcy":"\u0459","llarr":"\u21C7","ll":"\u226A","Ll":"\u22D8","llcorner":"\u231E","Lleftarrow":"\u21DA","llhard":"\u296B","lltri":"\u25FA","Lmidot":"\u013F","lmidot":"\u0140","lmoustache":"\u23B0","lmoust":"\u23B0","lnap":"\u2A89","lnapprox":"\u2A89","lne":"\u2A87","lnE":"\u2268","lneq":"\u2A87","lneqq":"\u2268","lnsim":"\u22E6","loang":"\u27EC","loarr":"\u21FD","lobrk":"\u27E6","longleftarrow":"\u27F5","LongLeftArrow":"\u27F5","Longleftarrow":"\u27F8","longleftrightarrow":"\u27F7","LongLeftRightArrow":"\u27F7","Longleftrightarrow":"\u27FA","longmapsto":"\u27FC","longrightarrow":"\u27F6","LongRightArrow":"\u27F6","Longrightarrow":"\u27F9","looparrowleft":"\u21AB","looparrowright":"\u21AC","lopar":"\u2985","Lopf":"\uD835\uDD43","lopf":"\uD835\uDD5D","loplus":"\u2A2D","lotimes":"\u2A34","lowast":"\u2217","lowbar":"_","LowerLeftArrow":"\u2199","LowerRightArrow":"\u2198","loz":"\u25CA","lozenge":"\u25CA","lozf":"\u29EB","lpar":"(","lparlt":"\u2993","lrarr":"\u21C6","lrcorner":"\u231F","lrhar":"\u21CB","lrhard":"\u296D","lrm":"\u200E","lrtri":"\u22BF","lsaquo":"\u2039","lscr":"\uD835\uDCC1","Lscr":"\u2112","lsh":"\u21B0","Lsh":"\u21B0","lsim":"\u2272","lsime":"\u2A8D","lsimg":"\u2A8F","lsqb":"[","lsquo":"\u2018","lsquor":"\u201A","Lstrok":"\u0141","lstrok":"\u0142","ltcc":"\u2AA6","ltcir":"\u2A79","lt":"<","LT":"<","Lt":"\u226A","ltdot":"\u22D6","lthree":"\u22CB","ltimes":"\u22C9","ltlarr":"\u2976","ltquest":"\u2A7B","ltri":"\u25C3","ltrie":"\u22B4","ltrif":"\u25C2","ltrPar":"\u2996","lurdshar":"\u294A","luruhar":"\u2966","lvertneqq":"\u2268\uFE00","lvnE":"\u2268\uFE00","macr":"\xAF","male":"\u2642","malt":"\u2720","maltese":"\u2720","Map":"\u2905","map":"\u21A6","mapsto":"\u21A6","mapstodown":"\u21A7","mapstoleft":"\u21A4","mapstoup":"\u21A5","marker":"\u25AE","mcomma":"\u2A29","Mcy":"\u041C","mcy":"\u043C","mdash":"\u2014","mDDot":"\u223A","measuredangle":"\u2221","MediumSpace":"\u205F","Mellintrf":"\u2133","Mfr":"\uD835\uDD10","mfr":"\uD835\uDD2A","mho":"\u2127","micro":"\xB5","midast":"*","midcir":"\u2AF0","mid":"\u2223","middot":"\xB7","minusb":"\u229F","minus":"\u2212","minusd":"\u2238","minusdu":"\u2A2A","MinusPlus":"\u2213","mlcp":"\u2ADB","mldr":"\u2026","mnplus":"\u2213","models":"\u22A7","Mopf":"\uD835\uDD44","mopf":"\uD835\uDD5E","mp":"\u2213","mscr":"\uD835\uDCC2","Mscr":"\u2133","mstpos":"\u223E","Mu":"\u039C","mu":"\u03BC","multimap":"\u22B8","mumap":"\u22B8","nabla":"\u2207","Nacute":"\u0143","nacute":"\u0144","nang":"\u2220\u20D2","nap":"\u2249","napE":"\u2A70\u0338","napid":"\u224B\u0338","napos":"\u0149","napprox":"\u2249","natural":"\u266E","naturals":"\u2115","natur":"\u266E","nbsp":"\xA0","nbump":"\u224E\u0338","nbumpe":"\u224F\u0338","ncap":"\u2A43","Ncaron":"\u0147","ncaron":"\u0148","Ncedil":"\u0145","ncedil":"\u0146","ncong":"\u2247","ncongdot":"\u2A6D\u0338","ncup":"\u2A42","Ncy":"\u041D","ncy":"\u043D","ndash":"\u2013","nearhk":"\u2924","nearr":"\u2197","neArr":"\u21D7","nearrow":"\u2197","ne":"\u2260","nedot":"\u2250\u0338","NegativeMediumSpace":"\u200B","NegativeThickSpace":"\u200B","NegativeThinSpace":"\u200B","NegativeVeryThinSpace":"\u200B","nequiv":"\u2262","nesear":"\u2928","nesim":"\u2242\u0338","NestedGreaterGreater":"\u226B","NestedLessLess":"\u226A","NewLine":"\n","nexist":"\u2204","nexists":"\u2204","Nfr":"\uD835\uDD11","nfr":"\uD835\uDD2B","ngE":"\u2267\u0338","nge":"\u2271","ngeq":"\u2271","ngeqq":"\u2267\u0338","ngeqslant":"\u2A7E\u0338","nges":"\u2A7E\u0338","nGg":"\u22D9\u0338","ngsim":"\u2275","nGt":"\u226B\u20D2","ngt":"\u226F","ngtr":"\u226F","nGtv":"\u226B\u0338","nharr":"\u21AE","nhArr":"\u21CE","nhpar":"\u2AF2","ni":"\u220B","nis":"\u22FC","nisd":"\u22FA","niv":"\u220B","NJcy":"\u040A","njcy":"\u045A","nlarr":"\u219A","nlArr":"\u21CD","nldr":"\u2025","nlE":"\u2266\u0338","nle":"\u2270","nleftarrow":"\u219A","nLeftarrow":"\u21CD","nleftrightarrow":"\u21AE","nLeftrightarrow":"\u21CE","nleq":"\u2270","nleqq":"\u2266\u0338","nleqslant":"\u2A7D\u0338","nles":"\u2A7D\u0338","nless":"\u226E","nLl":"\u22D8\u0338","nlsim":"\u2274","nLt":"\u226A\u20D2","nlt":"\u226E","nltri":"\u22EA","nltrie":"\u22EC","nLtv":"\u226A\u0338","nmid":"\u2224","NoBreak":"\u2060","NonBreakingSpace":"\xA0","nopf":"\uD835\uDD5F","Nopf":"\u2115","Not":"\u2AEC","not":"\xAC","NotCongruent":"\u2262","NotCupCap":"\u226D","NotDoubleVerticalBar":"\u2226","NotElement":"\u2209","NotEqual":"\u2260","NotEqualTilde":"\u2242\u0338","NotExists":"\u2204","NotGreater":"\u226F","NotGreaterEqual":"\u2271","NotGreaterFullEqual":"\u2267\u0338","NotGreaterGreater":"\u226B\u0338","NotGreaterLess":"\u2279","NotGreaterSlantEqual":"\u2A7E\u0338","NotGreaterTilde":"\u2275","NotHumpDownHump":"\u224E\u0338","NotHumpEqual":"\u224F\u0338","notin":"\u2209","notindot":"\u22F5\u0338","notinE":"\u22F9\u0338","notinva":"\u2209","notinvb":"\u22F7","notinvc":"\u22F6","NotLeftTriangleBar":"\u29CF\u0338","NotLeftTriangle":"\u22EA","NotLeftTriangleEqual":"\u22EC","NotLess":"\u226E","NotLessEqual":"\u2270","NotLessGreater":"\u2278","NotLessLess":"\u226A\u0338","NotLessSlantEqual":"\u2A7D\u0338","NotLessTilde":"\u2274","NotNestedGreaterGreater":"\u2AA2\u0338","NotNestedLessLess":"\u2AA1\u0338","notni":"\u220C","notniva":"\u220C","notnivb":"\u22FE","notnivc":"\u22FD","NotPrecedes":"\u2280","NotPrecedesEqual":"\u2AAF\u0338","NotPrecedesSlantEqual":"\u22E0","NotReverseElement":"\u220C","NotRightTriangleBar":"\u29D0\u0338","NotRightTriangle":"\u22EB","NotRightTriangleEqual":"\u22ED","NotSquareSubset":"\u228F\u0338","NotSquareSubsetEqual":"\u22E2","NotSquareSuperset":"\u2290\u0338","NotSquareSupersetEqual":"\u22E3","NotSubset":"\u2282\u20D2","NotSubsetEqual":"\u2288","NotSucceeds":"\u2281","NotSucceedsEqual":"\u2AB0\u0338","NotSucceedsSlantEqual":"\u22E1","NotSucceedsTilde":"\u227F\u0338","NotSuperset":"\u2283\u20D2","NotSupersetEqual":"\u2289","NotTilde":"\u2241","NotTildeEqual":"\u2244","NotTildeFullEqual":"\u2247","NotTildeTilde":"\u2249","NotVerticalBar":"\u2224","nparallel":"\u2226","npar":"\u2226","nparsl":"\u2AFD\u20E5","npart":"\u2202\u0338","npolint":"\u2A14","npr":"\u2280","nprcue":"\u22E0","nprec":"\u2280","npreceq":"\u2AAF\u0338","npre":"\u2AAF\u0338","nrarrc":"\u2933\u0338","nrarr":"\u219B","nrArr":"\u21CF","nrarrw":"\u219D\u0338","nrightarrow":"\u219B","nRightarrow":"\u21CF","nrtri":"\u22EB","nrtrie":"\u22ED","nsc":"\u2281","nsccue":"\u22E1","nsce":"\u2AB0\u0338","Nscr":"\uD835\uDCA9","nscr":"\uD835\uDCC3","nshortmid":"\u2224","nshortparallel":"\u2226","nsim":"\u2241","nsime":"\u2244","nsimeq":"\u2244","nsmid":"\u2224","nspar":"\u2226","nsqsube":"\u22E2","nsqsupe":"\u22E3","nsub":"\u2284","nsubE":"\u2AC5\u0338","nsube":"\u2288","nsubset":"\u2282\u20D2","nsubseteq":"\u2288","nsubseteqq":"\u2AC5\u0338","nsucc":"\u2281","nsucceq":"\u2AB0\u0338","nsup":"\u2285","nsupE":"\u2AC6\u0338","nsupe":"\u2289","nsupset":"\u2283\u20D2","nsupseteq":"\u2289","nsupseteqq":"\u2AC6\u0338","ntgl":"\u2279","Ntilde":"\xD1","ntilde":"\xF1","ntlg":"\u2278","ntriangleleft":"\u22EA","ntrianglelefteq":"\u22EC","ntriangleright":"\u22EB","ntrianglerighteq":"\u22ED","Nu":"\u039D","nu":"\u03BD","num":"#","numero":"\u2116","numsp":"\u2007","nvap":"\u224D\u20D2","nvdash":"\u22AC","nvDash":"\u22AD","nVdash":"\u22AE","nVDash":"\u22AF","nvge":"\u2265\u20D2","nvgt":">\u20D2","nvHarr":"\u2904","nvinfin":"\u29DE","nvlArr":"\u2902","nvle":"\u2264\u20D2","nvlt":"<\u20D2","nvltrie":"\u22B4\u20D2","nvrArr":"\u2903","nvrtrie":"\u22B5\u20D2","nvsim":"\u223C\u20D2","nwarhk":"\u2923","nwarr":"\u2196","nwArr":"\u21D6","nwarrow":"\u2196","nwnear":"\u2927","Oacute":"\xD3","oacute":"\xF3","oast":"\u229B","Ocirc":"\xD4","ocirc":"\xF4","ocir":"\u229A","Ocy":"\u041E","ocy":"\u043E","odash":"\u229D","Odblac":"\u0150","odblac":"\u0151","odiv":"\u2A38","odot":"\u2299","odsold":"\u29BC","OElig":"\u0152","oelig":"\u0153","ofcir":"\u29BF","Ofr":"\uD835\uDD12","ofr":"\uD835\uDD2C","ogon":"\u02DB","Ograve":"\xD2","ograve":"\xF2","ogt":"\u29C1","ohbar":"\u29B5","ohm":"\u03A9","oint":"\u222E","olarr":"\u21BA","olcir":"\u29BE","olcross":"\u29BB","oline":"\u203E","olt":"\u29C0","Omacr":"\u014C","omacr":"\u014D","Omega":"\u03A9","omega":"\u03C9","Omicron":"\u039F","omicron":"\u03BF","omid":"\u29B6","ominus":"\u2296","Oopf":"\uD835\uDD46","oopf":"\uD835\uDD60","opar":"\u29B7","OpenCurlyDoubleQuote":"\u201C","OpenCurlyQuote":"\u2018","operp":"\u29B9","oplus":"\u2295","orarr":"\u21BB","Or":"\u2A54","or":"\u2228","ord":"\u2A5D","order":"\u2134","orderof":"\u2134","ordf":"\xAA","ordm":"\xBA","origof":"\u22B6","oror":"\u2A56","orslope":"\u2A57","orv":"\u2A5B","oS":"\u24C8","Oscr":"\uD835\uDCAA","oscr":"\u2134","Oslash":"\xD8","oslash":"\xF8","osol":"\u2298","Otilde":"\xD5","otilde":"\xF5","otimesas":"\u2A36","Otimes":"\u2A37","otimes":"\u2297","Ouml":"\xD6","ouml":"\xF6","ovbar":"\u233D","OverBar":"\u203E","OverBrace":"\u23DE","OverBracket":"\u23B4","OverParenthesis":"\u23DC","para":"\xB6","parallel":"\u2225","par":"\u2225","parsim":"\u2AF3","parsl":"\u2AFD","part":"\u2202","PartialD":"\u2202","Pcy":"\u041F","pcy":"\u043F","percnt":"%","period":".","permil":"\u2030","perp":"\u22A5","pertenk":"\u2031","Pfr":"\uD835\uDD13","pfr":"\uD835\uDD2D","Phi":"\u03A6","phi":"\u03C6","phiv":"\u03D5","phmmat":"\u2133","phone":"\u260E","Pi":"\u03A0","pi":"\u03C0","pitchfork":"\u22D4","piv":"\u03D6","planck":"\u210F","planckh":"\u210E","plankv":"\u210F","plusacir":"\u2A23","plusb":"\u229E","pluscir":"\u2A22","plus":"+","plusdo":"\u2214","plusdu":"\u2A25","pluse":"\u2A72","PlusMinus":"\xB1","plusmn":"\xB1","plussim":"\u2A26","plustwo":"\u2A27","pm":"\xB1","Poincareplane":"\u210C","pointint":"\u2A15","popf":"\uD835\uDD61","Popf":"\u2119","pound":"\xA3","prap":"\u2AB7","Pr":"\u2ABB","pr":"\u227A","prcue":"\u227C","precapprox":"\u2AB7","prec":"\u227A","preccurlyeq":"\u227C","Precedes":"\u227A","PrecedesEqual":"\u2AAF","PrecedesSlantEqual":"\u227C","PrecedesTilde":"\u227E","preceq":"\u2AAF","precnapprox":"\u2AB9","precneqq":"\u2AB5","precnsim":"\u22E8","pre":"\u2AAF","prE":"\u2AB3","precsim":"\u227E","prime":"\u2032","Prime":"\u2033","primes":"\u2119","prnap":"\u2AB9","prnE":"\u2AB5","prnsim":"\u22E8","prod":"\u220F","Product":"\u220F","profalar":"\u232E","profline":"\u2312","profsurf":"\u2313","prop":"\u221D","Proportional":"\u221D","Proportion":"\u2237","propto":"\u221D","prsim":"\u227E","prurel":"\u22B0","Pscr":"\uD835\uDCAB","pscr":"\uD835\uDCC5","Psi":"\u03A8","psi":"\u03C8","puncsp":"\u2008","Qfr":"\uD835\uDD14","qfr":"\uD835\uDD2E","qint":"\u2A0C","qopf":"\uD835\uDD62","Qopf":"\u211A","qprime":"\u2057","Qscr":"\uD835\uDCAC","qscr":"\uD835\uDCC6","quaternions":"\u210D","quatint":"\u2A16","quest":"?","questeq":"\u225F","quot":"\"","QUOT":"\"","rAarr":"\u21DB","race":"\u223D\u0331","Racute":"\u0154","racute":"\u0155","radic":"\u221A","raemptyv":"\u29B3","rang":"\u27E9","Rang":"\u27EB","rangd":"\u2992","range":"\u29A5","rangle":"\u27E9","raquo":"\xBB","rarrap":"\u2975","rarrb":"\u21E5","rarrbfs":"\u2920","rarrc":"\u2933","rarr":"\u2192","Rarr":"\u21A0","rArr":"\u21D2","rarrfs":"\u291E","rarrhk":"\u21AA","rarrlp":"\u21AC","rarrpl":"\u2945","rarrsim":"\u2974","Rarrtl":"\u2916","rarrtl":"\u21A3","rarrw":"\u219D","ratail":"\u291A","rAtail":"\u291C","ratio":"\u2236","rationals":"\u211A","rbarr":"\u290D","rBarr":"\u290F","RBarr":"\u2910","rbbrk":"\u2773","rbrace":"}","rbrack":"]","rbrke":"\u298C","rbrksld":"\u298E","rbrkslu":"\u2990","Rcaron":"\u0158","rcaron":"\u0159","Rcedil":"\u0156","rcedil":"\u0157","rceil":"\u2309","rcub":"}","Rcy":"\u0420","rcy":"\u0440","rdca":"\u2937","rdldhar":"\u2969","rdquo":"\u201D","rdquor":"\u201D","rdsh":"\u21B3","real":"\u211C","realine":"\u211B","realpart":"\u211C","reals":"\u211D","Re":"\u211C","rect":"\u25AD","reg":"\xAE","REG":"\xAE","ReverseElement":"\u220B","ReverseEquilibrium":"\u21CB","ReverseUpEquilibrium":"\u296F","rfisht":"\u297D","rfloor":"\u230B","rfr":"\uD835\uDD2F","Rfr":"\u211C","rHar":"\u2964","rhard":"\u21C1","rharu":"\u21C0","rharul":"\u296C","Rho":"\u03A1","rho":"\u03C1","rhov":"\u03F1","RightAngleBracket":"\u27E9","RightArrowBar":"\u21E5","rightarrow":"\u2192","RightArrow":"\u2192","Rightarrow":"\u21D2","RightArrowLeftArrow":"\u21C4","rightarrowtail":"\u21A3","RightCeiling":"\u2309","RightDoubleBracket":"\u27E7","RightDownTeeVector":"\u295D","RightDownVectorBar":"\u2955","RightDownVector":"\u21C2","RightFloor":"\u230B","rightharpoondown":"\u21C1","rightharpoonup":"\u21C0","rightleftarrows":"\u21C4","rightleftharpoons":"\u21CC","rightrightarrows":"\u21C9","rightsquigarrow":"\u219D","RightTeeArrow":"\u21A6","RightTee":"\u22A2","RightTeeVector":"\u295B","rightthreetimes":"\u22CC","RightTriangleBar":"\u29D0","RightTriangle":"\u22B3","RightTriangleEqual":"\u22B5","RightUpDownVector":"\u294F","RightUpTeeVector":"\u295C","RightUpVectorBar":"\u2954","RightUpVector":"\u21BE","RightVectorBar":"\u2953","RightVector":"\u21C0","ring":"\u02DA","risingdotseq":"\u2253","rlarr":"\u21C4","rlhar":"\u21CC","rlm":"\u200F","rmoustache":"\u23B1","rmoust":"\u23B1","rnmid":"\u2AEE","roang":"\u27ED","roarr":"\u21FE","robrk":"\u27E7","ropar":"\u2986","ropf":"\uD835\uDD63","Ropf":"\u211D","roplus":"\u2A2E","rotimes":"\u2A35","RoundImplies":"\u2970","rpar":")","rpargt":"\u2994","rppolint":"\u2A12","rrarr":"\u21C9","Rrightarrow":"\u21DB","rsaquo":"\u203A","rscr":"\uD835\uDCC7","Rscr":"\u211B","rsh":"\u21B1","Rsh":"\u21B1","rsqb":"]","rsquo":"\u2019","rsquor":"\u2019","rthree":"\u22CC","rtimes":"\u22CA","rtri":"\u25B9","rtrie":"\u22B5","rtrif":"\u25B8","rtriltri":"\u29CE","RuleDelayed":"\u29F4","ruluhar":"\u2968","rx":"\u211E","Sacute":"\u015A","sacute":"\u015B","sbquo":"\u201A","scap":"\u2AB8","Scaron":"\u0160","scaron":"\u0161","Sc":"\u2ABC","sc":"\u227B","sccue":"\u227D","sce":"\u2AB0","scE":"\u2AB4","Scedil":"\u015E","scedil":"\u015F","Scirc":"\u015C","scirc":"\u015D","scnap":"\u2ABA","scnE":"\u2AB6","scnsim":"\u22E9","scpolint":"\u2A13","scsim":"\u227F","Scy":"\u0421","scy":"\u0441","sdotb":"\u22A1","sdot":"\u22C5","sdote":"\u2A66","searhk":"\u2925","searr":"\u2198","seArr":"\u21D8","searrow":"\u2198","sect":"\xA7","semi":";","seswar":"\u2929","setminus":"\u2216","setmn":"\u2216","sext":"\u2736","Sfr":"\uD835\uDD16","sfr":"\uD835\uDD30","sfrown":"\u2322","sharp":"\u266F","SHCHcy":"\u0429","shchcy":"\u0449","SHcy":"\u0428","shcy":"\u0448","ShortDownArrow":"\u2193","ShortLeftArrow":"\u2190","shortmid":"\u2223","shortparallel":"\u2225","ShortRightArrow":"\u2192","ShortUpArrow":"\u2191","shy":"\xAD","Sigma":"\u03A3","sigma":"\u03C3","sigmaf":"\u03C2","sigmav":"\u03C2","sim":"\u223C","simdot":"\u2A6A","sime":"\u2243","simeq":"\u2243","simg":"\u2A9E","simgE":"\u2AA0","siml":"\u2A9D","simlE":"\u2A9F","simne":"\u2246","simplus":"\u2A24","simrarr":"\u2972","slarr":"\u2190","SmallCircle":"\u2218","smallsetminus":"\u2216","smashp":"\u2A33","smeparsl":"\u29E4","smid":"\u2223","smile":"\u2323","smt":"\u2AAA","smte":"\u2AAC","smtes":"\u2AAC\uFE00","SOFTcy":"\u042C","softcy":"\u044C","solbar":"\u233F","solb":"\u29C4","sol":"/","Sopf":"\uD835\uDD4A","sopf":"\uD835\uDD64","spades":"\u2660","spadesuit":"\u2660","spar":"\u2225","sqcap":"\u2293","sqcaps":"\u2293\uFE00","sqcup":"\u2294","sqcups":"\u2294\uFE00","Sqrt":"\u221A","sqsub":"\u228F","sqsube":"\u2291","sqsubset":"\u228F","sqsubseteq":"\u2291","sqsup":"\u2290","sqsupe":"\u2292","sqsupset":"\u2290","sqsupseteq":"\u2292","square":"\u25A1","Square":"\u25A1","SquareIntersection":"\u2293","SquareSubset":"\u228F","SquareSubsetEqual":"\u2291","SquareSuperset":"\u2290","SquareSupersetEqual":"\u2292","SquareUnion":"\u2294","squarf":"\u25AA","squ":"\u25A1","squf":"\u25AA","srarr":"\u2192","Sscr":"\uD835\uDCAE","sscr":"\uD835\uDCC8","ssetmn":"\u2216","ssmile":"\u2323","sstarf":"\u22C6","Star":"\u22C6","star":"\u2606","starf":"\u2605","straightepsilon":"\u03F5","straightphi":"\u03D5","strns":"\xAF","sub":"\u2282","Sub":"\u22D0","subdot":"\u2ABD","subE":"\u2AC5","sube":"\u2286","subedot":"\u2AC3","submult":"\u2AC1","subnE":"\u2ACB","subne":"\u228A","subplus":"\u2ABF","subrarr":"\u2979","subset":"\u2282","Subset":"\u22D0","subseteq":"\u2286","subseteqq":"\u2AC5","SubsetEqual":"\u2286","subsetneq":"\u228A","subsetneqq":"\u2ACB","subsim":"\u2AC7","subsub":"\u2AD5","subsup":"\u2AD3","succapprox":"\u2AB8","succ":"\u227B","succcurlyeq":"\u227D","Succeeds":"\u227B","SucceedsEqual":"\u2AB0","SucceedsSlantEqual":"\u227D","SucceedsTilde":"\u227F","succeq":"\u2AB0","succnapprox":"\u2ABA","succneqq":"\u2AB6","succnsim":"\u22E9","succsim":"\u227F","SuchThat":"\u220B","sum":"\u2211","Sum":"\u2211","sung":"\u266A","sup1":"\xB9","sup2":"\xB2","sup3":"\xB3","sup":"\u2283","Sup":"\u22D1","supdot":"\u2ABE","supdsub":"\u2AD8","supE":"\u2AC6","supe":"\u2287","supedot":"\u2AC4","Superset":"\u2283","SupersetEqual":"\u2287","suphsol":"\u27C9","suphsub":"\u2AD7","suplarr":"\u297B","supmult":"\u2AC2","supnE":"\u2ACC","supne":"\u228B","supplus":"\u2AC0","supset":"\u2283","Supset":"\u22D1","supseteq":"\u2287","supseteqq":"\u2AC6","supsetneq":"\u228B","supsetneqq":"\u2ACC","supsim":"\u2AC8","supsub":"\u2AD4","supsup":"\u2AD6","swarhk":"\u2926","swarr":"\u2199","swArr":"\u21D9","swarrow":"\u2199","swnwar":"\u292A","szlig":"\xDF","Tab":"\t","target":"\u2316","Tau":"\u03A4","tau":"\u03C4","tbrk":"\u23B4","Tcaron":"\u0164","tcaron":"\u0165","Tcedil":"\u0162","tcedil":"\u0163","Tcy":"\u0422","tcy":"\u0442","tdot":"\u20DB","telrec":"\u2315","Tfr":"\uD835\uDD17","tfr":"\uD835\uDD31","there4":"\u2234","therefore":"\u2234","Therefore":"\u2234","Theta":"\u0398","theta":"\u03B8","thetasym":"\u03D1","thetav":"\u03D1","thickapprox":"\u2248","thicksim":"\u223C","ThickSpace":"\u205F\u200A","ThinSpace":"\u2009","thinsp":"\u2009","thkap":"\u2248","thksim":"\u223C","THORN":"\xDE","thorn":"\xFE","tilde":"\u02DC","Tilde":"\u223C","TildeEqual":"\u2243","TildeFullEqual":"\u2245","TildeTilde":"\u2248","timesbar":"\u2A31","timesb":"\u22A0","times":"\xD7","timesd":"\u2A30","tint":"\u222D","toea":"\u2928","topbot":"\u2336","topcir":"\u2AF1","top":"\u22A4","Topf":"\uD835\uDD4B","topf":"\uD835\uDD65","topfork":"\u2ADA","tosa":"\u2929","tprime":"\u2034","trade":"\u2122","TRADE":"\u2122","triangle":"\u25B5","triangledown":"\u25BF","triangleleft":"\u25C3","trianglelefteq":"\u22B4","triangleq":"\u225C","triangleright":"\u25B9","trianglerighteq":"\u22B5","tridot":"\u25EC","trie":"\u225C","triminus":"\u2A3A","TripleDot":"\u20DB","triplus":"\u2A39","trisb":"\u29CD","tritime":"\u2A3B","trpezium":"\u23E2","Tscr":"\uD835\uDCAF","tscr":"\uD835\uDCC9","TScy":"\u0426","tscy":"\u0446","TSHcy":"\u040B","tshcy":"\u045B","Tstrok":"\u0166","tstrok":"\u0167","twixt":"\u226C","twoheadleftarrow":"\u219E","twoheadrightarrow":"\u21A0","Uacute":"\xDA","uacute":"\xFA","uarr":"\u2191","Uarr":"\u219F","uArr":"\u21D1","Uarrocir":"\u2949","Ubrcy":"\u040E","ubrcy":"\u045E","Ubreve":"\u016C","ubreve":"\u016D","Ucirc":"\xDB","ucirc":"\xFB","Ucy":"\u0423","ucy":"\u0443","udarr":"\u21C5","Udblac":"\u0170","udblac":"\u0171","udhar":"\u296E","ufisht":"\u297E","Ufr":"\uD835\uDD18","ufr":"\uD835\uDD32","Ugrave":"\xD9","ugrave":"\xF9","uHar":"\u2963","uharl":"\u21BF","uharr":"\u21BE","uhblk":"\u2580","ulcorn":"\u231C","ulcorner":"\u231C","ulcrop":"\u230F","ultri":"\u25F8","Umacr":"\u016A","umacr":"\u016B","uml":"\xA8","UnderBar":"_","UnderBrace":"\u23DF","UnderBracket":"\u23B5","UnderParenthesis":"\u23DD","Union":"\u22C3","UnionPlus":"\u228E","Uogon":"\u0172","uogon":"\u0173","Uopf":"\uD835\uDD4C","uopf":"\uD835\uDD66","UpArrowBar":"\u2912","uparrow":"\u2191","UpArrow":"\u2191","Uparrow":"\u21D1","UpArrowDownArrow":"\u21C5","updownarrow":"\u2195","UpDownArrow":"\u2195","Updownarrow":"\u21D5","UpEquilibrium":"\u296E","upharpoonleft":"\u21BF","upharpoonright":"\u21BE","uplus":"\u228E","UpperLeftArrow":"\u2196","UpperRightArrow":"\u2197","upsi":"\u03C5","Upsi":"\u03D2","upsih":"\u03D2","Upsilon":"\u03A5","upsilon":"\u03C5","UpTeeArrow":"\u21A5","UpTee":"\u22A5","upuparrows":"\u21C8","urcorn":"\u231D","urcorner":"\u231D","urcrop":"\u230E","Uring":"\u016E","uring":"\u016F","urtri":"\u25F9","Uscr":"\uD835\uDCB0","uscr":"\uD835\uDCCA","utdot":"\u22F0","Utilde":"\u0168","utilde":"\u0169","utri":"\u25B5","utrif":"\u25B4","uuarr":"\u21C8","Uuml":"\xDC","uuml":"\xFC","uwangle":"\u29A7","vangrt":"\u299C","varepsilon":"\u03F5","varkappa":"\u03F0","varnothing":"\u2205","varphi":"\u03D5","varpi":"\u03D6","varpropto":"\u221D","varr":"\u2195","vArr":"\u21D5","varrho":"\u03F1","varsigma":"\u03C2","varsubsetneq":"\u228A\uFE00","varsubsetneqq":"\u2ACB\uFE00","varsupsetneq":"\u228B\uFE00","varsupsetneqq":"\u2ACC\uFE00","vartheta":"\u03D1","vartriangleleft":"\u22B2","vartriangleright":"\u22B3","vBar":"\u2AE8","Vbar":"\u2AEB","vBarv":"\u2AE9","Vcy":"\u0412","vcy":"\u0432","vdash":"\u22A2","vDash":"\u22A8","Vdash":"\u22A9","VDash":"\u22AB","Vdashl":"\u2AE6","veebar":"\u22BB","vee":"\u2228","Vee":"\u22C1","veeeq":"\u225A","vellip":"\u22EE","verbar":"|","Verbar":"\u2016","vert":"|","Vert":"\u2016","VerticalBar":"\u2223","VerticalLine":"|","VerticalSeparator":"\u2758","VerticalTilde":"\u2240","VeryThinSpace":"\u200A","Vfr":"\uD835\uDD19","vfr":"\uD835\uDD33","vltri":"\u22B2","vnsub":"\u2282\u20D2","vnsup":"\u2283\u20D2","Vopf":"\uD835\uDD4D","vopf":"\uD835\uDD67","vprop":"\u221D","vrtri":"\u22B3","Vscr":"\uD835\uDCB1","vscr":"\uD835\uDCCB","vsubnE":"\u2ACB\uFE00","vsubne":"\u228A\uFE00","vsupnE":"\u2ACC\uFE00","vsupne":"\u228B\uFE00","Vvdash":"\u22AA","vzigzag":"\u299A","Wcirc":"\u0174","wcirc":"\u0175","wedbar":"\u2A5F","wedge":"\u2227","Wedge":"\u22C0","wedgeq":"\u2259","weierp":"\u2118","Wfr":"\uD835\uDD1A","wfr":"\uD835\uDD34","Wopf":"\uD835\uDD4E","wopf":"\uD835\uDD68","wp":"\u2118","wr":"\u2240","wreath":"\u2240","Wscr":"\uD835\uDCB2","wscr":"\uD835\uDCCC","xcap":"\u22C2","xcirc":"\u25EF","xcup":"\u22C3","xdtri":"\u25BD","Xfr":"\uD835\uDD1B","xfr":"\uD835\uDD35","xharr":"\u27F7","xhArr":"\u27FA","Xi":"\u039E","xi":"\u03BE","xlarr":"\u27F5","xlArr":"\u27F8","xmap":"\u27FC","xnis":"\u22FB","xodot":"\u2A00","Xopf":"\uD835\uDD4F","xopf":"\uD835\uDD69","xoplus":"\u2A01","xotime":"\u2A02","xrarr":"\u27F6","xrArr":"\u27F9","Xscr":"\uD835\uDCB3","xscr":"\uD835\uDCCD","xsqcup":"\u2A06","xuplus":"\u2A04","xutri":"\u25B3","xvee":"\u22C1","xwedge":"\u22C0","Yacute":"\xDD","yacute":"\xFD","YAcy":"\u042F","yacy":"\u044F","Ycirc":"\u0176","ycirc":"\u0177","Ycy":"\u042B","ycy":"\u044B","yen":"\xA5","Yfr":"\uD835\uDD1C","yfr":"\uD835\uDD36","YIcy":"\u0407","yicy":"\u0457","Yopf":"\uD835\uDD50","yopf":"\uD835\uDD6A","Yscr":"\uD835\uDCB4","yscr":"\uD835\uDCCE","YUcy":"\u042E","yucy":"\u044E","yuml":"\xFF","Yuml":"\u0178","Zacute":"\u0179","zacute":"\u017A","Zcaron":"\u017D","zcaron":"\u017E","Zcy":"\u0417","zcy":"\u0437","Zdot":"\u017B","zdot":"\u017C","zeetrf":"\u2128","ZeroWidthSpace":"\u200B","Zeta":"\u0396","zeta":"\u03B6","zfr":"\uD835\uDD37","Zfr":"\u2128","ZHcy":"\u0416","zhcy":"\u0436","zigrarr":"\u21DD","zopf":"\uD835\uDD6B","Zopf":"\u2124","Zscr":"\uD835\uDCB5","zscr":"\uD835\uDCCF","zwj":"\u200D","zwnj":"\u200C"};},{}],23:[function(require,module,exports){module.exports={"Aacute":"\xC1","aacute":"\xE1","Acirc":"\xC2","acirc":"\xE2","acute":"\xB4","AElig":"\xC6","aelig":"\xE6","Agrave":"\xC0","agrave":"\xE0","amp":"&","AMP":"&","Aring":"\xC5","aring":"\xE5","Atilde":"\xC3","atilde":"\xE3","Auml":"\xC4","auml":"\xE4","brvbar":"\xA6","Ccedil":"\xC7","ccedil":"\xE7","cedil":"\xB8","cent":"\xA2","copy":"\xA9","COPY":"\xA9","curren":"\xA4","deg":"\xB0","divide":"\xF7","Eacute":"\xC9","eacute":"\xE9","Ecirc":"\xCA","ecirc":"\xEA","Egrave":"\xC8","egrave":"\xE8","ETH":"\xD0","eth":"\xF0","Euml":"\xCB","euml":"\xEB","frac12":"\xBD","frac14":"\xBC","frac34":"\xBE","gt":">","GT":">","Iacute":"\xCD","iacute":"\xED","Icirc":"\xCE","icirc":"\xEE","iexcl":"\xA1","Igrave":"\xCC","igrave":"\xEC","iquest":"\xBF","Iuml":"\xCF","iuml":"\xEF","laquo":"\xAB","lt":"<","LT":"<","macr":"\xAF","micro":"\xB5","middot":"\xB7","nbsp":"\xA0","not":"\xAC","Ntilde":"\xD1","ntilde":"\xF1","Oacute":"\xD3","oacute":"\xF3","Ocirc":"\xD4","ocirc":"\xF4","Ograve":"\xD2","ograve":"\xF2","ordf":"\xAA","ordm":"\xBA","Oslash":"\xD8","oslash":"\xF8","Otilde":"\xD5","otilde":"\xF5","Ouml":"\xD6","ouml":"\xF6","para":"\xB6","plusmn":"\xB1","pound":"\xA3","quot":"\"","QUOT":"\"","raquo":"\xBB","reg":"\xAE","REG":"\xAE","sect":"\xA7","shy":"\xAD","sup1":"\xB9","sup2":"\xB2","sup3":"\xB3","szlig":"\xDF","THORN":"\xDE","thorn":"\xFE","times":"\xD7","Uacute":"\xDA","uacute":"\xFA","Ucirc":"\xDB","ucirc":"\xFB","Ugrave":"\xD9","ugrave":"\xF9","uml":"\xA8","Uuml":"\xDC","uuml":"\xFC","Yacute":"\xDD","yacute":"\xFD","yen":"\xA5","yuml":"\xFF"};},{}],24:[function(require,module,exports){module.exports={"amp":"&","apos":"'","gt":">","lt":"<","quot":"\""};},{}],25:[function(require,module,exports){// Copyright Joyent, Inc. and other Node contributors.
//
// Permission is hereby granted, free of charge, to any person obtaining a
// copy of this software and associated documentation files (the
// "Software"), to deal in the Software without restriction, including
// without limitation the rights to use, copy, modify, merge, publish,
// distribute, sublicense, and/or sell copies of the Software, and to permit
// persons to whom the Software is furnished to do so, subject to the
// following conditions:
//
// The above copyright notice and this permission notice shall be included
// in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
// OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
// NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
// DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
// OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
// USE OR OTHER DEALINGS IN THE SOFTWARE.
var objectCreate=Object.create||objectCreatePolyfill;var objectKeys=Object.keys||objectKeysPolyfill;var bind=Function.prototype.bind||functionBindPolyfill;function EventEmitter(){if(!this._events||!Object.prototype.hasOwnProperty.call(this,'_events')){this._events=objectCreate(null);this._eventsCount=0;}this._maxListeners=this._maxListeners||undefined;}module.exports=EventEmitter;// Backwards-compat with node 0.10.x
EventEmitter.EventEmitter=EventEmitter;EventEmitter.prototype._events=undefined;EventEmitter.prototype._maxListeners=undefined;// By default EventEmitters will print a warning if more than 10 listeners are
// added to it. This is a useful default which helps finding memory leaks.
var defaultMaxListeners=10;var hasDefineProperty;try{var o={};if(Object.defineProperty)Object.defineProperty(o,'x',{value:0});hasDefineProperty=o.x===0;}catch(err){hasDefineProperty=false;}if(hasDefineProperty){Object.defineProperty(EventEmitter,'defaultMaxListeners',{enumerable:true,get:function get(){return defaultMaxListeners;},set:function set(arg){// check whether the input is a positive number (whose value is zero or
// greater and not a NaN).
if(typeof arg!=='number'||arg<0||arg!==arg)throw new TypeError('"defaultMaxListeners" must be a positive number');defaultMaxListeners=arg;}});}else{EventEmitter.defaultMaxListeners=defaultMaxListeners;}// Obviously not all Emitters should be limited to 10. This function allows
// that to be increased. Set to zero for unlimited.
EventEmitter.prototype.setMaxListeners=function setMaxListeners(n){if(typeof n!=='number'||n<0||isNaN(n))throw new TypeError('"n" argument must be a positive number');this._maxListeners=n;return this;};function $getMaxListeners(that){if(that._maxListeners===undefined)return EventEmitter.defaultMaxListeners;return that._maxListeners;}EventEmitter.prototype.getMaxListeners=function getMaxListeners(){return $getMaxListeners(this);};// These standalone emit* functions are used to optimize calling of event
// handlers for fast cases because emit() itself often has a variable number of
// arguments and can be deoptimized because of that. These functions always have
// the same number of arguments and thus do not get deoptimized, so the code
// inside them can execute faster.
function emitNone(handler,isFn,self){if(isFn)handler.call(self);else{var len=handler.length;var listeners=arrayClone(handler,len);for(var i=0;i<len;++i){listeners[i].call(self);}}}function emitOne(handler,isFn,self,arg1){if(isFn)handler.call(self,arg1);else{var len=handler.length;var listeners=arrayClone(handler,len);for(var i=0;i<len;++i){listeners[i].call(self,arg1);}}}function emitTwo(handler,isFn,self,arg1,arg2){if(isFn)handler.call(self,arg1,arg2);else{var len=handler.length;var listeners=arrayClone(handler,len);for(var i=0;i<len;++i){listeners[i].call(self,arg1,arg2);}}}function emitThree(handler,isFn,self,arg1,arg2,arg3){if(isFn)handler.call(self,arg1,arg2,arg3);else{var len=handler.length;var listeners=arrayClone(handler,len);for(var i=0;i<len;++i){listeners[i].call(self,arg1,arg2,arg3);}}}function emitMany(handler,isFn,self,args){if(isFn)handler.apply(self,args);else{var len=handler.length;var listeners=arrayClone(handler,len);for(var i=0;i<len;++i){listeners[i].apply(self,args);}}}EventEmitter.prototype.emit=function emit(type){var er,handler,len,args,i,events;var doError=type==='error';events=this._events;if(events)doError=doError&&events.error==null;else if(!doError)return false;// If there is no 'error' event listener then throw.
if(doError){if(arguments.length>1)er=arguments[1];if(er instanceof Error){throw er;// Unhandled 'error' event
}else{// At least give some kind of context to the user
var err=new Error('Unhandled "error" event. ('+er+')');err.context=er;throw err;}return false;}handler=events[type];if(!handler)return false;var isFn=typeof handler==='function';len=arguments.length;switch(len){// fast cases
case 1:emitNone(handler,isFn,this);break;case 2:emitOne(handler,isFn,this,arguments[1]);break;case 3:emitTwo(handler,isFn,this,arguments[1],arguments[2]);break;case 4:emitThree(handler,isFn,this,arguments[1],arguments[2],arguments[3]);break;// slower
default:args=new Array(len-1);for(i=1;i<len;i++){args[i-1]=arguments[i];}emitMany(handler,isFn,this,args);}return true;};function _addListener(target,type,listener,prepend){var m;var events;var existing;if(typeof listener!=='function')throw new TypeError('"listener" argument must be a function');events=target._events;if(!events){events=target._events=objectCreate(null);target._eventsCount=0;}else{// To avoid recursion in the case that type === "newListener"! Before
// adding it to the listeners, first emit "newListener".
if(events.newListener){target.emit('newListener',type,listener.listener?listener.listener:listener);// Re-assign `events` because a newListener handler could have caused the
// this._events to be assigned to a new object
events=target._events;}existing=events[type];}if(!existing){// Optimize the case of one listener. Don't need the extra array object.
existing=events[type]=listener;++target._eventsCount;}else{if(typeof existing==='function'){// Adding the second element, need to change to array.
existing=events[type]=prepend?[listener,existing]:[existing,listener];}else{// If we've already got an array, just append.
if(prepend){existing.unshift(listener);}else{existing.push(listener);}}// Check for listener leak
if(!existing.warned){m=$getMaxListeners(target);if(m&&m>0&&existing.length>m){existing.warned=true;var w=new Error('Possible EventEmitter memory leak detected. '+existing.length+' "'+String(type)+'" listeners '+'added. Use emitter.setMaxListeners() to '+'increase limit.');w.name='MaxListenersExceededWarning';w.emitter=target;w.type=type;w.count=existing.length;if((typeof console==="undefined"?"undefined":_typeof(console))==='object'&&console.warn){console.warn('%s: %s',w.name,w.message);}}}}return target;}EventEmitter.prototype.addListener=function addListener(type,listener){return _addListener(this,type,listener,false);};EventEmitter.prototype.on=EventEmitter.prototype.addListener;EventEmitter.prototype.prependListener=function prependListener(type,listener){return _addListener(this,type,listener,true);};function onceWrapper(){if(!this.fired){this.target.removeListener(this.type,this.wrapFn);this.fired=true;switch(arguments.length){case 0:return this.listener.call(this.target);case 1:return this.listener.call(this.target,arguments[0]);case 2:return this.listener.call(this.target,arguments[0],arguments[1]);case 3:return this.listener.call(this.target,arguments[0],arguments[1],arguments[2]);default:var args=new Array(arguments.length);for(var i=0;i<args.length;++i){args[i]=arguments[i];}this.listener.apply(this.target,args);}}}function _onceWrap(target,type,listener){var state={fired:false,wrapFn:undefined,target:target,type:type,listener:listener};var wrapped=bind.call(onceWrapper,state);wrapped.listener=listener;state.wrapFn=wrapped;return wrapped;}EventEmitter.prototype.once=function once(type,listener){if(typeof listener!=='function')throw new TypeError('"listener" argument must be a function');this.on(type,_onceWrap(this,type,listener));return this;};EventEmitter.prototype.prependOnceListener=function prependOnceListener(type,listener){if(typeof listener!=='function')throw new TypeError('"listener" argument must be a function');this.prependListener(type,_onceWrap(this,type,listener));return this;};// Emits a 'removeListener' event if and only if the listener was removed.
EventEmitter.prototype.removeListener=function removeListener(type,listener){var list,events,position,i,originalListener;if(typeof listener!=='function')throw new TypeError('"listener" argument must be a function');events=this._events;if(!events)return this;list=events[type];if(!list)return this;if(list===listener||list.listener===listener){if(--this._eventsCount===0)this._events=objectCreate(null);else{delete events[type];if(events.removeListener)this.emit('removeListener',type,list.listener||listener);}}else if(typeof list!=='function'){position=-1;for(i=list.length-1;i>=0;i--){if(list[i]===listener||list[i].listener===listener){originalListener=list[i].listener;position=i;break;}}if(position<0)return this;if(position===0)list.shift();else spliceOne(list,position);if(list.length===1)events[type]=list[0];if(events.removeListener)this.emit('removeListener',type,originalListener||listener);}return this;};EventEmitter.prototype.removeAllListeners=function removeAllListeners(type){var listeners,events,i;events=this._events;if(!events)return this;// not listening for removeListener, no need to emit
if(!events.removeListener){if(arguments.length===0){this._events=objectCreate(null);this._eventsCount=0;}else if(events[type]){if(--this._eventsCount===0)this._events=objectCreate(null);else delete events[type];}return this;}// emit removeListener for all listeners on all events
if(arguments.length===0){var keys=objectKeys(events);var key;for(i=0;i<keys.length;++i){key=keys[i];if(key==='removeListener')continue;this.removeAllListeners(key);}this.removeAllListeners('removeListener');this._events=objectCreate(null);this._eventsCount=0;return this;}listeners=events[type];if(typeof listeners==='function'){this.removeListener(type,listeners);}else if(listeners){// LIFO order
for(i=listeners.length-1;i>=0;i--){this.removeListener(type,listeners[i]);}}return this;};function _listeners(target,type,unwrap){var events=target._events;if(!events)return[];var evlistener=events[type];if(!evlistener)return[];if(typeof evlistener==='function')return unwrap?[evlistener.listener||evlistener]:[evlistener];return unwrap?unwrapListeners(evlistener):arrayClone(evlistener,evlistener.length);}EventEmitter.prototype.listeners=function listeners(type){return _listeners(this,type,true);};EventEmitter.prototype.rawListeners=function rawListeners(type){return _listeners(this,type,false);};EventEmitter.listenerCount=function(emitter,type){if(typeof emitter.listenerCount==='function'){return emitter.listenerCount(type);}else{return listenerCount.call(emitter,type);}};EventEmitter.prototype.listenerCount=listenerCount;function listenerCount(type){var events=this._events;if(events){var evlistener=events[type];if(typeof evlistener==='function'){return 1;}else if(evlistener){return evlistener.length;}}return 0;}EventEmitter.prototype.eventNames=function eventNames(){return this._eventsCount>0?Reflect.ownKeys(this._events):[];};// About 1.5x faster than the two-arg version of Array#splice().
function spliceOne(list,index){for(var i=index,k=i+1,n=list.length;k<n;i+=1,k+=1){list[i]=list[k];}list.pop();}function arrayClone(arr,n){var copy=new Array(n);for(var i=0;i<n;++i){copy[i]=arr[i];}return copy;}function unwrapListeners(arr){var ret=new Array(arr.length);for(var i=0;i<ret.length;++i){ret[i]=arr[i].listener||arr[i];}return ret;}function objectCreatePolyfill(proto){var F=function F(){};F.prototype=proto;return new F();}function objectKeysPolyfill(obj){var keys=[];for(var k in obj){if(Object.prototype.hasOwnProperty.call(obj,k)){keys.push(k);}}return k;}function functionBindPolyfill(context){var fn=this;return function(){return fn.apply(context,arguments);};}},{}],26:[function(require,module,exports){"use strict";var __extends=this&&this.__extends||function(){var _extendStatics2=function extendStatics(d,b){_extendStatics2=Object.setPrototypeOf||{__proto__:[]}instanceof Array&&function(d,b){d.__proto__=b;}||function(d,b){for(var p in b){if(b.hasOwnProperty(p))d[p]=b[p];}};return _extendStatics2(d,b);};return function(d,b){_extendStatics2(d,b);function __(){this.constructor=d;}d.prototype=b===null?Object.create(b):(__.prototype=b.prototype,new __());};}();var __importDefault=this&&this.__importDefault||function(mod){return mod&&mod.__esModule?mod:{"default":mod};};Object.defineProperty(exports,"__esModule",{value:true});var MultiplexHandler_1=__importDefault(require("./MultiplexHandler"));var CollectingHandler=/** @class */function(_super){__extends(CollectingHandler,_super);function CollectingHandler(cbs){if(cbs===void 0){cbs={};}var _this=_super.call(this,function(name){var _a;var args=[];for(var _i=1;_i<arguments.length;_i++){args[_i-1]=arguments[_i];}_this.events.push([name].concat(args));// @ts-ignore
if(_this._cbs[name])(_a=_this._cbs)[name].apply(_a,args);})||this;_this._cbs=cbs;_this.events=[];return _this;}CollectingHandler.prototype.onreset=function(){this.events=[];if(this._cbs.onreset)this._cbs.onreset();};CollectingHandler.prototype.restart=function(){var _a;if(this._cbs.onreset)this._cbs.onreset();for(var i=0;i<this.events.length;i++){var _b=this.events[i],name_1=_b[0],args=_b.slice(1);if(!this._cbs[name_1]){continue;}// @ts-ignore
(_a=this._cbs)[name_1].apply(_a,args);}};return CollectingHandler;}(MultiplexHandler_1["default"]);exports.CollectingHandler=CollectingHandler;},{"./MultiplexHandler":28}],27:[function(require,module,exports){"use strict";var __extends=this&&this.__extends||function(){var _extendStatics3=function extendStatics(d,b){_extendStatics3=Object.setPrototypeOf||{__proto__:[]}instanceof Array&&function(d,b){d.__proto__=b;}||function(d,b){for(var p in b){if(b.hasOwnProperty(p))d[p]=b[p];}};return _extendStatics3(d,b);};return function(d,b){_extendStatics3(d,b);function __(){this.constructor=d;}d.prototype=b===null?Object.create(b):(__.prototype=b.prototype,new __());};}();var __importDefault=this&&this.__importDefault||function(mod){return mod&&mod.__esModule?mod:{"default":mod};};var __importStar=this&&this.__importStar||function(mod){if(mod&&mod.__esModule)return mod;var result={};if(mod!=null)for(var k in mod){if(Object.hasOwnProperty.call(mod,k))result[k]=mod[k];}result["default"]=mod;return result;};Object.defineProperty(exports,"__esModule",{value:true});var domhandler_1=__importDefault(require("domhandler"));var DomUtils=__importStar(require("domutils"));var Parser_1=require("./Parser");//TODO: Consume data as it is coming in
var FeedHandler=/** @class */function(_super){__extends(FeedHandler,_super);/**
     *
     * @param callback
     * @param options
     */function FeedHandler(callback,options){var _this=this;if(_typeof(callback)==="object"&&callback!==null){callback=undefined;options=callback;}_this=_super.call(this,callback,options)||this;return _this;}FeedHandler.prototype.onend=function(){var feed={};var feedRoot=getOneElement(isValidFeed,this.dom);if(feedRoot){if(feedRoot.name==="feed"){var childs=feedRoot.children;feed.type="atom";addConditionally(feed,"id","id",childs);addConditionally(feed,"title","title",childs);var href=getAttribute("href",getOneElement("link",childs));if(href){feed.link=href;}addConditionally(feed,"description","subtitle",childs);var updated=fetch("updated",childs);if(updated){feed.updated=new Date(updated);}addConditionally(feed,"author","email",childs,true);feed.items=getElements("entry",childs).map(function(item){var entry={};var children=item.children;addConditionally(entry,"id","id",children);addConditionally(entry,"title","title",children);var href=getAttribute("href",getOneElement("link",children));if(href){entry.link=href;}var description=fetch("summary",children)||fetch("content",children);if(description){entry.description=description;}var pubDate=fetch("updated",children);if(pubDate){entry.pubDate=new Date(pubDate);}return entry;});}else{var childs=getOneElement("channel",feedRoot.children).children;feed.type=feedRoot.name.substr(0,3);feed.id="";addConditionally(feed,"title","title",childs);addConditionally(feed,"link","link",childs);addConditionally(feed,"description","description",childs);var updated=fetch("lastBuildDate",childs);if(updated){feed.updated=new Date(updated);}addConditionally(feed,"author","managingEditor",childs,true);feed.items=getElements("item",feedRoot.children).map(function(item){var entry={};var children=item.children;addConditionally(entry,"id","guid",children);addConditionally(entry,"title","title",children);addConditionally(entry,"link","link",children);addConditionally(entry,"description","description",children);var pubDate=fetch("pubDate",children);if(pubDate)entry.pubDate=new Date(pubDate);return entry;});}}this.feed=feed;this.handleCallback(feedRoot?null:Error("couldn't find root of feed"));};return FeedHandler;}(domhandler_1["default"]);exports.FeedHandler=FeedHandler;function getElements(what,where){return DomUtils.getElementsByTagName(what,where,true);}function getOneElement(what,where){return DomUtils.getElementsByTagName(what,where,true,1)[0];}function fetch(what,where,recurse){if(recurse===void 0){recurse=false;}return DomUtils.getText(DomUtils.getElementsByTagName(what,where,recurse,1)).trim();}function getAttribute(name,elem){if(!elem){return null;}var attribs=elem.attribs;return attribs[name];}function addConditionally(obj,prop,what,where,recurse){if(recurse===void 0){recurse=false;}var tmp=fetch(what,where,recurse);// @ts-ignore
if(tmp)obj[prop]=tmp;}function isValidFeed(value){return value==="rss"||value==="feed"||value==="rdf:RDF";}var defaultOptions={xmlMode:true};/**
 * Parse a feed.
 *
 * @param feed The feed that should be parsed, as a string.
 * @param options Optionally, options for parsing. When using this option, you probably want to set `xmlMode` to `true`.
 */function parseFeed(feed,options){if(options===void 0){options=defaultOptions;}var handler=new FeedHandler(options);new Parser_1.Parser(handler,options).end(feed);return handler.feed;}exports.parseFeed=parseFeed;},{"./Parser":29,"domhandler":7,"domutils":10}],28:[function(require,module,exports){"use strict";Object.defineProperty(exports,"__esModule",{value:true});/**
 * Calls a specific handler function for all events that are encountered.
 *
 * @param func — The function to multiplex all events to.
 */var MultiplexHandler=/** @class */function(){function MultiplexHandler(func){this._func=func;}/* Format: eventname: number of arguments */MultiplexHandler.prototype.onattribute=function(name,value){this._func("onattribute",name,value);};MultiplexHandler.prototype.oncdatastart=function(){this._func("oncdatastart");};MultiplexHandler.prototype.oncdataend=function(){this._func("oncdataend");};MultiplexHandler.prototype.ontext=function(text){this._func("ontext",text);};MultiplexHandler.prototype.onprocessinginstruction=function(name,value){this._func("onprocessinginstruction",name,value);};MultiplexHandler.prototype.oncomment=function(comment){this._func("oncomment",comment);};MultiplexHandler.prototype.oncommentend=function(){this._func("oncommentend");};MultiplexHandler.prototype.onclosetag=function(name){this._func("onclosetag",name);};MultiplexHandler.prototype.onopentag=function(name,attribs){this._func("onopentag",name,attribs);};MultiplexHandler.prototype.onopentagname=function(name){this._func("onopentagname",name);};MultiplexHandler.prototype.onerror=function(error){this._func("onerror",error);};MultiplexHandler.prototype.onend=function(){this._func("onend");};MultiplexHandler.prototype.onparserinit=function(parser){this._func("onparserinit",parser);};MultiplexHandler.prototype.onreset=function(){this._func("onreset");};return MultiplexHandler;}();exports["default"]=MultiplexHandler;},{}],29:[function(require,module,exports){"use strict";var __extends=this&&this.__extends||function(){var _extendStatics4=function extendStatics(d,b){_extendStatics4=Object.setPrototypeOf||{__proto__:[]}instanceof Array&&function(d,b){d.__proto__=b;}||function(d,b){for(var p in b){if(b.hasOwnProperty(p))d[p]=b[p];}};return _extendStatics4(d,b);};return function(d,b){_extendStatics4(d,b);function __(){this.constructor=d;}d.prototype=b===null?Object.create(b):(__.prototype=b.prototype,new __());};}();var __importDefault=this&&this.__importDefault||function(mod){return mod&&mod.__esModule?mod:{"default":mod};};Object.defineProperty(exports,"__esModule",{value:true});var Tokenizer_1=__importDefault(require("./Tokenizer"));var events_1=require("events");var formTags=new Set(["input","option","optgroup","select","button","datalist","textarea"]);var pTag=new Set(["p"]);var openImpliesClose={tr:new Set(["tr","th","td"]),th:new Set(["th"]),td:new Set(["thead","th","td"]),body:new Set(["head","link","script"]),li:new Set(["li"]),p:pTag,h1:pTag,h2:pTag,h3:pTag,h4:pTag,h5:pTag,h6:pTag,select:formTags,input:formTags,output:formTags,button:formTags,datalist:formTags,textarea:formTags,option:new Set(["option"]),optgroup:new Set(["optgroup","option"]),dd:new Set(["dt","dd"]),dt:new Set(["dt","dd"]),address:pTag,article:pTag,aside:pTag,blockquote:pTag,details:pTag,div:pTag,dl:pTag,fieldset:pTag,figcaption:pTag,figure:pTag,footer:pTag,form:pTag,header:pTag,hr:pTag,main:pTag,nav:pTag,ol:pTag,pre:pTag,section:pTag,table:pTag,ul:pTag,rt:new Set(["rt","rp"]),rp:new Set(["rt","rp"]),tbody:new Set(["thead","tbody"]),tfoot:new Set(["thead","tbody"])};var voidElements=new Set(["area","base","basefont","br","col","command","embed","frame","hr","img","input","isindex","keygen","link","meta","param","source","track","wbr"]);var foreignContextElements=new Set(["math","svg"]);var htmlIntegrationElements=new Set(["mi","mo","mn","ms","mtext","annotation-xml","foreignObject","desc","title"]);var reNameEnd=/\s|\//;var Parser=/** @class */function(_super){__extends(Parser,_super);function Parser(cbs,options){var _this=_super.call(this)||this;_this._tagname="";_this._attribname="";_this._attribvalue="";_this._attribs=null;_this._stack=[];_this._foreignContext=[];_this.startIndex=0;_this.endIndex=null;// Aliases for backwards compatibility
_this.parseChunk=Parser.prototype.write;_this.done=Parser.prototype.end;_this._options=options||{};_this._cbs=cbs||{};_this._tagname="";_this._attribname="";_this._attribvalue="";_this._attribs=null;_this._stack=[];_this._foreignContext=[];_this.startIndex=0;_this.endIndex=null;_this._lowerCaseTagNames="lowerCaseTags"in _this._options?!!_this._options.lowerCaseTags:!_this._options.xmlMode;_this._lowerCaseAttributeNames="lowerCaseAttributeNames"in _this._options?!!_this._options.lowerCaseAttributeNames:!_this._options.xmlMode;_this._tokenizer=new(_this._options.Tokenizer||Tokenizer_1["default"])(_this._options,_this);if(_this._cbs.onparserinit)_this._cbs.onparserinit(_this);return _this;}Parser.prototype._updatePosition=function(initialOffset){if(this.endIndex===null){if(this._tokenizer._sectionStart<=initialOffset){this.startIndex=0;}else{this.startIndex=this._tokenizer._sectionStart-initialOffset;}}else this.startIndex=this.endIndex+1;this.endIndex=this._tokenizer.getAbsoluteIndex();};//Tokenizer event handlers
Parser.prototype.ontext=function(data){this._updatePosition(1);// @ts-ignore
this.endIndex--;if(this._cbs.ontext)this._cbs.ontext(data);};Parser.prototype.onopentagname=function(name){if(this._lowerCaseTagNames){name=name.toLowerCase();}this._tagname=name;if(!this._options.xmlMode&&Object.prototype.hasOwnProperty.call(openImpliesClose,name)){for(var el=void 0;// @ts-ignore
openImpliesClose[name].has(el=this._stack[this._stack.length-1]);this.onclosetag(el)){;}}if(this._options.xmlMode||!voidElements.has(name)){this._stack.push(name);if(foreignContextElements.has(name)){this._foreignContext.push(true);}else if(htmlIntegrationElements.has(name)){this._foreignContext.push(false);}}if(this._cbs.onopentagname)this._cbs.onopentagname(name);if(this._cbs.onopentag)this._attribs={};};Parser.prototype.onopentagend=function(){this._updatePosition(1);if(this._attribs){if(this._cbs.onopentag){this._cbs.onopentag(this._tagname,this._attribs);}this._attribs=null;}if(!this._options.xmlMode&&this._cbs.onclosetag&&voidElements.has(this._tagname)){this._cbs.onclosetag(this._tagname);}this._tagname="";};Parser.prototype.onclosetag=function(name){this._updatePosition(1);if(this._lowerCaseTagNames){name=name.toLowerCase();}if(foreignContextElements.has(name)||htmlIntegrationElements.has(name)){this._foreignContext.pop();}if(this._stack.length&&(this._options.xmlMode||!voidElements.has(name))){var pos=this._stack.lastIndexOf(name);if(pos!==-1){if(this._cbs.onclosetag){pos=this._stack.length-pos;// @ts-ignore
while(pos--){this._cbs.onclosetag(this._stack.pop());}}else this._stack.length=pos;}else if(name==="p"&&!this._options.xmlMode){this.onopentagname(name);this._closeCurrentTag();}}else if(!this._options.xmlMode&&(name==="br"||name==="p")){this.onopentagname(name);this._closeCurrentTag();}};Parser.prototype.onselfclosingtag=function(){if(this._options.xmlMode||this._options.recognizeSelfClosing||this._foreignContext[this._foreignContext.length-1]){this._closeCurrentTag();}else{this.onopentagend();}};Parser.prototype._closeCurrentTag=function(){var name=this._tagname;this.onopentagend();//self-closing tags will be on the top of the stack
//(cheaper check than in onclosetag)
if(this._stack[this._stack.length-1]===name){if(this._cbs.onclosetag){this._cbs.onclosetag(name);}this._stack.pop();}};Parser.prototype.onattribname=function(name){if(this._lowerCaseAttributeNames){name=name.toLowerCase();}this._attribname=name;};Parser.prototype.onattribdata=function(value){this._attribvalue+=value;};Parser.prototype.onattribend=function(){if(this._cbs.onattribute)this._cbs.onattribute(this._attribname,this._attribvalue);if(this._attribs&&!Object.prototype.hasOwnProperty.call(this._attribs,this._attribname)){this._attribs[this._attribname]=this._attribvalue;}this._attribname="";this._attribvalue="";};Parser.prototype._getInstructionName=function(value){var idx=value.search(reNameEnd);var name=idx<0?value:value.substr(0,idx);if(this._lowerCaseTagNames){name=name.toLowerCase();}return name;};Parser.prototype.ondeclaration=function(value){if(this._cbs.onprocessinginstruction){var name_1=this._getInstructionName(value);this._cbs.onprocessinginstruction("!"+name_1,"!"+value);}};Parser.prototype.onprocessinginstruction=function(value){if(this._cbs.onprocessinginstruction){var name_2=this._getInstructionName(value);this._cbs.onprocessinginstruction("?"+name_2,"?"+value);}};Parser.prototype.oncomment=function(value){this._updatePosition(4);if(this._cbs.oncomment)this._cbs.oncomment(value);if(this._cbs.oncommentend)this._cbs.oncommentend();};Parser.prototype.oncdata=function(value){this._updatePosition(1);if(this._options.xmlMode||this._options.recognizeCDATA){if(this._cbs.oncdatastart)this._cbs.oncdatastart();if(this._cbs.ontext)this._cbs.ontext(value);if(this._cbs.oncdataend)this._cbs.oncdataend();}else{this.oncomment("[CDATA["+value+"]]");}};Parser.prototype.onerror=function(err){if(this._cbs.onerror)this._cbs.onerror(err);};Parser.prototype.onend=function(){if(this._cbs.onclosetag){for(var i=this._stack.length;i>0;this._cbs.onclosetag(this._stack[--i])){;}}if(this._cbs.onend)this._cbs.onend();};//Resets the parser to a blank state, ready to parse a new HTML document
Parser.prototype.reset=function(){if(this._cbs.onreset)this._cbs.onreset();this._tokenizer.reset();this._tagname="";this._attribname="";this._attribs=null;this._stack=[];if(this._cbs.onparserinit)this._cbs.onparserinit(this);};//Parses a complete HTML document and pushes it to the handler
Parser.prototype.parseComplete=function(data){this.reset();this.end(data);};Parser.prototype.write=function(chunk){this._tokenizer.write(chunk);};Parser.prototype.end=function(chunk){this._tokenizer.end(chunk);};Parser.prototype.pause=function(){this._tokenizer.pause();};Parser.prototype.resume=function(){this._tokenizer.resume();};return Parser;}(events_1.EventEmitter);exports.Parser=Parser;},{"./Tokenizer":30,"events":25}],30:[function(require,module,exports){"use strict";var __importDefault=this&&this.__importDefault||function(mod){return mod&&mod.__esModule?mod:{"default":mod};};Object.defineProperty(exports,"__esModule",{value:true});var decode_codepoint_1=__importDefault(require("entities/lib/decode_codepoint"));var entities_json_1=__importDefault(require("entities/lib/maps/entities.json"));var legacy_json_1=__importDefault(require("entities/lib/maps/legacy.json"));var xml_json_1=__importDefault(require("entities/lib/maps/xml.json"));function whitespace(c){return c===" "||c==="\n"||c==="\t"||c==="\f"||c==="\r";}function ifElseState(upper,SUCCESS,FAILURE){var lower=upper.toLowerCase();if(upper===lower){return function(t,c){if(c===lower){t._state=SUCCESS;}else{t._state=FAILURE;t._index--;}};}else{return function(t,c){if(c===lower||c===upper){t._state=SUCCESS;}else{t._state=FAILURE;t._index--;}};}}function consumeSpecialNameChar(upper,NEXT_STATE){var lower=upper.toLowerCase();return function(t,c){if(c===lower||c===upper){t._state=NEXT_STATE;}else{t._state=3/* InTagName */;t._index--;//consume the token again
}};}var stateBeforeCdata1=ifElseState("C",23/* BeforeCdata2 */,16/* InDeclaration */);var stateBeforeCdata2=ifElseState("D",24/* BeforeCdata3 */,16/* InDeclaration */);var stateBeforeCdata3=ifElseState("A",25/* BeforeCdata4 */,16/* InDeclaration */);var stateBeforeCdata4=ifElseState("T",26/* BeforeCdata5 */,16/* InDeclaration */);var stateBeforeCdata5=ifElseState("A",27/* BeforeCdata6 */,16/* InDeclaration */);var stateBeforeScript1=consumeSpecialNameChar("R",34/* BeforeScript2 */);var stateBeforeScript2=consumeSpecialNameChar("I",35/* BeforeScript3 */);var stateBeforeScript3=consumeSpecialNameChar("P",36/* BeforeScript4 */);var stateBeforeScript4=consumeSpecialNameChar("T",37/* BeforeScript5 */);var stateAfterScript1=ifElseState("R",39/* AfterScript2 */,1/* Text */);var stateAfterScript2=ifElseState("I",40/* AfterScript3 */,1/* Text */);var stateAfterScript3=ifElseState("P",41/* AfterScript4 */,1/* Text */);var stateAfterScript4=ifElseState("T",42/* AfterScript5 */,1/* Text */);var stateBeforeStyle1=consumeSpecialNameChar("Y",44/* BeforeStyle2 */);var stateBeforeStyle2=consumeSpecialNameChar("L",45/* BeforeStyle3 */);var stateBeforeStyle3=consumeSpecialNameChar("E",46/* BeforeStyle4 */);var stateAfterStyle1=ifElseState("Y",48/* AfterStyle2 */,1/* Text */);var stateAfterStyle2=ifElseState("L",49/* AfterStyle3 */,1/* Text */);var stateAfterStyle3=ifElseState("E",50/* AfterStyle4 */,1/* Text */);var stateBeforeEntity=ifElseState("#",52/* BeforeNumericEntity */,53/* InNamedEntity */);var stateBeforeNumericEntity=ifElseState("X",55/* InHexEntity */,54/* InNumericEntity */);var Tokenizer=/** @class */function(){function Tokenizer(options,cbs){/** The current state the tokenizer is in. */this._state=1/* Text */;/** The read buffer. */this._buffer="";/** The beginning of the section that is currently being read. */this._sectionStart=0;/** The index within the buffer that we are currently looking at. */this._index=0;/**
         * Data that has already been processed will be removed from the buffer occasionally.
         * `_bufferOffset` keeps track of how many characters have been removed, to make sure position information is accurate.
         */this._bufferOffset=0;/** Some behavior, eg. when decoding entities, is done while we are in another state. This keeps track of the other state type. */this._baseState=1/* Text */;/** For special parsing behavior inside of script and style tags. */this._special=1/* None */;/** Indicates whether the tokenizer has been paused. */this._running=true;/** Indicates whether the tokenizer has finished running / `.end` has been called. */this._ended=false;this._cbs=cbs;this._xmlMode=!!(options&&options.xmlMode);this._decodeEntities=!!(options&&options.decodeEntities);}Tokenizer.prototype.reset=function(){this._state=1/* Text */;this._buffer="";this._sectionStart=0;this._index=0;this._bufferOffset=0;this._baseState=1/* Text */;this._special=1/* None */;this._running=true;this._ended=false;};Tokenizer.prototype._stateText=function(c){if(c==="<"){if(this._index>this._sectionStart){this._cbs.ontext(this._getSection());}this._state=2/* BeforeTagName */;this._sectionStart=this._index;}else if(this._decodeEntities&&this._special===1/* None */&&c==="&"){if(this._index>this._sectionStart){this._cbs.ontext(this._getSection());}this._baseState=1/* Text */;this._state=51/* BeforeEntity */;this._sectionStart=this._index;}};Tokenizer.prototype._stateBeforeTagName=function(c){if(c==="/"){this._state=5/* BeforeClosingTagName */;}else if(c==="<"){this._cbs.ontext(this._getSection());this._sectionStart=this._index;}else if(c===">"||this._special!==1/* None */||whitespace(c)){this._state=1/* Text */;}else if(c==="!"){this._state=15/* BeforeDeclaration */;this._sectionStart=this._index+1;}else if(c==="?"){this._state=17/* InProcessingInstruction */;this._sectionStart=this._index+1;}else{this._state=!this._xmlMode&&(c==="s"||c==="S")?31/* BeforeSpecial */:3/* InTagName */;this._sectionStart=this._index;}};Tokenizer.prototype._stateInTagName=function(c){if(c==="/"||c===">"||whitespace(c)){this._emitToken("onopentagname");this._state=8/* BeforeAttributeName */;this._index--;}};Tokenizer.prototype._stateBeforeClosingTagName=function(c){if(whitespace(c)){// ignore
}else if(c===">"){this._state=1/* Text */;}else if(this._special!==1/* None */){if(c==="s"||c==="S"){this._state=32/* BeforeSpecialEnd */;}else{this._state=1/* Text */;this._index--;}}else{this._state=6/* InClosingTagName */;this._sectionStart=this._index;}};Tokenizer.prototype._stateInClosingTagName=function(c){if(c===">"||whitespace(c)){this._emitToken("onclosetag");this._state=7/* AfterClosingTagName */;this._index--;}};Tokenizer.prototype._stateAfterClosingTagName=function(c){//skip everything until ">"
if(c===">"){this._state=1/* Text */;this._sectionStart=this._index+1;}};Tokenizer.prototype._stateBeforeAttributeName=function(c){if(c===">"){this._cbs.onopentagend();this._state=1/* Text */;this._sectionStart=this._index+1;}else if(c==="/"){this._state=4/* InSelfClosingTag */;}else if(!whitespace(c)){this._state=9/* InAttributeName */;this._sectionStart=this._index;}};Tokenizer.prototype._stateInSelfClosingTag=function(c){if(c===">"){this._cbs.onselfclosingtag();this._state=1/* Text */;this._sectionStart=this._index+1;}else if(!whitespace(c)){this._state=8/* BeforeAttributeName */;this._index--;}};Tokenizer.prototype._stateInAttributeName=function(c){if(c==="="||c==="/"||c===">"||whitespace(c)){this._cbs.onattribname(this._getSection());this._sectionStart=-1;this._state=10/* AfterAttributeName */;this._index--;}};Tokenizer.prototype._stateAfterAttributeName=function(c){if(c==="="){this._state=11/* BeforeAttributeValue */;}else if(c==="/"||c===">"){this._cbs.onattribend();this._state=8/* BeforeAttributeName */;this._index--;}else if(!whitespace(c)){this._cbs.onattribend();this._state=9/* InAttributeName */;this._sectionStart=this._index;}};Tokenizer.prototype._stateBeforeAttributeValue=function(c){if(c==='"'){this._state=12/* InAttributeValueDq */;this._sectionStart=this._index+1;}else if(c==="'"){this._state=13/* InAttributeValueSq */;this._sectionStart=this._index+1;}else if(!whitespace(c)){this._state=14/* InAttributeValueNq */;this._sectionStart=this._index;this._index--;//reconsume token
}};Tokenizer.prototype._stateInAttributeValueDoubleQuotes=function(c){if(c==='"'){this._emitToken("onattribdata");this._cbs.onattribend();this._state=8/* BeforeAttributeName */;}else if(this._decodeEntities&&c==="&"){this._emitToken("onattribdata");this._baseState=this._state;this._state=51/* BeforeEntity */;this._sectionStart=this._index;}};Tokenizer.prototype._stateInAttributeValueSingleQuotes=function(c){if(c==="'"){this._emitToken("onattribdata");this._cbs.onattribend();this._state=8/* BeforeAttributeName */;}else if(this._decodeEntities&&c==="&"){this._emitToken("onattribdata");this._baseState=this._state;this._state=51/* BeforeEntity */;this._sectionStart=this._index;}};Tokenizer.prototype._stateInAttributeValueNoQuotes=function(c){if(whitespace(c)||c===">"){this._emitToken("onattribdata");this._cbs.onattribend();this._state=8/* BeforeAttributeName */;this._index--;}else if(this._decodeEntities&&c==="&"){this._emitToken("onattribdata");this._baseState=this._state;this._state=51/* BeforeEntity */;this._sectionStart=this._index;}};Tokenizer.prototype._stateBeforeDeclaration=function(c){this._state=c==="["?22/* BeforeCdata1 */:c==="-"?18/* BeforeComment */:16/* InDeclaration */;};Tokenizer.prototype._stateInDeclaration=function(c){if(c===">"){this._cbs.ondeclaration(this._getSection());this._state=1/* Text */;this._sectionStart=this._index+1;}};Tokenizer.prototype._stateInProcessingInstruction=function(c){if(c===">"){this._cbs.onprocessinginstruction(this._getSection());this._state=1/* Text */;this._sectionStart=this._index+1;}};Tokenizer.prototype._stateBeforeComment=function(c){if(c==="-"){this._state=19/* InComment */;this._sectionStart=this._index+1;}else{this._state=16/* InDeclaration */;}};Tokenizer.prototype._stateInComment=function(c){if(c==="-")this._state=20/* AfterComment1 */;};Tokenizer.prototype._stateAfterComment1=function(c){if(c==="-"){this._state=21/* AfterComment2 */;}else{this._state=19/* InComment */;}};Tokenizer.prototype._stateAfterComment2=function(c){if(c===">"){//remove 2 trailing chars
this._cbs.oncomment(this._buffer.substring(this._sectionStart,this._index-2));this._state=1/* Text */;this._sectionStart=this._index+1;}else if(c!=="-"){this._state=19/* InComment */;}// else: stay in AFTER_COMMENT_2 (`--->`)
};Tokenizer.prototype._stateBeforeCdata6=function(c){if(c==="["){this._state=28/* InCdata */;this._sectionStart=this._index+1;}else{this._state=16/* InDeclaration */;this._index--;}};Tokenizer.prototype._stateInCdata=function(c){if(c==="]")this._state=29/* AfterCdata1 */;};Tokenizer.prototype._stateAfterCdata1=function(c){if(c==="]")this._state=30/* AfterCdata2 */;else this._state=28/* InCdata */;};Tokenizer.prototype._stateAfterCdata2=function(c){if(c===">"){//remove 2 trailing chars
this._cbs.oncdata(this._buffer.substring(this._sectionStart,this._index-2));this._state=1/* Text */;this._sectionStart=this._index+1;}else if(c!=="]"){this._state=28/* InCdata */;}//else: stay in AFTER_CDATA_2 (`]]]>`)
};Tokenizer.prototype._stateBeforeSpecial=function(c){if(c==="c"||c==="C"){this._state=33/* BeforeScript1 */;}else if(c==="t"||c==="T"){this._state=43/* BeforeStyle1 */;}else{this._state=3/* InTagName */;this._index--;//consume the token again
}};Tokenizer.prototype._stateBeforeSpecialEnd=function(c){if(this._special===2/* Script */&&(c==="c"||c==="C")){this._state=38/* AfterScript1 */;}else if(this._special===3/* Style */&&(c==="t"||c==="T")){this._state=47/* AfterStyle1 */;}else this._state=1/* Text */;};Tokenizer.prototype._stateBeforeScript5=function(c){if(c==="/"||c===">"||whitespace(c)){this._special=2/* Script */;}this._state=3/* InTagName */;this._index--;//consume the token again
};Tokenizer.prototype._stateAfterScript5=function(c){if(c===">"||whitespace(c)){this._special=1/* None */;this._state=6/* InClosingTagName */;this._sectionStart=this._index-6;this._index--;//reconsume the token
}else this._state=1/* Text */;};Tokenizer.prototype._stateBeforeStyle4=function(c){if(c==="/"||c===">"||whitespace(c)){this._special=3/* Style */;}this._state=3/* InTagName */;this._index--;//consume the token again
};Tokenizer.prototype._stateAfterStyle4=function(c){if(c===">"||whitespace(c)){this._special=1/* None */;this._state=6/* InClosingTagName */;this._sectionStart=this._index-5;this._index--;//reconsume the token
}else this._state=1/* Text */;};//for entities terminated with a semicolon
Tokenizer.prototype._parseNamedEntityStrict=function(){//offset = 1
if(this._sectionStart+1<this._index){var entity=this._buffer.substring(this._sectionStart+1,this._index),map=this._xmlMode?xml_json_1["default"]:entities_json_1["default"];if(Object.prototype.hasOwnProperty.call(map,entity)){// @ts-ignore
this._emitPartial(map[entity]);this._sectionStart=this._index+1;}}};//parses legacy entities (without trailing semicolon)
Tokenizer.prototype._parseLegacyEntity=function(){var start=this._sectionStart+1;var limit=this._index-start;if(limit>6)limit=6;// The max length of legacy entities is 6
while(limit>=2){// The min length of legacy entities is 2
var entity=this._buffer.substr(start,limit);if(Object.prototype.hasOwnProperty.call(legacy_json_1["default"],entity)){// @ts-ignore
this._emitPartial(legacy_json_1["default"][entity]);this._sectionStart+=limit+1;return;}else{limit--;}}};Tokenizer.prototype._stateInNamedEntity=function(c){if(c===";"){this._parseNamedEntityStrict();if(this._sectionStart+1<this._index&&!this._xmlMode){this._parseLegacyEntity();}this._state=this._baseState;}else if((c<"a"||c>"z")&&(c<"A"||c>"Z")&&(c<"0"||c>"9")){if(this._xmlMode||this._sectionStart+1===this._index){// ignore
}else if(this._baseState!==1/* Text */){if(c!=="="){this._parseNamedEntityStrict();}}else{this._parseLegacyEntity();}this._state=this._baseState;this._index--;}};Tokenizer.prototype._decodeNumericEntity=function(offset,base){var sectionStart=this._sectionStart+offset;if(sectionStart!==this._index){//parse entity
var entity=this._buffer.substring(sectionStart,this._index);var parsed=parseInt(entity,base);this._emitPartial(decode_codepoint_1["default"](parsed));this._sectionStart=this._index;}else{this._sectionStart--;}this._state=this._baseState;};Tokenizer.prototype._stateInNumericEntity=function(c){if(c===";"){this._decodeNumericEntity(2,10);this._sectionStart++;}else if(c<"0"||c>"9"){if(!this._xmlMode){this._decodeNumericEntity(2,10);}else{this._state=this._baseState;}this._index--;}};Tokenizer.prototype._stateInHexEntity=function(c){if(c===";"){this._decodeNumericEntity(3,16);this._sectionStart++;}else if((c<"a"||c>"f")&&(c<"A"||c>"F")&&(c<"0"||c>"9")){if(!this._xmlMode){this._decodeNumericEntity(3,16);}else{this._state=this._baseState;}this._index--;}};Tokenizer.prototype._cleanup=function(){if(this._sectionStart<0){this._buffer="";this._bufferOffset+=this._index;this._index=0;}else if(this._running){if(this._state===1/* Text */){if(this._sectionStart!==this._index){this._cbs.ontext(this._buffer.substr(this._sectionStart));}this._buffer="";this._bufferOffset+=this._index;this._index=0;}else if(this._sectionStart===this._index){//the section just started
this._buffer="";this._bufferOffset+=this._index;this._index=0;}else{//remove everything unnecessary
this._buffer=this._buffer.substr(this._sectionStart);this._index-=this._sectionStart;this._bufferOffset+=this._sectionStart;}this._sectionStart=0;}};//TODO make events conditional
Tokenizer.prototype.write=function(chunk){if(this._ended)this._cbs.onerror(Error(".write() after done!"));this._buffer+=chunk;this._parse();};// Iterates through the buffer, calling the function corresponding to the current state.
// States that are more likely to be hit are higher up, as a performance improvement.
Tokenizer.prototype._parse=function(){while(this._index<this._buffer.length&&this._running){var c=this._buffer.charAt(this._index);if(this._state===1/* Text */){this._stateText(c);}else if(this._state===12/* InAttributeValueDq */){this._stateInAttributeValueDoubleQuotes(c);}else if(this._state===9/* InAttributeName */){this._stateInAttributeName(c);}else if(this._state===19/* InComment */){this._stateInComment(c);}else if(this._state===8/* BeforeAttributeName */){this._stateBeforeAttributeName(c);}else if(this._state===3/* InTagName */){this._stateInTagName(c);}else if(this._state===6/* InClosingTagName */){this._stateInClosingTagName(c);}else if(this._state===2/* BeforeTagName */){this._stateBeforeTagName(c);}else if(this._state===10/* AfterAttributeName */){this._stateAfterAttributeName(c);}else if(this._state===13/* InAttributeValueSq */){this._stateInAttributeValueSingleQuotes(c);}else if(this._state===11/* BeforeAttributeValue */){this._stateBeforeAttributeValue(c);}else if(this._state===5/* BeforeClosingTagName */){this._stateBeforeClosingTagName(c);}else if(this._state===7/* AfterClosingTagName */){this._stateAfterClosingTagName(c);}else if(this._state===31/* BeforeSpecial */){this._stateBeforeSpecial(c);}else if(this._state===20/* AfterComment1 */){this._stateAfterComment1(c);}else if(this._state===14/* InAttributeValueNq */){this._stateInAttributeValueNoQuotes(c);}else if(this._state===4/* InSelfClosingTag */){this._stateInSelfClosingTag(c);}else if(this._state===16/* InDeclaration */){this._stateInDeclaration(c);}else if(this._state===15/* BeforeDeclaration */){this._stateBeforeDeclaration(c);}else if(this._state===21/* AfterComment2 */){this._stateAfterComment2(c);}else if(this._state===18/* BeforeComment */){this._stateBeforeComment(c);}else if(this._state===32/* BeforeSpecialEnd */){this._stateBeforeSpecialEnd(c);}else if(this._state===38/* AfterScript1 */){stateAfterScript1(this,c);}else if(this._state===39/* AfterScript2 */){stateAfterScript2(this,c);}else if(this._state===40/* AfterScript3 */){stateAfterScript3(this,c);}else if(this._state===33/* BeforeScript1 */){stateBeforeScript1(this,c);}else if(this._state===34/* BeforeScript2 */){stateBeforeScript2(this,c);}else if(this._state===35/* BeforeScript3 */){stateBeforeScript3(this,c);}else if(this._state===36/* BeforeScript4 */){stateBeforeScript4(this,c);}else if(this._state===37/* BeforeScript5 */){this._stateBeforeScript5(c);}else if(this._state===41/* AfterScript4 */){stateAfterScript4(this,c);}else if(this._state===42/* AfterScript5 */){this._stateAfterScript5(c);}else if(this._state===43/* BeforeStyle1 */){stateBeforeStyle1(this,c);}else if(this._state===28/* InCdata */){this._stateInCdata(c);}else if(this._state===44/* BeforeStyle2 */){stateBeforeStyle2(this,c);}else if(this._state===45/* BeforeStyle3 */){stateBeforeStyle3(this,c);}else if(this._state===46/* BeforeStyle4 */){this._stateBeforeStyle4(c);}else if(this._state===47/* AfterStyle1 */){stateAfterStyle1(this,c);}else if(this._state===48/* AfterStyle2 */){stateAfterStyle2(this,c);}else if(this._state===49/* AfterStyle3 */){stateAfterStyle3(this,c);}else if(this._state===50/* AfterStyle4 */){this._stateAfterStyle4(c);}else if(this._state===17/* InProcessingInstruction */){this._stateInProcessingInstruction(c);}else if(this._state===53/* InNamedEntity */){this._stateInNamedEntity(c);}else if(this._state===22/* BeforeCdata1 */){stateBeforeCdata1(this,c);}else if(this._state===51/* BeforeEntity */){stateBeforeEntity(this,c);}else if(this._state===23/* BeforeCdata2 */){stateBeforeCdata2(this,c);}else if(this._state===24/* BeforeCdata3 */){stateBeforeCdata3(this,c);}else if(this._state===29/* AfterCdata1 */){this._stateAfterCdata1(c);}else if(this._state===30/* AfterCdata2 */){this._stateAfterCdata2(c);}else if(this._state===25/* BeforeCdata4 */){stateBeforeCdata4(this,c);}else if(this._state===26/* BeforeCdata5 */){stateBeforeCdata5(this,c);}else if(this._state===27/* BeforeCdata6 */){this._stateBeforeCdata6(c);}else if(this._state===55/* InHexEntity */){this._stateInHexEntity(c);}else if(this._state===54/* InNumericEntity */){this._stateInNumericEntity(c);}else if(this._state===52/* BeforeNumericEntity */){stateBeforeNumericEntity(this,c);}else{this._cbs.onerror(Error("unknown _state"),this._state);}this._index++;}this._cleanup();};Tokenizer.prototype.pause=function(){this._running=false;};Tokenizer.prototype.resume=function(){this._running=true;if(this._index<this._buffer.length){this._parse();}if(this._ended){this._finish();}};Tokenizer.prototype.end=function(chunk){if(this._ended)this._cbs.onerror(Error(".end() after done!"));if(chunk)this.write(chunk);this._ended=true;if(this._running)this._finish();};Tokenizer.prototype._finish=function(){//if there is remaining data, emit it in a reasonable way
if(this._sectionStart<this._index){this._handleTrailingData();}this._cbs.onend();};Tokenizer.prototype._handleTrailingData=function(){var data=this._buffer.substr(this._sectionStart);if(this._state===28/* InCdata */||this._state===29/* AfterCdata1 */||this._state===30/* AfterCdata2 */){this._cbs.oncdata(data);}else if(this._state===19/* InComment */||this._state===20/* AfterComment1 */||this._state===21/* AfterComment2 */){this._cbs.oncomment(data);}else if(this._state===53/* InNamedEntity */&&!this._xmlMode){this._parseLegacyEntity();if(this._sectionStart<this._index){this._state=this._baseState;this._handleTrailingData();}}else if(this._state===54/* InNumericEntity */&&!this._xmlMode){this._decodeNumericEntity(2,10);if(this._sectionStart<this._index){this._state=this._baseState;this._handleTrailingData();}}else if(this._state===55/* InHexEntity */&&!this._xmlMode){this._decodeNumericEntity(3,16);if(this._sectionStart<this._index){this._state=this._baseState;this._handleTrailingData();}}else if(this._state!==3/* InTagName */&&this._state!==8/* BeforeAttributeName */&&this._state!==11/* BeforeAttributeValue */&&this._state!==10/* AfterAttributeName */&&this._state!==9/* InAttributeName */&&this._state!==13/* InAttributeValueSq */&&this._state!==12/* InAttributeValueDq */&&this._state!==14/* InAttributeValueNq */&&this._state!==6/* InClosingTagName */){this._cbs.ontext(data);}//else, ignore remaining data
//TODO add a way to remove current tag
};Tokenizer.prototype.getAbsoluteIndex=function(){return this._bufferOffset+this._index;};Tokenizer.prototype._getSection=function(){return this._buffer.substring(this._sectionStart,this._index);};Tokenizer.prototype._emitToken=function(name){this._cbs[name](this._getSection());this._sectionStart=-1;};Tokenizer.prototype._emitPartial=function(value){if(this._baseState!==1/* Text */){this._cbs.onattribdata(value);//TODO implement the new event
}else{this._cbs.ontext(value);}};return Tokenizer;}();exports["default"]=Tokenizer;},{"entities/lib/decode_codepoint":18,"entities/lib/maps/entities.json":22,"entities/lib/maps/legacy.json":23,"entities/lib/maps/xml.json":24}],31:[function(require,module,exports){"use strict";function __export(m){for(var p in m){if(!exports.hasOwnProperty(p))exports[p]=m[p];}}var __importStar=this&&this.__importStar||function(mod){if(mod&&mod.__esModule)return mod;var result={};if(mod!=null)for(var k in mod){if(Object.hasOwnProperty.call(mod,k))result[k]=mod[k];}result["default"]=mod;return result;};Object.defineProperty(exports,"__esModule",{value:true});var Parser_1=require("./Parser");exports.Parser=Parser_1.Parser;var domhandler_1=require("domhandler");exports.DomHandler=domhandler_1.DomHandler;exports.DefaultHandler=domhandler_1.DomHandler;// Helper methods
/**
 * Parses data, returns the resulting DOM.
 *
 * @param data The data that should be parsed.
 * @param options Optional options for the parser and DOM builder.
 */function parseDOM(data,options){var handler=new domhandler_1.DomHandler(void 0,options);new Parser_1.Parser(handler,options).end(data);return handler.dom;}exports.parseDOM=parseDOM;/**
 * Creates a parser instance, with an attached DOM handler.
 *
 * @param cb A callback that will be called once parsing has been completed.
 * @param options Optional options for the parser and DOM builder.
 * @param elementCb An optional callback that will be called every time a tag has been completed inside of the DOM.
 */function createDomStream(cb,options,elementCb){var handler=new domhandler_1.DomHandler(cb,options,elementCb);return new Parser_1.Parser(handler,options);}exports.createDomStream=createDomStream;var Tokenizer_1=require("./Tokenizer");exports.Tokenizer=Tokenizer_1["default"];var ElementType=__importStar(require("domelementtype"));exports.ElementType=ElementType;/**
 * List of all events that the parser emits.
 *
 * Format: eventname: number of arguments.
 */exports.EVENTS={attribute:2,cdatastart:0,cdataend:0,text:1,processinginstruction:2,comment:1,commentend:0,closetag:1,opentag:2,opentagname:1,error:1,end:0};/*
    All of the following exports exist for backwards-compatibility.
    They should probably be removed eventually.
*/__export(require("./FeedHandler"));__export(require("./WritableStream"));__export(require("./CollectingHandler"));var DomUtils=__importStar(require("domutils"));exports.DomUtils=DomUtils;var FeedHandler_1=require("./FeedHandler");exports.RssHandler=FeedHandler_1.FeedHandler;},{"./CollectingHandler":26,"./FeedHandler":27,"./Parser":29,"./Tokenizer":30,"./WritableStream":2,"domelementtype":6,"domhandler":7,"domutils":10}],32:[function(require,module,exports){exports.read=function(buffer,offset,isLE,mLen,nBytes){var e,m;var eLen=nBytes*8-mLen-1;var eMax=(1<<eLen)-1;var eBias=eMax>>1;var nBits=-7;var i=isLE?nBytes-1:0;var d=isLE?-1:1;var s=buffer[offset+i];i+=d;e=s&(1<<-nBits)-1;s>>=-nBits;nBits+=eLen;for(;nBits>0;e=e*256+buffer[offset+i],i+=d,nBits-=8){}m=e&(1<<-nBits)-1;e>>=-nBits;nBits+=mLen;for(;nBits>0;m=m*256+buffer[offset+i],i+=d,nBits-=8){}if(e===0){e=1-eBias;}else if(e===eMax){return m?NaN:(s?-1:1)*Infinity;}else{m=m+Math.pow(2,mLen);e=e-eBias;}return(s?-1:1)*m*Math.pow(2,e-mLen);};exports.write=function(buffer,value,offset,isLE,mLen,nBytes){var e,m,c;var eLen=nBytes*8-mLen-1;var eMax=(1<<eLen)-1;var eBias=eMax>>1;var rt=mLen===23?Math.pow(2,-24)-Math.pow(2,-77):0;var i=isLE?0:nBytes-1;var d=isLE?1:-1;var s=value<0||value===0&&1/value<0?1:0;value=Math.abs(value);if(isNaN(value)||value===Infinity){m=isNaN(value)?1:0;e=eMax;}else{e=Math.floor(Math.log(value)/Math.LN2);if(value*(c=Math.pow(2,-e))<1){e--;c*=2;}if(e+eBias>=1){value+=rt/c;}else{value+=rt*Math.pow(2,1-eBias);}if(value*c>=2){e++;c/=2;}if(e+eBias>=eMax){m=0;e=eMax;}else if(e+eBias>=1){m=(value*c-1)*Math.pow(2,mLen);e=e+eBias;}else{m=value*Math.pow(2,eBias-1)*Math.pow(2,mLen);e=0;}}for(;mLen>=8;buffer[offset+i]=m&0xff,i+=d,m/=256,mLen-=8){}e=e<<mLen|m;eLen+=mLen;for(;eLen>0;buffer[offset+i]=e&0xff,i+=d,e/=256,eLen-=8){}buffer[offset+i-d]|=s*128;};},{}],33:[function(require,module,exports){var getNative=require('./_getNative'),root=require('./_root');/* Built-in method references that are verified to be native. */var DataView=getNative(root,'DataView');module.exports=DataView;},{"./_getNative":93,"./_root":130}],34:[function(require,module,exports){var hashClear=require('./_hashClear'),hashDelete=require('./_hashDelete'),hashGet=require('./_hashGet'),hashHas=require('./_hashHas'),hashSet=require('./_hashSet');/**
 * Creates a hash object.
 *
 * @private
 * @constructor
 * @param {Array} [entries] The key-value pairs to cache.
 */function Hash(entries){var index=-1,length=entries==null?0:entries.length;this.clear();while(++index<length){var entry=entries[index];this.set(entry[0],entry[1]);}}// Add methods to `Hash`.
Hash.prototype.clear=hashClear;Hash.prototype['delete']=hashDelete;Hash.prototype.get=hashGet;Hash.prototype.has=hashHas;Hash.prototype.set=hashSet;module.exports=Hash;},{"./_hashClear":100,"./_hashDelete":101,"./_hashGet":102,"./_hashHas":103,"./_hashSet":104}],35:[function(require,module,exports){var listCacheClear=require('./_listCacheClear'),listCacheDelete=require('./_listCacheDelete'),listCacheGet=require('./_listCacheGet'),listCacheHas=require('./_listCacheHas'),listCacheSet=require('./_listCacheSet');/**
 * Creates an list cache object.
 *
 * @private
 * @constructor
 * @param {Array} [entries] The key-value pairs to cache.
 */function ListCache(entries){var index=-1,length=entries==null?0:entries.length;this.clear();while(++index<length){var entry=entries[index];this.set(entry[0],entry[1]);}}// Add methods to `ListCache`.
ListCache.prototype.clear=listCacheClear;ListCache.prototype['delete']=listCacheDelete;ListCache.prototype.get=listCacheGet;ListCache.prototype.has=listCacheHas;ListCache.prototype.set=listCacheSet;module.exports=ListCache;},{"./_listCacheClear":113,"./_listCacheDelete":114,"./_listCacheGet":115,"./_listCacheHas":116,"./_listCacheSet":117}],36:[function(require,module,exports){var getNative=require('./_getNative'),root=require('./_root');/* Built-in method references that are verified to be native. */var Map=getNative(root,'Map');module.exports=Map;},{"./_getNative":93,"./_root":130}],37:[function(require,module,exports){var mapCacheClear=require('./_mapCacheClear'),mapCacheDelete=require('./_mapCacheDelete'),mapCacheGet=require('./_mapCacheGet'),mapCacheHas=require('./_mapCacheHas'),mapCacheSet=require('./_mapCacheSet');/**
 * Creates a map cache object to store key-value pairs.
 *
 * @private
 * @constructor
 * @param {Array} [entries] The key-value pairs to cache.
 */function MapCache(entries){var index=-1,length=entries==null?0:entries.length;this.clear();while(++index<length){var entry=entries[index];this.set(entry[0],entry[1]);}}// Add methods to `MapCache`.
MapCache.prototype.clear=mapCacheClear;MapCache.prototype['delete']=mapCacheDelete;MapCache.prototype.get=mapCacheGet;MapCache.prototype.has=mapCacheHas;MapCache.prototype.set=mapCacheSet;module.exports=MapCache;},{"./_mapCacheClear":118,"./_mapCacheDelete":119,"./_mapCacheGet":120,"./_mapCacheHas":121,"./_mapCacheSet":122}],38:[function(require,module,exports){var getNative=require('./_getNative'),root=require('./_root');/* Built-in method references that are verified to be native. */var Promise=getNative(root,'Promise');module.exports=Promise;},{"./_getNative":93,"./_root":130}],39:[function(require,module,exports){var getNative=require('./_getNative'),root=require('./_root');/* Built-in method references that are verified to be native. */var Set=getNative(root,'Set');module.exports=Set;},{"./_getNative":93,"./_root":130}],40:[function(require,module,exports){var ListCache=require('./_ListCache'),stackClear=require('./_stackClear'),stackDelete=require('./_stackDelete'),stackGet=require('./_stackGet'),stackHas=require('./_stackHas'),stackSet=require('./_stackSet');/**
 * Creates a stack cache object to store key-value pairs.
 *
 * @private
 * @constructor
 * @param {Array} [entries] The key-value pairs to cache.
 */function Stack(entries){var data=this.__data__=new ListCache(entries);this.size=data.size;}// Add methods to `Stack`.
Stack.prototype.clear=stackClear;Stack.prototype['delete']=stackDelete;Stack.prototype.get=stackGet;Stack.prototype.has=stackHas;Stack.prototype.set=stackSet;module.exports=Stack;},{"./_ListCache":35,"./_stackClear":134,"./_stackDelete":135,"./_stackGet":136,"./_stackHas":137,"./_stackSet":138}],41:[function(require,module,exports){var root=require('./_root');/** Built-in value references. */var _Symbol=root.Symbol;module.exports=_Symbol;},{"./_root":130}],42:[function(require,module,exports){var root=require('./_root');/** Built-in value references. */var Uint8Array=root.Uint8Array;module.exports=Uint8Array;},{"./_root":130}],43:[function(require,module,exports){var getNative=require('./_getNative'),root=require('./_root');/* Built-in method references that are verified to be native. */var WeakMap=getNative(root,'WeakMap');module.exports=WeakMap;},{"./_getNative":93,"./_root":130}],44:[function(require,module,exports){/**
 * A faster alternative to `Function#apply`, this function invokes `func`
 * with the `this` binding of `thisArg` and the arguments of `args`.
 *
 * @private
 * @param {Function} func The function to invoke.
 * @param {*} thisArg The `this` binding of `func`.
 * @param {Array} args The arguments to invoke `func` with.
 * @returns {*} Returns the result of `func`.
 */function apply(func,thisArg,args){switch(args.length){case 0:return func.call(thisArg);case 1:return func.call(thisArg,args[0]);case 2:return func.call(thisArg,args[0],args[1]);case 3:return func.call(thisArg,args[0],args[1],args[2]);}return func.apply(thisArg,args);}module.exports=apply;},{}],45:[function(require,module,exports){/**
 * A specialized version of `_.forEach` for arrays without support for
 * iteratee shorthands.
 *
 * @private
 * @param {Array} [array] The array to iterate over.
 * @param {Function} iteratee The function invoked per iteration.
 * @returns {Array} Returns `array`.
 */function arrayEach(array,iteratee){var index=-1,length=array==null?0:array.length;while(++index<length){if(iteratee(array[index],index,array)===false){break;}}return array;}module.exports=arrayEach;},{}],46:[function(require,module,exports){/**
 * A specialized version of `_.filter` for arrays without support for
 * iteratee shorthands.
 *
 * @private
 * @param {Array} [array] The array to iterate over.
 * @param {Function} predicate The function invoked per iteration.
 * @returns {Array} Returns the new filtered array.
 */function arrayFilter(array,predicate){var index=-1,length=array==null?0:array.length,resIndex=0,result=[];while(++index<length){var value=array[index];if(predicate(value,index,array)){result[resIndex++]=value;}}return result;}module.exports=arrayFilter;},{}],47:[function(require,module,exports){var baseTimes=require('./_baseTimes'),isArguments=require('./isArguments'),isArray=require('./isArray'),isBuffer=require('./isBuffer'),isIndex=require('./_isIndex'),isTypedArray=require('./isTypedArray');/** Used for built-in method references. */var objectProto=Object.prototype;/** Used to check objects for own properties. */var hasOwnProperty=objectProto.hasOwnProperty;/**
 * Creates an array of the enumerable property names of the array-like `value`.
 *
 * @private
 * @param {*} value The value to query.
 * @param {boolean} inherited Specify returning inherited property names.
 * @returns {Array} Returns the array of property names.
 */function arrayLikeKeys(value,inherited){var isArr=isArray(value),isArg=!isArr&&isArguments(value),isBuff=!isArr&&!isArg&&isBuffer(value),isType=!isArr&&!isArg&&!isBuff&&isTypedArray(value),skipIndexes=isArr||isArg||isBuff||isType,result=skipIndexes?baseTimes(value.length,String):[],length=result.length;for(var key in value){if((inherited||hasOwnProperty.call(value,key))&&!(skipIndexes&&(// Safari 9 has enumerable `arguments.length` in strict mode.
key=='length'||// Node.js 0.10 has enumerable non-index properties on buffers.
isBuff&&(key=='offset'||key=='parent')||// PhantomJS 2 has enumerable non-index properties on typed arrays.
isType&&(key=='buffer'||key=='byteLength'||key=='byteOffset')||// Skip index properties.
isIndex(key,length)))){result.push(key);}}return result;}module.exports=arrayLikeKeys;},{"./_baseTimes":72,"./_isIndex":108,"./isArguments":145,"./isArray":146,"./isBuffer":149,"./isTypedArray":159}],48:[function(require,module,exports){/**
 * A specialized version of `_.map` for arrays without support for iteratee
 * shorthands.
 *
 * @private
 * @param {Array} [array] The array to iterate over.
 * @param {Function} iteratee The function invoked per iteration.
 * @returns {Array} Returns the new mapped array.
 */function arrayMap(array,iteratee){var index=-1,length=array==null?0:array.length,result=Array(length);while(++index<length){result[index]=iteratee(array[index],index,array);}return result;}module.exports=arrayMap;},{}],49:[function(require,module,exports){/**
 * Appends the elements of `values` to `array`.
 *
 * @private
 * @param {Array} array The array to modify.
 * @param {Array} values The values to append.
 * @returns {Array} Returns `array`.
 */function arrayPush(array,values){var index=-1,length=values.length,offset=array.length;while(++index<length){array[offset+index]=values[index];}return array;}module.exports=arrayPush;},{}],50:[function(require,module,exports){var baseAssignValue=require('./_baseAssignValue'),eq=require('./eq');/**
 * This function is like `assignValue` except that it doesn't assign
 * `undefined` values.
 *
 * @private
 * @param {Object} object The object to modify.
 * @param {string} key The key of the property to assign.
 * @param {*} value The value to assign.
 */function assignMergeValue(object,key,value){if(value!==undefined&&!eq(object[key],value)||value===undefined&&!(key in object)){baseAssignValue(object,key,value);}}module.exports=assignMergeValue;},{"./_baseAssignValue":55,"./eq":142}],51:[function(require,module,exports){var baseAssignValue=require('./_baseAssignValue'),eq=require('./eq');/** Used for built-in method references. */var objectProto=Object.prototype;/** Used to check objects for own properties. */var hasOwnProperty=objectProto.hasOwnProperty;/**
 * Assigns `value` to `key` of `object` if the existing value is not equivalent
 * using [`SameValueZero`](http://ecma-international.org/ecma-262/7.0/#sec-samevaluezero)
 * for equality comparisons.
 *
 * @private
 * @param {Object} object The object to modify.
 * @param {string} key The key of the property to assign.
 * @param {*} value The value to assign.
 */function assignValue(object,key,value){var objValue=object[key];if(!(hasOwnProperty.call(object,key)&&eq(objValue,value))||value===undefined&&!(key in object)){baseAssignValue(object,key,value);}}module.exports=assignValue;},{"./_baseAssignValue":55,"./eq":142}],52:[function(require,module,exports){var eq=require('./eq');/**
 * Gets the index at which the `key` is found in `array` of key-value pairs.
 *
 * @private
 * @param {Array} array The array to inspect.
 * @param {*} key The key to search for.
 * @returns {number} Returns the index of the matched value, else `-1`.
 */function assocIndexOf(array,key){var length=array.length;while(length--){if(eq(array[length][0],key)){return length;}}return-1;}module.exports=assocIndexOf;},{"./eq":142}],53:[function(require,module,exports){var copyObject=require('./_copyObject'),keys=require('./keys');/**
 * The base implementation of `_.assign` without support for multiple sources
 * or `customizer` functions.
 *
 * @private
 * @param {Object} object The destination object.
 * @param {Object} source The source object.
 * @returns {Object} Returns `object`.
 */function baseAssign(object,source){return object&&copyObject(source,keys(source),object);}module.exports=baseAssign;},{"./_copyObject":82,"./keys":160}],54:[function(require,module,exports){var copyObject=require('./_copyObject'),keysIn=require('./keysIn');/**
 * The base implementation of `_.assignIn` without support for multiple sources
 * or `customizer` functions.
 *
 * @private
 * @param {Object} object The destination object.
 * @param {Object} source The source object.
 * @returns {Object} Returns `object`.
 */function baseAssignIn(object,source){return object&&copyObject(source,keysIn(source),object);}module.exports=baseAssignIn;},{"./_copyObject":82,"./keysIn":161}],55:[function(require,module,exports){var defineProperty=require('./_defineProperty');/**
 * The base implementation of `assignValue` and `assignMergeValue` without
 * value checks.
 *
 * @private
 * @param {Object} object The object to modify.
 * @param {string} key The key of the property to assign.
 * @param {*} value The value to assign.
 */function baseAssignValue(object,key,value){if(key=='__proto__'&&defineProperty){defineProperty(object,key,{'configurable':true,'enumerable':true,'value':value,'writable':true});}else{object[key]=value;}}module.exports=baseAssignValue;},{"./_defineProperty":88}],56:[function(require,module,exports){var Stack=require('./_Stack'),arrayEach=require('./_arrayEach'),assignValue=require('./_assignValue'),baseAssign=require('./_baseAssign'),baseAssignIn=require('./_baseAssignIn'),cloneBuffer=require('./_cloneBuffer'),copyArray=require('./_copyArray'),copySymbols=require('./_copySymbols'),copySymbolsIn=require('./_copySymbolsIn'),getAllKeys=require('./_getAllKeys'),getAllKeysIn=require('./_getAllKeysIn'),getTag=require('./_getTag'),initCloneArray=require('./_initCloneArray'),initCloneByTag=require('./_initCloneByTag'),initCloneObject=require('./_initCloneObject'),isArray=require('./isArray'),isBuffer=require('./isBuffer'),isMap=require('./isMap'),isObject=require('./isObject'),isSet=require('./isSet'),keys=require('./keys'),keysIn=require('./keysIn');/** Used to compose bitmasks for cloning. */var CLONE_DEEP_FLAG=1,CLONE_FLAT_FLAG=2,CLONE_SYMBOLS_FLAG=4;/** `Object#toString` result references. */var argsTag='[object Arguments]',arrayTag='[object Array]',boolTag='[object Boolean]',dateTag='[object Date]',errorTag='[object Error]',funcTag='[object Function]',genTag='[object GeneratorFunction]',mapTag='[object Map]',numberTag='[object Number]',objectTag='[object Object]',regexpTag='[object RegExp]',setTag='[object Set]',stringTag='[object String]',symbolTag='[object Symbol]',weakMapTag='[object WeakMap]';var arrayBufferTag='[object ArrayBuffer]',dataViewTag='[object DataView]',float32Tag='[object Float32Array]',float64Tag='[object Float64Array]',int8Tag='[object Int8Array]',int16Tag='[object Int16Array]',int32Tag='[object Int32Array]',uint8Tag='[object Uint8Array]',uint8ClampedTag='[object Uint8ClampedArray]',uint16Tag='[object Uint16Array]',uint32Tag='[object Uint32Array]';/** Used to identify `toStringTag` values supported by `_.clone`. */var cloneableTags={};cloneableTags[argsTag]=cloneableTags[arrayTag]=cloneableTags[arrayBufferTag]=cloneableTags[dataViewTag]=cloneableTags[boolTag]=cloneableTags[dateTag]=cloneableTags[float32Tag]=cloneableTags[float64Tag]=cloneableTags[int8Tag]=cloneableTags[int16Tag]=cloneableTags[int32Tag]=cloneableTags[mapTag]=cloneableTags[numberTag]=cloneableTags[objectTag]=cloneableTags[regexpTag]=cloneableTags[setTag]=cloneableTags[stringTag]=cloneableTags[symbolTag]=cloneableTags[uint8Tag]=cloneableTags[uint8ClampedTag]=cloneableTags[uint16Tag]=cloneableTags[uint32Tag]=true;cloneableTags[errorTag]=cloneableTags[funcTag]=cloneableTags[weakMapTag]=false;/**
 * The base implementation of `_.clone` and `_.cloneDeep` which tracks
 * traversed objects.
 *
 * @private
 * @param {*} value The value to clone.
 * @param {boolean} bitmask The bitmask flags.
 *  1 - Deep clone
 *  2 - Flatten inherited properties
 *  4 - Clone symbols
 * @param {Function} [customizer] The function to customize cloning.
 * @param {string} [key] The key of `value`.
 * @param {Object} [object] The parent object of `value`.
 * @param {Object} [stack] Tracks traversed objects and their clone counterparts.
 * @returns {*} Returns the cloned value.
 */function baseClone(value,bitmask,customizer,key,object,stack){var result,isDeep=bitmask&CLONE_DEEP_FLAG,isFlat=bitmask&CLONE_FLAT_FLAG,isFull=bitmask&CLONE_SYMBOLS_FLAG;if(customizer){result=object?customizer(value,key,object,stack):customizer(value);}if(result!==undefined){return result;}if(!isObject(value)){return value;}var isArr=isArray(value);if(isArr){result=initCloneArray(value);if(!isDeep){return copyArray(value,result);}}else{var tag=getTag(value),isFunc=tag==funcTag||tag==genTag;if(isBuffer(value)){return cloneBuffer(value,isDeep);}if(tag==objectTag||tag==argsTag||isFunc&&!object){result=isFlat||isFunc?{}:initCloneObject(value);if(!isDeep){return isFlat?copySymbolsIn(value,baseAssignIn(result,value)):copySymbols(value,baseAssign(result,value));}}else{if(!cloneableTags[tag]){return object?value:{};}result=initCloneByTag(value,tag,isDeep);}}// Check for circular references and return its corresponding clone.
stack||(stack=new Stack());var stacked=stack.get(value);if(stacked){return stacked;}stack.set(value,result);if(isSet(value)){value.forEach(function(subValue){result.add(baseClone(subValue,bitmask,customizer,subValue,value,stack));});}else if(isMap(value)){value.forEach(function(subValue,key){result.set(key,baseClone(subValue,bitmask,customizer,key,value,stack));});}var keysFunc=isFull?isFlat?getAllKeysIn:getAllKeys:isFlat?keysIn:keys;var props=isArr?undefined:keysFunc(value);arrayEach(props||value,function(subValue,key){if(props){key=subValue;subValue=value[key];}// Recursively populate clone (susceptible to call stack limits).
assignValue(result,key,baseClone(subValue,bitmask,customizer,key,value,stack));});return result;}module.exports=baseClone;},{"./_Stack":40,"./_arrayEach":45,"./_assignValue":51,"./_baseAssign":53,"./_baseAssignIn":54,"./_cloneBuffer":76,"./_copyArray":81,"./_copySymbols":83,"./_copySymbolsIn":84,"./_getAllKeys":90,"./_getAllKeysIn":91,"./_getTag":98,"./_initCloneArray":105,"./_initCloneByTag":106,"./_initCloneObject":107,"./isArray":146,"./isBuffer":149,"./isMap":152,"./isObject":153,"./isSet":156,"./keys":160,"./keysIn":161}],57:[function(require,module,exports){var isObject=require('./isObject');/** Built-in value references. */var objectCreate=Object.create;/**
 * The base implementation of `_.create` without support for assigning
 * properties to the created object.
 *
 * @private
 * @param {Object} proto The object to inherit from.
 * @returns {Object} Returns the new object.
 */var baseCreate=function(){function object(){}return function(proto){if(!isObject(proto)){return{};}if(objectCreate){return objectCreate(proto);}object.prototype=proto;var result=new object();object.prototype=undefined;return result;};}();module.exports=baseCreate;},{"./isObject":153}],58:[function(require,module,exports){var createBaseFor=require('./_createBaseFor');/**
 * The base implementation of `baseForOwn` which iterates over `object`
 * properties returned by `keysFunc` and invokes `iteratee` for each property.
 * Iteratee functions may exit iteration early by explicitly returning `false`.
 *
 * @private
 * @param {Object} object The object to iterate over.
 * @param {Function} iteratee The function invoked per iteration.
 * @param {Function} keysFunc The function to get the keys of `object`.
 * @returns {Object} Returns `object`.
 */var baseFor=createBaseFor();module.exports=baseFor;},{"./_createBaseFor":87}],59:[function(require,module,exports){var arrayPush=require('./_arrayPush'),isArray=require('./isArray');/**
 * The base implementation of `getAllKeys` and `getAllKeysIn` which uses
 * `keysFunc` and `symbolsFunc` to get the enumerable property names and
 * symbols of `object`.
 *
 * @private
 * @param {Object} object The object to query.
 * @param {Function} keysFunc The function to get the keys of `object`.
 * @param {Function} symbolsFunc The function to get the symbols of `object`.
 * @returns {Array} Returns the array of property names and symbols.
 */function baseGetAllKeys(object,keysFunc,symbolsFunc){var result=keysFunc(object);return isArray(object)?result:arrayPush(result,symbolsFunc(object));}module.exports=baseGetAllKeys;},{"./_arrayPush":49,"./isArray":146}],60:[function(require,module,exports){var _Symbol2=require('./_Symbol'),getRawTag=require('./_getRawTag'),objectToString=require('./_objectToString');/** `Object#toString` result references. */var nullTag='[object Null]',undefinedTag='[object Undefined]';/** Built-in value references. */var symToStringTag=_Symbol2?_Symbol2.toStringTag:undefined;/**
 * The base implementation of `getTag` without fallbacks for buggy environments.
 *
 * @private
 * @param {*} value The value to query.
 * @returns {string} Returns the `toStringTag`.
 */function baseGetTag(value){if(value==null){return value===undefined?undefinedTag:nullTag;}return symToStringTag&&symToStringTag in Object(value)?getRawTag(value):objectToString(value);}module.exports=baseGetTag;},{"./_Symbol":41,"./_getRawTag":95,"./_objectToString":127}],61:[function(require,module,exports){var baseGetTag=require('./_baseGetTag'),isObjectLike=require('./isObjectLike');/** `Object#toString` result references. */var argsTag='[object Arguments]';/**
 * The base implementation of `_.isArguments`.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is an `arguments` object,
 */function baseIsArguments(value){return isObjectLike(value)&&baseGetTag(value)==argsTag;}module.exports=baseIsArguments;},{"./_baseGetTag":60,"./isObjectLike":154}],62:[function(require,module,exports){var getTag=require('./_getTag'),isObjectLike=require('./isObjectLike');/** `Object#toString` result references. */var mapTag='[object Map]';/**
 * The base implementation of `_.isMap` without Node.js optimizations.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a map, else `false`.
 */function baseIsMap(value){return isObjectLike(value)&&getTag(value)==mapTag;}module.exports=baseIsMap;},{"./_getTag":98,"./isObjectLike":154}],63:[function(require,module,exports){var isFunction=require('./isFunction'),isMasked=require('./_isMasked'),isObject=require('./isObject'),toSource=require('./_toSource');/**
 * Used to match `RegExp`
 * [syntax characters](http://ecma-international.org/ecma-262/7.0/#sec-patterns).
 */var reRegExpChar=/[\\^$.*+?()[\]{}|]/g;/** Used to detect host constructors (Safari). */var reIsHostCtor=/^\[object .+?Constructor\]$/;/** Used for built-in method references. */var funcProto=Function.prototype,objectProto=Object.prototype;/** Used to resolve the decompiled source of functions. */var funcToString=funcProto.toString;/** Used to check objects for own properties. */var hasOwnProperty=objectProto.hasOwnProperty;/** Used to detect if a method is native. */var reIsNative=RegExp('^'+funcToString.call(hasOwnProperty).replace(reRegExpChar,'\\$&').replace(/hasOwnProperty|(function).*?(?=\\\()| for .+?(?=\\\])/g,'$1.*?')+'$');/**
 * The base implementation of `_.isNative` without bad shim checks.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a native function,
 *  else `false`.
 */function baseIsNative(value){if(!isObject(value)||isMasked(value)){return false;}var pattern=isFunction(value)?reIsNative:reIsHostCtor;return pattern.test(toSource(value));}module.exports=baseIsNative;},{"./_isMasked":111,"./_toSource":139,"./isFunction":150,"./isObject":153}],64:[function(require,module,exports){var getTag=require('./_getTag'),isObjectLike=require('./isObjectLike');/** `Object#toString` result references. */var setTag='[object Set]';/**
 * The base implementation of `_.isSet` without Node.js optimizations.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a set, else `false`.
 */function baseIsSet(value){return isObjectLike(value)&&getTag(value)==setTag;}module.exports=baseIsSet;},{"./_getTag":98,"./isObjectLike":154}],65:[function(require,module,exports){var baseGetTag=require('./_baseGetTag'),isLength=require('./isLength'),isObjectLike=require('./isObjectLike');/** `Object#toString` result references. */var argsTag='[object Arguments]',arrayTag='[object Array]',boolTag='[object Boolean]',dateTag='[object Date]',errorTag='[object Error]',funcTag='[object Function]',mapTag='[object Map]',numberTag='[object Number]',objectTag='[object Object]',regexpTag='[object RegExp]',setTag='[object Set]',stringTag='[object String]',weakMapTag='[object WeakMap]';var arrayBufferTag='[object ArrayBuffer]',dataViewTag='[object DataView]',float32Tag='[object Float32Array]',float64Tag='[object Float64Array]',int8Tag='[object Int8Array]',int16Tag='[object Int16Array]',int32Tag='[object Int32Array]',uint8Tag='[object Uint8Array]',uint8ClampedTag='[object Uint8ClampedArray]',uint16Tag='[object Uint16Array]',uint32Tag='[object Uint32Array]';/** Used to identify `toStringTag` values of typed arrays. */var typedArrayTags={};typedArrayTags[float32Tag]=typedArrayTags[float64Tag]=typedArrayTags[int8Tag]=typedArrayTags[int16Tag]=typedArrayTags[int32Tag]=typedArrayTags[uint8Tag]=typedArrayTags[uint8ClampedTag]=typedArrayTags[uint16Tag]=typedArrayTags[uint32Tag]=true;typedArrayTags[argsTag]=typedArrayTags[arrayTag]=typedArrayTags[arrayBufferTag]=typedArrayTags[boolTag]=typedArrayTags[dataViewTag]=typedArrayTags[dateTag]=typedArrayTags[errorTag]=typedArrayTags[funcTag]=typedArrayTags[mapTag]=typedArrayTags[numberTag]=typedArrayTags[objectTag]=typedArrayTags[regexpTag]=typedArrayTags[setTag]=typedArrayTags[stringTag]=typedArrayTags[weakMapTag]=false;/**
 * The base implementation of `_.isTypedArray` without Node.js optimizations.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a typed array, else `false`.
 */function baseIsTypedArray(value){return isObjectLike(value)&&isLength(value.length)&&!!typedArrayTags[baseGetTag(value)];}module.exports=baseIsTypedArray;},{"./_baseGetTag":60,"./isLength":151,"./isObjectLike":154}],66:[function(require,module,exports){var isPrototype=require('./_isPrototype'),nativeKeys=require('./_nativeKeys');/** Used for built-in method references. */var objectProto=Object.prototype;/** Used to check objects for own properties. */var hasOwnProperty=objectProto.hasOwnProperty;/**
 * The base implementation of `_.keys` which doesn't treat sparse arrays as dense.
 *
 * @private
 * @param {Object} object The object to query.
 * @returns {Array} Returns the array of property names.
 */function baseKeys(object){if(!isPrototype(object)){return nativeKeys(object);}var result=[];for(var key in Object(object)){if(hasOwnProperty.call(object,key)&&key!='constructor'){result.push(key);}}return result;}module.exports=baseKeys;},{"./_isPrototype":112,"./_nativeKeys":124}],67:[function(require,module,exports){var isObject=require('./isObject'),isPrototype=require('./_isPrototype'),nativeKeysIn=require('./_nativeKeysIn');/** Used for built-in method references. */var objectProto=Object.prototype;/** Used to check objects for own properties. */var hasOwnProperty=objectProto.hasOwnProperty;/**
 * The base implementation of `_.keysIn` which doesn't treat sparse arrays as dense.
 *
 * @private
 * @param {Object} object The object to query.
 * @returns {Array} Returns the array of property names.
 */function baseKeysIn(object){if(!isObject(object)){return nativeKeysIn(object);}var isProto=isPrototype(object),result=[];for(var key in object){if(!(key=='constructor'&&(isProto||!hasOwnProperty.call(object,key)))){result.push(key);}}return result;}module.exports=baseKeysIn;},{"./_isPrototype":112,"./_nativeKeysIn":125,"./isObject":153}],68:[function(require,module,exports){var Stack=require('./_Stack'),assignMergeValue=require('./_assignMergeValue'),baseFor=require('./_baseFor'),baseMergeDeep=require('./_baseMergeDeep'),isObject=require('./isObject'),keysIn=require('./keysIn'),safeGet=require('./_safeGet');/**
 * The base implementation of `_.merge` without support for multiple sources.
 *
 * @private
 * @param {Object} object The destination object.
 * @param {Object} source The source object.
 * @param {number} srcIndex The index of `source`.
 * @param {Function} [customizer] The function to customize merged values.
 * @param {Object} [stack] Tracks traversed source values and their merged
 *  counterparts.
 */function baseMerge(object,source,srcIndex,customizer,stack){if(object===source){return;}baseFor(source,function(srcValue,key){stack||(stack=new Stack());if(isObject(srcValue)){baseMergeDeep(object,source,key,srcIndex,baseMerge,customizer,stack);}else{var newValue=customizer?customizer(safeGet(object,key),srcValue,key+'',object,source,stack):undefined;if(newValue===undefined){newValue=srcValue;}assignMergeValue(object,key,newValue);}},keysIn);}module.exports=baseMerge;},{"./_Stack":40,"./_assignMergeValue":50,"./_baseFor":58,"./_baseMergeDeep":69,"./_safeGet":131,"./isObject":153,"./keysIn":161}],69:[function(require,module,exports){var assignMergeValue=require('./_assignMergeValue'),cloneBuffer=require('./_cloneBuffer'),cloneTypedArray=require('./_cloneTypedArray'),copyArray=require('./_copyArray'),initCloneObject=require('./_initCloneObject'),isArguments=require('./isArguments'),isArray=require('./isArray'),isArrayLikeObject=require('./isArrayLikeObject'),isBuffer=require('./isBuffer'),isFunction=require('./isFunction'),isObject=require('./isObject'),isPlainObject=require('./isPlainObject'),isTypedArray=require('./isTypedArray'),safeGet=require('./_safeGet'),toPlainObject=require('./toPlainObject');/**
 * A specialized version of `baseMerge` for arrays and objects which performs
 * deep merges and tracks traversed objects enabling objects with circular
 * references to be merged.
 *
 * @private
 * @param {Object} object The destination object.
 * @param {Object} source The source object.
 * @param {string} key The key of the value to merge.
 * @param {number} srcIndex The index of `source`.
 * @param {Function} mergeFunc The function to merge values.
 * @param {Function} [customizer] The function to customize assigned values.
 * @param {Object} [stack] Tracks traversed source values and their merged
 *  counterparts.
 */function baseMergeDeep(object,source,key,srcIndex,mergeFunc,customizer,stack){var objValue=safeGet(object,key),srcValue=safeGet(source,key),stacked=stack.get(srcValue);if(stacked){assignMergeValue(object,key,stacked);return;}var newValue=customizer?customizer(objValue,srcValue,key+'',object,source,stack):undefined;var isCommon=newValue===undefined;if(isCommon){var isArr=isArray(srcValue),isBuff=!isArr&&isBuffer(srcValue),isTyped=!isArr&&!isBuff&&isTypedArray(srcValue);newValue=srcValue;if(isArr||isBuff||isTyped){if(isArray(objValue)){newValue=objValue;}else if(isArrayLikeObject(objValue)){newValue=copyArray(objValue);}else if(isBuff){isCommon=false;newValue=cloneBuffer(srcValue,true);}else if(isTyped){isCommon=false;newValue=cloneTypedArray(srcValue,true);}else{newValue=[];}}else if(isPlainObject(srcValue)||isArguments(srcValue)){newValue=objValue;if(isArguments(objValue)){newValue=toPlainObject(objValue);}else if(!isObject(objValue)||isFunction(objValue)){newValue=initCloneObject(srcValue);}}else{isCommon=false;}}if(isCommon){// Recursively merge objects and arrays (susceptible to call stack limits).
stack.set(srcValue,newValue);mergeFunc(newValue,srcValue,srcIndex,customizer,stack);stack['delete'](srcValue);}assignMergeValue(object,key,newValue);}module.exports=baseMergeDeep;},{"./_assignMergeValue":50,"./_cloneBuffer":76,"./_cloneTypedArray":80,"./_copyArray":81,"./_initCloneObject":107,"./_safeGet":131,"./isArguments":145,"./isArray":146,"./isArrayLikeObject":148,"./isBuffer":149,"./isFunction":150,"./isObject":153,"./isPlainObject":155,"./isTypedArray":159,"./toPlainObject":165}],70:[function(require,module,exports){var identity=require('./identity'),overRest=require('./_overRest'),setToString=require('./_setToString');/**
 * The base implementation of `_.rest` which doesn't validate or coerce arguments.
 *
 * @private
 * @param {Function} func The function to apply a rest parameter to.
 * @param {number} [start=func.length-1] The start position of the rest parameter.
 * @returns {Function} Returns the new function.
 */function baseRest(func,start){return setToString(overRest(func,start,identity),func+'');}module.exports=baseRest;},{"./_overRest":129,"./_setToString":132,"./identity":144}],71:[function(require,module,exports){var constant=require('./constant'),defineProperty=require('./_defineProperty'),identity=require('./identity');/**
 * The base implementation of `setToString` without support for hot loop shorting.
 *
 * @private
 * @param {Function} func The function to modify.
 * @param {Function} string The `toString` result.
 * @returns {Function} Returns `func`.
 */var baseSetToString=!defineProperty?identity:function(func,string){return defineProperty(func,'toString',{'configurable':true,'enumerable':false,'value':constant(string),'writable':true});};module.exports=baseSetToString;},{"./_defineProperty":88,"./constant":141,"./identity":144}],72:[function(require,module,exports){/**
 * The base implementation of `_.times` without support for iteratee shorthands
 * or max array length checks.
 *
 * @private
 * @param {number} n The number of times to invoke `iteratee`.
 * @param {Function} iteratee The function invoked per iteration.
 * @returns {Array} Returns the array of results.
 */function baseTimes(n,iteratee){var index=-1,result=Array(n);while(++index<n){result[index]=iteratee(index);}return result;}module.exports=baseTimes;},{}],73:[function(require,module,exports){var _Symbol3=require('./_Symbol'),arrayMap=require('./_arrayMap'),isArray=require('./isArray'),isSymbol=require('./isSymbol');/** Used as references for various `Number` constants. */var INFINITY=1/0;/** Used to convert symbols to primitives and strings. */var symbolProto=_Symbol3?_Symbol3.prototype:undefined,symbolToString=symbolProto?symbolProto.toString:undefined;/**
 * The base implementation of `_.toString` which doesn't convert nullish
 * values to empty strings.
 *
 * @private
 * @param {*} value The value to process.
 * @returns {string} Returns the string.
 */function baseToString(value){// Exit early for strings to avoid a performance hit in some environments.
if(typeof value=='string'){return value;}if(isArray(value)){// Recursively convert values (susceptible to call stack limits).
return arrayMap(value,baseToString)+'';}if(isSymbol(value)){return symbolToString?symbolToString.call(value):'';}var result=value+'';return result=='0'&&1/value==-INFINITY?'-0':result;}module.exports=baseToString;},{"./_Symbol":41,"./_arrayMap":48,"./isArray":146,"./isSymbol":158}],74:[function(require,module,exports){/**
 * The base implementation of `_.unary` without support for storing metadata.
 *
 * @private
 * @param {Function} func The function to cap arguments for.
 * @returns {Function} Returns the new capped function.
 */function baseUnary(func){return function(value){return func(value);};}module.exports=baseUnary;},{}],75:[function(require,module,exports){var Uint8Array=require('./_Uint8Array');/**
 * Creates a clone of `arrayBuffer`.
 *
 * @private
 * @param {ArrayBuffer} arrayBuffer The array buffer to clone.
 * @returns {ArrayBuffer} Returns the cloned array buffer.
 */function cloneArrayBuffer(arrayBuffer){var result=new arrayBuffer.constructor(arrayBuffer.byteLength);new Uint8Array(result).set(new Uint8Array(arrayBuffer));return result;}module.exports=cloneArrayBuffer;},{"./_Uint8Array":42}],76:[function(require,module,exports){var root=require('./_root');/** Detect free variable `exports`. */var freeExports=_typeof(exports)=='object'&&exports&&!exports.nodeType&&exports;/** Detect free variable `module`. */var freeModule=freeExports&&_typeof(module)=='object'&&module&&!module.nodeType&&module;/** Detect the popular CommonJS extension `module.exports`. */var moduleExports=freeModule&&freeModule.exports===freeExports;/** Built-in value references. */var Buffer=moduleExports?root.Buffer:undefined,allocUnsafe=Buffer?Buffer.allocUnsafe:undefined;/**
 * Creates a clone of  `buffer`.
 *
 * @private
 * @param {Buffer} buffer The buffer to clone.
 * @param {boolean} [isDeep] Specify a deep clone.
 * @returns {Buffer} Returns the cloned buffer.
 */function cloneBuffer(buffer,isDeep){if(isDeep){return buffer.slice();}var length=buffer.length,result=allocUnsafe?allocUnsafe(length):new buffer.constructor(length);buffer.copy(result);return result;}module.exports=cloneBuffer;},{"./_root":130}],77:[function(require,module,exports){var cloneArrayBuffer=require('./_cloneArrayBuffer');/**
 * Creates a clone of `dataView`.
 *
 * @private
 * @param {Object} dataView The data view to clone.
 * @param {boolean} [isDeep] Specify a deep clone.
 * @returns {Object} Returns the cloned data view.
 */function cloneDataView(dataView,isDeep){var buffer=isDeep?cloneArrayBuffer(dataView.buffer):dataView.buffer;return new dataView.constructor(buffer,dataView.byteOffset,dataView.byteLength);}module.exports=cloneDataView;},{"./_cloneArrayBuffer":75}],78:[function(require,module,exports){/** Used to match `RegExp` flags from their coerced string values. */var reFlags=/\w*$/;/**
 * Creates a clone of `regexp`.
 *
 * @private
 * @param {Object} regexp The regexp to clone.
 * @returns {Object} Returns the cloned regexp.
 */function cloneRegExp(regexp){var result=new regexp.constructor(regexp.source,reFlags.exec(regexp));result.lastIndex=regexp.lastIndex;return result;}module.exports=cloneRegExp;},{}],79:[function(require,module,exports){var _Symbol4=require('./_Symbol');/** Used to convert symbols to primitives and strings. */var symbolProto=_Symbol4?_Symbol4.prototype:undefined,symbolValueOf=symbolProto?symbolProto.valueOf:undefined;/**
 * Creates a clone of the `symbol` object.
 *
 * @private
 * @param {Object} symbol The symbol object to clone.
 * @returns {Object} Returns the cloned symbol object.
 */function cloneSymbol(symbol){return symbolValueOf?Object(symbolValueOf.call(symbol)):{};}module.exports=cloneSymbol;},{"./_Symbol":41}],80:[function(require,module,exports){var cloneArrayBuffer=require('./_cloneArrayBuffer');/**
 * Creates a clone of `typedArray`.
 *
 * @private
 * @param {Object} typedArray The typed array to clone.
 * @param {boolean} [isDeep] Specify a deep clone.
 * @returns {Object} Returns the cloned typed array.
 */function cloneTypedArray(typedArray,isDeep){var buffer=isDeep?cloneArrayBuffer(typedArray.buffer):typedArray.buffer;return new typedArray.constructor(buffer,typedArray.byteOffset,typedArray.length);}module.exports=cloneTypedArray;},{"./_cloneArrayBuffer":75}],81:[function(require,module,exports){/**
 * Copies the values of `source` to `array`.
 *
 * @private
 * @param {Array} source The array to copy values from.
 * @param {Array} [array=[]] The array to copy values to.
 * @returns {Array} Returns `array`.
 */function copyArray(source,array){var index=-1,length=source.length;array||(array=Array(length));while(++index<length){array[index]=source[index];}return array;}module.exports=copyArray;},{}],82:[function(require,module,exports){var assignValue=require('./_assignValue'),baseAssignValue=require('./_baseAssignValue');/**
 * Copies properties of `source` to `object`.
 *
 * @private
 * @param {Object} source The object to copy properties from.
 * @param {Array} props The property identifiers to copy.
 * @param {Object} [object={}] The object to copy properties to.
 * @param {Function} [customizer] The function to customize copied values.
 * @returns {Object} Returns `object`.
 */function copyObject(source,props,object,customizer){var isNew=!object;object||(object={});var index=-1,length=props.length;while(++index<length){var key=props[index];var newValue=customizer?customizer(object[key],source[key],key,object,source):undefined;if(newValue===undefined){newValue=source[key];}if(isNew){baseAssignValue(object,key,newValue);}else{assignValue(object,key,newValue);}}return object;}module.exports=copyObject;},{"./_assignValue":51,"./_baseAssignValue":55}],83:[function(require,module,exports){var copyObject=require('./_copyObject'),getSymbols=require('./_getSymbols');/**
 * Copies own symbols of `source` to `object`.
 *
 * @private
 * @param {Object} source The object to copy symbols from.
 * @param {Object} [object={}] The object to copy symbols to.
 * @returns {Object} Returns `object`.
 */function copySymbols(source,object){return copyObject(source,getSymbols(source),object);}module.exports=copySymbols;},{"./_copyObject":82,"./_getSymbols":96}],84:[function(require,module,exports){var copyObject=require('./_copyObject'),getSymbolsIn=require('./_getSymbolsIn');/**
 * Copies own and inherited symbols of `source` to `object`.
 *
 * @private
 * @param {Object} source The object to copy symbols from.
 * @param {Object} [object={}] The object to copy symbols to.
 * @returns {Object} Returns `object`.
 */function copySymbolsIn(source,object){return copyObject(source,getSymbolsIn(source),object);}module.exports=copySymbolsIn;},{"./_copyObject":82,"./_getSymbolsIn":97}],85:[function(require,module,exports){var root=require('./_root');/** Used to detect overreaching core-js shims. */var coreJsData=root['__core-js_shared__'];module.exports=coreJsData;},{"./_root":130}],86:[function(require,module,exports){var baseRest=require('./_baseRest'),isIterateeCall=require('./_isIterateeCall');/**
 * Creates a function like `_.assign`.
 *
 * @private
 * @param {Function} assigner The function to assign values.
 * @returns {Function} Returns the new assigner function.
 */function createAssigner(assigner){return baseRest(function(object,sources){var index=-1,length=sources.length,customizer=length>1?sources[length-1]:undefined,guard=length>2?sources[2]:undefined;customizer=assigner.length>3&&typeof customizer=='function'?(length--,customizer):undefined;if(guard&&isIterateeCall(sources[0],sources[1],guard)){customizer=length<3?undefined:customizer;length=1;}object=Object(object);while(++index<length){var source=sources[index];if(source){assigner(object,source,index,customizer);}}return object;});}module.exports=createAssigner;},{"./_baseRest":70,"./_isIterateeCall":109}],87:[function(require,module,exports){/**
 * Creates a base function for methods like `_.forIn` and `_.forOwn`.
 *
 * @private
 * @param {boolean} [fromRight] Specify iterating from right to left.
 * @returns {Function} Returns the new base function.
 */function createBaseFor(fromRight){return function(object,iteratee,keysFunc){var index=-1,iterable=Object(object),props=keysFunc(object),length=props.length;while(length--){var key=props[fromRight?length:++index];if(iteratee(iterable[key],key,iterable)===false){break;}}return object;};}module.exports=createBaseFor;},{}],88:[function(require,module,exports){var getNative=require('./_getNative');var defineProperty=function(){try{var func=getNative(Object,'defineProperty');func({},'',{});return func;}catch(e){}}();module.exports=defineProperty;},{"./_getNative":93}],89:[function(require,module,exports){(function(global){/** Detect free variable `global` from Node.js. */var freeGlobal=_typeof(global)=='object'&&global&&global.Object===Object&&global;module.exports=freeGlobal;}).call(this,typeof global!=="undefined"?global:typeof self!=="undefined"?self:typeof window!=="undefined"?window:{});},{}],90:[function(require,module,exports){var baseGetAllKeys=require('./_baseGetAllKeys'),getSymbols=require('./_getSymbols'),keys=require('./keys');/**
 * Creates an array of own enumerable property names and symbols of `object`.
 *
 * @private
 * @param {Object} object The object to query.
 * @returns {Array} Returns the array of property names and symbols.
 */function getAllKeys(object){return baseGetAllKeys(object,keys,getSymbols);}module.exports=getAllKeys;},{"./_baseGetAllKeys":59,"./_getSymbols":96,"./keys":160}],91:[function(require,module,exports){var baseGetAllKeys=require('./_baseGetAllKeys'),getSymbolsIn=require('./_getSymbolsIn'),keysIn=require('./keysIn');/**
 * Creates an array of own and inherited enumerable property names and
 * symbols of `object`.
 *
 * @private
 * @param {Object} object The object to query.
 * @returns {Array} Returns the array of property names and symbols.
 */function getAllKeysIn(object){return baseGetAllKeys(object,keysIn,getSymbolsIn);}module.exports=getAllKeysIn;},{"./_baseGetAllKeys":59,"./_getSymbolsIn":97,"./keysIn":161}],92:[function(require,module,exports){var isKeyable=require('./_isKeyable');/**
 * Gets the data for `map`.
 *
 * @private
 * @param {Object} map The map to query.
 * @param {string} key The reference key.
 * @returns {*} Returns the map data.
 */function getMapData(map,key){var data=map.__data__;return isKeyable(key)?data[typeof key=='string'?'string':'hash']:data.map;}module.exports=getMapData;},{"./_isKeyable":110}],93:[function(require,module,exports){var baseIsNative=require('./_baseIsNative'),getValue=require('./_getValue');/**
 * Gets the native function at `key` of `object`.
 *
 * @private
 * @param {Object} object The object to query.
 * @param {string} key The key of the method to get.
 * @returns {*} Returns the function if it's native, else `undefined`.
 */function getNative(object,key){var value=getValue(object,key);return baseIsNative(value)?value:undefined;}module.exports=getNative;},{"./_baseIsNative":63,"./_getValue":99}],94:[function(require,module,exports){var overArg=require('./_overArg');/** Built-in value references. */var getPrototype=overArg(Object.getPrototypeOf,Object);module.exports=getPrototype;},{"./_overArg":128}],95:[function(require,module,exports){var _Symbol5=require('./_Symbol');/** Used for built-in method references. */var objectProto=Object.prototype;/** Used to check objects for own properties. */var hasOwnProperty=objectProto.hasOwnProperty;/**
 * Used to resolve the
 * [`toStringTag`](http://ecma-international.org/ecma-262/7.0/#sec-object.prototype.tostring)
 * of values.
 */var nativeObjectToString=objectProto.toString;/** Built-in value references. */var symToStringTag=_Symbol5?_Symbol5.toStringTag:undefined;/**
 * A specialized version of `baseGetTag` which ignores `Symbol.toStringTag` values.
 *
 * @private
 * @param {*} value The value to query.
 * @returns {string} Returns the raw `toStringTag`.
 */function getRawTag(value){var isOwn=hasOwnProperty.call(value,symToStringTag),tag=value[symToStringTag];try{value[symToStringTag]=undefined;var unmasked=true;}catch(e){}var result=nativeObjectToString.call(value);if(unmasked){if(isOwn){value[symToStringTag]=tag;}else{delete value[symToStringTag];}}return result;}module.exports=getRawTag;},{"./_Symbol":41}],96:[function(require,module,exports){var arrayFilter=require('./_arrayFilter'),stubArray=require('./stubArray');/** Used for built-in method references. */var objectProto=Object.prototype;/** Built-in value references. */var propertyIsEnumerable=objectProto.propertyIsEnumerable;/* Built-in method references for those with the same name as other `lodash` methods. */var nativeGetSymbols=Object.getOwnPropertySymbols;/**
 * Creates an array of the own enumerable symbols of `object`.
 *
 * @private
 * @param {Object} object The object to query.
 * @returns {Array} Returns the array of symbols.
 */var getSymbols=!nativeGetSymbols?stubArray:function(object){if(object==null){return[];}object=Object(object);return arrayFilter(nativeGetSymbols(object),function(symbol){return propertyIsEnumerable.call(object,symbol);});};module.exports=getSymbols;},{"./_arrayFilter":46,"./stubArray":163}],97:[function(require,module,exports){var arrayPush=require('./_arrayPush'),getPrototype=require('./_getPrototype'),getSymbols=require('./_getSymbols'),stubArray=require('./stubArray');/* Built-in method references for those with the same name as other `lodash` methods. */var nativeGetSymbols=Object.getOwnPropertySymbols;/**
 * Creates an array of the own and inherited enumerable symbols of `object`.
 *
 * @private
 * @param {Object} object The object to query.
 * @returns {Array} Returns the array of symbols.
 */var getSymbolsIn=!nativeGetSymbols?stubArray:function(object){var result=[];while(object){arrayPush(result,getSymbols(object));object=getPrototype(object);}return result;};module.exports=getSymbolsIn;},{"./_arrayPush":49,"./_getPrototype":94,"./_getSymbols":96,"./stubArray":163}],98:[function(require,module,exports){var DataView=require('./_DataView'),Map=require('./_Map'),Promise=require('./_Promise'),Set=require('./_Set'),WeakMap=require('./_WeakMap'),baseGetTag=require('./_baseGetTag'),toSource=require('./_toSource');/** `Object#toString` result references. */var mapTag='[object Map]',objectTag='[object Object]',promiseTag='[object Promise]',setTag='[object Set]',weakMapTag='[object WeakMap]';var dataViewTag='[object DataView]';/** Used to detect maps, sets, and weakmaps. */var dataViewCtorString=toSource(DataView),mapCtorString=toSource(Map),promiseCtorString=toSource(Promise),setCtorString=toSource(Set),weakMapCtorString=toSource(WeakMap);/**
 * Gets the `toStringTag` of `value`.
 *
 * @private
 * @param {*} value The value to query.
 * @returns {string} Returns the `toStringTag`.
 */var getTag=baseGetTag;// Fallback for data views, maps, sets, and weak maps in IE 11 and promises in Node.js < 6.
if(DataView&&getTag(new DataView(new ArrayBuffer(1)))!=dataViewTag||Map&&getTag(new Map())!=mapTag||Promise&&getTag(Promise.resolve())!=promiseTag||Set&&getTag(new Set())!=setTag||WeakMap&&getTag(new WeakMap())!=weakMapTag){getTag=function getTag(value){var result=baseGetTag(value),Ctor=result==objectTag?value.constructor:undefined,ctorString=Ctor?toSource(Ctor):'';if(ctorString){switch(ctorString){case dataViewCtorString:return dataViewTag;case mapCtorString:return mapTag;case promiseCtorString:return promiseTag;case setCtorString:return setTag;case weakMapCtorString:return weakMapTag;}}return result;};}module.exports=getTag;},{"./_DataView":33,"./_Map":36,"./_Promise":38,"./_Set":39,"./_WeakMap":43,"./_baseGetTag":60,"./_toSource":139}],99:[function(require,module,exports){/**
 * Gets the value at `key` of `object`.
 *
 * @private
 * @param {Object} [object] The object to query.
 * @param {string} key The key of the property to get.
 * @returns {*} Returns the property value.
 */function getValue(object,key){return object==null?undefined:object[key];}module.exports=getValue;},{}],100:[function(require,module,exports){var nativeCreate=require('./_nativeCreate');/**
 * Removes all key-value entries from the hash.
 *
 * @private
 * @name clear
 * @memberOf Hash
 */function hashClear(){this.__data__=nativeCreate?nativeCreate(null):{};this.size=0;}module.exports=hashClear;},{"./_nativeCreate":123}],101:[function(require,module,exports){/**
 * Removes `key` and its value from the hash.
 *
 * @private
 * @name delete
 * @memberOf Hash
 * @param {Object} hash The hash to modify.
 * @param {string} key The key of the value to remove.
 * @returns {boolean} Returns `true` if the entry was removed, else `false`.
 */function hashDelete(key){var result=this.has(key)&&delete this.__data__[key];this.size-=result?1:0;return result;}module.exports=hashDelete;},{}],102:[function(require,module,exports){var nativeCreate=require('./_nativeCreate');/** Used to stand-in for `undefined` hash values. */var HASH_UNDEFINED='__lodash_hash_undefined__';/** Used for built-in method references. */var objectProto=Object.prototype;/** Used to check objects for own properties. */var hasOwnProperty=objectProto.hasOwnProperty;/**
 * Gets the hash value for `key`.
 *
 * @private
 * @name get
 * @memberOf Hash
 * @param {string} key The key of the value to get.
 * @returns {*} Returns the entry value.
 */function hashGet(key){var data=this.__data__;if(nativeCreate){var result=data[key];return result===HASH_UNDEFINED?undefined:result;}return hasOwnProperty.call(data,key)?data[key]:undefined;}module.exports=hashGet;},{"./_nativeCreate":123}],103:[function(require,module,exports){var nativeCreate=require('./_nativeCreate');/** Used for built-in method references. */var objectProto=Object.prototype;/** Used to check objects for own properties. */var hasOwnProperty=objectProto.hasOwnProperty;/**
 * Checks if a hash value for `key` exists.
 *
 * @private
 * @name has
 * @memberOf Hash
 * @param {string} key The key of the entry to check.
 * @returns {boolean} Returns `true` if an entry for `key` exists, else `false`.
 */function hashHas(key){var data=this.__data__;return nativeCreate?data[key]!==undefined:hasOwnProperty.call(data,key);}module.exports=hashHas;},{"./_nativeCreate":123}],104:[function(require,module,exports){var nativeCreate=require('./_nativeCreate');/** Used to stand-in for `undefined` hash values. */var HASH_UNDEFINED='__lodash_hash_undefined__';/**
 * Sets the hash `key` to `value`.
 *
 * @private
 * @name set
 * @memberOf Hash
 * @param {string} key The key of the value to set.
 * @param {*} value The value to set.
 * @returns {Object} Returns the hash instance.
 */function hashSet(key,value){var data=this.__data__;this.size+=this.has(key)?0:1;data[key]=nativeCreate&&value===undefined?HASH_UNDEFINED:value;return this;}module.exports=hashSet;},{"./_nativeCreate":123}],105:[function(require,module,exports){/** Used for built-in method references. */var objectProto=Object.prototype;/** Used to check objects for own properties. */var hasOwnProperty=objectProto.hasOwnProperty;/**
 * Initializes an array clone.
 *
 * @private
 * @param {Array} array The array to clone.
 * @returns {Array} Returns the initialized clone.
 */function initCloneArray(array){var length=array.length,result=new array.constructor(length);// Add properties assigned by `RegExp#exec`.
if(length&&typeof array[0]=='string'&&hasOwnProperty.call(array,'index')){result.index=array.index;result.input=array.input;}return result;}module.exports=initCloneArray;},{}],106:[function(require,module,exports){var cloneArrayBuffer=require('./_cloneArrayBuffer'),cloneDataView=require('./_cloneDataView'),cloneRegExp=require('./_cloneRegExp'),cloneSymbol=require('./_cloneSymbol'),cloneTypedArray=require('./_cloneTypedArray');/** `Object#toString` result references. */var boolTag='[object Boolean]',dateTag='[object Date]',mapTag='[object Map]',numberTag='[object Number]',regexpTag='[object RegExp]',setTag='[object Set]',stringTag='[object String]',symbolTag='[object Symbol]';var arrayBufferTag='[object ArrayBuffer]',dataViewTag='[object DataView]',float32Tag='[object Float32Array]',float64Tag='[object Float64Array]',int8Tag='[object Int8Array]',int16Tag='[object Int16Array]',int32Tag='[object Int32Array]',uint8Tag='[object Uint8Array]',uint8ClampedTag='[object Uint8ClampedArray]',uint16Tag='[object Uint16Array]',uint32Tag='[object Uint32Array]';/**
 * Initializes an object clone based on its `toStringTag`.
 *
 * **Note:** This function only supports cloning values with tags of
 * `Boolean`, `Date`, `Error`, `Map`, `Number`, `RegExp`, `Set`, or `String`.
 *
 * @private
 * @param {Object} object The object to clone.
 * @param {string} tag The `toStringTag` of the object to clone.
 * @param {boolean} [isDeep] Specify a deep clone.
 * @returns {Object} Returns the initialized clone.
 */function initCloneByTag(object,tag,isDeep){var Ctor=object.constructor;switch(tag){case arrayBufferTag:return cloneArrayBuffer(object);case boolTag:case dateTag:return new Ctor(+object);case dataViewTag:return cloneDataView(object,isDeep);case float32Tag:case float64Tag:case int8Tag:case int16Tag:case int32Tag:case uint8Tag:case uint8ClampedTag:case uint16Tag:case uint32Tag:return cloneTypedArray(object,isDeep);case mapTag:return new Ctor();case numberTag:case stringTag:return new Ctor(object);case regexpTag:return cloneRegExp(object);case setTag:return new Ctor();case symbolTag:return cloneSymbol(object);}}module.exports=initCloneByTag;},{"./_cloneArrayBuffer":75,"./_cloneDataView":77,"./_cloneRegExp":78,"./_cloneSymbol":79,"./_cloneTypedArray":80}],107:[function(require,module,exports){var baseCreate=require('./_baseCreate'),getPrototype=require('./_getPrototype'),isPrototype=require('./_isPrototype');/**
 * Initializes an object clone.
 *
 * @private
 * @param {Object} object The object to clone.
 * @returns {Object} Returns the initialized clone.
 */function initCloneObject(object){return typeof object.constructor=='function'&&!isPrototype(object)?baseCreate(getPrototype(object)):{};}module.exports=initCloneObject;},{"./_baseCreate":57,"./_getPrototype":94,"./_isPrototype":112}],108:[function(require,module,exports){/** Used as references for various `Number` constants. */var MAX_SAFE_INTEGER=9007199254740991;/** Used to detect unsigned integer values. */var reIsUint=/^(?:0|[1-9]\d*)$/;/**
 * Checks if `value` is a valid array-like index.
 *
 * @private
 * @param {*} value The value to check.
 * @param {number} [length=MAX_SAFE_INTEGER] The upper bounds of a valid index.
 * @returns {boolean} Returns `true` if `value` is a valid index, else `false`.
 */function isIndex(value,length){var type=_typeof(value);length=length==null?MAX_SAFE_INTEGER:length;return!!length&&(type=='number'||type!='symbol'&&reIsUint.test(value))&&value>-1&&value%1==0&&value<length;}module.exports=isIndex;},{}],109:[function(require,module,exports){var eq=require('./eq'),isArrayLike=require('./isArrayLike'),isIndex=require('./_isIndex'),isObject=require('./isObject');/**
 * Checks if the given arguments are from an iteratee call.
 *
 * @private
 * @param {*} value The potential iteratee value argument.
 * @param {*} index The potential iteratee index or key argument.
 * @param {*} object The potential iteratee object argument.
 * @returns {boolean} Returns `true` if the arguments are from an iteratee call,
 *  else `false`.
 */function isIterateeCall(value,index,object){if(!isObject(object)){return false;}var type=_typeof(index);if(type=='number'?isArrayLike(object)&&isIndex(index,object.length):type=='string'&&index in object){return eq(object[index],value);}return false;}module.exports=isIterateeCall;},{"./_isIndex":108,"./eq":142,"./isArrayLike":147,"./isObject":153}],110:[function(require,module,exports){/**
 * Checks if `value` is suitable for use as unique object key.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is suitable, else `false`.
 */function isKeyable(value){var type=_typeof(value);return type=='string'||type=='number'||type=='symbol'||type=='boolean'?value!=='__proto__':value===null;}module.exports=isKeyable;},{}],111:[function(require,module,exports){var coreJsData=require('./_coreJsData');/** Used to detect methods masquerading as native. */var maskSrcKey=function(){var uid=/[^.]+$/.exec(coreJsData&&coreJsData.keys&&coreJsData.keys.IE_PROTO||'');return uid?'Symbol(src)_1.'+uid:'';}();/**
 * Checks if `func` has its source masked.
 *
 * @private
 * @param {Function} func The function to check.
 * @returns {boolean} Returns `true` if `func` is masked, else `false`.
 */function isMasked(func){return!!maskSrcKey&&maskSrcKey in func;}module.exports=isMasked;},{"./_coreJsData":85}],112:[function(require,module,exports){/** Used for built-in method references. */var objectProto=Object.prototype;/**
 * Checks if `value` is likely a prototype object.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a prototype, else `false`.
 */function isPrototype(value){var Ctor=value&&value.constructor,proto=typeof Ctor=='function'&&Ctor.prototype||objectProto;return value===proto;}module.exports=isPrototype;},{}],113:[function(require,module,exports){/**
 * Removes all key-value entries from the list cache.
 *
 * @private
 * @name clear
 * @memberOf ListCache
 */function listCacheClear(){this.__data__=[];this.size=0;}module.exports=listCacheClear;},{}],114:[function(require,module,exports){var assocIndexOf=require('./_assocIndexOf');/** Used for built-in method references. */var arrayProto=Array.prototype;/** Built-in value references. */var splice=arrayProto.splice;/**
 * Removes `key` and its value from the list cache.
 *
 * @private
 * @name delete
 * @memberOf ListCache
 * @param {string} key The key of the value to remove.
 * @returns {boolean} Returns `true` if the entry was removed, else `false`.
 */function listCacheDelete(key){var data=this.__data__,index=assocIndexOf(data,key);if(index<0){return false;}var lastIndex=data.length-1;if(index==lastIndex){data.pop();}else{splice.call(data,index,1);}--this.size;return true;}module.exports=listCacheDelete;},{"./_assocIndexOf":52}],115:[function(require,module,exports){var assocIndexOf=require('./_assocIndexOf');/**
 * Gets the list cache value for `key`.
 *
 * @private
 * @name get
 * @memberOf ListCache
 * @param {string} key The key of the value to get.
 * @returns {*} Returns the entry value.
 */function listCacheGet(key){var data=this.__data__,index=assocIndexOf(data,key);return index<0?undefined:data[index][1];}module.exports=listCacheGet;},{"./_assocIndexOf":52}],116:[function(require,module,exports){var assocIndexOf=require('./_assocIndexOf');/**
 * Checks if a list cache value for `key` exists.
 *
 * @private
 * @name has
 * @memberOf ListCache
 * @param {string} key The key of the entry to check.
 * @returns {boolean} Returns `true` if an entry for `key` exists, else `false`.
 */function listCacheHas(key){return assocIndexOf(this.__data__,key)>-1;}module.exports=listCacheHas;},{"./_assocIndexOf":52}],117:[function(require,module,exports){var assocIndexOf=require('./_assocIndexOf');/**
 * Sets the list cache `key` to `value`.
 *
 * @private
 * @name set
 * @memberOf ListCache
 * @param {string} key The key of the value to set.
 * @param {*} value The value to set.
 * @returns {Object} Returns the list cache instance.
 */function listCacheSet(key,value){var data=this.__data__,index=assocIndexOf(data,key);if(index<0){++this.size;data.push([key,value]);}else{data[index][1]=value;}return this;}module.exports=listCacheSet;},{"./_assocIndexOf":52}],118:[function(require,module,exports){var Hash=require('./_Hash'),ListCache=require('./_ListCache'),Map=require('./_Map');/**
 * Removes all key-value entries from the map.
 *
 * @private
 * @name clear
 * @memberOf MapCache
 */function mapCacheClear(){this.size=0;this.__data__={'hash':new Hash(),'map':new(Map||ListCache)(),'string':new Hash()};}module.exports=mapCacheClear;},{"./_Hash":34,"./_ListCache":35,"./_Map":36}],119:[function(require,module,exports){var getMapData=require('./_getMapData');/**
 * Removes `key` and its value from the map.
 *
 * @private
 * @name delete
 * @memberOf MapCache
 * @param {string} key The key of the value to remove.
 * @returns {boolean} Returns `true` if the entry was removed, else `false`.
 */function mapCacheDelete(key){var result=getMapData(this,key)['delete'](key);this.size-=result?1:0;return result;}module.exports=mapCacheDelete;},{"./_getMapData":92}],120:[function(require,module,exports){var getMapData=require('./_getMapData');/**
 * Gets the map value for `key`.
 *
 * @private
 * @name get
 * @memberOf MapCache
 * @param {string} key The key of the value to get.
 * @returns {*} Returns the entry value.
 */function mapCacheGet(key){return getMapData(this,key).get(key);}module.exports=mapCacheGet;},{"./_getMapData":92}],121:[function(require,module,exports){var getMapData=require('./_getMapData');/**
 * Checks if a map value for `key` exists.
 *
 * @private
 * @name has
 * @memberOf MapCache
 * @param {string} key The key of the entry to check.
 * @returns {boolean} Returns `true` if an entry for `key` exists, else `false`.
 */function mapCacheHas(key){return getMapData(this,key).has(key);}module.exports=mapCacheHas;},{"./_getMapData":92}],122:[function(require,module,exports){var getMapData=require('./_getMapData');/**
 * Sets the map `key` to `value`.
 *
 * @private
 * @name set
 * @memberOf MapCache
 * @param {string} key The key of the value to set.
 * @param {*} value The value to set.
 * @returns {Object} Returns the map cache instance.
 */function mapCacheSet(key,value){var data=getMapData(this,key),size=data.size;data.set(key,value);this.size+=data.size==size?0:1;return this;}module.exports=mapCacheSet;},{"./_getMapData":92}],123:[function(require,module,exports){var getNative=require('./_getNative');/* Built-in method references that are verified to be native. */var nativeCreate=getNative(Object,'create');module.exports=nativeCreate;},{"./_getNative":93}],124:[function(require,module,exports){var overArg=require('./_overArg');/* Built-in method references for those with the same name as other `lodash` methods. */var nativeKeys=overArg(Object.keys,Object);module.exports=nativeKeys;},{"./_overArg":128}],125:[function(require,module,exports){/**
 * This function is like
 * [`Object.keys`](http://ecma-international.org/ecma-262/7.0/#sec-object.keys)
 * except that it includes inherited enumerable properties.
 *
 * @private
 * @param {Object} object The object to query.
 * @returns {Array} Returns the array of property names.
 */function nativeKeysIn(object){var result=[];if(object!=null){for(var key in Object(object)){result.push(key);}}return result;}module.exports=nativeKeysIn;},{}],126:[function(require,module,exports){var freeGlobal=require('./_freeGlobal');/** Detect free variable `exports`. */var freeExports=_typeof(exports)=='object'&&exports&&!exports.nodeType&&exports;/** Detect free variable `module`. */var freeModule=freeExports&&_typeof(module)=='object'&&module&&!module.nodeType&&module;/** Detect the popular CommonJS extension `module.exports`. */var moduleExports=freeModule&&freeModule.exports===freeExports;/** Detect free variable `process` from Node.js. */var freeProcess=moduleExports&&freeGlobal.process;/** Used to access faster Node.js helpers. */var nodeUtil=function(){try{// Use `util.types` for Node.js 10+.
var types=freeModule&&freeModule.require&&freeModule.require('util').types;if(types){return types;}// Legacy `process.binding('util')` for Node.js < 10.
return freeProcess&&freeProcess.binding&&freeProcess.binding('util');}catch(e){}}();module.exports=nodeUtil;},{"./_freeGlobal":89}],127:[function(require,module,exports){/** Used for built-in method references. */var objectProto=Object.prototype;/**
 * Used to resolve the
 * [`toStringTag`](http://ecma-international.org/ecma-262/7.0/#sec-object.prototype.tostring)
 * of values.
 */var nativeObjectToString=objectProto.toString;/**
 * Converts `value` to a string using `Object.prototype.toString`.
 *
 * @private
 * @param {*} value The value to convert.
 * @returns {string} Returns the converted string.
 */function objectToString(value){return nativeObjectToString.call(value);}module.exports=objectToString;},{}],128:[function(require,module,exports){/**
 * Creates a unary function that invokes `func` with its argument transformed.
 *
 * @private
 * @param {Function} func The function to wrap.
 * @param {Function} transform The argument transform.
 * @returns {Function} Returns the new function.
 */function overArg(func,transform){return function(arg){return func(transform(arg));};}module.exports=overArg;},{}],129:[function(require,module,exports){var apply=require('./_apply');/* Built-in method references for those with the same name as other `lodash` methods. */var nativeMax=Math.max;/**
 * A specialized version of `baseRest` which transforms the rest array.
 *
 * @private
 * @param {Function} func The function to apply a rest parameter to.
 * @param {number} [start=func.length-1] The start position of the rest parameter.
 * @param {Function} transform The rest array transform.
 * @returns {Function} Returns the new function.
 */function overRest(func,start,transform){start=nativeMax(start===undefined?func.length-1:start,0);return function(){var args=arguments,index=-1,length=nativeMax(args.length-start,0),array=Array(length);while(++index<length){array[index]=args[start+index];}index=-1;var otherArgs=Array(start+1);while(++index<start){otherArgs[index]=args[index];}otherArgs[start]=transform(array);return apply(func,this,otherArgs);};}module.exports=overRest;},{"./_apply":44}],130:[function(require,module,exports){var freeGlobal=require('./_freeGlobal');/** Detect free variable `self`. */var freeSelf=(typeof self==="undefined"?"undefined":_typeof(self))=='object'&&self&&self.Object===Object&&self;/** Used as a reference to the global object. */var root=freeGlobal||freeSelf||Function('return this')();module.exports=root;},{"./_freeGlobal":89}],131:[function(require,module,exports){/**
 * Gets the value at `key`, unless `key` is "__proto__" or "constructor".
 *
 * @private
 * @param {Object} object The object to query.
 * @param {string} key The key of the property to get.
 * @returns {*} Returns the property value.
 */function safeGet(object,key){if(key==='constructor'&&typeof object[key]==='function'){return;}if(key=='__proto__'){return;}return object[key];}module.exports=safeGet;},{}],132:[function(require,module,exports){var baseSetToString=require('./_baseSetToString'),shortOut=require('./_shortOut');/**
 * Sets the `toString` method of `func` to return `string`.
 *
 * @private
 * @param {Function} func The function to modify.
 * @param {Function} string The `toString` result.
 * @returns {Function} Returns `func`.
 */var setToString=shortOut(baseSetToString);module.exports=setToString;},{"./_baseSetToString":71,"./_shortOut":133}],133:[function(require,module,exports){/** Used to detect hot functions by number of calls within a span of milliseconds. */var HOT_COUNT=800,HOT_SPAN=16;/* Built-in method references for those with the same name as other `lodash` methods. */var nativeNow=Date.now;/**
 * Creates a function that'll short out and invoke `identity` instead
 * of `func` when it's called `HOT_COUNT` or more times in `HOT_SPAN`
 * milliseconds.
 *
 * @private
 * @param {Function} func The function to restrict.
 * @returns {Function} Returns the new shortable function.
 */function shortOut(func){var count=0,lastCalled=0;return function(){var stamp=nativeNow(),remaining=HOT_SPAN-(stamp-lastCalled);lastCalled=stamp;if(remaining>0){if(++count>=HOT_COUNT){return arguments[0];}}else{count=0;}return func.apply(undefined,arguments);};}module.exports=shortOut;},{}],134:[function(require,module,exports){var ListCache=require('./_ListCache');/**
 * Removes all key-value entries from the stack.
 *
 * @private
 * @name clear
 * @memberOf Stack
 */function stackClear(){this.__data__=new ListCache();this.size=0;}module.exports=stackClear;},{"./_ListCache":35}],135:[function(require,module,exports){/**
 * Removes `key` and its value from the stack.
 *
 * @private
 * @name delete
 * @memberOf Stack
 * @param {string} key The key of the value to remove.
 * @returns {boolean} Returns `true` if the entry was removed, else `false`.
 */function stackDelete(key){var data=this.__data__,result=data['delete'](key);this.size=data.size;return result;}module.exports=stackDelete;},{}],136:[function(require,module,exports){/**
 * Gets the stack value for `key`.
 *
 * @private
 * @name get
 * @memberOf Stack
 * @param {string} key The key of the value to get.
 * @returns {*} Returns the entry value.
 */function stackGet(key){return this.__data__.get(key);}module.exports=stackGet;},{}],137:[function(require,module,exports){/**
 * Checks if a stack value for `key` exists.
 *
 * @private
 * @name has
 * @memberOf Stack
 * @param {string} key The key of the entry to check.
 * @returns {boolean} Returns `true` if an entry for `key` exists, else `false`.
 */function stackHas(key){return this.__data__.has(key);}module.exports=stackHas;},{}],138:[function(require,module,exports){var ListCache=require('./_ListCache'),Map=require('./_Map'),MapCache=require('./_MapCache');/** Used as the size to enable large array optimizations. */var LARGE_ARRAY_SIZE=200;/**
 * Sets the stack `key` to `value`.
 *
 * @private
 * @name set
 * @memberOf Stack
 * @param {string} key The key of the value to set.
 * @param {*} value The value to set.
 * @returns {Object} Returns the stack cache instance.
 */function stackSet(key,value){var data=this.__data__;if(data instanceof ListCache){var pairs=data.__data__;if(!Map||pairs.length<LARGE_ARRAY_SIZE-1){pairs.push([key,value]);this.size=++data.size;return this;}data=this.__data__=new MapCache(pairs);}data.set(key,value);this.size=data.size;return this;}module.exports=stackSet;},{"./_ListCache":35,"./_Map":36,"./_MapCache":37}],139:[function(require,module,exports){/** Used for built-in method references. */var funcProto=Function.prototype;/** Used to resolve the decompiled source of functions. */var funcToString=funcProto.toString;/**
 * Converts `func` to its source code.
 *
 * @private
 * @param {Function} func The function to convert.
 * @returns {string} Returns the source code.
 */function toSource(func){if(func!=null){try{return funcToString.call(func);}catch(e){}try{return func+'';}catch(e){}}return'';}module.exports=toSource;},{}],140:[function(require,module,exports){var baseClone=require('./_baseClone');/** Used to compose bitmasks for cloning. */var CLONE_DEEP_FLAG=1,CLONE_SYMBOLS_FLAG=4;/**
 * This method is like `_.clone` except that it recursively clones `value`.
 *
 * @static
 * @memberOf _
 * @since 1.0.0
 * @category Lang
 * @param {*} value The value to recursively clone.
 * @returns {*} Returns the deep cloned value.
 * @see _.clone
 * @example
 *
 * var objects = [{ 'a': 1 }, { 'b': 2 }];
 *
 * var deep = _.cloneDeep(objects);
 * console.log(deep[0] === objects[0]);
 * // => false
 */function cloneDeep(value){return baseClone(value,CLONE_DEEP_FLAG|CLONE_SYMBOLS_FLAG);}module.exports=cloneDeep;},{"./_baseClone":56}],141:[function(require,module,exports){/**
 * Creates a function that returns `value`.
 *
 * @static
 * @memberOf _
 * @since 2.4.0
 * @category Util
 * @param {*} value The value to return from the new function.
 * @returns {Function} Returns the new constant function.
 * @example
 *
 * var objects = _.times(2, _.constant({ 'a': 1 }));
 *
 * console.log(objects);
 * // => [{ 'a': 1 }, { 'a': 1 }]
 *
 * console.log(objects[0] === objects[1]);
 * // => true
 */function constant(value){return function(){return value;};}module.exports=constant;},{}],142:[function(require,module,exports){/**
 * Performs a
 * [`SameValueZero`](http://ecma-international.org/ecma-262/7.0/#sec-samevaluezero)
 * comparison between two values to determine if they are equivalent.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to compare.
 * @param {*} other The other value to compare.
 * @returns {boolean} Returns `true` if the values are equivalent, else `false`.
 * @example
 *
 * var object = { 'a': 1 };
 * var other = { 'a': 1 };
 *
 * _.eq(object, object);
 * // => true
 *
 * _.eq(object, other);
 * // => false
 *
 * _.eq('a', 'a');
 * // => true
 *
 * _.eq('a', Object('a'));
 * // => false
 *
 * _.eq(NaN, NaN);
 * // => true
 */function eq(value,other){return value===other||value!==value&&other!==other;}module.exports=eq;},{}],143:[function(require,module,exports){var toString=require('./toString');/**
 * Used to match `RegExp`
 * [syntax characters](http://ecma-international.org/ecma-262/7.0/#sec-patterns).
 */var reRegExpChar=/[\\^$.*+?()[\]{}|]/g,reHasRegExpChar=RegExp(reRegExpChar.source);/**
 * Escapes the `RegExp` special characters "^", "$", "\", ".", "*", "+",
 * "?", "(", ")", "[", "]", "{", "}", and "|" in `string`.
 *
 * @static
 * @memberOf _
 * @since 3.0.0
 * @category String
 * @param {string} [string=''] The string to escape.
 * @returns {string} Returns the escaped string.
 * @example
 *
 * _.escapeRegExp('[lodash](https://lodash.com/)');
 * // => '\[lodash\]\(https://lodash\.com/\)'
 */function escapeRegExp(string){string=toString(string);return string&&reHasRegExpChar.test(string)?string.replace(reRegExpChar,'\\$&'):string;}module.exports=escapeRegExp;},{"./toString":166}],144:[function(require,module,exports){/**
 * This method returns the first argument it receives.
 *
 * @static
 * @since 0.1.0
 * @memberOf _
 * @category Util
 * @param {*} value Any value.
 * @returns {*} Returns `value`.
 * @example
 *
 * var object = { 'a': 1 };
 *
 * console.log(_.identity(object) === object);
 * // => true
 */function identity(value){return value;}module.exports=identity;},{}],145:[function(require,module,exports){var baseIsArguments=require('./_baseIsArguments'),isObjectLike=require('./isObjectLike');/** Used for built-in method references. */var objectProto=Object.prototype;/** Used to check objects for own properties. */var hasOwnProperty=objectProto.hasOwnProperty;/** Built-in value references. */var propertyIsEnumerable=objectProto.propertyIsEnumerable;/**
 * Checks if `value` is likely an `arguments` object.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is an `arguments` object,
 *  else `false`.
 * @example
 *
 * _.isArguments(function() { return arguments; }());
 * // => true
 *
 * _.isArguments([1, 2, 3]);
 * // => false
 */var isArguments=baseIsArguments(function(){return arguments;}())?baseIsArguments:function(value){return isObjectLike(value)&&hasOwnProperty.call(value,'callee')&&!propertyIsEnumerable.call(value,'callee');};module.exports=isArguments;},{"./_baseIsArguments":61,"./isObjectLike":154}],146:[function(require,module,exports){/**
 * Checks if `value` is classified as an `Array` object.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is an array, else `false`.
 * @example
 *
 * _.isArray([1, 2, 3]);
 * // => true
 *
 * _.isArray(document.body.children);
 * // => false
 *
 * _.isArray('abc');
 * // => false
 *
 * _.isArray(_.noop);
 * // => false
 */var isArray=Array.isArray;module.exports=isArray;},{}],147:[function(require,module,exports){var isFunction=require('./isFunction'),isLength=require('./isLength');/**
 * Checks if `value` is array-like. A value is considered array-like if it's
 * not a function and has a `value.length` that's an integer greater than or
 * equal to `0` and less than or equal to `Number.MAX_SAFE_INTEGER`.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is array-like, else `false`.
 * @example
 *
 * _.isArrayLike([1, 2, 3]);
 * // => true
 *
 * _.isArrayLike(document.body.children);
 * // => true
 *
 * _.isArrayLike('abc');
 * // => true
 *
 * _.isArrayLike(_.noop);
 * // => false
 */function isArrayLike(value){return value!=null&&isLength(value.length)&&!isFunction(value);}module.exports=isArrayLike;},{"./isFunction":150,"./isLength":151}],148:[function(require,module,exports){var isArrayLike=require('./isArrayLike'),isObjectLike=require('./isObjectLike');/**
 * This method is like `_.isArrayLike` except that it also checks if `value`
 * is an object.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is an array-like object,
 *  else `false`.
 * @example
 *
 * _.isArrayLikeObject([1, 2, 3]);
 * // => true
 *
 * _.isArrayLikeObject(document.body.children);
 * // => true
 *
 * _.isArrayLikeObject('abc');
 * // => false
 *
 * _.isArrayLikeObject(_.noop);
 * // => false
 */function isArrayLikeObject(value){return isObjectLike(value)&&isArrayLike(value);}module.exports=isArrayLikeObject;},{"./isArrayLike":147,"./isObjectLike":154}],149:[function(require,module,exports){var root=require('./_root'),stubFalse=require('./stubFalse');/** Detect free variable `exports`. */var freeExports=_typeof(exports)=='object'&&exports&&!exports.nodeType&&exports;/** Detect free variable `module`. */var freeModule=freeExports&&_typeof(module)=='object'&&module&&!module.nodeType&&module;/** Detect the popular CommonJS extension `module.exports`. */var moduleExports=freeModule&&freeModule.exports===freeExports;/** Built-in value references. */var Buffer=moduleExports?root.Buffer:undefined;/* Built-in method references for those with the same name as other `lodash` methods. */var nativeIsBuffer=Buffer?Buffer.isBuffer:undefined;/**
 * Checks if `value` is a buffer.
 *
 * @static
 * @memberOf _
 * @since 4.3.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a buffer, else `false`.
 * @example
 *
 * _.isBuffer(new Buffer(2));
 * // => true
 *
 * _.isBuffer(new Uint8Array(2));
 * // => false
 */var isBuffer=nativeIsBuffer||stubFalse;module.exports=isBuffer;},{"./_root":130,"./stubFalse":164}],150:[function(require,module,exports){var baseGetTag=require('./_baseGetTag'),isObject=require('./isObject');/** `Object#toString` result references. */var asyncTag='[object AsyncFunction]',funcTag='[object Function]',genTag='[object GeneratorFunction]',proxyTag='[object Proxy]';/**
 * Checks if `value` is classified as a `Function` object.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a function, else `false`.
 * @example
 *
 * _.isFunction(_);
 * // => true
 *
 * _.isFunction(/abc/);
 * // => false
 */function isFunction(value){if(!isObject(value)){return false;}// The use of `Object#toString` avoids issues with the `typeof` operator
// in Safari 9 which returns 'object' for typed arrays and other constructors.
var tag=baseGetTag(value);return tag==funcTag||tag==genTag||tag==asyncTag||tag==proxyTag;}module.exports=isFunction;},{"./_baseGetTag":60,"./isObject":153}],151:[function(require,module,exports){/** Used as references for various `Number` constants. */var MAX_SAFE_INTEGER=9007199254740991;/**
 * Checks if `value` is a valid array-like length.
 *
 * **Note:** This method is loosely based on
 * [`ToLength`](http://ecma-international.org/ecma-262/7.0/#sec-tolength).
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a valid length, else `false`.
 * @example
 *
 * _.isLength(3);
 * // => true
 *
 * _.isLength(Number.MIN_VALUE);
 * // => false
 *
 * _.isLength(Infinity);
 * // => false
 *
 * _.isLength('3');
 * // => false
 */function isLength(value){return typeof value=='number'&&value>-1&&value%1==0&&value<=MAX_SAFE_INTEGER;}module.exports=isLength;},{}],152:[function(require,module,exports){var baseIsMap=require('./_baseIsMap'),baseUnary=require('./_baseUnary'),nodeUtil=require('./_nodeUtil');/* Node.js helper references. */var nodeIsMap=nodeUtil&&nodeUtil.isMap;/**
 * Checks if `value` is classified as a `Map` object.
 *
 * @static
 * @memberOf _
 * @since 4.3.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a map, else `false`.
 * @example
 *
 * _.isMap(new Map);
 * // => true
 *
 * _.isMap(new WeakMap);
 * // => false
 */var isMap=nodeIsMap?baseUnary(nodeIsMap):baseIsMap;module.exports=isMap;},{"./_baseIsMap":62,"./_baseUnary":74,"./_nodeUtil":126}],153:[function(require,module,exports){/**
 * Checks if `value` is the
 * [language type](http://www.ecma-international.org/ecma-262/7.0/#sec-ecmascript-language-types)
 * of `Object`. (e.g. arrays, functions, objects, regexes, `new Number(0)`, and `new String('')`)
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is an object, else `false`.
 * @example
 *
 * _.isObject({});
 * // => true
 *
 * _.isObject([1, 2, 3]);
 * // => true
 *
 * _.isObject(_.noop);
 * // => true
 *
 * _.isObject(null);
 * // => false
 */function isObject(value){var type=_typeof(value);return value!=null&&(type=='object'||type=='function');}module.exports=isObject;},{}],154:[function(require,module,exports){/**
 * Checks if `value` is object-like. A value is object-like if it's not `null`
 * and has a `typeof` result of "object".
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is object-like, else `false`.
 * @example
 *
 * _.isObjectLike({});
 * // => true
 *
 * _.isObjectLike([1, 2, 3]);
 * // => true
 *
 * _.isObjectLike(_.noop);
 * // => false
 *
 * _.isObjectLike(null);
 * // => false
 */function isObjectLike(value){return value!=null&&_typeof(value)=='object';}module.exports=isObjectLike;},{}],155:[function(require,module,exports){var baseGetTag=require('./_baseGetTag'),getPrototype=require('./_getPrototype'),isObjectLike=require('./isObjectLike');/** `Object#toString` result references. */var objectTag='[object Object]';/** Used for built-in method references. */var funcProto=Function.prototype,objectProto=Object.prototype;/** Used to resolve the decompiled source of functions. */var funcToString=funcProto.toString;/** Used to check objects for own properties. */var hasOwnProperty=objectProto.hasOwnProperty;/** Used to infer the `Object` constructor. */var objectCtorString=funcToString.call(Object);/**
 * Checks if `value` is a plain object, that is, an object created by the
 * `Object` constructor or one with a `[[Prototype]]` of `null`.
 *
 * @static
 * @memberOf _
 * @since 0.8.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a plain object, else `false`.
 * @example
 *
 * function Foo() {
 *   this.a = 1;
 * }
 *
 * _.isPlainObject(new Foo);
 * // => false
 *
 * _.isPlainObject([1, 2, 3]);
 * // => false
 *
 * _.isPlainObject({ 'x': 0, 'y': 0 });
 * // => true
 *
 * _.isPlainObject(Object.create(null));
 * // => true
 */function isPlainObject(value){if(!isObjectLike(value)||baseGetTag(value)!=objectTag){return false;}var proto=getPrototype(value);if(proto===null){return true;}var Ctor=hasOwnProperty.call(proto,'constructor')&&proto.constructor;return typeof Ctor=='function'&&Ctor instanceof Ctor&&funcToString.call(Ctor)==objectCtorString;}module.exports=isPlainObject;},{"./_baseGetTag":60,"./_getPrototype":94,"./isObjectLike":154}],156:[function(require,module,exports){var baseIsSet=require('./_baseIsSet'),baseUnary=require('./_baseUnary'),nodeUtil=require('./_nodeUtil');/* Node.js helper references. */var nodeIsSet=nodeUtil&&nodeUtil.isSet;/**
 * Checks if `value` is classified as a `Set` object.
 *
 * @static
 * @memberOf _
 * @since 4.3.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a set, else `false`.
 * @example
 *
 * _.isSet(new Set);
 * // => true
 *
 * _.isSet(new WeakSet);
 * // => false
 */var isSet=nodeIsSet?baseUnary(nodeIsSet):baseIsSet;module.exports=isSet;},{"./_baseIsSet":64,"./_baseUnary":74,"./_nodeUtil":126}],157:[function(require,module,exports){var baseGetTag=require('./_baseGetTag'),isArray=require('./isArray'),isObjectLike=require('./isObjectLike');/** `Object#toString` result references. */var stringTag='[object String]';/**
 * Checks if `value` is classified as a `String` primitive or object.
 *
 * @static
 * @since 0.1.0
 * @memberOf _
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a string, else `false`.
 * @example
 *
 * _.isString('abc');
 * // => true
 *
 * _.isString(1);
 * // => false
 */function isString(value){return typeof value=='string'||!isArray(value)&&isObjectLike(value)&&baseGetTag(value)==stringTag;}module.exports=isString;},{"./_baseGetTag":60,"./isArray":146,"./isObjectLike":154}],158:[function(require,module,exports){var baseGetTag=require('./_baseGetTag'),isObjectLike=require('./isObjectLike');/** `Object#toString` result references. */var symbolTag='[object Symbol]';/**
 * Checks if `value` is classified as a `Symbol` primitive or object.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a symbol, else `false`.
 * @example
 *
 * _.isSymbol(Symbol.iterator);
 * // => true
 *
 * _.isSymbol('abc');
 * // => false
 */function isSymbol(value){return _typeof(value)=='symbol'||isObjectLike(value)&&baseGetTag(value)==symbolTag;}module.exports=isSymbol;},{"./_baseGetTag":60,"./isObjectLike":154}],159:[function(require,module,exports){var baseIsTypedArray=require('./_baseIsTypedArray'),baseUnary=require('./_baseUnary'),nodeUtil=require('./_nodeUtil');/* Node.js helper references. */var nodeIsTypedArray=nodeUtil&&nodeUtil.isTypedArray;/**
 * Checks if `value` is classified as a typed array.
 *
 * @static
 * @memberOf _
 * @since 3.0.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a typed array, else `false`.
 * @example
 *
 * _.isTypedArray(new Uint8Array);
 * // => true
 *
 * _.isTypedArray([]);
 * // => false
 */var isTypedArray=nodeIsTypedArray?baseUnary(nodeIsTypedArray):baseIsTypedArray;module.exports=isTypedArray;},{"./_baseIsTypedArray":65,"./_baseUnary":74,"./_nodeUtil":126}],160:[function(require,module,exports){var arrayLikeKeys=require('./_arrayLikeKeys'),baseKeys=require('./_baseKeys'),isArrayLike=require('./isArrayLike');/**
 * Creates an array of the own enumerable property names of `object`.
 *
 * **Note:** Non-object values are coerced to objects. See the
 * [ES spec](http://ecma-international.org/ecma-262/7.0/#sec-object.keys)
 * for more details.
 *
 * @static
 * @since 0.1.0
 * @memberOf _
 * @category Object
 * @param {Object} object The object to query.
 * @returns {Array} Returns the array of property names.
 * @example
 *
 * function Foo() {
 *   this.a = 1;
 *   this.b = 2;
 * }
 *
 * Foo.prototype.c = 3;
 *
 * _.keys(new Foo);
 * // => ['a', 'b'] (iteration order is not guaranteed)
 *
 * _.keys('hi');
 * // => ['0', '1']
 */function keys(object){return isArrayLike(object)?arrayLikeKeys(object):baseKeys(object);}module.exports=keys;},{"./_arrayLikeKeys":47,"./_baseKeys":66,"./isArrayLike":147}],161:[function(require,module,exports){var arrayLikeKeys=require('./_arrayLikeKeys'),baseKeysIn=require('./_baseKeysIn'),isArrayLike=require('./isArrayLike');/**
 * Creates an array of the own and inherited enumerable property names of `object`.
 *
 * **Note:** Non-object values are coerced to objects.
 *
 * @static
 * @memberOf _
 * @since 3.0.0
 * @category Object
 * @param {Object} object The object to query.
 * @returns {Array} Returns the array of property names.
 * @example
 *
 * function Foo() {
 *   this.a = 1;
 *   this.b = 2;
 * }
 *
 * Foo.prototype.c = 3;
 *
 * _.keysIn(new Foo);
 * // => ['a', 'b', 'c'] (iteration order is not guaranteed)
 */function keysIn(object){return isArrayLike(object)?arrayLikeKeys(object,true):baseKeysIn(object);}module.exports=keysIn;},{"./_arrayLikeKeys":47,"./_baseKeysIn":67,"./isArrayLike":147}],162:[function(require,module,exports){var baseMerge=require('./_baseMerge'),createAssigner=require('./_createAssigner');/**
 * This method is like `_.merge` except that it accepts `customizer` which
 * is invoked to produce the merged values of the destination and source
 * properties. If `customizer` returns `undefined`, merging is handled by the
 * method instead. The `customizer` is invoked with six arguments:
 * (objValue, srcValue, key, object, source, stack).
 *
 * **Note:** This method mutates `object`.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Object
 * @param {Object} object The destination object.
 * @param {...Object} sources The source objects.
 * @param {Function} customizer The function to customize assigned values.
 * @returns {Object} Returns `object`.
 * @example
 *
 * function customizer(objValue, srcValue) {
 *   if (_.isArray(objValue)) {
 *     return objValue.concat(srcValue);
 *   }
 * }
 *
 * var object = { 'a': [1], 'b': [2] };
 * var other = { 'a': [3], 'b': [4] };
 *
 * _.mergeWith(object, other, customizer);
 * // => { 'a': [1, 3], 'b': [2, 4] }
 */var mergeWith=createAssigner(function(object,source,srcIndex,customizer){baseMerge(object,source,srcIndex,customizer);});module.exports=mergeWith;},{"./_baseMerge":68,"./_createAssigner":86}],163:[function(require,module,exports){/**
 * This method returns a new empty array.
 *
 * @static
 * @memberOf _
 * @since 4.13.0
 * @category Util
 * @returns {Array} Returns the new empty array.
 * @example
 *
 * var arrays = _.times(2, _.stubArray);
 *
 * console.log(arrays);
 * // => [[], []]
 *
 * console.log(arrays[0] === arrays[1]);
 * // => false
 */function stubArray(){return[];}module.exports=stubArray;},{}],164:[function(require,module,exports){/**
 * This method returns `false`.
 *
 * @static
 * @memberOf _
 * @since 4.13.0
 * @category Util
 * @returns {boolean} Returns `false`.
 * @example
 *
 * _.times(2, _.stubFalse);
 * // => [false, false]
 */function stubFalse(){return false;}module.exports=stubFalse;},{}],165:[function(require,module,exports){var copyObject=require('./_copyObject'),keysIn=require('./keysIn');/**
 * Converts `value` to a plain object flattening inherited enumerable string
 * keyed properties of `value` to own properties of the plain object.
 *
 * @static
 * @memberOf _
 * @since 3.0.0
 * @category Lang
 * @param {*} value The value to convert.
 * @returns {Object} Returns the converted plain object.
 * @example
 *
 * function Foo() {
 *   this.b = 2;
 * }
 *
 * Foo.prototype.c = 3;
 *
 * _.assign({ 'a': 1 }, new Foo);
 * // => { 'a': 1, 'b': 2 }
 *
 * _.assign({ 'a': 1 }, _.toPlainObject(new Foo));
 * // => { 'a': 1, 'b': 2, 'c': 3 }
 */function toPlainObject(value){return copyObject(value,keysIn(value));}module.exports=toPlainObject;},{"./_copyObject":82,"./keysIn":161}],166:[function(require,module,exports){var baseToString=require('./_baseToString');/**
 * Converts `value` to a string. An empty string is returned for `null`
 * and `undefined` values. The sign of `-0` is preserved.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to convert.
 * @returns {string} Returns the converted string.
 * @example
 *
 * _.toString(null);
 * // => ''
 *
 * _.toString(-0);
 * // => '-0'
 *
 * _.toString([1, 2, 3]);
 * // => '1,2,3'
 */function toString(value){return value==null?'':baseToString(value);}module.exports=toString;},{"./_baseToString":73}],167:[function(require,module,exports){/**
 * Srcset Parser
 *
 * By Alex Bell |  MIT License
 *
 * JS Parser for the string value that appears in markup <img srcset="here">
 *
 * @returns Array [{url: _, d: _, w: _, h:_}, ...]
 *
 * Based super duper closely on the reference algorithm at:
 * https://html.spec.whatwg.org/multipage/embedded-content.html#parse-a-srcset-attribute
 *
 * Most comments are copied in directly from the spec
 * (except for comments in parens).
 */(function(root,factory){if(typeof define==='function'&&define.amd){// AMD. Register as an anonymous module.
define([],factory);}else if(_typeof(module)==='object'&&module.exports){// Node. Does not work with strict CommonJS, but
// only CommonJS-like environments that support module.exports,
// like Node.
module.exports=factory();}else{// Browser globals (root is window)
root.parseSrcset=factory();}})(this,function(){// 1. Let input be the value passed to this algorithm.
return function(input){// UTILITY FUNCTIONS
// Manual is faster than RegEx
// http://bjorn.tipling.com/state-and-regular-expressions-in-javascript
// http://jsperf.com/whitespace-character/5
function isSpace(c){return c===" "||// space
c==="\t"||// horizontal tab
c==="\n"||// new line
c==="\f"||// form feed
c==="\r";// carriage return
}function collectCharacters(regEx){var chars,match=regEx.exec(input.substring(pos));if(match){chars=match[0];pos+=chars.length;return chars;}}var inputLength=input.length,// (Don't use \s, to avoid matching non-breaking space)
regexLeadingSpaces=/^[ \t\n\r\u000c]+/,regexLeadingCommasOrSpaces=/^[, \t\n\r\u000c]+/,regexLeadingNotSpaces=/^[^ \t\n\r\u000c]+/,regexTrailingCommas=/[,]+$/,regexNonNegativeInteger=/^\d+$/,// ( Positive or negative or unsigned integers or decimals, without or without exponents.
// Must include at least one digit.
// According to spec tests any decimal point must be followed by a digit.
// No leading plus sign is allowed.)
// https://html.spec.whatwg.org/multipage/infrastructure.html#valid-floating-point-number
regexFloatingPoint=/^-?(?:[0-9]+|[0-9]*\.[0-9]+)(?:[eE][+-]?[0-9]+)?$/,url,descriptors,currentDescriptor,state,c,// 2. Let position be a pointer into input, initially pointing at the start
//    of the string.
pos=0,// 3. Let candidates be an initially empty source set.
candidates=[];// 4. Splitting loop: Collect a sequence of characters that are space
//    characters or U+002C COMMA characters. If any U+002C COMMA characters
//    were collected, that is a parse error.
while(true){collectCharacters(regexLeadingCommasOrSpaces);// 5. If position is past the end of input, return candidates and abort these steps.
if(pos>=inputLength){return candidates;// (we're done, this is the sole return path)
}// 6. Collect a sequence of characters that are not space characters,
//    and let that be url.
url=collectCharacters(regexLeadingNotSpaces);// 7. Let descriptors be a new empty list.
descriptors=[];// 8. If url ends with a U+002C COMMA character (,), follow these substeps:
//		(1). Remove all trailing U+002C COMMA characters from url. If this removed
//         more than one character, that is a parse error.
if(url.slice(-1)===","){url=url.replace(regexTrailingCommas,"");// (Jump ahead to step 9 to skip tokenization and just push the candidate).
parseDescriptors();//	Otherwise, follow these substeps:
}else{tokenize();}// (close else of step 8)
// 16. Return to the step labeled splitting loop.
}// (Close of big while loop.)
/**
		 * Tokenizes descriptor properties prior to parsing
		 * Returns undefined.
		 */function tokenize(){// 8.1. Descriptor tokeniser: Skip whitespace
collectCharacters(regexLeadingSpaces);// 8.2. Let current descriptor be the empty string.
currentDescriptor="";// 8.3. Let state be in descriptor.
state="in descriptor";while(true){// 8.4. Let c be the character at position.
c=input.charAt(pos);//  Do the following depending on the value of state.
//  For the purpose of this step, "EOF" is a special character representing
//  that position is past the end of input.
// In descriptor
if(state==="in descriptor"){// Do the following, depending on the value of c:
// Space character
// If current descriptor is not empty, append current descriptor to
// descriptors and let current descriptor be the empty string.
// Set state to after descriptor.
if(isSpace(c)){if(currentDescriptor){descriptors.push(currentDescriptor);currentDescriptor="";state="after descriptor";}// U+002C COMMA (,)
// Advance position to the next character in input. If current descriptor
// is not empty, append current descriptor to descriptors. Jump to the step
// labeled descriptor parser.
}else if(c===","){pos+=1;if(currentDescriptor){descriptors.push(currentDescriptor);}parseDescriptors();return;// U+0028 LEFT PARENTHESIS (()
// Append c to current descriptor. Set state to in parens.
}else if(c==="("){currentDescriptor=currentDescriptor+c;state="in parens";// EOF
// If current descriptor is not empty, append current descriptor to
// descriptors. Jump to the step labeled descriptor parser.
}else if(c===""){if(currentDescriptor){descriptors.push(currentDescriptor);}parseDescriptors();return;// Anything else
// Append c to current descriptor.
}else{currentDescriptor=currentDescriptor+c;}// (end "in descriptor"
// In parens
}else if(state==="in parens"){// U+0029 RIGHT PARENTHESIS ())
// Append c to current descriptor. Set state to in descriptor.
if(c===")"){currentDescriptor=currentDescriptor+c;state="in descriptor";// EOF
// Append current descriptor to descriptors. Jump to the step labeled
// descriptor parser.
}else if(c===""){descriptors.push(currentDescriptor);parseDescriptors();return;// Anything else
// Append c to current descriptor.
}else{currentDescriptor=currentDescriptor+c;}// After descriptor
}else if(state==="after descriptor"){// Do the following, depending on the value of c:
// Space character: Stay in this state.
if(isSpace(c)){// EOF: Jump to the step labeled descriptor parser.
}else if(c===""){parseDescriptors();return;// Anything else
// Set state to in descriptor. Set position to the previous character in input.
}else{state="in descriptor";pos-=1;}}// Advance position to the next character in input.
pos+=1;// Repeat this step.
}// (close while true loop)
}/**
		 * Adds descriptor properties to a candidate, pushes to the candidates array
		 * @return undefined
		 */ // Declared outside of the while loop so that it's only created once.
function parseDescriptors(){// 9. Descriptor parser: Let error be no.
var pError=false,// 10. Let width be absent.
// 11. Let density be absent.
// 12. Let future-compat-h be absent. (We're implementing it now as h)
w,d,h,i,candidate={},desc,lastChar,value,intVal,floatVal;// 13. For each descriptor in descriptors, run the appropriate set of steps
// from the following list:
for(i=0;i<descriptors.length;i++){desc=descriptors[i];lastChar=desc[desc.length-1];value=desc.substring(0,desc.length-1);intVal=parseInt(value,10);floatVal=parseFloat(value);// If the descriptor consists of a valid non-negative integer followed by
// a U+0077 LATIN SMALL LETTER W character
if(regexNonNegativeInteger.test(value)&&lastChar==="w"){// If width and density are not both absent, then let error be yes.
if(w||d){pError=true;}// Apply the rules for parsing non-negative integers to the descriptor.
// If the result is zero, let error be yes.
// Otherwise, let width be the result.
if(intVal===0){pError=true;}else{w=intVal;}// If the descriptor consists of a valid floating-point number followed by
// a U+0078 LATIN SMALL LETTER X character
}else if(regexFloatingPoint.test(value)&&lastChar==="x"){// If width, density and future-compat-h are not all absent, then let error
// be yes.
if(w||d||h){pError=true;}// Apply the rules for parsing floating-point number values to the descriptor.
// If the result is less than zero, let error be yes. Otherwise, let density
// be the result.
if(floatVal<0){pError=true;}else{d=floatVal;}// If the descriptor consists of a valid non-negative integer followed by
// a U+0068 LATIN SMALL LETTER H character
}else if(regexNonNegativeInteger.test(value)&&lastChar==="h"){// If height and density are not both absent, then let error be yes.
if(h||d){pError=true;}// Apply the rules for parsing non-negative integers to the descriptor.
// If the result is zero, let error be yes. Otherwise, let future-compat-h
// be the result.
if(intVal===0){pError=true;}else{h=intVal;}// Anything else, Let error be yes.
}else{pError=true;}}// (close step 13 for loop)
// 15. If error is still no, then append a new image source to candidates whose
// URL is url, associated with a width width if not absent and a pixel
// density density if not absent. Otherwise, there is a parse error.
if(!pError){candidate.url=url;if(w){candidate.w=w;}if(d){candidate.d=d;}if(h){candidate.h=h;}candidates.push(candidate);}else if(console&&console.log){console.log("Invalid srcset descriptor found in '"+input+"' at '"+desc+"'.");}}// (close parseDescriptors fn)
};});},{}],168:[function(require,module,exports){(function(process){// .dirname, .basename, and .extname methods are extracted from Node.js v8.11.1,
// backported and transplited with Babel, with backwards-compat fixes
// Copyright Joyent, Inc. and other Node contributors.
//
// Permission is hereby granted, free of charge, to any person obtaining a
// copy of this software and associated documentation files (the
// "Software"), to deal in the Software without restriction, including
// without limitation the rights to use, copy, modify, merge, publish,
// distribute, sublicense, and/or sell copies of the Software, and to permit
// persons to whom the Software is furnished to do so, subject to the
// following conditions:
//
// The above copyright notice and this permission notice shall be included
// in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
// OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
// NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
// DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
// OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
// USE OR OTHER DEALINGS IN THE SOFTWARE.
// resolves . and .. elements in a path array with directory names there
// must be no slashes, empty elements, or device names (c:\) in the array
// (so also no leading and trailing slashes - it does not distinguish
// relative and absolute paths)
function normalizeArray(parts,allowAboveRoot){// if the path tries to go above the root, `up` ends up > 0
var up=0;for(var i=parts.length-1;i>=0;i--){var last=parts[i];if(last==='.'){parts.splice(i,1);}else if(last==='..'){parts.splice(i,1);up++;}else if(up){parts.splice(i,1);up--;}}// if the path is allowed to go above the root, restore leading ..s
if(allowAboveRoot){for(;up--;up){parts.unshift('..');}}return parts;}// path.resolve([from ...], to)
// posix version
exports.resolve=function(){var resolvedPath='',resolvedAbsolute=false;for(var i=arguments.length-1;i>=-1&&!resolvedAbsolute;i--){var path=i>=0?arguments[i]:process.cwd();// Skip empty and invalid entries
if(typeof path!=='string'){throw new TypeError('Arguments to path.resolve must be strings');}else if(!path){continue;}resolvedPath=path+'/'+resolvedPath;resolvedAbsolute=path.charAt(0)==='/';}// At this point the path should be resolved to a full absolute path, but
// handle relative paths to be safe (might happen when process.cwd() fails)
// Normalize the path
resolvedPath=normalizeArray(filter(resolvedPath.split('/'),function(p){return!!p;}),!resolvedAbsolute).join('/');return(resolvedAbsolute?'/':'')+resolvedPath||'.';};// path.normalize(path)
// posix version
exports.normalize=function(path){var isAbsolute=exports.isAbsolute(path),trailingSlash=substr(path,-1)==='/';// Normalize the path
path=normalizeArray(filter(path.split('/'),function(p){return!!p;}),!isAbsolute).join('/');if(!path&&!isAbsolute){path='.';}if(path&&trailingSlash){path+='/';}return(isAbsolute?'/':'')+path;};// posix version
exports.isAbsolute=function(path){return path.charAt(0)==='/';};// posix version
exports.join=function(){var paths=Array.prototype.slice.call(arguments,0);return exports.normalize(filter(paths,function(p,index){if(typeof p!=='string'){throw new TypeError('Arguments to path.join must be strings');}return p;}).join('/'));};// path.relative(from, to)
// posix version
exports.relative=function(from,to){from=exports.resolve(from).substr(1);to=exports.resolve(to).substr(1);function trim(arr){var start=0;for(;start<arr.length;start++){if(arr[start]!=='')break;}var end=arr.length-1;for(;end>=0;end--){if(arr[end]!=='')break;}if(start>end)return[];return arr.slice(start,end-start+1);}var fromParts=trim(from.split('/'));var toParts=trim(to.split('/'));var length=Math.min(fromParts.length,toParts.length);var samePartsLength=length;for(var i=0;i<length;i++){if(fromParts[i]!==toParts[i]){samePartsLength=i;break;}}var outputParts=[];for(var i=samePartsLength;i<fromParts.length;i++){outputParts.push('..');}outputParts=outputParts.concat(toParts.slice(samePartsLength));return outputParts.join('/');};exports.sep='/';exports.delimiter=':';exports.dirname=function(path){if(typeof path!=='string')path=path+'';if(path.length===0)return'.';var code=path.charCodeAt(0);var hasRoot=code===47/*/*/;var end=-1;var matchedSlash=true;for(var i=path.length-1;i>=1;--i){code=path.charCodeAt(i);if(code===47/*/*/){if(!matchedSlash){end=i;break;}}else{// We saw the first non-path separator
matchedSlash=false;}}if(end===-1)return hasRoot?'/':'.';if(hasRoot&&end===1){// return '//';
// Backwards-compat fix:
return'/';}return path.slice(0,end);};function basename(path){if(typeof path!=='string')path=path+'';var start=0;var end=-1;var matchedSlash=true;var i;for(i=path.length-1;i>=0;--i){if(path.charCodeAt(i)===47/*/*/){// If we reached a path separator that was not part of a set of path
// separators at the end of the string, stop now
if(!matchedSlash){start=i+1;break;}}else if(end===-1){// We saw the first non-path separator, mark this as the end of our
// path component
matchedSlash=false;end=i+1;}}if(end===-1)return'';return path.slice(start,end);}// Uses a mixed approach for backwards-compatibility, as ext behavior changed
// in new Node.js versions, so only basename() above is backported here
exports.basename=function(path,ext){var f=basename(path);if(ext&&f.substr(-1*ext.length)===ext){f=f.substr(0,f.length-ext.length);}return f;};exports.extname=function(path){if(typeof path!=='string')path=path+'';var startDot=-1;var startPart=0;var end=-1;var matchedSlash=true;// Track the state of characters (if any) we see before our first dot and
// after any path separator we find
var preDotState=0;for(var i=path.length-1;i>=0;--i){var code=path.charCodeAt(i);if(code===47/*/*/){// If we reached a path separator that was not part of a set of path
// separators at the end of the string, stop now
if(!matchedSlash){startPart=i+1;break;}continue;}if(end===-1){// We saw the first non-path separator, mark this as the end of our
// extension
matchedSlash=false;end=i+1;}if(code===46/*.*/){// If this is our first dot, mark it as the start of our extension
if(startDot===-1)startDot=i;else if(preDotState!==1)preDotState=1;}else if(startDot!==-1){// We saw a non-dot and non-path separator before our dot, so we should
// have a good chance at having a non-empty extension
preDotState=-1;}}if(startDot===-1||end===-1||// We saw a non-dot character immediately before the dot
preDotState===0||// The (right-most) trimmed path component is exactly '..'
preDotState===1&&startDot===end-1&&startDot===startPart+1){return'';}return path.slice(startDot,end);};function filter(xs,f){if(xs.filter)return xs.filter(f);var res=[];for(var i=0;i<xs.length;i++){if(f(xs[i],i,xs))res.push(xs[i]);}return res;}// String.prototype.substr - negative index don't work in IE8
var substr='ab'.substr(-1)==='b'?function(str,start,len){return str.substr(start,len);}:function(str,start,len){if(start<0)start=str.length+start;return str.substr(start,len);};}).call(this,require('_process'));},{"_process":193}],169:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=void 0;var _container=_interopRequireDefault(require("./container"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}function _inheritsLoose(subClass,superClass){subClass.prototype=Object.create(superClass.prototype);subClass.prototype.constructor=subClass;subClass.__proto__=superClass;}/**
 * Represents an at-rule.
 *
 * If it’s followed in the CSS by a {} block, this node will have
 * a nodes property representing its children.
 *
 * @extends Container
 *
 * @example
 * const root = postcss.parse('@charset "UTF-8"; @media print {}')
 *
 * const charset = root.first
 * charset.type  //=> 'atrule'
 * charset.nodes //=> undefined
 *
 * const media = root.last
 * media.nodes   //=> []
 */var AtRule=/*#__PURE__*/function(_Container){_inheritsLoose(AtRule,_Container);function AtRule(defaults){var _this;_this=_Container.call(this,defaults)||this;_this.type='atrule';return _this;}var _proto=AtRule.prototype;_proto.append=function append(){var _Container$prototype$;if(!this.nodes)this.nodes=[];for(var _len=arguments.length,children=new Array(_len),_key=0;_key<_len;_key++){children[_key]=arguments[_key];}return(_Container$prototype$=_Container.prototype.append).call.apply(_Container$prototype$,[this].concat(children));};_proto.prepend=function prepend(){var _Container$prototype$2;if(!this.nodes)this.nodes=[];for(var _len2=arguments.length,children=new Array(_len2),_key2=0;_key2<_len2;_key2++){children[_key2]=arguments[_key2];}return(_Container$prototype$2=_Container.prototype.prepend).call.apply(_Container$prototype$2,[this].concat(children));}/**
   * @memberof AtRule#
   * @member {string} name The at-rule’s name immediately follows the `@`.
   *
   * @example
   * const root  = postcss.parse('@media print {}')
   * media.name //=> 'media'
   * const media = root.first
   */ /**
   * @memberof AtRule#
   * @member {string} params The at-rule’s parameters, the values
   *                         that follow the at-rule’s name but precede
   *                         any {} block.
   *
   * @example
   * const root  = postcss.parse('@media print, screen {}')
   * const media = root.first
   * media.params //=> 'print, screen'
   */ /**
   * @memberof AtRule#
   * @member {object} raws Information to generate byte-to-byte equal
   *                        node string as it was in the origin input.
   *
   * Every parser saves its own properties,
   * but the default CSS parser uses:
   *
   * * `before`: the space symbols before the node. It also stores `*`
   *   and `_` symbols before the declaration (IE hack).
   * * `after`: the space symbols after the last child of the node
   *   to the end of the node.
   * * `between`: the symbols between the property and value
   *   for declarations, selector and `{` for rules, or last parameter
   *   and `{` for at-rules.
   * * `semicolon`: contains true if the last child has
   *   an (optional) semicolon.
   * * `afterName`: the space between the at-rule name and its parameters.
   *
   * PostCSS cleans at-rule parameters from comments and extra spaces,
   * but it stores origin content in raws properties.
   * As such, if you don’t change a declaration’s value,
   * PostCSS will use the raw value with comments.
   *
   * @example
   * const root = postcss.parse('  @media\nprint {\n}')
   * root.first.first.raws //=> { before: '  ',
   *                       //     between: ' ',
   *                       //     afterName: '\n',
   *                       //     after: '\n' }
   */;return AtRule;}(_container["default"]);var _default=AtRule;exports["default"]=_default;module.exports=exports["default"];},{"./container":171}],170:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=void 0;var _node=_interopRequireDefault(require("./node"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}function _inheritsLoose(subClass,superClass){subClass.prototype=Object.create(superClass.prototype);subClass.prototype.constructor=subClass;subClass.__proto__=superClass;}/**
 * Represents a comment between declarations or statements (rule and at-rules).
 *
 * Comments inside selectors, at-rule parameters, or declaration values
 * will be stored in the `raws` properties explained above.
 *
 * @extends Node
 */var Comment=/*#__PURE__*/function(_Node){_inheritsLoose(Comment,_Node);function Comment(defaults){var _this;_this=_Node.call(this,defaults)||this;_this.type='comment';return _this;}/**
   * @memberof Comment#
   * @member {string} text The comment’s text.
   */ /**
   * @memberof Comment#
   * @member {object} raws Information to generate byte-to-byte equal
   *                       node string as it was in the origin input.
   *
   * Every parser saves its own properties,
   * but the default CSS parser uses:
   *
   * * `before`: the space symbols before the node.
   * * `left`: the space symbols between `/*` and the comment’s text.
   * * `right`: the space symbols between the comment’s text.
   */return Comment;}(_node["default"]);var _default=Comment;exports["default"]=_default;module.exports=exports["default"];},{"./node":178}],171:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=void 0;var _declaration=_interopRequireDefault(require("./declaration"));var _comment=_interopRequireDefault(require("./comment"));var _node=_interopRequireDefault(require("./node"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}function _createForOfIteratorHelperLoose(o,allowArrayLike){var it;if(typeof Symbol==="undefined"||o[Symbol.iterator]==null){if(Array.isArray(o)||(it=_unsupportedIterableToArray(o))||allowArrayLike&&o&&typeof o.length==="number"){if(it)o=it;var i=0;return function(){if(i>=o.length)return{done:true};return{done:false,value:o[i++]};};}throw new TypeError("Invalid attempt to iterate non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");}it=o[Symbol.iterator]();return it.next.bind(it);}function _unsupportedIterableToArray(o,minLen){if(!o)return;if(typeof o==="string")return _arrayLikeToArray(o,minLen);var n=Object.prototype.toString.call(o).slice(8,-1);if(n==="Object"&&o.constructor)n=o.constructor.name;if(n==="Map"||n==="Set")return Array.from(o);if(n==="Arguments"||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n))return _arrayLikeToArray(o,minLen);}function _arrayLikeToArray(arr,len){if(len==null||len>arr.length)len=arr.length;for(var i=0,arr2=new Array(len);i<len;i++){arr2[i]=arr[i];}return arr2;}function _defineProperties(target,props){for(var i=0;i<props.length;i++){var descriptor=props[i];descriptor.enumerable=descriptor.enumerable||false;descriptor.configurable=true;if("value"in descriptor)descriptor.writable=true;Object.defineProperty(target,descriptor.key,descriptor);}}function _createClass(Constructor,protoProps,staticProps){if(protoProps)_defineProperties(Constructor.prototype,protoProps);if(staticProps)_defineProperties(Constructor,staticProps);return Constructor;}function _inheritsLoose(subClass,superClass){subClass.prototype=Object.create(superClass.prototype);subClass.prototype.constructor=subClass;subClass.__proto__=superClass;}function cleanSource(nodes){return nodes.map(function(i){if(i.nodes)i.nodes=cleanSource(i.nodes);delete i.source;return i;});}/**
 * The {@link Root}, {@link AtRule}, and {@link Rule} container nodes
 * inherit some common methods to help work with their children.
 *
 * Note that all containers can store any content. If you write a rule inside
 * a rule, PostCSS will parse it.
 *
 * @extends Node
 * @abstract
 */var Container=/*#__PURE__*/function(_Node){_inheritsLoose(Container,_Node);function Container(){return _Node.apply(this,arguments)||this;}var _proto=Container.prototype;_proto.push=function push(child){child.parent=this;this.nodes.push(child);return this;}/**
   * Iterates through the container’s immediate children,
   * calling `callback` for each child.
   *
   * Returning `false` in the callback will break iteration.
   *
   * This method only iterates through the container’s immediate children.
   * If you need to recursively iterate through all the container’s descendant
   * nodes, use {@link Container#walk}.
   *
   * Unlike the for `{}`-cycle or `Array#forEach` this iterator is safe
   * if you are mutating the array of child nodes during iteration.
   * PostCSS will adjust the current index to match the mutations.
   *
   * @param {childIterator} callback Iterator receives each node and index.
   *
   * @return {false|undefined} Returns `false` if iteration was broke.
   *
   * @example
   * const root = postcss.parse('a { color: black; z-index: 1 }')
   * const rule = root.first
   *
   * for (const decl of rule.nodes) {
   *   decl.cloneBefore({ prop: '-webkit-' + decl.prop })
   *   // Cycle will be infinite, because cloneBefore moves the current node
   *   // to the next index
   * }
   *
   * rule.each(decl => {
   *   decl.cloneBefore({ prop: '-webkit-' + decl.prop })
   *   // Will be executed only for color and z-index
   * })
   */;_proto.each=function each(callback){if(!this.lastEach)this.lastEach=0;if(!this.indexes)this.indexes={};this.lastEach+=1;var id=this.lastEach;this.indexes[id]=0;if(!this.nodes)return undefined;var index,result;while(this.indexes[id]<this.nodes.length){index=this.indexes[id];result=callback(this.nodes[index],index);if(result===false)break;this.indexes[id]+=1;}delete this.indexes[id];return result;}/**
   * Traverses the container’s descendant nodes, calling callback
   * for each node.
   *
   * Like container.each(), this method is safe to use
   * if you are mutating arrays during iteration.
   *
   * If you only need to iterate through the container’s immediate children,
   * use {@link Container#each}.
   *
   * @param {childIterator} callback Iterator receives each node and index.
   *
   * @return {false|undefined} Returns `false` if iteration was broke.
   *
   * @example
   * root.walk(node => {
   *   // Traverses all descendant nodes.
   * })
   */;_proto.walk=function walk(callback){return this.each(function(child,i){var result;try{result=callback(child,i);}catch(e){e.postcssNode=child;if(e.stack&&child.source&&/\n\s{4}at /.test(e.stack)){var s=child.source;e.stack=e.stack.replace(/\n\s{4}at /,"$&"+s.input.from+":"+s.start.line+":"+s.start.column+"$&");}throw e;}if(result!==false&&child.walk){result=child.walk(callback);}return result;});}/**
   * Traverses the container’s descendant nodes, calling callback
   * for each declaration node.
   *
   * If you pass a filter, iteration will only happen over declarations
   * with matching properties.
   *
   * Like {@link Container#each}, this method is safe
   * to use if you are mutating arrays during iteration.
   *
   * @param {string|RegExp} [prop]   String or regular expression
   *                                 to filter declarations by property name.
   * @param {childIterator} callback Iterator receives each node and index.
   *
   * @return {false|undefined} Returns `false` if iteration was broke.
   *
   * @example
   * root.walkDecls(decl => {
   *   checkPropertySupport(decl.prop)
   * })
   *
   * root.walkDecls('border-radius', decl => {
   *   decl.remove()
   * })
   *
   * root.walkDecls(/^background/, decl => {
   *   decl.value = takeFirstColorFromGradient(decl.value)
   * })
   */;_proto.walkDecls=function walkDecls(prop,callback){if(!callback){callback=prop;return this.walk(function(child,i){if(child.type==='decl'){return callback(child,i);}});}if(prop instanceof RegExp){return this.walk(function(child,i){if(child.type==='decl'&&prop.test(child.prop)){return callback(child,i);}});}return this.walk(function(child,i){if(child.type==='decl'&&child.prop===prop){return callback(child,i);}});}/**
   * Traverses the container’s descendant nodes, calling callback
   * for each rule node.
   *
   * If you pass a filter, iteration will only happen over rules
   * with matching selectors.
   *
   * Like {@link Container#each}, this method is safe
   * to use if you are mutating arrays during iteration.
   *
   * @param {string|RegExp} [selector] String or regular expression
   *                                   to filter rules by selector.
   * @param {childIterator} callback   Iterator receives each node and index.
   *
   * @return {false|undefined} returns `false` if iteration was broke.
   *
   * @example
   * const selectors = []
   * root.walkRules(rule => {
   *   selectors.push(rule.selector)
   * })
   * console.log(`Your CSS uses ${ selectors.length } selectors`)
   */;_proto.walkRules=function walkRules(selector,callback){if(!callback){callback=selector;return this.walk(function(child,i){if(child.type==='rule'){return callback(child,i);}});}if(selector instanceof RegExp){return this.walk(function(child,i){if(child.type==='rule'&&selector.test(child.selector)){return callback(child,i);}});}return this.walk(function(child,i){if(child.type==='rule'&&child.selector===selector){return callback(child,i);}});}/**
   * Traverses the container’s descendant nodes, calling callback
   * for each at-rule node.
   *
   * If you pass a filter, iteration will only happen over at-rules
   * that have matching names.
   *
   * Like {@link Container#each}, this method is safe
   * to use if you are mutating arrays during iteration.
   *
   * @param {string|RegExp} [name]   String or regular expression
   *                                 to filter at-rules by name.
   * @param {childIterator} callback Iterator receives each node and index.
   *
   * @return {false|undefined} Returns `false` if iteration was broke.
   *
   * @example
   * root.walkAtRules(rule => {
   *   if (isOld(rule.name)) rule.remove()
   * })
   *
   * let first = false
   * root.walkAtRules('charset', rule => {
   *   if (!first) {
   *     first = true
   *   } else {
   *     rule.remove()
   *   }
   * })
   */;_proto.walkAtRules=function walkAtRules(name,callback){if(!callback){callback=name;return this.walk(function(child,i){if(child.type==='atrule'){return callback(child,i);}});}if(name instanceof RegExp){return this.walk(function(child,i){if(child.type==='atrule'&&name.test(child.name)){return callback(child,i);}});}return this.walk(function(child,i){if(child.type==='atrule'&&child.name===name){return callback(child,i);}});}/**
   * Traverses the container’s descendant nodes, calling callback
   * for each comment node.
   *
   * Like {@link Container#each}, this method is safe
   * to use if you are mutating arrays during iteration.
   *
   * @param {childIterator} callback Iterator receives each node and index.
   *
   * @return {false|undefined} Returns `false` if iteration was broke.
   *
   * @example
   * root.walkComments(comment => {
   *   comment.remove()
   * })
   */;_proto.walkComments=function walkComments(callback){return this.walk(function(child,i){if(child.type==='comment'){return callback(child,i);}});}/**
   * Inserts new nodes to the end of the container.
   *
   * @param {...(Node|object|string|Node[])} children New nodes.
   *
   * @return {Node} This node for methods chain.
   *
   * @example
   * const decl1 = postcss.decl({ prop: 'color', value: 'black' })
   * const decl2 = postcss.decl({ prop: 'background-color', value: 'white' })
   * rule.append(decl1, decl2)
   *
   * root.append({ name: 'charset', params: '"UTF-8"' })  // at-rule
   * root.append({ selector: 'a' })                       // rule
   * rule.append({ prop: 'color', value: 'black' })       // declaration
   * rule.append({ text: 'Comment' })                     // comment
   *
   * root.append('a {}')
   * root.first.append('color: black; z-index: 1')
   */;_proto.append=function append(){for(var _len=arguments.length,children=new Array(_len),_key=0;_key<_len;_key++){children[_key]=arguments[_key];}for(var _i=0,_children=children;_i<_children.length;_i++){var child=_children[_i];var nodes=this.normalize(child,this.last);for(var _iterator=_createForOfIteratorHelperLoose(nodes),_step;!(_step=_iterator()).done;){var node=_step.value;this.nodes.push(node);}}return this;}/**
   * Inserts new nodes to the start of the container.
   *
   * @param {...(Node|object|string|Node[])} children New nodes.
   *
   * @return {Node} This node for methods chain.
   *
   * @example
   * const decl1 = postcss.decl({ prop: 'color', value: 'black' })
   * const decl2 = postcss.decl({ prop: 'background-color', value: 'white' })
   * rule.prepend(decl1, decl2)
   *
   * root.append({ name: 'charset', params: '"UTF-8"' })  // at-rule
   * root.append({ selector: 'a' })                       // rule
   * rule.append({ prop: 'color', value: 'black' })       // declaration
   * rule.append({ text: 'Comment' })                     // comment
   *
   * root.append('a {}')
   * root.first.append('color: black; z-index: 1')
   */;_proto.prepend=function prepend(){for(var _len2=arguments.length,children=new Array(_len2),_key2=0;_key2<_len2;_key2++){children[_key2]=arguments[_key2];}children=children.reverse();for(var _iterator2=_createForOfIteratorHelperLoose(children),_step2;!(_step2=_iterator2()).done;){var child=_step2.value;var nodes=this.normalize(child,this.first,'prepend').reverse();for(var _iterator3=_createForOfIteratorHelperLoose(nodes),_step3;!(_step3=_iterator3()).done;){var node=_step3.value;this.nodes.unshift(node);}for(var id in this.indexes){this.indexes[id]=this.indexes[id]+nodes.length;}}return this;};_proto.cleanRaws=function cleanRaws(keepBetween){_Node.prototype.cleanRaws.call(this,keepBetween);if(this.nodes){for(var _iterator4=_createForOfIteratorHelperLoose(this.nodes),_step4;!(_step4=_iterator4()).done;){var node=_step4.value;node.cleanRaws(keepBetween);}}}/**
   * Insert new node before old node within the container.
   *
   * @param {Node|number} exist             Child or child’s index.
   * @param {Node|object|string|Node[]} add New node.
   *
   * @return {Node} This node for methods chain.
   *
   * @example
   * rule.insertBefore(decl, decl.clone({ prop: '-webkit-' + decl.prop }))
   */;_proto.insertBefore=function insertBefore(exist,add){exist=this.index(exist);var type=exist===0?'prepend':false;var nodes=this.normalize(add,this.nodes[exist],type).reverse();for(var _iterator5=_createForOfIteratorHelperLoose(nodes),_step5;!(_step5=_iterator5()).done;){var node=_step5.value;this.nodes.splice(exist,0,node);}var index;for(var id in this.indexes){index=this.indexes[id];if(exist<=index){this.indexes[id]=index+nodes.length;}}return this;}/**
   * Insert new node after old node within the container.
   *
   * @param {Node|number} exist             Child or child’s index.
   * @param {Node|object|string|Node[]} add New node.
   *
   * @return {Node} This node for methods chain.
   */;_proto.insertAfter=function insertAfter(exist,add){exist=this.index(exist);var nodes=this.normalize(add,this.nodes[exist]).reverse();for(var _iterator6=_createForOfIteratorHelperLoose(nodes),_step6;!(_step6=_iterator6()).done;){var node=_step6.value;this.nodes.splice(exist+1,0,node);}var index;for(var id in this.indexes){index=this.indexes[id];if(exist<index){this.indexes[id]=index+nodes.length;}}return this;}/**
   * Removes node from the container and cleans the parent properties
   * from the node and its children.
   *
   * @param {Node|number} child Child or child’s index.
   *
   * @return {Node} This node for methods chain
   *
   * @example
   * rule.nodes.length  //=> 5
   * rule.removeChild(decl)
   * rule.nodes.length  //=> 4
   * decl.parent        //=> undefined
   */;_proto.removeChild=function removeChild(child){child=this.index(child);this.nodes[child].parent=undefined;this.nodes.splice(child,1);var index;for(var id in this.indexes){index=this.indexes[id];if(index>=child){this.indexes[id]=index-1;}}return this;}/**
   * Removes all children from the container
   * and cleans their parent properties.
   *
   * @return {Node} This node for methods chain.
   *
   * @example
   * rule.removeAll()
   * rule.nodes.length //=> 0
   */;_proto.removeAll=function removeAll(){for(var _iterator7=_createForOfIteratorHelperLoose(this.nodes),_step7;!(_step7=_iterator7()).done;){var node=_step7.value;node.parent=undefined;}this.nodes=[];return this;}/**
   * Passes all declaration values within the container that match pattern
   * through callback, replacing those values with the returned result
   * of callback.
   *
   * This method is useful if you are using a custom unit or function
   * and need to iterate through all values.
   *
   * @param {string|RegExp} pattern      Replace pattern.
   * @param {object} opts                Options to speed up the search.
   * @param {string|string[]} opts.props An array of property names.
   * @param {string} opts.fast           String that’s used to narrow down
   *                                     values and speed up the regexp search.
   * @param {function|string} callback   String to replace pattern or callback
   *                                     that returns a new value. The callback
   *                                     will receive the same arguments
   *                                     as those passed to a function parameter
   *                                     of `String#replace`.
   *
   * @return {Node} This node for methods chain.
   *
   * @example
   * root.replaceValues(/\d+rem/, { fast: 'rem' }, string => {
   *   return 15 * parseInt(string) + 'px'
   * })
   */;_proto.replaceValues=function replaceValues(pattern,opts,callback){if(!callback){callback=opts;opts={};}this.walkDecls(function(decl){if(opts.props&&opts.props.indexOf(decl.prop)===-1)return;if(opts.fast&&decl.value.indexOf(opts.fast)===-1)return;decl.value=decl.value.replace(pattern,callback);});return this;}/**
   * Returns `true` if callback returns `true`
   * for all of the container’s children.
   *
   * @param {childCondition} condition Iterator returns true or false.
   *
   * @return {boolean} Is every child pass condition.
   *
   * @example
   * const noPrefixes = rule.every(i => i.prop[0] !== '-')
   */;_proto.every=function every(condition){return this.nodes.every(condition);}/**
   * Returns `true` if callback returns `true` for (at least) one
   * of the container’s children.
   *
   * @param {childCondition} condition Iterator returns true or false.
   *
   * @return {boolean} Is some child pass condition.
   *
   * @example
   * const hasPrefix = rule.some(i => i.prop[0] === '-')
   */;_proto.some=function some(condition){return this.nodes.some(condition);}/**
   * Returns a `child`’s index within the {@link Container#nodes} array.
   *
   * @param {Node} child Child of the current container.
   *
   * @return {number} Child index.
   *
   * @example
   * rule.index( rule.nodes[2] ) //=> 2
   */;_proto.index=function index(child){if(typeof child==='number'){return child;}return this.nodes.indexOf(child);}/**
   * The container’s first child.
   *
   * @type {Node}
   *
   * @example
   * rule.first === rules.nodes[0]
   */;_proto.normalize=function normalize(nodes,sample){var _this=this;if(typeof nodes==='string'){var parse=require('./parse');nodes=cleanSource(parse(nodes).nodes);}else if(Array.isArray(nodes)){nodes=nodes.slice(0);for(var _iterator8=_createForOfIteratorHelperLoose(nodes),_step8;!(_step8=_iterator8()).done;){var i=_step8.value;if(i.parent)i.parent.removeChild(i,'ignore');}}else if(nodes.type==='root'){nodes=nodes.nodes.slice(0);for(var _iterator9=_createForOfIteratorHelperLoose(nodes),_step9;!(_step9=_iterator9()).done;){var _i2=_step9.value;if(_i2.parent)_i2.parent.removeChild(_i2,'ignore');}}else if(nodes.type){nodes=[nodes];}else if(nodes.prop){if(typeof nodes.value==='undefined'){throw new Error('Value field is missed in node creation');}else if(typeof nodes.value!=='string'){nodes.value=String(nodes.value);}nodes=[new _declaration["default"](nodes)];}else if(nodes.selector){var Rule=require('./rule');nodes=[new Rule(nodes)];}else if(nodes.name){var AtRule=require('./at-rule');nodes=[new AtRule(nodes)];}else if(nodes.text){nodes=[new _comment["default"](nodes)];}else{throw new Error('Unknown node type in node creation');}var processed=nodes.map(function(i){if(i.parent)i.parent.removeChild(i);if(typeof i.raws.before==='undefined'){if(sample&&typeof sample.raws.before!=='undefined'){i.raws.before=sample.raws.before.replace(/[^\s]/g,'');}}i.parent=_this;return i;});return processed;}/**
   * @memberof Container#
   * @member {Node[]} nodes An array containing the container’s children.
   *
   * @example
   * const root = postcss.parse('a { color: black }')
   * root.nodes.length           //=> 1
   * root.nodes[0].selector      //=> 'a'
   * root.nodes[0].nodes[0].prop //=> 'color'
   */;_createClass(Container,[{key:"first",get:function get(){if(!this.nodes)return undefined;return this.nodes[0];}/**
     * The container’s last child.
     *
     * @type {Node}
     *
     * @example
     * rule.last === rule.nodes[rule.nodes.length - 1]
     */},{key:"last",get:function get(){if(!this.nodes)return undefined;return this.nodes[this.nodes.length-1];}}]);return Container;}(_node["default"]);var _default=Container;/**
 * @callback childCondition
 * @param {Node} node    Container child.
 * @param {number} index Child index.
 * @param {Node[]} nodes All container children.
 * @return {boolean}
 */ /**
 * @callback childIterator
 * @param {Node} node    Container child.
 * @param {number} index Child index.
 * @return {false|undefined} Returning `false` will break iteration.
 */exports["default"]=_default;module.exports=exports["default"];},{"./at-rule":169,"./comment":170,"./declaration":173,"./node":178,"./parse":179,"./rule":186}],172:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=void 0;var _supportsColor=_interopRequireDefault(require("supports-color"));var _chalk=_interopRequireDefault(require("chalk"));var _terminalHighlight=_interopRequireDefault(require("./terminal-highlight"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}function _assertThisInitialized(self){if(self===void 0){throw new ReferenceError("this hasn't been initialised - super() hasn't been called");}return self;}function _inheritsLoose(subClass,superClass){subClass.prototype=Object.create(superClass.prototype);subClass.prototype.constructor=subClass;subClass.__proto__=superClass;}function _wrapNativeSuper(Class){var _cache=typeof Map==="function"?new Map():undefined;_wrapNativeSuper=function _wrapNativeSuper(Class){if(Class===null||!_isNativeFunction(Class))return Class;if(typeof Class!=="function"){throw new TypeError("Super expression must either be null or a function");}if(typeof _cache!=="undefined"){if(_cache.has(Class))return _cache.get(Class);_cache.set(Class,Wrapper);}function Wrapper(){return _construct(Class,arguments,_getPrototypeOf(this).constructor);}Wrapper.prototype=Object.create(Class.prototype,{constructor:{value:Wrapper,enumerable:false,writable:true,configurable:true}});return _setPrototypeOf(Wrapper,Class);};return _wrapNativeSuper(Class);}function _construct(Parent,args,Class){if(_isNativeReflectConstruct()){_construct=Reflect.construct;}else{_construct=function _construct(Parent,args,Class){var a=[null];a.push.apply(a,args);var Constructor=Function.bind.apply(Parent,a);var instance=new Constructor();if(Class)_setPrototypeOf(instance,Class.prototype);return instance;};}return _construct.apply(null,arguments);}function _isNativeReflectConstruct(){if(typeof Reflect==="undefined"||!Reflect.construct)return false;if(Reflect.construct.sham)return false;if(typeof Proxy==="function")return true;try{Date.prototype.toString.call(Reflect.construct(Date,[],function(){}));return true;}catch(e){return false;}}function _isNativeFunction(fn){return Function.toString.call(fn).indexOf("[native code]")!==-1;}function _setPrototypeOf(o,p){_setPrototypeOf=Object.setPrototypeOf||function _setPrototypeOf(o,p){o.__proto__=p;return o;};return _setPrototypeOf(o,p);}function _getPrototypeOf(o){_getPrototypeOf=Object.setPrototypeOf?Object.getPrototypeOf:function _getPrototypeOf(o){return o.__proto__||Object.getPrototypeOf(o);};return _getPrototypeOf(o);}/**
 * The CSS parser throws this error for broken CSS.
 *
 * Custom parsers can throw this error for broken custom syntax using
 * the {@link Node#error} method.
 *
 * PostCSS will use the input source map to detect the original error location.
 * If you wrote a Sass file, compiled it to CSS and then parsed it with PostCSS,
 * PostCSS will show the original position in the Sass file.
 *
 * If you need the position in the PostCSS input
 * (e.g., to debug the previous compiler), use `error.input.file`.
 *
 * @example
 * // Catching and checking syntax error
 * try {
 *   postcss.parse('a{')
 * } catch (error) {
 *   if (error.name === 'CssSyntaxError') {
 *     error //=> CssSyntaxError
 *   }
 * }
 *
 * @example
 * // Raising error from plugin
 * throw node.error('Unknown variable', { plugin: 'postcss-vars' })
 */var CssSyntaxError=/*#__PURE__*/function(_Error){_inheritsLoose(CssSyntaxError,_Error);/**
   * @param {string} message  Error message.
   * @param {number} [line]   Source line of the error.
   * @param {number} [column] Source column of the error.
   * @param {string} [source] Source code of the broken file.
   * @param {string} [file]   Absolute path to the broken file.
   * @param {string} [plugin] PostCSS plugin name, if error came from plugin.
   */function CssSyntaxError(message,line,column,source,file,plugin){var _this;_this=_Error.call(this,message)||this;/**
     * Always equal to `'CssSyntaxError'`. You should always check error type
     * by `error.name === 'CssSyntaxError'`
     * instead of `error instanceof CssSyntaxError`,
     * because npm could have several PostCSS versions.
     *
     * @type {string}
     *
     * @example
     * if (error.name === 'CssSyntaxError') {
     *   error //=> CssSyntaxError
     * }
     */_this.name='CssSyntaxError';/**
     * Error message.
     *
     * @type {string}
     *
     * @example
     * error.message //=> 'Unclosed block'
     */_this.reason=message;if(file){/**
       * Absolute path to the broken file.
       *
       * @type {string}
       *
       * @example
       * error.file       //=> 'a.sass'
       * error.input.file //=> 'a.css'
       */_this.file=file;}if(source){/**
       * Source code of the broken file.
       *
       * @type {string}
       *
       * @example
       * error.source       //=> 'a { b {} }'
       * error.input.column //=> 'a b { }'
       */_this.source=source;}if(plugin){/**
       * Plugin name, if error came from plugin.
       *
       * @type {string}
       *
       * @example
       * error.plugin //=> 'postcss-vars'
       */_this.plugin=plugin;}if(typeof line!=='undefined'&&typeof column!=='undefined'){/**
       * Source line of the error.
       *
       * @type {number}
       *
       * @example
       * error.line       //=> 2
       * error.input.line //=> 4
       */_this.line=line;/**
       * Source column of the error.
       *
       * @type {number}
       *
       * @example
       * error.column       //=> 1
       * error.input.column //=> 4
       */_this.column=column;}_this.setMessage();if(Error.captureStackTrace){Error.captureStackTrace(_assertThisInitialized(_this),CssSyntaxError);}return _this;}var _proto=CssSyntaxError.prototype;_proto.setMessage=function setMessage(){/**
     * Full error text in the GNU error format
     * with plugin, file, line and column.
     *
     * @type {string}
     *
     * @example
     * error.message //=> 'a.css:1:1: Unclosed block'
     */this.message=this.plugin?this.plugin+': ':'';this.message+=this.file?this.file:'<css input>';if(typeof this.line!=='undefined'){this.message+=':'+this.line+':'+this.column;}this.message+=': '+this.reason;}/**
   * Returns a few lines of CSS source that caused the error.
   *
   * If the CSS has an input source map without `sourceContent`,
   * this method will return an empty string.
   *
   * @param {boolean} [color] Whether arrow will be colored red by terminal
   *                          color codes. By default, PostCSS will detect
   *                          color support by `process.stdout.isTTY`
   *                          and `process.env.NODE_DISABLE_COLORS`.
   *
   * @example
   * error.showSourceCode() //=> "  4 | }
   *                        //      5 | a {
   *                        //    > 6 |   bad
   *                        //        |   ^
   *                        //      7 | }
   *                        //      8 | b {"
   *
   * @return {string} Few lines of CSS source that caused the error.
   */;_proto.showSourceCode=function showSourceCode(color){var _this2=this;if(!this.source)return'';var css=this.source;if(_terminalHighlight["default"]){if(typeof color==='undefined')color=_supportsColor["default"].stdout;if(color)css=(0,_terminalHighlight["default"])(css);}var lines=css.split(/\r?\n/);var start=Math.max(this.line-3,0);var end=Math.min(this.line+2,lines.length);var maxWidth=String(end).length;function mark(text){if(color&&_chalk["default"].red){return _chalk["default"].red.bold(text);}return text;}function aside(text){if(color&&_chalk["default"].gray){return _chalk["default"].gray(text);}return text;}return lines.slice(start,end).map(function(line,index){var number=start+1+index;var gutter=' '+(' '+number).slice(-maxWidth)+' | ';if(number===_this2.line){var spacing=aside(gutter.replace(/\d/g,' '))+line.slice(0,_this2.column-1).replace(/[^\t]/g,' ');return mark('>')+aside(gutter)+line+'\n '+spacing+mark('^');}return' '+aside(gutter)+line;}).join('\n');}/**
   * Returns error position, message and source code of the broken part.
   *
   * @example
   * error.toString() //=> "CssSyntaxError: app.css:1:1: Unclosed block
   *                  //    > 1 | a {
   *                  //        | ^"
   *
   * @return {string} Error position, message and source code.
   */;_proto.toString=function toString(){var code=this.showSourceCode();if(code){code='\n\n'+code+'\n';}return this.name+': '+this.message+code;}/**
   * @memberof CssSyntaxError#
   * @member {Input} input Input object with PostCSS internal information
   *                       about input file. If input has source map
   *                       from previous tool, PostCSS will use origin
   *                       (for example, Sass) source. You can use this
   *                       object to get PostCSS input source.
   *
   * @example
   * error.input.file //=> 'a.css'
   * error.file       //=> 'a.sass'
   */;return CssSyntaxError;}(/*#__PURE__*/_wrapNativeSuper(Error));var _default=CssSyntaxError;exports["default"]=_default;module.exports=exports["default"];},{"./terminal-highlight":2,"chalk":2,"supports-color":2}],173:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=void 0;var _node=_interopRequireDefault(require("./node"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}function _inheritsLoose(subClass,superClass){subClass.prototype=Object.create(superClass.prototype);subClass.prototype.constructor=subClass;subClass.__proto__=superClass;}/**
 * Represents a CSS declaration.
 *
 * @extends Node
 *
 * @example
 * const root = postcss.parse('a { color: black }')
 * const decl = root.first.first
 * decl.type       //=> 'decl'
 * decl.toString() //=> ' color: black'
 */var Declaration=/*#__PURE__*/function(_Node){_inheritsLoose(Declaration,_Node);function Declaration(defaults){var _this;_this=_Node.call(this,defaults)||this;_this.type='decl';return _this;}/**
   * @memberof Declaration#
   * @member {string} prop The declaration’s property name.
   *
   * @example
   * const root = postcss.parse('a { color: black }')
   * const decl = root.first.first
   * decl.prop //=> 'color'
   */ /**
   * @memberof Declaration#
   * @member {string} value The declaration’s value.
   *
   * @example
   * const root = postcss.parse('a { color: black }')
   * const decl = root.first.first
   * decl.value //=> 'black'
   */ /**
   * @memberof Declaration#
   * @member {boolean} important `true` if the declaration
   *                             has an !important annotation.
   *
   * @example
   * const root = postcss.parse('a { color: black !important; color: red }')
   * root.first.first.important //=> true
   * root.first.last.important  //=> undefined
   */ /**
   * @memberof Declaration#
   * @member {object} raws Information to generate byte-to-byte equal
   *                       node string as it was in the origin input.
   *
   * Every parser saves its own properties,
   * but the default CSS parser uses:
   *
   * * `before`: the space symbols before the node. It also stores `*`
   *   and `_` symbols before the declaration (IE hack).
   * * `between`: the symbols between the property and value
   *   for declarations.
   * * `important`: the content of the important statement,
   *   if it is not just `!important`.
   *
   * PostCSS cleans declaration from comments and extra spaces,
   * but it stores origin content in raws properties.
   * As such, if you don’t change a declaration’s value,
   * PostCSS will use the raw value with comments.
   *
   * @example
   * const root = postcss.parse('a {\n  color:black\n}')
   * root.first.first.raws //=> { before: '\n  ', between: ':' }
   */return Declaration;}(_node["default"]);var _default=Declaration;exports["default"]=_default;module.exports=exports["default"];},{"./node":178}],174:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=void 0;var _path=_interopRequireDefault(require("path"));var _cssSyntaxError=_interopRequireDefault(require("./css-syntax-error"));var _previousMap=_interopRequireDefault(require("./previous-map"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}function _defineProperties(target,props){for(var i=0;i<props.length;i++){var descriptor=props[i];descriptor.enumerable=descriptor.enumerable||false;descriptor.configurable=true;if("value"in descriptor)descriptor.writable=true;Object.defineProperty(target,descriptor.key,descriptor);}}function _createClass(Constructor,protoProps,staticProps){if(protoProps)_defineProperties(Constructor.prototype,protoProps);if(staticProps)_defineProperties(Constructor,staticProps);return Constructor;}var sequence=0;/**
 * Represents the source CSS.
 *
 * @example
 * const root  = postcss.parse(css, { from: file })
 * const input = root.source.input
 */var Input=/*#__PURE__*/function(){/**
   * @param {string} css    Input CSS source.
   * @param {object} [opts] {@link Processor#process} options.
   */function Input(css,opts){if(opts===void 0){opts={};}if(css===null||typeof css==='undefined'||_typeof(css)==='object'&&!css.toString){throw new Error("PostCSS received "+css+" instead of CSS string");}/**
     * Input CSS source
     *
     * @type {string}
     *
     * @example
     * const input = postcss.parse('a{}', { from: file }).input
     * input.css //=> "a{}"
     */this.css=css.toString();if(this.css[0]==="\uFEFF"||this.css[0]==="\uFFFE"){this.hasBOM=true;this.css=this.css.slice(1);}else{this.hasBOM=false;}if(opts.from){if(/^\w+:\/\//.test(opts.from)||_path["default"].isAbsolute(opts.from)){/**
         * The absolute path to the CSS source file defined
         * with the `from` option.
         *
         * @type {string}
         *
         * @example
         * const root = postcss.parse(css, { from: 'a.css' })
         * root.source.input.file //=> '/home/ai/a.css'
         */this.file=opts.from;}else{this.file=_path["default"].resolve(opts.from);}}var map=new _previousMap["default"](this.css,opts);if(map.text){/**
       * The input source map passed from a compilation step before PostCSS
       * (for example, from Sass compiler).
       *
       * @type {PreviousMap}
       *
       * @example
       * root.source.input.map.consumer().sources //=> ['a.sass']
       */this.map=map;var file=map.consumer().file;if(!this.file&&file)this.file=this.mapResolve(file);}if(!this.file){sequence+=1;/**
       * The unique ID of the CSS source. It will be created if `from` option
       * is not provided (because PostCSS does not know the file path).
       *
       * @type {string}
       *
       * @example
       * const root = postcss.parse(css)
       * root.source.input.file //=> undefined
       * root.source.input.id   //=> "<input css 1>"
       */this.id='<input css '+sequence+'>';}if(this.map)this.map.file=this.from;}var _proto=Input.prototype;_proto.error=function error(message,line,column,opts){if(opts===void 0){opts={};}var result;var origin=this.origin(line,column);if(origin){result=new _cssSyntaxError["default"](message,origin.line,origin.column,origin.source,origin.file,opts.plugin);}else{result=new _cssSyntaxError["default"](message,line,column,this.css,this.file,opts.plugin);}result.input={line:line,column:column,source:this.css};if(this.file)result.input.file=this.file;return result;}/**
   * Reads the input source map and returns a symbol position
   * in the input source (e.g., in a Sass file that was compiled
   * to CSS before being passed to PostCSS).
   *
   * @param {number} line   Line in input CSS.
   * @param {number} column Column in input CSS.
   *
   * @return {filePosition} Position in input source.
   *
   * @example
   * root.source.input.origin(1, 1) //=> { file: 'a.css', line: 3, column: 1 }
   */;_proto.origin=function origin(line,column){if(!this.map)return false;var consumer=this.map.consumer();var from=consumer.originalPositionFor({line:line,column:column});if(!from.source)return false;var result={file:this.mapResolve(from.source),line:from.line,column:from.column};var source=consumer.sourceContentFor(from.source);if(source)result.source=source;return result;};_proto.mapResolve=function mapResolve(file){if(/^\w+:\/\//.test(file)){return file;}return _path["default"].resolve(this.map.consumer().sourceRoot||'.',file);}/**
   * The CSS source identifier. Contains {@link Input#file} if the user
   * set the `from` option, or {@link Input#id} if they did not.
   *
   * @type {string}
   *
   * @example
   * const root = postcss.parse(css, { from: 'a.css' })
   * root.source.input.from //=> "/home/ai/a.css"
   *
   * const root = postcss.parse(css)
   * root.source.input.from //=> "<input css 1>"
   */;_createClass(Input,[{key:"from",get:function get(){return this.file||this.id;}}]);return Input;}();var _default=Input;/**
 * @typedef  {object} filePosition
 * @property {string} file   Path to file.
 * @property {number} line   Source line in file.
 * @property {number} column Source column in file.
 */exports["default"]=_default;module.exports=exports["default"];},{"./css-syntax-error":172,"./previous-map":182,"path":168}],175:[function(require,module,exports){(function(process){"use strict";exports.__esModule=true;exports["default"]=void 0;var _mapGenerator=_interopRequireDefault(require("./map-generator"));var _stringify2=_interopRequireDefault(require("./stringify"));var _warnOnce=_interopRequireDefault(require("./warn-once"));var _result=_interopRequireDefault(require("./result"));var _parse=_interopRequireDefault(require("./parse"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}function _createForOfIteratorHelperLoose(o,allowArrayLike){var it;if(typeof Symbol==="undefined"||o[Symbol.iterator]==null){if(Array.isArray(o)||(it=_unsupportedIterableToArray(o))||allowArrayLike&&o&&typeof o.length==="number"){if(it)o=it;var i=0;return function(){if(i>=o.length)return{done:true};return{done:false,value:o[i++]};};}throw new TypeError("Invalid attempt to iterate non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");}it=o[Symbol.iterator]();return it.next.bind(it);}function _unsupportedIterableToArray(o,minLen){if(!o)return;if(typeof o==="string")return _arrayLikeToArray(o,minLen);var n=Object.prototype.toString.call(o).slice(8,-1);if(n==="Object"&&o.constructor)n=o.constructor.name;if(n==="Map"||n==="Set")return Array.from(o);if(n==="Arguments"||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n))return _arrayLikeToArray(o,minLen);}function _arrayLikeToArray(arr,len){if(len==null||len>arr.length)len=arr.length;for(var i=0,arr2=new Array(len);i<len;i++){arr2[i]=arr[i];}return arr2;}function _defineProperties(target,props){for(var i=0;i<props.length;i++){var descriptor=props[i];descriptor.enumerable=descriptor.enumerable||false;descriptor.configurable=true;if("value"in descriptor)descriptor.writable=true;Object.defineProperty(target,descriptor.key,descriptor);}}function _createClass(Constructor,protoProps,staticProps){if(protoProps)_defineProperties(Constructor.prototype,protoProps);if(staticProps)_defineProperties(Constructor,staticProps);return Constructor;}function isPromise(obj){return _typeof(obj)==='object'&&typeof obj.then==='function';}/**
 * A Promise proxy for the result of PostCSS transformations.
 *
 * A `LazyResult` instance is returned by {@link Processor#process}.
 *
 * @example
 * const lazy = postcss([autoprefixer]).process(css)
 */var LazyResult=/*#__PURE__*/function(){function LazyResult(processor,css,opts){this.stringified=false;this.processed=false;var root;if(_typeof(css)==='object'&&css!==null&&css.type==='root'){root=css;}else if(css instanceof LazyResult||css instanceof _result["default"]){root=css.root;if(css.map){if(typeof opts.map==='undefined')opts.map={};if(!opts.map.inline)opts.map.inline=false;opts.map.prev=css.map;}}else{var parser=_parse["default"];if(opts.syntax)parser=opts.syntax.parse;if(opts.parser)parser=opts.parser;if(parser.parse)parser=parser.parse;try{root=parser(css,opts);}catch(error){this.error=error;}}this.result=new _result["default"](processor,root,opts);}/**
   * Returns a {@link Processor} instance, which will be used
   * for CSS transformations.
   *
   * @type {Processor}
   */var _proto=LazyResult.prototype;/**
   * Processes input CSS through synchronous plugins
   * and calls {@link Result#warnings()}.
   *
   * @return {Warning[]} Warnings from plugins.
   */_proto.warnings=function warnings(){return this.sync().warnings();}/**
   * Alias for the {@link LazyResult#css} property.
   *
   * @example
   * lazy + '' === lazy.css
   *
   * @return {string} Output CSS.
   */;_proto.toString=function toString(){return this.css;}/**
   * Processes input CSS through synchronous and asynchronous plugins
   * and calls `onFulfilled` with a Result instance. If a plugin throws
   * an error, the `onRejected` callback will be executed.
   *
   * It implements standard Promise API.
   *
   * @param {onFulfilled} onFulfilled Callback will be executed
   *                                  when all plugins will finish work.
   * @param {onRejected}  onRejected  Callback will be executed on any error.
   *
   * @return {Promise} Promise API to make queue.
   *
   * @example
   * postcss([autoprefixer]).process(css, { from: cssPath }).then(result => {
   *   console.log(result.css)
   * })
   */;_proto.then=function then(onFulfilled,onRejected){if(process.env.NODE_ENV!=='production'){if(!('from'in this.opts)){(0,_warnOnce["default"])('Without `from` option PostCSS could generate wrong source map '+'and will not find Browserslist config. Set it to CSS file path '+'or to `undefined` to prevent this warning.');}}return this.async().then(onFulfilled,onRejected);}/**
   * Processes input CSS through synchronous and asynchronous plugins
   * and calls onRejected for each error thrown in any plugin.
   *
   * It implements standard Promise API.
   *
   * @param {onRejected} onRejected Callback will be executed on any error.
   *
   * @return {Promise} Promise API to make queue.
   *
   * @example
   * postcss([autoprefixer]).process(css).then(result => {
   *   console.log(result.css)
   * }).catch(error => {
   *   console.error(error)
   * })
   */;_proto["catch"]=function _catch(onRejected){return this.async()["catch"](onRejected);}/**
   * Processes input CSS through synchronous and asynchronous plugins
   * and calls onFinally on any error or when all plugins will finish work.
   *
   * It implements standard Promise API.
   *
   * @param {onFinally} onFinally Callback will be executed on any error or
   *                              when all plugins will finish work.
   *
   * @return {Promise} Promise API to make queue.
   *
   * @example
   * postcss([autoprefixer]).process(css).finally(() => {
   *   console.log('processing ended')
   * })
   */;_proto["finally"]=function _finally(onFinally){return this.async().then(onFinally,onFinally);};_proto.handleError=function handleError(error,plugin){try{this.error=error;if(error.name==='CssSyntaxError'&&!error.plugin){error.plugin=plugin.postcssPlugin;error.setMessage();}else if(plugin.postcssVersion){if(process.env.NODE_ENV!=='production'){var pluginName=plugin.postcssPlugin;var pluginVer=plugin.postcssVersion;var runtimeVer=this.result.processor.version;var a=pluginVer.split('.');var b=runtimeVer.split('.');if(a[0]!==b[0]||parseInt(a[1])>parseInt(b[1])){console.error('Unknown error from PostCSS plugin. Your current PostCSS '+'version is '+runtimeVer+', but '+pluginName+' uses '+pluginVer+'. Perhaps this is the source of the error below.');}}}}catch(err){if(console&&console.error)console.error(err);}};_proto.asyncTick=function asyncTick(resolve,reject){var _this=this;if(this.plugin>=this.processor.plugins.length){this.processed=true;return resolve();}try{var plugin=this.processor.plugins[this.plugin];var promise=this.run(plugin);this.plugin+=1;if(isPromise(promise)){promise.then(function(){_this.asyncTick(resolve,reject);})["catch"](function(error){_this.handleError(error,plugin);_this.processed=true;reject(error);});}else{this.asyncTick(resolve,reject);}}catch(error){this.processed=true;reject(error);}};_proto.async=function async(){var _this2=this;if(this.processed){return new Promise(function(resolve,reject){if(_this2.error){reject(_this2.error);}else{resolve(_this2.stringify());}});}if(this.processing){return this.processing;}this.processing=new Promise(function(resolve,reject){if(_this2.error)return reject(_this2.error);_this2.plugin=0;_this2.asyncTick(resolve,reject);}).then(function(){_this2.processed=true;return _this2.stringify();});return this.processing;};_proto.sync=function sync(){if(this.processed)return this.result;this.processed=true;if(this.processing){throw new Error('Use process(css).then(cb) to work with async plugins');}if(this.error)throw this.error;for(var _iterator=_createForOfIteratorHelperLoose(this.result.processor.plugins),_step;!(_step=_iterator()).done;){var plugin=_step.value;var promise=this.run(plugin);if(isPromise(promise)){throw new Error('Use process(css).then(cb) to work with async plugins');}}return this.result;};_proto.run=function run(plugin){this.result.lastPlugin=plugin;try{return plugin(this.result.root,this.result);}catch(error){this.handleError(error,plugin);throw error;}};_proto.stringify=function stringify(){if(this.stringified)return this.result;this.stringified=true;this.sync();var opts=this.result.opts;var str=_stringify2["default"];if(opts.syntax)str=opts.syntax.stringify;if(opts.stringifier)str=opts.stringifier;if(str.stringify)str=str.stringify;var map=new _mapGenerator["default"](str,this.result.root,this.result.opts);var data=map.generate();this.result.css=data[0];this.result.map=data[1];return this.result;};_createClass(LazyResult,[{key:"processor",get:function get(){return this.result.processor;}/**
     * Options from the {@link Processor#process} call.
     *
     * @type {processOptions}
     */},{key:"opts",get:function get(){return this.result.opts;}/**
     * Processes input CSS through synchronous plugins, converts `Root`
     * to a CSS string and returns {@link Result#css}.
     *
     * This property will only work with synchronous plugins.
     * If the processor contains any asynchronous plugins
     * it will throw an error. This is why this method is only
     * for debug purpose, you should always use {@link LazyResult#then}.
     *
     * @type {string}
     * @see Result#css
     */},{key:"css",get:function get(){return this.stringify().css;}/**
     * An alias for the `css` property. Use it with syntaxes
     * that generate non-CSS output.
     *
     * This property will only work with synchronous plugins.
     * If the processor contains any asynchronous plugins
     * it will throw an error. This is why this method is only
     * for debug purpose, you should always use {@link LazyResult#then}.
     *
     * @type {string}
     * @see Result#content
     */},{key:"content",get:function get(){return this.stringify().content;}/**
     * Processes input CSS through synchronous plugins
     * and returns {@link Result#map}.
     *
     * This property will only work with synchronous plugins.
     * If the processor contains any asynchronous plugins
     * it will throw an error. This is why this method is only
     * for debug purpose, you should always use {@link LazyResult#then}.
     *
     * @type {SourceMapGenerator}
     * @see Result#map
     */},{key:"map",get:function get(){return this.stringify().map;}/**
     * Processes input CSS through synchronous plugins
     * and returns {@link Result#root}.
     *
     * This property will only work with synchronous plugins. If the processor
     * contains any asynchronous plugins it will throw an error.
     *
     * This is why this method is only for debug purpose,
     * you should always use {@link LazyResult#then}.
     *
     * @type {Root}
     * @see Result#root
     */},{key:"root",get:function get(){return this.sync().root;}/**
     * Processes input CSS through synchronous plugins
     * and returns {@link Result#messages}.
     *
     * This property will only work with synchronous plugins. If the processor
     * contains any asynchronous plugins it will throw an error.
     *
     * This is why this method is only for debug purpose,
     * you should always use {@link LazyResult#then}.
     *
     * @type {Message[]}
     * @see Result#messages
     */},{key:"messages",get:function get(){return this.sync().messages;}}]);return LazyResult;}();var _default=LazyResult;/**
 * @callback onFulfilled
 * @param {Result} result
 */ /**
 * @callback onRejected
 * @param {Error} error
 */exports["default"]=_default;module.exports=exports["default"];}).call(this,require('_process'));},{"./map-generator":177,"./parse":179,"./result":184,"./stringify":188,"./warn-once":191,"_process":193}],176:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=void 0;/**
 * Contains helpers for safely splitting lists of CSS values,
 * preserving parentheses and quotes.
 *
 * @example
 * const list = postcss.list
 *
 * @namespace list
 */var list={split:function split(string,separators,last){var array=[];var current='';var split=false;var func=0;var quote=false;var escape=false;for(var i=0;i<string.length;i++){var letter=string[i];if(quote){if(escape){escape=false;}else if(letter==='\\'){escape=true;}else if(letter===quote){quote=false;}}else if(letter==='"'||letter==='\''){quote=letter;}else if(letter==='('){func+=1;}else if(letter===')'){if(func>0)func-=1;}else if(func===0){if(separators.indexOf(letter)!==-1)split=true;}if(split){if(current!=='')array.push(current.trim());current='';split=false;}else{current+=letter;}}if(last||current!=='')array.push(current.trim());return array;},/**
   * Safely splits space-separated values (such as those for `background`,
   * `border-radius`, and other shorthand properties).
   *
   * @param {string} string Space-separated values.
   *
   * @return {string[]} Split values.
   *
   * @example
   * postcss.list.space('1px calc(10% + 1px)') //=> ['1px', 'calc(10% + 1px)']
   */space:function space(string){var spaces=[' ','\n','\t'];return list.split(string,spaces);},/**
   * Safely splits comma-separated values (such as those for `transition-*`
   * and `background` properties).
   *
   * @param {string} string Comma-separated values.
   *
   * @return {string[]} Split values.
   *
   * @example
   * postcss.list.comma('black, linear-gradient(white, black)')
   * //=> ['black', 'linear-gradient(white, black)']
   */comma:function comma(string){return list.split(string,[','],true);}};var _default=list;exports["default"]=_default;module.exports=exports["default"];},{}],177:[function(require,module,exports){(function(Buffer){"use strict";exports.__esModule=true;exports["default"]=void 0;var _sourceMap=_interopRequireDefault(require("source-map"));var _path=_interopRequireDefault(require("path"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}function _createForOfIteratorHelperLoose(o,allowArrayLike){var it;if(typeof Symbol==="undefined"||o[Symbol.iterator]==null){if(Array.isArray(o)||(it=_unsupportedIterableToArray(o))||allowArrayLike&&o&&typeof o.length==="number"){if(it)o=it;var i=0;return function(){if(i>=o.length)return{done:true};return{done:false,value:o[i++]};};}throw new TypeError("Invalid attempt to iterate non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");}it=o[Symbol.iterator]();return it.next.bind(it);}function _unsupportedIterableToArray(o,minLen){if(!o)return;if(typeof o==="string")return _arrayLikeToArray(o,minLen);var n=Object.prototype.toString.call(o).slice(8,-1);if(n==="Object"&&o.constructor)n=o.constructor.name;if(n==="Map"||n==="Set")return Array.from(o);if(n==="Arguments"||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n))return _arrayLikeToArray(o,minLen);}function _arrayLikeToArray(arr,len){if(len==null||len>arr.length)len=arr.length;for(var i=0,arr2=new Array(len);i<len;i++){arr2[i]=arr[i];}return arr2;}var MapGenerator=/*#__PURE__*/function(){function MapGenerator(stringify,root,opts){this.stringify=stringify;this.mapOpts=opts.map||{};this.root=root;this.opts=opts;}var _proto=MapGenerator.prototype;_proto.isMap=function isMap(){if(typeof this.opts.map!=='undefined'){return!!this.opts.map;}return this.previous().length>0;};_proto.previous=function previous(){var _this=this;if(!this.previousMaps){this.previousMaps=[];this.root.walk(function(node){if(node.source&&node.source.input.map){var map=node.source.input.map;if(_this.previousMaps.indexOf(map)===-1){_this.previousMaps.push(map);}}});}return this.previousMaps;};_proto.isInline=function isInline(){if(typeof this.mapOpts.inline!=='undefined'){return this.mapOpts.inline;}var annotation=this.mapOpts.annotation;if(typeof annotation!=='undefined'&&annotation!==true){return false;}if(this.previous().length){return this.previous().some(function(i){return i.inline;});}return true;};_proto.isSourcesContent=function isSourcesContent(){if(typeof this.mapOpts.sourcesContent!=='undefined'){return this.mapOpts.sourcesContent;}if(this.previous().length){return this.previous().some(function(i){return i.withContent();});}return true;};_proto.clearAnnotation=function clearAnnotation(){if(this.mapOpts.annotation===false)return;var node;for(var i=this.root.nodes.length-1;i>=0;i--){node=this.root.nodes[i];if(node.type!=='comment')continue;if(node.text.indexOf('# sourceMappingURL=')===0){this.root.removeChild(i);}}};_proto.setSourcesContent=function setSourcesContent(){var _this2=this;var already={};this.root.walk(function(node){if(node.source){var from=node.source.input.from;if(from&&!already[from]){already[from]=true;var relative=_this2.relative(from);_this2.map.setSourceContent(relative,node.source.input.css);}}});};_proto.applyPrevMaps=function applyPrevMaps(){for(var _iterator=_createForOfIteratorHelperLoose(this.previous()),_step;!(_step=_iterator()).done;){var prev=_step.value;var from=this.relative(prev.file);var root=prev.root||_path["default"].dirname(prev.file);var map=void 0;if(this.mapOpts.sourcesContent===false){map=new _sourceMap["default"].SourceMapConsumer(prev.text);if(map.sourcesContent){map.sourcesContent=map.sourcesContent.map(function(){return null;});}}else{map=prev.consumer();}this.map.applySourceMap(map,from,this.relative(root));}};_proto.isAnnotation=function isAnnotation(){if(this.isInline()){return true;}if(typeof this.mapOpts.annotation!=='undefined'){return this.mapOpts.annotation;}if(this.previous().length){return this.previous().some(function(i){return i.annotation;});}return true;};_proto.toBase64=function toBase64(str){if(Buffer){return Buffer.from(str).toString('base64');}return window.btoa(unescape(encodeURIComponent(str)));};_proto.addAnnotation=function addAnnotation(){var content;if(this.isInline()){content='data:application/json;base64,'+this.toBase64(this.map.toString());}else if(typeof this.mapOpts.annotation==='string'){content=this.mapOpts.annotation;}else{content=this.outputFile()+'.map';}var eol='\n';if(this.css.indexOf('\r\n')!==-1)eol='\r\n';this.css+=eol+'/*# sourceMappingURL='+content+' */';};_proto.outputFile=function outputFile(){if(this.opts.to){return this.relative(this.opts.to);}if(this.opts.from){return this.relative(this.opts.from);}return'to.css';};_proto.generateMap=function generateMap(){this.generateString();if(this.isSourcesContent())this.setSourcesContent();if(this.previous().length>0)this.applyPrevMaps();if(this.isAnnotation())this.addAnnotation();if(this.isInline()){return[this.css];}return[this.css,this.map];};_proto.relative=function relative(file){if(file.indexOf('<')===0)return file;if(/^\w+:\/\//.test(file))return file;var from=this.opts.to?_path["default"].dirname(this.opts.to):'.';if(typeof this.mapOpts.annotation==='string'){from=_path["default"].dirname(_path["default"].resolve(from,this.mapOpts.annotation));}file=_path["default"].relative(from,file);if(_path["default"].sep==='\\'){return file.replace(/\\/g,'/');}return file;};_proto.sourcePath=function sourcePath(node){if(this.mapOpts.from){return this.mapOpts.from;}return this.relative(node.source.input.from);};_proto.generateString=function generateString(){var _this3=this;this.css='';this.map=new _sourceMap["default"].SourceMapGenerator({file:this.outputFile()});var line=1;var column=1;var lines,last;this.stringify(this.root,function(str,node,type){_this3.css+=str;if(node&&type!=='end'){if(node.source&&node.source.start){_this3.map.addMapping({source:_this3.sourcePath(node),generated:{line:line,column:column-1},original:{line:node.source.start.line,column:node.source.start.column-1}});}else{_this3.map.addMapping({source:'<no source>',original:{line:1,column:0},generated:{line:line,column:column-1}});}}lines=str.match(/\n/g);if(lines){line+=lines.length;last=str.lastIndexOf('\n');column=str.length-last;}else{column+=str.length;}if(node&&type!=='start'){var p=node.parent||{raws:{}};if(node.type!=='decl'||node!==p.last||p.raws.semicolon){if(node.source&&node.source.end){_this3.map.addMapping({source:_this3.sourcePath(node),generated:{line:line,column:column-2},original:{line:node.source.end.line,column:node.source.end.column-1}});}else{_this3.map.addMapping({source:'<no source>',original:{line:1,column:0},generated:{line:line,column:column-1}});}}}});};_proto.generate=function generate(){this.clearAnnotation();if(this.isMap()){return this.generateMap();}var result='';this.stringify(this.root,function(i){result+=i;});return[result];};return MapGenerator;}();var _default=MapGenerator;exports["default"]=_default;module.exports=exports["default"];}).call(this,require("buffer").Buffer);},{"buffer":3,"path":168,"source-map":208}],178:[function(require,module,exports){(function(process){"use strict";exports.__esModule=true;exports["default"]=void 0;var _cssSyntaxError=_interopRequireDefault(require("./css-syntax-error"));var _stringifier=_interopRequireDefault(require("./stringifier"));var _stringify=_interopRequireDefault(require("./stringify"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}function cloneNode(obj,parent){var cloned=new obj.constructor();for(var i in obj){if(!obj.hasOwnProperty(i))continue;var value=obj[i];var type=_typeof(value);if(i==='parent'&&type==='object'){if(parent)cloned[i]=parent;}else if(i==='source'){cloned[i]=value;}else if(value instanceof Array){cloned[i]=value.map(function(j){return cloneNode(j,cloned);});}else{if(type==='object'&&value!==null)value=cloneNode(value);cloned[i]=value;}}return cloned;}/**
 * All node classes inherit the following common methods.
 *
 * @abstract
 */var Node=/*#__PURE__*/function(){/**
   * @param {object} [defaults] Value for node properties.
   */function Node(defaults){if(defaults===void 0){defaults={};}this.raws={};if(process.env.NODE_ENV!=='production'){if(_typeof(defaults)!=='object'&&typeof defaults!=='undefined'){throw new Error('PostCSS nodes constructor accepts object, not '+JSON.stringify(defaults));}}for(var name in defaults){this[name]=defaults[name];}}/**
   * Returns a `CssSyntaxError` instance containing the original position
   * of the node in the source, showing line and column numbers and also
   * a small excerpt to facilitate debugging.
   *
   * If present, an input source map will be used to get the original position
   * of the source, even from a previous compilation step
   * (e.g., from Sass compilation).
   *
   * This method produces very useful error messages.
   *
   * @param {string} message     Error description.
   * @param {object} [opts]      Options.
   * @param {string} opts.plugin Plugin name that created this error.
   *                             PostCSS will set it automatically.
   * @param {string} opts.word   A word inside a node’s string that should
   *                             be highlighted as the source of the error.
   * @param {number} opts.index  An index inside a node’s string that should
   *                             be highlighted as the source of the error.
   *
   * @return {CssSyntaxError} Error object to throw it.
   *
   * @example
   * if (!variables[name]) {
   *   throw decl.error('Unknown variable ' + name, { word: name })
   *   // CssSyntaxError: postcss-vars:a.sass:4:3: Unknown variable $black
   *   //   color: $black
   *   // a
   *   //          ^
   *   //   background: white
   * }
   */var _proto=Node.prototype;_proto.error=function error(message,opts){if(opts===void 0){opts={};}if(this.source){var pos=this.positionBy(opts);return this.source.input.error(message,pos.line,pos.column,opts);}return new _cssSyntaxError["default"](message);}/**
   * This method is provided as a convenience wrapper for {@link Result#warn}.
   *
   * @param {Result} result      The {@link Result} instance
   *                             that will receive the warning.
   * @param {string} text        Warning message.
   * @param {object} [opts]      Options
   * @param {string} opts.plugin Plugin name that created this warning.
   *                             PostCSS will set it automatically.
   * @param {string} opts.word   A word inside a node’s string that should
   *                             be highlighted as the source of the warning.
   * @param {number} opts.index  An index inside a node’s string that should
   *                             be highlighted as the source of the warning.
   *
   * @return {Warning} Created warning object.
   *
   * @example
   * const plugin = postcss.plugin('postcss-deprecated', () => {
   *   return (root, result) => {
   *     root.walkDecls('bad', decl => {
   *       decl.warn(result, 'Deprecated property bad')
   *     })
   *   }
   * })
   */;_proto.warn=function warn(result,text,opts){var data={node:this};for(var i in opts){data[i]=opts[i];}return result.warn(text,data);}/**
   * Removes the node from its parent and cleans the parent properties
   * from the node and its children.
   *
   * @example
   * if (decl.prop.match(/^-webkit-/)) {
   *   decl.remove()
   * }
   *
   * @return {Node} Node to make calls chain.
   */;_proto.remove=function remove(){if(this.parent){this.parent.removeChild(this);}this.parent=undefined;return this;}/**
   * Returns a CSS string representing the node.
   *
   * @param {stringifier|syntax} [stringifier] A syntax to use
   *                                           in string generation.
   *
   * @return {string} CSS string of this node.
   *
   * @example
   * postcss.rule({ selector: 'a' }).toString() //=> "a {}"
   */;_proto.toString=function toString(stringifier){if(stringifier===void 0){stringifier=_stringify["default"];}if(stringifier.stringify)stringifier=stringifier.stringify;var result='';stringifier(this,function(i){result+=i;});return result;}/**
   * Returns an exact clone of the node.
   *
   * The resulting cloned node and its (cloned) children will retain
   * code style properties.
   *
   * @param {object} [overrides] New properties to override in the clone.
   *
   * @example
   * decl.raws.before    //=> "\n  "
   * const cloned = decl.clone({ prop: '-moz-' + decl.prop })
   * cloned.raws.before  //=> "\n  "
   * cloned.toString()   //=> -moz-transform: scale(0)
   *
   * @return {Node} Clone of the node.
   */;_proto.clone=function clone(overrides){if(overrides===void 0){overrides={};}var cloned=cloneNode(this);for(var name in overrides){cloned[name]=overrides[name];}return cloned;}/**
   * Shortcut to clone the node and insert the resulting cloned node
   * before the current node.
   *
   * @param {object} [overrides] Mew properties to override in the clone.
   *
   * @example
   * decl.cloneBefore({ prop: '-moz-' + decl.prop })
   *
   * @return {Node} New node
   */;_proto.cloneBefore=function cloneBefore(overrides){if(overrides===void 0){overrides={};}var cloned=this.clone(overrides);this.parent.insertBefore(this,cloned);return cloned;}/**
   * Shortcut to clone the node and insert the resulting cloned node
   * after the current node.
   *
   * @param {object} [overrides] New properties to override in the clone.
   *
   * @return {Node} New node.
   */;_proto.cloneAfter=function cloneAfter(overrides){if(overrides===void 0){overrides={};}var cloned=this.clone(overrides);this.parent.insertAfter(this,cloned);return cloned;}/**
   * Inserts node(s) before the current node and removes the current node.
   *
   * @param {...Node} nodes Mode(s) to replace current one.
   *
   * @example
   * if (atrule.name === 'mixin') {
   *   atrule.replaceWith(mixinRules[atrule.params])
   * }
   *
   * @return {Node} Current node to methods chain.
   */;_proto.replaceWith=function replaceWith(){if(this.parent){for(var _len=arguments.length,nodes=new Array(_len),_key=0;_key<_len;_key++){nodes[_key]=arguments[_key];}for(var _i=0,_nodes=nodes;_i<_nodes.length;_i++){var node=_nodes[_i];this.parent.insertBefore(this,node);}this.remove();}return this;}/**
   * Returns the next child of the node’s parent.
   * Returns `undefined` if the current node is the last child.
   *
   * @return {Node|undefined} Next node.
   *
   * @example
   * if (comment.text === 'delete next') {
   *   const next = comment.next()
   *   if (next) {
   *     next.remove()
   *   }
   * }
   */;_proto.next=function next(){if(!this.parent)return undefined;var index=this.parent.index(this);return this.parent.nodes[index+1];}/**
   * Returns the previous child of the node’s parent.
   * Returns `undefined` if the current node is the first child.
   *
   * @return {Node|undefined} Previous node.
   *
   * @example
   * const annotation = decl.prev()
   * if (annotation.type === 'comment') {
   *   readAnnotation(annotation.text)
   * }
   */;_proto.prev=function prev(){if(!this.parent)return undefined;var index=this.parent.index(this);return this.parent.nodes[index-1];}/**
   * Insert new node before current node to current node’s parent.
   *
   * Just alias for `node.parent.insertBefore(node, add)`.
   *
   * @param {Node|object|string|Node[]} add New node.
   *
   * @return {Node} This node for methods chain.
   *
   * @example
   * decl.before('content: ""')
   */;_proto.before=function before(add){this.parent.insertBefore(this,add);return this;}/**
   * Insert new node after current node to current node’s parent.
   *
   * Just alias for `node.parent.insertAfter(node, add)`.
   *
   * @param {Node|object|string|Node[]} add New node.
   *
   * @return {Node} This node for methods chain.
   *
   * @example
   * decl.after('color: black')
   */;_proto.after=function after(add){this.parent.insertAfter(this,add);return this;};_proto.toJSON=function toJSON(){var fixed={};for(var name in this){if(!this.hasOwnProperty(name))continue;if(name==='parent')continue;var value=this[name];if(value instanceof Array){fixed[name]=value.map(function(i){if(_typeof(i)==='object'&&i.toJSON){return i.toJSON();}else{return i;}});}else if(_typeof(value)==='object'&&value.toJSON){fixed[name]=value.toJSON();}else{fixed[name]=value;}}return fixed;}/**
   * Returns a {@link Node#raws} value. If the node is missing
   * the code style property (because the node was manually built or cloned),
   * PostCSS will try to autodetect the code style property by looking
   * at other nodes in the tree.
   *
   * @param {string} prop          Name of code style property.
   * @param {string} [defaultType] Name of default value, it can be missed
   *                               if the value is the same as prop.
   *
   * @example
   * const root = postcss.parse('a { background: white }')
   * root.nodes[0].append({ prop: 'color', value: 'black' })
   * root.nodes[0].nodes[1].raws.before   //=> undefined
   * root.nodes[0].nodes[1].raw('before') //=> ' '
   *
   * @return {string} Code style value.
   */;_proto.raw=function raw(prop,defaultType){var str=new _stringifier["default"]();return str.raw(this,prop,defaultType);}/**
   * Finds the Root instance of the node’s tree.
   *
   * @example
   * root.nodes[0].nodes[0].root() === root
   *
   * @return {Root} Root parent.
   */;_proto.root=function root(){var result=this;while(result.parent){result=result.parent;}return result;}/**
   * Clear the code style properties for the node and its children.
   *
   * @param {boolean} [keepBetween] Keep the raws.between symbols.
   *
   * @return {undefined}
   *
   * @example
   * node.raws.before  //=> ' '
   * node.cleanRaws()
   * node.raws.before  //=> undefined
   */;_proto.cleanRaws=function cleanRaws(keepBetween){delete this.raws.before;delete this.raws.after;if(!keepBetween)delete this.raws.between;};_proto.positionInside=function positionInside(index){var string=this.toString();var column=this.source.start.column;var line=this.source.start.line;for(var i=0;i<index;i++){if(string[i]==='\n'){column=1;line+=1;}else{column+=1;}}return{line:line,column:column};};_proto.positionBy=function positionBy(opts){var pos=this.source.start;if(opts.index){pos=this.positionInside(opts.index);}else if(opts.word){var index=this.toString().indexOf(opts.word);if(index!==-1)pos=this.positionInside(index);}return pos;}/**
   * @memberof Node#
   * @member {string} type String representing the node’s type.
   *                       Possible values are `root`, `atrule`, `rule`,
   *                       `decl`, or `comment`.
   *
   * @example
   * postcss.decl({ prop: 'color', value: 'black' }).type //=> 'decl'
   */ /**
   * @memberof Node#
   * @member {Container} parent The node’s parent node.
   *
   * @example
   * root.nodes[0].parent === root
   */ /**
   * @memberof Node#
   * @member {source} source The input source of the node.
   *
   * The property is used in source map generation.
   *
   * If you create a node manually (e.g., with `postcss.decl()`),
   * that node will not have a `source` property and will be absent
   * from the source map. For this reason, the plugin developer should
   * consider cloning nodes to create new ones (in which case the new node’s
   * source will reference the original, cloned node) or setting
   * the `source` property manually.
   *
   * ```js
   * // Bad
   * const prefixed = postcss.decl({
   *   prop: '-moz-' + decl.prop,
   *   value: decl.value
   * })
   *
   * // Good
   * const prefixed = decl.clone({ prop: '-moz-' + decl.prop })
   * ```
   *
   * ```js
   * if (atrule.name === 'add-link') {
   *   const rule = postcss.rule({ selector: 'a', source: atrule.source })
   *   atrule.parent.insertBefore(atrule, rule)
   * }
   * ```
   *
   * @example
   * decl.source.input.from //=> '/home/ai/a.sass'
   * decl.source.start      //=> { line: 10, column: 2 }
   * decl.source.end        //=> { line: 10, column: 12 }
   */ /**
   * @memberof Node#
   * @member {object} raws Information to generate byte-to-byte equal
   *                       node string as it was in the origin input.
   *
   * Every parser saves its own properties,
   * but the default CSS parser uses:
   *
   * * `before`: the space symbols before the node. It also stores `*`
   *   and `_` symbols before the declaration (IE hack).
   * * `after`: the space symbols after the last child of the node
   *   to the end of the node.
   * * `between`: the symbols between the property and value
   *   for declarations, selector and `{` for rules, or last parameter
   *   and `{` for at-rules.
   * * `semicolon`: contains true if the last child has
   *   an (optional) semicolon.
   * * `afterName`: the space between the at-rule name and its parameters.
   * * `left`: the space symbols between `/*` and the comment’s text.
   * * `right`: the space symbols between the comment’s text
   *   and <code>*&#47;</code>.
   * * `important`: the content of the important statement,
   *   if it is not just `!important`.
   *
   * PostCSS cleans selectors, declaration values and at-rule parameters
   * from comments and extra spaces, but it stores origin content in raws
   * properties. As such, if you don’t change a declaration’s value,
   * PostCSS will use the raw value with comments.
   *
   * @example
   * const root = postcss.parse('a {\n  color:black\n}')
   * root.first.first.raws //=> { before: '\n  ', between: ':' }
   */;return Node;}();var _default=Node;/**
 * @typedef {object} position
 * @property {number} line   Source line in file.
 * @property {number} column Source column in file.
 */ /**
 * @typedef {object} source
 * @property {Input} input    {@link Input} with input file
 * @property {position} start The starting position of the node’s source.
 * @property {position} end   The ending position of the node’s source.
 */exports["default"]=_default;module.exports=exports["default"];}).call(this,require('_process'));},{"./css-syntax-error":172,"./stringifier":187,"./stringify":188,"_process":193}],179:[function(require,module,exports){(function(process){"use strict";exports.__esModule=true;exports["default"]=void 0;var _parser=_interopRequireDefault(require("./parser"));var _input=_interopRequireDefault(require("./input"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}function parse(css,opts){var input=new _input["default"](css,opts);var parser=new _parser["default"](input);try{parser.parse();}catch(e){if(process.env.NODE_ENV!=='production'){if(e.name==='CssSyntaxError'&&opts&&opts.from){if(/\.scss$/i.test(opts.from)){e.message+='\nYou tried to parse SCSS with '+'the standard CSS parser; '+'try again with the postcss-scss parser';}else if(/\.sass/i.test(opts.from)){e.message+='\nYou tried to parse Sass with '+'the standard CSS parser; '+'try again with the postcss-sass parser';}else if(/\.less$/i.test(opts.from)){e.message+='\nYou tried to parse Less with '+'the standard CSS parser; '+'try again with the postcss-less parser';}}}throw e;}return parser.root;}var _default=parse;exports["default"]=_default;module.exports=exports["default"];}).call(this,require('_process'));},{"./input":174,"./parser":180,"_process":193}],180:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=void 0;var _declaration=_interopRequireDefault(require("./declaration"));var _tokenize=_interopRequireDefault(require("./tokenize"));var _comment=_interopRequireDefault(require("./comment"));var _atRule=_interopRequireDefault(require("./at-rule"));var _root=_interopRequireDefault(require("./root"));var _rule=_interopRequireDefault(require("./rule"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}var Parser=/*#__PURE__*/function(){function Parser(input){this.input=input;this.root=new _root["default"]();this.current=this.root;this.spaces='';this.semicolon=false;this.createTokenizer();this.root.source={input:input,start:{line:1,column:1}};}var _proto=Parser.prototype;_proto.createTokenizer=function createTokenizer(){this.tokenizer=(0,_tokenize["default"])(this.input);};_proto.parse=function parse(){var token;while(!this.tokenizer.endOfFile()){token=this.tokenizer.nextToken();switch(token[0]){case'space':this.spaces+=token[1];break;case';':this.freeSemicolon(token);break;case'}':this.end(token);break;case'comment':this.comment(token);break;case'at-word':this.atrule(token);break;case'{':this.emptyRule(token);break;default:this.other(token);break;}}this.endFile();};_proto.comment=function comment(token){var node=new _comment["default"]();this.init(node,token[2],token[3]);node.source.end={line:token[4],column:token[5]};var text=token[1].slice(2,-2);if(/^\s*$/.test(text)){node.text='';node.raws.left=text;node.raws.right='';}else{var match=text.match(/^(\s*)([^]*[^\s])(\s*)$/);node.text=match[2];node.raws.left=match[1];node.raws.right=match[3];}};_proto.emptyRule=function emptyRule(token){var node=new _rule["default"]();this.init(node,token[2],token[3]);node.selector='';node.raws.between='';this.current=node;};_proto.other=function other(start){var end=false;var type=null;var colon=false;var bracket=null;var brackets=[];var tokens=[];var token=start;while(token){type=token[0];tokens.push(token);if(type==='('||type==='['){if(!bracket)bracket=token;brackets.push(type==='('?')':']');}else if(brackets.length===0){if(type===';'){if(colon){this.decl(tokens);return;}else{break;}}else if(type==='{'){this.rule(tokens);return;}else if(type==='}'){this.tokenizer.back(tokens.pop());end=true;break;}else if(type===':'){colon=true;}}else if(type===brackets[brackets.length-1]){brackets.pop();if(brackets.length===0)bracket=null;}token=this.tokenizer.nextToken();}if(this.tokenizer.endOfFile())end=true;if(brackets.length>0)this.unclosedBracket(bracket);if(end&&colon){while(tokens.length){token=tokens[tokens.length-1][0];if(token!=='space'&&token!=='comment')break;this.tokenizer.back(tokens.pop());}this.decl(tokens);}else{this.unknownWord(tokens);}};_proto.rule=function rule(tokens){tokens.pop();var node=new _rule["default"]();this.init(node,tokens[0][2],tokens[0][3]);node.raws.between=this.spacesAndCommentsFromEnd(tokens);this.raw(node,'selector',tokens);this.current=node;};_proto.decl=function decl(tokens){var node=new _declaration["default"]();this.init(node);var last=tokens[tokens.length-1];if(last[0]===';'){this.semicolon=true;tokens.pop();}if(last[4]){node.source.end={line:last[4],column:last[5]};}else{node.source.end={line:last[2],column:last[3]};}while(tokens[0][0]!=='word'){if(tokens.length===1)this.unknownWord(tokens);node.raws.before+=tokens.shift()[1];}node.source.start={line:tokens[0][2],column:tokens[0][3]};node.prop='';while(tokens.length){var type=tokens[0][0];if(type===':'||type==='space'||type==='comment'){break;}node.prop+=tokens.shift()[1];}node.raws.between='';var token;while(tokens.length){token=tokens.shift();if(token[0]===':'){node.raws.between+=token[1];break;}else{if(token[0]==='word'&&/\w/.test(token[1])){this.unknownWord([token]);}node.raws.between+=token[1];}}if(node.prop[0]==='_'||node.prop[0]==='*'){node.raws.before+=node.prop[0];node.prop=node.prop.slice(1);}node.raws.between+=this.spacesAndCommentsFromStart(tokens);this.precheckMissedSemicolon(tokens);for(var i=tokens.length-1;i>0;i--){token=tokens[i];if(token[1].toLowerCase()==='!important'){node.important=true;var string=this.stringFrom(tokens,i);string=this.spacesFromEnd(tokens)+string;if(string!==' !important')node.raws.important=string;break;}else if(token[1].toLowerCase()==='important'){var cache=tokens.slice(0);var str='';for(var j=i;j>0;j--){var _type=cache[j][0];if(str.trim().indexOf('!')===0&&_type!=='space'){break;}str=cache.pop()[1]+str;}if(str.trim().indexOf('!')===0){node.important=true;node.raws.important=str;tokens=cache;}}if(token[0]!=='space'&&token[0]!=='comment'){break;}}this.raw(node,'value',tokens);if(node.value.indexOf(':')!==-1)this.checkMissedSemicolon(tokens);};_proto.atrule=function atrule(token){var node=new _atRule["default"]();node.name=token[1].slice(1);if(node.name===''){this.unnamedAtrule(node,token);}this.init(node,token[2],token[3]);var prev;var shift;var last=false;var open=false;var params=[];while(!this.tokenizer.endOfFile()){token=this.tokenizer.nextToken();if(token[0]===';'){node.source.end={line:token[2],column:token[3]};this.semicolon=true;break;}else if(token[0]==='{'){open=true;break;}else if(token[0]==='}'){if(params.length>0){shift=params.length-1;prev=params[shift];while(prev&&prev[0]==='space'){prev=params[--shift];}if(prev){node.source.end={line:prev[4],column:prev[5]};}}this.end(token);break;}else{params.push(token);}if(this.tokenizer.endOfFile()){last=true;break;}}node.raws.between=this.spacesAndCommentsFromEnd(params);if(params.length){node.raws.afterName=this.spacesAndCommentsFromStart(params);this.raw(node,'params',params);if(last){token=params[params.length-1];node.source.end={line:token[4],column:token[5]};this.spaces=node.raws.between;node.raws.between='';}}else{node.raws.afterName='';node.params='';}if(open){node.nodes=[];this.current=node;}};_proto.end=function end(token){if(this.current.nodes&&this.current.nodes.length){this.current.raws.semicolon=this.semicolon;}this.semicolon=false;this.current.raws.after=(this.current.raws.after||'')+this.spaces;this.spaces='';if(this.current.parent){this.current.source.end={line:token[2],column:token[3]};this.current=this.current.parent;}else{this.unexpectedClose(token);}};_proto.endFile=function endFile(){if(this.current.parent)this.unclosedBlock();if(this.current.nodes&&this.current.nodes.length){this.current.raws.semicolon=this.semicolon;}this.current.raws.after=(this.current.raws.after||'')+this.spaces;};_proto.freeSemicolon=function freeSemicolon(token){this.spaces+=token[1];if(this.current.nodes){var prev=this.current.nodes[this.current.nodes.length-1];if(prev&&prev.type==='rule'&&!prev.raws.ownSemicolon){prev.raws.ownSemicolon=this.spaces;this.spaces='';}}}// Helpers
;_proto.init=function init(node,line,column){this.current.push(node);node.source={start:{line:line,column:column},input:this.input};node.raws.before=this.spaces;this.spaces='';if(node.type!=='comment')this.semicolon=false;};_proto.raw=function raw(node,prop,tokens){var token,type;var length=tokens.length;var value='';var clean=true;var next,prev;var pattern=/^([.|#])?([\w])+/i;for(var i=0;i<length;i+=1){token=tokens[i];type=token[0];if(type==='comment'&&node.type==='rule'){prev=tokens[i-1];next=tokens[i+1];if(prev[0]!=='space'&&next[0]!=='space'&&pattern.test(prev[1])&&pattern.test(next[1])){value+=token[1];}else{clean=false;}continue;}if(type==='comment'||type==='space'&&i===length-1){clean=false;}else{value+=token[1];}}if(!clean){var raw=tokens.reduce(function(all,i){return all+i[1];},'');node.raws[prop]={value:value,raw:raw};}node[prop]=value;};_proto.spacesAndCommentsFromEnd=function spacesAndCommentsFromEnd(tokens){var lastTokenType;var spaces='';while(tokens.length){lastTokenType=tokens[tokens.length-1][0];if(lastTokenType!=='space'&&lastTokenType!=='comment')break;spaces=tokens.pop()[1]+spaces;}return spaces;};_proto.spacesAndCommentsFromStart=function spacesAndCommentsFromStart(tokens){var next;var spaces='';while(tokens.length){next=tokens[0][0];if(next!=='space'&&next!=='comment')break;spaces+=tokens.shift()[1];}return spaces;};_proto.spacesFromEnd=function spacesFromEnd(tokens){var lastTokenType;var spaces='';while(tokens.length){lastTokenType=tokens[tokens.length-1][0];if(lastTokenType!=='space')break;spaces=tokens.pop()[1]+spaces;}return spaces;};_proto.stringFrom=function stringFrom(tokens,from){var result='';for(var i=from;i<tokens.length;i++){result+=tokens[i][1];}tokens.splice(from,tokens.length-from);return result;};_proto.colon=function colon(tokens){var brackets=0;var token,type,prev;for(var i=0;i<tokens.length;i++){token=tokens[i];type=token[0];if(type==='('){brackets+=1;}if(type===')'){brackets-=1;}if(brackets===0&&type===':'){if(!prev){this.doubleColon(token);}else if(prev[0]==='word'&&prev[1]==='progid'){continue;}else{return i;}}prev=token;}return false;}// Errors
;_proto.unclosedBracket=function unclosedBracket(bracket){throw this.input.error('Unclosed bracket',bracket[2],bracket[3]);};_proto.unknownWord=function unknownWord(tokens){throw this.input.error('Unknown word',tokens[0][2],tokens[0][3]);};_proto.unexpectedClose=function unexpectedClose(token){throw this.input.error('Unexpected }',token[2],token[3]);};_proto.unclosedBlock=function unclosedBlock(){var pos=this.current.source.start;throw this.input.error('Unclosed block',pos.line,pos.column);};_proto.doubleColon=function doubleColon(token){throw this.input.error('Double colon',token[2],token[3]);};_proto.unnamedAtrule=function unnamedAtrule(node,token){throw this.input.error('At-rule without name',token[2],token[3]);};_proto.precheckMissedSemicolon=function precheckMissedSemicolon()/* tokens */{// Hook for Safe Parser
};_proto.checkMissedSemicolon=function checkMissedSemicolon(tokens){var colon=this.colon(tokens);if(colon===false)return;var founded=0;var token;for(var j=colon-1;j>=0;j--){token=tokens[j];if(token[0]!=='space'){founded+=1;if(founded===2)break;}}throw this.input.error('Missed semicolon',token[2],token[3]);};return Parser;}();exports["default"]=Parser;module.exports=exports["default"];},{"./at-rule":169,"./comment":170,"./declaration":173,"./root":185,"./rule":186,"./tokenize":189}],181:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=void 0;var _declaration=_interopRequireDefault(require("./declaration"));var _processor=_interopRequireDefault(require("./processor"));var _stringify=_interopRequireDefault(require("./stringify"));var _comment=_interopRequireDefault(require("./comment"));var _atRule=_interopRequireDefault(require("./at-rule"));var _vendor=_interopRequireDefault(require("./vendor"));var _parse=_interopRequireDefault(require("./parse"));var _list=_interopRequireDefault(require("./list"));var _rule=_interopRequireDefault(require("./rule"));var _root=_interopRequireDefault(require("./root"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}/**
 * Create a new {@link Processor} instance that will apply `plugins`
 * as CSS processors.
 *
 * @param {Array.<Plugin|pluginFunction>|Processor} plugins PostCSS plugins.
 *        See {@link Processor#use} for plugin format.
 *
 * @return {Processor} Processor to process multiple CSS.
 *
 * @example
 * import postcss from 'postcss'
 *
 * postcss(plugins).process(css, { from, to }).then(result => {
 *   console.log(result.css)
 * })
 *
 * @namespace postcss
 */function postcss(){for(var _len=arguments.length,plugins=new Array(_len),_key=0;_key<_len;_key++){plugins[_key]=arguments[_key];}if(plugins.length===1&&Array.isArray(plugins[0])){plugins=plugins[0];}return new _processor["default"](plugins);}/**
 * Creates a PostCSS plugin with a standard API.
 *
 * The newly-wrapped function will provide both the name and PostCSS
 * version of the plugin.
 *
 * ```js
 * const processor = postcss([replace])
 * processor.plugins[0].postcssPlugin  //=> 'postcss-replace'
 * processor.plugins[0].postcssVersion //=> '6.0.0'
 * ```
 *
 * The plugin function receives 2 arguments: {@link Root}
 * and {@link Result} instance. The function should mutate the provided
 * `Root` node. Alternatively, you can create a new `Root` node
 * and override the `result.root` property.
 *
 * ```js
 * const cleaner = postcss.plugin('postcss-cleaner', () => {
 *   return (root, result) => {
 *     result.root = postcss.root()
 *   }
 * })
 * ```
 *
 * As a convenience, plugins also expose a `process` method so that you can use
 * them as standalone tools.
 *
 * ```js
 * cleaner.process(css, processOpts, pluginOpts)
 * // This is equivalent to:
 * postcss([ cleaner(pluginOpts) ]).process(css, processOpts)
 * ```
 *
 * Asynchronous plugins should return a `Promise` instance.
 *
 * ```js
 * postcss.plugin('postcss-import', () => {
 *   return (root, result) => {
 *     return new Promise( (resolve, reject) => {
 *       fs.readFile('base.css', (base) => {
 *         root.prepend(base)
 *         resolve()
 *       })
 *     })
 *   }
 * })
 * ```
 *
 * Add warnings using the {@link Node#warn} method.
 * Send data to other plugins using the {@link Result#messages} array.
 *
 * ```js
 * postcss.plugin('postcss-caniuse-test', () => {
 *   return (root, result) => {
 *     root.walkDecls(decl => {
 *       if (!caniuse.support(decl.prop)) {
 *         decl.warn(result, 'Some browsers do not support ' + decl.prop)
 *       }
 *     })
 *   }
 * })
 * ```
 *
 * @param {string} name          PostCSS plugin name. Same as in `name`
 *                               property in `package.json`. It will be saved
 *                               in `plugin.postcssPlugin` property.
 * @param {function} initializer Will receive plugin options
 *                               and should return {@link pluginFunction}
 *
 * @return {Plugin} PostCSS plugin.
 */postcss.plugin=function plugin(name,initializer){function creator(){var transformer=initializer.apply(void 0,arguments);transformer.postcssPlugin=name;transformer.postcssVersion=new _processor["default"]().version;return transformer;}var cache;Object.defineProperty(creator,'postcss',{get:function get(){if(!cache)cache=creator();return cache;}});creator.process=function(css,processOpts,pluginOpts){return postcss([creator(pluginOpts)]).process(css,processOpts);};return creator;};/**
 * Default function to convert a node tree into a CSS string.
 *
 * @param {Node} node       Start node for stringifing. Usually {@link Root}.
 * @param {builder} builder Function to concatenate CSS from node’s parts
 *                          or generate string and source map.
 *
 * @return {void}
 *
 * @function
 */postcss.stringify=_stringify["default"];/**
 * Parses source css and returns a new {@link Root} node,
 * which contains the source CSS nodes.
 *
 * @param {string|toString} css   String with input CSS or any object
 *                                with toString() method, like a Buffer
 * @param {processOptions} [opts] Options with only `from` and `map` keys.
 *
 * @return {Root} PostCSS AST.
 *
 * @example
 * // Simple CSS concatenation with source map support
 * const root1 = postcss.parse(css1, { from: file1 })
 * const root2 = postcss.parse(css2, { from: file2 })
 * root1.append(root2).toResult().css
 *
 * @function
 */postcss.parse=_parse["default"];/**
 * Contains the {@link vendor} module.
 *
 * @type {vendor}
 *
 * @example
 * postcss.vendor.unprefixed('-moz-tab') //=> ['tab']
 */postcss.vendor=_vendor["default"];/**
 * Contains the {@link list} module.
 *
 * @member {list}
 *
 * @example
 * postcss.list.space('5px calc(10% + 5px)') //=> ['5px', 'calc(10% + 5px)']
 */postcss.list=_list["default"];/**
 * Creates a new {@link Comment} node.
 *
 * @param {object} [defaults] Properties for the new node.
 *
 * @return {Comment} New comment node
 *
 * @example
 * postcss.comment({ text: 'test' })
 */postcss.comment=function(defaults){return new _comment["default"](defaults);};/**
 * Creates a new {@link AtRule} node.
 *
 * @param {object} [defaults] Properties for the new node.
 *
 * @return {AtRule} new at-rule node
 *
 * @example
 * postcss.atRule({ name: 'charset' }).toString() //=> "@charset"
 */postcss.atRule=function(defaults){return new _atRule["default"](defaults);};/**
 * Creates a new {@link Declaration} node.
 *
 * @param {object} [defaults] Properties for the new node.
 *
 * @return {Declaration} new declaration node
 *
 * @example
 * postcss.decl({ prop: 'color', value: 'red' }).toString() //=> "color: red"
 */postcss.decl=function(defaults){return new _declaration["default"](defaults);};/**
 * Creates a new {@link Rule} node.
 *
 * @param {object} [defaults] Properties for the new node.
 *
 * @return {Rule} new rule node
 *
 * @example
 * postcss.rule({ selector: 'a' }).toString() //=> "a {\n}"
 */postcss.rule=function(defaults){return new _rule["default"](defaults);};/**
 * Creates a new {@link Root} node.
 *
 * @param {object} [defaults] Properties for the new node.
 *
 * @return {Root} new root node.
 *
 * @example
 * postcss.root({ after: '\n' }).toString() //=> "\n"
 */postcss.root=function(defaults){return new _root["default"](defaults);};var _default=postcss;exports["default"]=_default;module.exports=exports["default"];},{"./at-rule":169,"./comment":170,"./declaration":173,"./list":176,"./parse":179,"./processor":183,"./root":185,"./rule":186,"./stringify":188,"./vendor":190}],182:[function(require,module,exports){(function(Buffer){"use strict";exports.__esModule=true;exports["default"]=void 0;var _sourceMap=_interopRequireDefault(require("source-map"));var _path=_interopRequireDefault(require("path"));var _fs=_interopRequireDefault(require("fs"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}function fromBase64(str){if(Buffer){return Buffer.from(str,'base64').toString();}else{return window.atob(str);}}/**
 * Source map information from input CSS.
 * For example, source map after Sass compiler.
 *
 * This class will automatically find source map in input CSS or in file system
 * near input file (according `from` option).
 *
 * @example
 * const root = postcss.parse(css, { from: 'a.sass.css' })
 * root.input.map //=> PreviousMap
 */var PreviousMap=/*#__PURE__*/function(){/**
   * @param {string}         css    Input CSS source.
   * @param {processOptions} [opts] {@link Processor#process} options.
   */function PreviousMap(css,opts){this.loadAnnotation(css);/**
     * Was source map inlined by data-uri to input CSS.
     *
     * @type {boolean}
     */this.inline=this.startWith(this.annotation,'data:');var prev=opts.map?opts.map.prev:undefined;var text=this.loadMap(opts.from,prev);if(text)this.text=text;}/**
   * Create a instance of `SourceMapGenerator` class
   * from the `source-map` library to work with source map information.
   *
   * It is lazy method, so it will create object only on first call
   * and then it will use cache.
   *
   * @return {SourceMapGenerator} Object with source map information.
   */var _proto=PreviousMap.prototype;_proto.consumer=function consumer(){if(!this.consumerCache){this.consumerCache=new _sourceMap["default"].SourceMapConsumer(this.text);}return this.consumerCache;}/**
   * Does source map contains `sourcesContent` with input source text.
   *
   * @return {boolean} Is `sourcesContent` present.
   */;_proto.withContent=function withContent(){return!!(this.consumer().sourcesContent&&this.consumer().sourcesContent.length>0);};_proto.startWith=function startWith(string,start){if(!string)return false;return string.substr(0,start.length)===start;};_proto.getAnnotationURL=function getAnnotationURL(sourceMapString){return sourceMapString.match(/\/\*\s*# sourceMappingURL=(.*)\s*\*\//)[1].trim();};_proto.loadAnnotation=function loadAnnotation(css){var annotations=css.match(/\/\*\s*# sourceMappingURL=(.*)\s*\*\//mg);if(annotations&&annotations.length>0){// Locate the last sourceMappingURL to avoid picking up
// sourceMappingURLs from comments, strings, etc.
var lastAnnotation=annotations[annotations.length-1];if(lastAnnotation){this.annotation=this.getAnnotationURL(lastAnnotation);}}};_proto.decodeInline=function decodeInline(text){var baseCharsetUri=/^data:application\/json;charset=utf-?8;base64,/;var baseUri=/^data:application\/json;base64,/;var uri='data:application/json,';if(this.startWith(text,uri)){return decodeURIComponent(text.substr(uri.length));}if(baseCharsetUri.test(text)||baseUri.test(text)){return fromBase64(text.substr(RegExp.lastMatch.length));}var encoding=text.match(/data:application\/json;([^,]+),/)[1];throw new Error('Unsupported source map encoding '+encoding);};_proto.loadMap=function loadMap(file,prev){if(prev===false)return false;if(prev){if(typeof prev==='string'){return prev;}else if(typeof prev==='function'){var prevPath=prev(file);if(prevPath&&_fs["default"].existsSync&&_fs["default"].existsSync(prevPath)){return _fs["default"].readFileSync(prevPath,'utf-8').toString().trim();}else{throw new Error('Unable to load previous source map: '+prevPath.toString());}}else if(prev instanceof _sourceMap["default"].SourceMapConsumer){return _sourceMap["default"].SourceMapGenerator.fromSourceMap(prev).toString();}else if(prev instanceof _sourceMap["default"].SourceMapGenerator){return prev.toString();}else if(this.isMap(prev)){return JSON.stringify(prev);}else{throw new Error('Unsupported previous source map format: '+prev.toString());}}else if(this.inline){return this.decodeInline(this.annotation);}else if(this.annotation){var map=this.annotation;if(file)map=_path["default"].join(_path["default"].dirname(file),map);this.root=_path["default"].dirname(map);if(_fs["default"].existsSync&&_fs["default"].existsSync(map)){return _fs["default"].readFileSync(map,'utf-8').toString().trim();}else{return false;}}};_proto.isMap=function isMap(map){if(_typeof(map)!=='object')return false;return typeof map.mappings==='string'||typeof map._mappings==='string';};return PreviousMap;}();var _default=PreviousMap;exports["default"]=_default;module.exports=exports["default"];}).call(this,require("buffer").Buffer);},{"buffer":3,"fs":2,"path":168,"source-map":208}],183:[function(require,module,exports){(function(process){"use strict";exports.__esModule=true;exports["default"]=void 0;var _lazyResult=_interopRequireDefault(require("./lazy-result"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}function _createForOfIteratorHelperLoose(o,allowArrayLike){var it;if(typeof Symbol==="undefined"||o[Symbol.iterator]==null){if(Array.isArray(o)||(it=_unsupportedIterableToArray(o))||allowArrayLike&&o&&typeof o.length==="number"){if(it)o=it;var i=0;return function(){if(i>=o.length)return{done:true};return{done:false,value:o[i++]};};}throw new TypeError("Invalid attempt to iterate non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");}it=o[Symbol.iterator]();return it.next.bind(it);}function _unsupportedIterableToArray(o,minLen){if(!o)return;if(typeof o==="string")return _arrayLikeToArray(o,minLen);var n=Object.prototype.toString.call(o).slice(8,-1);if(n==="Object"&&o.constructor)n=o.constructor.name;if(n==="Map"||n==="Set")return Array.from(o);if(n==="Arguments"||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n))return _arrayLikeToArray(o,minLen);}function _arrayLikeToArray(arr,len){if(len==null||len>arr.length)len=arr.length;for(var i=0,arr2=new Array(len);i<len;i++){arr2[i]=arr[i];}return arr2;}/**
 * Contains plugins to process CSS. Create one `Processor` instance,
 * initialize its plugins, and then use that instance on numerous CSS files.
 *
 * @example
 * const processor = postcss([autoprefixer, precss])
 * processor.process(css1).then(result => console.log(result.css))
 * processor.process(css2).then(result => console.log(result.css))
 */var Processor=/*#__PURE__*/function(){/**
   * @param {Array.<Plugin|pluginFunction>|Processor} plugins PostCSS plugins.
   *        See {@link Processor#use} for plugin format.
   */function Processor(plugins){if(plugins===void 0){plugins=[];}/**
     * Current PostCSS version.
     *
     * @type {string}
     *
     * @example
     * if (result.processor.version.split('.')[0] !== '6') {
     *   throw new Error('This plugin works only with PostCSS 6')
     * }
     */this.version='7.0.34';/**
     * Plugins added to this processor.
     *
     * @type {pluginFunction[]}
     *
     * @example
     * const processor = postcss([autoprefixer, precss])
     * processor.plugins.length //=> 2
     */this.plugins=this.normalize(plugins);}/**
   * Adds a plugin to be used as a CSS processor.
   *
   * PostCSS plugin can be in 4 formats:
   * * A plugin created by {@link postcss.plugin} method.
   * * A function. PostCSS will pass the function a @{link Root}
   *   as the first argument and current {@link Result} instance
   *   as the second.
   * * An object with a `postcss` method. PostCSS will use that method
   *   as described in #2.
   * * Another {@link Processor} instance. PostCSS will copy plugins
   *   from that instance into this one.
   *
   * Plugins can also be added by passing them as arguments when creating
   * a `postcss` instance (see [`postcss(plugins)`]).
   *
   * Asynchronous plugins should return a `Promise` instance.
   *
   * @param {Plugin|pluginFunction|Processor} plugin PostCSS plugin
   *                                                 or {@link Processor}
   *                                                 with plugins.
   *
   * @example
   * const processor = postcss()
   *   .use(autoprefixer)
   *   .use(precss)
   *
   * @return {Processes} Current processor to make methods chain.
   */var _proto=Processor.prototype;_proto.use=function use(plugin){this.plugins=this.plugins.concat(this.normalize([plugin]));return this;}/**
   * Parses source CSS and returns a {@link LazyResult} Promise proxy.
   * Because some plugins can be asynchronous it doesn’t make
   * any transformations. Transformations will be applied
   * in the {@link LazyResult} methods.
   *
   * @param {string|toString|Result} css String with input CSS or any object
   *                                     with a `toString()` method,
   *                                     like a Buffer. Optionally, send
   *                                     a {@link Result} instance
   *                                     and the processor will take
   *                                     the {@link Root} from it.
   * @param {processOptions} [opts]      Options.
   *
   * @return {LazyResult} Promise proxy.
   *
   * @example
   * processor.process(css, { from: 'a.css', to: 'a.out.css' })
   *   .then(result => {
   *      console.log(result.css)
   *   })
   */;_proto.process=function(_process){function process(_x){return _process.apply(this,arguments);}process.toString=function(){return _process.toString();};return process;}(function(css,opts){if(opts===void 0){opts={};}if(this.plugins.length===0&&opts.parser===opts.stringifier){if(process.env.NODE_ENV!=='production'){if(typeof console!=='undefined'&&console.warn){console.warn('You did not set any plugins, parser, or stringifier. '+'Right now, PostCSS does nothing. Pick plugins for your case '+'on https://www.postcss.parts/ and use them in postcss.config.js.');}}}return new _lazyResult["default"](this,css,opts);});_proto.normalize=function normalize(plugins){var normalized=[];for(var _iterator=_createForOfIteratorHelperLoose(plugins),_step;!(_step=_iterator()).done;){var i=_step.value;if(i.postcss===true){var plugin=i();throw new Error('PostCSS plugin '+plugin.postcssPlugin+' requires PostCSS 8. Update PostCSS or downgrade this plugin.');}if(i.postcss)i=i.postcss;if(_typeof(i)==='object'&&Array.isArray(i.plugins)){normalized=normalized.concat(i.plugins);}else if(typeof i==='function'){normalized.push(i);}else if(_typeof(i)==='object'&&(i.parse||i.stringify)){if(process.env.NODE_ENV!=='production'){throw new Error('PostCSS syntaxes cannot be used as plugins. Instead, please use '+'one of the syntax/parser/stringifier options as outlined '+'in your PostCSS runner documentation.');}}else if(_typeof(i)==='object'&&i.postcssPlugin){throw new Error('PostCSS plugin '+i.postcssPlugin+' requires PostCSS 8. Update PostCSS or downgrade this plugin.');}else{throw new Error(i+' is not a PostCSS plugin');}}return normalized;};return Processor;}();var _default=Processor;/**
 * @callback builder
 * @param {string} part          Part of generated CSS connected to this node.
 * @param {Node}   node          AST node.
 * @param {"start"|"end"} [type] Node’s part type.
 */ /**
 * @callback parser
 *
 * @param {string|toString} css   String with input CSS or any object
 *                                with toString() method, like a Buffer.
 * @param {processOptions} [opts] Options with only `from` and `map` keys.
 *
 * @return {Root} PostCSS AST
 */ /**
 * @callback stringifier
 *
 * @param {Node} node       Start node for stringifing. Usually {@link Root}.
 * @param {builder} builder Function to concatenate CSS from node’s parts
 *                          or generate string and source map.
 *
 * @return {void}
 */ /**
 * @typedef {object} syntax
 * @property {parser} parse          Function to generate AST by string.
 * @property {stringifier} stringify Function to generate string by AST.
 */ /**
 * @typedef {object} toString
 * @property {function} toString
 */ /**
 * @callback pluginFunction
 * @param {Root} root     Parsed input CSS.
 * @param {Result} result Result to set warnings or check other plugins.
 */ /**
 * @typedef {object} Plugin
 * @property {function} postcss PostCSS plugin function.
 */ /**
 * @typedef {object} processOptions
 * @property {string} from             The path of the CSS source file.
 *                                     You should always set `from`,
 *                                     because it is used in source map
 *                                     generation and syntax error messages.
 * @property {string} to               The path where you’ll put the output
 *                                     CSS file. You should always set `to`
 *                                     to generate correct source maps.
 * @property {parser} parser           Function to generate AST by string.
 * @property {stringifier} stringifier Class to generate string by AST.
 * @property {syntax} syntax           Object with `parse` and `stringify`.
 * @property {object} map              Source map options.
 * @property {boolean} map.inline                    Does source map should
 *                                                   be embedded in the output
 *                                                   CSS as a base64-encoded
 *                                                   comment.
 * @property {string|object|false|function} map.prev Source map content
 *                                                   from a previous
 *                                                   processing step
 *                                                   (for example, Sass).
 *                                                   PostCSS will try to find
 *                                                   previous map automatically,
 *                                                   so you could disable it by
 *                                                   `false` value.
 * @property {boolean} map.sourcesContent            Does PostCSS should set
 *                                                   the origin content to map.
 * @property {string|false} map.annotation           Does PostCSS should set
 *                                                   annotation comment to map.
 * @property {string} map.from                       Override `from` in map’s
 *                                                   sources`.
 */exports["default"]=_default;module.exports=exports["default"];}).call(this,require('_process'));},{"./lazy-result":175,"_process":193}],184:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=void 0;var _warning=_interopRequireDefault(require("./warning"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}function _defineProperties(target,props){for(var i=0;i<props.length;i++){var descriptor=props[i];descriptor.enumerable=descriptor.enumerable||false;descriptor.configurable=true;if("value"in descriptor)descriptor.writable=true;Object.defineProperty(target,descriptor.key,descriptor);}}function _createClass(Constructor,protoProps,staticProps){if(protoProps)_defineProperties(Constructor.prototype,protoProps);if(staticProps)_defineProperties(Constructor,staticProps);return Constructor;}/**
 * Provides the result of the PostCSS transformations.
 *
 * A Result instance is returned by {@link LazyResult#then}
 * or {@link Root#toResult} methods.
 *
 * @example
 * postcss([autoprefixer]).process(css).then(result => {
 *  console.log(result.css)
 * })
 *
 * @example
 * const result2 = postcss.parse(css).toResult()
 */var Result=/*#__PURE__*/function(){/**
   * @param {Processor} processor Processor used for this transformation.
   * @param {Root}      root      Root node after all transformations.
   * @param {processOptions} opts Options from the {@link Processor#process}
   *                              or {@link Root#toResult}.
   */function Result(processor,root,opts){/**
     * The Processor instance used for this transformation.
     *
     * @type {Processor}
     *
     * @example
     * for (const plugin of result.processor.plugins) {
     *   if (plugin.postcssPlugin === 'postcss-bad') {
     *     throw 'postcss-good is incompatible with postcss-bad'
     *   }
     * })
     */this.processor=processor;/**
     * Contains messages from plugins (e.g., warnings or custom messages).
     * Each message should have type and plugin properties.
     *
     * @type {Message[]}
     *
     * @example
     * postcss.plugin('postcss-min-browser', () => {
     *   return (root, result) => {
     *     const browsers = detectMinBrowsersByCanIUse(root)
     *     result.messages.push({
     *       type: 'min-browser',
     *       plugin: 'postcss-min-browser',
     *       browsers
     *     })
     *   }
     * })
     */this.messages=[];/**
     * Root node after all transformations.
     *
     * @type {Root}
     *
     * @example
     * root.toResult().root === root
     */this.root=root;/**
     * Options from the {@link Processor#process} or {@link Root#toResult} call
     * that produced this Result instance.
     *
     * @type {processOptions}
     *
     * @example
     * root.toResult(opts).opts === opts
     */this.opts=opts;/**
     * A CSS string representing of {@link Result#root}.
     *
     * @type {string}
     *
     * @example
     * postcss.parse('a{}').toResult().css //=> "a{}"
     */this.css=undefined;/**
     * An instance of `SourceMapGenerator` class from the `source-map` library,
     * representing changes to the {@link Result#root} instance.
     *
     * @type {SourceMapGenerator}
     *
     * @example
     * result.map.toJSON() //=> { version: 3, file: 'a.css', … }
     *
     * @example
     * if (result.map) {
     *   fs.writeFileSync(result.opts.to + '.map', result.map.toString())
     * }
     */this.map=undefined;}/**
   * Returns for @{link Result#css} content.
   *
   * @example
   * result + '' === result.css
   *
   * @return {string} String representing of {@link Result#root}.
   */var _proto=Result.prototype;_proto.toString=function toString(){return this.css;}/**
   * Creates an instance of {@link Warning} and adds it
   * to {@link Result#messages}.
   *
   * @param {string} text        Warning message.
   * @param {Object} [opts]      Warning options.
   * @param {Node}   opts.node   CSS node that caused the warning.
   * @param {string} opts.word   Word in CSS source that caused the warning.
   * @param {number} opts.index  Index in CSS node string that caused
   *                             the warning.
   * @param {string} opts.plugin Name of the plugin that created
   *                             this warning. {@link Result#warn} fills
   *                             this property automatically.
   *
   * @return {Warning} Created warning.
   */;_proto.warn=function warn(text,opts){if(opts===void 0){opts={};}if(!opts.plugin){if(this.lastPlugin&&this.lastPlugin.postcssPlugin){opts.plugin=this.lastPlugin.postcssPlugin;}}var warning=new _warning["default"](text,opts);this.messages.push(warning);return warning;}/**
     * Returns warnings from plugins. Filters {@link Warning} instances
     * from {@link Result#messages}.
     *
     * @example
     * result.warnings().forEach(warn => {
     *   console.warn(warn.toString())
     * })
     *
     * @return {Warning[]} Warnings from plugins.
     */;_proto.warnings=function warnings(){return this.messages.filter(function(i){return i.type==='warning';});}/**
   * An alias for the {@link Result#css} property.
   * Use it with syntaxes that generate non-CSS output.
   *
   * @type {string}
   *
   * @example
   * result.css === result.content
   */;_createClass(Result,[{key:"content",get:function get(){return this.css;}}]);return Result;}();var _default=Result;/**
 * @typedef  {object} Message
 * @property {string} type   Message type.
 * @property {string} plugin Source PostCSS plugin name.
 */exports["default"]=_default;module.exports=exports["default"];},{"./warning":192}],185:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=void 0;var _container=_interopRequireDefault(require("./container"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}function _createForOfIteratorHelperLoose(o,allowArrayLike){var it;if(typeof Symbol==="undefined"||o[Symbol.iterator]==null){if(Array.isArray(o)||(it=_unsupportedIterableToArray(o))||allowArrayLike&&o&&typeof o.length==="number"){if(it)o=it;var i=0;return function(){if(i>=o.length)return{done:true};return{done:false,value:o[i++]};};}throw new TypeError("Invalid attempt to iterate non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");}it=o[Symbol.iterator]();return it.next.bind(it);}function _unsupportedIterableToArray(o,minLen){if(!o)return;if(typeof o==="string")return _arrayLikeToArray(o,minLen);var n=Object.prototype.toString.call(o).slice(8,-1);if(n==="Object"&&o.constructor)n=o.constructor.name;if(n==="Map"||n==="Set")return Array.from(o);if(n==="Arguments"||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n))return _arrayLikeToArray(o,minLen);}function _arrayLikeToArray(arr,len){if(len==null||len>arr.length)len=arr.length;for(var i=0,arr2=new Array(len);i<len;i++){arr2[i]=arr[i];}return arr2;}function _inheritsLoose(subClass,superClass){subClass.prototype=Object.create(superClass.prototype);subClass.prototype.constructor=subClass;subClass.__proto__=superClass;}/**
 * Represents a CSS file and contains all its parsed nodes.
 *
 * @extends Container
 *
 * @example
 * const root = postcss.parse('a{color:black} b{z-index:2}')
 * root.type         //=> 'root'
 * root.nodes.length //=> 2
 */var Root=/*#__PURE__*/function(_Container){_inheritsLoose(Root,_Container);function Root(defaults){var _this;_this=_Container.call(this,defaults)||this;_this.type='root';if(!_this.nodes)_this.nodes=[];return _this;}var _proto=Root.prototype;_proto.removeChild=function removeChild(child,ignore){var index=this.index(child);if(!ignore&&index===0&&this.nodes.length>1){this.nodes[1].raws.before=this.nodes[index].raws.before;}return _Container.prototype.removeChild.call(this,child);};_proto.normalize=function normalize(child,sample,type){var nodes=_Container.prototype.normalize.call(this,child);if(sample){if(type==='prepend'){if(this.nodes.length>1){sample.raws.before=this.nodes[1].raws.before;}else{delete sample.raws.before;}}else if(this.first!==sample){for(var _iterator=_createForOfIteratorHelperLoose(nodes),_step;!(_step=_iterator()).done;){var node=_step.value;node.raws.before=sample.raws.before;}}}return nodes;}/**
   * Returns a {@link Result} instance representing the root’s CSS.
   *
   * @param {processOptions} [opts] Options with only `to` and `map` keys.
   *
   * @return {Result} Result with current root’s CSS.
   *
   * @example
   * const root1 = postcss.parse(css1, { from: 'a.css' })
   * const root2 = postcss.parse(css2, { from: 'b.css' })
   * root1.append(root2)
   * const result = root1.toResult({ to: 'all.css', map: true })
   */;_proto.toResult=function toResult(opts){if(opts===void 0){opts={};}var LazyResult=require('./lazy-result');var Processor=require('./processor');var lazy=new LazyResult(new Processor(),this,opts);return lazy.stringify();}/**
   * @memberof Root#
   * @member {object} raws Information to generate byte-to-byte equal
   *                       node string as it was in the origin input.
   *
   * Every parser saves its own properties,
   * but the default CSS parser uses:
   *
   * * `after`: the space symbols after the last child to the end of file.
   * * `semicolon`: is the last child has an (optional) semicolon.
   *
   * @example
   * postcss.parse('a {}\n').raws //=> { after: '\n' }
   * postcss.parse('a {}').raws   //=> { after: '' }
   */;return Root;}(_container["default"]);var _default=Root;exports["default"]=_default;module.exports=exports["default"];},{"./container":171,"./lazy-result":175,"./processor":183}],186:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=void 0;var _container=_interopRequireDefault(require("./container"));var _list=_interopRequireDefault(require("./list"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}function _defineProperties(target,props){for(var i=0;i<props.length;i++){var descriptor=props[i];descriptor.enumerable=descriptor.enumerable||false;descriptor.configurable=true;if("value"in descriptor)descriptor.writable=true;Object.defineProperty(target,descriptor.key,descriptor);}}function _createClass(Constructor,protoProps,staticProps){if(protoProps)_defineProperties(Constructor.prototype,protoProps);if(staticProps)_defineProperties(Constructor,staticProps);return Constructor;}function _inheritsLoose(subClass,superClass){subClass.prototype=Object.create(superClass.prototype);subClass.prototype.constructor=subClass;subClass.__proto__=superClass;}/**
 * Represents a CSS rule: a selector followed by a declaration block.
 *
 * @extends Container
 *
 * @example
 * const root = postcss.parse('a{}')
 * const rule = root.first
 * rule.type       //=> 'rule'
 * rule.toString() //=> 'a{}'
 */var Rule=/*#__PURE__*/function(_Container){_inheritsLoose(Rule,_Container);function Rule(defaults){var _this;_this=_Container.call(this,defaults)||this;_this.type='rule';if(!_this.nodes)_this.nodes=[];return _this;}/**
   * An array containing the rule’s individual selectors.
   * Groups of selectors are split at commas.
   *
   * @type {string[]}
   *
   * @example
   * const root = postcss.parse('a, b { }')
   * const rule = root.first
   *
   * rule.selector  //=> 'a, b'
   * rule.selectors //=> ['a', 'b']
   *
   * rule.selectors = ['a', 'strong']
   * rule.selector //=> 'a, strong'
   */_createClass(Rule,[{key:"selectors",get:function get(){return _list["default"].comma(this.selector);},set:function set(values){var match=this.selector?this.selector.match(/,\s*/):null;var sep=match?match[0]:','+this.raw('between','beforeOpen');this.selector=values.join(sep);}/**
     * @memberof Rule#
     * @member {string} selector The rule’s full selector represented
     *                           as a string.
     *
     * @example
     * const root = postcss.parse('a, b { }')
     * const rule = root.first
     * rule.selector //=> 'a, b'
     */ /**
     * @memberof Rule#
     * @member {object} raws Information to generate byte-to-byte equal
     *                       node string as it was in the origin input.
     *
     * Every parser saves its own properties,
     * but the default CSS parser uses:
     *
     * * `before`: the space symbols before the node. It also stores `*`
     *   and `_` symbols before the declaration (IE hack).
     * * `after`: the space symbols after the last child of the node
     *   to the end of the node.
     * * `between`: the symbols between the property and value
     *   for declarations, selector and `{` for rules, or last parameter
     *   and `{` for at-rules.
     * * `semicolon`: contains `true` if the last child has
     *   an (optional) semicolon.
     * * `ownSemicolon`: contains `true` if there is semicolon after rule.
     *
     * PostCSS cleans selectors from comments and extra spaces,
     * but it stores origin content in raws properties.
     * As such, if you don’t change a declaration’s value,
     * PostCSS will use the raw value with comments.
     *
     * @example
     * const root = postcss.parse('a {\n  color:black\n}')
     * root.first.first.raws //=> { before: '', between: ' ', after: '\n' }
     */}]);return Rule;}(_container["default"]);var _default=Rule;exports["default"]=_default;module.exports=exports["default"];},{"./container":171,"./list":176}],187:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=void 0;var DEFAULT_RAW={colon:': ',indent:'    ',beforeDecl:'\n',beforeRule:'\n',beforeOpen:' ',beforeClose:'\n',beforeComment:'\n',after:'\n',emptyBody:'',commentLeft:' ',commentRight:' ',semicolon:false};function capitalize(str){return str[0].toUpperCase()+str.slice(1);}var Stringifier=/*#__PURE__*/function(){function Stringifier(builder){this.builder=builder;}var _proto=Stringifier.prototype;_proto.stringify=function stringify(node,semicolon){this[node.type](node,semicolon);};_proto.root=function root(node){this.body(node);if(node.raws.after)this.builder(node.raws.after);};_proto.comment=function comment(node){var left=this.raw(node,'left','commentLeft');var right=this.raw(node,'right','commentRight');this.builder('/*'+left+node.text+right+'*/',node);};_proto.decl=function decl(node,semicolon){var between=this.raw(node,'between','colon');var string=node.prop+between+this.rawValue(node,'value');if(node.important){string+=node.raws.important||' !important';}if(semicolon)string+=';';this.builder(string,node);};_proto.rule=function rule(node){this.block(node,this.rawValue(node,'selector'));if(node.raws.ownSemicolon){this.builder(node.raws.ownSemicolon,node,'end');}};_proto.atrule=function atrule(node,semicolon){var name='@'+node.name;var params=node.params?this.rawValue(node,'params'):'';if(typeof node.raws.afterName!=='undefined'){name+=node.raws.afterName;}else if(params){name+=' ';}if(node.nodes){this.block(node,name+params);}else{var end=(node.raws.between||'')+(semicolon?';':'');this.builder(name+params+end,node);}};_proto.body=function body(node){var last=node.nodes.length-1;while(last>0){if(node.nodes[last].type!=='comment')break;last-=1;}var semicolon=this.raw(node,'semicolon');for(var i=0;i<node.nodes.length;i++){var child=node.nodes[i];var before=this.raw(child,'before');if(before)this.builder(before);this.stringify(child,last!==i||semicolon);}};_proto.block=function block(node,start){var between=this.raw(node,'between','beforeOpen');this.builder(start+between+'{',node,'start');var after;if(node.nodes&&node.nodes.length){this.body(node);after=this.raw(node,'after');}else{after=this.raw(node,'after','emptyBody');}if(after)this.builder(after);this.builder('}',node,'end');};_proto.raw=function raw(node,own,detect){var value;if(!detect)detect=own;// Already had
if(own){value=node.raws[own];if(typeof value!=='undefined')return value;}var parent=node.parent;// Hack for first rule in CSS
if(detect==='before'){if(!parent||parent.type==='root'&&parent.first===node){return'';}}// Floating child without parent
if(!parent)return DEFAULT_RAW[detect];// Detect style by other nodes
var root=node.root();if(!root.rawCache)root.rawCache={};if(typeof root.rawCache[detect]!=='undefined'){return root.rawCache[detect];}if(detect==='before'||detect==='after'){return this.beforeAfter(node,detect);}else{var method='raw'+capitalize(detect);if(this[method]){value=this[method](root,node);}else{root.walk(function(i){value=i.raws[own];if(typeof value!=='undefined')return false;});}}if(typeof value==='undefined')value=DEFAULT_RAW[detect];root.rawCache[detect]=value;return value;};_proto.rawSemicolon=function rawSemicolon(root){var value;root.walk(function(i){if(i.nodes&&i.nodes.length&&i.last.type==='decl'){value=i.raws.semicolon;if(typeof value!=='undefined')return false;}});return value;};_proto.rawEmptyBody=function rawEmptyBody(root){var value;root.walk(function(i){if(i.nodes&&i.nodes.length===0){value=i.raws.after;if(typeof value!=='undefined')return false;}});return value;};_proto.rawIndent=function rawIndent(root){if(root.raws.indent)return root.raws.indent;var value;root.walk(function(i){var p=i.parent;if(p&&p!==root&&p.parent&&p.parent===root){if(typeof i.raws.before!=='undefined'){var parts=i.raws.before.split('\n');value=parts[parts.length-1];value=value.replace(/[^\s]/g,'');return false;}}});return value;};_proto.rawBeforeComment=function rawBeforeComment(root,node){var value;root.walkComments(function(i){if(typeof i.raws.before!=='undefined'){value=i.raws.before;if(value.indexOf('\n')!==-1){value=value.replace(/[^\n]+$/,'');}return false;}});if(typeof value==='undefined'){value=this.raw(node,null,'beforeDecl');}else if(value){value=value.replace(/[^\s]/g,'');}return value;};_proto.rawBeforeDecl=function rawBeforeDecl(root,node){var value;root.walkDecls(function(i){if(typeof i.raws.before!=='undefined'){value=i.raws.before;if(value.indexOf('\n')!==-1){value=value.replace(/[^\n]+$/,'');}return false;}});if(typeof value==='undefined'){value=this.raw(node,null,'beforeRule');}else if(value){value=value.replace(/[^\s]/g,'');}return value;};_proto.rawBeforeRule=function rawBeforeRule(root){var value;root.walk(function(i){if(i.nodes&&(i.parent!==root||root.first!==i)){if(typeof i.raws.before!=='undefined'){value=i.raws.before;if(value.indexOf('\n')!==-1){value=value.replace(/[^\n]+$/,'');}return false;}}});if(value)value=value.replace(/[^\s]/g,'');return value;};_proto.rawBeforeClose=function rawBeforeClose(root){var value;root.walk(function(i){if(i.nodes&&i.nodes.length>0){if(typeof i.raws.after!=='undefined'){value=i.raws.after;if(value.indexOf('\n')!==-1){value=value.replace(/[^\n]+$/,'');}return false;}}});if(value)value=value.replace(/[^\s]/g,'');return value;};_proto.rawBeforeOpen=function rawBeforeOpen(root){var value;root.walk(function(i){if(i.type!=='decl'){value=i.raws.between;if(typeof value!=='undefined')return false;}});return value;};_proto.rawColon=function rawColon(root){var value;root.walkDecls(function(i){if(typeof i.raws.between!=='undefined'){value=i.raws.between.replace(/[^\s:]/g,'');return false;}});return value;};_proto.beforeAfter=function beforeAfter(node,detect){var value;if(node.type==='decl'){value=this.raw(node,null,'beforeDecl');}else if(node.type==='comment'){value=this.raw(node,null,'beforeComment');}else if(detect==='before'){value=this.raw(node,null,'beforeRule');}else{value=this.raw(node,null,'beforeClose');}var buf=node.parent;var depth=0;while(buf&&buf.type!=='root'){depth+=1;buf=buf.parent;}if(value.indexOf('\n')!==-1){var indent=this.raw(node,null,'indent');if(indent.length){for(var step=0;step<depth;step++){value+=indent;}}}return value;};_proto.rawValue=function rawValue(node,prop){var value=node[prop];var raw=node.raws[prop];if(raw&&raw.value===value){return raw.raw;}return value;};return Stringifier;}();var _default=Stringifier;exports["default"]=_default;module.exports=exports["default"];},{}],188:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=void 0;var _stringifier=_interopRequireDefault(require("./stringifier"));function _interopRequireDefault(obj){return obj&&obj.__esModule?obj:{"default":obj};}function stringify(node,builder){var str=new _stringifier["default"](builder);str.stringify(node);}var _default=stringify;exports["default"]=_default;module.exports=exports["default"];},{"./stringifier":187}],189:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=tokenizer;var SINGLE_QUOTE='\''.charCodeAt(0);var DOUBLE_QUOTE='"'.charCodeAt(0);var BACKSLASH='\\'.charCodeAt(0);var SLASH='/'.charCodeAt(0);var NEWLINE='\n'.charCodeAt(0);var SPACE=' '.charCodeAt(0);var FEED='\f'.charCodeAt(0);var TAB='\t'.charCodeAt(0);var CR='\r'.charCodeAt(0);var OPEN_SQUARE='['.charCodeAt(0);var CLOSE_SQUARE=']'.charCodeAt(0);var OPEN_PARENTHESES='('.charCodeAt(0);var CLOSE_PARENTHESES=')'.charCodeAt(0);var OPEN_CURLY='{'.charCodeAt(0);var CLOSE_CURLY='}'.charCodeAt(0);var SEMICOLON=';'.charCodeAt(0);var ASTERISK='*'.charCodeAt(0);var COLON=':'.charCodeAt(0);var AT='@'.charCodeAt(0);var RE_AT_END=/[ \n\t\r\f{}()'"\\;/[\]#]/g;var RE_WORD_END=/[ \n\t\r\f(){}:;@!'"\\\][#]|\/(?=\*)/g;var RE_BAD_BRACKET=/.[\\/("'\n]/;var RE_HEX_ESCAPE=/[a-f0-9]/i;function tokenizer(input,options){if(options===void 0){options={};}var css=input.css.valueOf();var ignore=options.ignoreErrors;var code,next,quote,lines,last,content,escape;var nextLine,nextOffset,escaped,escapePos,prev,n,currentToken;var length=css.length;var offset=-1;var line=1;var pos=0;var buffer=[];var returned=[];function position(){return pos;}function unclosed(what){throw input.error('Unclosed '+what,line,pos-offset);}function endOfFile(){return returned.length===0&&pos>=length;}function nextToken(opts){if(returned.length)return returned.pop();if(pos>=length)return;var ignoreUnclosed=opts?opts.ignoreUnclosed:false;code=css.charCodeAt(pos);if(code===NEWLINE||code===FEED||code===CR&&css.charCodeAt(pos+1)!==NEWLINE){offset=pos;line+=1;}switch(code){case NEWLINE:case SPACE:case TAB:case CR:case FEED:next=pos;do{next+=1;code=css.charCodeAt(next);if(code===NEWLINE){offset=next;line+=1;}}while(code===SPACE||code===NEWLINE||code===TAB||code===CR||code===FEED);currentToken=['space',css.slice(pos,next)];pos=next-1;break;case OPEN_SQUARE:case CLOSE_SQUARE:case OPEN_CURLY:case CLOSE_CURLY:case COLON:case SEMICOLON:case CLOSE_PARENTHESES:var controlChar=String.fromCharCode(code);currentToken=[controlChar,controlChar,line,pos-offset];break;case OPEN_PARENTHESES:prev=buffer.length?buffer.pop()[1]:'';n=css.charCodeAt(pos+1);if(prev==='url'&&n!==SINGLE_QUOTE&&n!==DOUBLE_QUOTE&&n!==SPACE&&n!==NEWLINE&&n!==TAB&&n!==FEED&&n!==CR){next=pos;do{escaped=false;next=css.indexOf(')',next+1);if(next===-1){if(ignore||ignoreUnclosed){next=pos;break;}else{unclosed('bracket');}}escapePos=next;while(css.charCodeAt(escapePos-1)===BACKSLASH){escapePos-=1;escaped=!escaped;}}while(escaped);currentToken=['brackets',css.slice(pos,next+1),line,pos-offset,line,next-offset];pos=next;}else{next=css.indexOf(')',pos+1);content=css.slice(pos,next+1);if(next===-1||RE_BAD_BRACKET.test(content)){currentToken=['(','(',line,pos-offset];}else{currentToken=['brackets',content,line,pos-offset,line,next-offset];pos=next;}}break;case SINGLE_QUOTE:case DOUBLE_QUOTE:quote=code===SINGLE_QUOTE?'\'':'"';next=pos;do{escaped=false;next=css.indexOf(quote,next+1);if(next===-1){if(ignore||ignoreUnclosed){next=pos+1;break;}else{unclosed('string');}}escapePos=next;while(css.charCodeAt(escapePos-1)===BACKSLASH){escapePos-=1;escaped=!escaped;}}while(escaped);content=css.slice(pos,next+1);lines=content.split('\n');last=lines.length-1;if(last>0){nextLine=line+last;nextOffset=next-lines[last].length;}else{nextLine=line;nextOffset=offset;}currentToken=['string',css.slice(pos,next+1),line,pos-offset,nextLine,next-nextOffset];offset=nextOffset;line=nextLine;pos=next;break;case AT:RE_AT_END.lastIndex=pos+1;RE_AT_END.test(css);if(RE_AT_END.lastIndex===0){next=css.length-1;}else{next=RE_AT_END.lastIndex-2;}currentToken=['at-word',css.slice(pos,next+1),line,pos-offset,line,next-offset];pos=next;break;case BACKSLASH:next=pos;escape=true;while(css.charCodeAt(next+1)===BACKSLASH){next+=1;escape=!escape;}code=css.charCodeAt(next+1);if(escape&&code!==SLASH&&code!==SPACE&&code!==NEWLINE&&code!==TAB&&code!==CR&&code!==FEED){next+=1;if(RE_HEX_ESCAPE.test(css.charAt(next))){while(RE_HEX_ESCAPE.test(css.charAt(next+1))){next+=1;}if(css.charCodeAt(next+1)===SPACE){next+=1;}}}currentToken=['word',css.slice(pos,next+1),line,pos-offset,line,next-offset];pos=next;break;default:if(code===SLASH&&css.charCodeAt(pos+1)===ASTERISK){next=css.indexOf('*/',pos+2)+1;if(next===0){if(ignore||ignoreUnclosed){next=css.length;}else{unclosed('comment');}}content=css.slice(pos,next+1);lines=content.split('\n');last=lines.length-1;if(last>0){nextLine=line+last;nextOffset=next-lines[last].length;}else{nextLine=line;nextOffset=offset;}currentToken=['comment',content,line,pos-offset,nextLine,next-nextOffset];offset=nextOffset;line=nextLine;pos=next;}else{RE_WORD_END.lastIndex=pos+1;RE_WORD_END.test(css);if(RE_WORD_END.lastIndex===0){next=css.length-1;}else{next=RE_WORD_END.lastIndex-2;}currentToken=['word',css.slice(pos,next+1),line,pos-offset,line,next-offset];buffer.push(currentToken);pos=next;}break;}pos++;return currentToken;}function back(token){returned.push(token);}return{back:back,nextToken:nextToken,endOfFile:endOfFile,position:position};}module.exports=exports["default"];},{}],190:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=void 0;/**
 * Contains helpers for working with vendor prefixes.
 *
 * @example
 * const vendor = postcss.vendor
 *
 * @namespace vendor
 */var vendor={/**
   * Returns the vendor prefix extracted from an input string.
   *
   * @param {string} prop String with or without vendor prefix.
   *
   * @return {string} vendor prefix or empty string
   *
   * @example
   * postcss.vendor.prefix('-moz-tab-size') //=> '-moz-'
   * postcss.vendor.prefix('tab-size')      //=> ''
   */prefix:function prefix(prop){var match=prop.match(/^(-\w+-)/);if(match){return match[0];}return'';},/**
     * Returns the input string stripped of its vendor prefix.
     *
     * @param {string} prop String with or without vendor prefix.
     *
     * @return {string} String name without vendor prefixes.
     *
     * @example
     * postcss.vendor.unprefixed('-moz-tab-size') //=> 'tab-size'
     */unprefixed:function unprefixed(prop){return prop.replace(/^-\w+-/,'');}};var _default=vendor;exports["default"]=_default;module.exports=exports["default"];},{}],191:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=warnOnce;var printed={};function warnOnce(message){if(printed[message])return;printed[message]=true;if(typeof console!=='undefined'&&console.warn){console.warn(message);}}module.exports=exports["default"];},{}],192:[function(require,module,exports){"use strict";exports.__esModule=true;exports["default"]=void 0;/**
 * Represents a plugin’s warning. It can be created using {@link Node#warn}.
 *
 * @example
 * if (decl.important) {
 *   decl.warn(result, 'Avoid !important', { word: '!important' })
 * }
 */var Warning=/*#__PURE__*/function(){/**
   * @param {string} text        Warning message.
   * @param {Object} [opts]      Warning options.
   * @param {Node}   opts.node   CSS node that caused the warning.
   * @param {string} opts.word   Word in CSS source that caused the warning.
   * @param {number} opts.index  Index in CSS node string that caused
   *                             the warning.
   * @param {string} opts.plugin Name of the plugin that created
   *                             this warning. {@link Result#warn} fills
   *                             this property automatically.
   */function Warning(text,opts){if(opts===void 0){opts={};}/**
     * Type to filter warnings from {@link Result#messages}.
     * Always equal to `"warning"`.
     *
     * @type {string}
     *
     * @example
     * const nonWarning = result.messages.filter(i => i.type !== 'warning')
     */this.type='warning';/**
     * The warning message.
     *
     * @type {string}
     *
     * @example
     * warning.text //=> 'Try to avoid !important'
     */this.text=text;if(opts.node&&opts.node.source){var pos=opts.node.positionBy(opts);/**
       * Line in the input file with this warning’s source.
       * @type {number}
       *
       * @example
       * warning.line //=> 5
       */this.line=pos.line;/**
       * Column in the input file with this warning’s source.
       *
       * @type {number}
       *
       * @example
       * warning.column //=> 6
       */this.column=pos.column;}for(var opt in opts){this[opt]=opts[opt];}}/**
   * Returns a warning position and message.
   *
   * @example
   * warning.toString() //=> 'postcss-lint:a.css:10:14: Avoid !important'
   *
   * @return {string} Warning position and message.
   */var _proto=Warning.prototype;_proto.toString=function toString(){if(this.node){return this.node.error(this.text,{plugin:this.plugin,index:this.index,word:this.word}).message;}if(this.plugin){return this.plugin+': '+this.text;}return this.text;}/**
   * @memberof Warning#
   * @member {string} plugin The name of the plugin that created
   *                         it will fill this property automatically.
   *                         this warning. When you call {@link Node#warn}
   *
   * @example
   * warning.plugin //=> 'postcss-important'
   */ /**
   * @memberof Warning#
   * @member {Node} node Contains the CSS node that caused the warning.
   *
   * @example
   * warning.node.toString() //=> 'color: white !important'
   */;return Warning;}();var _default=Warning;exports["default"]=_default;module.exports=exports["default"];},{}],193:[function(require,module,exports){// shim for using process in browser
var process=module.exports={};// cached from whatever global is present so that test runners that stub it
// don't break things.  But we need to wrap it in a try catch in case it is
// wrapped in strict mode code which doesn't define any globals.  It's inside a
// function because try/catches deoptimize in certain engines.
var cachedSetTimeout;var cachedClearTimeout;function defaultSetTimout(){throw new Error('setTimeout has not been defined');}function defaultClearTimeout(){throw new Error('clearTimeout has not been defined');}(function(){try{if(typeof setTimeout==='function'){cachedSetTimeout=setTimeout;}else{cachedSetTimeout=defaultSetTimout;}}catch(e){cachedSetTimeout=defaultSetTimout;}try{if(typeof clearTimeout==='function'){cachedClearTimeout=clearTimeout;}else{cachedClearTimeout=defaultClearTimeout;}}catch(e){cachedClearTimeout=defaultClearTimeout;}})();function runTimeout(fun){if(cachedSetTimeout===setTimeout){//normal enviroments in sane situations
return setTimeout(fun,0);}// if setTimeout wasn't available but was latter defined
if((cachedSetTimeout===defaultSetTimout||!cachedSetTimeout)&&setTimeout){cachedSetTimeout=setTimeout;return setTimeout(fun,0);}try{// when when somebody has screwed with setTimeout but no I.E. maddness
return cachedSetTimeout(fun,0);}catch(e){try{// When we are in I.E. but the script has been evaled so I.E. doesn't trust the global object when called normally
return cachedSetTimeout.call(null,fun,0);}catch(e){// same as above but when it's a version of I.E. that must have the global object for 'this', hopfully our context correct otherwise it will throw a global error
return cachedSetTimeout.call(this,fun,0);}}}function runClearTimeout(marker){if(cachedClearTimeout===clearTimeout){//normal enviroments in sane situations
return clearTimeout(marker);}// if clearTimeout wasn't available but was latter defined
if((cachedClearTimeout===defaultClearTimeout||!cachedClearTimeout)&&clearTimeout){cachedClearTimeout=clearTimeout;return clearTimeout(marker);}try{// when when somebody has screwed with setTimeout but no I.E. maddness
return cachedClearTimeout(marker);}catch(e){try{// When we are in I.E. but the script has been evaled so I.E. doesn't  trust the global object when called normally
return cachedClearTimeout.call(null,marker);}catch(e){// same as above but when it's a version of I.E. that must have the global object for 'this', hopfully our context correct otherwise it will throw a global error.
// Some versions of I.E. have different rules for clearTimeout vs setTimeout
return cachedClearTimeout.call(this,marker);}}}var queue=[];var draining=false;var currentQueue;var queueIndex=-1;function cleanUpNextTick(){if(!draining||!currentQueue){return;}draining=false;if(currentQueue.length){queue=currentQueue.concat(queue);}else{queueIndex=-1;}if(queue.length){drainQueue();}}function drainQueue(){if(draining){return;}var timeout=runTimeout(cleanUpNextTick);draining=true;var len=queue.length;while(len){currentQueue=queue;queue=[];while(++queueIndex<len){if(currentQueue){currentQueue[queueIndex].run();}}queueIndex=-1;len=queue.length;}currentQueue=null;draining=false;runClearTimeout(timeout);}process.nextTick=function(fun){var args=new Array(arguments.length-1);if(arguments.length>1){for(var i=1;i<arguments.length;i++){args[i-1]=arguments[i];}}queue.push(new Item(fun,args));if(queue.length===1&&!draining){runTimeout(drainQueue);}};// v8 likes predictible objects
function Item(fun,array){this.fun=fun;this.array=array;}Item.prototype.run=function(){this.fun.apply(null,this.array);};process.title='browser';process.browser=true;process.env={};process.argv=[];process.version='';// empty string to avoid regexp issues
process.versions={};function noop(){}process.on=noop;process.addListener=noop;process.once=noop;process.off=noop;process.removeListener=noop;process.removeAllListeners=noop;process.emit=noop;process.prependListener=noop;process.prependOnceListener=noop;process.listeners=function(name){return[];};process.binding=function(name){throw new Error('process.binding is not supported');};process.cwd=function(){return'/';};process.chdir=function(dir){throw new Error('process.chdir is not supported');};process.umask=function(){return 0;};},{}],194:[function(require,module,exports){(function(global){/*! https://mths.be/punycode v1.4.1 by @mathias */;(function(root){/** Detect free variables */var freeExports=_typeof(exports)=='object'&&exports&&!exports.nodeType&&exports;var freeModule=_typeof(module)=='object'&&module&&!module.nodeType&&module;var freeGlobal=_typeof(global)=='object'&&global;if(freeGlobal.global===freeGlobal||freeGlobal.window===freeGlobal||freeGlobal.self===freeGlobal){root=freeGlobal;}/**
	 * The `punycode` object.
	 * @name punycode
	 * @type Object
	 */var punycode,/** Highest positive signed 32-bit float value */maxInt=2147483647,// aka. 0x7FFFFFFF or 2^31-1
/** Bootstring parameters */base=36,tMin=1,tMax=26,skew=38,damp=700,initialBias=72,initialN=128,// 0x80
delimiter='-',// '\x2D'
/** Regular expressions */regexPunycode=/^xn--/,regexNonASCII=/[^\x20-\x7E]/,// unprintable ASCII chars + non-ASCII chars
regexSeparators=/[\x2E\u3002\uFF0E\uFF61]/g,// RFC 3490 separators
/** Error messages */errors={'overflow':'Overflow: input needs wider integers to process','not-basic':'Illegal input >= 0x80 (not a basic code point)','invalid-input':'Invalid input'},/** Convenience shortcuts */baseMinusTMin=base-tMin,floor=Math.floor,stringFromCharCode=String.fromCharCode,/** Temporary variable */key;/*--------------------------------------------------------------------------*/ /**
	 * A generic error utility function.
	 * @private
	 * @param {String} type The error type.
	 * @returns {Error} Throws a `RangeError` with the applicable error message.
	 */function error(type){throw new RangeError(errors[type]);}/**
	 * A generic `Array#map` utility function.
	 * @private
	 * @param {Array} array The array to iterate over.
	 * @param {Function} callback The function that gets called for every array
	 * item.
	 * @returns {Array} A new array of values returned by the callback function.
	 */function map(array,fn){var length=array.length;var result=[];while(length--){result[length]=fn(array[length]);}return result;}/**
	 * A simple `Array#map`-like wrapper to work with domain name strings or email
	 * addresses.
	 * @private
	 * @param {String} domain The domain name or email address.
	 * @param {Function} callback The function that gets called for every
	 * character.
	 * @returns {Array} A new string of characters returned by the callback
	 * function.
	 */function mapDomain(string,fn){var parts=string.split('@');var result='';if(parts.length>1){// In email addresses, only the domain name should be punycoded. Leave
// the local part (i.e. everything up to `@`) intact.
result=parts[0]+'@';string=parts[1];}// Avoid `split(regex)` for IE8 compatibility. See #17.
string=string.replace(regexSeparators,'\x2E');var labels=string.split('.');var encoded=map(labels,fn).join('.');return result+encoded;}/**
	 * Creates an array containing the numeric code points of each Unicode
	 * character in the string. While JavaScript uses UCS-2 internally,
	 * this function will convert a pair of surrogate halves (each of which
	 * UCS-2 exposes as separate characters) into a single code point,
	 * matching UTF-16.
	 * @see `punycode.ucs2.encode`
	 * @see <https://mathiasbynens.be/notes/javascript-encoding>
	 * @memberOf punycode.ucs2
	 * @name decode
	 * @param {String} string The Unicode input string (UCS-2).
	 * @returns {Array} The new array of code points.
	 */function ucs2decode(string){var output=[],counter=0,length=string.length,value,extra;while(counter<length){value=string.charCodeAt(counter++);if(value>=0xD800&&value<=0xDBFF&&counter<length){// high surrogate, and there is a next character
extra=string.charCodeAt(counter++);if((extra&0xFC00)==0xDC00){// low surrogate
output.push(((value&0x3FF)<<10)+(extra&0x3FF)+0x10000);}else{// unmatched surrogate; only append this code unit, in case the next
// code unit is the high surrogate of a surrogate pair
output.push(value);counter--;}}else{output.push(value);}}return output;}/**
	 * Creates a string based on an array of numeric code points.
	 * @see `punycode.ucs2.decode`
	 * @memberOf punycode.ucs2
	 * @name encode
	 * @param {Array} codePoints The array of numeric code points.
	 * @returns {String} The new Unicode string (UCS-2).
	 */function ucs2encode(array){return map(array,function(value){var output='';if(value>0xFFFF){value-=0x10000;output+=stringFromCharCode(value>>>10&0x3FF|0xD800);value=0xDC00|value&0x3FF;}output+=stringFromCharCode(value);return output;}).join('');}/**
	 * Converts a basic code point into a digit/integer.
	 * @see `digitToBasic()`
	 * @private
	 * @param {Number} codePoint The basic numeric code point value.
	 * @returns {Number} The numeric value of a basic code point (for use in
	 * representing integers) in the range `0` to `base - 1`, or `base` if
	 * the code point does not represent a value.
	 */function basicToDigit(codePoint){if(codePoint-48<10){return codePoint-22;}if(codePoint-65<26){return codePoint-65;}if(codePoint-97<26){return codePoint-97;}return base;}/**
	 * Converts a digit/integer into a basic code point.
	 * @see `basicToDigit()`
	 * @private
	 * @param {Number} digit The numeric value of a basic code point.
	 * @returns {Number} The basic code point whose value (when used for
	 * representing integers) is `digit`, which needs to be in the range
	 * `0` to `base - 1`. If `flag` is non-zero, the uppercase form is
	 * used; else, the lowercase form is used. The behavior is undefined
	 * if `flag` is non-zero and `digit` has no uppercase form.
	 */function digitToBasic(digit,flag){//  0..25 map to ASCII a..z or A..Z
// 26..35 map to ASCII 0..9
return digit+22+75*(digit<26)-((flag!=0)<<5);}/**
	 * Bias adaptation function as per section 3.4 of RFC 3492.
	 * https://tools.ietf.org/html/rfc3492#section-3.4
	 * @private
	 */function adapt(delta,numPoints,firstTime){var k=0;delta=firstTime?floor(delta/damp):delta>>1;delta+=floor(delta/numPoints);for(;/* no initialization */delta>baseMinusTMin*tMax>>1;k+=base){delta=floor(delta/baseMinusTMin);}return floor(k+(baseMinusTMin+1)*delta/(delta+skew));}/**
	 * Converts a Punycode string of ASCII-only symbols to a string of Unicode
	 * symbols.
	 * @memberOf punycode
	 * @param {String} input The Punycode string of ASCII-only symbols.
	 * @returns {String} The resulting string of Unicode symbols.
	 */function decode(input){// Don't use UCS-2
var output=[],inputLength=input.length,out,i=0,n=initialN,bias=initialBias,basic,j,index,oldi,w,k,digit,t,/** Cached calculation results */baseMinusT;// Handle the basic code points: let `basic` be the number of input code
// points before the last delimiter, or `0` if there is none, then copy
// the first basic code points to the output.
basic=input.lastIndexOf(delimiter);if(basic<0){basic=0;}for(j=0;j<basic;++j){// if it's not a basic code point
if(input.charCodeAt(j)>=0x80){error('not-basic');}output.push(input.charCodeAt(j));}// Main decoding loop: start just after the last delimiter if any basic code
// points were copied; start at the beginning otherwise.
for(index=basic>0?basic+1:0;index<inputLength;)/* no final expression */{// `index` is the index of the next character to be consumed.
// Decode a generalized variable-length integer into `delta`,
// which gets added to `i`. The overflow checking is easier
// if we increase `i` as we go, then subtract off its starting
// value at the end to obtain `delta`.
for(oldi=i,w=1,k=base;;/* no condition */k+=base){if(index>=inputLength){error('invalid-input');}digit=basicToDigit(input.charCodeAt(index++));if(digit>=base||digit>floor((maxInt-i)/w)){error('overflow');}i+=digit*w;t=k<=bias?tMin:k>=bias+tMax?tMax:k-bias;if(digit<t){break;}baseMinusT=base-t;if(w>floor(maxInt/baseMinusT)){error('overflow');}w*=baseMinusT;}out=output.length+1;bias=adapt(i-oldi,out,oldi==0);// `i` was supposed to wrap around from `out` to `0`,
// incrementing `n` each time, so we'll fix that now:
if(floor(i/out)>maxInt-n){error('overflow');}n+=floor(i/out);i%=out;// Insert `n` at position `i` of the output
output.splice(i++,0,n);}return ucs2encode(output);}/**
	 * Converts a string of Unicode symbols (e.g. a domain name label) to a
	 * Punycode string of ASCII-only symbols.
	 * @memberOf punycode
	 * @param {String} input The string of Unicode symbols.
	 * @returns {String} The resulting Punycode string of ASCII-only symbols.
	 */function encode(input){var n,delta,handledCPCount,basicLength,bias,j,m,q,k,t,currentValue,output=[],/** `inputLength` will hold the number of code points in `input`. */inputLength,/** Cached calculation results */handledCPCountPlusOne,baseMinusT,qMinusT;// Convert the input in UCS-2 to Unicode
input=ucs2decode(input);// Cache the length
inputLength=input.length;// Initialize the state
n=initialN;delta=0;bias=initialBias;// Handle the basic code points
for(j=0;j<inputLength;++j){currentValue=input[j];if(currentValue<0x80){output.push(stringFromCharCode(currentValue));}}handledCPCount=basicLength=output.length;// `handledCPCount` is the number of code points that have been handled;
// `basicLength` is the number of basic code points.
// Finish the basic string - if it is not empty - with a delimiter
if(basicLength){output.push(delimiter);}// Main encoding loop:
while(handledCPCount<inputLength){// All non-basic code points < n have been handled already. Find the next
// larger one:
for(m=maxInt,j=0;j<inputLength;++j){currentValue=input[j];if(currentValue>=n&&currentValue<m){m=currentValue;}}// Increase `delta` enough to advance the decoder's <n,i> state to <m,0>,
// but guard against overflow
handledCPCountPlusOne=handledCPCount+1;if(m-n>floor((maxInt-delta)/handledCPCountPlusOne)){error('overflow');}delta+=(m-n)*handledCPCountPlusOne;n=m;for(j=0;j<inputLength;++j){currentValue=input[j];if(currentValue<n&&++delta>maxInt){error('overflow');}if(currentValue==n){// Represent delta as a generalized variable-length integer
for(q=delta,k=base;;/* no condition */k+=base){t=k<=bias?tMin:k>=bias+tMax?tMax:k-bias;if(q<t){break;}qMinusT=q-t;baseMinusT=base-t;output.push(stringFromCharCode(digitToBasic(t+qMinusT%baseMinusT,0)));q=floor(qMinusT/baseMinusT);}output.push(stringFromCharCode(digitToBasic(q,0)));bias=adapt(delta,handledCPCountPlusOne,handledCPCount==basicLength);delta=0;++handledCPCount;}}++delta;++n;}return output.join('');}/**
	 * Converts a Punycode string representing a domain name or an email address
	 * to Unicode. Only the Punycoded parts of the input will be converted, i.e.
	 * it doesn't matter if you call it on a string that has already been
	 * converted to Unicode.
	 * @memberOf punycode
	 * @param {String} input The Punycoded domain name or email address to
	 * convert to Unicode.
	 * @returns {String} The Unicode representation of the given Punycode
	 * string.
	 */function toUnicode(input){return mapDomain(input,function(string){return regexPunycode.test(string)?decode(string.slice(4).toLowerCase()):string;});}/**
	 * Converts a Unicode string representing a domain name or an email address to
	 * Punycode. Only the non-ASCII parts of the domain name will be converted,
	 * i.e. it doesn't matter if you call it with a domain that's already in
	 * ASCII.
	 * @memberOf punycode
	 * @param {String} input The domain name or email address to convert, as a
	 * Unicode string.
	 * @returns {String} The Punycode representation of the given domain name or
	 * email address.
	 */function toASCII(input){return mapDomain(input,function(string){return regexNonASCII.test(string)?'xn--'+encode(string):string;});}/*--------------------------------------------------------------------------*/ /** Define the public API */punycode={/**
		 * A string representing the current Punycode.js version number.
		 * @memberOf punycode
		 * @type String
		 */'version':'1.4.1',/**
		 * An object of methods to convert from JavaScript's internal character
		 * representation (UCS-2) to Unicode code points, and back.
		 * @see <https://mathiasbynens.be/notes/javascript-encoding>
		 * @memberOf punycode
		 * @type Object
		 */'ucs2':{'decode':ucs2decode,'encode':ucs2encode},'decode':decode,'encode':encode,'toASCII':toASCII,'toUnicode':toUnicode};/** Expose `punycode` */ // Some AMD build optimizers, like r.js, check for specific condition patterns
// like the following:
if(typeof define=='function'&&_typeof(define.amd)=='object'&&define.amd){define('punycode',function(){return punycode;});}else if(freeExports&&freeModule){if(module.exports==freeExports){// in Node.js, io.js, or RingoJS v0.8.0+
freeModule.exports=punycode;}else{// in Narwhal or RingoJS v0.7.0-
for(key in punycode){punycode.hasOwnProperty(key)&&(freeExports[key]=punycode[key]);}}}else{// in Rhino or a web browser
root.punycode=punycode;}})(this);}).call(this,typeof global!=="undefined"?global:typeof self!=="undefined"?self:typeof window!=="undefined"?window:{});},{}],195:[function(require,module,exports){// Copyright Joyent, Inc. and other Node contributors.
//
// Permission is hereby granted, free of charge, to any person obtaining a
// copy of this software and associated documentation files (the
// "Software"), to deal in the Software without restriction, including
// without limitation the rights to use, copy, modify, merge, publish,
// distribute, sublicense, and/or sell copies of the Software, and to permit
// persons to whom the Software is furnished to do so, subject to the
// following conditions:
//
// The above copyright notice and this permission notice shall be included
// in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
// OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
// NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
// DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
// OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
// USE OR OTHER DEALINGS IN THE SOFTWARE.
'use strict';// If obj.hasOwnProperty has been overridden, then calling
// obj.hasOwnProperty(prop) will break.
// See: https://github.com/joyent/node/issues/1707
function hasOwnProperty(obj,prop){return Object.prototype.hasOwnProperty.call(obj,prop);}module.exports=function(qs,sep,eq,options){sep=sep||'&';eq=eq||'=';var obj={};if(typeof qs!=='string'||qs.length===0){return obj;}var regexp=/\+/g;qs=qs.split(sep);var maxKeys=1000;if(options&&typeof options.maxKeys==='number'){maxKeys=options.maxKeys;}var len=qs.length;// maxKeys <= 0 means that we should not limit keys count
if(maxKeys>0&&len>maxKeys){len=maxKeys;}for(var i=0;i<len;++i){var x=qs[i].replace(regexp,'%20'),idx=x.indexOf(eq),kstr,vstr,k,v;if(idx>=0){kstr=x.substr(0,idx);vstr=x.substr(idx+1);}else{kstr=x;vstr='';}k=decodeURIComponent(kstr);v=decodeURIComponent(vstr);if(!hasOwnProperty(obj,k)){obj[k]=v;}else if(isArray(obj[k])){obj[k].push(v);}else{obj[k]=[obj[k],v];}}return obj;};var isArray=Array.isArray||function(xs){return Object.prototype.toString.call(xs)==='[object Array]';};},{}],196:[function(require,module,exports){// Copyright Joyent, Inc. and other Node contributors.
//
// Permission is hereby granted, free of charge, to any person obtaining a
// copy of this software and associated documentation files (the
// "Software"), to deal in the Software without restriction, including
// without limitation the rights to use, copy, modify, merge, publish,
// distribute, sublicense, and/or sell copies of the Software, and to permit
// persons to whom the Software is furnished to do so, subject to the
// following conditions:
//
// The above copyright notice and this permission notice shall be included
// in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
// OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
// NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
// DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
// OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
// USE OR OTHER DEALINGS IN THE SOFTWARE.
'use strict';var stringifyPrimitive=function stringifyPrimitive(v){switch(_typeof(v)){case'string':return v;case'boolean':return v?'true':'false';case'number':return isFinite(v)?v:'';default:return'';}};module.exports=function(obj,sep,eq,name){sep=sep||'&';eq=eq||'=';if(obj===null){obj=undefined;}if(_typeof(obj)==='object'){return map(objectKeys(obj),function(k){var ks=encodeURIComponent(stringifyPrimitive(k))+eq;if(isArray(obj[k])){return map(obj[k],function(v){return ks+encodeURIComponent(stringifyPrimitive(v));}).join(sep);}else{return ks+encodeURIComponent(stringifyPrimitive(obj[k]));}}).join(sep);}if(!name)return'';return encodeURIComponent(stringifyPrimitive(name))+eq+encodeURIComponent(stringifyPrimitive(obj));};var isArray=Array.isArray||function(xs){return Object.prototype.toString.call(xs)==='[object Array]';};function map(xs,f){if(xs.map)return xs.map(f);var res=[];for(var i=0;i<xs.length;i++){res.push(f(xs[i],i));}return res;}var objectKeys=Object.keys||function(obj){var res=[];for(var key in obj){if(Object.prototype.hasOwnProperty.call(obj,key))res.push(key);}return res;};},{}],197:[function(require,module,exports){'use strict';exports.decode=exports.parse=require('./decode');exports.encode=exports.stringify=require('./encode');},{"./decode":195,"./encode":196}],198:[function(require,module,exports){/* -*- Mode: js; js-indent-level: 2; -*- */ /*
 * Copyright 2011 Mozilla Foundation and contributors
 * Licensed under the New BSD license. See LICENSE or:
 * http://opensource.org/licenses/BSD-3-Clause
 */var util=require('./util');var has=Object.prototype.hasOwnProperty;var hasNativeMap=typeof Map!=="undefined";/**
 * A data structure which is a combination of an array and a set. Adding a new
 * member is O(1), testing for membership is O(1), and finding the index of an
 * element is O(1). Removing elements from the set is not supported. Only
 * strings are supported for membership.
 */function ArraySet(){this._array=[];this._set=hasNativeMap?new Map():Object.create(null);}/**
 * Static method for creating ArraySet instances from an existing array.
 */ArraySet.fromArray=function ArraySet_fromArray(aArray,aAllowDuplicates){var set=new ArraySet();for(var i=0,len=aArray.length;i<len;i++){set.add(aArray[i],aAllowDuplicates);}return set;};/**
 * Return how many unique items are in this ArraySet. If duplicates have been
 * added, than those do not count towards the size.
 *
 * @returns Number
 */ArraySet.prototype.size=function ArraySet_size(){return hasNativeMap?this._set.size:Object.getOwnPropertyNames(this._set).length;};/**
 * Add the given string to this set.
 *
 * @param String aStr
 */ArraySet.prototype.add=function ArraySet_add(aStr,aAllowDuplicates){var sStr=hasNativeMap?aStr:util.toSetString(aStr);var isDuplicate=hasNativeMap?this.has(aStr):has.call(this._set,sStr);var idx=this._array.length;if(!isDuplicate||aAllowDuplicates){this._array.push(aStr);}if(!isDuplicate){if(hasNativeMap){this._set.set(aStr,idx);}else{this._set[sStr]=idx;}}};/**
 * Is the given string a member of this set?
 *
 * @param String aStr
 */ArraySet.prototype.has=function ArraySet_has(aStr){if(hasNativeMap){return this._set.has(aStr);}else{var sStr=util.toSetString(aStr);return has.call(this._set,sStr);}};/**
 * What is the index of the given string in the array?
 *
 * @param String aStr
 */ArraySet.prototype.indexOf=function ArraySet_indexOf(aStr){if(hasNativeMap){var idx=this._set.get(aStr);if(idx>=0){return idx;}}else{var sStr=util.toSetString(aStr);if(has.call(this._set,sStr)){return this._set[sStr];}}throw new Error('"'+aStr+'" is not in the set.');};/**
 * What is the element at the given index?
 *
 * @param Number aIdx
 */ArraySet.prototype.at=function ArraySet_at(aIdx){if(aIdx>=0&&aIdx<this._array.length){return this._array[aIdx];}throw new Error('No element indexed by '+aIdx);};/**
 * Returns the array representation of this set (which has the proper indices
 * indicated by indexOf). Note that this is a copy of the internal array used
 * for storing the members so that no one can mess with internal state.
 */ArraySet.prototype.toArray=function ArraySet_toArray(){return this._array.slice();};exports.ArraySet=ArraySet;},{"./util":207}],199:[function(require,module,exports){/* -*- Mode: js; js-indent-level: 2; -*- */ /*
 * Copyright 2011 Mozilla Foundation and contributors
 * Licensed under the New BSD license. See LICENSE or:
 * http://opensource.org/licenses/BSD-3-Clause
 *
 * Based on the Base 64 VLQ implementation in Closure Compiler:
 * https://code.google.com/p/closure-compiler/source/browse/trunk/src/com/google/debugging/sourcemap/Base64VLQ.java
 *
 * Copyright 2011 The Closure Compiler Authors. All rights reserved.
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met:
 *
 *  * Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *  * Redistributions in binary form must reproduce the above
 *    copyright notice, this list of conditions and the following
 *    disclaimer in the documentation and/or other materials provided
 *    with the distribution.
 *  * Neither the name of Google Inc. nor the names of its
 *    contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */var base64=require('./base64');// A single base 64 digit can contain 6 bits of data. For the base 64 variable
// length quantities we use in the source map spec, the first bit is the sign,
// the next four bits are the actual value, and the 6th bit is the
// continuation bit. The continuation bit tells us whether there are more
// digits in this value following this digit.
//
//   Continuation
//   |    Sign
//   |    |
//   V    V
//   101011
var VLQ_BASE_SHIFT=5;// binary: 100000
var VLQ_BASE=1<<VLQ_BASE_SHIFT;// binary: 011111
var VLQ_BASE_MASK=VLQ_BASE-1;// binary: 100000
var VLQ_CONTINUATION_BIT=VLQ_BASE;/**
 * Converts from a two-complement value to a value where the sign bit is
 * placed in the least significant bit.  For example, as decimals:
 *   1 becomes 2 (10 binary), -1 becomes 3 (11 binary)
 *   2 becomes 4 (100 binary), -2 becomes 5 (101 binary)
 */function toVLQSigned(aValue){return aValue<0?(-aValue<<1)+1:(aValue<<1)+0;}/**
 * Converts to a two-complement value from a value where the sign bit is
 * placed in the least significant bit.  For example, as decimals:
 *   2 (10 binary) becomes 1, 3 (11 binary) becomes -1
 *   4 (100 binary) becomes 2, 5 (101 binary) becomes -2
 */function fromVLQSigned(aValue){var isNegative=(aValue&1)===1;var shifted=aValue>>1;return isNegative?-shifted:shifted;}/**
 * Returns the base 64 VLQ encoded value.
 */exports.encode=function base64VLQ_encode(aValue){var encoded="";var digit;var vlq=toVLQSigned(aValue);do{digit=vlq&VLQ_BASE_MASK;vlq>>>=VLQ_BASE_SHIFT;if(vlq>0){// There are still more digits in this value, so we must make sure the
// continuation bit is marked.
digit|=VLQ_CONTINUATION_BIT;}encoded+=base64.encode(digit);}while(vlq>0);return encoded;};/**
 * Decodes the next base 64 VLQ value from the given string and returns the
 * value and the rest of the string via the out parameter.
 */exports.decode=function base64VLQ_decode(aStr,aIndex,aOutParam){var strLen=aStr.length;var result=0;var shift=0;var continuation,digit;do{if(aIndex>=strLen){throw new Error("Expected more digits in base 64 VLQ value.");}digit=base64.decode(aStr.charCodeAt(aIndex++));if(digit===-1){throw new Error("Invalid base64 digit: "+aStr.charAt(aIndex-1));}continuation=!!(digit&VLQ_CONTINUATION_BIT);digit&=VLQ_BASE_MASK;result=result+(digit<<shift);shift+=VLQ_BASE_SHIFT;}while(continuation);aOutParam.value=fromVLQSigned(result);aOutParam.rest=aIndex;};},{"./base64":200}],200:[function(require,module,exports){/* -*- Mode: js; js-indent-level: 2; -*- */ /*
 * Copyright 2011 Mozilla Foundation and contributors
 * Licensed under the New BSD license. See LICENSE or:
 * http://opensource.org/licenses/BSD-3-Clause
 */var intToCharMap='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'.split('');/**
 * Encode an integer in the range of 0 to 63 to a single base 64 digit.
 */exports.encode=function(number){if(0<=number&&number<intToCharMap.length){return intToCharMap[number];}throw new TypeError("Must be between 0 and 63: "+number);};/**
 * Decode a single base 64 character code digit to an integer. Returns -1 on
 * failure.
 */exports.decode=function(charCode){var bigA=65;// 'A'
var bigZ=90;// 'Z'
var littleA=97;// 'a'
var littleZ=122;// 'z'
var zero=48;// '0'
var nine=57;// '9'
var plus=43;// '+'
var slash=47;// '/'
var littleOffset=26;var numberOffset=52;// 0 - 25: ABCDEFGHIJKLMNOPQRSTUVWXYZ
if(bigA<=charCode&&charCode<=bigZ){return charCode-bigA;}// 26 - 51: abcdefghijklmnopqrstuvwxyz
if(littleA<=charCode&&charCode<=littleZ){return charCode-littleA+littleOffset;}// 52 - 61: 0123456789
if(zero<=charCode&&charCode<=nine){return charCode-zero+numberOffset;}// 62: +
if(charCode==plus){return 62;}// 63: /
if(charCode==slash){return 63;}// Invalid base64 digit.
return-1;};},{}],201:[function(require,module,exports){/* -*- Mode: js; js-indent-level: 2; -*- */ /*
 * Copyright 2011 Mozilla Foundation and contributors
 * Licensed under the New BSD license. See LICENSE or:
 * http://opensource.org/licenses/BSD-3-Clause
 */exports.GREATEST_LOWER_BOUND=1;exports.LEAST_UPPER_BOUND=2;/**
 * Recursive implementation of binary search.
 *
 * @param aLow Indices here and lower do not contain the needle.
 * @param aHigh Indices here and higher do not contain the needle.
 * @param aNeedle The element being searched for.
 * @param aHaystack The non-empty array being searched.
 * @param aCompare Function which takes two elements and returns -1, 0, or 1.
 * @param aBias Either 'binarySearch.GREATEST_LOWER_BOUND' or
 *     'binarySearch.LEAST_UPPER_BOUND'. Specifies whether to return the
 *     closest element that is smaller than or greater than the one we are
 *     searching for, respectively, if the exact element cannot be found.
 */function recursiveSearch(aLow,aHigh,aNeedle,aHaystack,aCompare,aBias){// This function terminates when one of the following is true:
//
//   1. We find the exact element we are looking for.
//
//   2. We did not find the exact element, but we can return the index of
//      the next-closest element.
//
//   3. We did not find the exact element, and there is no next-closest
//      element than the one we are searching for, so we return -1.
var mid=Math.floor((aHigh-aLow)/2)+aLow;var cmp=aCompare(aNeedle,aHaystack[mid],true);if(cmp===0){// Found the element we are looking for.
return mid;}else if(cmp>0){// Our needle is greater than aHaystack[mid].
if(aHigh-mid>1){// The element is in the upper half.
return recursiveSearch(mid,aHigh,aNeedle,aHaystack,aCompare,aBias);}// The exact needle element was not found in this haystack. Determine if
// we are in termination case (3) or (2) and return the appropriate thing.
if(aBias==exports.LEAST_UPPER_BOUND){return aHigh<aHaystack.length?aHigh:-1;}else{return mid;}}else{// Our needle is less than aHaystack[mid].
if(mid-aLow>1){// The element is in the lower half.
return recursiveSearch(aLow,mid,aNeedle,aHaystack,aCompare,aBias);}// we are in termination case (3) or (2) and return the appropriate thing.
if(aBias==exports.LEAST_UPPER_BOUND){return mid;}else{return aLow<0?-1:aLow;}}}/**
 * This is an implementation of binary search which will always try and return
 * the index of the closest element if there is no exact hit. This is because
 * mappings between original and generated line/col pairs are single points,
 * and there is an implicit region between each of them, so a miss just means
 * that you aren't on the very start of a region.
 *
 * @param aNeedle The element you are looking for.
 * @param aHaystack The array that is being searched.
 * @param aCompare A function which takes the needle and an element in the
 *     array and returns -1, 0, or 1 depending on whether the needle is less
 *     than, equal to, or greater than the element, respectively.
 * @param aBias Either 'binarySearch.GREATEST_LOWER_BOUND' or
 *     'binarySearch.LEAST_UPPER_BOUND'. Specifies whether to return the
 *     closest element that is smaller than or greater than the one we are
 *     searching for, respectively, if the exact element cannot be found.
 *     Defaults to 'binarySearch.GREATEST_LOWER_BOUND'.
 */exports.search=function search(aNeedle,aHaystack,aCompare,aBias){if(aHaystack.length===0){return-1;}var index=recursiveSearch(-1,aHaystack.length,aNeedle,aHaystack,aCompare,aBias||exports.GREATEST_LOWER_BOUND);if(index<0){return-1;}// We have found either the exact element, or the next-closest element than
// the one we are searching for. However, there may be more than one such
// element. Make sure we always return the smallest of these.
while(index-1>=0){if(aCompare(aHaystack[index],aHaystack[index-1],true)!==0){break;}--index;}return index;};},{}],202:[function(require,module,exports){/* -*- Mode: js; js-indent-level: 2; -*- */ /*
 * Copyright 2014 Mozilla Foundation and contributors
 * Licensed under the New BSD license. See LICENSE or:
 * http://opensource.org/licenses/BSD-3-Clause
 */var util=require('./util');/**
 * Determine whether mappingB is after mappingA with respect to generated
 * position.
 */function generatedPositionAfter(mappingA,mappingB){// Optimized for most common case
var lineA=mappingA.generatedLine;var lineB=mappingB.generatedLine;var columnA=mappingA.generatedColumn;var columnB=mappingB.generatedColumn;return lineB>lineA||lineB==lineA&&columnB>=columnA||util.compareByGeneratedPositionsInflated(mappingA,mappingB)<=0;}/**
 * A data structure to provide a sorted view of accumulated mappings in a
 * performance conscious manner. It trades a neglibable overhead in general
 * case for a large speedup in case of mappings being added in order.
 */function MappingList(){this._array=[];this._sorted=true;// Serves as infimum
this._last={generatedLine:-1,generatedColumn:0};}/**
 * Iterate through internal items. This method takes the same arguments that
 * `Array.prototype.forEach` takes.
 *
 * NOTE: The order of the mappings is NOT guaranteed.
 */MappingList.prototype.unsortedForEach=function MappingList_forEach(aCallback,aThisArg){this._array.forEach(aCallback,aThisArg);};/**
 * Add the given source mapping.
 *
 * @param Object aMapping
 */MappingList.prototype.add=function MappingList_add(aMapping){if(generatedPositionAfter(this._last,aMapping)){this._last=aMapping;this._array.push(aMapping);}else{this._sorted=false;this._array.push(aMapping);}};/**
 * Returns the flat, sorted array of mappings. The mappings are sorted by
 * generated position.
 *
 * WARNING: This method returns internal data without copying, for
 * performance. The return value must NOT be mutated, and should be treated as
 * an immutable borrow. If you want to take ownership, you must make your own
 * copy.
 */MappingList.prototype.toArray=function MappingList_toArray(){if(!this._sorted){this._array.sort(util.compareByGeneratedPositionsInflated);this._sorted=true;}return this._array;};exports.MappingList=MappingList;},{"./util":207}],203:[function(require,module,exports){/* -*- Mode: js; js-indent-level: 2; -*- */ /*
 * Copyright 2011 Mozilla Foundation and contributors
 * Licensed under the New BSD license. See LICENSE or:
 * http://opensource.org/licenses/BSD-3-Clause
 */ // It turns out that some (most?) JavaScript engines don't self-host
// `Array.prototype.sort`. This makes sense because C++ will likely remain
// faster than JS when doing raw CPU-intensive sorting. However, when using a
// custom comparator function, calling back and forth between the VM's C++ and
// JIT'd JS is rather slow *and* loses JIT type information, resulting in
// worse generated code for the comparator function than would be optimal. In
// fact, when sorting with a comparator, these costs outweigh the benefits of
// sorting in C++. By using our own JS-implemented Quick Sort (below), we get
// a ~3500ms mean speed-up in `bench/bench.html`.
/**
 * Swap the elements indexed by `x` and `y` in the array `ary`.
 *
 * @param {Array} ary
 *        The array.
 * @param {Number} x
 *        The index of the first item.
 * @param {Number} y
 *        The index of the second item.
 */function swap(ary,x,y){var temp=ary[x];ary[x]=ary[y];ary[y]=temp;}/**
 * Returns a random integer within the range `low .. high` inclusive.
 *
 * @param {Number} low
 *        The lower bound on the range.
 * @param {Number} high
 *        The upper bound on the range.
 */function randomIntInRange(low,high){return Math.round(low+Math.random()*(high-low));}/**
 * The Quick Sort algorithm.
 *
 * @param {Array} ary
 *        An array to sort.
 * @param {function} comparator
 *        Function to use to compare two items.
 * @param {Number} p
 *        Start index of the array
 * @param {Number} r
 *        End index of the array
 */function doQuickSort(ary,comparator,p,r){// If our lower bound is less than our upper bound, we (1) partition the
// array into two pieces and (2) recurse on each half. If it is not, this is
// the empty array and our base case.
if(p<r){// (1) Partitioning.
//
// The partitioning chooses a pivot between `p` and `r` and moves all
// elements that are less than or equal to the pivot to the before it, and
// all the elements that are greater than it after it. The effect is that
// once partition is done, the pivot is in the exact place it will be when
// the array is put in sorted order, and it will not need to be moved
// again. This runs in O(n) time.
// Always choose a random pivot so that an input array which is reverse
// sorted does not cause O(n^2) running time.
var pivotIndex=randomIntInRange(p,r);var i=p-1;swap(ary,pivotIndex,r);var pivot=ary[r];// Immediately after `j` is incremented in this loop, the following hold
// true:
//
//   * Every element in `ary[p .. i]` is less than or equal to the pivot.
//
//   * Every element in `ary[i+1 .. j-1]` is greater than the pivot.
for(var j=p;j<r;j++){if(comparator(ary[j],pivot)<=0){i+=1;swap(ary,i,j);}}swap(ary,i+1,j);var q=i+1;// (2) Recurse on each half.
doQuickSort(ary,comparator,p,q-1);doQuickSort(ary,comparator,q+1,r);}}/**
 * Sort the given array in-place with the given comparator function.
 *
 * @param {Array} ary
 *        An array to sort.
 * @param {function} comparator
 *        Function to use to compare two items.
 */exports.quickSort=function(ary,comparator){doQuickSort(ary,comparator,0,ary.length-1);};},{}],204:[function(require,module,exports){/* -*- Mode: js; js-indent-level: 2; -*- */ /*
 * Copyright 2011 Mozilla Foundation and contributors
 * Licensed under the New BSD license. See LICENSE or:
 * http://opensource.org/licenses/BSD-3-Clause
 */var util=require('./util');var binarySearch=require('./binary-search');var ArraySet=require('./array-set').ArraySet;var base64VLQ=require('./base64-vlq');var quickSort=require('./quick-sort').quickSort;function SourceMapConsumer(aSourceMap,aSourceMapURL){var sourceMap=aSourceMap;if(typeof aSourceMap==='string'){sourceMap=util.parseSourceMapInput(aSourceMap);}return sourceMap.sections!=null?new IndexedSourceMapConsumer(sourceMap,aSourceMapURL):new BasicSourceMapConsumer(sourceMap,aSourceMapURL);}SourceMapConsumer.fromSourceMap=function(aSourceMap,aSourceMapURL){return BasicSourceMapConsumer.fromSourceMap(aSourceMap,aSourceMapURL);};/**
 * The version of the source mapping spec that we are consuming.
 */SourceMapConsumer.prototype._version=3;// `__generatedMappings` and `__originalMappings` are arrays that hold the
// parsed mapping coordinates from the source map's "mappings" attribute. They
// are lazily instantiated, accessed via the `_generatedMappings` and
// `_originalMappings` getters respectively, and we only parse the mappings
// and create these arrays once queried for a source location. We jump through
// these hoops because there can be many thousands of mappings, and parsing
// them is expensive, so we only want to do it if we must.
//
// Each object in the arrays is of the form:
//
//     {
//       generatedLine: The line number in the generated code,
//       generatedColumn: The column number in the generated code,
//       source: The path to the original source file that generated this
//               chunk of code,
//       originalLine: The line number in the original source that
//                     corresponds to this chunk of generated code,
//       originalColumn: The column number in the original source that
//                       corresponds to this chunk of generated code,
//       name: The name of the original symbol which generated this chunk of
//             code.
//     }
//
// All properties except for `generatedLine` and `generatedColumn` can be
// `null`.
//
// `_generatedMappings` is ordered by the generated positions.
//
// `_originalMappings` is ordered by the original positions.
SourceMapConsumer.prototype.__generatedMappings=null;Object.defineProperty(SourceMapConsumer.prototype,'_generatedMappings',{configurable:true,enumerable:true,get:function get(){if(!this.__generatedMappings){this._parseMappings(this._mappings,this.sourceRoot);}return this.__generatedMappings;}});SourceMapConsumer.prototype.__originalMappings=null;Object.defineProperty(SourceMapConsumer.prototype,'_originalMappings',{configurable:true,enumerable:true,get:function get(){if(!this.__originalMappings){this._parseMappings(this._mappings,this.sourceRoot);}return this.__originalMappings;}});SourceMapConsumer.prototype._charIsMappingSeparator=function SourceMapConsumer_charIsMappingSeparator(aStr,index){var c=aStr.charAt(index);return c===";"||c===",";};/**
 * Parse the mappings in a string in to a data structure which we can easily
 * query (the ordered arrays in the `this.__generatedMappings` and
 * `this.__originalMappings` properties).
 */SourceMapConsumer.prototype._parseMappings=function SourceMapConsumer_parseMappings(aStr,aSourceRoot){throw new Error("Subclasses must implement _parseMappings");};SourceMapConsumer.GENERATED_ORDER=1;SourceMapConsumer.ORIGINAL_ORDER=2;SourceMapConsumer.GREATEST_LOWER_BOUND=1;SourceMapConsumer.LEAST_UPPER_BOUND=2;/**
 * Iterate over each mapping between an original source/line/column and a
 * generated line/column in this source map.
 *
 * @param Function aCallback
 *        The function that is called with each mapping.
 * @param Object aContext
 *        Optional. If specified, this object will be the value of `this` every
 *        time that `aCallback` is called.
 * @param aOrder
 *        Either `SourceMapConsumer.GENERATED_ORDER` or
 *        `SourceMapConsumer.ORIGINAL_ORDER`. Specifies whether you want to
 *        iterate over the mappings sorted by the generated file's line/column
 *        order or the original's source/line/column order, respectively. Defaults to
 *        `SourceMapConsumer.GENERATED_ORDER`.
 */SourceMapConsumer.prototype.eachMapping=function SourceMapConsumer_eachMapping(aCallback,aContext,aOrder){var context=aContext||null;var order=aOrder||SourceMapConsumer.GENERATED_ORDER;var mappings;switch(order){case SourceMapConsumer.GENERATED_ORDER:mappings=this._generatedMappings;break;case SourceMapConsumer.ORIGINAL_ORDER:mappings=this._originalMappings;break;default:throw new Error("Unknown order of iteration.");}var sourceRoot=this.sourceRoot;mappings.map(function(mapping){var source=mapping.source===null?null:this._sources.at(mapping.source);source=util.computeSourceURL(sourceRoot,source,this._sourceMapURL);return{source:source,generatedLine:mapping.generatedLine,generatedColumn:mapping.generatedColumn,originalLine:mapping.originalLine,originalColumn:mapping.originalColumn,name:mapping.name===null?null:this._names.at(mapping.name)};},this).forEach(aCallback,context);};/**
 * Returns all generated line and column information for the original source,
 * line, and column provided. If no column is provided, returns all mappings
 * corresponding to a either the line we are searching for or the next
 * closest line that has any mappings. Otherwise, returns all mappings
 * corresponding to the given line and either the column we are searching for
 * or the next closest column that has any offsets.
 *
 * The only argument is an object with the following properties:
 *
 *   - source: The filename of the original source.
 *   - line: The line number in the original source.  The line number is 1-based.
 *   - column: Optional. the column number in the original source.
 *    The column number is 0-based.
 *
 * and an array of objects is returned, each with the following properties:
 *
 *   - line: The line number in the generated source, or null.  The
 *    line number is 1-based.
 *   - column: The column number in the generated source, or null.
 *    The column number is 0-based.
 */SourceMapConsumer.prototype.allGeneratedPositionsFor=function SourceMapConsumer_allGeneratedPositionsFor(aArgs){var line=util.getArg(aArgs,'line');// When there is no exact match, BasicSourceMapConsumer.prototype._findMapping
// returns the index of the closest mapping less than the needle. By
// setting needle.originalColumn to 0, we thus find the last mapping for
// the given line, provided such a mapping exists.
var needle={source:util.getArg(aArgs,'source'),originalLine:line,originalColumn:util.getArg(aArgs,'column',0)};needle.source=this._findSourceIndex(needle.source);if(needle.source<0){return[];}var mappings=[];var index=this._findMapping(needle,this._originalMappings,"originalLine","originalColumn",util.compareByOriginalPositions,binarySearch.LEAST_UPPER_BOUND);if(index>=0){var mapping=this._originalMappings[index];if(aArgs.column===undefined){var originalLine=mapping.originalLine;// Iterate until either we run out of mappings, or we run into
// a mapping for a different line than the one we found. Since
// mappings are sorted, this is guaranteed to find all mappings for
// the line we found.
while(mapping&&mapping.originalLine===originalLine){mappings.push({line:util.getArg(mapping,'generatedLine',null),column:util.getArg(mapping,'generatedColumn',null),lastColumn:util.getArg(mapping,'lastGeneratedColumn',null)});mapping=this._originalMappings[++index];}}else{var originalColumn=mapping.originalColumn;// Iterate until either we run out of mappings, or we run into
// a mapping for a different line than the one we were searching for.
// Since mappings are sorted, this is guaranteed to find all mappings for
// the line we are searching for.
while(mapping&&mapping.originalLine===line&&mapping.originalColumn==originalColumn){mappings.push({line:util.getArg(mapping,'generatedLine',null),column:util.getArg(mapping,'generatedColumn',null),lastColumn:util.getArg(mapping,'lastGeneratedColumn',null)});mapping=this._originalMappings[++index];}}}return mappings;};exports.SourceMapConsumer=SourceMapConsumer;/**
 * A BasicSourceMapConsumer instance represents a parsed source map which we can
 * query for information about the original file positions by giving it a file
 * position in the generated source.
 *
 * The first parameter is the raw source map (either as a JSON string, or
 * already parsed to an object). According to the spec, source maps have the
 * following attributes:
 *
 *   - version: Which version of the source map spec this map is following.
 *   - sources: An array of URLs to the original source files.
 *   - names: An array of identifiers which can be referrenced by individual mappings.
 *   - sourceRoot: Optional. The URL root from which all sources are relative.
 *   - sourcesContent: Optional. An array of contents of the original source files.
 *   - mappings: A string of base64 VLQs which contain the actual mappings.
 *   - file: Optional. The generated file this source map is associated with.
 *
 * Here is an example source map, taken from the source map spec[0]:
 *
 *     {
 *       version : 3,
 *       file: "out.js",
 *       sourceRoot : "",
 *       sources: ["foo.js", "bar.js"],
 *       names: ["src", "maps", "are", "fun"],
 *       mappings: "AA,AB;;ABCDE;"
 *     }
 *
 * The second parameter, if given, is a string whose value is the URL
 * at which the source map was found.  This URL is used to compute the
 * sources array.
 *
 * [0]: https://docs.google.com/document/d/1U1RGAehQwRypUTovF1KRlpiOFze0b-_2gc6fAH0KY0k/edit?pli=1#
 */function BasicSourceMapConsumer(aSourceMap,aSourceMapURL){var sourceMap=aSourceMap;if(typeof aSourceMap==='string'){sourceMap=util.parseSourceMapInput(aSourceMap);}var version=util.getArg(sourceMap,'version');var sources=util.getArg(sourceMap,'sources');// Sass 3.3 leaves out the 'names' array, so we deviate from the spec (which
// requires the array) to play nice here.
var names=util.getArg(sourceMap,'names',[]);var sourceRoot=util.getArg(sourceMap,'sourceRoot',null);var sourcesContent=util.getArg(sourceMap,'sourcesContent',null);var mappings=util.getArg(sourceMap,'mappings');var file=util.getArg(sourceMap,'file',null);// Once again, Sass deviates from the spec and supplies the version as a
// string rather than a number, so we use loose equality checking here.
if(version!=this._version){throw new Error('Unsupported version: '+version);}if(sourceRoot){sourceRoot=util.normalize(sourceRoot);}sources=sources.map(String)// Some source maps produce relative source paths like "./foo.js" instead of
// "foo.js".  Normalize these first so that future comparisons will succeed.
// See bugzil.la/1090768.
.map(util.normalize)// Always ensure that absolute sources are internally stored relative to
// the source root, if the source root is absolute. Not doing this would
// be particularly problematic when the source root is a prefix of the
// source (valid, but why??). See github issue #199 and bugzil.la/1188982.
.map(function(source){return sourceRoot&&util.isAbsolute(sourceRoot)&&util.isAbsolute(source)?util.relative(sourceRoot,source):source;});// Pass `true` below to allow duplicate names and sources. While source maps
// are intended to be compressed and deduplicated, the TypeScript compiler
// sometimes generates source maps with duplicates in them. See Github issue
// #72 and bugzil.la/889492.
this._names=ArraySet.fromArray(names.map(String),true);this._sources=ArraySet.fromArray(sources,true);this._absoluteSources=this._sources.toArray().map(function(s){return util.computeSourceURL(sourceRoot,s,aSourceMapURL);});this.sourceRoot=sourceRoot;this.sourcesContent=sourcesContent;this._mappings=mappings;this._sourceMapURL=aSourceMapURL;this.file=file;}BasicSourceMapConsumer.prototype=Object.create(SourceMapConsumer.prototype);BasicSourceMapConsumer.prototype.consumer=SourceMapConsumer;/**
 * Utility function to find the index of a source.  Returns -1 if not
 * found.
 */BasicSourceMapConsumer.prototype._findSourceIndex=function(aSource){var relativeSource=aSource;if(this.sourceRoot!=null){relativeSource=util.relative(this.sourceRoot,relativeSource);}if(this._sources.has(relativeSource)){return this._sources.indexOf(relativeSource);}// Maybe aSource is an absolute URL as returned by |sources|.  In
// this case we can't simply undo the transform.
var i;for(i=0;i<this._absoluteSources.length;++i){if(this._absoluteSources[i]==aSource){return i;}}return-1;};/**
 * Create a BasicSourceMapConsumer from a SourceMapGenerator.
 *
 * @param SourceMapGenerator aSourceMap
 *        The source map that will be consumed.
 * @param String aSourceMapURL
 *        The URL at which the source map can be found (optional)
 * @returns BasicSourceMapConsumer
 */BasicSourceMapConsumer.fromSourceMap=function SourceMapConsumer_fromSourceMap(aSourceMap,aSourceMapURL){var smc=Object.create(BasicSourceMapConsumer.prototype);var names=smc._names=ArraySet.fromArray(aSourceMap._names.toArray(),true);var sources=smc._sources=ArraySet.fromArray(aSourceMap._sources.toArray(),true);smc.sourceRoot=aSourceMap._sourceRoot;smc.sourcesContent=aSourceMap._generateSourcesContent(smc._sources.toArray(),smc.sourceRoot);smc.file=aSourceMap._file;smc._sourceMapURL=aSourceMapURL;smc._absoluteSources=smc._sources.toArray().map(function(s){return util.computeSourceURL(smc.sourceRoot,s,aSourceMapURL);});// Because we are modifying the entries (by converting string sources and
// names to indices into the sources and names ArraySets), we have to make
// a copy of the entry or else bad things happen. Shared mutable state
// strikes again! See github issue #191.
var generatedMappings=aSourceMap._mappings.toArray().slice();var destGeneratedMappings=smc.__generatedMappings=[];var destOriginalMappings=smc.__originalMappings=[];for(var i=0,length=generatedMappings.length;i<length;i++){var srcMapping=generatedMappings[i];var destMapping=new Mapping();destMapping.generatedLine=srcMapping.generatedLine;destMapping.generatedColumn=srcMapping.generatedColumn;if(srcMapping.source){destMapping.source=sources.indexOf(srcMapping.source);destMapping.originalLine=srcMapping.originalLine;destMapping.originalColumn=srcMapping.originalColumn;if(srcMapping.name){destMapping.name=names.indexOf(srcMapping.name);}destOriginalMappings.push(destMapping);}destGeneratedMappings.push(destMapping);}quickSort(smc.__originalMappings,util.compareByOriginalPositions);return smc;};/**
 * The version of the source mapping spec that we are consuming.
 */BasicSourceMapConsumer.prototype._version=3;/**
 * The list of original sources.
 */Object.defineProperty(BasicSourceMapConsumer.prototype,'sources',{get:function get(){return this._absoluteSources.slice();}});/**
 * Provide the JIT with a nice shape / hidden class.
 */function Mapping(){this.generatedLine=0;this.generatedColumn=0;this.source=null;this.originalLine=null;this.originalColumn=null;this.name=null;}/**
 * Parse the mappings in a string in to a data structure which we can easily
 * query (the ordered arrays in the `this.__generatedMappings` and
 * `this.__originalMappings` properties).
 */BasicSourceMapConsumer.prototype._parseMappings=function SourceMapConsumer_parseMappings(aStr,aSourceRoot){var generatedLine=1;var previousGeneratedColumn=0;var previousOriginalLine=0;var previousOriginalColumn=0;var previousSource=0;var previousName=0;var length=aStr.length;var index=0;var cachedSegments={};var temp={};var originalMappings=[];var generatedMappings=[];var mapping,str,segment,end,value;while(index<length){if(aStr.charAt(index)===';'){generatedLine++;index++;previousGeneratedColumn=0;}else if(aStr.charAt(index)===','){index++;}else{mapping=new Mapping();mapping.generatedLine=generatedLine;// Because each offset is encoded relative to the previous one,
// many segments often have the same encoding. We can exploit this
// fact by caching the parsed variable length fields of each segment,
// allowing us to avoid a second parse if we encounter the same
// segment again.
for(end=index;end<length;end++){if(this._charIsMappingSeparator(aStr,end)){break;}}str=aStr.slice(index,end);segment=cachedSegments[str];if(segment){index+=str.length;}else{segment=[];while(index<end){base64VLQ.decode(aStr,index,temp);value=temp.value;index=temp.rest;segment.push(value);}if(segment.length===2){throw new Error('Found a source, but no line and column');}if(segment.length===3){throw new Error('Found a source and line, but no column');}cachedSegments[str]=segment;}// Generated column.
mapping.generatedColumn=previousGeneratedColumn+segment[0];previousGeneratedColumn=mapping.generatedColumn;if(segment.length>1){// Original source.
mapping.source=previousSource+segment[1];previousSource+=segment[1];// Original line.
mapping.originalLine=previousOriginalLine+segment[2];previousOriginalLine=mapping.originalLine;// Lines are stored 0-based
mapping.originalLine+=1;// Original column.
mapping.originalColumn=previousOriginalColumn+segment[3];previousOriginalColumn=mapping.originalColumn;if(segment.length>4){// Original name.
mapping.name=previousName+segment[4];previousName+=segment[4];}}generatedMappings.push(mapping);if(typeof mapping.originalLine==='number'){originalMappings.push(mapping);}}}quickSort(generatedMappings,util.compareByGeneratedPositionsDeflated);this.__generatedMappings=generatedMappings;quickSort(originalMappings,util.compareByOriginalPositions);this.__originalMappings=originalMappings;};/**
 * Find the mapping that best matches the hypothetical "needle" mapping that
 * we are searching for in the given "haystack" of mappings.
 */BasicSourceMapConsumer.prototype._findMapping=function SourceMapConsumer_findMapping(aNeedle,aMappings,aLineName,aColumnName,aComparator,aBias){// To return the position we are searching for, we must first find the
// mapping for the given position and then return the opposite position it
// points to. Because the mappings are sorted, we can use binary search to
// find the best mapping.
if(aNeedle[aLineName]<=0){throw new TypeError('Line must be greater than or equal to 1, got '+aNeedle[aLineName]);}if(aNeedle[aColumnName]<0){throw new TypeError('Column must be greater than or equal to 0, got '+aNeedle[aColumnName]);}return binarySearch.search(aNeedle,aMappings,aComparator,aBias);};/**
 * Compute the last column for each generated mapping. The last column is
 * inclusive.
 */BasicSourceMapConsumer.prototype.computeColumnSpans=function SourceMapConsumer_computeColumnSpans(){for(var index=0;index<this._generatedMappings.length;++index){var mapping=this._generatedMappings[index];// Mappings do not contain a field for the last generated columnt. We
// can come up with an optimistic estimate, however, by assuming that
// mappings are contiguous (i.e. given two consecutive mappings, the
// first mapping ends where the second one starts).
if(index+1<this._generatedMappings.length){var nextMapping=this._generatedMappings[index+1];if(mapping.generatedLine===nextMapping.generatedLine){mapping.lastGeneratedColumn=nextMapping.generatedColumn-1;continue;}}// The last mapping for each line spans the entire line.
mapping.lastGeneratedColumn=Infinity;}};/**
 * Returns the original source, line, and column information for the generated
 * source's line and column positions provided. The only argument is an object
 * with the following properties:
 *
 *   - line: The line number in the generated source.  The line number
 *     is 1-based.
 *   - column: The column number in the generated source.  The column
 *     number is 0-based.
 *   - bias: Either 'SourceMapConsumer.GREATEST_LOWER_BOUND' or
 *     'SourceMapConsumer.LEAST_UPPER_BOUND'. Specifies whether to return the
 *     closest element that is smaller than or greater than the one we are
 *     searching for, respectively, if the exact element cannot be found.
 *     Defaults to 'SourceMapConsumer.GREATEST_LOWER_BOUND'.
 *
 * and an object is returned with the following properties:
 *
 *   - source: The original source file, or null.
 *   - line: The line number in the original source, or null.  The
 *     line number is 1-based.
 *   - column: The column number in the original source, or null.  The
 *     column number is 0-based.
 *   - name: The original identifier, or null.
 */BasicSourceMapConsumer.prototype.originalPositionFor=function SourceMapConsumer_originalPositionFor(aArgs){var needle={generatedLine:util.getArg(aArgs,'line'),generatedColumn:util.getArg(aArgs,'column')};var index=this._findMapping(needle,this._generatedMappings,"generatedLine","generatedColumn",util.compareByGeneratedPositionsDeflated,util.getArg(aArgs,'bias',SourceMapConsumer.GREATEST_LOWER_BOUND));if(index>=0){var mapping=this._generatedMappings[index];if(mapping.generatedLine===needle.generatedLine){var source=util.getArg(mapping,'source',null);if(source!==null){source=this._sources.at(source);source=util.computeSourceURL(this.sourceRoot,source,this._sourceMapURL);}var name=util.getArg(mapping,'name',null);if(name!==null){name=this._names.at(name);}return{source:source,line:util.getArg(mapping,'originalLine',null),column:util.getArg(mapping,'originalColumn',null),name:name};}}return{source:null,line:null,column:null,name:null};};/**
 * Return true if we have the source content for every source in the source
 * map, false otherwise.
 */BasicSourceMapConsumer.prototype.hasContentsOfAllSources=function BasicSourceMapConsumer_hasContentsOfAllSources(){if(!this.sourcesContent){return false;}return this.sourcesContent.length>=this._sources.size()&&!this.sourcesContent.some(function(sc){return sc==null;});};/**
 * Returns the original source content. The only argument is the url of the
 * original source file. Returns null if no original source content is
 * available.
 */BasicSourceMapConsumer.prototype.sourceContentFor=function SourceMapConsumer_sourceContentFor(aSource,nullOnMissing){if(!this.sourcesContent){return null;}var index=this._findSourceIndex(aSource);if(index>=0){return this.sourcesContent[index];}var relativeSource=aSource;if(this.sourceRoot!=null){relativeSource=util.relative(this.sourceRoot,relativeSource);}var url;if(this.sourceRoot!=null&&(url=util.urlParse(this.sourceRoot))){// XXX: file:// URIs and absolute paths lead to unexpected behavior for
// many users. We can help them out when they expect file:// URIs to
// behave like it would if they were running a local HTTP server. See
// https://bugzilla.mozilla.org/show_bug.cgi?id=885597.
var fileUriAbsPath=relativeSource.replace(/^file:\/\//,"");if(url.scheme=="file"&&this._sources.has(fileUriAbsPath)){return this.sourcesContent[this._sources.indexOf(fileUriAbsPath)];}if((!url.path||url.path=="/")&&this._sources.has("/"+relativeSource)){return this.sourcesContent[this._sources.indexOf("/"+relativeSource)];}}// This function is used recursively from
// IndexedSourceMapConsumer.prototype.sourceContentFor. In that case, we
// don't want to throw if we can't find the source - we just want to
// return null, so we provide a flag to exit gracefully.
if(nullOnMissing){return null;}else{throw new Error('"'+relativeSource+'" is not in the SourceMap.');}};/**
 * Returns the generated line and column information for the original source,
 * line, and column positions provided. The only argument is an object with
 * the following properties:
 *
 *   - source: The filename of the original source.
 *   - line: The line number in the original source.  The line number
 *     is 1-based.
 *   - column: The column number in the original source.  The column
 *     number is 0-based.
 *   - bias: Either 'SourceMapConsumer.GREATEST_LOWER_BOUND' or
 *     'SourceMapConsumer.LEAST_UPPER_BOUND'. Specifies whether to return the
 *     closest element that is smaller than or greater than the one we are
 *     searching for, respectively, if the exact element cannot be found.
 *     Defaults to 'SourceMapConsumer.GREATEST_LOWER_BOUND'.
 *
 * and an object is returned with the following properties:
 *
 *   - line: The line number in the generated source, or null.  The
 *     line number is 1-based.
 *   - column: The column number in the generated source, or null.
 *     The column number is 0-based.
 */BasicSourceMapConsumer.prototype.generatedPositionFor=function SourceMapConsumer_generatedPositionFor(aArgs){var source=util.getArg(aArgs,'source');source=this._findSourceIndex(source);if(source<0){return{line:null,column:null,lastColumn:null};}var needle={source:source,originalLine:util.getArg(aArgs,'line'),originalColumn:util.getArg(aArgs,'column')};var index=this._findMapping(needle,this._originalMappings,"originalLine","originalColumn",util.compareByOriginalPositions,util.getArg(aArgs,'bias',SourceMapConsumer.GREATEST_LOWER_BOUND));if(index>=0){var mapping=this._originalMappings[index];if(mapping.source===needle.source){return{line:util.getArg(mapping,'generatedLine',null),column:util.getArg(mapping,'generatedColumn',null),lastColumn:util.getArg(mapping,'lastGeneratedColumn',null)};}}return{line:null,column:null,lastColumn:null};};exports.BasicSourceMapConsumer=BasicSourceMapConsumer;/**
 * An IndexedSourceMapConsumer instance represents a parsed source map which
 * we can query for information. It differs from BasicSourceMapConsumer in
 * that it takes "indexed" source maps (i.e. ones with a "sections" field) as
 * input.
 *
 * The first parameter is a raw source map (either as a JSON string, or already
 * parsed to an object). According to the spec for indexed source maps, they
 * have the following attributes:
 *
 *   - version: Which version of the source map spec this map is following.
 *   - file: Optional. The generated file this source map is associated with.
 *   - sections: A list of section definitions.
 *
 * Each value under the "sections" field has two fields:
 *   - offset: The offset into the original specified at which this section
 *       begins to apply, defined as an object with a "line" and "column"
 *       field.
 *   - map: A source map definition. This source map could also be indexed,
 *       but doesn't have to be.
 *
 * Instead of the "map" field, it's also possible to have a "url" field
 * specifying a URL to retrieve a source map from, but that's currently
 * unsupported.
 *
 * Here's an example source map, taken from the source map spec[0], but
 * modified to omit a section which uses the "url" field.
 *
 *  {
 *    version : 3,
 *    file: "app.js",
 *    sections: [{
 *      offset: {line:100, column:10},
 *      map: {
 *        version : 3,
 *        file: "section.js",
 *        sources: ["foo.js", "bar.js"],
 *        names: ["src", "maps", "are", "fun"],
 *        mappings: "AAAA,E;;ABCDE;"
 *      }
 *    }],
 *  }
 *
 * The second parameter, if given, is a string whose value is the URL
 * at which the source map was found.  This URL is used to compute the
 * sources array.
 *
 * [0]: https://docs.google.com/document/d/1U1RGAehQwRypUTovF1KRlpiOFze0b-_2gc6fAH0KY0k/edit#heading=h.535es3xeprgt
 */function IndexedSourceMapConsumer(aSourceMap,aSourceMapURL){var sourceMap=aSourceMap;if(typeof aSourceMap==='string'){sourceMap=util.parseSourceMapInput(aSourceMap);}var version=util.getArg(sourceMap,'version');var sections=util.getArg(sourceMap,'sections');if(version!=this._version){throw new Error('Unsupported version: '+version);}this._sources=new ArraySet();this._names=new ArraySet();var lastOffset={line:-1,column:0};this._sections=sections.map(function(s){if(s.url){// The url field will require support for asynchronicity.
// See https://github.com/mozilla/source-map/issues/16
throw new Error('Support for url field in sections not implemented.');}var offset=util.getArg(s,'offset');var offsetLine=util.getArg(offset,'line');var offsetColumn=util.getArg(offset,'column');if(offsetLine<lastOffset.line||offsetLine===lastOffset.line&&offsetColumn<lastOffset.column){throw new Error('Section offsets must be ordered and non-overlapping.');}lastOffset=offset;return{generatedOffset:{// The offset fields are 0-based, but we use 1-based indices when
// encoding/decoding from VLQ.
generatedLine:offsetLine+1,generatedColumn:offsetColumn+1},consumer:new SourceMapConsumer(util.getArg(s,'map'),aSourceMapURL)};});}IndexedSourceMapConsumer.prototype=Object.create(SourceMapConsumer.prototype);IndexedSourceMapConsumer.prototype.constructor=SourceMapConsumer;/**
 * The version of the source mapping spec that we are consuming.
 */IndexedSourceMapConsumer.prototype._version=3;/**
 * The list of original sources.
 */Object.defineProperty(IndexedSourceMapConsumer.prototype,'sources',{get:function get(){var sources=[];for(var i=0;i<this._sections.length;i++){for(var j=0;j<this._sections[i].consumer.sources.length;j++){sources.push(this._sections[i].consumer.sources[j]);}}return sources;}});/**
 * Returns the original source, line, and column information for the generated
 * source's line and column positions provided. The only argument is an object
 * with the following properties:
 *
 *   - line: The line number in the generated source.  The line number
 *     is 1-based.
 *   - column: The column number in the generated source.  The column
 *     number is 0-based.
 *
 * and an object is returned with the following properties:
 *
 *   - source: The original source file, or null.
 *   - line: The line number in the original source, or null.  The
 *     line number is 1-based.
 *   - column: The column number in the original source, or null.  The
 *     column number is 0-based.
 *   - name: The original identifier, or null.
 */IndexedSourceMapConsumer.prototype.originalPositionFor=function IndexedSourceMapConsumer_originalPositionFor(aArgs){var needle={generatedLine:util.getArg(aArgs,'line'),generatedColumn:util.getArg(aArgs,'column')};// Find the section containing the generated position we're trying to map
// to an original position.
var sectionIndex=binarySearch.search(needle,this._sections,function(needle,section){var cmp=needle.generatedLine-section.generatedOffset.generatedLine;if(cmp){return cmp;}return needle.generatedColumn-section.generatedOffset.generatedColumn;});var section=this._sections[sectionIndex];if(!section){return{source:null,line:null,column:null,name:null};}return section.consumer.originalPositionFor({line:needle.generatedLine-(section.generatedOffset.generatedLine-1),column:needle.generatedColumn-(section.generatedOffset.generatedLine===needle.generatedLine?section.generatedOffset.generatedColumn-1:0),bias:aArgs.bias});};/**
 * Return true if we have the source content for every source in the source
 * map, false otherwise.
 */IndexedSourceMapConsumer.prototype.hasContentsOfAllSources=function IndexedSourceMapConsumer_hasContentsOfAllSources(){return this._sections.every(function(s){return s.consumer.hasContentsOfAllSources();});};/**
 * Returns the original source content. The only argument is the url of the
 * original source file. Returns null if no original source content is
 * available.
 */IndexedSourceMapConsumer.prototype.sourceContentFor=function IndexedSourceMapConsumer_sourceContentFor(aSource,nullOnMissing){for(var i=0;i<this._sections.length;i++){var section=this._sections[i];var content=section.consumer.sourceContentFor(aSource,true);if(content){return content;}}if(nullOnMissing){return null;}else{throw new Error('"'+aSource+'" is not in the SourceMap.');}};/**
 * Returns the generated line and column information for the original source,
 * line, and column positions provided. The only argument is an object with
 * the following properties:
 *
 *   - source: The filename of the original source.
 *   - line: The line number in the original source.  The line number
 *     is 1-based.
 *   - column: The column number in the original source.  The column
 *     number is 0-based.
 *
 * and an object is returned with the following properties:
 *
 *   - line: The line number in the generated source, or null.  The
 *     line number is 1-based. 
 *   - column: The column number in the generated source, or null.
 *     The column number is 0-based.
 */IndexedSourceMapConsumer.prototype.generatedPositionFor=function IndexedSourceMapConsumer_generatedPositionFor(aArgs){for(var i=0;i<this._sections.length;i++){var section=this._sections[i];// Only consider this section if the requested source is in the list of
// sources of the consumer.
if(section.consumer._findSourceIndex(util.getArg(aArgs,'source'))===-1){continue;}var generatedPosition=section.consumer.generatedPositionFor(aArgs);if(generatedPosition){var ret={line:generatedPosition.line+(section.generatedOffset.generatedLine-1),column:generatedPosition.column+(section.generatedOffset.generatedLine===generatedPosition.line?section.generatedOffset.generatedColumn-1:0)};return ret;}}return{line:null,column:null};};/**
 * Parse the mappings in a string in to a data structure which we can easily
 * query (the ordered arrays in the `this.__generatedMappings` and
 * `this.__originalMappings` properties).
 */IndexedSourceMapConsumer.prototype._parseMappings=function IndexedSourceMapConsumer_parseMappings(aStr,aSourceRoot){this.__generatedMappings=[];this.__originalMappings=[];for(var i=0;i<this._sections.length;i++){var section=this._sections[i];var sectionMappings=section.consumer._generatedMappings;for(var j=0;j<sectionMappings.length;j++){var mapping=sectionMappings[j];var source=section.consumer._sources.at(mapping.source);source=util.computeSourceURL(section.consumer.sourceRoot,source,this._sourceMapURL);this._sources.add(source);source=this._sources.indexOf(source);var name=null;if(mapping.name){name=section.consumer._names.at(mapping.name);this._names.add(name);name=this._names.indexOf(name);}// The mappings coming from the consumer for the section have
// generated positions relative to the start of the section, so we
// need to offset them to be relative to the start of the concatenated
// generated file.
var adjustedMapping={source:source,generatedLine:mapping.generatedLine+(section.generatedOffset.generatedLine-1),generatedColumn:mapping.generatedColumn+(section.generatedOffset.generatedLine===mapping.generatedLine?section.generatedOffset.generatedColumn-1:0),originalLine:mapping.originalLine,originalColumn:mapping.originalColumn,name:name};this.__generatedMappings.push(adjustedMapping);if(typeof adjustedMapping.originalLine==='number'){this.__originalMappings.push(adjustedMapping);}}}quickSort(this.__generatedMappings,util.compareByGeneratedPositionsDeflated);quickSort(this.__originalMappings,util.compareByOriginalPositions);};exports.IndexedSourceMapConsumer=IndexedSourceMapConsumer;},{"./array-set":198,"./base64-vlq":199,"./binary-search":201,"./quick-sort":203,"./util":207}],205:[function(require,module,exports){/* -*- Mode: js; js-indent-level: 2; -*- */ /*
 * Copyright 2011 Mozilla Foundation and contributors
 * Licensed under the New BSD license. See LICENSE or:
 * http://opensource.org/licenses/BSD-3-Clause
 */var base64VLQ=require('./base64-vlq');var util=require('./util');var ArraySet=require('./array-set').ArraySet;var MappingList=require('./mapping-list').MappingList;/**
 * An instance of the SourceMapGenerator represents a source map which is
 * being built incrementally. You may pass an object with the following
 * properties:
 *
 *   - file: The filename of the generated source.
 *   - sourceRoot: A root for all relative URLs in this source map.
 */function SourceMapGenerator(aArgs){if(!aArgs){aArgs={};}this._file=util.getArg(aArgs,'file',null);this._sourceRoot=util.getArg(aArgs,'sourceRoot',null);this._skipValidation=util.getArg(aArgs,'skipValidation',false);this._sources=new ArraySet();this._names=new ArraySet();this._mappings=new MappingList();this._sourcesContents=null;}SourceMapGenerator.prototype._version=3;/**
 * Creates a new SourceMapGenerator based on a SourceMapConsumer
 *
 * @param aSourceMapConsumer The SourceMap.
 */SourceMapGenerator.fromSourceMap=function SourceMapGenerator_fromSourceMap(aSourceMapConsumer){var sourceRoot=aSourceMapConsumer.sourceRoot;var generator=new SourceMapGenerator({file:aSourceMapConsumer.file,sourceRoot:sourceRoot});aSourceMapConsumer.eachMapping(function(mapping){var newMapping={generated:{line:mapping.generatedLine,column:mapping.generatedColumn}};if(mapping.source!=null){newMapping.source=mapping.source;if(sourceRoot!=null){newMapping.source=util.relative(sourceRoot,newMapping.source);}newMapping.original={line:mapping.originalLine,column:mapping.originalColumn};if(mapping.name!=null){newMapping.name=mapping.name;}}generator.addMapping(newMapping);});aSourceMapConsumer.sources.forEach(function(sourceFile){var sourceRelative=sourceFile;if(sourceRoot!==null){sourceRelative=util.relative(sourceRoot,sourceFile);}if(!generator._sources.has(sourceRelative)){generator._sources.add(sourceRelative);}var content=aSourceMapConsumer.sourceContentFor(sourceFile);if(content!=null){generator.setSourceContent(sourceFile,content);}});return generator;};/**
 * Add a single mapping from original source line and column to the generated
 * source's line and column for this source map being created. The mapping
 * object should have the following properties:
 *
 *   - generated: An object with the generated line and column positions.
 *   - original: An object with the original line and column positions.
 *   - source: The original source file (relative to the sourceRoot).
 *   - name: An optional original token name for this mapping.
 */SourceMapGenerator.prototype.addMapping=function SourceMapGenerator_addMapping(aArgs){var generated=util.getArg(aArgs,'generated');var original=util.getArg(aArgs,'original',null);var source=util.getArg(aArgs,'source',null);var name=util.getArg(aArgs,'name',null);if(!this._skipValidation){this._validateMapping(generated,original,source,name);}if(source!=null){source=String(source);if(!this._sources.has(source)){this._sources.add(source);}}if(name!=null){name=String(name);if(!this._names.has(name)){this._names.add(name);}}this._mappings.add({generatedLine:generated.line,generatedColumn:generated.column,originalLine:original!=null&&original.line,originalColumn:original!=null&&original.column,source:source,name:name});};/**
 * Set the source content for a source file.
 */SourceMapGenerator.prototype.setSourceContent=function SourceMapGenerator_setSourceContent(aSourceFile,aSourceContent){var source=aSourceFile;if(this._sourceRoot!=null){source=util.relative(this._sourceRoot,source);}if(aSourceContent!=null){// Add the source content to the _sourcesContents map.
// Create a new _sourcesContents map if the property is null.
if(!this._sourcesContents){this._sourcesContents=Object.create(null);}this._sourcesContents[util.toSetString(source)]=aSourceContent;}else if(this._sourcesContents){// Remove the source file from the _sourcesContents map.
// If the _sourcesContents map is empty, set the property to null.
delete this._sourcesContents[util.toSetString(source)];if(Object.keys(this._sourcesContents).length===0){this._sourcesContents=null;}}};/**
 * Applies the mappings of a sub-source-map for a specific source file to the
 * source map being generated. Each mapping to the supplied source file is
 * rewritten using the supplied source map. Note: The resolution for the
 * resulting mappings is the minimium of this map and the supplied map.
 *
 * @param aSourceMapConsumer The source map to be applied.
 * @param aSourceFile Optional. The filename of the source file.
 *        If omitted, SourceMapConsumer's file property will be used.
 * @param aSourceMapPath Optional. The dirname of the path to the source map
 *        to be applied. If relative, it is relative to the SourceMapConsumer.
 *        This parameter is needed when the two source maps aren't in the same
 *        directory, and the source map to be applied contains relative source
 *        paths. If so, those relative source paths need to be rewritten
 *        relative to the SourceMapGenerator.
 */SourceMapGenerator.prototype.applySourceMap=function SourceMapGenerator_applySourceMap(aSourceMapConsumer,aSourceFile,aSourceMapPath){var sourceFile=aSourceFile;// If aSourceFile is omitted, we will use the file property of the SourceMap
if(aSourceFile==null){if(aSourceMapConsumer.file==null){throw new Error('SourceMapGenerator.prototype.applySourceMap requires either an explicit source file, '+'or the source map\'s "file" property. Both were omitted.');}sourceFile=aSourceMapConsumer.file;}var sourceRoot=this._sourceRoot;// Make "sourceFile" relative if an absolute Url is passed.
if(sourceRoot!=null){sourceFile=util.relative(sourceRoot,sourceFile);}// Applying the SourceMap can add and remove items from the sources and
// the names array.
var newSources=new ArraySet();var newNames=new ArraySet();// Find mappings for the "sourceFile"
this._mappings.unsortedForEach(function(mapping){if(mapping.source===sourceFile&&mapping.originalLine!=null){// Check if it can be mapped by the source map, then update the mapping.
var original=aSourceMapConsumer.originalPositionFor({line:mapping.originalLine,column:mapping.originalColumn});if(original.source!=null){// Copy mapping
mapping.source=original.source;if(aSourceMapPath!=null){mapping.source=util.join(aSourceMapPath,mapping.source);}if(sourceRoot!=null){mapping.source=util.relative(sourceRoot,mapping.source);}mapping.originalLine=original.line;mapping.originalColumn=original.column;if(original.name!=null){mapping.name=original.name;}}}var source=mapping.source;if(source!=null&&!newSources.has(source)){newSources.add(source);}var name=mapping.name;if(name!=null&&!newNames.has(name)){newNames.add(name);}},this);this._sources=newSources;this._names=newNames;// Copy sourcesContents of applied map.
aSourceMapConsumer.sources.forEach(function(sourceFile){var content=aSourceMapConsumer.sourceContentFor(sourceFile);if(content!=null){if(aSourceMapPath!=null){sourceFile=util.join(aSourceMapPath,sourceFile);}if(sourceRoot!=null){sourceFile=util.relative(sourceRoot,sourceFile);}this.setSourceContent(sourceFile,content);}},this);};/**
 * A mapping can have one of the three levels of data:
 *
 *   1. Just the generated position.
 *   2. The Generated position, original position, and original source.
 *   3. Generated and original position, original source, as well as a name
 *      token.
 *
 * To maintain consistency, we validate that any new mapping being added falls
 * in to one of these categories.
 */SourceMapGenerator.prototype._validateMapping=function SourceMapGenerator_validateMapping(aGenerated,aOriginal,aSource,aName){// When aOriginal is truthy but has empty values for .line and .column,
// it is most likely a programmer error. In this case we throw a very
// specific error message to try to guide them the right way.
// For example: https://github.com/Polymer/polymer-bundler/pull/519
if(aOriginal&&typeof aOriginal.line!=='number'&&typeof aOriginal.column!=='number'){throw new Error('original.line and original.column are not numbers -- you probably meant to omit '+'the original mapping entirely and only map the generated position. If so, pass '+'null for the original mapping instead of an object with empty or null values.');}if(aGenerated&&'line'in aGenerated&&'column'in aGenerated&&aGenerated.line>0&&aGenerated.column>=0&&!aOriginal&&!aSource&&!aName){// Case 1.
return;}else if(aGenerated&&'line'in aGenerated&&'column'in aGenerated&&aOriginal&&'line'in aOriginal&&'column'in aOriginal&&aGenerated.line>0&&aGenerated.column>=0&&aOriginal.line>0&&aOriginal.column>=0&&aSource){// Cases 2 and 3.
return;}else{throw new Error('Invalid mapping: '+JSON.stringify({generated:aGenerated,source:aSource,original:aOriginal,name:aName}));}};/**
 * Serialize the accumulated mappings in to the stream of base 64 VLQs
 * specified by the source map format.
 */SourceMapGenerator.prototype._serializeMappings=function SourceMapGenerator_serializeMappings(){var previousGeneratedColumn=0;var previousGeneratedLine=1;var previousOriginalColumn=0;var previousOriginalLine=0;var previousName=0;var previousSource=0;var result='';var next;var mapping;var nameIdx;var sourceIdx;var mappings=this._mappings.toArray();for(var i=0,len=mappings.length;i<len;i++){mapping=mappings[i];next='';if(mapping.generatedLine!==previousGeneratedLine){previousGeneratedColumn=0;while(mapping.generatedLine!==previousGeneratedLine){next+=';';previousGeneratedLine++;}}else{if(i>0){if(!util.compareByGeneratedPositionsInflated(mapping,mappings[i-1])){continue;}next+=',';}}next+=base64VLQ.encode(mapping.generatedColumn-previousGeneratedColumn);previousGeneratedColumn=mapping.generatedColumn;if(mapping.source!=null){sourceIdx=this._sources.indexOf(mapping.source);next+=base64VLQ.encode(sourceIdx-previousSource);previousSource=sourceIdx;// lines are stored 0-based in SourceMap spec version 3
next+=base64VLQ.encode(mapping.originalLine-1-previousOriginalLine);previousOriginalLine=mapping.originalLine-1;next+=base64VLQ.encode(mapping.originalColumn-previousOriginalColumn);previousOriginalColumn=mapping.originalColumn;if(mapping.name!=null){nameIdx=this._names.indexOf(mapping.name);next+=base64VLQ.encode(nameIdx-previousName);previousName=nameIdx;}}result+=next;}return result;};SourceMapGenerator.prototype._generateSourcesContent=function SourceMapGenerator_generateSourcesContent(aSources,aSourceRoot){return aSources.map(function(source){if(!this._sourcesContents){return null;}if(aSourceRoot!=null){source=util.relative(aSourceRoot,source);}var key=util.toSetString(source);return Object.prototype.hasOwnProperty.call(this._sourcesContents,key)?this._sourcesContents[key]:null;},this);};/**
 * Externalize the source map.
 */SourceMapGenerator.prototype.toJSON=function SourceMapGenerator_toJSON(){var map={version:this._version,sources:this._sources.toArray(),names:this._names.toArray(),mappings:this._serializeMappings()};if(this._file!=null){map.file=this._file;}if(this._sourceRoot!=null){map.sourceRoot=this._sourceRoot;}if(this._sourcesContents){map.sourcesContent=this._generateSourcesContent(map.sources,map.sourceRoot);}return map;};/**
 * Render the source map being generated to a string.
 */SourceMapGenerator.prototype.toString=function SourceMapGenerator_toString(){return JSON.stringify(this.toJSON());};exports.SourceMapGenerator=SourceMapGenerator;},{"./array-set":198,"./base64-vlq":199,"./mapping-list":202,"./util":207}],206:[function(require,module,exports){/* -*- Mode: js; js-indent-level: 2; -*- */ /*
 * Copyright 2011 Mozilla Foundation and contributors
 * Licensed under the New BSD license. See LICENSE or:
 * http://opensource.org/licenses/BSD-3-Clause
 */var SourceMapGenerator=require('./source-map-generator').SourceMapGenerator;var util=require('./util');// Matches a Windows-style `\r\n` newline or a `\n` newline used by all other
// operating systems these days (capturing the result).
var REGEX_NEWLINE=/(\r?\n)/;// Newline character code for charCodeAt() comparisons
var NEWLINE_CODE=10;// Private symbol for identifying `SourceNode`s when multiple versions of
// the source-map library are loaded. This MUST NOT CHANGE across
// versions!
var isSourceNode="$$$isSourceNode$$$";/**
 * SourceNodes provide a way to abstract over interpolating/concatenating
 * snippets of generated JavaScript source code while maintaining the line and
 * column information associated with the original source code.
 *
 * @param aLine The original line number.
 * @param aColumn The original column number.
 * @param aSource The original source's filename.
 * @param aChunks Optional. An array of strings which are snippets of
 *        generated JS, or other SourceNodes.
 * @param aName The original identifier.
 */function SourceNode(aLine,aColumn,aSource,aChunks,aName){this.children=[];this.sourceContents={};this.line=aLine==null?null:aLine;this.column=aColumn==null?null:aColumn;this.source=aSource==null?null:aSource;this.name=aName==null?null:aName;this[isSourceNode]=true;if(aChunks!=null)this.add(aChunks);}/**
 * Creates a SourceNode from generated code and a SourceMapConsumer.
 *
 * @param aGeneratedCode The generated code
 * @param aSourceMapConsumer The SourceMap for the generated code
 * @param aRelativePath Optional. The path that relative sources in the
 *        SourceMapConsumer should be relative to.
 */SourceNode.fromStringWithSourceMap=function SourceNode_fromStringWithSourceMap(aGeneratedCode,aSourceMapConsumer,aRelativePath){// The SourceNode we want to fill with the generated code
// and the SourceMap
var node=new SourceNode();// All even indices of this array are one line of the generated code,
// while all odd indices are the newlines between two adjacent lines
// (since `REGEX_NEWLINE` captures its match).
// Processed fragments are accessed by calling `shiftNextLine`.
var remainingLines=aGeneratedCode.split(REGEX_NEWLINE);var remainingLinesIndex=0;var shiftNextLine=function shiftNextLine(){var lineContents=getNextLine();// The last line of a file might not have a newline.
var newLine=getNextLine()||"";return lineContents+newLine;function getNextLine(){return remainingLinesIndex<remainingLines.length?remainingLines[remainingLinesIndex++]:undefined;}};// We need to remember the position of "remainingLines"
var lastGeneratedLine=1,lastGeneratedColumn=0;// The generate SourceNodes we need a code range.
// To extract it current and last mapping is used.
// Here we store the last mapping.
var lastMapping=null;aSourceMapConsumer.eachMapping(function(mapping){if(lastMapping!==null){// We add the code from "lastMapping" to "mapping":
// First check if there is a new line in between.
if(lastGeneratedLine<mapping.generatedLine){// Associate first line with "lastMapping"
addMappingWithCode(lastMapping,shiftNextLine());lastGeneratedLine++;lastGeneratedColumn=0;// The remaining code is added without mapping
}else{// There is no new line in between.
// Associate the code between "lastGeneratedColumn" and
// "mapping.generatedColumn" with "lastMapping"
var nextLine=remainingLines[remainingLinesIndex]||'';var code=nextLine.substr(0,mapping.generatedColumn-lastGeneratedColumn);remainingLines[remainingLinesIndex]=nextLine.substr(mapping.generatedColumn-lastGeneratedColumn);lastGeneratedColumn=mapping.generatedColumn;addMappingWithCode(lastMapping,code);// No more remaining code, continue
lastMapping=mapping;return;}}// We add the generated code until the first mapping
// to the SourceNode without any mapping.
// Each line is added as separate string.
while(lastGeneratedLine<mapping.generatedLine){node.add(shiftNextLine());lastGeneratedLine++;}if(lastGeneratedColumn<mapping.generatedColumn){var nextLine=remainingLines[remainingLinesIndex]||'';node.add(nextLine.substr(0,mapping.generatedColumn));remainingLines[remainingLinesIndex]=nextLine.substr(mapping.generatedColumn);lastGeneratedColumn=mapping.generatedColumn;}lastMapping=mapping;},this);// We have processed all mappings.
if(remainingLinesIndex<remainingLines.length){if(lastMapping){// Associate the remaining code in the current line with "lastMapping"
addMappingWithCode(lastMapping,shiftNextLine());}// and add the remaining lines without any mapping
node.add(remainingLines.splice(remainingLinesIndex).join(""));}// Copy sourcesContent into SourceNode
aSourceMapConsumer.sources.forEach(function(sourceFile){var content=aSourceMapConsumer.sourceContentFor(sourceFile);if(content!=null){if(aRelativePath!=null){sourceFile=util.join(aRelativePath,sourceFile);}node.setSourceContent(sourceFile,content);}});return node;function addMappingWithCode(mapping,code){if(mapping===null||mapping.source===undefined){node.add(code);}else{var source=aRelativePath?util.join(aRelativePath,mapping.source):mapping.source;node.add(new SourceNode(mapping.originalLine,mapping.originalColumn,source,code,mapping.name));}}};/**
 * Add a chunk of generated JS to this source node.
 *
 * @param aChunk A string snippet of generated JS code, another instance of
 *        SourceNode, or an array where each member is one of those things.
 */SourceNode.prototype.add=function SourceNode_add(aChunk){if(Array.isArray(aChunk)){aChunk.forEach(function(chunk){this.add(chunk);},this);}else if(aChunk[isSourceNode]||typeof aChunk==="string"){if(aChunk){this.children.push(aChunk);}}else{throw new TypeError("Expected a SourceNode, string, or an array of SourceNodes and strings. Got "+aChunk);}return this;};/**
 * Add a chunk of generated JS to the beginning of this source node.
 *
 * @param aChunk A string snippet of generated JS code, another instance of
 *        SourceNode, or an array where each member is one of those things.
 */SourceNode.prototype.prepend=function SourceNode_prepend(aChunk){if(Array.isArray(aChunk)){for(var i=aChunk.length-1;i>=0;i--){this.prepend(aChunk[i]);}}else if(aChunk[isSourceNode]||typeof aChunk==="string"){this.children.unshift(aChunk);}else{throw new TypeError("Expected a SourceNode, string, or an array of SourceNodes and strings. Got "+aChunk);}return this;};/**
 * Walk over the tree of JS snippets in this node and its children. The
 * walking function is called once for each snippet of JS and is passed that
 * snippet and the its original associated source's line/column location.
 *
 * @param aFn The traversal function.
 */SourceNode.prototype.walk=function SourceNode_walk(aFn){var chunk;for(var i=0,len=this.children.length;i<len;i++){chunk=this.children[i];if(chunk[isSourceNode]){chunk.walk(aFn);}else{if(chunk!==''){aFn(chunk,{source:this.source,line:this.line,column:this.column,name:this.name});}}}};/**
 * Like `String.prototype.join` except for SourceNodes. Inserts `aStr` between
 * each of `this.children`.
 *
 * @param aSep The separator.
 */SourceNode.prototype.join=function SourceNode_join(aSep){var newChildren;var i;var len=this.children.length;if(len>0){newChildren=[];for(i=0;i<len-1;i++){newChildren.push(this.children[i]);newChildren.push(aSep);}newChildren.push(this.children[i]);this.children=newChildren;}return this;};/**
 * Call String.prototype.replace on the very right-most source snippet. Useful
 * for trimming whitespace from the end of a source node, etc.
 *
 * @param aPattern The pattern to replace.
 * @param aReplacement The thing to replace the pattern with.
 */SourceNode.prototype.replaceRight=function SourceNode_replaceRight(aPattern,aReplacement){var lastChild=this.children[this.children.length-1];if(lastChild[isSourceNode]){lastChild.replaceRight(aPattern,aReplacement);}else if(typeof lastChild==='string'){this.children[this.children.length-1]=lastChild.replace(aPattern,aReplacement);}else{this.children.push(''.replace(aPattern,aReplacement));}return this;};/**
 * Set the source content for a source file. This will be added to the SourceMapGenerator
 * in the sourcesContent field.
 *
 * @param aSourceFile The filename of the source file
 * @param aSourceContent The content of the source file
 */SourceNode.prototype.setSourceContent=function SourceNode_setSourceContent(aSourceFile,aSourceContent){this.sourceContents[util.toSetString(aSourceFile)]=aSourceContent;};/**
 * Walk over the tree of SourceNodes. The walking function is called for each
 * source file content and is passed the filename and source content.
 *
 * @param aFn The traversal function.
 */SourceNode.prototype.walkSourceContents=function SourceNode_walkSourceContents(aFn){for(var i=0,len=this.children.length;i<len;i++){if(this.children[i][isSourceNode]){this.children[i].walkSourceContents(aFn);}}var sources=Object.keys(this.sourceContents);for(var i=0,len=sources.length;i<len;i++){aFn(util.fromSetString(sources[i]),this.sourceContents[sources[i]]);}};/**
 * Return the string representation of this source node. Walks over the tree
 * and concatenates all the various snippets together to one string.
 */SourceNode.prototype.toString=function SourceNode_toString(){var str="";this.walk(function(chunk){str+=chunk;});return str;};/**
 * Returns the string representation of this source node along with a source
 * map.
 */SourceNode.prototype.toStringWithSourceMap=function SourceNode_toStringWithSourceMap(aArgs){var generated={code:"",line:1,column:0};var map=new SourceMapGenerator(aArgs);var sourceMappingActive=false;var lastOriginalSource=null;var lastOriginalLine=null;var lastOriginalColumn=null;var lastOriginalName=null;this.walk(function(chunk,original){generated.code+=chunk;if(original.source!==null&&original.line!==null&&original.column!==null){if(lastOriginalSource!==original.source||lastOriginalLine!==original.line||lastOriginalColumn!==original.column||lastOriginalName!==original.name){map.addMapping({source:original.source,original:{line:original.line,column:original.column},generated:{line:generated.line,column:generated.column},name:original.name});}lastOriginalSource=original.source;lastOriginalLine=original.line;lastOriginalColumn=original.column;lastOriginalName=original.name;sourceMappingActive=true;}else if(sourceMappingActive){map.addMapping({generated:{line:generated.line,column:generated.column}});lastOriginalSource=null;sourceMappingActive=false;}for(var idx=0,length=chunk.length;idx<length;idx++){if(chunk.charCodeAt(idx)===NEWLINE_CODE){generated.line++;generated.column=0;// Mappings end at eol
if(idx+1===length){lastOriginalSource=null;sourceMappingActive=false;}else if(sourceMappingActive){map.addMapping({source:original.source,original:{line:original.line,column:original.column},generated:{line:generated.line,column:generated.column},name:original.name});}}else{generated.column++;}}});this.walkSourceContents(function(sourceFile,sourceContent){map.setSourceContent(sourceFile,sourceContent);});return{code:generated.code,map:map};};exports.SourceNode=SourceNode;},{"./source-map-generator":205,"./util":207}],207:[function(require,module,exports){/* -*- Mode: js; js-indent-level: 2; -*- */ /*
 * Copyright 2011 Mozilla Foundation and contributors
 * Licensed under the New BSD license. See LICENSE or:
 * http://opensource.org/licenses/BSD-3-Clause
 */ /**
 * This is a helper function for getting values from parameter/options
 * objects.
 *
 * @param args The object we are extracting values from
 * @param name The name of the property we are getting.
 * @param defaultValue An optional value to return if the property is missing
 * from the object. If this is not specified and the property is missing, an
 * error will be thrown.
 */function getArg(aArgs,aName,aDefaultValue){if(aName in aArgs){return aArgs[aName];}else if(arguments.length===3){return aDefaultValue;}else{throw new Error('"'+aName+'" is a required argument.');}}exports.getArg=getArg;var urlRegexp=/^(?:([\w+\-.]+):)?\/\/(?:(\w+:\w+)@)?([\w.-]*)(?::(\d+))?(.*)$/;var dataUrlRegexp=/^data:.+\,.+$/;function urlParse(aUrl){var match=aUrl.match(urlRegexp);if(!match){return null;}return{scheme:match[1],auth:match[2],host:match[3],port:match[4],path:match[5]};}exports.urlParse=urlParse;function urlGenerate(aParsedUrl){var url='';if(aParsedUrl.scheme){url+=aParsedUrl.scheme+':';}url+='//';if(aParsedUrl.auth){url+=aParsedUrl.auth+'@';}if(aParsedUrl.host){url+=aParsedUrl.host;}if(aParsedUrl.port){url+=":"+aParsedUrl.port;}if(aParsedUrl.path){url+=aParsedUrl.path;}return url;}exports.urlGenerate=urlGenerate;/**
 * Normalizes a path, or the path portion of a URL:
 *
 * - Replaces consecutive slashes with one slash.
 * - Removes unnecessary '.' parts.
 * - Removes unnecessary '<dir>/..' parts.
 *
 * Based on code in the Node.js 'path' core module.
 *
 * @param aPath The path or url to normalize.
 */function normalize(aPath){var path=aPath;var url=urlParse(aPath);if(url){if(!url.path){return aPath;}path=url.path;}var isAbsolute=exports.isAbsolute(path);var parts=path.split(/\/+/);for(var part,up=0,i=parts.length-1;i>=0;i--){part=parts[i];if(part==='.'){parts.splice(i,1);}else if(part==='..'){up++;}else if(up>0){if(part===''){// The first part is blank if the path is absolute. Trying to go
// above the root is a no-op. Therefore we can remove all '..' parts
// directly after the root.
parts.splice(i+1,up);up=0;}else{parts.splice(i,2);up--;}}}path=parts.join('/');if(path===''){path=isAbsolute?'/':'.';}if(url){url.path=path;return urlGenerate(url);}return path;}exports.normalize=normalize;/**
 * Joins two paths/URLs.
 *
 * @param aRoot The root path or URL.
 * @param aPath The path or URL to be joined with the root.
 *
 * - If aPath is a URL or a data URI, aPath is returned, unless aPath is a
 *   scheme-relative URL: Then the scheme of aRoot, if any, is prepended
 *   first.
 * - Otherwise aPath is a path. If aRoot is a URL, then its path portion
 *   is updated with the result and aRoot is returned. Otherwise the result
 *   is returned.
 *   - If aPath is absolute, the result is aPath.
 *   - Otherwise the two paths are joined with a slash.
 * - Joining for example 'http://' and 'www.example.com' is also supported.
 */function join(aRoot,aPath){if(aRoot===""){aRoot=".";}if(aPath===""){aPath=".";}var aPathUrl=urlParse(aPath);var aRootUrl=urlParse(aRoot);if(aRootUrl){aRoot=aRootUrl.path||'/';}// `join(foo, '//www.example.org')`
if(aPathUrl&&!aPathUrl.scheme){if(aRootUrl){aPathUrl.scheme=aRootUrl.scheme;}return urlGenerate(aPathUrl);}if(aPathUrl||aPath.match(dataUrlRegexp)){return aPath;}// `join('http://', 'www.example.com')`
if(aRootUrl&&!aRootUrl.host&&!aRootUrl.path){aRootUrl.host=aPath;return urlGenerate(aRootUrl);}var joined=aPath.charAt(0)==='/'?aPath:normalize(aRoot.replace(/\/+$/,'')+'/'+aPath);if(aRootUrl){aRootUrl.path=joined;return urlGenerate(aRootUrl);}return joined;}exports.join=join;exports.isAbsolute=function(aPath){return aPath.charAt(0)==='/'||urlRegexp.test(aPath);};/**
 * Make a path relative to a URL or another path.
 *
 * @param aRoot The root path or URL.
 * @param aPath The path or URL to be made relative to aRoot.
 */function relative(aRoot,aPath){if(aRoot===""){aRoot=".";}aRoot=aRoot.replace(/\/$/,'');// It is possible for the path to be above the root. In this case, simply
// checking whether the root is a prefix of the path won't work. Instead, we
// need to remove components from the root one by one, until either we find
// a prefix that fits, or we run out of components to remove.
var level=0;while(aPath.indexOf(aRoot+'/')!==0){var index=aRoot.lastIndexOf("/");if(index<0){return aPath;}// If the only part of the root that is left is the scheme (i.e. http://,
// file:///, etc.), one or more slashes (/), or simply nothing at all, we
// have exhausted all components, so the path is not relative to the root.
aRoot=aRoot.slice(0,index);if(aRoot.match(/^([^\/]+:\/)?\/*$/)){return aPath;}++level;}// Make sure we add a "../" for each component we removed from the root.
return Array(level+1).join("../")+aPath.substr(aRoot.length+1);}exports.relative=relative;var supportsNullProto=function(){var obj=Object.create(null);return!('__proto__'in obj);}();function identity(s){return s;}/**
 * Because behavior goes wacky when you set `__proto__` on objects, we
 * have to prefix all the strings in our set with an arbitrary character.
 *
 * See https://github.com/mozilla/source-map/pull/31 and
 * https://github.com/mozilla/source-map/issues/30
 *
 * @param String aStr
 */function toSetString(aStr){if(isProtoString(aStr)){return'$'+aStr;}return aStr;}exports.toSetString=supportsNullProto?identity:toSetString;function fromSetString(aStr){if(isProtoString(aStr)){return aStr.slice(1);}return aStr;}exports.fromSetString=supportsNullProto?identity:fromSetString;function isProtoString(s){if(!s){return false;}var length=s.length;if(length<9/* "__proto__".length */){return false;}if(s.charCodeAt(length-1)!==95/* '_' */||s.charCodeAt(length-2)!==95/* '_' */||s.charCodeAt(length-3)!==111/* 'o' */||s.charCodeAt(length-4)!==116/* 't' */||s.charCodeAt(length-5)!==111/* 'o' */||s.charCodeAt(length-6)!==114/* 'r' */||s.charCodeAt(length-7)!==112/* 'p' */||s.charCodeAt(length-8)!==95/* '_' */||s.charCodeAt(length-9)!==95/* '_' */){return false;}for(var i=length-10;i>=0;i--){if(s.charCodeAt(i)!==36/* '$' */){return false;}}return true;}/**
 * Comparator between two mappings where the original positions are compared.
 *
 * Optionally pass in `true` as `onlyCompareGenerated` to consider two
 * mappings with the same original source/line/column, but different generated
 * line and column the same. Useful when searching for a mapping with a
 * stubbed out mapping.
 */function compareByOriginalPositions(mappingA,mappingB,onlyCompareOriginal){var cmp=strcmp(mappingA.source,mappingB.source);if(cmp!==0){return cmp;}cmp=mappingA.originalLine-mappingB.originalLine;if(cmp!==0){return cmp;}cmp=mappingA.originalColumn-mappingB.originalColumn;if(cmp!==0||onlyCompareOriginal){return cmp;}cmp=mappingA.generatedColumn-mappingB.generatedColumn;if(cmp!==0){return cmp;}cmp=mappingA.generatedLine-mappingB.generatedLine;if(cmp!==0){return cmp;}return strcmp(mappingA.name,mappingB.name);}exports.compareByOriginalPositions=compareByOriginalPositions;/**
 * Comparator between two mappings with deflated source and name indices where
 * the generated positions are compared.
 *
 * Optionally pass in `true` as `onlyCompareGenerated` to consider two
 * mappings with the same generated line and column, but different
 * source/name/original line and column the same. Useful when searching for a
 * mapping with a stubbed out mapping.
 */function compareByGeneratedPositionsDeflated(mappingA,mappingB,onlyCompareGenerated){var cmp=mappingA.generatedLine-mappingB.generatedLine;if(cmp!==0){return cmp;}cmp=mappingA.generatedColumn-mappingB.generatedColumn;if(cmp!==0||onlyCompareGenerated){return cmp;}cmp=strcmp(mappingA.source,mappingB.source);if(cmp!==0){return cmp;}cmp=mappingA.originalLine-mappingB.originalLine;if(cmp!==0){return cmp;}cmp=mappingA.originalColumn-mappingB.originalColumn;if(cmp!==0){return cmp;}return strcmp(mappingA.name,mappingB.name);}exports.compareByGeneratedPositionsDeflated=compareByGeneratedPositionsDeflated;function strcmp(aStr1,aStr2){if(aStr1===aStr2){return 0;}if(aStr1===null){return 1;// aStr2 !== null
}if(aStr2===null){return-1;// aStr1 !== null
}if(aStr1>aStr2){return 1;}return-1;}/**
 * Comparator between two mappings with inflated source and name strings where
 * the generated positions are compared.
 */function compareByGeneratedPositionsInflated(mappingA,mappingB){var cmp=mappingA.generatedLine-mappingB.generatedLine;if(cmp!==0){return cmp;}cmp=mappingA.generatedColumn-mappingB.generatedColumn;if(cmp!==0){return cmp;}cmp=strcmp(mappingA.source,mappingB.source);if(cmp!==0){return cmp;}cmp=mappingA.originalLine-mappingB.originalLine;if(cmp!==0){return cmp;}cmp=mappingA.originalColumn-mappingB.originalColumn;if(cmp!==0){return cmp;}return strcmp(mappingA.name,mappingB.name);}exports.compareByGeneratedPositionsInflated=compareByGeneratedPositionsInflated;/**
 * Strip any JSON XSSI avoidance prefix from the string (as documented
 * in the source maps specification), and then parse the string as
 * JSON.
 */function parseSourceMapInput(str){return JSON.parse(str.replace(/^\)]}'[^\n]*\n/,''));}exports.parseSourceMapInput=parseSourceMapInput;/**
 * Compute the URL of a source given the the source root, the source's
 * URL, and the source map's URL.
 */function computeSourceURL(sourceRoot,sourceURL,sourceMapURL){sourceURL=sourceURL||'';if(sourceRoot){// This follows what Chrome does.
if(sourceRoot[sourceRoot.length-1]!=='/'&&sourceURL[0]!=='/'){sourceRoot+='/';}// The spec says:
//   Line 4: An optional source root, useful for relocating source
//   files on a server or removing repeated values in the
//   “sources” entry.  This value is prepended to the individual
//   entries in the “source” field.
sourceURL=sourceRoot+sourceURL;}// Historically, SourceMapConsumer did not take the sourceMapURL as
// a parameter.  This mode is still somewhat supported, which is why
// this code block is conditional.  However, it's preferable to pass
// the source map URL to SourceMapConsumer, so that this function
// can implement the source URL resolution algorithm as outlined in
// the spec.  This block is basically the equivalent of:
//    new URL(sourceURL, sourceMapURL).toString()
// ... except it avoids using URL, which wasn't available in the
// older releases of node still supported by this library.
//
// The spec says:
//   If the sources are not absolute URLs after prepending of the
//   “sourceRoot”, the sources are resolved relative to the
//   SourceMap (like resolving script src in a html document).
if(sourceMapURL){var parsed=urlParse(sourceMapURL);if(!parsed){throw new Error("sourceMapURL could not be parsed");}if(parsed.path){// Strip the last path component, but keep the "/".
var index=parsed.path.lastIndexOf('/');if(index>=0){parsed.path=parsed.path.substring(0,index+1);}}sourceURL=join(urlGenerate(parsed),sourceURL);}return normalize(sourceURL);}exports.computeSourceURL=computeSourceURL;},{}],208:[function(require,module,exports){/*
 * Copyright 2009-2011 Mozilla Foundation and contributors
 * Licensed under the New BSD license. See LICENSE.txt or:
 * http://opensource.org/licenses/BSD-3-Clause
 */exports.SourceMapGenerator=require('./lib/source-map-generator').SourceMapGenerator;exports.SourceMapConsumer=require('./lib/source-map-consumer').SourceMapConsumer;exports.SourceNode=require('./lib/source-node').SourceNode;},{"./lib/source-map-consumer":204,"./lib/source-map-generator":205,"./lib/source-node":206}],209:[function(require,module,exports){// Copyright Joyent, Inc. and other Node contributors.
//
// Permission is hereby granted, free of charge, to any person obtaining a
// copy of this software and associated documentation files (the
// "Software"), to deal in the Software without restriction, including
// without limitation the rights to use, copy, modify, merge, publish,
// distribute, sublicense, and/or sell copies of the Software, and to permit
// persons to whom the Software is furnished to do so, subject to the
// following conditions:
//
// The above copyright notice and this permission notice shall be included
// in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
// OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
// NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
// DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
// OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
// USE OR OTHER DEALINGS IN THE SOFTWARE.
'use strict';var punycode=require('punycode');var util=require('./util');exports.parse=urlParse;exports.resolve=urlResolve;exports.resolveObject=urlResolveObject;exports.format=urlFormat;exports.Url=Url;function Url(){this.protocol=null;this.slashes=null;this.auth=null;this.host=null;this.port=null;this.hostname=null;this.hash=null;this.search=null;this.query=null;this.pathname=null;this.path=null;this.href=null;}// Reference: RFC 3986, RFC 1808, RFC 2396
// define these here so at least they only have to be
// compiled once on the first module load.
var protocolPattern=/^([a-z0-9.+-]+:)/i,portPattern=/:[0-9]*$/,// Special case for a simple path URL
simplePathPattern=/^(\/\/?(?!\/)[^\?\s]*)(\?[^\s]*)?$/,// RFC 2396: characters reserved for delimiting URLs.
// We actually just auto-escape these.
delims=['<','>','"','`',' ','\r','\n','\t'],// RFC 2396: characters not allowed for various reasons.
unwise=['{','}','|','\\','^','`'].concat(delims),// Allowed by RFCs, but cause of XSS attacks.  Always escape these.
autoEscape=['\''].concat(unwise),// Characters that are never ever allowed in a hostname.
// Note that any invalid chars are also handled, but these
// are the ones that are *expected* to be seen, so we fast-path
// them.
nonHostChars=['%','/','?',';','#'].concat(autoEscape),hostEndingChars=['/','?','#'],hostnameMaxLen=255,hostnamePartPattern=/^[+a-z0-9A-Z_-]{0,63}$/,hostnamePartStart=/^([+a-z0-9A-Z_-]{0,63})(.*)$/,// protocols that can allow "unsafe" and "unwise" chars.
unsafeProtocol={'javascript':true,'javascript:':true},// protocols that never have a hostname.
hostlessProtocol={'javascript':true,'javascript:':true},// protocols that always contain a // bit.
slashedProtocol={'http':true,'https':true,'ftp':true,'gopher':true,'file':true,'http:':true,'https:':true,'ftp:':true,'gopher:':true,'file:':true},querystring=require('querystring');function urlParse(url,parseQueryString,slashesDenoteHost){if(url&&util.isObject(url)&&url instanceof Url)return url;var u=new Url();u.parse(url,parseQueryString,slashesDenoteHost);return u;}Url.prototype.parse=function(url,parseQueryString,slashesDenoteHost){if(!util.isString(url)){throw new TypeError("Parameter 'url' must be a string, not "+_typeof(url));}// Copy chrome, IE, opera backslash-handling behavior.
// Back slashes before the query string get converted to forward slashes
// See: https://code.google.com/p/chromium/issues/detail?id=25916
var queryIndex=url.indexOf('?'),splitter=queryIndex!==-1&&queryIndex<url.indexOf('#')?'?':'#',uSplit=url.split(splitter),slashRegex=/\\/g;uSplit[0]=uSplit[0].replace(slashRegex,'/');url=uSplit.join(splitter);var rest=url;// trim before proceeding.
// This is to support parse stuff like "  http://foo.com  \n"
rest=rest.trim();if(!slashesDenoteHost&&url.split('#').length===1){// Try fast path regexp
var simplePath=simplePathPattern.exec(rest);if(simplePath){this.path=rest;this.href=rest;this.pathname=simplePath[1];if(simplePath[2]){this.search=simplePath[2];if(parseQueryString){this.query=querystring.parse(this.search.substr(1));}else{this.query=this.search.substr(1);}}else if(parseQueryString){this.search='';this.query={};}return this;}}var proto=protocolPattern.exec(rest);if(proto){proto=proto[0];var lowerProto=proto.toLowerCase();this.protocol=lowerProto;rest=rest.substr(proto.length);}// figure out if it's got a host
// user@server is *always* interpreted as a hostname, and url
// resolution will treat //foo/bar as host=foo,path=bar because that's
// how the browser resolves relative URLs.
if(slashesDenoteHost||proto||rest.match(/^\/\/[^@\/]+@[^@\/]+/)){var slashes=rest.substr(0,2)==='//';if(slashes&&!(proto&&hostlessProtocol[proto])){rest=rest.substr(2);this.slashes=true;}}if(!hostlessProtocol[proto]&&(slashes||proto&&!slashedProtocol[proto])){// there's a hostname.
// the first instance of /, ?, ;, or # ends the host.
//
// If there is an @ in the hostname, then non-host chars *are* allowed
// to the left of the last @ sign, unless some host-ending character
// comes *before* the @-sign.
// URLs are obnoxious.
//
// ex:
// http://a@b@c/ => user:a@b host:c
// http://a@b?@c => user:a host:c path:/?@c
// v0.12 TODO(isaacs): This is not quite how Chrome does things.
// Review our test case against browsers more comprehensively.
// find the first instance of any hostEndingChars
var hostEnd=-1;for(var i=0;i<hostEndingChars.length;i++){var hec=rest.indexOf(hostEndingChars[i]);if(hec!==-1&&(hostEnd===-1||hec<hostEnd))hostEnd=hec;}// at this point, either we have an explicit point where the
// auth portion cannot go past, or the last @ char is the decider.
var auth,atSign;if(hostEnd===-1){// atSign can be anywhere.
atSign=rest.lastIndexOf('@');}else{// atSign must be in auth portion.
// http://a@b/c@d => host:b auth:a path:/c@d
atSign=rest.lastIndexOf('@',hostEnd);}// Now we have a portion which is definitely the auth.
// Pull that off.
if(atSign!==-1){auth=rest.slice(0,atSign);rest=rest.slice(atSign+1);this.auth=decodeURIComponent(auth);}// the host is the remaining to the left of the first non-host char
hostEnd=-1;for(var i=0;i<nonHostChars.length;i++){var hec=rest.indexOf(nonHostChars[i]);if(hec!==-1&&(hostEnd===-1||hec<hostEnd))hostEnd=hec;}// if we still have not hit it, then the entire thing is a host.
if(hostEnd===-1)hostEnd=rest.length;this.host=rest.slice(0,hostEnd);rest=rest.slice(hostEnd);// pull out port.
this.parseHost();// we've indicated that there is a hostname,
// so even if it's empty, it has to be present.
this.hostname=this.hostname||'';// if hostname begins with [ and ends with ]
// assume that it's an IPv6 address.
var ipv6Hostname=this.hostname[0]==='['&&this.hostname[this.hostname.length-1]===']';// validate a little.
if(!ipv6Hostname){var hostparts=this.hostname.split(/\./);for(var i=0,l=hostparts.length;i<l;i++){var part=hostparts[i];if(!part)continue;if(!part.match(hostnamePartPattern)){var newpart='';for(var j=0,k=part.length;j<k;j++){if(part.charCodeAt(j)>127){// we replace non-ASCII char with a temporary placeholder
// we need this to make sure size of hostname is not
// broken by replacing non-ASCII by nothing
newpart+='x';}else{newpart+=part[j];}}// we test again with ASCII char only
if(!newpart.match(hostnamePartPattern)){var validParts=hostparts.slice(0,i);var notHost=hostparts.slice(i+1);var bit=part.match(hostnamePartStart);if(bit){validParts.push(bit[1]);notHost.unshift(bit[2]);}if(notHost.length){rest='/'+notHost.join('.')+rest;}this.hostname=validParts.join('.');break;}}}}if(this.hostname.length>hostnameMaxLen){this.hostname='';}else{// hostnames are always lower case.
this.hostname=this.hostname.toLowerCase();}if(!ipv6Hostname){// IDNA Support: Returns a punycoded representation of "domain".
// It only converts parts of the domain name that
// have non-ASCII characters, i.e. it doesn't matter if
// you call it with a domain that already is ASCII-only.
this.hostname=punycode.toASCII(this.hostname);}var p=this.port?':'+this.port:'';var h=this.hostname||'';this.host=h+p;this.href+=this.host;// strip [ and ] from the hostname
// the host field still retains them, though
if(ipv6Hostname){this.hostname=this.hostname.substr(1,this.hostname.length-2);if(rest[0]!=='/'){rest='/'+rest;}}}// now rest is set to the post-host stuff.
// chop off any delim chars.
if(!unsafeProtocol[lowerProto]){// First, make 100% sure that any "autoEscape" chars get
// escaped, even if encodeURIComponent doesn't think they
// need to be.
for(var i=0,l=autoEscape.length;i<l;i++){var ae=autoEscape[i];if(rest.indexOf(ae)===-1)continue;var esc=encodeURIComponent(ae);if(esc===ae){esc=escape(ae);}rest=rest.split(ae).join(esc);}}// chop off from the tail first.
var hash=rest.indexOf('#');if(hash!==-1){// got a fragment string.
this.hash=rest.substr(hash);rest=rest.slice(0,hash);}var qm=rest.indexOf('?');if(qm!==-1){this.search=rest.substr(qm);this.query=rest.substr(qm+1);if(parseQueryString){this.query=querystring.parse(this.query);}rest=rest.slice(0,qm);}else if(parseQueryString){// no query string, but parseQueryString still requested
this.search='';this.query={};}if(rest)this.pathname=rest;if(slashedProtocol[lowerProto]&&this.hostname&&!this.pathname){this.pathname='/';}//to support http.request
if(this.pathname||this.search){var p=this.pathname||'';var s=this.search||'';this.path=p+s;}// finally, reconstruct the href based on what has been validated.
this.href=this.format();return this;};// format a parsed object into a url string
function urlFormat(obj){// ensure it's an object, and not a string url.
// If it's an obj, this is a no-op.
// this way, you can call url_format() on strings
// to clean up potentially wonky urls.
if(util.isString(obj))obj=urlParse(obj);if(!(obj instanceof Url))return Url.prototype.format.call(obj);return obj.format();}Url.prototype.format=function(){var auth=this.auth||'';if(auth){auth=encodeURIComponent(auth);auth=auth.replace(/%3A/i,':');auth+='@';}var protocol=this.protocol||'',pathname=this.pathname||'',hash=this.hash||'',host=false,query='';if(this.host){host=auth+this.host;}else if(this.hostname){host=auth+(this.hostname.indexOf(':')===-1?this.hostname:'['+this.hostname+']');if(this.port){host+=':'+this.port;}}if(this.query&&util.isObject(this.query)&&Object.keys(this.query).length){query=querystring.stringify(this.query);}var search=this.search||query&&'?'+query||'';if(protocol&&protocol.substr(-1)!==':')protocol+=':';// only the slashedProtocols get the //.  Not mailto:, xmpp:, etc.
// unless they had them to begin with.
if(this.slashes||(!protocol||slashedProtocol[protocol])&&host!==false){host='//'+(host||'');if(pathname&&pathname.charAt(0)!=='/')pathname='/'+pathname;}else if(!host){host='';}if(hash&&hash.charAt(0)!=='#')hash='#'+hash;if(search&&search.charAt(0)!=='?')search='?'+search;pathname=pathname.replace(/[?#]/g,function(match){return encodeURIComponent(match);});search=search.replace('#','%23');return protocol+host+pathname+search+hash;};function urlResolve(source,relative){return urlParse(source,false,true).resolve(relative);}Url.prototype.resolve=function(relative){return this.resolveObject(urlParse(relative,false,true)).format();};function urlResolveObject(source,relative){if(!source)return relative;return urlParse(source,false,true).resolveObject(relative);}Url.prototype.resolveObject=function(relative){if(util.isString(relative)){var rel=new Url();rel.parse(relative,false,true);relative=rel;}var result=new Url();var tkeys=Object.keys(this);for(var tk=0;tk<tkeys.length;tk++){var tkey=tkeys[tk];result[tkey]=this[tkey];}// hash is always overridden, no matter what.
// even href="" will remove it.
result.hash=relative.hash;// if the relative url is empty, then there's nothing left to do here.
if(relative.href===''){result.href=result.format();return result;}// hrefs like //foo/bar always cut to the protocol.
if(relative.slashes&&!relative.protocol){// take everything except the protocol from relative
var rkeys=Object.keys(relative);for(var rk=0;rk<rkeys.length;rk++){var rkey=rkeys[rk];if(rkey!=='protocol')result[rkey]=relative[rkey];}//urlParse appends trailing / to urls like http://www.example.com
if(slashedProtocol[result.protocol]&&result.hostname&&!result.pathname){result.path=result.pathname='/';}result.href=result.format();return result;}if(relative.protocol&&relative.protocol!==result.protocol){// if it's a known url protocol, then changing
// the protocol does weird things
// first, if it's not file:, then we MUST have a host,
// and if there was a path
// to begin with, then we MUST have a path.
// if it is file:, then the host is dropped,
// because that's known to be hostless.
// anything else is assumed to be absolute.
if(!slashedProtocol[relative.protocol]){var keys=Object.keys(relative);for(var v=0;v<keys.length;v++){var k=keys[v];result[k]=relative[k];}result.href=result.format();return result;}result.protocol=relative.protocol;if(!relative.host&&!hostlessProtocol[relative.protocol]){var relPath=(relative.pathname||'').split('/');while(relPath.length&&!(relative.host=relPath.shift())){;}if(!relative.host)relative.host='';if(!relative.hostname)relative.hostname='';if(relPath[0]!=='')relPath.unshift('');if(relPath.length<2)relPath.unshift('');result.pathname=relPath.join('/');}else{result.pathname=relative.pathname;}result.search=relative.search;result.query=relative.query;result.host=relative.host||'';result.auth=relative.auth;result.hostname=relative.hostname||relative.host;result.port=relative.port;// to support http.request
if(result.pathname||result.search){var p=result.pathname||'';var s=result.search||'';result.path=p+s;}result.slashes=result.slashes||relative.slashes;result.href=result.format();return result;}var isSourceAbs=result.pathname&&result.pathname.charAt(0)==='/',isRelAbs=relative.host||relative.pathname&&relative.pathname.charAt(0)==='/',mustEndAbs=isRelAbs||isSourceAbs||result.host&&relative.pathname,removeAllDots=mustEndAbs,srcPath=result.pathname&&result.pathname.split('/')||[],relPath=relative.pathname&&relative.pathname.split('/')||[],psychotic=result.protocol&&!slashedProtocol[result.protocol];// if the url is a non-slashed url, then relative
// links like ../.. should be able
// to crawl up to the hostname, as well.  This is strange.
// result.protocol has already been set by now.
// Later on, put the first path part into the host field.
if(psychotic){result.hostname='';result.port=null;if(result.host){if(srcPath[0]==='')srcPath[0]=result.host;else srcPath.unshift(result.host);}result.host='';if(relative.protocol){relative.hostname=null;relative.port=null;if(relative.host){if(relPath[0]==='')relPath[0]=relative.host;else relPath.unshift(relative.host);}relative.host=null;}mustEndAbs=mustEndAbs&&(relPath[0]===''||srcPath[0]==='');}if(isRelAbs){// it's absolute.
result.host=relative.host||relative.host===''?relative.host:result.host;result.hostname=relative.hostname||relative.hostname===''?relative.hostname:result.hostname;result.search=relative.search;result.query=relative.query;srcPath=relPath;// fall through to the dot-handling below.
}else if(relPath.length){// it's relative
// throw away the existing file, and take the new path instead.
if(!srcPath)srcPath=[];srcPath.pop();srcPath=srcPath.concat(relPath);result.search=relative.search;result.query=relative.query;}else if(!util.isNullOrUndefined(relative.search)){// just pull out the search.
// like href='?foo'.
// Put this after the other two cases because it simplifies the booleans
if(psychotic){result.hostname=result.host=srcPath.shift();//occationaly the auth can get stuck only in host
//this especially happens in cases like
//url.resolveObject('mailto:local1@domain1', 'local2@domain2')
var authInHost=result.host&&result.host.indexOf('@')>0?result.host.split('@'):false;if(authInHost){result.auth=authInHost.shift();result.host=result.hostname=authInHost.shift();}}result.search=relative.search;result.query=relative.query;//to support http.request
if(!util.isNull(result.pathname)||!util.isNull(result.search)){result.path=(result.pathname?result.pathname:'')+(result.search?result.search:'');}result.href=result.format();return result;}if(!srcPath.length){// no path at all.  easy.
// we've already handled the other stuff above.
result.pathname=null;//to support http.request
if(result.search){result.path='/'+result.search;}else{result.path=null;}result.href=result.format();return result;}// if a url ENDs in . or .., then it must get a trailing slash.
// however, if it ends in anything else non-slashy,
// then it must NOT get a trailing slash.
var last=srcPath.slice(-1)[0];var hasTrailingSlash=(result.host||relative.host||srcPath.length>1)&&(last==='.'||last==='..')||last==='';// strip single dots, resolve double dots to parent dir
// if the path tries to go above the root, `up` ends up > 0
var up=0;for(var i=srcPath.length;i>=0;i--){last=srcPath[i];if(last==='.'){srcPath.splice(i,1);}else if(last==='..'){srcPath.splice(i,1);up++;}else if(up){srcPath.splice(i,1);up--;}}// if the path is allowed to go above the root, restore leading ..s
if(!mustEndAbs&&!removeAllDots){for(;up--;up){srcPath.unshift('..');}}if(mustEndAbs&&srcPath[0]!==''&&(!srcPath[0]||srcPath[0].charAt(0)!=='/')){srcPath.unshift('');}if(hasTrailingSlash&&srcPath.join('/').substr(-1)!=='/'){srcPath.push('');}var isAbsolute=srcPath[0]===''||srcPath[0]&&srcPath[0].charAt(0)==='/';// put the host back
if(psychotic){result.hostname=result.host=isAbsolute?'':srcPath.length?srcPath.shift():'';//occationaly the auth can get stuck only in host
//this especially happens in cases like
//url.resolveObject('mailto:local1@domain1', 'local2@domain2')
var authInHost=result.host&&result.host.indexOf('@')>0?result.host.split('@'):false;if(authInHost){result.auth=authInHost.shift();result.host=result.hostname=authInHost.shift();}}mustEndAbs=mustEndAbs||result.host&&srcPath.length;if(mustEndAbs&&!isAbsolute){srcPath.unshift('');}if(!srcPath.length){result.pathname=null;result.path=null;}else{result.pathname=srcPath.join('/');}//to support request.http
if(!util.isNull(result.pathname)||!util.isNull(result.search)){result.path=(result.pathname?result.pathname:'')+(result.search?result.search:'');}result.auth=relative.auth||result.auth;result.slashes=result.slashes||relative.slashes;result.href=result.format();return result;};Url.prototype.parseHost=function(){var host=this.host;var port=portPattern.exec(host);if(port){port=port[0];if(port!==':'){this.port=port.substr(1);}host=host.substr(0,host.length-port.length);}if(host)this.hostname=host;};},{"./util":210,"punycode":194,"querystring":197}],210:[function(require,module,exports){'use strict';module.exports={isString:function isString(arg){return typeof arg==='string';},isObject:function isObject(arg){return _typeof(arg)==='object'&&arg!==null;},isNull:function isNull(arg){return arg===null;},isNullOrUndefined:function isNullOrUndefined(arg){return arg==null;}};},{}],211:[function(require,module,exports){/* eslint-disable no-useless-escape */var htmlparser=require('htmlparser2');var quoteRegexp=require('lodash/escapeRegExp');var cloneDeep=require('lodash/cloneDeep');var mergeWith=require('lodash/mergeWith');var isString=require('lodash/isString');var isPlainObject=require('lodash/isPlainObject');var parseSrcset=require('parse-srcset');var postcss=require('postcss');var url=require('url');// Tags that can conceivably represent stand-alone media.
var mediaTags=['img','audio','video','picture','svg','object','map','iframe','embed'];// Tags that are inherently vulnerable to being used in XSS attacks.
var vulnerableTags=['script','style'];function each(obj,cb){if(obj){Object.keys(obj).forEach(function(key){cb(obj[key],key);});}}// Avoid false positives with .__proto__, .hasOwnProperty, etc.
function has(obj,key){return{}.hasOwnProperty.call(obj,key);}// Returns those elements of `a` for which `cb(a)` returns truthy
function filter(a,cb){var n=[];each(a,function(v){if(cb(v)){n.push(v);}});return n;}function isEmptyObject(obj){for(var key in obj){if(has(obj,key)){return false;}}return true;}function stringifySrcset(parsedSrcset){return parsedSrcset.map(function(part){if(!part.url){throw new Error('URL missing');}return part.url+(part.w?" ".concat(part.w,"w"):'')+(part.h?" ".concat(part.h,"h"):'')+(part.d?" ".concat(part.d,"x"):'');}).join(', ');}module.exports=sanitizeHtml;// A valid attribute name.
// We use a tolerant definition based on the set of strings defined by
// html.spec.whatwg.org/multipage/parsing.html#before-attribute-name-state
// and html.spec.whatwg.org/multipage/parsing.html#attribute-name-state .
// The characters accepted are ones which can be appended to the attribute
// name buffer without triggering a parse error:
//   * unexpected-equals-sign-before-attribute-name
//   * unexpected-null-character
//   * unexpected-character-in-attribute-name
// We exclude the empty string because it's impossible to get to the after
// attribute name state with an empty attribute name buffer.
var VALID_HTML_ATTRIBUTE_NAME=/^[^\0\t\n\f\r /<=>]+$/;// Ignore the _recursing flag; it's there for recursive
// invocation as a guard against this exploit:
// https://github.com/fb55/htmlparser2/issues/105
function sanitizeHtml(html,options,_recursing){var result='';// Used for hot swapping the result variable with an empty string in order to "capture" the text written to it.
var tempResult='';function Frame(tag,attribs){var that=this;this.tag=tag;this.attribs=attribs||{};this.tagPosition=result.length;this.text='';// Node inner text
this.mediaChildren=[];this.updateParentNodeText=function(){if(stack.length){var parentFrame=stack[stack.length-1];parentFrame.text+=that.text;}};this.updateParentNodeMediaChildren=function(){if(stack.length&&mediaTags.indexOf(this.tag)>-1){var parentFrame=stack[stack.length-1];parentFrame.mediaChildren.push(this.tag);}};}if(!options){options=sanitizeHtml.defaults;options.parser=htmlParserDefaults;}else{options=Object.assign({},sanitizeHtml.defaults,options);if(options.parser){options.parser=Object.assign({},htmlParserDefaults,options.parser);}else{options.parser=htmlParserDefaults;}}// vulnerableTags
vulnerableTags.forEach(function(tag){if(options.allowedTags&&options.allowedTags.indexOf(tag)>-1&&!options.allowVulnerableTags){// eslint-disable-next-line no-console
console.warn("\n\n\u26A0\uFE0F Your `allowedTags` option includes, `".concat(tag,"`, which is inherently\nvulnerable to XSS attacks. Please remove it from `allowedTags`.\nOr, to disable this warning, add the `allowVulnerableTags` option\nand ensure you are accounting for this risk.\n\n"));}});// Tags that contain something other than HTML, or where discarding
// the text when the tag is disallowed makes sense for other reasons.
// If we are not allowing these tags, we should drop their content too.
// For other tags you would drop the tag but keep its content.
var nonTextTagsArray=options.nonTextTags||['script','style','textarea','option'];var allowedAttributesMap;var allowedAttributesGlobMap;if(options.allowedAttributes){allowedAttributesMap={};allowedAttributesGlobMap={};each(options.allowedAttributes,function(attributes,tag){allowedAttributesMap[tag]=[];var globRegex=[];attributes.forEach(function(obj){if(isString(obj)&&obj.indexOf('*')>=0){globRegex.push(quoteRegexp(obj).replace(/\\\*/g,'.*'));}else{allowedAttributesMap[tag].push(obj);}});allowedAttributesGlobMap[tag]=new RegExp('^('+globRegex.join('|')+')$');});}var allowedClassesMap={};each(options.allowedClasses,function(classes,tag){// Implicitly allows the class attribute
if(allowedAttributesMap){if(!has(allowedAttributesMap,tag)){allowedAttributesMap[tag]=[];}allowedAttributesMap[tag].push('class');}allowedClassesMap[tag]=classes;});var transformTagsMap={};var transformTagsAll;each(options.transformTags,function(transform,tag){var transFun;if(typeof transform==='function'){transFun=transform;}else if(typeof transform==='string'){transFun=sanitizeHtml.simpleTransform(transform);}if(tag==='*'){transformTagsAll=transFun;}else{transformTagsMap[tag]=transFun;}});var depth;var stack;var skipMap;var transformMap;var skipText;var skipTextDepth;var addedText=false;initializeState();var parser=new htmlparser.Parser({onopentag:function onopentag(name,attribs){// If `enforceHtmlBoundary` is `true` and this has found the opening
// `html` tag, reset the state.
if(options.enforceHtmlBoundary&&name==='html'){initializeState();}if(skipText){skipTextDepth++;return;}var frame=new Frame(name,attribs);stack.push(frame);var skip=false;var hasText=!!frame.text;var transformedTag;if(has(transformTagsMap,name)){transformedTag=transformTagsMap[name](name,attribs);frame.attribs=attribs=transformedTag.attribs;if(transformedTag.text!==undefined){frame.innerText=transformedTag.text;}if(name!==transformedTag.tagName){frame.name=name=transformedTag.tagName;transformMap[depth]=transformedTag.tagName;}}if(transformTagsAll){transformedTag=transformTagsAll(name,attribs);frame.attribs=attribs=transformedTag.attribs;if(name!==transformedTag.tagName){frame.name=name=transformedTag.tagName;transformMap[depth]=transformedTag.tagName;}}if(options.allowedTags&&options.allowedTags.indexOf(name)===-1||options.disallowedTagsMode==='recursiveEscape'&&!isEmptyObject(skipMap)){skip=true;skipMap[depth]=true;if(options.disallowedTagsMode==='discard'){if(nonTextTagsArray.indexOf(name)!==-1){skipText=true;skipTextDepth=1;}}skipMap[depth]=true;}depth++;if(skip){if(options.disallowedTagsMode==='discard'){// We want the contents but not this tag
return;}tempResult=result;result='';}result+='<'+name;if(!allowedAttributesMap||has(allowedAttributesMap,name)||allowedAttributesMap['*']){each(attribs,function(value,a){if(!VALID_HTML_ATTRIBUTE_NAME.test(a)){// This prevents part of an attribute name in the output from being
// interpreted as the end of an attribute, or end of a tag.
delete frame.attribs[a];return;}var parsed;// check allowedAttributesMap for the element and attribute and modify the value
// as necessary if there are specific values defined.
var passedAllowedAttributesMapCheck=false;if(!allowedAttributesMap||has(allowedAttributesMap,name)&&allowedAttributesMap[name].indexOf(a)!==-1||allowedAttributesMap['*']&&allowedAttributesMap['*'].indexOf(a)!==-1||has(allowedAttributesGlobMap,name)&&allowedAttributesGlobMap[name].test(a)||allowedAttributesGlobMap['*']&&allowedAttributesGlobMap['*'].test(a)){passedAllowedAttributesMapCheck=true;}else if(allowedAttributesMap&&allowedAttributesMap[name]){var _iterator10=_createForOfIteratorHelper(allowedAttributesMap[name]),_step10;try{for(_iterator10.s();!(_step10=_iterator10.n()).done;){var o=_step10.value;if(isPlainObject(o)&&o.name&&o.name===a){passedAllowedAttributesMapCheck=true;var newValue='';if(o.multiple===true){// verify the values that are allowed
var splitStrArray=value.split(' ');var _iterator11=_createForOfIteratorHelper(splitStrArray),_step11;try{for(_iterator11.s();!(_step11=_iterator11.n()).done;){var s=_step11.value;if(o.values.indexOf(s)!==-1){if(newValue===''){newValue=s;}else{newValue+=' '+s;}}}}catch(err){_iterator11.e(err);}finally{_iterator11.f();}}else if(o.values.indexOf(value)>=0){// verified an allowed value matches the entire attribute value
newValue=value;}value=newValue;}}}catch(err){_iterator10.e(err);}finally{_iterator10.f();}}if(passedAllowedAttributesMapCheck){if(options.allowedSchemesAppliedToAttributes.indexOf(a)!==-1){if(naughtyHref(name,value)){delete frame.attribs[a];return;}}if(name==='iframe'&&a==='src'){var allowed=true;try{// naughtyHref is in charge of whether protocol relative URLs
// are cool. We should just accept them.
// eslint-disable-next-line node/no-deprecated-api
parsed=url.parse(value,false,true);var isRelativeUrl=parsed&&parsed.host===null&&parsed.protocol===null;if(isRelativeUrl){// default value of allowIframeRelativeUrls is true
// unless allowedIframeHostnames or allowedIframeDomains specified
allowed=has(options,'allowIframeRelativeUrls')?options.allowIframeRelativeUrls:!options.allowedIframeHostnames&&!options.allowedIframeDomains;}else if(options.allowedIframeHostnames||options.allowedIframeDomains){var allowedHostname=(options.allowedIframeHostnames||[]).find(function(hostname){return hostname===parsed.hostname;});var allowedDomain=(options.allowedIframeDomains||[]).find(function(domain){return parsed.hostname===domain||parsed.hostname.endsWith(".".concat(domain));});allowed=allowedHostname||allowedDomain;}}catch(e){// Unparseable iframe src
allowed=false;}if(!allowed){delete frame.attribs[a];return;}}if(a==='srcset'){try{parsed=parseSrcset(value);each(parsed,function(value){if(naughtyHref('srcset',value.url)){value.evil=true;}});parsed=filter(parsed,function(v){return!v.evil;});if(!parsed.length){delete frame.attribs[a];return;}else{value=stringifySrcset(filter(parsed,function(v){return!v.evil;}));frame.attribs[a]=value;}}catch(e){// Unparseable srcset
delete frame.attribs[a];return;}}if(a==='class'){value=filterClasses(value,allowedClassesMap[name]);if(!value.length){delete frame.attribs[a];return;}}if(a==='style'){try{var abstractSyntaxTree=postcss.parse(name+' {'+value+'}');var filteredAST=filterCss(abstractSyntaxTree,options.allowedStyles);value=stringifyStyleAttributes(filteredAST);if(value.length===0){delete frame.attribs[a];return;}}catch(e){delete frame.attribs[a];return;}}result+=' '+a;if(value&&value.length){result+='="'+escapeHtml(value,true)+'"';}}else{delete frame.attribs[a];}});}if(options.selfClosing.indexOf(name)!==-1){result+=' />';}else{result+='>';if(frame.innerText&&!hasText&&!options.textFilter){result+=frame.innerText;addedText=true;}}if(skip){result=tempResult+escapeHtml(result);tempResult='';}},ontext:function ontext(text){if(skipText){return;}var lastFrame=stack[stack.length-1];var tag;if(lastFrame){tag=lastFrame.tag;// If inner text was set by transform function then let's use it
text=lastFrame.innerText!==undefined?lastFrame.innerText:text;}if(options.disallowedTagsMode==='discard'&&(tag==='script'||tag==='style')){// htmlparser2 gives us these as-is. Escaping them ruins the content. Allowing
// script tags is, by definition, game over for XSS protection, so if that's
// your concern, don't allow them. The same is essentially true for style tags
// which have their own collection of XSS vectors.
result+=text;}else{var escaped=escapeHtml(text,false);if(options.textFilter&&!addedText){result+=options.textFilter(escaped,tag);}else if(!addedText){result+=escaped;}}if(stack.length){var frame=stack[stack.length-1];frame.text+=text;}},onclosetag:function onclosetag(name){if(skipText){skipTextDepth--;if(!skipTextDepth){skipText=false;}else{return;}}var frame=stack.pop();if(!frame){// Do not crash on bad markup
return;}skipText=options.enforceHtmlBoundary?name==='html':false;depth--;var skip=skipMap[depth];if(skip){delete skipMap[depth];if(options.disallowedTagsMode==='discard'){frame.updateParentNodeText();return;}tempResult=result;result='';}if(transformMap[depth]){name=transformMap[depth];delete transformMap[depth];}if(options.exclusiveFilter&&options.exclusiveFilter(frame)){result=result.substr(0,frame.tagPosition);return;}frame.updateParentNodeMediaChildren();frame.updateParentNodeText();if(options.selfClosing.indexOf(name)!==-1){// Already output />
if(skip){result=tempResult;tempResult='';}return;}result+='</'+name+'>';if(skip){result=tempResult+escapeHtml(result);tempResult='';}}},options.parser);parser.write(html);parser.end();return result;function initializeState(){result='';depth=0;stack=[];skipMap={};transformMap={};skipText=false;skipTextDepth=0;}function escapeHtml(s,quote){if(typeof s!=='string'){s=s+'';}if(options.parser.decodeEntities){s=s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\>/g,'&gt;');if(quote){s=s.replace(/\"/g,'&quot;');}}// TODO: this is inadequate because it will pass `&0;`. This approach
// will not work, each & must be considered with regard to whether it
// is followed by a 100% syntactically valid entity or not, and escaped
// if it is not. If this bothers you, don't set parser.decodeEntities
// to false. (The default is true.)
s=s.replace(/&(?![a-zA-Z0-9#]{1,20};)/g,'&amp;')// Match ampersands not part of existing HTML entity
.replace(/</g,'&lt;').replace(/\>/g,'&gt;');if(quote){s=s.replace(/\"/g,'&quot;');}return s;}function naughtyHref(name,href){// Browsers ignore character codes of 32 (space) and below in a surprising
// number of situations. Start reading here:
// https://www.owasp.org/index.php/XSS_Filter_Evasion_Cheat_Sheet#Embedded_tab
// eslint-disable-next-line no-control-regex
href=href.replace(/[\x00-\x20]+/g,'');// Clobber any comments in URLs, which the browser might
// interpret inside an XML data island, allowing
// a javascript: URL to be snuck through
href=href.replace(/<\!\-\-.*?\-\-\>/g,'');// Case insensitive so we don't get faked out by JAVASCRIPT #1
var matches=href.match(/^([a-zA-Z]+)\:/);if(!matches){// Protocol-relative URL starting with any combination of '/' and '\'
if(href.match(/^[\/\\]{2}/)){return!options.allowProtocolRelative;}// No scheme
return false;}var scheme=matches[1].toLowerCase();if(has(options.allowedSchemesByTag,name)){return options.allowedSchemesByTag[name].indexOf(scheme)===-1;}return!options.allowedSchemes||options.allowedSchemes.indexOf(scheme)===-1;}/**
   * Filters user input css properties by whitelisted regex attributes.
   *
   * @param {object} abstractSyntaxTree  - Object representation of CSS attributes.
   * @property {array[Declaration]} abstractSyntaxTree.nodes[0] - Each object cointains prop and value key, i.e { prop: 'color', value: 'red' }.
   * @param {object} allowedStyles       - Keys are properties (i.e color), value is list of permitted regex rules (i.e /green/i).
   * @return {object}                    - Abstract Syntax Tree with filtered style attributes.
   */function filterCss(abstractSyntaxTree,allowedStyles){if(!allowedStyles){return abstractSyntaxTree;}var filteredAST=cloneDeep(abstractSyntaxTree);var astRules=abstractSyntaxTree.nodes[0];var selectedRule;// Merge global and tag-specific styles into new AST.
if(allowedStyles[astRules.selector]&&allowedStyles['*']){selectedRule=mergeWith(cloneDeep(allowedStyles[astRules.selector]),allowedStyles['*'],function(objValue,srcValue){if(Array.isArray(objValue)){return objValue.concat(srcValue);}});}else{selectedRule=allowedStyles[astRules.selector]||allowedStyles['*'];}if(selectedRule){filteredAST.nodes[0].nodes=astRules.nodes.reduce(filterDeclarations(selectedRule),[]);}return filteredAST;}/**
   * Extracts the style attribues from an AbstractSyntaxTree and formats those
   * values in the inline style attribute format.
   *
   * @param  {AbstractSyntaxTree} filteredAST
   * @return {string}             - Example: "color:yellow;text-align:center;font-family:helvetica;"
   */function stringifyStyleAttributes(filteredAST){return filteredAST.nodes[0].nodes.reduce(function(extractedAttributes,attributeObject){extractedAttributes.push(attributeObject.prop+':'+attributeObject.value);return extractedAttributes;},[]).join(';');}/**
    * Filters the existing attributes for the given property. Discards any attributes
    * which don't match the whitelist.
    *
    * @param  {object} selectedRule             - Example: { color: red, font-family: helvetica }
    * @param  {array} allowedDeclarationsList   - List of declarations which pass whitelisting.
    * @param  {object} attributeObject          - Object representing the current css property.
    * @property {string} attributeObject.type   - Typically 'declaration'.
    * @property {string} attributeObject.prop   - The CSS property, i.e 'color'.
    * @property {string} attributeObject.value  - The corresponding value to the css property, i.e 'red'.
    * @return {function}                        - When used in Array.reduce, will return an array of Declaration objects
    */function filterDeclarations(selectedRule){return function(allowedDeclarationsList,attributeObject){// If this property is whitelisted...
if(has(selectedRule,attributeObject.prop)){var matchesRegex=selectedRule[attributeObject.prop].some(function(regularExpression){return regularExpression.test(attributeObject.value);});if(matchesRegex){allowedDeclarationsList.push(attributeObject);}}return allowedDeclarationsList;};}function filterClasses(classes,allowed){if(!allowed){// The class attribute is allowed without filtering on this tag
return classes;}classes=classes.split(/\s+/);return classes.filter(function(clss){return allowed.indexOf(clss)!==-1;}).join(' ');}}// Defaults are accessible to you so that you can use them as a starting point
// programmatically if you wish
var htmlParserDefaults={decodeEntities:true};sanitizeHtml.defaults={allowedTags:['h3','h4','h5','h6','blockquote','p','a','ul','ol','nl','li','b','i','strong','em','strike','abbr','code','hr','br','div','table','thead','caption','tbody','tr','th','td','pre','iframe'],disallowedTagsMode:'discard',allowedAttributes:{a:['href','name','target'],// We don't currently allow img itself by default, but this
// would make sense if we did. You could add srcset here,
// and if you do the URL is checked for safety
img:['src']},// Lots of these won't come up by default because we don't allow them
selfClosing:['img','br','hr','area','base','basefont','input','link','meta'],// URL schemes we permit
allowedSchemes:['http','https','ftp','mailto'],allowedSchemesByTag:{},allowedSchemesAppliedToAttributes:['href','src','cite'],allowProtocolRelative:true,enforceHtmlBoundary:false};sanitizeHtml.simpleTransform=function(newTagName,newAttribs,merge){merge=merge===undefined?true:merge;newAttribs=newAttribs||{};return function(tagName,attribs){var attrib;if(merge){for(attrib in newAttribs){attribs[attrib]=newAttribs[attrib];}}else{attribs=newAttribs;}return{tagName:newTagName,attribs:attribs};};};},{"htmlparser2":31,"lodash/cloneDeep":140,"lodash/escapeRegExp":143,"lodash/isPlainObject":155,"lodash/isString":157,"lodash/mergeWith":162,"parse-srcset":167,"postcss":181,"url":209}]},{},[211])(211);});
