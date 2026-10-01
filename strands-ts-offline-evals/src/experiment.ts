import { randomUUID } from 'node:crypto'
import { type Client } from '@honeyhive/api-client'
import { type Datapoint, type LoadedDataset } from './dataset.js'
import { type Evaluator } from './evaluators.js'

export interface ExperimentOptions {
  readonly client: Client
  readonly name: string
  readonly dataset: LoadedDataset
  /** Runs the system under test for one datapoint. Every span it emits must carry `sessionId`. */
  readonly task: (datapoint: Datapoint, sessionId: string) => Promise<string>
  readonly evaluators: Readonly<Record<string, Evaluator>>
  /** Flushes buffered spans so they reach HoneyHive before the run closes. */
  readonly flush: () => Promise<void>
  readonly concurrency?: number
}

export interface ExperimentResult {
  readonly runId: string
  readonly sessionIds: readonly string[]
}

/**
 * Runs an offline experiment with the HoneyHive runs API.
 *
 * It follows the same contract as the Python SDK's evaluate(): one session per datapoint,
 * linked to the run through `run_id`, `dataset_id`, and `datapoint_id` in session metadata,
 * with outputs, ground truth, and evaluator scores written to the session event.
 */
export async function runExperiment(options: ExperimentOptions): Promise<ExperimentResult> {
  const { client, name, dataset, task, evaluators, flush, concurrency = 4 } = options

  const { run_id: runId } = await client.experiments.createRun({
    name,
    status: 'running',
    dataset_id: dataset.datasetId,
    datapoint_ids: dataset.datapoints.map((point) => point.id),
    configuration: { evaluators: Object.keys(evaluators), concurrency },
  })

  const sessionIds: string[] = []
  const queue = [...dataset.datapoints]

  async function runDatapoint(datapoint: Datapoint): Promise<void> {
    const sessionId = randomUUID()
    sessionIds.push(sessionId)

    // Create the session first. The agent's spans join it through honeyhive.session_id.
    await client.sessions.create({
      session_id: sessionId,
      session_name: name,
      source: 'evaluation',
      inputs: datapoint.inputs,
      metadata: { run_id: runId, dataset_id: dataset.datasetId, datapoint_id: datapoint.id },
    })

    let output: string
    try {
      output = await task(datapoint, sessionId)
    } catch (error) {
      // A failed datapoint stays in the run with its error, so it is visible next to the passes.
      await client.events.update({
        event_id: sessionId,
        metadata: { error: error instanceof Error ? error.message : String(error) },
      })
      return
    }

    const metrics: Record<string, number | boolean> = {}
    for (const [evaluatorName, evaluator] of Object.entries(evaluators)) {
      metrics[evaluatorName] = await evaluator({ datapoint, output })
    }

    await client.events.update({
      event_id: sessionId,
      outputs: { answer: output },
      metrics,
      ...(datapoint.ground_truth ? { feedback: { ground_truth: datapoint.ground_truth } } : {}),
    })
  }

  const workers = Array.from({ length: Math.min(concurrency, queue.length) }, async () => {
    for (let datapoint = queue.shift(); datapoint; datapoint = queue.shift()) {
      await runDatapoint(datapoint)
    }
  })
  await Promise.all(workers)
  await flush()

  await client.experiments.updateRun({
    run_id: runId,
    status: 'completed',
    event_ids: sessionIds,
    ...(dataset.datasetId.startsWith('EXT-') ? { metadata: { offline_dataset_id: dataset.datasetId } } : {}),
  })

  return { runId, sessionIds }
}
