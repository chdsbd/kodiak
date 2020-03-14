import React from "react"
import {
  Table,
  Row,
  Col,
  Popover,
  OverlayTrigger,
  Modal,
  Form,
  Button,
} from "react-bootstrap"
import { Image } from "./Image"
import { WebData } from "../webdata"
import { Spinner } from "./Spinner"
import { Current } from "../world"
import { useTeamApi } from "../useApi"
import sub from "date-fns/sub"
import format from "date-fns/format"
import sortBy from "lodash/sortBy"

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
  readonly subscription: {
    readonly seats: number
    readonly nextBillingDate: string
    readonly costCents: number
    readonly billingContact: {
      readonly email: string
    }
  } | null
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
    <UsageAndBillingContainer>
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

function UsageAndBillingContainer({ children }: { children: React.ReactNode }) {
  return (
    <div className="d-flex flex-column flex-grow-1">
      <h2>Usage & Billing</h2>
      {children}
    </div>
  )
}


function formatCents(cents: number): string {
  return `\$${cents / 100}`
}

function InstallCompleteModal() {
  return (
    <Modal size="lg" show={false}>
      <Modal.Header closeButton>
        <Modal.Title>🎉 Your Kodiak install is ready!</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <p>
          <a href="https://kodiakhq.com/docs/quickstart">Visit our docs</a> to
          learn more about installation or{" "}
          <a href="https://kodiakhq.com/help">contact us</a> for support setting
          up Kodiak.
        </p>
        <Button size="sm">Close</Button>
      </Modal.Body>
    </Modal>
  )
}

function StartTrialModal() {
  return (
    <Modal size="lg" show={false}>
      <Modal.Header closeButton>
        <Modal.Title>Start Trial</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Form>
          <Form.Group controlId="formBasicEmail">
            <Form.Label>Billing Email</Form.Label>
            <Form.Control type="email" placeholder="Enter email" />
            <Form.Text className="text-muted">
              We’ll send you billing reminders at this email address.
            </Form.Text>
          </Form.Group>
          <div className="mb-4">
            <b className="mr-4">Trial expiration</b>
            <span>2020-02-23 (14 days from now)</span>
          </div>

          <Button variant="primary" type="submit">
            Begin Trial
          </Button>
        </Form>
      </Modal.Body>
    </Modal>
  )
}

interface ISubscriptionPromptProps {
  readonly trailAvailable: boolean
}
function SubscriptionPrompt({ trailAvailable }: ISubscriptionPromptProps) {
  if (trailAvailable) {
    return (
      <>
        <h4 className="h6">
          Subscribe and use Kodiak on your private repositories!
        </h4>
        <div className="d-flex align-items-center">
          <Button variant="success" size="large">
            Start Trial
          </Button>
          <span className="mx-2">or</span>{" "}
          <a className="mr-2" href="#" variant="link">
            subscribe
          </a>{" "}
          <span>($4.99 per active user per month)</span>
        </div>
      </>
    )
  }

  return (
    <>
      <h4 className="h6">
        Subscribe and use Kodiak on your private repositories!
      </h4>
      <div className="d-flex align-items-center">
        <Button variant="success" size="large" className="mr-2">
          Subscribe
        </Button>
        <span>($4.99 per active user per month)</span>
      </div>
    </>
  )
}

function SubscriptionActiveTrialPrompt() {
  return (
    <>
      <div>
        <p className="mb-0">
          Subscribe to continue using Kodiak on your private repositories!
        </p>
        <b className="mr-4">Trial expiration</b>
        <span>2020-03-23 (12 days from now)</span>
      </div>
      <div className="d-flex align-items-center">
        <Button variant="success" size="large" className="mr-2">
          Subscribe
        </Button>
        <span>($4.99 per active user per month)</span>
      </div>
    </>
  )
}

