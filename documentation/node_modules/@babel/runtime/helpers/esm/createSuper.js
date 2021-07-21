import getPrototypeOf from "@babel/runtime/helpers/esm/getPrototypeOf";
import isNativeReflectConstruct from "@babel/runtime/helpers/esm/isNativeReflectConstruct";
import possibleConstructorReturn from "@babel/runtime/helpers/esm/possibleConstructorReturn";
export default function _createSuper(Derived) {
  var hasNativeReflectConstruct = isNativeReflectConstruct();
  return function _createSuperInternal() {
    var Super = getPrototypeOf(Derived),
        result;

    if (hasNativeReflectConstruct) {
      var NewTarget = getPrototypeOf(this).constructor;
      result = Reflect.construct(Super, arguments, NewTarget);
    } else {
      result = Super.apply(this, arguments);
    }

    return possibleConstructorReturn(this, result);
  };
}