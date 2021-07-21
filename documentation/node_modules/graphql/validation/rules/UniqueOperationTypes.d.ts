import { ASTVisitor } from '../../language/visitor';
import { SDLValidationContext } from '../ValidationContext';

export function duplicateOperationTypeMessage(operation: string): string;

export function existedOperationTypeMessage(operation: string): string;

/**
 * Unique operation types
 *
 * A GraphQL document is only valid if it has only one type per operation.
 */
export function UniqueOperationTypes(context: SDLValidationContext): ASTVisitor;
