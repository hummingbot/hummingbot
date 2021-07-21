import useEffectOnce from './useEffectOnce';
var useMount = function (fn) {
    useEffectOnce(function () {
        fn();
    });
};
export default useMount;
