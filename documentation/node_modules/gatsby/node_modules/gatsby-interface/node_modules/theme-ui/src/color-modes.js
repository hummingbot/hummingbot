import React, { useState, useEffect } from 'react'
import { css } from '@styled-system/css'
import { Global } from '@emotion/core'
import { useThemeUI } from './context'
import { createColorStyles } from './custom-properties'

const STORAGE_KEY = 'theme-ui-color-mode'
const HAS_STORAGE = typeof Storage !== 'undefined'

const storage = {
  get: init => HAS_STORAGE && window.localStorage.getItem(STORAGE_KEY) || init,
  set: value => HAS_STORAGE && window.localStorage.setItem(STORAGE_KEY, value),
}

export const getMediaQuery = () => {
  const darkQuery = '(prefers-color-scheme: dark)'
  const mql = window.matchMedia ? window.matchMedia(darkQuery) : {}
  const dark = mql.media === darkQuery
  return dark && mql.matches
}

const getName = theme =>
  theme.initialColorModeName || theme.initialColorMode || 'default'

export const useColorState = theme => {
  const [mode, setMode] = useState(getName(theme))

  useEffect(() => {
    // initialize
    const stored = storage.get()
    document.body.classList.remove('theme-ui-' + stored)
    const dark = getMediaQuery()
    if (!stored && dark && theme.useColorSchemeMediaQuery)
      return setMode('dark')
    if (!stored || stored === mode) return
    setMode(stored)
  }, [])

  useEffect(() => {
    if (!mode) return
    storage.set(mode)
  }, [mode])

  if (process.env.NODE_ENV !== 'production') {
    if (
      theme.colors &&
      theme.colors.modes &&
      Object.keys(theme.colors.modes).indexOf(getName(theme)) > -1
    ) {
      console.warn(
        'The `initialColorMode` value should be a unique name' +
          ' and cannot reference a key in `theme.colors.modes`.'
      )
    }
  }

  return [mode, setMode]
}

export const useColorMode = () => {
  const { colorMode, setColorMode } = useThemeUI()

  if (typeof setColorMode !== 'function') {
    throw new Error(`[useColorMode] requires the ThemeProvider component`)
  }

  return [colorMode, setColorMode]
}

const bodyColor = theme => ({
  body: createColorStyles(theme),
})

export const ColorMode = () => <Global styles={bodyColor} />

export const InitializeColorMode = () => (
  <script
    key="theme-ui-no-flash"
    dangerouslySetInnerHTML={{
      __html: `(function() { try {
        var mode = localStorage.getItem('theme-ui-color-mode');
        if (!mode) return
        document.body.classList.add('theme-ui-' + mode);
      } catch (e) {} })();`,
    }}
  />
)

export default useColorMode
