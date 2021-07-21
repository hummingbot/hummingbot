import getWindowScroll from "./getWindowScroll.js";
import getWindow from "./getWindow.js";
import { isHTMLElement } from "./instanceOf.js";
import getHTMLElementScroll from "./getHTMLElementScroll.js";
export default function getNodeScroll(node) {
  if (node === getWindow(node) || !isHTMLElement(node)) {
    return getWindowScroll(node);
  } else {
    return getHTMLElementScroll(node);
  }
}