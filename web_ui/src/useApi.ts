import React, { useCallback } from "react"
import { useParams } from "react-router-dom"
import { WebData } from "./webdata"

export function useApi<T>(
  func: () => Promise<T>,
): [WebData<T>, { refetch: () => Promise<unknown> }] {
  const [state, setState] = React.useState<WebData<T>>({
    status: "loading",
  })

  const fetch = useCallback(() => {
    return func()
      .then(res => {
        setState({ status: "success", data: res })
      })
      .catch(() => {
        setState({ status: "failure" })
      })
  }, [func])

  React.useEffect(() => {
    fetch()
  }, [fetch, func])

  return [state, { refetch: fetch }]
}

interface ITeamArgs {
  readonly teamId: string
}
export function useTeamApi<T>(
  func: (args: ITeamArgs) => Promise<T>,
): WebData<T> {
  const params = useParams<{ team_id: string }>()
  const [state, setState] = React.useState<WebData<T>>({
    status: "loading",
  })
  const teamId = params.team_id

  React.useEffect(() => {
    func({ teamId })
      .then(res => {
        setState({ status: "success", data: res })
      })
      .catch(() => {
        setState({ status: "failure" })
      })
  }, [func, teamId])

  return state
}

export function useTeamApiMutation<
  T,
  V extends {
    readonly teamId: string
  }
>(
  func: (args: V) => Promise<T>,
): [WebData<T>, (args: Omit<V, "teamId">) => void] {
  const [state, setState] = React.useState<WebData<T>>({
    status: "loading",
  })

  function callApi(args: Omit<V, "teamId">) {
    teamApi(func, args).then(res => {
      if (res.ok) {
        setState({ status: "success", data: res.data })
      } else {
        setState({ status: "failure" })
      }
    })
  }

  return [state, callApi]
}

export function teamApi<T, V extends ITeamArgs>(
  func: (args: V) => Promise<T>,
  // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
  args: Omit<V, "teamId"> = {} as Omit<V, "teamId">,
): Promise<{ ok: true; data: T } | { ok: false }> {
  const teamId: string = location.pathname.split("/")[2]
  // We know better than TS. This is a safe assertion.
  // https://github.com/microsoft/TypeScript/issues/35858
  // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
  return func({ ...args, teamId } as V)
    .then(res => ({ ok: true, data: res }))
    .catch(() => ({ ok: false }))
}
