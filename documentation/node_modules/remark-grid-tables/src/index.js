const trimEnd = require('lodash.trimend')
const visit = require('unist-util-visit')
const stringWidth = require('string-width')
const splitter = new (require('grapheme-splitter'))()

const mainLineRegex = new RegExp(/((\+)|(\|)).+((\|)|(\+))/)
const totalMainLineRegex = new RegExp(/^((\+)|(\|)).+((\|)|(\+))$/)
const headerLineRegex = new RegExp(/^\+=[=+]+=\+$/)
const partLineRegex = new RegExp(/\+-[-+]+-\+/)
const separationLineRegex = new RegExp(/^\+-[-+]+-\+$/)

module.exports = plugin

// A small class helping table generation
class Table {
  constructor (linesInfos) {
    this._parts = []
    this._linesInfos = linesInfos
    this.addPart()
  }

  lastPart () {
    return this._parts[this._parts.length - 1]
  }

  addPart () {
    this._parts.push(new TablePart(this._linesInfos))
  }
}

class TablePart {
  constructor (linesInfos) {
    this._rows = []
    this._linesInfos = linesInfos
    this.addRow()
  }

  addRow () {
    this._rows.push(new TableRow(this._linesInfos))
  }

  removeLastRow () {
    this._rows.pop()
  }

  lastRow () {
    return this._rows[this._rows.length - 1]
  }

  updateWithMainLine (line, isEndLine) {
    // Update last row according to a line.
    const mergeChars = isEndLine ? '+|' : '|'
    const newCells = [this.lastRow()._cells[0]]
    for (let c = 1; c < this.lastRow()._cells.length; c++) {
      const cell = this.lastRow()._cells[c]

      // Only cells with rowspan equals can be merged
      // Test if the char does not compose a character
      // or the char before the cell is a separation character
      if (cell._rowspan === newCells[newCells.length - 1]._rowspan && (
        !isCodePointPosition(line, cell._startPosition - 1) ||
        !mergeChars.includes(substringLine(line, cell._startPosition - 1))
      )) {
        newCells[newCells.length - 1].mergeWith(cell)
      } else {
        newCells.push(cell)
      }
    }
    this.lastRow()._cells = newCells
  }

  updateWithPartLine (line) {
    // Get cells not finished
    const remainingCells = []
    for (let c = 0; c < this.lastRow()._cells.length; c++) {
      const cell = this.lastRow()._cells[c]
      const partLine = substringLine(line, cell._startPosition - 1, cell._endPosition + 1)
      if (!isSeparationLine(partLine)) {
        cell._lines.push(substringLine(line, cell._startPosition, cell._endPosition))
        cell._rowspan += 1
        remainingCells.push(cell)
      }
    }
    // Generate new row
    this.addRow()
    const newCells = []
    for (let c = 0; c < remainingCells.length; c++) {
      const remainingCell = remainingCells[c]
      for (let cc = 0; cc < this.lastRow()._cells.length; cc++) {
        const cell = this.lastRow()._cells[cc]
        if (cell._endPosition < remainingCell._startPosition && !newCells.includes(cell)) {
          newCells.push(cell)
        }
      }
      newCells.push(remainingCell)
      for (let cc = 0; cc < this.lastRow()._cells.length; cc++) {
        const cell = this.lastRow()._cells[cc]
        if (cell._startPosition > remainingCell._endPosition && !newCells.includes(cell)) {
          newCells.push(cell)
        }
      }
    }

    // Remove duplicates
    for (let nc = 0; nc < newCells.length; nc++) {
      let newCell = newCells[nc]
      for (let ncc = 0; ncc < newCells.length; ncc++) {
        if (nc !== ncc) {
          const other = newCells[ncc]
          if (other._startPosition >= newCell._startPosition &&
          other._endPosition <= newCell._endPosition) {
            if (other._lines.length === 0) {
              newCells.splice(ncc, 1)
              ncc -= 1
              if (nc > ncc) {
                nc -= 1
                newCell = newCells[nc]
              }
            }
          }
        }
      }
    }
    this.lastRow()._cells = newCells
  }
}

class TableRow {
  constructor (linesInfos) {
    this._linesInfos = linesInfos
    this._cells = []
    for (let i = 0; i < linesInfos.length - 1; i++) {
      this._cells.push(new TableCell(linesInfos[i] + 1, linesInfos[i + 1]))
    }
  }

