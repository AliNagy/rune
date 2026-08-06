#!/usr/bin/env node
// Generates an OpenCode variant of Rune from the canonical Claude Code source.
//
//   node scripts/sync-opencode.mjs [--provider <id>] [--target <dir>] [--dry-run]
//
// Claude Code namespaces plugin skills as /rune:<name>. OpenCode has no plugin
// namespace, so every skill and agent is emitted with a literal rune- prefix
// instead, and cross-references in skill bodies are rewritten to match.

import { readFileSync, writeFileSync, mkdirSync, readdirSync, rmSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { homedir } from 'node:os'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')

const argv = process.argv.slice(2)
const arg = (n, d) => { const i = argv.indexOf(`--${n}`); return i === -1 ? d : argv[i + 1] }
const DRY = argv.includes('--dry-run')
const PROVIDER = arg('provider', 'opencode')
const TARGET = arg('target', join(homedir(), '.config', 'opencode'))

const TIER = { fast: `${PROVIDER}/claude-sonnet-5`, strong: `${PROVIDER}/claude-opus-5` }

// name -> [tier, may write files, may edit files]
const AGENTS = {
  surveyor: ['fast', true, false],
  triage: ['fast', false, false],
  planner: ['strong', true, true],
  executor: ['fast', true, true],
  verifier: ['fast', false, false],
}

const AI_SKILLS = [
  'taskfmt', 'serena', 'oracle', 'survey', 'decompose', 'report', 'recover',
  'bug', 'feature', 'refactor', 'investigate', 'research', 'drift', 'verify',
  'ledger',
]

// Claude Code's /rune:init becomes OpenCode's /rune-init; bare ai-* skill
// references pick up the prefix they lose without a plugin namespace.
function rewriteBody(text) {
  return text
    .replace(/\/rune:/g, '/rune-')
    .replace(/rune:/g, 'rune-')
    .replace(new RegExp(`\\bai-(${AI_SKILLS.join('|')})\\b`, 'g'), 'rune-ai-$1')
}

function splitFrontmatter(raw) {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/)
  if (!m) throw new Error('no frontmatter')
  const fields = {}
  for (const line of m[1].split(/\r?\n/)) {
    const f = line.match(/^([a-zA-Z-]+):\s*(.*)$/)
    if (f) fields[f[1]] = f[2]
  }
  return { fields, body: m[2] }
}

const write = (path, content) => {
  if (DRY) return
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, content, 'utf8')
}

let skillCount = 0
const skillsOut = join(TARGET, 'skills')

for (const name of readdirSync(join(ROOT, 'skills'))) {
  const src = join(ROOT, 'skills', name, 'SKILL.md')
  if (!existsSync(src)) continue

  const { fields, body } = splitFrontmatter(readFileSync(src, 'utf8'))
  const outName = `rune-${name}`

  // user-invocable is a Claude Code field. OpenCode ignores unknown frontmatter,
  // so it is preserved rather than dropped: harmless now, correct if support lands.
  const fm = [
    '---',
    `name: ${outName}`,
    ...(fields['user-invocable'] ? [`user-invocable: ${fields['user-invocable']}`] : []),
    `description: ${rewriteBody(fields.description)}`,
    '---',
  ].join('\n')

  write(join(skillsOut, outName, 'SKILL.md'), `${fm}\n${rewriteBody(body)}`)
  skillCount++
}

let agentCount = 0
const agentsOut = join(TARGET, 'agents')

for (const [name, [tier, canWrite, canEdit]] of Object.entries(AGENTS)) {
  const src = join(ROOT, 'agents', `${name}.md`)
  if (!existsSync(src)) { console.warn(`  ! missing agents/${name}.md`); continue }

  const { fields, body } = splitFrontmatter(readFileSync(src, 'utf8'))

  // The Claude Code `tools:` list enumerates mcp__serena__* names that do not
  // exist under OpenCode's MCP naming. Coarse write/edit gates are used instead,
  // so read and search tools stay available without naming them.
  const fm = [
    '---',
    `description: ${rewriteBody(fields.description)}`,
    'mode: subagent',
    `model: ${TIER[tier]}`,
    'temperature: 0.1',
    'tools:',
    `  write: ${canWrite}`,
    `  edit: ${canEdit}`,
    '---',
  ].join('\n')

  write(join(agentsOut, `rune-${name}.md`), `${fm}\n${rewriteBody(body)}`)
  agentCount++
}

console.log(`${DRY ? '[dry run] ' : ''}rune -> opencode`)
console.log(`  skills   ${skillCount}  -> ${skillsOut}`)
console.log(`  agents   ${agentCount}  -> ${agentsOut}`)
console.log(`  models   fast=${TIER.fast}  strong=${TIER.strong}`)
if (!DRY) console.log('\nRestart OpenCode, then run /rune-init')
