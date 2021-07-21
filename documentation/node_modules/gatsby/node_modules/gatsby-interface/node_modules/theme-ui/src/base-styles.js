/** @jsx jsx */
import jsx from './jsx'

export const BaseStyles = props =>
  <div
    {...props}
    sx={{
      fontFamily: 'body',
      lineHeight: 'body',
      fontWeight: 'body',
      variant: 'styles',
    }}
  />

export default BaseStyles
