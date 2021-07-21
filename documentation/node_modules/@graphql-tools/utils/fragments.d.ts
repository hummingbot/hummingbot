import { InlineFragmentNode } from 'graphql';
export declare function concatInlineFragments(type: string, fragments: Array<InlineFragmentNode>): InlineFragmentNode;
export declare function parseFragmentToInlineFragment(definitions: string): InlineFragmentNode;
