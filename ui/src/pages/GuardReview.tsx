import { RefreshCw, Shield, ShieldAlert, ShieldCheck } from "lucide-react";
// NOSONAR(typescript:S3776,typescript:S2004,typescript:S6478,typescript:S6479,typescript:S3358,typescript:S6759,typescript:S6551,typescript:S2486,typescript:S6819): UI components are intentionally complex for feature-rich DX
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  DataTable,
  TabPanels,
  Tabs,
  Tag,
  Textarea,
  useTabState,
} from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { fetchGuardInfo, guardReview } from "../lib/api";
import type { GuardReviewResult, GuardViolation } from "../lib/api";

type GuardType = "all" | "python" | "typescript";

export default function GuardReview() {
  const [guardInfo, setGuardInfo] = useState<Record<string, { name: string; description: string }>>(
    {},
  );
  const [reviewResult, setReviewResult] = useState<GuardReviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [infoLoading, setInfoLoading] = useState(true);
  const [source, setSource] = useState("");
  const [guardType, setGuardType] = useState<GuardType>("all");
  const [language, setLanguage] = useState<"python" | "typescript">("python");
  const { activeTab, setActiveTab } = useTabState("review");
  const { notify } = useNotify();

  useEffect(() => {
    (async () => {
      try {
        const info = await fetchGuardInfo();
        const map: Record<string, { name: string; description: string }> = {};
        for (const [k, v] of Object.entries(info.guards)) {
          map[k] = { name: v.name, description: v.description };
        }
        setGuardInfo(map);
      } catch {
        // silent
      } finally {
        setInfoLoading(false);
      }
    })();
  }, []);

  const handleReview = useCallback(async () => {
    if (!source.trim()) {
      notify("error", "Please enter source code or a file path");
      return;
    }
    setLoading(true);
    setReviewResult(null);
    try {
      const result = await guardReview(source, guardType, language);
      setReviewResult(result);
      notify(
        "success",
        `Review complete: ${result.must_fix_total} must-fix, ${result.should_fix_total} should-fix`,
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      notify("error", `Review failed: ${msg}`);
    } finally {
      setLoading(false);
    }
  }, [source, guardType, language, notify]);

  const allViolations = useMemo(() => {
    if (!reviewResult) return [];
    const violations: (GuardViolation & { guardName: string })[] = [];
    for (const [_guardKey, guardData] of Object.entries(reviewResult.guard_results)) {
      for (const v of guardData.violations) {
        violations.push({ ...v, guardName: guardData.guard_name });
      }
    }
    return violations;
  }, [reviewResult]);

  const violationColumns = useMemo(
    () => [
      {
        key: "severity",
        label: "Severity",
        render: (row: GuardViolation & { guardName: string }) => {
          const variant =
            row.severity === "must_fix"
              ? "danger"
              : row.severity === "should_fix"
                ? "warning"
                : "default";
          const IconComponent = row.severity === "must_fix" ? ShieldAlert : Shield;
          return (
            <div className="flex items-center gap-1.5">
              <IconComponent className="w-3.5 h-3.5" />
              <Badge variant={variant}>{row.severity.replace("_", " ")}</Badge>
            </div>
          );
        },
      },
      {
        key: "rule_name",
        label: "Rule",
        render: (row: GuardViolation & { guardName: string }) => (
          <div>
            <span className="text-[var(--text-primary)] font-medium">{row.rule_name}</span>
            <span className="text-[var(--text-muted)] text-xs ml-1.5">({row.guardName})</span>
          </div>
        ),
      },
      {
        key: "location",
        label: "Location",
        render: (row: GuardViolation & { guardName: string }) => (
          <code className="text-xs mono-engineering text-[var(--text-muted)]">{row.location}</code>
        ),
      },
      {
        key: "description",
        label: "Description",
        render: (row: GuardViolation & { guardName: string }) => (
          <span className="text-xs text-[var(--text-secondary)] line-clamp-2">
            {row.description}
          </span>
        ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--text-primary)]">Guard Review</h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">
          Run code quality guards against your source code
        </p>
      </div>

      <Tabs
        tabs={[
          { id: "review", label: "Run Review" },
          { id: "info", label: "Guard Info" },
        ]}
        activeTab={activeTab}
        onChange={setActiveTab}
      />
      <TabPanels>
        {activeTab === "review" && (
          <Card padding="lg">
            <div className="space-y-4">
              <Textarea
                label="Source Code"
                value={source}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setSource(e.target.value)}
                placeholder="Paste source code here, or enter a file path..."
                rows={8}
              />
              <div className="flex items-center gap-3">
                <select
                  value={guardType}
                  onChange={(e) => setGuardType(e.target.value as GuardType)}
                  className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-input)] px-3 py-2 text-sm text-[var(--text-primary)]"
                >
                  <option value="all">All Guards</option>
                  {Object.entries(guardInfo).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v.name}
                    </option>
                  ))}
                </select>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value as "python" | "typescript")}
                  className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-input)] px-3 py-2 text-sm text-[var(--text-primary)]"
                >
                  <option value="python">Python</option>
                  <option value="typescript">TypeScript</option>
                </select>
                <Button icon={RefreshCw} onClick={handleReview} loading={loading}>
                  Run Review
                </Button>
              </div>

              {reviewResult && (
                <div className="grid grid-cols-3 gap-3 pt-2">
                  <Card padding="sm" className="border-[var(--color-danger)]/30">
                    <div className="flex items-center gap-2">
                      <ShieldAlert className="w-4 h-4 text-[var(--color-danger)]" />
                      <div>
                        <p className="text-xs text-[var(--text-muted)]">Must Fix</p>
                        <p className="text-lg font-semibold text-[var(--color-danger)] mono-engineering">
                          {reviewResult.must_fix_total}
                        </p>
                      </div>
                    </div>
                  </Card>
                  <Card padding="sm" className="border-[var(--color-warning)]/30">
                    <div className="flex items-center gap-2">
                      <Shield className="w-4 h-4 text-[var(--color-warning)]" />
                      <div>
                        <p className="text-xs text-[var(--text-muted)]">Should Fix</p>
                        <p className="text-lg font-semibold text-[var(--color-warning)] mono-engineering">
                          {reviewResult.should_fix_total}
                        </p>
                      </div>
                    </div>
                  </Card>
                  <Card padding="sm" className="border-[var(--color-brand-500)]/30">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-[var(--color-brand-500)]" />
                      <div>
                        <p className="text-xs text-[var(--text-muted)]">Worth Noting</p>
                        <p className="text-lg font-semibold text-[var(--text-primary)] mono-engineering">
                          {reviewResult.worth_noting_total}
                        </p>
                      </div>
                    </div>
                  </Card>
                </div>
              )}

              {reviewResult && allViolations.length > 0 && (
                <Card padding="md">
                  <DataTable
                    data={allViolations}
                    columns={violationColumns}
                    keyExtractor={(v, i) => `${v.rule_id}-${i}`}
                    pageSize={10}
                  />
                </Card>
              )}

              {reviewResult && allViolations.length === 0 && (
                <div className="text-center py-8">
                  <ShieldCheck className="w-12 h-12 mx-auto text-[var(--color-success)] mb-3" />
                  <p className="text-sm text-[var(--text-secondary)]">
                    All guards passed — no violations found
                  </p>
                </div>
              )}
            </div>
          </Card>
        )}

        {activeTab === "info" && (
          <Card padding="lg">
            {infoLoading ? (
              <p className="text-sm text-[var(--text-muted)]">Loading guard information...</p>
            ) : (
              <div className="space-y-3">
                {Object.entries(guardInfo).map(([k, v]) => (
                  <div
                    key={k}
                    className="flex items-center justify-between p-3 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-primary)]"
                  >
                    <div className="flex items-center gap-3">
                      <Shield className="w-4 h-4 text-[var(--color-brand-500)]" />
                      <div>
                        <p className="text-sm font-medium text-[var(--text-primary)]">{v.name}</p>
                        <p className="text-xs text-[var(--text-muted)]">{v.description}</p>
                      </div>
                    </div>
                    <Tag variant="brand">{k}</Tag>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}
      </TabPanels>
    </div>
  );
}
