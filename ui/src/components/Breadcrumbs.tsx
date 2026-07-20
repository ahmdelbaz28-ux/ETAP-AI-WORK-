import { ChevronRight, Home } from "lucide-react";
import { useTranslation } from "react-i18next";

const routeLabels: Record<string, string> = {
  dashboard: "sidebar.dashboard",
  studies: "sidebar.studies",
  assistant: "sidebar.assistant",
  projects: "sidebar.projects",
  etap: "sidebar.etapIntegration",
  gis: "sidebar.gisIntegration",
  "digital-twin": "sidebar.digitalTwin",
  "asset-management": "sidebar.assetManagement",
  reports: "sidebar.reports",
  "data-import": "sidebar.dataImport",
  "data-export": "sidebar.dataExport",
  settings: "sidebar.settings",
  admin: "sidebar.administration",
  diagnostics: "sidebar.diagnostics",
  logs: "sidebar.logs",
  "code-guard": "sidebar.codeGuard",
};

export function Breadcrumbs({ path }: { path: string }) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  const { t } = useTranslation();
  const segments = path.split("/").filter(Boolean);

  if (segments.length === 0) return null;

  return (
    <nav
      className="flex items-center gap-1.5 text-xs text-[var(--text-muted)] mb-4"
      aria-label="Breadcrumb"
    >
      <Home className="w-3.5 h-3.5" />
      <ChevronRight className="w-3 h-3 opacity-50" />
      {segments.map((segment, i) => {
        const isLast = i === segments.length - 1;
        const labelKey = routeLabels[segment];
        return (
          <span key={`${segment}-${i}`} className="flex items-center gap-1.5">
            <span className={isLast ? "text-[var(--text-secondary)] font-medium" : ""}>
              {labelKey ? t(labelKey) : segment.replaceAll("-", " ")}
            </span>
            {!isLast && <ChevronRight className="w-3 h-3 opacity-50" />}
          </span>
        );
      })}
    </nav>
  );
}
