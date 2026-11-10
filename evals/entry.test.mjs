// 综合插件入口技能的检查。
// 业务含义：入口是用户唯一接触的部分。流程导图里的每个步骤都必须在入口里，并且目标、原则、工具、过关证据四栏齐全；
// 每一步写的工具必须是插件里真实存在的文件、子代理或脚本，不能指向只存在于某个宿主或没有收录的东西。
// 运行：在仓库根目录 node --test evals/entry.test.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { DEFAULTS, LAYOUT_DEFAULTS } from '../engineering-kit/kit/gate/config.mjs';
import { ENTRY_SKILL, PLUGIN_DIR, ROOT } from '../tools/build-plugin.mjs';

const PLUGIN = path.join(ROOT, PLUGIN_DIR);
const ENTRY_DIR = `skills/${ENTRY_SKILL}`;
const REFS = ['process', 'planning', 'build', 'self-review', 'review', 'debugging'];
/** 插件内的相对路径是否存在。 */
const has = (rel) => fs.existsSync(path.join(PLUGIN, rel));
const read = (rel) => fs.readFileSync(path.join(PLUGIN, rel), 'utf8').replace(/\r\n/g, '\n');
const ENTRY = read(`${ENTRY_DIR}/SKILL.md`);

/**
 * 流程导图里的步骤清单（来源：流程导图的四张流程图，共 31 步）。键是入口里的节标题开头。
 * 导图改了步骤，这里和入口要一起改。
 */
export const STEPS = {
  '0. 恢复现场': ['恢复现场'],
  '2. 新项目': ['装工程底座', '需求 PRD', '原型与 UI', '实际走查', '架构设计', '综合评审', '配置闸门'],
  '3. 加功能': ['开工检查', '探索代码库', '澄清问题', '改产品行为?', '功能契约', '方案对比', '用户选定方案'],
  '4. 交付段': ['任务拆解', '逐片开发', '推送前自查', '机械闸门', 'PR 与 CI', '独立复审', '合并与收工', '验收与发布'],
  '5. 修 bug': ['稳定复现', '定位根因', '是需求缺口?', '写失败测试', '最小修复', '查同类与调用方', '自查到合并', '回归入库'],
};
const COLUMNS = ['步骤', '目标', '原则', '工具', '过关证据'];

