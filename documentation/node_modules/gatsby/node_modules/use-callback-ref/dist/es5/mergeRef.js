"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var createRef_1 = require("./createRef");
var assignRef_1 = require("./assignRef");
/**
 * Merges two or more refs together providing a single interface to set their value
 * @param {RefObject|Ref} refs
 * @returns {MutableRefObject} - a new ref, which translates all changes to {refs}
 *
 * @see {@link useMergeRefs} to be used in ReactComponents
 * @example
 * const Component = React.forwardRef((props, ref) => {
 *   const ownRef = useRef();
 *   const domRef = mergeRefs([ref, ownRef]); // 👈 merge together
 *   return <div ref={domRef}>...</div>
 * }
 */
function mergeRefs(refs) {
    return createRef_1.createCallbackRef(function (newValue) {
        return refs.forEach(function (ref) { return assignRef_1.assignRef(ref, newValue); });
    });
}
exports.mergeRefs = mergeRefs;
