import React from "react"
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
      .catch(e => {
        setState({ status: "failure" })
      })
  }, [func])

  return state
}
