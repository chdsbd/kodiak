interface ILoginUserResponseError {
  readonly ok: false
  readonly error: string
  readonly error_description: string
}
interface ILoginUserResponseSucess {
  readonly ok: true
}
type ILoginUserResponse = ILoginUserResponseSucess | ILoginUserResponseError

interface IUsageBillingPageApiResponse {
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

interface ISettingsApiResponse {
  readonly notifyOnExceedBilledSeats: boolean
}
type ISettingsUpdate = ISettingsApiResponse

interface IChart {
  readonly labels: Array<string>
  readonly datasets: {
    readonly approved: Array<number>
    readonly merged: Array<number>
    readonly updated: Array<number>
  }
}
interface IActivityApiResponse {
  readonly pullRequestActivity: IChart
  readonly kodiakActivity: IChart
}

interface IAccountsApiResponse
  extends ReadonlyArray<{
    readonly id: number
    readonly name: string
    readonly profileImgUrl: string
  }> {}

interface ICurrentAccountApiResponse {
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

interface ILoginUserArgs {
  code: string
  serverState: string
  clientState: string
}

interface IGetUsageBillingArgs {
  teamId: number
}

export interface Api {
  loginUser: (args: ILoginUserArgs) => Promise<ILoginUserResponse>
  getUsageBilling: (args: IGetUsageBillingArgs) => Promise<IUsageBillingPageApiResponse>
  getSettings: () => Promise<ISettingsApiResponse>
  updateSettings: (_: ISettingsUpdate) => Promise<ISettingsApiResponse>
  getActivity: () => Promise<IActivityApiResponse>
  getAccounts: () => Promise<IAccountsApiResponse>
  getCurrentAccount: () => Promise<ICurrentAccountApiResponse>
}
