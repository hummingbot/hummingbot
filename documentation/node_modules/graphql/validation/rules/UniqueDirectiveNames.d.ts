import { ASTVisitor } from '../../language/visitor';
import { SDLValidationContext } from '../ValidationContext';

export function duplicateDirectiveNameMessage(directiveName: string): string;

export function existedDirectiveNameMessage(directiveName: string): string;

/**
 * Unique directive names
 *
 * A GraphQL document is only valid if all defined directives have unique names.
 */
export function UniqueDirectiveNames(context: SDLValidationContext): ASTVisitor;
