import React from "react"
import {
  BrowserRouter as Router,
  Switch,
  Route,
  Link,
  NavLink,
} from "react-router-dom"
import {
  Container,
  Row,
  Col,
  Table,
  Popover,
  Dropdown,
  ButtonGroup,
  OverlayTrigger,
  Alert,
} from "react-bootstrap"
import ReactApexChart from "react-apexcharts"
import {
  GoGraph,
  GoCreditCard,
  GoSettings,
  GoGift,
  GoBook,
  GoChevronDown,
  GoLinkExternal,
  GoSignOut,
  GoQuestion,
} from "react-icons/go"
import sortBy from "lodash/sortBy"
import { Bar } from "react-chartjs-2"
import { ChartOptions } from "chart.js"
import format from "date-fns/format"

function Page({ children }: { children: React.ReactNode }) {
  const accountIsOver = false
  const seats = { current: 16, total: 15 }
  const nextBillingPeriod = "Feb 21"
  return (
    <div className="h-100">
      <div className="h-100 d-flex">
        <div className="h-100 flex-shrink-0">
          <SideBarNav />
        </div>
        <Container className="p-4 w-100 overflow-auto">
          {accountIsOver ? (
            <Alert variant="warning">
              <b>ATTENTION:</b> You’ve used {seats.current}/{seats.total} seats
              for your current billing period. Please add more seats to your
              plan by your next billing period ({nextBillingPeriod}) to ensure
              continued service.
            </Alert>
          ) : null}
          {children}
        </Container>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Router>
      <Switch>
        <Route exact path="/">
          <Page>
            <Activity />
          </Page>
        </Route>
        <Route path="/usage">
          <Page>
            <Usage />
          </Page>
        </Route>
        <Route path="/settings">
          <Page>
            <Settings />
          </Page>
        </Route>
        <Route path="/login">
          <Container className="h-100">
            <Login />
          </Container>
        </Route>
        <Route path="/accounts">
          <Container className="h-100">
            <Accounts />
          </Container>
        </Route>
      </Switch>
    </Router>
  )
}

function Image({
  url,
  size,
  alt,
  className,
}: {
  url: string
  size: number
  alt: string
  className: string
}) {
  return (
    <img
      src={url}
      alt={alt}
      width={size}
      height={size}
      className={`rounded ${className}`}
    />
  )
}

function ProfileImg({
  profileImgUrl,
  name,
  className = "",
  size,
}: {
  profileImgUrl: string
  name: string
  className?: string
  size: number
}) {
  return (
    <div className={className}>
      <Image
        url={profileImgUrl}
        alt="org profile"
        size={size}
        className="mr-2"></Image>
      <span className="h6 some-cls">{name}</span>
    </div>
  )
}
const modifyPlanLink = "https://github.com/marketplace/kodiakhq"
const installUrl = "https://github.com/marketplace/kodiakhq"
const docsUrl = "https://kodiakhq.com/docs/quickstart"
const helpUrl = "https://kodiakhq.com/help"
const activeUserUrl = "https://kodiakhq.com/docs/glossary#activeuser"

function SideBarNavLink({
  to,
  children,
  external = false,
  className,
}: {
  to: string
  children: React.ReactChild
  external?: boolean
  className?: string
}) {
  return (
    <li>
      {external ? (
        <a href={to} className={"text-decoration-none " + className}>
          {children}
        </a>
      ) : (
        <NavLink
          exact
          activeClassName="font-weight-bold"
          className={"text-decoration-none " + className}
          to={to}>
          {children}
        </NavLink>
      )}
    </li>
  )
}

