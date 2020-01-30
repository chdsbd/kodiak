import React from "react"
import { Table, Row, Col, Popover, OverlayTrigger } from "react-bootstrap"
import { Image } from "./Image"
import { modifyPlanLink, activeUserUrl } from "../settings"

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

export function UsageBillingPage() {
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
        },
        {
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
