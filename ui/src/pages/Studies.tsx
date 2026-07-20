import { motion } from "framer-motion";
import { Beaker, BookOpen, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Badge, Card } from "../components/ui";
import { fetchStudyTypes } from "../lib/api";
import { studyCategories } from "../lib/studyCategories";
import { cn } from "../utils/helpers";

import { ContextHelpButton } from "../components/help/ContextHelpButton";
const categoryColors: Record<string, string> = {
  load_flow: "from-blue-500 to-blue-700",
  short_circuit: "from-amber-500 to-orange-600",
  arc_flash: "from-red-500 to-red-700",
  harmonic_analysis: "from-purple-500 to-purple-700",
  protection_coordination: "from-cyan-500 to-cyan-700",
  motor_starting: "from-green-500 to-emerald-700",
  optimal_power_flow: "from-indigo-500 to-indigo-700",
  transient_stability: "from-rose-500 to-pink-700",
};

export default function Studies() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [disabledStudies, setDisabledStudies] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchStudyTypes().then((data) => {
      setDisabledStudies(new Set((data.disabled_studies || []).map((d) => d.study_type)));
    }).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <Beaker className="w-6 h-6 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">{t("studies.title")}</h2>
            <div className="flex items-center gap-2 mt-0.5">
              <p className="text-[var(--text-tertiary)]">{t("studies.subtitle")}</p>
              <ContextHelpButton contextId="studies.overview" />
            </div>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {studyCategories.map((s, index) => {
          const isDisabled = disabledStudies.has(s.id);
          return (
            <motion.div
              key={s.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
            >
              <Card
                variant="interactive"
                padding="md"
                className={cn(
                  "relative overflow-hidden group",
                  isDisabled && "opacity-60 pointer-events-none",
                )}
                onClick={() => !isDisabled && navigate(`/studies/${s.id}`)}
              >
                {/* Gradient accent on top */}
                <div
                  className={cn(
                    "absolute top-0 left-0 right-0 h-1 bg-gradient-to-r",
                    categoryColors[s.id] || "from-brand-500 to-brand-700",
                  )}
                />

                {/* Glow effect on hover */}
                <div className="absolute inset-0 bg-gradient-to-br from-brand-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

                <div className="relative">
                  <div className="flex items-start justify-between">
                    <span className="text-3xl">{s.icon}</span>
                    <div className="flex items-center gap-1.5">
                      {isDisabled && (
                        <Badge variant="warning" size="sm">
                          Coming Soon
                        </Badge>
                      )}
                      {s.standard && (
                        <Badge variant="brand" size="sm">
                          {s.standard}
                        </Badge>
                      )}
                    </div>
                  </div>

                  <h3 className="text-[var(--text-primary)] font-semibold mt-3 group-hover:text-brand-400 transition-colors">
                    {s.name}
                  </h3>
                  <p className="text-sm text-[var(--text-tertiary)] mt-1.5 line-clamp-2">
                    {s.description}
                  </p>

                  <div className="flex items-center justify-between mt-4 pt-3 border-t border-[var(--border-primary)]">
                    <div className="flex items-center gap-1 text-[10px] text-[var(--text-muted)]">
                      <BookOpen className="w-3 h-3" />
                      <span>
                        {s.params.length} {t("studies.parameters")}
                      </span>
                    </div>
                    {!isDisabled && (
                      <div className="flex items-center gap-1.5 text-xs text-brand-400 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Play className="w-3.5 h-3.5" />
                        <span>{t("studies.runStudy")}</span>
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
