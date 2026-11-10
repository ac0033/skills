// 设计文档落位测试：新项目第一步装好套件后，产品设计阶段的文档按约定位置和状态写入，巡检与推送核对都不报错。
// 业务含义：设计技能与工程套件共用一套目录和状态用词；这里防止两边再次各说各话（旧位置 docs/design/、中文状态值）。
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { runHygiene } from '../gate/hygiene.mjs';
import { newFileProblems } from '../gate/verify.mjs';
import { normalizeConfig } from '../gate/config.mjs';
import { syncKit } from '../sync.mjs';
import { commitAll, git, read, tmpRepo, write } from './helpers.mjs';

/** 设计阶段的全部产物：路径 → 文件头状态。位置与产品设计技能的共享协议一致。 */
const DESIGN_DOCS = {
  'docs/00-总览/PROJECT_STATE.md': 'active',
  'docs/00-总览/RECORDS.md': 'active',
  'docs/00-总览/IMPLEMENTATION.md': 'draft',
  'docs/01-需求/PRD.md': 'review',
  'docs/02-原型/PROTOTYPE.md': 'draft',
  'docs/03-架构/ARCHITECTURE.md': 'active',
  'docs/adr/ADR-0001-存储选型.md': 'accepted',
};

/** 装好套件并提交基线的新项目，当前在功能分支上。 */
function installedProject() {
  const root = tmpRepo();
  write(root, 'README.md', '# 项目\n');
  commitAll(root, 'init');
  const res = syncKit({ target: root, hooks: false });
  assert.equal(res.ok, true, JSON.stringify(res));
  commitAll(root, 'install kit');
  git(root, ['checkout', '-q', '-b', 'design']);
  return root;
}

test('设计文档：按约定位置和状态写入后，巡检零错误、推送核对不拦位置', () => {
  const root = installedProject();
  for (const [rel, status] of Object.entries(DESIGN_DOCS)) write(root, rel, `# ${rel}\n\n状态：${status}\n\n正文 ${rel}\n`);
  write(root, 'docs/02-原型/prototype/index.html', '<!doctype html><title>原型</title>\n');
  const config = normalizeConfig(JSON.parse(read(root, 'engineering.config.json')));
  assert.deepEqual(newFileProblems(root, config, { newFiles: {} }), []);
  const report = runHygiene(root);
  assert.deepEqual(report.findings.error, [], JSON.stringify(report.findings.error));
});

test('设计文档：旧位置 docs/design/ 被推送核对拦截，中文状态值被巡检报错', () => {
  const root = installedProject();
  write(root, 'docs/design/PRD.md', '状态：draft\n');
  write(root, 'docs/01-需求/PRD.md', '状态：基线\n');
  const config = normalizeConfig(JSON.parse(read(root, 'engineering.config.json')));
  const problems = newFileProblems(root, config, { newFiles: {} });
  assert.ok(problems.some((p) => /docs\/design\/PRD\.md/.test(p)), JSON.stringify(problems));
  const report = runHygiene(root);
  assert.ok(report.findings.error.some((e) => /状态不合法（基线）/.test(e)), JSON.stringify(report.findings.error));
});
