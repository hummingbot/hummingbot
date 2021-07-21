import { useEffect, useReducer } from 'react'
import { ThemeContext as EmotionContext } from '@emotion/core'
import { version as emotionVersion } from '@emotion/core/package.json'
import { MDXProvider } from '@mdx-js/react'
import { get } from '@styled-system/css'
import merge from './merge'
import jsx from './jsx'
import { Context, useThemeUI } from './context'
import { useColorState } from './color-modes'
import { createComponents } from './components'
import { toCustomProperties } from './custom-properties'

const mergeState = (state = {}, next) => merge.all({}, state, next)

const applyColorMode = (theme, mode) => {
  if (!mode) return theme
  const modes = get(theme, 'colors.modes', {})
  return merge.all({}, theme, {
    colors: get(modes, mode, {}),
  })
}

const BaseProvider = ({ context, components, children }) => {
  const theme = { ...context.theme }
  if (theme.useCustomProperties !== false) {
    theme.colors = toCustomProperties(theme.colors, 'colors')
  }
  return jsx(
    EmotionContext.Provider,
    { value: theme },
    jsx(
      MDXProvider,
      { components },
      jsx(Context.Provider, { value: context, children })
    )
  )
}

const RootProvider = ({ theme: propsTheme = {}, components, children }) => {
  // components are provided in the default Context
  const outer = useThemeUI()
  const propsThemeObject =
    typeof propsTheme === 'function' ? propsTheme({}) : propsTheme
  const [colorMode, setColorMode] = useColorState(
    outer.theme || propsThemeObject
  )

  const theme = applyColorMode(outer.theme || propsThemeObject, colorMode)

  const context = {
    ...outer,
    __THEME_UI__: true,
    colorMode,
    setColorMode,
    components: { ...outer.components, ...createComponents(components) },
    theme,
  }

  useEffect(() => {
    window.__THEME_UI__ = context
  }, [context.theme, context.colorMode])

  return jsx(BaseProvider, {
    context,
    components: context.components,
    children,
  })
}

const NestedProvider = ({ theme, components, children }) => {
  const outer = useThemeUI()
  const context =
    typeof theme === 'function'
      ? { ...outer, theme: theme(outer.theme) }
      : merge.all({}, outer, { theme })

  return jsx(BaseProvider, {
    context,
    components: createComponents(components),
    children,
  })
}

export const ThemeProvider = props => {
  const outer = useThemeUI()

  if (process.env.NODE_ENV !== 'production') {
    if (outer.emotionVersion !== emotionVersion) {
      console.warn(
        'Multiple versions of Emotion detected,',
        'and theming might not work as expected.',
        'Please ensure there is only one copy of @emotion/core installed in your application.'
      )
    }
  }

  if (!props.scoped && outer.__THEME_UI__) {
    return jsx(NestedProvider, props)
  }
  return jsx(RootProvider, props)
}

export const ThemeStateProvider = ({ theme, children }) => {
  const outer = useThemeUI()
  const [state, setTheme] = useReducer(mergeState, theme)
  const context = {
    ...outer,
    theme: state,
    setTheme,
  }

  return jsx(Context.Provider, {
    value: context,
    children,
  })
}
