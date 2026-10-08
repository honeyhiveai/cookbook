import 'dotenv/config'
import { provider } from './tracing.js' // Import before Strands so its spans go to HoneyHive
import { createHash, randomUUID } from 'node:crypto'
import { Client } from '@honeyhive/api-client'
import { Agent, tool } from '@strands-agents/sdk'
import { OpenAIModel } from '@strands-agents/sdk/models/openai'
import OpenAI from 'openai'
import { z } from 'zod'

// 1. The agent under test. Replace it with your own.
const CATALOG: Record<string, { price_usd: number; stock: number; warranty_years: number }> = {
  'trail-runner-2': { price_usd: 129, stock: 14, warranty_years: 1 },
  'summit-jacket': { price_usd: 249, stock: 0, warranty_years: 3 },
  'basecamp-tent-4p': { price_usd: 419, stock: 6, warranty_years: 5 },
}

const getProduct = tool({
  name: 'get_product',
  description: 'Look up price, stock, and warranty for a product by its SKU.',
  inputSchema: z.object({ sku: z.string() }),
  callback: ({ sku }) => CATALOG[sku] ?? { error: `Unknown SKU: ${sku}` },
})

const calculator = tool({
  name: 'calculator',
  description: 'Multiply a unit price by a quantity.',
  inputSchema: z.object({ unit_price: z.number(), quantity: z.number() }),
  callback: ({ unit_price, quantity }) => unit_price * quantity,
})

async function runAgent(question: string, sessionId: string): Promise<string> {
  // A fresh agent per datapoint, so datapoints never share conversation state.
  const agent = new Agent({
    model: new OpenAIModel({ modelId: 'gpt-4.1-mini' }),
    tools: [getProduct, calculator],
    systemPrompt:
      'You are a support agent for an outdoor gear store. Use get_product for any product fact ' +
      'and calculator for any total. Answer in one or two sentences.',
    printer: false,
    traceAttributes: { 'honeyhive.session_id': sessionId }, // Puts the agent's spans in this session
  })
  return String(await agent.invoke(question))
}

// 2. The dataset.
const dataset = [
  { question: 'How much do 3 pairs of trail-runner-2 cost?', answer: '$387' },
  { question: 'Is the summit-jacket in stock?', answer: 'No, the summit-jacket is out of stock.' },
  { question: 'What warranty comes with the basecamp-tent-4p?', answer: '5 years' },
]

// 3. The evaluators. Each returns a number or a boolean, which HoneyHive aggregates across the run.
const openai = new OpenAI()

async function correctness(question: string, answer: string, reference: string): Promise<boolean> {
  const response = await openai.chat.completions.create({
    model: 'gpt-4.1-mini',
    temperature: 0,
    response_format: { type: 'json_object' },
    messages: [
      {
        role: 'system',
        content:
          'You grade a support agent. Return JSON {"correct": boolean}. correct is true only if ' +
          'the answer states the same facts as the reference. Ignore wording.',
      },
      { role: 'user', content: JSON.stringify({ question, reference, answer }) },
    ],
  })
  return JSON.parse(response.choices[0]?.message.content ?? '{}').correct === true
}

function concise(answer: string): boolean {
  return answer.split(/[.!?](?:\s|$)/).filter((sentence) => sentence.trim()).length <= 2
}

// 4. The experiment. One session per datapoint, linked to the run and the datapoint.
const client = new Client() // Reads HH_PROJECT_API_KEY and HH_DATA_PLANE_URL

// The EXT- prefix marks a dataset that lives in your code, not in HoneyHive.
const extId = (value: string) => `EXT-${createHash('sha256').update(value).digest('hex').slice(0, 16)}`
const datasetId = extId(JSON.stringify(dataset))
const datapointIds = dataset.map((point) => extId(point.question))

const { run_id } = await client.experiments.createRun({
  name: `strands-support-agent-${new Date().toISOString().slice(0, 16)}`,
  status: 'running',
  dataset_id: datasetId,
  datapoint_ids: datapointIds,
})

const sessionIds: string[] = []
try {
  for (const [index, point] of dataset.entries()) {
    const sessionId = randomUUID()
    await client.sessions.create({
      session_id: sessionId,
      session_name: 'strands-support-agent',
      source: 'evaluation',
      inputs: { question: point.question },
      metadata: { run_id, dataset_id: datasetId, datapoint_id: datapointIds[index] },
    })
    sessionIds.push(sessionId)

    const answer = await runAgent(point.question, sessionId)
    await client.events.update({
      event_id: sessionId,
      outputs: { answer },
      feedback: { ground_truth: { answer: point.answer } },
      metrics: {
        correctness: await correctness(point.question, answer, point.answer),
        concise: concise(answer),
      },
    })
  }
  await provider.forceFlush() // Send all spans before the run closes
  await client.experiments.updateRun({ run_id, status: 'completed', event_ids: sessionIds })
} catch (error) {
  await client.experiments.updateRun({ run_id, status: 'failed', event_ids: sessionIds })
  throw error
} finally {
  await provider.shutdown()
}

const { evaluation } = await client.experiments.getRun({ run_id })
const appUrl = process.env.HH_APP_URL || 'https://app.us.honeyhive.ai'
console.log(`Results: ${appUrl}/p/${evaluation.scope_id}/experiments/runs/${run_id}`)
