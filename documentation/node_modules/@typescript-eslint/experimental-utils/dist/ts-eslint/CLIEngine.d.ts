import { Linter } from './Linter';
import { RuleMetaData, RuleModule, RuleListener } from './Rule';
interface CLIEngine {
    executeOnFiles(patterns: string[]): CLIEngine.LintReport;
    resolveFileGlobPatterns(patterns: string[]): string[];
    getConfigForFile(filePath: string): Linter.Config;
    executeOnText(text: string, filename?: string): CLIEngine.LintReport;
    addPlugin(name: string, pluginObject: unknown): void;
    isPathIgnored(filePath: string): boolean;
    getFormatter(format?: string): CLIEngine.Formatter;
    getRules<TMessageIds extends string = string, TOptions extends readonly unknown[] = unknown[], TRuleListener extends RuleListener = RuleListener>(): Map<string, RuleModule<TMessageIds, TOptions, TRuleListener>>;
}
declare namespace CLIEngine {
    interface Options {
        allowInlineConfig?: boolean;
        baseConfig?: false | {
            [name: string]: unknown;
        };
        cache?: boolean;
        cacheFile?: string;
        cacheLocation?: string;
        configFile?: string;
        cwd?: string;
        envs?: string[];
        errorOnUnmatchedPattern?: boolean;
        extensions?: string[];
        fix?: boolean;
        globals?: string[];
        ignore?: boolean;
        ignorePath?: string;
        ignorePattern?: string | string[];
        useEslintrc?: boolean;
        parser?: string;
        parserOptions?: Linter.ParserOptions;
        plugins?: string[];
        resolvePluginsRelativeTo?: string;
        rules?: {
            [name: string]: Linter.RuleLevel | Linter.RuleLevelAndOptions;
        };
        rulePaths?: string[];
        reportUnusedDisableDirectives?: boolean;
    }
    interface LintResult {
        filePath: string;
        messages: Linter.LintMessage[];
        errorCount: number;
        warningCount: number;
        fixableErrorCount: number;
        fixableWarningCount: number;
        output?: string;
        source?: string;
    }
    interface LintReport {
        results: LintResult[];
        errorCount: number;
        warningCount: number;
        fixableErrorCount: number;
        fixableWarningCount: number;
        usedDeprecatedRules: DeprecatedRuleUse[];
    }
    interface DeprecatedRuleUse {
        ruleId: string;
        replacedBy: string[];
    }
    interface LintResultData<TMessageIds extends string> {
        rulesMeta: {
            [ruleId: string]: RuleMetaData<TMessageIds>;
        };
    }
    type Formatter = <TMessageIds extends string>(results: LintResult[], data?: LintResultData<TMessageIds>) => string;
}
declare const CLIEngine: {
    new (options: CLIEngine.Options): CLIEngine;
    getErrorResults(results: CLIEngine.LintResult[]): CLIEngine.LintResult[];
    getFormatter(format?: string | undefined): CLIEngine.Formatter;
    outputFixes(report: CLIEngine.LintReport): void;
    version: string;
};
export { CLIEngine };
//# sourceMappingURL=CLIEngine.d.ts.map