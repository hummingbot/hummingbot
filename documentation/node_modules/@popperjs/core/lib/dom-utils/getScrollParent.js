import getParentNode from "./getParentNode.js";
import isScrollParent from "./isScrollParent.js";
import getNodeName from "./getNodeName.js";
import { isHTMLElement } from "./instanceOf.js";
export default function getScrollParent(node) {
  if (['html', 'body', '#document'].indexOf(getNodeName(node)) >= 0) {
    // $FlowFixMe: assume body is always available
    return node.ownerDocument.body;
  }

  if (isHTMLElement(node) && isScrollParent(node)) {
    return node;
  }

  return getScrollParent(getParentNode(node));
}