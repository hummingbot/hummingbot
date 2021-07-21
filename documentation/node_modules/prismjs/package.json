{
  "name": "prismjs",
  "version": "1.22.0",
  "description": "Lightweight, robust, elegant syntax highlighting. A spin-off project from Dabblet.",
  "main": "prism.js",
  "style": "themes/prism.css",
  "scripts": {
    "build": "gulp",
    "test:aliases": "mocha tests/aliases-test.js",
    "test:core": "mocha tests/core/**/*.js",
    "test:dependencies": "mocha tests/dependencies-test.js",
    "test:examples": "mocha tests/examples-test.js",
    "test:identifiers": "mocha tests/identifier-test.js",
    "test:languages": "mocha tests/run.js",
    "test:patterns": "mocha tests/pattern-tests.js",
    "test:plugins": "mocha tests/plugins/**/*.js",
    "test:runner": "mocha tests/testrunner-tests.js",
    "test": "npm run test:runner && npm run test:core && npm run test:dependencies && npm run test:languages && npm run test:plugins && npm run test:aliases && npm run test:patterns && npm run test:examples && npm run test:identifiers"
  },
  "repository": {
    "type": "git",
    "url": "https://github.com/PrismJS/prism.git"
  },
  "keywords": [
    "prism",
    "highlight"
  ],
  "author": "Lea Verou",
  "license": "MIT",
  "readmeFilename": "README.md",
  "optionalDependencies": {
    "clipboard": "^2.0.0"
  },
  "devDependencies": {
    "chai": "^4.2.0",
    "del": "^4.1.1",
    "docdash": "^1.2.0",
    "gulp": "^4.0.2",
    "gulp-concat": "^2.3.4",
    "gulp-header": "^2.0.7",
    "gulp-jsdoc3": "^3.0.0",
    "gulp-rename": "^1.2.0",
    "gulp-replace": "^1.0.0",
    "gulp-uglify": "^3.0.1",
    "htmlparser2": "^4.0.0",
    "jsdom": "^13.0.0",
    "mocha": "^6.2.0",
    "pump": "^3.0.0",
    "regexpp": "^2.0.1",
    "simple-git": "^1.107.0",
    "yargs": "^13.2.2"
  },
  "jspm": {
    "main": "prism",
    "registry": "jspm",
    "jspmPackage": true,
    "format": "global",
    "files": [
      "components/**/*.js",
      "plugins/**/*",
      "themes/*.css",
      "prism.js"
    ]
  }
}
