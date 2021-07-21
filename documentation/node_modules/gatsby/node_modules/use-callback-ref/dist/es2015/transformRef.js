import { assignRef } from './assignRef';
import { createCallbackRef } from './createRef';
export function transformRef(ref, transformer) {
    return createCallbackRef(function (value) { return assignRef(ref, transformer(value)); });
}
