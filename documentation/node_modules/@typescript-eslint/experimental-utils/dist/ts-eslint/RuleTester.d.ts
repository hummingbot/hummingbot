import { AST_NODE_TYPES, AST_TOKEN_TYPES } from '../ts-estree';
import { ParserOptions } from './ParserOptions';
import { RuleModule } from './Rule';
interface ValidTestCase<TOptions extends Readonly<unknown[]>> {
    code: string;
    options?: TOptions;
    filename?: string;
    parserOptions?: ParserOptions;
    settings?: Record<string, unknown>;
    parser?: string;
    globals?: Record<string, boolean>;
    env?: {
        browser?: boolean;
    };
}
interface SuggestionOutput<TMessageIds extends string> {
    messageId: TMessageIds;
    data?: Record<string, unknown>;
    /**
     * NOTE: Suggestions will be applied as a stand-alone change, without triggering multi-pass fixes.
     * Each individual error has its own suggestion, so you have to show the correct, _isolated_ output for each suggestion.
     */
    output: string;
}
interface InvalidTestCase<TMessageIds extends string, TOptions extends Readonly<unknown[]>> extends ValidTestCase<TOptions> {
    errors: TestCaseError<TMessageIds>[];
    output?: string | null;
}
interface TestCaseError<TMessageIds extends string> {
    messageId: TMessageIds;
    data?: Record<string, unknown>;
    type?: AST_NODE_TYPES | AST_TOKEN_TYPES;
    line?: number;
    column?: number;
    endLine?: number;
    endColumn?: number;
    suggestions?: SuggestionOutput<TMessageIds>[] | null;
}
interface RunTests<TMessageIds extends string, TOptions extends Readonly<unknown[]>> {
    valid: (ValidTestCase<TOptions> | string)[];
    invalid: InvalidTestCase<TMessageIds, TOptions>[];
}
interface RuleTesterConfig {
    parser: string;
    parserOptions?: ParserOptions;
}
declare const RuleTester_base: new (...args: unknown[]) => any;
declare class RuleTester extends RuleTester_base {
    constructor(config?: RuleTesterConfig);
    run<TMessageIds extends string, TOptions extends Readonly<unknown[]>>(name: string, rule: RuleModule<TMessageIds, TOptions>, tests: RunTests<TMessageIds, TOptions>): void;
}
export { InvalidTestCase, SuggestionOutput, RuleTester, RuleTesterConfig, RunTests, TestCaseError, ValidTestCase, };
//# sourceMappingURL=RuleTester.d.ts.map