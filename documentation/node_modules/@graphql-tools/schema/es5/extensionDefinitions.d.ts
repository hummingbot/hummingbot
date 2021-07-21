import { DocumentNode, DefinitionNode } from 'graphql';
export declare function extractExtensionDefinitions(ast: DocumentNode): {
    definitions: DefinitionNode[];
    kind: "Document";
    loc?: import("graphql").Location;
};
export declare function filterExtensionDefinitions(ast: DocumentNode): {
    definitions: DefinitionNode[];
    kind: "Document";
    loc?: import("graphql").Location;
};
