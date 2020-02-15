import React from "react"
import { Spinner as BootstrapSpinner } from "react-bootstrap"

export function Spinner() {
  return (
    <div className="d-flex align-items-center justify-content-center h-100">
      <BootstrapSpinner animation="grow" role="status">
        <span className="sr-only">Loading...</span>
      </BootstrapSpinner>
    </div>
  )
}
