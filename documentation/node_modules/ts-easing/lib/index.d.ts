export declare type TEasing = (time: number) => number;
export interface IEasingMap {
    linear: TEasing;
    quadratic: TEasing;
    cubic: TEasing;
    elastic: TEasing;
    inQuad: TEasing;
    outQuad: TEasing;
    inOutQuad: TEasing;
    inCubic: TEasing;
    outCubic: TEasing;
    inOutCubic: TEasing;
    inQuart: TEasing;
    outQuart: TEasing;
    inOutQuart: TEasing;
    inQuint: TEasing;
    outQuint: TEasing;
    inOutQuint: TEasing;
    inSine: TEasing;
    outSine: TEasing;
    inOutSine: TEasing;
    inExpo: TEasing;
    outExpo: TEasing;
    inOutExpo: TEasing;
    inCirc: TEasing;
    outCirc: TEasing;
    inOutCirc: TEasing;
}
export declare const easing: IEasingMap;
