import React from "react"
import { WebData } from "../webdata"
import { Spinner } from "./Spinner"
import { Current } from "../world"

export function SettingsPage() {
  const { data, updateSettings } = useSettingsData()
  return <SettingsPageInner data={data} updateSettings={updateSettings} />
}

function useSettingsData(): {
  readonly data: WebData<ISettingsData>
  readonly updateSettings: (settings: ISettingsData) => void
} {
  const [state, setState] = React.useState<WebData<ISettingsData>>({
    status: "loading",
  })

  React.useEffect(() => {
    Current.api
      .getSettings()
      .then(res => {
        setState({ status: "success", data: res })
      })
      .catch(() => {
        setState({ status: "failure" })
      })
  }, [])

  function updateSettings(data: ISettingsData) {
    setState({ status: "success", data: data })
    Current.api
      .updateSettings(data)
      .then(res => {
        setState({ status: "success", data: res })
      })
      .catch(() => {
        setState({ status: "failure" })
      })
  }

  return { data: state, updateSettings }
}

interface ISettingsData {
  readonly notifyOnExceedBilledSeats: boolean
}

interface ISettingsPageInnerProps {
  readonly data: WebData<ISettingsData>
  readonly updateSettings: (data: ISettingsData) => void
}
function SettingsPageInner({ data, updateSettings }: ISettingsPageInnerProps) {
  if (data.status === "loading") {
    return (
      <SettingsPageContainer>
        <Spinner />
      </SettingsPageContainer>
    )
  }
  if (data.status === "failure") {
    return (
      <SettingsPageContainer>
        <p>failure...</p>
      </SettingsPageContainer>
    )
  }

  const handleSettingsChange = (e: React.MouseEvent) => {
    updateSettings({
      notifyOnExceedBilledSeats: !data.data.notifyOnExceedBilledSeats,
    })
  }
  return (
    <SettingsPageContainer>
      <div>
        <h3 className="h5">Notifications</h3>
        <div className="border border-primary rounded p-2">
          <label className="d-flex align-items-center mb-0">
            <input
              type="checkbox"
              onClick={handleSettingsChange}
              checked={data.data.notifyOnExceedBilledSeats}
              className="mr-2"></input>
            <p className="mb-0">notify me when I’ve exceeded my billed seats</p>
          </label>
        </div>
      </div>
    </SettingsPageContainer>
  )
}

interface ISettingsPageContainerProps {
  readonly children: React.ReactNode
}

function SettingsPageContainer({ children }: ISettingsPageContainerProps) {
  return (
    <div>
      <h2>Settings</h2>
      {children}
    </div>
  )
}
