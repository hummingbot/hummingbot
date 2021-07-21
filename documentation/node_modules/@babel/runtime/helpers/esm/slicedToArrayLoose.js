import arrayWithHoles from "@babel/runtime/helpers/esm/arrayWithHoles";
import iterableToArrayLimitLoose from "@babel/runtime/helpers/esm/iterableToArrayLimitLoose";
import unsupportedIterableToArray from "@babel/runtime/helpers/esm/unsupportedIterableToArray";
import nonIterableRest from "@babel/runtime/helpers/esm/nonIterableRest";
export default function _slicedToArrayLoose(arr, i) {
  return arrayWithHoles(arr) || iterableToArrayLimitLoose(arr, i) || unsupportedIterableToArray(arr, i) || nonIterableRest();
}