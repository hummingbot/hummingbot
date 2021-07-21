import { ASTVisitor } from '../../language/visitor';
import { ValidationContext } from '../ValidationContext';

export function unknownFragmentMessage(fragName: string): string;

/**
 * Known fragment names
 *
 * A GraphQL document is only valid if all `...Fragment` fragment spreads refer
 * to fragments defined in the same document.
 */
export function KnownFragmentNames(context: ValidationContext): ASTVisitor;
