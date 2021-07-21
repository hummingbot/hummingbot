import { EnumValueDefinitionNode } from 'graphql/language/ast';
import { Config } from './merge-typedefs';
export declare function mergeEnumValues(first: ReadonlyArray<EnumValueDefinitionNode>, second: ReadonlyArray<EnumValueDefinitionNode>, config: Config): EnumValueDefinitionNode[];
