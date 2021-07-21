const puppeteer = require('./');

(async () => {
  const browser = await puppeteer.launch({ headless: false });

  const page = await browser.newPage();

  await page.emulateMedia('prefers-color-scheme: dark');
  await page.goto('https://paulmillr.com/posts/using-dark-mode-in-css/');
  await page.screenshot({ path: 'dark.png' });
  await page.emulateMedia('prefers-color-scheme: light');
  await page.screenshot({ path: 'light.png' });
  await browser.close();
})();
