import React from "react"
import { Table, Row, Col, Popover, OverlayTrigger } from "react-bootstrap"
import { Image } from "./Image"
import { WebData } from "../webdata"
import { Spinner } from "./Spinner"
import { Current } from "../world"
import { useTeamApi } from "../useApi"
import sub from "date-fns/sub"
import format from "date-fns/format"

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
  const data = useTeamApi(Current.api.getUsageBilling)
  return <UsageBillingPageInner data={data} />
}

interface IUsageBillingData {
  readonly activeUsers: ReadonlyArray<{
    readonly id: number
    readonly name: string
    readonly profileImgUrl: string
    readonly interactions: number
    readonly lastActiveDate: string
  }>
}

interface IUsageBillingPageInnerProps {
  readonly data: WebData<IUsageBillingData>
}

function Loading() {
  return (
    <UsageAndBillingContainer className="h-100">
      <Spinner />
    </UsageAndBillingContainer>
  )
}

function Failure() {
  return (
    <UsageAndBillingContainer>
      <p className="text-center text-muted">failed to load usage data</p>
    </UsageAndBillingContainer>
  )
}

function UsageAndBillingContainer({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={className}>
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
          name: "Active Users",
          content: <>{data.activeUsers.length}</>,
          description: (
            <>
              Active users are only counted for private repositories. Kodiak
              does not have a billing system yet, so it is free, however
              donations through GitHub sponsors are very welcome.
            </>
          ),
        },
      ],
    },
  ]

  const dateToday = new Date()
  const today = format(dateToday, "MMM do")
  const dateOneMonthAgo = sub(dateToday, { months: 1 })
  const oneMonthAgo = format(dateOneMonthAgo, "MMM do")

  return (
    <UsageAndBillingContainer>
      <p>
        <b> Period</b>
        <br />
        {oneMonthAgo} – {today}
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
        <h3 className="h5">Active Users ({data.activeUsers.length})</h3>

        <div>
          <Table size="sm">
            <thead>
              <tr>
                <th>User</th>
                <th>
                  Days Active{" "}
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
                <tr key={u.id}>
                  <td>
                    <Image
                      url={u.profileImgUrl}
                      alt="user profile"
                      size={30}
                      className="mr-3"
                    />
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
