import React from "react"
import { Bar } from "react-chartjs-2"
import { ChartOptions } from "chart.js"
import format from "date-fns/format"
import { Container } from "react-bootstrap"

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

function ChartJSChart() {
  const barChartData = {
    labels: Array(30)
      .fill(0)
      .map((_, i) => `01/${i + 1}/2011 GMT`),
    datasets: [
      {
        label: "Approved",
        backgroundColor: color.approved,
        data: Array(30)
          .fill(0)
          .map((_, i) => [13, 23, 20, 8, 13, 27, 4, 4, 5, 6][i % 10]),
      },
      {
        label: "Merged",
        backgroundColor: color.merged,
        data: Array(30)
          .fill(0)
          .map((_, i) => [13, 23, 20, 8, 13, 27, 4, 4, 5, 6][i % 10]),
      },
      {
        label: "Updated",
        backgroundColor: color.updated,
        data: Array(30)
          .fill(0)
          .map((_, i) => [44, 55, 41, 67, 22, 43, 2, 7, 9, 8][i % 10]),
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
  return (
    <Container>
      <h2>Activity</h2>
      <h3 className="h5">Pull Request Activity</h3>
      <ChartJSChart />

      <h3 className="h5">Kodiak Activity</h3>
      <ChartJSChart />
    </Container>
  )
}
