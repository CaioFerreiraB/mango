// Self-check: `npx tsx src/lib/echart-tema.check.ts`
import assert from "node:assert/strict"

import { comAlfa } from "./echart-tema"

assert.equal(comAlfa("rgba(10, 20, 30, 1)", 0.5), "rgba(10, 20, 30,0.5)")
assert.equal(comAlfa("rgb(10, 20, 30)", 0), "rgba(10, 20, 30,0)")
assert.equal(comAlfa("#ffffff", 0), "rgba(255,255,255,0)")
assert.equal(comAlfa("#0f8", 0.28), "rgba(0,255,136,0.28)")
console.log("echart-tema: ok")
