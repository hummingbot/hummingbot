// 1C:Enterprise
// https://github.com/Diversus23/
//
Prism.languages.bsl = {
	'comment': /\/\/.*/,
	'string': [
		// Строки
		// Strings
		{
			pattern: /"(?:[^"]|"")*"(?!")/,
			greedy: true
		},
		// Дата и время
		// Date & time
		{
			pattern: /'(?:[^'\r\n\\]|\\.)*'/
		}
	],
	'keyword': [
		{
			// RU
			pattern: /(^|[^\w\u0400-\u0484\u0487-\u052f\u1c80-\u1c88\u1d2b\u1d78\u2de0-\u2dff\ua640-\ua69f\ufe2e\ufe2f])(?:пока|для|новый|прервать|попытка|исключение|вызватьисключение|иначе|конецпопытки|неопределено|функция|перем|возврат|конецфункции|если|иначеесли|процедура|конецпроцедуры|тогда|знач|экспорт|конецесли|из|каждого|истина|ложь|по|цикл|конеццикла|выполнить)(?![\w\u0400-\u0484\u0487-\u052f\u1c80-\u1c88\u1d2b\u1d78\u2de0-\u2dff\ua640-\ua69f\ufe2e\ufe2f])/i,
			lookbehind: true
		},
		{
			// EN
			pattern: /\b(?:while|for|new|break|try|except|raise|else|endtry|undefined|function|var|return|endfunction|null|if|elseif|procedure|endprocedure|then|val|export|endif|in|each|true|false|to|do|enddo|execute)\b/i
		}
	],
	'number': {
		pattern: /(^(?=\d)|[^\w\u0400-\u0484\u0487-\u052f\u1c80-\u1c88\u1d2b\u1d78\u2de0-\u2dff\ua640-\ua69f\ufe2e\ufe2f])(?:\d+\.?\d*|\.\d+)(?:E[+-]?\d+)?/i,
		lookbehind: true
	},
	'operator': [	
		/[<>+\-*/]=?|[%=]/,
		// RU
		{
			pattern: /(^|[^\w\u0400-\u0484\u0487-\u052f\u1c80-\u1c88\u1d2b\u1d78\u2de0-\u2dff\ua640-\ua69f\ufe2e\ufe2f])(?:и|или|не)(?![\w\u0400-\u0484\u0487-\u052f\u1c80-\u1c88\u1d2b\u1d78\u2de0-\u2dff\ua640-\ua69f\ufe2e\ufe2f])/i,
			lookbehind: true
		},		
		// EN
		{
			pattern: /\b(?:and|or|not)\b/i
		}
		
	],
	'punctuation': /\(\.|\.\)|[()\[\]:;,.]/,	
	'directive': [
		// Теги препроцессора вида &Клиент, &Сервер, ...
		// Preprocessor tags of the type &Client, &Server, ...
		{
			pattern: /^(\s*)&.*/m,
			lookbehind: true,
			alias: 'important'
		},
		// Инструкции препроцессора вида:
		// #Если Сервер Тогда 
		// ... 
		// #КонецЕсли
		// Preprocessor instructions of the form:
		// #If Server Then 
		// ... 
		// #EndIf
		{
			pattern: /^\s*#.*/gm,
			alias: 'important'
		}	
	]
};

Prism.languages.oscript = Prism.languages['bsl'];
