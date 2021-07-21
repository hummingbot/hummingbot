import { TSESTree } from './ts-estree';
interface SimpleTraverseOptions {
    enter: (node: TSESTree.Node, parent: TSESTree.Node | undefined) => void;
}
export declare function simpleTraverse(startingNode: TSESTree.Node, options: SimpleTraverseOptions): void;
export {};
//# sourceMappingURL=simple-traverse.d.ts.map