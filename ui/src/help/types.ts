export interface HelpContent {
  en: string
  ar: string
}

export interface HelpTopic {
  id: string
  category: HelpCategory
  title: HelpContent
  description: HelpContent
  content: HelpContent
  tags: string[]
  navigateTo?: string
  relatedTopics?: string[]
  icon?: string
}

export type HelpCategory =
  | 'getting-started'
  | 'projects'
  | 'fire-alarm'
  | 'engineering'
  | 'reports'
  | 'digital-twin'
  | 'settings'
  | 'troubleshooting'
  | 'keyboard-shortcuts'

export interface ContextMapping {
  contextId: string
  topicId: string
  priority?: number
}

export interface SmartHelpState {
  isOpen: boolean
  activeTopic: string | null
  searchQuery: string
  selectedCategory: HelpCategory | 'all'
}
