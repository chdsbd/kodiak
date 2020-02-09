import { sleep } from "./sleep"
import { Api } from "./api"
import { API_ROOT } from "./settings"
import axios from "axios"

interface World {
  api: Api
}

const httpClient = axios.create({
  baseURL: API_ROOT,
})

/** Convert JSON to FormData
 *
 * Our Django app only accepts multi-part and url encoded form data. JSON is not
 * supported.
 */
function jsonToFormData(data: object) {
  const form = new FormData()
  Object.entries(data).forEach(([k, v]) => {
    // tslint:disable-next-line no-unsafe-any
    form.set(k, v)
  })
  return form
}

interface IOAuthCompleteResponseError {
  readonly ok: false
  readonly error: string
  readonly error_description: string
}
interface IOAuthCompleteResponseSuccess {
  readonly ok: true
}
type IOAuthCompleteResponse =
  | IOAuthCompleteResponseSuccess
  | IOAuthCompleteResponseError

interface ILoginUserArgs {
  code: string
  serverState: string
  clientState: string
}

export const Current: World = {
  api: {
    loginUser: async (args: ILoginUserArgs) => {
      try {
        const res = await httpClient.post<IOAuthCompleteResponse>(
          "/v1/oauth_complete",
          jsonToFormData(args),
        )
        return res.data
      } catch (e) {
        // pass
      }
      return {
        ok: false,
        error: "Server Error",
        error_description: "problem contacting backend services.",
      }
    },
    getUsageBilling: async () => {
      await sleep(400)
      return {
        seats: { current: 8, total: 15 },
        nextBillingDate: "February 21st, 2019",
        billingPeriod: { start: "Jan 17", end: "Feb 16" },
        activeUsers: [
          {
            name: "bernard",
            profileImgUrl:
              "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
            interactions: 15,
            lastActiveDate: "Jan 22",
          },
          {
            name: "william",
            profileImgUrl:
              "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
            interactions: 15,
            lastActiveDate: "Jan 22",
          },
          {
            name: "deloris",
            profileImgUrl:
              "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
            interactions: 15,
            lastActiveDate: "Jan 15",
          },
          {
            name: "maeve",
            profileImgUrl:
              "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
            interactions: 15,
            lastActiveDate: "Jan 3",
          },
        ],
        repos: [
          { name: "backend", id: 50234 },
          { name: "api-frontend", id: 23485 },
        ],
        perUserUSD: 5,
        perMonthUSD: 75,
      }
    },
    getSettings: async () => {
      await sleep(400)
      return { notifyOnExceedBilledSeats: true }
    },
    updateSettings: async () => {
      await sleep(400)
      return { notifyOnExceedBilledSeats: false }
    },
    getActivity: async () => {
      await sleep(400)
      return {
        labels: Array(30)
          .fill(0)
          .map((_, i) => `01/${i + 1}/2011 GMT`),
        datasets: {
          approved: Array(30)
            .fill(0)
            .map((_, i) => [13, 23, 20, 8, 13, 27, 4, 4, 5, 6][i % 10]),
          merged: Array(30)
            .fill(0)
            .map((_, i) => [13, 23, 20, 8, 13, 27, 4, 4, 5, 6][i % 10]),
          updated: Array(30)
            .fill(0)
            .map((_, i) => [44, 55, 41, 67, 22, 43, 2, 7, 9, 8][i % 10]),
        },
      }
    },
    getAccounts: async () => {
      await sleep(400)
      return [
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
    },
    getCurrentAccount: async () => {
      await sleep(400)
      const user = {
        name: "sbdchd",
        profileImgUrl:
          "https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
      }
      const org = {
        name: "Kodiak",
        profileImgUrl:
          "https://avatars1.githubusercontent.com/in/29196?s=400&v=4",
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

      return {
        user,
        org,
        accounts,
      }
    },
  },
}
