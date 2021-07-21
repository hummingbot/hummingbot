# contentful-sdk-core

[![Build Status](https://travis-ci.org/contentful/contentful-sdk-core.svg?branch=master)](https://travis-ci.org/contentful/contentful-sdk-core)
[![codecov](https://codecov.io/gh/contentful/contentful-sdk-core/branch/master/graph/badge.svg)](https://codecov.io/gh/contentful/contentful-sdk-core)
![David](https://img.shields.io/david/contentful/contentful-sdk-core.svg)
![David](https://img.shields.io/david/dev/contentful/contentful-sdk-core.svg)

![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)
[![NPM Version](https://img.shields.io/npm/v/contentful-sdk-core.svg)](https://www.npmjs.com/package/contentful-sdk-core)
[![npm downloads](https://img.shields.io/npm/dm/contentful-management.svg)](http://npm-stat.com/charts.html?package=contentful-management)
[![js-standard-style](https://img.shields.io/badge/code%20style-standard-brightgreen.svg?style=flat)](https://github.com/feross/standard)
[![semantic-release](https://img.shields.io/badge/%F0%9F%93%A6%F0%9F%9A%80-semantic--release-e10079.svg)](https://github.com/semantic-release/semantic-release)
[![Commitizen friendly](https://img.shields.io/badge/commitizen-friendly-brightgreen.svg)](http://commitizen.github.io/cz-cli/)

> This package contains some core modules and utilities used by both the [contentful.js](https://github.com/contentful/contentful.js) and [contentful-management.js](https://github.com/contentful/contentful-management.js) SDKs.


## About

[Contentful](https://www.contentful.com) provides a content infrastructure for digital teams to power content in websites, apps, and devices. Unlike a CMS, Contentful was built to integrate with the modern software stack. It offers a central hub for structured content, powerful management and delivery APIs, and a customizable web app that enable developers and content creators to ship digital products faster.

## Pre-requisites

* Make sure you use at least Node 4.7

## Installation

```
npm install --saveDev contentful-sdk-core
```

## Use case

This package contains some core modules and utilities used by both the [contentful.js](https://github.com/contentful/contentful.js) and [contentful-management.js](https://github.com/contentful/contentful-management.js) SDKs.

## Support

We support all current browsers in their last 3 versions including IE 11. The minimal node version is 4.

### ES2015 modules version

For bundlers like webpack2 and rollup we support the `module` &
`jsnext:main` entry in the package.json

## Development

### Create the default and the es-modules build:
```
npm run build
```

### Run Tests:

Run only the unit tests:
```
npm run test:unit
```

Run unit tests including coverage report:
```
npm run test:cover
```

Run unit tests with coverage report and display the result in your browser:
```
npm run browser-coverage
```

Emulate a CI test run:
```
npm run test:ci-emulate
```

Enable debug mode for tests:
```
npm run test:debug
```
