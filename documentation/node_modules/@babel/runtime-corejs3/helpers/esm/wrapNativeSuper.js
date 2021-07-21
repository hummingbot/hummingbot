import _Object$create from "@babel/runtime-corejs3/core-js/object/create";
import _Map from "@babel/runtime-corejs3/core-js/map";
import getPrototypeOf from "@babel/runtime-corejs3/helpers/esm/getPrototypeOf";
import setPrototypeOf from "@babel/runtime-corejs3/helpers/esm/setPrototypeOf";
import isNativeFunction from "@babel/runtime-corejs3/helpers/esm/isNativeFunction";
import construct from "@babel/runtime-corejs3/helpers/esm/construct";
export default function _wrapNativeSuper(Class) {
  var _cache = typeof _Map === "function" ? new _Map() : undefined;

  _wrapNativeSuper = function _wrapNativeSuper(Class) {
    if (Class === null || !isNativeFunction(Class)) return Class;

    if (typeof Class !== "function") {
      throw new TypeError("Super expression must either be null or a function");
    }

    if (typeof _cache !== "undefined") {
      if (_cache.has(Class)) return _cache.get(Class);

      _cache.set(Class, Wrapper);
    }

    function Wrapper() {
      return construct(Class, arguments, getPrototypeOf(this).constructor);
    }

    Wrapper.prototype = _Object$create(Class.prototype, {
      constructor: {
        value: Wrapper,
        enumerable: false,
        writable: true,
        configurable: true
      }
    });
    return setPrototypeOf(Wrapper, Class);
  };

  return _wrapNativeSuper(Class);
}