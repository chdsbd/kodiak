/* Get the API root for the current environment.

This is kind of hacky but it avoids us rebuilding the app between environments.
A more robust solution would be to create an http server that injects the API
root into index.html from an environment variable.
*/
function getApiRoot(): string {
  const environmentApiRoot = process.env.REACT_APP_KODIAK_API_ROOT
  if (environmentApiRoot) {
    return environmentApiRoot
  }
  if (location.hostname === "app.staging.kodiakhq.com") {
    return "https://api.staging.kodiakhq.com"
  }
  return "https://api.kodiakhq.com"
}
export const API_ROOT = getApiRoot() || "https://api.kodiakhq.com"
export const installUrl = "https://github.com/marketplace/kodiakhq"
export const docsUrl = "https://kodiakhq.com/docs/quickstart"
export const helpUrl = "https://kodiakhq.com/help"
export const loginUrl = `${API_ROOT}/v1/oauth_login`
export const monthlyCost = 499

export const getStripeSelfServeUrl = (teamId: string) =>
  `${API_ROOT}/v1/t/${teamId}/stripe_self_serve_redirect`

// tslint:disable-next-line no-console
console.info(`API_ROOT=${API_ROOT}`)