/** 把入口按二级标题切成节，取出每节里表头为“步骤、目标、原则、工具、过关证据”的表格行。 */
export function stepRows(text) {
  const out = new Map();
  for (const section of text.split(/^## /m).slice(1)) {
    const title = section.split('\n')[0].trim();
    const lines = section.split('\n');
    const head = lines.findIndex((l) => l.replace(/\s/g, '') === `|${COLUMNS.join('|')}|`);
    if (head < 0) continue;
    const rows = [];
    for (const line of lines.slice(head + 2)) {
      if (!line.startsWith('|')) break;
      rows.push(line.slice(1, line.lastIndexOf('|')).split('|').map((c) => c.trim()));
    }
    out.set(title, rows);
  }
  return out;
}

/**
 * 一段文字里“能在插件里核对”的工具引用，返回 [{ ref, target }]，target 是它在插件里应当存在的相对路径。
 * 认五种写法：相对链接、product-dev:<名>（内部技能或子代理）、<插件根>/ 路径、
 * 装进项目后的闸门脚本 scripts/engineering/gate/*、装进项目后的模板 docs/_templates/*。
 */
export function toolRefs(text) {
  const refs = [];
  for (const m of text.matchAll(/\]\(([^)\s#]+)(#[^)\s]*)?\)/g)) {
    if (/^[a-z][a-z0-9+.-]*:/i.test(m[1])) continue;
    refs.push({ ref: m[1], target: path.posix.normalize(path.posix.join(ENTRY_DIR, m[1])) });
  }
  for (const m of text.matchAll(/product-dev:([a-z][a-z0-9-]*)/g)) {
    const target = [`agents/${m[1]}.md`, `skills/${m[1]}/SKILL.md`].find(has) || `agents/${m[1]}.md`;
    refs.push({ ref: m[0], target });
  }
  for (const m of text.matchAll(/<插件根>\/([\w./-]+)/g)) refs.push({ ref: m[0], target: m[1].replace(/\/$/, '') });
  for (const m of text.matchAll(/scripts\/engineering\/gate\/([\w-]+\.mjs)/g)) refs.push({ ref: m[0], target: `skills/engineering-kit/kit/gate/${m[1]}` });
  for (const m of text.matchAll(/docs\/_templates\/([\w-]+\.md)/g)) refs.push({ ref: m[0], target: `skills/engineering-kit/kit/templates/docs/templates/${m[1]}` });
  return refs;
}

test('步骤齐全：导图里的步骤入口里都有，次序一致，四栏都写了内容', () => {
  const rows = stepRows(ENTRY);
  let count = 0;
  for (const [prefix, names] of Object.entries(STEPS)) {
    const title = [...rows.keys()].find((t) => t.startsWith(prefix));
    assert.ok(title, `入口里没有“${prefix}”一节的步骤表`);
    assert.deepEqual(rows.get(title).map((r) => r[0]), names, `“${title}”的步骤与导图不一致`);
    for (const cells of rows.get(title)) {
      assert.equal(cells.length, COLUMNS.length, `${cells[0]} 的栏数不是 ${COLUMNS.length}`);
      cells.forEach((c, i) => assert.ok(c.replace(/[\s—\-–]/g, '').length >= 4, `${cells[0]} 的“${COLUMNS[i]}”一栏是空的`));
      count += 1;
    }
  }
  assert.equal(count, 31, '步骤总数不是导图里的 31 步');
  assert.equal([...rows.keys()].length, Object.keys(STEPS).length, '入口里有清单之外的步骤表');
});

test('工具落地：每一步的工具都指向插件里存在的文件、子代理或脚本', () => {
  const missing = [];
  const ungrounded = [];
  for (const rows of stepRows(ENTRY).values()) {
    for (const cells of rows) {
      const refs = toolRefs(cells[3]);
      if (!refs.length) ungrounded.push(cells[0]);
      for (const { ref, target } of refs) if (!has(target)) missing.push(`${cells[0]}：${ref} → ${target}`);
      // 只有 Claude Code 才有的内置命令不能写进步骤的工具栏
      assert.doesNotMatch(cells[3], /\/(simplify|code-review|security-review)\b/, `${cells[0]} 的工具栏用了只有 Claude Code 才有的命令`);
    }
  }
  assert.deepEqual(ungrounded, [], '这些步骤的工具栏没有一个能在插件里核对的部件');
  assert.deepEqual(missing, []);
  // 步骤表之外（约定、分流、缩短路线等）提到的部件同样要存在
  assert.deepEqual(toolRefs(ENTRY).filter((r) => !has(r.target)).map((r) => `${r.ref} → ${r.target}`), []);
  assert.ok(toolRefs(ENTRY).length >= 60, '没有从入口里解析到工具引用');
});

test('工具落地：入口点名的方法文档小节和步骤号都存在，六份方法文档都被入口用到', () => {
  const bad = [];
  // 例：[process.md](references/process.md) 的“开工”、[process.md](references/process.md)“收工”
  for (const m of ENTRY.matchAll(/\]\(references\/([\w-]+)\.md\)[^“|\n]{0,3}“([^”]+)”/g)) {
    const headings = read(`${ENTRY_DIR}/references/${m[1]}.md`).split('\n').filter((l) => /^#{2,3} /.test(l)).map((l) => l.replace(/^#+ (\d+\. )?/, ''));
    if (!headings.includes(m[2])) bad.push(`${m[1]}.md 没有“${m[2]}”这一节`);
  }
  for (const m of ENTRY.matchAll(/\]\(references\/debugging\.md\) 第 ([\d、]+) 步/g)) {
    for (const n of m[1].split('、')) if (!read(`${ENTRY_DIR}/references/debugging.md`).includes(`### 第 ${n} 步`)) bad.push(`debugging.md 没有第 ${n} 步`);
  }
  assert.deepEqual(bad, []);
  assert.ok([...ENTRY.matchAll(/\]\(references\/[\w-]+\.md\)[^“|\n]{0,3}“/g)].length >= 8, '没有解析到对方法文档小节的引用');
  const steps = [...stepRows(ENTRY).values()].flat().map((c) => c[3]).join('\n');
  for (const name of REFS) assert.ok(steps.includes(`(references/${name}.md)`), `没有哪一步用到 ${name}.md`);
  assert.deepEqual(fs.readdirSync(path.join(PLUGIN, ENTRY_DIR, 'references')).sort(), REFS.map((n) => `${n}.md`).sort());
});

test('授权口径：分流和装工程底座写明受 R2 约束，可选加强单列，纪律不复述规则原文', () => {
  const line = (key) => ENTRY.split('\n').find((l) => l.includes(key)) || '';
  assert.match(line('先说判断'), /R2/, '分流的“先说判断”没有写明按 R2');
  for (const key of ['可以直接做', '先得到批准']) assert.ok(line(key), `分流没有写“${key}”`);
  assert.match(line('装工程底座的授权'), /R2/);
  assert.match(line('装工程底座的授权'), /R6/, '装工程底座没有写明在项目根之外新建目录按 R6');
  assert.ok(!/不等确认|直接开始，不/.test(ENTRY), '入口里还有不受 R2 约束的“直接开始”');
  // 内置命令只出现在“可选加强”一条里
  const builtin = ENTRY.split('\n').filter((l) => /`\/(simplify|code-review|security-review)`/.test(l));
  assert.equal(builtin.length, 1);
  assert.match(builtin[0], /可选加强.*不能代替/);
  // R2 原文里的整句不应出现在入口里（只引用编号）
  const r2 = read('skills/engineering-kit/kit/rules/AGENTS.block.md').split('\n').find((l) => l.startsWith('- R2 '));
  for (const sent of r2.split(/[。；]/).map((s) => s.trim()).filter((s) => s.length >= 20)) assert.ok(!ENTRY.includes(sent), `入口复述了 R2 的原文：${sent.slice(0, 20)}`);
  assert.match(ENTRY, /## 用户授权“按推荐执行”后怎么推进/);
});

test('受控的值：方法文档里的默认值与套件配置一致，常规动作一句没有丢', () => {
  const review = read(`${ENTRY_DIR}/references/review.md`);
  const proc = read(`${ENTRY_DIR}/references/process.md`);
  assert.ok(review.includes(`默认 ${DEFAULTS.reviewMinChars}`), '复审报告最短字数与套件默认值不一致');
  assert.ok(review.includes(`不少于 ${DEFAULTS.reviewMinChars} 字`), '任务书里的最短字数与套件默认值不一致');
  assert.ok(review.includes(`默认是“${DEFAULTS.reviewKeyword}”`) && review.includes(`## ${DEFAULTS.reviewKeyword}`), '报告格式里没有套件要求的关键词一节');
  for (const name of DEFAULTS.reviewers) assert.ok(review.includes(`\`${name}\``), `review.md 没有列出默认复审者 ${name}`);
  assert.ok(proc.includes(`\`${DEFAULTS.reviewFlow}\`（默认）`), '默认复审流程与套件默认值不一致');
  for (const stage of LAYOUT_DEFAULTS.stages) assert.ok(proc.includes(`\`${stage}\``), `process.md 的阶段目录缺 ${stage}`);
  assert.ok(proc.includes('推送功能分支、合并（经合并入口）、构建、预发部署属于常规动作'));
  for (const cmd of ['review.mjs pass|fail --reviewer', '--kind code', '--kind consistency', 'review.mjs defer --pr', 'merge.mjs <编号>']) assert.ok(proc.includes(cmd), `process.md 缺复审流程的命令：${cmd}`);
});

test('出处：改写的方法文档文末注明来源，第三方声明、组件清单、README 与之相符', () => {
  const notices = read('THIRD_PARTY_NOTICES.md');
  const components = fs.readFileSync(path.join(ROOT, 'COMPONENTS.md'), 'utf8');
  const readme = fs.readFileSync(path.join(ROOT, 'README.md'), 'utf8');
  const sources = {
    ponytail: { url: 'https://github.com/DietrichGebert/ponytail', copyright: 'Copyright (c) 2026 DietrichGebert', docs: ['build', 'self-review'] },
    'agent-skills': { url: 'https://github.com/addyosmani/agent-skills', copyright: 'Copyright (c) 2025 Addy Osmani', docs: ['planning', 'build', 'debugging', 'review'] },
  };
  for (const [name, s] of Object.entries(sources)) {
    const section = notices.split(/^## /m).find((x) => new RegExp(`^\\d+\\. ${name}$`).test(x.split('\n')[0]));
    assert.ok(section, `第三方声明里没有 ${name} 一节`);
    const row = components.split('\n').find((l) => l.startsWith(`| ${name} |`));
    assert.ok(row, `COMPONENTS.md 里没有 ${name}`);
    const version = row.split('|')[3].trim().split('（')[0];
    for (const text of [s.url, `版本：${version}`, '原许可：MIT', s.copyright, '我们的改动：']) assert.ok(section.includes(text), `第三方声明的 ${name} 一节缺：${text}`);
    assert.ok(row.includes('已收录（改写）'), `COMPONENTS.md 里 ${name} 没有标为已收录`);
    assert.ok(readme.includes(`[${name}](${s.url}) ${version}`), `README 的收录表里没有 ${name} ${version}`);
    for (const doc of s.docs) {
      const tail = read(`${ENTRY_DIR}/references/${doc}.md`).split('\n---\n').pop();
      for (const text of ['出处：', s.url, version, 'MIT 许可', s.copyright, '改动：', 'THIRD_PARTY_NOTICES.md']) assert.ok(tail.includes(text), `${doc}.md 文末的出处缺：${text}`);
      assert.ok(section.includes(`references/${doc}.md`), `第三方声明的 ${name} 一节没有列 ${doc}.md`);
    }
  }
  const version = JSON.parse(read('.claude-plugin/plugin.json')).version;
  assert.ok(components.includes(`${version}：`) && readme.includes(`（${version}）`), `COMPONENTS.md 或 README 里的插件版本不是 ${version}`);
  assert.ok(!/存放在维护者本机|计划：/.test(components), 'COMPONENTS.md 还留着旧说法');
});
