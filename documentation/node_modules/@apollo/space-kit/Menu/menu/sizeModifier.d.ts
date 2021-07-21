import { Boundary, Modifier, Padding, Placement, RootBoundary } from "@popperjs/core";
interface Options {
    allowedAutoPlacements: Array<Placement>;
    altBoundary: boolean;
    boundary: Boundary;
    fallbackPlacements: Array<Placement>;
    flipVariations: boolean;
    padding: Padding;
    rootBoundary: RootBoundary;
}
/**
 * Popper [modifier](https://popper.js.org/docs/v2/modifiers/) based on popper's
 * built-in [flip]() modifier and the community
 * [`maxSize`](https://www.npmjs.com/package/popper-max-size-modifier). Neither
 * of those fit our needs because the `flip` modifier can't make an element
 * scrollable and the max size modifier only sets the max size, it doesn't try
 * to figure out the best position to use with a max size.
 *
 * This combines the logic of those two to create a modifier that will behave
 * exactly like `flip`, but if there are no placements that can display the
 * element in it's entirety, it'll find the placement that can show the most
 * content with a max-height.
 */
export declare const sizeModifier: Modifier<Options>;
export {};
