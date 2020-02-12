import * as api from "./api"
import { API_ROOT } from "./settings"
import axios from "axios"

interface World {
  api: api.Api
}

const httpClient = axios.create({
  baseURL: API_ROOT,
  withCredentials: true,
})

/** Convert JSON to FormData
 *
 * Our Django app only accepts multi-part and url encoded form data. JSON is not
 * supported.
 */
function jsonToFormData(data: object) {
  const form = new FormData()
  Object.entries(data).forEach(([k, v]) => {
    // tslint:disable-next-line no-unsafe-any
    form.set(k, v)
  })
  return form
}

export const Current: World = {
  api: {
    loginUser: async (args: api.ILoginUserArgs) => {
      try {
        const res = await httpClient.post<api.ILoginUserResponse>(
          "/v1/oauth_complete",
          jsonToFormData(args),
        )
        return res.data
      } catch (e) {
        // pass
      }
      return {
        ok: false,
        error: "Server Error",
        error_description: "problem contacting backend services.",
      }
    },
    logoutUser: async () => {
      try {
        await httpClient.post("/v1/logout")
        return { ok: true }
      } catch (e) {
        // pass
      }
      return { ok: false }
    },
    getUsageBilling: async (args: api.IUsageBillingPageArgs) => {
      return (
        await httpClient.get<api.IUsageBillingPageApiResponse>(
          `/v1/t/${args.teamId}/usage_billing`,
        )
      ).data
    },
    getActivity: async (args: api.IActivityArgs) => {
      return (
        await httpClient.get<api.IActivityApiResponse>(
          `/v1/t/${args.teamId}/activity`,
        )
      ).data
    },
    getAccounts: async () => {
      return (await httpClient.get<api.IAccountsApiResponse>("/v1/accounts"))
        .data
    },
    getCurrentAccount: async () => {
      return (
        await httpClient.get<api.ICurrentAccountApiResponse>(
          "/v1/current_account",
        )
      ).data
    },
  },
}
