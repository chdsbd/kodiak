import React from "react"
import { Bar } from "react-chartjs-2"
import { ChartOptions } from "chart.js"
import format from "date-fns/format"
import { Container } from "react-bootstrap"
import { WebData } from "../webdata"
import { sleep } from "../sleep"
import { Spinner } from "./Spinner"

const color = {
  updated: "#D29D0D",
  merged: "#5B28B3",
  approved: "#2AB53E",
}

const fontFamily =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji"'

const fontColor = "#212529"
const backgroundColor = "white"

const chartOptions: ChartOptions = {
  tooltips: {
    mode: "index",
    intersect: false,
    backgroundColor,
    titleFontColor: fontColor,
    bodyFontColor: fontColor,
    borderWidth: 1,
    borderColor: fontColor,
    titleFontFamily: fontFamily,
    bodyFontFamily: fontFamily,
    bodyFontStyle: "bold",
    footerFontFamily: fontFamily,
    cornerRadius: 4,
    callbacks: {
      title: (tooltipItem, data) => {
        const label = tooltipItem[0].label
        if (label == null) {
          return "unknown"
        }
        const date = new Date(label)
        return format(date, "MMM do")
      },
    },
  },
  scales: {
    xAxes: [
      {
        type: "time",
        offset: true,
        stacked: true,
        scaleLabel: {
          display: true,
          labelString: "Time",
          padding: 0,
          fontFamily,
          fontColor,
          fontSize: 16,
        },
        gridLines: {
          display: false,
        },
        ticks: {
          fontColor,
          fontFamily,
          maxRotation: 0,
          padding: -5,
        },
      },
    ],
    yAxes: [
      {
        stacked: true,
        scaleLabel: {
          display: true,
          labelString: "Event Count",
          padding: 0,
          fontFamily,
          fontColor,
          fontSize: 16,
        },
        gridLines: {
          drawBorder: false,
          color: "rgba(0, 0, 0, 0.1)",
          lineWidth: 1,
          tickMarkLength: 0,
        },
        ticks: {
          fontColor,
          fontFamily,
          padding: 5,
        },
      },
    ],
  },
  responsive: true,
  maintainAspectRatio: false,
  legend: {
    display: false,
  },
}

interface IActivityData {
  labels: Array<string>
  datasets: {
    approved: Array<number>
    merged: Array<number>
    updated: Array<number>
  }
}

interface IActivityChartProps {
  data: {
    labels: Array<string>
    datasets: {
      approved: Array<number>
      merged: Array<number>
      updated: Array<number>
    }
  }
}
function ActivityChart({ data: { labels, datasets } }: IActivityChartProps) {
  const barChartData = {
    labels: labels,
    datasets: [
      {
        label: "Approved",
        backgroundColor: color.approved,
        data: datasets.approved,
      },
      {
        label: "Merged",
        backgroundColor: color.merged,
        data: datasets.merged,
      },
      {
        label: "Updated",
        backgroundColor: color.updated,
        data: datasets.updated,
      },
    ],
  }
  return (
    <div className="chart-container">
      <Bar data={barChartData} options={chartOptions} />
    </div>
  )
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
