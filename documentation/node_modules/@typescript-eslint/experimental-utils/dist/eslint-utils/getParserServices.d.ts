import * as TSESLint from '../ts-eslint';
import { ParserServices } from '../ts-estree';
declare type RequiredParserServices = {
    [k in keyof ParserServices]: Exclude<ParserServices[k], undefined>;
};
/**
 * Try to retrieve typescript parser service from context
 */
declare function getParserServices<TMessageIds extends string, TOptions extends unknown[]>(context: TSESLint.RuleContext<TMessageIds, TOptions>): RequiredParserServices;
export { getParserServices };
//# sourceMappingURL=getParserServices.d.ts.map