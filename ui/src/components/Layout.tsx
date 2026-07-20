import { Outlet, useLocation } from "react-router-dom";
import { Breadcrumbs } from "./Breadcrumbs";
import { Navbar } from "./Navbar";
import { Sidebar } from "./Sidebar";
import { TitleBar } from "./TitleBar";

export function Layout() {
  const location = useLocation();

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[var(--bg-primary)] relative">
      {/* Animated ambient background */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden" aria-hidden="true">
        <div className="absolute -top-40 -left-40 w-[500px] h-[500px] bg-gradient-to-br from-[var(--accent-primary)]/4 via-transparent to-transparent rounded-full blur-3xl animate-aurora" />
        <div
          className="absolute -bottom-60 -right-40 w-[600px] h-[600px] bg-gradient-to-tl from-purple-500/4 via-transparent to-transparent rounded-full blur-3xl animate-aurora"
          style={{ animationDelay: "-7s", animationDirection: "reverse" }}
        />
        <div
          className="absolute top-1/2 left-1/3 w-[400px] h-[400px] bg-gradient-to-r from-cyan-500/3 via-transparent to-transparent rounded-full blur-3xl animate-aurora"
          style={{ animationDelay: "-14s" }}
        />
      </div>

      <TitleBar />
      <div className="flex flex-1 overflow-hidden relative z-10">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          <Navbar />
          <main className="flex-1 overflow-y-auto relative">
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[var(--accent-primary)]/1 pointer-events-none" />
            <div className="relative p-6 max-w-[1400px] mx-auto w-full">
              <Breadcrumbs path={location.pathname} />
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
