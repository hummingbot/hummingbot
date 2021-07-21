// convert theme and style objects to CSS custom properties
import { css } from '@styled-system/css'

const toVarName = key => `--theme-ui-${key}`
const toVarValue = (key, value) => `var(${toVarName(key)}, ${value})`

const join = (...args) => args.filter(Boolean).join('-')

const numberScales = {
  fontWeights: true,
  lineHeights: true,
}
const reservedKeys = {
  useCustomProperties: true,
  initialColorModeName: true,
  initialColorMode: true,
}

const toPixel = (key, value) => {
  if (typeof value !== 'number') return value
  if (numberScales[key]) return value
  return value + 'px'
}

// convert theme values to custom properties
export const toCustomProperties = (obj, parent, themeKey) => {
  const next = Array.isArray(obj) ? [] : {}

  for (let key in obj) {
    const value = obj[key]
    const name = join(parent, key)
    if (value && typeof value === 'object') {
      next[key] = toCustomProperties(value, name, key)
      continue
    }
    if (reservedKeys[key]) {
      next[key] = value
      continue
    }
    const val = toPixel(themeKey || key, value)
    next[key] = toVarValue(name, val)
  }

  return next
}

export const objectToVars = (parent, obj) => {
  let vars = {}
  for (let key in obj) {
    if (key === 'modes') continue
    const name = join(parent, key)
    const value = obj[key]
    if (value && typeof value === 'object') {
      vars = {
        ...vars,
        ...objectToVars(name, value),
      }
    } else {
      vars[toVarName(name)] = value
    }
  }
  return vars
}

// create body styles for color modes
export const createColorStyles = theme => {
  if (!theme.colors || !theme.colors.modes) return {}
  if (theme.useCustomProperties === false) {
    return css({
      color: 'text',
      bg: 'background',
    })(theme)
  }
  const { modes } = theme.colors
  const styles = objectToVars('colors', theme.colors)

  Object.keys(modes).forEach(mode => {
    const key = `&.theme-ui-${mode}`
    styles[key] = objectToVars('colors', modes[mode])
  })

  return css({
    ...styles,
    color: t => `var(--theme-ui-colors-text, ${t.colors.text})`,
    bg: t => `var(--theme-ui-colors-background, ${t.colors.background})`,
  })(theme)
}