function SideBarNav() {
  const user = {
    name: "sbdchd",
    profileImgUrl: "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
  }
  const org = {
    name: "Kodiak",
    profileImgUrl: "https://avatars1.githubusercontent.com/in/29196?s=400&v=4",
  }

  const accounts = [
    {
      name: "sbdchd",
      profileImgUrl:
        "https://avatars0.githubusercontent.com/u/7340772?s=200&v=4",
    },
    {
      name: "recipeyak",
      profileImgUrl:
        "https://avatars2.githubusercontent.com/u/32210060?s=200&v=4",
    },
    {
      name: "AdmitHub",
      profileImgUrl:
        "https://avatars3.githubusercontent.com/u/7806836?s=200&v=4",
    },
    {
      name: "getdoug",
      profileImgUrl:
        "https://avatars0.githubusercontent.com/u/33015070?s=200&v=4",
    },
    {
      name: "pytest-dev",
      profileImgUrl:
        "https://avatars1.githubusercontent.com/u/8897583?s=200&v=4",
    },
  ]

  const DropdownToggle = Dropdown.Toggle as any
  return (
    <div className="bg-light p-3 h-100 d-flex flex-column justify-content-between">
      <div>
        <div>
          <Dropdown as={ButtonGroup}>
            <DropdownToggle id="dropdown-custom-1" as={CustomToggle}>
              <div className="d-flex align-items-center">
                <Image
                  url={org.profileImgUrl}
                  alt="kodiak avatar"
                  size={30}
                  className="mr-2"></Image>
                <span className="h4 mb-0">{org.name}</span>
              </div>
            </DropdownToggle>
            <Dropdown.Menu className="super-colors shadow-sm">
              <Dropdown.Header>switch account</Dropdown.Header>
              {sortBy(accounts, "name").map(x => (
                <Dropdown.Item as="button">
                  <>
                    <Image
                      url={x.profileImgUrl}
                      alt={x.name}
                      size={30}
                      className="mr-3"></Image>
                    {x.name}
                  </>
                </Dropdown.Item>
              ))}
            </Dropdown.Menu>
          </Dropdown>
        </div>
        <ul className="list-unstyled">
          <SideBarNavLink to="/" className="d-flex align-items-center">
            <>
              <GoGraph className="mr-1" size="1.25rem" />
              <span>Activity</span>
            </>
          </SideBarNavLink>
          <SideBarNavLink to="/usage">
            <>
              <GoCreditCard className="mr-1" size="1.25rem" />
              <span>Usage & Billing</span>
            </>
          </SideBarNavLink>
          <SideBarNavLink to="/settings">
            <>
              <GoSettings className="mr-1" size="1.25rem" />
              <span>Settings</span>
            </>
          </SideBarNavLink>
          <hr></hr>

          <SideBarNavLink
            to={docsUrl}
            external
            className="d-flex align-items-center">
            <>
              <GoBook className="mr-1" size="1.25rem" />
              <span>Docs</span>
              <GoLinkExternal className="ml-auto" />
            </>
          </SideBarNavLink>
          <SideBarNavLink
            to={helpUrl}
            external
            className="d-flex align-items-center">
            <>
              <GoQuestion className="mr-1" size="1.25rem" />
              <span>Help</span>
              <GoLinkExternal className="ml-auto" />
            </>
          </SideBarNavLink>

          <SideBarNavLink
            to={modifyPlanLink}
            external
            className="d-flex align-items-center">
            <>
              <GoGift className="mr-1" size="1.25rem" />
              <span>Upgrade</span>
              <GoLinkExternal className="ml-auto" />
            </>
          </SideBarNavLink>
        </ul>
      </div>

      <div>
        <Dropdown as={ButtonGroup}>
          <DropdownToggle id="dropdown-custom-1" as={CustomToggle}>
            <ProfileImg
              profileImgUrl={user.profileImgUrl}
              name={user.name}
              size={30}
            />
          </DropdownToggle>
          <Dropdown.Menu className="super-colors shadow-sm">
            <Dropdown.Item as="button">
              <span className="mr-1">Logout</span>
              <GoSignOut />
            </Dropdown.Item>
          </Dropdown.Menu>
        </Dropdown>
      </div>
    </div>
  )
}

const CustomToggle = React.forwardRef(
  (
    {
      children,
      onClick,
    }: {
      children: React.ReactNode
      onClick: (e: React.MouseEvent<HTMLButtonElement, MouseEvent>) => void
    },
    ref: React.Ref<HTMLButtonElement>,
  ) => (
    <button
      className="btn border-hover rounded mb-2"
      ref={ref}
      onClick={e => {
        e.preventDefault()
        if (onClick) {
          onClick(e)
        }
      }}>
      <div className="d-flex align-items-center some-cls">
        {children}
        <span className="ml-2">
          <GoChevronDown size="1.5rem" />
        </span>
      </div>
    </button>
  ),
)

