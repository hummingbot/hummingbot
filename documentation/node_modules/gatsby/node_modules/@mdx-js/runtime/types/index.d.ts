// TypeScript Version: 3.5

import {FunctionComponent} from 'react'
import {Options} from '@mdx-js/mdx'
import {ComponentsProp} from '@mdx-js/react'

/**
 * Properties for the MDX Runtime component
 */
export interface MDXRuntimeProps
  extends Omit<Options, 'footnotes' | 'compilers'>,
    Partial<ComponentsProp> {
  /**
   * MDX text
   */
  children?: string

  /**
   * Values in usable in MDX scope
   */
  scope?: {
    [variableName: string]: unknown
  }
}

/**
 * Renders child MDX text as a React component
 */
declare const mdxRuntime: FunctionComponent<MDXRuntimeProps>

export default mdxRuntime
