"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const ERROR_MESSAGE = 'You have used a rule which requires parserServices to be generated. You must therefore provide a value for the "parserOptions.project" property for @typescript-eslint/parser.';
/**
 * Try to retrieve typescript parser service from context
 */
function getParserServices(context) {
    if (!context.parserServices ||
        !context.parserServices.program ||
        !context.parserServices.esTreeNodeToTSNodeMap) {
        /**
         * The user needs to have configured "project" in their parserOptions
         * for @typescript-eslint/parser
         */
        throw new Error(ERROR_MESSAGE);
    }
    return context.parserServices;
}
exports.getParserServices = getParserServices;
//# sourceMappingURL=getParserServices.js.map