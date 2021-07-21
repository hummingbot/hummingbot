### 0.11.1 - Nov 15 2013
 * Adjust approximate-size-test.js to account for snappy compression

### 0.11.0 - Oct 14 2013
 * Introduce _setupIteratorOptions() method to fix options object prior to _iterator() call; makes working with gt/gte/lt/lte options a little easier (@rvagg)

### 0.10.2 - Sep 6 2013

 * Refactor duplicated versions of isTypedArray into util.js (@rvagg)
 * Refactor duplicated versions of 'NotFound' checks into util.js, fixed too-strict version in get-test.js (@rvagg)

### 0.10.1 - Aug 29 2013

 * Relax check for 'Not Found: ' in error message to be case insensitive in get-test.js (@rvagg)

### 0.10.0 - Aug 19 2013

 * Added test for gt, gte, lt, lte ranges (@dominictarr)
