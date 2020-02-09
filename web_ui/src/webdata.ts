export type WebData<T> =
  | { readonly status: "loading" }
  | { readonly status: "refetching"; readonly data: T }
  | { readonly status: "success"; readonly data: T }
  | { readonly status: "failure" }
