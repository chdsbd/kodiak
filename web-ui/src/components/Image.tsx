import React from "react"

interface IImageProps {
  readonly url: string
  readonly size: number
  readonly alt: string
  readonly className: string
}
export function Image({ url, size, alt, className }: IImageProps) {
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
