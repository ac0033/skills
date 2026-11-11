// 市场入口的独立校验：双宿主身份与来源一致，发布标签的真实插件版本和入口可用。
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {test} from 'node:test';
const root=new URL('../',import.meta.url);
const read=p=>fs.readFileSync(new URL(p,root),'utf8');
const claude=JSON.parse(read('.claude-plugin/marketplace.json'));
const codex=JSON.parse(read('.agents/plugins/marketplace.json'));
test('保留市场及插件身份，两宿主声明同一发布版本和来源',()=>{
  assert.equal(claude.name,'ac0033-skills'); assert.equal(codex.name,claude.name);
  assert.deepEqual(claude.plugins.map(p=>p.name),codex.plugins.map(p=>p.name));
  assert.ok(claude.plugins.some(p=>p.name==='product-dev'));
  for(const p of claude.plugins){
    const other=codex.plugins.find(x=>x.name===p.name);
    assert.equal(other.version,p.version); assert.deepEqual(other.source,p.source);
    assert.equal(p.source.source,'git-subdir');
    assert.match(p.source.url,/^https:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+\.git$/);
    assert.match(p.source.path,/^[a-zA-Z0-9_-]+(?:\/[a-zA-Z0-9_-]+)*$/);
    assert.match(p.source.ref,/^v\d+\.\d+\.\d+$/);
    assert.equal(p.source.ref,'v'+p.version);
    assert.ok(read('README.md').includes(p.source.url.replace(/\.git$/,'')),p.name+' 缺少导航');
  }
});
test('来源标签存在，真实清单版本、名称和入口资源匹配',async()=>{
  for(const p of claude.plugins){
    const repo=p.source.url.match(/github\.com\/(.*)\.git$/)[1];
    const base='https://raw.githubusercontent.com/'+repo+'/'+p.source.ref+'/'+p.source.path+'/';
    const fetchText=async rel=>{
      let last;
      for(let attempt=0;attempt<3;attempt++){
        try { const r=await fetch(base+rel,{signal:AbortSignal.timeout(20000)}); assert.equal(r.status,200,base+rel); return await r.text(); }
        catch(e){last=e;}
      }
      throw last;
    };
    const [a,b]=await Promise.all(['.claude-plugin/plugin.json','.codex-plugin/plugin.json'].map(async rel=>JSON.parse(await fetchText(rel))));
    for(const m of [a,b]){assert.equal(m.name,p.name);assert.equal(m.version,p.version);}
    assert.equal(b.skills,'./skills/product-dev/');
    assert.match(await fetchText('skills/product-dev/SKILL.md'),/^name: product-dev$/m);
    assert.ok((await fetchText('skills/engineering-kit/kit/sync.mjs')).includes('export function syncKit'));
    assert.ok((await fetchText('agents/code-reviewer.md')).includes('code-reviewer'));
  }
});
