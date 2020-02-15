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
