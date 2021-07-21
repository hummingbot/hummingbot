import * as ts from 'typescript';
import { Extra } from '../parser-options';
interface ASTAndProgram {
    ast: ts.SourceFile;
    program: ts.Program | undefined;
}
declare function createDefaultCompilerOptionsFromExtra(extra: Extra): ts.CompilerOptions;
declare type CanonicalPath = string & {
    __brand: unknown;
};
declare function getCanonicalFileName(filePath: string): CanonicalPath;
declare function ensureAbsolutePath(p: string, extra: Extra): string;
declare function getTsconfigPath(tsconfigPath: string, extra: Extra): CanonicalPath;
declare function canonicalDirname(p: CanonicalPath): CanonicalPath;
declare function getScriptKind(extra: Extra, filePath?: string): ts.ScriptKind;
export { ASTAndProgram, canonicalDirname, CanonicalPath, createDefaultCompilerOptionsFromExtra, ensureAbsolutePath, getCanonicalFileName, getScriptKind, getTsconfigPath, };
//# sourceMappingURL=shared.d.ts.map