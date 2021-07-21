import { TSESTreeOptions } from '@typescript-eslint/typescript-estree';
declare type EcmaVersion = 3 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020;
interface ParserOptions {
    comment?: boolean;
    ecmaFeatures?: {
        globalReturn?: boolean;
        jsx?: boolean;
    };
    ecmaVersion?: EcmaVersion;
    errorOnTypeScriptSyntacticAndSemanticIssues?: boolean;
    errorOnUnknownASTType?: boolean;
    extraFileExtensions?: string[];
    debugLevel?: TSESTreeOptions['debugLevel'];
    filePath?: string;
    loc?: boolean;
    noWatch?: boolean;
    project?: string | string[];
    projectFolderIgnoreList?: (string | RegExp)[];
    range?: boolean;
    sourceType?: 'script' | 'module';
    tokens?: boolean;
    tsconfigRootDir?: string;
    useJSXTextNode?: boolean;
    warnOnUnsupportedTypeScriptVersion?: boolean;
}
export { EcmaVersion, ParserOptions };
//# sourceMappingURL=ParserOptions.d.ts.map