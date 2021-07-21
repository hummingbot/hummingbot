import { ASTVisitor } from '../../language/visitor';
import { ASTValidationContext } from '../ValidationContext';

export function duplicateFragmentNameMessage(fragName: string): string;

/**
 * Unique fragment names
 *
 * A GraphQL document is only valid if all defined fragments have unique names.
 */
export function UniqueFragmentNames(context: ASTValidationContext): ASTVisitor;
