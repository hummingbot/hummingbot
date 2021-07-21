"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;

var _helperPluginUtils = require("@babel/helper-plugin-utils");

var _helperSkipTransparentExpressionWrappers = require("@babel/helper-skip-transparent-expression-wrappers");

var _pluginSyntaxOptionalChaining = _interopRequireDefault(require("@babel/plugin-syntax-optional-chaining"));

var _core = require("@babel/core");

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

var _default = (0, _helperPluginUtils.declare)((api, options) => {
  api.assertVersion(7);
  const {
    loose = false
  } = options;

  function isSimpleMemberExpression(expression) {
    expression = (0, _helperSkipTransparentExpressionWrappers.skipTransparentExprWrappers)(expression);
    return _core.types.isIdentifier(expression) || _core.types.isSuper(expression) || _core.types.isMemberExpression(expression) && !expression.computed && isSimpleMemberExpression(expression.object);
  }

  function needsMemoize(path) {
    let optionalPath = path;
    const {
      scope
    } = path;

    while (optionalPath.isOptionalMemberExpression() || optionalPath.isOptionalCallExpression()) {
      const {
        node
      } = optionalPath;
      const childKey = optionalPath.isOptionalMemberExpression() ? "object" : "callee";
      const childPath = (0, _helperSkipTransparentExpressionWrappers.skipTransparentExprWrappers)(optionalPath.get(childKey));

      if (node.optional) {
        return !scope.isStatic(childPath.node);
      }

      optionalPath = childPath;
    }
  }

  return {
    name: "proposal-optional-chaining",
    inherits: _pluginSyntaxOptionalChaining.default,
    visitor: {
      "OptionalCallExpression|OptionalMemberExpression"(path) {
        const {
          scope
        } = path;
        let maybeWrapped = path;
        const parentPath = path.findParent(p => {
          if (!(0, _helperSkipTransparentExpressionWrappers.isTransparentExprWrapper)(p)) return true;
          maybeWrapped = p;
        });
        let isDeleteOperation = false;
        const parentIsCall = parentPath.isCallExpression({
          callee: maybeWrapped.node
        }) && path.isOptionalMemberExpression();
        const optionals = [];
        let optionalPath = path;

        if (scope.path.isPattern() && needsMemoize(optionalPath)) {
          path.replaceWith(_core.template.ast`(() => ${path.node})()`);
          return;
        }

        while (optionalPath.isOptionalMemberExpression() || optionalPath.isOptionalCallExpression()) {
          const {
            node
          } = optionalPath;

          if (node.optional) {
            optionals.push(node);
          }

          if (optionalPath.isOptionalMemberExpression()) {
            optionalPath.node.type = "MemberExpression";
            optionalPath = (0, _helperSkipTransparentExpressionWrappers.skipTransparentExprWrappers)(optionalPath.get("object"));
          } else if (optionalPath.isOptionalCallExpression()) {
            optionalPath.node.type = "CallExpression";
            optionalPath = (0, _helperSkipTransparentExpressionWrappers.skipTransparentExprWrappers)(optionalPath.get("callee"));
          }
        }

        let replacementPath = path;

        if (parentPath.isUnaryExpression({
          operator: "delete"
        })) {
          replacementPath = parentPath;
          isDeleteOperation = true;
        }

        for (let i = optionals.length - 1; i >= 0; i--) {
          const node = optionals[i];

          const isCall = _core.types.isCallExpression(node);

          const replaceKey = isCall ? "callee" : "object";
          const chainWithTypes = node[replaceKey];
          let chain = chainWithTypes;

          while ((0, _helperSkipTransparentExpressionWrappers.isTransparentExprWrapper)(chain)) {
            chain = chain.expression;
          }

          let ref;
          let check;

          if (isCall && _core.types.isIdentifier(chain, {
            name: "eval"
          })) {
            check = ref = chain;
            node[replaceKey] = _core.types.sequenceExpression([_core.types.numericLiteral(0), ref]);
          } else if (loose && isCall && isSimpleMemberExpression(chain)) {
            check = ref = chainWithTypes;
          } else {
            ref = scope.maybeGenerateMemoised(chain);

            if (ref) {
              check = _core.types.assignmentExpression("=", _core.types.cloneNode(ref), chainWithTypes);
              node[replaceKey] = ref;
            } else {
              check = ref = chainWithTypes;
            }
          }

          if (isCall && _core.types.isMemberExpression(chain)) {
            if (loose && isSimpleMemberExpression(chain)) {
              node.callee = chainWithTypes;
            } else {
              const {
                object
              } = chain;
              let context = scope.maybeGenerateMemoised(object);

              if (context) {
                chain.object = _core.types.assignmentExpression("=", context, object);
              } else if (_core.types.isSuper(object)) {
                context = _core.types.thisExpression();
              } else {
                context = object;
              }

              node.arguments.unshift(_core.types.cloneNode(context));
              node.callee = _core.types.memberExpression(node.callee, _core.types.identifier("call"));
            }
          }

          let replacement = replacementPath.node;

          if (i === 0 && parentIsCall) {
            var _baseRef;

            const object = (0, _helperSkipTransparentExpressionWrappers.skipTransparentExprWrappers)(replacementPath.get("object")).node;
            let baseRef;

            if (!loose || !isSimpleMemberExpression(object)) {
              baseRef = scope.maybeGenerateMemoised(object);

              if (baseRef) {
                replacement.object = _core.types.assignmentExpression("=", baseRef, object);
              }
            }

            replacement = _core.types.callExpression(_core.types.memberExpression(replacement, _core.types.identifier("bind")), [_core.types.cloneNode((_baseRef = baseRef) != null ? _baseRef : object)]);
          }

          replacementPath.replaceWith(_core.types.conditionalExpression(loose ? _core.types.binaryExpression("==", _core.types.cloneNode(check), _core.types.nullLiteral()) : _core.types.logicalExpression("||", _core.types.binaryExpression("===", _core.types.cloneNode(check), _core.types.nullLiteral()), _core.types.binaryExpression("===", _core.types.cloneNode(ref), scope.buildUndefinedNode())), isDeleteOperation ? _core.types.booleanLiteral(true) : scope.buildUndefinedNode(), replacement));
          replacementPath = (0, _helperSkipTransparentExpressionWrappers.skipTransparentExprWrappers)(replacementPath.get("alternate"));
        }
      }

    }
  };
});

exports.default = _default;