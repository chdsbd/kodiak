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

export function useTeamId(): string | null {
  const params = useParams<{ team_id: string }>()
  return params.team_id
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

export function teamApi<T, V extends ITeamArgs>(
  func: (args: V) => Promise<T>,
  args: Omit<V, "teamId"> = {} as Omit<V, "teamId">,
): Promise<{ ok: true; data: T } | { ok: false }> {
  const teamId: string = location.pathname.split("/")[2]
  return func({ ...args, teamId } as V)
    .then(res => ({ ok: true, data: res }))
    .catch(() => ({ ok: false }))
}
