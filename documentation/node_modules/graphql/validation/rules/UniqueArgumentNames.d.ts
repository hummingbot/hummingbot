import { ASTVisitor } from '../../language/visitor';
import { ASTValidationContext } from '../ValidationContext';

export function duplicateArgMessage(argName: string): string;

/**
 * Unique argument names
 *
 * A GraphQL field or directive is only valid if all supplied arguments are
 * uniquely named.
 */
export function UniqueArgumentNames(context: ASTValidationContext): ASTVisitor;
