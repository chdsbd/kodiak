import React from "react"
import { SideBarNav } from "./SideBarNav"
import { Container, Alert } from "react-bootstrap"

export function Page({ children }: { children: React.ReactNode }) {
  const accountIsOver = false
  const seats = { current: 16, total: 15 }
  const nextBillingPeriod = "Feb 21"
  return (
    <div className="h-100">
      <div className="h-100 d-flex">
        <div className="h-100 flex-shrink-0">
          <SideBarNav />
        </div>
        <Container className="p-4 w-100 overflow-auto">
          {accountIsOver ? (
            <Alert variant="warning">
              <b>ATTENTION:</b> You’ve used {seats.current}/{seats.total} seats
              for your current billing period. Please add more seats to your
              plan by your next billing period ({nextBillingPeriod}) to ensure
              continued service.
            </Alert>
          ) : null}
          {children}
        </Container>
      </div>
    </div>
  )
}