interface IActiveSubscriptionProps {
  readonly seats: number
  readonly nextBillingDate: string
  readonly billingEmail: string
  readonly cost: {
    readonly totalCents: number
    readonly perSeatCents: number
  }
}
function ActiveSubscription({
  seats,
  cost,
  billingEmail,
  nextBillingDate,
}: IActiveSubscriptionProps) {
  return (
    <>
      <Row>
        <Col md={3}>
          <b>Seats</b>
        </Col>
        <Col>{seats}</Col>

        <Col sm={12}>
          <p className="small mb-0">
            An active user consumes one per billing period seat. If your usage
            exceeds your purchased seats you will need to add more seats to your
            subscription.
          </p>
        </Col>
      </Row>
      <Row>
        <Col md={3}>
          <b>Next Billing Date</b>
        </Col>
        <Col>{nextBillingDate}</Col>
      </Row>
      <Row>
        <Col md={3}>
          <b>Cost</b>
        </Col>
        <Col>
          <span className="mr-4">{formatCents(cost.totalCents)} / month</span>
          <span>
            ({formatCents(cost.perSeatCents)} / seat * {seats})
          </span>
        </Col>
      </Row>
      <Row>
        <Col md={3}>
          <b>Billing Email</b>
        </Col>
        <Col>{billingEmail}</Col>
      </Row>
      <Row className="mt-3">
        <Col>
          <Button variant="dark" size="sm">
            Modify Subscription
          </Button>
        </Col>
        <Col sm={12}>
          <p className="small mb-0 mt-2">
            Send us an email at{" "}
            <a href="mailto:support@kodiakhq.com">support@kodiakhq.com</a> if
            you need any assistance.
          </p>
        </Col>
      </Row>
    </>
  )
}

interface ISubscriptionProps {
  readonly activeSubscription: boolean
  readonly state:
    | "trialAvailable"
    | "trialActive"
    | "subscriptionAvailable"
    | "subscriptionActive"
}
function Subscription({
  activeSubscription,
  state = "subscriptionAvailable",
}: ISubscriptionProps) {
  return (
    <>
      <h3 className="h5">Subscription</h3>
      <div className="border border-primary rounded p-2 mb-4">
        <Row>
          <Col>
            {state === "trialAvailable" ? (
              <SubscriptionActiveTrialPrompt />
            ) : state === "trailActive" ? (
              <SubscriptionPrompt trialAvailable />
            ) : state === "subscriptionActive" ? (
              <ActiveSubscription
                cost={{ perSeatCents: 499, totalCents: 4999 }}
                seats={10}
                nextBillingDate="2020-04-15"
                billingEmail="dev@acme-corp.com"
              />
            ) : (
              // subscriptionAvailable case.
              <SubscriptionPrompt trialAvailable={false} />
            )}
          </Col>
        </Row>
        <Row>
          <Col>
            <hr />
          </Col>
        </Row>
        <Row>
          <Col>
            <b>Subscription benefits</b>
            <ul>
              <li>
                private repositories – use kodiak on your private repositories
              </li>
              <li>priority support – get priority help configuring Kodiak</li>
              <li>
                sustain Kodiak – help us cover server costs and support Kodiak
              </li>
            </ul>
          </Col>
        </Row>
        <Row>
          <Col>
            <b>Trial</b>
            <p>
              The 14-day trial is free and allows for using Kodiak on private
              repos with an unlimited number of users. After 14-days you can
              subscribe to continue using Kodiak on private repositories.
            </p>
          </Col>
        </Row>
        <Row>
          <Col>
            <b>Pricing</b>
            <p>
              Kodiak is $4.99 per active user per month. An active user is
              anyone that opens a GitHub pull request that Kodiak updates,
              approves, or merges.
            </p>
          </Col>
        </Row>
      </div>
    </>
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
      <div className="mb-4">
        <InstallCompleteModal />
        <StartTrialModal />
        <Subscription />

        <h3 className="h5">Usage</h3>
        <div className="border border-primary rounded p-2">
          <Row>
            <Col md={3}>
              <b>Active Users</b>
            </Col>
            <Col>
              {data.activeUsers.length} / {data.subscription?.seats ?? 0} seats
            </Col>

            <Col sm={12}>
              <p className="small mb-0">
                Active users are only counted for private repositories. Public
                repositories are free.
              </p>
            </Col>
          </Row>

          <Table size="sm" className="mt-2">
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
              {sortBy(data.activeUsers, x => x.name.toLowerCase()).map(u => (
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
