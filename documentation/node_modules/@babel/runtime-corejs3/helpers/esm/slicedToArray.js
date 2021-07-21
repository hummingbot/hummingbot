import arrayWithHoles from "@babel/runtime-corejs3/helpers/esm/arrayWithHoles";
import iterableToArrayLimit from "@babel/runtime-corejs3/helpers/esm/iterableToArrayLimit";
import unsupportedIterableToArray from "@babel/runtime-corejs3/helpers/esm/unsupportedIterableToArray";
import nonIterableRest from "@babel/runtime-corejs3/helpers/esm/nonIterableRest";
export default function _slicedToArray(arr, i) {
  return arrayWithHoles(arr) || iterableToArrayLimit(arr, i) || unsupportedIterableToArray(arr, i) || nonIterableRest();
}