import React from "react"
import { Image } from "./Image"

export function AccountsPage() {
  const accounts = [
    {
      name: "bernard",
      profileImgUrl:
        "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
    },
    {
      name: "william",
      profileImgUrl:
        "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
    },
    {
      name: "deloris",
      profileImgUrl:
        "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
    },
    {
      name: "maeve",
      profileImgUrl:
        "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
    },
  ]
  return (
    <div className="h-100 d-flex justify-content-center align-items-center flex-column">
      <div
        className="w-100 text-center d-flex justify-content-around align-items-center flex-column"
        style={{ minHeight: 300 }}>
        <h1 className="h4">Select an Account</h1>
        <ul className="list-unstyled">
          {accounts.map(a => (
            <li className="d-flex align-items-center">
              <a href="https://github.com/" className="pb-3">
                <Image
                  url={a.profileImgUrl}
                  alt="org profile"
                  size={30}
                  className="mr-2"></Image>
                <span>{a.name}</span>
              </a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
