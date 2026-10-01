import { Component, type ReactNode } from 'react'

interface Props {
  resetKey: string
  onError: (message: string) => void
  children: ReactNode
}

interface State {
  hasError: boolean
  resetKey: string
}

/** Isolates a single model so one broken GLB never takes down the whole scene. */
export class ModelErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, resetKey: props.resetKey }
  }

  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    return props.resetKey !== state.resetKey ? { hasError: false, resetKey: props.resetKey } : null
  }

  static getDerivedStateFromError(): Partial<State> {
    return { hasError: true }
  }

  componentDidCatch(error: Error) {
    this.props.onError(error.message)
  }

  render() {
    return this.state.hasError ? null : this.props.children
  }
}
