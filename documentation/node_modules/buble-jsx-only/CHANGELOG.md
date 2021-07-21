# buble changelog

## 0.19.8 (2019-07-03)

* Allow shebang ([#191](https://github.com/bublejs/buble/pull/191))
* Fix tagged template literal in certain cases ([#190](https://github.com/bublejs/buble/issues/190))
* Fix removing of trailing commas in certain cases ([#194](https://github.com/bublejs/buble/pull/194))
* Make JSX Fragment configurable ([#198](https://github.com/bublejs/buble/issues/198))
* Fix transpiling string-keyed properties with whitespaces before colons ([#200](https://github.com/bublejs/buble/pull/200))

## 0.19.7 (2019-03-11)

* Throw error on dynamic import expression if transform is not disabled
* Throw error on async and await if transform is not disabled
* Allow await outside of functions
* Don't bundle acorn dependencies ([#165](https://github.com/bublejs/buble/pull/165))
* Inline spread elements where possible ([#179](https://github.com/bublejs/buble/pull/179))
* Correctly handle operator precedence for array spread ([#177](https://github.com/bublejs/buble/issues/177))
* Correctly pass-through async arrow functions and methods ([#109](https://github.com/bublejs/buble/issues/109), [#146](https://github.com/bublejs/buble/issues/146))
* Move repository to https://github.com/bublejs/buble
* Exclude non-string keys from rest properties ([#149](https://github.com/bublejs/buble/issues/149))

## 0.19.6 (2018-10-23)

* Fix class expressions with heritage in arrow functions ([#150](https://github.com/bublejs/buble/issues/150))
* Support `objectAssign: true` in API as a short-hand for `objectAssign: "Object.assign"`
* Bundle all acorn dependencies (for now), but no others ([#159](https://github.com/bublejs/buble/issues/159))

## 0.19.5 (2018-10-16)

* Transpile U+2028 and U+2029 according to stage 4 proposal json-superset
* Add `/*@__PURE__*/` annotations to transpiled classes
* Update support data
* Allow disabling spread properties transpiling
* Fix specific edge case with spread and computed properties ([#139](https://github.com/bublejs/buble/issues/139))
* Allow global `return` statements
* Don't create unnecessary `this` aliases with loops ([#120](https://github.com/bublejs/buble/issues/120))
* Don't allow getters and setters if IE8 is transpile target ([#20](https://github.com/bublejs/buble/issues/20))

## 0.19.4 (2018-10-06)

* Fix transpiling destructuring assignments in brace-less if statement's bodies ([#152](https://github.com/bublejs/buble/issues/152))
* Fix transpiling const and let after brace-less if statements ([#132](https://github.com/bublejs/buble/issues/132))
* Transpile binary and octal number literals if base prefix is upper-case ([#74](https://github.com/bublejs/buble/issues/74))
* Mark classes as supported in Chrome 48
* Mark destructuring of arrow function arguments as not supported in Firefox < 52

## 0.19.3 (2018-02-13)

* Make sure browser builds are actually valid ES5 (except for the modules build)

## 0.19.2 (2018-02-12)

* Correctly specify browser field in package.json ([#107](https://github.com/bublejs/buble/issues/107))
* Fix a compile error about using `super` outside of class methods
* Fix transpiling rest properties

## 0.19.1 (2018-02-10)

* Fix transpiling let and const if arrow functions are not transpiled (i. e. node: 4)

## 0.19.0 (2018-02-10)

### Enhancements

* Add support information for new environments
* Add (pass-thru) support for aync generators and for-async-of
* Add support for dynamic import ([#102](https://github.com/bublejs/buble/pull/102))
* Add support for JSX fragments ([#62](https://github.com/bublejs/buble/issues/62))
* Add unpkg build and transpile browser build for older environments ([#93](https://github.com/bublejs/buble/issues/93))
* Reuse tagged template quasis ([#67](https://github.com/bublejs/buble/pull/67))
* Transpile trailing commas in new expressions ([#63](https://github.com/bublejs/buble/issues/63))
* Add support for destructuring in for-in and for-of loop heads
* Add support for destructuring in catch clause params
* Add support for rest properties in assignments

### Fixes

* Don't remove commas in comments after the last argument ([#89](https://github.com/bublejs/buble/issues/89))
* Support transformations involving aliasing of variables in block scopes ([#60](https://github.com/bublejs/buble/issues/60))
* Evaluate expression only once with inline default pattern elements
* Fix nested object and array patterns, rest properties and default values in for loop heads
* Only put own properties in rest properties
* Improve declaration of helper variables
* Allow modification of mutable variables that shadow a const before declaration ([#59](https://github.com/bublejs/buble/issues/59))
* Correctly detect modification of immutable variables through destructuring assignments
* In object methods, support destructuring declarations initialized with a variable having the same name as the method ([#86](https://github.com/bublejs/buble/issues/86))
* Fix properties with string literal keys after computed properties ([#91](https://github.com/bublejs/buble/pull/91))
* Fix methods after computed properties ([#101](https://github.com/bublejs/buble/issues/101))
* Fix short-hand generator methods
* Fix template literals in array after spread element ([#105](https://github.com/bublejs/buble/issues/105))
* Fix arrow functions in array after spread element ([#100](https://github.com/bublejs/buble/issues/100))
* Fix arrow functions in new expression after spread element ([#100](https://github.com/bublejs/buble/issues/100))
* Restore decoding HTML entities in JSX ([#104](https://github.com/bublejs/buble/issues/104))
* Correct various entries in support matrix

## 0.18.0

* Allow anonymous functions and classes as default exports ([#37](https://github.com/bublejs/buble/issues/37))
* Handle non-breaking spaces in JSX ([#46](https://github.com/bublejs/buble/issues/46))
* Allow anonymous classes to be assigned to properties ([#33](https://github.com/bublejs/buble/issues/33))
* Add `trailingFunctionCommas` transformation ([#50](https://github.com/bublejs/buble/issues/50))

## 0.17.3

* Move `chalk` to dependencies ([#35](https://github.com/bublejs/buble/issues/35))

## 0.17.2

* Fix nested template literals regression ([#39](https://github.com/bublejs/buble/issues/39))

## 0.17.1

* Error on nested rest elements ([#31](https://github.com/bublejs/buble/pull/31))
* Allow destructuring with computed properties ([#34](https://github.com/bublejs/buble/pull/34))

## 0.17.0

* Update dependencies
* Transpile arrow functions unconditionally if spread arguments need transpilation ([#22](https://github.com/bublejs/buble/pull/22))
* Better object spread support ([#25](https://github.com/bublejs/buble/pull/25))
* Rest properties ([#30](https://github.com/bublejs/buble/pull/30))
* Fix ([#24](https://github.com/bublejs/buble/pull/24))

## 0.16.0

* Allow truthy dash-cased props ([#2](https://github.com/bublejs/buble/pull/2))
* Make class accessors configurable ([#3](https://github.com/bublejs/buble/pull/3))
* Support JSX pragma comments ([#5](https://github.com/bublejs/buble/pull/5))
* Handle JSX with no spaces between attributes ([#6](https://github.com/bublejs/buble/pull/6))

## 0.15.2

* Don't create function names for object methods with `namedFunctionExpressions: false`
* Simplify destructuring assignment statements
* Give unique names to methods that shadow free variables ([#166](https://gitlab.com/Rich-Harris/buble/issues/166))

## 0.15.1

* Fix `Object.assign` regression ([#163](https://gitlab.com/Rich-Harris/buble/issues/163))

## 0.15.0

* More informative CLI errors when input comes from stdin ([#155](https://gitlab.com/Rich-Harris/buble/issues/155))
* Prevent PhantomJS shadowing errors ([#154](https://gitlab.com/Rich-Harris/buble/issues/154))
* Use local `register.js` in tests ([#153](https://gitlab.com/Rich-Harris/buble/issues/153))
* Correct CLI output filename with .jsx input ([#151](https://gitlab.com/Rich-Harris/buble/issues/151))
* Fix whitespace removal bug ([#159](https://gitlab.com/Rich-Harris/buble/issues/159))
* Allow computed properties in object destructuring ([#146](https://gitlab.com/Rich-Harris/buble/issues/146))
* Support rest elements in array destructuring ([#147](https://gitlab.com/Rich-Harris/buble/issues/147))
* Fix array swap assignment expression ([#148](https://gitlab.com/Rich-Harris/buble/issues/148))
* Allow template string as destructuring default ([#145](https://gitlab.com/Rich-Harris/buble/issues/145))
* Support multiple returning loops with block scoping ([cbc17ad5e](https://gitlab.com/Rich-Harris/buble/commit/cbc17ad5e1dc6e8af820fee372e6fb68e475afa4))
* Fix `super` with spread arguments ([#129](https://gitlab.com/Rich-Harris/buble/issues/129))
* Arrow function returning computed property ([#126](https://gitlab.com/Rich-Harris/buble/issues/126))
* Allow computed property and object spread to coexist ([#144](https://gitlab.com/Rich-Harris/buble/issues/144))
* Add `namedFunctionExpressions` option to prevent scope leak in old browsers ([#130](https://gitlab.com/Rich-Harris/buble/issues/130))
* Fix exponentiation assignment edge case ([#122](https://gitlab.com/Rich-Harris/buble/issues/122))
* Allow CLI `--output` flag to work with stdin input

## 0.14.3

* Prevent crashing on Node versions more recent than the latest 'supported' version ([#102](https://gitlab.com/Rich-Harris/buble/merge_requests/102))

## 0.14.2

* Allow `.jsx` file extension ([#127](https://gitlab.com/Rich-Harris/buble/issues/127))
* Handle trailing comma in spread operator ([#133](https://gitlab.com/Rich-Harris/buble/issues/133))
* Allow empty code blocks in JSX ([#131](https://gitlab.com/Rich-Harris/buble/issues/131))
* Allow computed shorthand function name with spread in body ([#135](https://gitlab.com/Rich-Harris/buble/issues/135))
* Add `--objectAssign` CLI option ([#113](https://gitlab.com/Rich-Harris/buble/issues/113))
* Allow numeric literals as shorthand method keys ([#139](https://gitlab.com/Rich-Harris/buble/issues/139))

## 0.14.1

* fix initialization of block-scoped variables in for-of and for-in loops ([#124](https://gitlab.com/Rich-Harris/buble/issues/124))

## 0.14.0

* Always wrap block-less bodies in curlies ([#110](https://gitlab.com/Rich-Harris/buble/issues/110), [#117](https://gitlab.com/Rich-Harris/buble/issues/117), [!80](https://gitlab.com/Rich-Harris/buble/merge_requests/80))
* Make sure block-scoped variables in loops have an initializer ([#124](https://gitlab.com/Rich-Harris/buble/issues/124))
* Destructuring assignments ([!82](https://gitlab.com/Rich-Harris/buble/merge_requests/82))
* Support string literals in object destructuring ([!81](https://gitlab.com/Rich-Harris/buble/merge_requests/81))
* Standalone arrow function expression statements ([!79](https://gitlab.com/Rich-Harris/buble/merge_requests/79))

## 0.13.2

* Fix spread operator when used with `new` and `this` ([#104](https://gitlab.com/Rich-Harris/buble/issues/104), [#115](https://gitlab.com/Rich-Harris/buble/issues/115))

## 0.13.1

* Handle destructuring in for/for-of loop heads ([#95](https://gitlab.com/Rich-Harris/buble/issues/95))
* Allow early return (without value) from loops ([#103](https://gitlab.com/Rich-Harris/buble/issues/103), [#105](https://gitlab.com/Rich-Harris/buble/issues/105))

## 0.13.0

* Require an `objectAssign` option to be specified if using object spread operator ([#93](https://gitlab.com/Rich-Harris/buble/issues/93))
* Fix spread operator with expression method calls and template strings ([!74](https://gitlab.com/Rich-Harris/buble/merge_requests/74))

## 0.12.5

* Prevent reserved words being used as identifiers ([#86](https://gitlab.com/Rich-Harris/buble/issues/86))
* Use correct `this` when transpiling `super` inside arrow function ([#89](https://gitlab.com/Rich-Harris/buble/issues/89))
* Handle body-less `for-of` loops ([#80](https://gitlab.com/Rich-Harris/buble/issues/80))

## 0.12.4

* Allow references to precede declaration (inside function) in block scoping ([#87](https://gitlab.com/Rich-Harris/buble/issues/87))

## 0.12.3

* Argh, npm

## 0.12.2

* Files missing in 0.12.1 (???)

## 0.12.1

* Don't require space before parens of shorthand computed method ([#82](https://gitlab.com/Rich-Harris/buble/issues/82))
* Allow string keys for shorthand methods ([#82](https://gitlab.com/Rich-Harris/buble/issues/82))

## 0.12.0

* Support `u` flag in regular expression literals ([!62](https://gitlab.com/Rich-Harris/buble/merge_requests/62))
* Save `buble/register` transformations to `$HOME/.buble-cache` ([!63](https://gitlab.com/Rich-Harris/buble/merge_requests/63))

## 0.11.6

* Allow shorthand methods with computed names ([#78](https://gitlab.com/Rich-Harris/buble/issues/78))
* Include code snippet in `error.toString()` ([#79](https://gitlab.com/Rich-Harris/buble/issues/79))

## 0.11.5

* Preserve whitespace between JSX tags on single line ([#65](https://gitlab.com/Rich-Harris/buble/issues/65))

## 0.11.4

* Allow computed class methods, except accessors ([!56](https://gitlab.com/Rich-Harris/buble/merge_requests/56))
* Compound destructuring ([!58](https://gitlab.com/Rich-Harris/buble/merge_requests/58))

## 0.11.3

* Ensure inserted statements follow use strict pragma ([#72](https://gitlab.com/Rich-Harris/buble/issues/72))

## 0.11.2

* Ensure closing parenthesis is in correct place when transpiling inline computed property object expressions ([#73](https://gitlab.com/Rich-Harris/buble/issues/73))

## 0.11.1

* Fix computed property followed by non-computed property in inline expression

## 0.11.0

* Computed properties ([#67](https://gitlab.com/Rich-Harris/buble/issues/67))
* Allow `super(...)` to use rest arguments ([#69](https://gitlab.com/Rich-Harris/buble/issues/69))

## 0.10.7

* Allow customisation of `Object.assign` (used in object spread) ([!51](https://gitlab.com/Rich-Harris/buble/merge_requests/51))

## 0.10.6

* Handle sparse arrays ([#62](https://gitlab.com/Rich-Harris/buble/issues/62))
* Handle spread expressions in JSX ([#64](https://gitlab.com/Rich-Harris/buble/issues/64))

## 0.10.5

* Create intermediate directories when transforming via CLI ([#63](https://gitlab.com/Rich-Harris/buble/issues/63))
* Update README ([#57](https://gitlab.com/Rich-Harris/buble/issues/57))

## 0.10.4

* Support spread operator in object literals ([!45](https://gitlab.com/Rich-Harris/buble/merge_requests/45)) and JSX elements ([!46](https://gitlab.com/Rich-Harris/buble/merge_requests/46))

## 0.10.3

* Disable intelligent destructuring, temporarily ([#53](https://gitlab.com/Rich-Harris/buble/issues/53))
* Fix whitespace in JSX literals ([!39](https://gitlab.com/Rich-Harris/buble/merge_requests/39))
* Add `: true` to value-less JSX attributes ([!40](https://gitlab.com/Rich-Harris/buble/merge_requests/40))
* Quote invalid attribute names ([!41](https://gitlab.com/Rich-Harris/buble/merge_requests/41))

## 0.10.2

* Don't add closing quote to JSX component without attributes ([#58](https://gitlab.com/Rich-Harris/buble/issues/58))

## 0.10.1

* Fix handling of literals inside JSX

## 0.10.0

* Basic JSX support

## 0.9.3

* Better spread operator support, including with `arguments` ([#40](https://gitlab.com/Rich-Harris/buble/issues/40))
* Fix indentation of inserted statements in class constructors ([#39](https://gitlab.com/Rich-Harris/buble/issues/39))

## 0.9.2

* Allow class to have accessors and no constructor ([#48](https://gitlab.com/Rich-Harris/buble/issues/48))
* Fix help message in CLI

## 0.9.1

* Prevent confusion over `Literal` node keys

## 0.9.0

* More complete and robust destructuring support ([#37](https://gitlab.com/Rich-Harris/buble/issues/37), [#43](https://gitlab.com/Rich-Harris/buble/issues/43))
* Correct `this`/`arguments` references inside for-of loop

## 0.8.5

* Allow destructured parameter to have default ([#43](https://gitlab.com/Rich-Harris/buble/issues/43))
* Allow `continue`/`break` statements inside a for-of loop

## 0.8.4

* Allow class body to follow ID/superclass without whitespace ([#46](https://gitlab.com/Rich-Harris/buble/issues/46))

## 0.8.3

* Performance enhancements ([!23](https://gitlab.com/Rich-Harris/buble/merge_requests/23))

## 0.8.2

* More robust version of ([!22](https://gitlab.com/Rich-Harris/buble/merge_requests/22))

## 0.8.1

* Fix `export default class A extends B` (broken in 0.8.0) ([!22](https://gitlab.com/Rich-Harris/buble/merge_requests/22))

## 0.8.0

* Subclasses inherit static methods ([#33](https://gitlab.com/Rich-Harris/buble/issues/33))
* Performance enhancements ([!21](https://gitlab.com/Rich-Harris/buble/merge_requests/21))

## 0.7.1

* Prevent omission of closing paren in template string ([#42](https://gitlab.com/Rich-Harris/buble/issues/42))
* Separate variable declarations for each name in destructured declaration ([#18](https://gitlab.com/Rich-Harris/buble/merge_requests/18))

## 0.7.0

* Allow arrow functions to be used as default parameter values ([#36](https://gitlab.com/Rich-Harris/buble/issues/36))

## 0.6.7

* Support `static get` and `set` in classes ([#34](https://gitlab.com/Rich-Harris/buble/issues/34))
* Support spread operator in expression method call ([!14](https://gitlab.com/Rich-Harris/buble/merge_requests/14))
* Fix `for-of` loops with no space after opening paren ([#35](https://gitlab.com/Rich-Harris/buble/issues/35))

## 0.6.6

* Fix another subclass `super()` bug ([#32](https://gitlab.com/Rich-Harris/buble/issues/32))

## 0.6.5

* Fix `super()` call in subclass expression ([#32](https://gitlab.com/Rich-Harris/buble/issues/32))
* Less defensive template string parenthesising ([!9](https://gitlab.com/Rich-Harris/buble/merge_requests/9))

## 0.6.4

* Add Node 6 to support matrix

## 0.6.3

* Handle empty template strings ([#28](https://gitlab.com/Rich-Harris/buble/issues/28))

## 0.6.2

* Handle body-less do-while blocks ([#27](https://gitlab.com/Rich-Harris/buble/issues/27))

## 0.6.1

* Always remember to close parens in template strings

## 0.6.0

* Strip unnecessary empty strings from template literals
* Intelligent destructuring for object patterns in parameters ([#17](https://gitlab.com/Rich-Harris/buble/issues/17))

## 0.5.8

* Fix exponentiation assignment operator edge case

## 0.5.7

* Exponentiation operator support ([#24](https://gitlab.com/Rich-Harris/buble/issues/24))
* More informative error messages for for-of and tagged template strings

## 0.5.6

* Add `dangerousTaggedTemplateString` ([!2](https://gitlab.com/Rich-Harris/buble/merge_requests/2)) and `dangerousForOf` ([!3](https://gitlab.com/Rich-Harris/buble/merge_requests/3)) transforms
* Prevent deindentation causing errors with removed whitespace in class methods
* Use correct identifier with default destructured function parameters ([#23](https://gitlab.com/Rich-Harris/buble/issues/23))


## 0.5.5

* Ensure `return` is in correct place when creating bodies for arrow functions ([#21](https://gitlab.com/Rich-Harris/buble/issues/21))
* Prevent deindentation of class methods causing breakage with destructuring statements ([#22](https://gitlab.com/Rich-Harris/buble/issues/22))

## 0.5.4

* Install missing `chalk` dependency
* Informative error messages when `buble/register` fails

## 0.5.3

* Add `register.js` to package. Yes I'm an idiot

## 0.5.2

* Add `buble/register` for use with e.g. Mocha

## 0.5.1

* Remove unused dependency

## 0.5.0

* Support `--target`, `--yes` and `--no` in CLI
* Compile entire directory of files via CLI
* Sourcemap support in CLI
* All transforms can be disabled (or errors suppressed) with the `transforms` option (or `--yes` and `--no`, in the CLI)
* `import` and `export` will throw an error unless `--no modules` transform is specified
* Fix bug with destructuring
* Fix bug with block scoping and loops


## 0.4.24

* Throw if `let`/`const` is redeclared, or `var` is redeclared with a `let`/`const` (0.4.22 regression)

## 0.4.23

* Add `buble.VERSION`
* Tidy up build process (don't bundle Acorn incorrectly)

## 0.4.22

* Allow double `var` declarations (only throw if `let` or `const` is redeclared)

## 0.4.21

* Add `find` and `findIndex` helpers for 0.12 support

## 0.4.20

* Bump to resolve unknown npm issue

## 0.4.19

* Fix block scoping bug with for loops that don't need to be rewritten as functions

## 0.4.18

* Fix break-inside-switch bug

## 0.4.17

* Support `for...in` loops and block scoping

## 0.4.16

* Add `ie` and `edge` to support matrix

## 0.4.15

* Rewrite reserved properties if specified ([#9](https://gitlab.com/Rich-Harris/buble/issues/9))

## 0.4.14

* Allow classes to extend expressions ([#15](https://gitlab.com/Rich-Harris/buble/issues/15))
* Experimental (partially implemented) API for disabling transforms based on target environment or custom requirements

## 0.4.13

* Fix return statement bug

## 0.4.12

* More complete and robust transpilation of loops that need to be rewritten as functions to simulate block scoping ([#11](https://gitlab.com/Rich-Harris/buble/issues/11), [#12](https://gitlab.com/Rich-Harris/buble/issues/12), [#13](https://gitlab.com/Rich-Harris/buble/issues/13))

## 0.4.11

* Remove source-map-support from CLI (only useful during development)

## 0.4.10

* Basic support for spread operator

## 0.4.9

* Support getters and setters on subclasses
* Disallow unsupported features e.g. generators

## 0.4.8

* Support getters and setters on classes
* Allow identifiers to be renamed in block-scoped destructuring ([#8](https://gitlab.com/Rich-Harris/buble/issues/8))
* Transpile body-less arrow functions correctly ([#9](https://gitlab.com/Rich-Harris/buble/issues/4))

## 0.4.7

* Add browser version

## 0.4.6

* Report locations of parse/compile errors ([#4](https://gitlab.com/Rich-Harris/buble/issues/4))

## 0.4.5

* Sourcemap support

## 0.4.4

* Support for class expressions
* More robust deconflicting
* Various bugfixes

## 0.4.3

* Handle arbitrary whitespace inside template literals

## 0.4.2

* Fix bug-inducing typo

## 0.4.1

* Rest parameters

## 0.4.0

* Self-hosting!

## 0.3.4

* Class inheritance

## 0.3.3

* Handle quote marks in template literals

## 0.3.2

* Handle empty `class` declarations

## 0.3.1

* Add `bin` to package

## 0.3.0

* (Very) basic CLI
* Handle `export default class ...`

## 0.2.2

* Initialise children of Property nodes
* Prevent false positives with reference detection

## 0.2.1

* Add missing files

## 0.2.0

* Support for a bunch more ES2015 features

## 0.1.0

* First (experimental) release
