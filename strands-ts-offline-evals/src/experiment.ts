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
  /** Datapoints whose task threw. Their sessions have the error in `metadata.error` and no scores. */
  readonly failedDatapoints: number
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

/**
 * Runs an offline experiment with the HoneyHive runs API.
 *
 * It links runs, sessions, and datapoints the same way as the Python SDK's evaluate(): one
 * session per datapoint, with `run_id`, `dataset_id`, and `datapoint_id` in session metadata.
 * Evaluator scores go on the session event as metrics.
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
  let failedDatapoints = 0
  const queue = [...dataset.datapoints]

  async function score(datapoint: Datapoint, output: string): Promise<Record<string, number | boolean>> {
    const metrics: Record<string, number | boolean> = {}
    for (const [evaluatorName, evaluator] of Object.entries(evaluators)) {
      try {
        const value = await evaluator({ datapoint, output })
        if (value !== undefined) metrics[evaluatorName] = value
      } catch (error) {
        // One failing evaluator must not discard the other scores for this datapoint.
        console.warn(`Evaluator ${evaluatorName} failed on ${datapoint.id}: ${errorMessage(error)}`)
      }
    }
    return metrics
  }

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
      failedDatapoints += 1
      await client.events.update({ event_id: sessionId, metadata: { error: errorMessage(error) } })
      return
    }

    await client.events.update({
      event_id: sessionId,
      outputs: { answer: output },
      metrics: await score(datapoint, output),
      ...(datapoint.ground_truth ? { feedback: { ground_truth: datapoint.ground_truth } } : {}),
    })
  }

  try {
    const workers = Array.from({ length: Math.min(concurrency, queue.length) }, async () => {
      for (let datapoint = queue.shift(); datapoint; datapoint = queue.shift()) {
        await runDatapoint(datapoint)
      }
    })
    await Promise.all(workers)
    await flush()
  } catch (error) {
    // Close the run so it does not stay in "running" in the HoneyHive UI.
    await flush()
    await client.experiments.updateRun({ run_id: runId, status: 'failed', event_ids: sessionIds })
    throw error
  }

  await client.experiments.updateRun({
    run_id: runId,
    status: 'completed',
    event_ids: sessionIds,
    metadata: { failed_datapoints: failedDatapoints },
  })

  return { runId, sessionIds, failedDatapoints }
}
