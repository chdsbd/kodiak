/**
 * Copyright (c) 2017-present, Facebook, Inc.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

const React = require("react");

const CompLibrary = require("../../core/CompLibrary.js");

const Container = CompLibrary.Container;
const GridBlock = CompLibrary.GridBlock;

/** @param {{language?: string, config: typeof import("../../siteConfig")}} props */
function Help(props) {
  const { config: siteConfig, language = "" } = props;
  const { baseUrl, docsUrl } = siteConfig;
  const docsPart = `${docsUrl ? `${docsUrl}/` : ""}`;
  const langPart = `${language ? `${language}/` : ""}`;

  /** @param {string} doc */
  const docUrl = doc => `${baseUrl}${docsPart}${langPart}${doc}`;

  const supportLinks = [
    {
      content: `If you need help installing or configuring Kodiak please open an issue on GitHub.

The team is happy to help!`,
      title: `[File an Issue on GitHub](${props.config.issuesUrl})`
    },
    {
      content: `Take a look around Kodiak's [Docs](${docUrl(
        "recipes.html"
      )}) and [Quick Start Guide](${docUrl("quickstart.html")}).`,
      title: "Browse Docs"
    }
  ];

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
  );
}

module.exports = Help;
