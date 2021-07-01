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

const LogoHeight = "32"

const Logos = {
  Atomic: function() {
    return (
      <svg
        fill="none"
        height={LogoHeight}
        viewBox="0 0 105 20"
        xmlns="http://www.w3.org/2000/svg">
        <title>atomic.io</title>
        <g clipRule="evenodd" fillRule="evenodd">
          <g fill="currentColor">
            <path d="m32.3465 12.044 3.1413-.4827c.7262-.1072.96-.4819.96-.9371 0-.93784-.7009-1.71479-2.1546-1.71479-1.5056 0-2.3364.99146-2.4397 2.14309l-3.0633-.6696c.2078-2.06273 2.0506-4.33993 5.4777-4.33993 4.0493 0 5.5544 2.35764 5.5544 5.00953v6.4831c0 .6965.0779 1.6343.1559 2.0895h-3.1666c-.078-.3486-.1299-1.0719-.1299-1.5807-.649 1.0451-1.8695 1.9554-3.7642 1.9554-2.7256 0-4.3865-1.9018-4.3865-3.9645 0-2.3576 1.6869-3.6702 3.8155-3.9913zm4.154 2.2306v-.6057l-2.805.468c-.8595.1377-1.542.6601-1.542 1.705 0 .7977.5307 1.568 1.6179 1.568 1.4149 0 2.7291-.7427 2.7291-3.1353z"></path>
            <path d="m46.552 6.48667h2.555v3.12731h-2.555v5.46002c0 1.1402.516 1.5109 1.4971 1.5109.4127 0 .8771-.053 1.0579-.1061v2.9157c-.31.1327-.9294.3178-1.9357.3178-2.4782 0-4.0263-1.5103-4.0263-4.0281v-6.07022h-2.2973v-3.12731h.6452c1.3421 0 1.9615-.90138 1.9615-2.06741v-1.82929h3.0976z"></path>
            <path d="m63.3444 13.0216c0 4.0379-2.899 6.9784-6.7379 6.9784-3.8388 0-6.7378-2.9405-6.7378-6.9784 0-4.06391 2.899-6.97839 6.7378-6.97839 3.8389 0 6.7379 2.91448 6.7379 6.97839zm-3.4776-.0722c0-2.4849-1.5645-3.74072-3.2603-3.74072-1.695 0-3.2602 1.25582-3.2602 3.74072 0 2.4587 1.5652 3.7413 3.2602 3.7413 1.6958 0 3.2603-1.2558 3.2603-3.7413z"></path>
            <path d="m88.4665 0c1.1791 0 2.1011.973578 2.1011 2.18495 0 1.15802-.922 2.1316-2.1011 2.1316-1.1534 0-2.101-.97358-2.101-2.1316 0-1.211372.9476-2.18495 2.101-2.18495zm-1.6663 6.47482h3.3327v13.09348h-3.3327z"></path>
            <path d="m95.2818 13.0216c0 2.3799 1.4954 3.7167 3.2482 3.7167 1.753 0 2.63-1.203 2.913-2.2193l3.016 1.0431c-.567 2.1919-2.552 4.4379-5.929 4.4379-3.7384 0-6.677-2.9405-6.677-6.9784 0-4.06391 2.8869-6.97839 6.5738-6.97839 3.4542 0 5.4142 2.21931 5.9552 4.43859l-3.068 1.0692c-.309-1.0959-1.109-2.21863-2.8098-2.21863-1.7534 0-3.2224 1.31003-3.2224 3.68923z"></path>
            <path d="m64.9568 19.6371v-13.1506h3.333v1.60328c.7085-1.28289 2.3612-1.97784 3.7782-1.97784 1.7578 0 3.1754.77522 3.8307 2.19188 1.0237-1.60328 2.3882-2.19188 4.0941-2.19188 2.3875 0 4.6705 1.47017 4.6705 4.99846v8.5267h-3.3849v-7.805c0-1.4167-.6822-2.48552-2.283-2.48552-1.4958 0-2.3882 1.17592-2.3882 2.59252v7.698h-3.463v-7.805c0-1.4167-.7085-2.48552-2.2837-2.48552-1.5214 0-2.4138 1.14912-2.4138 2.59252v7.698z"></path>
          </g>
          <path
            d="m15.1501 19.6747h-12.16857c-1.64665 0-2.98153-1.3349-2.98153-2.9815 0-1.6469 1.33463-2.9822 2.98153-2.9831l6.89508-.0034c1.13429-.0006 2.18239.6047 2.74879 1.5874z"
            fill="#1e6efa"></path>
          <path
            d="m2.25879 12.0296 6.0843-10.53834c.82333-1.4260409 2.64681-1.91464 4.07281-1.091313 1.4263.823453 1.9154 2.646933 1.0927 4.073593l-3.4446 5.97306c-.56661.9826-1.61493 1.5876-2.74918 1.5868z"
            fill="#ff3c5a"></path>
          <path
            d="m15.344 4.68799 6.0843 10.53831c.8234 1.4261.3348 3.2495-1.0913 4.0729-1.4262.8234-3.25.3352-4.0741-1.0906l-3.4506-5.9696c-.5676-.982-.5674-2.1924.0004-3.17427z"
            fill="#ffc5ce"></path>
        </g>
      </svg>
    )
  },
  ComplexGmbH: function() {
    return (
      <img
        title="complex-it.de"
        src="img/logo_complexgmbh.png"
        height={LogoHeight}
      />
    )
  },
  Celtra: function() {
    return (
      <svg
        height={LogoHeight}
        viewBox="0 0 122 59"
        fill="none"
        xmlns="http://www.w3.org/2000/svg">
        <title>{"Celtra"}</title>
        <path
          d="M13.868 29.432c0-9.043 5.47-15.885 14.46-15.885 6.57 0 11.82 3.89 12.26 10.152h-4.386c-.44-3.753-3.505-6.176-7.67-6.176h-.423c-6.35 0-9.855 5.289-9.855 11.909 0 6.62 3.505 11.91 9.855 11.91h.44c4.165 0 7.23-2.424 7.67-6.177h4.386c-.44 6.261-5.69 10.152-12.26 10.152-8.99.017-14.477-6.825-14.477-15.885zM42.976 33.8c0-7.644 5.029-11.432 10.21-11.432 5.69 0 9.28 3.976 9.28 9.708V34.5H47.14c.271 5.033 3.454 7.286 6.13 7.286h.355c2.15 0 4.2-1.11 4.64-3.447h4.165c-.796 4.453-4.605 6.978-9.11 6.978-5.435.017-10.345-3.787-10.345-11.516zM58.3 31.206c-.17-3.839-2.456-5.289-4.945-5.289H53c-2.27 0-4.826 1.365-5.605 5.29H58.3zM66.292 15.748h4.165V44.89h-4.165V15.748zM77.552 40.028V26.429h-4.825v-3.617h4.825v-7.064h4.166v7.064h6.13v3.617h-6.13v12.933c0 1.331.017 1.758.017 1.758h6.112v3.753h-5.469c-3.082.017-4.826-1.757-4.826-4.845zM91.014 22.812h3.945v4.863c.88-3.31 3.505-5.085 6.35-5.085h1.1v4.061h-.88c-3.945 0-6.35 2.645-6.35 7.064v11.158h-4.165v-22.06zM118.19 44.89l-.22-3.532c-.881 1.98-3.505 3.976-7.01 3.976-4.166 0-7.231-2.782-7.231-6.535 0-5.033 4.42-6.535 7.976-6.842l6.045-.478v-.7c0-3.087-1.744-4.862-4.555-4.862h-.356c-2.286 0-4.25 1.11-4.504 3.31h-4.165c.271-4.06 3.894-6.842 8.856-6.842 5.824 0 8.889 3.89 8.889 8.378V44.89h-3.725zm-.44-7.951v-2.252l-5.469.444c-2.54.221-4.386 1.45-4.386 3.48 0 1.809 1.49 3.174 3.556 3.174h.355c2.659.017 5.944-2.201 5.944-4.846zM122.001 55.041H.119V59h121.882V55.04zM122 0H13.986v3.958H122V0zM3.928.103H0V44.89h3.928V.103z"
          fill="#000"
        />
      </svg>
    )
  },
  Hasura: function() {
    return (
      <svg
        viewBox="0 0 468 140"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        height={LogoHeight}>
        <title>hasura.io</title>
        <path
          d="M133.607 47.673c4.034-12.558 1.608-37.609-6.207-46.857-1.024-1.214-2.931-1.04-3.782.299l-9.626 15.11c-2.379 3.025-6.665 3.718-9.895 1.607C93.651 10.994 81.173 7.023 67.765 7.023c-13.408 0-25.886 3.97-36.332 10.809-3.214 2.11-7.5 1.402-9.895-1.607l-9.626-15.11C11.06-.225 9.155-.382 8.13.815.316 10.08-2.11 35.132 1.923 47.674c1.339 4.175 1.701 8.586.914 12.872-.788 4.254-1.576 9.39-1.576 12.967C1.261 110.238 31.039 140 67.749 140c36.726 0 66.489-29.778 66.489-66.488 0-3.577-.788-8.713-1.576-12.967-.772-4.286-.394-8.697.945-12.872zm-65.858 77.485c-28.391 0-51.473-23.097-51.473-51.489 0-.93.032-1.843.079-2.757 1.024-19.348 12.778-35.875 29.4-43.753 6.664-3.183 14.132-4.947 22.01-4.947 7.878 0 15.33 1.764 22.01 4.963 16.623 7.877 28.376 24.42 29.4 43.753.048.914.079 1.843.079 2.757-.016 28.376-23.113 51.473-51.505 51.473z"
          fill="#1EB4D4"
        />
        <path
          d="M90.06 93.49L76.902 70.676l-11.28-19.017a1.474 1.474 0 00-1.277-.725H53.57c-.535 0-1.024.284-1.292.756a1.465 1.465 0 00.016 1.481l10.793 18.135-14.48 22.09c-.299.456-.315 1.039-.063 1.512a1.48 1.48 0 001.308.772h10.856c.504 0 .977-.252 1.244-.678l7.83-12.226 7.028 12.179c.268.457.756.74 1.276.74h10.698a1.45 1.45 0 001.276-.74 1.436 1.436 0 000-1.465zM195.558 35.446h13.723v75.249h-13.723V78.632h-15.503v32.078h-13.723V35.446h13.723v32.677h15.503V35.446zM251.616 110.71l-2.867-15.629h-16.465l-2.631 15.629H215.93l15.141-75.248h18.481l15.866 75.248h-13.802zM234.08 84.698h12.762l-6.554-36.017-6.208 36.017zM295.984 96.987V80.885c0-1.276-.236-2.127-.709-2.568-.473-.441-1.355-.662-2.631-.662h-9.658c-8.193 0-12.29-3.97-12.29-11.927V47.263c0-7.878 4.286-11.8 12.873-11.8h13.124c8.587 0 12.872 3.938 12.872 11.8v10.493h-13.833V49.17c0-1.276-.237-2.127-.709-2.568-.473-.44-1.355-.661-2.631-.661h-4.538c-1.355 0-2.269.22-2.741.661-.473.441-.709 1.292-.709 2.568V64.31c0 1.277.236 2.127.709 2.569.472.44 1.386.661 2.741.661h9.422c8.35 0 12.526 3.892 12.526 11.69v19.68c0 7.877-4.333 11.8-12.999 11.8h-12.888c-8.665 0-12.998-3.938-12.998-11.8V88.527h13.707v8.46c0 1.277.237 2.127.709 2.569.473.44 1.387.661 2.742.661h4.537c1.276 0 2.143-.22 2.631-.661.489-.442.741-1.292.741-2.569zM346.417 35.446h13.708v63.448c0 7.878-4.333 11.801-12.999 11.801h-14.542c-8.666 0-12.998-3.939-12.998-11.801V35.446h13.723v61.541c0 1.277.236 2.127.709 2.569.472.44 1.355.661 2.631.661h6.318c1.355 0 2.269-.22 2.741-.661.473-.442.709-1.292.709-2.569v-61.54zM385.176 81.374v29.336h-13.707V35.446h27.666c8.666 0 12.999 3.94 12.999 11.801v22.31c0 6.523-2.899 10.336-8.713 11.454l12.526 29.699h-14.795l-11.454-29.336h-4.522zm0-35.434v25.287h9.894c1.277 0 2.143-.22 2.632-.662.472-.44.709-1.292.709-2.568V49.17c0-1.276-.237-2.127-.709-2.568-.473-.44-1.355-.661-2.632-.661h-9.894zM453.634 110.71l-2.868-15.629h-16.464l-2.631 15.629h-13.708l15.141-75.248h18.482l15.865 75.248h-13.817zm-17.52-26.012h12.762l-6.555-36.017-6.207 36.017z"
          fill="#1EB4D4"
        />
      </svg>
    )
  },
/** @param {{language?: string, siteConfig: typeof import("../../siteConfig")}} props */
function HomeSplash(props) {
  const { siteConfig } = props
  const baseUrl = siteConfig.baseUrl

  /** @param {{children: React.ReactNode}} props */
  const SplashContainer = props => (
    <div className="homeContainer">
      <div className="homeSplashFade">
        <div className="wrapper homeWrapper">{props.children}</div>
      </div>
    </div>
  )

  /** @param {{img_src: string, width?: number, height?: number, className?: string}} props */
  const Logo = props => (
    <img
      src={props.img_src}
      alt="Project Logo"
      className={props.className}
      height={props.width}
      width={props.height}
    />
  )

  /** @param {{children: React.ReactNode, marginBottom?: boolean}} props */
  const PromoSection = props => (
    <div className={`section promoSection ${props.marginBottom ? "mb-4" : ""}`}>
      <div className="promoRow">
        <div className="pluginRowBlock">{props.children}</div>
      </div>
    </div>
  )

  /** @param {{href: string, target?: string, children: React.ReactNode}} props */
  const Button = props => (
    <div className="pluginWrapper buttonWrapper">
      <a className="button" href={props.href} target={props.target}>
        {props.children}
      </a>
    </div>
  )

  const ProjectTitle = () => (
    <h2 className="projectTitle">
      <span className="d-flex justify-center align-center">
        <Logo
          img_src={`${baseUrl}img/favicon.ico`}
          width={40}
          height={40}
          className="mr-3"
        />
        {siteConfig.title}
      </span>
      <small>{siteConfig.tagline}</small>
    </h2>
  )

  const InstallButton = () => (
    <div className="pluginWrapper buttonWrapper">
      <a className="gh-install-btn" href={siteConfig.installUrl}>
        Install on GitHub
      </a>
    </div>
  )

  return (
    <SplashContainer>
      <div className="projLogo">
        <Logo img_src={`${baseUrl}img/kodiak-pr-flow.svg`} />
      </div>
      <div className="inner">
        <ProjectTitle />

        <PromoSection marginBottom>
          <InstallButton />
        </PromoSection>

        <PromoSection>
          <Button href="#quickstart">Quick Start</Button>
          <Button href="#why">Why?</Button>
          <Button href={siteConfig.dashboardUrl}>Dashboard</Button>
        </PromoSection>
      </div>
    </SplashContainer>
  )
}

/** @param {{language: string | undefined, config: typeof import("../../siteConfig") }} props */
function Index(props) {
  const { config: siteConfig, language = "" } = props
  const { baseUrl } = siteConfig

  /** @param {{id?: string, background?: string, children: React.ReactNode, layout?: string, align?: "center" | "left" | undefined, paddingTop?: boolean}} props */
  const Block = ({
    paddingTop = true,
    id,
    background,
    align,
    children,
    layout,
  }) => {
    let padding = ["bottom"]
    if (paddingTop) {
      padding.push("top")
    }
    return (
      <Container padding={padding} id={id} background={background}>
        <GridBlock
          align={align || "center"}
          contents={children}
          layout={layout}
        />
      </Container>
    )
  }

  const QuickStart = () => (
    <Block id="quickstart" align="left">
      {[
        {
          content: `\
1.  Install [the GitHub app](https://github.com/marketplace/kodiakhq#pricing-and-setup)

2.  Create a \`.kodiak.toml\` file in the root of your repository with the following contents

    \`\`\`toml
    # .kodiak.toml
    version = 1
    \`\`\`

3.  [Configure GitHub branch protection](https://help.github.com/en/articles/configuring-protected-branches)

4.  Create an automerge label (default: "automerge")

5.  Start auto merging PRs with Kodiak

    Label your PRs with your \`automerge\` label and let Kodiak do the rest! 🎉

See the [docs](/docs/quickstart) for additional setup information.

If you have any questions please review [our help page](./help).

`,
          image: `${baseUrl}img/undraw_code_review.svg`,
          imageAlign: "left",
          title: "Quickstart",
        },
      ]}
    </Block>
  )

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
          title: "Why?",
        },
      ]}
    </Block>
  )

  /**
   * @param {{children: React.ReactNode}} props
   */
  const Logo = props => <span style={{ margin: "20px" }}>{props.children}</span>

  const Users = () => (
    <Container background="light" padding={["top", "bottom"]}>
      <h2>Users</h2>
      <div
        style={{ display: "flex", flexWrap: "wrap", justifyContent: "center" }}>
        <Logo>
          <Logos.Atomic />
        </Logo>
        <Logo>
          <Logos.Celtra />
        </Logo>
        <Logo>
          <Logos.ComplexGmbH />
        </Logo>
    
        <Logo>
          <Logos.Hasura />
        </Logo>
      </div>
    </Container>
  )

  // Simple & Configurable — a simple configuration file with smart defaults will get you started in minutes
  // Update — update your branches automatically
  // Merge — use Kodiak's simple configuration with GitHub Branch Protection to merge pull requests automatically
  // Delete — remove your old branches automatically

  const Features = () => (
    <Block layout="fourColumn" paddingTop={false}>
      {[
        {
          content: "Keep your PRs up to date with `master` automatically.",
          title: "Auto Update",
        },
        {
          content:
            "Add the `automerge` label or configure Kodiak to auto merge without a label once CI and Approvals pass. Configure Eco Merge to only update branches when necessary.",
          title: "Auto Merge",
        },
        {
          content:
            "A short and sweet configuration file, `.kodiak.toml`, with smart defaults, will get you started in minutes.",
          title: "Simple & Configurable",
        },
        {
          content:
            "Once enabled, Kodiak will use your PR's `title` and `body` along with the PR number to create a rich commit message on merge.",
          title: "Smart Commit Messages",
        },
        {
          content:
            "Kodiak understands there is no I in Team and works well with other Bots. Combine Kodiak with a dependency bot ([dependabot](https://dependabot.com), [snyk](https://snyk.io), [greenskeeper.io](https://greenkeeper.io)) to automate updating of dependencies.",
          title: "Bot Collaboration",
        },
        {
          content:
            "When configured, Kodiak will comment on your PR if a merge conflict gets in the way of an auto merge.",
          title: "Merge Conflict Alerts",
        },
        {
          content:
            "Remove your old branches automatically. Kodiak will cleanup after auto merging your PR. GitHub has this built in but Kodiak deletes those old branches faster.",
          title: "Tidy Up",
        },
        {
          content:
            "Add a feature, fix a bug, or self host, it's Open Source. Take a [peek under the hood.](https://github.com/chdsbd/kodiak)",
          title: "Open Source",
        },
      ]}
    </Block>
  )

  return (
    <div>
      <HomeSplash siteConfig={siteConfig} language={language} />
      <div className="mainContainer">
        <Features />
        <Users />
        <Why />
        <QuickStart />
      </div>
    </div>
  )
}

module.exports = Index
