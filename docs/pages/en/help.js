/**
 * Copyright (c) 2017-present, Facebook, Inc.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

const React = require("react")

// @ts-ignore
const CompLibrary = require("../../core/CompLibrary.js")

const Container = CompLibrary.Container
const GridBlock = CompLibrary.GridBlock

/** @param {{config: typeof import("../../siteConfig")}} props */
function Help(props) {
  const supportLinks = [
    {
      content: `If you need help installing or configuring Kodiak please [open an issue on GitHub](${props.config.issuesUrl}).

The team is happy to help!`,
      title: `[File an Issue on GitHub](${props.config.issuesUrl})`,
    },
    {
      content: `Take a look around Kodiak's [Troubleshooting page](/docs/troubleshooting) and [Quick Start Guide](/docs/quickstart).`,
      title: "Browse Docs",
    },
    {
      content: `Reach us privately at support@kodiakhq.com.`,
      title: `Send an Email`,
    },
  ]

  return (
    <div className="docMainWrapper wrapper">
      <Container className="mainContainer documentContainer postContainer">
        <div className="post">
          <header className="postHeader">
            <h1>Need help?</h1>
          </header>
          <GridBlock contents={supportLinks} layout="threeColumn" />
        </div>
      </Container>
    </div>
  )
}

module.exports = Help
