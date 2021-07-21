Bublé version <%= version %>
=====================================

Usage: buble [options] <entry file>

Basic options:

-v, --version            Show version number
-h, --help               Show this help message
-i, --input              Input (alternative to <entry file>)
-o, --output <output>    Output (if absent, prints to stdout)
-m, --sourcemap          Generate sourcemap (`-m inline` for inline map)
-t, --target             Select compilation targets
-y, --yes                Transforms to always apply (overrides --target)
-n, --no                 Transforms to always skip (overrides --target)
--jsx                    Custom JSX pragma
--objectAssign           Specify Object.assign or equivalent polyfill
--no-named-function-expr Don't output named function expressions

Examples:

# Compile input.js to output.js
buble input.js > output.js

# Compile input.js to output.js, write sourcemap to output.js.map
buble input.js -o output.js -m

# Compile input.js to output.js with inline sourcemap
buble input.js -o output.js -m inline

# Only use transforms necessary for output.js to run in FF43 and Node 5
buble input.js -o output.js -t firefox:43,node:5

# As above, but use arrow function and destructuring transforms
buble input.js -o output.js -t firefox:43,node:5 -y arrow,destructuring

# Compile all the files in src/ to dest/
buble src -o dest

Notes:

* When piping to stdout, only inline sourcemaps are permitted

For more information visit http://buble.surge.sh/guide
