[![NPM version](https://badge.fury.io/js/idb-wrapper.svg)](http://badge.fury.io/js/idb-wrapper)
[![Dependency Status](https://gemnasium.com/jensarps/IDBWrapper.png)](https://gemnasium.com/jensarps/IDBWrapper)
[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2Fjensarps%2FIDBWrapper.svg?type=shield)](https://app.fossa.io/projects/git%2Bgithub.com%2Fjensarps%2FIDBWrapper?ref=badge_shield)


**IDBWrapper** is a cross-browser wrapper for the HTML5 IndexedDB API. While this
API is the future of offline storage, it is not very intuitive to use.
IDBWrapper is there to provide easy access to IndexedDB's features.

Browser Support
---

IDBWrapper works on all browsers supporting the IndexedDB API, which are:

**Desktop**

Chrome, Firefox, Opera 15+, IE 10+, Safari 8+

**Mobile**

Chrome for Android, Firefox for Android, Opera for Android, IE10 for WP8, iOS 8+

**Worker** 

IDBWrapper runs inside of a worker on following browsers:

Chrome (also on Android), Firefox (also on Android), Opera (also on Android), IE10+ (also on WP8+)

If using in an older browser supporting WebSql along with [IndexedDBShim](https://github.com/axemclion/IndexedDBShim), IndexedDBShim needs to run first.

Note on limited/buggy IndexedDB support:

* IE has limited support, which can be fixed by including [idb-iegap](https://github.com/dfahlander/idb-iegap)
* Safari has buggy support, which can be fixed by using the above mentioned shim
* Details on how to change the implementation being used can be found in the [wiki](https://github.com/jensarps/IDBWrapper/wiki/Usage#defining-implementation-preference-aka-make-idbwrapper-use-the-shim)
* Here's a guide to [feature detecting limited/buggy IndexedDB support](http://jensarps.de/2015/12/16/how-to-detect-buggy-indexeddb-implementations/)

Using IDBWrapper
===

Tutorials
---

There are two tutorials to get you up and running:

Part 1: Setup and CRUD operations
http://jensarps.de/2011/11/25/working-with-idbwrapper-part-1/

Part 2: Running Queries against the store
http://jensarps.de/2012/11/13/working-with-idbwrapper-part-2/

Examples
---

There are some examples to run right in your browser over here: http://jensarps.github.io/IDBWrapper/example/

The source for these examples are in the `example` folder of this repository.

Wiki
---

For usage instructions, details about mothods for reading and writing 
data, setting up indexes and running queries, please refer to the 
[Wiki](https://github.com/jensarps/IDBWrapper/wiki).

API Reference
---

There's an API reference over here: http://jensarps.github.io/IDBWrapper/doc/latest/IDBStore.html

For references of older versions, please refer to this index: http://jensarps.github.io/IDBWrapper/doc/

Obtaining IDBWrapper
===

cdnjs
---

IDBWrapper is also available on [cdnjs](http://cdnjs.com/). You can directly 
point a script tag there, or `require()` it from there. cdnjs supports http,
https and spdy, so you can just leave the protocol off. The URLs for the 
different versions of IDBWrapper can be found here: 
[https://cdnjs.com/libraries/idbwrapper](https://cdnjs.com/libraries/idbwrapper)

Package Managers
---

If you use NPM as your package manager, you can get it from there, too, by
running:

```bash
$ npm install idb-wrapper
```

If you use bower as your package manager, run the following:

```bash
$ bower install idbwrapper
```

If you want to add IDBWrapper to a volo project, just run:

```bash
$ volo add idbwrapper
```

git
---

You can git clone the repository, or download a zip file here: https://github.com/jensarps/IDBWrapper/releases

## License
[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2Fjensarps%2FIDBWrapper.svg?type=large)](https://app.fossa.io/projects/git%2Bgithub.com%2Fjensarps%2FIDBWrapper?ref=badge_large)
