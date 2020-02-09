import React from "react"
import { Container } from "react-bootstrap"
import { WebData } from "../webdata"
import { Spinner } from "./Spinner"
import { ActivityChart } from "./ActivityChart"
import { Current } from "../world"

interface IActivityData {
  readonly labels: Array<string>
  readonly datasets: {
    readonly approved: Array<number>
    readonly merged: Array<number>
    readonly updated: Array<number>
  }
}

export function ActivityPage() {
  const data = useActivityData()
  return <ActivityPageInner data={data} />
}

function useActivityData(): WebData<IActivityData> {
  const [state, setState] = React.useState<WebData<IActivityData>>({
    status: "loading",
  })

  React.useEffect(() => {
    Current.api
      .getActivity()
      .then(res => {
        setState({ status: "success", data: res })
      })
      .catch(() => {
        setState({ status: "failure" })
      })
  }, [])
  return state
}

interface IActivityPageInnerProps {
  readonly data: WebData<IActivityData>
}
function ActivityPageInner({ data }: IActivityPageInnerProps) {
  if (data.status === "loading") {
    return (
      <ActivityPageContainer>
        <Spinner />
      </ActivityPageContainer>
    )
  }
  if (data.status === "failure") {
    return (
      <ActivityPageContainer>
        <p>Failure loading data D:</p>
      </ActivityPageContainer>
    )
  }

  return (
    <ActivityPageContainer>
      <h3 className="h5">Pull Request Activity</h3>
      <ActivityChart data={data.data} />
      <h3 className="h5">Kodiak Activity</h3>
      <ActivityChart data={data.data} />
    </ActivityPageContainer>
  )
}

interface IActivityPageContainer {
  readonly children: React.ReactNode
}
function ActivityPageContainer({ children }: IActivityPageContainer) {
  return (
    <Container>
      <h2>Activity</h2>
      {children}
    </Container>
  )
}
