import { popperGenerator, detectOverflow } from "./createPopper.js";
import eventListeners from "./modifiers/eventListeners.js";
import popperOffsets from "./modifiers/popperOffsets.js";
import computeStyles from "./modifiers/computeStyles.js";
import applyStyles from "./modifiers/applyStyles.js";
var defaultModifiers = [eventListeners, popperOffsets, computeStyles, applyStyles];
var createPopper = /*#__PURE__*/popperGenerator({
  defaultModifiers: defaultModifiers
}); // eslint-disable-next-line import/no-unused-modules

export { createPopper, popperGenerator, defaultModifiers, detectOverflow };