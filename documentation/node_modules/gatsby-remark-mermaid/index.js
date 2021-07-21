const path = require('path');
const visit = require('unist-util-visit');
const puppeteer = require('puppeteer');

async function render(browser, definition, theme, viewport, mermaidOptions) {
    const page = await browser.newPage();
    page.setViewport(viewport);
    await page.goto(`file://${path.join(__dirname, 'render.html')}`);
    await page.addScriptTag({
        path:  require.resolve('mermaid/dist/mermaid.min.js')
    });
    return await page.$eval('#container', (container, definition, theme, mermaidOptions) => {
        container.innerHTML = `<div class="mermaid">${definition}</div>`;

        try {
            window.mermaid.initialize({
                ...mermaidOptions,
                theme
            });
            window.mermaid.init();
            return container.innerHTML;
        } catch (e) {
            return `${e}`
        }
    }, definition, theme, mermaidOptions);
}

function mermaidNodes(markdownAST, language) {
    const result = [];
    visit(markdownAST, 'code', node => {
        if ((node.lang || '').toLowerCase() === language) {
            result.push(node);
        }
    });
    return result;
}

module.exports = async ({markdownAST},
                        {
                            language = 'mermaid',
                            theme = 'default',
                            viewport = {height: 200, width: 200},
                            mermaidOptions = {}
                        }) => {

    // Check if there is a match before launching anything
    let nodes = mermaidNodes(markdownAST, language);
    if (nodes.length === 0) {
        // No nodes to process
        return;
    }

    // Launch virtual browser
    const browser = await puppeteer.launch({args: ['--no-sandbox', '--disable-setuid-sandbox']});

    await Promise.all(nodes.map(async node => {
        node.type = 'html';
        node.value = await render(browser, node.value, theme, viewport, mermaidOptions);
    }));
    browser.close();
};
