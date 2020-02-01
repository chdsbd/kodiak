import React from "react"
import { Table, Row, Col, Popover, OverlayTrigger } from "react-bootstrap"
import { Image } from "./Image"
import { modifyPlanLink, activeUserUrl } from "../settings"
import { WebData } from "../webdata"
import { Spinner } from "./Spinner"
import { Current } from "../world"
import { useApi } from "../useApi"

interface IQuestionProps {
  readonly content: string | React.ReactNode
}
function Question({ content }: IQuestionProps) {
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
  const data = useApi(Current.api.getUsageBilling)
  return <UsageBillingPageInner data={data} />
}

interface IUsageBillingData {
  readonly seats: {
    readonly current: number
    readonly total: number
  }
  readonly perUserUSD: number
  readonly perMonthUSD: number
  readonly nextBillingDate: string
  readonly billingPeriod: {
    readonly start: string
    readonly end: string
  }
  readonly activeUsers: ReadonlyArray<{
    readonly name: string
    readonly profileImgUrl: string
    readonly interactions: number
    readonly lastActiveDate: string
  }>
  readonly repos: ReadonlyArray<{
    readonly name: string
    readonly id: number
  }>
}

interface IUsageBillingPageInnerProps {
  readonly data: WebData<IUsageBillingData>
}

function Loading() {
  return (
    <UsageAndBillingContainer>
      <Spinner />
    </UsageAndBillingContainer>
  )
}

function Failure() {
  return (
    <UsageAndBillingContainer>
      <p className="text-center">failed to fetch data</p>
    </UsageAndBillingContainer>
  )
}

function UsageAndBillingContainer({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <h2>Usage & Billing</h2>
      {children}
    </div>
  )
}

function UsageBillingPageInner(props: IUsageBillingPageInnerProps) {
  if (props.data.status === "loading") {
    return <Loading />
  }

  if (props.data.status === "failure") {
    return <Failure />
  }

  const data = props.data.data

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
              {data.seats.current} of {data.seats.total} available
            </>
          ),
        },
        {
          name: "Next Billing Date",
          content: data.nextBillingDate,
        },
        {
          name: "Cost",
          content: (
            <>
              ${data.perMonthUSD}/month{" "}
              <Question
                content={`$${data.perUserUSD}/user * ${data.seats.total} users = $${data.perMonthUSD}`}
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
              {data.seats.total} <a href={modifyPlanLink}>add/remove seats</a>
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
    <UsageAndBillingContainer>
      <p>
        Current activity for billing period{" "}
        <b>
          {data.billingPeriod.start} – {data.billingPeriod.end}
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
          <h3 className="h5">Active Users ({data.activeUsers.length})</h3>
          <select>
            <option>All Repositories</option>
            {data.repos.map(r => (
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
              {data.activeUsers.map(u => (
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
    </UsageAndBillingContainer>
  )
}