function ApexChart() {
  const axisStyle = {
    color: undefined,
    fontSize: "1rem",
    cssClass: "h5 text-body",
  }

  const color = {
    updated: "#D29D0D",
    merged: "#5B28B3",
    approved: "#2AB53E",
  }
  const state = {
    series: [
      {
        name: "Updated",
        data: Array(30)
          .fill(0)
          .map((_, i) => [11, 17, 15, 15, 21, 14, 0, 1, 2, 3][i % 10]),
      },
      {
        name: "Merged",
        data: Array(30)
          .fill(0)
          .map((_, i) => [13, 23, 20, 8, 13, 27, 4, 4, 5, 6][i % 10]),
      },
      {
        name: "Approved",
        data: Array(30)
          .fill(0)
          .map((_, i) => [44, 55, 41, 67, 22, 43, 2, 7, 9, 8][i % 10]),
      },
    ],
    options: {
      noData: {
        text: "no data",
      },
      // states: {
      //   hover: {
      //     filter: {
      //       type: "none",
      //     },
      //   },
      //   active: { filter: { type: "none" } },
      // },
      tooltip: {
        shared: true,
        followCursor: true,
      },
      chart: {
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji"',
        type: "bar",
        height: 350,
        stacked: true,
        toolbar: {
          show: false,
        },
        zoom: {
          enabled: false,
        },
        animations: {
          enabled: false,
        },
      },
      colors: [color.updated, color.merged, color.approved],
      plotOptions: {
        bar: {
          horizontal: false,
          dataLabels: {
            hideOverflowingLabels: true,
          },
        },
      },
      yaxis: {
        title: {
          text: "Event Count",
          style: axisStyle,
        },
      },
      xaxis: {
        title: {
          text: "Time",
          offsetY: 10,
          style: axisStyle,
        },
        type: "datetime",
        categories: Array(30)
          .fill(0)
          .map((_, i) => `01/${i + 1}/2011 GMT`),
      },
      legend: {
        show: false,
        position: "bottom",
        offsetY: -10,
      },
      fill: {
        opacity: 1,
      },
    },
  }

  return (
    <div id="chart">
      <ReactApexChart
        options={state.options}
        series={state.series}
        type="bar"
        height={350}
      />
    </div>
  )
}
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
    // borderColor: "rgb(222, 226, 230)",
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
        // debugger
        return format(date, "MMM do")
        return String(tooltipItem[0].label)
      },
      // label: function(tooltipItem, data) {
      //   console.log(tooltipItem.label)
      //   return String(tooltipItem.label)
      //     // var label = data.datasets[tooltipItem.datasetIndex].label || '';

      //     // if (label) {
      //     //     label += ': ';
      //     // }
      //     // label += Math.round(tooltipItem.yLabel * 100) / 100;
      //     // return label;
      // }
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
          // zeroLineWidth: 0,
          // drawOnChartArea: false,
          // color: "rgba(0, 0, 0, 0.1)",
          // lineWidth: 1,
          // tickMarkLength: 5,
          // drawBorder: false,
        },
        ticks: {
          fontColor,
          fontFamily,
          // fontStyle: "bold",
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
          // fontStyle: "bold",
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
  // -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji"
  return (
    <div className="chart-container">
      <Bar data={barChartData} options={chartOptions} />
    </div>
  )
}

function Activity() {
  return (
    <Container>
      <h2>Activity</h2>

      {/* <h3 className="h5">Pull Request Activity</h3>
      <ApexChart></ApexChart>

      <h3 className="h5">Kodiak Activity</h3>
      <ApexChart></ApexChart> */}
      <h3 className="h5">Pull Request Activity</h3>
      <ChartJSChart />

      <h3 className="h5">Kodiak Activity</h3>
      <ChartJSChart />
    </Container>
  )
}

function Question({ content }: { content: string | React.ReactNode }) {
  const popover = (
    <Popover id="popover-basic">
      <Popover.Content>{content}</Popover.Content>
    </Popover>
  )

  return (
    <OverlayTrigger trigger="hover" placement="top" overlay={popover}>
      <b>(?)</b>
    </OverlayTrigger>
  )
}

