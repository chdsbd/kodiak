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
import { useTeamApi, teamApi } from "../useApi"
import formatDate from "date-fns/format"
import formatDistanceToNow from "date-fns/formatDistanceToNow"
import parseISO from "date-fns/parseISO"
import sub from "date-fns/sub"
import sortBy from "lodash/sortBy"
import { useLocation, useHistory, useParams } from "react-router-dom"
import { loadStripe } from "@stripe/stripe-js"
import * as settings from "../settings"
import debounce from "lodash/debounce"
import { GoLinkExternal } from "react-icons/go"

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
  return `\$${(cents / 100).toFixed(2)}`
}

function formatFromNow(dateString: string): string {
  return formatDistanceToNow(parseISO(dateString))
}

function FormatDate({ date }: { date: string }) {
  return <>{formatDate(parseISO(date), "y-MM-dd kk:mm O")}</>
}

const formattedMonthlyCost = formatCents(settings.monthlyCost)

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
              value={formatCents(costCents)}
            />
            <Form.Text className="text-muted">
              Billed monthly. <b>{seats} seat(s) </b>
              at <b>{formatCents(settings.monthlyCost)}/seat</b>.{" "}
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
}
function ManageSubscriptionModal({
  show,
  onClose,
  seatUsage,
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
    fetchProrationDebounced()
  }, [fetchProrationDebounced, seats])
  function formatProration(x: IProrationAmount) {
    if (x.kind === "loading" || x.kind === "failed") {
      return "--"
    }
    if (x.kind === "success") {
      if (x.cost > 0) {
        return formatCents(x.cost)
      }
      return `account credit of ${formatCents(-x.cost)}`
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

  const costCents = seats * settings.monthlyCost
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
              Your current plan costs <b>{formattedMonthlyCost}/month</b> for{" "}
              <b>{currentSeats} seat(s)</b> at{" "}
              <b>{formattedMonthlyCost}/seat</b>.
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
                <b>{formatCents(costCents)}</b> for <b>{seats} seat(s) </b>
                at <b>{formatCents(settings.monthlyCost)}/seat</b>.{" "}
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
                ? `Update Plan for ${formatCents(prorationAmount.cost)}`
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
  return (
    <Col className="d-flex justify-content-center">
      <div className="m-auto">
        {trial == null && (
          <h4 className="h5">
            Subscribe and use Kodiak on your private repositories!
          </h4>
        )}

        {trial != null ? (
          <>
            {!trial.expired ? (
              <>
                <h3 className="text-center">Trial Active</h3>
                <p className="text-center">
                  Your active trial expires in{" "}
                  <b>{formatFromNow(trial.endDate)}</b> at{" "}
                  <b>
                    <FormatDate date={trial.endDate} />
                  </b>
                  .
                </p>
              </>
            ) : (
              <>
                <h3 className="text-center text-danger">Trial Inactive</h3>
                <p className="text-center">
                  Your trial expired at{" "}
                  <b>
                    <FormatDate date={trial.endDate} />
                  </b>
                  .
                </p>
              </>
            )}

            <p className="text-center">
              Subscribe to continue using Kodiak on your private repositories!
            </p>
          </>
        ) : null}
        {trial == null ? (
          <>
            <div className="d-flex justify-content-center">
              <Button variant="success" size="lg" onClick={startTrial}>
                Start 30 Day Trial
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
            <Button variant="dark" size="lg" onClick={startSubscription}>
              Subscribe
            </Button>
          </div>
        )}
        <p className="text-center">
          ({formattedMonthlyCost} per active user per month)
        </p>
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
  readonly teamId: string
}
function ActiveSubscription({
  seats,
  cost,
  billingEmail,
  nextBillingDate,
  modifySubscription,
  teamId,
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
        <Col>
          <FormatDate date={nextBillingDate} />
        </Col>
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
      <Row>
        <Col md={3}>
          <b>Billing History</b>
        </Col>
        <Col>
          <a href={settings.getStripeSelfServeUrl(teamId)}>
            view billing history
            <GoLinkExternal className="pl-1" />
          </a>
        </Col>
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
    readonly expired: boolean
    readonly cost: {
      readonly totalCents: number
      readonly perSeatCents: number
    }
    readonly billingEmail: string
  } | null
  readonly startSubscription: () => void
  readonly startTrial: () => void
  readonly modifySubscription: () => void
  readonly trial: ISubscriptionUpsellPromptProps["trial"]
  readonly teamId: string
}
function Subscription({
  subscription,
  startSubscription,
  startTrial,
  modifySubscription,
  trial,
  teamId,
}: ISubscriptionProps) {
  return (
    <>
      <h3 className="h5">Subscription</h3>
      <div className="border border-primary rounded p-2 mb-4">
        <Row>
          {subscription != null && !subscription.expired ? (
            <ActiveSubscription
              cost={subscription.cost}
              seats={subscription.seats}
              nextBillingDate={subscription.nextBillingDate}
              billingEmail={subscription.billingEmail}
              modifySubscription={modifySubscription}
              teamId={teamId}
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
              The 30-day trial is free and allows for using Kodiak on private
              repos with an unlimited number of users. After 30-days you can
              subscribe to continue using Kodiak on private repositories.
            </p>
          </Col>
        </Row>
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
        <Row>
          <Col>
            <p>
              For more information about billing visit{" "}
              <a href="https://kodiakhq.com/docs/billing">
                https://kodiakhq.com/docs/billing
              </a>
              . Send us an email at{" "}
              <a href="mailto:support@kodiakhq.com">support@kodiakhq.com</a> if
              you need any assistance.
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
          teamId={teamId}
        />
        <StartSubscriptionModal
          show={showSubscriptionManagerModal}
          onClose={clearQueryString}
          seatUsage={data.activeUsers.length}
        />
        {data.subscription != null ? (
          <ManageSubscriptionModal
            show={showSubscriptionModifyModal}
            currentSeats={data.subscription.seats}
            seatUsage={data.activeUsers.length}
            billingEmail={data.subscription.billingEmail}
            cardInfo={data.subscription.cardInfo}
            onClose={x => {
              if (x?.reload) {
                location.search = ""
              } else {
                clearQueryString()
              }
            }}
          />
        ) : null}
        {data.accountCanSubscribe ? (
          <Subscription
            startSubscription={handleStartSubscription}
            startTrial={handleStartTrial}
            modifySubscription={modifySubscription}
            subscription={data.subscription}
            trial={data.trial}
            teamId={teamId}
          />
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
                      "This user opened a GitHub pull request that Kodiak updated, approved, or merged."
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
