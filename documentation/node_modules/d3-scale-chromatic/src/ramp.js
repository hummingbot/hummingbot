import {interpolateRgbBasis} from "d3-interpolate";

export default function(scheme) {
  return interpolateRgbBasis(scheme[scheme.length - 1]);
}
