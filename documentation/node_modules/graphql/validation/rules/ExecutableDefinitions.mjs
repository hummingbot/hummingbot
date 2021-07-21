import { GraphQLError } from '../../error/GraphQLError';
import { Kind } from '../../language/kinds';
import { isExecutableDefinitionNode } from '../../language/predicates';
export function nonExecutableDefinitionMessage(defName) {
  return "The ".concat(defName, " definition is not executable.");
}
/**
 * Executable definitions
 *
 * A GraphQL document is only valid for execution if all definitions are either
 * operation or fragment definitions.
 */

export function ExecutableDefinitions(context) {
  return {
    Document: function Document(node) {
      for (var _i2 = 0, _node$definitions2 = node.definitions; _i2 < _node$definitions2.length; _i2++) {
        var definition = _node$definitions2[_i2];

        if (!isExecutableDefinitionNode(definition)) {
          context.reportError(new GraphQLError(nonExecutableDefinitionMessage(definition.kind === Kind.SCHEMA_DEFINITION || definition.kind === Kind.SCHEMA_EXTENSION ? 'schema' : definition.name.value), definition));
        }
      }

      return false;
    }
  };
}
