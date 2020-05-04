import React from "react"
import { SideBarNav } from "./SideBarNav"
import { Container } from "react-bootstrap"
import { ErrorBoundary } from "./ErrorBoundary"

interface IPageProps {
  readonly children: React.ReactNode
}
export function Page({ children }: IPageProps) {
  return (
    <div className="h-100">
      <div className="h-100 d-flex flex-column flex-sm-row">
        <div className="flex-shrink-0">
          <SideBarNav />
        </div>
        <ErrorBoundary>
          <Container className="p-4 w-100 overflow-sm-auto d-flex">
            {children}
          </Container>
        </ErrorBoundary>
      </div>
    </div>
  )
}
