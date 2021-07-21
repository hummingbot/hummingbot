# Benchmarks

## Running the benchmarks

From the parent directory, run

```bash
npm run-script benchmark
```

The above script supports the following arguments:

* `--benchmarks=...`: A semicolon-separated list of benchmark names. These names
    will be mapped to file names in this directory by appending `.js`.

## Adding benchmarks

The steps below should be followed when adding new benchmarks.

0. Decide on a name for the benchmark. This name will be used in several places.
   This example will use the name `new_benchmark`.

0. Create files `new_benchmark.cc` and `new_benchmark.js` in this directory.

0. Copy an existing benchmark in `binding.gyp` and change the target name prefix
    and the source file name to `new_benchmark`. This should result in two new
    targets which look like this:

    ```gyp
      {
        'target_name': 'new_benchmark',
        'sources': [ 'new_benchmark.cc' ],
        'includes': [ '../except.gypi' ],
      },
      {
        'target_name': 'new_benchmark_noexcept',
        'sources': [ 'new_benchmark.cc' ],
        'includes': [ '../noexcept.gypi' ],
      },
    ```

    There should always be a pair of targets: one bearing the name of the
    benchmark and configured with C++ exceptions enabled, and one bearing the
    same name followed by the suffix `_noexcept` and configured with C++
    exceptions disabled. This will ensure that the benchmark can be written to
    cover both the case where C++ exceptions are enabled and the case where they
    are disabled.
