import { DocumentNode } from 'graphql';
export declare function processImport(filePath: string, cwd?: string, predefinedImports?: Record<string, string>): DocumentNode;
export declare function parseImportLine(importLine: string): {
    imports: string[];
    from: string;
};
