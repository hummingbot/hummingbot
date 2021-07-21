import deepmerge from 'deepmerge'

const canUseSymbol = typeof Symbol === 'function' && Symbol.for

const REACT_ELEMENT = canUseSymbol ? Symbol.for('react.element') : 0xeac7
const FORWARD_REF = canUseSymbol ? Symbol.for('react.forward_ref') : 0xeac7

const isMergeableObject = n => {
  return (
    !!n &&
    typeof n === 'object' &&
    n.$$typeof !== REACT_ELEMENT &&
    n.$$typeof !== FORWARD_REF
  )
}

const arrayMerge = (destinationArray, sourceArray, options) => sourceArray

export const merge = (a, b) =>
  deepmerge(a, b, { isMergeableObject, arrayMerge })

merge.all = (...args) => deepmerge.all(args, { isMergeableObject, arrayMerge })

export default merge
