module.exports = safe

function safe(context, input, config) {
  var value = (config.before || '') + (input || '') + (config.after || '')
  var positions = []
  var result = []
  var infos = {}
  var index = -1
  var before
  var after
  var position
  var pattern
  var expression
  var match
  var start
  var end

  while (++index < context.unsafePatterns.length) {
    pattern = context.unsafePatterns[index]

    if (
      !inScope(context.stack, pattern.inConstruct, true) ||
      inScope(context.stack, pattern.notInConstruct)
    ) {
      continue
    }

    expression =
      pattern._compiled || (pattern._compiled = toExpression(pattern))

    while ((match = expression.exec(value))) {
      before = 'before' in pattern || pattern.atBreak
      after = 'after' in pattern
      position = match.index + (before ? match[1].length : 0)

      if (positions.indexOf(position) === -1) {
        positions.push(position)
        infos[position] = {before: before, after: after}
      } else {
        if (infos[position].before && !before) {
          infos[position].before = false
        }

        if (infos[position].after && !after) {
          infos[position].after = false
        }
      }
    }
  }

  positions.sort(numerical)

  start = config.before ? config.before.length : 0
  end = value.length - (config.after ? config.after.length : 0)
  index = -1

  while (++index < positions.length) {
    position = positions[index]

    if (
      // Character before or after matched:
      position < start ||
      position >= end
    ) {
      continue
    }

    // If this character is supposed to be escaped because it has a condition on
    // the next character, and the next character is definitly being escaped,
    // then skip this escape.
    if (
      position + 1 < end &&
      positions[index + 1] === position + 1 &&
      infos[position].after &&
      !infos[position + 1].before &&
      !infos[position + 1].after
    ) {
      continue
    }

    if (start !== position) {
      result.push(value.slice(start, position))
    }

    start = position

    if (
      /[!-/:-@[-`{-~]/.test(value.charAt(position)) &&
      (!config.encode || config.encode.indexOf(value.charAt(position)) === -1)
    ) {
      // Character escape.
      result.push('\\')
    } else {
      // Character reference.
      result.push(
        '&#x' + value.charCodeAt(position).toString(16).toUpperCase() + ';'
      )
      start++
    }
  }

  result.push(value.slice(start, end))

  return result.join('')
}

function inScope(stack, list, none) {
  var index

  if (!list) {
    return none
  }

  if (typeof list === 'string') {
    list = [list]
  }

  index = -1

  while (++index < list.length) {
    if (stack.indexOf(list[index]) !== -1) {
      return true
    }
  }

  return false
}

function toExpression(pattern) {
  var before = pattern.before ? '(?:' + pattern.before + ')' : ''
  var after = pattern.after ? '(?:' + pattern.after + ')' : ''

  if (pattern.atBreak) {
    before = '[\\r\\n][\\t ]*' + before
  }

  return new RegExp(
    (before ? '(' + before + ')' : '') +
      (/[|\\{}()[\]^$+*?.-]/.test(pattern.character) ? '\\' : '') +
      pattern.character +
      (after || ''),
    'g'
  )
}

function numerical(a, b) {
  return a - b
}
