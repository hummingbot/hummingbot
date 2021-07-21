/// <reference types="node"/>
import {Readable as ReadableStream} from 'stream';

declare namespace fileType {
	type FileType =
		| 'jpg'
		| 'png'
		| 'apng'
		| 'gif'
		| 'webp'
		| 'flif'
		| 'cr2'
		| 'orf'
		| 'arw'
		| 'dng'
		| 'nef'
		| 'rw2'
		| 'raf'
		| 'tif'
		| 'bmp'
		| 'jxr'
		| 'psd'
		| 'zip'
		| 'tar'
		| 'rar'
		| 'gz'
		| 'bz2'
		| '7z'
		| 'dmg'
		| 'mp4'
		| 'mid'
		| 'mkv'
		| 'webm'
		| 'mov'
		| 'avi'
		| 'wmv'
		| 'mpg'
		| 'mp2'
		| 'mp3'
		| 'm4a'
		| 'ogg'
		| 'opus'
		| 'flac'
		| 'wav'
		| 'qcp'
		| 'amr'
		| 'pdf'
		| 'epub'
		| 'mobi'
		| 'exe'
		| 'swf'
		| 'rtf'
		| 'woff'
		| 'woff2'
		| 'eot'
		| 'ttf'
		| 'otf'
		| 'ico'
		| 'flv'
		| 'ps'
		| 'xz'
		| 'sqlite'
		| 'nes'
		| 'crx'
		| 'xpi'
		| 'cab'
		| 'deb'
		| 'ar'
		| 'rpm'
		| 'Z'
		| 'lz'
		| 'msi'
		| 'mxf'
		| 'mts'
		| 'wasm'
		| 'blend'
		| 'bpg'
		| 'docx'
		| 'pptx'
		| 'xlsx'
		| '3gp'
		| '3g2'
		| 'jp2'
		| 'jpm'
		| 'jpx'
		| 'mj2'
		| 'aif'
		| 'odt'
		| 'ods'
		| 'odp'
		| 'xml'
		| 'heic'
		| 'cur'
		| 'ktx'
		| 'ape'
		| 'wv'
		| 'asf'
		| 'wma'
		| 'dcm'
		| 'mpc'
		| 'ics'
		| 'glb'
		| 'pcap'
		| 'dsf'
		| 'lnk'
		| 'alias'
		| 'voc'
		| 'ac3'
		| 'm4b'
		| 'm4p'
		| 'm4v'
		| 'f4a'
		| 'f4b'
		| 'f4p'
		| 'f4v'
		| 'mie'
		| 'ogv'
		| 'ogm'
		| 'oga'
		| 'spx'
		| 'ogx'
		| 'arrow'
		| 'shp';

	type MimeType =
		| 'image/jpeg'
		| 'image/png'
		| 'image/gif'
		| 'image/webp'
		| 'image/flif'
		| 'image/x-canon-cr2'
		| 'image/tiff'
		| 'image/bmp'
		| 'image/vnd.ms-photo'
		| 'image/vnd.adobe.photoshop'
		| 'application/epub+zip'
		| 'application/x-xpinstall'
		| 'application/vnd.oasis.opendocument.text'
		| 'application/vnd.oasis.opendocument.spreadsheet'
		| 'application/vnd.oasis.opendocument.presentation'
		| 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
		| 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
		| 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
		| 'application/zip'
		| 'application/x-tar'
		| 'application/x-rar-compressed'
		| 'application/gzip'
		| 'application/x-bzip2'
		| 'application/x-7z-compressed'
		| 'application/x-apple-diskimage'
		| 'video/mp4'
		| 'audio/midi'
		| 'video/x-matroska'
		| 'video/webm'
		| 'video/quicktime'
		| 'video/vnd.avi'
		| 'audio/vnd.wave'
		| 'audio/qcelp'
		| 'audio/x-ms-wma'
		| 'video/x-ms-asf'
		| 'application/vnd.ms-asf'
		| 'video/mpeg'
		| 'video/3gpp'
		| 'audio/mpeg'
		| 'audio/mp4' // RFC 4337
		| 'audio/opus'
		| 'video/ogg'
		| 'audio/ogg'
		| 'application/ogg'
		| 'audio/x-flac'
		| 'audio/ape'
		| 'audio/wavpack'
		| 'audio/amr'
		| 'application/pdf'
		| 'application/x-msdownload'
		| 'application/x-shockwave-flash'
		| 'application/rtf'
		| 'application/wasm'
		| 'font/woff'
		| 'font/woff2'
		| 'application/vnd.ms-fontobject'
		| 'font/ttf'
		| 'font/otf'
		| 'image/x-icon'
		| 'video/x-flv'
		| 'application/postscript'
		| 'application/x-xz'
		| 'application/x-sqlite3'
		| 'application/x-nintendo-nes-rom'
		| 'application/x-google-chrome-extension'
		| 'application/vnd.ms-cab-compressed'
		| 'application/x-deb'
		| 'application/x-unix-archive'
		| 'application/x-rpm'
		| 'application/x-compress'
		| 'application/x-lzip'
		| 'application/x-msi'
		| 'application/x-mie'
		| 'application/x-apache-arrow'
		| 'application/mxf'
		| 'video/mp2t'
		| 'application/x-blender'
		| 'image/bpg'
		| 'image/jp2'
		| 'image/jpx'
		| 'image/jpm'
		| 'image/mj2'
		| 'audio/aiff'
		| 'application/xml'
		| 'application/x-mobipocket-ebook'
		| 'image/heif'
		| 'image/heif-sequence'
		| 'image/heic'
		| 'image/heic-sequence'
		| 'image/ktx'
		| 'application/dicom'
		| 'audio/x-musepack'
		| 'text/calendar'
		| 'model/gltf-binary'
		| 'application/vnd.tcpdump.pcap'
		| 'audio/x-dsf' // Non-standard
		| 'application/x.ms.shortcut' // Invented by us
		| 'application/x.apple.alias' // Invented by us
		| 'audio/x-voc'
		| 'audio/vnd.dolby.dd-raw'
		| 'audio/x-m4a'
		| 'image/apng'
		| 'image/x-olympus-orf'
		| 'image/x-sony-arw'
		| 'image/x-adobe-dng'
		| 'image/x-nikon-nef'
		| 'image/x-panasonic-rw2'
		| 'image/x-fujifilm-raf'
		| 'video/x-m4v'
		| 'video/3gpp2'
		| 'application/x-esri-shape';