  updateContent (line) {
    for (let c = 0; c < this._cells.length; c++) {
      const cell = this._cells[c]
      cell._lines.push(substringLine(line, cell._startPosition, cell._endPosition))
    }
  }
}

class TableCell {
  constructor (startPosition, endPosition) {
    this._startPosition = startPosition
    this._endPosition = endPosition
    this._colspan = 1
    this._rowspan = 1
    this._lines = []
  }

  mergeWith (other) {
    this._endPosition = other._endPosition
    this._colspan += other._colspan
    const newLines = []
    for (let l = 0; l < this._lines.length; l++) {
      newLines.push(`${this._lines[l]}|${other._lines[l]}`)
    }
    this._lines = newLines
  }
}


function merge (beforeTable, gridTable, afterTable) {
  // get the eaten text
  let total = beforeTable.join('\n')
  if (total.length) {
    total += '\n'
  }
  total += gridTable.join('\n')
  if (afterTable.join('\n').length) {
    total += '\n'
  }
  total += afterTable.join('\n')
  return total
}

function isSeparationLine (line) {
  return separationLineRegex.exec(line)
}

function isHeaderLine (line) {
  return headerLineRegex.exec(line)
}

function isPartLine (line) {
  return partLineRegex.exec(line)
}

function findAll (str, characters) {
  let current = 0
  const pos = []
  const content = splitter.splitGraphemes(str)
  for (let i = 0; i < content.length; i++) {
    const char = content[i]
    if (characters.includes(char)) {
      pos.push(current)
    }
    current += stringWidth(char)
  }
  return pos
}

function computePlainLineColumnsStartingPositions (line) {
  return findAll(line, '+|')
}

function mergeColumnsStartingPositions (allPos) {
  // Get all starting positions, allPos is an array of array of positions
  const positions = []

  allPos.forEach((posRow) => posRow.forEach((pos) => {
    if (!positions.includes(pos)) {
      positions.push(pos)
    }
  }))

  return positions.sort((a, b) => a - b)
}

function computeColumnStartingPositions (lines) {
  const linesInfo = []

  lines.forEach((line) => {
    if (isHeaderLine(line) || isPartLine(line)) {
      linesInfo.push(computePlainLineColumnsStartingPositions(line))
    }
  })

  return mergeColumnsStartingPositions(linesInfo)
}

function isCodePointPosition (line, pos) {
  const content = splitter.splitGraphemes(line)
  let offset = 0

  for (let i = 0; i < content.length; i++) {
    // The pos points character position
    if (pos === offset) {
      return true
    }
    // The pos points non-character position
    if (pos < offset) {
      return false
    }
    offset += stringWidth(content[i])
  }

  // Reaching end means character position
  return true
}

function substringLine (line, start, end) {
  end = end || start + 1

  const content = splitter.splitGraphemes(line)
  let offset = 0
  let str = ''

  for (let i = 0; i < content.length; i++) {
    if (offset >= start) {
      str += content[i]
    }

    offset += stringWidth(content[i])

    if (offset >= end) {
      break
    }
  }

  return str
}

function extractTable (value, eat, tokenizer) {
  // Extract lines before the grid table
  const markdownLines = value
    .split('\n')

  let i = 0
  const before = []
  for (; i < markdownLines.length; i++) {
    const line = markdownLines[i]
    if (isSeparationLine(line)) break
    if (stringWidth(line) === 0) break
    before.push(line)
  }

  const possibleGridTable = markdownLines
    .map(line => trimEnd(line))

  // Extract table
  if (!possibleGridTable[i + 1]) return [null, null, null, null]

  const gridTable = []
  const realGridTable = []
  let hasHeader = false
  for (; i < possibleGridTable.length; i++) {
    const line = possibleGridTable[i]
    const realLine = markdownLines[i]
    // line is in table
    if (totalMainLineRegex.exec(line)) {
      const isHeaderLine = headerLineRegex.exec(line)
      if (isHeaderLine && !hasHeader) hasHeader = true
      // A table can't have 2 headers
      else if (isHeaderLine && hasHeader) {
        break
      }
      realGridTable.push(realLine)
      gridTable.push(line)
    } else {
      // this line is not in the grid table.
      break
    }
  }

  // if the last line is not a plain line
  if (!separationLineRegex.exec(gridTable[gridTable.length - 1])) {
    // Remove lines not in the table
    for (let j = gridTable.length - 1; j >= 0; j--) {
      const isSeparation = separationLineRegex.exec(gridTable[j])
      if (isSeparation) break
      gridTable.pop()
      i -= 1
    }
  }

  // Extract lines after table
  const after = []
  for (; i < possibleGridTable.length; i++) {
    const line = possibleGridTable[i]
    if (stringWidth(line) === 0) break
    after.push(markdownLines[i])
  }

  return [before, gridTable, realGridTable, after, hasHeader]
}

