import { useEffect, useRef } from 'react'

export function useDebouncedEffect(effect, deps, delay) {
  const efectoRef = useRef(effect)

  useEffect(() => {
    efectoRef.current = effect
  })

  useEffect(() => {
    const timeoutId = setTimeout(() => efectoRef.current(), delay)
    return () => clearTimeout(timeoutId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, delay])
}
