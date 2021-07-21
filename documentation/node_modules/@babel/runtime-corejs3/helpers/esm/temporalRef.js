import undef from "@babel/runtime-corejs3/helpers/esm/temporalUndefined";
import err from "@babel/runtime-corejs3/helpers/esm/tdz";
export default function _temporalRef(val, name) {
  return val === undef ? err(name) : val;
}