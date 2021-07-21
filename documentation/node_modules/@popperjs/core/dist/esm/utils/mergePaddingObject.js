import getFreshSideObject from "./getFreshSideObject.js";
export default function mergePaddingObject(paddingObject) {
  return Object.assign(Object.assign({}, getFreshSideObject()), paddingObject);
}