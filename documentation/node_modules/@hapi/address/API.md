## Methods

### `domain.analyze(domain, [options])`

Analyzes a string to verify it is a valid domain name where:
- `domain` - the domain name string being verified.
- `options` - optional settings:
    - `allowUnicode` - if `false`, Unicode characters are not allowd in domain names. Defaults to `true`.
    - `minDomainSegments` - the minimum number of domain segments (e.g. `x.y.z` has 3 segments) required. Defaults to `2`.
    - `tlds` - options to validate the top-level-domain segment (e.g. `com` in `example.com`). Can be set to one of:
        - `false` - disable TLD validation.
        - `true` - validate the TLD using the official list of [registered names](http://data.iana.org/TLD/tlds-alpha-by-domain.txt). This is the default setting.
        - an object with one (and only one) of:
            - `deny` - a `Set` with strings matching forbidden TLD values (all non-matching values are allowed).
            - `allow` - a `Set` with strings matching the only allowed TLD values. Can also be set to `true` which defaults to the official list of [registered names](http://data.iana.org/TLD/tlds-alpha-by-domain.txt).

If the `domain` is valid, no return value. If the `domain` is invalid, an object is returned with:
- `error` - a string containing the reason the domain is invalid.

### `domain.isValid(domain, [options])`

Validates a string to verify it is a valid domain name where:
- `domain` - the domain name string being verified.
- `options` - same options as [`domain.analyze()`](#domainanalyzedomain-options).

### `email.analyze(email, [options])`

Analyzes a string to verify it is a valid email address where:
- `email` - the email address string being verified.
- `options` - optional settings:
    - `allowUnicode` - if `false`, Unicode characters are not allowd in the email address local and domain parts. Defaults to `true`.
    - `ignoreLength` - if `true`, the standards email maximum length limit is ignored. Defaults to `true`.
    - `minDomainSegments` - the minimum number of domain segments (e.g. `x.y.z` has 3 segments) required in the domain part. Defaults to `2`.
    - `tlds` - options to validate the top-level-domain segment (e.g. `com` in `example.com`) of the domain part. Can be set to one of:
        - `false` - disable TLD validation.
        - `true` - validate the TLD using the official list of [registered names](http://data.iana.org/TLD/tlds-alpha-by-domain.txt). This is the default setting.
        - an object with one (and only one) of:
            - `deny` - a `Set` with strings matching forbidden TLD values (all non-matching values are allowed).
            - `allow` - a `Set` with strings matching the only allowed TLD values. Can also be set to `true` which defaults to the official list of [registered names](http://data.iana.org/TLD/tlds-alpha-by-domain.txt).

If the `email` is valid, no return value. If the `email` is invalid, an object is returned with:
- `error` - a string containing the reason the email is invalid.


### `email.isValid(email, [options])`

Validates a string to verify it is a valid email address where:
- `email` - the email address string being verified.
- `options` - same options as [`email.analyze()`](#emailanalyzeemail-options).