function extractTableContent (lines, linesInfos, hasHeader) {
  const table = new Table(linesInfos)

  for (let l = 0; l < lines.length; l++) {
    const line = lines[l]
    // Get if the line separate the head of the table from the body
    const matchHeader = hasHeader & isHeaderLine(line) !== null
    // Get if the line close some cells
    const isEndLine = matchHeader | isPartLine(line) !== null

    if (isEndLine) {
      // It is a header, a plain line or a line with plain line part.
      // First, update the last row
      table.lastPart().updateWithMainLine(line, isEndLine)

      // Create the new row
      if (l !== 0) {
        if (matchHeader) {
          table.addPart()
        } else if (isSeparationLine(line)) {
          table.lastPart().addRow()
        } else {
          table.lastPart().updateWithPartLine(line)
        }
      }
      // update the last row
      table.lastPart().updateWithMainLine(line, isEndLine)
    } else {
      // it's a plain line
      table.lastPart().updateWithMainLine(line, isEndLine)
      table.lastPart().lastRow().updateContent(line)
    }
  }
  // Because the last line is a separation, the last row is always empty
  table.lastPart().removeLastRow()
  return table
}

function generateTable (tableContent, now, tokenizer) {
  // Generate the gridTable node to insert in the AST
  const tableElt = {
    type: 'gridTable',
    children: [],
    data: {
      hName: 'table',
    },
  }

  const hasHeader = tableContent._parts.length > 1

  for (let p = 0; p < tableContent._parts.length; p++) {
    const part = tableContent._parts[p]
    const partElt = {
      type: 'tableHeader',
      children: [],
      data: {
        hName: (hasHeader && p === 0) ? 'thead' : 'tbody',
      },
    }
    for (let r = 0; r < part._rows.length; r++) {
      const row = part._rows[r]
      const rowElt = {
        type: 'tableRow',
        children: [],
        data: {
          hName: 'tr',
        },
      }
      for (let c = 0; c < row._cells.length; c++) {
        const cell = row._cells[c]
        const tokenizedContent = tokenizer.tokenizeBlock(
          cell._lines.map((e) => e.trim()).join('\n'),
          now
        )
        const cellElt = {
          type: 'tableCell',
          children: tokenizedContent,
          data: {
            hName: (hasHeader && p === 0) ? 'th' : 'td',
            hProperties: {
              colspan: cell._colspan,
              rowspan: cell._rowspan,
            },
          },
        }

        const endLine = r + cell._rowspan
        if (cell._rowspan > 1 && endLine - 1 < part._rows.length) {
          for (let rs = 1; rs < cell._rowspan; rs++) {
            for (let cc = 0; cc < part._rows[r + rs]._cells.length; cc++) {
              const other = part._rows[r + rs]._cells[cc]
              if (cell._startPosition === other._startPosition &&
              cell._endPosition === other._endPosition &&
              cell._colspan === other._colspan &&
              cell._rowspan === other._rowspan &&
              cell._lines === other._lines) {
                part._rows[r + rs]._cells.splice(cc, 1)
              }
            }
          }
        }

        rowElt.children.push(cellElt)
      }
      partElt.children.push(rowElt)
    }
    tableElt.children.push(partElt)
  }

  return tableElt
}

