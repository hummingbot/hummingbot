import arrayWithHoles from "@babel/runtime/helpers/esm/arrayWithHoles";
import iterableToArrayLimit from "@babel/runtime/helpers/esm/iterableToArrayLimit";
import unsupportedIterableToArray from "@babel/runtime/helpers/esm/unsupportedIterableToArray";
import nonIterableRest from "@babel/runtime/helpers/esm/nonIterableRest";
export default function _slicedToArray(arr, i) {
  return arrayWithHoles(arr) || iterableToArrayLimit(arr, i) || unsupportedIterableToArray(arr, i) || nonIterableRest();
}