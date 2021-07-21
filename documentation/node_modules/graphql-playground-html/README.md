# graphql-playground-html

> **SECURITY WARNING:** This package and all of it's dependendents had a severe XSS Reflection attack vulnerability until version `1.6.22` of this package. You must sanitize any and all user input values to `renderPlaygroundPage()` values. If you used static values in your middlewares, including ours, you were not vulnerable to the attack.

This package is being used by the GraphQL Playground middlewares.

For local development, you can `yarn link` this package, then use `yarn link graphql-playground-html` in the
middleware you want to develop.
