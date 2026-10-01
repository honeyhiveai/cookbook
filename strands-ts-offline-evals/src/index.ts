import 'dotenv/config'
import { Client } from '@honeyhive/api-client'
import { createSupportAgent } from './agent.js'
import { INLINE_DATASET, loadHoneyHiveDataset, prepareInlineDataset } from './dataset.js'
import { concise, correctness } from './evaluators.js'
import { runExperiment } from './experiment.js'
import { setupTracing } from './tracing.js'

const projectApiKey = process.env.HH_PROJECT_API_KEY
const dataPlaneUrl = process.env.HH_DATA_PLANE_URL ?? 'https://api.dp1.us.honeyhive.ai'
if (!projectApiKey) throw new Error('Set HH_PROJECT_API_KEY to a HoneyHive project API key')
if (!process.env.OPENAI_API_KEY) throw new Error('Set OPENAI_API_KEY for the agent and the LLM judge')

// Register the tracer provider before the first agent runs, so Strands spans go to HoneyHive.
const provider = setupTracing(projectApiKey, dataPlaneUrl)
const client = new Client({ projectApiKey, dataPlaneUrl })

try {
  const datasetId = process.env.HH_DATASET_ID
  const dataset = datasetId
    ? await loadHoneyHiveDataset(client, datasetId)
    : prepareInlineDataset(INLINE_DATASET)

  const { runId, sessionIds, failedDatapoints } = await runExperiment({
    client,
    name: `strands-ts-support-agent-${new Date().toISOString().slice(0, 16)}`,
    dataset,
    task: async (datapoint, sessionId) => {
      const result = await createSupportAgent(sessionId).invoke(String(datapoint.inputs.question))
      return String(result)
    },
    evaluators: { correctness, concise },
    flush: () => provider.forceFlush(),
  })

  // The run belongs to the project of the API key. Its scope_id is the project ID that the app URL uses.
  const { evaluation } = await client.experiments.getRun({ run_id: runId })
  const appUrl = process.env.HH_APP_URL ?? 'https://app.us.honeyhive.ai'
  console.log(`Ran ${sessionIds.length} datapoints, ${failedDatapoints} failed.`)
  console.log(`Results: ${appUrl}/p/${evaluation.scope_id}/experiments/runs/${runId}`)
  console.log(`Session IDs: ${sessionIds.join(' ')}`)
} finally {
  await provider.shutdown() // Flush spans before the process exits
}
