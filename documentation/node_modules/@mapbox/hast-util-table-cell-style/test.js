/* eslint-env es6 */
'use strict';

const unified = require('unified');
const rehypeParse = require('rehype-parse');
const rehypeStringify = require('rehype-stringify');
const tableCellStyle = require('.');

function transformHtml(html) {
  return unified()
    .use(rehypeParse, { fragment: true })
    .use(() => tableCellStyle)
    .use(rehypeStringify)
    .processSync(html).contents;
}

describe('transforms align to CSS text-align', () => {
  test('for <tr>', () => {
    const actual = transformHtml('<tr align="center"><td>foo</td></tr>');
    expect(actual).toBe('<tr style="text-align: center;"><td>foo</td></tr>');
  });
  test('for <tr> that already has a style', () => {
    const actual = transformHtml(
      '<tr align="center" style="color: pink"><td>foo</td></tr>'
    );
    expect(actual).toBe(
      '<tr style="color: pink; text-align: center;"><td>foo</td></tr>'
    );
  });
  test('for <td>', () => {
    const actual = transformHtml('<td align="center">foo</td>');
    expect(actual).toBe('<td style="text-align: center;">foo</td>');
  });
  test('for <td> that already has a style', () => {
    const actual = transformHtml(
      '<td align="center" style="color: pink;">foo</td>'
    );
    expect(actual).toBe(
      '<td style="color: pink; text-align: center;">foo</td>'
    );
  });
  test('for <th>', () => {
    const actual = transformHtml('<th align="center">foo</th>');
    expect(actual).toBe('<th style="text-align: center;">foo</th>');
  });
  test('for <th> that already has a style', () => {
    const actual = transformHtml(
      '<th align="center" style="color: pink;   ">foo</th>'
    );
    expect(actual).toBe(
      '<th style="color: pink; text-align: center;">foo</th>'
    );
  });
});

describe('transforms valign to CSS vertical-align', () => {
  test('for <tr>', () => {
    const actual = transformHtml('<tr valign="center"><td>foo</td></tr>');
    expect(actual).toBe(
      '<tr style="vertical-align: center;"><td>foo</td></tr>'
    );
  });
  test('for <tr> that already has a style', () => {
    const actual = transformHtml(
      '<tr valign="center" style="color: pink"><td>foo</td></tr>'
    );
    expect(actual).toBe(
      '<tr style="color: pink; vertical-align: center;"><td>foo</td></tr>'
    );
  });
  test('for <td>', () => {
    const actual = transformHtml('<td valign="center">foo</td>');
    expect(actual).toBe('<td style="vertical-align: center;">foo</td>');
  });
  test('for <td> that already has a style', () => {
    const actual = transformHtml(
      '<td valign="center" style="color: pink;">foo</td>'
    );
    expect(actual).toBe(
      '<td style="color: pink; vertical-align: center;">foo</td>'
    );
  });
  test('for <th>', () => {
    const actual = transformHtml('<th valign="center">foo</th>');
    expect(actual).toBe('<th style="vertical-align: center;">foo</th>');
  });
  test('for <th> that already has a style', () => {
    const actual = transformHtml(
      '<th valign="center" style="color: pink;   ">foo</th>'
    );
    expect(actual).toBe(
      '<th style="color: pink; vertical-align: center;">foo</th>'
    );
  });
});

describe('transforms height to CSS height', () => {
  test('for <tr>', () => {
    const actual = transformHtml('<tr height="10px"><td>foo</td></tr>');
    expect(actual).toBe('<tr style="height: 10px;"><td>foo</td></tr>');
  });
  test('for <tr> that already has a style', () => {
    const actual = transformHtml(
      '<tr height="10px" style="color: pink"><td>foo</td></tr>'
    );
    expect(actual).toBe(
      '<tr style="color: pink; height: 10px;"><td>foo</td></tr>'
    );
  });
  test('for <td>', () => {
    const actual = transformHtml('<td height="10px">foo</td>');
    expect(actual).toBe('<td style="height: 10px;">foo</td>');
  });
  test('for <td> that already has a style', () => {
    const actual = transformHtml(
      '<td height="10px" style="color: pink;">foo</td>'
    );
    expect(actual).toBe('<td style="color: pink; height: 10px;">foo</td>');
  });
  test('for <th>', () => {
    const actual = transformHtml('<th height="10px">foo</th>');
    expect(actual).toBe('<th style="height: 10px;">foo</th>');
  });
  test('for <th> that already has a style', () => {
    const actual = transformHtml(
      '<th height="10px" style="color: pink;   ">foo</th>'
    );
    expect(actual).toBe('<th style="color: pink; height: 10px;">foo</th>');
  });
});

describe('transforms width to CSS width', () => {
  test('for <tr>', () => {
    const actual = transformHtml('<tr width="10px"><td>foo</td></tr>');
    expect(actual).toBe('<tr style="width: 10px;"><td>foo</td></tr>');
  });
  test('for <tr> that already has a style', () => {
    const actual = transformHtml(
      '<tr width="10px" style="color: pink"><td>foo</td></tr>'
    );
    expect(actual).toBe(
      '<tr style="color: pink; width: 10px;"><td>foo</td></tr>'
    );
  });
  test('for <td>', () => {
    const actual = transformHtml('<td width="10px">foo</td>');
    expect(actual).toBe('<td style="width: 10px;">foo</td>');
  });
  test('for <td> that already has a style', () => {
    const actual = transformHtml(
      '<td width="10px" style="color: pink;">foo</td>'
    );
    expect(actual).toBe('<td style="color: pink; width: 10px;">foo</td>');
  });
  test('for <th>', () => {
    const actual = transformHtml('<th width="10px">foo</th>');
    expect(actual).toBe('<th style="width: 10px;">foo</th>');
  });
  test('for <th> that already has a style', () => {
    const actual = transformHtml(
      '<th width="10px" style="color: pink;   ">foo</th>'
    );
    expect(actual).toBe('<th style="color: pink; width: 10px;">foo</th>');
  });
});
