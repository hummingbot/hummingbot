Utility functions shared by [`react-highlight-words`](https://github.com/bvaughn/react-highlight-words) and [`react-native-highlight-words`](https://github.com/clauderic/react-native-highlight-words).

## API

The primary API for this package is a function exported as `findAll`. This method searches a string of text for a set of search terms and returns an array of "chunks" that describe the matches found.

Each "chunk" is an object consisting of a pair of indices (`chunk.start` and `chunk.end`) and a boolean specfifying whether the chunk is a match (`chunk.highlight`). For example:

```js
import { findAll } from "highlight-words-core";

const textToHighlight = "This is some text to highlight.";
const searchWords = ["This", "i"];

const chunks = findAll({
  searchWords,
  textToHighlight
});

const highlightedText = chunks
  .map(chunk => {
    const { end, highlight, start } = chunk;
    const text = textToHighlight.substr(start, end - start);
    if (highlight) {
      return `<mark>${text}</mark>`;
    } else {
      return text;
    }
  })
  .join("");
```

[Run this example on Code Sandbox.](https://codesandbox.io/s/ykwrzrl6wx)

### `findAll`

The `findAll` function accepts several parameters, although only the `searchWords` array and `textToHighlight` string are required.

| Parameter | Required? | Type | Description |
| --- | :---: | --- | --- |
| autoEscape |  | `boolean` | Escape special regular expression characters |
| caseSensitive |  | `boolean` | Search should be case sensitive |
| findChunks |  | `Function` | Custom find function (advanced) |
| sanitize |  | `Function` | Custom sanitize function (advanced) |
| searchWords | ✅ | `Array<string>` | Array of words to search for |
| textToHighlight | ✅ | `string` | Text to search and highlight |


## License
MIT License - fork, modify and use however you want.
