import { useEffect, useRef } from 'react';
import { off, on } from './util';
var defaultEvents = ['mousedown', 'touchstart'];
var useClickAway = function (ref, onClickAway, events) {
    if (events === void 0) { events = defaultEvents; }
    var savedCallback = useRef(onClickAway);
    useEffect(function () {
        savedCallback.current = onClickAway;
    }, [onClickAway]);
    useEffect(function () {
        var handler = function (event) {
            var el = ref.current;
            el && !el.contains(event.target) && savedCallback.current(event);
        };
        for (var _i = 0, events_1 = events; _i < events_1.length; _i++) {
            var eventName = events_1[_i];
            on(document, eventName, handler);
        }
        return function () {
            for (var _i = 0, events_2 = events; _i < events_2.length; _i++) {
                var eventName = events_2[_i];
                off(document, eventName, handler);
            }
        };
    }, [events, ref]);
};
export default useClickAway;