function Usage() {
  const perUserUSD = 5
  const perMonthUSD = 75
  const billingPeriod = { start: "Jan 17", end: "Feb 16" }
  const seats = { current: 8, total: 15 }
  const nextBillingDate = "February 21st, 2019"
  const repos = [
    { name: "backend", id: 50234 },
    { name: "api-frontend", id: 23485 },
  ]
  const activeUsers = [
    {
      name: "bernard",
      profileImgUrl:
        "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
      interactions: 15,
      lastActiveDate: "Jan 22",
    },
    {
      name: "william",
      profileImgUrl:
        "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
      interactions: 15,
      lastActiveDate: "Jan 22",
    },
    {
      name: "deloris",
      profileImgUrl:
        "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
      interactions: 15,
      lastActiveDate: "Jan 15",
    },
    {
      name: "maeve",
      profileImgUrl:
        "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
      interactions: 15,
      lastActiveDate: "Jan 3",
    },
  ]

  const sections: {
    name: React.ReactNode
    rows: {
      name: React.ReactNode
      content: React.ReactNode
      description?: React.ReactNode
    }[]
  }[] = [
    {
      name: "Usage",
      rows: [
        {
          name: "Seats",
          content: (
            <>
              {seats.current} of {seats.total} available
            </>
          ),
        },{
          name: "Next Billing Date",
          content: nextBillingDate,
        },
        {
          name: "Cost",
          content: (
            <>
              ${perMonthUSD}/month{" "}
              <Question
                content={`$${perUserUSD}/user * ${seats.total} users = $${perMonthUSD}`}
              />{" "}
              <a href={modifyPlanLink}>change plan</a>
            </>
          ),
        },
      ],
    },
    {
      name: "Plan",
      rows: [
        { name: "Plan Type", content: "Private" },
        {
          name: "Seats",
          content: (
            <>
              {seats.total} <a href={modifyPlanLink}>add/remove seats</a>
            </>
          ),
          description: (
            <>
              A seat license is required for each{" "}
              <a href={activeUserUrl}>active user</a> on a private repository.{" "}
              <i>Public repositories</i> are free.{" "}
            </>
          ),
        },
        
      ],
    },
  ]

  return (
    <div>
      <h2>Usage & Billing</h2>

      <p>
        Current activity for billing period{" "}
        <b>
          {billingPeriod.start} – {billingPeriod.end}
        </b>
      </p>

      {sections.map(s => (
        <div className="mb-4">
          <h3 className="h5">{s.name}</h3>
          <div className="border border-primary rounded p-2">
            {s.rows.map((r, i) => {
              const isLast = i === s.rows.length - 1
              const cls = isLast ? "" : "mb-2"
              return (
                <Row className={cls}>
                  <Col md={3}>
                    <b>{r.name}</b>
                  </Col>
                  <Col>{r.content}</Col>
                  {r.description ? (
                    <Col sm={12}>
                      <p className="small mb-0">{r.description}</p>
                    </Col>
                  ) : null}
                </Row>
              )
            })}
          </div>
        </div>
      ))}

      <div className="mb-4">
        <div className="d-flex justify-content-between">
          <h3 className="h5">Active Users ({activeUsers.length})</h3>
          <select>
            <option>All Repositories</option>
            {repos.map(r => (
              <option value={r.id}>{r.name}</option>
            ))}
          </select>
        </div>

        <div>
          <Table size="sm">
            <thead>
              <tr>
                <th>User</th>
                <th>
                  Interactions{" "}
                  <Question
                    content={
                      "This user opened, reviewed or edited a pull request that Kodiak updated, approved, or merged."
                    }
                  />
                </th>
                <th>Last Active Date</th>
              </tr>
            </thead>
            <tbody>
              {activeUsers.map(u => (
                <tr>
                  <td>
                    <Image
                      url={u.profileImgUrl}
                      alt="user profile"
                      size={30}
                      className="mr-3"></Image>
                    {u.name}
                  </td>
                  <td>{u.interactions}</td>
                  <td>{u.lastActiveDate}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </div>
    </div>
  )
}

function Settings() {
  const settings = { notifyOnExceedBilledSeats: true }
  return (
    <div>
      <h2>Settings</h2>
      <div>
        <h3 className="h5">Notifications</h3>
        <div className="border border-primary rounded p-2">
          <label className="d-flex align-items-center mb-0">
            <input
              type="checkbox"
              checked={settings.notifyOnExceedBilledSeats}
              className="mr-2"></input>

            <p className="mb-0">notify me when I’ve exceeded my billed seats</p>
          </label>
        </div>
      </div>
    </div>
  )
}

function Login() {
  return (
    <div className="h-100 d-flex justify-content-center align-items-center">
      <div
        className="w-100 text-center d-flex justify-content-around align-items-center flex-column"
        style={{ minHeight: 300 }}>
        <div className="d-flex justify-content-center align-items-center">
          <img
            src="/favicon.ico"
            alt="favicon"
            height={30}
            width={30}
            className="mr-2"></img>
          <h1 className="h2 mb-0 font-weight-bold">Kodiak</h1>
        </div>

        <div>
          <Link to="/" className="gh-install-btn">
            Login with GitHub
          </Link>
        </div>

        <p className="mb-0">
          <a href={installUrl}>Install</a> | <a href={docsUrl}>Docs</a> |{" "}
          <a href={helpUrl}>Help</a>
        </p>
      </div>
    </div>
  )
}

function Accounts() {
  const accounts = [
    {
      name: "bernard",
      profileImgUrl:
        "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
    },
    {
      name: "william",
      profileImgUrl:
        "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
    },
    {
      name: "deloris",
      profileImgUrl:
        "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
    },
    {
      name: "maeve",
      profileImgUrl:
        "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
    },
  ]
  return (
    <div className="h-100 d-flex justify-content-center align-items-center flex-column">
      <div
        className="w-100 text-center d-flex justify-content-around align-items-center flex-column"
        style={{ minHeight: 300 }}>
        <h1 className="h4">Select an Account</h1>
        <ul className="list-unstyled">
          {accounts.map(a => (
            <li className="d-flex align-items-center">
              <a href="https://github.com/" className="pb-3">
                <Image
                  url={a.profileImgUrl}
                  alt="org profile"
                  size={30}
                  className="mr-2"></Image>
                <span>{a.name}</span>
              </a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
