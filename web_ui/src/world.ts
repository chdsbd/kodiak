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
function jsonToFormData(data: { readonly [_: string]: string | number }) {
  const form = new FormData()
  Object.entries(data).forEach(([k, v]) => {
    form.set(k, String(v))
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
    startTrial: async (args: api.IStartTrialArgs) =>
      (
        await authRoute.post<unknown>(
          `/v1/t/${args.teamId}/start_trial`,
          jsonToFormData({ billingEmail: args.billingEmail }),
        )
      ).data,
    updateSubscription: async (args: api.IUpdateSubscriptionArgs) =>
      (
        await authRoute.post<unknown>(
          `/v1/t/${args.teamId}/update_subscription`,
          jsonToFormData(args),
        )
      ).data,
    cancelSubscription: async (args: api.ICancelSubscriptionArgs) =>
      await authRoute.post<unknown>(`/v1/t/${args.teamId}/cancel_subscription`),
    startCheckout: async (args: api.IStartCheckoutArgs) =>
      (
        await authRoute.post<api.IStartCheckoutResponse>(
          `/v1/t/${args.teamId}/start_checkout`,
          jsonToFormData({ seatCount: args.seatCount }),
        )
      ).data,
    modifyBilling: async (args: api.IModifyBillingArgs) =>
      (
        await authRoute.post<api.ModifyBillingResponse>(
          `/v1/t/${args.teamId}/modify_payment_details`,
        )
      ).data,
    fetchProration: async (args: api.IFetchProrationArgs) =>
      (
        await authRoute.post<api.IFetchProrationResponse>(
          `/v1/t/${args.teamId}/fetch_proration`,
          jsonToFormData({
            subscriptionQuantity: args.subscriptionQuantity,
          }),
        )
      ).data,
  },
}
