import { EcmaVersion } from '../ts-eslint';
import { ScopeManager } from './ScopeManager';
interface AnalysisOptions {
    optimistic?: boolean;
    directive?: boolean;
    ignoreEval?: boolean;
    nodejsScope?: boolean;
    impliedStrict?: boolean;
    fallback?: string | ((node: {}) => string[]);
    sourceType?: 'script' | 'module';
    ecmaVersion?: EcmaVersion;
}
declare const analyze: (ast: {}, options?: AnalysisOptions | undefined) => ScopeManager;
export { analyze, AnalysisOptions };
//# sourceMappingURL=analyze.d.ts.map