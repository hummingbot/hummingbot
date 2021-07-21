import _Symbol$hasInstance from "@babel/runtime-corejs3/core-js/symbol/has-instance";
import _Symbol from "@babel/runtime-corejs3/core-js/symbol";
export default function _instanceof(left, right) {
  if (right != null && typeof _Symbol !== "undefined" && right[_Symbol$hasInstance]) {
    return !!right[_Symbol$hasInstance](left);
  } else {
    return left instanceof right;
  }
}