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
import { WebData } from "../webdata"
import { useApi } from "../useApi"
import { Current } from "../world"

interface IDropdownToggleProps<T> {
  readonly id: string
  readonly children: React.ReactNode
  readonly as: React.FunctionComponent<T>
}

function DropdownToggle<T>(props: IDropdownToggleProps<T>) {
  // TODO(sbdchd): types are broken for this component. Probably better to just
  // write the component ourselves.
  // tslint:disable-next-line no-any
  const BootstrapDropdownToggle = Dropdown.Toggle as any
  // tslint:disable-next-line no-unsafe-any
  return <BootstrapDropdownToggle {...props} />
}

interface IProfileImgProps {
  readonly profileImgUrl: string
  readonly name: string
  readonly className?: string
  readonly size: number
}
function ProfileImg({
  profileImgUrl,
  name,
  className = "",
  size,
}: IProfileImgProps) {
  return (
    <div className={className}>
      <Image
        url={profileImgUrl}
        alt="org profile"
        size={size}
        className="mr-2"
      />
      <span className="h6 some-cls">{name}</span>
    </div>
  )
}

interface ICustomToggleProps {
  readonly children: React.ReactNode
  readonly onClick: (e: React.MouseEvent<HTMLButtonElement, MouseEvent>) => void
}
const CustomToggle = React.forwardRef(
  (
    { children, onClick }: ICustomToggleProps,
    ref: React.Ref<HTMLButtonElement>,
  ) => (
    <button
      className="btn border-hover rounded mb-2 pl-0 pr-0"
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

interface ISideBarNavLinkProps {
  readonly to: string
  readonly children: React.ReactChild
  readonly external?: boolean
  readonly className?: string
}
function SideBarNavLink({
  to,
  children,
  external = false,
  className,
}: ISideBarNavLinkProps) {
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
  const data = useApi(Current.api.getCurrentAccount)
  return <SideBarNavInner accounts={data} />
}

function SkeletonProfileImage() {
  return (
    <div className="d-flex align-items-center mr-auto">
      <div
        style={{
          height: 30,
          width: 30,
          backgroundColor: "lightgray",
        }}
        className="mr-2 rounded"
      />
      <span
        className="h4 mb-0 rounded"
        style={{
          width: 75,
          height: 30,
          backgroundColor: "lightgray",
        }}
      />
    </div>
  )
}

function Loading() {
  return (
    <SideBarNavContainer
      userContent={<SkeletonProfileImage />}
      orgContent={<SkeletonProfileImage />}
      switchAccountContent={<></>}
    />
  )
}

interface ISideBarNavContainerProps {
  readonly orgContent: React.ReactNode
  readonly userContent: React.ReactNode
  readonly switchAccountContent: React.ReactNode
}
function SideBarNavContainer({
  orgContent,
  userContent,
  switchAccountContent,
}: ISideBarNavContainerProps) {
  return (
    <div
      className="bg-light p-3 h-100 d-flex flex-column justify-content-between"
      style={{ width: 230 }}>
      <div>
        <div>
          <Dropdown as={ButtonGroup} className="w-100">
            <DropdownToggle id="org-dropdown" as={CustomToggle}>
              {orgContent}
            </DropdownToggle>
            <Dropdown.Menu className="super-colors shadow-sm">
              <Dropdown.Header className="text-center">switch account</Dropdown.Header>
              {switchAccountContent}
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
          <hr />

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
        <Dropdown as={ButtonGroup} className="w-100">
          <DropdownToggle id="user-dropdown" as={CustomToggle}>
            {userContent}
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

interface ISideBarNavInnerProps {
  readonly accounts: WebData<{
    readonly accounts: ReadonlyArray<{
      readonly id: number
      readonly name: string
      readonly profileImgUrl: string
    }>
    readonly org: {
      readonly id: number
      readonly name: string
      readonly profileImgUrl: string
    }
    readonly user: {
      readonly id: number
      readonly name: string
      readonly profileImgUrl: string
    }
  }>
}
function SideBarNavInner({ accounts }: ISideBarNavInnerProps) {
  if (accounts.status === "loading") {
    return <Loading />
  }
  if (accounts.status === "failure") {
    return <p>failure</p>
  }

  return (
    <SideBarNavContainer
      userContent={
        <ProfileImg
        className="mr-auto"
          profileImgUrl={accounts.data.user.profileImgUrl}
          name={accounts.data.user.name}
          size={30}
        />
      }
      orgContent={
        <div className="d-flex align-items-center mr-auto">
          <Image
            url={accounts.data.org.profileImgUrl}
            alt="kodiak avatar"
            size={30}
            className="mr-2"
          />
          <span className="h5 mb-0 sidebar-overflow-ellipsis">{accounts.data.org.name}</span>
        </div>
      }
      switchAccountContent={
        <>
          {sortBy(accounts.data.accounts, "name").map(x => (
            <Dropdown.Item as="button" key={x.id}>
              <>
                <Image
                  url={x.profileImgUrl}
                  alt={x.name}
                  size={30}
                  className="mr-3"
                />
                {x.name}
              </>
            </Dropdown.Item>
          ))}
        </>
      }
    />
  )
}