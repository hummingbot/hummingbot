import { easing } from 'ts-easing';
import useRaf from './useRaf';
var useTween = function (easingName, ms, delay) {
    if (easingName === void 0) { easingName = 'inCirc'; }
    if (ms === void 0) { ms = 200; }
    if (delay === void 0) { delay = 0; }
    var fn = easing[easingName];
    var t = useRaf(ms, delay);
    if (process.env.NODE_ENV !== 'production') {
        if (typeof fn !== 'function') {
            console.error('useTween() expected "easingName" property to be a valid easing function name, like:' +
                '"' +
                Object.keys(easing).join('", "') +
                '".');
            console.trace();
            return 0;
        }
    }
    return fn(t);
};
export default useTween;
