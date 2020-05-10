import React from "react"
import { Link, useParams } from "react-router-dom"
import { Alert } from "react-bootstrap"
import { Current } from "src/world"

type State<T> =
  | { readonly status: "loading" }
  | { readonly status: "failure" }
  | {
      readonly status: "success"
      readonly data: T
    }

type Subscription =
  | {
      // personal user, subscription valid, or trial account
      readonly type: "VALID_SUBSCRIPTION"
    }
  | { readonly type: "TRIAL_EXPIRED" }
  | { readonly type: "SUBSCRIPTION_EXPIRED" }
  | {
      readonly type: "SUBSCRIPTION_OVERAGE"
      readonly activeUserCount: number

      readonly licenseCount: number
    }

function useSubscriptionInfo({ teamId }: { readonly teamId: string }) {
  const [state, setState] = React.useState<State<Subscription>>({
    status: "loading",
  })
  React.useEffect(() => {
    setState({ status: "loading" })
    Current.api
      .getSubscriptionInfo({ teamId })
      .then(res => {
        setState({
          status: "success",
          data: res,
        })
      })
      .catch(() => {
        setState({ status: "failure" })
      })
  }, [setState, teamId])
  return state
}

function TrialExpiredAlert() {
  return (
    <Alert variant="warning">
      <strong>Trial Expired: </strong>Please{" "}
      <Link to="./usage">update your subscription</Link> to prevent service
      disruption.
    </Alert>
  )
}

function SubscriptionExpiredAlert() {
  return (
    <Alert variant="warning">
      <strong>Subscription Expired: </strong>Please{" "}
      <Link to="./usage">update your subscription</Link> to prevent service
      disruption.
    </Alert>
  )
}

function SubscriptionExceededAlert({
  activeUserCount,
  licenseCount,
}: {
  readonly activeUserCount: number
  readonly licenseCount: number
}) {
  return (
    <Alert variant="warning">
      <strong>Subscription Exceeded: </strong>You have{" "}
      <b>{activeUserCount} active users</b> and{" "}
      <b>{licenseCount} seat licenses.</b> Please{" "}
      <Link to="./usage">upgrade your seat licenses</Link> to prevent service
      disruption.
    </Alert>
  )
}

export function SubscriptionAlert() {
  const teamId = useParams<{ readonly team_id: string }>().team_id
  const state = useSubscriptionInfo({ teamId })

  if (state.status === "loading" || state.status === "failure") {
    return null
  }

  if (state.data.type === "validSubscription") {
    return null
  }

  if (state.data.type === "trialExpired") {
    return <TrialExpiredAlert />
  }

  if (state.data.type === "subscriptionExpired") {
    return <SubscriptionExpiredAlert />
  }

  return (
    <SubscriptionExceededAlert
      activeUserCount={state.data.activeUserCount}
      licenseCount={state.data.licenseCount}
    />
  )
}
