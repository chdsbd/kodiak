import React from "react"
import { useParams } from "react-router-dom"
import { WebData } from "./webdata"

export function useApi<T>(func: () => Promise<T>): WebData<T> {
  const [state, setState] = React.useState<WebData<T>>({
    status: "loading",
  })

  React.useEffect(() => {
    func()
      .then(res => {
        setState({ status: "success", data: res })
      })
      .catch(() => {
        setState({ status: "failure" })
      })
  }, [func])

  return state
}



interface ITeamArgs {
  readonly teamId: number
}
export function useTeamApi<T>(func: (args: ITeamArgs) => Promise<T>): WebData<T> {
  const params = useParams()
  const [state, setState] = React.useState<WebData<T>>({
    status: "loading",
  })
    const teamId = params.team_id

  React.useEffect(() => {
    func({teamId})
      .then(res => {
        setState({ status: "success", data: res })
      })
      .catch(() => {
        setState({ status: "failure" })
      })
  }, [func])

  return state
}
