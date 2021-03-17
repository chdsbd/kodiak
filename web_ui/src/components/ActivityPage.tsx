import React from "react"
import { WebData } from "../webdata"
import { Spinner } from "./Spinner"
import { PullRequestActivityChart, KodiakActivityChart } from "./ActivityChart"
import formatDistanceToNowStrict from "date-fns/formatDistanceToNowStrict"
import fromUnixTime from "date-fns/fromUnixTime"

import { Current } from "../world"
import { useTeamApi } from "../useApi"
import { IActiveMergeQueue } from "../api"

function NoQueueFound() {
  return <p className="text-muted">No active merge queues to display.</p>
}

function MergeQueues({
  mergeQueues,
}: {
  readonly mergeQueues: IActiveMergeQueue[]
}) {
  return (
    <>
      {mergeQueues.map(repo => (
        <React.Fragment key={repo.repo}>
          <div className="row">
            {repo.queues.map(queue => (
              <div className="col-5" key={repo.repo + queue.branch}>
                <span>
                  {repo.repo} ({queue.branch})
                </span>
                <table className="table table-sm">
                  <thead>
                    <tr>
                      <th scope="col">position</th>
                      <th scope="col">pull request</th>
                      <th scope="col">added</th>
                    </tr>
                  </thead>
                  <tbody>
                    {queue.pull_requests.map((pr, index) => (
                      <tr key={pr.number}>
                        <td scope="row">{index + 1}</td>
                        <td>
                          <a
                            href={`https://github.com/${repo.owner}/${repo.repo}/pull/${pr.number}`}>
                            #{pr.number}
                          </a>
                        </td>
                        <td
                          title={fromUnixTime(
                            pr.added_at_timestamp,
                          ).toLocaleString()}>
                          {formatDistanceToNowStrict(
                            fromUnixTime(pr.added_at_timestamp),
                            {
                              addSuffix: true,
                            },
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </React.Fragment>
      ))}
      {mergeQueues.length === 0 && <NoQueueFound />}
      <p>
        <b>Tip: </b> Move a pull request to the front of the queue with the{" "}
        <a href="https://kodiakhq.com/docs/config-reference#mergepriority_merge_label">
          <code>merge.priority_merge_label</code>{" "}
        </a>
        label.
      </p>
    </>
  )
}

interface IKodiakChartData {
  readonly labels: Array<string>
  readonly datasets: {
    readonly approved: Array<number>
    readonly merged: Array<number>
    readonly updated: Array<number>
  }
}
interface ITotalChart {
  readonly labels: Array<string>
  readonly datasets: {
    readonly opened: Array<number>
    readonly merged: Array<number>
    readonly closed: Array<number>
  }
}
interface IActivityData {
  readonly kodiakActivity: IKodiakChartData
  readonly pullRequestActivity: ITotalChart
  readonly activeMergeQueues: IActiveMergeQueue[]
}

export function ActivityPage() {
  const data = useTeamApi(Current.api.getActivity)
  return <ActivityPageInner data={data} />
}

interface IActivityPageInnerProps {
  readonly data: WebData<IActivityData>
}
function ActivityPageInner({ data }: IActivityPageInnerProps) {
  if (data.status === "initial" || data.status === "loading") {
    return (
      <ActivityPageContainer>
        <Spinner />
      </ActivityPageContainer>
    )
  }
  if (data.status === "failure") {
    return (
      <ActivityPageContainer>
        <p className="text-center text-muted">failed to load activity data</p>
      </ActivityPageContainer>
    )
  }

  return (
    <ActivityPageContainer>
      <h3 className="h5">Pull Requests</h3>
      <PullRequestActivityChart data={data.data.pullRequestActivity} />
      <h3 className="h5">Kodiak</h3>
      <KodiakActivityChart data={data.data.kodiakActivity} />
      <h3 className="h5">Merge Queues</h3>
      <MergeQueues mergeQueues={data.data.activeMergeQueues} />
    </ActivityPageContainer>
  )
}

interface IActivityPageContainer {
  readonly children: React.ReactNode
}
function ActivityPageContainer({ children }: IActivityPageContainer) {
  return (
    <div className="flex-grow-1 d-flex w-100 flex-column">
      <h2>Activity</h2>
      {children}
    </div>
  )
}
