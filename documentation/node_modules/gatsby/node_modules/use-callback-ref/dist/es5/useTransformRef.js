"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var useRef_1 = require("./useRef");
var assignRef_1 = require("./assignRef");
/**
 * Create a _lense_ on Ref, making it possible to transform ref value
 * @param {ReactRef} ref
 * @param {Function} transformer. 👉 Ref would be __NOT updated__ on `transformer` update.
 * @returns {RefObject}
 *
 * @see https://github.com/theKashey/use-callback-ref#usetransformref-to-replace-reactuseimperativehandle
 * @example
 *
 * const ResizableWithRef = forwardRef((props, ref) =>
 *  <Resizable {...props} ref={useTransformRef(ref, i => i ? i.resizable : null)}/>
 * );
 */
function useTransformRef(ref, transformer) {
    return useRef_1.useCallbackRef(undefined, function (value) {
        return assignRef_1.assignRef(ref, transformer(value));
    });
}
exports.useTransformRef = useTransformRef;
