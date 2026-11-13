import { RouterProvider } from 'react-router-dom'
import { router } from './router'
import { RealtimeProvider } from '../providers/RealtimeProvider'
import { useAuth } from '../lib/api'

export default function App() {
  const { token } = useAuth()
  return <RealtimeProvider key={token ?? 'guest'}><RouterProvider router={router} /></RealtimeProvider>
}
