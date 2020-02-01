import React from "react"
import { Bar } from "react-chartjs-2"
import { ChartOptions } from "chart.js"
import format from "date-fns/format"

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

interface IActivityChartProps {
  readonly data: {
    readonly labels: Array<string>
    readonly datasets: {
      readonly approved: Array<number>
      readonly merged: Array<number>
      readonly updated: Array<number>
    }
  }
}

export function ActivityChart({
  data: { labels, datasets },
}: IActivityChartProps) {
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
