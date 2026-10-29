'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const Q = require('../web/js/quote.js');
const trucks = Object.freeze([
  Object.freeze({maxT:40,rate:100,name:'Трал 40 т'}),
  Object.freeze({maxT:60,rate:140,name:'Трал 60 т'})
]);
function unit(mass, cat='exc', price=1350) {
  return {id:'machine',cat,price,unit:'год',specs:mass == null ? [] : [{k:'Маса',v:mass + ' т'}]};
}
test('known price: one calculation, no fabricated delivery', () => {
  const q=Q.quote(unit(22),trucks,10,20);
  assert.equal(q.total,15500); assert.equal(q.delivery,2000);
  assert.equal(q.status,'complete'); assert.equal(q.reason,null);
  assert.equal(Q.legacyTotal(unit(22),trucks,10,20),15500);
});
test('unknown mass, crane, and out-of-capacity costs must be partial', () => {
  assert.deepEqual([Q.quote(unit(null),trucks,2,20).status, Q.quote(unit(80),trucks,2,20).reason],['rent-only','capacity-exceeded']);
  assert.equal(Q.quote(unit(null),trucks,2,20).delivery,null);
  assert.equal(Q.quote(unit(null),trucks,2,20).total,null);
  assert.equal(Q.legacyTotal(unit(null),trucks,2,20),null);
  assert.equal(Q.quote(unit(null,'crane'),trucks,2,20).reason,'crane-arrival');
  assert.equal(Q.legacyTotal(unit(null,'crane'),trucks,2,20),2700);
  assert.equal(Q.quote(unit(null),trucks,2,0).total,2700);
});
test('strict boundaries and mass parsing cannot be gamed', () => {
  for(const [h,km] of [[0,0],[-1,1],[1,-1],[5001,1],[1,3001],[1.1,0],[NaN,0],[1,Infinity],[1,'2']]) {
    assert.equal(Q.quote(unit(22),trucks,h,km),null,String(h)+','+String(km));
  }
  for(const s of [[{k:'Маса',v:'22 т'},{k:'Вага',v:'30 т'}],[{k:'Маса',v:'4, 6, 12, 18 т'}],[]]){
    assert.equal(Q.massTonnes(s),null);
  }
  assert.equal(Q.massTonnes([{k:'Маса',v:'22,5 т'}]),22.5);
  assert.equal(Q.massTonnes([{k:'Вага',v:'31 т'}]),31);
});
test('tariff configuration is immutable and order-independent', () => {
  const front=Q.quote(unit(22),trucks,2,15);
  const back=Q.quote(unit(22),trucks.slice().reverse(),2,15);
  assert.deepEqual(front,back);
  assert.deepEqual(trucks.map(t=>t.maxT),[40,60]);
  assert(Object.isFrozen(front)); assert(Object.isFrozen(front.trailer));
  assert.equal(Q.quote(unit(22),[{name:'X',maxT:40,rate:NaN}],2,10).reason,'tariff-invalid');
});
test('seeded monotonicity / deterministic oracle: 2000 property cases', () => {
  let seed=0x917a209d;
  const rand=()=>((seed=Math.imul(seed,1664525)+1013904223|0)>>>0);
  for(let n=0;n<2000;n++) {
    const m=1+(rand()%61),h=1+(rand()%500),km=rand()%200;
    const u=unit(m);
    const a=Q.quote(u,trucks,h,km),b=Q.quote(u,trucks,h+1,km);
    assert.deepEqual(a,Q.quote(u,trucks,h,km));
    if(a.status==='complete') {
      assert.equal(b.total-a.total,u.price);
      assert.equal(a.displayed,a.total);
      assert.equal(Q.legacyTotal(u,trucks,h,km),a.total);
    } else {
      assert.equal(a.total,null);
      assert.equal(a.delivery,null);
    }
  }
});
