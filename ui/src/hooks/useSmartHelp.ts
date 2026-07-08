import { useState, useCallback, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { helpTopics } from '../help/helpTopics'
import { helpCategories } from '../help/helpCategories'
import { resolveContext } from '../help/contextRegistry'
import type { HelpTopic, HelpCategory } from '../help/types'

interface UseSmartHelpReturn {
  topics: HelpTopic[]
  categories: typeof helpCategories
  activeTopic: HelpTopic | null
  searchQuery: string
  selectedCategory: HelpCategory | 'all'
  setSearchQuery: (q: string) => void
  setSelectedCategory: (c: HelpCategory | 'all') => void
  openTopic: (topicId: string) => void
  openContext: (contextId: string) => void
  closeTopic: () => void
  filteredTopics: HelpTopic[]
}

function fuzzyMatch(query: string, text: string): boolean {
  const q = query.toLowerCase()
  const t = text.toLowerCase()
  if (t.includes(q)) return true
  // Simple fuzzy: all chars of query appear in order in text
  let qi = 0
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) qi++
  }
  return qi === q.length
}

export function useSmartHelp(): UseSmartHelpReturn {
  const { i18n } = useTranslation()
  const lang = (i18n.language === 'ar' ? 'ar' : 'en') as 'en' | 'ar'
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<HelpCategory | 'all'>('all')
  const [activeTopicId, setActiveTopicId] = useState<string | null>(null)

  const activeTopic = useMemo(
    () => helpTopics.find(t => t.id === activeTopicId) ?? null,
    [activeTopicId]
  )

  const filteredTopics = useMemo(() => {
    let results = helpTopics

    if (selectedCategory !== 'all') {
      results = results.filter(t => t.category === selectedCategory)
    }

    if (searchQuery.trim()) {
      const q = searchQuery.trim()
      results = results.filter(t => {
        const searchText = [
          t.title[lang],
          t.description[lang],
          t.content[lang],
          ...t.tags,
        ].join(' ')
        return fuzzyMatch(q, searchText)
      })
    }

    return results
  }, [searchQuery, selectedCategory, lang])

  const openTopic = useCallback((topicId: string) => {
    setActiveTopicId(topicId)
  }, [])

  const openContext = useCallback((contextId: string) => {
    const topicId = resolveContext(contextId)
    if (topicId) setActiveTopicId(topicId)
  }, [])

  const closeTopic = useCallback(() => {
    setActiveTopicId(null)
  }, [])

  return {
    topics: helpTopics,
    categories: helpCategories,
    activeTopic,
    searchQuery,
    selectedCategory,
    setSearchQuery,
    setSelectedCategory,
    openTopic,
    openContext,
    closeTopic,
    filteredTopics,
  }
}
