// Auth0 Post Login Action. Configure MAAHER_CLIENT_ID as an Action secret.
// Requires Guardian WebAuthn roaming user_verification=required and supervised
// key enrollment before approving/binding the staff identity. No auto-enrollment.
exports.onExecutePostLogin = async (event, api) => {
  const client = event.secrets?.MAAHER_CLIENT_ID;
  if (!client) {
    api.access.deny('Staff login policy is not configured');
    return;
  }
  if (event.client?.client_id !== client) return;
  if (event.user?.app_metadata?.maaher_staff_approved !== true
      || !event.user?.enrolledFactors?.some(factor => factor.type === 'webauthn-roaming')) {
    api.access.deny('Verified staff enrollment is required');
    return;
  }
  // Auth0 does not issue the ID token unless this challenge is fulfilled.
  // There are deliberately no optional/fallback factors. See official
  // @auth0/actions post-login/v3 AuthenticationAPI.challengeWith contract.
  api.authentication.challengeWith({ type: 'webauthn-roaming' });
  api.idToken.setCustomClaim('https://maaherlms.aimz.my.id/assurance', 'maaher-fido2-uv-v1');
};
