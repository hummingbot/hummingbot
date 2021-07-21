# v5.6.0 (Fri Jun 12 2020)

#### 🚀 Enhancement

- [AR-572](https://apollographql.atlassian.net/browse/AR-572): Create Alert component [#174](https://github.com/apollographql/space-kit/pull/174) ([@Jephuff](https://github.com/Jephuff))

#### Authors: 1

- Jeffrey Burt ([@Jephuff](https://github.com/Jephuff))

---

# v5.5.0 (Thu Jun 11 2020)

#### 🚀 Enhancement

- Adds keyboard control icon [#185](https://github.com/apollographql/space-kit/pull/185) ([@jchesterman](https://github.com/jchesterman))

#### Authors: 1

- [@jchesterman](https://github.com/jchesterman)

---

# v5.4.1 (Wed Jun 10 2020)

#### 🐛 Bug Fix

- Fix history icon [#184](https://github.com/apollographql/space-kit/pull/184) ([@jgzuke](https://github.com/jgzuke))

#### 🏠 Internal

- link npm badge to npm page in readme [#183](https://github.com/apollographql/space-kit/pull/183) ([@cheapsteak](https://github.com/cheapsteak))

#### Authors: 2

- Chang Wang ([@cheapsteak](https://github.com/cheapsteak))
- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))

---

# v5.4.0 (Fri Jun 05 2020)

#### 🚀 Enhancement

- Add Midnight color palette to SpaceKit [#180](https://github.com/apollographql/space-kit/pull/180) ([@jglovier](https://github.com/jglovier))

#### Authors: 1

- Joel Glovier ([@jglovier](https://github.com/jglovier))

---

# v5.3.0 (Fri Jun 05 2020)

#### 🚀 Enhancement

- Add history and left/right/down/up double arrow icons [#181](https://github.com/apollographql/space-kit/pull/181) ([@Jephuff](https://github.com/Jephuff))

#### Authors: 1

- Jeffrey Burt ([@Jephuff](https://github.com/Jephuff))

---

# v5.2.0 (Thu Jun 04 2020)

#### 🚀 Enhancement

- Add color configurability to `Menu` [#178](https://github.com/apollographql/space-kit/pull/178) ([@justinanastos](https://github.com/justinanastos))

#### 🏠 Internal

- [AR-1689](https://apollographql.atlassian.net/browse/AR-1689): Fix crashing chromatic builds [#179](https://github.com/apollographql/space-kit/pull/179) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v5.1.0 (Wed Jun 03 2020)

#### 🚀 Enhancement

- Apply hover states to `MenuItem` and `Button` when `aria-expanded="true"` [#177](https://github.com/apollographql/space-kit/pull/177) ([@justinanastos](https://github.com/justinanastos))

#### 🏠 Internal

- Update testing dependencies [#175](https://github.com/apollographql/space-kit/pull/175) ([@justinanastos](https://github.com/justinanastos))
- Add space-kit svg as favicon [#173](https://github.com/apollographql/space-kit/pull/173) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v5.0.0 (Fri May 08 2020)

#### 💥 Breaking Change

- Align icons with upcoming alert designs [#172](https://github.com/apollographql/space-kit/pull/172) ([@Jephuff](https://github.com/Jephuff))

#### Authors: 1

- Jeffrey Burt ([@Jephuff](https://github.com/Jephuff))

---

# v4.2.0 (Wed Apr 22 2020)

#### 🚀 Enhancement

- Add success solid icon [#170](https://github.com/apollographql/space-kit/pull/170) ([@jgzuke](https://github.com/jgzuke))

#### Authors: 1

- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))

---

# v4.1.0 (Mon Apr 20 2020)

#### 🚀 Enhancement

- adds another operations icon [#168](https://github.com/apollographql/space-kit/pull/168) ([@caydie-tran](https://github.com/caydie-tran))

#### Authors: 1

- Caydie Tran ([@caydie-tran](https://github.com/caydie-tran))

---

# v4.0.0 (Mon Apr 20 2020)

### Release Notes

_From #166_

* Upgrade `@tippyjs/react` library to v4

    This includes the new popper v2, greatly simplifying how we modify the default behavior of popups, tooltips, and menus

* Upgrade Menu flip logic to attempt to flip the menu to somewhere it'll fix on the window, and if it doesn't, to pick the placement to show the maximum amount of content while enabling scrolling

* Animations can now be disabled out of the box

    Hopefully this will stop our Chromatic story thrashing. We'll see 🤷‍♂️ 

* [Breaking change] Remove `flip` and `scrollableContent` props, they are always enabled now

---

#### 💥 Breaking Change

- [AR-1541](https://apollographql.atlassian.net/browse/AR-1541): Upgrade underlying dependencies and logic in menus and tooltips [#166](https://github.com/apollographql/space-kit/pull/166) ([@justinanastos](https://github.com/justinanastos))

#### 🏠 Internal

- Fix broken release process [#169](https://github.com/apollographql/space-kit/pull/169) ([@justinanastos](https://github.com/justinanastos))
- Restore CI check to require a label be applied before merging a PR [#165](https://github.com/apollographql/space-kit/pull/165) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v3.4.0 (Tue Apr 07 2020)

#### 🚀  Enhancement

- Add warning and book icons [#164](https://github.com/apollographql/space-kit/pull/164) ([@jgzuke](https://github.com/jgzuke))

#### Authors: 1

- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))

---

# v3.3.0 (Sat Apr 04 2020)

#### 🚀  Enhancement

- Add run icon [#163](https://github.com/apollographql/space-kit/pull/163) ([@jgzuke](https://github.com/jgzuke))

#### Authors: 1

- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))

---

# v3.2.0 (Wed Apr 01 2020)

#### 🚀  Enhancement

- Add `containerAs` prop to Modal [#162](https://github.com/apollographql/space-kit/pull/162) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v3.1.2 (Mon Mar 30 2020)

#### 🐛  Bug Fix

- Fix: Minor typo in Emotion description [#161](https://github.com/apollographql/space-kit/pull/161) ([@AlexanderMann](https://github.com/AlexanderMann))

#### Authors: 1

- Alexander Mann ([@AlexanderMann](https://github.com/AlexanderMann))

---

# v3.1.1 (Wed Mar 11 2020)

#### 🐛  Bug Fix

- 📚 Table: expand `colProps` docs to explain applicable styles [#160](https://github.com/apollographql/space-kit/pull/160) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v3.1.0 (Tue Mar 10 2020)

#### 🚀  Enhancement

- [AP-1393](https://apollographql.atlassian.net/browse/AP-1393): Add `endIcon` prop to `Button` [#159](https://github.com/apollographql/space-kit/pull/159) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v3.0.1 (Fri Feb 14 2020)

#### 🐛  Bug Fix

- [AP-1335](https://apollographql.atlassian.net/browse/AP-1335): Fix `MenuItem`s not being truncated properly [#158](https://github.com/apollographql/space-kit/pull/158) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v3.0.0 (Thu Feb 13 2020)

### Release Notes

_From #156_

- Remove `instanceRef` prop on `Menu` (💥 breaking change)
- Replace `icon` with `startIcon` in `MenuItem` (💥 breaking change)
- Add `endIcon` to `MenuItem`
- Add `closeOnMenuItemClick` prop, defaulted to `true`, on `Menu`

---

#### 💥  Breaking Change

- [AP-1335](https://apollographql.atlassian.net/browse/AP-1335): Remove `Menu` `instanceRef` prop and add `closeOnMenuItemClick` [#156](https://github.com/apollographql/space-kit/pull/156) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.25.2 (Tue Feb 11 2020)

#### 🐛  Bug Fix

- [AP-1335](https://apollographql.atlassian.net/browse/AP-1335): Fix broken animations again [#157](https://github.com/apollographql/space-kit/pull/157) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.25.1 (Fri Feb 07 2020)

#### 🐛  Bug Fix

- [AP-1335](https://apollographql.atlassian.net/browse/AP-1335): Fix animations not being disabled by `SpaceKitProvider` [#155](https://github.com/apollographql/space-kit/pull/155) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.25.0 (Tue Feb 04 2020)

### Release Notes

_From #153_

Create new `Menu` component and supporting components `MenuItem`, `MenuHeader`, and `MenuDivider`.

See https://zpl.io/adX0ELe for the original designs and the storybook docs page for usage instructions and examples.

This does not include any tests because I didn't know what to test. Any tests or ideas for tests would be most welcome!

---

#### 🚀  Enhancement

- [AP-1335](https://apollographql.atlassian.net/browse/AP-1335): Implement Menus [#153](https://github.com/apollographql/space-kit/pull/153) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.24.0 (Fri Jan 17 2020)

#### 🚀  Enhancement

- [AP-1023,AP-1312](https://apollographql.atlassian.net/browse/AP-1023/AP-1312): AP-1312 Implement `Tooltip` and `ConfirmationTooltip` [#150](https://github.com/apollographql/space-kit/pull/150) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.23.0 (Tue Jan 14 2020)

#### 🚀  Enhancement

- Add address icon [#152](https://github.com/apollographql/space-kit/pull/152) ([@jgzuke](https://github.com/jgzuke))

#### Authors: 1

- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))

---

# v2.22.0 (Fri Dec 20 2019)

#### 🚀  Enhancement

- feat(LoadingSpinner): Add `progressbar` role [#151](https://github.com/apollographql/space-kit/pull/151) ([@justinanastos](https://github.com/justinanastos))

#### 🏗  Internal

- [AP-1023](https://apollographql.atlassian.net/browse/AP-1023): Use rollup to bundle library [#149](https://github.com/apollographql/space-kit/pull/149) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.21.1 (Thu Dec 05 2019)

#### 🐛  Bug Fix

- Make tslib a proper dep [#147](https://github.com/apollographql/space-kit/pull/147) ([@jgzuke](https://github.com/jgzuke))

#### Authors: 1

- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))

---

# v2.21.0 (Wed Dec 04 2019)

#### 🚀  Enhancement

- [AP-1215](https://apollographql.atlassian.net/browse/AP-1215): Add `as` prop to `Modal` [#146](https://github.com/apollographql/space-kit/pull/146) ([@justinanastos](https://github.com/justinanastos) [@jgzuke](https://github.com/jgzuke))

#### Authors: 2

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))
- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))

---

# v2.20.0 (Mon Nov 25 2019)

#### 🚀  Enhancement

- Fix: avoid descriptions pushing actions off-screen - [AP-1138](https://apollographql.atlassian.net/browse/AP-1138) [#145](https://github.com/apollographql/space-kit/pull/145) ([@cheapsteak](https://github.com/cheapsteak))

#### Authors: 1

- Chang Wang ([@cheapsteak](https://github.com/cheapsteak))

---

# v2.19.0 (Fri Nov 22 2019)

#### 🚀  Enhancement

- Turn off syncAnimationRestarts for chromatic and buttons [#141](https://github.com/apollographql/space-kit/pull/141) ([@jgzuke](https://github.com/jgzuke))

#### Authors: 1

- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))

---

# v2.18.0 (Thu Nov 21 2019)

#### 🚀  Enhancement

- [AP-1222](https://apollographql.atlassian.net/browse/AP-1222): Add option to disable Modal animations [#142](https://github.com/apollographql/space-kit/pull/142) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.17.1 (Thu Nov 21 2019)

#### 🐛  Bug Fix

- Stop stripping comments from TypeScript builds [#143](https://github.com/apollographql/space-kit/pull/143) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.17.0 (Tue Nov 19 2019)

#### 🚀  Enhancement

- Change loader spin duration to 750ms [#140](https://github.com/apollographql/space-kit/pull/140) ([@jgzuke](https://github.com/jgzuke))

#### Authors: 1

- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))

---

# v2.16.0 (Mon Nov 18 2019)

#### 🚀  Enhancement

- [AP-1075](https://apollographql.atlassian.net/browse/AP-1075): Fix spinner remounting restarts [#137](https://github.com/apollographql/space-kit/pull/137) ([@jgzuke](https://github.com/jgzuke))

#### Authors: 1

- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))

---

# v2.15.0 (Mon Nov 18 2019)

#### 🚀  Enhancement

- [AP-786](https://apollographql.atlassian.net/browse/AP-786): ✨ add illustrations [#131](https://github.com/apollographql/space-kit/pull/131) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.14.3 (Mon Nov 18 2019)

#### 🐛  Bug Fix

- remove unnecessary scrollbar [#139](https://github.com/apollographql/space-kit/pull/139) ([@cheapsteak](https://github.com/cheapsteak))

#### 🏗  Internal

- Stop CI trying to run `check-label` [#138](https://github.com/apollographql/space-kit/pull/138) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 2

- Chang Wang ([@cheapsteak](https://github.com/cheapsteak))
- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.14.2 (Mon Nov 11 2019)

#### 🏠  Internal

- [AP-1165](https://apollographql.atlassian.net/browse/AP-1165): Disable label checks for PRs [#136](https://github.com/apollographql/space-kit/pull/136) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.14.1 (Thu Nov 07 2019)

### Release Notes

_From #134_

We tried setting a default height and width for icons, but this ran into issues with rectangular icons where we were required to set a width and a height. Per @daniman 's suggestion we'll just set the height. I chose to set it to the viewbox height and users can override this if they want to.

---

#### 🐛  Bug Fix

- [AP-1099](https://apollographql.atlassian.net/browse/AP-1099): Remove default width on icons [#134](https://github.com/apollographql/space-kit/pull/134) ([@justinanastos](https://github.com/justinanastos))

#### 🏗  Internal

- Improve `TextField` tests [#133](https://github.com/apollographql/space-kit/pull/133) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.14.0 (Wed Nov 06 2019)

#### 🚀  Enhancement

- [AP-1099](https://apollographql.atlassian.net/browse/AP-1099): Set default size of icons to be 20px by 20px [#132](https://github.com/apollographql/space-kit/pull/132) ([@justinanastos](https://github.com/justinanastos))

#### 📚  Documentation

- 📚 improve documentation for `as` prop in `Button` [#129](https://github.com/apollographql/space-kit/pull/129) ([@justinanastos](https://github.com/justinanastos))
- [AP-1071](https://apollographql.atlassian.net/browse/AP-1071): Write docs on how to use `npm link` with consuming libra… [#128](https://github.com/apollographql/space-kit/pull/128) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.13.0 (Thu Oct 03 2019)

#### 🚀  Enhancement

- Add framer-motion as peer-dep; animate modal [AP-812](https://apollographql.atlassian.net/browse/AP-812) [#126](https://github.com/apollographql/space-kit/pull/126) ([@cheapsteak](https://github.com/cheapsteak))

#### 🐛  Bug Fix

- Fix changelog configuration for adding jira links [#127](https://github.com/apollographql/space-kit/pull/127) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 2

- Chang Wang ([@cheapsteak](https://github.com/cheapsteak))
- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.12.0 (Thu Oct 03 2019)

#### 🚀  Enhancement

- [AP-919](https://apollographql.atlassian.net/AP-919): Stop propagation of clicks when disabled using input as [#122](https://github.com/apollographql/space-kit/pull/122) ([@jgzuke](https://github.com/jgzuke))

#### Authors: 1

- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))

---

# v2.11.0 (Wed Oct 02 2019)

#### 🚀  Enhancement

- [AP-1011](https://apollographql.atlassian.net/AP-1011): Stop wrapping long text in Buttons [#125](https://github.com/apollographql/space-kit/pull/125) ([@justinanastos](https://github.com/justinanastos))

#### 🐛  Bug Fix

- Update auto to add Jira links [#124](https://github.com/apollographql/space-kit/pull/124) ([@justinanastos](https://github.com/justinanastos))
- Upgrade storybook to production v5.2.1 [#123](https://github.com/apollographql/space-kit/pull/123) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.10.0 (Tue Sep 24 2019)

#### 🚀  Enhancement

- Add copy icon [#121](https://github.com/apollographql/space-kit/pull/121) ([@jgzuke](https://github.com/jgzuke))

#### Authors: 1

- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))

---

# v2.9.0 (Wed Sep 18 2019)

#### 🚀  Enhancement

- Imcrease modal max height and center contents [#120](https://github.com/apollographql/space-kit/pull/120) ([@jgzuke](https://github.com/jgzuke))

#### 🐛  Bug Fix

- Remove renovate [#119](https://github.com/apollographql/space-kit/pull/119) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 2

- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))
- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.8.1 (Wed Sep 18 2019)

### Release Notes

_From #106_

* GitHub actions are deprecating HCL syntax on September 30. This ensure that automatic release will continue to work while I'm on vacation.

* Convert our long-running task that re-runs `check-label` to "modern" JavaScript implementation with minimal custom logic

---

#### 🐛  Bug Fix

- AP-704 Setup and configure renovate [#105](https://github.com/apollographql/space-kit/pull/105) ([@justinanastos](https://github.com/justinanastos))
- AP-829 converted main.workflow to Actions V2 yml files [#106](https://github.com/apollographql/space-kit/pull/106) ([@justinanastos](https://github.com/justinanastos))

#### ⬆  Renovate Dependency Upgrade

- Pin dependencies [#91](https://github.com/apollographql/space-kit/pull/91) ([@renovate-bot](https://github.com/renovate-bot))

#### Authors: 2

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))
- Renovate Bot ([@renovate-bot](https://github.com/renovate-bot))

---

# v2.8.0 (Thu Sep 12 2019)

#### 🚀  Enhancement

- Add className to Modals [#103](https://github.com/apollographql/space-kit/pull/103) ([@jgzuke](https://github.com/jgzuke))

#### Authors: 1

- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))

---

# v2.7.0 (Wed Sep 11 2019)

#### 🚀  Enhancement

- Add the layout-module icon [#104](https://github.com/apollographql/space-kit/pull/104) ([@trevorblades](https://github.com/trevorblades))

#### Authors: 1

- Trevor Blades ([@trevorblades](https://github.com/trevorblades))

---

# v2.6.1 (Mon Sep 09 2019)

#### 🐛  Bug Fix

- AP-801 Show appropriate cursor for `Button`'s `loading` and `disa… [#97](https://github.com/apollographql/space-kit/pull/97) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.6.0 (Sun Sep 08 2019)

#### 🚀  Enhancement

- AP-808 Add `as` prop to `Modal` [#96](https://github.com/apollographql/space-kit/pull/96) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.5.1 (Sat Sep 07 2019)

#### 🐛  Bug Fix

- AP-808 Add `will-change` to `LoadingSpinner`'s animation [#93](https://github.com/apollographql/space-kit/pull/93) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.5.0 (Fri Sep 06 2019)

#### 🚀  Enhancement

- AP-808: passthrough `autoFocus` prop to underlying `input` in `Te… [#95](https://github.com/apollographql/space-kit/pull/95) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.4.0 (Fri Sep 06 2019)

### Release Notes

_From #92_

- Add `loading` prop to `Button`
- Add `theme="grayscale"` option to `LoadingSpinner`
- Make `LoadingSpinner` motion linear
- Write preliminary docs page for `LoadingSpinner`

Contributes to issue https://apollographql.atlassian.net/browse/AP-809

---

#### 🚀  Enhancement

- AP-809 Add loading state to button [#92](https://github.com/apollographql/space-kit/pull/92) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.3.0 (Wed Sep 04 2019)

#### 🚀  Enhancement

- AP-703: Write integration tests (AP-780) [#34](https://github.com/apollographql/space-kit/pull/34) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.2.1 (Fri Aug 30 2019)

#### 🐛  Bug Fix

- AP-783 set modal `max-height` to 60% [#89](https://github.com/apollographql/space-kit/pull/89) ([@cheapsteak](https://github.com/cheapsteak))

#### Authors: 1

- Chang Wang ([@cheapsteak](https://github.com/cheapsteak))

---

# v2.2.0 (Wed Aug 28 2019)

#### 🚀  Enhancement

- Remove font weight from smaller fonts [#87](https://github.com/apollographql/space-kit/pull/87) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.1.2 (Wed Aug 28 2019)

#### 🐛  Bug Fix

- fix(Card): Change font size for large card heading [#86](https://github.com/apollographql/space-kit/pull/86) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.1.1 (Wed Aug 28 2019)

#### 🐛  Bug Fix

- Button: add 12px padding and expanded content example [#79](https://github.com/apollographql/space-kit/pull/79) ([@evans](https://github.com/evans))

#### Authors: 1

- Evans Hauser ([@evans](https://github.com/evans))

---

# v2.1.0 (Tue Aug 27 2019)

#### 🚀  Enhancement

- Add onFocus prop to TextField type [#84](https://github.com/apollographql/space-kit/pull/84) ([@jgzuke](https://github.com/jgzuke))

#### Authors: 1

- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))

---

# v2.0.3 (Mon Aug 26 2019)

#### 🐛  Bug Fix

- fix(button): fix broken button clicks [#83](https://github.com/apollographql/space-kit/pull/83) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v2.0.1 (Fri Aug 23 2019)

#### 🐛  Bug Fix

- medium modals should have 32 px above actions [#78](https://github.com/apollographql/space-kit/pull/78) ([@mayakoneval](https://github.com/mayakoneval))

#### Authors: 1

- [@mayakoneval](https://github.com/mayakoneval)

---

# v2.0.0 (Fri Aug 23 2019)

#### 💥  Breaking Change

- Change `Button` `as` prop to only accept `React.ReactElement` [#80](https://github.com/apollographql/space-kit/pull/80) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v1.8.0 (Fri Aug 23 2019)

#### 🚀  Enhancement

- Add loading spinner [#75](https://github.com/apollographql/space-kit/pull/75) ([@jgzuke](https://github.com/jgzuke))

#### Authors: 1

- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))

---

# v1.7.2 (Thu Aug 22 2019)

#### 🐛  Bug Fix

- fix(TextField): Pass `name` and `type` to `<input>` [#76](https://github.com/apollographql/space-kit/pull/76) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v1.7.0 (Thu Aug 22 2019)

#### 🚀  Enhancement

- Add `inputAs` prop to `TextField` to customize how the underlying… [#72](https://github.com/apollographql/space-kit/pull/72) ([@justinanastos](https://github.com/justinanastos))

#### ⚠️  Pushed to master

- 1.6.0  ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

# v1.6.0 (Tue Aug 20 2019)

#### 🚀  Enhancement

- Add `as` prop to `Button` [#70](https://github.com/apollographql/space-kit/pull/70) ([@justinanastos](https://github.com/justinanastos))

#### 🐛 Bug Fix

- fix(button): fix disabled button style #70 ([@justinanastos](https://github.com/justinanastos))
- build: update ssh fingerprint to release through `apollo-bot2` #74 ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

# v1.5.1 (Thu Aug 15 2019)

### Release Notes

_From #69_

@justinanastos made an update to the TextField logic and didn't update the clean script. This fixes it.

---

#### 🐛  Bug Fix

- Correct npm script for cleaning TextField, make labels optional [#69](https://github.com/apollographql/space-kit/pull/69) ([@mayakoneval](https://github.com/mayakoneval))

#### Authors: 1

- [@mayakoneval](https://github.com/mayakoneval)

---

# v1.5.0 (Thu Aug 15 2019)

#### 🚀  Enhancement

- Small text field fixes [#67](https://github.com/apollographql/space-kit/pull/67) ([@jgzuke](https://github.com/jgzuke))

#### Authors: 1

- Jason Zukewich ([@jgzuke](https://github.com/jgzuke))

---

# v1.4.0 (Tue Aug 13 2019)

#### 🚀  Enhancement

- AP-544 Implement Text Inputs [#45](https://github.com/apollographql/space-kit/pull/45) ([@mayakoneval](https://github.com/mayakoneval) [@justinanastos](https://github.com/justinanastos))

#### Authors: 2

- [@mayakoneval](https://github.com/mayakoneval)
- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v1.3.1 (Mon Aug 12 2019)

#### 🐛  Bug Fix

- removed table header margins to match table body [#66](https://github.com/apollographql/space-kit/pull/66) (monsalve@mit.edu)

#### Authors: 1

- monsalve@mit.edu

---

# v1.3.0 (Mon Aug 12 2019)

#### 🚀  Enhancement

- feat(button): Replace feel="secondary" with color={colors.white} [#65](https://github.com/apollographql/space-kit/pull/65) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v1.2.0 (Mon Aug 12 2019)

#### 🚀  Enhancement

- Automatically calculate button text color [#64](https://github.com/apollographql/space-kit/pull/64) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v1.1.1 (Mon Aug 12 2019)

#### 🐛  Bug Fix

- install emotion dependencies in dependencies [#62](https://github.com/apollographql/space-kit/pull/62) ([@justinanastos](https://github.com/justinanastos))
- fix(button): center icons [#63](https://github.com/apollographql/space-kit/pull/63) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v1.1.0 (Sun Aug 11 2019)

#### 🚀  Enhancement

- AP-700 Export `emotionCacheProviderFactory` so allow consumers to… [#46](https://github.com/apollographql/space-kit/pull/46) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v1.0.6 (Fri Aug 09 2019)

### Release Notes

_From #58_

There's no easy way to override the classes that we're putting on our Space Kit components until https://github.com/apollographql/space-kit/pull/46 lands. We can't put default sizes on icons because they can't be overridden yet.

---

#### 🐛  Bug Fix

- Change `Icon` to have `thin` and `normal` weights [#59](https://github.com/apollographql/space-kit/pull/59) ([@justinanastos](https://github.com/justinanastos))
- remove default size on icons [#58](https://github.com/apollographql/space-kit/pull/58) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v1.0.5 (Thu Aug 08 2019)

### Release Notes

_From #57_

* Refactor icon conversion script to use `@babel/types` instead of `immutability-helper` and trying to craft AST by hand. That was too opaque and it wasn't type safe. Now we're safe and it's as concise as it's going to get.

* Move intermediate icon files to `src/icons`

    This makes them accessible from anywhere else _and_ gives them access to other modules. We _were_ going to use this for the `EmotionProvider`, but now we aren't. This is less elegant and clever, but makes more sense and will make our code actually work.

---

#### 🐛  Bug Fix

- Refactor icon generation [#57](https://github.com/apollographql/space-kit/pull/57) ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# v1.0.4 (Thu Aug 08 2019)

#### 🐛  Bug Fix

- Test automatic releases [#56](https://github.com/apollographql/space-kit/pull/56) ([@justinanastos](https://github.com/justinanastos))

#### ⚠️  Pushed to master

- 1.0.3  ([@justinanastos](https://github.com/justinanastos))
- Use read-write key for deploys  ([@justinanastos](https://github.com/justinanastos))
- still working on automatic releases  ([@justinanastos](https://github.com/justinanastos))

#### Authors: 1

- Justin Anastos ([@justinanastos](https://github.com/justinanastos))

---

# Changelog

## Upcoming

- Added colProps property to the table columns [#32](https://github.com/apollographql/space-kit/pull/32)

## [`v0.7.3`](https://github.com/apollographql/space-kit/releases/tag/v0.7.3)

- Remove `.awcache` from releases
- Remove eslint cache and config from releases

## [`v0.7.0`](https://github.com/apollographql/space-kit/releases/tag/v0.7.0)

- Convert all remaining files to TypeScript (#27)
- Move all `src` files to live in paths (#31)
- Fix broken storybook (#39)
- Remove top level Space Kit namespace in Storybook (#38)
- Make Icon weight configurable (#33)
- Edit Modal prop descriptions, fix margin top on children [#41](https://github.com/apollographql/space-kit/pull/41)
- Export constant from `colors` instead of requiring `import * as colors` (#35)
- Add Card component (#34)
- Text Inputs and Steppers [(#45)](https://github.com/apollographql/space-kit/pull/45)

## [`v0.6.2`](https://github.com/apollographql/space-kit/releases/tag/v0.6.2)

- Remove tsconfig.buildinfo from builds (#30)

## [`v0.6.1`](https://github.com/apollographql/space-kit/releases/tag/v0.6.1)

- Roll back changes for custom css injection point in favor of documentation on how todo it yourself (#xx, [AP-543](https://golinks.io/j/AP-543))
- Move `@emotion/core` to `dependencies` so consumers will install it automatically (#xx, [AP-543](https://golinks.io/j/AP-543))
- Refactor Buttons implementation and change external interface (#26, [AP-543](https://golinks.io/j/AP-543))
- Implement Modals (#22, [AP-545](https://golinks.io/j/AP-545))
- Implement Tables (#21, [AP-546](https://golinks.io/j/AP-546))

## [`v0.4.1`](https://github.com/apollographql/space-kit/releases/tag/v0.4.1)

- Allow custom emotion css injection point (#23, [AP-543](https://golinks.io/j/AP-543))

## [`v0.4.0`](https://github.com/apollographql/space-kit/releases/tag/v0.4.0)

- Add buttons implementation (#10, [AP-543](https://golinks.io/j/AP-543))

## [`v0.2.0`](https://github.com/apollographql/space-kit/releases/tag/v0.2.0)

- Add initial typography implementation (#8, [AP-542](https://golinks.io/j/AP-542))
