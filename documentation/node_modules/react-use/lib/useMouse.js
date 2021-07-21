"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var useMouse = function (ref) {
    if (process.env.NODE_ENV === 'development') {
        if (typeof ref !== 'object' || typeof ref.current === 'undefined') {
            console.error('useMouse expects a single ref argument.');
        }
    }
    var frame = react_1.useRef(0);
    var _a = react_1.useState({
        docX: 0,
        docY: 0,
        posX: 0,
        posY: 0,
        elX: 0,
        elY: 0,
        elH: 0,
        elW: 0,
    }), state = _a[0], setState = _a[1];
    react_1.useEffect(function () {
        var moveHandler = function (event) {
            cancelAnimationFrame(frame.current);
            frame.current = requestAnimationFrame(function () {
                if (ref && ref.current) {
                    var _a = ref.current.getBoundingClientRect(), left = _a.left, top_1 = _a.top, elW = _a.width, elH = _a.height;
                    var posX = left + window.scrollX;
                    var posY = top_1 + window.scrollY;
                    var elX = event.pageX - posX;
                    var elY = event.pageY - posY;
                    setState({
                        docX: event.pageX,
                        docY: event.pageY,
                        posX: posX,
                        posY: posY,
                        elX: elX,
                        elY: elY,
                        elH: elH,
                        elW: elW,
                    });
                }
            });
        };
        document.addEventListener('mousemove', moveHandler);
        return function () {
            cancelAnimationFrame(frame.current);
            document.removeEventListener('mousemove', moveHandler);
        };
    }, [ref.current]);
    return state;
};
exports.default = useMouse;
