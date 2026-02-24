const ALLOWED_ADMINS = ["gkamradt"];

export function isAllowedAdmin(githubUsername: string | undefined): boolean {
  if (!githubUsername) return false;
  return ALLOWED_ADMINS.includes(githubUsername.toLowerCase());
}
