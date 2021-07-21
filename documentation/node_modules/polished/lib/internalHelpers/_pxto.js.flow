// @flow

import endsWith from './_endsWith'
import stripUnit from '../helpers/stripUnit'

/**
 * Factory function that creates pixel-to-x converters
 * @private
 */
const pxtoFactory = (to: string) => (
  pxval: string | number,
  base?: string | number = '16px',
): string => {
  let newPxval = pxval
  let newBase = base
  if (typeof pxval === 'string') {
    if (!endsWith(pxval, 'px')) {
      throw new Error(`Expected a string ending in "px" or a number passed as the first argument to ${to}(), got "${pxval}" instead.`)
    }
    newPxval = stripUnit(pxval)
  }

  if (typeof base === 'string') {
    if (!endsWith(base, 'px')) {
      throw new Error(`Expected a string ending in "px" or a number passed as the second argument to ${to}(), got "${base}" instead.`)
    }
    newBase = stripUnit(base)
  }

  if (typeof newPxval === 'string') {
    throw new Error(`Passed invalid pixel value ("${pxval}") to ${to}(), please pass a value like "12px" or 12.`)
  }

  if (typeof newBase === 'string') {
    throw new Error(`Passed invalid base value ("${base}") to ${to}(), please pass a value like "12px" or 12.`)
  }

  return `${newPxval / newBase}${to}`
}

export default pxtoFactory
