import { ASTVisitor } from '../../language/visitor';
import { ValidationContext } from '../ValidationContext';

export function unusedFragMessage(fragName: string): string;

/**
 * No unused fragments
 *
 * A GraphQL document is only valid if all fragment definitions are spread
 * within operations, or spread within other fragments spread within operations.
 */
export function NoUnusedFragments(context: ValidationContext): ASTVisitor;
