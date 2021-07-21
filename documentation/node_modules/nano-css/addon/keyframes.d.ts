import {NanoRenderer} from '../types/nano';

export interface KeyframesAddon {
    /**
     * @param frames Map of keyframes.
     * @param block Optional semantic name.
     *
     * Returns a generated animation name.
     *
     * ```js
     * const animationName = nano.keyframes({
     *     from: {
     *         left: '0%',
     *     },
     *     to: {
     *         left: '100%',
     *     },
     * });
     * ```
     *
     * You need to install [`keyframes()` addon]()https://github.com/streamich/nano-css/blob/master/docs/keyframes.md) to use this method.
     *
     * ```js
     * import {create} from 'nano-css';
     * import {addon as addonKeyframes} from 'nano-css/addon/keyframes';
     *
     * const nano = create();
     * addonKeyframes(nano);
     * ```
     */
    keyframes: (frames: object, block?: string) => string;
}

export function addon(nano: NanoRenderer);
