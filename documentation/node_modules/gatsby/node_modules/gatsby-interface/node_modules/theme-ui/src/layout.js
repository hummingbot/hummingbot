import jsx from './jsx'
import styled from './styled'

export const Box = styled('div')({
  boxSizing: 'border-box',
  minWidth: 0,
})

export const Flex = styled(Box)({
  display: 'flex',
})

// root/page layout
export const Layout = props =>
  jsx(Box, {
    ...props,
    sx: {
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      variant: 'styles.Layout',
    },
  })

export const Header = props =>
  jsx(Box, {
    as: 'header',
    ...props,
    sx: {
      display: 'flex',
      variant: 'styles.Header',
    },
  })

export const Main = props =>
  jsx(Box, {
    as: 'main',
    ...props,
    sx: {
      flex: '1 1 auto',
      variant: 'styles.Main',
    },
  })

export const Container = props =>
  jsx(Box, {
    ...props,
    sx: {
      width: '100%',
      minWidth: 0,
      maxWidth: 1024,
      mx: 'auto',
      p: 4,
      variant: 'styles.Container',
    },
  })

export const Footer = props =>
  jsx(Box, {
    as: 'footer',
    ...props,
    sx: {
      display: 'flex',
      variant: 'styles.Footer',
    },
  })
