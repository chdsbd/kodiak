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
import { useTeamApi, teamApi, useTeamId } from "../useApi"
import sub from "date-fns/sub"
import format from "date-fns/format"
import sortBy from "lodash/sortBy"
import parseISO from "date-fns/parseISO"
import formatDistanceToNow from "date-fns/formatDistanceToNow"
import formatDate from "date-fns/format"
import { useLocation, useHistory } from "react-router-dom"

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
    readonly active: boolean
    readonly nextBillingDate: string
    readonly costCents: number
    readonly billingContact: {
      readonly email: string
    }
  } | null
  readonly trial: {
    readonly startDate: string
    readonly endDate: string
    readonly active: boolean
    readonly startedBy: {
      readonly id: number
      readonly name: string
      readonly profileImgUrl: string
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

function formatFromNow(dateString: string): string {
  return formatDistanceToNow(parseISO(dateString))
}

interface IInstallCompleteModalProps {
  readonly show: boolean
  readonly onClose: () => void
}
function InstallCompleteModal({ show, onClose }: IInstallCompleteModalProps) {
  return (
    <Modal size="lg" show={show} onHide={onClose}>
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
        <Button size="sm" onClick={onClose}>
          Close
        </Button>
      </Modal.Body>
    </Modal>
  )
}

interface IStartTrialModalProps {
  readonly show: boolean
  readonly onClose: () => void
}
function StartTrialModal({ show, onClose }: IStartTrialModalProps) {
  const [email, setEmail] = React.useState("")
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState("")
  const teamId = useTeamId()
  function startTrial() {
    setLoading(true)
    setError("")
    teamApi(Current.api.startTrial, { billingEmail: email }).then(res => {
      if (res.ok) {
        location.href = `/t/${teamId}/usage`
      } else {
        setLoading(false)
        setError("Failed to start trial")
      }
    })
  }
  return (
    <Modal show={show} onHide={onClose}>
      <Modal.Header closeButton>
        <Modal.Title>Start Trial</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Form
          onSubmit={(e: React.FormEvent) => {
            e.preventDefault()
            startTrial()
          }}>
          <Form.Group controlId="formBasicEmail">
            <Form.Label>Billing Email</Form.Label>
            <Form.Control
              type="email"
              placeholder="Enter email"
              required
              value={email}
              onChange={(x: React.ChangeEvent<HTMLInputElement>) =>
                setEmail(x.target.value)
              }
            />
            <Form.Text className="text-muted">
              We’ll send you billing reminders at this email address.
            </Form.Text>
          </Form.Group>
          <Button variant="primary" type="submit" disabled={loading}>
            {loading ? "Loading" : "Begin Trial"}
          </Button>
          {error && <Form.Text className="text-danger">{error}</Form.Text>}
          <Form.Text className="text-muted">
            Your trial will expire 14 days after start.
          </Form.Text>
        </Form>
      </Modal.Body>
    </Modal>
  )
}

interface ISubscriptionManagementModalProps {
  readonly show: boolean
  readonly onClose: () => void
  readonly seatUsage: number
}
function SubscriptionManagementModal({
  show,
  onClose,
  seatUsage,
}: ISubscriptionManagementModalProps) {
  const [email, setEmail] = React.useState("")
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState("")
  const teamId = useTeamId()
  function startTrial() {
    setLoading(true)
    setError("")
    teamApi(Current.api.startTrial, { billingEmail: email }).then(res => {
      setLoading(false)
      if (res.ok) {
        location.href = `/t/${teamId}/usage`
      } else {
        setError("Failed to start trial")
      }
    })
  }
  return (
    <Modal show={show} onHide={onClose}>
      <Modal.Header closeButton>
        <Modal.Title>Manage Subscription</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Form
          onSubmit={(e: React.FormEvent) => {
            e.preventDefault()
            startTrial()
          }}>
          <Form.Group controlId="formBasicEmail">
            <Form.Label>Billing Email</Form.Label>
            <Form.Control
              type="email"
              placeholder="Enter email"
              required
              value={email}
              onChange={(x: React.ChangeEvent<HTMLInputElement>) =>
                setEmail(x.target.value)
              }
            />
            <Form.Text className="text-muted">
              We’ll send you billing reminders at this email address.
            </Form.Text>
          </Form.Group>
          <Form.Group controlId="formBasicEmail">
            <Form.Label>Seats</Form.Label>
            <Form.Control
              type="number"
              required
              placeholder="Enter seat count"
            />
            <Form.Text className="text-muted">
              You have <b>{seatUsage}</b> active seats this billing period.
              Select at least <b>{seatUsage}</b> seats to continue service.
            </Form.Text>
          </Form.Group>

          <Button variant="primary" type="submit" disabled={loading}>
            {loading ? "Loading" : "Pay"}
          </Button>
          {error && <Form.Text className="text-danger">{error}</Form.Text>}
        </Form>
      </Modal.Body>
    </Modal>
  )
}

interface IStartDateProps {
  readonly date: string
}
function StartDate({ date }: IStartDateProps) {
  return <span>{formatDate(parseISO(date), "y-MM-d k:m") + " UTC"}</span>
}
interface IExpirationDateProps {
  readonly date: string
  readonly expired: boolean
}
function ExpirationDate({ date, expired }: IExpirationDateProps) {
  return (
    <span>
      {formatDate(parseISO(date), "y-MM-dd kk:mm") + " UTC"} (
      {formatFromNow(date) + (expired ? " expired" : "")})
    </span>
  )
}

interface ISubscriptionUpsellPromptProps {
  readonly trial: {
    readonly startDate: string
    readonly endDate: string
    readonly expired: boolean
    readonly startedBy: {
      readonly id: number
      readonly name: string
      readonly profileImgUrl: string
    }
  } | null
  readonly startSubscription: () => void
  readonly startTrial: () => void
}
function SubscriptionUpsellPrompt({
  trial,
  startSubscription,
  startTrial,
}: ISubscriptionUpsellPromptProps) {
  return (
    <Col className="d-flex justify-content-center">
      <div className="m-auto">
        <h4 className="h5">
          Subscribe and use Kodiak on your private repositories!
        </h4>
        {trial == null ? (
          <>
            <div className="d-flex justify-content-center">
              <Button variant="success" size="lg" onClick={startTrial}>
                Start 14 Day Trial
              </Button>
            </div>
            <p className="mb-0 text-center">or</p>
            <div className="d-flex justify-content-center">
              <Button variant="dark" onClick={startSubscription}>
                Subscribe
              </Button>
            </div>
          </>
        ) : (
          <div className="d-flex justify-content-center">
            <Button variant="success" size="lg" onClick={startSubscription}>
              Subscribe
            </Button>
          </div>
        )}
        <p className="text-center">($4.99 per active user per month)</p>

        {trial != null ? (
          <div className="d-flex justify-content-center">
            {!trial.expired ? (
              <p>
                Your active trial expires in{" "}
                <b>{formatFromNow(trial.endDate)}</b> at{" "}
                <b>
                  {formatDate(parseISO(trial.endDate), "y-MM-dd kk:mm") +
                    " UTC"}
                </b>
                .
              </p>
            ) : (
              <p>
                Your trial expired at{" "}
                <b>
                  {formatDate(parseISO(trial.endDate), "y-MM-dd kk:mm") +
                    " UTC"}
                </b>
                .
              </p>
            )}
          </div>
        ) : null}
      </div>
    </Col>
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
  readonly modifySubscription: () => void
}
function ActiveSubscription({
  seats,
  cost,
  billingEmail,
  nextBillingDate,
  modifySubscription,
}: IActiveSubscriptionProps) {
  return (
    <Col>
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
            ({formatCents(cost.perSeatCents)} / seat ⨉ {seats} seats)
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
          <Button variant="dark" size="sm" onClick={modifySubscription}>
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
    </Col>
  )
}

interface ISubscriptionProps {
  readonly subscription: {
    readonly seats: number
    readonly nextBillingDate: string
    readonly active: boolean
    readonly cost: {
      readonly totalCents: number
      readonly perSeatCents: number
    }
    readonly billingContact: {
      readonly email: string
    }
  } | null
  readonly startSubscription: () => void
  readonly startTrial: () => void
  readonly trial: {
    readonly startDate: string
    readonly endDate: string
    readonly expired: boolean
    readonly startedBy: {
      readonly id: number
      readonly name: string
      readonly profileImgUrl: string
    }
  } | null
}
function Subscription({
  subscription,
  startSubscription,
  startTrial,
  trial,
}: ISubscriptionProps) {
  const missingSubscription = !Boolean(subscription?.active)
  const missingTrial = !Boolean(trial?.active)
  return (
    <>
      <h3 className="h5">Subscription</h3>
      <div className="border border-primary rounded p-2 mb-4">
        <Row>
          {subscription?.active ? (
            <ActiveSubscription
              cost={subscription.cost}
              seats={subscription.seats}
              nextBillingDate={subscription.nextBillingDate}
              billingEmail={subscription.billingEmail}
            />
          ) : (
            <SubscriptionUpsellPrompt
              trial={trial}
              startSubscription={startSubscription}
              startTrial={startTrial}
            />
          )}
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
  const location = useLocation()
  const history = useHistory()
  const queryParams = new URLSearchParams(location.search)
  const showStartTrialModal = Boolean(queryParams.get("start_trial"))
  const showInstallCompleteModal = Boolean(queryParams.get("install_complete"))
  const showSubscriptionManagerModal = Boolean(
    queryParams.get("manage_subscription"),
  )
  function clearQueryString() {
    history.push(location.pathname)
  }
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

  function handleStartSubscription() {
    history.push(location.pathname + "?manage_subscription=1")
  }
  function handleStartTrial() {
    history.push(location.pathname + "?start_trial=1")
  }

  const subscriptionInfo = undefined
  return (
    <UsageAndBillingContainer>
      <p>
        <b> Period</b>
        <br />
        {oneMonthAgo} – {today}
      </p>
      <div className="mb-4">
        <InstallCompleteModal
          show={showInstallCompleteModal}
          onClose={clearQueryString}
        />
        <StartTrialModal
          show={showStartTrialModal}
          onClose={clearQueryString}
        />
        <SubscriptionManagementModal
          show={showSubscriptionManagerModal}
          onClose={clearQueryString}
          seatUsage={data.activeUsers.length}
        />
        <Subscription
          activeSubscription={subscriptionInfo}
          startSubscription={handleStartSubscription}
          startTrial={handleStartTrial}
          subscription={data.subscription}
          trial={data.trial}
        />

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
