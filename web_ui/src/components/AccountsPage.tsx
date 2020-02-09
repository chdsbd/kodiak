import React from "react"
import { Image } from "./Image"
import { useApi } from "../useApi"
import { Current } from "../world"
import { WebData } from "../webdata"

export function AccountsPage() {
  const accounts = useApi(Current.api.getAccounts)
  return <AccountsPageInner accounts={accounts} />
}

interface IAccount {
  readonly name: string
  readonly profileImgUrl: string
}

interface IAccountsPageInnerProps {
  readonly accounts: WebData<ReadonlyArray<IAccount>>
}
function AccountsPageInner({ accounts }: IAccountsPageInnerProps) {
  if (accounts.status === "loading") {
    return <p>loading...</p>
  }
  if (accounts.status === "failure") {
    return <p>failure...</p>
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
              <a href="https://github.com/" className="pb-3">
                <Image
                  url={a.profileImgUrl}
                  alt="org profile"
                  size={30}
                  className="mr-2" />
                <span>{a.name}</span>
              </a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
