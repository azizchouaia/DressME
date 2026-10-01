import { useCallback, useEffect, useRef, useState } from 'react'

export interface Resource<T> {
  data: T | undefined
  error: string | null
  loading: boolean
  reload: () => void
  setData: (updater: (current: T | undefined) => T | undefined) => void
}

/** Minimal async loader with loading/error states and stale-response protection. */
export function useResource<T>(fetcher: () => Promise<T>, deps: readonly unknown[]): Resource<T> {
  const [data, setDataState] = useState<T>()
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState(0)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    fetcherRef
      .current()
      .then((result) => {
        if (active) setDataState(result)
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Something went wrong')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version])

  const reload = useCallback(() => setVersion((v) => v + 1), [])
  const setData = useCallback(
    (updater: (current: T | undefined) => T | undefined) => setDataState(updater),
    [],
  )

  return { data, error, loading, reload, setData }
}
