module.exports = function (num, base) {
  return parseInt(num.toString(), base || 8)
}
