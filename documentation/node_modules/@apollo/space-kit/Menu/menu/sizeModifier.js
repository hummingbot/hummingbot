'use strict';

Object.defineProperty(exports, '__esModule', { value: true });

function _interopDefault (ex) { return (ex && (typeof ex === 'object') && 'default' in ex) ? ex['default'] : ex; }

var _tslib = require('../../_tslib-bcbe0269.js');
var computeAutoPlacement = _interopDefault(require('@popperjs/core/lib/utils/computeAutoPlacement'));
var detectOverflow = _interopDefault(require('@popperjs/core/lib/utils/detectOverflow'));
var getOppositePlacement = _interopDefault(require('@popperjs/core/lib/utils/getOppositePlacement'));
var getOppositeVariationPlacement = _interopDefault(require('@popperjs/core/lib/utils/getOppositeVariationPlacement'));

/**
 * Get the base of a `Placement`, meaning strip off `-start` and `-end`
 *
 * This will also work with `auto`, which is why this is modified from the
 * internal popper version
 */
function getBasePlacement(placement) {
    return placement.split("-")[0];
}
function getExpandedFallbackPlacements(placement) {
    if (getBasePlacement(placement) === "auto") {
        return [];
    }
    var oppositePlacement = getOppositePlacement(placement);
    return [
        getOppositeVariationPlacement(placement),
        oppositePlacement,
        getOppositeVariationPlacement(oppositePlacement),
    ];
}
/**
 * Find the placement with the minimum vertical overflow. If there is a tie
 * between placements, the first placement wins.
 */
function findPlacementWithMinimumVerticalOverflow(_a) {
    var placementOverflows = _a.placementOverflows, popperRect = _a.popperRect, _b = _a.preventOverflow, preventOverflow = _b === void 0 ? { x: 0, y: 0 } : _b;
    var height = popperRect.height;
    var y = preventOverflow.y;
    var placementCalculations = placementOverflows.map(function (_a) {
        var placement = _a.placement, overflow = _a.overflow;
        var verticalOverflow = overflow[getBasePlacement(placement) === "top" ? "top" : "bottom"];
        return {
            placement: placement,
            overflowPixels: Math.max(0, verticalOverflow),
            // The `overflow` can be negative here; this is how the container can
            // expand when we are resizing to expose more of the clipped content.
            maxHeight: height - verticalOverflow - y,
        };
    });
    // Sort `placementCalculations` by which placement has the least overflow
    // pixels. If there is a tie, use the preferred placement.
    placementCalculations.sort(function (a, b) {
        if (b.overflowPixels !== a.overflowPixels) {
            return a.overflowPixels - b.overflowPixels;
        }
        // If the heights are the same then we have no overflow in these two
        // placements. We must prioritize the user-specified placement order here.
        // While `overflowed` is already in the correct order, preserving original
        // sort order is explicitly stated to not be stable in the
        // [`Array.prototype.sort`
        // spec](http://www.ecma-international.org/ecma-262/6.0/#sec-array.prototype.sort)
        //
        // We could build an index for the indicies, but I don't think we'll have
        // any performance issues because the placement lists are short.
        var aPlacementWeight = placementOverflows.findIndex(function (overflow) { return overflow.placement === a.placement; });
        var bPlacementWeight = placementOverflows.findIndex(function (overflow) { return overflow.placement === b.placement; });
        return aPlacementWeight - bPlacementWeight;
    });
    return placementCalculations[0];
}
/**
 * Find the last ordered modifier that includes a `padding` configuration.
 * Defaults to `0` if none are found.
 */
function getPaddingFromState(state) {
    return state.orderedModifiers.reduce(function (accumulator, modifier) {
        var _a;
        if (typeof ((_a = modifier.options) === null || _a === void 0 ? void 0 : _a.padding) != "undefined") {
            accumulator = modifier.options.padding;
        }
        return accumulator;
    }, 0);
}
/**
 * Calculate the placement and max size
 */
