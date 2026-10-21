'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('index.html','utf8');
const engine=fs.readFileSync('engine.js','utf8');
const marker='})(typeof window!==\'undefined\'?window:globalThis);';
const a=html.indexOf('/* LIFE Financial Studio'),b=html.indexOf(marker,a);

test('配布HTMLに単一エンジンが埋め込まれ、ソースと一致する',()=>{
  assert.ok(a>=0 && b>a);assert.equal(html.slice(a,b+marker.length), engine.trim());
});
test('計算エンジンは読み込める',()=>{
  const ctx=vm.createContext({console});vm.runInContext(engine,ctx,{timeout:10000});
  assert.equal(typeof ctx.LifeEngine.calculate,'function');
  assert.equal(typeof ctx.LifeEngine.education,'function');
  assert.equal(typeof ctx.LifeEngine.mortgageSchedule,'function');
});
test('資金が不足したら借入と負の純資産を記録',()=>{
  const ctx=vm.createContext({console});vm.runInContext(engine,ctx,{timeout:10000});
  const actual=ctx.LifeEngine.settleAssets(100,0,-250,0,0);
  assert.equal(actual.debt,150);assert.equal(actual.total,-150);
});
test('公開アプリにGemini APIキー・外部スクリプトが埋まっていない',()=>{
  assert.ok(!/AIza[0-9A-Za-z_-]{25,}/.test(html),'API key found');
  assert.ok(!/<script\s+[^>]*src\s*=/i.test(html),'external script');
});

test('教育費専用画面は公表根拠と未確認費用の扱いを示す',()=>{
  const page=fs.readFileSync('education-reserve.html','utf8');
  assert.match(page,/教育費の安心準備額/);
  assert.match(page,/未完成/);
  assert.match(page,/university/);
  assert.match(page,/costs\/official_sources\.json/);
  assert.match(html,/education-reserve\.html/);
});
