import { TSESTree, ParserServices } from '../ts-estree';
import { ParserOptions as TSParserOptions } from './ParserOptions';
import { RuleModule, RuleFix } from './Rule';
import { Scope } from './Scope';
import { SourceCode } from './SourceCode';
interface Linter {
    version: string;
    verify(code: SourceCode | string, config: Linter.Config, filename?: string): Linter.LintMessage[];
    verify(code: SourceCode | string, config: Linter.Config, options: Linter.LintOptions): Linter.LintMessage[];
    verifyAndFix(code: string, config: Linter.Config, filename?: string): Linter.FixReport;
    verifyAndFix(code: string, config: Linter.Config, options: Linter.FixOptions): Linter.FixReport;
    getSourceCode(): SourceCode;
    defineRule<TMessageIds extends string, TOptions extends readonly unknown[]>(name: string, rule: {
        meta?: RuleModule<TMessageIds, TOptions>['meta'];
        create: RuleModule<TMessageIds, TOptions>['create'];
    }): void;
    defineRules<TMessageIds extends string, TOptions extends readonly unknown[]>(rules: Record<string, RuleModule<TMessageIds, TOptions>>): void;
    getRules<TMessageIds extends string, TOptions extends readonly unknown[]>(): Map<string, RuleModule<TMessageIds, TOptions>>;
    defineParser(name: string, parser: Linter.ParserModule): void;
}
declare namespace Linter {
    export type Severity = 0 | 1 | 2;
    export type RuleLevel = Severity | 'off' | 'warn' | 'error';
    export type RuleLevelAndOptions = [RuleLevel, ...unknown[]];
    export type RuleEntry = RuleLevel | RuleLevelAndOptions;
    export type RulesRecord = Partial<Record<string, RuleEntry>>;
    interface BaseConfig {
        $schema?: string;
        env?: {
            [name: string]: boolean;
        };
        extends?: string | string[];
        globals?: {
            [name: string]: boolean;
        };
        noInlineConfig?: boolean;
        overrides?: ConfigOverride[];
        parser?: string;
        parserOptions?: ParserOptions;
        plugins?: string[];
        processor?: string;
        reportUnusedDisableDirectives?: boolean;
        settings?: {
            [name: string]: unknown;
        };
        rules?: RulesRecord;
    }
    export interface ConfigOverride extends BaseConfig {
        excludedFiles?: string | string[];
        files: string | string[];
    }
    export type RuleOverride = ConfigOverride;
    export interface Config extends BaseConfig {
        ignorePatterns?: string | string[];
        root?: boolean;
    }
    export type ParserOptions = TSParserOptions;
    export interface LintOptions {
        filename?: string;
        preprocess?: (code: string) => string[];
        postprocess?: (problemLists: LintMessage[][]) => LintMessage[];
        allowInlineConfig?: boolean;
        reportUnusedDisableDirectives?: boolean;
    }
    export interface LintSuggestion {
        desc: string;
        fix: RuleFix;
        messageId?: string;
    }
    export interface LintMessage {
        column: number;
        line: number;
        endColumn?: number;
        endLine?: number;
        ruleId: string | null;
        message: string;
        messageId?: string;
        nodeType: string;
        fatal?: true;
        severity: Severity;
        fix?: RuleFix;
        source: string | null;
        suggestions?: LintSuggestion[];
    }
    export interface FixOptions extends LintOptions {
        fix?: boolean;
    }
    export interface FixReport {
        fixed: boolean;
        output: string;
        messages: LintMessage[];
    }
    export type ParserModule = {
        parse(text: string, options?: unknown): TSESTree.Program;
    } | {
        parseForESLint(text: string, options?: unknown): ESLintParseResult;
    };
    export interface ESLintParseResult {
        ast: TSESTree.Program;
        parserServices?: ParserServices;
        scopeManager?: Scope.ScopeManager;
        visitorKeys?: SourceCode.VisitorKeys;
    }
    export {};
}
declare const Linter: new () => Linter;
export { Linter };
//# sourceMappingURL=Linter.d.ts.map