function getPlacementAndMaxSize(_a) {
    var state = _a.state, options = _a.options;
    var specifiedFallbackPlacements = options.fallbackPlacements, _b = options.padding, padding = _b === void 0 ? getPaddingFromState(state) : _b, _c = options.boundary, boundary = _c === void 0 ? "clippingParents" : _c, _d = options.rootBoundary, rootBoundary = _d === void 0 ? "viewport" : _d, altBoundary = options.altBoundary, _e = options.flipVariations, flipVariations = _e === void 0 ? true : _e, allowedAutoPlacements = options.allowedAutoPlacements;
    /**
     * Preferred placement
     *
     * Taken from options
     */
    var preferredPlacement = state.options.placement;
    /**
     * Base placement from `preferredPlacement`
     */
    var basePlacement = getBasePlacement(preferredPlacement);
    /**
     * Represents if the `preferredPlacement` is a `BasePlacement` (meaning it has
     * no `-begin` or `-end`)
     */
    var isBasePlacement = basePlacement === preferredPlacement;
    /**
     * List of fallback placements
     *
     * Either passed in with `specifiedFallbackPlacements`, or calculated
     * depending on
     * [`flipVariations`](https://popper.js.org/docs/v2/modifiers/flip/#flipvariations)
     *
     * Copied verbatim from popper's flip modifier source; @see
     * https://github.com/popperjs/popper-core/blob/de867743d4b841af88675691064c8271452e150f/src/modifiers/flip.js#L55-L59
     */
    var fallbackPlacements = specifiedFallbackPlacements ||
        (isBasePlacement || !flipVariations
            ? [getOppositePlacement(preferredPlacement)]
            : getExpandedFallbackPlacements(preferredPlacement));
    /**
     * Aggregate of all placements, including preferred and fallbacks.
     *
     * This is copied verbatim from the popper's flip modifier source; @see
     * https://github.com/popperjs/popper-core/blob/de867743d4b841af88675691064c8271452e150f/src/modifiers/flip.js#L61-L77
     */
    var placements = _tslib.__spreadArrays([preferredPlacement], fallbackPlacements).reduce(function (acc, placement) {
        return acc.concat(getBasePlacement(placement) === "auto"
            ? computeAutoPlacement(state, {
                placement: placement,
                boundary: boundary,
                rootBoundary: rootBoundary,
                padding: padding,
                flipVariations: flipVariations,
                allowedAutoPlacements: allowedAutoPlacements,
            })
            : placement);
    }, []);
    var popperRect = state.rects.popper;
    /**
     * Array calculated from `placements` with the calculated values of each
     * `placement`. This will be used to determine if we're capable of flipping
     * the element to display it or of we have to set the `max-height` too.
     */
    var placementOverflows = placements.map(function (placement) { return ({
        placement: placement,
        overflow: detectOverflow(state, {
            placement: placement,
            boundary: boundary,
            rootBoundary: rootBoundary,
            altBoundary: altBoundary,
            padding: padding,
        }),
    }); });
    /**
     * First placement that does not overflow on any side
     */
    var firstPlacementWithNoOverflow = placementOverflows.find(function (_a) {
        var overflow = _a.overflow;
        return overflow.bottom <= 0 &&
            overflow.top <= 0 &&
            overflow.right <= 0 &&
            overflow.left <= 0;
    });
    if (firstPlacementWithNoOverflow) {
        return {
            placement: firstPlacementWithNoOverflow.placement,
            maxSize: popperRect,
        };
    }
    var minimumOverflowPlacement = findPlacementWithMinimumVerticalOverflow({
        placementOverflows: placementOverflows,
        popperRect: state.rects.popper,
        preventOverflow: state.modifiersData.preventOverflow,
    });
    return {
        placement: minimumOverflowPlacement.placement,
        maxSize: { height: minimumOverflowPlacement.maxHeight },
    };
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
var sizeModifier = {
    name: "maxSize",
    enabled: true,
    phase: "main",
    requiresIfExists: ["offset", "preventOverflow", "flip"],
    // `_skip` is a custom property we use internally to prevent us from flipping
    // more than once in a single tick.
    data: { _skip: false },
    fn: function (modifierArguments) {
        var _a = getPlacementAndMaxSize(modifierArguments), placement = _a.placement, maxSize = _a.maxSize;
        // Set the max height to be written in the `write` phase. See
        // https://www.npmjs.com/package/popper-max-size-modifier and
        // https://codesandbox.io/s/great-tesla-3roz7 for prior art
        modifierArguments.state.modifiersData[modifierArguments.name] = {
            height: maxSize.height,
        };
        // If the placement has changed and we haven't already changed the
        // placement, then change it.
        if (modifierArguments.state.placement !== placement &&
            !modifierArguments.state.modifiersData[modifierArguments.name]._skip) {
            modifierArguments.state.modifiersData[modifierArguments.name]._skip = true;
            modifierArguments.state.placement = placement;
            // If we're applying a new position, then all other modifiers need to be
            // completely re-run, which is what setting `state.reset = true` does.
            // @see https://popper.js.org/docs/v2/modifiers/#fn
            modifierArguments.state.reset = true;
        }
    },
};

exports.sizeModifier = sizeModifier;
//# sourceMappingURL=sizeModifier.js.map
