export type ILoginUserArgs = {
  code: string
  serverState: string
  clientState: string
}
interface ILoginUserResponseError {
  readonly ok: false
  readonly error: string
  readonly error_description: string
}
interface ILoginUserResponseSuccess {
  readonly ok: true
}
export type ILoginUserResponse =
  | ILoginUserResponseSuccess
  | ILoginUserResponseError

interface ILogoutResponseSuccess {
  ok: true
}
interface ILogoutResponseError {
  ok: false
}
export type ILogoutResponse = ILogoutResponseSuccess | ILogoutResponseError

export type ISyncAccountsResponse =
  | {
      ok: true
    }
  | { ok: false }

export interface IUsageBillingPageArgs {
  readonly teamId: string
}
export interface IUsageBillingPageApiResponse {
  readonly accountCanSubscribe: boolean
  readonly subscription: {
    readonly seats: number
    readonly nextBillingDate: string
    readonly expired: boolean
    readonly cost: {
      readonly totalCents: number
      readonly perSeatCents: number
      readonly currency: string
      readonly planInterval: "month" | "year"
    }
    readonly billingEmail: string
    readonly customerName?: string
    readonly customerAddress?: {
      readonly line1?: string
      readonly city?: string
      readonly country?: string
      readonly line2?: string
      readonly postalCode?: string
      readonly state?: string
    }
    readonly cardInfo: string
    readonly viewerIsOrgOwner: boolean
    readonly viewerCanModify: boolean
    readonly limitBillingAccessToOwners: boolean
  } | null
  readonly trial: {
    readonly startDate: string
    readonly endDate: string
    readonly expired: boolean
    readonly startedBy: {
      readonly id: string
      readonly name: string
      readonly profileImgUrl: string
    }
  } | null
  readonly activeUsers: ReadonlyArray<{
    readonly id: string
    readonly name: string
    readonly profileImgUrl: string
    readonly interactions: number
    readonly lastActiveDate: string
    readonly firstActiveDate?: string
    readonly hasSeatLicense?: boolean
  }>
  readonly subscriptionExemption: {
    readonly message: string | null
  } | null
}

export interface IActivityArgs {
  readonly teamId: string
}
export interface ICurrentAccountArgs {
  readonly teamId: string
}

interface IKodiakChart {
  readonly labels: Array<string>
  readonly datasets: {
    readonly approved: Array<number>
    readonly merged: Array<number>
    readonly updated: Array<number>
  }
}
interface ITotalChart {
  readonly labels: Array<string>
  readonly datasets: {
    readonly opened: Array<number>
    readonly merged: Array<number>
    readonly closed: Array<number>
  }
}

export interface IActiveMergeQueue {
  readonly owner: string
  readonly repo: string
  readonly queues: {
    readonly branch: string
    readonly pull_requests: {
      readonly number: string
      readonly added_at_timestamp: number
    }[]
  }[]
}

export interface IActivityApiResponse {
  readonly kodiakActivity: IKodiakChart
  readonly pullRequestActivity: ITotalChart
  readonly activeMergeQueues: IActiveMergeQueue[]
}

export interface IAccountsApiResponse
  extends ReadonlyArray<{
    readonly id: string
    readonly name: string
    readonly profileImgUrl: string
  }> {}

export interface ICurrentAccountApiResponse {
  readonly org: {
    readonly id: string
    readonly name: string
    readonly profileImgUrl: string
  }
  readonly user: {
    readonly id: string
    readonly name: string
    readonly profileImgUrl: string
  }
  readonly accounts: ReadonlyArray<{
    readonly id: string
    readonly name: string
    readonly profileImgUrl: string
  }>
}

export interface IStartTrialArgs {
  readonly teamId: string
  readonly billingEmail: string
}
export type IUpdateSubscriptionArgs = {
  readonly teamId: string
  readonly seats: number
  readonly prorationTimestamp: number
  readonly planPeriod: "month" | "year"
}
export interface ICancelSubscriptionArgs {
  readonly teamId: string
}
export interface IFetchSubscriptionInfoArgs {
  readonly teamId: string
}

export interface IStartCheckoutArgs {
  readonly teamId: string
  readonly seatCount: number
  readonly planPeriod: "month" | "year"
}
export interface IStartCheckoutResponse {
  readonly stripeCheckoutSessionId: string
  readonly stripePublishableApiKey: string
}
export interface IModifyBillingArgs {
  readonly teamId: string
}
export interface ModifyBillingResponse {
  readonly stripeCheckoutSessionId: string
  readonly stripePublishableApiKey: string
}

export interface IFetchProrationArgs {
  readonly teamId: string
  readonly subscriptionQuantity: number
  readonly subscriptionPeriod: "month" | "year"
}
export interface IFetchProrationResponse {
  readonly proratedCost: number
  readonly prorationTime: number
}

export type GetSubscriptionInfoArgs = {
  readonly teamId: string
}

export type SubscriptionInfoResponse =
  | {
      // personal user, subscription valid, or trial account
      readonly type: "VALID_SUBSCRIPTION"
    }
  | { readonly type: "TRIAL_EXPIRED" }
  | { readonly type: "SUBSCRIPTION_EXPIRED" }
  | {
      readonly type: "SUBSCRIPTION_OVERAGE"
      readonly activeUserCount: number

      readonly licenseCount: number
    }

export type UpdateStripeCustomerInfoArgs = {
  readonly teamId: string
  readonly email?: string
  readonly name?: string
  readonly address?: {
    readonly line1?: string
    readonly city?: string
    readonly country?: string
    readonly line2?: string
    readonly postalCode?: string
    readonly state?: string
  }
  readonly limitBillingAccessToOwners?: boolean
  readonly contactEmails?: string
}

export interface Api {
  loginUser: (args: ILoginUserArgs) => Promise<ILoginUserResponse>
  logoutUser: () => Promise<ILogoutResponse>
  syncAccounts: () => Promise<ISyncAccountsResponse>
  getUsageBilling: (
    args: IUsageBillingPageArgs,
  ) => Promise<IUsageBillingPageApiResponse>
  getActivity: (args: IActivityArgs) => Promise<IActivityApiResponse>
  getAccounts: () => Promise<IAccountsApiResponse>
  getCurrentAccount: (
    args: ICurrentAccountArgs,
  ) => Promise<ICurrentAccountApiResponse>
  startTrial: (args: IStartTrialArgs) => Promise<unknown>
  updateSubscription: (args: IUpdateSubscriptionArgs) => Promise<unknown>
  cancelSubscription: (args: ICancelSubscriptionArgs) => Promise<unknown>
  fetchProration: (
    args: IFetchProrationArgs,
  ) => Promise<IFetchProrationResponse>
  startCheckout: (args: IStartCheckoutArgs) => Promise<IStartCheckoutResponse>
  modifyBilling: (args: IModifyBillingArgs) => Promise<ModifyBillingResponse>
  getSubscriptionInfo: (
    args: GetSubscriptionInfoArgs,
  ) => Promise<SubscriptionInfoResponse>
  updateStripeCustomerInfo: (
    args: UpdateStripeCustomerInfoArgs,
  ) => Promise<unknown>
}
