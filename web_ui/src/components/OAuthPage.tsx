import React, { useEffect, useState } from "react"
import { startLogin, getOauthState } from "../auth"
import { useLocation, useHistory } from "react-router-dom"
import { Current } from "../world"
import { Button } from "react-bootstrap"

export function OAuthPage() {
  const location = useLocation()
  const history = useHistory()
  const [error, setError] = useState<string>()
  // This isn't supported in IE, but we're not going to support IE anyway.
  const queryParams = new URLSearchParams(location.search)
  const code = queryParams.get("code") || ""
  const serverState = queryParams.get("state") || ""
  const clientState = getOauthState()
  useEffect(() => {
    Current.api.loginUser({ code, serverState, clientState }).then(res => {
      if (res.ok) {
        // navigate to activity page on success.
        history.push("/")
        return
      } else {
        setError(`${res.error} – ${res.error_description}`)
      }
    })
  }, [clientState, code, history, serverState])
  return (
    <>
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
              className="mr-2" />
            <h1 className="h2 mb-0 font-weight-bold">Kodiak</h1>
          </div>

          {!error ? (
            <p className="text-muted">Logging in...</p>
          ) : (
            <p className="text-danger">
              <b>
                Login failure
                <br />
              </b>{" "}
              {error}
            </p>
          )}

          <p className="mb-0 d-flex flex-column">
            {error && (
              <Button variant="primary" className="mb-4" onClick={startLogin}>
                {" "}
                Retry login
              </Button>
            )}
            <a href="/login">Return to Login</a>
          </p>
        </div>
      </div>
    </>
  )
}
