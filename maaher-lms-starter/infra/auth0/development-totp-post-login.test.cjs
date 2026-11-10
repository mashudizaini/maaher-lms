const { test } = require('node:test');
const assert = require('node:assert/strict');
const { onExecutePostLogin } = require('./development-totp-post-login.cjs');

function input() {
  const calls = [];
  return {
    event: { secrets: { MAAHER_DEV_CLIENT_ID: 'development-client' }, client: { client_id: 'development-client' },
      user: { app_metadata: { maaher_dev_totp_approved: true }, enrolledFactors: [] } },
    api: { access: { deny: reason => calls.push(['deny', reason]) },
      authentication: { challengeWith: factor => calls.push(['challenge', factor]),
        enrollWith: factor => calls.push(['enroll', factor]) },
      idToken: { setCustomClaim: (key, value) => calls.push(['claim', key, value]) } }, calls,
  };
}

test('approved synthetic user enrolls OTP without a pre-existing factor dead end', async () => {
  const { event, api, calls } = input(); await onExecutePostLogin(event, api);
  assert.deepEqual(calls, [['enroll', { type: 'otp' }],
    ['claim', 'https://maaherlms.aimz.my.id/assurance', 'maaher-dev-totp-v1']]);
});
test('subsequent login requires the exact OTP challenge, without fallback', async () => {
  const { event, api, calls } = input(); event.user.enrolledFactors = [{ type: 'otp' }, { type: 'email' }];
  await onExecutePostLogin(event, api);
  assert.deepEqual(calls, [['challenge', { type: 'otp' }],
    ['claim', 'https://maaherlms.aimz.my.id/assurance', 'maaher-dev-totp-v1']]);
});
test('no approval or another approval type cannot enroll or issue a claim', async () => {
  for (const metadata of [{}, { maaher_dev_totp_approved: 'true' }, { maaher_staff_approved: true }]) {
    const { event, api, calls } = input(); event.user.app_metadata = metadata;
    await onExecutePostLogin(event, api); assert.equal(calls.length, 1); assert.equal(calls[0][0], 'deny');
  }
});
test('request data and user_metadata cannot approve an account', async () => {
  const { event, api, calls } = input(); event.user.app_metadata = {};
  event.user.user_metadata = { maaher_dev_totp_approved: true };
  event.request = { query: { maaher_dev_totp_approved: true, assurance: 'maaher-fido2-uv-v1' } };
  await onExecutePostLogin(event, api); assert.equal(calls.length, 1); assert.equal(calls[0][0], 'deny');
});
test('other applications never receive this policy', async () => {
  const { event, api, calls } = input(); event.client.client_id = 'production-client';
  await onExecutePostLogin(event, api); assert.deepEqual(calls, []);
});
test('missing Action configuration fails closed', async () => {
  const { event, api, calls } = input(); event.secrets = {};
  await onExecutePostLogin(event, api); assert.equal(calls.length, 1); assert.equal(calls[0][0], 'deny');
});
test('failure to request enrollment or challenge never reaches claim issuance', async () => {
  for (const enrolled of [false, true]) {
    const { event, api, calls } = input(); event.user.enrolledFactors = enrolled ? [{ type: 'otp' }] : [];
    api.authentication[enrolled ? 'challengeWith' : 'enrollWith'] = () => { throw Error('synthetic denial'); };
    await assert.rejects(onExecutePostLogin(event, api)); assert.deepEqual(calls, []);
  }
});
test('non-OTP factors do not satisfy the development policy', async () => {
  const { event, api, calls } = input(); event.user.enrolledFactors = [{ type: 'email' }, { type: 'webauthn-roaming' }];
  await onExecutePostLogin(event, api); assert.equal(calls[0][0], 'enroll');
  assert.equal(calls.at(-1)[2], 'maaher-dev-totp-v1');
});
