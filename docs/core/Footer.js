/**
 * Copyright (c) 2017-present, Facebook, Inc.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

const React = require("react")

/** @param {{config: typeof import("../siteConfig")}} props */
function Footer(props) {
  return (
    <footer className="nav-footer" id="footer">
      <section className="sitemap">
        <a href={props.config.baseUrl} className="nav-home">
          {props.config.footerIcon && (
            <img
              src={props.config.baseUrl + props.config.footerIcon}
              alt={props.config.title}
              style={{
                minWidth: "58px",
                minHeight: "58px",
                width: "58px",
                height: "58px",
              }}
              width="58"
              height="58"
            />
          )}
        </a>
        <div>
          <h5>Docs</h5>
          <a href="/docs/quickstart">Quick Start</a>
          <a href="/docs/recipes">Recipes</a>
          <a href="/docs/why-and-how">Why and How</a>
          <a href="/docs/config-reference">Configuration Reference</a>
        </div>
        <div>
          <h5>More</h5>
          <a href={props.config.installUrl}>Install</a>
          <a href={props.config.repoUrl}>GitHub</a>
          <a href={props.config.changeLogUrl}>Changelog</a>
          <a href="/help">Help</a>
        </div>
      </section>
      <section className="copyright">{props.config.copyright}</section>
    </footer>
  )
}

module.exports = Footer