function gridTableTokenizer (eat, value, silent) {
  let index = 0
  const length = value.length
  let character
  while (index < length) {
    character = value.charAt(index)

    if (character !== ' ' && character !== '\t') {
      break
    }

    index++
  }

  if (value.charAt(index) !== '+') {
    return
  }
  if (value.charAt(index + 1) !== '-') {
    return
  }

  const keep = mainLineRegex.test(value)
  if (!keep) return

  const [before, gridTable, realGridTable, after, hasHeader] = extractTable(value, eat, this)
  if (!gridTable || gridTable.length < 3) return

  const now = eat.now()
  const linesInfos = computeColumnStartingPositions(gridTable)
  const tableContent = extractTableContent(gridTable, linesInfos, hasHeader)
  const tableElt = generateTable(tableContent, now, this)
  const merged = merge(before, realGridTable, after)

  // Because we can't add multiples blocs in one eat, I use a temp block
  const wrapperBlock = {
    type: 'element',
    tagName: 'WrapperBlock',
    children: [],
  }

  if (before.length) {
    const tokensBefore = this.tokenizeBlock(before.join('\n'), now)[0]
    wrapperBlock.children.push(tokensBefore)
  }

  wrapperBlock.children.push(tableElt)

  if (after.length) {
    const tokensAfter = this.tokenizeBlock(after.join('\n'), now)
    if (tokensAfter.length) {
      wrapperBlock.children.push(tokensAfter[0])
    }
  }

  return eat(merged)(wrapperBlock)
}

function deleteWrapperBlock () {
  function one (node, index, parent) {
    if (!node.children) return

    const newChildren = []
    let replace = false
    for (let c = 0; c < node.children.length; c++) {
      const child = node.children[c]
      if (child.tagName === 'WrapperBlock' && child.type === 'element') {
        replace = true
        for (let cc = 0; cc < child.children.length; cc++) {
          newChildren.push(child.children[cc])
        }
      } else {
        newChildren.push(child)
      }
    }
    if (replace) {
      node.children = newChildren
    }
  }
  return one
}

function transformer (tree) {
  // Remove the temporary block in which we previously wrapped the table parts
  visit(tree, deleteWrapperBlock())
}

function createGrid (nbRows, nbCols) {
  const grid = []

  for (let i = 0; i < nbRows; i++) {
    grid.push([])
    for (let j = 0; j < nbCols; j++) {
      grid[i].push({height: -1, width: -1, hasBottom: true, hasRigth: true})
    }
  }

  return grid
}

function setWidth (grid, i, j, cols) {
  /* To do it, we put enougth space to write the text.
   * For multi-cell, we divid it among the cells. */
  let tmpWidth = Math.max(...Array.from(grid[i][j].value).map(x => x.length)) + 2

  grid[i].forEach((_, c) => {
    if (c < cols) { // To divid
      const localWidth = Math.ceil(tmpWidth / (cols - c)) // cols - c will be 1 for the last cell
      tmpWidth -= localWidth
      grid[i][j + c].width = localWidth
    }
  })
}

function setHeight (grid, i, j, values) {
  // To do it, we count the line. Extra length to cell with a pipe
  // in the value of the last line, to not be confuse with a border.
  grid[i][j].height = values.length
  // Extra line
  if (values[values.length - 1].indexOf('|') > 0) {
    grid[i][j].height += 1
  }
}

function extractAST (gridNode, grid) {
  let i = 0
  /* Fill the grid with value, height and width from the ast */
  gridNode.children.forEach(th => {
    th.children.forEach(row => {
      row.children.forEach((cell, j) => {
        let X = 0 // x taking colspan and rowspan into account

        while (grid[i][j + X].evaluated) X++
        grid[i][j + X].value = this.all(cell).join('\n\n').split('\n')

        setHeight(grid, i, j + X, grid[i][j + X].value)
        setWidth(grid, i, j + X, cell.data.hProperties.colspan)

        // If it's empty, we fill it up with a useless space
        // Otherwise, it will not be parsed.
        if (!grid[0][0].value.join('\n')) {
          grid[0][0].value = [' ']
          grid[0][0].width = 3
        }

        // Define the border of each cell
        for (let x = 0; x < cell.data.hProperties.rowspan; x++) {
          for (let y = 0; y < cell.data.hProperties.colspan; y++) {
            // b attribute is for bottom
            grid[i + x][j + X + y].hasBottom = x + 1 === cell.data.hProperties.rowspan
            // r attribute is for right
            grid[i + x][j + X + y].hasRigth = y + 1 === cell.data.hProperties.colspan

            // set v if a cell has ever been define
            grid[i + x][j + X + y].evaluated = ' '
          }
        }
      })
      i++
    })
  })

  // If they is 2 differents tableHeader, so the first one is a header and
  // should be underlined
  if (gridNode.children.length > 1) {
    grid[gridNode.children[0].children.length - 1][0].isHeader = true
  }
}

