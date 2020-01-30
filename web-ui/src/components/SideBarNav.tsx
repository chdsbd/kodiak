import React from "react"
import { NavLink } from "react-router-dom"
import { Dropdown, ButtonGroup } from "react-bootstrap"
import {
  GoGraph,
  GoCreditCard,
  GoSettings,
  GoGift,
  GoBook,
  GoChevronDown,
  GoLinkExternal,
  GoSignOut,
  GoQuestion,
} from "react-icons/go"
import sortBy from "lodash/sortBy"
import { Image } from "./Image"
import { docsUrl, modifyPlanLink, helpUrl } from "../settings"

function ProfileImg({
  profileImgUrl,
  name,
  className = "",
  size,
}: {
  profileImgUrl: string
  name: string
  className?: string
  size: number
}) {
  return (
    <div className={className}>
      <Image
        url={profileImgUrl}
        alt="org profile"
        size={size}
        className="mr-2"></Image>
      <span className="h6 some-cls">{name}</span>
    </div>
  )
}

const CustomToggle = React.forwardRef(
  (
    {
      children,
      onClick,
    }: {
      children: React.ReactNode
      onClick: (e: React.MouseEvent<HTMLButtonElement, MouseEvent>) => void
    },
    ref: React.Ref<HTMLButtonElement>,
  ) => (
    <button
      className="btn border-hover rounded mb-2"
      ref={ref}
      onClick={e => {
        e.preventDefault()
        if (onClick) {
          onClick(e)
        }
      }}>
      <div className="d-flex align-items-center some-cls">
        {children}
        <span className="ml-2">
          <GoChevronDown size="1.5rem" />
        </span>
      </div>
    </button>
  ),
)

function SideBarNavLink({
  to,
  children,
  external = false,
  className,
}: {
  to: string
  children: React.ReactChild
  external?: boolean
  className?: string
}) {
  return (
    <li>
      {external ? (
        <a href={to} className={"text-decoration-none " + className}>
          {children}
        </a>
      ) : (
        <NavLink
          exact
          activeClassName="font-weight-bold"
          className={"text-decoration-none " + className}
          to={to}>
          {children}
        </NavLink>
      )}
    </li>
  )
}

export function SideBarNav() {
  const user = {
    name: "sbdchd",
    profileImgUrl: "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
  }
  const org = {
    name: "Kodiak",
    profileImgUrl: "https://avatars1.githubusercontent.com/in/29196?s=400&v=4",
  }

  const accounts = [
    {
      name: "sbdchd",
      profileImgUrl:
        "https://avatars0.githubusercontent.com/u/7340772?s=200&v=4",
    },
    {
      name: "recipeyak",
      profileImgUrl:
        "https://avatars2.githubusercontent.com/u/32210060?s=200&v=4",
    },
    {
      name: "AdmitHub",
      profileImgUrl:
        "https://avatars3.githubusercontent.com/u/7806836?s=200&v=4",
    },
    {
      name: "getdoug",
      profileImgUrl:
        "https://avatars0.githubusercontent.com/u/33015070?s=200&v=4",
    },
    {
      name: "pytest-dev",
      profileImgUrl:
        "https://avatars1.githubusercontent.com/u/8897583?s=200&v=4",
    },
  ]

  const DropdownToggle = Dropdown.Toggle as any
  return (
    <div className="bg-light p-3 h-100 d-flex flex-column justify-content-between">
      <div>
        <div>
          <Dropdown as={ButtonGroup}>
            <DropdownToggle id="dropdown-custom-1" as={CustomToggle}>
              <div className="d-flex align-items-center">
                <Image
                  url={org.profileImgUrl}
                  alt="kodiak avatar"
                  size={30}
                  className="mr-2"></Image>
                <span className="h4 mb-0">{org.name}</span>
              </div>
            </DropdownToggle>
            <Dropdown.Menu className="super-colors shadow-sm">
              <Dropdown.Header>switch account</Dropdown.Header>
              {sortBy(accounts, "name").map(x => (
                <Dropdown.Item as="button">
                  <>
                    <Image
                      url={x.profileImgUrl}
                      alt={x.name}
                      size={30}
                      className="mr-3"></Image>
                    {x.name}
                  </>
                </Dropdown.Item>
              ))}
            </Dropdown.Menu>
          </Dropdown>
        </div>
        <ul className="list-unstyled">
          <SideBarNavLink to="/" className="d-flex align-items-center">
            <>
              <GoGraph className="mr-1" size="1.25rem" />
              <span>Activity</span>
            </>
          </SideBarNavLink>
          <SideBarNavLink to="/usage">
            <>
              <GoCreditCard className="mr-1" size="1.25rem" />
              <span>Usage & Billing</span>
            </>
          </SideBarNavLink>
          <SideBarNavLink to="/settings">
            <>
              <GoSettings className="mr-1" size="1.25rem" />
              <span>Settings</span>
            </>
          </SideBarNavLink>
          <hr></hr>

          <SideBarNavLink
            to={docsUrl}
            external
            className="d-flex align-items-center">
            <>
              <GoBook className="mr-1" size="1.25rem" />
              <span>Docs</span>
              <GoLinkExternal className="ml-auto" />
            </>
          </SideBarNavLink>
          <SideBarNavLink
            to={helpUrl}
            external
            className="d-flex align-items-center">
            <>
              <GoQuestion className="mr-1" size="1.25rem" />
              <span>Help</span>
              <GoLinkExternal className="ml-auto" />
            </>
          </SideBarNavLink>

          <SideBarNavLink
            to={modifyPlanLink}
            external
            className="d-flex align-items-center">
            <>
              <GoGift className="mr-1" size="1.25rem" />
              <span>Upgrade</span>
              <GoLinkExternal className="ml-auto" />
            </>
          </SideBarNavLink>
        </ul>
      </div>

      <div>
        <Dropdown as={ButtonGroup}>
          <DropdownToggle id="dropdown-custom-1" as={CustomToggle}>
            <ProfileImg
              profileImgUrl={user.profileImgUrl}
              name={user.name}
              size={30}
            />
          </DropdownToggle>
          <Dropdown.Menu className="super-colors shadow-sm">
            <Dropdown.Item as="button">
              <span className="mr-1">Logout</span>
              <GoSignOut />
            </Dropdown.Item>
          </Dropdown.Menu>
        </Dropdown>
      </div>
    </div>
  )
}
