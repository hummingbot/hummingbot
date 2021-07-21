// @flow
import reduceHexValue from '../internalHelpers/_reduceHexValue'
import toHex from '../internalHelpers/_numberToHex'

import type { RgbColor } from '../types/color'

/**
 * Returns a string value for the color. The returned result is the smallest possible hex notation.
 *
 * @example
 * // Styles as object usage
 * const styles = {
 *   background: rgb(255, 205, 100),
 *   background: rgb({ red: 255, green: 205, blue: 100 }),
 * }
 *
 * // styled-components usage
 * const div = styled.div`
 *   background: ${rgb(255, 205, 100)};
 *   background: ${rgb({ red: 255, green: 205, blue: 100 })};
 * `
 *
 * // CSS in JS Output
 *
 * element {
 *   background: "#ffcd64";
 *   background: "#ffcd64";
 * }
 */
function rgb(value: RgbColor | number, green?: number, blue?: number): string {
  if (
    typeof value === 'number'
    && typeof green === 'number'
    && typeof blue === 'number'
  ) {
    return reduceHexValue(`#${toHex(value)}${toHex(green)}${toHex(blue)}`)
  } else if (
    typeof value === 'object'
    && green === undefined
    && blue === undefined
  ) {
    return reduceHexValue(
      `#${toHex(value.red)}${toHex(value.green)}${toHex(value.blue)}`,
    )
  }

  throw new Error(
    'Passed invalid arguments to rgb, please pass multiple numbers e.g. rgb(255, 205, 100) or an object e.g. rgb({ red: 255, green: 205, blue: 100 }).',
  )
}

export default rgb
