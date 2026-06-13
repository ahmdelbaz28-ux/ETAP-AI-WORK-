import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { Play, BookOpen, Beaker } from 'lucide-react'
import { studyCategories } from '../lib/studyCategories'

export function Studies() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-brand-500/10">
            <Beaker className="w-6 h-6 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-white">{t('studies.title')}</h2>
            <p className="text-surface-400 mt-0.5">{t('studies.subtitle')}</p>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {studyCategories.map((s, index) => (
          <motion.button
            key={s.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
            onClick={() => navigate(`/studies/${s.id}`)}
            className="bg-surface-800 rounded-xl p-5 border border-surface-700 hover:border-brand-500/50 hover:bg-surface-750 transition-all text-left group relative overflow-hidden"
          >
            {/* Glow effect on hover */}
            <div className="absolute inset-0 bg-gradient-to-br from-brand-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

            <div className="relative">
              <span className="text-3xl">{s.icon}</span>
              <h3 className="text-white font-semibold mt-3 group-hover:text-brand-400 transition-colors">{s.name}</h3>
              <p className="text-sm text-surface-400 mt-1.5 line-clamp-2">{s.description}</p>

              <div className="flex items-center justify-between mt-4">
                {s.standard && (
                  <span className="text-[10px] font-medium text-surface-400 bg-surface-700 px-2 py-0.5 rounded-full">
                    {s.standard}
                  </span>
                )}
                <div className="flex items-center gap-1.5 text-xs text-brand-400 opacity-0 group-hover:opacity-100 transition-opacity ml-auto">
                  <Play className="w-3.5 h-3.5" />
                  <span>{t('studies.runStudy')}</span>
                </div>
              </div>

              <div className="flex items-center gap-1 text-[10px] text-surface-500 mt-2">
                <BookOpen className="w-3 h-3" />
                <span>{s.params.length} {t('studies.parameters')}</span>
              </div>
            </div>
          </motion.button>
        ))}
      </div>
    </div>
  )
}
