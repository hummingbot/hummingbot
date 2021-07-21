module.exports = shallow

var assign = require('../constant/assign')

function shallow(object) {
  return assign({}, object)
}
