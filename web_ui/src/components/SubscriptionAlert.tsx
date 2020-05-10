import React from "react"
import { Link } from "react-router-dom"
import { Alert } from "react-bootstrap"
import { Current } from "src/world"
import { useTeamApi } from "src/useApi"

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
  const state = useTeamApi(Current.api.getSubscriptionInfo)

  if (state.status === "loading" || state.status === "failure") {
    return null
  }

  if (state.data.type === "VALID_SUBSCRIPTION") {
    return null
  }

  if (state.data.type === "TRIAL_EXPIRED") {
    return <TrialExpiredAlert />
  }

  if (state.data.type === "SUBSCRIPTION_EXPIRED") {
    return <SubscriptionExpiredAlert />
  }

  return (
    <SubscriptionExceededAlert
      activeUserCount={state.data.activeUserCount}
      licenseCount={state.data.licenseCount}
    />
  )
}
