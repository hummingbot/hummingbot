"use strict";

var _url = _interopRequireDefault(require("url"));

var _accepts = _interopRequireDefault(require("accepts"));

var _httpErrors = _interopRequireDefault(require("http-errors"));

var _graphql = require("graphql");

var _parseBody = require("./parseBody");

var _renderGraphiQL = require("./renderGraphiQL");

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

/**
 * Middleware for express; takes an options object or function as input to
 * configure behavior, and returns an express middleware.
 */
module.exports = graphqlHTTP;

function graphqlHTTP(options) {
  if (!options) {
    throw new Error('GraphQL middleware requires options.');
  }

  return function graphqlMiddleware(request, response) {
    // Higher scoped variables are referred to at various stages in the
    // asynchronous state machine below.
    let context;
    let params;
    let pretty;
    let formatErrorFn = _graphql.formatError;
    let validateFn = _graphql.validate;
    let executeFn = _graphql.execute;
    let parseFn = _graphql.parse;
    let extensionsFn;
    let showGraphiQL = false;
    let query;
    let documentAST;
    let variables;
    let operationName; // Promises are used as a mechanism for capturing any thrown errors during
    // the asynchronous process below.
    // Parse the Request to get GraphQL request parameters.

    return getGraphQLParams(request).then(graphQLParams => {
      params = graphQLParams; // Then, resolve the Options to get OptionsData.

      return resolveOptions(params);
    }, error => {
      // When we failed to parse the GraphQL parameters, we still need to get
      // the options object, so make an options call to resolve just that.
      const dummyParams = {
        query: null,
        variables: null,
        operationName: null,
        raw: null
      };
      return resolveOptions(dummyParams).then(() => Promise.reject(error));
    }).then(optionsData => {
      // Assert that schema is required.
      if (!optionsData.schema) {
        throw new Error('GraphQL middleware options must contain a schema.');
      } // Collect information from the options data object.


      const schema = optionsData.schema;
      const rootValue = optionsData.rootValue;
      const fieldResolver = optionsData.fieldResolver;
      const typeResolver = optionsData.typeResolver;
      const validationRules = optionsData.validationRules || [];
      const graphiql = optionsData.graphiql;
      context = optionsData.context || request; // GraphQL HTTP only supports GET and POST methods.

      if (request.method !== 'GET' && request.method !== 'POST') {
        response.setHeader('Allow', 'GET, POST');
        throw (0, _httpErrors.default)(405, 'GraphQL only supports GET and POST requests.');
      } // Get GraphQL params from the request and POST body data.


      query = params.query;
      variables = params.variables;
      operationName = params.operationName;
      showGraphiQL = canDisplayGraphiQL(request, params) && graphiql; // If there is no query, but GraphiQL will be displayed, do not produce
      // a result, otherwise return a 400: Bad Request.

      if (!query) {
        if (showGraphiQL) {
          return null;
        }

        throw (0, _httpErrors.default)(400, 'Must provide query string.');
      } // Validate Schema


      const schemaValidationErrors = (0, _graphql.validateSchema)(schema);

      if (schemaValidationErrors.length > 0) {
        // Return 500: Internal Server Error if invalid schema.
        response.statusCode = 500;
        return {
          errors: schemaValidationErrors
        };
      } //  GraphQL source.


      const source = new _graphql.Source(query, 'GraphQL request'); // Parse source to AST, reporting any syntax error.

      try {
        documentAST = parseFn(source);
      } catch (syntaxError) {
        // Return 400: Bad Request if any syntax errors errors exist.
        response.statusCode = 400;
        return {
          errors: [syntaxError]
        };
      } // Validate AST, reporting any errors.


      const validationErrors = validateFn(schema, documentAST, [..._graphql.specifiedRules, ...validationRules]);

      if (validationErrors.length > 0) {
        // Return 400: Bad Request if any validation errors exist.
        response.statusCode = 400;
        return {
          errors: validationErrors
        };
      } // Only query operations are allowed on GET requests.


      if (request.method === 'GET') {
        // Determine if this GET request will perform a non-query.
        const operationAST = (0, _graphql.getOperationAST)(documentAST, operationName);

        if (operationAST && operationAST.operation !== 'query') {
          // If GraphiQL can be shown, do not perform this query, but
          // provide it to GraphiQL so that the requester may perform it
          // themselves if desired.
          if (showGraphiQL) {
            return null;
          } // Otherwise, report a 405: Method Not Allowed error.


          response.setHeader('Allow', 'POST');
          throw (0, _httpErrors.default)(405, `Can only perform a ${operationAST.operation} operation from a POST request.`);
        }
      } // Perform the execution, reporting any errors creating the context.


      try {
        return executeFn({
          schema,
          document: documentAST,
          rootValue,
          contextValue: context,
          variableValues: variables,
          operationName,
          fieldResolver,
          typeResolver
        });
      } catch (contextError) {
        // Return 400: Bad Request if any execution context errors exist.
        response.statusCode = 400;
        return {
          errors: [contextError]
        };
      }
    }).then(result => {
      // Collect and apply any metadata extensions if a function was provided.
      // https://graphql.github.io/graphql-spec/#sec-Response-Format
      if (result && extensionsFn) {
        return Promise.resolve(extensionsFn({
          document: documentAST,
          variables,
          operationName,
          result,
          context
        })).then(extensions => {
          if (extensions && typeof extensions === 'object') {
            result.extensions = extensions;
          }

          return result;
        });
      }

      return result;
    }).catch(error => {
      // If an error was caught, report the httpError status, or 500.
      response.statusCode = error.status || 500;
      return {
        errors: [error]
      };
    }).then(result => {
      // If no data was included in the result, that indicates a runtime query
      // error, indicate as such with a generic status code.
      // Note: Information about the error itself will still be contained in
      // the resulting JSON payload.
      // https://graphql.github.io/graphql-spec/#sec-Data
      if (response.statusCode === 200 && result && !result.data) {
        response.statusCode = 500;
      } // Format any encountered errors.


      if (result && result.errors) {
        result.errors = result.errors.map(formatErrorFn);
      } // If allowed to show GraphiQL, present it instead of JSON.


      if (showGraphiQL) {
        const payload = (0, _renderGraphiQL.renderGraphiQL)({
          query,
          variables,
          operationName,
          result,
          options: typeof showGraphiQL !== 'boolean' ? showGraphiQL : {}
        });
        return sendResponse(response, 'text/html', payload);
      } // At this point, result is guaranteed to exist, as the only scenario
      // where it will not is when showGraphiQL is true.


      if (!result) {
        throw (0, _httpErrors.default)(500, 'Internal Error');
      } // If "pretty" JSON isn't requested, and the server provides a
      // response.json method (express), use that directly.
      // Otherwise use the simplified sendResponse method.


      if (!pretty && typeof response.json === 'function') {
        response.json(result);
      } else {
        const payload = JSON.stringify(result, null, pretty ? 2 : 0);
        sendResponse(response, 'application/json', payload);
      }
    });

    async function resolveOptions(requestParams) {
      const optionsResult = typeof options === 'function' ? options(request, response, requestParams) : options;
      const optionsData = await optionsResult; // Assert that optionsData is in fact an Object.

      if (!optionsData || typeof optionsData !== 'object') {
        throw new Error('GraphQL middleware option function must return an options object or a promise which will be resolved to an options object.');
      }

      if (optionsData.formatError) {
        // eslint-disable-next-line no-console
        console.warn('`formatError` is deprecated and replaced by `customFormatErrorFn`. It will be removed in version 1.0.0.');
      }

      validateFn = optionsData.customValidateFn || validateFn;
      executeFn = optionsData.customExecuteFn || executeFn;
      parseFn = optionsData.customParseFn || parseFn;
      formatErrorFn = optionsData.customFormatErrorFn || optionsData.formatError || formatErrorFn;
      extensionsFn = optionsData.extensions;
      pretty = optionsData.pretty;
      return optionsData;
    }
  };
}

