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
import { useTeamApi, teamApi, useTeamApiMutation } from "../useApi"
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
const MONTHLY_COST = formatCents(settings.monthlyCost, DEFAULT_CURRENCY)
const ANNUAL_COST = formatCents(settings.annualCost, DEFAULT_CURRENCY)

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
      readonly planInterval: "month" | "year"
    }
    readonly billingEmail: string
    readonly customerName?: string
    readonly customerAddress?: {
      readonly line1?: string
      readonly city?: string
      readonly country?: string
      readonly line2?: string
      readonly postalCode?: string
      readonly state?: string
    }
    readonly cardInfo: string
    readonly viewerIsOrgOwner: boolean
    readonly viewerCanModify: boolean
    readonly limitBillingAccessToOwners: boolean
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
  readonly subscriptionExemption: {
    readonly message: string | null
  } | null
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

function formatPeriod(period: "month" | "year"): "monthly" | "annually" {
  switch (period) {
    case "year": {
      return "annually"
    }
    case "month": {
      return "monthly"
    }
  }
}

function formatFromNow(dateString: string): string {
  return formatDistanceToNowStrict(parseISO(dateString))
}

function FormatDate({ date }: { date: string }) {
  return <>{formatDate(parseISO(date), "y-MM-dd kk:mm O")}</>
}

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
  const [period, setPeriod] = React.useState<"month" | "year">("month")
  const [status, setStatus] = React.useState<
    { type: "initial" } | { type: "loading" } | { type: "error"; msg: string }
  >({ type: "initial" })

  // fetch the selected subscription period from the url params and use that as
  // the default period.
  const location = useLocation()
  const queryParams = new URLSearchParams(location.search)
  const subscriptionPeriod: string | null = queryParams.get("period")
  React.useEffect(() => {
    if (subscriptionPeriod === "month") {
      setPeriod("month")
    }
    if (subscriptionPeriod === "year") {
      setPeriod("year")
    }
  }, [show, subscriptionPeriod])

  function setSubscription() {
    setStatus({ type: "loading" })

    teamApi(Current.api.startCheckout, {
      seatCount: seats,
      planPeriod: period,
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
  const seatCost =
    period === "year" ? settings.annualCost : settings.monthlyCost
  const costCents = seats * seatCost
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
            <Form.Label>Plan Period</Form.Label>

            <Form.Check
              type="radio"
              id="monthly-plan-sub"
              checked={period === "month"}
              onChange={() => setPeriod("month")}
              label={`Monthly – ${MONTHLY_COST} / seat`}
            />

            <Form.Check
              type="radio"
              id="annual-plan-sub"
              checked={period === "year"}
              onChange={() => setPeriod("year")}
              label={`Annually – ${ANNUAL_COST} / seat`}
            />
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
              Billed {formatPeriod(period)}. <b>{seats} seat(s) </b>
              at <b>{formatCost(seatCost)}/seat</b>.{" "}
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
    readonly planInterval: "month" | "year"
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
  const [creatingSubscription, setCreatingSubscription] = React.useState(false)
  const [error, setError] = React.useState("")
  const [prorationAmount, setProrationAmount] = React.useState<
    IProrationAmount
  >({ kind: "loading" })
  const [prorationTimestamp, setProrationTimestamp] = React.useState(0)
  const [subscriptionPeriod, setSubscriptionPeriod] = React.useState<
    "month" | "year"
  >(cost.planInterval)
  const seatsRef = React.useRef(0)
  const subscriptionPeriodRef = React.useRef<"month" | "year">("month")

  const formatCost = (cents: number) => formatCents(cents, DEFAULT_CURRENCY)

  React.useEffect(() => {
    seatsRef.current = seats
  }, [seats])
  React.useEffect(() => {
    subscriptionPeriodRef.current = subscriptionPeriod
  }, [subscriptionPeriod])

  function setSubscription() {
    setCreatingSubscription(true)
    setError("")
    teamApi(Current.api.updateSubscription, {
      seats,
      prorationTimestamp,
      planPeriod: subscriptionPeriod,
    }).then(res => {
      if (res.ok) {
        // trigger page refresh.
        location.search = ""
      } else {
        setError("failed to update plan")
      }
      setCreatingSubscription(false)
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
        subscriptionPeriod: subscriptionPeriodRef.current,
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
  }, [show, fetchProrationDebounced, seats, subscriptionPeriod])

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

  const perSeatCents =
    subscriptionPeriod === "year" ? settings.annualCost : settings.monthlyCost

  const costCents = seats * perSeatCents
  const subscriptionUnchanged =
    seats === currentSeats && subscriptionPeriod === cost.planInterval
  return (
    <Modal show={show} onHide={() => onClose()}>
      <Modal.Header closeButton>
        <Modal.Title>Manage Subscription</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Form
          onSubmit={(e: React.FormEvent) => {
            e.preventDefault()
            if (creatingSubscription) {
              return
            }
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
              Your current plan costs{" "}
              <b>
                {formatCost(cost.totalCents)}/{cost.planInterval}
              </b>{" "}
              for <b>{currentSeats} seat(s)</b> at{" "}
              <b>{formatCost(cost.perSeatCents)}/seat</b>.
            </Form.Text>
          </Form.Group>

          <Form.Group controlId="formBasicEmail">
            <Form.Label>Plan Period</Form.Label>
            <Form.Check
              type="radio"
              id="monthly-sub-editor"
              label="Monthly"
              checked={subscriptionPeriod === "month"}
              onChange={() => setSubscriptionPeriod("month")}
            />
            <Form.Check
              type="radio"
              id="annually-sub-editor"
              label="Annually"
              checked={subscriptionPeriod === "year"}
              onChange={() => setSubscriptionPeriod("year")}
            />
          </Form.Group>
          <Form.Group>
            <Form.Label>Billing Email </Form.Label>
            <Form.Control type="text" required disabled value={billingEmail} />
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
                subscriptionUnchanged || prorationAmount.kind !== "success"
                  ? "--"
                  : formatProration(prorationAmount)
              }
            />
            {!subscriptionUnchanged && prorationAmount.kind === "success" ? (
              <Form.Text className="text-muted">
                Includes prorations. Renews {formatPeriod(subscriptionPeriod)}{" "}
                at <b>{formatCost(costCents)}</b> for <b>{seats} seat(s) </b>
                at <b>{formatCost(perSeatCents)}/seat</b>.{" "}
              </Form.Text>
            ) : null}
          </Form.Group>
          <Button
            variant="primary"
            type="submit"
            block
            disabled={
              creatingSubscription ||
              prorationAmount.kind !== "success" ||
              subscriptionUnchanged
            }>
            {subscriptionUnchanged
              ? "first modify your subscription..."
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
  readonly className?: string
  readonly name: React.ReactNode
  readonly cost: React.ReactNode
  readonly features: ReadonlyArray<string>
  readonly startButton: React.ReactNode
  readonly highlight?: boolean
}) {
  return (
    <Card className={"shadow-sm  " + className + (highlight ? " shadow " : "")}>
      <Card.Header>
        <h4 className="text-center">{name}</h4>
      </Card.Header>
      <Card.Body>
        {cost}
        <div>
          <ul className="list-unstyled mt-3 mb-4 text-center">
            {features.map(x => (
              <li key={x}>{x}</li>
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
  readonly children: React.ReactNode
  readonly content: React.ReactNode
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
  readonly startSubscription: (params: { period: "month" | "year" }) => void
  readonly startTrial: () => void
}
function SubscriptionUpsellPrompt({
  trial,
  startSubscription,
  startTrial,
}: ISubscriptionUpsellPromptProps) {
  const [period, setPeriod] = React.useState<"month" | "year">("month")
  const price = period === "year" ? ANNUAL_COST : MONTHLY_COST
  const plans = [
    {
      name: "30 Day Trial",
      cost: <h1 className="text-center">Free</h1>,
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
            <Button block variant="dark" disabled>
              Trial Expired
            </Button>
            <p className="text-center mt-2 mb-0">
              Your active trial has <b>expired</b>.
            </p>
          </>
        ) : (
          <>
            <Button block variant="dark" disabled>
              Trial Started
            </Button>
            <p className="text-center mt-2 mb-0">
              Your active trial expires in{" "}
              <KodiakTooltip content={<FormatDate date={trial.endDate} />}>
                <u>
                  <b>{formatFromNow(trial.endDate)}</b>
                </u>
              </KodiakTooltip>
              .
            </p>
          </>
        ),
    },
    {
      name: "Professional",
      highlight: trial != null,
      cost: (
        <div className="text-center">
          <h1>
            {price} <small className="text-muted">/ seat</small>
          </h1>
          <div>
            <Form.Check
              type="radio"
              id="monthly-plan"
              inline
              checked={period === "month"}
              onChange={() => setPeriod("month")}
              label={"Monthly"}
            />

            <Form.Check
              type="radio"
              id="annual-plan"
              inline
              checked={period === "year"}
              onChange={() => setPeriod("year")}
              label={"Annually"}
            />
          </div>
          <i>Two months free with annual plan</i>
        </div>
      ),
      features: ["Public & private repositories", "Access priority support"],
      startButton: (
        <Button
          block
          variant={trial != null ? "success" : "dark"}
          onClick={() => startSubscription({ period })}>
          Subscribe
        </Button>
      ),
    },
    {
      name: "Enterprise",
      highlight: false,
      cost: <h1 className="text-center">Custom Pricing</h1>,
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
        {plans.map(x => (
          <Col key={x.name} lg={4} className="mx-auto mb-2">
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

function KodiakSaveButton({
  state,
  disabled,
}: {
  state: WebData<unknown>
  disabled?: boolean
}) {
  const loading = state.status === "loading"
  return (
    <>
      <Button
        variant="dark"
        size="sm"
        disabled={loading || disabled}
        type="submit">
        {loading ? "Loading..." : "Save"}
      </Button>
      {state.status === "failure" && (
        <Form.Text className="text-danger">Save failed</Form.Text>
      )}
      {disabled && (
        <Form.Text className="text-muted">
          You must be an organization owner to modify this field.
        </Form.Text>
      )}
    </>
  )
}

function BillingEmailForm({
  defaultValue,
  className,
  disabled,
}: {
  readonly defaultValue: string
  readonly className?: string
  readonly disabled: boolean
}) {
  const [billingEmail, setBillingEmail] = React.useState(defaultValue)
  const [apiState, updateStripeCustomerInfo] = useTeamApiMutation(
    Current.api.updateStripeCustomerInfo,
  )
  function handleSubmit(e: React.ChangeEvent<HTMLFormElement>) {
    e.preventDefault()
    if (disabled) {
      return
    }
    updateStripeCustomerInfo({ email: billingEmail })
  }
  return (
    <Card className={className}>
      <Card.Body>
        <Card.Title>Billing Email</Card.Title>
        <Form onSubmit={handleSubmit}>
          <Form.Group>
            <Form.Control
              type="email"
              required
              value={billingEmail}
              disabled={disabled}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setBillingEmail(e.target.value)
              }
            />
            <Form.Text className="text-muted">
              <b>Required</b>. Address to send billing receipts.
            </Form.Text>
          </Form.Group>
          <KodiakSaveButton state={apiState} disabled={disabled} />
        </Form>
      </Card.Body>
    </Card>
  )
}

function CompanyNameForm({
  defaultValue,
  className,
  disabled,
}: {
  readonly defaultValue: string
  readonly className?: string
  readonly disabled: boolean
}) {
  const [companyName, setCompanyName] = React.useState(defaultValue)
  const [apiState, updateStripeCustomerInfo] = useTeamApiMutation(
    Current.api.updateStripeCustomerInfo,
  )
  function handleSubmit(e: React.ChangeEvent<HTMLFormElement>) {
    e.preventDefault()
    if (disabled) {
      return
    }
    updateStripeCustomerInfo({ name: companyName })
  }
  return (
    <Card className={className}>
      <Card.Body>
        <Card.Title>Company Name</Card.Title>
        <Form onSubmit={handleSubmit}>
          <Form.Group>
            <Form.Control
              type="text"
              value={companyName}
              disabled={disabled}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setCompanyName(e.target.value)
              }
            />
            <Form.Text className="text-muted">
              Added to billing receipts if provided.
            </Form.Text>
          </Form.Group>
          <KodiakSaveButton state={apiState} disabled={disabled} />
        </Form>
      </Card.Body>
    </Card>
  )
}

function PostalAddressForm({
  defaultValue = {},
  disabled,
  className,
}: {
  readonly defaultValue: {
    readonly line1?: string
    readonly line2?: string
    readonly city?: string
    readonly state?: string
    readonly postalCode?: string
    readonly country?: string
  }
  readonly disabled?: boolean
  readonly className?: string
}) {
  const [line1, setLine1] = React.useState(defaultValue.line1 ?? "")
  const [line2, setLine2] = React.useState(defaultValue.line2 ?? "")
  const [city, setCity] = React.useState(defaultValue.city ?? "")
  const [state, setState] = React.useState(defaultValue.state ?? "")
  const [postalCode, setPostalCode] = React.useState(
    defaultValue.postalCode ?? "",
  )
  const [country, setCountry] = React.useState(defaultValue.country ?? "")

  const [apiState, updateStripeCustomerInfo] = useTeamApiMutation(
    Current.api.updateStripeCustomerInfo,
  )
  function handleSubmit(e: React.ChangeEvent<HTMLFormElement>) {
    e.preventDefault()
    if (disabled) {
      return
    }
    updateStripeCustomerInfo({
      address: { line1, line2, city, state, postalCode, country },
    })
  }
  return (
    <Card className={className}>
      <Card.Body>
        <Card.Title>Postal Address</Card.Title>
        <Form onSubmit={handleSubmit}>
          <Form.Group>
            <Form.Control
              type="text"
              placeholder="Address line 1"
              value={line1}
              disabled={disabled}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setLine1(e.target.value)
              }
            />
          </Form.Group>
          <Form.Group>
            <Form.Control
              type="text"
              placeholder="Address line 2"
              value={line2}
              disabled={disabled}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setLine2(e.target.value)
              }
            />
          </Form.Group>
          <Form.Group>
            <Form.Control
              type="text"
              placeholder="City"
              value={city}
              disabled={disabled}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setCity(e.target.value)
              }
            />
          </Form.Group>
          <Form.Group>
            <Form.Row>
              <Col>
                <Form.Control
                  type="text"
                  placeholder="State / Province / Region"
                  value={state}
                  disabled={disabled}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    setState(e.target.value)
                  }
                />
              </Col>
              <Col>
                <Form.Control
                  type="text"
                  placeholder="ZIP / Postal Code"
                  value={postalCode}
                  disabled={disabled}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    setPostalCode(e.target.value)
                  }
                />
              </Col>
            </Form.Row>
          </Form.Group>
          <Form.Group>
            <Form.Control
              type="text"
              placeholder="Country"
              value={country}
              disabled={disabled}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setCountry(e.target.value)
              }
            />
            <Form.Text className="text-muted">
              Added to billing receipts if provided.
            </Form.Text>
          </Form.Group>
          <KodiakSaveButton state={apiState} disabled={disabled} />
        </Form>
      </Card.Body>
    </Card>
  )
}

function LimitBillingAccessForm({
  defaultValue = false,
  className,
  canEdit,
}: {
  readonly defaultValue: boolean
  readonly className?: string
  readonly canEdit?: boolean
}) {
  const [
    limitBillingAccessToOwners,
    setLimitBillingAccessToOwners,
  ] = React.useState(defaultValue)
  const [apiState, updateStripeCustomerInfo] = useTeamApiMutation(
    Current.api.updateStripeCustomerInfo,
  )
  const formDisabled = !canEdit
  function handleSubmit(e: React.ChangeEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!canEdit) {
      return
    }
    updateStripeCustomerInfo({
      limitBillingAccessToOwners,
    })
  }
  return (
    <Card className={className}>
      <Card.Body>
        <Card.Title>Billing Permissions</Card.Title>
        <Form onSubmit={handleSubmit}>
          <Form.Group>
            <Form.Check
              label="Limit billing modifications to GitHub Organization Owners"
              id="limit-billing-access-to-owners"
              disabled={formDisabled}
              checked={limitBillingAccessToOwners}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setLimitBillingAccessToOwners(e.target.checked)
              }
            />
            <Form.Text className="text-muted">
              When enabled, only{" "}
              <a href="https://help.github.com/en/github/setting-up-and-managing-organizations-and-teams/permission-levels-for-an-organization#permission-levels-for-an-organization">
                GitHub Organization Owners
              </a>{" "}
              can modify the subscription or update billing information.
            </Form.Text>
          </Form.Group>
          <KodiakSaveButton state={apiState} disabled={formDisabled} />
        </Form>
      </Card.Body>
    </Card>
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
      readonly planInterval: "month" | "year"
    }
    readonly billingEmail: string
    readonly customerName?: string
    readonly customerAddress?: {
      readonly line1?: string
      readonly city?: string
      readonly country?: string
      readonly line2?: string
      readonly postalCode?: string
      readonly state?: string
    }
    readonly viewerIsOrgOwner: boolean
    readonly viewerCanModify: boolean
    readonly limitBillingAccessToOwners: boolean
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
              <Form.Label className="font-weight-bold">Seats</Form.Label>
              <p className="mb-0">{subscription.seats} seats</p>
              <Form.Text className="text-muted">
                An active user consumes one seat per billing period.
              </Form.Text>
            </Form.Group>
            <Form.Group>
              <Form.Label className="font-weight-bold">
                Next Billing Date
              </Form.Label>
              <p>
                <FormatDate date={subscription.nextBillingDate} />
              </p>
            </Form.Group>
            <Form.Group>
              <Form.Label className="font-weight-bold">Cost</Form.Label>
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
                )}{" "}
                / {subscription.cost.planInterval}
              </p>
            </Form.Group>
            <Form.Group>
              <Form.Label className="font-weight-bold">
                Billing History
              </Form.Label>
              <p>
                <a href={settings.getStripeSelfServeUrl(teamId)}>
                  view billing history
                  <GoLinkExternal className="pl-1" />
                </a>
              </p>
            </Form.Group>
            <Button
              variant="dark"
              size="sm"
              onClick={modifySubscription}
              disabled={!subscription?.viewerCanModify}>
              Modify Subscription
            </Button>
            {!subscription?.viewerCanModify && (
              <Form.Text className="text-muted">
                You must be an organization owner to modify the subscription.
              </Form.Text>
            )}
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
        <BillingEmailForm
          className="mb-4"
          defaultValue={subscription.billingEmail}
          disabled={!subscription.viewerCanModify}
        />

        <CompanyNameForm
          className="mb-4"
          defaultValue={subscription.customerName ?? ""}
          disabled={!subscription.viewerCanModify}
        />

        <PostalAddressForm
          className="mb-4"
          defaultValue={subscription.customerAddress ?? {}}
          disabled={!subscription.viewerCanModify}
        />
        <LimitBillingAccessForm
          className="mb-4"
          canEdit={subscription.viewerIsOrgOwner}
          defaultValue={subscription.limitBillingAccessToOwners ?? false}
        />
      </Col>
    </Row>
  )
}

function SubscriptionTrialStarter({
  startSubscription,
  startTrial,
  trial,
}: {
  readonly startSubscription: (params: { period: "month" | "year" }) => void
  readonly startTrial: () => void
  readonly trial: ISubscriptionUpsellPromptProps["trial"]
}) {
  return (
    <Row>
      <Col className="mx-auto">
        <Card className="mb-4">
          <Card.Body>
            <Card.Title className="d-flex align-items-baseline justify-content-between">
              <span>Subscription Plans</span>
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
            <BillingDocumentation
              pricingInfo
              subscriptionInfo={false}
              trialInfo
            />
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
                sustain Kodiak – help us cover server costs and feature
                development
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
            <b>Active User</b>
            <p>
              A GitHub user that opens a pull request which Kodiak updates,
              approves, or merges.
            </p>
          </Col>
        </Row>
      )}
    </>
  )
}

const FALLBACK_SUBSCRIPTION_EXEMPTION =
  "Your account is excepted from subscriptions. Please contact us at support@kodiakhq.com with any questions."

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
  if (props.data.status === "initial" || props.data.status === "loading") {
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

  function handleStartSubscription({ period }: { period: "month" | "year" }) {
    history.push({ search: `start_subscription=1&period=${period}` })
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
            <Col lg={8}>
              <Card className="mb-4">
                <Card.Body>
                  <Card.Title>
                    <span>Subscription</span>
                  </Card.Title>
                  {data.subscriptionExemption != null ? (
                    data.subscriptionExemption.message ||
                    FALLBACK_SUBSCRIPTION_EXEMPTION
                  ) : (
                    <>
                      Kodiak is free for personal GitHub accounts.
                      <br />
                      Organizations can subscribe to use Kodiak on private
                      repositories.
                    </>
                  )}
                </Card.Body>
              </Card>
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
