import { createContext, useContext } from 'react'
import { components } from './components'
import { version as emotionVersion } from '@emotion/core/package.json'

export const Context = createContext({
  emotionVersion,
  theme: null,
  components,
})

export const useThemeUI = () => useContext(Context)
