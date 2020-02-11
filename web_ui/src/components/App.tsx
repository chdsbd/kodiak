import React from "react"
import { BrowserRouter as Router, Switch, Route, Redirect } from "react-router-dom"
import { Container } from "react-bootstrap"
import { UsageBillingPage } from "./UsageBillingPage"
import { LoginPage } from "./LoginPage"
import { OAuthPage } from "./OAuthPage"
import { AccountsPage } from "./AccountsPage"
import { SettingsPage } from "./SettingsPage"
import { ActivityPage } from "./ActivityPage"
import { Page } from "./Page"

export default function App() {
  return (
    <Router>
      <Switch>
        <Route exact path="/t/:team_id/">
          <Page>
            <ActivityPage />
          </Page>
        </Route>
        <Route path="/t/:team_id/usage">
          <Page>
            <UsageBillingPage />
          </Page>
        </Route>
        <Route path="/t/:team_id/settings">
          <Page>
            <SettingsPage />
          </Page>
        </Route>
        <Route path="/login">
          <Container className="h-100">
            <LoginPage />
          </Container>
        </Route>
        <Route path="/oauth">
          <Container className="h-100">
            <OAuthPage />
          </Container>
        </Route>
        <Route path="/accounts">
          <Container className="h-100">
            <AccountsPage />
          </Container>
        </Route>
        <Redirect from="/" to="/accounts"/>
        <Redirect from="/t/" to="/accounts"/>
      </Switch>
    </Router>
  )
}
