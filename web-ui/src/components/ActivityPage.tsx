import React from "react"
import { Container } from "react-bootstrap"
import { WebData } from "../webdata"
import { sleep } from "../sleep"
import { Spinner } from "./Spinner"
import { ActivityChart } from "./ActivityChart"

interface IActivityData {
  labels: Array<string>
  datasets: {
    approved: Array<number>
    merged: Array<number>
    updated: Array<number>
  }
}

export function ActivityPage() {
  const data = useActivityData()
  return <ActivityPageInner data={data} />
}

function useActivityData(): WebData<IActivityData> {
  const data = {
    labels: Array(30)
      .fill(0)
      .map((_, i) => `01/${i + 1}/2011 GMT`),
    datasets: {
      approved: Array(30)
        .fill(0)
        .map((_, i) => [13, 23, 20, 8, 13, 27, 4, 4, 5, 6][i % 10]),
      merged: Array(30)
        .fill(0)
        .map((_, i) => [13, 23, 20, 8, 13, 27, 4, 4, 5, 6][i % 10]),
      updated: Array(30)
        .fill(0)
        .map((_, i) => [44, 55, 41, 67, 22, 43, 2, 7, 9, 8][i % 10]),
    },
  }

  const [state, setState] = React.useState<WebData<IActivityData>>({
    status: "loading",
  })

  React.useEffect(() => {
    sleep(400).then(() => {
      setState({ status: "success", data })
    })
  }, [data])
  return state
}

interface IActivityPageInnerProps {
  data: WebData<IActivityData>
}
function ActivityPageInner({ data }: IActivityPageInnerProps) {
  if (data.status === "loading") {
    return (
      <ActivityPageContainer>
        <Spinner></Spinner>
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

function ActivityPageContainer({ children }: { children: React.ReactNode }) {
  return (
    <Container>
      <h2>Activity</h2>
      {children}
    </Container>
  )
}
