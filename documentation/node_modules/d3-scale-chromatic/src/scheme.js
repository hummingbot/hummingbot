export default function(ranges) {
  ranges = ranges.map(function(colors) {
    return colors.match(/.{6}/g).map(function(x) {
      return "#" + x;
    });
  });
  var n0 = ranges[0].length;
  return function(n) {
    return ranges[n - n0];
  };
}
