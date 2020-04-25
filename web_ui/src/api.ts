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
  readonly subscription: {
    readonly seats: number
    readonly nextBillingDate: string
    readonly expired: boolean
    readonly cost: {
      readonly totalCents: number
      readonly perSeatCents: number
    }
    readonly billingEmail: string
    readonly cardInfo: string
  } | null
  readonly trial: {
    readonly startDate: string
    readonly endDate: string
    readonly expired: boolean
    readonly startedBy: {
      readonly id: number
      readonly name: string
      readonly profileImgUrl: string
    }
  } | null
  readonly activeUsers: ReadonlyArray<{
    readonly id: number
    readonly name: string
    readonly profileImgUrl: string
    readonly interactions: number
    readonly lastActiveDate: string
  }>
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
export interface IActivityApiResponse {
  readonly kodiakActivity: IKodiakChart
  readonly pullRequestActivity: ITotalChart
}

export interface IAccountsApiResponse
  extends ReadonlyArray<{
    readonly id: number
    readonly name: string
    readonly profileImgUrl: string
  }> {}

export interface ICurrentAccountApiResponse {
  readonly org: {
    readonly id: number
    readonly name: string
    readonly profileImgUrl: string
  }
  readonly user: {
    readonly id: number
    readonly name: string
    readonly profileImgUrl: string
  }
  readonly accounts: ReadonlyArray<{
    readonly id: number
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
}
export interface IFetchProrationResponse {
  readonly proratedCost: number
  readonly prorationTime: number
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
}