/**
 * Provided a "Request" provided by express or connect (typically a node style
 * HTTPClientRequest), Promise the GraphQL request parameters.
 */
module.exports.getGraphQLParams = getGraphQLParams;

async function getGraphQLParams(request) {
  const bodyData = await (0, _parseBody.parseBody)(request);
  const urlData = request.url && _url.default.parse(request.url, true).query || {};
  return parseGraphQLParams(urlData, bodyData);
}
/**
 * Helper function to get the GraphQL params from the request.
 */


function parseGraphQLParams(urlData, bodyData) {
  // GraphQL Query string.
  let query = urlData.query || bodyData.query;

  if (typeof query !== 'string') {
    query = null;
  } // Parse the variables if needed.


  let variables = urlData.variables || bodyData.variables;

  if (variables && typeof variables === 'string') {
    try {
      variables = JSON.parse(variables);
    } catch (error) {
      throw (0, _httpErrors.default)(400, 'Variables are invalid JSON.');
    }
  } else if (typeof variables !== 'object') {
    variables = null;
  } // Name of GraphQL operation to execute.


  let operationName = urlData.operationName || bodyData.operationName;

  if (typeof operationName !== 'string') {
    operationName = null;
  }

  const raw = urlData.raw !== undefined || bodyData.raw !== undefined;
  return {
    query,
    variables,
    operationName,
    raw
  };
}
/**
 * Helper function to determine if GraphiQL can be displayed.
 */


function canDisplayGraphiQL(request, params) {
  // If `raw` exists, GraphiQL mode is not enabled.
  // Allowed to show GraphiQL if not requested as raw and this request
  // prefers HTML over JSON.
  return !params.raw && (0, _accepts.default)(request).types(['json', 'html']) === 'html';
}
/**
 * Helper function for sending a response using only the core Node server APIs.
 */


function sendResponse(response, type, data) {
  const chunk = Buffer.from(data, 'utf8');
  response.setHeader('Content-Type', type + '; charset=utf-8');
  response.setHeader('Content-Length', String(chunk.length));
  response.end(chunk);
}
