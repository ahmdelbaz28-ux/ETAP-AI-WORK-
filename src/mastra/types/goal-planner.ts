// TypeScript interfaces for the structured output schema of the goal planner agent

/**
 * Represents the output of the goal planner agent after processing messy input
 */
export interface GoalPlannerOutput {
  /** Brief restatement of the user's input and identified goals/tasks */
  problem_understanding: string;
  /** List of extracted tasks with initial estimates and dependencies */
  tasks: {
    /** Clear description of the task */
    name: string;
    /** Estimated time to complete the task (in hours) */
    estimated_duration_hours: number;
    /** Priority level of the task */
    priority: string;
    /** Dependencies for this task (optional) */
    dependencies?: string[];
    /** Additional notes (e.g., required resources) */
    notes?: string;
  }[];
  /** Explanation of the prioritization criteria used */
  prioritization_logic: string;
  /** Final prioritized task list for the day (as task names) */
  daily_plan: string[];
  /** Notes on assumptions made and potential risks */
  risks: string[];
  /** Suggested adjustments or next steps */
  recommendations: string[];
}
