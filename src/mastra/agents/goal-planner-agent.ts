import { Agent } from '@mastra/core/agent';
import { z } from 'zod';
import { getSystemPrompt } from '../prompts';
import { getActiveModelConfig } from '../lib/model-config';

const promptContent = await getSystemPrompt('goal_planner_agent');

// Define the output schema matching GoalPlannerOutput interface
const goalPlannerOutputSchema = z.object({
  problem_understanding: z.string(),
  tasks: z.array(
    z.object({
      name: z.string(),
      estimated_duration_hours: z.number(),
      priority: z.string(),
      dependencies: z.array(z.string()).optional(),
      notes: z.string().optional(),
    })
  ),
  prioritization_logic: z.string(),
  daily_plan: z.array(z.string()),
  risks: z.array(z.string()),
  recommendations: z.array(z.string()),
});

export const goalPlannerAgent = new Agent({
  id: 'goal-planner-agent',
  name: 'Goal Planner Agent',
  instructions: promptContent,
  model: getActiveModelConfig() as any,
  outputSchema: goalPlannerOutputSchema,
} as any);
