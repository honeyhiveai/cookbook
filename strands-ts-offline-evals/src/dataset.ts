import { createHash } from 'node:crypto'
import { type Client } from '@honeyhive/api-client'

/** One test case. `ground_truth` is optional so the same runner works for unlabeled datasets. */
export interface Datapoint {
  readonly id: string
  readonly inputs: Record<string, unknown>
  readonly ground_truth?: Record<string, unknown>
}

export interface LoadedDataset {
  readonly datasetId: string
  readonly datapoints: readonly Datapoint[]
}

/** Inline test cases. Replace these with your own, or set HH_DATASET_ID to use a HoneyHive dataset. */
export const INLINE_DATASET: readonly Omit<Datapoint, 'id'>[] = [
  {
    inputs: { question: 'How much do 3 pairs of trail-runner-2 cost?' },
    ground_truth: { answer: '$387' },
  },
  {
    inputs: { question: 'Is the summit-jacket in stock?' },
    ground_truth: { answer: 'No, the summit-jacket is out of stock.' },
  },
  {
    inputs: { question: 'What warranty comes with the basecamp-tent-4p?' },
    ground_truth: { answer: '5 years' },
  },
]

function sha16(value: string): string {
  return createHash('sha256').update(value).digest('hex').slice(0, 16)
}

/**
 * Gives inline datapoints stable EXT- IDs. HoneyHive reads the EXT- prefix as an external dataset
 * that is not stored in the project, and the Python SDK's evaluate() uses the same convention.
 */
export function prepareInlineDataset(points: readonly Omit<Datapoint, 'id'>[]): LoadedDataset {
  return {
    datasetId: `EXT-${sha16(JSON.stringify(points))}`,
    datapoints: points.map((point, index) => ({
      ...point,
      id: `EXT-${sha16(`${JSON.stringify(point)}${index}`)}`,
    })),
  }
}

/** Loads a dataset that is stored in HoneyHive, with its datapoints. */
export async function loadHoneyHiveDataset(client: Client, datasetId: string): Promise<LoadedDataset> {
  const { datasets } = await client.datasets.list({ dataset_id: datasetId })
  const dataset = datasets[0]
  if (!dataset) throw new Error(`Dataset not found: ${datasetId}`)

  const datapoints: Datapoint[] = []
  for (const datapointId of dataset.datapoints ?? []) {
    const { datapoint } = await client.datapoints.get({ datapoint_id: datapointId })
    const point = datapoint[0]
    if (!point) continue
    datapoints.push({
      id: datapointId,
      inputs: point.inputs ?? {},
      ...(point.ground_truth ? { ground_truth: point.ground_truth } : {}),
    })
  }
  if (datapoints.length === 0) throw new Error(`Dataset ${datasetId} has no readable datapoints`)
  return { datasetId, datapoints }
}
