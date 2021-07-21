import getWindow from "./getWindow.js";
export default function getComputedStyle(element) {
  return getWindow(element).getComputedStyle(element);
}