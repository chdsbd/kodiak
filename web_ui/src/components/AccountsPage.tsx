import React from "react"
import { Image } from "./Image"
import { useApi } from "../useApi"
import { Current } from "../world"
import { WebData } from "../webdata"
import { NavLink } from "react-router-dom"
import { Button, Container } from "react-bootstrap"
import { Spinner } from "./Spinner"
import { ToolTip } from "./ToolTip"
import { installUrl } from "../settings"

export function AccountsPage() {
  const [accounts, { refetch }] = useApi(Current.api.getAccounts)
  return <AccountsPageInner accounts={accounts} refetchAccounts={refetch} />
}

interface IAccount {
  readonly id: string
  readonly name: string
  readonly profileImgUrl: string
}

interface IAccountsPageInnerProps {
  readonly accounts: WebData<ReadonlyArray<IAccount>>
  readonly refetchAccounts: () => Promise<unknown>
}
function AccountsPageInner({
  accounts,
  refetchAccounts,
}: IAccountsPageInnerProps) {
  const [syncAccountStatus, setSyncAccountStatus] = React.useState<
    "initial" | "loading" | "failure" | "success"
  >("initial")
  if (accounts.status === "initial" || accounts.status === "loading") {
    return <Spinner />
  }
  if (accounts.status === "failure") {
    return (
      <Container className="d-flex h-100">
        <p className="m-auto text-muted">failed to load accounts data</p>
      </Container>
    )
  }

  const syncAccounts = () => {
    setSyncAccountStatus("loading")
    Current.api.syncAccounts().then(res => {
      if (res.ok) {
        setSyncAccountStatus("success")
        refetchAccounts()
      } else {
        setSyncAccountStatus("failure")
      }
    })
  }

  const isSyncLoading = syncAccountStatus === "loading"
  const isSyncSuccess = syncAccountStatus === "success"
  const isSyncFailure = syncAccountStatus === "failure"

  return (
    <div className="h-100 d-flex justify-content-center align-items-center flex-column">
      <div
        className="w-100 text-center d-flex align-items-center flex-column"
        style={{ minHeight: 300 }}>
        <h1 className="h4 mb-4">Select an Acccount</h1>
        <ul className="list-unstyled">
          {accounts.data.length === 0 && (
            <p className="text-muted">0 Acccounts Available.</p>
          )}
          {accounts.data.map(a => (
            <li key={a.id} className="d-flex align-items-center">
              <NavLink
                to={`/t/${a.id}/`}
                className="d-flex align-items-center flex-grow-1 mb-2 px-4 py-2 border border-dark rounded text-decoration-none account-chooser-image">
                <Image
                  url={a.profileImgUrl}
                  alt="org profile"
                  size={48}
                  className="mr-2"
                />
                <h2 className="h4 m-0">{a.name}</h2>
              </NavLink>
            </li>
          ))}
        </ul>
        <details>
          <summary className="mb-2">Not seeing an account?</summary>
          <a href={installUrl}>Install Kodiak</a> and sync your accounts.
          <br />
          <ToolTip
            content={
              isSyncSuccess
                ? "sync successful!"
                : isSyncFailure
                ? "sync failed!"
                : ""
            }
            visible={isSyncSuccess || isSyncFailure}
            placement="right">
            <Button
              size="sm"
              className="mb-4"
              variant="light"
              onClick={syncAccounts}
              disabled={isSyncLoading}>
              {isSyncLoading ? "Syncing accounts..." : "Sync Accounts"}
            </Button>
          </ToolTip>
        </details>
      </div>
    </div>
  )
}
