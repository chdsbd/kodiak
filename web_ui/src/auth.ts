import { loginUrl } from "./settings"
import uuid from "uuid/v4"

export function startLogin() {
  const url = new URL(loginUrl)
  const queryParams = new URLSearchParams(location.search)
  const redirectUri = queryParams.get("redirect")
  const state = JSON.stringify({ nonce: uuid(), redirect: redirectUri })
  url.searchParams.set("state", state)
  localStorage.setItem("oauth_state", state)
  // eslint-disable-next-line no-restricted-globals
  location.href = String(url)
}

export function getOauthState() {
  return localStorage.getItem("oauth_state") || ""
}
