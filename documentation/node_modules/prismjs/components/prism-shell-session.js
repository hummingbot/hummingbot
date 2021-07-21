(function (Prism) {

	// CAREFUL!
	// The following patterns are concatenated, so the group referenced by a back reference is non-obvious!

	var strings = [
		// normal string
		// 1 capturing group
		/(["'])(?:\\[\s\S]|\$\([^)]+\)|`[^`]+`|(?!\1)[^\\])*\1/.source,

		// here doc
		// 2 capturing groups
		/<<-?\s*(["']?)(\w+)\2\s[\s\S]*?[\r\n]\3/.source
	].join('|');

	Prism.languages['shell-session'] = {
		'info': {
			// foo@bar:~/files$ exit
			// foo@bar$ exit
			pattern: /^[^\r\n$#*!]+(?=[$#])/m,
			alias: 'punctuation',
			inside: {
				'path': {
					pattern: /(:)[\s\S]+/,
					lookbehind: true
				},
				'user': /^[^\s@:$#*!/\\]+@[^\s@:$#*!/\\]+(?=:|$)/,
				'punctuation': /:/
			}
		},
		'command': {
			pattern: RegExp(/[$#](?:[^\\\r\n'"<]|\\.|<<str>>)+/.source.replace(/<<str>>/g, function () { return strings; })),
			greedy: true,
			inside: {
				'bash': {
					pattern: /(^[$#]\s*)[\s\S]+/,
					lookbehind: true,
					alias: 'language-bash',
					inside: Prism.languages.bash
				},
				'shell-symbol': {
					pattern: /^[$#]/,
					alias: 'important'
				}
			}
		},
		'output': /.(?:.*(?:[\r\n]|.$))*/
	};

	Prism.languages['sh-session'] = Prism.languages['shellsession'] = Prism.languages['shell-session'];

}(Prism));
