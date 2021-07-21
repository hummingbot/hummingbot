import { LoadersRegistry } from './loaders';
export declare type GraphQLExtensionDeclaration = (api: ExtensionAPI) => GraphQLConfigExtension;
export interface ExtensionAPI {
    logger: any;
    loaders: {
        schema: Pick<LoadersRegistry, 'register' | 'use'>;
        documents: Pick<LoadersRegistry, 'register'>;
    };
}
export interface GraphQLConfigExtension {
    name: string;
}
export declare class GraphQLExtensionsRegistry {
    private readonly _extensions;
    readonly loaders: {
        schema: LoadersRegistry;
        documents: LoadersRegistry;
    };
    constructor({ cwd }: {
        cwd: string;
    });
    register(extensionFn: GraphQLExtensionDeclaration): void;
    has(extensionName: string): boolean;
    get(extensionName: string): GraphQLConfigExtension;
    names(): string[];
    forEach(cb: (extension: GraphQLConfigExtension) => void): void;
}
//# sourceMappingURL=extension.d.ts.map