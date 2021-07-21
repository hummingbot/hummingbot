// TypeScript Version: 3.0

import { IncomingMessage, ServerResponse } from 'http';
import {
  Source,
  ASTVisitor,
  DocumentNode,
  ValidationContext,
  ExecutionArgs,
  ExecutionResult,
  GraphQLError,
  GraphQLSchema,
  GraphQLFieldResolver,
  GraphQLTypeResolver,
} from 'graphql';

// TODO: Temporary until we update TS typings for 'graphql' package
import { ValidationRule } from 'graphql/validation/ValidationContext';

export = graphqlHTTP;

type Request = IncomingMessage;
type Response = ServerResponse;

declare namespace graphqlHTTP {
  /**
   * Used to configure the graphqlHTTP middleware by providing a schema
   * and other configuration options.
   *
   * Options can be provided as an Object, a Promise for an Object, or a Function
   * that returns an Object or a Promise for an Object.
   */
  type Options =
    | ((
        request: Request,
        response: Response,
        params?: GraphQLParams,
      ) => OptionsResult)
    | OptionsResult;
  type OptionsResult = OptionsData | Promise<OptionsData>;

  interface OptionsData {
    /**
     * A GraphQL schema from graphql-js.
     */
    schema: GraphQLSchema;

    /**
     * A value to pass as the context to the graphql() function.
     */
    context?: unknown;

    /**
     * An object to pass as the rootValue to the graphql() function.
     */
    rootValue?: unknown;

    /**
     * A boolean to configure whether the output should be pretty-printed.
     */
    pretty?: boolean | null;

    /**
     * An optional array of validation rules that will be applied on the document
     * in additional to those defined by the GraphQL spec.
     */
    validationRules?: ReadonlyArray<
      (ctx: ValidationContext) => ASTVisitor
    > | null;

    /**
     * An optional function which will be used to validate instead of default `validate`
     * from `graphql-js`.
     */
    customValidateFn?:
      | ((
          schema: GraphQLSchema,
          documentAST: DocumentNode,
          rules: ReadonlyArray<ValidationRule>,
        ) => ReadonlyArray<GraphQLError>)
      | null;

    /**
     * An optional function which will be used to execute instead of default `execute`
     * from `graphql-js`.
     */
    customExecuteFn?:
      | ((args: ExecutionArgs) => Promise<ExecutionResult>)
      | null;

    /**
     * An optional function which will be used to format any errors produced by
     * fulfilling a GraphQL operation. If no function is provided, GraphQL's
     * default spec-compliant `formatError` function will be used.
     */
    customFormatErrorFn?: ((error: GraphQLError) => unknown) | null;

    /**
     * An optional function which will be used to create a document instead of
     * the default `parse` from `graphql-js`.
     */
    customParseFn?: (source: Source) => DocumentNode | null;

    /**
     * `formatError` is deprecated and replaced by `customFormatErrorFn`. It will
     *  be removed in version 1.0.0.
     */
    formatError?: ((error: GraphQLError) => unknown) | null;

    /**
     * An optional function for adding additional metadata to the GraphQL response
     * as a key-value object. The result will be added to "extensions" field in
     * the resulting JSON. This is often a useful place to add development time
     * info such as the runtime of a query or the amount of resources consumed.
     *
     * Information about the request is provided to be used.
     *
     * This function may be async.
     */
    extensions?: ((info: RequestInfo) => { [key: string]: unknown }) | null;

    /**
     * A boolean to optionally enable GraphiQL mode.
     */
    graphiql?: boolean | null;

    /**
     * A resolver function to use when one is not provided by the schema.
     * If not provided, the default field resolver is used (which looks for a
     * value or method on the source value with the field's name).
     */
    fieldResolver?: GraphQLFieldResolver<unknown, unknown> | null;

    /**
     * A type resolver function to use when none is provided by the schema.
     * If not provided, the default type resolver is used (which looks for a
     * `__typename` field or alternatively calls the `isTypeOf` method).
     */
    typeResolver?: GraphQLTypeResolver<unknown, unknown> | null;
  }

  /**
   * All information about a GraphQL request.
   */
  interface RequestInfo {
    /**
     * The parsed GraphQL document.
     */
    document: DocumentNode | null | undefined;

    /**
     * The variable values used at runtime.
     */
    variables: { readonly [name: string]: unknown } | null | undefined;

    /**
     * The (optional) operation name requested.
     */
    operationName: string | null | undefined;

    /**
     * The result of executing the operation.
     */
    result: unknown;

    /**
     * A value to pass as the context to the graphql() function.
     */
    context?: unknown;
  }

  type Middleware = (
    request: Request,
    response: Response,
  ) => Promise<undefined>;

  interface GraphQLParams {
    query: string | null | undefined;
    variables: { readonly [name: string]: unknown } | null | undefined;
    operationName: string | null | undefined;
    raw: boolean | null | undefined;
  }
}

/**
 * Middleware for express; takes an options object or function as input to
 * configure behavior, and returns an express middleware.
 */
declare function graphqlHTTP(
  options: graphqlHTTP.Options,
): graphqlHTTP.Middleware;
