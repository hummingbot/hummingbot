import _Reflect$construct from "@babel/runtime-corejs3/core-js/reflect/construct";
import getPrototypeOf from "@babel/runtime-corejs3/helpers/esm/getPrototypeOf";
import isNativeReflectConstruct from "@babel/runtime-corejs3/helpers/esm/isNativeReflectConstruct";
import possibleConstructorReturn from "@babel/runtime-corejs3/helpers/esm/possibleConstructorReturn";
export default function _createSuper(Derived) {
  var hasNativeReflectConstruct = isNativeReflectConstruct();
  return function _createSuperInternal() {
    var Super = getPrototypeOf(Derived),
        result;

    if (hasNativeReflectConstruct) {
      var NewTarget = getPrototypeOf(this).constructor;
      result = _Reflect$construct(Super, arguments, NewTarget);
    } else {
      result = Super.apply(this, arguments);
    }

    return possibleConstructorReturn(this, result);
  };
}