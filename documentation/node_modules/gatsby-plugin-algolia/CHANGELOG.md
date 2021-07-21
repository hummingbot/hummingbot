# Change Log

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

<a name="0.14.0"></a>
# [0.14.0](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.13.0...v0.14.0) (2020-10-23)


### Features

* **replica:** safely update replicas ([#81](https://github.com/algolia/gatsby-plugin-algolia/issues/81)) ([1bdadb2](https://github.com/algolia/gatsby-plugin-algolia/commit/1bdadb2))



<a name="0.13.0"></a>
# [0.13.0](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.12.1...v0.13.0) (2020-10-13)


### Features

* **concurrentQueries:** add option to disable queries happening at the same time ([#96](https://github.com/algolia/gatsby-plugin-algolia/issues/96)) ([165aed1](https://github.com/algolia/gatsby-plugin-algolia/commit/165aed1))



<a name="0.12.1"></a>
## [0.12.1](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.12.0...v0.12.1) (2020-09-16)


### Bug Fixes

* define variable for fields check ([#94](https://github.com/algolia/gatsby-plugin-algolia/issues/94)) ([150e675](https://github.com/algolia/gatsby-plugin-algolia/commit/150e675))



<a name="0.12.0"></a>
# [0.12.0](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.11.2...v0.12.0) (2020-09-16)


### Bug Fixes

* **partial:** make matchFields required ([dcb93c8](https://github.com/algolia/gatsby-plugin-algolia/commit/dcb93c8)), closes [#93](https://github.com/algolia/gatsby-plugin-algolia/issues/93)


### BREAKING CHANGES

* **partial:** matchFields is now required when using enablePartialUpdates to prevent issues



<a name="0.11.2"></a>
## [0.11.2](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.11.1...v0.11.2) (2020-07-28)


### Bug Fixes

* remove deleted records ([#86](https://github.com/algolia/gatsby-plugin-algolia/issues/86)) ([2f6b6e8](https://github.com/algolia/gatsby-plugin-algolia/commit/2f6b6e8)), closes [#82](https://github.com/algolia/gatsby-plugin-algolia/issues/82)



<a name="0.11.1"></a>
## [0.11.1](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.11.0...v0.11.1) (2020-06-01)



<a name="0.11.0"></a>
# [0.11.0](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.10.0...v0.11.0) (2020-05-04)


### Bug Fixes

* **settings:** use main settings if not provided in query ([#65](https://github.com/algolia/gatsby-plugin-algolia/issues/65)) ([8eea55c](https://github.com/algolia/gatsby-plugin-algolia/commit/8eea55c))



<a name="0.10.0"></a>
# [0.10.0](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.9.0...v0.10.0) (2020-05-04)


### Bug Fixes

* create index before browse ([#61](https://github.com/algolia/gatsby-plugin-algolia/issues/61)) ([1bf7164](https://github.com/algolia/gatsby-plugin-algolia/commit/1bf7164))
* **example:** enablePartialUpdates is false ([#62](https://github.com/algolia/gatsby-plugin-algolia/issues/62)) ([155dbf3](https://github.com/algolia/gatsby-plugin-algolia/commit/155dbf3))



<a name="0.9.0"></a>
# [0.9.0](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.8.1...v0.9.0) (2020-04-24)


### Bug Fixes

* **settings:** allow user provided settings to be replicated ([6f65b81](https://github.com/algolia/gatsby-plugin-algolia/commit/6f65b81)), closes [#57](https://github.com/algolia/gatsby-plugin-algolia/issues/57)



<a name="0.8.1"></a>
## [0.8.1](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.8.0...v0.8.1) (2020-04-23)


### Bug Fixes

* allow "id" instead of "objectID" again ([#56](https://github.com/algolia/gatsby-plugin-algolia/issues/56)) ([4de4b1b](https://github.com/algolia/gatsby-plugin-algolia/commit/4de4b1b))



<a name="0.8.0"></a>
# [0.8.0](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.7.0...v0.8.0) (2020-04-20)


### Features

* Partial updates ([#27](https://github.com/algolia/gatsby-plugin-algolia/issues/27)) ([c0b6e47](https://github.com/algolia/gatsby-plugin-algolia/commit/c0b6e47))



<a name="0.7.0"></a>
# [0.7.0](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.6.0...v0.7.0) (2020-04-10)


### Features

* **replica:** prevent temporary indices to have replicas ([#51](https://github.com/algolia/gatsby-plugin-algolia/issues/51)) ([b3e6fad](https://github.com/algolia/gatsby-plugin-algolia/commit/b3e6fad))



<a name="0.6.0"></a>
# [0.6.0](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.5.0...v0.6.0) (2020-04-01)


### Features

* **exists:** prevent empty index from being overridden ([e587abe](https://github.com/algolia/gatsby-plugin-algolia/commit/e587abe))



<a name="0.5.0"></a>
# [0.5.0](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.4.0...v0.5.0) (2019-11-18)


### Bug Fixes

* **settings:** wait for task to finish ([67f4e46](https://github.com/algolia/gatsby-plugin-algolia/commit/67f4e46))


### BREAKING CHANGES

* **settings:** indexing will take a slight bit longer if settings are applied to be more sure we don't set settings on the wrong index.



<a name="0.4.0"></a>
# [0.4.0](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.3.4...v0.4.0) (2019-11-07)


### Features

* **transformer:** Wait for me! 🙋‍♂️ Ability to await the data transformer ([#40](https://github.com/algolia/gatsby-plugin-algolia/issues/40)) ([d47e35f](https://github.com/algolia/gatsby-plugin-algolia/commit/d47e35f)), closes [#25](https://github.com/algolia/gatsby-plugin-algolia/issues/25)



<a name="0.3.4"></a>
## [0.3.4](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.3.3...v0.3.4) (2019-09-11)

### Bug Fixes

* **settings**: await settings to be sent before moving indices ([231221e](https://github.com/algolia/gatsby-plugin-algolia/commit/231221e)), closes [#37](https://github.com/algolia/gatsby-plugin-algolia/issues/37)

<a name="0.3.3"></a>
## [0.3.3](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.3.2...v0.3.3) (2019-08-12)



<a name="0.3.2"></a>
## [0.3.2](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.3.1...v0.3.2) (2019-07-03)


### Bug Fixes

* **pkg:** add index.js to files ([282b151](https://github.com/algolia/gatsby-plugin-algolia/commit/282b151)), closes [#32](https://github.com/algolia/gatsby-plugin-algolia/issues/32)



<a name="0.3.1"></a>
## [0.3.1](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.3.0...v0.3.1) (2019-07-03)


### Bug Fixes

* Don't publish examples to npm ([#31](https://github.com/algolia/gatsby-plugin-algolia/issues/31)) ([b042481](https://github.com/algolia/gatsby-plugin-algolia/commit/b042481))



<a name="0.3.0"></a>
# [0.3.0](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.2.0...v0.3.0) (2018-11-13)


### Features

* **settings:** allow user to set settings for each query individually ([#17](https://github.com/algolia/gatsby-plugin-algolia/issues/17)) ([ea6e8b1](https://github.com/algolia/gatsby-plugin-algolia/commit/ea6e8b1))



<a name="0.2.0"></a>
# [0.2.0](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.1.0...v0.2.0) (2018-10-02)


### Bug Fixes

* don't "atomic" index when there's no info in main index ([#12](https://github.com/algolia/gatsby-plugin-algolia/issues/12)) ([1be256f](https://github.com/algolia/gatsby-plugin-algolia/commit/1be256f))


### Features

* add more detailed logging ([#14](https://github.com/algolia/gatsby-plugin-algolia/issues/14)) ([5e7372a](https://github.com/algolia/gatsby-plugin-algolia/commit/5e7372a))



<a name="0.1.1"></a>
## [0.1.1](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.1.0...v0.1.1) (2018-09-28)


### Features

* Make sure people use the right name for `query` ([2b47488](https://github.com/algolia/gatsby-plugin-algolia/commit/2b47488))

<a name="0.1.0"></a>
## [0.1.0](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.0.4...v0.1.0) (2018-09-05)


### Features

* Atomic indexing ([cc351f0](https://github.com/algolia/gatsby-plugin-algolia/commit/cc351f0))
  * this will add one more index while you're indexing to always have live data on your index


<a name="0.0.4"></a>
## [0.0.4](https://github.com/algolia/gatsby-plugin-algolia/compare/v0.0.3...v0.0.4) (2018-05-30)


### Features

* Allow multiple indices ([fd6d9e5](https://github.com/algolia/gatsby-plugin-algolia/commit/fd6d9e5))
* make indexName in query and transformer optional ([337fdc8](https://github.com/algolia/gatsby-plugin-algolia/commit/337fdc8))



# Change Log

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.
