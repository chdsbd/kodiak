import React from "react"
import { docsUrl, helpUrl, installUrl } from "../settings"
import { startLogin } from "../auth"

export function LoginPage() {
  return (
    <div className="h-100 d-flex justify-content-center align-items-center">
      <div
        className="w-100 text-center d-flex justify-content-around align-items-center flex-column"
        style={{ minHeight: 300 }}>
        <div className="d-flex justify-content-center align-items-center">
          <img
            src="/favicon.ico"
            alt="favicon"
            height={30}
            width={30}
            className="mr-2"
          />
          <h1 className="h2 mb-0 font-weight-bold">Kodiak</h1>
        </div>

        <div>
          <button onClick={startLogin} className="gh-install-btn">
            Login with GitHub
          </button>
        </div>

        <p className="mb-0">
          <a href={installUrl}>Install</a> | <a href={docsUrl}>Docs</a> |{" "}
          <a href={helpUrl}>Help</a>
        </p>
      </div>
    </div>
  )
}
