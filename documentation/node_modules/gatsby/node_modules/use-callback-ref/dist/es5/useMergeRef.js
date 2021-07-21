"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var useRef_1 = require("./useRef");
var assignRef_1 = require("./assignRef");
/**
 * Merges two or more refs together providing a single interface to set their value
 * @param {RefObject|Ref} refs
 * @returns {MutableRefObject} - a new ref, which translates all changes to {refs}
 *
 * @see {@link mergeRefs} a version without buit-in memoization
 * @see https://github.com/theKashey/use-callback-ref#usemergerefs
 * @example
 * const Component = React.forwardRef((props, ref) => {
 *   const ownRef = useRef();
 *   const domRef = useMergeRefs([ref, ownRef]); // 👈 merge together
 *   return <div ref={domRef}>...</div>
 * }
 */
function useMergeRefs(refs, defaultValue) {
    return useRef_1.useCallbackRef(defaultValue, function (newValue) {
        return refs.forEach(function (ref) { return assignRef_1.assignRef(ref, newValue); });
    });
}
exports.useMergeRefs = useMergeRefs;
