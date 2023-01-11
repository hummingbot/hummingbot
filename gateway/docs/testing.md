# Unit tests for gateway

Gateway is written in [TypeScript](https://www.typescriptlang.org/) for a NodeJS environment. 
The majority of block chain SDKs we use have type annotations for TypeScript so they integrate 
smoothly into this project.

Our main tool for unit testing is [jest](https://jestjs.io). Our configurations
for jest are located [here](../jest.config.js).

We use [prettier](https://prettier.io/) for formatting. Configuration file
[here](../.prettierrc).

We use [ESLint](https://eslint.org/) for linting. Configuration file 
[here](../.eslintrc.js).

## Running the unit tests

We primarily use `yarn` for development, but `npm` should work as well.

First install dependencies:

```
yarn install --frozen-lockfile
```

Then build the gateway package:

```
yarn build
```

Then you can run the unit tests:

```
yarn test:unit
```

You do not actually need to build before running, but if you have any compiler
errors, the unit tests will crash, so in practice if you make changes, it is
best to run build first.

## Run individual unit test file

`yarn test:unit` runs all of the tests. Alternatively, you can run the unit tests
from a single file with `yarn jest path/to/test`. For example:

```
yarn jest test/chains/ethereum/ethereum.controller.test.ts
```

## Test coverage

Our github repository has requirements for test coverage. These requirements may 
change, so specifically look at our [workflow file](../../.github/workflows/workflow.yml) 
and find the section for gateway unit tests. If you are interested in merging a PR,
you will need to make sure unit test coverage meets the requirements.

To see the current coverage, run the following:

```
yarn test:cov
```

This will produce a table with absolute numbers, percentages and line numbers that
are not being tested. These are helpful for knowing where to increment tests.

### Coverage areas

When you run test coverage, you will see a table of information with the following
concepts:

function coverage: the percentage of declared functions that are tested (this 
ignores details of how much internal function code is run).

branch coverage: percentage of decision conditions like loop, if/else, while that
are called.

statement coverage: the percentage of executable statements this includes function calls,
assignment, branches that are called

line coverage: the percentage of lines of declared code that are called.

uncovered lines: the line numbers of code that is not called


## Jest: describe, it, before, after

The main tools from Jest we use are `describe` and `it`.

`describe` is a collection of one or more related unit tests. For example,
the expected result of adding one to different numbers. You should include a 
description.


`it` is an individual unit test with a description.

```TypeScript
describe('addition', () => {
  it('1+1=2', () => {
    expect(1+1).toEqual(2);
  });
  
  it('1+2=3', () => {
    expect(1+2).toEqual(3);
  });
});

```

Some useful tools to reduce repetition are:

- `beforeAll`: run code before any test in the file is run.
- `afterAll`: run code after all the tests in a file are run.
- `beforeEach`: run code before every test in scope.
- `afterEach`: run code after every test in scope.

## Testing for Failure

Not only do we want to test that things work properly, we also want to
test when we expect things to fail. Consider adding expected error throwing
to your unit test code.

## Network Calls and Mock Values

Our philosophy for unit testing is to avoid any outside network calls. Unit tests
requiring calls to APIs may be fragile and slow. Instead we try to mock the values that 
would be returned from an API. This will allow us to test the logic of the code, without
worrying about the value returned from a network call.

### patch and unpatch

We designed our own patching system in [patch.ts](../test/services/patch.ts) since we
did not find a good tool for TypeScript or JavaScript. The main idea is to mock values
and function return values on objects, namespaces and modules, and remove these changes
after a test.

Here is an example:

```TypeScript
    patch(eth, 'getWallet', () => {
      return {
        address: '0...',
      };
    });
```

Normally `eth.getWallet` would take a private key and return a `Wallet` object
with some information from the Ethereum block chain. This would require a network
call. Instead, we only need the address.

Generally you will find in our unit tests the following code:

```TypeScript
  afterEach(() => {
    unpatch();
  });
```

This means after each test `it`, remove any applied patch. This way there will not 
be unexpected patches applied in other tests.

Please keep in mind that [patch.ts](../test/services/patch.ts) was only designed
for our current use cases, and may not support patching all TypeScript data types.

## Testing Non-Network I/0, Files, etc.

Other than network calls, we generally allow system I/O for testing, for example:
[local-storage.test.ts](../test/services/local-storage.test.s) tests how we use leveldb,
and [config-manager-v2.test.ts](../test/services/config-manager-v2.test.s) creates 
temporary files. The general rule of thumb is to store files with `mkdtemp` and 
remove them when they are no longer needed.

# Manual Testing

We also do a lot of manual testing of gateway to ensure API endpoints behave 
correctly. It is best to start doing these tests on test networks to ensure
you do not lose valuable cryptocurrencies.

The main source of testing is a [curl file](../manual-tests/curl.sh). This outlines
a number of curl commands that are paired with JSON request bodies stored in files.
By storing them in files, they are easier to edit.

Currently the following env varables are expected, depending on the route:

```bash
AVALANCHE_ADDRESSS='0000...'
ETH_ADDRESS='000...'
GATEWAY_CERT='/absolute/path/to/certs/client_cert.pem'
GATEWAY_KEY='/absolut/path/to/certs/client_key.pem'
```

You may also replace these values with hard coded ones if you like. Please be
careful when storing private keys in the environment or in a file. Never commit
these values to a git repository.

If you add new routes to gateway, add a corresponding curl call in [curl.sh](../manual-tests/curl.sh).
