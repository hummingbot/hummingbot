# [5.3.0](https://github.com/streamich/nano-css/compare/v5.2.0...v5.3.0) (2020-02-17)


### Bug Fixes

* **addon\atom:** mistake in types; ([3be2d1f](https://github.com/streamich/nano-css/commit/3be2d1ff04c8e3d1580280b52aa47a52cdfdb7e7))
* **addon\emmet:** mistake in types; ([54583fe](https://github.com/streamich/nano-css/commit/54583fe04a22efc97fabfc7655abdcd8f2394119))


### Features

* 🎸 export all types ([23a1ade](https://github.com/streamich/nano-css/commit/23a1adeeb8f436b108644ee9fb1b2c83dc2265b4))

# [5.2.0](https://github.com/streamich/nano-css/compare/v5.1.0...v5.2.0) (2019-06-03)


### Features

* add "::placeholder" support to prefixer ([caf78d8](https://github.com/streamich/nano-css/commit/caf78d8))

# [5.1.0](https://github.com/streamich/nano-css/compare/v5.0.0...v5.1.0) (2019-03-26)


### Bug Fixes

* 🐛 don't crash CSSOM and VCSSOM addons on server side ([123f76c](https://github.com/streamich/nano-css/commit/123f76c))


### Features

* 🎸 add .del() to VRule, removeRule() now acc only 1 arg ([6d25e55](https://github.com/streamich/nano-css/commit/6d25e55))
* 🎸 change VRule interface, add vcssom docs ([18cea49](https://github.com/streamich/nano-css/commit/18cea49))

# [5.0.0](https://github.com/streamich/nano-css/compare/v4.0.0...v5.0.0) (2019-03-22)


### Bug Fixes

* 🐛 don't load VCSSOM in non-browser environments ([857b2d2](https://github.com/streamich/nano-css/commit/857b2d2))
* 🐛 search for rule index before removing it ([27b48ca](https://github.com/streamich/nano-css/commit/27b48ca))


### Features

* 🎸 add CSSOM and VCSSOM TypeScript typings ([607253a](https://github.com/streamich/nano-css/commit/607253a))
* 🎸 add TypeScript definitiosn for some missing addons ([6611aac](https://github.com/streamich/nano-css/commit/6611aac))
* 🎸 allow JS-style snake-case declaration properties ([9b8197a](https://github.com/streamich/nano-css/commit/9b8197a))
* 🎸 move TypeScript typings inline next to implementations ([224ee56](https://github.com/streamich/nano-css/commit/224ee56))


### BREAKING CHANGES

* 🧨 refactoring TypeScript types might break some TypeScript builds

# [4.0.0](https://github.com/streamich/nano-css/compare/v3.5.0...v4.0.0) (2019-03-21)


### Bug Fixes

* 🐛`NODE_EVN` should be `NODE_ENV` ([8feead7](https://github.com/streamich/nano-css/commit/8feead7))
* upgrade react-dom due to vulnerability ([8bdeeba](https://github.com/streamich/nano-css/commit/8bdeeba))
* upgrade webpack-dev-server due to vulnerability ([602d9c3](https://github.com/streamich/nano-css/commit/602d9c3))


### Features

* 🎸 add vcssom addon ([63e27f2](https://github.com/streamich/nano-css/commit/63e27f2))
* 🎸 create unified CSSOM createRule() for all use cases ([6976707](https://github.com/streamich/nano-css/commit/6976707))
* 🎸 improve cssom addon ([6f1ead5](https://github.com/streamich/nano-css/commit/6f1ead5))
* 🎸support `[@font-face](https://github.com/font-face)` ([a905b54](https://github.com/streamich/nano-css/commit/a905b54)), closes [#220](https://github.com/streamich/nano-css/issues/220)


### BREAKING CHANGES

* cssom addon API changed, pipe addon as a consequence now behaves
differently, too
* old putRule() CSSOM function is now removed, use createRule() instead

# [3.5.0](https://github.com/streamich/nano-css/compare/v3.4.0...v3.5.0) (2018-12-26)


### Features

* add Emmet based abbreviations for css atoms ([#215](https://github.com/streamich/nano-css/issues/215)) ([ee1f487](https://github.com/streamich/nano-css/commit/ee1f487))

# [3.4.0](https://github.com/streamich/nano-css/compare/v3.3.0...v3.4.0) (2018-09-18)


### Features

* better prefixing ([e5e83c4](https://github.com/streamich/nano-css/commit/e5e83c4)), closes [#206](https://github.com/streamich/nano-css/issues/206)

# [3.3.0](https://github.com/streamich/nano-css/compare/v3.2.1...v3.3.0) (2018-09-18)


### Bug Fixes

* improve kebab case conversion ([1819a14](https://github.com/streamich/nano-css/commit/1819a14))


### Features

* better kebab case conversion ([380f65f](https://github.com/streamich/nano-css/commit/380f65f))

## [3.2.1](https://github.com/streamich/nano-css/compare/v3.2.0...v3.2.1) (2018-08-06)


### Bug Fixes

* 🐛 don't insert empty !important declarations ([197430d](https://github.com/streamich/nano-css/commit/197430d))

# [3.2.0](https://github.com/streamich/nano-css/compare/v3.1.0...v3.2.0) (2018-08-05)


### Bug Fixes

* 🐛 add !important only if it is not already there ([8f0bc4c](https://github.com/streamich/nano-css/commit/8f0bc4c))
* 🐛 replace all & operators in nesting addon ([0e1eca8](https://github.com/streamich/nano-css/commit/0e1eca8))


### Features

* 🎸 add placeholders for decorator and comp addons types ([2c897e0](https://github.com/streamich/nano-css/commit/2c897e0))

# [3.1.0](https://github.com/streamich/nano-css/compare/v3.0.1...v3.1.0) (2018-07-21)


### Features

* 🎸 add atoms addon typings ([472415c](https://github.com/streamich/nano-css/commit/472415c))
* 🎸 add drule addon typings ([fe0345c](https://github.com/streamich/nano-css/commit/fe0345c))
* 🎸 add keyframes() addon typings ([4615452](https://github.com/streamich/nano-css/commit/4615452))
* 🎸 add sheet addon typings ([2b86cc2](https://github.com/streamich/nano-css/commit/2b86cc2))
* add sheet preset typings ([94c11ac](https://github.com/streamich/nano-css/commit/94c11ac))

## [3.0.1](https://github.com/streamich/nano-css/compare/v3.0.0...v3.0.1) (2018-07-16)


### Bug Fixes

* 🐛 enumerate map returned by sheet() ([58da52a](https://github.com/streamich/nano-css/commit/58da52a)), closes [#189](https://github.com/streamich/nano-css/issues/189)

# [3.0.0](https://github.com/streamich/nano-css/compare/v2.2.0...v3.0.0) (2018-07-15)


### Features

* 🎸 add TypeScript type definitions ([696dd4d](https://github.com/streamich/nano-css/commit/696dd4d))
* 🎸 improve TypeScript definitions ([21a3a49](https://github.com/streamich/nano-css/commit/21a3a49))
* 🎸 pretty-print CSS in DEV mode ([446e9c1](https://github.com/streamich/nano-css/commit/446e9c1))
* 🎸 protect .putRaw from unknown pseudo-selectors ([d122cf5](https://github.com/streamich/nano-css/commit/d122cf5))
* 🎸 remove `safe` addon in favor of new changes ([9f0c2fc](https://github.com/streamich/nano-css/commit/9f0c2fc))


### BREAKING CHANGES

* safe addon is now removed and .putRaw will not throw

# [2.2.0](https://github.com/streamich/nano-css/compare/v2.1.0...v2.2.0) (2018-07-14)


### Features

* 🎸 make `safe` addom less chatty ([c449a13](https://github.com/streamich/nano-css/commit/c449a13))


### Performance Improvements

* ⚡️ store all units in a string ([7142d86](https://github.com/streamich/nano-css/commit/7142d86))

# [2.1.0](https://github.com/streamich/nano-css/compare/v2.0.2...v2.1.0) (2018-07-11)


### Features

* 🎸 add "tr" atom for "transform" property ([e4d59e5](https://github.com/streamich/nano-css/commit/e4d59e5))
* 🎸 add sourcemaps addon to presets ([8fb46c0](https://github.com/streamich/nano-css/commit/8fb46c0))
* 🎸 create "safe" addon ([d6f0ad5](https://github.com/streamich/nano-css/commit/d6f0ad5))
* 🎸 create "units" addon ([0e1e25c](https://github.com/streamich/nano-css/commit/0e1e25c))
* 🎸 improve hydrate addon ([511b293](https://github.com/streamich/nano-css/commit/511b293))
* 🎸 improve source maps, make work with jsx and sheet ([8b24e44](https://github.com/streamich/nano-css/commit/8b24e44))
* 🎸 make first version of sourcemap addon work ([038b2c1](https://github.com/streamich/nano-css/commit/038b2c1))
* 🎸 warn user on clashing block names ([79a0a36](https://github.com/streamich/nano-css/commit/79a0a36))


### Performance Improvements

* ⚡️ create units object only once ([4c39f31](https://github.com/streamich/nano-css/commit/4c39f31))

## [2.0.2](https://github.com/streamich/nano-css/compare/v2.0.1...v2.0.2) (2018-06-15)


### Bug Fixes

* release hydrate bug fix ([88b5a2c](https://github.com/streamich/nano-css/commit/88b5a2c))

## [2.0.1](https://github.com/streamich/nano-css/compare/v2.0.0...v2.0.1) (2018-06-15)


### Bug Fixes

* remove complicated selectors in Normalize.css reset ([4f13854](https://github.com/streamich/nano-css/commit/4f13854))

# [2.0.0](https://github.com/streamich/nano-css/compare/v1.0.0...v2.0.0) (2018-06-13)


### Features

* semantic-releaes v2 ([ccb5d6d](https://github.com/streamich/nano-css/commit/ccb5d6d))


### BREAKING CHANGES

* v2

# 1.0.0 (2018-06-13)


### Bug Fixes

* add back Yahoo reset test ([45ff58f](https://github.com/streamich/nano-css/commit/45ff58f))
* always render style() comps on extract addon ([2657001](https://github.com/streamich/nano-css/commit/2657001))
* dont require json loader for webpack ([91d1874](https://github.com/streamich/nano-css/commit/91d1874))
* fix atoms addon ([7bac059](https://github.com/streamich/nano-css/commit/7bac059))
* improve fonts reset ([daab84b](https://github.com/streamich/nano-css/commit/daab84b))
* insert rules at the end of stylesheet ([752de24](https://github.com/streamich/nano-css/commit/752de24))
* make precedence of top level rules higher ([3ae7050](https://github.com/streamich/nano-css/commit/3ae7050))
* support array-as-value after prefixing ([5197e66](https://github.com/streamich/nano-css/commit/5197e66))
* typos ([33186cd](https://github.com/streamich/nano-css/commit/33186cd))


### Features

* 🎸 add Normalize.css reest ([fe8fee1](https://github.com/streamich/nano-css/commit/fe8fee1)), closes [#132](https://github.com/streamich/nano-css/issues/132)
* add $ref and $as support for jsx() ([1207854](https://github.com/streamich/nano-css/commit/1207854))
* add atom addon ([edc5d59](https://github.com/streamich/nano-css/commit/edc5d59))
* add Atrule support ([20882c4](https://github.com/streamich/nano-css/commit/20882c4))
* add basic amp addon ([5e5b633](https://github.com/streamich/nano-css/commit/5e5b633))
* add basic cssom addon ([a08dbc9](https://github.com/streamich/nano-css/commit/a08dbc9))
* add basic keyframes() implementation ([cd3dcc7](https://github.com/streamich/nano-css/commit/cd3dcc7))
* add basic pipe addon ([034ab59](https://github.com/streamich/nano-css/commit/034ab59))
* add basic rtl addon implementation ([c7b901d](https://github.com/streamich/nano-css/commit/c7b901d))
* add basic spread implementation ([fa376da](https://github.com/streamich/nano-css/commit/fa376da))
* add basic static class decorator ([51b09b3](https://github.com/streamich/nano-css/commit/51b09b3))
* add CSS resets ([26f86b4](https://github.com/streamich/nano-css/commit/26f86b4))
* add decorator addon ([381d4fd](https://github.com/streamich/nano-css/commit/381d4fd))
* add dsheet() ([744149c](https://github.com/streamich/nano-css/commit/744149c))
* add dsheet() interface ([1d509ed](https://github.com/streamich/nano-css/commit/1d509ed))
* add extract addon ([8f9fed0](https://github.com/streamich/nano-css/commit/8f9fed0))
* add fadeIn animation ([9de1af8](https://github.com/streamich/nano-css/commit/9de1af8))
* add fadeIn animation story ([b17051d](https://github.com/streamich/nano-css/commit/b17051d))
* add fadeInDown animation ([074b954](https://github.com/streamich/nano-css/commit/074b954))
* add fadeInExpand animation ([cc3e75e](https://github.com/streamich/nano-css/commit/cc3e75e))
* add garbage collection to pipe() ([f2a9087](https://github.com/streamich/nano-css/commit/f2a9087))
* add hoistGlobalsAndWrapContext() ([364ba2b](https://github.com/streamich/nano-css/commit/364ba2b))
* add hydration addon ([0a8feb4](https://github.com/streamich/nano-css/commit/0a8feb4))
* add initial implementation ([32a7caf](https://github.com/streamich/nano-css/commit/32a7caf))
* add inline-style-prefixer addon ([005dd68](https://github.com/streamich/nano-css/commit/005dd68))
* add keyframes() ([77578ba](https://github.com/streamich/nano-css/commit/77578ba))
* add limit addon ([4b2ab42](https://github.com/streamich/nano-css/commit/4b2ab42))
* add minH and maxH atoms ([5772142](https://github.com/streamich/nano-css/commit/5772142))
* add nesting addon ([ce8b5dc](https://github.com/streamich/nano-css/commit/ce8b5dc))
* add prefixes to keyframes ([6e98435](https://github.com/streamich/nano-css/commit/6e98435))
* add pseudo selectors :hover :focus ([4bacb7e](https://github.com/streamich/nano-css/commit/4bacb7e))
* add react preset ([ae542c0](https://github.com/streamich/nano-css/commit/ae542c0))
* add reset-font addon ([913320d](https://github.com/streamich/nano-css/commit/913320d))
* add sheet preset ([1d67594](https://github.com/streamich/nano-css/commit/1d67594))
* add sheet() addon ([f2d4bd2](https://github.com/streamich/nano-css/commit/f2d4bd2))
* add snake any value .s and semantic accents ([ee296ed](https://github.com/streamich/nano-css/commit/ee296ed))
* add spread addon ([388b391](https://github.com/streamich/nano-css/commit/388b391))
* add stable hash story ([c0367ee](https://github.com/streamich/nano-css/commit/c0367ee))
* add stable stringify plugin ([be13c1b](https://github.com/streamich/nano-css/commit/be13c1b))
* add static decorator dynamic CSS ([5ef8a08](https://github.com/streamich/nano-css/commit/5ef8a08))
* add stylis ([37f714c](https://github.com/streamich/nano-css/commit/37f714c))
* add tachyons definitions ([bd1bfa7](https://github.com/streamich/nano-css/commit/bd1bfa7))
* add tachyons hover rules ([0aabd1c](https://github.com/streamich/nano-css/commit/0aabd1c))
* add toCss() ([b8a4958](https://github.com/streamich/nano-css/commit/b8a4958))
* add unitless addon that add 'px' automatical ([ca0f9b0](https://github.com/streamich/nano-css/commit/ca0f9b0))
* add useStyles interface ([2e78159](https://github.com/streamich/nano-css/commit/2e78159))
* add vendor prefixes to keyframes addon ([5ddd5bb](https://github.com/streamich/nano-css/commit/5ddd5bb))
* add virtual CSS addon ([3220b02](https://github.com/streamich/nano-css/commit/3220b02))
* add warning generator for missing deps ([f81481d](https://github.com/streamich/nano-css/commit/f81481d))
* add withStyles() interface ([4d04280](https://github.com/streamich/nano-css/commit/4d04280))
* allow .s to accept an object ([aedbc41](https://github.com/streamich/nano-css/commit/aedbc41))
* allow composition ([d47d212](https://github.com/streamich/nano-css/commit/d47d212))
* basic snake addon implementation ([04965d2](https://github.com/streamich/nano-css/commit/04965d2))
* change how hydration sheet is located ([73259ef](https://github.com/streamich/nano-css/commit/73259ef))
* creat tachyons snake rules ([2829c33](https://github.com/streamich/nano-css/commit/2829c33))
* create Component interface ([2de1804](https://github.com/streamich/nano-css/commit/2de1804))
* create new snake instance dynamically ([d8c0951](https://github.com/streamich/nano-css/commit/d8c0951))
* create react preset ([69b0c4e](https://github.com/streamich/nano-css/commit/69b0c4e))
* create separate stylesheet for keyframes ([90a75a1](https://github.com/streamich/nano-css/commit/90a75a1))
* create styled() addon ([a68d1d7](https://github.com/streamich/nano-css/commit/a68d1d7))
* display inserted styles in devtools in DEV ([f047821](https://github.com/streamich/nano-css/commit/f047821))
* expose .sheet property ([4b4a32d](https://github.com/streamich/nano-css/commit/4b4a32d))
* expose selector for addons ([ad64849](https://github.com/streamich/nano-css/commit/ad64849))
* expose stringify() function ([d4756d8](https://github.com/streamich/nano-css/commit/d4756d8))
* first implementation of array addon ([77f0ad9](https://github.com/streamich/nano-css/commit/77f0ad9))
* fix sheet() and add storeis ([923cced](https://github.com/streamich/nano-css/commit/923cced))
* fix sheet() and add stories ([f135cc2](https://github.com/streamich/nano-css/commit/f135cc2))
* implement basic ref() interface ([46de4fd](https://github.com/streamich/nano-css/commit/46de4fd))
* implement drule() ([31ee8a2](https://github.com/streamich/nano-css/commit/31ee8a2))
* implement first version of virtual addon ([d3225e2](https://github.com/streamich/nano-css/commit/d3225e2))
* implement googleFont addon ([9083919](https://github.com/streamich/nano-css/commit/9083919))
* implement hyperstyle() interface ([7fe96eb](https://github.com/streamich/nano-css/commit/7fe96eb))
* implement jsx() ([7721f0b](https://github.com/streamich/nano-css/commit/7721f0b))
* implement put() function ([07ab8e6](https://github.com/streamich/nano-css/commit/07ab8e6))
* implement ref addon ([d8b6a1e](https://github.com/streamich/nano-css/commit/d8b6a1e))
* implement styled() ([33d31b4](https://github.com/streamich/nano-css/commit/33d31b4))
* implement validate addon ([03d039f](https://github.com/streamich/nano-css/commit/03d039f))
* improve amp addon ([7314eae](https://github.com/streamich/nano-css/commit/7314eae))
* improve atoms and snake addons ([8eff686](https://github.com/streamich/nano-css/commit/8eff686))
* improve fade out animations ([564ac3a](https://github.com/streamich/nano-css/commit/564ac3a))
* improve snake addon ([9ec9de6](https://github.com/streamich/nano-css/commit/9ec9de6))
* improve snake nesting .s ([1e2409e](https://github.com/streamich/nano-css/commit/1e2409e))
* improvements ([31d23ee](https://github.com/streamich/nano-css/commit/31d23ee))
* initial commit ([422f05b](https://github.com/streamich/nano-css/commit/422f05b))
* make rule() work ([3816612](https://github.com/streamich/nano-css/commit/3816612))
* make validate addon compile ([a9f1adc](https://github.com/streamich/nano-css/commit/a9f1adc))
* release v2 ([ed24a90](https://github.com/streamich/nano-css/commit/ed24a90))
* remove pipe rules when node is unmounted ([d278cec](https://github.com/streamich/nano-css/commit/d278cec))
* setup project files ([c9580d5](https://github.com/streamich/nano-css/commit/c9580d5))
* various ([40039b7](https://github.com/streamich/nano-css/commit/40039b7))
* work on hydration ([5f4dc5c](https://github.com/streamich/nano-css/commit/5f4dc5c))


### Performance Improvements

* improve styled() addon ([859a01f](https://github.com/streamich/nano-css/commit/859a01f))


### BREAKING CHANGES

* release v2
