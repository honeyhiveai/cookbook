import OpenAI from 'openai'
import { type Datapoint } from './dataset.js'

export interface EvaluatorArgs {
  readonly datapoint: Datapoint
  readonly output: string
}

/** A score for one datapoint. HoneyHive aggregates numbers and booleans across the run. */
export type Evaluator = (args: EvaluatorArgs) => Promise<number | boolean> | number | boolean

const openai = new OpenAI()

/**
 * LLM-as-judge for answer correctness. It compares the agent's answer with the reference answer
 * and returns a binary verdict, which is easier to calibrate than a 1-10 scale.
 */
export const correctness: Evaluator = async ({ datapoint, output }) => {
  const reference = datapoint.ground_truth?.answer
  if (typeof reference !== 'string') return false

  const response = await openai.chat.completions.create({
    model: 'gpt-4.1-mini',
    temperature: 0,
    response_format: { type: 'json_object' },
    messages: [
      {
        role: 'system',
        content:
          'You grade a support agent. Return JSON {"correct": boolean}. correct is true only if ' +
          'the answer states the same facts as the reference. Ignore wording and extra politeness.',
      },
      {
        role: 'user',
        content: JSON.stringify({ question: datapoint.inputs.question, reference, answer: output }),
      },
    ],
  })
  const verdict: unknown = JSON.parse(response.choices[0]?.message.content ?? '{}')
  return typeof verdict === 'object' && verdict !== null && 'correct' in verdict && verdict.correct === true
}

/** Deterministic check that the answer stays within the system prompt's two-sentence limit. */
export const concise: Evaluator = ({ output }) => output.split(/[.!?](\s|$)/).filter((s) => s.trim()).length <= 2
