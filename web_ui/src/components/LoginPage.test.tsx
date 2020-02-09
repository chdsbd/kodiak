import React from "react"
import { render } from "@testing-library/react"
import { LoginPage } from "./LoginPage"

describe("LoginPage", () => {
  test("snap smoke test", () => {
    const { container } = render(<LoginPage />)

    expect(container).toMatchSnapshot()
  })
})
