
const {gitP} = require('./lib/runners/promise-wrapped');
const {esModuleFactory, gitInstanceFactory, gitExportFactory} = require('./git-factory');

module.exports = esModuleFactory(
   gitExportFactory(gitInstanceFactory, {gitP})
);
