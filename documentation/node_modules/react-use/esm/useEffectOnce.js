import { useEffect } from 'react';
var useEffectOnce = function (effect) {
    useEffect(effect, []);
};
export default useEffectOnce;
