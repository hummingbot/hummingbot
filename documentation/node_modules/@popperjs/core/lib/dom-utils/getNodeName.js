export default function getNodeName(element) {
  return element ? (element.nodeName || '').toLowerCase() : null;
}