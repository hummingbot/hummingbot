import useKeyPressDefault from './useKeyPress';
import useUpdateEffect from './useUpdateEffect';
var useKeyPressEvent = function (key, keydown, keyup, useKeyPress) {
    if (useKeyPress === void 0) { useKeyPress = useKeyPressDefault; }
    var _a = useKeyPress(key), pressed = _a[0], event = _a[1];
    useUpdateEffect(function () {
        if (!pressed && keyup) {
            keyup(event);
        }
        else if (pressed && keydown) {
            keydown(event);
        }
    }, [pressed]);
};
export default useKeyPressEvent;
