/*
<!-- LICENSEFILE/ -->

<h1>License</h1>

Unless stated otherwise all works are:

<ul><li>Copyright &copy; 2013+ <a href="http://bevry.me">Bevry Pty Ltd</a></li></ul>

and licensed under:

<ul><li><a href="http://spdx.org/licenses/MIT.html">MIT License</a></li></ul>

<h2>MIT License</h2>

<pre>
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
</pre>

<!-- /LICENSEFILE -->
*/
/*
modified by Calvin Metcalf to adhere to how the node one works a little better
*/
import {EventEmitter} from 'events';
import inherits from './inherits';
inherits(Domain, EventEmitter);
function createEmitError(d) {
  return emitError;
  function emitError(e) {
    d.emit('error', e)
  }
}

export function Domain() {
  EventEmitter.call(this);
  this.__emitError = createEmitError(this);
}
Domain.prototype.add = function (emitter) {
  emitter.on('error', this.__emitError);
}
Domain.prototype.remove = function(emitter) {
  emitter.removeListener('error', this.__emitError)
}
Domain.prototype.bind = function(fn) {
  var emitError = this.__emitError;
  return function() {
    var args = Array.prototype.slice.call(arguments)
    try {
      fn.apply(null, args)
    } catch (err) {
      emitError(err)
    }
  }
}
Domain.prototype.intercept = function(fn) {
  var emitError = this.__emitError;
  return function(err) {
    if (err) {
      emitError(err)
    } else {
      var args = Array.prototype.slice.call(arguments, 1)
      try {
        fn.apply(null, args)
      } catch (err) {
        emitError(err)
      }
    }
  }
}
Domain.prototype.run = function(fn) {
  var emitError = this.__emitError;
  try {
    fn()
  } catch (err) {
    emitError(err)
  }
  return this
}
Domain.prototype.dispose = function() {
  this.removeAllListeners()
  return this
}
Domain.prototype.enter = Domain.prototype.exit = function() {
  return this
}
export function createDomain() {
  return new Domain();
}
export var create = createDomain;

export default {
  Domain: Domain,
  createDomain: createDomain,
  create: create
}
