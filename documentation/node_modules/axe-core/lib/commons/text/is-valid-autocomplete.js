/* global text */
const autocomplete = {
	stateTerms: ['on', 'off'],
	standaloneTerms: [
		'name',
		'honorific-prefix',
		'given-name',
		'additional-name',
		'family-name',
		'honorific-suffix',
		'nickname',
		'username',
		'new-password',
		'current-password',
		'organization-title',
		'organization',
		'street-address',
		'address-line1',
		'address-line2',
		'address-line3',
		'address-level4',
		'address-level3',
		'address-level2',
		'address-level1',
		'country',
		'country-name',
		'postal-code',
		'cc-name',
		'cc-given-name',
		'cc-additional-name',
		'cc-family-name',
		'cc-number',
		'cc-exp',
		'cc-exp-month',
		'cc-exp-year',
		'cc-csc',
		'cc-type',
		'transaction-currency',
		'transaction-amount',
		'language',
		'bday',
		'bday-day',
		'bday-month',
		'bday-year',
		'sex',
		'url',
		'photo'
	],
	qualifiers: ['home', 'work', 'mobile', 'fax', 'pager'],
	qualifiedTerms: [
		'tel',
		'tel-country-code',
		'tel-national',
		'tel-area-code',
		'tel-local',
		'tel-local-prefix',
		'tel-local-suffix',
		'tel-extension',
		'email',
		'impp'
	],
	locations: ['billing', 'shipping']
};
text.autocomplete = autocomplete;

text.isValidAutocomplete = function isValidAutocomplete(
	autocomplete,
	{
		looseTyped = false,
		stateTerms = [],
		locations = [],
		qualifiers = [],
		standaloneTerms = [],
		qualifiedTerms = []
	} = {}
) {
	autocomplete = autocomplete.toLowerCase().trim();
	stateTerms = stateTerms.concat(text.autocomplete.stateTerms);
	if (stateTerms.includes(autocomplete) || autocomplete === '') {
		return true;
	}

	qualifiers = qualifiers.concat(text.autocomplete.qualifiers);
	locations = locations.concat(text.autocomplete.locations);
	standaloneTerms = standaloneTerms.concat(text.autocomplete.standaloneTerms);
	qualifiedTerms = qualifiedTerms.concat(text.autocomplete.qualifiedTerms);

	const autocompleteTerms = autocomplete.split(/\s+/g);
	if (!looseTyped) {
		if (
			autocompleteTerms[0].length > 8 &&
			autocompleteTerms[0].substr(0, 8) === 'section-'
		) {
			autocompleteTerms.shift();
		}

		if (locations.includes(autocompleteTerms[0])) {
			autocompleteTerms.shift();
		}

		if (qualifiers.includes(autocompleteTerms[0])) {
			autocompleteTerms.shift();
			// only quantifiers allowed at this point
			standaloneTerms = [];
		}

		if (autocompleteTerms.length !== 1) {
			return false;
		}
	}

	const purposeTerm = autocompleteTerms[autocompleteTerms.length - 1];
	return (
		standaloneTerms.includes(purposeTerm) ||
		qualifiedTerms.includes(purposeTerm)
	);
};
