import * as api from "./api"
import { API_ROOT } from "./settings"
import axios from "axios"

interface World {
  api: api.Api
}

const openRoute = axios.create({
  baseURL: API_ROOT,
  withCredentials: true,
})

const authRoute = axios.create({
  baseURL: API_ROOT,
  withCredentials: true,
})

authRoute.interceptors.response.use(
  res => res,
  err => {
    // tslint:disable-next-line no-unsafe-any
    if (err?.response?.status === 401) {
      const redirectPath = location.pathname
      location.href = `/login?redirect=${redirectPath}`
    }
    return Promise.reject(err)
  },
)

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
        const res = await openRoute.post<api.ILoginUserResponse>(
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
        await openRoute.post("/v1/logout")
        return { ok: true }
      } catch (e) {
        // pass
      }
      return { ok: false }
    },
    syncAccounts: async () => {
      try {
        const res = await authRoute.post<api.ISyncAccountsResponse>(
          "/v1/sync_accounts",
        )
        return res.data
      } catch (e) {
        // pass
      }
      return {
        ok: false,
      }
    },
    getUsageBilling: async (args: api.IUsageBillingPageArgs) => {
      return (
        await authRoute.get<api.IUsageBillingPageApiResponse>(
          `/v1/t/${args.teamId}/usage_billing`,
        )
      ).data
    },
    getActivity: async (args: api.IActivityArgs) => {
      return (
        await authRoute.get<api.IActivityApiResponse>(
          `/v1/t/${args.teamId}/activity`,
        )
      ).data
    },
    getAccounts: async () => {
      return (await authRoute.get<api.IAccountsApiResponse>("/v1/accounts"))
        .data
    },
    getCurrentAccount: async (args: api.ICurrentAccountArgs) => {
      return (
        await authRoute.get<api.ICurrentAccountApiResponse>(
          `/v1/t/${args.teamId}/current_account`,
        )
      ).data
    },
  },
}
