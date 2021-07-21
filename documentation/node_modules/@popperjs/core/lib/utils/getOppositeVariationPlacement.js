var hash = {
  start: 'end',
  end: 'start'
};
export default function getOppositeVariationPlacement(placement) {
  return placement.replace(/start|end/g, function (matched) {
    return hash[matched];
  });
}