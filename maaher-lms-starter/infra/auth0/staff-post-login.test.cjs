const { test } = require('node:test');
const assert = require('node:assert/strict');
const { onExecutePostLogin } = require('./staff-post-login.cjs');

function input() {
  const calls = [];
  return {
    event: { secrets: { MAAHER_CLIENT_ID: 'staff-client' }, client: { client_id: 'staff-client' },
      user: { app_metadata: { maaher_staff_approved: true }, enrolledFactors: [{ type: 'webauthn-roaming' }] } },
    api: { access: { deny: reason => calls.push(['deny', reason]) },
      authentication: { challengeWith: factor => calls.push(['challenge', factor]) },
      idToken: { setCustomClaim: (key, value) => calls.push(['claim', key, value]) } }, calls,
  };
}

test('approved staff must complete the exact security-key challenge; no fallback is supplied', async () => {
  const { event, api, calls } = input(); await onExecutePostLogin(event, api);
  assert.deepEqual(calls, [['challenge', { type: 'webauthn-roaming' }],
    ['claim', 'https://maaherlms.aimz.my.id/assurance', 'maaher-fido2-uv-v1']]);
});
test('unapproved subject is denied even with an enrolled key', async () => {
  const { event, api, calls } = input(); event.user.app_metadata.maaher_staff_approved = false;
  await onExecutePostLogin(event, api); assert.equal(calls.length, 1); assert.equal(calls[0][0], 'deny');
});
test('a user-editable metadata flag cannot approve staff', async () => {
  const { event, api, calls } = input(); event.user.app_metadata = {};
  event.user.user_metadata = { maaher_staff_approved: true };
  await onExecutePostLogin(event, api); assert.equal(calls[0][0], 'deny');
});
test('email, OTP and platform factors do not replace the roaming key', async () => {
  for (const type of ['email', 'otp', 'webauthn-platform', 'recovery-code']) {
    const { event, api, calls } = input(); event.user.enrolledFactors = [{ type }];
    await onExecutePostLogin(event, api); assert.equal(calls.length, 1); assert.equal(calls[0][0], 'deny');
  }
});
test('another application does not receive the Maaher assurance claim', async () => {
  const { event, api, calls } = input(); event.client.client_id = 'other-client';
  await onExecutePostLogin(event, api); assert.deepEqual(calls, []);
});
test('missing policy configuration fails closed', async () => {
  const { event, api, calls } = input(); event.secrets = {};
  await onExecutePostLogin(event, api); assert.equal(calls[0][0], 'deny');
});
test('a rejected challenge does not reach claim issuance', async () => {
  const { event, api, calls } = input(); api.authentication.challengeWith = () => { throw Error('synthetic denial'); };
  await assert.rejects(onExecutePostLogin(event, api)); assert.deepEqual(calls, []);
});
test('client request data cannot supply the assurance or approval', async () => {
  const { event, api, calls } = input(); event.user.app_metadata = {};
  event.request = { query: { maaher_staff_approved: true, assurance: 'maaher-fido2-uv-v1' } };
  await onExecutePostLogin(event, api); assert.equal(calls[0][0], 'deny');
});
