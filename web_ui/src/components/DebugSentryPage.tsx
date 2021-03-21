function throwError() {
  throw Error("Test exception for Sentry")
}
export function DebugSentryPage() {
  throwError()
  return null
}
