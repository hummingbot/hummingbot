import arrayWithHoles from "@babel/runtime-corejs3/helpers/esm/arrayWithHoles";
import iterableToArrayLimitLoose from "@babel/runtime-corejs3/helpers/esm/iterableToArrayLimitLoose";
import unsupportedIterableToArray from "@babel/runtime-corejs3/helpers/esm/unsupportedIterableToArray";
import nonIterableRest from "@babel/runtime-corejs3/helpers/esm/nonIterableRest";
export default function _slicedToArrayLoose(arr, i) {
  return arrayWithHoles(arr) || iterableToArrayLimitLoose(arr, i) || unsupportedIterableToArray(arr, i) || nonIterableRest();
}