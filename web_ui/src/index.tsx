import React from "react"
import ReactDOM from "react-dom"
import "./custom.scss"
import App from "./components/App"
import * as settings from "./settings"

import * as Sentry from "@sentry/browser"

Sentry.init({ dsn: settings.SENTRY_DSN })

ReactDOM.render(<App />, document.getElementById("root"))
