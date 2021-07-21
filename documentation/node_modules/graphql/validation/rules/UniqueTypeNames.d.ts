import { ASTVisitor } from '../../language/visitor';
import { SDLValidationContext } from '../ValidationContext';

export function duplicateTypeNameMessage(typeName: string): string;

export function existedTypeNameMessage(typeName: string): string;

/**
 * Unique type names
 *
 * A GraphQL document is only valid if all defined types have unique names.
 */
export function UniqueTypeNames(context: SDLValidationContext): ASTVisitor;
