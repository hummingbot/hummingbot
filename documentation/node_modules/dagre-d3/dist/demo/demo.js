var bodyElem = d3.select('body'),
    jsElem = d3.select('#js'),
    jsPanel = bodyElem.append('div').attr('id', 'jsPanel');
    cssElem = d3.select('#css'),
    cssPanel = bodyElem.append('div').attr('id', 'cssPanel');

function setupPanel(panel, elem, title) {
  panel.append('h2').text(title);
  return panel.append('pre').append('code').text(elem.html().trim());
}

var jsCode = setupPanel(jsPanel, jsElem, 'JavaScript');
var cssCode = setupPanel(cssPanel, cssElem, 'CSS');

var hljsRoot = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/8.1';

bodyElem.append('link')
  .attr('rel', 'stylesheet')
  .attr('href', hljsRoot + '/styles/xcode.min.css');
bodyElem.append('script')
  .attr('src', hljsRoot + '/highlight.min.js')
  .on('load', function() {
    hljs.highlightBlock(jsCode.node());
    hljs.highlightBlock(cssCode.node());
  });
