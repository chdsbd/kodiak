/**
 * Copyright (c) 2017-present, Facebook, Inc.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

const React = require("react");

const CompLibrary = require("../../core/CompLibrary.js");

const MarkdownBlock = CompLibrary.MarkdownBlock; /* Used to read markdown */
const Container = CompLibrary.Container;
const GridBlock = CompLibrary.GridBlock;

/**
 * @param {{baseUrl: string, docsUrl?: string}} siteConfig
 * @param {string} language
 */
function createDocUrl({ baseUrl }, language) {
  const langPart = `${language ? `${language}/` : ""}`;
  /** @param {string} doc */
  const docUrl = doc => `${baseUrl}${langPart}${doc}`;
  return docUrl;
}

/** @param {{language?: string, siteConfig: typeof import("../../siteConfig")}} props */
function HomeSplash(props) {
  const { siteConfig, language = "" } = props;
  const baseUrl = siteConfig.baseUrl;

  /** @param {{children: React.ReactNode}} props */
  const SplashContainer = props => (
    <div className="homeContainer">
      <div className="homeSplashFade">
        <div className="wrapper homeWrapper">{props.children}</div>
      </div>
    </div>
  );

  /** @param {{img_src: string}} props */
  const Logo = props => (
    <img
      src={props.img_src}
      alt="Project Logo"
      className="mr-3"
      height={40}
      width={40}
    />
  );

  const ProjectTitle = () => (
    <h2 className="projectTitle">
      <span className="d-flex justify-center align-center">
        <Logo img_src={`${baseUrl}img/favicon.ico`} />
        {siteConfig.title}
      </span>
      <small>{siteConfig.tagline}</small>
    </h2>
  );

  /** @param {{children: React.ReactNode, marginBottom?: boolean}} props */
  const PromoSection = props => (
    <div className={`section promoSection ${props.marginBottom ? "mb-4" : ""}`}>
      <div className="promoRow">
        <div className="pluginRowBlock">{props.children}</div>
      </div>
    </div>
  );

  /** @param {{href: string, target?: string, children: React.ReactNode}} props */
  const Button = props => (
    <div className="pluginWrapper buttonWrapper">
      <a className="button" href={props.href} target={props.target}>
        {props.children}
      </a>
    </div>
  );

  const InstallButton = () => (
    <div className="pluginWrapper buttonWrapper">
      <a className="gh-install-btn" href={siteConfig.installUrl}>
        Install on GitHub
      </a>
    </div>
  );

  return (
    <SplashContainer>
      <div className="inner">
        <ProjectTitle />

        <PromoSection marginBottom>
          <InstallButton />
        </PromoSection>
        <PromoSection>
          <Button href="#quickstart">Quick Start</Button>
          <Button href="#why">Why?</Button>
          <Button href={props.siteConfig.changeLogUrl}>Changelog</Button>
        </PromoSection>
      </div>
    </SplashContainer>
  );
}

/** @param {{language: string | undefined, config: typeof import("../../siteConfig") }} props */
function Index(props) {
  const { config: siteConfig, language = "" } = props;
  const { baseUrl } = siteConfig;

  const docUrl = createDocUrl(siteConfig, language);

  /** @param {{id?: string, background?: string, children: React.ReactNode, layout?: string, align?: "center" | "left" | undefined}} props */
  const Block = props => (
    <Container
      padding={["bottom", "top"]}
      id={props.id}
      background={props.background}
    >
      <GridBlock
        align={props.align || "center"}
        contents={props.children}
        layout={props.layout}
      />
    </Container>
  );

  const QuickStart = () => (
    <Block id="quickstart" align="left">
      {[
        {
          content: `\
1.  Install [the GitHub app](https://github.com/marketplace/kodiakhq#pricing-and-setup)

2.  Create a \`.kodiak.toml\` file in the root of your repository with the following contents

    \`\`\`toml
    # .kodiak.toml
    # Minimal config. version is the only required field.
    version = 1
    \`\`\`

3.  [Configure GitHub branch protection](https://help.github.com/en/articles/configuring-protected-branches)

4.  Create an automerge label (default: "automerge")

5.  Start auto merging PRs with Kodiak

    Label your PRs with your \`automerge\` label and let Kodiak do the rest! 🎉

See the [docs](${docUrl("quickstart.html")}) for additional setup information.

If you have any questions please review [our help page](./help).

`,
          image: `${baseUrl}img/undraw_code_review.svg`,
          imageAlign: "left",
          title: "Quickstart"
        }
      ]}
    </Block>
  );

  const Why = () => (
    <Block background="dark" align="left" id="why">
      {[
        {
          content: `\
Kodiak saves developer time by automating branch updates and merges, enabling you to keep your branches green and developers happy.

Kodiak's Eco Merge feature will use the _minimal number of updates_ to land code on \`master\`, preventing spurious CI jobs, minimizing CI costs.

Stop waiting for CI and let Kodiak automate your GitHub workflow.
`,
          image: `${baseUrl}img/undraw_uploading.svg`,
          imageAlign: "right",
          title: "Why?"
        }
      ]}
    </Block>
  );

  // Simple & Configurable — a simple configuration file with smart defaults will get you started in minutes
  // Update — update your branches automatically
  // Merge — use Kodiak's simple configuration with GitHub Branch Protection to merge pull requests automatically
  // Delete — remove your old branches automatically

  const Features = () => (
    <Block layout="fourColumn">
      {[
        {
          content: "Keep your PRs up to date with `master` automatically.",
          title: "Auto Update"
        },
        {
          content:
            "Add the `automerge` label or configure Kodiak to auto merge without a label once CI and Approvals pass. Configure Eco Merge to only update branches when necessary.",
          title: "Auto Merge"
        },
        {
          content:
            "A short and sweet configuration file, `.kodiak.toml`, with smart defaults, will get you started in minutes.",
          title: "Simple & Configurable"
        },
        {
          content:
            "Once enabled, Kodiak will use your PR's `title` and `body` along with the PR number to create a rich commit message on merge.",
          title: "Smart Commit Messages"
        },
        {
          content:
            "Kodiak understands there is no I in Team and works well with other Bots. Combine Kodiak with a dependency bot ([dependabot](https://dependabot.com), [snyk](https://snyk.io), [greenskeeper.io](https://greenkeeper.io)) to automate updating of dependencies.",
          title: "Bot Collaboration"
        },
        {
          content:
            "When configured, Kodiak will comment on your PR if a merge conflict gets in the way of an auto merge.",
          title: "Merge Conflict Alerts"
        },
        {
          content:
            "Remove your old branches automatically. Kodiak will cleanup after auto merging your PR. GitHub has this built in but Kodiak deletes those old branches faster.",
          title: "Tidy Up"
        },
        {
          content:
            "Add a feature, fix a bug, or self host, it's Open Source. Take a [peek under the hood.](https://github.com/chdsbd/kodiak)",
          title: "Open Source"
        }
      ]}
    </Block>
  );

  return (
    <div>
      <HomeSplash siteConfig={siteConfig} language={language} />
      <div className="mainContainer">
        <Features />
        <Why />
        <QuickStart />
      </div>
    </div>
  );
}

module.exports = Index;
