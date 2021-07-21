import { ASTVisitor } from '../../language/visitor';
import { SDLValidationContext } from '../ValidationContext';

export function schemaDefinitionNotAloneMessage(): string;

export function canNotDefineSchemaWithinExtensionMessage(): string;

/**
 * Lone Schema definition
 *
 * A GraphQL document is only valid if it contains only one schema definition.
 */
export function LoneSchemaDefinition(context: SDLValidationContext): ASTVisitor;
