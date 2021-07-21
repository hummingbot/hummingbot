// @flow
import capitalizeString from '../internalHelpers/_capitalizeString'

import type { Styles } from '../types/style'

/**
 * Shorthand that accepts a value for side and a value for radius and applies the radius value to both corners of the side.
 * @example
 * // Styles as object usage
 * const styles = {
 *   ...borderRadius('top', '5px')
 * }
 *
 * // styled-components usage
 * const div = styled.div`
 *   ${borderRadius('top', '5px')}
 * `
 *
 * // CSS as JS Output
 *
 * div {
 *   'borderTopRightRadius': '5px',
 *   'borderTopLeftRadius': '5px',
 * }
 */
function borderRadius(side: string, radius: string | number): Styles {
  const uppercaseSide = capitalizeString(side)
  if (!radius && radius !== 0) {
    throw new Error(
      'borderRadius expects a radius value as a string or number as the second argument.',
    )
  }
  if (uppercaseSide === 'Top' || uppercaseSide === 'Bottom') {
    return {
      [`border${uppercaseSide}RightRadius`]: radius,
      [`border${uppercaseSide}LeftRadius`]: radius,
    }
  }

  if (uppercaseSide === 'Left' || uppercaseSide === 'Right') {
    return {
      [`borderTop${uppercaseSide}Radius`]: radius,
      [`borderBottom${uppercaseSide}Radius`]: radius,
    }
  }

  throw new Error(
    'borderRadius expects one of "top", "bottom", "left" or "right" as the first argument.',
  )
}

export default borderRadius