function setSize (grid) {
  // The idea is the max win

  // Set the height of each column
  grid.forEach(row => {
    // Find the max
    const maxHeight = Math.max(...row.map(cell => cell.height))

    // Set it to each cell
    row.forEach(cell => { cell.height = maxHeight })
  })

  // Set the width of each row
  grid[0].forEach((_, j) => {
    // Find the max
    const maxWidth = Math.max(...grid.map(row => row[j].width))

    // Set it to each cell
    grid.forEach(row => { row[j].width = maxWidth })
  })
}
function generateBorders (grid, nbRows, nbCols, gridString) {
  /** **** Create the borders *******/

  // Create the first line
  /*
   * We have to create the first line manually because
   * we process the borders from the attributes bottom
   * and right of each cell. For the first line, their
   * is no bottom nor right cell.
   *
   * We only need the right attribute of the first row's
   * cells
   */
  let first = '+'
  grid[0].forEach((cell, i) => {
    first += '-'.repeat(cell.width)
    first += cell.hasRigth || i === nbCols - 1 ? '+' : '-'
  })

  gridString.push(first)

  grid.forEach((row, i) => {
    let line = ''

    // Cells lines
    // The inner of the cell
    line = '|'
    row.forEach(cell => {
      cell.y = gridString.length
      cell.x = line.length + 1
      line += ' '.repeat(cell.width)
      line += cell.hasRigth ? '|' : ' '
    })

    // Add it until the text can fit
    for (let t = 0; t < row[0].height; t++) {
      gridString.push(line)
    }

    // "End" line
    // It's the last line of the cell. Actually the border.
    line = row[0].hasBottom ? '+' : '|'

    row.forEach((cell, j) => {
      let char = ' '

      if (cell.hasBottom) {
        if (row[0].isHeader) {
          char = '='
        } else {
          char = '-'
        }
      }

      line += char.repeat(cell.width)

      if (cell.hasBottom || (j + 1 < nbCols && grid[i][j + 1].hasBottom)) {
        if (cell.hasRigth || (i + 1 < nbRows && grid[i + 1][j].hasRigth)) {
          line += '+'
        } else {
          line += (row[0].isHeader ? '=' : '-')
        }
      } else if (cell.hasRigth || (i + 1 < nbRows && grid[i + 1][j].hasRigth)) {
        line += '|'
      } else {
        line += ' '
      }
    })

    gridString.push(line)
  })
}

function writeText (grid, gridString) {
  grid.forEach(row => {
    row.forEach(cell => {
      if (cell.value && cell.value[0]) {
        for (let tmpCount = 0; tmpCount < cell.value.length; tmpCount++) {
          const tmpLine = cell.y + tmpCount
          const line = cell.value[tmpCount]
          const lineEdit = gridString[tmpLine]

          gridString[tmpLine] = lineEdit.substr(0, cell.x)
          gridString[tmpLine] += line
          gridString[tmpLine] += lineEdit.substr(cell.x + line.length)
        }
      }
    })
  })
}

function stringifyGridTables (gridNode) {
  const gridString = []

  const nbRows = gridNode.children.map(th => th.children.length).reduce((a, b) => a + b)
  const nbCols = gridNode.children[0]
    .children[0]
    .children.map(c => c.data.hProperties.colspan)
    .reduce((a, b) => a + b)

  const grid = createGrid(nbRows, nbCols)

  /* First, we extract the information
   * then, we set the size(2) of the border
   * and create it(3).
   * Finaly we fill it up.
   */

  extractAST.bind(this)(gridNode, grid)

  setSize(grid)

  generateBorders(grid, nbRows, nbCols, gridString)

  writeText(grid, gridString)

  return gridString.join('\n')
}

function plugin () {
  const Parser = this.Parser

  // Inject blockTokenizer
  const blockTokenizers = Parser.prototype.blockTokenizers
  const blockMethods = Parser.prototype.blockMethods
  blockTokenizers.gridTable = gridTableTokenizer
  blockMethods.splice(blockMethods.indexOf('fencedCode') + 1, 0, 'gridTable')

  const Compiler = this.Compiler

  // Stringify
  if (Compiler) {
    const visitors = Compiler.prototype.visitors
    if (!visitors) return

    visitors.gridTable = stringifyGridTables
  }

  return transformer
}
