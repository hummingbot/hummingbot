import { css, get } from '@styled-system/css'

export const themed = key => props =>
  css(get(props.theme, `styles.${key}`))(props.theme)

export default themed
