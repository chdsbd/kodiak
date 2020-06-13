import React from "react"
import {
  Table,
  Row,
  Col,
  Popover,
  OverlayTrigger,
  Modal,
  Form,
  Card,
  Button,
  Tooltip,
} from "react-bootstrap"
import { Image } from "./Image"
import { WebData } from "../webdata"
import { Spinner } from "./Spinner"
import { Current } from "../world"
import { useTeamApi, teamApi } from "../useApi"
import formatDate from "date-fns/format"
import formatDistanceToNowStrict from "date-fns/formatDistanceToNowStrict"
import parseISO from "date-fns/parseISO"
import sub from "date-fns/sub"
import sortBy from "lodash/sortBy"
import { useLocation, useHistory, useParams } from "react-router-dom"
import { loadStripe } from "@stripe/stripe-js"
import * as settings from "../settings"
import debounce from "lodash/debounce"
import { GoLinkExternal } from "react-icons/go"

const DEFAULT_CURRENCY = "usd"

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
  readonly accountCanSubscribe: boolean
  readonly subscription: {
    readonly seats: number
    readonly nextBillingDate: string
    readonly expired: boolean
    readonly cost: {
      readonly totalCents: number
      readonly perSeatCents: number
      readonly currency: string
    }
    readonly billingEmail: string
    readonly cardInfo: string
  } | null
  readonly trial: {
    readonly startDate: string
    readonly endDate: string
    readonly expired: boolean
    readonly startedBy: {
      readonly id: string
      readonly name: string
      readonly profileImgUrl: string
    }
  } | null
  readonly activeUsers: ReadonlyArray<{
    readonly id: string
    readonly name: string
    readonly profileImgUrl: string
    readonly interactions: number
    readonly lastActiveDate: string
    readonly firstActiveDate?: string
    readonly hasSeatLicense?: boolean
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

function formatCents(cents: number, currency: string): string {
  const formatter = new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
  })
  return formatter.format(cents / 100)
}

function formatFromNow(dateString: string): string {
  return formatDistanceToNowStrict(parseISO(dateString))
}

function FormatDate({ date }: { date: string }) {
  return <>{formatDate(parseISO(date), "y-MM-dd kk:mm O")}</>
}

const formattedMonthlyCost = formatCents(settings.monthlyCost, DEFAULT_CURRENCY)

