import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Navbar } from './Navbar'
import { Breadcrumbs } from './Breadcrumbs'
import { TitleBar } from './TitleBar'

export function Layout() {
  const location = useLocation()

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[var(--bg-primary)]">
      <TitleBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          <Navbar />
          <main className="flex-1 overflow-y-auto">
            <div className="p-6 max-w-[1400px] mx-auto w-full">
              <Breadcrumbs path={location.pathname} />
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}
