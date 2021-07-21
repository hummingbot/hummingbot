import { forwardRef, useContext } from 'react'
import { ThemeContext } from '@emotion/core'
import isPropValid from '@emotion/is-prop-valid'
import jsx from './jsx'

export const styled = tag => (...args) => {
  const Styled = forwardRef(({ as, ...props }, ref) => {
    const shouldForwardProps =
      typeof tag !== 'string' || (as && typeof as !== 'string')
    const theme = useContext(ThemeContext)
    let nextProps = shouldForwardProps ? props : {}
    let styles = {}
    args.forEach(arg => {
      const style = typeof arg === 'function' ? arg({ theme, ...props }) : arg
      Object.assign(styles, style)
    })

    if (!shouldForwardProps) {
      for (let key in props) {
        if (!isPropValid(key)) continue
        nextProps[key] = props[key]
      }
    }

    return jsx(as || tag, {
      ...nextProps,
      ref,
      css: styles,
    })
  })
  return Styled
}

export default styled
