"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var util_1 = require("./util");
var useWindowScroll = function () {
    var frame = react_1.useRef(0);
    var _a = react_1.useState({
        x: util_1.isClient ? window.scrollX : 0,
        y: util_1.isClient ? window.scrollY : 0,
    }), state = _a[0], setState = _a[1];
    react_1.useEffect(function () {
        var handler = function () {
            cancelAnimationFrame(frame.current);
            frame.current = requestAnimationFrame(function () {
                setState({
                    x: window.scrollX,
                    y: window.scrollY,
                });
            });
        };
        window.addEventListener('scroll', handler, {
            capture: false,
            passive: true,
        });
        return function () {
            cancelAnimationFrame(frame.current);
            window.removeEventListener('scroll', handler);
        };
    }, []);
    return state;
};
exports.default = useWindowScroll;
