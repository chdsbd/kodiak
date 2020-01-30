import React from "react"

export function SettingsPage() {
  const settings = { notifyOnExceedBilledSeats: true }
  return (
    <div>
      <h2>Settings</h2>
      <div>
        <h3 className="h5">Notifications</h3>
        <div className="border border-primary rounded p-2">
          <label className="d-flex align-items-center mb-0">
            <input
              type="checkbox"
              checked={settings.notifyOnExceedBilledSeats}
              className="mr-2"></input>

            <p className="mb-0">notify me when I’ve exceeded my billed seats</p>
          </label>
        </div>
      </div>
    </div>
  )
}
