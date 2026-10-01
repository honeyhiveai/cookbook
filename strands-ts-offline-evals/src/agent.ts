import { Agent, tool } from '@strands-agents/sdk'
import { OpenAIModel } from '@strands-agents/sdk/models/openai'
import { z } from 'zod'

// A small, fixed catalog so the experiment has a ground truth to score against.
const CATALOG: Record<string, { price_usd: number; stock: number; warranty_years: number }> = {
  'trail-runner-2': { price_usd: 129, stock: 14, warranty_years: 1 },
  'summit-jacket': { price_usd: 249, stock: 0, warranty_years: 3 },
  'basecamp-tent-4p': { price_usd: 419, stock: 6, warranty_years: 5 },
}

const getProduct = tool({
  name: 'get_product',
  description: 'Look up price, stock, and warranty for a product by its SKU.',
  inputSchema: z.object({ sku: z.string().describe('Product SKU, for example trail-runner-2') }),
  callback: ({ sku }) => CATALOG[sku] ?? { error: `Unknown SKU: ${sku}` },
})

const calculator = tool({
  name: 'calculator',
  description: 'Multiply a unit price by a quantity.',
  inputSchema: z.object({ unit_price: z.number(), quantity: z.number() }),
  callback: ({ unit_price, quantity }) => unit_price * quantity,
})

/**
 * Builds the agent under test. Each call creates a fresh agent so datapoints never share
 * conversation state, and stamps the HoneyHive session ID on the agent's root span.
 */
export function createSupportAgent(sessionId: string): Agent {
  return new Agent({
    model: new OpenAIModel({ modelId: 'gpt-4.1-mini' }),
    tools: [getProduct, calculator],
    systemPrompt:
      'You are a support agent for an outdoor gear store. Use get_product for any product fact ' +
      'and calculator for any total. Answer in one or two sentences.',
    printer: false,
    traceAttributes: { 'honeyhive.session_id': sessionId },
  })
}
