import React from "react"
import { Bar } from "react-chartjs-2"
import { ChartOptions } from "chart.js"
import format from "date-fns/format"
import sub from "date-fns/sub"
import parseISO from "date-fns/parseISO"

const TODAY = new Date()
const ONE_MONTH_AGO = sub(new Date(), { months: 1 })

const color = {
  updated: "#D29D0D",
  merged: "#5B28B3",
  approved: "#2AB53E",
  opened: "#2AB53E",
  closed: "#cb2431",
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
      title: tooltipItem => {
        const label = tooltipItem[0].label
        if (label == null) {
          return "unknown"
        }
        const date = parseISO(label)
        return format(date, "MMM do")
      },
    },
  },
  scales: {
    xAxes: [
      {
        type: "time",
        time: {
          unit: "day",
        },
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
          autoSkipPadding: 25,
          padding: -5,
          min: ONE_MONTH_AGO,
          max: TODAY,
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

interface IKodiakActivityChartProps {
  readonly data: {
    readonly labels: Array<string>
    readonly datasets: {
      readonly approved: Array<number>
      readonly merged: Array<number>
      readonly updated: Array<number>
    }
  }
}
export function KodiakActivityChart({
  data: { labels, datasets },
}: IKodiakActivityChartProps) {
  const barChartData = {
    labels,
    datasets: [
      {
        label: "Approvals",
        backgroundColor: color.approved,
        data: datasets.approved,
      },
      {
        label: "Merges",
        backgroundColor: color.merged,
        data: datasets.merged,
      },
      {
        label: "Updates",
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

const chartOptionsTotal: ChartOptions = {
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
      title: tooltipItem => {
        const label = tooltipItem[0].label
        if (label == null) {
          return "unknown"
        }
        const date = parseISO(label)
        return format(date, "MMM do")
      },
    },
  },
  scales: {
    xAxes: [
      {
        type: "time",
        time: {
          unit: "day",
        },
        offset: true,
        stacked: false,
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
          autoSkipPadding: 25,
          padding: -5,
          min: ONE_MONTH_AGO,
          max: TODAY,
        },
      },
    ],
    yAxes: [
      {
        stacked: false,
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
interface IPullRequestActivityChartProps {
  readonly data: {
    readonly labels: Array<string>
    readonly datasets: {
      readonly opened: Array<number>
      readonly merged: Array<number>
      readonly closed: Array<number>
    }
  }
}
export function PullRequestActivityChart({
  data: { labels, datasets },
}: IPullRequestActivityChartProps) {
  const barChartData = {
    labels,
    datasets: [
      {
        label: "Opened",
        backgroundColor: color.opened,
        data: datasets.opened,
      },
      {
        label: "Merged",
        backgroundColor: color.merged,
        data: datasets.merged,
      },
      {
        label: "Closed",
        backgroundColor: color.closed,
        data: datasets.closed,
      },
    ],
  }
  return (
    <div className="chart-container">
      <Bar data={barChartData} options={chartOptionsTotal} />
    </div>
  )
}
