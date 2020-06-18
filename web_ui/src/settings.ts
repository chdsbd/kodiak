export const SENTRY_DSN =
  "https://0012ad6693d042d1b57ac5f00918b3bd@o64108.ingest.sentry.io/3352104"
export const installUrl = "https://github.com/marketplace/kodiakhq"
export const docsUrl = "https://kodiakhq.com/docs/quickstart"
export const helpUrl = "https://kodiakhq.com/help"
export const billingDocsUrl = "https://kodiakhq.com/docs/billing"
export const loginPath = "/v1/oauth_login"
export const monthlyCost = 499

export const getStripeSelfServeUrl = (teamId: string) =>
  `/v1/t/${teamId}/stripe_self_serve_redirect`
