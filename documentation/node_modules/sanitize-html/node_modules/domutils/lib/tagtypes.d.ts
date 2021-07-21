import type { Node, Element, NodeWithChildren, DataNode } from "domhandler";
/**
 * @param node Node to check.
 * @returns `true` if the node is a `Element`, `false` otherwise.
 */
export declare function isTag(node: Node): node is Element;
/**
 * @param node Node to check.
 * @returns `true` if the node is a `NodeWithChildren`, `false` otherwise.
 */
export declare function isCDATA(node: Node): node is NodeWithChildren;
/**
 * @param node Node to check.
 * @returns `true` if the node is a `DataNode`, `false` otherwise.
 */
export declare function isText(node: Node): node is DataNode;
/**
 * @param node Node to check.
 * @returns `true` if the node is a `DataNode`, `false` otherwise.
 */
export declare function isComment(node: Node): node is DataNode;
/**
 * @param node Node to check.
 * @returns `true` if the node is a `NodeWithChildren` (has children), `false` otherwise.
 */
export declare function hasChildren(node: Node): node is NodeWithChildren;
//# sourceMappingURL=tagtypes.d.ts.map