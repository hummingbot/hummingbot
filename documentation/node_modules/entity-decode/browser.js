/**
 * @see https://github.com/vuejs/vue/commit/a855dd0564a657a73b7249469490d39817f27cf7#diff-c0a2623ea5896a83e3b630f236b47b52
 * @see https://stackoverflow.com/a/13091266/4936667
 */

var decoder;

export default function decode(html) {
    decoder = decoder || document.createElement('div');
    // Escape HTML before decoding for HTML Entities
    html = escape(html).replace(/%26/g,'&').replace(/%23/g,'#').replace(/%3B/g,';');
    // decoding
    decoder.innerHTML = html;

    return unescape(decoder.textContent);
}
