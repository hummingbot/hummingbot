const path = require('path');
const Benchmark = require('benchmark');
const addonName = path.basename(__filename, '.js');

[ addonName, addonName + '_noexcept' ]
  .forEach((addonName) => {
    const rootAddon = require('bindings')({
      bindings: addonName,
      module_root: __dirname
    });
    delete rootAddon.path;
    const getters = new Benchmark.Suite;
    const setters = new Benchmark.Suite;
    const maxNameLength = Object.keys(rootAddon)
      .reduce((soFar, value) => Math.max(soFar, value.length), 0);

    console.log(`\n${addonName}: `);

    Object.keys(rootAddon).forEach((key) => {
      getters.add(`${key} getter`.padStart(maxNameLength + 7), () => {
        const x = rootAddon[key];
      });
      setters.add(`${key} setter`.padStart(maxNameLength + 7), () => {
        rootAddon[key] = 5;
      })
    });

    getters
      .on('cycle', (event) => console.log(String(event.target)))
      .run();

    console.log('');

    setters
      .on('cycle', (event) => console.log(String(event.target)))
      .run();
  });