interface IInstallCompleteModalProps {
  readonly show: boolean
  readonly onClose: () => void
}
function InstallCompleteModal({ show, onClose }: IInstallCompleteModalProps) {
  return (
    <Modal show={show} onHide={onClose}>
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
  readonly teamId: string
  readonly onClose: () => void
}
function StartTrialModal({ show, onClose, teamId }: IStartTrialModalProps) {
  const [email, setEmail] = React.useState("")
  const [status, setStatus] = React.useState<
    { type: "initial" } | { type: "loading" } | { type: "error"; msg: string }
  >({ type: "initial" })
  function startTrial() {
    setStatus({ type: "loading" })
    teamApi(Current.api.startTrial, { billingEmail: email }).then(res => {
      if (res.ok) {
        // trigger full page reload
        location.href = `/t/${teamId}/usage?install_complete=1`
      } else {
        setStatus({ type: "error", msg: "Failed to start trial" })
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
            <Form.Label>Notification Email</Form.Label>
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
              We’ll send you trial reminders at this email address.
            </Form.Text>
          </Form.Group>
          <Button
            variant="primary"
            type="submit"
            disabled={status.type === "loading"}>
            {status.type === "loading" ? "Loading" : "Begin Trial"}
          </Button>
          {status.type === "error" && (
            <Form.Text className="text-danger">{status.msg}</Form.Text>
          )}
          <Form.Text className="text-muted">
            Your trial will expire 30 days after start.
          </Form.Text>
        </Form>
      </Modal.Body>
    </Modal>
  )
}

interface IStartSubscriptionModalProps {
  readonly show: boolean
  readonly onClose: () => void
  readonly seatUsage: number
}
function StartSubscriptionModal({
  show,
  onClose,
  seatUsage,
}: IStartSubscriptionModalProps) {
  const [seats, setSeats] = React.useState(seatUsage)
  const [status, setStatus] = React.useState<
    { type: "initial" } | { type: "loading" } | { type: "error"; msg: string }
  >({ type: "initial" })

  function setSubscription() {
    setStatus({ type: "loading" })

    teamApi(Current.api.startCheckout, {
      seatCount: seats,
    }).then(async res => {
      if (res.ok) {
        const stripe = await loadStripe(res.data.stripePublishableApiKey)
        if (stripe == null) {
          setStatus({ type: "error", msg: "Failed to load Stripe" })
          return
        }
        const { error } = await stripe.redirectToCheckout({
          sessionId: res.data.stripeCheckoutSessionId,
        })
        setStatus({
          type: "error",
          msg: error.message || "error redirecting to checkout",
        })
      } else {
        setStatus({
          type: "error",
          msg: "Failed to start checkout",
        })
      }
    })
  }
  const formatCost = (cents: number) => formatCents(cents, DEFAULT_CURRENCY)
  const costCents = seats * settings.monthlyCost
  const notEnoughSeats = seats < seatUsage && seatUsage > 0
  return (
    <Modal show={show} onHide={onClose}>
      <Modal.Header closeButton>
        <Modal.Title>Start Subscription</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Form
          onSubmit={(e: React.FormEvent) => {
            e.preventDefault()
            setSubscription()
          }}>
          <Form.Group controlId="formBasicEmail">
            <Form.Label>Seats</Form.Label>
            <Form.Control
              type="number"
              required
              min="1"
              placeholder="Enter seat count"
              value={String(seats)}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setSeats(Math.max(parseInt(e.target.value, 10) || 1, 1))
              }
            />
            {seatUsage > 0 && (
              <Form.Text className="text-muted">
                You have <b>{seatUsage}</b> active seats this billing period.{" "}
                <span className={notEnoughSeats ? "text-danger" : ""}>
                  Select at least <b>{seatUsage}</b> seats to continue service.
                </span>
              </Form.Text>
            )}
          </Form.Group>

          <Form.Group>
            <Form.Label>Due Today</Form.Label>
            <Form.Control
              type="text"
              required
              disabled
              value={formatCost(costCents)}
            />
            <Form.Text className="text-muted">
              Billed monthly. <b>{seats} seat(s) </b>
              at <b>{formatCost(settings.monthlyCost)}/seat</b>.{" "}
            </Form.Text>
          </Form.Group>
          <Button
            variant="primary"
            type="submit"
            block
            disabled={status.type === "loading" || notEnoughSeats}>
            {status.type === "loading" ? "Loading" : "Continue to Payment"}
          </Button>
          {notEnoughSeats && (
            <Form.Text className="text-danger">
              Select at least <b>{seatUsage}</b> seats.
            </Form.Text>
          )}
          <Form.Text className="text-muted">
            Kodiak uses Stripe.com to securely handle payments.
          </Form.Text>
          {status.type === "error" && (
            <Form.Text className="text-danger">{status.msg}</Form.Text>
          )}
        </Form>
      </Modal.Body>
    </Modal>
  )
}

type IProrationAmount =
  | { kind: "loading" }
  | { kind: "failed" }
  | { kind: "success"; cost: number }

interface IManageSubscriptionModalProps {
  readonly show: boolean
  readonly onClose: (props?: { reload?: boolean }) => void
  readonly seatUsage: number
  readonly currentSeats: number
  readonly billingEmail: string
  readonly cardInfo: string
  readonly cost: {
    readonly totalCents: number
    readonly perSeatCents: number
    readonly currency: string
  }
}
function ManageSubscriptionModal({
  show,
  onClose,
  seatUsage,
  cost,
  billingEmail,
  cardInfo,
  currentSeats,
}: IManageSubscriptionModalProps) {
  const [seats, setSeats] = React.useState(currentSeats)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState("")
  const [prorationAmount, setProrationAmount] = React.useState<
    IProrationAmount
  >({ kind: "loading" })
  const [prorationTimestamp, setProrationTimestamp] = React.useState(0)
  const seatsRef = React.useRef(0)

  const formatCost = (cents: number) => formatCents(cents, cost.currency)

  React.useEffect(() => {
    seatsRef.current = seats
  }, [seats])

  function setSubscription() {
    setLoading(true)
    setError("")
    teamApi(Current.api.updateSubscription, {
      seats,
      prorationTimestamp,
    }).then(res => {
      if (res.ok) {
        // trigger page refresh.
        location.search = ""
      } else {
        setError("failed to update plan")
      }
      setLoading(false)
    })
  }

  function cancelSubscription() {
    const res = prompt(
      "Please enter 'cancel subscription' to cancel your subscription.",
    )
    if (
      res == null ||
      res.toLowerCase().replace(/\s/g, "") !== "cancelsubscription"
    ) {
      return
    }
    teamApi(Current.api.cancelSubscription).then(res => {
      if (res.ok) {
        onClose({ reload: true })
        alert("subscription canceled")
        location.search = ""
      } else {
        alert("failed to cancel subscription")
      }
    })
  }

  const fetchProrationDebounced = React.useCallback(
    debounce(() => {
      setProrationAmount({ kind: "loading" })
      teamApi(Current.api.fetchProration, {
        subscriptionQuantity: seatsRef.current,
      }).then(res => {
        if (res.ok) {
          setProrationAmount({ kind: "success", cost: res.data.proratedCost })
          setProrationTimestamp(res.data.prorationTime)
        } else {
          setProrationAmount({ kind: "failed" })
        }
      })
    }, 250),
    [],
  )

  React.useEffect(() => {
    if (show) {
      fetchProrationDebounced()
    }
  }, [show, fetchProrationDebounced, seats])

  function formatProration(x: IProrationAmount) {
    if (x.kind === "loading" || x.kind === "failed") {
      return "--"
    }
    if (x.kind === "success") {
      if (x.cost > 0) {
        return formatCost(x.cost)
      }
      return `account credit of ${formatCost(-x.cost)}`
    }
    return "--"
  }

  function updateBillingInfo() {
    teamApi(Current.api.modifyBilling).then(async res => {
      if (res.ok) {
        const stripe = await loadStripe(res.data.stripePublishableApiKey)
        if (stripe == null) {
          setError("Failed to load Stripe")
          return
        }
        const { error } = await stripe.redirectToCheckout({
          sessionId: res.data.stripeCheckoutSessionId,
        })
        if (error) {
          setError("Problem updating billing info")
        }
      } else {
        setError("Problem updating billing info")
      }
    })
  }

  const costCents = seats * cost.perSeatCents
  return (
    <Modal show={show} onHide={() => onClose()}>
      <Modal.Header closeButton>
        <Modal.Title>Manage Subscription</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Form
          onSubmit={(e: React.FormEvent) => {
            e.preventDefault()
            setSubscription()
          }}>
          <Form.Group controlId="formBasicEmail">
            <Form.Label>Seats</Form.Label>
            <Form.Control
              type="number"
              required
              min="1"
              placeholder="Enter seat count"
              value={String(seats)}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                setSeats(Math.max(parseInt(e.target.value, 10) || 1, 1))
              }}
            />
            {seatUsage > 0 && (
              <Form.Text className="text-muted">
                You have <b>{seatUsage}</b> active seats this billing period.
                Select at least <b>{seatUsage}</b> seats to continue service.
              </Form.Text>
            )}
            <Form.Text className="text-muted">
              Your current plan costs <b>{formatCost(cost.totalCents)}/month</b>{" "}
              for <b>{currentSeats} seat(s)</b> at{" "}
              <b>{formatCost(cost.perSeatCents)}/seat</b>.
            </Form.Text>
          </Form.Group>
          <Form.Group>
            <Form.Label>Billing Email </Form.Label>
            <Form.Control type="text" required disabled value={billingEmail} />
            <Form.Text className="text-muted">
              <a href="#" onClick={updateBillingInfo}>
                update
              </a>
            </Form.Text>
          </Form.Group>
          <Form.Group>
            <Form.Label>Payment Method </Form.Label>
            <Form.Control type="text" required disabled value={cardInfo} />
            <Form.Text className="text-muted">
              <a href="#" onClick={updateBillingInfo}>
                update
              </a>
            </Form.Text>
          </Form.Group>
          <Form.Group>
            <Form.Label>Due Today</Form.Label>
            <Form.Control
              type="text"
              required
              disabled
              value={
                seats === currentSeats || prorationAmount.kind !== "success"
                  ? "--"
                  : formatProration(prorationAmount)
              }
            />
            {seats !== currentSeats && prorationAmount.kind === "success" ? (
              <Form.Text className="text-muted">
                Includes prorations. Renews monthly at{" "}
                <b>{formatCost(costCents)}</b> for <b>{seats} seat(s) </b>
                at <b>{formatCost(cost.perSeatCents)}/seat</b>.{" "}
              </Form.Text>
            ) : null}
          </Form.Group>
          <Button
            variant="primary"
            type="submit"
            block
            disabled={
              loading ||
              prorationAmount.kind !== "success" ||
              seats === currentSeats
            }>
            {seats === currentSeats
              ? "first modify your seat count..."
              : prorationAmount.kind === "success"
              ? prorationAmount.cost > 0
                ? `Update Plan for ${formatCost(prorationAmount.cost)}`
                : "Update Plan"
              : "loading..."}
          </Button>
          {error && <Form.Text className="text-danger">{error}</Form.Text>}
        </Form>
        <hr />
        <Button
          variant="outline-danger"
          type="button"
          size="sm"
          onClick={cancelSubscription}>
          Cancel Subscription
        </Button>
      </Modal.Body>
    </Modal>
  )
}

function Plan({
  className,
  name,
  cost,
  features,
  startButton,
  highlight,
}: {
  className?: string
  name: React.ReactNode
  cost: React.ReactNode
  features: React.ReactNodeArray
  startButton: React.ReactNode
  highlight?: boolean
}) {
  return (
    <Card
      className={
        "shadow-sm h-100 " + className + (highlight ? " shadow " : "")
      }>
      <Card.Header>
        <h4 className="text-center">{name}</h4>
      </Card.Header>
      <Card.Body className="d-flex flex-column">
        <h1 className="text-center">{cost}</h1>
        <div className="flex-grow-1 d-flex flex-column">
          <ul className="flex-grow-1 list-unstyled mt-3 mb-4 text-center">
            {features.map(x => (
              <li>{x}</li>
            ))}
          </ul>
          {startButton}
        </div>
      </Card.Body>
    </Card>
  )
}

const KodiakTooltip = ({
  children,
  content,
}: {
  children: React.ReactNode
  content: React.ReactNode
}) => (
  <OverlayTrigger overlay={<Tooltip id="kodiak-tooltip">{content}</Tooltip>}>
    {children}
  </OverlayTrigger>
)

interface ISubscriptionUpsellPromptProps {
  readonly trial: {
    readonly endDate: string
    readonly expired: boolean
  } | null
  readonly startSubscription: () => void
  readonly startTrial: () => void
}
function SubscriptionUpsellPrompt({
  trial,
  startSubscription,
  startTrial,
}: ISubscriptionUpsellPromptProps) {
  const plans = [
    {
      name: "30 Day Trial",
      cost: "Free",
      highlight: trial == null,
      features: [
        "Public & private repositories",
        "Unlimited users for 30 days",
        "No credit card required",
      ],
      startButton:
        trial == null ? (
          <Button block variant="success" onClick={startTrial}>
            Start 30 Day Trial
          </Button>
        ) : trial.expired ? (
          <>
            <p className="text-center">
              Your active trial has <b>expired</b>.
            </p>
            <Button block variant="dark" disabled>
              Trial Expired
            </Button>
          </>
        ) : (
          <>
            <p className="text-center">
              Your active trial expires in{" "}
              <KodiakTooltip content={<FormatDate date={trial.endDate} />}>
                <u>
                  <b>{formatFromNow(trial.endDate)}</b>
                </u>
              </KodiakTooltip>
              .
            </p>
            <Button block variant="dark" disabled>
              Trial Started
            </Button>
          </>
        ),
    },
    {
      name: "Professional",
      highlight: trial != null,
      cost: (
        <>
          $4.99 <small className="text-muted">/ seat</small>
        </>
      ),
      features: [
        "Public & private repositories",
        "Access priority support",
        "Support Kodiak's development",
      ],
      startButton: (
        <Button
          block
          variant={trial != null ? "success" : "dark"}
          onClick={startSubscription}>
          Subscribe
        </Button>
      ),
    },
    {
      name: "Enterprise",
      highlight: false,
      cost: "Custom Pricing",
      features: [
        "Public & private repositories",
        "Access priority support",
        "Hands-on onboarding",
        "Annual invoicing",
      ],
      startButton: (
        <a
          className="btn btn-block btn-dark text-decoration-none"
          href="mailto:support@kodiakhq.com?subject=enterprise%20plan">
          Contact Us
        </a>
      ),
    },
  ]
  return (
    <>
      <Row>
        <Col>
          <h3 className="text-center">Plans</h3>
        </Col>
      </Row>
      <Row>
        {plans.map(x => (
          <Col lg={4} className="mx-auto mb-2">
            <Plan
              name={x.name}
              highlight={x.highlight}
              cost={x.cost}
              features={x.features}
              startButton={x.startButton}
            />
          </Col>
        ))}
      </Row>
    </>
  )
}

function Subcription({
  subscription,
  teamId,
  modifySubscription,
}: {
  readonly subscription: {
    readonly seats: number
    readonly nextBillingDate: string
    readonly expired: boolean
    readonly cost: {
      readonly totalCents: number
      readonly perSeatCents: number
      readonly currency: string
    }
    readonly billingEmail: string
  }
  readonly modifySubscription: () => void
  readonly teamId: string
}) {
  return (
    <Row>
      <Col lg={8}>
        <Card className="mb-4">
          <Card.Body>
            <Card.Title className="d-flex align-items-baseline justify-content-between">
              <span>Subscription</span>
              <small>
                <a href={settings.billingDocsUrl}>billing docs</a>
              </small>
            </Card.Title>
            <Form.Group>
              <Form.Label>Seats</Form.Label>
              <p className="mb-0">{subscription.seats} seats</p>
              <Form.Text className="text-muted">
                An active user consumes one seat per billing period.
              </Form.Text>
            </Form.Group>
            <Form.Group>
              <Form.Label>Next Billing Date</Form.Label>
              <p>
                <FormatDate date={subscription.nextBillingDate} />
              </p>
            </Form.Group>
            <Form.Group>
              <Form.Label>Cost</Form.Label>
              <p>
                {subscription.seats} seats ⨉{" "}
                {formatCents(
                  subscription.cost.perSeatCents,
                  subscription.cost.currency,
                )}{" "}
                / seat ={" "}
                {formatCents(
                  subscription.cost.totalCents,
                  subscription.cost.currency,
                )}
              </p>
            </Form.Group>
            <Form.Group>
              <Form.Label>Billing History</Form.Label>
              <p>
                <a href={settings.getStripeSelfServeUrl(teamId)}>
                  view billing history
                  <GoLinkExternal className="pl-1" />
                </a>
              </p>
            </Form.Group>
            <Button variant="dark" size="sm" onClick={modifySubscription}>
              Modify Subscription
            </Button>
            <p className="small mb-0 mt-2">
              Send us an email at{" "}
              <a href="mailto:support@kodiakhq.com">support@kodiakhq.com</a> if
              you need any assistance.
            </p>

            <hr />
            <BillingDocumentation
              subscriptionInfo
              trialInfo={false}
              pricingInfo
            />
          </Card.Body>
        </Card>
      </Col>
    </Row>
  )
}

function SubscriptionTrialStarter({
  startSubscription,
  startTrial,
  trial,
}: {
  readonly startSubscription: () => void
  readonly startTrial: () => void
  readonly trial: ISubscriptionUpsellPromptProps["trial"]
}) {
  return (
    <Row>
      <Col className="mx-auto">
        <Card className="mb-4">
          <Card.Body>
            <Card.Title className="d-flex align-items-baseline justify-content-between">
              <span>Subscription</span>
              <small>
                <a href={settings.billingDocsUrl}>billing docs</a>
              </small>
            </Card.Title>
            <SubscriptionUpsellPrompt
              trial={trial}
              startSubscription={startSubscription}
              startTrial={startTrial}
            />

            <hr />
            <BillingDocumentation pricingInfo subscriptionInfo trialInfo />
          </Card.Body>
        </Card>
      </Col>
    </Row>
  )
}

function BillingDocumentation({
  subscriptionInfo,
  trialInfo,
  pricingInfo,
}: {
  readonly subscriptionInfo: boolean
  readonly trialInfo: boolean
  readonly pricingInfo: boolean
}) {
  return (
    <>
      {subscriptionInfo && (
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
      )}
      {trialInfo && (
        <Row>
          <Col>
            <b>Trial</b>
            <p>
              The 30-day trial is free and allows for using Kodiak on private
              repos with an unlimited number of users. After 30-days you can
              subscribe to continue using Kodiak on private repositories.
            </p>
          </Col>
        </Row>
      )}
      {pricingInfo && (
        <Row>
          <Col>
            <b>Pricing</b>
            <p>
              Kodiak is {formattedMonthlyCost} per active user per month. An
              active user is anyone that opens a GitHub pull request that Kodiak
              updates, approves, or merges.
            </p>
          </Col>
        </Row>
      )}
    </>
  )
}

function UsageBillingPageInner(props: IUsageBillingPageInnerProps) {
  const location = useLocation()
  const history = useHistory()
  const params = useParams<{ readonly team_id: string }>()
  const teamId = params.team_id
  const queryParams = new URLSearchParams(location.search)
  const showStartTrialModal = Boolean(queryParams.get("start_trial"))
  const showInstallCompleteModal = Boolean(queryParams.get("install_complete"))
  const showSubscriptionManagerModal = Boolean(
    queryParams.get("start_subscription"),
  )
  const showSubscriptionModifyModal = Boolean(
    queryParams.get("modify_subscription"),
  )
  function clearQueryString() {
    history.push({ search: "" })
  }
  if (props.data.status === "loading") {
    return <Loading />
  }

  if (props.data.status === "failure") {
    return <Failure />
  }

  const data = props.data.data

  const dateToday = new Date()
  const today = formatDate(dateToday, "MMM do")
  const dateOneMonthAgo = sub(dateToday, { months: 1 })
  const oneMonthAgo = formatDate(dateOneMonthAgo, "MMM do")

  function handleStartSubscription() {
    history.push({ search: "start_subscription=1" })
  }
  function handleStartTrial() {
    history.push({ search: "start_trial=1" })
  }
  function modifySubscription() {
    history.push({ search: "modify_subscription=1" })
  }

  return (
    <UsageAndBillingContainer>
      <div className="mb-4">
        <InstallCompleteModal
          show={showInstallCompleteModal}
          onClose={clearQueryString}
        />
        <StartTrialModal
          show={showStartTrialModal}
          onClose={clearQueryString}
          teamId={teamId}
        />
        <StartSubscriptionModal
          show={showSubscriptionManagerModal}
          onClose={clearQueryString}
          seatUsage={data.activeUsers.length}
        />
        {data.subscription != null ? (
          <>
            <ManageSubscriptionModal
              show={showSubscriptionModifyModal}
              currentSeats={data.subscription.seats}
              seatUsage={data.activeUsers.length}
              billingEmail={data.subscription.billingEmail}
              cardInfo={data.subscription.cardInfo}
              cost={data.subscription.cost}
              onClose={x => {
                if (x?.reload) {
                  location.search = ""
                } else {
                  clearQueryString()
                }
              }}
            />
          </>
        ) : null}
        {data.accountCanSubscribe ? (
          <>
            {data.subscription == null ? (
              <SubscriptionTrialStarter
                startSubscription={handleStartSubscription}
                startTrial={handleStartTrial}
                trial={data.trial}
              />
            ) : (
              <Subcription
                subscription={data.subscription}
                teamId={teamId}
                modifySubscription={modifySubscription}
              />
            )}
          </>
        ) : (
          <Row>
            <Col>
              <p className="text-center">
                Kodiak is free for personal GitHub accounts.
                <br />
                Organizations can subscribe to use Kodiak on private
                repositories.
              </p>
            </Col>
          </Row>
        )}

        <Row>
          <Col>
            <Card className="mb-4">
              <Card.Body>
                <Card.Title className="d-flex align-items-baseline justify-content-between">
                  <span>Usage</span>
                  <small>
                    {oneMonthAgo} – {today}
                  </small>
                </Card.Title>

                <Form.Group>
                  <Form.Label>Active Users</Form.Label>
                  <p className="mb-0">
                    {data.activeUsers.length} / {data.subscription?.seats ?? 0}{" "}
                    seats
                  </p>

                  <Form.Text className="text-muted">
                    Active users are only counted for private repositories.
                    Public repositories are free.
                  </Form.Text>
                </Form.Group>

                <Table size="sm" className="mt-2">
                  <thead>
                    <tr>
                      <th>User</th>
                      <th>
                        Days Active{" "}
                        <Question
                          content={
                            "This user opened a GitHub pull request that Kodiak updated, approved, or merged."
                          }
                        />
                      </th>
                      <th>First Active Date</th>
                      <th>Last Active Date</th>
                      <th>
                        Has Seat{" "}
                        <Question
                          content={
                            "An active user occupies a seat. If all seats are occupied, you must upgrade to add more users."
                          }
                        />
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortBy(data.activeUsers, x => x.name.toLowerCase()).map(
                      u => (
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
                          <td>{u.firstActiveDate}</td>
                          <td>{u.lastActiveDate}</td>
                          <td>{u.hasSeatLicense ? "Yes" : "No"}</td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </Table>
              </Card.Body>
            </Card>
          </Col>
        </Row>
      </div>
    </UsageAndBillingContainer>
  )
}
