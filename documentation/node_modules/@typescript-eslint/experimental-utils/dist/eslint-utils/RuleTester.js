"use strict";
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (Object.hasOwnProperty.call(mod, k)) result[k] = mod[k];
    result["default"] = mod;
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
const TSESLint = __importStar(require("../ts-eslint"));
const path = __importStar(require("path"));
const parser = '@typescript-eslint/parser';
class RuleTester extends TSESLint.RuleTester {
    // as of eslint 6 you have to provide an absolute path to the parser
    // but that's not as clean to type, this saves us trying to manually enforce
    // that contributors require.resolve everything
    constructor(options) {
        super(Object.assign(Object.assign({}, options), { parser: require.resolve(options.parser) }));
        this.options = options;
        // make sure that the parser doesn't hold onto file handles between tests
        // on linux (i.e. our CI env), there can be very a limited number of watch handles available
        afterAll(() => {
            try {
                // instead of creating a hard dependency, just use a soft require
                // a bit weird, but if they're using this tooling, it'll be installed
                require(parser).clearCaches();
            }
            catch (_a) {
                // ignored
            }
        });
    }
    getFilename(options) {
        if (options) {
            const filename = `file.ts${options.ecmaFeatures && options.ecmaFeatures.jsx ? 'x' : ''}`;
            if (options.project) {
                return path.join(options.tsconfigRootDir != null
                    ? options.tsconfigRootDir
                    : process.cwd(), filename);
            }
            return filename;
        }
        else if (this.options.parserOptions) {
            return this.getFilename(this.options.parserOptions);
        }
        return 'file.ts';
    }
    // as of eslint 6 you have to provide an absolute path to the parser
    // If you don't do that at the test level, the test will fail somewhat cryptically...
    // This is a lot more explicit
    run(name, rule, tests) {
        const errorMessage = `Do not set the parser at the test level unless you want to use a parser other than ${parser}`;
        // standardize the valid tests as objects
        tests.valid = tests.valid.map(test => {
            if (typeof test === 'string') {
                return {
                    code: test,
                };
            }
            return test;
        });
        tests.valid.forEach(test => {
            if (typeof test !== 'string') {
                if (test.parser === parser) {
                    throw new Error(errorMessage);
                }
                if (!test.filename) {
                    test.filename = this.getFilename(test.parserOptions);
                }
            }
        });
        tests.invalid.forEach(test => {
            if (test.parser === parser) {
                throw new Error(errorMessage);
            }
            if (!test.filename) {
                test.filename = this.getFilename(test.parserOptions);
            }
        });
        super.run(name, rule, tests);
    }
}
exports.RuleTester = RuleTester;
/**
 * Simple no-op tag to mark code samples as "should not format with prettier"
 *   for the internal/plugin-test-formatting lint rule
 */
function noFormat(strings, ...keys) {
    const lastIndex = strings.length - 1;
    return (strings.slice(0, lastIndex).reduce((p, s, i) => p + s + keys[i], '') +
        strings[lastIndex]);
}
exports.noFormat = noFormat;
//# sourceMappingURL=RuleTester.js.map