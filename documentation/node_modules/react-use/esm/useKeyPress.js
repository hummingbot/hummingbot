import { useState } from 'react';
import useKey from './useKey';
var useKeyPress = function (keyFilter) {
    var _a = useState([false, null]), state = _a[0], set = _a[1];
    useKey(keyFilter, function (event) { return set([true, event]); }, { event: 'keydown' }, [state]);
    useKey(keyFilter, function (event) { return set([false, event]); }, { event: 'keyup' }, [state]);
    return state;
};
export default useKeyPress;
