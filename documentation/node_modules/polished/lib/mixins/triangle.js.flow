// @flow
import borderColor from '../shorthands/borderColor'

import type { SideKeyword } from '../types/sideKeyword'
import type { Styles } from '../types/style'
import type { TriangleConfiguration } from '../types/triangleConfiguration'

const getBorderWidth = (
  pointingDirection: SideKeyword,
  height: [number, string],
  width: [number, string],
): string => {
  switch (pointingDirection) {
    case 'top':
      return `0 ${width[0] / 2}${width[1]} ${height[0]}${height[1]} ${width[0]
        / 2}${width[1]}`
    case 'left':
      return `${height[0] / 2}${height[1]} ${width[0]}${width[1]} ${height[0]
        / 2}${height[1]} 0`
    case 'bottom':
      return `${height[0]}${height[1]} ${width[0] / 2}${width[1]} 0 ${width[0]
        / 2}${width[1]}`
    case 'right':
      return `${height[0] / 2}${height[1]} 0 ${height[0] / 2}${height[1]} ${
        width[0]
      }${width[1]}`

    default:
      throw new Error(
        "Passed invalid argument to triangle, please pass correct pointingDirection e.g. 'right'.",
      )
  }
}

// needed for border-color
const reverseDirection = ['bottom', 'left', 'top', 'right']
const NUMBER_AND_FLOAT = /(\d*\.?\d*)/

/**
 * CSS to represent triangle with any pointing direction with an optional background color. Accepts number or px values for height and width.
 *
 * @example
 * // Styles as object usage
 *
 * const styles = {
 *   ...triangle({ pointingDirection: 'right', width: '100px', height: '100px', foregroundColor: 'red' })
 * }
 *
 *
 * // styled-components usage
 * const div = styled.div`
 *   ${triangle({ pointingDirection: 'right', width: '100px', height: '100px', foregroundColor: 'red' })}
 *
 *
 * // CSS as JS Output
 *
 * div: {
 *  'borderColor': 'transparent',
 *  'borderLeftColor': 'red !important',
 *  'borderStyle': 'solid',
 *  'borderWidth': '50px 0 50px 100px',
 *  'height': '0',
 *  'width': '0',
 * }
 */
function triangle({
  pointingDirection,
  height,
  width,
  foregroundColor,
  backgroundColor = 'transparent',
}: TriangleConfiguration): Styles {
  const widthAndUnit = [
    parseFloat(width),
    String(width).replace(NUMBER_AND_FLOAT, '') || 'px',
  ]
  const heightAndUnit = [
    parseFloat(height),
    String(height).replace(NUMBER_AND_FLOAT, '') || 'px',
  ]
  if (isNaN(heightAndUnit[0]) || isNaN(widthAndUnit[0])) {
    throw new Error(
      'Passed an invalid value to `height` or `width`. Please provide a pixel based unit',
    )
  }

  const reverseDirectionIndex = reverseDirection.indexOf(pointingDirection)
  return {
    width: '0',
    height: '0',
    borderWidth: getBorderWidth(pointingDirection, heightAndUnit, widthAndUnit),
    borderStyle: 'solid',
    ...borderColor(
      ...Array.from({ length: 4 }).map(
        (_, index) => index === reverseDirectionIndex ? foregroundColor : backgroundColor,
      ),
    ),
  }
}

export default triangle
