"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
/**
 * This is a compatibility ruleset that disables rules from eslint:recommended
 * which are already handled by TypeScript.
 */
exports.default = {
    overrides: [
        {
            files: ['*.ts', '*.tsx'],
            rules: {
                // Checked by Typescript - ts(2378)
                'getter-return': 'off',
                // Checked by Typescript - ts(2300)
                'no-dupe-args': 'off',
                // Checked by Typescript - ts(1117)
                'no-dupe-keys': 'off',
                // Checked by Typescript - ts(7027)
                'no-unreachable': 'off',
                // Checked by Typescript - ts(2367)
                'valid-typeof': 'off',
                // Checked by Typescript - ts(2588)
                'no-const-assign': 'off',
                // Checked by Typescript - ts(2588)
                'no-new-symbol': 'off',
                // Checked by Typescript - ts(2376)
                'no-this-before-super': 'off',
                // This is checked by Typescript using the option `strictNullChecks`.
                'no-undef': 'off',
                // This is already checked by Typescript.
                'no-dupe-class-members': 'off',
                // This is already checked by Typescript.
                'no-redeclare': 'off',
            },
        },
    ],
};
//# sourceMappingURL=eslint-recommended.js.map