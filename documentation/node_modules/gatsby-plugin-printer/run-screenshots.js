const fs = require("fs-extra");
const path = require("path");
const puppeteer = require("puppeteer");
const debug = require("debug")("gatsby-plugin-printer:run-screenshots");

function waitForNetworkIdle(page, timeout, maxInflightRequests = 0) {
  page.on("request", onRequestStarted);
  page.on("requestfinished", onRequestFinished);
  page.on("requestfailed", onRequestFinished);

  let inflight = 0;
  let fulfill;
  let promise = new Promise(x => (fulfill = x));
  let timeoutId = setTimeout(onTimeoutDone, timeout);
  return promise;

  function onTimeoutDone() {
    page.removeListener("request", onRequestStarted);
    page.removeListener("requestfinished", onRequestFinished);
    page.removeListener("requestfailed", onRequestFinished);
    fulfill();
  }

  function onRequestStarted() {
    ++inflight;
    if (inflight > maxInflightRequests) clearTimeout(timeoutId);
  }

  function onRequestFinished() {
    if (inflight === 0) return;
    --inflight;
    if (inflight === maxInflightRequests)
      timeoutId = setTimeout(onTimeoutDone, timeout);
  }
}
const runScreenshots = async ({ data, code }, puppeteerLaunchOptions = {}) => {
  const browser = await puppeteer.launch(puppeteerLaunchOptions);
  const page = await browser.newPage();
  const html = `
  <html>
  <head>
  <script>${code}</script>
  </head>
  <body>
  </body>
  </html>
`;

  async function screenshotDOMElement({
    path: filePath,
    selector,
    outputDir
  } = {}) {
    if (!filePath) {
      throw new Error(
        `[gatsby-plugin-printer]: screenshotDOMElement requires a filepath to write file to`
      );
    }
    if (!selector) {
      throw Error("[gatsby-plugin-printer]: Please provide a selector.");
    }

    const rect = await page.evaluate(selector => {
      const element = document.querySelector(selector);
      if (!element) return null;
      const { x, y, width, height } = element.getBoundingClientRect();
      return { left: x, top: y, width, height, id: element.id };
    }, selector);

    if (!rect) {
      throw Error(`Could not find element that matches selector: ${selector}.`);
    }

    await fs.mkdirp(path.join("./public/", outputDir));

    return await page.screenshot({
      path: path.join("./public/", outputDir, filePath),
      clip: {
        x: rect.left,
        y: rect.top,
        width: rect.width,
        height: rect.height
      }
    });
  }

  await page.setContent(html);
  await page.evaluate(
    ({ data }) => {
      let dom = document.querySelector("body");
      dom.innerHTML =
        `<div data-id="empty"></div>` +
        data.map(({ id }) => `<div data-id="${id}"></div>`).join("\n");
    },
    { data }
  );

  await page.evaluate(
    ({ node }) => {
      const $element = document.querySelector(`[data-id="empty"]`);
      window.ogRender($element, node.data);
    },
    { node: data[0] }
  );

  await page.evaluateHandle("document.fonts.ready");

  await Promise.all(
    data.map(node => {
      return page.evaluate(
        ({ node }) => {
          const $element = document.querySelector(`[data-id="${node.id}"]`);
          window.ogRender($element, node.data);
        },
        { node }
      );
    })
  );

  // one day we might be able to use page.waitFor
  await waitForNetworkIdle(page, 500);

  const titlePromises = data.map(({ id, fileName, outputDir }) =>
    screenshotDOMElement({
      path: `${fileName}.png`,
      selector: `[data-id="${id}"] > *`,
      outputDir
    })
  );
  const results = await Promise.all(titlePromises);
  await browser.close();
};

module.exports = runScreenshots;
