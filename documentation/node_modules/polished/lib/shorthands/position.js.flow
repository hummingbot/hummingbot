// @flow
import directionalProperty from '../helpers/directionalProperty'

import type { Styles } from '../types/style'

const positionMap = ['absolute', 'fixed', 'relative', 'static', 'sticky']

/**
 * Shorthand accepts up to five values, including null to skip a value, and maps them to their respective directions. The first value can optionally be a position keyword.
 * @example
 * // Styles as object usage
 * const styles = {
 *   ...position('12px', '24px', '36px', '48px')
 * }
 *
 * // styled-components usage
 * const div = styled.div`
 *   ${position('12px', '24px', '36px', '48px')}
 * `
 *
 * // CSS as JS Output
 *
 * div {
 *   'top': '12px',
 *   'right': '24px',
 *   'bottom': '36px',
 *   'left': '48px'
 * }
 *
 * // Styles as object usage
 * const styles = {
 *   ...position('absolute', '12px', '24px', '36px', '48px')
 * }
 *
 * // styled-components usage
 * const div = styled.div`
 *   ${position('absolute', '12px', '24px', '36px', '48px')}
 * `
 *
 * // CSS as JS Output
 *
 * div {
 *   'position': 'absolute',
 *   'top': '12px',
 *   'right': '24px',
 *   'bottom': '36px',
 *   'left': '48px'
 * }
 */
function position(
  positionKeyword: string | null,
  ...values: Array<?string | ?number>
): Styles {
  if (positionMap.indexOf(positionKeyword) >= 0) {
    return {
      position: positionKeyword,
      ...directionalProperty('', ...values),
    }
  } else {
    const firstValue = positionKeyword // in this case position is actually the first value
    return directionalProperty('', firstValue, ...values)
  }
}

export default position
