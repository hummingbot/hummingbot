import { State, Padding } from "../types";
import { Placement, ComputedPlacement, Boundary, RootBoundary } from "../enums";
declare type Options = {
    placement: Placement;
    padding: Padding;
    boundary: Boundary;
    rootBoundary: RootBoundary;
    flipVariations: boolean;
    allowedAutoPlacements?: Array<Placement>;
};
export default function computeAutoPlacement(state: Partial<State>, options?: Options): Array<ComputedPlacement>;
export {};
