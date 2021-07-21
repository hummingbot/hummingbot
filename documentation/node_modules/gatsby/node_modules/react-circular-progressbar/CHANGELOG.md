## 2.0.2

- Import react with "\* as React" to prevent the need to use allowSyntheticDefaultExports/esModuleInterop in consumers (issue #110) #112

## 2.0.1

- Fix vertical centering of CircularProgressbarWithChildren [#96]

## 2.0.0

- Add buildStyles utility, and make CircularProgressbar a named import [#86]
- Add <CircularProgressbarWithChildren /> wrapper component [#87]
- Remove initialAnimation prop in favor of percentage being controlled externally [#88]
- Replace props.percentage with props.value, and add minValue and maxValue [#89]
- Update docs for v2.0.0 [#90]

## 1.2.1

- Use Rollup to build package [#83]
- Extract Path component into separate file [#84]

## 1.2.0

- Add props.circleRatio to enable partial diameter "car speedometer" style [#80]

## 1.1.0

- Convert project to Typescript and improve demo setup [#77]
- Remove prop-types dependency [#78]

  1.1.0 now uses Typescript!

There should not be any breaking changes to the public JS interface. However, the slight discrepancy in typing may cause type errors when switching from 1.0 using DefinitelyTyped. Runtime prop-types checking is also now removed in [#78].

## 1.0.0

We're at 1.0.0! 🎉 Thank you to all the contributors and issue creators.

- Add text prop and remove textForPercentage and classForPercentage props [#61]

## 0.8.1

- Use styles.root style hook properly [#60]

## 0.8.0

- Check in build files to `/dist` and enable importing styles from `dist/styles.css` [#40][#45]

## 0.7.0

- Add `styles` prop for customizing inline styles [#42]

## 0.6.0

- Add `counterClockwise` prop for having progressbar go in opposite direction [#39]

## 0.5.0

- Add `classes` prop for customizing svg element classNames [#25]

## 0.4.1

- Don't render <text> when textForPercentage is falsy

## 0.4.0

- Add `background` prop, fix black circle issue for upgrading without new CSS

## 0.3.0

- Support custom background colors and added `backgroundPadding` prop [#23]

## 0.2.2

- Allow react 16 as a peerDependency

## 0.2.1

- Restrict percentages to be between 0 and 100
- Fix "undefined" className when it's unset

## 0.2.0

- Adds `className` prop to customize component styles

## 0.1.5

- Fixes 'calling PropTypes validators directly' issue caused by prop-types package by upgrading to 15.5.10+

## 0.1.4

- Fixes React PropTypes import warning by using prop-types package
- Upgrades devDependencies

## 0.1.3

- Fix errors when component is unmounted immediately [#1]

## 0.1.2

- Tweak initialAnimation behavior
- Fix package.json repo URL

## 0.1.1

- Remove unused dependencies

## 0.1.0

- Initial working version
