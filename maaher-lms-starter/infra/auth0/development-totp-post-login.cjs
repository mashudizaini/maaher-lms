// DEVELOPMENT ONLY: synthetic accounts, dedicated Development application.
// Configure MAAHER_DEV_CLIENT_ID as an Action secret (the public Client ID).
// Owner pre-approves this test subject in app_metadata, then personally enrolls
// their phone before creating any LMS identity binding. No production trust.
exports.onExecutePostLogin = async (event, api) => {
  const client = event.secrets?.MAAHER_DEV_CLIENT_ID;
  if (!client) {
    api.access.deny('Development login policy is not configured');
    return;
  }
  if (event.client?.client_id !== client) return;
  if (event.user?.app_metadata?.maaher_dev_totp_approved !== true) {
    api.access.deny('Owner approval for synthetic development is required');
    return;
  }
  if (event.user.enrolledFactors?.some(factor => factor.type === 'otp')) {
    api.authentication.challengeWith({ type: 'otp' });
  } else {
    // Auth0 completes enrollment before issuing the token / continuing Actions.
    // The API still requires fresh auth_time + amr=mfa and an offline binding.
    api.authentication.enrollWith({ type: 'otp' });
  }
  api.idToken.setCustomClaim('https://maaherlms.aimz.my.id/assurance', 'maaher-dev-totp-v1');
};
