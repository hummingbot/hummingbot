"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var useScroll = function (ref) {
    if (process.env.NODE_ENV === 'development') {
        if (typeof ref !== 'object' || typeof ref.current === 'undefined') {
            console.error('`useScroll` expects a single ref argument.');
        }
    }
    var frame = react_1.useRef(0);
    var _a = react_1.useState({
        x: 0,
        y: 0,
    }), state = _a[0], setState = _a[1];
    react_1.useEffect(function () {
        var handler = function () {
            cancelAnimationFrame(frame.current);
            frame.current = requestAnimationFrame(function () {
                if (ref.current) {
                    setState({
                        x: ref.current.scrollLeft,
                        y: ref.current.scrollTop,
                    });
                }
            });
        };
        if (ref.current) {
            ref.current.addEventListener('scroll', handler, {
                capture: false,
                passive: true,
            });
        }
        return function () {
            if (frame.current) {
                cancelAnimationFrame(frame.current);
            }
            if (ref.current) {
                ref.current.removeEventListener('scroll', handler);
            }
        };
    }, [ref.current]);
    return state;
};
exports.default = useScroll;
