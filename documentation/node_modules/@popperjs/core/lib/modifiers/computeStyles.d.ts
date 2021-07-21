import { PositioningStrategy, Modifier, Rect } from "../types";
import { BasePlacement } from "../enums";
export declare type Options = {
    gpuAcceleration: boolean;
    adaptive: boolean;
};
export declare function mapToStyles({ popper, popperRect, placement, offsets, position, gpuAcceleration, adaptive }: {
    popper: HTMLElement;
    popperRect: Rect;
    placement: BasePlacement;
    offsets: Partial<{
        x: number;
        y: number;
        centerOffset: number;
    }>;
    position: PositioningStrategy;
    gpuAcceleration: boolean;
    adaptive: boolean;
}): {
    transform: string;
    top: string;
    right: string;
    bottom: string;
    left: string;
    position: PositioningStrategy;
};
export declare type ComputeStylesModifier = Modifier<"computeStyles", Options>;
declare const _default: Modifier<"computeStyles", Options>;
export default _default;
