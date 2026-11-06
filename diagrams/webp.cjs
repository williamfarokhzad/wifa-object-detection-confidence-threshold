const {join} = require('node:path');
const sharp = require('sharp');

(async () => {
  for (const name of ['confidence-cost-sweep','confidence-frozen-holdout']) {
    await sharp(join(__dirname, name + '.svg')).webp({quality: 86, effort: 6})
      .toFile(join(__dirname, name + '.webp'));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
