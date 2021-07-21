import { GraphQLConfigResult } from '../types';
export declare function findConfig({ rootDir, legacy, configName, }: {
    rootDir: string;
    configName: string;
    legacy?: boolean;
}): Promise<GraphQLConfigResult>;
export declare function findConfigSync({ rootDir, legacy, configName, }: {
    rootDir: string;
    configName: string;
    legacy?: boolean;
}): GraphQLConfigResult;
//# sourceMappingURL=find-config.d.ts.map