export declare function composeMessage(...lines: string[]): string;
declare const ConfigNotFoundError_base: ErrorConstructor;
export declare class ConfigNotFoundError extends ConfigNotFoundError_base {
    constructor(message: string);
}
declare const ConfigEmptyError_base: ErrorConstructor;
export declare class ConfigEmptyError extends ConfigEmptyError_base {
    constructor(message: string);
}
declare const ConfigInvalidError_base: ErrorConstructor;
export declare class ConfigInvalidError extends ConfigInvalidError_base {
    constructor(message: string);
}
declare const ProjectNotFoundError_base: ErrorConstructor;
export declare class ProjectNotFoundError extends ProjectNotFoundError_base {
    constructor(message: string);
}
declare const LoadersMissingError_base: ErrorConstructor;
export declare class LoadersMissingError extends LoadersMissingError_base {
    constructor(message: string);
}
declare const LoaderNoResultError_base: ErrorConstructor;
export declare class LoaderNoResultError extends LoaderNoResultError_base {
    constructor(message: string);
}
declare const ExtensionMissingError_base: ErrorConstructor;
export declare class ExtensionMissingError extends ExtensionMissingError_base {
    constructor(message: string);
}
export {};
//# sourceMappingURL=errors.d.ts.map