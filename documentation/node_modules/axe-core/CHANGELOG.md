# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

### [3.5.5](https://github.com/dequelabs/axe-core/compare/v3.5.4...v3.5.5) (2020-06-16)

### Bug Fixes

- **aria-input-field-name:** add the missing word must to help metadata ([b0f5562](https://github.com/dequelabs/axe-core/commit/b0f5562ac2a746e8ac78f6e483e39162680f3a22))
- **color-contrast:** fix font-weight calculation for safari ([205b587](https://github.com/dequelabs/axe-core/commit/205b58709c280f00100bf24a7b6bf15da50ed0ed))
- **configure:** validate rules and checks properties ([8c91ead](https://github.com/dequelabs/axe-core/commit/8c91ead900fd3cab58f77af45cce54d02e734a8e))
- **is-visible:** return false for opacity: 0 and 0 height scrollable regions ([86ada3f](https://github.com/dequelabs/axe-core/commit/86ada3f7cef5b1fbcaad37b8acfaee93566ba8bf))
- **listitem:** do not fail for parent with role=presentation|none ([a3ddc6e](https://github.com/dequelabs/axe-core/commit/a3ddc6e1e43716b761e8bb42fba4842d88f813dc))
- **meta-viewport:** don't throw error if viewport property doesn't have a value ([2176794](https://github.com/dequelabs/axe-core/commit/2176794f8a831c8303984039e4a07b99d368b111))

### [3.5.4](https://github.com/dequelabs/axe-core/compare/v3.5.3...v3.5.4) (2020-05-22)

### Bug Fixes

- **get-element-stack:** properly calculate position of children of floated elements ([28a8c58](https://github.com/dequelabs/axe-core/commit/28a8c58b409461600da07eac164e5b0ca4744502))

### [3.5.3](https://github.com/dequelabs/axe-core/compare/v3.5.2...v3.5.3) (2020-03-31)

### Bug Fixes

- **meta-viewport:** parse negative and string values for `maximum-scale` ([#2137](https://github.com/dequelabs/axe-core/issues/2137)) ([8c92472](https://github.com/dequelabs/axe-core/commit/8c92472397676d44b333cf50ad1a9413b9783c2c))
- **respondable:** ignore reflected messages from iframes ([#2134](https://github.com/dequelabs/axe-core/issues/2134)) ([3ab9f21](https://github.com/dequelabs/axe-core/commit/3ab9f21414d8f4195ac95ffca8f0ce52258539b0))
- **header-present:** update verbiage to use heading instead of header ([#2132](https://github.com/dequelabs/axe-core/issues/2132)) ([8890063](https://github.com/dequelabs/axe-core/commit/889006397329a35a170f4a3d24c55c3c4fd758fc))
- **color-contrast:** mark more punctuations for review ([#2126](https://github.com/dequelabs/axe-core/issues/2126)) ([dc98afc](https://github.com/dequelabs/axe-core/commit/dc98afc841c86e4b7b771bbb1171152a151c3e5b))
- **unicode:** detect supplementary private use area A ([#2102](https://github.com/dequelabs/axe-core/issues/2102)) ([f1739c2](https://github.com/dequelabs/axe-core/commit/f1739c21efdf5cf6fddf425d1c72b056757f3ba1))
- **definition-list:** Mention <div> is allowed to group content in <dl> ([#2098](https://github.com/dequelabs/axe-core/issues/2098)) ([76b1a9f](https://github.com/dequelabs/axe-core/commit/76b1a9f7f244e43f63351c46d91fc8b27040ba98))
- **td-headers-attr:** mark as needs review if headers attr is empty ([#2096](https://github.com/dequelabs/axe-core/issues/2096)) ([699b566](https://github.com/dequelabs/axe-core/commit/699b566111cfed2a4ebeade35346a49bcb3546c7))
- **td-has-headers:** don't fail for empty headers attribute ([#2095](https://github.com/dequelabs/axe-core/issues/2095)) ([7952a37](https://github.com/dequelabs/axe-core/commit/7952a377b960c2403c8d4758a9f35ebe525549fe))
- **th-has-data-cells:** fail when data cell points to a different header ([#2094](https://github.com/dequelabs/axe-core/issues/2094)) ([d3bd416](https://github.com/dequelabs/axe-core/commit/d3bd416a3df7324231f17ff9e1e20dc6342c7aa5))
- **has-lang:** update message to indicate that xml:lang is not valid on HTML pages ([#2093](https://github.com/dequelabs/axe-core/issues/2093)) ([c3a7de2](https://github.com/dequelabs/axe-core/commit/c3a7de206baf77c0b25c8c095119393b1dc85f0f))
- **page-no-duplicate-contentinfo:** do not fail when first element is inside landmark ([#2092](https://github.com/dequelabs/axe-core/issues/2092)) ([eca7e05](https://github.com/dequelabs/axe-core/commit/eca7e05cc6ff750855bcb219833967a9d7087679))

### [3.5.2](https://github.com/dequelabs/axe-core/compare/v3.5.1...v3.5.2) (2020-03-06)

### Bug Fixes

- **aria-allowed-role:** allow role=spinbutton on input[type=tel](<[635445b](https://github.com/dequelabs/axe-core/commit/635445ba6da7bc197bcdee6fb1a9d9dc81e43941)>)
- **color-contrast:** ignore form elements that move text outside of node using text-indent ([#2044](https://github.com/dequelabs/axe-core/issues/2044)) ([85cc6ab](https://github.com/dequelabs/axe-core/commit/85cc6abd7f919a7311c6da01a41853cbfd539508))
- **commons:** handle node(s) contained by SVG document when de… ([#2054](https://github.com/dequelabs/axe-core/issues/2054)) ([bf4c9bf](https://github.com/dequelabs/axe-core/commit/bf4c9bff2953b1ac7f40dbb1d0bd1986c1caa673))
- **getCheckMessage:** add API to return check message ([#2066](https://github.com/dequelabs/axe-core/issues/2066)) ([e216322](https://github.com/dequelabs/axe-core/commit/e216322183c8b064ebfd748fea785b8c2fe78b16))
- **has-lang:** fail check when `xml:lang` is used in HTML docum… ([#2053](https://github.com/dequelabs/axe-core/issues/2053)) ([e07aaea](https://github.com/dequelabs/axe-core/commit/e07aaea86bc9460a2d9f568637b4a77d33094ed6))
- **label-content-name-mismatch:** ignore non `widget` aria role(s) & do not use deprecated `lookupTable.rolesOfType` ([#2022](https://github.com/dequelabs/axe-core/issues/2022)) ([89bd84c](https://github.com/dequelabs/axe-core/commit/89bd84c4a9846dc31a660eda6b274329e7ac70b5))
- **package-lock:** change @deque/doT from agora to npm ([#2058](https://github.com/dequelabs/axe-core/issues/2058)) ([c03c0e5](https://github.com/dequelabs/axe-core/commit/c03c0e5ffc3ea1b49607355fa9d6f2e2faf0ebd1))
- **page-has-heading-one:** find screen-reader only headings ([#2065](https://github.com/dequelabs/axe-core/issues/2065)) ([f808a12](https://github.com/dequelabs/axe-core/commit/f808a12261269719534ae52c878d1700fb70053e))
- **region:** ignore direct child text nodes of body ([#2050](https://github.com/dequelabs/axe-core/issues/2050)) ([fde31d0](https://github.com/dequelabs/axe-core/commit/fde31d03d24820f681b257c4c42b98f25b2877ec))
- **skip-link:** identify as skip-link only if the link is offscreen ([#2079](https://github.com/dequelabs/axe-core/issues/2079)) ([241e1d0](https://github.com/dequelabs/axe-core/commit/241e1d0715398a39c2e502ddb781f5fc29987dde))
- check `invaildrole` fails only when all roles are invalid ([#2075](https://github.com/dequelabs/axe-core/issues/2075)) ([989b317](https://github.com/dequelabs/axe-core/commit/989b31788b08b6514dd4b606162193d4dd168be9))
- ignore empty, whitespace or undefined `role` for rule `ari… ([#2077](https://github.com/dequelabs/axe-core/issues/2077)) ([dbd3c02](https://github.com/dequelabs/axe-core/commit/dbd3c0211b05641f366dfe2fe9c2124cad9e5e3a))
- update tags for rule `area-alt` ([#2051](https://github.com/dequelabs/axe-core/issues/2051)) ([7db231f](https://github.com/dequelabs/axe-core/commit/7db231f2ff2b70a4e8e6f7aababe0871764ece96))

### [3.5.1](https://github.com/dequelabs/axe-core/compare/v3.5.0...v3.5.1) (2020-02-12)

### Bug Fixes

- **color-contrast:** parse font-weight value as number ([#2031](https://github.com/dequelabs/axe-core/issues/2031)) ([#2040](https://github.com/dequelabs/axe-core/issues/2040)) ([0bb2166](https://github.com/dequelabs/axe-core/commit/0bb21669f75b3adc0e3345c85680d437c57f94d8))
- **color-contrast:** properly pass options to check ([#2033](https://github.com/dequelabs/axe-core/issues/2033)) ([26b99c0](https://github.com/dequelabs/axe-core/commit/26b99c0a511bd6fffaaca7535d732f26b39ef46e))
- **commons:** avoid unicode regex encoding in axe.min.js ([#2024](https://github.com/dequelabs/axe-core/issues/2024)) ([ae90dc4](https://github.com/dequelabs/axe-core/commit/ae90dc47521f6047f71befcb3551686cf857208d))
- **sri-history:** correct SRI for various versions ([#2041](https://github.com/dequelabs/axe-core/issues/2041)) ([940c017](https://github.com/dequelabs/axe-core/commit/940c01708cede33e796972ce810a815ddf492ba4))

## [3.5.0](https://github.com/dequelabs/axe-core/compare/v3.4.0...v3.5.0) (2020-02-04)

### Features

- **aria-dpub-role-fallback:** depreacte aria-dpub-role-fallback and move into aria-allowed-role ([#1899](https://github.com/dequelabs/axe-core/issues/1899)) ([8e25c20](https://github.com/dequelabs/axe-core/commit/8e25c20a479b03820117c6cd349b51ce7f2e94ee))
- **aria-label:** deprecate Element arg; use virtualNode ([#1922](https://github.com/dequelabs/axe-core/issues/1922)) ([d14981c](https://github.com/dequelabs/axe-core/commit/d14981c1f67ba849f9519ee826ac646d281649c7))
- **audit:** allow runOnly option to accept an array of rules ([#1889](https://github.com/dequelabs/axe-core/issues/1889)) ([38d6a3f](https://github.com/dequelabs/axe-core/commit/38d6a3fb26c66215cca0f3df8da268b34bcb6be5))
- **color-contrast:** greatly improve performance for very large sites ([#1943](https://github.com/dequelabs/axe-core/issues/1943)) ([9ea0065](https://github.com/dequelabs/axe-core/commit/9ea006534a423b2b7df1826a40e8214c6bb1fc48))
- **core:** add preload configuration option for media files ([#1958](https://github.com/dequelabs/axe-core/issues/1958)) ([8a62649](https://github.com/dequelabs/axe-core/commit/8a626498dc9694a992e76855781e2ad1cbd4fe9b))
- **core/reporters/v1:** Add failureSummary to incomplete results ([#1972](https://github.com/dequelabs/axe-core/issues/1972)) ([c88883d](https://github.com/dequelabs/axe-core/commit/c88883d00b6578593b83f3134ebf897d22a3ba61))
- **get-element-stack:** performant api to replace document.elementsFromPoint ([#1842](https://github.com/dequelabs/axe-core/issues/1842)) ([9ae07fb](https://github.com/dequelabs/axe-core/commit/9ae07fbda36afd18a42a96d6755055006f309a4c))
- **i18n:** add Danish (da-DK) translation ([#1876](https://github.com/dequelabs/axe-core/issues/1876)) ([fb6fc41](https://github.com/dequelabs/axe-core/commit/fb6fc414246bdaf1590d367352e4bea033822639))
- **landmark-no-duplicate-\*:** add rule landmark-no-duplicate-main, don't use html as element source for all duplicate rules ([#1949](https://github.com/dequelabs/axe-core/issues/1949)) ([5ec7894](https://github.com/dequelabs/axe-core/commit/5ec7894394f8348761f5fe48ad0d09b31a27d2b2))
- **layout-table:** deprecate layout-table rule and checks ([#1885](https://github.com/dequelabs/axe-core/issues/1885)) ([d22cb30](https://github.com/dequelabs/axe-core/commit/d22cb30ad29f5d1aec089eea3544ff88f3b4f8ab))
- **matches:** use VirtualNode and deprecate HTMLElement ([#1988](https://github.com/dequelabs/axe-core/issues/1988)) ([2600a06](https://github.com/dequelabs/axe-core/commit/2600a062d65f0c079b30d6a9f2aa3b6faeea6872))
- **rule:** add color-contrast check for unicode characters, behind flags. ([#1969](https://github.com/dequelabs/axe-core/issues/1969)) ([0cd4037](https://github.com/dequelabs/axe-core/commit/0cd40373ff9a080ffcb128ce66f9eaf80f0d19b4)), closes [#1906](https://github.com/dequelabs/axe-core/issues/1906)
- **rule:** identical-links-same-purpose ([#1649](https://github.com/dequelabs/axe-core/issues/1649)) ([9c73f62](https://github.com/dequelabs/axe-core/commit/9c73f62fea2be68cb555c36fc32c79f7ce2697dd))
- **rule:** no-autoplay-audio ([#1946](https://github.com/dequelabs/axe-core/issues/1946)) ([b2373cb](https://github.com/dequelabs/axe-core/commit/b2373cb9ce73a15e79aec86af7edff62c9a4e2b3))
- **svg-img-alt:** rule for when svg needs a title ([#1953](https://github.com/dequelabs/axe-core/issues/1953)) ([9491e09](https://github.com/dequelabs/axe-core/commit/9491e094fe82c4dba45eb253ed18bf0a0165197c))
- deprecate the use doT.js for messages ([#1938](https://github.com/dequelabs/axe-core/issues/1938)) ([a2ddba3](https://github.com/dequelabs/axe-core/commit/a2ddba305003db0540c093f4ad9015c8854cd98d))

### Bug Fixes

- **color-contrast:** properly pass options to check ([#2033](https://github.com/dequelabs/axe-core/issues/2033)) ([26b99c0](https://github.com/dequelabs/axe-core/commit/26b99c0a511bd6fffaaca7535d732f26b39ef46e))
- **commons:** avoid unicode regex encoding in axe.min.js ([#2024](https://github.com/dequelabs/axe-core/issues/2024)) ([ae90dc4](https://github.com/dequelabs/axe-core/commit/ae90dc47521f6047f71befcb3551686cf857208d))
- add tags with dots for wcag sc ([#1849](https://github.com/dequelabs/axe-core/issues/1849)) ([2f1ab36](https://github.com/dequelabs/axe-core/commit/2f1ab36354add65fe77be3e2831278ce37c3bbab))
- compute orientation lock from various transformation func… ([#1937](https://github.com/dequelabs/axe-core/issues/1937)) ([c987de0](https://github.com/dequelabs/axe-core/commit/c987de0ce7cfcde5a280a9d6c643879093df1bcd))
- ignores axe.ping responses that do not contain axe=true ([26cb1fb](https://github.com/dequelabs/axe-core/commit/26cb1fbdd7127c421bb7ca60e07d72385c6e2ea1))
- input[role=button][value='correct'] should pass ([#1897](https://github.com/dequelabs/axe-core/issues/1897)) ([4635fef](https://github.com/dequelabs/axe-core/commit/4635fef8bafd1c1cf916962693d0deee082266cf))
- remove heading from list of widget roles ([#1882](https://github.com/dequelabs/axe-core/issues/1882)) ([a8cbf71](https://github.com/dequelabs/axe-core/commit/a8cbf717ef3aa8b0bf09ddcb17f3a95fd2d1a64a))
- **link-name:** test role=link when there is no href ([#1921](https://github.com/dequelabs/axe-core/issues/1921)) ([6db28bc](https://github.com/dequelabs/axe-core/commit/6db28bc455b1c8937f44346aa232eacc4a1c3457))
- remove isNaN check ([#2010](https://github.com/dequelabs/axe-core/issues/2010)) ([5359b3f](https://github.com/dequelabs/axe-core/commit/5359b3f06ac051963ee61fcef417bcc20bdec55b))
- **aria-allowed-attr:** allow aria-details ([#1956](https://github.com/dequelabs/axe-core/issues/1956)) ([79e1c58](https://github.com/dequelabs/axe-core/commit/79e1c58cad4fdbd1409a0b545981c12f13252432))
- **aria-allowed-role:** allow role combobox on input tel, search, url, and email ([#1850](https://github.com/dequelabs/axe-core/issues/1850)) ([ba75961](https://github.com/dequelabs/axe-core/commit/ba759618ed8068f4eb74b6cd00f002322b20eca5))
- **aria-hidden-focus:** mark as needs review if a modal is open ([#1995](https://github.com/dequelabs/axe-core/issues/1995)) ([28a3553](https://github.com/dequelabs/axe-core/commit/28a35531b97b987e2fd1ad0beb25fbda3822fbd5))
- **aria-required-children:** allow comboboxes with more popup roles ([#1950](https://github.com/dequelabs/axe-core/issues/1950)) ([35a24c0](https://github.com/dequelabs/axe-core/commit/35a24c034520e3c6d95514e3b9d9f2ab6ca10e06))
- **aria-roles:** report error for fallback roles ([#1970](https://github.com/dequelabs/axe-core/issues/1970)) ([a1b7e08](https://github.com/dequelabs/axe-core/commit/a1b7e08f1f8e1c1caff228469cd891d0458680de))
- **aria-valid-attr-value:** mark as needs review for aria-current with invalid value ([#1998](https://github.com/dequelabs/axe-core/issues/1998)) ([39b8eae](https://github.com/dequelabs/axe-core/commit/39b8eae9d3352be4f77bef41abcb8eab268a6809))
- **axe.d.ts:** RunOnly.values should not accept a RunOnlyOption ([#1888](https://github.com/dequelabs/axe-core/issues/1888)) ([b68aa19](https://github.com/dequelabs/axe-core/commit/b68aa19500ffb57fdf370707d7614384ac239ad6))
- **build:** add lang query parameter to helpUrl when builing with a locale ([#1909](https://github.com/dequelabs/axe-core/issues/1909)) ([8c5f9ef](https://github.com/dequelabs/axe-core/commit/8c5f9efd6449f82e410eb7c6a68cfb5304fc66ae))
- **color-contrast:** improve speed and accuracy of code blocks with syntax highlighting ([#2003](https://github.com/dequelabs/axe-core/issues/2003)) ([1b6ab42](https://github.com/dequelabs/axe-core/commit/1b6ab42f72b1ea0d2ed223c6fd63b9b1e54cfa9b))
- **color-contrast:** mark as needs review for text that contains only non-BMP characters ([#2005](https://github.com/dequelabs/axe-core/issues/2005)) ([e559be0](https://github.com/dequelabs/axe-core/commit/e559be041e90951c734de4e7ad70d7299f590cf6))
- **color-contrast:** support IE extension context ([#2008](https://github.com/dequelabs/axe-core/issues/2008)) ([62e31ea](https://github.com/dequelabs/axe-core/commit/62e31ea5034871f572f8bb47dba2596fb1b13063))
- **color-contrast:** take into account parent opacity for foreground color ([#1902](https://github.com/dequelabs/axe-core/issues/1902)) ([8719700](https://github.com/dequelabs/axe-core/commit/87197005d046cc8c845764ff9107683938864c65))
- **getElementStack:** do not add hidden elements to the stack ([#1991](https://github.com/dequelabs/axe-core/issues/1991)) ([759d88d](https://github.com/dequelabs/axe-core/commit/759d88d08af059755d908794038770cc57448252))
- **is-focusable:** use tabindex attribute instead of property ([#1912](https://github.com/dequelabs/axe-core/issues/1912)) ([042a148](https://github.com/dequelabs/axe-core/commit/042a1487df76489483330274933d06fd27b842e0))
- **is-icon-ligature:** ignore whitespace characters ([#1908](https://github.com/dequelabs/axe-core/issues/1908)) ([7d2b2a6](https://github.com/dequelabs/axe-core/commit/7d2b2a6fca992e27bab36ed8ab64b7ba3385d7e5))
- **is-ligature-icon:** rename canvas to canvasContext ([#1880](https://github.com/dequelabs/axe-core/issues/1880)) ([de9885d](https://github.com/dequelabs/axe-core/commit/de9885d5708d6928fa2eb2816351879307a31a5b))
- **isFocusable:** return true for summary element and false for details element with summary child ([#1957](https://github.com/dequelabs/axe-core/issues/1957)) ([34ec2d7](https://github.com/dequelabs/axe-core/commit/34ec2d7326786347f8704786e886fc8d13dd3f9b))
- **listitem:** clarify that li elements must be contained in a list or role=list ([#1894](https://github.com/dequelabs/axe-core/issues/1894)) ([6d8cfee](https://github.com/dequelabs/axe-core/commit/6d8cfee91f0f0b5dcacba7ffb0b3d6505862e6b7))
- **locales:** fix incompeteMessageFallback to be a string rather than an object ([#1853](https://github.com/dequelabs/axe-core/issues/1853)) ([88677a9](https://github.com/dequelabs/axe-core/commit/88677a93d0ffe32d7305984314a37e623fb51153))
- **meta-viewport:** mark as a best-practice rule instead of wcag failure ([#1960](https://github.com/dequelabs/axe-core/issues/1960)) ([766f962](https://github.com/dequelabs/axe-core/commit/766f96210d05d35cab0139839db4f009b1139ce1))
- **only-listitem:** add message about invalid role on li elements ([#1954](https://github.com/dequelabs/axe-core/issues/1954)) ([c3049ab](https://github.com/dequelabs/axe-core/commit/c3049abaccff72412ec3d58fab9b386fe8a2ae5a))
- **page-has-main:** do not find hidden elements ([#2001](https://github.com/dequelabs/axe-core/issues/2001)) ([6429e60](https://github.com/dequelabs/axe-core/commit/6429e608f082db76b4cc445679b61a6e0ab8f034))
- **page-no-duplicate-main:** do not fail for duplicate hidden elements ([#2000](https://github.com/dequelabs/axe-core/issues/2000)) ([414dfb1](https://github.com/dequelabs/axe-core/commit/414dfb1c9a4ade645ce60e8918e8143fe58b3eb6))
- **preload:** reject promise `axe.utils.preload` when XHR fails ([#2009](https://github.com/dequelabs/axe-core/issues/2009)) ([b406b1f](https://github.com/dequelabs/axe-core/commit/b406b1fd09d72f9193d5b4011fa6f24bd33e3576))
- **region:** allow content in roles with implicit aria-live ([#2002](https://github.com/dequelabs/axe-core/issues/2002)) ([a8d829e](https://github.com/dequelabs/axe-core/commit/a8d829e081dabb62a5247e8956adbf7a2ef000a2))
- **region:** return outermost regionless node instead of html ([#1980](https://github.com/dequelabs/axe-core/issues/1980)) ([8d77be2](https://github.com/dequelabs/axe-core/commit/8d77be206e11537e8b509d593707c98143181bfa))
- **region-rule:** allow live regions with explicit roles ([#1999](https://github.com/dequelabs/axe-core/issues/1999)) ([b49bd95](https://github.com/dequelabs/axe-core/commit/b49bd9547b7d8ac392ebf958356f90aca7e48a38))
- **run:** throw error if axe.run is called after a run has started but not completed ([#1914](https://github.com/dequelabs/axe-core/issues/1914)) ([3252a02](https://github.com/dequelabs/axe-core/commit/3252a020ffd372e9583d39c989affd3d3b22957b))
- **server-side-image-map:** return as needs review rather than failure ([#1898](https://github.com/dequelabs/axe-core/issues/1898)) ([d544856](https://github.com/dequelabs/axe-core/commit/d5448567b23de8289443c9c314b34b3140f68c30))
- **tabindex:** don't error when tabindex property is overridden ([#1910](https://github.com/dequelabs/axe-core/issues/1910)) ([6b82a4c](https://github.com/dequelabs/axe-core/commit/6b82a4c513a1d5be78dcc54ad90a90768613b918))
- **td-has-headers:** greatly improve performance of td-has-headers rule ([#1887](https://github.com/dequelabs/axe-core/issues/1887)) ([a550309](https://github.com/dequelabs/axe-core/commit/a550309255b025cb1e63710af2142f2c02d79657))
- removes flaky test in axe Pro api check ([b2bdcd1](https://github.com/dequelabs/axe-core/commit/b2bdcd13e7623d3111f7035f2e951ff6b330132c))
- **typings:** add proper return value to getRule ([#1900](https://github.com/dequelabs/axe-core/issues/1900)) ([4d907f8](https://github.com/dequelabs/axe-core/commit/4d907f86b0152122f92cceae0b242e09aff0f49a))
- **unicode:** stop parsing escaped unicode strings ([#1997](https://github.com/dequelabs/axe-core/issues/1997)) ([7447d03](https://github.com/dequelabs/axe-core/commit/7447d03bcfd118897d8114fded1ea8a42f3da08f))

## [3.4.2](https://github.com/dequelabs/axe-core/compare/v3.4.1...v3.4.2) (2020-02-04)

### Bug Fixes

- **color-contrast:** support IE extension context ([#2008](https://github.com/dequelabs/axe-core/issues/2008)) ([cd651a0](https://github.com/dequelabs/axe-core/commit/cd651a0713fa2f4b307cc7fc2be033f8636b40d2))
- **unicode:** stop parsing escaped unicode strings ([#1997](https://github.com/dequelabs/axe-core/issues/1997)) ([523a31c](https://github.com/dequelabs/axe-core/commit/523a31c19fefd330e0b4f4c45f51d400c6f66164))

### [3.4.1](https://github.com/dequelabs/axe-core/compare/v3.4.0...v3.4.1) (2019-12-11)

### Bug Fixes

- ignores axe.ping responses that do not contain axe=true ([7d8aa42](https://github.com/dequelabs/axe-core/commit/7d8aa42))
- input[role=button][value='correct'] should pass ([#1897](https://github.com/dequelabs/axe-core/issues/1897)) ([3aba02c](https://github.com/dequelabs/axe-core/commit/3aba02c))
- remove heading from list of widget roles ([#1882](https://github.com/dequelabs/axe-core/issues/1882)) ([beb458f](https://github.com/dequelabs/axe-core/commit/beb458f))
- **listitem:** clarify that li elements must be contained in a list or role=list ([#1894](https://github.com/dequelabs/axe-core/issues/1894)) ([8fa0964](https://github.com/dequelabs/axe-core/commit/8fa0964))
- removes flaky test in axe Pro api check ([f2b3b54](https://github.com/dequelabs/axe-core/commit/f2b3b54))
- **aria-allowed-role:** allow role combobox on input tel, search, url, and email ([#1850](https://github.com/dequelabs/axe-core/issues/1850)) ([75d3c8b](https://github.com/dequelabs/axe-core/commit/75d3c8b))
- **axe.d.ts:** RunOnly.values should not accept a RunOnlyOption ([#1888](https://github.com/dequelabs/axe-core/issues/1888)) ([94b1466](https://github.com/dequelabs/axe-core/commit/94b1466))
- **build:** add lang query parameter to helpUrl when builing with a locale ([#1909](https://github.com/dequelabs/axe-core/issues/1909)) ([a2f0247](https://github.com/dequelabs/axe-core/commit/a2f0247))
- **color-contrast:** take into account parent opacity for foreground color ([#1902](https://github.com/dequelabs/axe-core/issues/1902)) ([639c41b](https://github.com/dequelabs/axe-core/commit/639c41b))
- **is-focusable:** use tabindex attribute instead of property ([#1912](https://github.com/dequelabs/axe-core/issues/1912)) ([aa5314d](https://github.com/dequelabs/axe-core/commit/aa5314d))
- **is-icon-ligature:** ignore whitespace characters ([#1908](https://github.com/dequelabs/axe-core/issues/1908)) ([77fc838](https://github.com/dequelabs/axe-core/commit/77fc838))
- **is-ligature-icon:** rename canvas to canvasContext ([#1880](https://github.com/dequelabs/axe-core/issues/1880)) ([604ba4f](https://github.com/dequelabs/axe-core/commit/604ba4f))
- **link-name:** test role=link when there is no href ([#1921](https://github.com/dequelabs/axe-core/issues/1921)) ([e839c57](https://github.com/dequelabs/axe-core/commit/e839c57))
- **locales:** fix incompeteMessageFallback to be a string rather than an object ([#1853](https://github.com/dequelabs/axe-core/issues/1853)) ([02a1d8a](https://github.com/dequelabs/axe-core/commit/02a1d8a))
- **run:** throw error if axe.run is called after a run has started but not completed ([#1914](https://github.com/dequelabs/axe-core/issues/1914)) ([290d125](https://github.com/dequelabs/axe-core/commit/290d125))
- **server-side-image-map:** return as needs review rather than failure ([#1898](https://github.com/dequelabs/axe-core/issues/1898)) ([ce73af9](https://github.com/dequelabs/axe-core/commit/ce73af9))
- **tabindex:** don't error when tabindex property is overridden ([#1910](https://github.com/dequelabs/axe-core/issues/1910)) ([e6875ee](https://github.com/dequelabs/axe-core/commit/e6875ee))
- **td-has-headers:** greatly improve performance of td-has-headers rule ([#1887](https://github.com/dequelabs/axe-core/issues/1887)) ([a588cad](https://github.com/dequelabs/axe-core/commit/a588cad))
- **typings:** add proper return value to getRule ([#1900](https://github.com/dequelabs/axe-core/issues/1900)) ([0d7c3d2](https://github.com/dequelabs/axe-core/commit/0d7c3d2))

## [3.4.0](https://github.com/dequelabs/axe-core/compare/v3.3.2...v3.4.0) (2019-10-18)

### Bug Fixes

- **aria-allowed-attr:** allow 'aria-readonly' on listbox ([#1825](https://github.com/dequelabs/axe-core/issues/1825)) ([15f5d2d](https://github.com/dequelabs/axe-core/commit/15f5d2d))
- **aria-form-field-name-matches:** don't test combobox elements when they have a child input ([#1742](https://github.com/dequelabs/axe-core/issues/1742)) ([f0be6dc](https://github.com/dequelabs/axe-core/commit/f0be6dc))
- **aria-required-children:** allow combobox to own a searchbox ([#1708](https://github.com/dequelabs/axe-core/issues/1708)) ([42158ac](https://github.com/dequelabs/axe-core/commit/42158ac))
- **aria-required-children:** allow reviewEmpty nodes to have empty children ([#1791](https://github.com/dequelabs/axe-core/issues/1791)) ([a5d727c](https://github.com/dequelabs/axe-core/commit/a5d727c))
- **aria-valid-attr-value:** fix incomplete translation message ([#1739](https://github.com/dequelabs/axe-core/issues/1739)) ([a0f3eef](https://github.com/dequelabs/axe-core/commit/a0f3eef))
- **color-contrast:** ignore nodes that don't contain text ([#1837](https://github.com/dequelabs/axe-core/issues/1837)) ([223a4bc](https://github.com/dequelabs/axe-core/commit/223a4bc))
- **color-contrast-matches:** don't check aria-disabled explicit label element ([#1741](https://github.com/dequelabs/axe-core/issues/1741)) ([5bb566f](https://github.com/dequelabs/axe-core/commit/5bb566f))
- **configure:** use translations for failure summaries ([#1808](https://github.com/dequelabs/axe-core/issues/1808)) ([5e53d7b](https://github.com/dequelabs/axe-core/commit/5e53d7b))
- **flatten-tree:** do not call deprecated getDistributedNodes ([#1729](https://github.com/dequelabs/axe-core/issues/1729)) ([46a5d11](https://github.com/dequelabs/axe-core/commit/46a5d11))
- **form-field-multiple-label:** incomplete rather than fail for multiple labels ([#1798](https://github.com/dequelabs/axe-core/issues/1798)) ([0bdaa2b](https://github.com/dequelabs/axe-core/commit/0bdaa2b))
- **get-background-color:** scroll element into view horizontally ([#1845](https://github.com/dequelabs/axe-core/issues/1845)) ([50df70a](https://github.com/dequelabs/axe-core/commit/50df70a))
- **get-selector:** don't throw error for disconnected fragment ([#1802](https://github.com/dequelabs/axe-core/issues/1802)) ([bb6591b](https://github.com/dequelabs/axe-core/commit/bb6591b))
- **label-content-name-mismatch:** ignore ligature fonts ([#1829](https://github.com/dequelabs/axe-core/issues/1829)) ([683e005](https://github.com/dequelabs/axe-core/commit/683e005))
- allows all roles on img tag with no alt attribute ([929085a](https://github.com/dequelabs/axe-core/commit/929085a))
- replace incorrect tag for meta-refresh rule ([#1844](https://github.com/dequelabs/axe-core/issues/1844)) ([754d56b](https://github.com/dequelabs/axe-core/commit/754d56b))
- update tags to wcag21aa for rule avoid-inline-spacing ([#1757](https://github.com/dequelabs/axe-core/issues/1757)) ([973d48f](https://github.com/dequelabs/axe-core/commit/973d48f))
- **label-content-name-mismatch:** ignore private space unicode ([#1822](https://github.com/dequelabs/axe-core/issues/1822)) ([b634c34](https://github.com/dequelabs/axe-core/commit/b634c34))
- **scrollable-region-focus:** ignore scrollable regions without content ([#1788](https://github.com/dequelabs/axe-core/issues/1788)) ([b36754e](https://github.com/dequelabs/axe-core/commit/b36754e))
- **utils:** Fix error in IE when getting scroll state on page with SVG elements. Closes [#525](https://github.com/dequelabs/axe-core/issues/525) ([#1820](https://github.com/dequelabs/axe-core/issues/1820)) ([9a32f6f](https://github.com/dequelabs/axe-core/commit/9a32f6f))

### Features

- **audit:** add lang query paramenter to help urls ([#1794](https://github.com/dequelabs/axe-core/issues/1794)) ([2d1c8a6](https://github.com/dequelabs/axe-core/commit/2d1c8a6))
- **configure:** accept ver property as axeVersion fallback ([#1812](https://github.com/dequelabs/axe-core/issues/1812)) ([4ebcde8](https://github.com/dequelabs/axe-core/commit/4ebcde8))
- **configure:** add axeVersion property that checks compatibility of axe.version ([#1793](https://github.com/dequelabs/axe-core/issues/1793)) ([18fb8c8](https://github.com/dequelabs/axe-core/commit/18fb8c8))
- **fieldset, group-labelledby:** deprecate fieldset and group-labelledby checks ([#1740](https://github.com/dequelabs/axe-core/issues/1740)) ([ec9b762](https://github.com/dequelabs/axe-core/commit/ec9b762))
- **i18n:** add spanish translation ([#1758](https://github.com/dequelabs/axe-core/issues/1758)) ([e9f821d](https://github.com/dequelabs/axe-core/commit/e9f821d)), closes [#1757](https://github.com/dequelabs/axe-core/issues/1757)
- Add axe.utils.assert method ([2f10d24](https://github.com/dequelabs/axe-core/commit/2f10d24))
- **is-visible:** add support for clip-path techniques ([#1706](https://github.com/dequelabs/axe-core/issues/1706)) ([8ab262a](https://github.com/dequelabs/axe-core/commit/8ab262a))
- **radiogroup, checkboxgroup:** deprecate radiogroup and checkboxgroup rules ([#1640](https://github.com/dequelabs/axe-core/issues/1640)) ([6d30880](https://github.com/dequelabs/axe-core/commit/6d30880))
- Add SerialVirtualNode class ([82d01b0](https://github.com/dequelabs/axe-core/commit/82d01b0))
- pt_BR localization ([#1756](https://github.com/dequelabs/axe-core/issues/1756)) ([330e2ec](https://github.com/dequelabs/axe-core/commit/330e2ec))
- **rule:** aria-roledescription ([#1745](https://github.com/dequelabs/axe-core/issues/1745)) ([16682fd](https://github.com/dequelabs/axe-core/commit/16682fd))
- **runVirtualNode:** Allow serialised nodes [experimental](<[512d51b](https://github.com/dequelabs/axe-core/commit/512d51b)>)
- **video-description:** deprecate video-description rule ([#1737](https://github.com/dequelabs/axe-core/issues/1737)) ([e91c25f](https://github.com/dequelabs/axe-core/commit/e91c25f))

## [3.3.3](https://github.com/dequelabs/axe-core/compare/v3.3.2...v3.3.3) (2020-02-04)

### Bug Fixes

- **color-contrast:** support IE extension context ([#2008](https://github.com/dequelabs/axe-core/issues/2008)) ([cd651a0](https://github.com/dequelabs/axe-core/commit/cd651a0713fa2f4b307cc7fc2be033f8636b40d2))
- **unicode:** stop parsing escaped unicode strings ([#1997](https://github.com/dequelabs/axe-core/issues/1997)) ([523a31c](https://github.com/dequelabs/axe-core/commit/523a31c19fefd330e0b4f4c45f51d400c6f66164))

### [3.3.2](https://github.com/dequelabs/axe-core/compare/v3.3.1...v3.3.2) (2019-08-12)

### Bug Fixes

- **aria-form-field-name-matches:** don't test combobox elements when they have a child input ([#1742](https://github.com/dequelabs/axe-core/issues/1742)) ([5ac278f](https://github.com/dequelabs/axe-core/commit/5ac278f))
- **aria-valid-attr-value:** fix incomplete translation message ([#1739](https://github.com/dequelabs/axe-core/issues/1739)) ([6909604](https://github.com/dequelabs/axe-core/commit/6909604))
- **flatten-tree:** do not call deprecated getDistributedNodes ([#1729](https://github.com/dequelabs/axe-core/issues/1729)) ([48ddf9d](https://github.com/dequelabs/axe-core/commit/48ddf9d))
- update tags to wcag21aa for rule avoid-inline-spacing ([#1757](https://github.com/dequelabs/axe-core/issues/1757)) ([f534a6b](https://github.com/dequelabs/axe-core/commit/f534a6b))

## [3.3.1](https://github.com/dequelabs/axe-core/compare/v3.3.0...v3.3.1) (2019-07-23)

### Bug Fixes

- **accessible-text-virtual:** sanitize attributes on start node ([#1694](https://github.com/dequelabs/axe-core/issues/1694)) ([c0bb08c](https://github.com/dequelabs/axe-core/commit/c0bb08c))
- **axe.d.ts:** add optional xpath property to NodeResult ([#1642](https://github.com/dequelabs/axe-core/issues/1642)) ([287ef9c](https://github.com/dequelabs/axe-core/commit/287ef9c))
- **get-background-color:** No longer calculate color from non-opaque overlapping element ([#1644](https://github.com/dequelabs/axe-core/issues/1644)) ([d45f81e](https://github.com/dequelabs/axe-core/commit/d45f81e))
- **get-background-color:** No longer calculate color from non-opaque overlapping elm ([f1c2310](https://github.com/dequelabs/axe-core/commit/f1c2310))
- **get-background-color:** process tbody, thead, and tfoot when getting background color ([#1653](https://github.com/dequelabs/axe-core/issues/1653)) ([e114bfd](https://github.com/dequelabs/axe-core/commit/e114bfd))
- enable running axe-core in strict CSPs ([#1707](https://github.com/dequelabs/axe-core/issues/1707)) ([cc5bd59](https://github.com/dequelabs/axe-core/commit/cc5bd59))
- **image-redundant-alt:** check for parent before calculating text ([#1705](https://github.com/dequelabs/axe-core/issues/1705)) ([1adbd02](https://github.com/dequelabs/axe-core/commit/1adbd02))
- **th-has-data-cells:** empty cells will now pass ([#1659](https://github.com/dequelabs/axe-core/issues/1659)) ([c7489ab](https://github.com/dequelabs/axe-core/commit/c7489ab))
- **types:** add new properties to RunOptions ([#1697](https://github.com/dequelabs/axe-core/issues/1697)) ([02aa36c](https://github.com/dequelabs/axe-core/commit/02aa36c)), closes [#1696](https://github.com/dequelabs/axe-core/issues/1696)
- **valid-attr-value:** allow aria-describedby to return needs review ([#1671](https://github.com/dequelabs/axe-core/issues/1671)) ([2390925](https://github.com/dequelabs/axe-core/commit/2390925))
- **color-contrast:** add px unit to error messages ([#1634](https://github.com/dequelabs/axe-core/issues/1634)) ([1712e46](https://github.com/dequelabs/axe-core/commit/1712e46))

### Tests

- **examples:** do not fail tests if deque.com has violations ([#1686](https://github.com/dequelabs/axe-core/issues/1686)) ([2118360](https://github.com/dequelabs/axe-core/commit/2118360))
- ensure locale files are valid ([#1673](https://github.com/dequelabs/axe-core/issues/1673)) ([588f9b5](https://github.com/dequelabs/axe-core/commit/588f9b5))
- require new release rule help docs to be active before creating release ([#1700](https://github.com/dequelabs/axe-core/issues/1700)) ([e9f9c18](https://github.com/dequelabs/axe-core/commit/e9f9c18))

## [3.3.0](https://github.com/dequelabs/axe-core/compare/v3.2.2...v3.3.0) (2019-07-08)

### Bug Fixes

- add SC 131 to rule aria hidden focus ([#1474](https://github.com/dequelabs/axe-core/issues/1474)) ([8da9a0d](https://github.com/dequelabs/axe-core/commit/8da9a0d))
- Add treegrid as allowed parent to rowgroup ([#1435](https://github.com/dequelabs/axe-core/issues/1435)) ([94e9893](https://github.com/dequelabs/axe-core/commit/94e9893)), closes [#1386](https://github.com/dequelabs/axe-core/issues/1386)
- arguments for gather function in build template ([#1605](https://github.com/dequelabs/axe-core/issues/1605)) ([753ecf4](https://github.com/dequelabs/axe-core/commit/753ecf4))
- check if property exists in cache of flattenedTree ([#1536](https://github.com/dequelabs/axe-core/issues/1536)) ([51c2e19](https://github.com/dequelabs/axe-core/commit/51c2e19))
- **aria-valid-attr-value:** allow aria-owns to pass when element is not in the DOM ([#1526](https://github.com/dequelabs/axe-core/issues/1526)) ([f835ed8](https://github.com/dequelabs/axe-core/commit/f835ed8))
- deprecate na reporter ([#1625](https://github.com/dequelabs/axe-core/issues/1625)) ([3e807f0](https://github.com/dequelabs/axe-core/commit/3e807f0))
- Exclude iframe for html-has-lang rule (Issue 1424) ([#1430](https://github.com/dequelabs/axe-core/issues/1430)) ([98b5ed2](https://github.com/dequelabs/axe-core/commit/98b5ed2))
- Include body as part of background color checks when element does not intersect ([#1520](https://github.com/dequelabs/axe-core/issues/1520)) ([55820cf](https://github.com/dequelabs/axe-core/commit/55820cf))
- make nullable impact properties have nullable types to match API docs ([#1477](https://github.com/dequelabs/axe-core/issues/1477)) ([efaed91](https://github.com/dequelabs/axe-core/commit/efaed91))
- Only load Promise polyfill if window.Promise is missing [[#1468](https://github.com/dequelabs/axe-core/issues/1468)](<[#1470](https://github.com/dequelabs/axe-core/issues/1470)>) ([1d70306](https://github.com/dequelabs/axe-core/commit/1d70306))
- Prevent error when using `<select name="attributes">` [[#1397](https://github.com/dequelabs/axe-core/issues/1397)](<[#1432](https://github.com/dequelabs/axe-core/issues/1432)>) ([b477e0d](https://github.com/dequelabs/axe-core/commit/b477e0d))
- remove unnecessary comments ([6ed71c9](https://github.com/dequelabs/axe-core/commit/6ed71c9))
- role=radio should not require aria-checked ([#1448](https://github.com/dequelabs/axe-core/issues/1448)) ([0643cbd](https://github.com/dequelabs/axe-core/commit/0643cbd))
- Scroll state had top and left properties flipped ([#1469](https://github.com/dequelabs/axe-core/issues/1469)) ([2ba83d3](https://github.com/dequelabs/axe-core/commit/2ba83d3))
- **skip-link,region:** Allow multiple skiplinks at page top ([#1496](https://github.com/dequelabs/axe-core/issues/1496)) ([642c8f1](https://github.com/dequelabs/axe-core/commit/642c8f1))
- use execa instead of child_process.spawn ([461ce83](https://github.com/dequelabs/axe-core/commit/461ce83))
- **aria-allowed-attr:** allow figure role ([#1558](https://github.com/dequelabs/axe-core/issues/1558)) ([a4b5240](https://github.com/dequelabs/axe-core/commit/a4b5240))
- **aria-required-attr:** allow aria-valuenow to pass on elements with value ([#1579](https://github.com/dequelabs/axe-core/issues/1579)) ([3893e04](https://github.com/dequelabs/axe-core/commit/3893e04))
- **aria-required-attr:** don't require aria-valuemin/max ([#1529](https://github.com/dequelabs/axe-core/issues/1529)) ([80ae444](https://github.com/dequelabs/axe-core/commit/80ae444))
- **aria-valid-attr-value:** allow aria-controls to pass when element is not in the DOM ([a7842e5](https://github.com/dequelabs/axe-core/commit/a7842e5))
- **flatten-tree:** do not call deprecated getDistributedNodes ([#1577](https://github.com/dequelabs/axe-core/issues/1577)) ([93d59f4](https://github.com/dequelabs/axe-core/commit/93d59f4))
- **image-redundant-alt:** prevent redundant issues of image tree ([#1616](https://github.com/dequelabs/axe-core/issues/1616)) ([af81897](https://github.com/dequelabs/axe-core/commit/af81897))
- **isSkipLink:** cache first page link ([#1525](https://github.com/dequelabs/axe-core/issues/1525)) ([6a1bcba](https://github.com/dequelabs/axe-core/commit/6a1bcba))
- **matches-selector:** don't call matches function if none exist on the element ([#1613](https://github.com/dequelabs/axe-core/issues/1613)) ([7581592](https://github.com/dequelabs/axe-core/commit/7581592))
- **multiple-label:** considers explicit labels in the same shadow tree ([#1584](https://github.com/dequelabs/axe-core/issues/1584)) ([b9a324a](https://github.com/dequelabs/axe-core/commit/b9a324a))
- **multiple-label:** no longer raises issue when aria-labelledby overrides how AT views multiple labels ([#1538](https://github.com/dequelabs/axe-core/issues/1538)) ([fbae36b](https://github.com/dequelabs/axe-core/commit/fbae36b))
- **prettier:** ignore generated api doc files ([#1522](https://github.com/dequelabs/axe-core/issues/1522)) ([c118da0](https://github.com/dequelabs/axe-core/commit/c118da0))
- **raw-reporter:** do not output `DqElement`s ([#1513](https://github.com/dequelabs/axe-core/issues/1513)) ([3babcb6](https://github.com/dequelabs/axe-core/commit/3babcb6))
- **scrollable-region-focusable:** exclude overflow:hidden as not scrollable ([#1599](https://github.com/dequelabs/axe-core/issues/1599)) ([940de07](https://github.com/dequelabs/axe-core/commit/940de07))
- **utils:** make cache global instead of only setup in axe.run ([#1535](https://github.com/dequelabs/axe-core/issues/1535)) ([91a04c5](https://github.com/dequelabs/axe-core/commit/91a04c5))
- **virtual-node:** fix hasClass to work with svg elements ([#1603](https://github.com/dequelabs/axe-core/issues/1603)) ([9d83662](https://github.com/dequelabs/axe-core/commit/9d83662))

### Features

- **autocomplete-matches:** use virtualNode only lookups ([#1604](https://github.com/dequelabs/axe-core/issues/1604)) ([b32d4fe](https://github.com/dequelabs/axe-core/commit/b32d4fe))
- **autocomplete-valid:** allow autocomplete-valid to be run entirely off of a virtual node ([#1591](https://github.com/dequelabs/axe-core/issues/1591)) ([b3e0873](https://github.com/dequelabs/axe-core/commit/b3e0873))
- **qsa, flatten-tree:** abstract Node and Element apis in virtual tree ([#1562](https://github.com/dequelabs/axe-core/issues/1562)) ([2f2e590](https://github.com/dequelabs/axe-core/commit/2f2e590))
- **reporter:** adds the rawEnv reporter which wraps raw and env data ([#1556](https://github.com/dequelabs/axe-core/issues/1556)) ([ed15ed3](https://github.com/dequelabs/axe-core/commit/ed15ed3))
- **role-img-alt:** Split rule for role=img with no accessible name ([#1586](https://github.com/dequelabs/axe-core/issues/1586)) ([2416ed3](https://github.com/dequelabs/axe-core/commit/2416ed3))
- **rule:** add additional elements to check for incomplete with required children ([#1547](https://github.com/dequelabs/axe-core/issues/1547)) ([3726901](https://github.com/dequelabs/axe-core/commit/3726901))
- **rule:** add more perf timing metrics to rules ([#1472](https://github.com/dequelabs/axe-core/issues/1472)) ([98646e5](https://github.com/dequelabs/axe-core/commit/98646e5))
- **rule,check:** add new apis to run a rule synchronously ([#1467](https://github.com/dequelabs/axe-core/issues/1467)) ([84094a1](https://github.com/dequelabs/axe-core/commit/84094a1))
- add AbstractVirtualNode for linting ([#1627](https://github.com/dequelabs/axe-core/issues/1627)) ([a072ed2](https://github.com/dequelabs/axe-core/commit/a072ed2))
- **rule:** Adding landmark-is-unique rule ([#1394](https://github.com/dequelabs/axe-core/issues/1394)) ([0088e94](https://github.com/dequelabs/axe-core/commit/0088e94))
- **rule:** Inline text spacing must be adjustable with custom stylesheets ([#1446](https://github.com/dequelabs/axe-core/issues/1446)) ([430b07f](https://github.com/dequelabs/axe-core/commit/430b07f))
- Improve perf of axe.run [WWD-1821](<[#1503](https://github.com/dequelabs/axe-core/issues/1503)>) ([a84431a](https://github.com/dequelabs/axe-core/commit/a84431a))
- **rule:** New aria-input-field-label rule ([#1610](https://github.com/dequelabs/axe-core/issues/1610)) ([73d5273](https://github.com/dequelabs/axe-core/commit/73d5273))
- **rule:** New aria-toggle-field-label rule ([#1450](https://github.com/dequelabs/axe-core/issues/1450)) ([69a9c3b](https://github.com/dequelabs/axe-core/commit/69a9c3b))
- **rule:** Scrollable region focusable ([#1396](https://github.com/dequelabs/axe-core/issues/1396)) ([861371a](https://github.com/dequelabs/axe-core/commit/861371a))
- **rules:** split button name rule into button only and button input rules ([#1615](https://github.com/dequelabs/axe-core/issues/1615)) ([ce20fbf](https://github.com/dequelabs/axe-core/commit/ce20fbf))
- **run-virtual-rule:** new api to run rules using only virtual nodes ([#1594](https://github.com/dequelabs/axe-core/issues/1594)) ([4e12217](https://github.com/dequelabs/axe-core/commit/4e12217))
- **utils:** add support for complex CSS selectors ([#1494](https://github.com/dequelabs/axe-core/issues/1494)) ([a9f9ee5](https://github.com/dequelabs/axe-core/commit/a9f9ee5)), closes [#1493](https://github.com/dequelabs/axe-core/issues/1493)
- **utils:** Update CSSOM for nested [@import](https://github.com/import) computation ([#1339](https://github.com/dequelabs/axe-core/issues/1339)) ([a4e177b](https://github.com/dequelabs/axe-core/commit/a4e177b))

### Tests

- createHTMLDocument needs mandatory title when invoked in IE ([#1442](https://github.com/dequelabs/axe-core/issues/1442)) ([8542773](https://github.com/dequelabs/axe-core/commit/8542773))
- disable es6 syntax usage within tests directory ([#1569](https://github.com/dequelabs/axe-core/issues/1569)) ([9b13508](https://github.com/dequelabs/axe-core/commit/9b13508))
- fix flakey test ([#1573](https://github.com/dequelabs/axe-core/issues/1573)) ([fb38ce7](https://github.com/dequelabs/axe-core/commit/fb38ce7))
- Fix invalid test html ([#1502](https://github.com/dequelabs/axe-core/issues/1502)) ([8d85082](https://github.com/dequelabs/axe-core/commit/8d85082))
- fix test for Safari ([#1557](https://github.com/dequelabs/axe-core/issues/1557)) ([1bac69e](https://github.com/dequelabs/axe-core/commit/1bac69e))
- fix tests failing in IE11 ([#1570](https://github.com/dequelabs/axe-core/issues/1570)) ([2102eca](https://github.com/dequelabs/axe-core/commit/2102eca))
- only run IE11 tests in appveyor ([#1571](https://github.com/dequelabs/axe-core/issues/1571)) ([35261ef](https://github.com/dequelabs/axe-core/commit/35261ef))
- watch integration html and json files ([#1598](https://github.com/dequelabs/axe-core/issues/1598)) ([3de0b05](https://github.com/dequelabs/axe-core/commit/3de0b05))

## [3.2.3](https://github.com/dequelabs/axe-core/compare/v3.2.2...v3.2.3) (2020-02-04)

### Bug Fixes

- **color-contrast:** support IE extension context ([#2008](https://github.com/dequelabs/axe-core/issues/2008)) ([cd651a0](https://github.com/dequelabs/axe-core/commit/cd651a0713fa2f4b307cc7fc2be033f8636b40d2))
- **unicode:** stop parsing escaped unicode strings ([#1997](https://github.com/dequelabs/axe-core/issues/1997)) ([523a31c](https://github.com/dequelabs/axe-core/commit/523a31c19fefd330e0b4f4c45f51d400c6f66164))

## [3.2.2](https://github.com/dequelabs/axe-core/compare/v3.2.0...v3.2.2) (2019-03-07)

### Bug Fixes

- Avoid "screen is not defined" error [[#1404](https://github.com/dequelabs/axe-core/issues/1404)](<[#1415](https://github.com/dequelabs/axe-core/issues/1415)>) ([c9653a5](https://github.com/dequelabs/axe-core/commit/c9653a5))

## [3.2.1](https://github.com/dequelabs/axe-core/compare/v3.2.0...v3.2.1) (2019-03-06)

### Bug Fixes

- Avoid require conflict with Cypress [[#1405](https://github.com/dequelabs/axe-core/issues/1405)](<[#1406](https://github.com/dequelabs/axe-core/issues/1406)>) ([30aa570](https://github.com/dequelabs/axe-core/commit/30aa570))

# [3.2.0](https://github.com/dequelabs/axe-core/compare/v3.0.3...v3.2.0) (2019-03-04)

### Bug Fixes

- **aria-allowed-role:** Allow iframe role=none ([a4fa44d](https://github.com/dequelabs/axe-core/commit/a4fa44d))
- **color-contrast:** Prevent crash on large inline elments [#1306](https://github.com/dequelabs/axe-core/issues/1306) ([#1341](https://github.com/dequelabs/axe-core/issues/1341)) ([e1bcafc](https://github.com/dequelabs/axe-core/commit/e1bcafc))
- **commons:** Allow any node in aria.getRole ([#1258](https://github.com/dequelabs/axe-core/issues/1258)) ([26fa49a](https://github.com/dequelabs/axe-core/commit/26fa49a)), closes [#1163](https://github.com/dequelabs/axe-core/issues/1163)
- **i18n:** Fix and add Japanese translation ([#1368](https://github.com/dequelabs/axe-core/issues/1368)) ([74fa0a4](https://github.com/dequelabs/axe-core/commit/74fa0a4), [#1291](https://github.com/dequelabs/axe-core/issues/1291)) ([f450176](https://github.com/dequelabs/axe-core/commit/f450176), [#1332](https://github.com/dequelabs/axe-core/issues/1332)) ([0a03c8f](https://github.com/dequelabs/axe-core/commit/0a03c8f), [#1107](https://github.com/dequelabs/axe-core/issues/1107)) ([8138e55](https://github.com/dequelabs/axe-core/commit/8138e55))
- **messages:** Change messages from "page" to "document" where appropriate ([#1156](https://github.com/dequelabs/axe-core/issues/1156)) ([49dff2b](https://github.com/dequelabs/axe-core/commit/49dff2b)), closes [#983](https://github.com/dequelabs/axe-core/issues/983) [#983](https://github.com/dequelabs/axe-core/issues/983)
- **rule:** Frame-title applies to wcag242 ([#1312](https://github.com/dequelabs/axe-core/issues/1312)) ([9225ae0](https://github.com/dequelabs/axe-core/commit/9225ae0))
- **rule:** Prevent th-has-data-cells from crashing on empty rows ([#1285](https://github.com/dequelabs/axe-core/issues/1285)) ([88017be](https://github.com/dequelabs/axe-core/commit/88017be))
- **typedefs:** Do not require brand and application ([#1264](https://github.com/dequelabs/axe-core/issues/1264)) ([59465dc](https://github.com/dequelabs/axe-core/commit/59465dc)), closes [/github.com/dequelabs/axe-webdriverjs/blob/v2.0.1/lib/axe-injector.js#L28](https://github.com//github.com/dequelabs/axe-webdriverjs/blob/v2.0.1/lib/axe-injector.js/issues/L28)
- Add Banner comment in generated axe files ([#1112](https://github.com/dequelabs/axe-core/issues/1112)) ([e4788bf](https://github.com/dequelabs/axe-core/commit/e4788bf))
- Allow div groups for dlitem rule ([#1284](https://github.com/dequelabs/axe-core/issues/1284)) ([d76cd36](https://github.com/dequelabs/axe-core/commit/d76cd36))
- Allow role presentation and none on object-alt rule ([#1224](https://github.com/dequelabs/axe-core/issues/1224)) ([d475a17](https://github.com/dequelabs/axe-core/commit/d475a17))
- Avoid IE problems by using nodeName instead of tagName ([#1219](https://github.com/dequelabs/axe-core/issues/1219)) ([cf86ff5](https://github.com/dequelabs/axe-core/commit/cf86ff5))
- Better unsupported attribute support for aria-roledescription ([#1382](https://github.com/dequelabs/axe-core/issues/1382)) ([93f721e](https://github.com/dequelabs/axe-core/commit/93f721e)), closes [#1216](https://github.com/dequelabs/axe-core/issues/1216)
- Consider element's accessible names when labels are hidden ([#1187](https://github.com/dequelabs/axe-core/issues/1187)) ([b91b624](https://github.com/dequelabs/axe-core/commit/b91b624)), closes [#1176](https://github.com/dequelabs/axe-core/issues/1176)
- Correct autocomplete appropriate to handle state terms ([#1121](https://github.com/dequelabs/axe-core/issues/1121)) ([35a4d11](https://github.com/dequelabs/axe-core/commit/35a4d11))
- Correct autocomplete street address ([#1217](https://github.com/dequelabs/axe-core/issues/1217)) ([27fce9d](https://github.com/dequelabs/axe-core/commit/27fce9d))
- Correct autocomplete-appropriate node type resolution ([#1318](https://github.com/dequelabs/axe-core/issues/1318)) ([2fc3eeb](https://github.com/dequelabs/axe-core/commit/2fc3eeb))
- CSSOM generation for shadowRoot in Safari ([#1113](https://github.com/dequelabs/axe-core/issues/1113)) ([a51ae03](https://github.com/dequelabs/axe-core/commit/a51ae03))
- Don't flag invalid roles in unsupportedrole ([#1328](https://github.com/dequelabs/axe-core/issues/1328)) ([2dfcbaa](https://github.com/dequelabs/axe-core/commit/2dfcbaa))
- Escape href attribute when generating a CSS selector [[#1137](https://github.com/dequelabs/axe-core/issues/1137)](<[#1366](https://github.com/dequelabs/axe-core/issues/1366)>) ([0c2f42d](https://github.com/dequelabs/axe-core/commit/0c2f42d))
- Flag hidden elms with disallowed role(s) for review ([#1225](https://github.com/dequelabs/axe-core/issues/1225)) ([bdff141](https://github.com/dequelabs/axe-core/commit/bdff141))
- Handle noscript and template in dom.isVisible ([#1257](https://github.com/dequelabs/axe-core/issues/1257)) ([e67fc65](https://github.com/dequelabs/axe-core/commit/e67fc65))
- html-lang-valid should consider xml:lang ([#1152](https://github.com/dequelabs/axe-core/issues/1152)) ([4279c72](https://github.com/dequelabs/axe-core/commit/4279c72))
- Ignore invalid and allow redundant role in aria-allowed-role ([#1118](https://github.com/dequelabs/axe-core/issues/1118)) ([a0f9b31](https://github.com/dequelabs/axe-core/commit/a0f9b31))
- Introduce dom.isHiddenWithCSS for use in dom.isFocusable ([#1211](https://github.com/dequelabs/axe-core/issues/1211)) ([2cff417](https://github.com/dequelabs/axe-core/commit/2cff417))
- Log instead of error on unknown tag ([#1290](https://github.com/dequelabs/axe-core/issues/1290)) ([f82d773](https://github.com/dequelabs/axe-core/commit/f82d773))
- Prevent TypeErrors in color-contrast checks ([#1320](https://github.com/dequelabs/axe-core/issues/1320)) ([a34165c](https://github.com/dequelabs/axe-core/commit/a34165c)), closes [#1306](https://github.com/dequelabs/axe-core/issues/1306) [#1259](https://github.com/dequelabs/axe-core/issues/1259)
- Respect preload set to false ([#1298](https://github.com/dequelabs/axe-core/issues/1298)) ([e847d38](https://github.com/dequelabs/axe-core/commit/e847d38))
- Set preload:true as default ([#1281](https://github.com/dequelabs/axe-core/issues/1281)) ([c9731c8](https://github.com/dequelabs/axe-core/commit/c9731c8))
- Support skiplinks starting with "/#" ([#1286](https://github.com/dequelabs/axe-core/issues/1286)) ([f93c0c9](https://github.com/dequelabs/axe-core/commit/f93c0c9))
- Update SC to wcag134 for CSS Orientation Rule ([d3f90df](https://github.com/dequelabs/axe-core/commit/d3f90df))

### Features

- **commons:** Add matches methods ([#1270](https://github.com/dequelabs/axe-core/issues/1270)) ([986c97a](https://github.com/dequelabs/axe-core/commit/986c97a)), closes [#1163](https://github.com/dequelabs/axe-core/issues/1163)
- **image-alt:** require alt text or empty strings ([#1260](https://github.com/dequelabs/axe-core/issues/1260)) ([e24cea9](https://github.com/dequelabs/axe-core/commit/e24cea9))
- **new-rule:** New aria-hidden-focus rule ([#1166](https://github.com/dequelabs/axe-core/issues/1166)) ([4489965](https://github.com/dequelabs/axe-core/commit/4489965))
- **new-rule:** Separate form-field-multiple-label from label rule ([#1226](https://github.com/dequelabs/axe-core/issues/1226)) ([0e0063c](https://github.com/dequelabs/axe-core/commit/0e0063c))
- **new-rule:** Label and Name from Content mismatch WCAG21 (Issue [#1149](https://github.com/dequelabs/axe-core/issues/1149)) ([#1335](https://github.com/dequelabs/axe-core/issues/1335)) ([a4255da](https://github.com/dequelabs/axe-core/commit/a4255da))
- **rule:** Require unique aria labels in checkboxgroup & radiogroup ([#1316](https://github.com/dequelabs/axe-core/issues/1316)) ([c9b310d](https://github.com/dequelabs/axe-core/commit/c9b310d))
- Add a reference to the `node` a rule failed on ([#1321](https://github.com/dequelabs/axe-core/issues/1321)) ([68741de](https://github.com/dequelabs/axe-core/commit/68741de)), closes [#1317](https://github.com/dequelabs/axe-core/issues/1317)
- Add allowEmpty option for aria-valid-attr-value ([#1154](https://github.com/dequelabs/axe-core/issues/1154)) ([89d18d0](https://github.com/dequelabs/axe-core/commit/89d18d0)), closes [#994](https://github.com/dequelabs/axe-core/issues/994)
- Add environment details to results ([#1353](https://github.com/dequelabs/axe-core/issues/1353)) ([e795f7d](https://github.com/dequelabs/axe-core/commit/e795f7d))
- ARIA supported checks ([#1254](https://github.com/dequelabs/axe-core/issues/1254)) ([51a18a8](https://github.com/dequelabs/axe-core/commit/51a18a8)), closes [#918](https://github.com/dequelabs/axe-core/issues/918)
- New rule landmark-complementary-is-top-level ([#1239](https://github.com/dequelabs/axe-core/issues/1239)) ([328ca2c](https://github.com/dequelabs/axe-core/commit/328ca2c))
- Pass context argument to rule matches ([#1370](https://github.com/dequelabs/axe-core/issues/1370)) ([b374669](https://github.com/dequelabs/axe-core/commit/b374669))
- Rebuild the accessible text algorithm ([#1163](https://github.com/dequelabs/axe-core/issues/1163)) ([5f420e5](https://github.com/dequelabs/axe-core/commit/5f420e5))
- Tag review-items rule as 'best-practice' ([#1344](https://github.com/dequelabs/axe-core/issues/1344)) ([05f37de](https://github.com/dequelabs/axe-core/commit/05f37de))

### Performance Improvements

- Defer rules rather than checks ([#1308](https://github.com/dequelabs/axe-core/issues/1308)) ([80c1c74](https://github.com/dequelabs/axe-core/commit/80c1c74)), closes [#1172](https://github.com/dequelabs/axe-core/issues/1172)
- Speed up getNodeFromTree ([#1302](https://github.com/dequelabs/axe-core/issues/1302)) ([5f834ed](https://github.com/dequelabs/axe-core/commit/5f834ed))
- Update performanceTimer end mark for rules ([#1303](https://github.com/dequelabs/axe-core/issues/1303)) ([a28674e](https://github.com/dequelabs/axe-core/commit/a28674e)), closes [#701](https://github.com/dequelabs/axe-core/issues/701) [#1172](https://github.com/dequelabs/axe-core/issues/1172)

### Deprecate

- Deprecate axe.commons.utils namespace ([#1330](https://github.com/dequelabs/axe-core/issues/1330)) ([df93272](https://github.com/dequelabs/axe-core/commit/df93272))

<a name="3.1.2"></a>

## [3.1.2](https://github.com/dequelabs/axe-core/compare/v3.0.3...v3.1.2) (2018-09-07)

### Bug Fixes

- **i18n:** Update Japanese locale ([#1107](https://github.com/dequelabs/axe-core/issues/1107)) ([8138e55](https://github.com/dequelabs/axe-core/commit/8138e55))
- autocomplete appropriate to handle state terms ([#1121](https://github.com/dequelabs/axe-core/issues/1121)) ([35a4d11](https://github.com/dequelabs/axe-core/commit/35a4d11))
- banner comment in generated axe files ([#1112](https://github.com/dequelabs/axe-core/issues/1112)) ([e4788bf](https://github.com/dequelabs/axe-core/commit/e4788bf))
- ignore invalid and allow redundant role in aria-allowed-role ([#1118](https://github.com/dequelabs/axe-core/issues/1118)) ([a0f9b31](https://github.com/dequelabs/axe-core/commit/a0f9b31))

<a name="3.1.1"></a>

## [3.1.1](https://github.com/dequelabs/axe-core/compare/v3.0.3...v3.1.1) (2018-08-28)

### Bug Fixes

- Fix broken 3.1.0 release script ([c3b2a52](https://github.com/dequelabs/axe-core/commit/c3b2a52))

<a name="3.1.0"></a>

# [3.1.0](https://github.com/dequelabs/axe-core/compare/v3.0.3...v3.1.0) (2018-08-28)

### Bug Fixes

- **rule fix:** Allow fallback labels when input has id ([#951](https://github.com/dequelabs/axe-core/issues/951)) ([54fa569](https://github.com/dequelabs/axe-core/commit/54fa569))
- **rule fix:** Updating aria 1.1 allowed attributes ([#964](https://github.com/dequelabs/axe-core/issues/964)) ([c3249c1](https://github.com/dequelabs/axe-core/commit/c3249c1))
- **rule fix:** Allow aria-errormessage with fallback ([17608b6](https://github.com/dequelabs/axe-core/commit/17608b6))
- **rule fix:** Ignore abstracts in determining element roles ([1af6088](https://github.com/dequelabs/axe-core/commit/1af6088))
- **rule fix:** Add combobox and radio required properties ([e80af7a](https://github.com/dequelabs/axe-core/commit/e80af7a))
- **rule fix:** Allow all ARIA idref(s) to be empty ([1498696](https://github.com/dequelabs/axe-core/commit/1498696))
- **rule fix:** Allow divs as groups in dl ([#1076](https://github.com/dequelabs/axe-core/issues/1076)) ([f4f6df6](https://github.com/dequelabs/axe-core/commit/f4f6df6)), closes [#262](https://github.com/dequelabs/axe-core/issues/262)
- **rule fix:** Allow live-region and dialog in `region` rule ([#1073](https://github.com/dequelabs/axe-core/issues/1073)) ([fb6438b](https://github.com/dequelabs/axe-core/commit/fb6438b))
- **rule fix:** Allow only-dlitem / only-listitem to have any hidden content ([#1098](https://github.com/dequelabs/axe-core/issues/1098)) ([6034aae](https://github.com/dequelabs/axe-core/commit/6034aae)), closes [#1021](https://github.com/dequelabs/axe-core/issues/1021)
- **rule fix:** Do not flag font icons in color-contrast rule ([#1095](https://github.com/dequelabs/axe-core/issues/1095)) ([b6ac084](https://github.com/dequelabs/axe-core/commit/b6ac084)), closes [#1068](https://github.com/dequelabs/axe-core/issues/1068)
- **rule fix:** Do not require media captions / descriptions ([#1075](https://github.com/dequelabs/axe-core/issues/1075)) ([289f623](https://github.com/dequelabs/axe-core/commit/289f623)), closes [#816](https://github.com/dequelabs/axe-core/issues/816)
- **rule fix:** improve messaging for hidden labels ([ae07b8e](https://github.com/dequelabs/axe-core/commit/ae07b8e))
- **rule fix:** Ignore abstracts in determining element roles ([e3b1e1d](https://github.com/dequelabs/axe-core/commit/e3b1e1d))
- **rule fix:** Correctly handle role attribute on lists and listitems. ([#949](https://github.com/dequelabs/axe-core/issues/949)) ([3a8729b](https://github.com/dequelabs/axe-core/commit/3a8729b))
- **core:** allow returning a Promise in jsdom from axe.run ([#943](https://github.com/dequelabs/axe-core/issues/943)) ([3858a1f](https://github.com/dequelabs/axe-core/commit/3858a1f))
- **typescript:** Correct `Check.evaluate` and `Check.after` type definitions ([#976](https://github.com/dequelabs/axe-core/issues/976)) ([db3ed40](https://github.com/dequelabs/axe-core/commit/db3ed40)), closes [#974](https://github.com/dequelabs/axe-core/issues/974)
- **typescript:** Typescript interface updates ([#973](https://github.com/dequelabs/axe-core/issues/973)) ([f8c9905](https://github.com/dequelabs/axe-core/commit/f8c9905)), closes [#972](https://github.com/dequelabs/axe-core/issues/972)
- **messages:** Clearer fail message for aria-labelledby ([956281b](https://github.com/dequelabs/axe-core/commit/956281b))
- **messages:** Consistent landmark rule/check descriptions ([#1003](https://github.com/dequelabs/axe-core/issues/1003)) ([d792970](https://github.com/dequelabs/axe-core/commit/d792970))
- **messages:** Show attribute in message ([#1061](https://github.com/dequelabs/axe-core/issues/1061)) ([9ff5d54](https://github.com/dequelabs/axe-core/commit/9ff5d54))
- Check data is an array of IDs ([d64bc5f](https://github.com/dequelabs/axe-core/commit/d64bc5f))
- Don't crash with slot elements without shadowDOM ([#977](https://github.com/dequelabs/axe-core/issues/977)) ([cc044af](https://github.com/dequelabs/axe-core/commit/cc044af))
- Generate jsdoc(umentation) ([9f9b15b](https://github.com/dequelabs/axe-core/commit/9f9b15b))
- Stop `indexOf` override from crashing Axe ([#968](https://github.com/dequelabs/axe-core/issues/968)) ([e3329ce](https://github.com/dequelabs/axe-core/commit/e3329ce))
- Use `node.matches*` in place of `prototype.matches*` to prevent IE crash ([#956](https://github.com/dequelabs/axe-core/issues/956)) ([ebdb590](https://github.com/dequelabs/axe-core/commit/ebdb590))

### Features

- **new rule:** Added new html-xml-lang-mismatch rule ([#999](https://github.com/dequelabs/axe-core/issues/999)) ([7452a51](https://github.com/dequelabs/axe-core/commit/7452a51))
- **new rule:** aria-allowed-role ([#945](https://github.com/dequelabs/axe-core/issues/945)) ([c270a46](https://github.com/dequelabs/axe-core/commit/c270a46))
- **new rule:** css-orientation-lock (wcag21) ([#1081](https://github.com/dequelabs/axe-core/issues/1081)) ([4ae4ea0](https://github.com/dequelabs/axe-core/commit/4ae4ea0))
- **new rule:** Add WCAG 2.1 autocomplete-valid rule ([e6189ce](https://github.com/dequelabs/axe-core/commit/e6189ce))
- **rule fix:** Flag unsupported roles ([#1064](https://github.com/dequelabs/axe-core/issues/1064)) ([5515ee6](https://github.com/dequelabs/axe-core/commit/5515ee6))
- **rule fix:** Remove non-existing "text" role ([#1069](https://github.com/dequelabs/axe-core/issues/1069)) ([67ec1f5](https://github.com/dequelabs/axe-core/commit/67ec1f5))
- **rule fix:** Break up duplicate-id rule for ARIA+labels and active elements ([2ecfea7](https://github.com/dequelabs/axe-core/commit/2ecfea7))
- **rule fix:** Tag aria rules as WCAG 2, SC4.1.2 issues ([e7816c0](https://github.com/dequelabs/axe-core/commit/e7816c0))
- **core:** Allow rules to access CSSOM assets ([#958](https://github.com/dequelabs/axe-core/issues/958)) ([5d6c1fa](https://github.com/dequelabs/axe-core/commit/5d6c1fa))
- **core:** Add `doT` template engine ([#1024](https://github.com/dequelabs/axe-core/issues/1024)) ([f6f08d4](https://github.com/dequelabs/axe-core/commit/f6f08d4))
- **commons:** Add aria.getRole method ([1d2a0e4](https://github.com/dequelabs/axe-core/commit/1d2a0e4))
- **commons:** Add text.isValidAutocomplete method ([8d44fe4](https://github.com/dequelabs/axe-core/commit/8d44fe4))
- **i18n:** Add runtime localization support ([#1036](https://github.com/dequelabs/axe-core/issues/1036)) ([7d4b70f](https://github.com/dequelabs/axe-core/commit/7d4b70f))
- **i18n:** Update FR (french) translation file for 3.1 release ([#1089](https://github.com/dequelabs/axe-core/issues/1089)) ([4a5cad0](https://github.com/dequelabs/axe-core/commit/4a5cad0))
- **i18n:** Update ja (Japanese) locale for 3.1 release ([#1101](https://github.com/dequelabs/axe-core/issues/1101)) ([ef6cd86](https://github.com/dequelabs/axe-core/commit/ef6cd86))
- **deprecate:** Deprecate audio-caption rule ([#1071](https://github.com/dequelabs/axe-core/issues/1071)) ([3b05fee](https://github.com/dequelabs/axe-core/commit/3b05fee))

<a name="3.0.3"></a>

## [3.0.3](https://github.com/dequelabs/axe-core/compare/v3.0.2...v3.0.3) (2018-06-04)

### Bug Fixes

- Resolve markdown lint errors. ([efdad94](https://github.com/dequelabs/axe-core/commit/efdad94)) ([aa90155](https://github.com/dequelabs/axe-core/commit/aa90155))
- Don't require all ARIA IDREFS to exist ([#921](https://github.com/dequelabs/axe-core/issues/921)) ([130efed](https://github.com/dequelabs/axe-core/commit/130efed))
- generate unsupported aria roles and attributes. ([7315662](https://github.com/dequelabs/axe-core/commit/7315662))
- Make empty role=lisbox elements as incomplete ([#927](https://github.com/dequelabs/axe-core/issues/927)) ([87e979f](https://github.com/dequelabs/axe-core/commit/87e979f))
- Prevent axe-core crashing on “-“ as a class name ([#884](https://github.com/dequelabs/axe-core/issues/884)) ([9c4d84e](https://github.com/dequelabs/axe-core/commit/9c4d84e))
- Right trim URLs before outputting them in getSelector ([#924](https://github.com/dequelabs/axe-core/issues/924)) ([4775a23](https://github.com/dequelabs/axe-core/commit/4775a23)), closes [#788](https://github.com/dequelabs/axe-core/issues/788)
- td-has-heading to ignore td with its role changed ([#928](https://github.com/dequelabs/axe-core/issues/928)) ([d68af4c](https://github.com/dequelabs/axe-core/commit/d68af4c))
- Update tags for frame-title rule ([#935](https://github.com/dequelabs/axe-core/issues/935)) ([6436bbf](https://github.com/dequelabs/axe-core/commit/6436bbf))
- **core:** Define 'axe-core' as an AMD module ([#859](https://github.com/dequelabs/axe-core/issues/859)) ([7b46f63](https://github.com/dequelabs/axe-core/commit/7b46f63)), closes [#849](https://github.com/dequelabs/axe-core/issues/849) [#856](https://github.com/dequelabs/axe-core/issues/856) [#861](https://github.com/dequelabs/axe-core/issues/861) [#847](https://github.com/dequelabs/axe-core/issues/847) [#844](https://github.com/dequelabs/axe-core/issues/844) [#871](https://github.com/dequelabs/axe-core/issues/871) [#849](https://github.com/dequelabs/axe-core/issues/849) [#849](https://github.com/dequelabs/axe-core/issues/849)
- Update tags to accesskey & link-name rules ([#922](https://github.com/dequelabs/axe-core/issues/922)) ([a8e801c](https://github.com/dequelabs/axe-core/commit/a8e801c))
- **rule:** Layout-table does not match presentation / none roles ([#828](https://github.com/dequelabs/axe-core/issues/828)) ([5651ecc](https://github.com/dequelabs/axe-core/commit/5651ecc))
- **rule:** restore labelledBy on unlabeled select ([b7bdf66](https://github.com/dequelabs/axe-core/commit/b7bdf66))
- **rules:** Allow focusable role=application elements ([b5de450](https://github.com/dequelabs/axe-core/commit/b5de450))
- **typescript:** Update ElementContext type ([#822](https://github.com/dequelabs/axe-core/issues/822)) ([eb09248](https://github.com/dequelabs/axe-core/commit/eb09248))

### Features

- generate ARIA supported documentation for roles and attributes. ([6f095dd](https://github.com/dequelabs/axe-core/commit/6f095dd))
- generated impacts as a part of rule descriptions ([#898](https://github.com/dequelabs/axe-core/issues/898)) ([6265608](https://github.com/dequelabs/axe-core/commit/6265608))

<a name="3.0.2"></a>

## [3.0.2](https://github.com/dequelabs/axe-core/compare/v3.0.0-beta.2...v3.0.2) (2018-04-24)

### Bug Fixes

- **rule:** Allow empty aria-labelledby values ([#829](https://github.com/dequelabs/axe-core/issues/829)) ([d280c5f](https://github.com/dequelabs/axe-core/commit/d280c5f))
- Prevent color rules from crashing Chrome 66+ [#856](https://github.com/dequelabs/axe-core/issues/856) ([#861](https://github.com/dequelabs/axe-core/issues/861)) ([147b665](https://github.com/dequelabs/axe-core/commit/147b665))
- **respondable:** Identify the current axe instance by its application name when it exists ([affd75c](https://github.com/dequelabs/axe-core/commit/affd75c))
- **respondable:** Use the hard-coded axe.application name as default ([ab4a49f](https://github.com/dequelabs/axe-core/commit/ab4a49f))
- **rule:** Ignore hashbang URLs for skiplinks ([#827](https://github.com/dequelabs/axe-core/issues/827)) ([e1f0c57](https://github.com/dequelabs/axe-core/commit/e1f0c57))
- **rule:** Tag video-caption only as SC 1.2.2 ([87818e7](https://github.com/dequelabs/axe-core/commit/87818e7))

<a name="3.0.1"></a>

## [3.0.1](https://github.com/dequelabs/axe-core/compare/v3.0.0...v3.0.1) (2018-04-03)

### Bug Fixes

- allow mixed casing of caption/summary ([ca091ac](https://github.com/dequelabs/axe-core/commit/ca091ac))
- Allow title on button-name ([#794](https://github.com/dequelabs/axe-core/issues/794)) ([e31fe9a](https://github.com/dequelabs/axe-core/commit/e31fe9a))
- **sri:** Fix incorrect sri-history entries ([#789](https://github.com/dequelabs/axe-core/issues/789)) ([f5f55f3](https://github.com/dequelabs/axe-core/commit/f5f55f3))

<a name="3.0.0"></a>

# [3.0.0](https://github.com/dequelabs/axe-core/compare/v3.0.0-beta.2...v3.0.0) (2018-03-19)

### Bug Fixes

- Allow exclusion of Shadow DOM content ([cc66eb2](https://github.com/dequelabs/axe-core/commit/cc66eb2))
- Avoid flatTree memory leak ([a902e80](https://github.com/dequelabs/axe-core/commit/a902e80))
- **main-is-top-level:** Rename check to landmark-is-top-level for greater reuse ([b405af1](https://github.com/dequelabs/axe-core/commit/b405af1))
- Avoid timing issue with axe cleanup method ([24ea6a7](https://github.com/dequelabs/axe-core/commit/24ea6a7))
- correct misnamed check ([1e709e0](https://github.com/dequelabs/axe-core/commit/1e709e0))
- Correct runOnly object for TypeScript definition ([571e984](https://github.com/dequelabs/axe-core/commit/571e984))
- **has-at-least-one-main:** Rename check to page-has-main, for reusability ([9a9c283](https://github.com/dequelabs/axe-core/commit/9a9c283))
- **has-no-more-than-one-main:** Rename check to page-no-duplicate for better reuse ([e75324b](https://github.com/dequelabs/axe-core/commit/e75324b))
- **region:** Ignore forms without accessible name as landmarks ([8ad2718](https://github.com/dequelabs/axe-core/commit/8ad2718))
- **rule:** skip-link rule doesn't decode URI encoded href's ([818b5cd](https://github.com/dequelabs/axe-core/commit/818b5cd))
- Ensure all rules have a category tag ([d61e67d](https://github.com/dequelabs/axe-core/commit/d61e67d))
- make getSelector work with URIs that cannot be shortened ([a113555](https://github.com/dequelabs/axe-core/commit/a113555))

### Features

- Make aria-level required with role=heading [#740](https://github.com/dequelabs/axe-core/issues/740) ([64b743f](https://github.com/dequelabs/axe-core/commit/64b743f))
- **aria:** allow DPUB ARIA roles ([70b48f6](https://github.com/dequelabs/axe-core/commit/70b48f6))
- **frame-tested:** Use this new rule to test if all frames are available, instead of axe.log ([83cd17d](https://github.com/dequelabs/axe-core/commit/83cd17d))
- **landmark-contentinfo-is-top-level:** add rule ensuring top level contentinfo ([5692e7d](https://github.com/dequelabs/axe-core/commit/5692e7d))
- **landmark-no-more-than-one-banner:** add rule ensuring no more than one banner ([6617800](https://github.com/dequelabs/axe-core/commit/6617800))
- **landmark-no-more-than-one-contentinfo:** add rule ensuring no more than one contentinfo ([82217ef](https://github.com/dequelabs/axe-core/commit/82217ef))
- **page-has-heading-one:** Added new best-practice rule ([cb8f261](https://github.com/dequelabs/axe-core/commit/cb8f261))
- **rules:** add new rule aria-dpub-role-fallback ([9470c02](https://github.com/dequelabs/axe-core/commit/9470c02))
- Make options.runOnly more forgiving about plurality ([fa81f9d](https://github.com/dequelabs/axe-core/commit/fa81f9d))
- Translated all 3.0 rules to Japanese ([3862e7e](https://github.com/dequelabs/axe-core/commit/3862e7e))

### BREAKING CHANGES

- Incorrect use of runOnly now throws errors
- **main-is-top-level:** The check main-is-top-level is no longer available
- **has-at-least-one-main:** Original has-at-least-one-main check is no longer available

<a name="3.0.0-beta.3"></a>

# [3.0.0-beta.3](https://github.com/dequelabs/axe-core/compare/v3.0.0-beta.2...v3.0.0-beta.3) (2018-03-08)

### Bug Fixes

- Correct runOnly object for TypeScript definition ([571e984](https://github.com/dequelabs/axe-core/commit/571e984))
- **has-at-least-one-main:** Rename check to page-has-main, for reusability ([9a9c283](https://github.com/dequelabs/axe-core/commit/9a9c283))
- **has-no-more-than-one-main:** Rename check to page-no-duplicate for better reuse ([e75324b](https://github.com/dequelabs/axe-core/commit/e75324b))
- **main-is-top-level:** Rename check to landmark-is-top-level for greater reuse ([b405af1](https://github.com/dequelabs/axe-core/commit/b405af1))
- **region:** Ignore forms without accessible name as landmarks ([8ad2718](https://github.com/dequelabs/axe-core/commit/8ad2718))

### Features

- **aria-required-attr:** Make aria-level required with role=heading [#740](https://github.com/dequelabs/axe-core/issues/740) ([64b743f](https://github.com/dequelabs/axe-core/commit/64b743f))
- **aria:** allow DPUB ARIA roles ([70b48f6](https://github.com/dequelabs/axe-core/commit/70b48f6))
- **frame-tested:** Use this new rule to test if all frames are available, instead of axe.log ([83cd17d](https://github.com/dequelabs/axe-core/commit/83cd17d))
- **landmark-contentinfo-is-top-level:** Add rule ensuring top level contentinfo ([5692e7d](https://github.com/dequelabs/axe-core/commit/5692e7d))
- **landmark-no-more-than-one-banner:** Add rule ensuring no more than one banner ([6617800](https://github.com/dequelabs/axe-core/commit/6617800))
- **landmark-no-more-than-one-contentinfo:** Add rule ensuring no more than one contentinfo ([82217ef](https://github.com/dequelabs/axe-core/commit/82217ef))
- **page-has-heading-one:** Added new best-practice rule ([cb8f261](https://github.com/dequelabs/axe-core/commit/cb8f261))
- **rules:** Add new rule aria-dpub-role-fallback ([9470c02](https://github.com/dequelabs/axe-core/commit/9470c02))

### BREAKING CHANGES

- **main-is-top-level:** The check main-is-top-level is no longer available
- **has-at-least-one-main:** Original has-at-least-one-main check is no longer available

<a name="3.0.0-beta.2"></a>

# [3.0.0-beta.2](https://github.com/dequelabs/axe-core/compare/v3.0.0-alpha.9...v3.0.0-beta.2) (2018-03-01)

### Bug Fixes

- **perf:** Improve getSelector performance ([737c81c](https://github.com/dequelabs/axe-core/commit/737c81c))
- Delete Selenium example, use grunt-axe-selenium instead ([063e701](https://github.com/dequelabs/axe-core/commit/063e701))

### Features

- Update Jasmin example ([72d49d5](https://github.com/dequelabs/axe-core/commit/72d49d5))
- Update Jest+React example ([5b35322](https://github.com/dequelabs/axe-core/commit/5b35322))
- Update Mocha example ([cf70f9f](https://github.com/dequelabs/axe-core/commit/cf70f9f))
- Update PhantomJS example ([641b5e6](https://github.com/dequelabs/axe-core/commit/641b5e6))
- Update QUnit example ([028ae51](https://github.com/dequelabs/axe-core/commit/028ae51))

# Change Log

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

<a name="3.0.0-beta.1"></a>

# [3.0.0-beta.1](https://github.com/dequelabs/axe-core/compare/v3.0.0-alpha.9...v3.0.0-beta.1) (2018-02-19)

### Bug Fixes

- **audio-caption:** Change tag wcag122 to wcag121 [#686](https://github.com/dequelabs/axe-core/issues/686) ([#721](https://github.com/dequelabs/axe-core/issues/721)) ([9c7b9f1](https://github.com/dequelabs/axe-core/commit/9c7b9f1))
- **empty-heading:** Skip headings with the role changed [#645](https://github.com/dequelabs/axe-core/issues/645) ([#722](https://github.com/dequelabs/axe-core/issues/722)) ([80ef961](https://github.com/dequelabs/axe-core/commit/80ef961))
- **image-alt:** Exclude svg[role="img"] elements ([#683](https://github.com/dequelabs/axe-core/issues/683)) ([0fe74d8](https://github.com/dequelabs/axe-core/commit/0fe74d8))
- **label:** Prevent label rule from crashing on input without type [#678](https://github.com/dequelabs/axe-core/issues/678) ([#730](https://github.com/dequelabs/axe-core/issues/730)) ([4498680](https://github.com/dequelabs/axe-core/commit/4498680))
- **perf:** improve select performance fixes [#702](https://github.com/dequelabs/axe-core/issues/702) ([3274919](https://github.com/dequelabs/axe-core/commit/3274919))
- **perf:** memoize axe.utils.select ([c9cd122](https://github.com/dequelabs/axe-core/commit/c9cd122))
- **perf:** normalize all selectors for better cache utilization ([189c165](https://github.com/dequelabs/axe-core/commit/189c165))
- **perf:** remove need for node sorting from select completely ([7677a6a](https://github.com/dequelabs/axe-core/commit/7677a6a))
- **performance:** significantly improve the performance of the dom.findUp utility fixes [#696](https://github.com/dequelabs/axe-core/issues/696) ([9197e03](https://github.com/dequelabs/axe-core/commit/9197e03))
- add shadow dom coverage to all checks ([0e48413](https://github.com/dequelabs/axe-core/commit/0e48413)), closes [#690](https://github.com/dequelabs/axe-core/issues/690)
- bug-705: cleanupPlugins() should not throw exception when no arguments are provided ([#709](https://github.com/dequelabs/axe-core/issues/709)) ([fb1d2f7](https://github.com/dequelabs/axe-core/commit/fb1d2f7))
- Remove axe.a11yCheck() ([88d039f](https://github.com/dequelabs/axe-core/commit/88d039f))
- use virtual methods where applicable ([6ddc4e5](https://github.com/dequelabs/axe-core/commit/6ddc4e5))
- **type-checking:** Improve typescript axe.run call signature ([#707](https://github.com/dequelabs/axe-core/issues/707)) ([de45ee3](https://github.com/dequelabs/axe-core/commit/de45ee3))

### Performance Improvements

- Add performance metrics in Rule.runChecks ([#701](https://github.com/dequelabs/axe-core/issues/701)) ([27fdc2f](https://github.com/dequelabs/axe-core/commit/27fdc2f))

<a name="3.0.0-alpha.9"></a>

# [3.0.0-alpha.9](https://github.com/dequelabs/axe-core/compare/v3.0.0-alpha.8...v3.0.0-alpha.9) (2018-01-18)

### Bug Fixes

- **aria-errormessage:** adds support for aria-errormessage ([#517](https://github.com/dequelabs/axe-core/issues/517)) ([c96f58c](https://github.com/dequelabs/axe-core/commit/c96f58c))
- **check:** fix bug with async checks ([441ca95](https://github.com/dequelabs/axe-core/commit/441ca95))
- **color-contrast:** allow disabled label children ([db26bc9](https://github.com/dequelabs/axe-core/commit/db26bc9))
- **color-contrast:** incl. elements w/ line breaks ([a464918](https://github.com/dequelabs/axe-core/commit/a464918))
- **commons/aria:** allow aria-required on checkbox role ([3e21c6e](https://github.com/dequelabs/axe-core/commit/3e21c6e))
- adjust color algorithm for inline elements ([7f8491e](https://github.com/dequelabs/axe-core/commit/7f8491e))
- Allow checkbox and radio groups with hidden aria-labelledby targets [#188](https://github.com/dequelabs/axe-core/issues/188) ([6149bde](https://github.com/dequelabs/axe-core/commit/6149bde))
- Ensure overloaded Array.prototype won't crash axe ([ea57ef2](https://github.com/dequelabs/axe-core/commit/ea57ef2))
- handle contrast of multiline inline el's ([f9d565f](https://github.com/dequelabs/axe-core/commit/f9d565f))
- Polyfills are made non-enumerable [#648](https://github.com/dequelabs/axe-core/issues/648). ([#649](https://github.com/dequelabs/axe-core/issues/649)) ([48d8703](https://github.com/dequelabs/axe-core/commit/48d8703))
- Remove href-no-hash rule ([342cb6e](https://github.com/dequelabs/axe-core/commit/342cb6e))
- Return inapplicable results ([#473](https://github.com/dequelabs/axe-core/issues/473)). ([c9caeff](https://github.com/dequelabs/axe-core/commit/c9caeff))
- Several of fixes for IE and Edge ([#577](https://github.com/dequelabs/axe-core/issues/577)) ([63e1272](https://github.com/dequelabs/axe-core/commit/63e1272))
- skip-link rule now checks if a target exists ([f7f9cf3](https://github.com/dequelabs/axe-core/commit/f7f9cf3))
- **commons/aria:** allow aria-required on radio role ([58b76a6](https://github.com/dequelabs/axe-core/commit/58b76a6))
- **commons/dom:** fix isFocusable functions by checking screenreader ([#658](https://github.com/dequelabs/axe-core/issues/658)) ([c665d0b](https://github.com/dequelabs/axe-core/commit/c665d0b)), closes [#647](https://github.com/dequelabs/axe-core/issues/647)
- **core/utils/querySelectorAll:** Ensure that elements do not get tested twice ([#666](https://github.com/dequelabs/axe-core/issues/666)) ([a76a454](https://github.com/dequelabs/axe-core/commit/a76a454))
- **required-children:** add combobox > listbox exception ([#559](https://github.com/dequelabs/axe-core/issues/559)) ([8d0991f](https://github.com/dequelabs/axe-core/commit/8d0991f))
- **rules/region:** Treat `<section>` as a landmark if it has an accessible name [#640](https://github.com/dequelabs/axe-core/issues/640) ([#642](https://github.com/dequelabs/axe-core/issues/642)) ([c11b442](https://github.com/dequelabs/axe-core/commit/c11b442))

### Features

- Add rule, landmark-main-is-top-level ([#462](https://github.com/dequelabs/axe-core/issues/462)) ([63040bd](https://github.com/dequelabs/axe-core/commit/63040bd))
- **collect-results-from-frames:** add frameWaitTime option ([#661](https://github.com/dequelabs/axe-core/issues/661)) ([8016ad1](https://github.com/dequelabs/axe-core/commit/8016ad1))
- **landmark-one-main:** add rule ensuring one main landmark in document ([#498](https://github.com/dequelabs/axe-core/issues/498)) ([dfc6069](https://github.com/dequelabs/axe-core/commit/dfc6069))
- **reporter:** return one result of each type instead of zero when resultTypes is used ([#604](https://github.com/dequelabs/axe-core/issues/604)) ([216a83b](https://github.com/dequelabs/axe-core/commit/216a83b)), closes [#603](https://github.com/dequelabs/axe-core/issues/603)
- **rule:** Flag div/p/spans/headings in focus order ([ce5f3dc](https://github.com/dequelabs/axe-core/commit/ce5f3dc)), closes [#632](https://github.com/dequelabs/axe-core/issues/632)
- allow options in aria-allowed-attr, aria-required-attr ([#673](https://github.com/dequelabs/axe-core/issues/673)) ([61ac303](https://github.com/dequelabs/axe-core/commit/61ac303))
- Enable all rules by default ([18263eb](https://github.com/dequelabs/axe-core/commit/18263eb))
- Improve generated selectors for namespaced elements in XHTML ([#582](https://github.com/dequelabs/axe-core/issues/582)) ([9e3ca45](https://github.com/dequelabs/axe-core/commit/9e3ca45)), closes [#563](https://github.com/dequelabs/axe-core/issues/563)

### BREAKING CHANGES

- Skip-link rule no longer requires skip lins with a focusable target.

<a name="3.0.0-alpha.8"></a>

# [3.0.0-alpha.8](https://github.com/dequelabs/axe-core/compare/v3.0.0-alpha.7...v3.0.0-alpha.8) (2017-10-20)

### Bug Fixes

- **aria-allowed-attr:** align rowcount, colcount, and colindex with 1.1 spec ([#555](https://github.com/dequelabs/axe-core/issues/555)) ([10efa88](https://github.com/dequelabs/axe-core/commit/10efa88))
- **required-children:** add combobox > listbox exception ([#559](https://github.com/dequelabs/axe-core/issues/559)) ([8d0991f](https://github.com/dequelabs/axe-core/commit/8d0991f))
- Added message about expected contrast ratio ([#381](https://github.com/dequelabs/axe-core/issues/381)) ([#562](https://github.com/dequelabs/axe-core/issues/562)) ([9e30d64](https://github.com/dequelabs/axe-core/commit/9e30d64))

<a name="3.0.0-alpha.6"></a>

# [3.0.0-alpha.6](https://github.com/dequelabs/axe-core/compare/v3.0.0-alpha.3...v3.0.0-alpha.6) (2017-09-27)

### Bug Fixes

- **aria:** adding support for aria-expanded in menuitem ([#521](https://github.com/dequelabs/axe-core/issues/521)) ([b30b451](https://github.com/dequelabs/axe-core/commit/b30b451))
- **color-contrast:** Include `THEAD` and `TBODY` in contrast checks ([#514](https://github.com/dequelabs/axe-core/issues/514)) ([f98f8bd](https://github.com/dequelabs/axe-core/commit/f98f8bd))
- Match prerelease versions for helpUrl ([#546](https://github.com/dequelabs/axe-core/issues/546)) ([5300577](https://github.com/dequelabs/axe-core/commit/5300577))
- **helpUrl:** Properly parse x.0 versions ([#550](https://github.com/dequelabs/axe-core/issues/550)) ([a51c5ce](https://github.com/dequelabs/axe-core/commit/a51c5ce))
- **postinstall:** use node, more conditionals ([#520](https://github.com/dequelabs/axe-core/issues/520)) ([f5b5299](https://github.com/dequelabs/axe-core/commit/f5b5299))
- **responsible:** Restrict error construction to known errors ([0128a7e](https://github.com/dequelabs/axe-core/commit/0128a7e))

<a name="3.0.0-alpha.5"></a>

# [3.0.0-alpha.5](https://github.com/dequelabs/axe-core/compare/v3.0.0-alpha.4...v3.0.0-alpha.5) (2017-09-25)

### Bug Fixes

- **aria:** adding support for aria-expanded in menuitem ([#521](https://github.com/dequelabs/axe-core/issues/521)) ([b30b451](https://github.com/dequelabs/axe-core/commit/b30b451))
- **postinstall:** use node, more conditionals ([#520](https://github.com/dequelabs/axe-core/issues/520)) ([f5b5299](https://github.com/dequelabs/axe-core/commit/f5b5299))
- Match prerelease versions for helpUrl ([#546](https://github.com/dequelabs/axe-core/issues/546)) ([5300577](https://github.com/dequelabs/axe-core/commit/5300577))

<a name="3.0.0-alpha.4"></a>

## [3.0.0-alpha.4](https://github.com/dequelabs/axe-core/compare/v3.0.0-alpha.3...v3.0.0-alpha.4) (2017-09-08)

### Bug fixes:

- fix(color-contrast): Include `THEAD` and `TBODY` in contrast checks (#514) ([f98f8bd](https://github.com/dequelabs/axe-core/commit/f98f8bdacc551579c259aefd88bef41ed8157b68))
- fix(responsible): Restrict error construction to known errors (#513) ([0128a7e](https://github.com/dequelabs/axe-core/commit/0128a7ea47847b9fa04dbf98327f4bc1760c5e11))

### Features:

- docs: Document how to propose axe-core rules (#507) ([cabd329](https://github.com/dequelabs/axe-core/commit/cabd3297afbbfe9dbcc41a168b5529ba52f408ba))

<a name="3.0.0-alpha.3"></a>

## [3.0.0-alpha.3](https://github.com/dequelabs/axe-core/compare/v3.0.0-alpha.2...v3.0.0-alpha.3) (2017-09-06)

### Bug fixes:

- Additional ARIA 1.1. support and tests (#509) ([9b4d2ee](https://github.com/dequelabs/axe-core/commit/9b4d2eea4fcb2c48bab71e442da3a588b3893853))
- fix: RestoreScroll was running out of sync (#508) ([ff3df2d](https://github.com/dequelabs/axe-core/commit/ff3df2d9b2c01c1ca0d12c1fcaf136528287fb6d))

<a name="3.0.0-alpha.2"></a>

## [3.0.0-alpha.2](https://github.com/dequelabs/axe-core/compare/v3.0.0-alpha.1...v3.0.0-alpha.2) (2017-09-01)

### Bug Fixes

- copy precommit hook as file, not a link ([16f2f76](https://github.com/dequelabs/axe-core/commit/16f2f76))
- expand tr support for color contrast ([5a77c2f](https://github.com/dequelabs/axe-core/commit/5a77c2f))
- Ignore shadowRoots on elements that don't allow them ([7f66ee8](https://github.com/dequelabs/axe-core/commit/7f66ee8))
- only run postinstall if .git exists ([1107783](https://github.com/dequelabs/axe-core/commit/1107783))
- try telling circle to skip .git/hooks ([674408f](https://github.com/dequelabs/axe-core/commit/674408f))
- Use frame query that supports shadow dom ([#492](https://github.com/dequelabs/axe-core/issues/492)) ([94008ff](https://github.com/dequelabs/axe-core/commit/94008ff))

### Features

- feat: Add sri-history file and update process ([25ddb47](https://github.com/dequelabs/axe-core/commit/25ddb47ec4eec565da330558ee061fd6e34a7c24))
- feat: add standard-version ([e1e067d](https://github.com/dequelabs/axe-core/commit/e1e067d8f4445042360b2bef957037d5cdd0b7db))

<a name="3.0.0-alpha.1"></a>

## [3.0.0-alpha.1](https://github.com/dequelabs/axe-core/compare/v2.3.1...v3.0.0-alpha.1) (2017-08-16)

### Bug Fixes

- add copyright banner back in to axe.js ([2aac29a](https://github.com/dequelabs/axe-core/commit/2aac29a))
- Adjust if formatting ([2211d78](https://github.com/dequelabs/axe-core/commit/2211d78))
- Align impact levels with Deque Way ([28f4477](https://github.com/dequelabs/axe-core/commit/28f4477))
- Allow <track> to have no kind attribute ([f996d0f](https://github.com/dequelabs/axe-core/commit/f996d0f))
- complete shadow support for color matches ([f0fe551](https://github.com/dequelabs/axe-core/commit/f0fe551))
- **aria:** Allow implicit attribute values ([b949749](https://github.com/dequelabs/axe-core/commit/b949749))
- Set relatedNodes on color/link-in-block rules ([#407](https://github.com/dequelabs/axe-core/issues/407)) ([7fde0fe](https://github.com/dequelabs/axe-core/commit/7fde0fe))
- **aria:** Treegrid should own rows, not treeitems ([645d1fa](https://github.com/dequelabs/axe-core/commit/645d1fa))
- Correct flattened tree algorithm to include the shadow host ([#405](https://github.com/dequelabs/axe-core/issues/405)) ([70985b0](https://github.com/dequelabs/axe-core/commit/70985b0))
- Ensure all tests pass in Chrome ([0b0240f](https://github.com/dequelabs/axe-core/commit/0b0240f))
- ensure document is fetched from correct node ([b28597c](https://github.com/dequelabs/axe-core/commit/b28597c))
- Exclude `any` checks from output if one passed ([#466](https://github.com/dequelabs/axe-core/issues/466)) ([2dd3d68](https://github.com/dequelabs/axe-core/commit/2dd3d68))
- get tests all passing ([#457](https://github.com/dequelabs/axe-core/issues/457)) ([4874327](https://github.com/dequelabs/axe-core/commit/4874327))
- get virtualNode with getNodeFromTree ([9bf2870](https://github.com/dequelabs/axe-core/commit/9bf2870))
- getComposedParent should not return slot nodes ([#438](https://github.com/dequelabs/axe-core/issues/438)) ([0478cbd](https://github.com/dequelabs/axe-core/commit/0478cbd))
- Have table rules use shadow DOM ([453be1b](https://github.com/dequelabs/axe-core/commit/453be1b))
- help-same-as-label for shadow DOM ([dbbc544](https://github.com/dequelabs/axe-core/commit/dbbc544))
- incomplete results should have impact ([fcc51eb](https://github.com/dequelabs/axe-core/commit/fcc51eb))
- Let findUp work on shadow root children ([0252218](https://github.com/dequelabs/axe-core/commit/0252218))
- Let findUp work on shadow root children ([#447](https://github.com/dequelabs/axe-core/issues/447)) ([0f98481](https://github.com/dequelabs/axe-core/commit/0f98481))
- Minimise scrolling in getBackgroundColor ([f4551bb](https://github.com/dequelabs/axe-core/commit/f4551bb))
- Pass all tests that use accessibleText ([7ea8d6b](https://github.com/dequelabs/axe-core/commit/7ea8d6b))
- **checks/aria/required-children:** add exception for native input combobox missing textbox ([81ee2e4](https://github.com/dequelabs/axe-core/commit/81ee2e4))
- use virtualNode in duplicate-img-label ([82e51bc](https://github.com/dequelabs/axe-core/commit/82e51bc))
- **is-in-text-block:** Add Shadow DOM support ([a125f79](https://github.com/dequelabs/axe-core/commit/a125f79))
- pass virtualNode to Rule.run ([4534e86](https://github.com/dequelabs/axe-core/commit/4534e86))
- Properly output error stack ([56f1867](https://github.com/dequelabs/axe-core/commit/56f1867))
- Remove log statements ([6a6bd73](https://github.com/dequelabs/axe-core/commit/6a6bd73))
- Solve a few tests ([02daad1](https://github.com/dequelabs/axe-core/commit/02daad1))
- Use getAttribute(id) over .id ([#374](https://github.com/dequelabs/axe-core/issues/374)) ([353b53f](https://github.com/dequelabs/axe-core/commit/353b53f))
- Use testUtils in table tests ([364d5cd](https://github.com/dequelabs/axe-core/commit/364d5cd))
- use virtualNode in title-only check ([5fb06e3](https://github.com/dequelabs/axe-core/commit/5fb06e3))
- whitespace in hidden-content test ([99e8b73](https://github.com/dequelabs/axe-core/commit/99e8b73))

### Features

- Add aria-orientation to additional roles ([bb07c2d](https://github.com/dequelabs/axe-core/commit/bb07c2d))
- add check testUtils ([6f53279](https://github.com/dequelabs/axe-core/commit/6f53279))
- Add dom.getComposedParent function ([aac57c0](https://github.com/dequelabs/axe-core/commit/aac57c0))
- Add Japanese localisation ([5f8c9c8](https://github.com/dequelabs/axe-core/commit/5f8c9c8))
- Add new ARIA 1.1 values for haspopup ([9f7da56](https://github.com/dequelabs/axe-core/commit/9f7da56))
- Add option restoreScroll ([d55f3cd](https://github.com/dequelabs/axe-core/commit/d55f3cd))
- add S.C. 2.4.4 to link-name rule. Fixes [#369](https://github.com/dequelabs/axe-core/issues/369) ([70728e6](https://github.com/dequelabs/axe-core/commit/70728e6))
- add SD support to color-contrast-matches ([b595b42](https://github.com/dequelabs/axe-core/commit/b595b42))
- Add shadow DOM support to list checks ([#439](https://github.com/dequelabs/axe-core/issues/439)) ([d92c1a1](https://github.com/dequelabs/axe-core/commit/d92c1a1))
- Add shadow DOM to duplicate-img-label check ([#443](https://github.com/dequelabs/axe-core/issues/443)) ([2c0b075](https://github.com/dequelabs/axe-core/commit/2c0b075))
- Add shadow DOM to landmark check ([98f6023](https://github.com/dequelabs/axe-core/commit/98f6023))
- add shadow support to aria-required-children ([f729e25](https://github.com/dequelabs/axe-core/commit/f729e25))
- add shadow support to group-labelledby ([e2a9642](https://github.com/dequelabs/axe-core/commit/e2a9642))
- Add sri-history file and update process ([#476](https://github.com/dequelabs/axe-core/issues/476)) ([25ddb47](https://github.com/dequelabs/axe-core/commit/25ddb47))
- Allow hidden-content to work through shadow DOM bounds ([789d62e](https://github.com/dequelabs/axe-core/commit/789d62e))
- fieldset check shadow DOM ([da148d3](https://github.com/dequelabs/axe-core/commit/da148d3))
- Make explicit check consider shadow DOM ([#442](https://github.com/dequelabs/axe-core/issues/442)) ([9ddfc0f](https://github.com/dequelabs/axe-core/commit/9ddfc0f))
- Make region check work with shadow DOM ([ecd222f](https://github.com/dequelabs/axe-core/commit/ecd222f))
- Run text.accessibleText() on virtual elements ([#420](https://github.com/dequelabs/axe-core/issues/420)) ([414fcbe](https://github.com/dequelabs/axe-core/commit/414fcbe))
- ShadowDOM support for media checks ([0f21574](https://github.com/dequelabs/axe-core/commit/0f21574))
- **aria:** Support progressive ARIA 1.1 attributes / roles ([#468](https://github.com/dequelabs/axe-core/issues/468)) ([ebb2a5d](https://github.com/dequelabs/axe-core/commit/ebb2a5d))
- **aria-required-parent:** add Shadow DOM support ([6ed29f0](https://github.com/dequelabs/axe-core/commit/6ed29f0))
- **duplicate-id:** Add shadow DOM support ([439bc71](https://github.com/dequelabs/axe-core/commit/439bc71))
- **link-in-text-block:** Add shadow DOM support ([46a2cca](https://github.com/dequelabs/axe-core/commit/46a2cca))
- **shadow DOM:** Create commons virtual methods, for backward compatibility ([86a4c25](https://github.com/dequelabs/axe-core/commit/86a4c25))

<a name="2.4.2"></a>

## [2.4.2](https://github.com/dequelabs/axe-core/compare/v2.4.1...v2.4.2) (2017-09-25)

### Bug Fixes

- **aria:** adding support for aria-expanded in menuitem ([#521](https://github.com/dequelabs/axe-core/issues/521)) ([b4c42fe](https://github.com/dequelabs/axe-core/commit/b4c42fe))
- Match prerelease versions for helpUrl ([#546](https://github.com/dequelabs/axe-core/issues/546)) ([c166708](https://github.com/dequelabs/axe-core/commit/c166708))
- fix(node4): use var to declare variables ([#541](https://github.com/dequelabs/axe-core/issues/541)) ([c72badb](https://github.com/dequelabs/axe-core/commit/c72badbd55ef0b56b97f0c64a4eb544e31b4b3f1))

<a name="2.4.1"></a>

## [2.4.1](https://github.com/dequelabs/axe-core/compare/v2.4.0...v2.4.1) (2017-09-12)

### Bug Fixes

- fix(postinstall): use node, more conditionals ([#520](https://github.com/dequelabs/axe-core/issues/520)) ([98fac8a](https://github.com/dequelabs/axe-core/commit/98fac8a))

<a name="2.4.0"></a>

## [2.4.0](https://github.com/dequelabs/axe-core/compare/v2.3.1-alpha.2...v2.4.0) (2017-09-08)

### Bug fixes:

- fix(color-contrast): Include `THEAD` and `TBODY` in contrast checks (#514) ([f98f8bd](https://github.com/dequelabs/axe-core/commit/f98f8bdacc551579c259aefd88bef41ed8157b68))
- fix(responsible): Restrict error construction to known errors (#513) ([0128a7e](https://github.com/dequelabs/axe-core/commit/0128a7ea47847b9fa04dbf98327f4bc1760c5e11))

### Features:

- docs: Document how to propose axe-core rules (#507) ([cabd329](https://github.com/dequelabs/axe-core/commit/cabd3297afbbfe9dbcc41a168b5529ba52f408ba))

<a name="2.4.0-alpha.2"></a>

## [2.4.0-alpha.2](https://github.com/dequelabs/axe-core/compare/v2.4.0-alpha.1...v2.4.0-alpha.2) (2017-09-06)

### Bug fixes:

- test(aria): aria-haspopup, aria-modal for 1.1
- style(test/aria): add line breaks for readability
- test(aria): add missing roles and properties
- fix: RestoreScroll was running out of sync (#508)

### Features:

- feat(ARIA 1.1): Allow row-index, setsize and posinset on more roles

<a name="2.4.0-alpha.1"></a>

## [2.4.0-alpha.1](https://github.com/dequelabs/axe-core/compare/v2.3.0...v2.4.0-alpha.1) (2017-08-31)

### Bug fixes:

- chore: add help text for testconfig Grunt task
- fix: Properly output error stack
- doc: Add 'on mobile' to viewport rule
- fix: Ensure all tests pass in Chrome
- fix: Minimise scrolling in getBackgroundColor
- chore: Minor build chores for whitespace and lockfile
- fix: Align impact levels with Deque Way
- fix: Set relatedNodes on color/link-in-block rules
- fix: incomplete results should have impact
- fix(aria): Allow implicit attribute values
- chore: ignore growl in retire
- fix: Use getAttribute(id) over .id
- fix: Exclude `any` checks from output if one passed
- fix(aria): Treegrid should own rows, not treeitems
- fix(aria): add exception for native input combobox missing textbox. Fixes #160
- test: fix aria/required-children for jshint
- feat: allow link text from single-cell layout table
- fix: expand tr support for color contrast
- chore: ignore node_modules in examples when linting

### Features:

- feat: Add option `restoreScroll`
- doc: add more info on testing hidden regions
- feat: add S.C. 2.4.4 to link-name rule. Fixes #369
- feat: Add Japanese localisation
- doc: Add instructions on debugging on CircleCI
- test: add unit tests for button-has-visible-text
- chore: add descriptions to Grunt tasks
- feat(aria): Support progressive ARIA 1.1 attributes / roles
- feat: Add new ARIA 1.1 values for haspopup
- feat: Add aria-orientation to additional roles

<a name="2.3.1"></a>

## [2.3.1](https://github.com/dequelabs/axe-core/compare/v2.3.0...v2.3.1) (2017-06-15)

### Bug fixes:

- Improvements to hidden-content rule
- Deduplicated langs in valid-lang options

<a name="2.3.0"></a>

## [2.3.0](https://github.com/dequelabs/axe-core/compare/v2.2.3...v2.3.0) (2017-06-14)

### Bug fixes:

- Overhaul of selectors API
- New experimental rule for hidden-content
- New rule for flagging aria-hidden="true" on document.body
- Color-contrast rule impact is now serious
- Color-contrast fixes for implicit labels and TR elements
- Color-contrast puts 1:1 ratio elements into Needs Review/incomplete
- List category mappings in docs
- Update axe.source to work with Firefox webdriver

<a name="2.2.3"></a>

## [2.2.3](https://github.com/dequelabs/axe-core/compare/v2.2.2...v2.2.3) (2017-06-01)

### Bug fixes:

- Removed the disable property from link-in-text-block

<a name="2.2.2"></a>

## [2.2.2](https://github.com/dequelabs/axe-core/compare/2.2.1...v2.2.2) (2017-05-25)

### Bug fixes

- Stabilize incompleteData API for backwards compatibility
- Change impact of duplicate-id rule to moderate

<a name="2.2.2"></a>

## [2.2.1](https://github.com/dequelabs/axe-core/compare/2.2.0...2.2.1) (2017-05-19)

### Bug fixes

- Remove nodes from the color contrast incompleteData API to avoid circular references

<a name="2.2.0"></a>

## 2.2.0 (2017-04-24)

### Changes

- Add configuration options for iframes: false, selectors: false, and elementRef: true
- Improve color-contrast rule for disabled elements
- Add webdriver task for testing mobile viewports
- Improve audio/video captioning rules
- Improve th-has-data-cells rule
- Expose incomplete reasons for color contrast rule as part of Needs Review
- Implement rule groupings as tags
- Allow building of axe in multiple languages
- Empty-heading rule has impact: moderate

<a name="2.1.8"></a>

## 2.1.8 (2017-05-21)

### Changes

- Move from Snyk to Retire.js
- Make CI run test-fast task instead of parallel
- Add documentation on writing integration tests and rules
- Allow a larger list of languages for HTML-valid-lang rule
- Add support for [role=img] in image-alt rule
- Fix bug with innerHeight in get-background-color
- Improve dom.is-offscreen function
- Integrate optional performance timer
- Empty include defaults to document

<a name="2.1.7"></a>

## 2.1.7 (2016-12-13)

### Changes

- Add promise-based axe.run API method in favor of axe.a11yCheck
- Move TypeScript definition to root of project
- Add Inapplicable and Can't Tell results
- New rule: frame-title-unique
- Improvements to table rules: td-has-header, th-has-data-cells
- Color contrast rule performance improvements using polyfilled elementsFromPoint
- Add better support for implicit roles
- DQElement supports xPath

<a name="2.0.7"></a>

## 2.0.7 (2016-09-28)

### Changes

- Add TypeScript definition v1

<a name="2.0.5"></a>

## 2.0.5 (2016-04-20)

### Changes

- Support for UMD pattern
- Adds 508 tagging for table rules
- Fixes race condition for iframes
- Exclude actual nodes from array checking

<a name="2.0.5"></a>

## 2.0.5 (2016-04-13)

### Changes

- Improvements to messaging for extensions

<a name="2.0.3"></a>

## 2.0.3 (2016-04-12)

### Changes

- Security improvements
- Build includes Babel/ES6
- Improvements to table rules
- axe can be loaded in Node

<a name="2.0.0"></a>

## 2.0.0 (2016-03-01)

### Changes

- Adds support for AMD modules
- Fixes incompatibility with Webpack
- Improvements to rules and checks
- Help urls no longer hard-coded
- Improved error handling

<a name="1.1.1"></a>

## 1.1.1 (2015-09-04)

### Changes

- Adds Travis hooks
- Adds Sauce Labs
- Encodes HTML in descriptions
- Updates messages and help URLs

<a name="1.0.1"></a>

## 1.0.1 (2015-06-10)

### Changes

- Initial public release
