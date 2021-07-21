## [2.4.1](https://github.com/theKashey/react-focus-lock/compare/v2.4.0...v2.4.1) (2020-07-18)


### Bug Fixes

* FocusLock compoenents does not have name. Used named components inside forwardRefs ([a2d781d](https://github.com/theKashey/react-focus-lock/commit/a2d781d310185ab67a19a9d56752209de15aacb2))



# [2.4.0](https://github.com/theKashey/react-focus-lock/compare/v2.3.1...v2.4.0) (2020-06-18)


### Bug Fixes

* avoid crash on IE ([1cbc9e5](https://github.com/theKashey/react-focus-lock/commit/1cbc9e53a14eb196ef74397d03cfaa1e91eaf909))
* tabIndex=-1 elements should be autofocusable if pointed, fixes [#108](https://github.com/theKashey/react-focus-lock/issues/108) ([258e6aa](https://github.com/theKashey/react-focus-lock/commit/258e6aa4e1b09c12e8ff1e59bb00247ea3bf06bb))
* update interfaces ([7f977fb](https://github.com/theKashey/react-focus-lock/commit/7f977fb409fc84f028cd39f2d95aa761e572bdd3))



## [2.3.1](https://github.com/theKashey/react-focus-lock/compare/v2.3.0...v2.3.1) (2020-04-17)



# [2.3.0](https://github.com/theKashey/react-focus-lock/compare/v2.2.1...v2.3.0) (2020-04-17)


### Bug Fixes

* correct behavior for radio buttons at the edge of lock, fixes [#103](https://github.com/theKashey/react-focus-lock/issues/103) ([9dac851](https://github.com/theKashey/react-focus-lock/commit/9dac85167508ed3e761545ffcc877ef891013d2c))


### Features

* add crossFrame property to control iframe behaviour, fixes [#104](https://github.com/theKashey/react-focus-lock/issues/104) ([486a7e0](https://github.com/theKashey/react-focus-lock/commit/486a7e08428487286d09ef7bfeaa701e8376318d))



## [2.2.1](https://github.com/theKashey/react-focus-lock/compare/v2.2.0...v2.2.1) (2019-10-17)



# [2.2.0](https://github.com/theKashey/react-focus-lock/compare/v2.1.1...v2.2.0) (2019-10-13)


### Features

* use forwardRef, and allow custom as prop ([af0e560](https://github.com/theKashey/react-focus-lock/commit/af0e560966ce3dd936d6fb7f3665ecab972bdd20))



## [2.1.1](https://github.com/theKashey/react-focus-lock/compare/v2.1.0...v2.1.1) (2019-10-05)



# [2.1.0](https://github.com/theKashey/react-focus-lock/compare/v2.0.5...v2.1.0) (2019-09-13)



## [2.0.5](https://github.com/theKashey/react-focus-lock/compare/v2.0.4...v2.0.5) (2019-08-01)



## [2.0.4](https://github.com/theKashey/react-focus-lock/compare/v2.0.3...v2.0.4) (2019-07-16)



## [2.0.3](https://github.com/theKashey/react-focus-lock/compare/v2.0.2...v2.0.3) (2019-07-02)


### Bug Fixes

* onActivation hooks not called in v2 ([ee1cb14](https://github.com/theKashey/react-focus-lock/commit/ee1cb14b8cd3c28f5ce8e093f1b7aa95779f3563))



## [2.0.2](https://github.com/theKashey/react-focus-lock/compare/v2.0.1...v2.0.2) (2019-06-29)



## [2.0.1](https://github.com/theKashey/react-focus-lock/compare/v1.19.1...v2.0.1) (2019-06-28)


### Bug Fixes

* nested return focus, fixes [#68](https://github.com/theKashey/react-focus-lock/issues/68) ([df4b313](https://github.com/theKashey/react-focus-lock/commit/df4b31389494a3dc7a3ebe5ce928721b1c289490))
* useLayoutEffect for focus actions ([254e2ae](https://github.com/theKashey/react-focus-lock/commit/254e2aee9433da048704dda159582fcb90b7f4c1))


### Features

* sidecar code splitting pattern ([187c3c8](https://github.com/theKashey/react-focus-lock/commit/187c3c8adc3d5613a7a3092398e024b78e545d02))
* sidecar FocusLock ([5493986](https://github.com/theKashey/react-focus-lock/commit/5493986ccb49b3f3a189a8859c478fbb7089d520))



## [1.19.1](https://github.com/theKashey/react-focus-lock/compare/v1.19.0...v1.19.1) (2019-04-24)



# [1.19.0](https://github.com/theKashey/react-focus-lock/compare/v1.18.3...v1.19.0) (2019-04-22)


### Bug Fixes

* infinite loop on ref set ([29e9691](https://github.com/theKashey/react-focus-lock/commit/29e9691fb516a92e99322a9832ceb120bb2e475e))


### Features

* no tail guard ([c0c5fde](https://github.com/theKashey/react-focus-lock/commit/c0c5fde64d6d07414ab5a57c807dc8ac6bdb2ac3))



## [1.18.3](https://github.com/theKashey/react-focus-lock/compare/v1.18.2...v1.18.3) (2019-03-11)


### Bug Fixes

* simplify proptype for shards, fixes [#59](https://github.com/theKashey/react-focus-lock/issues/59) ([55b7129](https://github.com/theKashey/react-focus-lock/commit/55b7129eb117aaf66c0c835d89deb74c27d59446))



## [1.18.2](https://github.com/theKashey/react-focus-lock/compare/v1.18.1...v1.18.2) (2019-03-11)


### Bug Fixes

* use only auto guards ([12dab4a](https://github.com/theKashey/react-focus-lock/commit/12dab4a636b96a12fc19f4ad4574d4498c25407a))



## [1.18.1](https://github.com/theKashey/react-focus-lock/compare/v1.18.0...v1.18.1) (2019-03-11)


### Bug Fixes

* support old refs ([8b87c2f](https://github.com/theKashey/react-focus-lock/commit/8b87c2f938e5dba4b303625068b9eaafe858d51b))



# [1.18.0](https://github.com/theKashey/react-focus-lock/compare/v1.17.7...v1.18.0) (2019-03-10)


### Features

* introduce shards ([7bc46f0](https://github.com/theKashey/react-focus-lock/commit/7bc46f0f81255455238999f56bf001c5c83797ea))



## [1.17.7](https://github.com/theKashey/react-focus-lock/compare/v1.17.6...v1.17.7) (2019-01-22)


### Bug Fixes

* nested portals ([9878ba7](https://github.com/theKashey/react-focus-lock/commit/9878ba72550272c7638781db7b923bf4c138bf4e))



## [1.17.6](https://github.com/theKashey/react-focus-lock/compare/v1.17.5...v1.17.6) (2018-11-12)



## [1.17.5](https://github.com/theKashey/react-focus-lock/compare/v1.17.4...v1.17.5) (2018-11-12)


### Bug Fixes

* initially disabled buttons with tabindex set, [#50](https://github.com/theKashey/react-focus-lock/issues/50) ([12e33e5](https://github.com/theKashey/react-focus-lock/commit/12e33e5e3d721d48045d7f8ba40d68cdd04db866))



## [1.17.4](https://github.com/theKashey/react-focus-lock/compare/v1.17.3...v1.17.4) (2018-11-07)



## [1.17.3](https://github.com/theKashey/react-focus-lock/compare/v1.17.2...v1.17.3) (2018-10-26)



## [1.17.2](https://github.com/theKashey/react-focus-lock/compare/v1.17.1...v1.17.2) (2018-10-26)



## [1.17.1](https://github.com/theKashey/react-focus-lock/compare/1.17.0...v1.17.1) (2018-10-26)



# [1.17.0](https://github.com/theKashey/react-focus-lock/compare/v1.16.2...v1.17.0) (2018-10-26)



## [1.16.2](https://github.com/theKashey/react-focus-lock/compare/v1.16.1...v1.16.2) (2018-10-26)



## [1.16.1](https://github.com/theKashey/react-focus-lock/compare/v1.16.0...v1.16.1) (2018-10-24)



# [1.16.0](https://github.com/theKashey/react-focus-lock/compare/1.16.0...v1.16.0) (2018-10-22)



# [1.15.0](https://github.com/theKashey/react-focus-lock/compare/1.15.0...v1.15.0) (2018-10-18)



## [1.14.1](https://github.com/theKashey/react-focus-lock/compare/v1.14.0...v1.14.1) (2018-10-02)



# [1.14.0](https://github.com/theKashey/react-focus-lock/compare/v1.13.2...v1.14.0) (2018-09-28)


### Features

* add 'as' and 'lockProps', [#44](https://github.com/theKashey/react-focus-lock/issues/44) ([5274e24](https://github.com/theKashey/react-focus-lock/commit/5274e2433a471c70640675a72a8285d563aaba88))



## [1.13.2](https://github.com/theKashey/react-focus-lock/compare/v1.13.1...v1.13.2) (2018-09-06)



## [1.13.1](https://github.com/theKashey/react-focus-lock/compare/v1.13.0...v1.13.1) (2018-09-04)



# [1.13.0](https://github.com/theKashey/react-focus-lock/compare/1.13.0...v1.13.0) (2018-09-03)



## [1.12.1](https://github.com/theKashey/react-focus-lock/compare/v1.12.0...v1.12.1) (2018-08-31)



# [1.12.0](https://github.com/theKashey/react-focus-lock/compare/1.12.0...v1.12.0) (2018-08-28)



## [1.11.3](https://github.com/theKashey/react-focus-lock/compare/1.11.3...v1.11.3) (2018-08-17)



## [1.11.2](https://github.com/theKashey/react-focus-lock/compare/v1.11.1...v1.11.2) (2018-07-15)


### Bug Fixes

* Safary and Negative TabIndex, [#33](https://github.com/theKashey/react-focus-lock/issues/33) ([f4a6a6d](https://github.com/theKashey/react-focus-lock/commit/f4a6a6d2aaf3b52deaa376f497b6a329f9b2a7e3))



## [1.11.1](https://github.com/theKashey/react-focus-lock/compare/v1.11.0...v1.11.1) (2018-05-17)



# [1.11.0](https://github.com/theKashey/react-focus-lock/compare/v1.10.0...v1.11.0) (2018-05-08)



# [1.10.0](https://github.com/theKashey/react-focus-lock/compare/1.10.0...v1.10.0) (2018-04-23)



## [1.9.1](https://github.com/theKashey/react-focus-lock/compare/v1.9.0...v1.9.1) (2018-04-18)



# [1.9.0](https://github.com/theKashey/react-focus-lock/compare/v1.8.1...v1.9.0) (2018-04-18)



## [1.8.1](https://github.com/theKashey/react-focus-lock/compare/1.8.0...v1.8.1) (2018-03-31)



# [1.8.0](https://github.com/theKashey/react-focus-lock/compare/v1.8.0...1.8.0) (2018-03-15)



# [1.8.0](https://github.com/theKashey/react-focus-lock/compare/v1.7.0...v1.8.0) (2018-03-15)



# [1.7.0](https://github.com/theKashey/react-focus-lock/compare/1.7.0...v1.7.0) (2018-02-26)



## [1.6.6](https://github.com/theKashey/react-focus-lock/compare/v1.6.5...v1.6.6) (2018-02-22)



## [1.6.5](https://github.com/theKashey/react-focus-lock/compare/1.6.5...v1.6.5) (2018-02-16)



## [1.6.4](https://github.com/theKashey/react-focus-lock/compare/1.6.4...v1.6.4) (2018-01-13)



## [1.6.1](https://github.com/theKashey/react-focus-lock/compare/v1.6.0...v1.6.1) (2017-12-28)



# [1.6.0](https://github.com/theKashey/react-focus-lock/compare/v1.5.5...v1.6.0) (2017-11-30)



## [1.5.5](https://github.com/theKashey/react-focus-lock/compare/v1.5.4...v1.5.5) (2017-11-25)



## [1.5.4](https://github.com/theKashey/react-focus-lock/compare/v1.5.3...v1.5.4) (2017-11-25)



## [1.5.3](https://github.com/theKashey/react-focus-lock/compare/v1.5.2...v1.5.3) (2017-11-23)



## [1.5.2](https://github.com/theKashey/react-focus-lock/compare/v1.5.1...v1.5.2) (2017-11-23)



## 1.5.1 (2017-11-23)



