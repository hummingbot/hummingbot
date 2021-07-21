/*
 * Color scheme
 */

module.exports = {
  'GREY': '0;30',
  'RED': '0;31',
  'GREEN': '0;32',
  'YELLOW': '0;33',
  'BLUE': '0;34',
  'MAGENTA': '0;35',
  'CYAN': '0;36',
  'BOLD': '0;1',
  'UNDERLINE': '0;4',
  'BOLDWHITE': '1;37',
  'NIL': '0;0',

  'line_number': 'GREY',

  'keyword': 'BOLD',            // like 'class', 'module', etc
  'built_in': 'keyword',        // like var, etc
  'tag': 'keyword',             // css tag
  'class': 'keyword',           // css class

  'title': 'UNDERLINE',         // tags, function names

  'comment': 'CYAN',
  'doctype': 'comment',
  'pi': 'comment',              // xml declaration
  'preprocessor': 'comment',    // C/C++ preprocessor directives
  'horizontal_rule': 'comment', // markdown HR ---
  'javadoc': 'comment',         // double-star comments
  'blockquote': 'comment',      // markdown blockquote
  'javadoctag': 'BLUE',         // tags like @param

  'string': 'GREEN',
  'value': 'string',            // html/json values
  'json:value': 'NIL',
  'code': 'string',             // markdown code
  'link_reference': 'string',   // markdown link reference

  'number': 'YELLOW',
  'symbol': 'number',           // ruby ':symbols
  'hexcolor': 'number',         // css hex holor
  'link_url': 'number',         // markdown link url

  'function': 'BOLD',           // css function, like rgba()
  'strong': 'function',         // markdown strong
  'link_label': 'strong',       // markdown links

  'header': 'BOLDWHITE',        // markdown header

  'attribute': 'BLUE',          // html/json attributes
  'literal': 'attribute',       // true, false, etc
  'variable': 'attribute',      // xml variable

  'pseudo': 'GREY',             // css pseudoclass :before
  'attr_selector': 'pseudo',    // css attr [type='number']

  'params': 'NIL',              // function parameters ()
  'regexp': 'MAGENTA',

  'subst': 'NIL',               // ruby interpolation

  'addition': 'GREEN',          // diff +
  'deletion': 'RED',            // diff -
  'chunk': 'BLUE',              // diff @@ -1,119 +1,768 @@

  'debug:tag': 'GREY'
};
