var hash = {
  left: 'right',
  right: 'left',
  bottom: 'top',
  top: 'bottom'
};
export default function getOppositePlacement(placement) {
  return placement.replace(/left|right|bottom|top/g, function (matched) {
    return hash[matched];
  });
}