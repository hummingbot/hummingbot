import { Placement, Boundary, RootBoundary } from "../enums";
import { Rect, Modifier, Padding } from "../types";
declare type TetherOffset = ((arg0: {
    popper: Rect;
    reference: Rect;
    placement: Placement;
}) => number) | number;
export declare type Options = {
    mainAxis: boolean;
    altAxis: boolean;
    boundary: Boundary;
    rootBoundary: RootBoundary;
    altBoundary: boolean;
    /**
     * Allows the popper to overflow from its boundaries to keep it near its
     * reference element
     */
    tether: boolean;
    tetherOffset: TetherOffset;
    padding: Padding;
};
export declare type PreventOverflowModifier = Modifier<"preventOverflow", Options>;
declare const _default: Modifier<"preventOverflow", Options>;
export default _default;
