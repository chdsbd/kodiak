export interface ILoginUserArgs {
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
  readonly activeUserCount: number
  readonly perUserUSD: number
  readonly perMonthUSD: number
  readonly nextBillingDate: string
  readonly billingPeriod: {
    readonly start: string
    readonly end: string
  }
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
interface IChart {
  readonly labels: Array<string>
  readonly datasets: {
    readonly approved: Array<number>
    readonly merged: Array<number>
    readonly updated: Array<number>
  }
}
export interface IActivityApiResponse {
  readonly pullRequestActivity: IChart
  readonly kodiakActivity: IChart
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
}
