'use strict';
// Read-only adapter: Python supplies fabricated inputs and independent expectations.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const standalone = require(path.join(root, 'engine.js'));
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const start = html.indexOf('/* LIFE Financial Studio');
const marker = "})(typeof window!=='undefined'?window:globalThis);";
const end = html.indexOf(marker, start);
if (start < 0 || end < start) throw Error('Embedded engine missing');
const context = vm.createContext({});
vm.runInContext(html.slice(start, end + marker.length), context, {timeout:10000});
const permitted = new Set(['settleAssets', 'mortgageSchedule', 'education', 'calculate', 'yearlyAllowance']);
const requests = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(requests.map(request => {
  if (!permitted.has(request.method)) throw Error('Unsupported probe method');
  const call = engine => {
    try { return {value:engine[request.method](...request.args)}; }
    catch (error) { return {error:String(error.message)}; }
  };
  return {standalone:call(standalone), embedded:call(context.LifeEngine)};
})));
