import { useState } from 'react';
import useIsomorphicLayoutEffect from './useIsomorphicLayoutEffect';
function useObservable(observable$, initialValue) {
    var _a = useState(initialValue), value = _a[0], update = _a[1];
    useIsomorphicLayoutEffect(function () {
        var s = observable$.subscribe(update);
        return function () { return s.unsubscribe(); };
    }, [observable$]);
    return value;
}
export default useObservable;
