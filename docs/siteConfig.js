/**
 * Copyright (c) 2017-present, Facebook, Inc.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

// See https://docusaurus.io/docs/site-config for all the possible
// site configuration options.

const repoUrl = "https://github.com/chdsbd/kodiak"
const installUrl = "https://github.com/marketplace/kodiakhq#pricing-and-setup"
const changeLogUrl = "https://github.com/chdsbd/kodiak/releases"
const issuesUrl = "https://github.com/chdsbd/kodiak/issues/new/choose"

const siteConfig = {
  title: "Kodiak", // Title for your website.
  tagline: "Automate your GitHub Pull Requests",
  url: "https://kodiakhq.com", // Your website URL
  baseUrl: "/", // Base URL for your project */
  // For github.io type URLs, you would set the url and baseUrl like:
  //   url: 'https://facebook.github.io',
  //   baseUrl: '/test-site/',

  // Used for publishing and more
  projectName: "kodiak",
  organizationName: "kodiak",
  // For top-level user or org sites, the organization is still the same.
  // e.g., for the https://JoelMarcey.github.io site, it would be set like...
  //   organizationName: 'JoelMarcey'

  algolia: {
    apiKey: process.env.AGOLIA_API_KEY,
    indexName: process.env.AGOLIA_INDEX_NAME,
  },

  repoUrl,
  installUrl,
  changeLogUrl,
  issuesUrl,

  customDocsPath: "docs/docs",

  // For no header links in the top nav bar -> headerLinks: [],
  headerLinks: [
    { doc: "quickstart", label: "Docs" },
    { href: "#quickstart", label: "Quick Start" },
    { page: "help", label: "Help" },
    { href: changeLogUrl, label: "Changelog" },
    {
      href: repoUrl,
      label: "GitHub",
    },
    {
      href: installUrl,
      label: "Install",
    },
    { search: true },
  ],

  /* path to images for header/footer */
  headerIcon: "img/favicon.ico",
  footerIcon: "img/favicon.ico",
  favicon: "img/favicon.ico",

  /* Colors for website */
  // "#3f466b",
  // "#50396c",
  colors: {
    primaryColor: "#47325f",
    secondaryColor: "#b2a0bb",
  },

  // This copyright info is used in /core/Footer.js and blog RSS/Atom feeds.
  copyright: `Copyright © ${new Date().getFullYear()} Kodiak Authors`,

  highlight: {
    // Highlight.js theme to use for syntax highlighting in code blocks.
    theme: "default",
  },

  // Add custom scripts here that would be placed in <script> tags.
  scripts: [],

  // On page navigation for the current documentation page.
  onPageNav: "separate",
  // No .html extensions for paths.
  cleanUrl: true,

  // Open Graph and Twitter card images.
  ogImage: "img/wordmark.svg",
  twitterImage: "img/wordmark.svg",

  // For sites with a sizable amount of content, set collapsible to true.
  // Expand/collapse the links and subcategories under categories.
  // docsSideNavCollapsible: false,

  // Show documentation's last contributor's name.
  // enableUpdateBy: true,

  // Show documentation's last update time.
  enableUpdateTime: true,

  // You may provide arbitrary config keys to be used as needed by your
  // template. For example, if you need your repo's URL...
}

module.exports = siteConfig
