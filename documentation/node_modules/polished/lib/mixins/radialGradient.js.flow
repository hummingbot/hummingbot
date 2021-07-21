// @flow
import type { RadialGradientConfiguration } from '../types/radialGradientConfiguration'
import type { Styles } from '../types/style'

function parseFallback(colorStops: Array<string>): string {
  return colorStops[0].split(' ')[0]
}

function constructGradientValue(
  literals: Array<string>,
  ...substitutions: Array<string>
): string {
  let template = ''
  for (let i = 0; i < literals.length; i += 1) {
    template += literals[i]
    // Adds leading coma if properties preceed color-stops
    if (
      i === 3
      && substitutions[i]
      && (substitutions[0] || substitutions[1] || substitutions[2])
    ) {
      template = template.slice(0, -1)
      template += `, ${substitutions[i]}`
      // No trailing space if color-stops is the only param provided
    } else if (
      i === 3
      && substitutions[i]
      && (!substitutions[0] && !substitutions[1] && !substitutions[2])
    ) {
      template += `${substitutions[i]}`
      // Only adds substitution if it is defined
    } else if (substitutions[i]) {
      template += `${substitutions[i]} `
    }
  }
  return template.trim()
}

/**
 * CSS for declaring a radial gradient, including a fallback background-color. The fallback is either the first color-stop or an explicitly passed fallback color.
 *
 * @example
 * // Styles as object usage
 * const styles = {
 *   ...radialGradient({
 *     colorStops: ['#00FFFF 0%', 'rgba(0, 0, 255, 0) 50%', '#0000FF 95%'],
 *     extent: 'farthest-corner at 45px 45px',
 *     position: 'center',
 *     shape: 'ellipse',
 *   })
 * }
 *
 * // styled-components usage
 * const div = styled.div`
 *   ${radialGradient({
 *     colorStops: ['#00FFFF 0%', 'rgba(0, 0, 255, 0) 50%', '#0000FF 95%'],
 *     extent: 'farthest-corner at 45px 45px',
 *     position: 'center',
 *     shape: 'ellipse',
 *   })}
 *`
 *
 * // CSS as JS Output
 *
 * div: {
 *   'backgroundColor': '#00FFFF',
 *   'backgroundImage': 'radial-gradient(center ellipse farthest-corner at 45px 45px, #00FFFF 0%, rgba(0, 0, 255, 0) 50%, #0000FF 95%)',
 * }
 */
function radialGradient({
  colorStops,
  extent,
  fallback,
  position,
  shape,
}: RadialGradientConfiguration): Styles {
  if (!colorStops || colorStops.length < 2) {
    throw new Error(
      'radialGradient requries at least 2 color-stops to properly render.',
    )
  }
  return {
    backgroundColor: fallback || parseFallback(colorStops),
    backgroundImage: constructGradientValue`radial-gradient(${position}${shape}${extent}${colorStops.join(
      ', ',
    )})`,
  }
}

export default radialGradient
