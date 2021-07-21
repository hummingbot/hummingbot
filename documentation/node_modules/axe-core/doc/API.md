# Axe Javascript Accessibility API

## Table of Contents

1. [Section 1: Introduction](#section-1-introduction)
   1. [Get Started](#getting-started)
1. [Section 2: API Reference](#section-2-api-reference)
   1. [Overview](#overview)
   1. [Required Globals](#required-globals)
   1. [API Notes](#api-notes)
   1. [API Name: axe.getRules](#api-name-axegetrules)
   1. [API Name: axe.configure](#api-name-axeconfigure)
   1. [API Name: axe.reset](#api-name-axereset)
   1. [API Name: axe.run](#api-name-axerun)
      1. [Parameters axe.run](#parameters-axerun)
         1. [Context Parameter](#context-parameter)
         2. [Options Parameter](#options-parameter)
         3. [Callback Parameter](#callback-parameter)
      1. [Return Promise](#return-promise)
      1. [Error result](#error-result)
      1. [Results Object](#results-object)
   1. [API Name: axe.registerPlugin](#api-name-axeregisterplugin)
   1. [API Name: axe.cleanup](#api-name-axecleanup)
   1. [Virtual DOM Utilities](#virtual-dom-utilities)
      1. [API Name: axe.utils.querySelectorAll](#api-name-axeutilsqueryselectorall)
   1. [Common Functions](#common-functions)
1. [Section 3: Example Reference](#section-3-example-reference)
1. [Section 4: Performance](#section-4-performance)

## Section 1: Introduction

The axe API is designed to be an improvement over the previous generation of accessibility APIs. It provides the following benefits:

- Runs in any modern browser
- Designed to work with existing testing infrastructure
- Runs locally, no connection to a third-party server is necessary
- Performs violation checking on multiple levels of nested iframes
- Provides list of rules and elements that passed accessibility checking, ensuring rules have been run against entire document
- Only checks rendered content to minimize false positives (that includes visually-hidden content)

### Getting Started

This section gives a quick description of how to use the axe APIs to analyze web page content and return a JSON object that lists any accessibility violations found.

The axe API can be used as part of a broader process that is performed on many, if not all, pages of a website. The API is used to analyze web page content and return a JSON object that lists any accessibility violations found. Here is how to get started:

1. Load page in testing system
2. Optionally, set configuration options for the javascript API (`axe.configure`)
3. Call analyze javascript API (`axe.run`)
4. Either assert against results or save them for later processing
5. Repeat for any inactive or non-rendered content after making it visible

## Section 2: API Reference

### Overview

The axe APIs are provided in the javascript file axe.js. It must be included in the web page under test. Parameters are sent as javascript function parameters. Results are returned in JSON format.

### Required Globals

Axe requires a handful of global variables and interfaces to be available in order to run. See the [jsdom example](https://github.com/dequelabs/axe-core/blob/develop/doc/examples/jsdom/test/a11y.js) for how to set these up in a non-browser environment.

- `window`
- `document`
- [`navigator`](https://developer.mozilla.org/en-US/docs/Web/API/Window/navigator)
- [`Node`](https://developer.mozilla.org/en-US/docs/Web/API/Node)
- [`NodeList`](https://developer.mozilla.org/en-US/docs/Web/API/NodeList)
- [`Element`](https://developer.mozilla.org/en-US/docs/Web/API/Element)
- [`Document`](https://developer.mozilla.org/en-US/docs/Web/API/Document)

### Full API Reference for Developers

For a full listing of API offered by axe, clone the repository and run `npm run api-docs`. This generates `jsdoc` documentation under `doc/api` which can be viewed using the browser.

### API Notes

- A Rule test is made up of sub-tests. Each sub-test is returned in an array of 'checks'
- The `"helpUrl"` in the results object is a link to a broader description of the accessibility issue and suggested remediation. These links point to Deque University help pages, which do not require a login.
- Axe does not test hidden regions, such as inactive menus or modal windows. To test those for accessibility, write tests that activate or render the regions visible and run the analysis again.

### API Name: axe.getRules

#### Purpose

To get information on all the rules in the system.

#### Description

Returns a list of all rules with their ID and description

#### Synopsis

`axe.getRules([Tag Name 1, Tag Name 2...]);`

#### Parameters

- `tags` - **optional** Array of tags used to filter returned rules. If omitted, it will return all rules.

**Returns:** Array of rules that match the input filter with each entry having a format of `{ruleId: <id>, description: <desc>}`

The current set of tags supported are listed in the following table:

| Tag Name        |       Accessibility Standard/Purpose        |
| --------------- | :-----------------------------------------: |
| `wcag2a`        |         WCAG 2.0 & WCAG 2.1 Level A         |
| `wcag2aa`       |        WCAG 2.0 & WCAG 2.1 Level AA         |
| `wcag21a`       |              WCAG 2.1 Level A               |
| `wcag21aa`      |              WCAG 2.1 Level AA              |
| `section508`    |                 Section 508                 |
| `best-practice` |      Best practices endorsed by Deque       |
| `experimental`  |           Cutting-edge techniques           |
| `cat`           | Category mappings used by Deque (see below) |

| Category name                 |
| ----------------------------- |
| `cat.aria`                    |
| `cat.color`                   |
| `cat.forms`                   |
| `cat.keyboard`                |
| `cat.language`                |
| `cat.name-role-value`         |
| `cat.parsing`                 |
| `cat.semantics`               |
| `cat.sensory-and-visual-cues` |
| `cat.structure`               |
| `cat.tables`                  |
| `cat.text-alternatives`       |
| `cat.time-and-media`          |

#### Example 1

In this example, we pass in the WCAG 2 A and AA tags into `axe.getRules` to retrieve only those rules. The function call returns an array of rules.

**Call:** `axe.getRules(['wcag2aa', 'wcag2a']);`

**Returned Data:**

```js
[
  { ruleId: "area-alt", description: "Checks the <area> elements of image…" },
  { ruleId: "aria-allowed-attr", description: "Checks all attributes that start…" },
  { ruleId: "aria-required-attr", description: "Checks all elements that contain…" },
  …
]
```

### API Name: axe.configure

#### Purpose

To configure the format of the data used by axe. This can be used to add new rules, which must be registered with the library to execute.

#### Description

User specifies the format of the JSON structure passed to the callback of `axe.run`

#### Synopsis

```js
axe.configure({
	branding: {
		brand: String,
		application: String
	},
	reporter: 'option',
	checks: [Object],
	rules: [Object],
	locale: Object,
	axeVersion: String
});
```

#### Parameters

- `configurationOptions` - Options object; where the valid name, value pairs are:
  - `branding` - mixed(optional) Used to set the branding of the helpUrls
    - `brand` - string(optional) sets the brand string - default "axe"
    - `application` - string(optional) sets the application string - default "axeAPI"
  - `reporter` - Used to set the output format that the axe.run function will pass to the callback function
    - `v1` to use the previous version's format: `axe.configure({ reporter: "v1" });`
    - `v2` to use the current version's format: `axe.configure({ reporter: "v2" });`
    - `raw` to return the raw result data without formating: `axe.configure({ reporter: "raw" });`
    - `raw-env` to return the raw result data with environment data: `axe.configure({ reporter: "raw-env" });`
    - `no-passes` to return only violation results: `axe.configure({ reporter: "no-passes" });`
  - `checks` - Used to add checks to the list of checks used by rules, or to override the properties of existing checks
    - The checks attribute is an array of check objects
    - Each check object can contain the following attributes
      - `id` - string(required). This uniquely identifies the check. If the check already exists, this will result in any supplied check properties being overridden. The properties below that are marked required if new are optional when the check is being overridden.
      - `evaluate` - function(required for new). This is the function that implements the check's functionality.
      - `after` - function(optional). This is the function that gets called for checks that operate on a page-level basis, to process the results from the iframes.
      - `options` - mixed(optional). This is the options structure that is passed to the evaluate function and is intended to be used to configure checks. It is the most common property that is intended to be overridden for existing checks.
      - `enabled` - boolean(optional, default `true`). This is used to indicate whether the check is on or off by default. Checks that are off are not evaluated, even when included in a rule. Overriding this is a common way to disable a particular check across multiple rules.
  - `rules` - Used to add rules to the existing set of rules, or to override the properties of existing rules
    - The rules attribute is an Array of rule objects
    - each rule object can contain the following attributes
      - `id` - string(required). This uniquely identifies the rule. If the rule already exists, it will be overridden with any of the attributes supplied. The attributes below that are marked required, are only required for new rules.
      - `selector` - string(optional, default `*`). A [CSS selector](./developer-guide.md#supported-css-selectors) used to identify the elements that are passed into the rule for evaluation.
      - `excludeHidden` - boolean(optional, default `true`). This indicates whether elements that are hidden from all users are to be passed into the rule for evaluation.
      - `enabled` - boolean(optional, default `true`). Whether the rule is turned on. This is a common attribute for overriding.
      - `pageLevel` - boolean(optional, default `false`). When set to true, this rule is only applied when the entire page is tested. Results from nodes on different frames are combined into a single result. See [page level rules](#page-level-rules).
      - `any` - array(optional, default `[]`). This is a list of checks that, if none "pass", will generate a violation.
      - `all` - array(optional, default `[]`). This is a list of checks that, if any "fails", will generate a violation.
      - `none` - array(optional, default `[]`). This is a list of checks that, if any "pass", will generate a violation.
      - `tags` - array(optional, default `[]`). A list if the tags that "classify" the rule. In practice, you must supply some valid tags or the default evaluation will not invoke the rule. The convention is to include the standard (WCAG 2 and/or section 508), the WCAG 2 level, Section 508 paragraph, and the WCAG 2 success criteria. Tags are constructed by converting all letters to lower case, removing spaces and periods and concatenating the result. E.g. WCAG 2 A success criteria 1.1.1 would become ["wcag2a", "wcag111"]
      - `matches` - string(optional, default `*`). A filtering [CSS selector](./developer-guide.md#supported-css-selectors) that will exclude elements that do not match the CSS selector.
  - `disableOtherRules` - Disables all rules not included in the `rules` property.
  - `locale` - A locale object to apply (at runtime) to all rules and checks, in the same shape as `/locales/*.json`.
  - `axeVersion` - Set the compatible version of a custom rule with the current axe version. Compatible versions are all patch and minor updates that are the same as, or newer than those of the `axeVersion` property.

**Returns:** Nothing

##### Page level rules

Page level rules split their evaluation into two phases. A 'data collection' phase which is done inside the 'evaluate' function and an assessment phase which is done inside the 'after' function. The evaluate function executes inside each individual frame and is responsible for collection data that is passed into the after function which inspects that data and makes a decision.

Page level rules raise violations on the entire document and not on individual nodes or frames from which the data was collected. For an example of how this works, see the heading order check:

- [lib/checks/navigation/heading-order.json](https://github.com/dequelabs/axe-core/blob/master/lib/checks/navigation/heading-order.json)
- [lib/checks/navigation/heading-order.js](https://github.com/dequelabs/axe-core/blob/master/lib/checks/navigation/heading-order.js)
- [lib/checks/navigation/heading-order-after.js](https://github.com/dequelabs/axe-core/blob/master/lib/checks/navigation/heading-order-after.js)

### API Name: axe.reset

#### Purpose

Reset the configuration to the default configuration.

#### Description

Override any previous calls to `axe.configure` and restore the configuration to the default configuration. Note: this will NOT unregister any new rules or checks that were registered but will reset the configuration back to the default configuration for everything else.

#### Synopsis

```js
axe.reset();
```

#### Parameters

None

### API Name: axe.run

#### Purpose

Analyze rendered content on the currently loaded page

#### Description

Runs a number of rules against the provided HTML page and returns the resulting issue list

#### Synopsis

```js
axe.run(context, options, (err, results) => {
	// ...
});
```

#### Parameters axe.run

- [`context`](#context-parameter): (optional) Defines the scope of the analysis - the part of the DOM that you would like to analyze. This will typically be the `document` or a specific selector such as class name, ID, selector, etc.
- [`options`](#options-parameter): (optional) Set of options passed into rules or checks, temporarily modifying them. This contrasts with `axe.configure`, which is more permanent.
- [`callback`](#callback-parameter): (optional) The callback function which receives either null or an [error result](#error-result) as the first parameter, and the [results object](#results-object) when analysis is completed successfully, or undefined if it did not.

##### Context Parameter

By default, `axe.run` will test the entire document. The context object is an optional parameter that can be used to specify which element should and which should not be tested. It can be passed one of the following:

1. An element reference that represents the portion of the document that must be analyzed
   - Example: To limit analysis to the `<div id="content">` element: `document.getElementById("content")`
1. A NodeList such as returned by `document.querySelectorAll`.
1. A [CSS selector](./developer-guide.md#supported-css-selectors) that selects the portion(s) of the document that must be analyzed.
1. An include-exclude object (see below)

###### Include-Exclude Object

The include exclude object is a JSON object with two attributes: include and exclude. Either include or exclude is required. If only `exclude` is specified; include will default to the entire `document`.

- A node, or
- An array of arrays of [CSS selectors](./developer-guide.md#supported-css-selectors)
  - If the nested array contains a single string, that string is the CSS selector
  - If the nested array contains multiple strings
    - The last string is the final CSS selector
    - All other's are the nested structure of iframes inside the document

In most cases, the component arrays will contain only one CSS selector. Multiple CSS selectors are only required if you want to include or exclude regions of a page that are inside iframes (or iframes within iframes within iframes). In this case, the first n-1 selectors are selectors that select the iframe(s) and the nth selector, selects the region(s) within the iframe.

###### Context Parameter Examples

1. Include the first item in the `$fixture` NodeList but exclude its first child

```js
axe.run(
	{
		include: $fixture[0],
		exclude: $fixture[0].firstChild
	},
	(err, results) => {
		// ...
	}
);
```

2. Include the element with the ID of `fix` but exclude any `div`s within it

```js
axe.run(
	{
		include: [['#fix']],
		exclude: [['#fix div']]
	},
	(err, results) => {
		// ...
	}
);
```

3. Include the whole document except any structures whose parent contains the class `exclude1` or `exclude2`

```js
axe.run(
	{
		exclude: [['.exclude1'], ['.exclude2']]
	},
	(err, results) => {
		// ...
	}
);
```

4. Include the element with the ID of `fix`, within the iframe with id `frame`

```js
axe.run(
	{
		include: [['#frame', '#fix']]
	},
	(err, results) => {
		// ...
	}
);
```

5. Include the element with the ID of `fix`, within the iframe with id `frame2`, within the iframe with id `frame1`

```js
axe.run(
	{
		include: [['#frame1', '#frame2', '#fix']]
	},
	(err, results) => {
		// ...
	}
);
```

6. Include the following:

- The element with the ID of `fix`, within the iframe with id `frame2`, within the iframe with id `frame1`
- The element with id `header`
- All links

```js
axe.run(
	{
		include: [['#header'], ['a'], ['#frame1', '#frame2', '#fix']]
	},
	(err, results) => {
		// ...
	}
);
```

##### Options Parameter

The options parameter is flexible way to configure how `axe.run` operates. The different modes of operation are:

- Run all rules corresponding to one of the accessibility standards
- Run all rules defined in the system, except for the list of rules specified
- Run a specific set of rules provided as a list of rule ids

Additionally, there are a number or properties that allow configuration of different options:

| Property           | Default | Description                                                                                                                             |
| ------------------ | :------ | :-------------------------------------------------------------------------------------------------------------------------------------- |
| `runOnly`          | n/a     | Limit which rules are executed, based on names or tags                                                                                  |
| `rules`            | n/a     | Allow customizing a rule's properties (including { enable: false })                                                                     |
| `reporter`         | `v1`    | Which reporter to use (see [Configuration](#api-name-axeconfigure))                                                                     |
| `resultTypes`      | n/a     | Limit which result types are processed and aggregated                                                                                   |
| `xpath`            | `false` | Return xpath selectors for elements                                                                                                     |
| `absolutePaths`    | `false` | Use absolute paths when creating element selectors                                                                                      |
| `iframes`          | `true`  | Tell axe to run inside iframes                                                                                                          |
| `elementRef`       | `false` | Return element references in addition to the target                                                                                     |
| `restoreScroll`    | `false` | Scrolls elements back to before axe started                                                                                             |
| `frameWaitTime`    | `60000` | How long (in milliseconds) axe waits for a response from embedded frames before timing out                                              |
| `preload`          | `true`  | Any additional assets (eg: cssom) to preload before running rules. [See here for configuration details](#preload-configuration-details) |
| `performanceTimer` | `false` | Log rule performance metrics to the console                                                                                             |

###### Options Parameter Examples

1. Run only Rules for an accessibility standard

There are certain standards defined that can be used to select a set of rules. The defined standards and tag string are defined as follows:

| Tag Name        |      Accessibility Standard      |
| --------------- | :------------------------------: |
| `wcag2a`        |         WCAG 2.0 Level A         |
| `wcag2aa`       |        WCAG 2.0 Level AA         |
| `section508`    |           Section 508            |
| `best-practice` | Best practices endorsed by Deque |

To run only WCAG 2.0 Level A rules, specify `options` as:

```js
axe.run(
	{
		runOnly: {
			type: 'tag',
			values: ['wcag2a']
		}
	},
	(err, results) => {
		// ...
	}
);
```

To run both WCAG 2.0 Level A and Level AA rules, you must specify both `wcag2a` and `wcag2aa`:

```js
axe.run(
	{
		runOnly: {
			type: 'tag',
			values: ['wcag2a', 'wcag2aa']
		}
	},
	(err, results) => {
		// ...
	}
);
```

Alternatively, runOnly can be passed an array of tags:

```js
axe.run({
	runOnly: ['wcag2a', 'wcag2aa'];
}, (err, results) => {
  // ...
})
```

2. Run only a specified list of Rules

If you only want to run certain rules, specify options as:

```js
axe.run(
	{
		runOnly: {
			type: 'rule',
			values: ['ruleId1', 'ruleId2', 'ruleId3']
		}
	},
	(err, results) => {
		// ...
	}
);
```

This example will only run the rules with the id of `ruleId1`, `ruleId2`, and `ruleId3`. No other rule will run.

Alternatively, runOnly can be passed an array of rules:

```js
axe.run({
  runOnly: ['ruleId1', 'ruleId2', 'ruleId3'];
}, (err, results) => {
  // ...
})
```

3. Run all enabled Rules except for a list of rules

The default operation for axe.run is to run all rules except for rules with the "experimental" tag. If certain rules should be disabled from being run, specify `options` as:

```js
axe.run(
	{
		rules: {
			'color-contrast': { enabled: false },
			'valid-lang': { enabled: false }
		}
	},
	(err, results) => {
		// ...
	}
);
```

This example will disable the rules with the id of `color-contrast` and `valid-lang`. All other rules will run. The list of valid rule IDs is specified in the section below.

4. Run a modified set or rules using tags and rule enable

By combining runOnly with type: tags and the rules option, a modified set can be defined. This lets you include rules with unspecified tags, and exclude rules that do have the specified tag(s).

```js
axe.run(
	{
		runOnly: {
			type: 'tag',
			values: ['wcag2a']
		},
		rules: {
			'color-contrast': { enabled: true },
			'valid-lang': { enabled: false }
		}
	},
	(err, results) => {
		// ...
	}
);
```

This example includes all level A rules except for valid-lang, and in addition will include the level AA color-contrast rule.

6. Only process certain types of results

The `resultTypes` option can be used to limit the number of nodes for a rule to a maximum of one. This can be useful for improving performance on very large or complicated pages when you are only interested in certain types of results.

After axe has processed all rules normally, it generates a unique selector for all nodes in all rules. This process can be time consuming, especially for pages with lots of nodes. By limiting the nodes to a maximum of one for result types you are not interested in, you can greatly speed up the tail end performance of axe.

Types listed in this option will cause rules that fall under those types to show all nodes. Types _not_ listed will causes rules that fall under one of the missing types to show a maximum of one node. This allows you to still see those results and inform the user of them if appropriate.

```js
axe.run(
	{
		resultTypes: ['violations', 'incomplete', 'inapplicable']
	},
	(err, results) => {
		// ...
	}
);
```

This example will return all the nodes for all rules that fall under the "violations", "incomplete", and "inapplicable" result types. Since the "passes" type was not specified, it will return at most one node for each rule that passes.

###### <a id='preload-configuration-details'></a> Preload Configuration in Options Parameter

The `preload` attribute (defaults to `true`) in options parameter, accepts a `boolean` or an `object` where an array of assets can be specified.

1. Specifying a `boolean`

```js
axe.run(
	{
		preload: true
	},
	(err, results) => {
		// ...
	}
);
```

2. Specifying an `object`

```js
axe.run(
	{
		preload: { assets: ['cssom'], timeout: 50000 }
	},
	(err, results) => {
		// ...
	}
);
```

The `assets` attribute expects an array of preload(able) constraints to be fetched. The current set of values supported for `assets` is listed in the following table:

| Asset Type | Description                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| :--------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `cssom`    | This asset type preloads all CSS Stylesheets rulesets specified in the page. The stylesheets can be an external cross-domain resource, a relative stylesheet or an inline style with in the head tag of the document. If the stylesheet is an external cross-domain a network request is made. An object representing the CSS Rules from each stylesheet is made available to the checks evaluate function as `preloadedAssets` at run-time |
| `media`    | This asset type preloads metadata information of any HTMLMediaElement in the specified document                                                                                                                                                                                                                                                                                                                                             |

The `timeout` attribute in the object configuration is `optional` and has a fallback default value (10000ms). The `timeout` is essential for any network dependent assets that are preloaded, where-in if a given request takes longer than the specified/ default value, the operation is aborted.

##### Callback Parameter

The callback parameter is a function that will be called when the asynchronous `axe.run` function completes. The callback function is passed two parameters. The first parameter will be an error thrown inside of axe if axe.run could not complete. If axe completed correctly the first parameter will be null, and the second parameter will be the results object.

#### Return Promise

If the callback was not defined, axe will return a Promise instead. Axe does not polyfill a Promise library however. So on systems without support for Promises this feature is not available. If you are unsure if the systems you will need axe on has Promise support we suggest you use the callback provided by axe.run instead.

#### Error Result

This will either be null or an object which is an instance of Error. If you are consistently receiving errors, please report this issue on the [Github issues list of Axe](https://github.com/dequelabs/axe-core/issues).

#### Results Object

The callback function passed in as the third parameter of `axe.run` runs on the results object. This object has four components – a `passes` array, a `violations` array, an `incomplete` array and an `inapplicable` array.

The `passes` array keeps track of all the passed tests, along with detailed information on each one. This leads to more efficient testing, especially when used in conjunction with manual testing, as the user can easily find out what tests have already been passed.

Similarly, the `violations` array keeps track of all the failed tests, along with detailed information on each one.

The `incomplete` array (also referred to as the "review items") indicates which nodes could neither be determined to definitively pass or definitively fail. They are separated out in order that a user interface can display these to the user for manual review (hence the term "review items").

The `inapplicable` array lists all the rules for which no matching elements were found on the page.

###### `url`

The URL of the page that was tested.

###### `timestamp`

The date and time that analysis was completed.

###### result arrays

The results of axe are grouped according to their outcome into the following arrays:

- `passes`: These results indicate what elements passed the rules
- `violations`: These results indicate what elements failed the rules
- `inapplicable`: These results indicate which rules did not run because no matching content was found on the page. For example, with no video, those rules won't run.
- `incomplete`: These results were aborted and require further testing. This can happen either because of technical restrictions to what the rule can test, or because a javascript error occurred.

Each object returned in these arrays have the following properties:

- `description` - Text string that describes what the rule does
- `help` - Help text that describes the test that was performed
- `helpUrl` - URL that provides more information about the specifics of the violation. Links to a page on the Deque University site.
- `id` - Unique identifier for the rule; [see the list of rules](rule-descriptions.md)
- `impact` - How serious the violation is. Can be one of "minor", "moderate", "serious", or "critical" if the Rule failed or `null` if the check passed
- `tags` - Array of tags that this rule is assigned. These tags can be used in the option structure to select which rules are run ([see `axe.run` parameters for more information](#parameters-axerun)).
- `nodes` - Array of all elements the Rule tested
  - `html` - Snippet of HTML of the Element
  - `impact` - How serious the violation is. Can be one of "minor", "moderate", "serious", or "critical" if the test failed or `null` if the check passed
  - `target` - Array of either strings or Arrays of strings. If the item in the array is a string, then it is a CSS selector. If there are multiple items in the array each item corresponds to one level of iframe or frame. If there is one iframe or frame, there should be two entries in `target`. If there are three iframe levels, there should be four entries in `target`. If the item in the Array is an Array of strings, then it points to an element in a shadow DOM and each item (except the n-1th) in this array is a selector to a DOM element with a shadow DOM. The last element in the array points to the final shadow DOM node.
  - `any` - Array of checks that were made where at least one must have passed. Each entry in the array contains:
    - `id` - Unique identifier for this check. Check ids may be the same as Rule ids
    - `impact` - How serious this particular check is. Can be one of "minor", "moderate", "serious", or "critical". Each check that is part of a rule can have different impacts. The highest impact of all the checks that fail is reported for the rule
    - `message` - Description of why this check passed or failed
    - `data` - Additional information that is specific to the type of Check which is optional. For example, a color contrast check would include the foreground color, background color, contrast ratio, etc.
    - `relatedNodes` - Optional array of information about other nodes that are related to this check. For example, a duplicate id check violation would list the other selectors that had this same duplicate id. Each entry in the array contains the following information:
      - `target` - Array of selectors for the related node
      - `html` - HTML source of the related node
  - `all` - Array of checks that were made where all must have passed. Each entry in the array contains the same information as the 'any' array
  - `none` - Array of checks that were made where all must have not passed. Each entry in the array contains the same information as the 'any' array

#### Example 2

In this example, we will pass the selector for the entire document, pass no options, which means all enabled rules will be run, and have a simple callback function that logs the entire results object to the console log:

```js
axe.run(document, function(err, results) {
	if (err) throw err;
	console.log(results);
});
```

###### `passes`

- `passes[0]`
  ...

  - `help` - `"Elements must have sufficient color contrast"`
  - `helpUrl` - `"https://dequeuniversity.com/courses/html-css/visual-layout/color-contrast"`
  - `id` - `"color-contrast"`
    - `nodes`
      - `target[0]` - `"#js_off-canvas-wrap > .inner-wrap >.kinja-title.proxima.js_kinja-title-desktop"`

- `passes[1]`
  ...

###### `violations`

- `violations[0]`

  - `help` - `"<button> elements must have alternate text"`
  - `helpUrl` - `"https://dequeuniversity.com/courses/html-css/forms/form-labels#id84_example_button"`
  - `id` - `"button-name"`
    - `nodes`
      - `target[0]` - `"post_5919997 > .row.content-wrapper > .column > span > iframe"`
      - `target[1]` - `"#u_0_1 > .pluginConnectButton > .pluginButtonImage > button"`

- `violations[1]` ...

##### `passes` Results Array

In the example above, the `passes` array contains two entries that correspond to the two rules tested. The first element in the array describes a color contrast check. It relays the information that a list of nodes was checked and subsequently passed. The `help`, `helpUrl`, and `id` fields are returned as expected for each of the entries in the `passes` array. The `target` array has one element in it with a value of

`#js_off-canvas-wrap > .inner-wrap >.kinja-title.proxima.js_kinja-title-desktop`

This indicates that the element selected by the entry in `target[0]` was checked for the color contrast rule and that it passed the test.

Each subsequent entry in the passes array has the same format, but will detail the different rules that were run as part of this call to `axe.run()`.

##### `violations` Results Array

The array of `violations` contains one entry; this entry describes a test that check if buttons have valid alternate text (button-name). This first entry in the array has the `help`, `helpUrl` and `id` fields returned as expected.

The `target` array demonstrates how we specify the selectors when the node specified is inside of an `iframe` or `frame`. The first element in the `target` array - `target[0]` - specifies the selector to the `iframe` that contains the button. The second element in the `target` array - `target[1]` - specifies the selector to the actual button, but starting from inside the iframe selected in `target[0]`.

Each subsequent entry in the violations array has the same format, but will detail the different rules that were run that generated accessibility violations as part of this call to `axe.run()`.

#### Example 3

In this example, we pass the selector for the entire document, enable two additional experimental rules, and have a simple callback function that logs the entire results object to the console log:

```js
axe.run(
	document,
	{
		rules: {
			'link-in-text-block': { enabled: true },
			'p-as-heading': { enabled: true }
		}
	},
	function(err, results) {
		if (err) throw err;
		console.log(results);
	}
);
```

#### Example 4

This example shows a result object that points to an open shadow DOM element.

##### `violations[0]`

```json
{
	"help": "Elements must have sufficient color contrast",
	"helpUrl": "https://dequeuniversity.com/rules/axe/2.1/color-contrast?application=axeAPI",
	"id": "color-contrast",
	"nodes": [
		{
			"target": [["header > aria-menu", "li.expanded"]]
		}
	]
}
```

As you can see the `target` array contains one item that is an array. This array contains two items, the first is a CSS selector string that finds the custom element `<aria-menu>` in the `<header>`. The second item in this array is the selector within that custom element's shadow DOM to find the `<li>` element with a class of `expanded`.

### API Name: axe.registerPlugin

Register a plugin with the axe plugin system. See [implementing a plugin](plugins.md) for more information on the plugin system

### API Name: axe.cleanup

Call each plugin's cleanup function. See [implementing a plugin](plugins.md).

The signature is:

```js
axe.cleanup(resolve, reject);
```

`resolve` and `reject` are functions that will be invoked on success or failure respectively.

`resolve` takes no arguments and `reject` takes a single argument that must be a string or have a toString() method in its prototype.

### Virtual DOM Utilities

Note: If you’re writing rules or checks, you’ll have both the `node` and `virtualNode` passed in.
But if you need to query the flattened tree, the documented function below should help. See the
[developer guide](./developer-guide.md) for more information.

#### API Name: axe.utils.querySelectorAll

##### Description

A querySelectorAll implementation that works on the virtual DOM and open Shadow DOM by manually walking the flattened tree instead of relying on DOM API methods which don’t step into Shadow DOM.

Note: while there is no `axe.utils.querySelector` method, you can reproduce that behavior by accessing the first item returned in the array.

##### Synopsis

```js
axe.utils.querySelectorAll(virtualNode, 'a[href]');
```

##### Parameters

- `virtualNode` – object, the flattened DOM tree to query against. `axe._tree` is available for this purpose during an audit; see below.
- `selector` – string, the [CSS selector](./developer-guide.md#supported-css-selectors) to use as a filter. For the most part, this should work seamlessly with `document.querySelectorAll`.

##### Returns

An Array of filtered HTML nodes.

### Common Functions

#### axe.commons.dom.getComposedParent

Get an element's parent in the flattened tree

##### Synopsis

```js
axe.commons.dom.getComposedParent(node);
```

##### Parameters

- `element` – HTMLElement. The element for which you want to find a parent

##### Returns

A DOMNode for the parent

#### axe.commons.dom.getRootNode

Return the document or document fragment (open shadow DOM)

##### Synopsis

```js
axe.commons.dom.getRootNode(node);
```

##### Parameters

- `element` – HTMLElement. The element for which you want to find the root node

##### Returns

The top-level document or shadow DOM document fragment

#### axe.commons.dom.findUp

Recursively walk up the DOM, checking for a node which matches a selector. Warning: this should be used sparingly for performance reasons.

##### Synopsis

```js
axe.commons.dom.findUp(node, '.selector');
```

##### Parameters

- `element` – HTMLElement. The starting element
- `selector` – String. The target selector for the HTMLElement

##### Returns

Either the matching HTMLElement or `null` if there was no match.

## Section 3: Example Reference

This package contains examples for [jasmine](examples/jasmine), [mocha](examples/mocha), [phantomjs](examples/phantomjs), [qunit](examples/qunit), and [generating HTML from the violations array](examples/html-handlebars.md). Each of these examples is in the [doc/examples](examples) folder. In each folder, there is a README.md file which contains specific information about each example.

See [axe-webdriverjs](https://github.com/dequelabs/axe-webdriverjs#axe-webdriverjs) for selenium webdriver javascript examples.

## Section 4: Performance

Axe-core performs very well in general and if you are analyzing average complexity pages with the default settings, you should not need to worry about performance at all. There are some scenarios that can cause performance issues. This is the list of known issues and what you can do to mitigate and/or avoid them.

### Very large pages

Certain rules (like the color-contrast rule) look at almost every element on a page and some of these rules also perform somewhat expensive operations on these elements including looking up the hierarchy, looking at overlapping elements, calculating the computed styles etc. It also calculates a unique selector for each element in the results and also de-duplicates elements so that you do not get duplicate items in your results.

If your page is very large (in terms of the number of Elements on the page) i.e. >50K elements on the page, then you will see analysis times that run over 10s on a relatively decent CPU.

#### Use resultTypes

An approach you can take to reducing the time is use the `resultTypes` option. By calling `axe.run` with the following options, axe-core will only return the full details of the `violations` array and will only return one instance of each of the `inapplicable`, `incomplete` and `pass` arrays for each rule that has at least one of those entries. This will reduce the amount of computation that axe-core does for the unique selectors.

```js
axe.run(
	{
		resultTypes: ['violations']
	},
	(err, results) => {
		// ...
	}
);
```

### Other strategies

#### Targeted color-contrast analysis

If you are analyzing multiple pages on a single Web site or application, chances are these pages all contain the same styles. It is therefore not adding any additional information to your analysis to analyze every page for color-contrast. Choose a small number of pages that represent the totality of you styles and analyze these with color-contrast and analyze all others without it.
