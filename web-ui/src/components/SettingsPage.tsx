import React from "react"
import { sleep } from "../sleep"
import { WebData } from "../webdata"
import { Spinner } from "./Spinner"

const data = { notifyOnExceedBilledSeats: true }

export function SettingsPage() {
  const { data, updateSettings } = useSettingsData()
  return <SettingsPageInner data={data} updateSettings={updateSettings} />
}

function useSettingsData(): {
  data: WebData<ISettingsData>
  updateSettings: (settings: ISettingsData) => void
} {
  const [state, setState] = React.useState<WebData<ISettingsData>>({
    status: "loading",
  })

  React.useEffect(() => {
    sleep(400).then(() => {
      setState({ status: "success", data })
    })
  }, [])

  // TODO(sbdchd): handle updates
  function updateSettings() {}

  return { data: state, updateSettings }
}

interface ISettingsData {
  notifyOnExceedBilledSeats: boolean
}

interface ISettingsPageInnerProps {
  data: WebData<ISettingsData>
  updateSettings: (data: ISettingsData) => void
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

function SettingsPageContainer({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <h2>Settings</h2>
      {children}
    </div>
  )
}
