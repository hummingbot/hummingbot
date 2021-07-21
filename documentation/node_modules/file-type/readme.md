# file-type [![Build Status](https://travis-ci.org/sindresorhus/file-type.svg?branch=master)](https://travis-ci.org/sindresorhus/file-type)

> Detect the file type of a Buffer/Uint8Array/ArrayBuffer

The file type is detected by checking the [magic number](https://en.wikipedia.org/wiki/Magic_number_(programming)#Magic_numbers_in_files) of the buffer.


## Install

```
$ npm install file-type
```


## Usage

##### Node.js

```js
const readChunk = require('read-chunk');
const fileType = require('file-type');

const buffer = readChunk.sync('unicorn.png', 0, fileType.minimumBytes);

fileType(buffer);
//=> {ext: 'png', mime: 'image/png'}
```

Or from a remote location:

```js
const https = require('https');
const fileType = require('file-type');

const url = 'https://upload.wikimedia.org/wikipedia/en/a/a9/Example.jpg';

https.get(url, response => {
	response.on('readable', () => {
		const chunk = response.read(fileType.minimumBytes);
		response.destroy();

		console.log(fileType(chunk));
		//=> {ext: 'jpg', mime: 'image/jpeg'}
	});
});
```

Or from a stream:

```js
const stream = require('stream');
const fs = require('fs');
const crypto = require('crypto');
const fileType = require('file-type');

(async () => {
	const read = fs.createReadStream('encrypted.enc');
	const decipher = crypto.createDecipheriv(alg, key, iv);

	const fileTypeStream = await fileType.stream(stream.pipeline(read, decipher));

	console.log(fileTypeStream.fileType);
	//=> {ext: 'mov', mime: 'video/quicktime'}

	const write = fs.createWriteStream(`decrypted.${fileTypeStream.fileType.ext}`);
	fileTypeStream.pipe(write);
})();
```


##### Browser

```js
const xhr = new XMLHttpRequest();
xhr.open('GET', 'unicorn.png');
xhr.responseType = 'arraybuffer';

xhr.onload = () => {
	fileType(new Uint8Array(this.response));
	//=> {ext: 'png', mime: 'image/png'}
};

xhr.send();
```


## API

### fileType(input)

Returns an `object` with:

- `ext` - One of the [supported file types](#supported-file-types)
- `mime` - The [MIME type](https://en.wikipedia.org/wiki/Internet_media_type)

Or `undefined` when there is no match.

#### input

Type: `Buffer | Uint8Array | ArrayBuffer`

It only needs the first `.minimumBytes` bytes. The exception is detection of `docx`, `pptx`, and `xlsx` which potentially requires reading the whole file.

### fileType.minimumBytes

Type: `number`

The minimum amount of bytes needed to detect a file type. Currently, it's 4100 bytes, but it can change, so don't hardcode it.

### fileType.stream(readableStream)

Detect the file type of a readable stream.

Returns a `Promise` which resolves to the original readable stream argument, but with an added `fileType` property, which is an object like the one returned from `fileType()`.

*Note:* This method is only for Node.js.

#### readableStream

Type: [`stream.Readable`](https://nodejs.org/api/stream.html#stream_class_stream_readable)

### fileType.extensions

Returns a set of supported file extensions.

### fileType.mimeTypes

Returns a set of supported MIME types.


## Supported file types

- [`jpg`](https://en.wikipedia.org/wiki/JPEG)
- [`png`](https://en.wikipedia.org/wiki/Portable_Network_Graphics)
- [`apng`](https://en.wikipedia.org/wiki/APNG) - Animated Portable Network Graphics
- [`gif`](https://en.wikipedia.org/wiki/GIF)
- [`webp`](https://en.wikipedia.org/wiki/WebP)
- [`flif`](https://en.wikipedia.org/wiki/Free_Lossless_Image_Format)
- [`cr2`](https://fileinfo.com/extension/cr2) - Canon Raw image file (v2)
- [`orf`](https://en.wikipedia.org/wiki/ORF_format) - Olympus Raw image file
- [`arw`](https://en.wikipedia.org/wiki/Raw_image_format#ARW) - Sony Alpha Raw image file
- [`dng`](https://en.wikipedia.org/wiki/Digital_Negative) - Adobe Digital Negative image file
- [`nef`](https://www.nikonusa.com/en/learn-and-explore/a/products-and-innovation/nikon-electronic-format-nef.html) - Nikon Electronic Format image file
- [`rw2`](https://en.wikipedia.org/wiki/Raw_image_format) - Panasonic RAW image file
- [`raf`](https://en.wikipedia.org/wiki/Raw_image_format) - Fujifilm RAW image file
- [`tif`](https://en.wikipedia.org/wiki/Tagged_Image_File_Format)
- [`bmp`](https://en.wikipedia.org/wiki/BMP_file_format)
- [`jxr`](https://en.wikipedia.org/wiki/JPEG_XR)
- [`psd`](https://en.wikipedia.org/wiki/Adobe_Photoshop#File_format)
- [`zip`](https://en.wikipedia.org/wiki/Zip_(file_format))
- [`tar`](https://en.wikipedia.org/wiki/Tar_(computing)#File_format)
- [`rar`](https://en.wikipedia.org/wiki/RAR_(file_format))
- [`gz`](https://en.wikipedia.org/wiki/Gzip)
- [`bz2`](https://en.wikipedia.org/wiki/Bzip2)
- [`7z`](https://en.wikipedia.org/wiki/7z)
- [`dmg`](https://en.wikipedia.org/wiki/Apple_Disk_Image)
- [`mp4`](https://en.wikipedia.org/wiki/MPEG-4_Part_14#Filename_extensions)
- [`mid`](https://en.wikipedia.org/wiki/MIDI)
- [`mkv`](https://en.wikipedia.org/wiki/Matroska)
- [`webm`](https://en.wikipedia.org/wiki/WebM)
- [`mov`](https://en.wikipedia.org/wiki/QuickTime_File_Format)
- [`avi`](https://en.wikipedia.org/wiki/Audio_Video_Interleave)
- [`mpg`](https://en.wikipedia.org/wiki/MPEG-1)
- [`mp2`](https://en.wikipedia.org/wiki/MPEG-1_Audio_Layer_II)
- [`mp3`](https://en.wikipedia.org/wiki/MP3)
- [`ogg`](https://en.wikipedia.org/wiki/Ogg)
- [`ogv`](https://en.wikipedia.org/wiki/Ogg)
- [`ogm`](https://en.wikipedia.org/wiki/Ogg)
- [`oga`](https://en.wikipedia.org/wiki/Ogg)
- [`spx`](https://en.wikipedia.org/wiki/Ogg)
- [`ogx`](https://en.wikipedia.org/wiki/Ogg)
- [`opus`](https://en.wikipedia.org/wiki/Opus_(audio_format))
- [`flac`](https://en.wikipedia.org/wiki/FLAC)
- [`wav`](https://en.wikipedia.org/wiki/WAV)
- [`qcp`](https://en.wikipedia.org/wiki/QCP)
- [`amr`](https://en.wikipedia.org/wiki/Adaptive_Multi-Rate_audio_codec)
- [`pdf`](https://en.wikipedia.org/wiki/Portable_Document_Format)
- [`epub`](https://en.wikipedia.org/wiki/EPUB)
- [`mobi`](https://en.wikipedia.org/wiki/Mobipocket) - Mobipocket
- [`exe`](https://en.wikipedia.org/wiki/.exe)
- [`swf`](https://en.wikipedia.org/wiki/SWF)
- [`rtf`](https://en.wikipedia.org/wiki/Rich_Text_Format)
- [`woff`](https://en.wikipedia.org/wiki/Web_Open_Font_Format)
- [`woff2`](https://en.wikipedia.org/wiki/Web_Open_Font_Format)
- [`eot`](https://en.wikipedia.org/wiki/Embedded_OpenType)
- [`ttf`](https://en.wikipedia.org/wiki/TrueType)
- [`otf`](https://en.wikipedia.org/wiki/OpenType)
- [`ico`](https://en.wikipedia.org/wiki/ICO_(file_format))
- [`flv`](https://en.wikipedia.org/wiki/Flash_Video)
- [`ps`](https://en.wikipedia.org/wiki/Postscript)
- [`xz`](https://en.wikipedia.org/wiki/Xz)
- [`sqlite`](https://www.sqlite.org/fileformat2.html)
- [`nes`](https://fileinfo.com/extension/nes)
- [`crx`](https://developer.chrome.com/extensions/crx)
- [`xpi`](https://en.wikipedia.org/wiki/XPInstall)
- [`cab`](https://en.wikipedia.org/wiki/Cabinet_(file_format))
- [`deb`](https://en.wikipedia.org/wiki/Deb_(file_format))
- [`ar`](https://en.wikipedia.org/wiki/Ar_(Unix))
- [`rpm`](https://fileinfo.com/extension/rpm)
- [`Z`](https://fileinfo.com/extension/z)
- [`lz`](https://en.wikipedia.org/wiki/Lzip)
- [`msi`](https://en.wikipedia.org/wiki/Windows_Installer)
- [`mxf`](https://en.wikipedia.org/wiki/Material_Exchange_Format)
- [`mts`](https://en.wikipedia.org/wiki/.m2ts)
- [`wasm`](https://en.wikipedia.org/wiki/WebAssembly)
- [`blend`](https://wiki.blender.org/index.php/Dev:Source/Architecture/File_Format)
- [`bpg`](https://bellard.org/bpg/)
- [`docx`](https://en.wikipedia.org/wiki/Office_Open_XML)
- [`pptx`](https://en.wikipedia.org/wiki/Office_Open_XML)
- [`xlsx`](https://en.wikipedia.org/wiki/Office_Open_XML)
- [`jp2`](https://en.wikipedia.org/wiki/JPEG_2000) - JPEG 2000
- [`jpm`](https://en.wikipedia.org/wiki/JPEG_2000) - JPEG 2000
- [`jpx`](https://en.wikipedia.org/wiki/JPEG_2000) - JPEG 2000
- [`mj2`](https://en.wikipedia.org/wiki/Motion_JPEG_2000) - Motion JPEG 2000
- [`aif`](https://en.wikipedia.org/wiki/Audio_Interchange_File_Format)
- [`odt`](https://en.wikipedia.org/wiki/OpenDocument) - OpenDocument for word processing
- [`ods`](https://en.wikipedia.org/wiki/OpenDocument) - OpenDocument for spreadsheets
- [`odp`](https://en.wikipedia.org/wiki/OpenDocument) - OpenDocument for presentations
- [`xml`](https://en.wikipedia.org/wiki/XML)
- [`heic`](https://nokiatech.github.io/heif/technical.html)
- [`cur`](https://en.wikipedia.org/wiki/ICO_(file_format))
- [`ktx`](https://www.khronos.org/opengles/sdk/tools/KTX/file_format_spec/)
- [`ape`](https://en.wikipedia.org/wiki/Monkey%27s_Audio) - Monkey's Audio
- [`wv`](https://en.wikipedia.org/wiki/WavPack) - WavPack
- [`asf`](https://en.wikipedia.org/wiki/Advanced_Systems_Format) - Advanced Systems Format
- [`wma`](https://en.wikipedia.org/wiki/Windows_Media_Audio) - Windows Media Audio
- [`wmv`](https://en.wikipedia.org/wiki/Windows_Media_Video) - Windows Media Video
- [`dcm`](https://en.wikipedia.org/wiki/DICOM#Data_format) - DICOM Image File
- [`mpc`](https://en.wikipedia.org/wiki/Musepack) - Musepack (SV7 & SV8)
- [`ics`](https://en.wikipedia.org/wiki/ICalendar#Data_format) - iCalendar
- [`glb`](https://github.com/KhronosGroup/glTF) - GL Transmission Format
- [`pcap`](https://wiki.wireshark.org/Development/LibpcapFileFormat) - Libpcap File Format
- [`dsf`](https://dsd-guide.com/sites/default/files/white-papers/DSFFileFormatSpec_E.pdf) - Sony DSD Stream File (DSF)
- [`lnk`](https://en.wikipedia.org/wiki/Shortcut_%28computing%29#Microsoft_Windows) - Microsoft Windows file shortcut
- [`alias`](https://en.wikipedia.org/wiki/Alias_%28Mac_OS%29) - macOS Alias file
- [`voc`](https://wiki.multimedia.cx/index.php/Creative_Voice) - Creative Voice File
- [`ac3`](https://www.atsc.org/standard/a522012-digital-audio-compression-ac-3-e-ac-3-standard-12172012/) - ATSC A/52 Audio File
- [`3gp`](https://en.wikipedia.org/wiki/3GP_and_3G2#3GP) - Multimedia container format defined by the Third Generation Partnership Project (3GPP) for 3G UMTS multimedia services
- [`3g2`](https://en.wikipedia.org/wiki/3GP_and_3G2#3G2) - Multimedia container format defined by the 3GPP2 for 3G CDMA2000 multimedia services
- [`m4v`](https://en.wikipedia.org/wiki/M4V) -  MPEG-4 Visual bitstreams
- [`m4p`](https://en.wikipedia.org/wiki/MPEG-4_Part_14#Filename_extensions) - MPEG-4 files with audio streams encrypted by FairPlay Digital Rights Management as were sold through the iTunes Store
- [`m4a`](https://en.wikipedia.org/wiki/M4A) - Audio-only MPEG-4 files
- [`m4b`](https://en.wikipedia.org/wiki/M4B) - Audiobook and podcast MPEG-4 files, which also contain metadata including chapter markers, images, and hyperlinks
- [`f4v`](https://en.wikipedia.org/wiki/Flash_Video) - ISO base media file format used by Adobe Flash Player
- [`f4p`](https://en.wikipedia.org/wiki/Flash_Video) - ISO base media file format protected by Adobe Access DRM used by Adobe Flash Player
- [`f4a`](https://en.wikipedia.org/wiki/Flash_Video) - Audio-only ISO base media file format used by Adobe Flash Player
- [`f4b`](https://en.wikipedia.org/wiki/Flash_Video) - Audiobook and podcast ISO base media file format used by Adobe Flash Player
- [`mie`](https://en.wikipedia.org/wiki/Sidecar_file) - Dedicated meta information format which supports storage of binary as well as textual meta information
- [`shp`](https://en.wikipedia.org/wiki/Shapefile) - Geospatial vector data format
- [`arrow`](https://arrow.apache.org) - Columnar format for tables of data

*SVG isn't included as it requires the whole file to be read, but you can get it [here](https://github.com/sindresorhus/is-svg).*

*Pull requests are welcome for additional commonly used file types, except for `doc`, `xls`, `ppt`.*


## file-type for enterprise

Available as part of the Tidelift Subscription.

The maintainers of file-type and thousands of other packages are working with Tidelift to deliver commercial support and maintenance for the open source dependencies you use to build your applications. Save time, reduce risk, and improve code health, while paying the maintainers of the exact dependencies you use. [Learn more.](https://tidelift.com/subscription/pkg/npm-file-type?utm_source=npm-file-type&utm_medium=referral&utm_campaign=enterprise&utm_term=repo)


## Related

- [file-type-cli](https://github.com/sindresorhus/file-type-cli) - CLI for this module


## Maintainers

- [Sindre Sorhus](https://github.com/sindresorhus)
- [Mikael Finstad](https://github.com/mifi)
- [Ben Brook](https://github.com/bencmbrook)
