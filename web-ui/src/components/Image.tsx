import React from "react"

export function Image({
  url,
  size,
  alt,
  className,
}: {
  url: string
  size: number
  alt: string
  className: string
}) {
  return (
    <img
      src={url}
      alt={alt}
      width={size}
      height={size}
      className={`rounded ${className}`}
    />
  )
}
