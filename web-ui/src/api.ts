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
  readonly seats: {
    readonly current: number
    readonly total: number
  }
  readonly perUserUSD: number
  readonly perMonthUSD: number
  readonly nextBillingDate: string
  readonly billingPeriod: {
    readonly start: string
    readonly end: string
  }
  readonly activeUsers: ReadonlyArray<{
    readonly name: string
    readonly profileImgUrl: string
    readonly interactions: number
    readonly lastActiveDate: string
  }>
  readonly repos: ReadonlyArray<{
    readonly name: string
    readonly id: number
  }>
}

interface ISettingsApiResponse {
  readonly notifyOnExceedBilledSeats: boolean
}
type ISettingsUpdate = ISettingsApiResponse

interface IActivityApiResponse {
  readonly labels: Array<string>
  readonly datasets: {
    readonly approved: Array<number>
    readonly merged: Array<number>
    readonly updated: Array<number>
  }
}

interface IAccountsApiResponse
  extends ReadonlyArray<{
    readonly name: string
    readonly profileImgUrl: string
  }> {}

interface ICurrentAccountApiResponse {
  readonly org: {
    readonly name: string
    readonly profileImgUrl: string
  }
  readonly user: {
    readonly name: string
    readonly profileImgUrl: string
  }
  readonly accounts: ReadonlyArray<{
    readonly name: string
    readonly profileImgUrl: string
  }>
}

interface ILoginUserArgs {
  code: string
  serverState: string
  clientState: string
}

export interface Api {
  loginUser: (args: ILoginUserArgs) => Promise<ILoginUserResponse>
  getUsageBilling: () => Promise<IUsageBillingPageApiResponse>
  getSettings: () => Promise<ISettingsApiResponse>
  updateSettings: (_: ISettingsUpdate) => Promise<ISettingsApiResponse>
  getActivity: () => Promise<IActivityApiResponse>
  getAccounts: () => Promise<IAccountsApiResponse>
  getCurrentAccount: () => Promise<ICurrentAccountApiResponse>
}
