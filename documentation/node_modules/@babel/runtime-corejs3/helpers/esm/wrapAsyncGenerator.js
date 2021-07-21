import AsyncGenerator from "@babel/runtime-corejs3/helpers/esm/AsyncGenerator";
export default function _wrapAsyncGenerator(fn) {
  return function () {
    return new AsyncGenerator(fn.apply(this, arguments));
  };
}