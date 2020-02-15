import React from "react"
import { Image } from "./Image"
import { useApi } from "../useApi"
import { Current } from "../world"
import { WebData } from "../webdata"
import { NavLink } from "react-router-dom"
import { Container } from "react-bootstrap"
import { Spinner } from "./Spinner"

export function AccountsPage() {
  const accounts = useApi(Current.api.getAccounts)
  return <AccountsPageInner accounts={accounts} />
}

interface IAccount {
  readonly id: number
  readonly name: string
  readonly profileImgUrl: string
}

interface IAccountsPageInnerProps {
  readonly accounts: WebData<ReadonlyArray<IAccount>>
}
function AccountsPageInner({ accounts }: IAccountsPageInnerProps) {
  if (accounts.status === "loading") {
    return <Spinner />
  }
  if (accounts.status === "failure") {
    return (
      <Container className="d-flex h-100">
        <p className="m-auto text-muted">failed to load accounts data</p>
      </Container>
    )
  }

  return (
    <div className="h-100 d-flex justify-content-center align-items-center flex-column">
      <div
        className="w-100 text-center d-flex justify-content-around align-items-center flex-column"
        style={{ minHeight: 300 }}>
        <h1 className="h4">Select an Account</h1>
        <ul className="list-unstyled">
          {accounts.data.map(a => (
            <li className="d-flex align-items-center">
              <NavLink to={`/t/${a.id}/`} className="pb-3">
                <Image
                  url={a.profileImgUrl}
                  alt="org profile"
                  size={30}
                  className="mr-2"
                />
                <span>{a.name}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