	interface FileTypeResult {
		/**
		One of the supported [file types](https://github.com/sindresorhus/file-type#supported-file-types).
		*/
		ext: FileType;

		/**
		The detected [MIME type](https://en.wikipedia.org/wiki/Internet_media_type).
		*/
		mime: MimeType;
	}

	type ReadableStreamWithFileType = ReadableStream & {
		readonly fileType?: FileTypeResult;
	};
}

declare const fileType: {
	/**
	Detect the file type of a `Buffer`/`Uint8Array`/`ArrayBuffer`. The file type is detected by checking the [magic number](https://en.wikipedia.org/wiki/Magic_number_(programming)#Magic_numbers_in_files) of the buffer.

	@param buffer - It only needs the first `.minimumBytes` bytes. The exception is detection of `docx`, `pptx`, and `xlsx` which potentially requires reading the whole file.
	@returns The detected file type and MIME type or `undefined` when there was no match.

	@example
	```
	import readChunk = require('read-chunk');
	import fileType = require('file-type');

	const buffer = readChunk.sync('unicorn.png', 0, fileType.minimumBytes);

	fileType(buffer);
	//=> {ext: 'png', mime: 'image/png'}


	// Or from a remote location:

	import * as http from 'http';

	const url = 'https://assets-cdn.github.com/images/spinners/octocat-spinner-32.gif';

	http.get(url, response => {
		response.on('readable', () => {
			const chunk = response.read(fileType.minimumBytes);
			response.destroy();
			console.log(fileType(chunk));
			//=> {ext: 'gif', mime: 'image/gif'}
		});
	});
	```
	*/
	(buffer: Buffer | Uint8Array | ArrayBuffer): fileType.FileTypeResult | undefined;

	/**
	The minimum amount of bytes needed to detect a file type. Currently, it's 4100 bytes, but it can change, so don't hard-code it.
	*/
	readonly minimumBytes: number;

	/**
	Supported file extensions.
	*/
	readonly extensions: readonly fileType.FileType[];

	/**
	Supported MIME types.
	*/
	readonly mimeTypes: readonly fileType.MimeType[];

	/**
	Detect the file type of a readable stream.

	@param readableStream - A readable stream containing a file to examine, see: [`stream.Readable`](https://nodejs.org/api/stream.html#stream_class_stream_readable).
	@returns A `Promise` which resolves to the original readable stream argument, but with an added `fileType` property, which is an object like the one returned from `fileType()`.

	@example
	```
	import * as fs from 'fs';
	import * as crypto from 'crypto';
	import fileType = require('file-type');

	(async () => {
		const read = fs.createReadStream('encrypted.enc');
		const decipher = crypto.createDecipheriv(alg, key, iv);

		const stream = await fileType.stream(read.pipe(decipher));

		console.log(stream.fileType);
		//=> {ext: 'mov', mime: 'video/quicktime'}

		const write = fs.createWriteStream(`decrypted.${stream.fileType.ext}`);
		stream.pipe(write);
	})();
	```
	*/
	readonly stream: (
		readableStream: ReadableStream
	) => Promise<fileType.ReadableStreamWithFileType>;
};

export = fileType;
