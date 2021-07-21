/* @noflow */
/* eslint-disable flowtype/require-return-type */
const report = require('../dist');

async function askQuestions() {
  let answer = await report.question('What do you want?');
  report.info(`Sorry, I don't have ${answer}`);

  answer = await report.question(`What's your password?`, {
    password: true,
    required: true,
  });

  answer = await report.question('What do you want?', {required: true});
  report.info(`Sorry, I don't have ${answer}`);

  report.info(`Thanks, I won't tell anyone`);
}

askQuestions();
